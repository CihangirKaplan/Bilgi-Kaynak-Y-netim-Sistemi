"""Cihaz rezervasyonu: planlı bakım veya kalibrasyonla kesişen saat aralığı reddedilir (SEC-T14).

Bakım/kalibrasyon kaydı cihazın durum alanını değiştirmez; bu yüzden rezervasyon, durumun
yanında bakım/kalibrasyon tarih aralığına da bakar. Gerçek PostgreSQL kullanılmaz.
"""
import datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from modeller import RezervasyonOlusturModeli
from sunucu import cihaz_rezervasyonu_yap


def model():
    return RezervasyonOlusturModeli(
        cihaz_id=7,
        baslangic_zamani="2026-11-10T10:00:00",
        bitis_zamani="2026-11-10T11:00:00",
    )


def calistir(fetchone_sirasi):
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchone.side_effect = fetchone_sirasi
    with patch("sunucu.psycopg2.connect", return_value=conn):
        try:
            sonuc = cihaz_rezervasyonu_yap(model(), kullanici_id=3)
            hata = None
        except HTTPException as e:
            sonuc, hata = None, e
    return sonuc, hata, conn, cursor


@pytest.mark.parametrize("tur", ["Bakım", "Kalibrasyon"])
def test_planli_bakim_veya_kalibrasyonla_kesisen_rezervasyon_409(tur):
    plan = (tur, datetime.date(2026, 11, 9), datetime.date(2026, 11, 12))
    _, hata, conn, cursor = calistir([("Kullanima_Hazir",), plan])
    assert hata.status_code == 409
    assert "09.11.2026 - 12.11.2026" in hata.detail
    assert tur.lower() in hata.detail
    sorgular = [c.args[0].upper() for c in cursor.execute.call_args_list]
    assert not any("INSERT INTO CIHAZ_REZERVASYONLARI" in s for s in sorgular)
    conn.commit.assert_not_called()


def test_plan_yoksa_rezervasyon_devam_eder():
    sonuc, hata, conn, _ = calistir([("Kullanima_Hazir",), None, None, (5,), (42,)])
    assert hata is None and sonuc["rezervasyon_id"] == 42
    conn.commit.assert_called_once()


def test_sorgu_cihaz_ve_saat_araligini_parametre_olarak_alir():
    _, _, _, cursor = calistir([("Kullanima_Hazir",), None, None, (5,), (42,)])
    plan_sorgusu = [c for c in cursor.execute.call_args_list if "cihaz_bakimlari" in c.args[0]][0]
    sorgu, parametreler = plan_sorgusu.args
    assert "cihaz_kalibrasyonlari" in sorgu
    assert parametreler == (
        7, 7,
        datetime.datetime(2026, 11, 10, 11, 0),   # bitis_zamani: plan başlangıcı bundan önce olmalı
        datetime.datetime(2026, 11, 10, 10, 0),   # baslangic_zamani: plan bitişi (dahil) bundan sonra olmalı
    )


def test_bitis_gunu_dahil_ve_eski_kayit_icin_bakim_tarihi_kullanilir():
    """Sorgu mantığı: bitiş günü tam gün dahil (bitis + 1) ve tarih aralığı boş eski bakım
    kayıtları bakim_tarihi'ne düşer; yeni kalibrasyon sütunları boşsa kayıt yok sayılır."""
    _, _, _, cursor = calistir([("Kullanima_Hazir",), None, None, (5,), (42,)])
    sorgu = [c.args[0] for c in cursor.execute.call_args_list if "cihaz_bakimlari" in c.args[0]][0]
    assert "bitis + 1 >" in sorgu
    assert "COALESCE(bakim_baslangic_tarihi, bakim_tarihi::date)" in sorgu
    assert "baslangic IS NOT NULL AND bitis IS NOT NULL" in sorgu


def test_durum_bakimda_ise_eski_kural_403_korunur():
    _, hata, _, _ = calistir([("Bakimda",)])
    assert hata.status_code == 403
