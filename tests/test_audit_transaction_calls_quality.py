"""
TKYS - Quality Assurance (QA-001)
GitHub Issue: #186
Test Alani: Audit Transaction Butunlugu

Veri degistiren kritik endpoint'lerde audit kaydi,
islemle ayni PostgreSQL cursor'unu kullanmalidir.
"""

import ast
from pathlib import Path

import pytest


FONKSIYONLAR = [
    "bakim_kaydi_ekle",
    "bakim_guncelle",
    "kalibrasyon_kaydi_ekle",
    "kalibrasyon_guncelle",
    "faaliyet_kaydi_ekle",
    "faaliyet_kaydi_guncelle",
    "faaliyet_kaydi_sil",
    "faaliyet_birimi_ekle",
    "faaliyet_birimi_guncelle",
    "faaliyet_birimi_sil",
]


@pytest.mark.parametrize("fonksiyon_adi", FONKSIYONLAR)
def test_quality_audit_ayni_cursor_kullanilmali(fonksiyon_adi):
    """
    QA-001 #186:
    Audit cagrisi mevcut_cursor=cursor icermeli.

    Bu test statik kod kontroludur.
    Gercek PostgreSQL transaction testi degildir.
    """

    kaynak = Path("sunucu.py").read_text(encoding="utf-8")
    agac = ast.parse(kaynak)

    fonksiyonlar = [
        dugum
        for dugum in agac.body
        if isinstance(dugum, ast.FunctionDef)
        and dugum.name == fonksiyon_adi
    ]

    assert len(fonksiyonlar) == 1

    audit_cagrilari = [
        dugum
        for dugum in ast.walk(fonksiyonlar[0])
        if isinstance(dugum, ast.Call)
        and isinstance(dugum.func, ast.Name)
        and dugum.func.id == "denetim_kaydi_olustur"
    ]

    assert len(audit_cagrilari) == 1

    cursor_parametreleri = [
        anahtar.value
        for anahtar in audit_cagrilari[0].keywords
        if anahtar.arg == "mevcut_cursor"
    ]

    assert len(cursor_parametreleri) == 1

    deger = cursor_parametreleri[0]

    assert isinstance(deger, ast.Name)
    assert deger.id == "cursor"
