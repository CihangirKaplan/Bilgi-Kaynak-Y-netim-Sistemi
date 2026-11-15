"""Gerçek PostgreSQL: sunucunun kısıtlı veritabanı kullanıcısı (scripts/uygulama_kullanicisi_olustur.py).

Bu test CI'daki "PostgreSQL Entegrasyon Testleri" işinde (alembic upgrade head sonrası) çalışır. Kısıtlı kullanıcı
oluşturulur; tablo silme/oluşturma, denetim kaydını değiştirme gibi yasak işlemler GERÇEKTEN reddediliyor mu, ve sunucu
bu kullanıcıyla gerçek istekleri (giriş, oda ekleme, listeleme, denetim kaydı) sorunsuz yapıyor mu denenir.
Biri sunucuya yönetici yetkisi gerektiren bir işlem eklerse (örn. çalışma anında CREATE TABLE) bu test kırmızı olur.
"""

import importlib.util
import os
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import psycopg2
import pytest
from fastapi.testclient import TestClient
from psycopg2 import errors, sql

from server.guvenlik import parola_hashle
from server.sunucu import VT_AYARLARI, app

KOK = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("uygulama_kullanicisi_olustur_pg", KOK / "scripts" / "uygulama_kullanicisi_olustur.py")
betik = importlib.util.module_from_spec(spec)
spec.loader.exec_module(betik)


def _dogru_veritabani(cursor):
    # Yanlış veritabanında çalışmayı kesinlikle engelle.
    assert os.getenv("TKYS_PG_TEST_ONAY") == "EVET"
    assert VT_AYARLARI["dbname"] == "crkys_alembic_test"
    cursor.execute("SELECT current_database()")
    assert cursor.fetchone()[0] == "crkys_alembic_test"


def _yonetici_baglantisi():
    return psycopg2.connect(**VT_AYARLARI)


def _kisitli_baglanti(rol, parola):
    return psycopg2.connect(**{**VT_AYARLARI, "user": rol, "password": parola})


@pytest.fixture(scope="module")
def kisitli_kullanici():
    """Betikle kısıtlı kullanıcı oluşturur; test bitince siler. (rol adı, parola) döndürür."""
    rol = f"tkys_pg_{uuid4().hex[:10]}"
    yonetici = _yonetici_baglantisi()
    try:
        with yonetici.cursor() as imlec:
            _dogru_veritabani(imlec)
        parola = betik.kullaniciyi_olustur(yonetici, VT_AYARLARI["dbname"], rol, VT_AYARLARI["user"])
        assert parola
        yield rol, parola
    finally:
        yonetici.rollback()
        with yonetici.cursor() as imlec:
            imlec.execute(sql.SQL("DROP OWNED BY {}").format(sql.Identifier(rol)))
            imlec.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(rol)))
        yonetici.commit()
        yonetici.close()


def _reddedilmeli(rol, parola, sorgu):
    """Kısıtlı kullanıcıyla çalıştırılan sorgu yetki hatasıyla reddedilmeli."""
    baglanti = _kisitli_baglanti(rol, parola)
    try:
        with baglanti.cursor() as imlec:
            with pytest.raises(errors.InsufficientPrivilege):
                imlec.execute(sorgu)
    finally:
        baglanti.rollback()
        baglanti.close()


def test_rol_kisitli_ozelliklerle_olusturuldu(kisitli_kullanici):
    rol, _ = kisitli_kullanici
    with _yonetici_baglantisi() as baglanti, baglanti.cursor() as imlec:
        imlec.execute(
            "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls, rolcanlogin "
            "FROM pg_roles WHERE rolname = %s", (rol,)
        )
        assert imlec.fetchone() == (False, False, False, False, False, True)


def test_veri_okuyup_yazabilir(kisitli_kullanici):
    rol, parola = kisitli_kullanici
    baglanti = _kisitli_baglanti(rol, parola)
    try:
        with baglanti.cursor() as imlec:
            imlec.execute("SELECT COUNT(*) FROM roller")
            assert imlec.fetchone()[0] > 0
            imlec.execute(
                "INSERT INTO odalar (oda_adi, kapasite, aktif_mi) VALUES (%s, 1, TRUE) RETURNING oda_id",
                (f"KisitliOda-{uuid4().hex[:6]}",),
            )
            oda_id = imlec.fetchone()[0]
            imlec.execute("UPDATE odalar SET kapasite = 2 WHERE oda_id = %s", (oda_id,))
            imlec.execute("DELETE FROM odalar WHERE oda_id = %s", (oda_id,))
        baglanti.commit()
    finally:
        baglanti.close()


def test_denetim_kaydina_yalnizca_ekleyebilir(kisitli_kullanici):
    rol, parola = kisitli_kullanici
    baglanti = _kisitli_baglanti(rol, parola)
    try:
        with baglanti.cursor() as imlec:
            imlec.execute("INSERT INTO denetim_kayitlari (olay_turu, hedef_tablo) VALUES ('CREATE', 'kisitli_kullanici_testi')")
            imlec.execute("SELECT COUNT(*) FROM denetim_kayitlari WHERE hedef_tablo = 'kisitli_kullanici_testi'")
            assert imlec.fetchone()[0] >= 1
        baglanti.commit()
    finally:
        baglanti.close()


@pytest.mark.parametrize("sorgu", [
    "UPDATE denetim_kayitlari SET hedef_tablo = 'x'",
    "DELETE FROM denetim_kayitlari",
    "TRUNCATE denetim_kayitlari",
])
def test_denetim_kaydini_degistiremez_silemez(kisitli_kullanici, sorgu):
    rol, parola = kisitli_kullanici
    _reddedilmeli(rol, parola, sorgu)


