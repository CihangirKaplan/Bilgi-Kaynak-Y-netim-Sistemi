"""Gerçek PostgreSQL: EXPORT denetim olayı, liste aktarım kaydı yetkisi ve sistem durumu."""
import os
from datetime import datetime
from uuid import uuid4

import psycopg2
import pytest
from fastapi import HTTPException

from server import sistem_durumu as sd
from server.sunucu import (
    VT_AYARLARI,
    ListeAktarimModeli,
    liste_aktarim_kaydi,
    sistem_durumu_getir,
    surum_bilgisi,
)


@pytest.fixture
def kullanicilar():
    assert os.getenv("TKYS_PG_TEST_ONAY") == "EVET"
    assert VT_AYARLARI["dbname"] == "crkys_alembic_test"
    conn = psycopg2.connect(**VT_AYARLARI)
    conn.autocommit = True
    c = conn.cursor()
    etiket = uuid4().hex[:8]
    k = {}
    for ad, rol in (("admin", "ADMIN"), ("psikolog", "PSIKOLOG")):
        c.execute("INSERT INTO kullanicilar (kullanici_adi, parola_hash, rol_id) VALUES (%s, 'x', (SELECT rol_id FROM roller WHERE rol_adi = %s)) RETURNING kullanici_id",
                  (f"sp_{ad}_{etiket}", rol))
        k[ad] = c.fetchone()[0]
    yield k, c
    ids = tuple(k.values())
    c.execute("DELETE FROM denetim_kayitlari WHERE kullanici_id IN %s", (ids,))
    c.execute("DELETE FROM kullanicilar WHERE kullanici_id IN %s", (ids,))
    conn.close()


def test_export_olayi_enum_icinde(kullanicilar):
    _, c = kullanicilar
    c.execute("SELECT 'EXPORT'::text = ANY(enum_range(NULL::denetim_olay_turu)::text[])")
    assert c.fetchone()[0] is True


def test_aktarim_kaydi_denetime_yazilir(kullanicilar):
    k, c = kullanicilar
    assert liste_aktarim_kaydi(ListeAktarimModeli(liste="OGRENCI", satir_sayisi=42), kullanici_id=k["admin"]) == {"durum": "basarili"}
    c.execute("SELECT olay_turu::text, hedef_tablo, ayrinti FROM denetim_kayitlari WHERE kullanici_id = %s", (k["admin"],))
    olay, tablo, ayrinti = c.fetchone()
    assert (olay, tablo) == ("EXPORT", "ogrenciler")
    assert ayrinti == {"liste": "OGRENCI", "satir_sayisi": 42}


def test_aktarim_kaydi_pdf_bicimini_denetime_yazar_excelde_eski_bicim_kalir(kullanicilar):
    k, c = kullanicilar
    liste_aktarim_kaydi(ListeAktarimModeli(liste="OGRENCI", satir_sayisi=3, bicim="PDF"), kullanici_id=k["admin"])
    liste_aktarim_kaydi(ListeAktarimModeli(liste="OGRENCI", satir_sayisi=4), kullanici_id=k["admin"])
    c.execute("SELECT ayrinti FROM denetim_kayitlari WHERE kullanici_id = %s AND olay_turu::text = 'EXPORT' ORDER BY denetim_id", (k["admin"],))
    assert [r[0] for r in c.fetchall()] == [{"liste": "OGRENCI", "satir_sayisi": 3, "bicim": "PDF"}, {"liste": "OGRENCI", "satir_sayisi": 4}]


def test_aktarim_kaydi_listeyi_gorme_yetkisi_ister(kullanicilar):
    k, c = kullanicilar
    with pytest.raises(HTTPException) as hata:                       # psikolog öğrenci listesini göremez
        liste_aktarim_kaydi(ListeAktarimModeli(liste="OGRENCI", satir_sayisi=1), kullanici_id=k["psikolog"])
    assert hata.value.status_code == 403
    c.execute("SELECT COUNT(*) FROM denetim_kayitlari WHERE kullanici_id = %s AND olay_turu::text = 'EXPORT'", (k["psikolog"],))
    assert c.fetchone()[0] == 0


