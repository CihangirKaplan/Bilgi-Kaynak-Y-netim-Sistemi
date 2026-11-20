"""Tablo başlığına tıklayınca sıralama: anahtar kuralları ve gerçek tablo davranışı."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QTableWidget, QTableWidgetItem

from client.tablo_siralama import siralama_anahtari, siralanabilir_yap


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    return QApplication.instance() or QApplication([])


def sirala(liste):
    return sorted(liste, key=siralama_anahtari)


# ------------------------------------------------------------------ anahtar kuralları
def test_turkce_harf_sirasi():
    assert sirala(["Zeynep", "Çağla", "Ayşe", "Ömer", "Şule", "Iğdır", "İzmir", "Ceren", "Gül", "Güler", "Ali"]) == \
        ["Ali", "Ayşe", "Ceren", "Çağla", "Gül", "Güler", "Iğdır", "İzmir", "Ömer", "Şule", "Zeynep"]


def test_buyuk_kucuk_harf_ayni_sayilir():
    assert sirala(["bahar", "Ali", "AYŞE", "ali"])[:2] in (["Ali", "ali"], ["ali", "Ali"])
    assert sirala(["bahar", "Ali", "AYŞE"]) == ["Ali", "AYŞE", "bahar"]


def test_sayilar_sayi_gibi_dogal_siralanir():
    assert sirala(["10", "9", "100", "2"]) == ["2", "9", "10", "100"]
    assert sirala(["E-10", "E-2", "E-1"]) == ["E-1", "E-2", "E-10"]
    assert sirala(["12 gün", "3 gün", "100 gün"]) == ["3 gün", "12 gün", "100 gün"]


def test_tutarlar_turkce_bicimde_sayi_olarak_siralanir():
    assert sirala(["1.250,50 ₺", "99,90 ₺", "10.000,00 ₺", "5,00 ₺"]) == ["5,00 ₺", "99,90 ₺", "1.250,50 ₺", "10.000,00 ₺"]


def test_tarihler_tarih_gibi_siralanir():
    assert sirala(["05.03.2026", "28.02.2027", "01.12.2025", "05.03.2026 09:30", "05.03.2026 08:00"]) == \
        ["01.12.2025", "05.03.2026", "05.03.2026 08:00", "05.03.2026 09:30", "28.02.2027"]


def test_bos_degerler_en_sonda():
    assert sirala(["—", "b", "", "a", "-"])[:2] == ["a", "b"]
    assert siralama_anahtari("—")[0] == 9 and siralama_anahtari(None)[0] == 9


# ------------------------------------------------------------------ gerçek tablo
def tablo_olustur(satirlar, rozet_sutunu=True):
    """satirlar: [(ad, sayi, tarih, durum)]. Durum sütunu yalnızca hücre bileşeni (rozet) taşır; ad sütunu kimlik saklar."""
    tablo = QTableWidget(len(satirlar), 5)
    tablo.setHorizontalHeaderLabels(["AD", "SAYI", "TARİH", "DURUM", "İŞLEM"])
    for s, (ad, sayi, tarih, durum) in enumerate(satirlar):
        oge = QTableWidgetItem(ad)
        oge.setData(Qt.UserRole, f"id-{ad}")
        tablo.setItem(s, 0, oge)
        tablo.setItem(s, 1, QTableWidgetItem(sayi))
        tablo.setItem(s, 2, QTableWidgetItem(tarih))
        tablo.setItem(s, 3, QTableWidgetItem(""))
        if rozet_sutunu:
            tablo.setCellWidget(s, 3, QLabel(durum))
        tablo.setCellWidget(s, 4, QPushButton(f"sil-{ad}"))
    siralanabilir_yap(tablo)
    return tablo


VERI = [("Zeynep", "10", "05.03.2026", "Aktif"), ("Ali", "9", "01.01.2026", "Pasif"), ("Çağla", "100", "—", "Aktif"),
        ("Ayşe", "2", "20.12.2025", "Beklemede")]


def adlar(tablo):
    return [tablo.item(s, 0).text() for s in range(tablo.rowCount())]


def tikla(tablo, sutun):
    tablo.horizontalHeader().sectionClicked.emit(sutun)


def test_ilk_tik_artan_ikinci_tik_azalan_ok_gosterilir():
    t = tablo_olustur(VERI)
    tikla(t, 0)
    assert adlar(t) == ["Ali", "Ayşe", "Çağla", "Zeynep"]
    assert t.horizontalHeader().isSortIndicatorShown() and t.horizontalHeader().sortIndicatorOrder() == Qt.AscendingOrder
    tikla(t, 0)
    assert adlar(t) == ["Zeynep", "Çağla", "Ayşe", "Ali"]
    assert t.horizontalHeader().sortIndicatorOrder() == Qt.DescendingOrder
    tikla(t, 0)
    assert adlar(t) == ["Ali", "Ayşe", "Çağla", "Zeynep"]                    # tekrar artan


def test_sayi_ve_tarih_sutunlari_dogru_siralanir_bos_hep_sonda():
    t = tablo_olustur(VERI)
    tikla(t, 1)
    assert adlar(t) == ["Ayşe", "Ali", "Zeynep", "Çağla"]                    # 2, 9, 10, 100
    tikla(t, 2)
    assert adlar(t) == ["Ayşe", "Ali", "Zeynep", "Çağla"]                    # 20.12.2025, 01.01.2026, 05.03.2026, boş
    tikla(t, 2)
    assert adlar(t) == ["Zeynep", "Ali", "Ayşe", "Çağla"]                    # azalan: boş yine sonda


def test_orijinal_metinler_ve_kimlikler_korunur():
    t = tablo_olustur(VERI)
    tikla(t, 1)
    assert [t.item(s, 1).text() for s in range(4)] == ["2", "9", "10", "100"]       # geçici sıra numaraları geri alındı
    assert all(t.item(s, 0).data(Qt.UserRole) == f"id-{t.item(s, 0).text()}" for s in range(4))   # kayıt kimliği satırla gider


def test_rozet_ve_dugmeler_satirla_birlikte_tasinir():
    t = tablo_olustur(VERI)
    tikla(t, 0)
    for s in range(4):
        ad = t.item(s, 0).text()
        assert t.cellWidget(s, 4).text() == f"sil-{ad}"                          # düğme kendi satırında
        beklenen = {a: d for a, _, _, d in VERI}[ad]
        assert t.cellWidget(s, 3).text() == beklenen                              # rozet kendi satırında


def test_rozet_metnine_gore_siralanir():
    t = tablo_olustur(VERI)                                                       # DURUM sütununda öğe boş, metin rozette
    tikla(t, 3)
    assert [t.cellWidget(s, 3).text() for s in range(4)] == ["Aktif", "Aktif", "Beklemede", "Pasif"]
    assert t.item(0, 3).text() == "" and t.columnCount() == 5                     # geçici öğe temizlenmiş değil, asıl boş metin korunmuş


def test_gizli_satirlar_satirla_birlikte_tasinir():
    t = tablo_olustur(VERI)
    t.setRowHidden(0, True)                                                       # Zeynep gizli (arama/süzgeç)
    tikla(t, 0)
    gizli = [adlar(t)[s] for s in range(4) if t.isRowHidden(s)]
    assert gizli == ["Zeynep"]


def test_islem_sutunu_ve_bos_sutun_siralanmaz():
    t = tablo_olustur(VERI)
    onceki = adlar(t)
    tikla(t, 4)                                                                   # İŞLEM
    assert adlar(t) == onceki and not t.horizontalHeader().isSortIndicatorShown()


def test_tablo_yeniden_doldurulunca_ok_kaybolur():
    t = tablo_olustur(VERI)
    tikla(t, 0)
    assert t.horizontalHeader().isSortIndicatorShown()
    t.setRowCount(0)                                                              # Yenile: tablo boşaltılıp yeniden doldurulur
    assert not t.horizontalHeader().isSortIndicatorShown()
    t.setRowCount(2)
    t.setItem(0, 0, QTableWidgetItem("b"))
    t.setItem(1, 0, QTableWidgetItem("a"))
    tikla(t, 0)
    assert adlar(t) == ["a", "b"] and t.horizontalHeader().sortIndicatorOrder() == Qt.AscendingOrder   # yeniden artanla başlar


def test_tek_satir_ve_bos_tabloda_hata_vermez():
    t = tablo_olustur([])
    tikla(t, 0)
    t2 = tablo_olustur([VERI[0]])
    tikla(t2, 0)
    assert adlar(t2) == ["Zeynep"]


def test_ayni_satir_sayisiyla_yeniden_doldurulunca_da_ok_kaybolur():
    t = tablo_olustur(VERI)
    tikla(t, 0)
    assert t.horizontalHeader().isSortIndicatorShown()
    for s in range(t.rowCount()):                                                 # Yenile: satır sayısı aynı, hücreler yeniden yazılır
        t.setItem(s, 0, QTableWidgetItem(f"yeni-{s}"))
    assert not t.horizontalHeader().isSortIndicatorShown()


def test_kendi_siralamasi_oku_silmez_ve_hap_gibi_kapli_etiket_siralanir():
    from client.tablo_tasarimi import hap
    t = QTableWidget(3, 2)
    t.setHorizontalHeaderLabels(["AD", "DURUM"])
    for s, (ad, durum) in enumerate([("a", "Pasif"), ("b", "Aktif"), ("c", "Bekliyor")]):
        t.setItem(s, 0, QTableWidgetItem(ad))
        t.setCellWidget(s, 1, hap(durum, "#000", "#fff"))                         # QWidget içinde QLabel (hücre bileşeni)
    siralanabilir_yap(t)
    tikla(t, 1)
    assert [t.item(s, 0).text() for s in range(3)] == ["b", "c", "a"]
    assert t.horizontalHeader().isSortIndicatorShown()


def test_rozetteki_ok_simgesi_sirayi_etkilemez():
    t = QTableWidget(3, 2)
    t.setHorizontalHeaderLabels(["AD", "DURUM"])
    for s, (ad, durum) in enumerate([("a", "Planlandı  ▾"), ("b", "Planlandı"), ("c", "Gelmedi  ▾")]):
        t.setItem(s, 0, QTableWidgetItem(ad))
        t.setCellWidget(s, 1, QLabel(durum))
    siralanabilir_yap(t)
    tikla(t, 1)
    assert [t.item(s, 0).text() for s in range(3)] == ["c", "a", "b"]          # Gelmedi, sonra iki Planlandı (kendi aralarında eski sıra)
