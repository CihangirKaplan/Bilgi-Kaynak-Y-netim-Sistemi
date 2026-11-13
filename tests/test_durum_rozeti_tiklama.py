"""
Tamamlandı / Gelmedi işaretleme durum rozetinden yapılır (düğme yok).

- Başlangıcı geçmiş ve iptal edilmemiş randevuların rozetinde ▾ vardır; tıklayınca rozetin hemen altında iki seçenekli liste açılır.
- Seçim doğrudan sunucuya gider (onay penceresi yok); mevcut durum listede kapalıdır; iptal/gelecek randevuda tıklanmaz.
- "Randevu düzenleme" yetkisi olmayan kullanıcıda rozet tıklanmaz.
- Üst düğme sırası: Yeni Randevu, Randevu Düzenle, Randevu İptal Et.

Tarihler "şimdi"ye göre üretilir.
"""

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox

import main_window as mw
import randevu_ekranlari as modul
from randevu_ekranlari import RandevuAnaEkrani, durum_isaretlenebilir, menu_konumu


def zaman(gun=0, saat=10):
    return (datetime.now().replace(hour=saat, minute=0, second=0, microsecond=0) + timedelta(days=gun)).isoformat()


def randevu(no, durum="PLANLANDI", gun=1):
    return {"randevu_id": no, "danisan_kod_id": f"DAN-2026-{no:04d}", "psikolog_id": 3, "oda_id": 2, "durum": durum,
            "baslangic_zamani": zaman(gun), "bitis_zamani": zaman(gun, 11), "iptal_nedeni": None, "iptal_notu": None}


def cevap(veri, durum=200):
    y = MagicMock()
    y.status_code = durum
    y.json.return_value = veri
    y._tkys_oturum_reddedildi = False
    return y


class Sunucu:
    def __init__(self, randevular, patch_cevabi=None):
        self.randevular = randevular
        self.patch_cevabi = patch_cevabi or cevap({"durum": "basarili"})
        self.istekler, self.govdeler = [], []

    def __call__(self, yontem, url, **kwargs):
        self.istekler.append((yontem, url))
        if yontem == "PATCH":
            self.govdeler.append(kwargs.get("json"))
            return self.patch_cevabi
        if url.endswith("/api/randevular"):
            return cevap(self.randevular)
        if url.endswith("/api/psikologlar"):
            return cevap([{"personel_id": 3, "ad_soyad": "Ayşe", "kullanici_id": 13}])
        if url.endswith("/api/odalar"):
            return cevap([{"oda_id": 2, "oda_adi": "Oda-1", "kapasite": 1, "aktif_mi": True}])
        return cevap([])


LISTE = [
    randevu(1, "PLANLANDI", gun=3),          # gelecek: tıklanmaz
    randevu(2, "PLANLANDI", gun=-2),         # geçmiş planlı: tıklanır
    randevu(3, "TAMAMLANDI", gun=-3),        # geçmiş işaretli: düzeltilebilir
    randevu(4, "IPTAL_EDILDI", gun=-1),      # iptal: tıklanmaz
    randevu(5, "GELMEDI", gun=-4),
]


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def ekran_ac(qt_app):
    acik, aktif = [], {}

    def ac(sunucu, **kw):
        aktif["s"] = sunucu
        ekran = RandevuAnaEkrani("http://testserver", "TOKEN", 11, "admin", **kw)
        ekran.chk_iptal_gizle.setChecked(False)
        ekran._sunucu = sunucu
        acik.append(ekran)
        ekran.show()
        return ekran

    with patch.object(modul, "oturum_kontrollu_istek", side_effect=lambda *a, **k: aktif["s"](*a, **k)):
        yield ac
    for e in acik:
        e.close()


def rozet(ekran, randevu_id):
    for satir in range(ekran.tablo.rowCount()):
        if ekran.tablo.item(satir, 0).text() == str(randevu_id):
            return ekran.tablo.cellWidget(satir, 6).findChild(QLabel)
    raise AssertionError(randevu_id)


def secenek(kod):
    return SimpleNamespace(data=lambda: kod)


def test_menu_konumu_sigiyorsa_sol_sigmiyorsa_sag_kenar_hizali():
    assert menu_konumu(QPoint(100, 200), 95, 130, 1000) == QPoint(100, 200)                 # sığıyor: sol kenar hizalı
    assert menu_konumu(QPoint(1250, 200), 95, 130, 1366) == QPoint(1215, 200)               # sığmıyor: sağ kenar hizalı
    assert menu_konumu(QPoint(1250, 200), 95, 95, 1366) == QPoint(1250, 200)                # rozet kadar geniş ve sığıyor


def test_isaretlenebilirlik_kurali():
    simdi = datetime.now()
    assert durum_isaretlenebilir(randevu(1, "PLANLANDI", gun=-1), simdi)
    assert durum_isaretlenebilir(randevu(1, "TAMAMLANDI", gun=-1), simdi)
    assert durum_isaretlenebilir(randevu(1, "GELMEDI", gun=-1), simdi)
    assert not durum_isaretlenebilir(randevu(1, "PLANLANDI", gun=2), simdi)       # henüz başlamadı
    assert not durum_isaretlenebilir(randevu(1, "IPTAL_EDILDI", gun=-1), simdi)   # iptal edilmiş
    assert not durum_isaretlenebilir({"durum": "PLANLANDI", "baslangic_zamani": None}, simdi)


