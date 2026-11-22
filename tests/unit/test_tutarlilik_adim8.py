"""Adım 8: Bakım Planları görüntüleme izni, bakım/kalibrasyon bildirimleri ve Cihaz Raporları sayfasının güncelliği."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication

import client.bakim_plani_ekranlari as plan_modulu
import client.cihaz_raporlari_ekrani as rapor_modulu
import client.cihaz_rezervasyon_ekranlari as rez_modulu
import client.main_window as mw


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def temiz_yetkiler():
    mw._SUNUCU_YETKILERI.clear()
    yield
    mw._SUNUCU_YETKILERI.clear()


def _yanit(veri):
    y = MagicMock(status_code=200, _tkys_oturum_reddedildi=False)
    y.json.return_value = veri
    return y


# ------------------------------------------------------------------ 7) Bakım Planları görüntüleme
@pytest.mark.parametrize("izinler,gorur,yonetir", [
    (["BAKIM_KAYITLARI_GORUNTULE"], True, False),
    (["KALIBRASYON_KAYITLARI_GORUNTULE"], True, False),
    (["BAKIM_KAYITLARI_YONET"], True, True),
    (["CIHAZ_ENVANTER_YONET"], False, False),
    ([], False, False),
])
def test_planlar_sayfasi_goruntuleme_ya_da_yonetme_ile_acilir_yonetme_yalniz_yonet_izniyle(izinler, gorur, yonetir):
    mw.yetkileri_ayarla("memur", izinler)
    ana = SimpleNamespace(aktif_rol="memur")
    assert mw.AnaPencere._sayfa_izinli_mi(ana, "Bakım Planları") is gorur
    assert mw.izin_var("memur", "Bakım/kalibrasyon planlarını yönetme") is yonetir


PLANLAR = [{"plan_id": 1, "cihaz_id": 1, "envanter_kodu": "E-1", "cihaz_adi": "EEG", "gorev_turu": "Yıllık bakım", "periyot_gun": 365, "uyari_suresi_gun": 30,
            "sonraki_gorev_tarihi": (date.today() + timedelta(days=20)).isoformat(), "kalan_gun": 20, "durum": "Yaklaşıyor", "aktif_mi": True}]


def test_planlar_ekrani_yalniz_gorunteleme_modunda_duzenle_sil_ve_cift_tikla_yok():
    from client.tablo_tasarimi import satir_kimligi
    with patch.object(plan_modulu, "oturum_kontrollu_istek", return_value=_yanit(PLANLAR)):
        g = plan_modulu.BakimPlanlariEkrani("http://x", "t", yetkili_mi=False)
        y = plan_modulu.BakimPlanlariEkrani("http://x", "t")
    g.resize(1300, 400)
    g.show()
    assert g.tablo.rowCount() == 1 and g.tablo.isColumnHidden(6) and g.tablo.cellWidget(0, 6) is None and satir_kimligi(g.tablo, 0) is None
    assert "Yeni Plan" not in g.bos_mesaj.text()
    assert not y.tablo.isColumnHidden(6) and y.tablo.cellWidget(0, 6) is not None and satir_kimligi(y.tablo, 0) == 1
    g.close()
    y.close()


# ------------------------------------------------------------------ 8) bildirim ucu izne göre süzer
def _yaklasan(izinler, bakim_satirlari, kalib_satirlari, plan_satirlari=()):
    import server.sunucu as sunucu
    conn = MagicMock()
    imlec = conn.cursor.return_value
    bugun = date.today()
    imlec.fetchone.return_value = (list(izinler),)                                       # kullanıcının ilgili izinleri
    imlec.fetchall.side_effect = [
        [("E-1", "EEG", bugun + timedelta(days=g), 7) for g in bakim_satirlari],
        [("E-2", "TMS", bugun + timedelta(days=g), 30) for g in kalib_satirlari],
        list(plan_satirlari),
    ]
    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        return sunucu.yaklasan_islemler_getir(kullanici_id=1)


def test_yaklasan_islemler_envanter_yoneten_hepsini_bakim_izinli_yalniz_bakimi_gorur():
    hepsi = _yaklasan(["CIHAZ_ENVANTER_YONET"], [3], [5])
    assert {i["islem_turu"] for i in hepsi} == {"Bakım", "Kalibrasyon"}
    yalniz_bakim = _yaklasan(["BAKIM_KAYITLARI_GORUNTULE"], [3], [5])
    assert {i["islem_turu"] for i in yalniz_bakim} == {"Bakım"}
    yalniz_kalib = _yaklasan(["KALIBRASYON_KAYITLARI_YONET"], [3], [5])
    assert {i["islem_turu"] for i in yalniz_kalib} == {"Kalibrasyon"}


def test_yaklasan_islemler_plan_turune_gore_de_suzulur():
    plan = [("E-3", "EKG", "Kalibrasyon Yıllık", date.today() + timedelta(days=2), 7)]
    sonuc = _yaklasan(["BAKIM_KAYITLARI_GORUNTULE"], [], [], plan)
    assert sonuc == []                                                                  # kalibrasyon planı, yalnız bakım izinli kullanıcıya gelmez
    sonuc = _yaklasan(["KALIBRASYON_KAYITLARI_GORUNTULE"], [], [], plan)
    assert [i["islem_turu"] for i in sonuc] == ["Kalibrasyon"]


def test_ana_pencere_bildirimleri_envanter_izni_olmadan_da_bakim_uyarisini_ister():
    kaynak = open("client/main_window.py", encoding="utf-8").read()
    assert 'any(sayfa in self.nav_btnler for sayfa in ("Cihaz Envanteri", "Bakım Kayıtları", "Kalibrasyon"))' in kaynak


# ------------------------------------------------------------------ 6) rezervasyon başarı bildirimi
def test_rezervasyon_olusturunca_toast_gosterilir_modal_pencere_acilmaz():
    kaynak = open("client/cihaz_rezervasyon_ekranlari.py", encoding="utf-8").read()
    assert 'basari_bildirimi(self, "Rezervasyon oluşturuldu.")' in kaynak and "Rezervasyon başarıyla oluşturuldu!" not in kaynak


# ------------------------------------------------------------------ sekmeler arası güncellik
def test_cihaz_raporlari_sayfaya_donuldugunde_yenilenir():
    assert mw.AnaPencere.SAYFA_YENILEME["Cihaz Raporları"] == ("aktif_cihaz_rapor_ekrani", "sayfa_gosterildi")
    def bos(yontem, url, **k):
        return _yanit([] if url.endswith("/api/cihazlar") else {"bakim_ozeti": {}, "bakimlar": [], "kalibrasyonlar": [], "arizalar": [], "ozet": {}})
    with patch.object(rapor_modulu, "oturum_kontrollu_istek", bos), patch.object(rapor_modulu, "oturum_hatasi_mi", return_value=False):
        e = rapor_modulu.CihazRaporlariEkrani("http://x", "t")
        with patch.object(e, "yenile") as yenile:
            e.sayfa_gosterildi()                                     # ilk sekme açıkken: ortak süzgeçle yenilenir
            yenile.assert_called_once()
        ek_ekran = MagicMock()
        e._ek_sekmeler[3]["ekran"] = ek_ekran
        e.rapor_sekmeleri.blockSignals(True)
        e.rapor_sekmeleri.setCurrentIndex(3)
        e.rapor_sekmeleri.blockSignals(False)
        with patch.object(e, "yenile") as yenile:
            e.sayfa_gosterildi()                                     # ek sekme açıkken: yalnız o sekmenin ekranı yenilenir
            yenile.assert_not_called()
        ek_ekran.yenile.assert_called_once()
    e.close()
