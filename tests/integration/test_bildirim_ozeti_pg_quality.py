"""Gerçek PostgreSQL: zil bildirimlerinin hafif özet uçları (öğrenci saklama süresi, sonucu girilmemiş randevu).

CI'daki "PostgreSQL Entegrasyon Testleri" işinde çalışır; gerçek kayıt oluşturur, sonunda temizler.
"""
import os
from datetime import datetime, timedelta
from uuid import uuid4

import psycopg2
import pytest

from server import bildirim_ozeti_api as ozet
from server.sunucu import VT_AYARLARI


def _dogru_veritabani(cursor):
    assert os.getenv("TKYS_PG_TEST_ONAY") == "EVET"
    assert VT_AYARLARI["dbname"] == "crkys_alembic_test"
    cursor.execute("SELECT current_database()")
    assert cursor.fetchone()[0] == "crkys_alembic_test"


@pytest.fixture
def imlec():
    conn = psycopg2.connect(**VT_AYARLARI)
    conn.autocommit = True
    c = conn.cursor()
    _dogru_veritabani(c)
    try:
        yield c
    finally:
        conn.close()


def _ogrenci(c, etiket, ad, aktif, pasife=None, tur="GONULLU"):
    c.execute("INSERT INTO ogrenciler (ad_soyad, ogrenci_numarasi, tur, aktif_mi) VALUES (%s, %s, %s, %s) RETURNING ogrenci_id",
              (f"BO {ad}", f"{etiket}{ad}"[:15], tur, aktif))                                      # öğrenci numarası en çok 15 karakter
    ogrenci_id = c.fetchone()[0]
    if pasife is not None:
        c.execute("UPDATE ogrenciler SET pasife_alinma_tarihi = %s WHERE ogrenci_id = %s", (pasife, ogrenci_id))
    return ogrenci_id


def test_ogrenci_saklama_ozeti_pasife_alinmaya_gore_sayar_ve_listeyle_tutarlidir(imlec):
    c = imlec
    once = ozet.ogrenci_saklama_ozeti()
    etiket = uuid4().hex[:8]
    ids = [
        _ogrenci(c, etiket, "doldu", False, datetime(2020, 1, 1)),                                 # bekleyen
        _ogrenci(c, etiket, "ertelenen", False, datetime(2020, 1, 1)),                              # ertelenen
        _ogrenci(c, etiket, "yeni", False, datetime.now() - timedelta(days=30)),                    # süresi dolmadı
        _ogrenci(c, etiket, "aktif", True),                                                         # aktif: süre işlemez
        _ogrenci(c, etiket, "asistan", False, datetime(2020, 1, 1), tur="ASISTAN"),                 # Gönüllü değil
    ]
    try:
        c.execute("SELECT ogrenci_numarasi FROM ogrenciler WHERE ogrenci_id = %s", (ids[1],))
        numara = c.fetchone()[0]
        c.execute("INSERT INTO ogrenci_kayit_erteleme_gecmisi (ogrenci_id, ogrenci_numarasi, yeni_uyari_tarihi) "
                  "VALUES (%s, %s, CURRENT_DATE + 30)", (ids[1], numara))
        sonra = ozet.ogrenci_saklama_ozeti()
        assert sonra["bekleyen"] - once["bekleyen"] == 1
        assert sonra["ertelenen"] - once["ertelenen"] == 1
        # Öğrenciler sayfasındaki listeyle aynı kural: bekleyen = süresi dolmuş ve ertelenmemiş.
        import server.sunucu as sunucu
        liste = sunucu.ogrenciler_yonetim_listesi(yetkili_id=None)
        assert sonra["bekleyen"] == sum(1 for o in liste if o["tur"] == "GONULLU" and o["kayit_suresi_doldu"] and not o["ertelendi_mi"])
        assert sonra["ertelenen"] == sum(1 for o in liste if o["tur"] == "GONULLU" and o["kayit_suresi_doldu"] and o["ertelendi_mi"])
    finally:
        c.execute("DELETE FROM ogrenci_kayit_erteleme_gecmisi WHERE ogrenci_id = ANY(%s)", (ids,))
        c.execute("DELETE FROM ogrenciler WHERE ogrenci_id = ANY(%s)", (ids,))


