"""Kısayollar (Ctrl+N, Ctrl+F, F5, F1), Hakkında/Yardım penceresi ve Sistem Durumu ekranı (gerçek ana pencere, ağ taklit)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLineEdit, QPushButton

import client.hakkinda_dialog as hakkinda
import client.main_window as mw
import client.sistem_durumu_ekrani as sd_ekran
from client.hakkinda_dialog import HakkindaDialog, KISAYOLLAR, destek_metni
from client.sistem_durumu_ekrani import SistemDurumuEkrani, gecen_metni, yedek_ozeti
from test_sayfa_basligi_ust_cubukta import pencere_ac, qt_app, sayfaya_git, yetki_tablosunu_koru  # noqa: F401


def _yanit(veri, durum=200):
    y = MagicMock(status_code=durum, _tkys_oturum_reddedildi=False)
    y.json.return_value = veri
    return y


# ------------------------------------------------------------------ kısayollar
def test_kisayollar_kurulur_ve_tuslari_dogru(pencere_ac):
    ana = pencere_ac(["TAKVIM_GORUNTULE"])
    tuslar = sorted(k.key().toString() for k in ana._kisayollar)
    assert tuslar == sorted(["Ctrl+N", "Ctrl+F", "F5", "F1"])
    ana.kisayollari_kur()                                                  # ikinci çağrı tekrar kurmaz
    assert len(ana._kisayollar) == 4


def test_ctrl_n_sayfadaki_yeni_dugmesine_basar(pencere_ac):
    ana = pencere_ac(["TAKVIM_GORUNTULE", "RANDEVU_OLUSTUR"])
    sayfaya_git(ana, "Randevu Yönetimi")
    with patch.object(ana, "yeni_randevu_ekrani_ac") as ac:
        yeni = next(b for b in ana.stack.currentWidget().findChildren(QPushButton) if "Yeni Randevu" in b.text())
        yeni.clicked.disconnect()
        yeni.clicked.connect(ac)
        assert ana.kisayol_yeni() is True
    ac.assert_called_once()


def test_ctrl_n_yeni_islemi_olmayan_sayfada_hicbir_sey_yapmaz(pencere_ac):
    ana = pencere_ac(["TAKVIM_GORUNTULE"])                                 # işlem yetkisi yok: ＋ düğmesi yok
    sayfaya_git(ana, "Randevu Yönetimi")
    assert ana.kisayol_yeni() is False


def test_ctrl_f_arama_kutusuna_odaklanir(pencere_ac):
    ana = pencere_ac(["TAKVIM_GORUNTULE"])
    sayfaya_git(ana, "Randevu Yönetimi")
    assert ana.kisayol_ara() is True
    odak = QApplication.focusWidget()
    assert isinstance(odak, QLineEdit) and "ara" in odak.placeholderText().lower()


def test_f5_sayfayi_throttle_sinirina_takilmadan_yeniler(pencere_ac):
    ana = pencere_ac(["TAKVIM_GORUNTULE"])
    sayfaya_git(ana, "Randevu Yönetimi")
    cagri = []
    ana.randevu_ana_ekrani.verileri_cek = lambda *a: cagri.append(1)
    ana._sayfayi_yenile("Randevu Yönetimi")                                # ilk çağrı: sınır başlar
    ana._sayfayi_yenile("Randevu Yönetimi")                                # 2 sn içinde ikinci: yok sayılır
    assert len(cagri) <= 1
    onceki = len(cagri)
    assert ana.kisayol_yenile() is True                                    # F5 sınırı yok sayar
    assert len(cagri) == onceki + 1


def test_f1_ve_soru_isareti_hakkinda_penceresini_acar(pencere_ac):
    ana = pencere_ac(["TAKVIM_GORUNTULE"])
    assert ana.btn_yardim.toolTip().endswith("(F1)")
    assert ana.btn_yardim.text() == "ⓘ  Yardım"                       # soru işareti yerine açık etiket
    with patch.object(mw, "QMessageBox"), patch("client.hakkinda_dialog.HakkindaDialog.exec") as exec_:
        ana.yardim_ac()
    exec_.assert_called_once()


# ------------------------------------------------------------------ Hakkında / Yardım
def _dialog(surum="1.0.0", durum=200):
    cevap = _yanit({"uygulama": "TKYS", "surum": surum, "sema_surumu": "abc123"}, durum)
    with patch.object(hakkinda, "oturum_kontrollu_istek", return_value=cevap):
        return HakkindaDialog("http://sunucu:8000/", "GIZLI-TOKEN", "ayse", "admin")


def test_hakkinda_surumleri_gosterir_token_gostermez(qt_app):
    d = _dialog()
    metin = " ".join(e.text() for e in d.findChildren(__import__("PySide6.QtWidgets", fromlist=["QLabel"]).QLabel))
    assert "1.0.0" in metin and "abc123" in metin and "ayse / admin" in metin and "http://sunucu:8000" in metin
    assert "GIZLI-TOKEN" not in metin and d.surum_uyarisi.isHidden()
    assert d.sekmeler.count() == 3


def test_hakkinda_surum_farkini_uyarir_ve_sunucu_yoksa_alinamadi_der(qt_app):
    assert not _dialog(surum="9.9.9").surum_uyarisi.isHidden()
    with patch.object(hakkinda, "oturum_kontrollu_istek", side_effect=hakkinda.requests.ConnectionError("yok")):
        d = HakkindaDialog("http://x", "T", "k", "r")
    assert d.sunucu_bilgisi is None
    assert "alınamadı" in destek_metni("1.0.0", None, "k", "r", "http://x")


def test_destek_metni_kopyalanir_ve_gizli_bilgi_icermez(qt_app):
    d = _dialog()
    d.destek_bilgisini_kopyala()
    pano = QApplication.clipboard().text()
    assert "İstemci sürümü: " in pano and "Sunucu sürümü: 1.0.0" in pano and "Veritabanı şema sürümü: abc123" in pano
    assert "GIZLI-TOKEN" not in pano and "parola" not in pano.lower()
    assert d.kopyala_btn.text().startswith("Kopyalandı")


def test_kisayol_listesi_yardimda_gosterilir(qt_app):
    d = _dialog()
    assert d.kisayol_tablosu.rowCount() == len(KISAYOLLAR)
    tuslar = {d.kisayol_tablosu.item(s, 0).text() for s in range(d.kisayol_tablosu.rowCount())}
    assert {"Ctrl + N", "Ctrl + F", "F5", "F1"} <= tuslar


def test_hakkinda_dogru_uygulama_adini_gosterir_ve_eski_yanlis_adi_icermez(qt_app):
    from PySide6.QtWidgets import QLabel
    d = _dialog()
    metin = " ".join(e.text() for e in d.findChildren(QLabel))
    assert "Travma Kaynak Yönetim Sistemi" in metin and "Terapi Kaynak" not in metin


def test_hakkinda_acik_koyu_temadan_bagimsiz_renk_belirtir_ve_surum_durumu_gosterir(qt_app):
    d = _dialog()
    assert "background: #F3F6FC" in d.styleSheet() and "color: #243653" in d.styleSheet()       # işletim sistemi teması okunabilirliği bozmaz
    assert not d.surum_durumu.isHidden() and "uyumlu" in d.surum_durumu.text() and d.surum_uyarisi.isHidden()
    farkli = _dialog(surum="9.9.9")
    assert farkli.surum_durumu.isHidden() and not farkli.surum_uyarisi.isHidden()


def test_yardim_sekmesi_baslikli_bolumler_icerir(qt_app):
    from PySide6.QtWidgets import QLabel
    d = _dialog()
    yardim = d.sekmeler.widget(2)
    metin = " ".join(e.text() for e in yardim.findChildren(QLabel))
    for baslik in ("Başlarken", "Listeler ve arama", "Excel ya da PDF olarak kaydetme", "Kişisel veriler", "Sorun bildirme"):
        assert baslik in metin, baslik


# ------------------------------------------------------------------ Sistem Durumu
DURUM = {
    "uygulama": "TKYS", "surum": "1.0.0", "sema_surumu": "c3f8a1d6e725", "veritabani_boyutu_mb": 12.5,
    "yedek": {"var": True, "tarih": "2026-11-20T03:00:00", "gecen_saat": 5.2, "eski": False, "adet": 7, "boyut_mb": 1.25},
    "oturum_suresi_dk": 45, "basarisiz_giris_24s": 3,
    "son_girisler": [{"kullanici_adi": "ayse", "rol": "Yönetici", "zaman": "2026-11-20T08:05:00"}],
    "sayilar": {"aktif_kullanici": 9, "randevu": 120, "danisan_kodu": 40},
}


def _ekran(veri=DURUM, durum=200):
    with patch.object(sd_ekran, "oturum_kontrollu_istek", return_value=_yanit(veri, durum)):
        return SistemDurumuEkrani("http://x", "T")


def test_sistem_durumu_kartlari_ve_girisleri_gosterir(qt_app):
    e = _ekran()
    assert e.kartlar["surum"][1].text() == "1.0.0" and e.kartlar["sema"][1].text() == "c3f8a1d6e725"
    assert e.kartlar["boyut"][1].text() == "12.5 MB"
    assert "20.11.2026 03:00" in e.kartlar["yedek"][1].text() and "7 yedek" in e.kartlar["yedek"][2].text()
    assert e.tablo.rowCount() == 1 and e.tablo.item(0, 0).text() == "ayse"
    assert "3 başarısız giriş" in e.ozet.text() and "120 randevu" in e.ozet.text()
    assert e.bos_mesaj.isHidden()


def test_sistem_durumu_yedek_yok_ve_eski_uyarir(qt_app):
    assert yedek_ozeti({"var": False})[2] == sd_ekran.KOTU
    assert yedek_ozeti({"var": True, "tarih": "2026-11-10T03:00:00", "gecen_saat": 240, "eski": True, "adet": 1, "boyut_mb": 1})[2] == sd_ekran.UYARI
    assert yedek_ozeti(DURUM["yedek"])[2] == sd_ekran.IYI
    e = _ekran({**DURUM, "yedek": {"var": False}, "son_girisler": []})
    assert "Yedek bulunamadı" in e.kartlar["yedek"][1].text() and not e.bos_mesaj.isHidden()


def test_sistem_durumu_surum_farkini_gosterir_ve_sure_metni(qt_app):
    e = _ekran({**DURUM, "surum": "2.0.0"})
    assert "sunucudan farklı" in e.kartlar["surum"][2].text()
    assert gecen_metni(0.2) == "1 saatten kısa süre önce" and gecen_metni(5.7) == "5 saat önce" and gecen_metni(72) == "3 gün önce"


def test_sistem_durumu_menude_yetkiyle_ve_yenilemede(qt_app):
    oge = next(o for _, og in mw.MENU for o in og if o["ad"] == "Sistem Durumu")
    assert oge["izin"] == "Audit kayıtlarını inceleme"
    assert mw.AnaPencere.SAYFA_YENILEME["Sistem Durumu"] == ("sistem_durumu_ekrani", "yenile")


def test_surum_istemci_ve_sunucuda_ayni():
    import client.surum as c
    import server.surum as s
    assert (c.SURUM, c.UYGULAMA_ADI) == (s.SURUM, s.UYGULAMA_ADI)
