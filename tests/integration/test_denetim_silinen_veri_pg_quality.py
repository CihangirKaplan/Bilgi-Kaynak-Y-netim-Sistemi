"""Gerçek PostgreSQL: silinen verinin denetim kaydına yazılması (denetim_kayitlari.ayrinti).

Her test kendi işleminde çalışır ve sonunda geri alır (kalıcı kayıt bırakmaz).
"""
import os
from uuid import uuid4

import psycopg2
import pytest

from server.denetim import (
    denetim_kaydi_olustur,
    psikolog_oda_degisikligini_yaz,
    satiri_sil_ve_ayrintisini_al,
)
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


def _cihaz(c):
    c.execute("INSERT INTO cihazlar (envanter_kodu, cihaz_adi) VALUES (%s, 'c') RETURNING cihaz_id", (f"DS-{uuid4().hex[:8]}",))
    return c.fetchone()[0]


def _son_kayit(c, tablo, kayit_id):
    c.execute(
        "SELECT olay_turu::text, ayrinti FROM denetim_kayitlari WHERE hedef_tablo = %s AND hedef_kayit_id = %s "
        "ORDER BY denetim_id DESC LIMIT 1", (tablo, kayit_id))
    return c.fetchone()


def test_bakim_silinince_icerik_denetim_kaydina_yazilir(imlec):
    cihaz = _cihaz(imlec)
    imlec.execute("INSERT INTO cihaz_bakimlari (cihaz_id, bakim_yapan_kisi, yapilan_islem, maliyet) "
                  "VALUES (%s, 'Ali Usta', 'Filtre değişimi', 150.5) RETURNING bakim_id", (cihaz,))
    bakim_id = imlec.fetchone()[0]

    silinen = satiri_sil_ve_ayrintisini_al(imlec, "cihaz_bakimlari", bakim_id)
    denetim_kaydi_olustur(None, "DELETE", None, "cihaz_bakimlari", bakim_id, mevcut_cursor=imlec, ayrinti=silinen)

    imlec.execute("SELECT 1 FROM cihaz_bakimlari WHERE bakim_id = %s", (bakim_id,))
    assert imlec.fetchone() is None
    olay, ayrinti = _son_kayit(imlec, "cihaz_bakimlari", bakim_id)
    assert olay == "DELETE"
    assert ayrinti["silinen"]["bakim_yapan_kisi"] == "Ali Usta"
    assert ayrinti["silinen"]["yapilan_islem"] == "Filtre değişimi"
    assert ayrinti["silinen"]["cihaz_id"] == cihaz


def test_olmayan_satir_icin_none_doner(imlec):
    assert satiri_sil_ve_ayrintisini_al(imlec, "cihaz_bakimlari", -1) is None


def test_ogrenci_silinince_kisisel_veri_denetim_kaydina_yazilmaz(imlec):
    etiket = uuid4().hex[:8]
    imlec.execute("INSERT INTO ogrenciler (ad_soyad, ogrenci_numarasi, telefon, tur) "
                  "VALUES (%s, %s, '5551234567', 'GONULLU') RETURNING ogrenci_id", (f"Gizli Kisi {etiket}", f"N{etiket}"))
    ogrenci_id = imlec.fetchone()[0]

    silinen = satiri_sil_ve_ayrintisini_al(imlec, "ogrenciler", ogrenci_id)
    denetim_kaydi_olustur(None, "DELETE", None, "ogrenciler", ogrenci_id, mevcut_cursor=imlec, ayrinti=silinen)

    _, ayrinti = _son_kayit(imlec, "ogrenciler", ogrenci_id)
    metin = str(ayrinti)
    assert etiket not in metin and "5551234567" not in metin
    assert {"ad_soyad", "ogrenci_numarasi", "telefon"} <= set(ayrinti["maskelenen_alanlar"])
    assert ayrinti["silinen"]["ogrenci_id"] == ogrenci_id
    assert ayrinti["silinen"]["tur"] == "GONULLU"


def test_denetim_kaydi_ayrintisiz_da_yazilir(imlec):
    denetim_kaydi_olustur(None, "UPDATE", None, "odalar", 12345, mevcut_cursor=imlec)
    olay, ayrinti = _son_kayit(imlec, "odalar", 12345)
    assert olay == "UPDATE" and ayrinti is None


def test_turkce_karakterler_bozulmadan_saklanir(imlec):
    denetim_kaydi_olustur(None, "DELETE", None, "roller", 54321, mevcut_cursor=imlec,
                          ayrinti={"silinen": {"rol_adi": "ÇĞİÖŞÜ çğıöşü"}})
    imlec.execute("SELECT ayrinti->'silinen'->>'rol_adi' FROM denetim_kayitlari WHERE hedef_kayit_id = 54321")
    assert imlec.fetchone()[0] == "ÇĞİÖŞÜ çğıöşü"


def test_psikolog_oda_degisikligi_update_ve_delete_kaydi_yazar(imlec):
    etiket = uuid4().hex[:8]
    imlec.execute("INSERT INTO kullanicilar (kullanici_adi, parola_hash, rol_id) VALUES (%s, 'x', "
                  "(SELECT rol_id FROM roller WHERE rol_adi = 'PSIKOLOG')) RETURNING kullanici_id", (f"ds_{etiket}",))
    kullanici = imlec.fetchone()[0]
    odalar = []
    for i in range(2):
        imlec.execute("INSERT INTO odalar (oda_adi) VALUES (%s) RETURNING oda_id", (f"ds_oda_{etiket}_{i}",))
        odalar.append(imlec.fetchone()[0])
    for oda in odalar:
        imlec.execute("INSERT INTO psikolog_odalar (kullanici_id, oda_id) VALUES (%s, %s)", (kullanici, oda))

    onceki = sorted(odalar)
    imlec.execute("DELETE FROM psikolog_odalar WHERE kullanici_id = %s AND oda_id = %s", (kullanici, odalar[1]))
    psikolog_oda_degisikligini_yaz(imlec, None, kullanici, onceki)

    imlec.execute("SELECT olay_turu::text, ayrinti FROM denetim_kayitlari WHERE hedef_tablo = 'psikolog_odalar' "
                  "AND hedef_kayit_id = %s ORDER BY denetim_id", (kullanici,))
    kayitlar = imlec.fetchall()
    assert [k[0] for k in kayitlar] == ["UPDATE", "DELETE"]
    assert kayitlar[0][1] == {"onceki_oda_idleri": onceki, "yeni_oda_idleri": [odalar[0]]}
    assert kayitlar[1][1]["silinen"]["oda_idleri"] == [odalar[1]]


def test_degisiklik_yoksa_delete_kaydi_yazilmaz(imlec):
    etiket = uuid4().hex[:8]
    imlec.execute("INSERT INTO kullanicilar (kullanici_adi, parola_hash, rol_id) VALUES (%s, 'x', "
                  "(SELECT rol_id FROM roller WHERE rol_adi = 'PSIKOLOG')) RETURNING kullanici_id", (f"ds2_{etiket}",))
    kullanici = imlec.fetchone()[0]
    psikolog_oda_degisikligini_yaz(imlec, None, kullanici, [])
    imlec.execute("SELECT olay_turu::text FROM denetim_kayitlari WHERE hedef_tablo = 'psikolog_odalar' AND hedef_kayit_id = %s", (kullanici,))
    assert [k[0] for k in imlec.fetchall()] == ["UPDATE"]
