"""Açık oturumda yetki yenileme: yönetici izin ya da rol değiştirince kullanıcı uygulamayı kapatmadan menüsü güncellenir.

Gerçek sunucu kullanılmaz; ağ istekleri taklit edilir.
"""
import turkce_mesaj_kutusu as tmk
import base64
import functools
import json
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

import main_window as mw
from main_window import AnaPencere


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def yetki_tablosunu_koru():
    onceki = dict(mw._SUNUCU_YETKILERI)
    yield
    mw._SUNUCU_YETKILERI.clear()
    mw._SUNUCU_YETKILERI.update(onceki)


class Yanit:
    """MagicMock değil: MagicMock her özelliği 'var' sayar ve oturum hatası gibi görünür."""
    def __init__(self, veri=None, durum=200):
        self._veri = veri
        self.status_code = durum
        self.text = "{}"
        self.headers = {}

    def json(self):
        return self._veri

    def raise_for_status(self):
        pass


# ================================================================ karar mantığı (hızlı, sahte pencere)
def sahte_pencere(**kw):
    p = SimpleNamespace(
        _oturum_kapatiliyor=False, rol_onizleme=False, token="t", _yetki_istegi_suruyor=False, _yetki_atlanan_tur=0,
        api_url="http://s", aktif_rol="memur", _sunucu_rol_adi="MEMUR",
        YETKI_HATA_SONRASI_ATLANAN_TUR=AnaPencere.YETKI_HATA_SONRASI_ATLANAN_TUR,
        _menuyu_yeniden_kur=MagicMock(), _rol_degisti_uyarisi=MagicMock(),
    )
    p.__dict__.update(kw)
    p._yeni_yetkileri_uygula = functools.partial(AnaPencere._yeni_yetkileri_uygula, p)
    return p


def denetle(p, yanit=None, hata=None, modal=None):
    istek = MagicMock(side_effect=hata) if hata else MagicMock(return_value=yanit)
    with patch.object(mw, "oturum_kontrollu_istek", istek), \
            patch.object(mw.QApplication, "activeModalWidget", return_value=modal):
        AnaPencere._yetkileri_denetle(p)
    return istek


def veri(izinler, rol="MEMUR"):
    return Yanit({"rol_adi": rol, "izinler": izinler})


@pytest.mark.parametrize("ayar", [{"_oturum_kapatiliyor": True}, {"rol_onizleme": True}, {"token": ""}, {"_yetki_istegi_suruyor": True}])
def test_oturum_kapaniyorsa_onizlemedeyse_tokensizse_ya_istek_suruyorsa_sunucuya_gidilmez(ayar):
    istek = denetle(sahte_pencere(**ayar), veri(["TAKVIM_GORUNTULE"]))
    assert not istek.called


def test_kullanici_bir_pencerede_calisiyorsa_o_turda_sunucuya_gidilmez():
    p = sahte_pencere()
    istek = denetle(p, veri(["TAKVIM_GORUNTULE"]), modal=object())
    assert not istek.called and not p._menuyu_yeniden_kur.called


def test_istek_dogru_adrese_token_ve_kisa_zaman_asimiyla_atilir():
    istek = denetle(sahte_pencere(), veri(["TAKVIM_GORUNTULE"]))
    assert istek.call_args.args == ("GET", "http://s/api/yetkilerim")
    assert istek.call_args.kwargs["headers"] == {"Authorization": "Bearer t"} and istek.call_args.kwargs["timeout"] == 2


def test_yetkiler_ayniysa_menu_yenilenmez():
    mw._SUNUCU_YETKILERI["memur"] = frozenset({"TAKVIM_GORUNTULE"})
    p = sahte_pencere()
    denetle(p, veri(["TAKVIM_GORUNTULE"]))
    assert not p._menuyu_yeniden_kur.called and not p._rol_degisti_uyarisi.called