def test_ok_yalnizca_gecmis_ve_iptal_edilmemis_randevularda(ekran_ac):
    ekran = ekran_ac(Sunucu(LISTE))
    metinler = {i: rozet(ekran, i).text() for i in range(1, 6)}
    assert metinler == {1: "Planlandı", 2: "Planlandı  ▾", 3: "Tamamlandı  ▾", 4: "İptal Edildi", 5: "Gelmedi  ▾"}
    assert rozet(ekran, 2).cursor().shape() == Qt.PointingHandCursor
    assert rozet(ekran, 1).cursor().shape() != Qt.PointingHandCursor


def test_duzenleme_yetkisi_yoksa_rozet_tiklanmaz(ekran_ac):
    ekran = ekran_ac(Sunucu(LISTE), duzenleme_yetkisi=False)
    assert all("▾" not in rozet(ekran, i).text() for i in range(1, 6))
    with patch.object(RandevuAnaEkrani, "_menuyu_goster", return_value=None) as menu:
        QTest.mouseClick(rozet(ekran, 2), Qt.LeftButton)
    menu.assert_not_called()


def test_tiklayinca_liste_rozetin_hemen_altinda_acilir_mevcut_durum_kapali(ekran_ac):
    ekran = ekran_ac(Sunucu(LISTE))
    r = rozet(ekran, 3)                                            # Tamamlandı
    cagrilar = []

    def sahte_goster(self, liste, konum):                             # gerçek exec etkileşimli döngü açıp testi bekletir
        cagrilar.append((liste, konum))
        return None

    with patch.object(RandevuAnaEkrani, "_menuyu_goster", sahte_goster):
        QTest.mouseClick(r, Qt.LeftButton)
    ((liste, konum),) = cagrilar
    sol_alt = r.mapToGlobal(QPoint(0, r.height() + 2))
    assert konum.y() == sol_alt.y()                                 # rozetin hemen altı
    assert konum.x() in (sol_alt.x(), sol_alt.x() + r.width() - max(liste.sizeHint().width(), r.width()))   # sol ya da (sığmıyorsa) sağ kenar hizalı
    assert liste.minimumWidth() == r.width()                        # en az rozet kadar geniş
    eylemler = liste.actions()
    assert [e.text() for e in eylemler] == ["Tamamlandı", "Gelmedi"]
    assert [e.isEnabled() for e in eylemler] == [False, True]       # mevcut durum seçilemez
    assert [e.data() for e in eylemler] == ["TAMAMLANDI", "GELMEDI"]
    assert not eylemler[0].icon().isNull() and not eylemler[1].icon().isNull()      # renkli nokta


@pytest.mark.parametrize("yeni", ["TAMAMLANDI", "GELMEDI"])
def test_secim_dogrudan_sunucuya_gider_onay_penceresi_yok(ekran_ac, yeni):
    sunucu = Sunucu(LISTE)
    ekran = ekran_ac(sunucu)
    r = rozet(ekran, 2)
    with patch.object(RandevuAnaEkrani, "_menuyu_goster", return_value=secenek(yeni)), \
            patch.object(QMessageBox, "question") as soru:
        QTest.mouseClick(r, Qt.LeftButton)
    soru.assert_not_called()
    assert ("PATCH", "http://testserver/api/randevular/2/durum") in sunucu.istekler
    assert sunucu.govdeler == [{"durum": yeni}]
    assert sunucu.istekler[-1][1].endswith("/api/randevular")       # sonra liste yenilenir


def test_liste_kapatilirsa_istek_gitmez(ekran_ac):
    sunucu = Sunucu(LISTE)
    ekran = ekran_ac(sunucu)
    with patch.object(RandevuAnaEkrani, "_menuyu_goster", return_value=None):
        QTest.mouseClick(rozet(ekran, 2), Qt.LeftButton)
    assert not any(y == "PATCH" for y, _ in sunucu.istekler)


@pytest.mark.parametrize("id_", [1, 4])
def test_gelecek_ve_iptal_edilmis_rozet_tiklanmaz(ekran_ac, id_):
    ekran = ekran_ac(Sunucu(LISTE))
    with patch.object(RandevuAnaEkrani, "_menuyu_goster", return_value=None) as menu:
        QTest.mouseClick(rozet(ekran, id_), Qt.LeftButton)
    menu.assert_not_called()


def test_sunucu_reddederse_mesaji_gosterilir(ekran_ac):
    ret = cevap({"detail": "Yalnızca kendi randevunuzun durumunu işaretleyebilirsiniz."}, 403)
    ekran = ekran_ac(Sunucu(LISTE, patch_cevabi=ret))
    with patch.object(RandevuAnaEkrani, "_menuyu_goster", return_value=secenek("GELMEDI")), patch.object(QMessageBox, "warning") as uyari:
        QTest.mouseClick(rozet(ekran, 2), Qt.LeftButton)
    assert uyari.call_args.args[2] == "Yalnızca kendi randevunuzun durumunu işaretleyebilirsiniz."


def test_ust_dugme_sirasi_ve_menu_baglantilari():
    ogeler = {o["ad"]: o for _, liste in mw.MENU for o in liste}
    etiketler = [e for e, _ in ogeler["Randevu Yönetimi"]["aksiyon"]]
    assert etiketler == ["＋  Yeni Randevu", "✎  Randevu Düzenle", "✕  Randevu İptal Et"]
    kaynak = open(mw.__file__, encoding="utf-8").read()
    assert "durum_isaretle(" not in kaynak                                  # üst düğmelerle işaretleme kalktı
    assert 'duzenleme_yetkisi=izin_var(self.aktif_rol, "Randevu düzenleme")' in kaynak


def test_danisanlar_sayfasindaki_rozetler_tiklanabilir_degil():
    kap, r = RandevuAnaEkrani._durum_rozeti("PLANLANDI")
    assert "▾" not in r.text() and r.cursor().shape() != Qt.PointingHandCursor
