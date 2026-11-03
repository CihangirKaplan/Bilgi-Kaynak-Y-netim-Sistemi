"""Personel atama sırasında danışma öğrencisi için öğrenci kaydı oluşturma.

Danışma öğrencisi personel olarak atanırken ad soyad ve öğrenci numarası da
alınır; aynı işlemde (tek transaction) türü DANISMA_MASASI olan, hesaba bağlı
bir öğrenci kaydı oluşturulur. Böylece Danışma Masası çalışır ve öğrenci
faaliyet listesinde görünür.
"""
from unittest.mock import MagicMock, patch

import psycopg2.errors
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from modeller import PersonelOlusturModeli
from sunucu import personel_olustur


def calistir(model, fetchone_degerleri, execute_hatasi=None):
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchone.side_effect = fetchone_degerleri
    if execute_hatasi is not None:
        def execute(sorgu, *a, **k):
            if "INSERT INTO ogrenciler" in sorgu:
                raise execute_hatasi
        cursor.execute.side_effect = execute
    with patch("sunucu.psycopg2.connect", return_value=conn):
        try:
            sonuc = personel_olustur(yeni_personel=model, islem_yapan_id=10)
            return sonuc, None, conn, cursor
        except HTTPException as hata:
            return None, hata, conn, cursor


def sorgular(cursor):
    return [c.args[0] for c in cursor.execute.call_args_list]


def test_danisma_ogrencisi_icin_ogrenci_kaydi_da_olusur():
    model = PersonelOlusturModeli(
        kullanici_id=8, personel_kodu="PER-OGR-001",
        ad_soyad="  Veli Kaya ", ogrenci_numarasi="2021002", telefon="05551112233",
    )
    sonuc, hata, conn, cursor = calistir(model, [
        (True, "DANISMA_OGRENCISI"),  # kullanıcı
        (15,),                        # personel_id
        None,                         # bağlı öğrenci kaydı yok
        (7,),                         # ogrenci_id
    ])

    assert hata is None
    assert sonuc["personel_id"] == 15 and sonuc["ogrenci_id"] == 7
    ogrenci_insert = next(c for c in cursor.execute.call_args_list if "INSERT INTO ogrenciler" in c.args[0])
    assert "'DANISMA_MASASI'" in ogrenci_insert.args[0]
    assert ogrenci_insert.args[1] == (8, "Veli Kaya", "2021002", "05551112233")
    assert sum("INSERT INTO denetim_kayitlari" in s for s in sorgular(cursor)) == 2
    conn.commit.assert_called_once()


def test_telefon_istege_baglidir():
    model = PersonelOlusturModeli(
        kullanici_id=8, personel_kodu="PER-OGR-001",
        ad_soyad="Veli Kaya", ogrenci_numarasi="2021002",
    )
    sonuc, hata, conn, cursor = calistir(model, [(True, "DANISMA_OGRENCISI"), (15,), None, (7,)])
    assert hata is None
    ogrenci_insert = next(c for c in cursor.execute.call_args_list if "INSERT INTO ogrenciler" in c.args[0])
    assert ogrenci_insert.args[1][3] is None


def test_zaten_bagli_ogrenci_kaydi_varsa_yenisi_olusmaz():
    model = PersonelOlusturModeli(
        kullanici_id=8, personel_kodu="PER-OGR-001",
        ad_soyad="Veli Kaya", ogrenci_numarasi="2021002",
    )
    sonuc, hata, conn, cursor = calistir(model, [(True, "DANISMA_OGRENCISI"), (15,), (3,)])
    assert hata is None and sonuc["ogrenci_id"] == 3
    assert not any("INSERT INTO ogrenciler" in s for s in sorgular(cursor))


@pytest.mark.parametrize("alanlar", [
    {},
    {"ad_soyad": "Veli Kaya"},
    {"ogrenci_numarasi": "2021002"},
    {"ad_soyad": "   ", "ogrenci_numarasi": "2021002"},
])
def test_danisma_ogrencisi_icin_ad_ve_numara_zorunludur(alanlar):
    model = PersonelOlusturModeli(kullanici_id=8, personel_kodu="PER-OGR-001", **alanlar)
    sonuc, hata, conn, cursor = calistir(model, [(True, "DANISMA_OGRENCISI")])
    assert hata.status_code == 422
    assert not any("INSERT" in s for s in sorgular(cursor))
    conn.commit.assert_not_called()


def test_diger_rollerde_ogrenci_bilgisi_kabul_edilmez():
    model = PersonelOlusturModeli(
        kullanici_id=25, personel_kodu="PER-PSK-001", ad_soyad="Ali Veli",
    )
    sonuc, hata, conn, cursor = calistir(model, [(True, "PSIKOLOG")])
    assert hata.status_code == 422
    assert not any("INSERT" in s for s in sorgular(cursor))


