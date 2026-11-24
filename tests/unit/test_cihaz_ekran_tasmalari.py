"""Cihaz ekranlarında taşma/kesilme düzeltmeleri: iki satırlı cihaz hücresi, durum rozeti genişliği, uygunluk ızgarası."""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "acceptance"))

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QLabel, QTableWidget, QTableWidgetItem

import client.cihaz_ekranlari as envanter
import client.cihaz_rezervasyon_ekranlari as rez_modulu
import client.cihaz_uygunluk_mantigi as mantik
import client.cihaz_uygunluk_ekrani as uyg_modulu
from client.tablo_tasarimi import CihazHucresiDelegate, cihaz_hucresi_uygula, hap, hap_sutununu_sigdir, tablo_olustur
from client.tablo_siralama import SIRALAMA_ROLU


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    return QApplication.instance() or QApplication([])


def _yanit(veri):
    y = MagicMock(status_code=200, _tkys_oturum_reddedildi=False)
    y.json.return_value = veri
    return y


# ------------------------------------------------------------------ iki satırlı cihaz hücresi
@pytest.mark.parametrize("metin,beklenen", [
    ("DENEME-001  ·  EEG Cihazı", ("EEG Cihazı", "DENEME-001")),
    ("E-1 - Monitör", ("Monitör", "E-1")),
    ("DENEME-004 · Pulse Oksimetre", ("Pulse Oksimetre", "DENEME-004")),
    ("E-1 - Ad - Ek", ("Ad - Ek", "E-1")),                         # ilk ayırıcıdan bölünür
    ("DENEME-001", ("DENEME-001", "")),                            # boşluksuz tire ayırıcı değildir
    ("", ("", "")),
    (None, ("", "")),
])
def test_cihaz_hucresi_ad_ve_kodu_ayirir(metin, beklenen):
    assert CihazHucresiDelegate.parcala(metin) == beklenen


def test_cihaz_hucresi_metni_degismez_cizim_iki_satir(qt_app):
    """Hücrenin metni eskisi gibi kalır (arama/sıralama/test); delege uzun metni taşırmadan çizer."""
    tablo = tablo_olustur(["CİHAZ", "X"], ortali=True)
    cihaz_hucresi_uygula(tablo, 0)
    uzun = "ENVANTER-UZUN-KOD-2026-0042  ·  " + "Çok Kanallı Elektroensefalografi Kayıt ve Analiz Sistemi Pro " * 3
    tablo.setRowCount(1)
    tablo.setItem(0, 0, QTableWidgetItem(uzun))
    tablo.setColumnWidth(0, 200)
    tablo.resize(420, 120)
    tablo.show()
    QApplication.processEvents()
    assert tablo.item(0, 0).text() == uzun                         # metin değişmedi
    resim = tablo.grab()                                           # çizim hata vermeden tamamlanır
    assert not resim.isNull()
    assert isinstance(tablo.itemDelegateForColumn(0), CihazHucresiDelegate)
    tablo.close()


# ------------------------------------------------------------------ durum rozeti kesilmez
def test_hap_en_az_genisligi_gercek_yazi_olcusune_gore(qt_app):
    from PySide6.QtGui import QFontMetrics
    for metin in ("Tamamlandı", "İptal Edildi", "Kullanıma Hazır", "Gecikmiş  ·  1234 gün gecikti"):
        kap = hap(metin, "#000", "#fff")                           # kap referansı tutulur (yoksa etiket silinir)
        etiket = kap.findChild(QLabel)
        yazi = QFont(etiket.font())
        yazi.setPixelSize(11)
        yazi.setWeight(QFont.ExtraBold)
        assert etiket.minimumWidth() >= QFontMetrics(yazi).horizontalAdvance(metin) + 24


def test_hap_sutunu_rozet_ve_hucre_dolgusu_kadar_genisler(qt_app):
    """Tablo stilindeki `padding: 6px 22px`, bileşenin yerleşeceği alanı 44 px daraltır; sütun buna göre genişlemelidir."""
    tablo = tablo_olustur(["A", "DURUM"], ortali=True)
    tablo.horizontalHeader().setSectionResizeMode(1, tablo.horizontalHeader().ResizeMode.Fixed)
    tablo.setRowCount(2)
    for satir, metin in enumerate(("Tamamlandı", "İptal Edildi")):
        tablo.setCellWidget(satir, 1, hap(metin, "#000", "#fff"))
    tablo.setColumnWidth(1, 90)                                    # eski sabit genişlik gibi dar
    hap_sutununu_sigdir(tablo, 1)
    tablo.resize(500, 200)
    tablo.show()
    QApplication.processEvents()
    for satir in range(2):
        kap = tablo.cellWidget(satir, 1)
        etiket = kap.findChild(QLabel)
        assert kap.width() >= etiket.minimumWidth() + 12           # kap kenar boşlukları (6+6) dahil rozet sığıyor
        assert etiket.width() >= etiket.minimumWidth()
    tablo.close()


