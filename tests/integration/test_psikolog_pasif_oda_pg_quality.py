"""Gerçek PostgreSQL: psikolog pasife alınınca oda atamaları kalkar (geçmiş randevular kalır); aktifleşirken oda seçilir.

- Bugünden sonra planlı randevusu olan psikolog pasife alınamaz (409); geçmişte kalan "Planlandı" kayıt engellemez
- Pasifleşince psikolog_odalar temizlenir, randevular ve oda_id'leri aynen kalır
- Aktifleşirken oda zorunlu; cihaz rezervasyonlu oda reddedilir; seçilen odalar yazılır

CI'daki "PostgreSQL Entegrasyon Testleri" işinde (alembic upgrade head sonrası) çalışır; gerçek kayıt oluşturur, sonunda temizler.
"""
import os
from datetime import datetime, timedelta
from uuid import uuid4

import psycopg2
import pytest
from fastapi.testclient import TestClient

from server.sunucu import VT_AYARLARI, app, mevcut_kullanici_id


def _dogru_veritabani(cursor):
    assert os.getenv("TKYS_PG_TEST_ONAY") == "EVET"
    assert VT_AYARLARI["dbname"] == "crkys_alembic_test"
    cursor.execute("SELECT current_database()")
    assert cursor.fetchone()[0] == "crkys_alembic_test"


def _kullanici(cursor, ad, rol):
    cursor.execute("INSERT INTO kullanicilar (kullanici_adi, parola_hash, rol_id) VALUES (%s, 'x', (SELECT rol_id FROM roller WHERE rol_adi = %s)) RETURNING kullanici_id", (ad, rol))
    return cursor.fetchone()[0]


@pytest.fixture
def ortam():
    etiket = uuid4().hex[:10]
    conn = psycopg2.connect(**VT_AYARLARI)
    conn.autocommit = True
    c = conn.cursor()
    _dogru_veritabani(c)
    admin = _kullanici(c, f"pa_{etiket}", "ADMIN")
    psikolog = _kullanici(c, f"pp_{etiket}", "PSIKOLOG")
    c.execute("INSERT INTO personel (kullanici_id, personel_kodu) VALUES (%s, %s) RETURNING personel_id", (psikolog, f"PO-{etiket}"))
    personel = c.fetchone()[0]
    odalar = []
    for ad in ("a", "b"):
        c.execute("INSERT INTO odalar (oda_adi, kapasite) VALUES (%s, 1) RETURNING oda_id", (f"pp_oda_{ad}_{etiket}",))
        odalar.append(c.fetchone()[0])
        c.execute("INSERT INTO psikolog_odalar (kullanici_id, oda_id) VALUES (%s, %s)", (psikolog, odalar[-1]))
    kod = f"PO-{etiket}-1"
    c.execute("INSERT INTO danisan_kodlari (danisan_kod_id, olusturan_psikolog_id) VALUES (%s, %s)", (kod, personel))
    c.execute("INSERT INTO cihazlar (envanter_kodu, cihaz_adi, durum) VALUES (%s, %s, 'Kullanima_Hazir') RETURNING cihaz_id", (f"PO-{etiket}", f"pp_cihaz_{etiket}"))
    cihaz = c.fetchone()[0]
    try:
        yield c, admin, psikolog, personel, odalar, kod, cihaz
    finally:
        app.dependency_overrides.pop(mevcut_kullanici_id, None)
        c.execute("DELETE FROM randevular WHERE danisan_kod_id = %s", (kod,))
        c.execute("DELETE FROM cihaz_rezervasyonlari WHERE cihaz_id = %s", (cihaz,))
        c.execute("DELETE FROM cihazlar WHERE cihaz_id = %s", (cihaz,))
        c.execute("DELETE FROM danisan_kodlari WHERE danisan_kod_id = %s", (kod,))
        c.execute("DELETE FROM psikolog_odalar WHERE kullanici_id = %s", (psikolog,))
        c.execute("DELETE FROM denetim_kayitlari WHERE kullanici_id = ANY(%s)", ([admin, psikolog],))
        c.execute("DELETE FROM odalar WHERE oda_id = ANY(%s)", (odalar,))
        c.execute("DELETE FROM personel WHERE personel_id = %s", (personel,))
        c.execute("DELETE FROM kullanicilar WHERE kullanici_id = ANY(%s)", ([admin, psikolog],))
        conn.close()


def _randevu(c, kod, personel, oda, baslangic, durum="PLANLANDI"):
    c.execute("INSERT INTO randevular (danisan_kod_id, psikolog_id, oda_id, baslangic_zamani, bitis_zamani, durum, gorusme_tipi, terapi_turu) "
              "VALUES (%s, %s, %s, %s, %s, %s, 'YUZ_YUZE', 'BIREYSEL_TERAPI') RETURNING randevu_id",
              (kod, personel, oda, baslangic, baslangic + timedelta(hours=1), durum))
    return c.fetchone()[0]


def _durum(c, psikolog):
    c.execute("SELECT k.aktif_mi, p.aktif_mi FROM kullanicilar k JOIN personel p ON p.kullanici_id = k.kullanici_id WHERE k.kullanici_id = %s", (psikolog,))
    return c.fetchone()


def _atanmis(c, psikolog):
    c.execute("SELECT oda_id FROM psikolog_odalar WHERE kullanici_id = %s ORDER BY oda_id", (psikolog,))
    return [k[0] for k in c.fetchall()]


