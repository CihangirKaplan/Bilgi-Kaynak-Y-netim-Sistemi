"""Oda etkinlikleri ve ortak oda çakışma kuralları."""

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from server.oda_etkinlikleri_kurallari import (
    oda_cakismasi_bul,
    oda_kilidini_al,
)


BASLANGIC = datetime(2034, 6, 15, 10, 30)
BITIS = datetime(2034, 6, 15, 11, 30)


class SahteCursor:
    def __init__(self, dolu_tablo=None):
        self.dolu_tablo = dolu_tablo
        self.sorgular = []
        self.son_tablo = None

    def execute(self, sql, parametreler):
        self.sorgular.append((sql, parametreler))

        if "FROM randevular" in sql:
            self.son_tablo = "randevu"
        elif "FROM cihaz_rezervasyonlari" in sql:
            self.son_tablo = "cihaz"
        elif "FROM oda_etkinlik_gunleri" in sql:
            self.son_tablo = "etkinlik"
        else:
            raise AssertionError("Beklenmeyen SQL sorgusu")

    def fetchone(self):
        if self.son_tablo == self.dolu_tablo:
            return (1,)
        return None


@pytest.mark.parametrize(
    "dolu_tablo,beklenen,sorgu_sayisi",
    [
        ("randevu", "randevu", 1),
        ("cihaz", "cihaz", 2),
        ("etkinlik", "etkinlik", 3),
        (None, None, 3),
    ],
)
def test_ortak_oda_cakisma_turleri(
    dolu_tablo, beklenen, sorgu_sayisi
):
    cursor = SahteCursor(dolu_tablo)

    sonuc = oda_cakismasi_bul(
        cursor, 7, BASLANGIC, BITIS
    )

    assert sonuc == beklenen
    assert len(cursor.sorgular) == sorgu_sayisi


def test_randevu_guncelleme_mevcut_kaydi_haric_tutar():
    cursor = SahteCursor()

    oda_cakismasi_bul(
        cursor,
        7,
        BASLANGIC,
        BITIS,
        haric_randevu_id=42,
    )

    sql, parametreler = cursor.sorgular[0]

    assert "randevu_id <> %s" in sql
    assert parametreler == (
        7, 42, 42, BITIS, BASLANGIC
    )


def test_etkinlik_guncelleme_mevcut_kaydi_haric_tutar():
    cursor = SahteCursor()

    oda_cakismasi_bul(
        cursor,
        7,
        BASLANGIC,
        BITIS,
        haric_etkinlik_id=55,
    )

    sql, parametreler = cursor.sorgular[2]

    assert "etkinlik_id <> %s" in sql
    assert parametreler == (
        7, BITIS, BASLANGIC, 55, 55
    )


def test_iptal_edilmis_kayitlar_sorguda_haric():
    cursor = SahteCursor()

    oda_cakismasi_bul(
        cursor, 7, BASLANGIC, BITIS
    )

    randevu_sql = cursor.sorgular[0][0]
    cihaz_sql = cursor.sorgular[1][0]
    etkinlik_sql = cursor.sorgular[2][0]

    assert "IPTAL_EDILDI" in randevu_sql
    assert "iptal_edildi_mi" in cihaz_sql
    assert "iptal_edildi_mi" in etkinlik_sql


def test_gecersiz_zaman_araligi_reddedilir():
    cursor = SahteCursor()

    with pytest.raises(ValueError):
        oda_cakismasi_bul(
            cursor, 7, BITIS, BASLANGIC
        )

    assert cursor.sorgular == []


def test_oda_kilidi_dogru_parametrelerle_alinir():
    cursor = MagicMock()

    oda_kilidini_al(cursor, 7)

    cursor.execute.assert_called_once_with(
        "SELECT pg_advisory_xact_lock(%s, %s)",
        (391284, 7),
    )


def test_oda_yoksa_kilit_alinmaz():
    cursor = MagicMock()

    oda_kilidini_al(cursor, None)

    cursor.execute.assert_not_called()