def test_izin_eklenince_yetkiler_guncellenir_ve_menu_yeniden_kurulur():
    mw._SUNUCU_YETKILERI["memur"] = frozenset({"TAKVIM_GORUNTULE"})
    p = sahte_pencere()
    denetle(p, veri(["TAKVIM_GORUNTULE", "CIHAZ_ENVANTER_YONET"]))
    assert mw._SUNUCU_YETKILERI["memur"] == frozenset({"TAKVIM_GORUNTULE", "CIHAZ_ENVANTER_YONET"})
    p._menuyu_yeniden_kur.assert_called_once_with()


def test_izin_kaldirilinca_da_menu_yeniden_kurulur():
    mw._SUNUCU_YETKILERI["memur"] = frozenset({"TAKVIM_GORUNTULE", "CIHAZ_ENVANTER_YONET"})
    p = sahte_pencere()
    denetle(p, veri(["TAKVIM_GORUNTULE"]))
    assert mw._SUNUCU_YETKILERI["memur"] == frozenset({"TAKVIM_GORUNTULE"}) and p._menuyu_yeniden_kur.called


def test_yerel_tabloya_dusulmusken_sunucu_yetkileri_gelince_ilk_kez_uygulanir():
    mw._SUNUCU_YETKILERI.pop("memur", None)                                   # ilk alım başarısız olmuştu
    p = sahte_pencere()
    denetle(p, veri(["TAKVIM_GORUNTULE"]))
    assert mw._SUNUCU_YETKILERI["memur"] == frozenset({"TAKVIM_GORUNTULE"}) and p._menuyu_yeniden_kur.called


def test_rol_degisince_yetkiler_uygulanmaz_yeniden_giris_istenir():
    mw._SUNUCU_YETKILERI["memur"] = frozenset({"TAKVIM_GORUNTULE"})
    p = sahte_pencere()
    denetle(p, veri(["TAKVIM_GORUNTULE", "KULLANICI_OLUSTUR"], rol="MUDUR"))
    p._rol_degisti_uyarisi.assert_called_once_with()
    assert not p._menuyu_yeniden_kur.called and mw._SUNUCU_YETKILERI["memur"] == frozenset({"TAKVIM_GORUNTULE"})


def test_ilk_alimda_rol_bilinmiyorsa_rol_farki_sayilmaz():
    mw._SUNUCU_YETKILERI.pop("memur", None)
    p = sahte_pencere(_sunucu_rol_adi=None)
    denetle(p, veri(["TAKVIM_GORUNTULE"], rol="BASKA"))
    assert not p._rol_degisti_uyarisi.called and p._menuyu_yeniden_kur.called and p._sunucu_rol_adi == "BASKA"


@pytest.mark.parametrize("yanit", [Yanit({"rol_adi": "MEMUR"}), Yanit({"rol_adi": "MEMUR", "izinler": "yok"}), Yanit(["liste"]), Yanit(None), Yanit({"detail": "x"}, 500),
                                   Yanit({"detail": "yetkisiz"}, 403)])
def test_bozuk_ya_da_hatali_yanitlar_menuyu_bozmaz(yanit):
    p = sahte_pencere()
    denetle(p, yanit)
    assert not p._menuyu_yeniden_kur.called and not p._rol_degisti_uyarisi.called


def test_oturum_hatasi_yanitinda_yetkiler_uygulanmaz():
    p = sahte_pencere()
    yanit = Yanit({"rol_adi": "MEMUR", "izinler": ["X"]}, 401)
    yanit._tkys_oturum_reddedildi = True
    denetle(p, yanit)
    assert not p._menuyu_yeniden_kur.called


