"""
TKYS - QA-001 / Issue #186
QA-BUG-008: Ogrenci ekleme RBAC ve Audit kontrolleri.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from sunucu import app, ogrenci_ekle


def test_ogrenci_ekleme_rbac_zorunlu():
    endpoint = next(
        route
        for route in app.routes
        if getattr(route, "path", None) == "/api/ogrenci-ekle"
        and "POST" in getattr(route, "methods", set())
    )

    bagimliliklar = endpoint.dependant.dependencies

    assert any(
        getattr(bagimlilik.call, "__qualname__", "")
        == "izin_kontrol.<locals>.kontrol"
        for bagimlilik in bagimliliklar
    ), "Ogrenci ekleme endpoint'inde RBAC kontrolu bulunmuyor."


def test_ogrenci_ekleme_audit_zorunlu():
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchone.return_value = (501,)

    ogrenci = SimpleNamespace(
        ad_soyad="QA Test",
        ogrenci_numarasi="QA001",
        telefon="05000000000",
        tur="Gönüllü",
    )

    with (
        patch("sunucu.psycopg2.connect", return_value=conn),
        patch("denetim.denetim_kaydi_olustur") as audit,
    ):
        sonuc = ogrenci_ekle(ogrenci, yetkili_id=1)

    assert sonuc["durum"] == "basarili"

    audit.assert_called_once()

    cagri = audit.call_args
    args = cagri.args
    kwargs = cagri.kwargs

    olay = kwargs.get("olay_turu")
    tablo = kwargs.get("hedef_tablo")
    hedef_id = kwargs.get("hedef_kayit_id")

    if olay is None and len(args) >= 2:
        olay = args[1]

    if tablo is None and len(args) >= 4:
        tablo = args[3]

    if hedef_id is None and len(args) >= 5:
        hedef_id = args[4]

    assert olay == "CREATE"
    assert tablo == "ogrenciler"
    assert hedef_id == 501
    assert kwargs.get("mevcut_cursor") is cursor

    conn.commit.assert_called_once()
    conn.rollback.assert_not_called()
    cursor.close.assert_called_once()
    conn.close.assert_called_once()