@pytest.mark.parametrize("liste,tablo", [
    ("REZERVASYON", "cihaz_rezervasyonlari"), ("BAKIM", "cihaz_bakimlari"), ("KALIBRASYON", "cihaz_kalibrasyonlari"),
    ("ARIZA", "cihaz_arizalari"), ("BAKIM_PLANI", "cihaz_bakim_planlari"),
])
def test_cihaz_listeleri_aktarimi_denetime_yazilir_ve_izin_ister(kullanicilar, liste, tablo):
    k, c = kullanicilar
    assert liste_aktarim_kaydi(ListeAktarimModeli(liste=liste, satir_sayisi=3), kullanici_id=k["admin"]) == {"durum": "basarili"}
    c.execute("SELECT hedef_tablo, ayrinti FROM denetim_kayitlari WHERE kullanici_id = %s AND olay_turu::text = 'EXPORT' ORDER BY denetim_id DESC", (k["admin"],))
    assert c.fetchone() == (tablo, {"liste": liste, "satir_sayisi": 3})
    with pytest.raises(HTTPException) as hata:                       # psikolog cihaz yönetim listelerini göremez
        liste_aktarim_kaydi(ListeAktarimModeli(liste=liste, satir_sayisi=1), kullanici_id=k["psikolog"])
    assert hata.value.status_code == 403


def test_surum_ve_sema_surumu(kullanicilar):
    k, c = kullanicilar
    bilgi = surum_bilgisi(kullanici_id=k["psikolog"])
    c.execute("SELECT version_num FROM alembic_version")
    assert bilgi["sema_surumu"] == c.fetchone()[0] and bilgi["surum"]


def test_sistem_durumu_alanlari_ve_yedek(kullanicilar, tmp_path):
    k, c = kullanicilar
    # son girişler: yeni bir LOGIN kaydı listede görünür
    c.execute("INSERT INTO denetim_kayitlari (kullanici_id, olay_turu, hedef_tablo, hedef_kayit_id) VALUES (%s, 'LOGIN', 'kullanicilar', %s)", (k["admin"], k["admin"]))
    simdi = datetime.now()
    db = VT_AYARLARI["dbname"]
    (tmp_path / f"{db}_20200101_010101_000001.dump").write_bytes(b"x" * 10)
    (tmp_path / f"{db}_{simdi:%Y%m%d_%H%M%S}_000002.dump").write_bytes(b"y" * 2048)
    (tmp_path / "baska_20300101_010101_000001.dump").write_bytes(b"z")          # başka veritabanının yedeği sayılmaz
    conn = psycopg2.connect(**VT_AYARLARI)
    try:
        durum = sd.sistem_durumu(conn.cursor(), db, klasor=tmp_path)
    finally:
        conn.close()
    assert set(durum) >= {"surum", "sema_surumu", "veritabani_boyutu_mb", "yedek", "son_girisler", "basarisiz_giris_24s", "sayilar", "oturum_suresi_dk"}
    assert durum["yedek"]["var"] and durum["yedek"]["adet"] == 2 and not durum["yedek"]["eski"]
    assert any(g["kullanici_adi"].startswith("sp_admin_") for g in durum["son_girisler"])
    assert all(isinstance(v, int) for v in durum["sayilar"].values())
    assert "parola" not in str(durum).lower() and str(tmp_path) not in str(durum)        # yol/parola sızmaz


def test_sistem_durumu_ucu_yonetici_izni_ister(kullanicilar):
    from fastapi.testclient import TestClient

    from server.sunucu import app, mevcut_kullanici_id
    k, _ = kullanicilar
    istemci = TestClient(app)
    try:
        app.dependency_overrides[mevcut_kullanici_id] = lambda: k["psikolog"]
        assert istemci.get("/api/sistem-durumu").status_code == 403           # psikolog görmez
        assert istemci.get("/api/surum").status_code == 200                   # sürüm herkese açık (giriş yapmış)
        app.dependency_overrides[mevcut_kullanici_id] = lambda: k["admin"]
        yanit = istemci.get("/api/sistem-durumu")
        assert yanit.status_code == 200 and yanit.json()["yedek"]["var"] in (True, False)
        assert istemci.post("/api/liste-aktarim-kaydi", json={"liste": "YOK", "satir_sayisi": 1}).status_code == 422
        assert istemci.post("/api/liste-aktarim-kaydi", json={"liste": "CIHAZ", "satir_sayisi": -1}).status_code == 422
    finally:
        app.dependency_overrides.pop(mevcut_kullanici_id, None)