def test_ag_hatasinda_cokmez_ve_birkac_tur_beklenir():
    import requests
    p = sahte_pencere()
    denetle(p, hata=requests.exceptions.ConnectionError("sunucu kapalı"))
    assert p._yetki_atlanan_tur == AnaPencere.YETKI_HATA_SONRASI_ATLANAN_TUR and p._yetki_istegi_suruyor is False
    for _ in range(AnaPencere.YETKI_HATA_SONRASI_ATLANAN_TUR):
        assert not denetle(p, veri(["X"])).called                             # bekleme turları: istek yok
    assert denetle(p, veri(["X"])).called                                      # sonra yeniden denenir


def test_istek_bayragi_hata_olsa_da_temizlenir():
    p = sahte_pencere()
    denetle(p, hata=RuntimeError("beklenmedik"))
    assert p._yetki_istegi_suruyor is False


# ================================================================ ilk alım ve zamanlayıcı
def test_giriste_alinan_rol_adi_saklanir_ve_izinler_kaydedilir():
    p = SimpleNamespace(aktif_rol="memur", token="t", rol_onizleme=False, api_url="http://s")
    with patch.object(mw, "oturum_kontrollu_istek", return_value=Yanit({"rol_adi": "MEMUR", "izinler": ["TAKVIM_GORUNTULE"]})):
        AnaPencere._yetkileri_sunucudan_al(p)
    assert p._sunucu_rol_adi == "MEMUR" and mw._SUNUCU_YETKILERI["memur"] == frozenset({"TAKVIM_GORUNTULE"})


def test_zamanlayici_sadece_tokenli_ve_onizlemesiz_oturumda_calisir(qt_app):
    from PySide6.QtWidgets import QWidget

    class Ev(QWidget):
        YETKI_YENILEME_ARALIGI_MS = AnaPencere.YETKI_YENILEME_ARALIGI_MS

        def _yetkileri_denetle(self):
            pass

    for token, onizleme, beklenen in [("t", False, True), ("", False, False), ("t", True, False)]:
        ev = Ev()
        ev.token, ev.rol_onizleme = token, onizleme
        AnaPencere._yetki_zamanlayicisini_kur(ev)
        assert ev._yetki_zamanlayici.isActive() is beklenen
        assert ev._yetki_zamanlayici.interval() == AnaPencere.YETKI_YENILEME_ARALIGI_MS == 20_000
        ev._yetki_zamanlayici.stop()


def test_oturum_kapaninca_yetki_zamanlayicisi_durdurulur():
    kaynak = open(mw.__file__, encoding="utf-8").read()
    govde = kaynak[kaynak.index("    def oturum_kapat(self):"):kaynak.index("    def yeni_oda_formunu_ac")]
    assert "self._yetki_zamanlayici.stop()" in govde


# ================================================================ menüyü yeniden kurma ve rol uyarısı
def test_menu_yenilenince_acik_sayfa_hala_yetkiliyse_ona_donulur_ve_bilgi_verilir():
    ana = SimpleNamespace(stack=MagicMock(), sayfa_bilgi=[("Ana Kontrol Paneli", ""), ("Cihaz Envanteri", "")], nav_btnler={"Cihaz Envanteri": 1},
                          aktif_rol="memur", rol_uygula=MagicMock(), _bildirimden_sayfaya_git=MagicMock())
    ana.stack.currentIndex.return_value = 1
    with patch.object(tmk, "bilgi") as bilgi:
        AnaPencere._menuyu_yeniden_kur(ana)
    ana.rol_uygula.assert_called_once_with("memur")
    ana._bildirimden_sayfaya_git.assert_called_once_with("Cihaz Envanteri")
    assert bilgi.call_args.args[1] == "Yetkileriniz Güncellendi"


def test_menu_yenilenince_acik_sayfanin_yetkisi_gittiyse_oraya_gidilmez():
    ana = SimpleNamespace(stack=MagicMock(), sayfa_bilgi=[("Ana Kontrol Paneli", ""), ("Cihaz Envanteri", "")], nav_btnler={},
                          aktif_rol="memur", rol_uygula=MagicMock(), _bildirimden_sayfaya_git=MagicMock())
    ana.stack.currentIndex.return_value = 1
    with patch.object(tmk, "bilgi"):
        AnaPencere._menuyu_yeniden_kur(ana)
    assert not ana._bildirimden_sayfaya_git.called


