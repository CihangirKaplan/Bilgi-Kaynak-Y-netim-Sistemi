"""
TKYS - Quality Assurance (QA-001)
GitHub Issue: #186
Test Alani: Randevu Guncelleme ve Iptal Branch Coverage

Amac:
Randevu guncelleme ve iptal islemlerinde
yetkilendirme, durum ve cakisma kontrollerini
dogrulamak.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from sunucu import randevu_guncelle, randevu_iptal_et


BASLANGIC = datetime(2026, 12, 1, 10, 0)
BITIS = BASLANGIC + timedelta(hours=1)

MEVCUT_RANDEVU = (
    "DAN-2026-0001",
    1,
    1,
    BASLANGIC,
    BITIS,
    "PLANLANDI",
)

IPTAL_EDILMIS_RANDEVU = (
    "DAN-2026-0001",
    1,
    1,
    BASLANGIC,
    BITIS,
    "IPTAL_EDILDI",
)


@pytest.mark.parametrize(
    "senaryo,cevaplar,degisiklikler,beklenen_status",
    [
        (
            "randevu_bulunamadi",
            [None],
            {"oda_id": 2},
            404,
        ),
        (
            "iptal_edilmis_randevu",
            [IPTAL_EDILMIS_RANDEVU],
            {"oda_id": 2},
            409,
        ),
        (
            "baska_psikologun_randevusu",
            [
                MEVCUT_RANDEVU,
                ("PSIKOLOG",),
                (2,),
            ],
            {"oda_id": 2},
            403,
        ),
        (
            "baska_psikologa_devretme",
            [
                MEVCUT_RANDEVU,
                ("PSIKOLOG",),
                (1,),
            ],
            {"psikolog_id": 2},
            403,
        ),
        (
            "randevu_cakismasi",
            [
                MEVCUT_RANDEVU,
                ("ADMIN",),
                (99,),
            ],
            {"oda_id": 2},
            409,
        ),
    ],
)
def test_quality_randevu_guncelleme_hata_senaryolari(
    senaryo,
    cevaplar,
    degisiklikler,
    beklenen_status,
):
    """
    QA-001 #186:
    Randevu guncelleme hata yollarini dogrular.
    """

    conn = MagicMock()
    cursor = conn.cursor.return_value

    cursor.fetchone.side_effect = cevaplar

    guncelleme = MagicMock()
    guncelleme.model_dump.return_value = degisiklikler

    with patch("sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            randevu_guncelle(
                randevu_id=10,
                guncelleme=guncelleme,
                kullanici_id=1,
            )

    assert hata.value.status_code == beklenen_status, senaryo

    conn.commit.assert_not_called()
    cursor.close.assert_called_once()
    conn.close.assert_called_once()


@pytest.mark.parametrize(
    "senaryo,cevaplar,beklenen_status",
    [
        (
            "randevu_bulunamadi",
            [None],
            404,
        ),
        (
            "baska_psikologun_randevusu",
            [
                (1, "PLANLANDI"),
                ("PSIKOLOG",),
                (2,),
            ],
            403,
        ),
        (
            "randevu_zaten_iptal",
            [
                (1, "IPTAL_EDILDI"),
                ("ADMIN",),
            ],
            409,
        ),
    ],
)
def test_quality_randevu_iptal_hata_senaryolari(
    senaryo,
    cevaplar,
    beklenen_status,
):
    """
    QA-001 #186:
    Randevu iptal isleminin hata yollarini dogrular.
    """

    conn = MagicMock()
    cursor = conn.cursor.return_value

    cursor.fetchone.side_effect = cevaplar

    with patch("sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            randevu_iptal_et(
                randevu_id=10,
                kullanici_id=1,
            )

    assert hata.value.status_code == beklenen_status, senaryo

    conn.commit.assert_not_called()
    cursor.close.assert_called_once()
    conn.close.assert_called_once()


def test_quality_psikolog_kendi_randevusunu_iptal_edebilir():
    """
    QA-001 #186:
    Psikolog kendi planlanmis randevusunu
    basariyla iptal edebilmeli.
    """

    conn = MagicMock()
    cursor = conn.cursor.return_value

    cursor.fetchone.side_effect = [
        (1, "PLANLANDI"),
        ("PSIKOLOG",),
        (1,),
    ]

    with patch("sunucu.psycopg2.connect", return_value=conn):
        sonuc = randevu_iptal_et(
            randevu_id=10,
            kullanici_id=1,
        )

    assert sonuc["durum"] == "basarili"
    assert sonuc["randevu_id"] == 10

    conn.commit.assert_called_once()
    cursor.close.assert_called_once()
    conn.close.assert_called_once()


def test_quality_randevu_guncelleme_basarili():
    """
    TKYS - Quality Assurance (QA-001)
    GitHub Issue: #186
    Test Alani: Basarili randevu guncelleme
    """

    conn = MagicMock()
    cursor = conn.cursor.return_value

    cursor.fetchone.side_effect = [
        MEVCUT_RANDEVU,
        ("ADMIN",),
        None,  # Cakisma yok
    ]

    guncelleme = MagicMock()
    guncelleme.model_dump.return_value = {"oda_id": 2}

    with patch("sunucu.psycopg2.connect", return_value=conn):
        sonuc = randevu_guncelle(
            randevu_id=10,
            guncelleme=guncelleme,
            kullanici_id=1,
        )

    assert sonuc["durum"] == "basarili"
    assert sonuc["randevu_id"] == 10

    assert any(
        "UPDATE randevular SET" in cagri.args[0]
        for cagri in cursor.execute.call_args_list
    )

    conn.commit.assert_called_once()
    conn.rollback.assert_not_called()
    cursor.close.assert_called_once()
    conn.close.assert_called_once()


def test_quality_randevu_guncelleme_exclusion_violation():
    """
    TKYS - Quality Assurance (QA-001)
    GitHub Issue: #186
    Test Alani: PostgreSQL EXCLUDE hatasi ve rollback
    """

    from psycopg2.errors import ExclusionViolation

    conn = MagicMock()
    cursor = conn.cursor.return_value

    cursor.fetchone.side_effect = [
        MEVCUT_RANDEVU,
        ("ADMIN",),
        None,
    ]

    def sorgu_calistir(sql, *args, **kwargs):
        if sql.strip().startswith("UPDATE randevular SET"):
            raise ExclusionViolation("QA-001 cakisma")

    cursor.execute.side_effect = sorgu_calistir

    guncelleme = MagicMock()
    guncelleme.model_dump.return_value = {"oda_id": 2}

    with patch("sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            randevu_guncelle(
                randevu_id=10,
                guncelleme=guncelleme,
                kullanici_id=1,
            )

    assert hata.value.status_code == 409

    conn.rollback.assert_called_once()
    conn.commit.assert_not_called()
    cursor.close.assert_called_once()
    conn.close.assert_called_once()
