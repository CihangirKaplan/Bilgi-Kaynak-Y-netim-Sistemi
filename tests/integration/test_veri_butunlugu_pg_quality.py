"""Gerçek PostgreSQL: veri bütünlüğü kısıtları (cihaz_id zorunlu, randevu durumu CHECK, büyük/küçük harf duyarsız benzersiz adlar).

CI'daki "PostgreSQL Entegrasyon Testleri" işinde (alembic upgrade head sonrası) çalışır. Her test kendi işleminde çalışır ve
sonunda geri alır (kalıcı kayıt bırakmaz); beklenen hatalar SAVEPOINT içinde yakalanır.
"""
import os
from uuid import uuid4

import psycopg2
import pytest
from psycopg2 import errors

from server.sunucu import VT_AYARLARI


@pytest.fixture
def imlec():
    assert os.getenv("TKYS_PG_TEST_ONAY") == "EVET"
    assert VT_AYARLARI["dbname"] == "crkys_alembic_test"
    conn = psycopg2.connect(**VT_AYARLARI)
    c = conn.cursor()
    try:
        yield c
    finally:
        conn.rollback()
        conn.close()


def reddedilir(c, sorgu, parametreler, hata):
    """Sorgunun beklenen veritabanı hatasıyla reddedildiğini doğrular (işlem bozulmasın diye SAVEPOINT içinde)."""
    c.execute("SAVEPOINT deneme")
    with pytest.raises(hata):
        c.execute(sorgu, parametreler)
    c.execute("ROLLBACK TO SAVEPOINT deneme")


@pytest.mark.parametrize("tablo,sutunlar,degerler", [
    ("cihaz_arizalari", "ariza_baslik, ariza_aciklamasi", ("baslik", "aciklama")),
    ("cihaz_bakimlari", "bakim_yapan_kisi", ("kisi",)),
    ("cihaz_kalibrasyonlari", "kalibrasyon_yapan_kurum", ("kurum",)),
    ("cihaz_bakim_planlari", "gorev_turu, periyot_gun, sonraki_gorev_tarihi", ("tur", 30, "2030-01-01")),
])
def test_cihaz_kayitlari_cihazsiz_olusturulamaz(imlec, tablo, sutunlar, degerler):
    yer_tutucu = ", ".join(["%s"] * len(degerler))
    reddedilir(imlec, f"INSERT INTO {tablo} (cihaz_id, {sutunlar}) VALUES (NULL, {yer_tutucu})", degerler, errors.NotNullViolation)
    # cihazı olan kayıt kabul edilir
    imlec.execute("INSERT INTO cihazlar (envanter_kodu, cihaz_adi) VALUES (%s, 'c') RETURNING cihaz_id", (f"VB-{uuid4().hex[:8]}",))
    cihaz_id = imlec.fetchone()[0]
    imlec.execute(f"INSERT INTO {tablo} (cihaz_id, {sutunlar}) VALUES (%s, {yer_tutucu})", (cihaz_id, *degerler))


def _randevu_hazirligi(c):
    etiket = uuid4().hex[:8]
    c.execute("INSERT INTO kullanicilar (kullanici_adi, parola_hash, rol_id) VALUES (%s, 'x', (SELECT rol_id FROM roller WHERE rol_adi = 'PSIKOLOG')) RETURNING kullanici_id", (f"vb_{etiket}",))
    c.execute("INSERT INTO personel (kullanici_id, personel_kodu) VALUES (%s, %s) RETURNING personel_id", (c.fetchone()[0], f"VB-{etiket}"))
    personel = c.fetchone()[0]
    c.execute("INSERT INTO odalar (oda_adi) VALUES (%s) RETURNING oda_id", (f"vb_oda_{etiket}",))
    oda = c.fetchone()[0]
    c.execute("INSERT INTO danisan_kodlari (danisan_kod_id) VALUES (%s)", (f"VB-{etiket}",))
    return f"VB-{etiket}", personel, oda


def test_randevu_durumu_yalnizca_tanimli_degerler_olabilir(imlec):
    kod, personel, oda = _randevu_hazirligi(imlec)
    sorgu = ("INSERT INTO randevular (danisan_kod_id, psikolog_id, oda_id, baslangic_zamani, bitis_zamani, durum, gorusme_tipi) "
             "VALUES (%s, %s, %s, %s, %s, %s, 'YUZ_YUZE')")
    for gun, durum in enumerate(("TAMAMLANDI", "GELMEDI"), start=1):          # çakışmasın diye farklı günler
        imlec.execute(sorgu, (kod, personel, oda, f"2030-01-0{gun} 10:00", f"2030-01-0{gun} 11:00", durum))
    for kotu in ("Planlandı", "planlandi", "PLANLANDI ", "IPTAL", "XYZ", ""):
        reddedilir(imlec, sorgu, (kod, personel, oda, "2030-02-01 10:00", "2030-02-01 11:00", kotu), errors.CheckViolation)
    reddedilir(imlec, sorgu, (kod, personel, oda, "2030-02-01 10:00", "2030-02-01 11:00", None), errors.NotNullViolation)


def test_randevu_durumu_varsayilan_planlandi_ve_uc_durum_kabul_edilir(imlec):
    kod, personel, oda = _randevu_hazirligi(imlec)
    imlec.execute("INSERT INTO randevular (danisan_kod_id, psikolog_id, oda_id, baslangic_zamani, bitis_zamani, gorusme_tipi) "
                  "VALUES (%s, %s, %s, '2030-03-01 10:00', '2030-03-01 11:00', 'YUZ_YUZE') RETURNING durum", (kod, personel, oda))
    assert imlec.fetchone()[0] == "PLANLANDI"


@pytest.mark.parametrize("tablo,sutun,ek_sutunlar,ek_degerler", [
    ("kullanicilar", "kullanici_adi", ", parola_hash, rol_id", ("'x'", "(SELECT rol_id FROM roller LIMIT 1)")),
    ("odalar", "oda_adi", "", ()),
    ("bolumler", "bolum_adi", ", sorumlu_ad_soyad", ("'sorumlu'",)),
])
def test_ad_alanlari_buyuk_kucuk_harf_farkiyla_tekrarlanamaz(imlec, tablo, sutun, ek_sutunlar, ek_degerler):
    etiket = uuid4().hex[:6]
    sorgu = f"INSERT INTO {tablo} ({sutun}{ek_sutunlar}) VALUES (%s{''.join(', ' + d for d in ek_degerler)})"
    imlec.execute(sorgu, (f"Ali_{etiket}",))
    reddedilir(imlec, sorgu, (f"ali_{etiket}",), errors.UniqueViolation)         # küçük harf
    reddedilir(imlec, sorgu, (f"ALI_{etiket}",), errors.UniqueViolation)         # büyük harf
    imlec.execute(sorgu, (f"Ali2_{etiket}",))                                    # farklı ad serbest


@pytest.mark.parametrize("ilk,tekrar", [
    ("IŞIK ODASI", "işık odası"),            # I, ı, İ, i aynı harf sayılır
    ("PSİKOLOJİ", "psikoloji"),
    ("İstanbul Odası", "ıstanbul odasi"),
])
def test_turkce_i_harfleri_odalarda_ayni_sayilir(imlec, ilk, tekrar):
    etiket = uuid4().hex[:6]
    sorgu = "INSERT INTO odalar (oda_adi) VALUES (%s)"
    imlec.execute(sorgu, (f"{ilk} {etiket}",))
    reddedilir(imlec, sorgu, (f"{tekrar} {etiket}",), errors.UniqueViolation)