REZ = [
    {"rezervasyon_id": 1, "envanter_kodu": "E-1", "cihaz_adi": "Zeta Cihazı", "oda_adi": "Oda-1", "bolum_adi": "B", "proje_turu": None,
     "proje_adi_aciklamasi": None, "baslangic_zamani": "2026-11-20T10:00:00", "bitis_zamani": "2026-11-20T12:00:00", "durum": "Tamamlandı"},
    {"rezervasyon_id": 2, "envanter_kodu": "E-2", "cihaz_adi": "Alfa Cihazı", "oda_adi": "Oda-2", "bolum_adi": "B", "proje_turu": None,
     "proje_adi_aciklamasi": None, "baslangic_zamani": "2026-11-21T10:00:00", "bitis_zamani": "2026-11-21T12:00:00", "durum": "İptal Edildi"},
]


def _rezervasyon_ekrani():
    with patch.object(rez_modulu, "oturum_kontrollu_istek", return_value=_yanit(REZ)):
        e = rez_modulu.RezervasyonYonetimEkrani("http://x", "T", yetkili_mi=True)
    e.resize(1300, 400)
    e.show()
    QApplication.processEvents()
    return e


def test_rezervasyon_durum_rozetleri_tam_gorunur_cihaz_adi_ustte(qt_app):
    e = _rezervasyon_ekrani()
    for satir in range(e.tablo.rowCount()):
        kap = e.tablo.cellWidget(satir, rez_modulu.SUTUN_DURUM)
        etiket = kap.findChild(QLabel)
        assert kap.width() >= etiket.minimumWidth() + 12
    assert isinstance(e.tablo.itemDelegateForColumn(0), CihazHucresiDelegate)
    assert e.tablo.item(0, 0).text() == "E-1 · Zeta Cihazı"          # metin eskisi gibi; çizim ad üstte, kod altta
    e.close()


def test_rezervasyon_cihaz_sutunu_ada_gore_siralanir(qt_app):
    e = _rezervasyon_ekrani()
    assert e.tablo.item(0, 0).data(SIRALAMA_ROLU) == "Zeta Cihazı"
    e.tablo.horizontalHeader().sectionClicked.emit(0)              # artan: Alfa, Zeta (kod sırası E-1, E-2 olurdu)
    assert [e.tablo.item(s, 0).data(SIRALAMA_ROLU) for s in range(2)] == ["Alfa Cihazı", "Zeta Cihazı"]
    e.close()


# ------------------------------------------------------------------ envanter
CIHAZLAR = [
    {"cihaz_id": 1, "envanter_kodu": "E-1", "cihaz_adi": "EEG", "marka_model": "M", "seri_no": "S", "durum": "Kullanima_Hazir", "kayit_tarihi": None},
    {"cihaz_id": 2, "envanter_kodu": "ENVANTER-UZUN-KOD-2026-0042", "cihaz_adi": "Çok Uzun Cihaz Adı " * 6, "marka_model": "X" * 80,
     "seri_no": "S" * 60, "durum": "Arizali", "kayit_tarihi": None},
]


def test_envanter_cihaz_adi_ilk_sutun_kod_ikinci_mantiksal_sira_ayni(qt_app):
    with patch.object(envanter, "oturum_kontrollu_istek", return_value=_yanit(CIHAZLAR)):
        e = envanter.CihazYonetimEkrani("http://x", "T", yetkili_mi=True)
    e.resize(1300, 400)
    e.show()
    QApplication.processEvents()
    kb = e.tablo.horizontalHeader()
    assert kb.visualIndex(1) == 0 and kb.visualIndex(0) == 1       # ekranda önce Cihaz Adı, sonra Envanter Kodu
    assert e.tablo.item(0, 0).text() == "E-1" and e.tablo.item(0, 1).text() == "EEG"   # mantıksal sütunlar değişmedi
    assert e.tablo.item(0, 1).font().bold() and not e.tablo.item(0, 0).font().bold()  # ad kalın, kod normal
    assert [c["cihaz_id"] for c in e.gorunen_cihazlar()] == [1, 2]                      # Excel/süzgeç aynı
    kap = e.tablo.cellWidget(0, 4)
    assert kap.width() >= kap.findChild(QLabel).minimumWidth() + 12                      # durum rozeti kesilmiyor
    assert e.tablo.columnWidth(0) == 170 and e.tablo.columnWidth(2) == 190               # uzun kod/marka sütunu şişirmiyor
    e.close()


