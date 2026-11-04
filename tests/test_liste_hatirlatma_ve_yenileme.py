"""Bakım/kalibrasyon listesinde hatırlatma sütunu, kayıt başına uyarı kuralı, sayfaya geçince yenileme."""
import datetime
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication, QLabel

import cihaz_bakim_ekranlari as bakim
import cihaz_kalibrasyon_ekranlari as kalib
import main_window as mw
from tablo_tasarimi import hatirlatma_metni, kalan_gun_hapi

BUGUN = datetime.date.today()


def gun(n):
    return (BUGUN + datetime.timedelta(days=n)).isoformat()


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def cevap(veri):
    r = MagicMock()
    r._tkys_oturum_reddedildi = False
    r.status_code = 200
    r.json.return_value = veri
    r.raise_for_status.return_value = None
    return r


def hap_metni(tablo, satir, sutun):
    return tablo.cellWidget(satir, sutun).findChild(QLabel).text()


# --------------------------------------------------------------- yardımcılar
@pytest.mark.parametrize("deger, beklenen", [(0, "Geldiği gün"), (7, "7 gün önce"), (45, "45 gün önce"),
                                             (None, "-"), ("x", "-")])
def test_hatirlatma_metni(deger, beklenen):
    assert hatirlatma_metni(deger) == beklenen


def test_kalan_gun_hapi_kayit_basina_uyari_suresini_kullanir(qt_app):
    # 20 gün kala: hatırlatma 30 ise yaklaşıyor, 10 ise henüz iyi; varsayılan eski 30 gün kuralıdır
    assert kalan_gun_hapi(gun(20), 30)[1] == "yaklasiyor"
    assert kalan_gun_hapi(gun(20), 10)[1] == "iyi"
    assert kalan_gun_hapi(gun(20))[1] == "yaklasiyor"
    assert kalan_gun_hapi(gun(10), 10)[1] == "yaklasiyor"          # sınır dahil
    assert kalan_gun_hapi(gun(-1), 0)[1] == "gecmis"
    assert kalan_gun_hapi(gun(0), 0)[1] == "yaklasiyor"


# --------------------------------------------------------------- bakım listesi
def bakim_ekrani(kayitlar):
    with patch.object(bakim, "oturum_kontrollu_istek", return_value=cevap(kayitlar)):
        return bakim.BakimYonetimEkrani("http://x", "T")


def bakim_kaydi(bid, sonraki, uyari):
    return {"bakim_id": bid, "cihaz_adi": f"C{bid}", "bakim_yapan_kisi": "k", "yapilan_islem": "i",
            "maliyet": 0, "bakim_baslangic_tarihi": gun(-30), "bakim_bitis_tarihi": gun(-30),
            "sonraki_bakim_tarihi": sonraki, "uyari_suresi_gun": uyari}


def test_bakim_listesinde_hatirlatma_sutunu_ve_kayit_basina_yaklasan_sayaci(qt_app):
    e = bakim_ekrani([bakim_kaydi(1, gun(20), 30),      # uyarı süresinde -> yaklaşan
                      bakim_kaydi(2, gun(20), 10),      # 20 gün kala ama süresi 10 -> yaklaşan değil
                      bakim_kaydi(3, gun(-2), 30),      # gecikmiş
                      bakim_kaydi(4, None, 30)])        # planlanmamış
    basliklar = [e.tablo.horizontalHeaderItem(i).text() for i in range(e.tablo.columnCount())]
    assert basliklar[-2:] == ["HATIRLATMA", "İŞLEM"]
    assert [e.tablo.item(i, 6).text() for i in range(4)] == ["30 gün önce", "10 gün önce", "30 gün önce", "-"]
    assert e.cip_yaklasan.text() == "1 yaklaşan" and e.cip_gecmis.text() == "1 gecikmiş"
    assert e.tablo.cellWidget(0, 7) is not None                      # işlem butonları yeni sütunda


def test_bakim_duzenle_ve_sil_butonlari_dogru_kaydi_acar(qt_app):
    e = bakim_ekrani([bakim_kaydi(1, gun(20), 30), bakim_kaydi(2, gun(50), 15)])
    from PySide6.QtWidgets import QPushButton
    duzenle = e.tablo.cellWidget(1, 7).findChildren(QPushButton)[0]
    with patch.object(bakim, "BakimDuzenleFormu") as form:
        form.return_value.exec.return_value = 0
        duzenle.click()
    assert form.call_args.args[2]["bakim_id"] == 2


