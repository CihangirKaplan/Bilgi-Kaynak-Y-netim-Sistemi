"""
Oda Yönetimi sayfası her açıldığında yenilenir.

Sayfalar açılışta bir kez kurulur; bu yüzden tablo yalnızca uygulama açılırken doluyordu ve başka
ekranda yapılan değişiklikler (örn. bir psikoloğa oda atamak) ancak yeniden giriş yapınca görünüyordu.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import client.main_window as mw
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


# ------------------------------------------------------------------ Kullanım, Planlı randevu, pasifleri gizleme, sıralama
def _odalar_ve_planlilar(odalar, planlilar):
    def istek(yontem, url, **kwargs):
        if url.endswith("/api/oda-planli-randevu-sayilari"):
            return cevap(planlilar)
        return cevap(odalar)
    return istek


def _yedi_sutunlu_pencere(atamalar, goster=False):
    from PySide6.QtWidgets import QCheckBox
    tablo = QTableWidget()
    tablo.setColumnCount(7)
    kutu = QCheckBox()
    kutu.setChecked(goster)
    return SimpleNamespace(oda_tablosu=tablo, api_url="http://testserver", token="TOKEN",
                           oda_psikolog_atamalarini_getir=lambda: atamalar, oda_pasifleri_goster=kutu)


ODALAR_PASIFLI = [
    {"oda_id": 1, "oda_adi": "EEG Odası", "kapasite": 1, "aktif_mi": True},
    {"oda_id": 2, "oda_adi": "Görüşme Odası-2", "kapasite": 1, "aktif_mi": True},
    {"oda_id": 3, "oda_adi": "Deneme Odası", "kapasite": 1, "aktif_mi": False},
]


def test_kullanim_sutunu_psikolog_odasini_ortak_odadan_ayirir(tkys_qapplication):
    ana = _yedi_sutunlu_pencere({2: "psikolog2"})
    with patch.object(mw, "oturum_kontrollu_istek", side_effect=_odalar_ve_planlilar(ODALAR_PASIFLI, [])):
        mw.AnaPencere.odalari_getir(ana)
    assert [ana.oda_tablosu.item(i, 5).text() for i in range(3)] == ["Ortak oda", "Psikolog odası", "Ortak oda"]
    assert "cihaz rezervasyonunda kullanılamaz" in ana.oda_tablosu.item(1, 5).toolTip()


def test_planli_randevu_sutunu_sayiyi_gosterir_olmayana_tire_koyar(tkys_qapplication):
    ana = _yedi_sutunlu_pencere({})
    planlilar = [{"oda_id": 2, "planli_randevu": 3}]
    with patch.object(mw, "oturum_kontrollu_istek", side_effect=_odalar_ve_planlilar(ODALAR_PASIFLI, planlilar)):
        mw.AnaPencere.odalari_getir(ana)
    assert [ana.oda_tablosu.item(i, 6).text() for i in range(3)] == ["-", "3", "-"]
    assert "pasife alınamaz" in ana.oda_tablosu.item(1, 6).toolTip()


def test_planli_kayit_sutunu_randevu_rezervasyon_ve_etkinligi_toplar(tkys_qapplication):
    ana = _yedi_sutunlu_pencere({})
    planlilar = [{"oda_id": 2, "planli_randevu": 1, "cihaz_rezervasyonu": 2, "etkinlik": 1}]
    with patch.object(mw, "oturum_kontrollu_istek", side_effect=_odalar_ve_planlilar(ODALAR_PASIFLI, planlilar)):
        mw.AnaPencere.odalari_getir(ana)
    assert ana.oda_tablosu.item(1, 6).text() == "4"
    ipucu = ana.oda_tablosu.item(1, 6).toolTip()
    assert "1 planlı randevu" in ipucu and "2 cihaz rezervasyonu" in ipucu and "1 etkinlik" in ipucu


def test_planli_randevu_sayilari_alinamazsa_tablo_yine_dolar(tkys_qapplication):
    """Yetki ya da ağ sorunu yüzünden sayılar gelmezse sütun "-" gösterir; oda listesi bozulmaz."""
    ana = _yedi_sutunlu_pencere({})

    def istek(yontem, url, **kwargs):
        if url.endswith("/api/oda-planli-randevu-sayilari"):
            raise RuntimeError("ağ yok")
        return cevap(ODALAR_PASIFLI)

    with patch.object(mw, "oturum_kontrollu_istek", side_effect=istek):
        mw.AnaPencere.odalari_getir(ana)
    assert ana.oda_tablosu.rowCount() == 3 and ana.oda_tablosu.item(1, 6).text() == "-"


def test_pasif_odalar_varsayilan_gizli_kutu_isaretlenince_gorunur(tkys_qapplication):
    ana = _yedi_sutunlu_pencere({}, goster=False)
    with patch.object(mw, "oturum_kontrollu_istek", side_effect=_odalar_ve_planlilar(ODALAR_PASIFLI, [])):
        mw.AnaPencere.odalari_getir(ana)
    assert [ana.oda_tablosu.isRowHidden(i) for i in range(3)] == [False, False, True]          # pasif oda gizli

    ana.oda_pasifleri_goster.setChecked(True)
    mw.AnaPencere.oda_pasif_gorunurlugu_uygula(ana)
    assert [ana.oda_tablosu.isRowHidden(i) for i in range(3)] == [False, False, False]         # kutu işaretlenince görünür

    ana.oda_pasifleri_goster.setChecked(False)
    mw.AnaPencere.oda_pasif_gorunurlugu_uygula(ana)
    assert ana.oda_tablosu.isRowHidden(2) is True


def test_yenilemede_pasif_gizleme_kutunun_durumunu_korur(tkys_qapplication):
    ana = _yedi_sutunlu_pencere({}, goster=True)
    with patch.object(mw, "oturum_kontrollu_istek", side_effect=_odalar_ve_planlilar(ODALAR_PASIFLI, [])):
        mw.AnaPencere.odalari_getir(ana)                                                       # kutu işaretliyken yenileme: pasifler görünür kalır
    assert not any(ana.oda_tablosu.isRowHidden(i) for i in range(3))


def test_oda_yonetimi_tablosu_kurulurken_id_sutunu_gizli_ve_siralama_bagli():
    """Tablo yalnızca sayfa kurulurken oluşturulduğu için kurulum kodu kaynaktan denetlenir."""
    import inspect
    kaynak = inspect.getsource(mw.AnaPencere)
    assert 'setHorizontalHeaderLabels(["Oda ID", "Oda Adı", "Kapasite", "Durum", "Psikologlar", "Kullanım", "Planlı kayıt"])' in kaynak
    assert "self.oda_tablosu.setColumnHidden(0, True)" in kaynak
    assert "siralanabilir_yap(self.oda_tablosu)" in kaynak


# ------------------------------------------------------------------ Oda formu (aktiflik onay kutusu yok) ve Pasife Al / Aktif Et düğmesi
def _form(oda_id=None):
    from client.oda_yonetimi import OdaFormu
    eski = {"oda_adi": "Gözlem Odası", "kapasite": 1, "aktif_mi": False} if oda_id else None
    return OdaFormu(api_url="http://testserver", token="TOKEN", oda_id=oda_id, eski_veriler=eski)


def _etiketler(form):
    from PySide6.QtWidgets import QCheckBox, QLabel
    return [e.text() for e in form.findChildren(QLabel)], form.findChildren(QCheckBox)


def test_yeni_oda_formunda_onay_kutusu_yok_aktif_bilgisi_yazi_olarak_var(tkys_qapplication):
    yazilar, kutular = _etiketler(_form())
    assert kutular == [] and "Bu oda aktif olarak kullanılabilir." in yazilar


def test_oda_duzenle_formunda_ne_onay_kutusu_ne_aktiflik_yazisi_var(tkys_qapplication):
    yazilar, kutular = _etiketler(_form(oda_id=8))
    assert kutular == [] and "Bu oda aktif olarak kullanılabilir." not in yazilar


def _gonderilen(form, ad="Gözlem Odası"):
    form.in_oda_adi.setText(ad)
    istek = MagicMock(return_value=cevap({}))
    with patch("client.oda_yonetimi.oturum_kontrollu_istek", istek), patch("client.oda_yonetimi.basari_bildirimi"):
        form.odayi_kaydet()
    return istek.call_args


def test_yeni_oda_aktif_olarak_kaydedilir_duzenleme_odanin_durumuna_dokunmaz(tkys_qapplication):
    yeni = _gonderilen(_form())
    assert yeni.args[0] == "POST" and yeni.kwargs["json"]["aktif_mi"] is True
    duzenle = _gonderilen(_form(oda_id=8))
    assert duzenle.args[0] == "PATCH" and "aktif_mi" not in duzenle.kwargs["json"]


def _durum_penceresi(durum, secili=True):
    from PySide6.QtWidgets import QAbstractItemView, QPushButton, QTableWidgetItem
    tablo = QTableWidget(2, 4)
    tablo.setSelectionBehavior(QAbstractItemView.SelectRows)
    for satir, (oda_id, ad, d) in enumerate([(7, "A Odası", "Aktif"), (8, "Gözlem Odası", durum)]):
        for sutun, deger in enumerate([str(oda_id), ad, "1", d]):
            tablo.setItem(satir, sutun, QTableWidgetItem(deger))
    if secili:
        tablo.selectRow(1)
    dugme = QPushButton(mw.ODA_PASIFE_AL_ETIKETI)
    ana = SimpleNamespace(oda_tablosu=tablo, oda_durum_butonu=dugme, api_url="http://testserver", token="TOKEN",
                          odalari_getir=MagicMock())
    return ana, dugme


def test_dugme_pasif_odada_aktif_et_aktif_odada_pasife_al_olur(tkys_qapplication):
    ana, dugme = _durum_penceresi("Pasif")
    mw.AnaPencere.oda_durum_butonunu_guncelle(ana)
    assert dugme.text() == mw.ODA_AKTIF_ET_ETIKETI
    ana.oda_tablosu.selectRow(0)
    mw.AnaPencere.oda_durum_butonunu_guncelle(ana)
    assert dugme.text() == mw.ODA_PASIFE_AL_ETIKETI
    ana.oda_tablosu.clearSelection()
    mw.AnaPencere.oda_durum_butonunu_guncelle(ana)
    assert dugme.text() == mw.ODA_PASIFE_AL_ETIKETI


def _durumu_degistir(ana, onay=True):
    from PySide6.QtWidgets import QMessageBox
    istek = MagicMock(return_value=cevap({}))
    bildirim = MagicMock()
    with patch.object(mw, "oturum_kontrollu_istek", istek), patch.object(mw, "basari_bildirimi", bildirim), \
            patch.object(QMessageBox, "question", return_value=QMessageBox.Yes if onay else QMessageBox.No):
        mw.AnaPencere.oda_durumunu_degistir(ana)
    return istek, bildirim


def test_pasif_oda_secili_iken_dugme_odayi_yeniden_aktif_eder(tkys_qapplication):
    ana, _ = _durum_penceresi("Pasif")
    istek, bildirim = _durumu_degistir(ana)
    assert istek.call_args.args[:2] == ("PATCH", "http://testserver/api/odalar/8") and istek.call_args.kwargs["json"] == {"aktif_mi": True}
    assert "aktif edildi" in bildirim.call_args.args[1]
    ana.odalari_getir.assert_called_once()


def test_aktif_oda_secili_iken_dugme_odayi_pasife_alir_onay_verilmezse_hicbir_sey_yapmaz(tkys_qapplication):
    ana, _ = _durum_penceresi("Aktif")
    istek, bildirim = _durumu_degistir(ana)
    assert istek.call_args.kwargs["json"] == {"aktif_mi": False} and "pasife alındı" in bildirim.call_args.args[1]
    ana2, _ = _durum_penceresi("Aktif")
    istek2, _ = _durumu_degistir(ana2, onay=False)
    istek2.assert_not_called()