# ------------------------------------------------------------------ uygunluk ızgarası
def aralik(sa, sb):
    return datetime(2026, 11, 4, sa), datetime(2026, 11, 4, sb)


def test_saat_araligi_satirlari_her_aralik_ayri_satir_fazlasi_ozetlenir():
    assert mantik.saat_araligi_satirlari([aralik(10, 12)]) == ["10:00–12:00"]
    assert mantik.saat_araligi_satirlari([aralik(9, 10), aralik(13, 14)]) == ["09:00–10:00", "13:00–14:00"]
    assert mantik.saat_araligi_satirlari([aralik(9, 10), aralik(11, 12), aralik(14, 15), aralik(16, 17)]) == \
        ["09:00–10:00", "11:00–12:00", "+2 daha"]
    assert mantik.saat_araligi_satirlari([]) == []


def test_hucreye_sigdir_dar_hucrede_kesmez_ve_tasirmaz(qt_app):
    from PySide6.QtGui import QFontMetrics
    yazi = QFont()
    yazi.setPixelSize(13)
    yazi.setBold(True)
    satirlar, son_yazi = uyg_modulu.hucreye_sigdir("Kısmen rezerve\n09:00–10:00\n11:00–12:00\n+2 daha", yazi, 80, 60)
    olcu = QFontMetrics(son_yazi)
    assert all(olcu.horizontalAdvance(s) <= 80 for s in satirlar)            # hiçbir satır hücre genişliğini aşmaz
    assert any("09:00" in s for s in satirlar)                              # saat metni kesilmeden korunur
    satirlar, _ = uyg_modulu.hucreye_sigdir("Müsait", yazi, 100, 40)
    assert satirlar == ["Müsait"]


def test_satir_yuksekligi_gun_hucresi_satirlarina_gore_uzar():
    assert uyg_modulu.satir_yuksekligi([], 2) == 54
    assert uyg_modulu.satir_yuksekligi([], 4) > 54
    assert uyg_modulu.satir_yuksekligi([], 5) > uyg_modulu.satir_yuksekligi([], 4)
    assert uyg_modulu.gun_hucresi_satir_sayisi("Müsait") == 1
    assert uyg_modulu.gun_hucresi_satir_sayisi("Kısmen rezerve\n09:00–10:00", 200) == 2
    assert uyg_modulu.gun_hucresi_satir_sayisi("Kısmen rezerve\n09:00–10:00", 80) == 3     # dar sütunda ilk satır sarar


def test_uygunluk_uzun_cihaz_adi_sutunu_sisirmez_gun_sutunlari_dengeli(qt_app):
    import test_cihaz_uygunluk_ekrani as t
    cihazlar = [t.cihaz(1, "ENVANTER-UZUN-KOD-2026-0042", "Çok Kanallı Elektroensefalografi Kayıt ve Analiz Sistemi Pro " * 2,
                        [t.d("REZERVASYON", "2026-11-04T09:00:00", "2026-11-04T10:00:00"),
                         t.d("REZERVASYON", "2026-11-04T11:00:00", "2026-11-04T12:00:00"),
                         t.d("REZERVASYON", "2026-11-04T13:00:00", "2026-11-04T14:00:00")])]
    sunucu = t.Sunucu(cihazlar)
    with patch.object(t.ekran_modulu, "oturum_kontrollu_istek", sunucu), \
            patch.object(uyg_modulu.CihazUygunlukEkrani, "_bugun", lambda self: t.BUGUN), \
            patch.object(uyg_modulu.CihazUygunlukEkrani, "_simdi", lambda self: t.SIMDI):
        e = uyg_modulu.CihazUygunlukEkrani("http://x", "T")
    e.resize(1400, 500)
    e.show()
    QApplication.processEvents()
    assert e.tablo.columnWidth(uyg_modulu.SUTUN_CIHAZ) == 170                # uzun ad sütunu şişirmedi
    gunler = [e.tablo.columnWidth(c) for c in range(uyg_modulu.ILK_GUN_SUTUNU, uyg_modulu.ILK_GUN_SUTUNU + 7)]
    assert min(gunler) >= 70 and max(gunler) - min(gunler) <= 2              # gün sütunları eşit ve dar değil
    cumartesi_degil = e.tablo.item(0, uyg_modulu.ILK_GUN_SUTUNU + 2)         # 4 Kasım (Çarşamba): 3 rezervasyon
    assert cumartesi_degil.text().split("\n")[1:] == ["09:00–10:00", "11:00–12:00", "+1 daha"]
    assert e.tablo.rowHeight(0) > 54                                         # satır çok satırlı hücreye göre uzadı
    assert "Çok Kanallı" in e.tablo.item(0, 0).toolTip()                     # kısaltılan ad ipucunda tam görünür
    e.close()


