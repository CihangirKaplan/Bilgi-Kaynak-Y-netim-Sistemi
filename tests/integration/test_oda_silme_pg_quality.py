"""Gerçek PostgreSQL: odayı veritabanından kalıcı silme (Oda Yönetimi "Odayı Sil").

- Kaydı olmayan oda silinir; psikolog-oda atamaları odayla kalkar; denetim kaydı (DELETE) yazılır
- Odayı kullanan randevu (geçmiş ya da iptal edilmiş bile), cihaz rezervasyonu ya da oda etkinliği varsa 409; oda yerinde kalır
- Bir psikologun tek aktif odası silinemez (409); pasif odası silinebilir
- Olmayan oda 404

CI'daki "PostgreSQL Entegrasyon Testleri" işinde çalışır; gerçek kayıt oluşturur, sonunda temizler.
"""
import os
from datetime import datetime, timedelta
from uuid import uuid4

import psycopg2
import pytest
from fastapi import HTTPException

from server import oda_api
from server.sunucu import VT_AYARLARI


def _dogru_veritabani(cursor):
    assert os.getenv("TKYS_PG_TEST_ONAY") == "EVET"
    assert VT_AYARLARI["dbname"] == "crkys_alembic_test"
    cursor.execute("SELECT current_database()")
    assert cursor.fetchone()[0] == "crkys_alembic_test"


def _kullanici(c, ad, rol):
    c.execute("INSERT INTO kullanicilar (kullanici_adi, parola_hash, rol_id) VALUES (%s, 'x', (SELECT rol_id FROM roller WHERE rol_adi = %s)) RETURNING kullanici_id", (ad, rol))
    return c.fetchone()[0]


@pytest.fixture
def ortam():
    etiket = uuid4().hex[:10]
    conn = psycopg2.connect(**VT_AYARLARI)
    conn.autocommit = True
    c = conn.cursor()
    _dogru_veritabani(c)
    admin = _kullanici(c, f"os_a_{etiket}", "ADMIN")
    psikolog = _kullanici(c, f"os_p_{etiket}", "PSIKOLOG")
    c.execute("INSERT INTO personel (kullanici_id, personel_kodu) VALUES (%s, %s) RETURNING personel_id", (psikolog, f"OS-{etiket}"))
    personel = c.fetchone()[0]
    kod = f"OS-{etiket}-1"
    c.execute("INSERT INTO danisan_kodlari (danisan_kod_id, olusturan_psikolog_id) VALUES (%s, %s)", (kod, personel))
    olusturulan = []

    def oda(ad, aktif=True, atanmis=False):
        c.execute("INSERT INTO odalar (oda_adi, kapasite, aktif_mi) VALUES (%s, 1, %s) RETURNING oda_id", (f"os_{ad}_{etiket}", aktif))
        oda_id = c.fetchone()[0]
        olusturulan.append(oda_id)
        if atanmis:
            c.execute("INSERT INTO psikolog_odalar (kullanici_id, oda_id) VALUES (%s, %s)", (psikolog, oda_id))
        return oda_id

    try:
        yield c, admin, psikolog, personel, kod, oda
    finally:
        c.execute("DELETE FROM randevular WHERE danisan_kod_id = %s", (kod,))
        c.execute("DELETE FROM cihaz_rezervasyonlari WHERE kullanilacak_oda_id = ANY(%s)", (olusturulan,))
        c.execute("DELETE FROM oda_etkinlikleri WHERE oda_id = ANY(%s)", (olusturulan,))
        c.execute("DELETE FROM danisan_kodlari WHERE danisan_kod_id = %s", (kod,))
        c.execute("DELETE FROM psikolog_odalar WHERE kullanici_id = %s", (psikolog,))
        c.execute("DELETE FROM denetim_kayitlari WHERE kullanici_id = ANY(%s) OR (hedef_tablo = 'odalar' AND hedef_kayit_id = ANY(%s))", ([admin, psikolog], olusturulan))
        c.execute("DELETE FROM odalar WHERE oda_id = ANY(%s)", (olusturulan,))
        c.execute("DELETE FROM personel WHERE personel_id = %s", (personel,))
        c.execute("DELETE FROM kullanicilar WHERE kullanici_id = ANY(%s)", ([admin, psikolog],))
        conn.close()


def _var_mi(c, oda_id):
    c.execute("SELECT 1 FROM odalar WHERE oda_id = %s", (oda_id,))
    return c.fetchone() is not None


def _randevu(c, kod, personel, oda, baslangic, durum="PLANLANDI"):
    c.execute("INSERT INTO randevular (danisan_kod_id, psikolog_id, oda_id, baslangic_zamani, bitis_zamani, durum, gorusme_tipi, terapi_turu) "
              "VALUES (%s, %s, %s, %s, %s, %s, 'YUZ_YUZE', 'BIREYSEL_TERAPI')",
              (kod, personel, oda, baslangic, baslangic + timedelta(hours=1), durum))