@pytest.mark.parametrize("sorgu", [
    "DROP TABLE kullanicilar",
    "ALTER TABLE kullanicilar ADD COLUMN kotu text",
    "CREATE TABLE kotu_tablo (a int)",
    "TRUNCATE kullanicilar CASCADE",
    "UPDATE alembic_version SET version_num = 'x'",
    "DELETE FROM alembic_version",
    "CREATE ROLE kotu_rol",
    "DROP TRIGGER denetim_kayitlari_degistirilemez ON denetim_kayitlari",
    "ALTER TABLE denetim_kayitlari DISABLE TRIGGER ALL",
])
def test_yonetici_islemleri_reddedilir(kisitli_kullanici, sorgu):
    rol, parola = kisitli_kullanici
    _reddedilmeli(rol, parola, sorgu)


def test_ileride_eklenen_tabloya_otomatik_yetki_alir(kisitli_kullanici):
    rol, parola = kisitli_kullanici
    tablo = f"gecici_{uuid4().hex[:8]}"
    yonetici = _yonetici_baglantisi()
    try:
        with yonetici.cursor() as imlec:
            imlec.execute(sql.SQL("CREATE TABLE {} (id serial PRIMARY KEY, ad text)").format(sql.Identifier(tablo)))
        yonetici.commit()

        baglanti = _kisitli_baglanti(rol, parola)
        try:
            with baglanti.cursor() as imlec:
                imlec.execute(sql.SQL("INSERT INTO {} (ad) VALUES ('a') RETURNING id").format(sql.Identifier(tablo)))
                assert imlec.fetchone()[0] == 1                      # sıra (sequence) kullanımı da çalışır
                imlec.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(tablo)))
                assert imlec.fetchone()[0] == 1
            baglanti.commit()
        finally:
            baglanti.close()
    finally:
        yonetici.rollback()
        with yonetici.cursor() as imlec:
            imlec.execute(sql.SQL("DROP TABLE IF EXISTS {}").format(sql.Identifier(tablo)))
        yonetici.commit()
        yonetici.close()


def test_betik_tekrar_calistirilabilir_ve_parolayi_degistirmez(kisitli_kullanici):
    rol, parola = kisitli_kullanici
    yonetici = _yonetici_baglantisi()
    try:
        assert betik.kullaniciyi_olustur(yonetici, VT_AYARLARI["dbname"], rol, VT_AYARLARI["user"]) is None
    finally:
        yonetici.close()
    _kisitli_baglanti(rol, parola).close()                          # eski parola hâlâ geçerli


def test_sunucu_kisitli_kullaniciyla_gercek_istekleri_yapar(kisitli_kullanici):
    """Giriş, yetki sorgusu, oda ekleme (satır + denetim kaydı + sıra), listeleme: hepsi kısıtlı kullanıcıyla."""
    rol, parola = kisitli_kullanici
    kullanici_adi = f"kisitli_{uuid4().hex[:8]}"
    sifre = "Kisitli!Parola2026x"

    yonetici = _yonetici_baglantisi()
    try:
        with yonetici.cursor() as imlec:
            imlec.execute("SELECT rol_id FROM roller WHERE rol_adi = 'ADMIN'")
            rol_id = imlec.fetchone()[0]
            imlec.execute(
                "INSERT INTO kullanicilar (kullanici_adi, parola_hash, rol_id, aktif_mi, ilk_giris_mi) "
                "VALUES (%s, %s, %s, TRUE, FALSE) RETURNING kullanici_id", (kullanici_adi, parola_hashle(sifre), rol_id),
            )
            kullanici_id = imlec.fetchone()[0]
            imlec.execute(                                         # giriş, kullanıcıya bağlı bir personel kaydı ister
                "INSERT INTO personel (kullanici_id, personel_kodu, aktif_mi) VALUES (%s, %s, TRUE)",
                (kullanici_id, f"PER-KST-{uuid4().hex[:6].upper()}"),
            )
        yonetici.commit()
    finally:
        yonetici.close()

    oda_adi = f"KisitliSunucuOda-{uuid4().hex[:6]}"
    with patch.dict(VT_AYARLARI, {"user": rol, "password": parola}):
        istemci = TestClient(app, raise_server_exceptions=False)
        giris = istemci.post("/api/login", json={"kullanici_adi": kullanici_adi, "parola": sifre})
        assert giris.status_code == 200, giris.text
        baslik = {"Authorization": "Bearer " + giris.json()["access_token"]}

        assert istemci.get("/api/yetkilerim", headers=baslik).status_code == 200
        olustur = istemci.post("/api/odalar", json={"oda_adi": oda_adi, "kapasite": 2}, headers=baslik)
        assert olustur.status_code == 201, olustur.text
        oda_id = olustur.json()["oda_id"]
        liste = istemci.get("/api/odalar", headers=baslik)
        assert liste.status_code == 200
        assert any(o.get("oda_adi") == oda_adi for o in liste.json())

    kontrol = _yonetici_baglantisi()
    try:
        with kontrol.cursor() as imlec:
            imlec.execute(
                "SELECT COUNT(*) FROM denetim_kayitlari WHERE hedef_tablo = 'odalar' AND hedef_kayit_id = %s", (oda_id,)
            )
            assert imlec.fetchone()[0] == 1                         # denetim kaydı kısıtlı kullanıcıyla yazıldı
    finally:
        kontrol.close()
