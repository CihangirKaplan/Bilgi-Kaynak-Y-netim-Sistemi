from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from modeller import KullaniciOlusturModeli, RolDegistirModeli
from sunucu import kullanici_rol_degistir


def test_kullanici_kendi_rolunu_degistiremez():
    mock_conn = MagicMock()

    with patch("sunucu.psycopg2.connect", return_value=mock_conn):
        with pytest.raises(HTTPException) as hata:
            kullanici_rol_degistir(
                kullanici_id=10,
                veri=RolDegistirModeli(rol_id=6),
                islem_yapan_id=10,
            )

    assert hata.value.status_code == 403
    mock_conn.commit.assert_not_called()
    mock_conn.cursor.assert_not_called()


def test_is_admin_alani_reddedilir():
    with pytest.raises(ValidationError) as hata:
        KullaniciOlusturModeli(
            kullanici_adi="test_kullanici",
            rol_id=2,
            is_admin=True,
        )

    assert any(
        hata_detayi["type"] == "extra_forbidden"
        for hata_detayi in hata.value.errors()
    )


@pytest.mark.parametrize(
    "rol,izin",
    [
        ("PSIKOLOG", "KULLANICI_OLUSTUR"),
        ("MEMUR", "ROL_ATAMA_DEGISTIRME"),
    ],
)
def test_yetkisiz_roller_yonetim_islemi_yapamaz(rol, izin):
    from sunucu import izin_kontrol

    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value
    mock_cursor.fetchone.return_value = (0,)

    with patch("sunucu.psycopg2.connect", return_value=mock_conn):
        with pytest.raises(HTTPException) as hata:
            izin_kontrol(izin)(kullanici_id=10)

    assert hata.value.status_code == 403
    mock_conn.commit.assert_not_called()

    sorgular = [
        call.args[0].strip().upper()
        for call in mock_cursor.execute.call_args_list
    ]
    assert not any(
        sorgu.startswith(("INSERT", "UPDATE", "DELETE"))
        for sorgu in sorgular
    )