# ================================================================== tüm cihaz sayfaları tutarlı
from datetime import date, timedelta

import client.bakim_plani_ekranlari as plan_modulu
import client.cihaz_ariza_ekranlari as ariza_modulu
import client.cihaz_bakim_ekranlari as bakim_modulu
import client.cihaz_kalibrasyon_ekranlari as kalib_modulu
from client.tablo_tasarimi import cihaz_ipucu, cihaz_siralama_adi


def _gun(n):
    return (date.today() + timedelta(days=n)).isoformat()


def test_cihaz_ipucu_ve_siralama_adi():
    assert cihaz_ipucu("E-1  ·  EEG") == "EEG\nEnvanter kodu: E-1"
    assert cihaz_ipucu("E-1 - EEG", "Yerine getirilen plan: X") == "EEG\nEnvanter kodu: E-1\nYerine getirilen plan: X"
    assert cihaz_ipucu("Sadece Ad") == "Sadece Ad"
    assert cihaz_siralama_adi("E-9 - Zeta") == "Zeta" and cihaz_siralama_adi("Ad") == "Ad"


def test_cihaz_hucresi_satir_yuksekligini_en_az_48_yapar_yuksek_satiri_kucultmez(qt_app):
    t = tablo_olustur(["A"])
    t.verticalHeader().setDefaultSectionSize(34)
    cihaz_hucresi_uygula(t, 0)
    assert t.verticalHeader().defaultSectionSize() == 48
    t.verticalHeader().setDefaultSectionSize(60)
    cihaz_hucresi_uygula(t, 0)
    assert t.verticalHeader().defaultSectionSize() == 60
    t2 = tablo_olustur(["A"])
    onceki = t2.verticalHeader().defaultSectionSize()
    cihaz_hucresi_uygula(t2, 0, en_az_satir_yuksekligi=0)
    assert t2.verticalHeader().defaultSectionSize() == onceki


UZUN_AD = "ENVANTER-UZUN-KOD-2026-0042 - Çok Kanallı Elektroensefalografi Kayıt ve Analiz Sistemi Pro"


def _kayit_ekrani(modul, sinif, veri):
    with patch.object(modul, "oturum_kontrollu_istek", return_value=_yanit(veri)):
        e = getattr(modul, sinif)("http://x", "T")
    e.resize(1500, 400)
    e.show()
    QApplication.processEvents()
    return e


def test_bakim_kayitlari_iki_satirli_cihaz_hucresi_ve_islem_dugmeleri_kirpilmaz(qt_app):
    veri = [{"bakim_id": 7, "cihaz_adi": "DENEME-006 - Ultrason Cihazı", "bakim_yapan_kisi": "k", "yapilan_islem": "i", "maliyet": 1,
             "bakim_baslangic_tarihi": _gun(-30), "bakim_bitis_tarihi": _gun(-30), "sonraki_bakim_tarihi": _gun(30), "uyari_suresi_gun": 7,
             "plan_adi": "Yıllık bakım"},
            {"bakim_id": 9, "cihaz_adi": UZUN_AD, "bakim_yapan_kisi": "k", "yapilan_islem": "i", "maliyet": 1,
             "bakim_baslangic_tarihi": _gun(-20), "bakim_bitis_tarihi": _gun(-20), "sonraki_bakim_tarihi": None, "uyari_suresi_gun": 7}]
    e = _kayit_ekrani(bakim_modulu, "BakimYonetimEkrani", veri)
    assert isinstance(e.tablo.itemDelegateForColumn(0), CihazHucresiDelegate)
    assert e.tablo.item(0, 0).text() == "DENEME-006 - Ultrason Cihazı"                 # metin değişmedi
    assert e.tablo.columnWidth(0) == 165                                               # uzun ad sütunu şişirmedi
    assert e.tablo.item(0, 0).data(SIRALAMA_ROLU) == "Ultrason Cihazı"                 # ada göre sıralama
    ipucu = e.tablo.item(0, 0).toolTip()
    assert "Envanter kodu: DENEME-006" in ipucu and "Yerine getirilen plan: Yıllık bakım" in ipucu
    for satir in range(2):                                                             # ✎ / 🗑 düğmeleri sağdan kırpılmıyor
        kap = e.tablo.cellWidget(satir, 7)
        assert kap.width() >= kap.sizeHint().width()
    e.close()