def test_psikolog_pasife_alinirken_ve_aktiflesirken_odalar_gercek_veritabaninda(ortam):
    c, admin, psikolog, personel, (oda_a, oda_b), kod, cihaz = ortam
    istemci = TestClient(app)
    app.dependency_overrides[mevcut_kullanici_id] = lambda: admin
    degistir = lambda **govde: istemci.patch(f"/api/kullanicilar/{psikolog}/durum-degistir", **({"json": govde} if govde else {}))
    gelecek = datetime.now() + timedelta(days=3)

    # 1) bugünden sonra planlı randevu varsa pasife alınamaz
    gelecek_randevu = _randevu(c, kod, personel, oda_a, gelecek)
    yanit = degistir()
    assert yanit.status_code == 409 and "1 planlı randevusu var" in yanit.json()["detail"]
    assert _durum(c, psikolog) == (True, True) and _atanmis(c, psikolog) == [oda_a, oda_b]

    # 2) iptal edilince ve geçmişte kalan "Planlandı" kaydı engel olmaz; pasife alınır, odalar kalkar, randevular kalır
    c.execute("UPDATE randevular SET durum = 'IPTAL_EDILDI' WHERE randevu_id = %s", (gelecek_randevu,))
    eski_planli = _randevu(c, kod, personel, oda_b, datetime.now() - timedelta(days=5))
    yanit = degistir()
    assert yanit.status_code == 200 and yanit.json()["yeni_durum"] is False
    assert _durum(c, psikolog) == (False, False) and _atanmis(c, psikolog) == []
    c.execute("SELECT randevu_id, oda_id, psikolog_id FROM randevular WHERE danisan_kod_id = %s ORDER BY randevu_id", (kod,))
    assert c.fetchall() == [(gelecek_randevu, oda_a, personel), (eski_planli, oda_b, personel)]      # geçmiş kayıtlar ve oda bilgileri aynen
    c.execute("SELECT count(*) FROM denetim_kayitlari WHERE kullanici_id = %s AND hedef_tablo = 'psikolog_odalar' AND hedef_kayit_id = %s", (admin, psikolog))
    assert c.fetchone()[0] == 1

    # 3) aktifleştirirken oda seçilmeli
    assert degistir().status_code == 422 and _durum(c, psikolog) == (False, False)
    assert degistir(oda_idleri=[]).status_code == 422

    # 4) cihaz rezervasyonlu oda seçilemez
    bas = datetime.now() + timedelta(days=2, hours=1)
    c.execute("INSERT INTO cihaz_rezervasyonlari (cihaz_id, kullanilacak_oda_id, baslangic_zamani, bitis_zamani) VALUES (%s, %s, %s, %s)", (cihaz, oda_a, bas, bas + timedelta(hours=1)))
    yanit = degistir(oda_idleri=[oda_a, oda_b])
    assert yanit.status_code == 409 and "psikologa atanamaz" in yanit.json()["detail"]
    assert _durum(c, psikolog) == (False, False) and _atanmis(c, psikolog) == []

    # 5) rezervasyonsuz oda ile aktifleşir; seçilen oda yazılır
    yanit = degistir(oda_idleri=[oda_b])
    assert yanit.status_code == 200 and yanit.json()["yeni_durum"] is True
    assert _durum(c, psikolog) == (True, True) and _atanmis(c, psikolog) == [oda_b]


def test_psikolog_adlari_pasifler_dahil_gercek_veritabaninda(ortam):
    """GET /api/psikologlar?pasifler_dahil=true: randevusu olan eski (başka role geçmiş) psikolog adıyla gelir, aktif_mi = false."""
    c, admin, psikolog, personel, (oda_a, oda_b), kod, cihaz = ortam
    etiket = uuid4().hex[:8]
    eski = _kullanici(c, f"eski_{etiket}", "MEMUR")
    sade = _kullanici(c, f"sade_{etiket}", "MEMUR")
    kayitlar = {}
    for ad, kullanici in (("eski", eski), ("sade", sade)):
        c.execute("INSERT INTO personel (kullanici_id, personel_kodu) VALUES (%s, %s) RETURNING personel_id", (kullanici, f"PA-{ad}-{etiket}"))
        kayitlar[ad] = c.fetchone()[0]
    try:
        _randevu(c, kod, kayitlar["eski"], oda_a, datetime.now() - timedelta(days=30), durum="TAMAMLANDI")     # geçmişte randevusu var
        istemci = TestClient(app)
        app.dependency_overrides[mevcut_kullanici_id] = lambda: admin

        varsayilan = {p["personel_id"] for p in istemci.get("/api/psikologlar").json()}
        assert personel in varsayilan and kayitlar["eski"] not in varsayilan                            # randevu formu: yalnızca aktif psikologlar

        liste = {p["personel_id"]: p for p in istemci.get("/api/psikologlar", params={"pasifler_dahil": "true"}).json()}
        assert liste[personel]["aktif_mi"] is True and liste[personel]["ad_soyad"].startswith("pp_")
        assert liste[kayitlar["eski"]] == {"personel_id": kayitlar["eski"], "ad_soyad": f"eski_{etiket}", "kullanici_id": eski, "aktif_mi": False}
        assert kayitlar["sade"] not in liste                                                            # geçmişi olmayan, psikolog olmayan gelmez

        c.execute("UPDATE kullanicilar SET aktif_mi = FALSE WHERE kullanici_id = %s", (psikolog,))     # pasif psikolog de adıyla gelir
        liste = {p["personel_id"]: p for p in istemci.get("/api/psikologlar", params={"pasifler_dahil": "true"}).json()}
        assert liste[personel]["aktif_mi"] is False and liste[personel]["ad_soyad"].startswith("pp_")
    finally:
        c.execute("DELETE FROM randevular WHERE psikolog_id = %s", (kayitlar["eski"],))
        c.execute("DELETE FROM personel WHERE personel_id = ANY(%s)", (list(kayitlar.values()),))
        c.execute("DELETE FROM kullanicilar WHERE kullanici_id = ANY(%s)", ([eski, sade],))