def test_kayitsiz_oda_silinir_atamalar_kalkar_denetim_yazilir(ortam):
    c, admin, psikolog, personel, kod, oda = ortam
    yedek = oda("yedek", atanmis=True)                          # psikologun ikinci aktif odası
    silinecek = oda("silinecek", atanmis=True)
    sonuc = oda_api.oda_sil(silinecek, kullanici_id=admin)
    assert sonuc["durum"] == "silindi" and not _var_mi(c, silinecek)
    c.execute("SELECT COUNT(*) FROM psikolog_odalar WHERE oda_id = %s", (silinecek,))
    assert c.fetchone()[0] == 0                                  # atama odayla birlikte kalktı
    assert _var_mi(c, yedek)                                     # diğer oda yerinde
    c.execute("SELECT olay_turu::text, kullanici_id, ayrinti->'silinen'->>'oda_adi' FROM denetim_kayitlari "
              "WHERE hedef_tablo = 'odalar' AND hedef_kayit_id = %s", (silinecek,))
    olay, kimlik, ad = c.fetchone()
    assert olay == "DELETE" and kimlik == admin and ad.startswith("os_silinecek_")


@pytest.mark.parametrize("tur", ["gecmis_randevu", "iptal_randevu", "gelecek_randevu", "rezervasyon", "etkinlik"])
def test_kullanilmis_oda_silinemez_ve_yerinde_kalir(ortam, tur):
    c, admin, psikolog, personel, kod, oda = ortam
    oda_id = oda("kullanilmis")
    simdi = datetime.now()
    if tur == "gecmis_randevu":
        _randevu(c, kod, personel, oda_id, simdi - timedelta(days=30), "TAMAMLANDI")
    elif tur == "iptal_randevu":
        _randevu(c, kod, personel, oda_id, simdi + timedelta(days=2), "IPTAL_EDILDI")
    elif tur == "gelecek_randevu":
        _randevu(c, kod, personel, oda_id, simdi + timedelta(days=2))
    elif tur == "rezervasyon":
        cihaz = None
        c.execute("INSERT INTO cihazlar (envanter_kodu, cihaz_adi, durum) VALUES (%s, %s, 'Kullanima_Hazir') RETURNING cihaz_id",
                  (f"OS-{uuid4().hex[:8]}", "os_cihaz"))
        cihaz = c.fetchone()[0]
        try:
            c.execute("INSERT INTO cihaz_rezervasyonlari (cihaz_id, baslangic_zamani, bitis_zamani, kullanilacak_oda_id) "
                      "VALUES (%s, %s, %s, %s)", (cihaz, simdi - timedelta(days=9), simdi - timedelta(days=9) + timedelta(hours=1), oda_id))
        except Exception:
            c.execute("DELETE FROM cihazlar WHERE cihaz_id = %s", (cihaz,))
            raise
    else:
        c.execute("INSERT INTO oda_etkinlikleri (oda_id, organize_eden_personel_id, etkinlik_adi, baslangic_zamani, bitis_zamani) "
                  "VALUES (%s, %s, 'os etkinlik', %s, %s)", (oda_id, personel, simdi - timedelta(days=9), simdi - timedelta(days=9) + timedelta(hours=1)))
    try:
        with pytest.raises(HTTPException) as hata:
            oda_api.oda_sil(oda_id, kullanici_id=admin)
        assert hata.value.status_code == 409 and "pasife" in hata.value.detail
        assert _var_mi(c, oda_id)
    finally:
        if tur == "rezervasyon":
            c.execute("DELETE FROM cihaz_rezervasyonlari WHERE cihaz_id = %s", (cihaz,))
            c.execute("DELETE FROM cihazlar WHERE cihaz_id = %s", (cihaz,))


def test_psikologun_tek_aktif_odasi_silinemez_pasif_odasi_silinir(ortam):
    c, admin, psikolog, personel, kod, oda = ortam
    tek = oda("tek", atanmis=True)
    with pytest.raises(HTTPException) as hata:
        oda_api.oda_sil(tek, kullanici_id=admin)
    assert hata.value.status_code == 409 and "tek aktif odası" in hata.value.detail and _var_mi(c, tek)
    pasif = oda("pasif", aktif=False, atanmis=True)             # pasif oda psikoloğun aktif oda sayısını etkilemez
    assert oda_api.oda_sil(pasif, kullanici_id=admin)["durum"] == "silindi" and not _var_mi(c, pasif)


def test_olmayan_oda_404(ortam):
    c, admin, *_ = ortam
    with pytest.raises(HTTPException) as hata:
        oda_api.oda_sil(2_000_000_000, kullanici_id=admin)
    assert hata.value.status_code == 404