def test_diger_roller_ogrenci_kaydi_olusturmaz():
    model = PersonelOlusturModeli(kullanici_id=25, personel_kodu="PER-PSK-001")
    sonuc, hata, conn, cursor = calistir(model, [(True, "PSIKOLOG"), (15,)])
    assert hata is None and sonuc["ogrenci_id"] is None
    assert not any("ogrenciler" in s for s in sorgular(cursor))


def test_ayni_ogrenci_numarasi_409_verir_ve_geri_alinir():
    model = PersonelOlusturModeli(
        kullanici_id=8, personel_kodu="PER-OGR-001",
        ad_soyad="Veli Kaya", ogrenci_numarasi="2021002",
    )
    sonuc, hata, conn, cursor = calistir(
        model, [(True, "DANISMA_OGRENCISI"), (15,), None],
        execute_hatasi=psycopg2.errors.UniqueViolation(),
    )
    assert hata.status_code == 409
    assert "öğrenci numarası" in hata.detail
    conn.rollback.assert_called()
    conn.commit.assert_not_called()


def test_ayni_personel_kodu_eski_mesajla_409_verir():
    model = PersonelOlusturModeli(kullanici_id=25, personel_kodu="PER-PSK-001")
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchone.side_effect = [(True, "PSIKOLOG")]
    def execute(sorgu, *a, **k):
        if "INSERT INTO personel" in sorgu:
            raise psycopg2.errors.UniqueViolation()
    cursor.execute.side_effect = execute
    with patch("sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            personel_olustur(yeni_personel=model, islem_yapan_id=10)
    assert hata.value.status_code == 409
    assert "personel kodu" in hata.value.detail


@pytest.mark.parametrize("alan, deger", [
    ("ogrenci_numarasi", "20A1002"),          # harf
    ("ogrenci_numarasi", "2021 002"),         # boşluk
    ("ogrenci_numarasi", "٢٠٢١٠٠٢"),          # ASCII dışı rakam
    ("ogrenci_numarasi", "1" * 16),           # 15 haneden uzun
    ("telefon", "0555111223"),                # 0 ile başlıyor ama 10 hane
    ("telefon", "055511122334"),              # 12 hane
    ("telefon", "555 111 22"),                # eksik hane
    ("telefon", "55511122334"),               # 11 hane ama 0 ile başlamıyor
    ("telefon", "0555abc2233"),               # harf
    ("telefon", "555-111-22-33"),             # tire
])
def test_gecersiz_ogrenci_numarasi_ve_telefon_reddedilir(alan, deger):
    taban = {"kullanici_id": 8, "personel_kodu": "PER-OGR-001",
             "ad_soyad": "Veli Kaya", "ogrenci_numarasi": "2021002"}
    taban[alan] = deger
    with pytest.raises(ValidationError):
        PersonelOlusturModeli(**taban)


@pytest.mark.parametrize("girilen, beklenen", [
    (None, None),
    ("", None),
    ("   ", None),
    ("5551112233", "05551112233"),        # başına 0 yazmak gerekmez
    ("555 111 22 33", "05551112233"),     # 3-3-2-2 gruplu
    ("05551112233", "05551112233"),
    ("0555 111 22 33", "05551112233"),
])
def test_telefon_basinda_0_olmadan_da_kabul_edilir_ve_11_haneye_tamamlanir(girilen, beklenen):
    model = PersonelOlusturModeli(
        kullanici_id=8, personel_kodu="PER-OGR-001",
        ad_soyad="Veli Kaya", ogrenci_numarasi="2021002", telefon=girilen,
    )
    assert model.telefon == beklenen


def test_gruplu_telefon_veritabanina_11_haneli_yazilir():
    model = PersonelOlusturModeli(
        kullanici_id=8, personel_kodu="PER-OGR-001",
        ad_soyad="Veli Kaya", ogrenci_numarasi="2021002", telefon="555 111 22 33",
    )
    sonuc, hata, conn, cursor = calistir(model, [(True, "DANISMA_OGRENCISI"), (15,), None, (7,)])
    assert hata is None
    ogrenci_insert = next(c for c in cursor.execute.call_args_list if "INSERT INTO ogrenciler" in c.args[0])
    assert ogrenci_insert.args[1][3] == "05551112233"


def test_en_fazla_15_haneli_numara_kabul_edilir():
    model = PersonelOlusturModeli(
        kullanici_id=8, personel_kodu="PER-OGR-001",
        ad_soyad="Veli Kaya", ogrenci_numarasi="1" * 15,
    )
    assert len(model.ogrenci_numarasi) == 15
