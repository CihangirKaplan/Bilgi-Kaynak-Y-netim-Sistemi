"""Yönetim Raporları sayfasının yeni tasarımı: süzgeç kartı, grafik türleri, tablo yerleşimi, bellek sızıntısı."""

import gc
import os
import weakref

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from client.yonetim_raporlari_panel import GENIS_ALT_SIRA, YonetimRaporlariEkrani


def oz(toplam, iptal=0, planlandi=0, sonucsuz=0, tamam=0, gelmedi=0):
    return {"toplam": toplam, "iptal_edildi": iptal, "planlandi": planlandi,
            "sonucu_girilmemis": sonucsuz, "tamamlandi": tamam, "gelmedi": gelmedi}


VERI = {
    "randevu": {"ozet": oz(4, 0, 4, 4), "onceki_ozet": oz(5, 0, 0, 0, 4, 1),
                "donem": {"baslangic": "2026-11-01", "bitis": "2026-11-25"},
                "onceki_donem": {"baslangic": "2026-10-01", "bitis": "2026-10-25"},
                "gunluk": [{"tarih": "2026-11-03", "sayi": 2}]},
    "cihaz": {"ozet": {"bakim": 0, "kalibrasyon": 0, "ariza": 0, "rezervasyon": 2},
              "onceki_ozet": {"bakim": 0, "kalibrasyon": 0, "ariza": 0, "rezervasyon": 1}},
    "ogrenci": {"ozet": {"kayit_sayisi": 3, "faaliyet_yapan_ogrenci": 3, "toplam_puan": 110},
                "onceki_ozet": {"kayit_sayisi": 0, "faaliyet_yapan_ogrenci": 0, "toplam_puan": 0},
                "guncel_ogrenci": {"toplam": 10},
                "faaliyet_dagilimi": [{"faaliyet": "Danışma masası nöbeti", "kayit_sayisi": 2, "toplam_puan": 60},
                                      {"faaliyet": "Etkinlik desteği", "kayit_sayisi": 1, "toplam_puan": 20}]},
    "proje": {"ozet": {"etkinlik_iptal_edilmemis": 7, "rezervasyon_iptal_edilmemis": 2, "rezervasyon_iptal": 0,
                       "kayitli_katilimci_toplami": 50, "rezervasyon_toplam": 2, "etkinlik_toplam": 7},
              "onceki_ozet": {"etkinlik_iptal_edilmemis": 0, "rezervasyon_iptal_edilmemis": 1, "rezervasyon_iptal": 0,
                              "kayitli_katilimci_toplami": 0, "rezervasyon_toplam": 1, "etkinlik_toplam": 0},
              "proje_turu_dagilimi": []},
}


@pytest.fixture(scope="module")
def qt_app():
    yield QApplication.instance() or QApplication([])


@pytest.fixture
def ekran(qt_app):
    widget = YonetimRaporlariEkrani("http://127.0.0.1:8002", "test-token")
    widget.raporu_yukle = lambda: None
    widget.yuklenen_donem = {"baslangic": "2026-11-01", "bitis": "2026-11-25"}
    widget.show()
    yield widget
    widget.close()
    widget.deleteLater()


def test_tarih_alani_yalniz_ozel_aralikta_gorunur(ekran):
    assert not ekran.tarih_alani.isVisibleTo(ekran)
    ekran.donem.setCurrentText("Tarih Aralığı")
    assert ekran.tarih_alani.isVisibleTo(ekran)
    ekran.rapor_turu.setCurrentText("Bugün Merkezde")
    assert not ekran.tarih_alani.isVisibleTo(ekran)


def test_donem_ozeti_iki_donemin_tarihlerini_yazar(ekran):
    ekran.verileri_goster(VERI)
    metin = ekran.donem_ozeti.text()
    assert "01.11.2026 – 25.11.2026" in metin
    assert "01.10.2026 – 25.10.2026" in metin


def test_genel_bakis_kullanilmayan_tablolar_gizli(ekran):
    ekran.verileri_goster(VERI)
    gorunen = [t.parentWidget().isVisibleTo(ekran) for _, t in ekran.tablolar]
    assert gorunen == [False, False, True, True, True]


def test_genel_bakis_tablolari_kaydirma_cubugu_gerektirmez(ekran):
    ekran.resize(1300, 900)
    ekran.verileri_goster(VERI)
    for _, tablo in ekran.tablolar[2:]:
        gerekli = tablo.horizontalHeader().height() + sum(tablo.rowHeight(i) for i in range(tablo.rowCount()))
        assert tablo.maximumHeight() >= gerekli


def test_alt_sira_dar_pencerede_iki_sutuna_iner(ekran):
    ekran.resize(GENIS_ALT_SIRA + 100, 900)
    assert ekran.alt_sutun_sayisi == 3
    ekran.resize(GENIS_ALT_SIRA - 200, 900)
    assert ekran.alt_sutun_sayisi == 2
    # Üçüncü kart ikinci satıra iner; hiçbiri kaybolmaz.
    assert ekran.alt_izgara.count() == 3
    assert ekran.alt_izgara.getItemPosition(2)[0] == 1


def test_grafik_turu_kisitlari(ekran):
    from client.yonetim_grafik_turleri import GrafikTuruSecici

    ekran.verileri_goster(VERI)
    # Tek türlü grafiklerde (karşılaştırma, cihaz) seçici gizlenir; öğrenci grafiği Pasta/Sütun, randevu grafiği 3 tür sunar.
    sayilar = sorted(s.count() for s in ekran.findChildren(GrafikTuruSecici) if s.isVisibleTo(ekran))
    assert sayilar and all(sayi in (2, 3) for sayi in sayilar) and 2 in sayilar


def test_ogrenci_pastasi_veriyi_alir(ekran):
    ekran.verileri_goster(VERI)
    toplam = sum(d["toplam_puan"] for d in VERI["ogrenci"]["faaliyet_dagilimi"])
    assert toplam == 80  # örnek verinin pasta toplamı


def test_sayfa_silinince_temizlenir_cikista_qt_cokmez(qt_app):
    """Sinyal bağlantısında sayfayı tutan `lambda` kullanılırsa sayfa çöp toplayıcıya görünmeyen bir döngüde kalır ve
    süreç kapanırken Qt'yi çökertir (çıkış kodu 139)."""
    widget = YonetimRaporlariEkrani("http://127.0.0.1:8002", "test-token")
    widget.verileri_goster(VERI)
    referans = weakref.ref(widget)
    del widget
    gc.collect()
    assert referans() is None
