"""
Danışanlar sayfası ve randevu formunda danışan listesinin psikologa göre süzülmesi.

Danışanlar yalnızca kodla tutulur (FR-008): sayfa kişisel veri göstermez, yalnızca kod/ücret/istisna/psikolog/randevu.
Tarihler hep "şimdi"ye göre üretilir (sabit tarih zamanla testleri bozar).
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from PySide6.QtWidgets import QLabel

import danisanlar_ekrani as modul
import main_window as mw
import randevu_ekranlari as rmodul
import sunucu
import tkys_sidebar_refined
from danisanlar_ekrani import (
    DanisanlarEkrani, danisan_ozeti, danisanlari_filtrele, istisna_etiketi, randevulari_danisana_gore,
)
from sunucu import app, mevcut_kullanici_id

PSIKOLOGLAR = {3: "Ayşe Yılmaz", 7: "Reyhan Kaya"}
ODALAR = {2: "Görüşme Odası-1", 3: "Görüşme Odası-2"}


def zaman(gun_farki=0, saat=10):
    taban = datetime.now().replace(hour=saat, minute=0, second=0, microsecond=0)
    return (taban + timedelta(days=gun_farki)).isoformat()


def danisan(kod, psikolog=3, ucretli=True, istisna="YOK", aktif=True):
    return {"danisan_kod_id": kod, "ucretli_mi": ucretli, "istisna_turu": istisna, "aktif_mi": aktif,
            "olusturulma_tarihi": zaman(-30), "olusturan_psikolog_id": psikolog}


def randevu(no, kod, durum="PLANLANDI", gun=1, saat=10, psikolog=3, oda=2):
    return {"randevu_id": no, "danisan_kod_id": kod, "psikolog_id": psikolog, "oda_id": oda, "durum": durum,
            "baslangic_zamani": zaman(gun, saat), "bitis_zamani": zaman(gun, saat + 1)}


def cevap(veri, durum=200):
    yanit = MagicMock()
    yanit.status_code = durum
    yanit.json.return_value = veri
    yanit._tkys_oturum_reddedildi = False
    return yanit


DANISANLAR = [
    danisan("DAN-2026-0001", psikolog=3),
    danisan("DAN-2026-0002", psikolog=3, ucretli=False, istisna="KANSER"),
    danisan("DAN-2026-0003", psikolog=7, ucretli=False, istisna="SEHIT_GAZI"),
]
RANDEVULAR = [
    randevu(1, "DAN-2026-0001", "TAMAMLANDI", gun=-10),
    randevu(2, "DAN-2026-0001", "GELMEDI", gun=-5),
    randevu(3, "DAN-2026-0001", "PLANLANDI", gun=4),
    randevu(4, "DAN-2026-0001", "IPTAL_EDILDI", gun=2),
    randevu(5, "DAN-2026-0003", "PLANLANDI", gun=1, psikolog=7, oda=3),
]


class Sunucu:
    """Sunucu taklidi: psikolog_id parametresine göre danışan listesini süzer (gerçek uçtaki gibi)."""

    def __init__(self, danisanlar=DANISANLAR, randevular=RANDEVULAR):
        self.danisanlar, self.randevular = danisanlar, randevular
        self.istekler = []

    def __call__(self, yontem, url, **kwargs):
        self.istekler.append((url, kwargs.get("params") or {}))
        if url.endswith("/api/danisan-kodlari"):
            pid = (kwargs.get("params") or {}).get("psikolog_id")
            return cevap([d for d in self.danisanlar if pid is None or d["olusturan_psikolog_id"] == pid])
        if url.endswith("/api/randevular"):
            return cevap(self.randevular)
        if url.endswith("/api/psikologlar"):
            return cevap([{"personel_id": k, "ad_soyad": v, "kullanici_id": 100 + k} for k, v in PSIKOLOGLAR.items()])
        if url.endswith("/api/odalar"):
            return cevap([{"oda_id": k, "oda_adi": v, "kapasite": 1, "aktif_mi": True} for k, v in ODALAR.items()])
        return cevap([])


AKTIF = {}


@pytest.fixture(autouse=True)
def sunucu_yamasi():
    """Ekran açıldıktan sonraki etkileşimlerde (psikolog seçimi vb.) de sahte sunucu kullanılsın."""
    AKTIF.clear()
    with patch.object(modul, "oturum_kontrollu_istek", side_effect=lambda *a, **k: AKTIF["s"](*a, **k)), \
            patch.object(rmodul, "oturum_kontrollu_istek", side_effect=lambda *a, **k: AKTIF["s"](*a, **k)):
        yield


def ekran_ac(sunucu=None, mevcut=11):
    sunucu = sunucu or Sunucu()
    AKTIF["s"] = sunucu
    ekran = DanisanlarEkrani("http://testserver", "TOKEN", mevcut)
    ekran._sunucu = sunucu
    return ekran


def kodlar(ekran):
    return [ekran.tablo.item(i, 0).text() for i in range(ekran.tablo.rowCount())]


def sec(ekran, kod):
    ekran.tablo.selectRow(kodlar(ekran).index(kod))


# ------------------------------------------------------------------ menü / bağlantılar
def test_menude_sidebar_ikonunda_ve_yenilemede_tanimli():
    ogeler = {oge["ad"]: oge for _, liste in mw.MENU for oge in liste}
    assert "Danışanlar" in ogeler
    assert mw.AnaPencere.SAYFA_YENILEME["Danışanlar"] == ("danisanlar_ekrani", "verileri_cek")
    assert tkys_sidebar_refined.PAGE_ICONS["Danışanlar"] == "users"


# ------------------------------------------------------------------ saf yardımcılar
def test_istisna_etiketleri():
    assert istisna_etiketi("YOK") == "Yok" and istisna_etiketi(None) == "Yok"
    assert istisna_etiketi("KANSER") == "Kanser hastası" and istisna_etiketi("SEHIT_GAZI") == "Şehit / gazi yakını"


def test_arama_kod_ve_psikolog_adina_gore_turkce_duyarsiz():
    adlar = PSIKOLOGLAR
    assert [d["danisan_kod_id"] for d in danisanlari_filtrele(DANISANLAR, adlar, "0002")] == ["DAN-2026-0002"]
    assert len(danisanlari_filtrele(DANISANLAR, adlar, "AYSE")) == 2
    assert len(danisanlari_filtrele(DANISANLAR, adlar, "reyhan")) == 1
    assert len(danisanlari_filtrele(DANISANLAR, adlar, "  ")) == 3
    assert danisanlari_filtrele(DANISANLAR, adlar, "yok böyle biri") == []


def test_ozet_sayilari_ilk_son_ve_siradaki_randevu():
    ozet = danisan_ozeti(randevulari_danisana_gore(RANDEVULAR)["DAN-2026-0001"], datetime.now())
    assert ozet["sayilar"] == {"PLANLANDI": 1, "TAMAMLANDI": 1, "GELMEDI": 1, "IPTAL_EDILDI": 1}
    assert ozet["toplam"] == 4
    assert ozet["ilk"] < ozet["son"] < ozet["siradaki"]
    assert ozet["siradaki"].date() == (datetime.now() + timedelta(days=4)).date()  # iptal edilen (2 gün sonra) sayılmaz


def test_randevusuz_danisan_ozeti_bos():
    ozet = danisan_ozeti([], datetime.now())
    assert ozet["toplam"] == 0 and ozet["ilk"] is None and ozet["son"] is None and ozet["siradaki"] is None


# ------------------------------------------------------------------ ekran
def test_basliklar_ve_ilk_yukleme():
    ekran = ekran_ac()
    basliklar = [ekran.tablo.horizontalHeaderItem(i).text() for i in range(ekran.tablo.columnCount())]
    assert basliklar == ["Danışan Kodu", "Psikolog", "Ücret", "İstisna", "Randevu", "Durum"]
    assert kodlar(ekran) == ["DAN-2026-0001", "DAN-2026-0002", "DAN-2026-0003"]
    assert ekran.lbl_sayac.text() == "3 danışan"
    ekran.close()


def test_psikolog_secilince_sunucudan_o_psikologun_danisanlari_istenir():
    ekran = ekran_ac()
    ekran.cmb_psikolog.setCurrentIndex(ekran.cmb_psikolog.findData(7))
    assert kodlar(ekran) == ["DAN-2026-0003"]
    assert ekran._sunucu.istekler[-1] == ("http://testserver/api/danisan-kodlari", {"psikolog_id": 7})
    ekran.cmb_psikolog.setCurrentIndex(0)
    assert len(kodlar(ekran)) == 3 and ekran._sunucu.istekler[-1][1] == {}
    ekran.close()


def test_psikolog_hesabinda_kutu_kendi_adina_kilitli():
    ekran = ekran_ac(mevcut=3)
    assert ekran.cmb_psikolog.currentData() == 3 and not ekran.cmb_psikolog.isEnabled()
    assert kodlar(ekran) == ["DAN-2026-0001", "DAN-2026-0002"]
    ekran.close()


def test_yetkili_rolde_kutu_serbest():
    ekran = ekran_ac(mevcut=11)       # psikolog listesinde olmayan kimlik (admin/danışma)
    assert ekran.cmb_psikolog.isEnabled() and ekran.cmb_psikolog.currentData() is None
    ekran.close()


def test_arama_listeyi_daraltir_ve_sayaci_gunceller():
    ekran = ekran_ac()
    ekran.arama.setText("reyhan")
    assert kodlar(ekran) == ["DAN-2026-0003"] and ekran.lbl_sayac.text() == "1 danışan"
    ekran.arama.setText("")
    assert len(kodlar(ekran)) == 3
    ekran.close()


def test_secim_yokken_detay_gizli_secince_bilgiler_gorunur():
    ekran = ekran_ac()
    assert ekran.lbl_secim_yok.isVisibleTo(ekran) and not ekran.detay_icerik.isVisibleTo(ekran)
    sec(ekran, "DAN-2026-0002")
    assert ekran.detay_icerik.isVisibleTo(ekran) and not ekran.lbl_secim_yok.isVisibleTo(ekran)
    assert ekran.bilgi_alanlari["kod"].text() == "DAN-2026-0002"
    assert ekran.bilgi_alanlari["ucret"].text() == "Ücretsiz"
    assert ekran.bilgi_alanlari["istisna"].text() == "Kanser hastası"
    assert ekran.bilgi_alanlari["psikolog"].text() == "Ayşe Yılmaz"
    assert ekran.bilgi_alanlari["tarih"].text() == (datetime.now() - timedelta(days=30)).strftime("%d.%m.%Y")
    ekran.close()


def test_bolum_dugmeleri_ayni_anda_tek_sayfa_gosterir():
    ekran = ekran_ac()
    sec(ekran, "DAN-2026-0001")
    assert ekran.bolumler.currentIndex() == 0 and ekran.btn_bolumler["Bilgiler"].isChecked()
    ekran.btn_bolumler["Özet"].click()
    assert ekran.bolumler.currentIndex() == 1 and ekran.btn_bolumler["Özet"].isChecked()
    assert not ekran.btn_bolumler["Bilgiler"].isChecked()
    ekran.btn_bolumler["Geçmiş"].click()
    assert ekran.bolumler.currentIndex() == 2
    ekran.close()


def test_ozet_sayfasi_secili_danisanin_sayilarini_gosterir():
    ekran = ekran_ac()
    sec(ekran, "DAN-2026-0001")
    assert {d: s.text() for d, s in ekran.ozet_sayilari.items()} == {
        "PLANLANDI": "1", "TAMAMLANDI": "1", "GELMEDI": "1", "IPTAL_EDILDI": "1"}
    assert ekran.ozet_alanlari["toplam"].text() == "4"
    assert ekran.ozet_alanlari["siradaki"].text().startswith((datetime.now() + timedelta(days=4)).strftime("%d.%m.%Y"))
    sec(ekran, "DAN-2026-0002")                        # randevusu yok
    assert ekran.ozet_alanlari["toplam"].text() == "0" and ekran.ozet_alanlari["siradaki"].text() == "-"
    ekran.close()


def test_gecmis_yeniden_eskiye_ve_baska_danisanin_randevusu_karismaz():
    ekran = ekran_ac()
    sec(ekran, "DAN-2026-0001")
    assert ekran.gecmis_tablosu.rowCount() == 4
    tarihler = [ekran.gecmis_tablosu.item(i, 0).text() for i in range(4)]
    beklenen = [(datetime.now() + timedelta(days=g)).strftime("%d.%m.%Y") for g in (4, 2, -5, -10)]
    assert tarihler == beklenen
    assert [ekran.gecmis_tablosu.horizontalHeaderItem(i).text() for i in range(4)] == ["Tarih", "Saat", "Oda", "Durum"]
    assert ekran.gecmis_tablosu.item(0, 2).text() == "Görüşme Odası-1"
    sec(ekran, "DAN-2026-0003")
    assert ekran.gecmis_tablosu.rowCount() == 1
    assert ekran.gecmis_tablosu.item(0, 2).text() == "Görüşme Odası-2"
    ekran.close()


def test_gecmis_rozetlerinde_eski_satirlarin_hayaleti_kalmaz():
    ekran = ekran_ac()
    sec(ekran, "DAN-2026-0001")
    sec(ekran, "DAN-2026-0003")
    gorunen = [w for w in ekran.gecmis_tablosu.viewport().findChildren(QLabel) if w.isVisibleTo(ekran.gecmis_tablosu)]
    assert len(gorunen) == 1 and gorunen[0].text() == "Planlandı"
    ekran.close()


def test_yenilenince_secim_korunur():
    ekran = ekran_ac()
    sec(ekran, "DAN-2026-0002")
    ekran.verileri_cek()
    assert ekran.secili_danisan()["danisan_kod_id"] == "DAN-2026-0002"
    ekran.close()


def test_sayfada_kisisel_veri_alani_yok():
    ekran = ekran_ac()
    sec(ekran, "DAN-2026-0001")
    gorunen = {k.lower() for k in (ekran.tablo.horizontalHeaderItem(i).text() for i in range(ekran.tablo.columnCount()))}
    for yasak in ("ad", "soyad", "telefon", "tc", "e-posta", "adres", "tanı"):
        assert yasak not in gorunen
    ekran.close()


# ------------------------------------------------------------------ yeni randevu
def test_yeni_randevu_secili_danisan_ve_psikologla_acilir():
    ekran = ekran_ac()
    sec(ekran, "DAN-2026-0003")
    ekran.yeni_randevu_ac()
    form = ekran.randevu_formu
    assert form.cmb_psikologlar.currentData() == 7
    assert form.cmb_danisan_kodu.currentData() == "DAN-2026-0003"
    assert [form.cmb_danisan_kodu.itemData(i) for i in range(form.cmb_danisan_kodu.count())] == ["", "DAN-2026-0003"]
    form.close()
    ekran.close()


def test_yeni_randevu_secim_yokken_uyari_verir():
    ekran = ekran_ac()
    with patch.object(modul.QMessageBox, "warning") as uyari:
        ekran.yeni_randevu_ac()
    uyari.assert_called_once()
    assert not hasattr(ekran, "randevu_formu")
    ekran.close()


def test_randevu_formunda_psikolog_degisince_danisan_listesi_yenilenir():
    AKTIF["s"] = Sunucu()
    form = rmodul.RandevuOlusturFormu("http://testserver", "TOKEN", 11)
    form.cmb_psikologlar.setCurrentIndex(form.cmb_psikologlar.findData(3))
    assert [form.cmb_danisan_kodu.itemData(i) for i in range(form.cmb_danisan_kodu.count())] == [
        "", "DAN-2026-0001", "DAN-2026-0002"]
    form.cmb_danisan_kodu.setCurrentIndex(form.cmb_danisan_kodu.findData("DAN-2026-0002"))
    form.cmb_psikologlar.setCurrentIndex(form.cmb_psikologlar.findData(7))
    assert [form.cmb_danisan_kodu.itemData(i) for i in range(form.cmb_danisan_kodu.count())] == ["", "DAN-2026-0003"]
    assert form.cmb_danisan_kodu.currentData() == ""       # eski psikologun danışanı yeni listede yok
    form.close()


# ------------------------------------------------------------------ sunucu ucu
@pytest.fixture
def istemci():
    app.dependency_overrides[mevcut_kullanici_id] = lambda: 5
    yield TestClient(app)
    app.dependency_overrides.pop(mevcut_kullanici_id, None)


def _liste_cagir(istemci, rol, sorgu="", satirlar=None, personel=(9,)):
    conn = MagicMock()
    c = conn.cursor.return_value
    c.fetchone.side_effect = [(1,), (rol,), personel]
    c.fetchall.return_value = satirlar if satirlar is not None else [
        ("DAN-2026-0001", True, True, "YOK", datetime(2026, 5, 1, 10, 0), 3)]
    with patch("sunucu.psycopg2.connect", return_value=conn):
        yanit = istemci.get("/api/danisan-kodlari" + sorgu)
    sorgular = [(a[0], a[1] if len(a) > 1 else None) for a, _ in c.execute.call_args_list]
    return yanit, sorgular


def test_uc_yeni_alanlari_dondurur(istemci):
    yanit, _ = _liste_cagir(istemci, "ADMIN")
    assert yanit.status_code == 200
    assert yanit.json() == [{"danisan_kod_id": "DAN-2026-0001", "ucretli_mi": True, "aktif_mi": True,
                             "istisna_turu": "YOK", "olusturulma_tarihi": "2026-05-01T10:00:00",
                             "olusturan_psikolog_id": 3}]


def test_ust_rol_psikolog_secince_o_psikologa_gore_sorgulanir(istemci):
    yanit, sorgular = _liste_cagir(istemci, "ADMIN", "?psikolog_id=7")
    assert yanit.status_code == 200
    son_sql, son_param = sorgular[-1]
    assert "olusturan_psikolog_id = %s" in son_sql and son_param == (7,)


def test_ust_rol_psikolog_secmezse_tum_danisanlar(istemci):
    _, sorgular = _liste_cagir(istemci, "ADMIN")
    assert "olusturan_psikolog_id = %s" not in sorgular[-1][0] and sorgular[-1][1] is None


def test_psikolog_baska_psikolog_istese_de_yalnizca_kendininkini_gorur(istemci):
    _, sorgular = _liste_cagir(istemci, "PSIKOLOG", "?psikolog_id=7", personel=(9,))
    son_sql, son_param = sorgular[-1]
    assert "olusturan_psikolog_id = %s" in son_sql and son_param == (9,)


def test_gecersiz_psikolog_id_reddedilir(istemci):
    conn = MagicMock()
    conn.cursor.return_value.fetchone.return_value = (1,)       # izin denetimi geçer; hata girdi doğrulamasından gelmeli
    for deger in ("0", "-3", "abc"):
        with patch("sunucu.psycopg2.connect", return_value=conn):
            assert istemci.get("/api/danisan-kodlari?psikolog_id=" + deger).status_code == 422


def test_sunucu_yaniti_kisisel_veri_sutunu_icermez(istemci):
    yanit, _ = _liste_cagir(istemci, "ADMIN")
    for kayit in yanit.json():
        assert set(kayit) <= {"danisan_kod_id", "ucretli_mi", "istisna_turu", "aktif_mi", "olusturulma_tarihi",
                              "olusturan_psikolog_id"}


def test_psikolog_degisirken_yukleme_hatasinda_eski_danisanlar_gizlenir():
    from unittest.mock import patch

    ekran = ekran_ac()
    assert len(kodlar(ekran)) == 3

    with patch.object(ekran, "_api_liste_getir", return_value=None):
        ekran.cmb_psikolog.setCurrentIndex(
            ekran.cmb_psikolog.findData(7)
        )

    assert kodlar(ekran) == []

    # Sunucu yeniden çalışınca doğru psikoloğun kayıtları gelir.
    ekran._danisanlari_yukle()
    assert kodlar(ekran) == ["DAN-2026-0003"]

    ekran.close()


def test_ayni_psikologda_yenileme_hatasi_eski_listeyi_korur():
    from unittest.mock import patch

    ekran = ekran_ac()
    onceki = kodlar(ekran)

    with patch.object(ekran, "_api_liste_getir", return_value=None):
        ekran._danisanlari_yukle()

    assert kodlar(ekran) == onceki
    ekran.close()
