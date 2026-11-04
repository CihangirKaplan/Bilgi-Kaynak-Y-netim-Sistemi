"""
QA-001: Pasif kullanicinin sifre degistirme guvenligi.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from modeller import SifreDegistirModeli
from sunucu import sifre_degistir


def test_pasif_kullanici_sifre_degistiremez():
    conn = MagicMock()
    cursor = conn.cursor.return_value

    # Kullanici mevcut ancak hesabi pasif.
    cursor.fetchone.return_value = ("kayitli_hash", False)

    veri = SifreDegistirModeli(
        eski_parola="EskiSifre123!",
        yeni_parola="YeniSifre456!",
        yeni_parola_tekrar="YeniSifre456!"
    )

    with (
        patch("sunucu.psycopg2.connect", return_value=conn),
        patch("sunucu.parola_dogrula") as mock_dogrula,
        patch("sunucu.parola_hashle") as mock_hashle,
    ):
        with pytest.raises(HTTPException) as hata:
            sifre_degistir(
                veri=veri,
                kullanici_id=10
            )

    assert hata.value.status_code == 403
    assert hata.value.detail == "Kullanıcı hesabı aktif değil."

    # Sifre kontrolune veya hashlemeye gecilmemeli.
    mock_dogrula.assert_not_called()
    mock_hashle.assert_not_called()

    # Sifre guncellenmemeli.
    cursor.execute.assert_called_once()
    sorgu, parametreler = cursor.execute.call_args.args

    assert "SELECT parola_hash, aktif_mi" in sorgu
    assert "FOR UPDATE" in sorgu
    assert parametreler == (10,)

    conn.commit.assert_not_called()
    conn.rollback.assert_called_once()

    # Kaynaklar kapatilmali.
    cursor.close.assert_called_once()
    conn.close.assert_called_once()
