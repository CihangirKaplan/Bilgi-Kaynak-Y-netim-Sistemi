"""Açılır kutuların (Dönem, durum, oda... seçicileri) sağındaki aşağı ok.

`QComboBox::drop-down { border: none; ... }` kuralı yazılınca Qt kendi okunu çizmez; kutu düz metin kutusuna benzer ve zamanı/seçimi oradan
yapacağınız anlaşılmaz. Ortak `ACILIR_OK_STILI` okun geri gelmesini sağlar: bu testler okun gerçekten çizildiğini piksel olarak sınar.
"""
import re
from pathlib import Path

import pytest
from PySide6.QtCore import QDate
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QComboBox, QDateEdit

from client import login_ekrani, main_window
from client.sayfa_tema import ACILIR_OK_STILI, dialog_stili, liste_sayfasi_stili

YEREL_KURAL = "QComboBox::drop-down { border: none; width: 26px; } QDateEdit::drop-down { border: none; width: 26px; }"


def _mavi_piksel(widget):
    """Kutunun sağ kenarında ok renginde (maviye çalan, koyu) piksel var mı."""
    widget.show()
    resim = widget.grab().toImage()
    for x in range(max(0, resim.width() - 34), resim.width() - 4):
        for y in range(4, resim.height() - 4):
            r = resim.pixelColor(x, y)
            if r.blue() - r.red() > 25 and r.red() < 190:
                return True
    return False


def _kutu(stil, aktif=True):
    kutu = QComboBox()
    kutu.addItems(["Bu Ay", "Geçen Ay"])
    kutu.setEnabled(aktif)
    kutu.setStyleSheet(stil)
    kutu.resize(180, 38)
    return kutu


def test_simge_dosyalari_var_ve_gecerli_svg():
    for ad in ("tkys_ok_asagi.svg", "tkys_ok_asagi_pasif.svg"):
        yol = Path("client/assets") / ad
        assert yol.exists(), ad
        assert QSvgRenderer(str(yol)).isValid(), ad


def test_stil_yollari_ileri_bolulu_ve_dosyalar_gercek():
    """QSS url(...) içinde ters bölü kaçış sayılır (Windows'ta stil sessizce uygulanmaz): yollar ileri bölülü olmalı."""
    yollar = re.findall(r'url\("([^"]+)"\)', ACILIR_OK_STILI)
    assert len(yollar) == 4 and all("\\" not in y and Path(y).exists() for y in yollar)


def test_ortak_stiller_ok_kuralini_icerir():
    for stil in (liste_sayfasi_stili(), dialog_stili(), main_window.STIL):
        assert "QComboBox::down-arrow" in stil


def test_uygulama_acilisi_ok_kuralini_uygulamaya_verir():
    """Ana pencereye bağlı olmayan pencereler de oku alsın diye kural uygulama düzeyinde verilir."""
    kaynak = Path("client/login_ekrani.py").read_text(encoding="utf-8")
    assert "app.setStyleSheet(ACILIR_OK_STILI)" in kaynak and login_ekrani.ACILIR_OK_STILI == ACILIR_OK_STILI


def test_drop_down_kurali_okun_kendisini_siliyordu(tkys_qapplication):
    assert not _mavi_piksel(_kutu(YEREL_KURAL))                      # sorunun belgelenmesi: ok kuralı olmadan ok yok


def test_acilir_kutuda_ok_cizilir(tkys_qapplication):
    assert _mavi_piksel(_kutu(YEREL_KURAL + ACILIR_OK_STILI))


def test_pasif_acilir_kutuda_ok_soluk_cizilir(tkys_qapplication):
    aktif = _kutu(YEREL_KURAL + ACILIR_OK_STILI)
    pasif = _kutu(YEREL_KURAL + ACILIR_OK_STILI, aktif=False)
    aktif.show(); pasif.show()
    a, p = aktif.grab().toImage(), pasif.grab().toImage()

    def en_koyu(resim):
        return min(resim.pixelColor(x, y).red() for x in range(resim.width() - 34, resim.width() - 4) for y in range(4, resim.height() - 4))
    assert en_koyu(a) < en_koyu(p)                                    # pasif ok daha açık renkte


def test_ortak_sayfa_stilleriyle_de_ok_cizilir(tkys_qapplication):
    for stil in (liste_sayfasi_stili(), dialog_stili()):
        assert _mavi_piksel(_kutu(stil))


def test_takvimli_tarih_kutusunda_ok_cizilir_takvimsizde_degismez(tkys_qapplication):
    def tarih(takvimli):
        kutu = QDateEdit(QDate(2026, 11, 26))
        kutu.setCalendarPopup(takvimli)
        kutu.setStyleSheet(YEREL_KURAL + ACILIR_OK_STILI)
        kutu.resize(180, 38)
        return kutu
    assert _mavi_piksel(tarih(True))
    assert not _mavi_piksel(tarih(False))                              # takvimsiz tarih kutusunun yukarı/aşağı düğmeleri etkilenmez
