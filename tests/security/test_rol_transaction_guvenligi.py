"""Rol işlemlerinde rollback ve bağlantı temizliği testleri."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from server.modeller import RolModeli, RolGorunenAdModeli
from server.sunucu import rol_olustur, rol_guncelle, rol_sil


@pytest.mark.parametrize(
    "islem,veri,hata_mesaji",
    [
        (
            rol_olustur,
            RolModeli(rol_adi="Yeni Test Rolü"),
            "Rol oluşturulurken bir hata oluştu.",
        ),
        (
            rol_guncelle,
            RolGorunenAdModeli(gorunen_ad="Yeni Ad", aktif_mi=True),
            "Rol güncellenirken bir hata oluştu.",
        ),
        (
            rol_sil,
            None,
            "Rol silinirken bir hata oluştu.",
        ),
    ],
)
def test_veritabani_hatasinda_rollback_ve_kapatma(islem, veri, hata_mesaji):
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.execute.side_effect = RuntimeError("Test veritabani hatasi")

    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            if islem is rol_olustur:
                islem(veri, kullanici_id=7)
            elif islem is rol_guncelle:
                islem(rol_id=15, veri=veri, kullanici_id=7)
            else:
                islem(rol_id=15, kullanici_id=7)

    assert hata.value.status_code == 500
    assert hata.value.detail == hata_mesaji

    conn.rollback.assert_called_once()
    conn.commit.assert_not_called()
    cursor.close.assert_called_once()
    conn.close.assert_called_once()


def test_admin_rolu_guncellenemez():
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchone.return_value = ("ADMIN",)

    veri = RolGorunenAdModeli(
        gorunen_ad="Degistirilmis Admin",
        aktif_mi=False,
    )

    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            rol_guncelle(rol_id=1, veri=veri, kullanici_id=7)

    assert hata.value.status_code == 403
    conn.rollback.assert_called_once()
    conn.commit.assert_not_called()
    cursor.close.assert_called_once()
    conn.close.assert_called_once()


def test_sistem_rolu_silinemez():
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchone.return_value = ("ADMIN",)

    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            rol_sil(rol_id=1, kullanici_id=7)

    assert hata.value.status_code == 403
    conn.rollback.assert_called_once()
    conn.commit.assert_not_called()
    cursor.close.assert_called_once()
    conn.close.assert_called_once()