def test_rol_degisti_uyarisi_zamanlayiciyi_durdurur_mesaj_verir_ve_oturumu_kapatir():
    ana = SimpleNamespace(_yetki_zamanlayici=MagicMock(), oturum_kapat=MagicMock())
    with patch.object(tmk, "bilgi") as bilgi:
        AnaPencere._rol_degisti_uyarisi(ana)
    assert ana._yetki_zamanlayici.stop.called and ana.oturum_kapat.called
    assert bilgi.call_args.args[1] == "Rolünüz Değişti" and "yeniden giriş" in bilgi.call_args.args[2]


# ================================================================ gerçek ana pencere (uçtan uca, ağ taklit)
def sahte_token():
    yuk = base64.urlsafe_b64encode(json.dumps({"exp": int(time.time()) + 99999}).encode()).decode().rstrip("=")
    return f"a.{yuk}.c"


@pytest.fixture
def gercek_pencere(qt_app):
    durum = {"rol_adi": "MEMUR", "izinler": ["TAKVIM_GORUNTULE", "ODA_DURUMU_GORUNTULE"]}

    def sahte_istek(self, method=None, url=None, *a, **k):
        return Yanit(durum if str(url).endswith("/api/yetkilerim") else {})

    with patch("requests.sessions.Session.request", sahte_istek), patch.object(tmk, "bilgi") as bilgi, \
            patch.object(tmk, "uyari"), patch.object(tmk, "hata"):
        ana = AnaPencere(aktif_rol="memur", kullanici_adi="m", token=sahte_token(), kullanici_id=2)
        yield ana, durum, bilgi
        ana._yetki_zamanlayici.stop()
        ana._oturum_zamanlayici.stop()
        ana.deleteLater()


def test_gercek_pencere_izin_eklenince_yeni_sekmeler_kendiliginden_gelir(gercek_pencere):
    ana, durum, bilgi = gercek_pencere
    assert list(ana.nav_btnler) == ["Ana Kontrol Paneli", "Randevu Yönetimi", "Oda Kullanımı"]
    durum["izinler"] += ["CIHAZ_ENVANTER_YONET", "BAKIM_KAYITLARI_YONET"]
    ana._yetkileri_denetle()                                                       # zamanlayıcının bir turu
    assert {"Cihaz Envanteri", "Bakım Kayıtları", "Bakım Planları", "Cihaz Raporları"} <= set(ana.nav_btnler)
    assert bilgi.call_args.args[1] == "Yetkileriniz Güncellendi"


def test_gercek_pencere_izin_kaldirilinca_sekmeler_kendiliginden_kaybolur(gercek_pencere):
    ana, durum, _ = gercek_pencere
    durum["izinler"] = ["TAKVIM_GORUNTULE"]
    ana._yetkileri_denetle()
    assert list(ana.nav_btnler) == ["Ana Kontrol Paneli", "Randevu Yönetimi"]


def test_gercek_pencere_degisiklik_yoksa_menu_ve_sayfalar_yeniden_olusmaz(gercek_pencere):
    ana, _, bilgi = gercek_pencere
    onceki = ana.stack.widget(0)
    ana._yetkileri_denetle()
    assert ana.stack.widget(0) is onceki and not bilgi.called


def test_gercek_pencere_rol_degisince_oturum_kapatilir(gercek_pencere):
    ana, durum, bilgi = gercek_pencere
    ana.oturum_kapat = MagicMock()
    durum["rol_adi"] = "MUDUR"
    ana._yetkileri_denetle()
    assert ana.oturum_kapat.called and bilgi.call_args.args[1] == "Rolünüz Değişti"
