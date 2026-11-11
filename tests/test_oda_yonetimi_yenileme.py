"""
Oda Yönetimi sayfası her açıldığında yenilenir.

Sayfalar açılışta bir kez kurulur; bu yüzden tablo yalnızca uygulama açılırken doluyordu ve başka
ekranda yapılan değişiklikler (örn. bir psikoloğa oda atamak) ancak yeniden giriş yapınca görünüyordu.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import main_window as mw
from PySide6.QtWidgets import QTableWidget


def pencere():
    ana = MagicMock()
    ana.SAYFA_YENILEME = mw.AnaPencere.SAYFA_YENILEME
    ana.SAYFA_YENILEME_ARALIGI = mw.AnaPencere.SAYFA_YENILEME_ARALIGI
    ana._sayfa_son_yenileme = {}
    return ana


def test_oda_yonetimi_yenileme_listesinde_ve_ana_pencerenin_kendi_yontemini_kullanir():
    assert mw.AnaPencere.SAYFA_YENILEME["Oda Yönetimi"] == (None, "odalari_getir")


def test_sayfa_acilinca_oda_tablosu_yenilenir():
    ana = pencere()
    mw.AnaPencere._sayfayi_yenile(ana, "Oda Yönetimi")
    ana.odalari_getir.assert_called_once()


def test_diger_sayfalarin_yenilemesi_etkilenmez():
    ekran = MagicMock()
    ana = pencere()
    ana.aktif_personel_ekrani = ekran
    mw.AnaPencere._sayfayi_yenile(ana, "Kullanıcı & Personel")
    ekran.verileri_cek.assert_called_once()
    ana.odalari_getir.assert_not_called()


def test_art_arda_gecis_sinirlanir_sure_dolunca_tekrar_yenilenir():
    ana = pencere()
    with patch.object(mw.time, "monotonic", side_effect=[100.0, 100.5, 103.0]):
        for _ in range(3):
            mw.AnaPencere._sayfayi_yenile(ana, "Oda Yönetimi")
    assert ana.odalari_getir.call_count == 2


def test_yenileme_hatasi_uygulamayi_cokertmez():
    ana = pencere()
    ana.odalari_getir.side_effect = RuntimeError("sunucu yok")
    mw.AnaPencere._sayfayi_yenile(ana, "Oda Yönetimi")
    ana.odalari_getir.assert_called_once()


def test_sayfa_ac_oda_yonetimi_icin_yenilemeyi_tetikler():
    ana = MagicMock()
    ana.sayfa_bilgi = [("Ana Kontrol Paneli", ""), ("Oda Yönetimi", "")]
    ana.master_stack, ana.stack = MagicMock(), MagicMock()
    mw.AnaPencere.sayfa_ac(ana, 1)
    ana._sayfayi_yenile.assert_called_once_with("Oda Yönetimi")


# ------------------------------------------------------------------ tablo gerçekten güncel veriyi gösterir
def cevap(veri):
    yanit = MagicMock()
    yanit.status_code = 200
    yanit.json.return_value = veri
    yanit._tkys_oturum_reddedildi = False
    return yanit


ODALAR = [
    {"oda_id": 1, "oda_adi": "EEG Odası", "kapasite": 1, "aktif_mi": True},
    {"oda_id": 2, "oda_adi": "Deneme Odası 1", "kapasite": 1, "aktif_mi": True},
]


def tablo_pencere(atamalar):
    tablo = QTableWidget()
    tablo.setColumnCount(5)
    return SimpleNamespace(
        oda_tablosu=tablo, api_url="http://testserver", token="TOKEN",
        oda_psikolog_atamalarini_getir=lambda: atamalar["simdiki"],
    )


def psikolog_sutunu(ana):
    return [ana.oda_tablosu.item(i, 4).text() for i in range(ana.oda_tablosu.rowCount())]


def test_psikologlar_sutunu_her_yenilemede_guncel_atamayi_gosterir():
    atamalar = {"simdiki": {}}
    ana = tablo_pencere(atamalar)
    with patch.object(mw, "oturum_kontrollu_istek", return_value=cevap(ODALAR)):
        mw.AnaPencere.odalari_getir(ana)
        assert psikolog_sutunu(ana) == ["-", "-"]                  # cihaz odası ve atanmamış oda: "-"

        atamalar["simdiki"] = {2: "deneme_kisi"}                    # başka ekranda atama yapıldı
        mw.AnaPencere.odalari_getir(ana)                            # sayfaya dönünce yenileme
        assert psikolog_sutunu(ana) == ["-", "deneme_kisi"]

        atamalar["simdiki"] = {}                                    # psikologluktan çıkarıldı
        mw.AnaPencere.odalari_getir(ana)
        assert psikolog_sutunu(ana) == ["-", "-"]
