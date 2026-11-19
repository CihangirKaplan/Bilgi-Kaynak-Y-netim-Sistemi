from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from server.sunucu import oda_etkinlikli_odalari_denetle


def test_etkinlik_yoksa_atama_serbest():
    cursor = MagicMock()
    cursor.fetchall.return_value = []

    oda_etkinlikli_odalari_denetle(cursor, [1])

    sql, parametreler = cursor.execute.call_args.args

    assert "oda_etkinlik_gunleri" in sql
    assert "g.bitis_zamani > NOW()" in sql
    assert "iptal_edildi_mi" in sql
    assert parametreler == ([1], None)


def test_etkinlik_varsa_atama_409():
    cursor = MagicMock()
    cursor.fetchall.return_value = [("Seminer Odası", 2)]

    with pytest.raises(HTTPException) as hata:
        oda_etkinlikli_odalari_denetle(cursor, [3])

    assert hata.value.status_code == 409
    assert "Seminer Odası" in hata.value.detail
    assert "2 etkinlik" in hata.value.detail


def test_mevcut_psikolog_atamasi_haric_tutulur():
    cursor = MagicMock()
    cursor.fetchall.return_value = []

    oda_etkinlikli_odalari_denetle(
        cursor, [4], haric_kullanici_id=15
    )

    sql, parametreler = cursor.execute.call_args.args

    assert "NOT EXISTS" in sql
    assert "po.kullanici_id = %s" in sql
    assert parametreler == ([4], 15)


def test_bos_oda_listesinde_sorgu_atilmaz():
    cursor = MagicMock()

    oda_etkinlikli_odalari_denetle(cursor, [])

    cursor.execute.assert_not_called()