def test_sonucu_girilmemis_randevu_psikolog_kendi_yoneticiler_hepsini_gorur(imlec):
    c = imlec
    etiket = uuid4().hex[:10]
    admin_once = ozet.sonucu_girilmemis_randevu_ozeti(kullanici_id=0)["sayi"]
    kullanicilar, personeller, odalar = [], [], []
    for ad in ("a", "b"):
        c.execute("INSERT INTO kullanicilar (kullanici_adi, parola_hash, rol_id) VALUES (%s, 'x', (SELECT rol_id FROM roller WHERE rol_adi = 'PSIKOLOG')) "
                  "RETURNING kullanici_id", (f"bo{ad}_{etiket}",))
        kullanici = c.fetchone()[0]
        c.execute("INSERT INTO personel (kullanici_id, personel_kodu) VALUES (%s, %s) RETURNING personel_id", (kullanici, f"BO-{ad}{etiket}"))
        pid = c.fetchone()[0]
        c.execute("INSERT INTO odalar (oda_adi, kapasite) VALUES (%s, 1) RETURNING oda_id", (f"bo_oda_{ad}{etiket}",))
        kullanicilar.append(kullanici); personeller.append(pid); odalar.append(c.fetchone()[0])
    kod = f"BO-{etiket}"
    c.execute("INSERT INTO danisan_kodlari (danisan_kod_id, olusturan_psikolog_id) VALUES (%s, %s)", (kod, personeller[0]))
    try:
        gecmis = datetime.now() - timedelta(days=3)
        gelecek = datetime.now() + timedelta(days=3)
        for pid, oda, bas, durum in (
            (personeller[0], odalar[0], gecmis, "PLANLANDI"),                                         # A: sonucu girilmemiş
            (personeller[0], odalar[0], gecmis - timedelta(hours=3), "TAMAMLANDI"),                   # sonucu girilmiş
            (personeller[0], odalar[0], gelecek, "PLANLANDI"),                                        # henüz gelmedi
            (personeller[1], odalar[1], gecmis, "PLANLANDI"),                                         # B: sonucu girilmemiş
            (personeller[1], odalar[1], gecmis - timedelta(hours=5), "IPTAL_EDILDI"),                 # iptal: sayılmaz
        ):
            c.execute("INSERT INTO randevular (danisan_kod_id, psikolog_id, oda_id, baslangic_zamani, bitis_zamani, durum) VALUES (%s, %s, %s, %s, %s, %s)",
                      (kod, pid, oda, bas, bas + timedelta(hours=1), durum))
        assert ozet.sonucu_girilmemis_randevu_ozeti(kullanici_id=kullanicilar[0])["sayi"] == 1        # psikolog A yalnızca kendininkini görür
        assert ozet.sonucu_girilmemis_randevu_ozeti(kullanici_id=kullanicilar[1])["sayi"] == 1
        assert ozet.sonucu_girilmemis_randevu_ozeti(kullanici_id=0)["sayi"] - admin_once == 2         # yönetici hepsini sayar
    finally:
        c.execute("DELETE FROM randevular WHERE danisan_kod_id = %s", (kod,))
        c.execute("DELETE FROM danisan_kodlari WHERE danisan_kod_id = %s", (kod,))
        for kullanici, pid, oda in zip(kullanicilar, personeller, odalar):
            c.execute("DELETE FROM odalar WHERE oda_id = %s", (oda,))
            c.execute("DELETE FROM personel WHERE personel_id = %s", (pid,))
            c.execute("DELETE FROM kullanicilar WHERE kullanici_id = %s", (kullanici,))
