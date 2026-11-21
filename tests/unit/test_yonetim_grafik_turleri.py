"""Yönetim raporları grafikleri: her grafikte aynı üç tür, okunaklı eksen, pasta dilimleri ve seçici."""
import pytest
from PySide6.QtCharts import QBarSeries, QLineSeries, QPieSeries, QValueAxis
from PySide6.QtWidgets import QApplication

import client.yonetim_grafik_turleri as gt


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def test_her_raporda_ayni_uc_tur_vardir():
    for rapor in ("randevu", "karsilastirma", "ogrenci", "proje", "Oda Kullanımı", "Yetkiler", None):
        assert gt.uygun_grafik_turleri(rapor) == ("Sütun", "Çizgi", "Pasta")


@pytest.mark.parametrize("maks, tam, beklenen_ust, beklenen_tik", [
    (98, True, 150, 4), (1240, True, 1500, 4), (9, True, 15, 4), (0, True, 4, 5), (70, True, 80, 5),
])
def test_deger_ekseni_okunakli_adimlarla_ilerler(qt_app, maks, tam, beklenen_ust, beklenen_tik):
    eksen = QValueAxis()
    gt.sayisal_eksen(eksen, maks, tam)
    assert eksen.max() == beklenen_ust and eksen.tickCount() == beklenen_tik
    adim = eksen.max() / (eksen.tickCount() - 1)
    assert adim == int(adim) and eksen.max() >= maks


def test_pasta_yedi_dilimden_fazlasini_diger_diliminde_toplar():
    kategoriler = [f"K{i}" for i in range(10)]
    dilimler = gt._pasta_dilimleri(kategoriler, [("Sayı", [10, 9, 8, 7, 6, 5, 4, 3, 2, 1])])
    assert len(dilimler) == gt.PASTA_EN_FAZLA_DILIM
    assert dilimler[-1][0] == "Diğer" and dilimler[-1][1] == 10           # 4 + 3 + 2 + 1
    assert [d[2] for d in dilimler[:-1]] == list(gt.PALET[:6])             # renkler sabit sırada


def test_iki_donemli_tek_gostergede_pasta_iki_donemin_payini_gosterir():
    dilimler = gt._pasta_dilimleri(["Faaliyet puanı"], [("Seçilen Dönem", [1240]), ("Önceki Dönem", [980])])
    assert [(d[0], d[1]) for d in dilimler] == [("Seçilen Dönem", 1240), ("Önceki Dönem", 980)]
    assert [d[2] for d in dilimler] == list(gt.RENKLER)


def test_gunluk_randevular_haftanin_gunlerine_toplanir():
    tarihler = ["2026-11-16", "2026-11-17", "2026-11-23"]                    # Pzt, Salı, Pzt
    gunler, seriler = gt.haftanin_gunlerine_gore(tarihler, [("Randevu", [3, 2, 5])])
    assert gunler[0] == "Pazartesi" and seriler[0][1][0] == 8 and seriler[0][1][1] == 2
    dilimler = gt._pasta_dilimleri(gunler, seriler)
    assert [d[0] for d in dilimler] == ["Pazartesi", "Salı"]               # gün sırası korunur


@pytest.mark.parametrize("tur, seri_turu", [("Sütun", QBarSeries), ("Çizgi", QLineSeries), ("Pasta", QPieSeries)])
def test_grafik_olustur_her_tur_icin_dogru_seriyi_cizer(qt_app, tur, seri_turu):
    chart = gt.grafik_olustur(["Randevu", "Bakım"], [("Seçilen Dönem", [5, 3]), ("Önceki Dönem", [4, 1])], tur)
    assert any(isinstance(s, seri_turu) for s in chart.series())


def test_secici_combobox_gibi_calisir_ve_sinyal_verir(qt_app):
    secici = gt.GrafikTuruSecici(varsayilan="Çizgi")
    assert secici.count() == 3 and [secici.itemText(i) for i in range(3)] == ["Sütun", "Çizgi", "Pasta"]
    assert secici.currentText() == "Çizgi"
    gelenler = []
    secici.currentTextChanged.connect(gelenler.append)
    secici.setCurrentText("Pasta")
    assert secici.currentText() == "Pasta" and gelenler == ["Pasta"]
    secici.setCurrentText("Olmayan")                                        # bilinmeyen tür: değişmez
    assert secici.currentText() == "Pasta"