def test_kalibrasyon_iki_satirli_cihaz_hucresi_ve_islem_dugmeleri_kirpilmaz(qt_app):
    veri = [{"kalibrasyon_id": 3, "cihaz_adi": UZUN_AD, "kalibrasyon_yapan_kurum": "K", "sertifika_no": "C-1",
             "kalibrasyon_baslangic_tarihi": _gun(-100), "kalibrasyon_bitis_tarihi": _gun(-100), "gecerlilik_tarihi": _gun(265), "uyari_suresi_gun": 30}]
    e = _kayit_ekrani(kalib_modulu, "KalibrasyonYonetimEkrani", veri)
    assert isinstance(e.tablo.itemDelegateForColumn(0), CihazHucresiDelegate)
    assert "Çok Kanallı" in e.tablo.item(0, 0).toolTip() and e.tablo.item(0, 0).data(SIRALAMA_ROLU).startswith("Çok Kanallı")
    kap = e.tablo.cellWidget(0, 6)
    assert kap.width() >= kap.sizeHint().width()
    e.close()


def test_ariza_envanter_kodu_gelirse_ad_ustte_kod_altta_gelmezse_eskisi_gibi(qt_app):
    veri = [{"ariza_id": 5, "cihaz_adi": "Çok Kanallı EEG", "envanter_kodu": "E-42", "ariza_baslik": "b", "ariza_aciklama": "a",
             "aciliyet": "Kritik", "durum": "Açık", "bildirim_tarihi": "2026-11-18T10:00:00"},
            {"ariza_id": 4, "cihaz_adi": "Eski Sunucu Cihazı", "ariza_baslik": "b", "ariza_aciklama": "a",
             "aciliyet": "Düşük", "durum": "Çözüldü", "bildirim_tarihi": "2026-11-10T10:00:00"}]
    e = _kayit_ekrani(ariza_modulu, "ArizaYonetimEkrani", veri)
    assert isinstance(e.tablo.itemDelegateForColumn(1), CihazHucresiDelegate)
    assert e.tablo.item(0, 1).text() == "E-42  ·  Çok Kanallı EEG" and e.tablo.item(0, 1).data(SIRALAMA_ROLU) == "Çok Kanallı EEG"
    assert e.tablo.item(1, 1).text() == "Eski Sunucu Cihazı"                         # envanter kodu yoksa (eski sunucu) düz ad
    for satir in range(2):
        kap = e.tablo.cellWidget(satir, 4)
        assert kap.width() >= kap.findChild(QLabel).minimumWidth() + 12               # "Çözüldü"/"Açık" rozeti kesilmiyor
    e.close()


def test_ariza_listesi_ucu_envanter_kodunu_da_dondurur():
    from server.sunucu import arizalari_listele
    from datetime import datetime as dt
    imleç = MagicMock()
    imleç.fetchall.return_value = [(1, "EEG", "Başlık", "Açıklama", "Yüksek", False, dt(2026, 11, 1, 10, 0), "E-1")]
    with patch("server.sunucu.psycopg2.connect", return_value=MagicMock(cursor=MagicMock(return_value=imleç))):
        sonuc = arizalari_listele(kullanici_id=1)
    assert sonuc[0]["envanter_kodu"] == "E-1" and sonuc[0]["cihaz_adi"] == "EEG"      # eski alanlar aynen duruyor


