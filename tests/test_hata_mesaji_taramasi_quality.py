"""
TKYS - Quality Assurance (QA-001)
GitHub Issue: #186
Test Alani: API Hata Mesajlarinda Bilgi Sizintisi
"""

import ast
from pathlib import Path

import pytest


FONKSIYONLAR = [
    "kullanici_rol_degistir",
    "kullanici_durum_degistir",
    "personel_olustur",
    "arizalari_listele",
    "bakimlari_listele",
    "bakim_guncelle",
    "kalibrasyonlari_listele",
    "kalibrasyon_guncelle",
    "dashboard_ozet_getir",
    "yaklasan_islemler_getir",
    "faaliyetleri_getir",
    "faaliyet_birimleri_getir",
    "ogrenci_ekle",
    "faaliyet_kayitlarini_getir",
    "faaliyet_kaydi_guncelle",
    "faaliyet_kaydi_sil",
    "faaliyet_birimi_ekle",
    "faaliyet_birimi_guncelle",
    "faaliyet_birimi_sil",
]


@pytest.mark.parametrize("fonksiyon_adi", FONKSIYONLAR)
def test_quality_api_hata_detayi_sizdirmaz(fonksiyon_adi):
    """
    QA-001 #186:
    Yakalanan teknik istisna HTTP detail alanina
    dogrudan aktarilmamali.
    """

    kaynak = Path("sunucu.py").read_text(encoding="utf-8")
    agac = ast.parse(kaynak)

    eslesenler = [
        dugum for dugum in agac.body
        if isinstance(dugum, (ast.FunctionDef, ast.AsyncFunctionDef))
        and dugum.name == fonksiyon_adi
    ]

    assert len(eslesenler) == 1

    kontrol_edilen = 0

    for handler in ast.walk(eslesenler[0]):
        if not isinstance(handler, ast.ExceptHandler):
            continue

        if not handler.name:
            continue

        for dugum in ast.walk(handler):
            if not isinstance(dugum, ast.Call):
                continue

            if not (
                isinstance(dugum.func, ast.Name)
                and dugum.func.id == "HTTPException"
            ):
                continue

            for anahtar in dugum.keywords:
                if anahtar.arg != "detail":
                    continue

                kontrol_edilen += 1

                kullanilan_isimler = {
                    isim.id
                    for isim in ast.walk(anahtar.value)
                    if isinstance(isim, ast.Name)
                }

                assert handler.name not in kullanilan_isimler, (
                    f"{fonksiyon_adi}: Teknik hata bilgisi "
                    f"HTTP yanitina aktariliyor."
                )

    assert kontrol_edilen >= 1