# --------------------------------------------------------------- kalibrasyon listesi
def test_kalibrasyon_listesinde_hatirlatma_sutunu(qt_app):
    kayitlar = [
        {"kalibrasyon_id": i, "cihaz_adi": f"K{i}", "kalibrasyon_yapan_kurum": "k", "sertifika_no": "s",
         "kalibrasyon_baslangic_tarihi": gun(-300), "kalibrasyon_bitis_tarihi": gun(-300),
         "gecerlilik_tarihi": g, "uyari_suresi_gun": u}
        for i, (g, u) in enumerate([(gun(20), 30), (gun(20), 0), (gun(-5), 7)], start=1)]
    with patch.object(kalib, "oturum_kontrollu_istek", return_value=cevap(kayitlar)):
        e = kalib.KalibrasyonYonetimEkrani("http://x", "T")
    assert [e.tablo.horizontalHeaderItem(i).text() for i in range(e.tablo.columnCount())][-2:] == ["HATIRLATMA", "İŞLEM"]
    assert [e.tablo.item(i, 5).text() for i in range(3)] == ["30 gün önce", "Geldiği gün", "7 gün önce"]
    assert e.cip_yaklasan.text() == "1 süresi yaklaşan" and e.cip_gecmis.text() == "1 süresi dolmuş"
    assert e.tablo.cellWidget(0, 6) is not None


# --------------------------------------------------------------- sayfaya geçince yenileme
def pencere(ekranlar):
    ana = MagicMock()
    ana.SAYFA_YENILEME = mw.AnaPencere.SAYFA_YENILEME
    ana.SAYFA_YENILEME_ARALIGI = mw.AnaPencere.SAYFA_YENILEME_ARALIGI
    ana.__dict__.update(ekranlar)
    ana._sayfa_son_yenileme = {}
    return ana


def test_sayfa_acilinca_ilgili_ekran_yenilenir():
    bakim_e, kalib_e, ariza_e, env_e = MagicMock(), MagicMock(), MagicMock(), MagicMock()
    ana = pencere({"aktif_bakim_ekrani": bakim_e, "aktif_kalibrasyon_ekrani": kalib_e,
                   "aktif_ariza_ekrani": ariza_e, "aktif_cihaz_ekrani": env_e})
    for ad in ("Bakım Kayıtları", "Kalibrasyon", "Arıza Kayıtları", "Cihaz Envanteri"):
        mw.AnaPencere._sayfayi_yenile(ana, ad)
    bakim_e.verileri_yukle.assert_called_once()
    kalib_e.yukle.assert_called_once()                   # kalibrasyon ekranının metodu 'yukle'
    ariza_e.verileri_yukle.assert_called_once()
    env_e.verileri_yukle.assert_called_once()


def test_art_arda_gecis_sinirlanir_sure_dolunca_tekrar_yenilenir():
    e = MagicMock()
    ana = pencere({"aktif_bakim_ekrani": e})
    with patch.object(mw.time, "monotonic", side_effect=[100.0, 100.5, 103.0]):
        for _ in range(3):
            mw.AnaPencere._sayfayi_yenile(ana, "Bakım Kayıtları")
    assert e.verileri_yukle.call_count == 2             # 0.5 sn sonraki atlandı, 3 sn sonraki yenilendi


def test_olmayan_ekran_ya_da_bilinmeyen_sayfa_sessizce_gecilir_ve_hata_yutulur():
    ana = pencere({})
    mw.AnaPencere._sayfayi_yenile(ana, "Bakım Kayıtları")      # ekran henüz yok
    mw.AnaPencere._sayfayi_yenile(ana, "Ana Kontrol Paneli")   # yenileme tanımlı değil
    bozuk = MagicMock()
    bozuk.verileri_yukle.side_effect = RuntimeError("sunucu yok")
    ana = pencere({"aktif_ariza_ekrani": bozuk})
    mw.AnaPencere._sayfayi_yenile(ana, "Arıza Kayıtları")      # çökmez
    bozuk.verileri_yukle.assert_called_once()


def test_sayfa_ac_yenilemeyi_tetikler_ve_bildirimden_gecis_de_sayfa_ac_kullanir():
    ana = MagicMock()
    ana.sayfa_bilgi = [("Ana Kontrol Paneli", ""), ("Bakım Kayıtları", "")]
    ana.master_stack, ana.stack = MagicMock(), MagicMock()
    mw.AnaPencere.sayfa_ac(ana, 1)
    ana.stack.setCurrentIndex.assert_called_once_with(1)
    ana._sayfayi_yenile.assert_called_once_with("Bakım Kayıtları")


# --------------------------------------------------------------- kullanılmayan plan API'si kaldırıldı
def test_bakim_planlari_api_ucları_kaldirildi():
    import sunucu
    assert not [r.path for r in sunucu.app.routes if "bakim-planlari" in r.path]
    import modeller
    assert not hasattr(modeller, "BakimPlaniOlusturModeli") and not hasattr(modeller, "BakimPlaniGuncelleModeli")
