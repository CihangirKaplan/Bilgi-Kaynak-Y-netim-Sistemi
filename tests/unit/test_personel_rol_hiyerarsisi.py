"""Personel uçlarında rol hiyerarşisi (son kontrol): kullanıcı yönetimindeki kural personel kaydında da geçerlidir.

Örn. müdür (PERSONEL_TANIMLA izni var), ADMIN'in ya da başka bir müdürün personel kodunu değiştiremez, müdür rolündeki
bir kullanıcıya personel kaydı veremez. ADMIN için hiyerarşi engel olmaz.
"""
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from server.modeller import PersonelGuncelleModeli, PersonelOlusturModeli
from server.rol_hiyerarsisi import HIYERARSI_MESAJI
from server.sunucu import personel_guncelle, personel_olustur


def _calistir(fonksiyon, fetchone_degerleri, **kwargs):
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchone.side_effect = fetchone_degerleri
    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        try:
            return fonksiyon(**kwargs), None, conn
        except HTTPException as hata:
            return None, hata, conn


@pytest.mark.parametrize("hedef_rol", ["ADMIN", "MUDUR"])
def test_mudur_esit_ya_da_ust_rolun_personel_kodunu_degistiremez(hedef_rol):
    _, hata, conn = _calistir(
        personel_guncelle, [(3, "PER-ADM-001", True, 3, hedef_rol, "MUDUR")],
        personel_id=3, guncelleme=PersonelGuncelleModeli(personel_kodu="DEGISTI"), islem_yapan_id=5,
    )
    assert hata is not None and hata.status_code == 403 and hata.detail == HIYERARSI_MESAJI
    conn.commit.assert_not_called()


def test_mudur_alt_rolun_personel_kodunu_degistirebilir():
    sonuc, hata, conn = _calistir(
        personel_guncelle, [(4, "PER-MEM-001", True, 4, "MEMUR", "MUDUR")],
        personel_id=4, guncelleme=PersonelGuncelleModeli(personel_kodu="PER-MEM-009"), islem_yapan_id=5,
    )
    assert hata is None and sonuc["personel_kodu"] == "PER-MEM-009"
    conn.commit.assert_called_once()


def test_admin_icin_hiyerarsi_engel_olmaz():
    sonuc, hata, conn = _calistir(
        personel_guncelle, [(3, "PER-ADM-001", True, 3, "ADMIN", "ADMIN")],
        personel_id=3, guncelleme=PersonelGuncelleModeli(personel_kodu="PER-ADM-002"), islem_yapan_id=3,
    )
    assert hata is None
    conn.commit.assert_called_once()


def test_mudur_mudur_rolundeki_kullaniciya_personel_kaydi_veremez():
    _, hata, conn = _calistir(
        personel_olustur, [(True, "MUDUR", "MUDUR")],
        yeni_personel=PersonelOlusturModeli(kullanici_id=12, personel_kodu="PER-MUD-009"), islem_yapan_id=5,
    )
    assert hata is not None and hata.status_code == 403
    conn.commit.assert_not_called()


def test_sorgu_islemi_yapanin_rolunu_de_okur():
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchone.side_effect = [(4, "PER-MEM-001", True, 4, "MEMUR", "MUDUR")]
    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        personel_guncelle(personel_id=4, guncelleme=PersonelGuncelleModeli(personel_kodu="PER-MEM-010"), islem_yapan_id=5)
    sorgu, parametreler = cursor.execute.call_args_list[0].args
    assert "FOR UPDATE OF k" in sorgu and parametreler == (5, 4)
