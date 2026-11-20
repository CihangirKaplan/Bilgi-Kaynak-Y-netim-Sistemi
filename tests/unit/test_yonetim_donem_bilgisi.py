"""Yönetim raporları dönem bilgisi arayüz testleri."""

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from unittest.mock import patch

import pytest
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication, QMessageBox

from client.yonetim_raporlari_panel import YonetimRaporlariEkrani


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def ekran(qt_app):
    widget = YonetimRaporlariEkrani(
        "http://127.0.0.1:8002", "test-token"
    )
    # Filtre değişiminde gerçek API çağrısı yapma.
    widget.raporu_yukle = lambda: None
    yield widget
    widget.close()


def tarihleri_ayarla(widget):
    widget.donem.setCurrentText("Tarih Aralığı")
    widget.baslangic.setDate(QDate(2026, 11, 1))
    widget.bitis.setDate(QDate(2026, 11, 20))


def rapor_yuklenmis_gibi_ayarla(widget):
    tarihleri_ayarla(widget)
    widget.yuklenen_donem = {
        "baslangic": "2026-11-01",
        "bitis": "2026-11-20",
    }
    widget.veriler = {
        "randevu": {
            "onceki_donem": {
                "baslangic": "2026-10-12",
                "bitis": "2026-10-31",
            }
        }
    }


def bilgi_metni(widget):
    with patch.object(QMessageBox, "information") as mesaj:
        widget.donem_bilgisi_goster()
    assert mesaj.call_count == 1
    return mesaj.call_args.args[2]


def test_donem_bilgisi_turkce_tarihler(ekran):
    rapor_yuklenmis_gibi_ayarla(ekran)
    metin = bilgi_metni(ekran)

    assert "01.11.2026" in metin
    assert "20.11.2026" in metin
    assert "12.10.2026" in metin
    assert "31.10.2026" in metin
    assert "SEÇİLEN DÖNEM" in metin
    assert "ÖNCEKİ DÖNEM" in metin
    assert "\\n" not in metin  # Yazılı ters eğik çizgi olmamalı.
    assert "\n" in metin      # Gerçek satır sonu olmalı.


def test_filtre_degisince_eski_tarihler_gosterilmez(ekran):
    rapor_yuklenmis_gibi_ayarla(ekran)

    ekran.bitis.setDate(QDate(2026, 11, 19))
    metin = bilgi_metni(ekran)

    assert "yenileyin" in metin.lower()
    assert "12.10.2026" not in metin


def test_rapor_yuklenmeden_aciklama_gorunur(ekran):
    metin = bilgi_metni(ekran)
    assert "Seçilen Dönem" in metin
    assert "Önceki Dönem" in metin


def test_buton_bu_gun_merkezde_ekraninda_gizlenir(ekran):
    assert ekran.donem_bilgi_btn is not None

    ekran.rapor_turu.setCurrentText("Bugün Merkezde")
    assert ekran.donem_bilgi_btn.isHidden()

    ekran.rapor_turu.setCurrentText("Genel Bakış")
    assert not ekran.donem_bilgi_btn.isHidden()
