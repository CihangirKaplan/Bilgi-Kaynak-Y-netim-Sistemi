"""İzin düzenleme API'sinin güvenlik ve kaynak yönetimi testleri."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from server.modeller import IzinDuzenleModeli
from server.sunucu import izin_duzenle


def test_admin_izni_kaldirilamaz():
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchone.return_value = (17,)
    cursor.fetchall.return_value = [
        (1, "ADMIN"),
        (2, "PSIKOLOG"),
    ]

    veri = IzinDuzenleModeli(
        gorunen_ad="Randevu Düzenle",
        verilen_rol_idleri=[2],
    )

    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            izin_duzenle(17, veri, kullanici_id=7)

    assert hata.value.status_code == 422
    assert "ADMIN" in hata.value.detail
    conn.rollback.assert_called_once()
    conn.commit.assert_not_called()
    assert not any(
        "UPDATE izinler" in call.args[0]
        for call in cursor.execute.call_args_list
    )


def test_gecersiz_rol_id_reddedilir():
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchone.return_value = (17,)
    cursor.fetchall.return_value = [
        (1, "ADMIN"),
        (2, "PSIKOLOG"),
    ]

    veri = IzinDuzenleModeli(
        gorunen_ad="Randevu Düzenle",
        verilen_rol_idleri=[1, 999],
    )

    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            izin_duzenle(17, veri, kullanici_id=7)

    assert hata.value.status_code == 422
    conn.rollback.assert_called_once()
    conn.commit.assert_not_called()


def test_basarili_izin_duzenleme_baglantiyi_kapatir():
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchone.return_value = (17,)
    cursor.fetchall.return_value = [
        (1, "ADMIN"),
        (2, "PSIKOLOG"),
    ]
    cursor.rowcount = 1

    veri = IzinDuzenleModeli(
        gorunen_ad="Randevu Düzenle",
        verilen_rol_idleri=[1, 2],
    )

    with (
        patch("server.sunucu.psycopg2.connect", return_value=conn),
        patch("server.rol_api.denetim_kaydi_olustur"),
    ):
        sonuc = izin_duzenle(17, veri, kullanici_id=7)

    assert sonuc["durum"] == "basarili"
    conn.commit.assert_called_once()
    cursor.close.assert_called_once()
    conn.close.assert_called_once()
