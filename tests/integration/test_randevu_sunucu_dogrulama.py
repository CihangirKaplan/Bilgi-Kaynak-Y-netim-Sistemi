"""Randevu sunucu doğrulamaları: danışan-psikolog uyumu, PATCH'te yeniden doğrulama, 500'de ayrıntı sızdırmama.

Kodlar sıralı ve tahmin edilebilir olduğundan kural arayüze değil sunucuya konur (API'ye doğrudan istek atılabilir).
Veritabanı sahte imleçle taklit edilir; PostgreSQL gerekmez.
"""
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from server.modeller import RandevuGuncelleModeli, RandevuOlusturModeli
from server.sunucu import (
    DANISAN_PSIKOLOG_MESAJI,
    danisan_psikologa_ait_mi,
    randevu_guncelle,
    randevu_olustur,
)


def gelecek_is_gunu(saat=10, gun=7):
    g = datetime.now().replace(hour=saat, minute=0, second=0, microsecond=0) + timedelta(days=gun)
    while g.weekday() >= 5:
        g += timedelta(days=1)
    return g


# ------------------------------------------------------------------ saf işlevler
def test_danisan_yalnizca_kendi_psikologuna_ait():
    assert danisan_psikologa_ait_mi(5, 5) is True
    assert danisan_psikologa_ait_mi(5, 6) is False
    assert danisan_psikologa_ait_mi(None, 6) is True                                    # eski kayıtlarda psikolog boş olabilir


# ------------------------------------------------------------------ oluşturma
def _model(bas, bit, psikolog_id=1):
    return RandevuOlusturModeli(danisan_kod_id="DAN-2026-0001", psikolog_id=psikolog_id, oda_id=1, baslangic_zamani=bas, bitis_zamani=bit)


def test_baska_psikologun_danisanina_randevu_olusturulamaz():
    g = gelecek_is_gunu(10)
    conn = MagicMock()
    imlec = conn.cursor.return_value
    imlec.fetchone.side_effect = [("MUDUR",), ("YETISKIN", 99)]                          # rol, danışan (sahibi psikolog 99)
    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            randevu_olustur(_model(g, g + timedelta(hours=1), psikolog_id=1), kullanici_id=1)
    assert hata.value.status_code == 422 and hata.value.detail == DANISAN_PSIKOLOG_MESAJI
    conn.commit.assert_not_called()


def test_beklenmeyen_hata_ayrintisini_istemciye_sizdirmaz():
    g = gelecek_is_gunu(10)
    with patch("server.sunucu.psycopg2.connect", side_effect=RuntimeError('relation "gizli_tablo" does not exist')):
        with pytest.raises(HTTPException) as hata:
            randevu_olustur(_model(g, g + timedelta(hours=1)), kullanici_id=1)
    assert hata.value.status_code == 500
    assert "gizli_tablo" not in hata.value.detail and "RuntimeError" not in hata.value.detail


# ------------------------------------------------------------------ düzenleme
def _guncelle(degisiklikler, fetchler, rol=("MUDUR",)):
    bas = gelecek_is_gunu(10)
    mevcut = ("DAN-2026-0001", 1, 1, bas, bas + timedelta(hours=1), "PLANLANDI", "YUZ_YUZE", "BIREYSEL_TERAPI")
    conn = MagicMock()
    conn.cursor.return_value.fetchone.side_effect = [(1,), mevcut, rol] + list(fetchler) + [None] * 6      # önce mevcut oda, sonra satır, sonra rol
    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        try:
            return randevu_guncelle(1, RandevuGuncelleModeli(**degisiklikler), kullanici_id=1), conn
        except HTTPException as h:
            return h, conn


def test_pasif_danisana_randevu_aktarilamaz():
    sonuc, conn = _guncelle({"danisan_kod_id": "DAN-2026-0099"}, [None])                  # danışan aktif değil/yok
    assert isinstance(sonuc, HTTPException) and sonuc.status_code == 422 and "danışan" in sonuc.detail.lower()
    conn.commit.assert_not_called()


def test_pasif_psikologa_randevu_aktarilamaz():
    sonuc, conn = _guncelle({"psikolog_id": 7}, [("YETISKIN", None), None])               # danışan tamam, psikolog aktif psikolog değil
    assert isinstance(sonuc, HTTPException) and sonuc.status_code == 422 and "psikolog" in sonuc.detail.lower()
    conn.commit.assert_not_called()


def test_danisan_baska_psikologa_aitse_randevu_o_psikologa_aktarilamaz():
    sonuc, conn = _guncelle({"psikolog_id": 7}, [("YETISKIN", 99), (1,)])                  # danışan psikolog 99'a ait, hedef 7
    assert isinstance(sonuc, HTTPException) and sonuc.status_code == 422 and sonuc.detail == DANISAN_PSIKOLOG_MESAJI


def test_rolu_bulunamayan_kullanici_500_ile_cokmez():
    sonuc, _ = _guncelle({"oda_id": 2}, [("YETISKIN", None), (1,)], rol=None)
    assert not (isinstance(sonuc, TypeError))
    assert not isinstance(sonuc, HTTPException) or sonuc.status_code != 500
