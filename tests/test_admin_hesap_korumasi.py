from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from modeller import KullaniciOlusturModeli
from sunucu import kullanici_olustur, kullanici_durum_degistir


def test_admin_baska_admin_hesabinin_aktifligini_degistiremez():
    conn = MagicMock()
    cursor = conn.cursor.return_value

    cursor.fetchone.side_effect = [
        ("ADMIN",),
        ("ADMIN", True),
    ]

    with patch("sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            kullanici_durum_degistir(
                kullanici_id=20,
                islem_yapan_id=10,
            )

    assert hata.value.status_code == 403
    assert "aktiflik durumu değiştirilemez" in hata.value.detail
    sorgular = [
        cagri.args[0].strip().upper()
        for cagri in cursor.execute.call_args_list
    ]
    assert not any(
        sorgu.startswith(("INSERT", "UPDATE", "DELETE"))
        for sorgu in sorgular
    )
    conn.commit.assert_not_called()
    conn.rollback.assert_called_once()


def test_admin_normal_api_ile_yeni_admin_olusturamaz():
    conn = MagicMock()
    cursor = conn.cursor.return_value

    cursor.fetchone.side_effect = [
        ("ADMIN",),
        (1,),
        ("ADMIN",),
    ]

    with patch("sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            kullanici_olustur(
                yeni_kullanici=KullaniciOlusturModeli(
                    kullanici_adi="qa_yeni_admin",
                    rol_id=6,
                ),
                kullanici_id=10,
            )

    assert hata.value.status_code == 403
    assert "ADMIN kullanıcısı" in hata.value.detail
    sorgular = [
        cagri.args[0].strip().upper()
        for cagri in cursor.execute.call_args_list
    ]
    assert not any(
        sorgu.startswith(("INSERT", "UPDATE", "DELETE"))
        for sorgu in sorgular
    )
    conn.commit.assert_not_called()
    conn.rollback.assert_called_once()

