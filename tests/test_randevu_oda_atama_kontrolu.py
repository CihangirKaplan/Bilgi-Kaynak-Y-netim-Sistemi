"""
Randevu ve oda yetkilendirme düzeltmeleri.

- Seçilen oda, seçilen psikoloğa atanmış olmalı (sunucu tarafında da).
- /api/psikologlar giriş yapan kullanıcının kimliğini (kullanici_id) de döndürür.
- /api/psikologlar/{id}/odalar sorgusu gerçek tablo adını (personel) kullanır.
- Psikolog yalnızca kendi randevularını listeler.
"""

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from sunucu import (
    aktif_psikologlari_listele,
    psikolog_odalarini_getir,
    randevu_guncelle,
    randevu_olustur,
    randevulari_listele,
)

BASLANGIC = datetime(2026, 12, 1, 10, 0)
BITIS = BASLANGIC + timedelta(hours=1)


def baglanti():
    conn = MagicMock()
    return conn, conn.cursor.return_value


def sorgular(cursor):
    return [c.args[0] for c in cursor.execute.call_args_list]


def test_atanmamis_odaya_randevu_olusturulamaz():
    conn, cursor = baglanti()
    cursor.fetchone.side_effect = [
        ("ADMIN",),  # kullanıcı rolü
        (1,),        # danışan kodu aktif
        (1,),        # psikolog geçerli
        (1,),        # oda aktif
        None,        # oda bu psikoloğa atanmamış
    ]
    randevu = SimpleNamespace(
        danisan_kod_id="DAN-2026-0001", psikolog_id=3, oda_id=9,
        baslangic_zamani=BASLANGIC, bitis_zamani=BITIS,
    )

    with patch("sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            randevu_olustur(randevu=randevu, kullanici_id=1)

    assert hata.value.status_code == 422
    assert "atanmamış" in hata.value.detail
    assert not any(s.strip().upper().startswith("INSERT INTO RANDEVULAR") for s in sorgular(cursor))
    conn.commit.assert_not_called()


def test_guncellemede_atanmamis_odaya_tasinamaz():
    conn, cursor = baglanti()
    cursor.fetchone.side_effect = [
        ("DAN-2026-0001", 3, 1, BASLANGIC, BITIS, "PLANLANDI"),  # mevcut randevu
        ("ADMIN",),                                              # kullanıcı rolü
        None,                                                    # yeni oda atanmamış
    ]
    guncelleme = MagicMock()
    guncelleme.model_dump.return_value = {"oda_id": 9}

    with patch("sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            randevu_guncelle(randevu_id=10, guncelleme=guncelleme, kullanici_id=1)

    assert hata.value.status_code == 422
    assert not any(s.strip().upper().startswith("UPDATE RANDEVULAR") for s in sorgular(cursor))
    conn.commit.assert_not_called()


def test_guncellemede_oda_ve_psikolog_degismiyorsa_atama_sorgulanmaz():
    """Yalnızca saat değişiyorsa oda atama kontrolü yapılmaz (ek sorgu yok)."""
    conn, cursor = baglanti()
    cursor.fetchone.side_effect = [
        ("DAN-2026-0001", 3, 1, BASLANGIC, BITIS, "PLANLANDI"),
        ("ADMIN",),
        None,  # çakışma yok
    ]
    guncelleme = MagicMock()
    guncelleme.model_dump.return_value = {"bitis_zamani": BITIS + timedelta(hours=1)}

    with patch("sunucu.psycopg2.connect", return_value=conn):
        sonuc = randevu_guncelle(randevu_id=10, guncelleme=guncelleme, kullanici_id=1)

    assert sonuc["durum"] == "basarili"
    assert not any("psikolog_odalar" in s for s in sorgular(cursor))


def test_psikolog_listesi_kullanici_kimligini_de_dondurur():
    conn, cursor = baglanti()
    cursor.fetchall.return_value = [(3, "ali", 11), (4, "ayse", 12)]

    with patch("sunucu.psycopg2.connect", return_value=conn):
        sonuc = aktif_psikologlari_listele(kullanici_id=1)

    assert sonuc == [
        {"personel_id": 3, "ad_soyad": "ali", "kullanici_id": 11},
        {"personel_id": 4, "ad_soyad": "ayse", "kullanici_id": 12},
    ]


def test_psikolog_odalari_sorgusu_gercek_tabloyu_kullanir():
    conn, cursor = baglanti()
    cursor.fetchall.return_value = [(1, "Oda 1", True)]

    with patch("sunucu.psycopg2.connect", return_value=conn):
        sonuc = psikolog_odalarini_getir(personel_id=3, kullanici_id=1)

    assert sonuc == [{"oda_id": 1, "oda_adi": "Oda 1", "aktif_mi": True}]
    sorgu = sorgular(cursor)[0]
    assert "JOIN personel p" in sorgu
    assert "personeller" not in sorgu
    assert cursor.execute.call_args.args[1] == (3,)


def test_psikolog_odalari_hata_detayi_disariya_sizdirilmaz():
    conn, cursor = baglanti()
    cursor.execute.side_effect = Exception('relation "gizli_tablo" does not exist')

    with patch("sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            psikolog_odalarini_getir(personel_id=3, kullanici_id=1)

    assert hata.value.status_code == 500
    assert "gizli_tablo" not in hata.value.detail


def test_psikolog_yalnizca_kendi_randevularini_gorur():
    conn, cursor = baglanti()
    cursor.fetchone.return_value = ("PSIKOLOG",)
    cursor.fetchall.return_value = []

    with patch("sunucu.psycopg2.connect", return_value=conn):
        randevulari_listele(kullanici_id=11)

    sorgu = sorgular(cursor)[-1]
    assert "p.kullanici_id = %s" in sorgu
    assert "psikolog_odalar" not in sorgu
    assert cursor.execute.call_args.args[1] == (11,)


def test_admin_tum_randevulari_gorur():
    conn, cursor = baglanti()
    cursor.fetchone.return_value = ("ADMIN",)
    cursor.fetchall.return_value = []

    with patch("sunucu.psycopg2.connect", return_value=conn):
        randevulari_listele(kullanici_id=1)

    sorgu = sorgular(cursor)[-1]
    assert "WHERE" not in sorgu.upper()
