"""Oda etkinliklerinde Admin düzenleyen personel kuralı."""

from unittest.mock import MagicMock
from fastapi import HTTPException

from server.oda_etkinlikleri_api import router_olustur


def test_admin_kontrolu_ortak_fonksiyonda():
    import inspect

    kaynak = inspect.getsource(router_olustur)

    assert "eski_personel_id=None" in kaynak
    assert "personel_id != eski_personel_id" in kaynak
    assert "UPPER(TRIM(r.rol_adi)) <> 'ADMIN'" in kaynak

    assert (
        'eski_personel_id=mevcut["organize_eden_personel_id"]'
        in kaynak
    )


def test_admin_secim_listesinde_filtreleniyor():
    import inspect

    kaynak = inspect.getsource(router_olustur)

    assert "JOIN roller r ON r.rol_id = k.rol_id" in kaynak
    assert "UPPER(TRIM(r.rol_adi)) <> 'ADMIN'" in kaynak
