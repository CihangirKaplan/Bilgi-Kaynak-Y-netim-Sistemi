
"""
TKYS QA-001
Personel kaydi olmayan kullanicinin giris guvenligi.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from modeller import GirisModeli
from sunucu import giris_yap


@pytest.fixture
def personel_kaydi_olmayan_giris():
    conn = MagicMock()
    cursor = conn.cursor.return_value

    cursor.fetchone.side_effect = [
        (
            5, "test_psikolog", "sahte_hash", 2,
            True, 0, None, False, "PSIKOLOG"
        ),
        None,
    ]

    with (
        patch("sunucu.psycopg2.connect", return_value=conn),
        patch("sunucu.parola_dogrula", return_value=True),
        patch("sunucu.access_token_olustur") as token,
        patch("sunucu.denetim_kaydi_olustur") as audit,
    ):
        with pytest.raises(HTTPException) as hata:
            giris_yap(
                GirisModeli(
                    kullanici_adi="test_psikolog",
                    parola="dogru_parola",
                )
            )

    assert hata.value.status_code == 403

    cursor.close.assert_called_once()
    conn.close.assert_called_once()

    return token, audit


def test_personel_kaydi_yoksa_jwt_olusturulmaz(
    personel_kaydi_olmayan_giris,
):
    token, _ = personel_kaydi_olmayan_giris

    token.assert_not_called()


def test_personel_kaydi_yoksa_login_failed_kaydedilir(
    personel_kaydi_olmayan_giris,
):
    _, audit = personel_kaydi_olmayan_giris

    audit.assert_called_once()

    assert audit.call_args.kwargs["olay_turu"] == "LOGIN_FAILED"
    assert audit.call_args.kwargs["kullanici_id"] == 5