def test_bakim_planlari_cihaz_hucresi_ada_gore_siralanir_ve_islem_kirpilmaz(qt_app):
    veri = [{"plan_id": 1, "cihaz_id": 1, "envanter_kodu": "E-9", "cihaz_adi": "Zeta", "gorev_turu": "Bakım", "periyot_gun": 30, "uyari_suresi_gun": 7,
             "sonraki_gorev_tarihi": _gun(-120), "kalan_gun": -120, "durum": "Gecikmiş", "aktif_mi": True, "tur": "Bakım"},
            {"plan_id": 2, "cihaz_id": 2, "envanter_kodu": "E-1", "cihaz_adi": "Alfa", "gorev_turu": "Bakım", "periyot_gun": 30, "uyari_suresi_gun": 7,
             "sonraki_gorev_tarihi": _gun(20), "kalan_gun": 20, "durum": "Yaklaşıyor", "aktif_mi": True, "tur": "Bakım"}]
    e = _kayit_ekrani(plan_modulu, "BakimPlanlariEkrani", veri)
    assert isinstance(e.tablo.itemDelegateForColumn(0), CihazHucresiDelegate)
    e.tablo.horizontalHeader().sectionClicked.emit(0)
    assert [e.tablo.item(s, 0).data(SIRALAMA_ROLU) for s in range(2)] == ["Alfa", "Zeta"]
    for satir in range(2):
        kap = e.tablo.cellWidget(satir, 6)
        assert kap.width() >= kap.sizeHint().width()
    e.close()


def test_rapor_sayfalarinda_cihaz_basligli_sutun_iki_satirli_digerleri_degil(qt_app):
    import test_rapor_sayfalari as tr
    import test_rapor_bakim_plani as tb
    from client.bakim_plani_raporu_ekrani import BakimPlaniRaporuEkrani
    ekran, _ = tr.ekran_ac(BakimPlaniRaporuEkrani, tb.VERI)
    geciken = ekran.tablolar["geciken"]                            # ["Cihaz", "Plan", ...]
    assert isinstance(geciken.itemDelegateForColumn(0), CihazHucresiDelegate)
    assert not isinstance(geciken.itemDelegateForColumn(1), CihazHucresiDelegate)
    assert not isinstance(ekran.tablolar["tur"].itemDelegateForColumn(0), CihazHucresiDelegate)       # "Tür" sütunu cihaz değil
    ekran.close()


def test_yonetim_paneli_cihaz_sutunu_gorunum_degisince_sifirlanir(qt_app):
    from client.yonetim_raporlari_panel import YonetimRaporlariEkrani
    with patch("client.yonetim_raporlari_panel.oturum_kontrollu_istek"):
        panel = YonetimRaporlariEkrani("http://x", "t")
    baslik, tablo = panel.tablolar[0]
    onceki_yukseklik = tablo.verticalHeader().defaultSectionSize()
    panel.tabloyu_doldur(panel.tablolar[0], "Geciken Planlar", ["Cihaz", "Plan", "Gecikme (gün)"], [("E-1 - EEG", "Bakım", 3)])
    assert isinstance(tablo.itemDelegateForColumn(0), CihazHucresiDelegate)
    assert tablo.verticalHeader().defaultSectionSize() >= 48
    panel.tabloyu_doldur(panel.tablolar[0], "Durumlar", ["Durum", "Sayı"], [("Planlandı", 3)])   # başka görünüm: çizici kalkar
    assert not isinstance(tablo.itemDelegateForColumn(0), CihazHucresiDelegate)
    assert tablo.verticalHeader().defaultSectionSize() == onceki_yukseklik


def test_ana_panel_cihaz_tablolari_iki_satirli_satir_yuksekligi_ayni(qt_app):
    from client.dashboard_ekrani import DashboardEkrani, SATIR_YUKSEKLIK
    def getir(self, yol, *a, **k):
        return {"/api/dashboard/ozet": {"acik_ariza_sayisi": 0},
                "/api/dashboard/yaklasan-islemler": [{"cihaz_adi": "E1 - EEG", "islem_turu": "Bakım", "kalan_gun": 3, "tarih": "01.01.2026"}],
                "/api/dashboard/bugunku-rezervasyonlar": [{"baslangic": "09:00", "bitis": "10:00", "cihaz": "E1 - EEG", "rezerve_eden": "a", "oda": "O"}],
                }.get(yol, [])
    with patch.object(DashboardEkrani, "_getir", getir):
        p = DashboardEkrani("http://x", "T", cihaz_ozeti=True)
    p.zamanlayici.stop()
    assert isinstance(p.tablo_rez.itemDelegateForColumn(1), CihazHucresiDelegate)
    assert isinstance(p.tablo_islem.itemDelegateForColumn(0), CihazHucresiDelegate)
    assert p.tablo_islem.verticalHeader().defaultSectionSize() == SATIR_YUKSEKLIK                 # ana panelin yerleşimi değişmedi
    assert "Envanter kodu: E1" in p.tablo_rez.item(0, 1).toolTip()
    p.close()
