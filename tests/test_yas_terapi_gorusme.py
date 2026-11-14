"""
Danışan yaş grubu + terapi türü; randevu görüşme tipi + terapi türü (kapalı listeler).

Kurallar: yaş grubu Çocuk/Yetişkin; yetişkinde terapi türü yalnızca Bireysel terapi (otomatik); çocukta Oyun terapisi ya da
Bireysel terapi. Görüşme tipi Yüz yüze/Online (online da oda ister). Eski kayıtlar "Belirtilmedi"/Yüz yüze kalır.
Bunlar serbest metin değildir (FR-008): modellerde Literal, veritabanında CHECK kısıtı.

Tarihler "şimdi"ye göre üretilir.
"""

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from PySide6.QtWidgets import QApplication, QMessageBox

import danisanlar_ekrani as dmodul
import modeller
import randevu_ekranlari as rmodul
import siniflandirma
from danisan_bilgi_diyalogu import DanisanBilgiDialog
from danisan_diyalog import DanisanOlusturDialog
from modeller import (
    DanisanBilgiModeli, RandevuOlusturModeli, danisan_terapisini_belirle, randevu_terapisini_belirle,
)
from randevu_ekranlari import RandevuAnaEkrani, RandevuDuzenleFormu, RandevuOlusturFormu
from sunucu import app, mevcut_kullanici_id, randevu_olustur


# ------------------------------------------------------------------ kurallar
def test_istemci_ve_sunucu_listeleri_ayni():
    assert dict(siniflandirma.YAS_GRUPLARI) == modeller.YAS_GRUPLARI
    assert dict(siniflandirma.TERAPI_TURLERI) == modeller.TERAPI_TURLERI
    assert dict(siniflandirma.GORUSME_TIPLERI) == modeller.GORUSME_TIPLERI
    for yas, terapiler in modeller.YAS_GRUBUNA_GORE_TERAPILER.items():
        assert siniflandirma.terapi_secenekleri(yas) == list(terapiler)
    assert siniflandirma.terapi_secenekleri(None) == []


def test_yetiskinde_terapi_otomatik_bireysel_terapi():
    assert danisan_terapisini_belirle("YETISKIN", None) == "BIREYSEL_TERAPI"
    assert danisan_terapisini_belirle("YETISKIN", "BIREYSEL_TERAPI") == "BIREYSEL_TERAPI"
    with pytest.raises(ValueError):
        danisan_terapisini_belirle("YETISKIN", "OYUN_TERAPISI")


def test_cocukta_terapi_secilmeli_iki_secenek_gecerli():
    with pytest.raises(ValueError):
        danisan_terapisini_belirle("COCUK", None)
    assert danisan_terapisini_belirle("COCUK", "OYUN_TERAPISI") == "OYUN_TERAPISI"
    assert danisan_terapisini_belirle("COCUK", "BIREYSEL_TERAPI") == "BIREYSEL_TERAPI"
    with pytest.raises(ValueError):
        danisan_terapisini_belirle("BILINMEYEN", None)


def test_randevu_terapisi_danisanin_yas_grubuna_uymali_eski_danisanda_serbest():
    assert randevu_terapisini_belirle("YETISKIN", None) == "BIREYSEL_TERAPI"
    with pytest.raises(ValueError):
        randevu_terapisini_belirle("YETISKIN", "OYUN_TERAPISI")
    with pytest.raises(ValueError):
        randevu_terapisini_belirle("COCUK", None)
    assert randevu_terapisini_belirle(None, None) is None                         # eski danışan: belirtilmedi
    assert randevu_terapisini_belirle(None, "OYUN_TERAPISI") == "OYUN_TERAPISI"


def test_bilgi_modeli_ve_kapali_liste_alanlari():
    m = DanisanBilgiModeli(yas_grubu="YETISKIN")
    assert m.terapi_turu == "BIREYSEL_TERAPI"
    assert DanisanBilgiModeli(yas_grubu="COCUK", terapi_turu="OYUN_TERAPISI").terapi_turu == "OYUN_TERAPISI"
    for veri in ({}, {"yas_grubu": "COCUK"}, {"yas_grubu": "YETISKIN", "terapi_turu": "OYUN_TERAPISI"},
                 {"yas_grubu": "Ergen"}, {"yas_grubu": "COCUK", "terapi_turu": "serbest metin"},
                 {"yas_grubu": "COCUK", "terapi_turu": "OYUN_TERAPISI", "ad_soyad": "Ali"}):
        with pytest.raises(ValidationError):
            DanisanBilgiModeli(**veri)
    # kapalı liste: bu alanlar serbest metin değil, Literal'dir
    for model, alan in ((DanisanBilgiModeli, "yas_grubu"), (DanisanBilgiModeli, "terapi_turu"),
                        (RandevuOlusturModeli, "gorusme_tipi"), (RandevuOlusturModeli, "terapi_turu"),
                        (modeller.RandevuGuncelleModeli, "gorusme_tipi"), (modeller.RandevuGuncelleModeli, "terapi_turu")):
        assert "Literal" in str(model.model_fields[alan].annotation), f"{model.__name__}.{alan}"


def test_randevu_modeli_gorusme_tipi_varsayilan_yuz_yuze_ve_gecersiz_deger_reddedilir():
    zaman = datetime(2026, 12, 7, 10, 0)
    ortak = dict(danisan_kod_id="D", psikolog_id=1, oda_id=1, baslangic_zamani=zaman, bitis_zamani=zaman + timedelta(hours=1))
    assert RandevuOlusturModeli(**ortak).gorusme_tipi == "YUZ_YUZE"
    assert RandevuOlusturModeli(**ortak, gorusme_tipi="ONLINE").gorusme_tipi == "ONLINE"
    for kotu in ({"gorusme_tipi": "telefon"}, {"terapi_turu": "grup terapisi"}):
        with pytest.raises(ValidationError):
            RandevuOlusturModeli(**ortak, **kotu)


# ------------------------------------------------------------------ sunucu: danışan
@pytest.fixture
def istemci():
    app.dependency_overrides[mevcut_kullanici_id] = lambda: 5
    yield TestClient(app)
    app.dependency_overrides.pop(mevcut_kullanici_id, None)


def _olustur(istemci, sorgu):
    conn = MagicMock()
    c = conn.cursor.return_value
    c.fetchone.side_effect = [(1,), (7, "PSIKOLOG"), ("DAN-2026-0099", True, "YOK", True, None, 7, "X", "Y")]
    with patch("sunucu.psycopg2.connect", return_value=conn), patch("sunucu.otomatik_danisan_kodu_uret", return_value="DAN-2026-0099"):
        yanit = istemci.post("/api/danisan-kodlari" + sorgu)
    ekleme = next((x.args[1] for x in c.execute.call_args_list if "INSERT INTO danisan_kodlari" in x.args[0]), None)
    return yanit, ekleme


def test_yetiskin_danisan_terapisiz_olusur_ve_otomatik_bireysel_terapi_yazilir(istemci):
    yanit, ekleme = _olustur(istemci, "?yas_grubu=YETISKIN")
    assert yanit.status_code == 201 and ekleme[-2:] == ("YETISKIN", "BIREYSEL_TERAPI")


def test_cocuk_danisan_terapi_secilmeden_olusmaz_secilince_olusur(istemci):
    yanit, ekleme = _olustur(istemci, "?yas_grubu=COCUK")
    assert yanit.status_code == 422 and ekleme is None
    yanit, ekleme = _olustur(istemci, "?yas_grubu=COCUK&terapi_turu=OYUN_TERAPISI")
    assert yanit.status_code == 201 and ekleme[-2:] == ("COCUK", "OYUN_TERAPISI")


@pytest.mark.parametrize("sorgu", ["", "?yas_grubu=", "?yas_grubu=Ergen", "?yas_grubu=YETISKIN&terapi_turu=OYUN_TERAPISI",
                                   "?yas_grubu=COCUK&terapi_turu=grup", "?yas_grubu=Ali%20Veli%20depresyon"])
def test_gecersiz_yas_grubu_ve_terapi_kombinasyonlari_reddedilir(istemci, sorgu):
    yanit, ekleme = _olustur(istemci, sorgu)
    assert yanit.status_code == 422 and ekleme is None
    assert "Ali" not in yanit.text                                                # girilen metin geri yansıtılmaz


def _bilgi(istemci, govde, danisan=(3,), rol="ADMIN", personel=(3,)):
    conn = MagicMock()
    c = conn.cursor.return_value
    sirali = [(1,), danisan] if danisan is not None else [(1,), None]
    if danisan is not None:
        sirali.append((rol,))
        if rol == "PSIKOLOG":
            sirali.append(personel)
    c.fetchone.side_effect = sirali
    with patch("sunucu.psycopg2.connect", return_value=conn):
        yanit = istemci.patch("/api/danisan-kodlari/DAN-2026-0001/bilgiler", json=govde)
    guncelleme = next((x.args[1] for x in c.execute.call_args_list if x.args[0].startswith("UPDATE danisan_kodlari")), None)
    return yanit, guncelleme, conn


def test_danisan_bilgileri_guncellenir(istemci):
    yanit, guncelleme, conn = _bilgi(istemci, {"yas_grubu": "COCUK", "terapi_turu": "BIREYSEL_TERAPI"})
    assert yanit.status_code == 200 and guncelleme == ("COCUK", "BIREYSEL_TERAPI", "DAN-2026-0001")
    conn.commit.assert_called_once()
    yanit, guncelleme, _ = _bilgi(istemci, {"yas_grubu": "YETISKIN"})
    assert guncelleme == ("YETISKIN", "BIREYSEL_TERAPI", "DAN-2026-0001")           # yetişkinde otomatik


def test_danisan_bilgileri_yetki_ve_hata_durumlari(istemci):
    yanit, guncelleme, _ = _bilgi(istemci, {"yas_grubu": "COCUK", "terapi_turu": "OYUN_TERAPISI"}, rol="PSIKOLOG", personel=(9,))
    assert yanit.status_code == 403 and guncelleme is None                           # başkasının danışanı
    yanit, _, _ = _bilgi(istemci, {"yas_grubu": "COCUK", "terapi_turu": "OYUN_TERAPISI"}, rol="PSIKOLOG", personel=(3,))
    assert yanit.status_code == 200                                                  # kendi danışanı
    yanit, _, _ = _bilgi(istemci, {"yas_grubu": "COCUK", "terapi_turu": "OYUN_TERAPISI"}, danisan=None)
    assert yanit.status_code == 404
    conn = MagicMock()
    conn.cursor.return_value.fetchone.return_value = (1,)
    with patch("sunucu.psycopg2.connect", return_value=conn):
        for kotu in ({"yas_grubu": "YETISKIN", "terapi_turu": "OYUN_TERAPISI"}, {"yas_grubu": "COCUK"},
                     {"yas_grubu": "COCUK", "terapi_turu": "OYUN_TERAPISI", "tani": "x"}, {}):
            assert istemci.patch("/api/danisan-kodlari/DAN-2026-0001/bilgiler", json=kotu).status_code == 422


# ------------------------------------------------------------------ sunucu: randevu
BAS = datetime(2026, 12, 7, 10, 0)


def _randevu_olustur(danisan_yas, **alanlar):
    conn = MagicMock()
    c = conn.cursor.return_value
    c.fetchone.side_effect = [("ADMIN",), (danisan_yas,), (1,), (1,), (1,), None, (123,)]
    randevu = SimpleNamespace(danisan_kod_id="DAN-2026-0001", psikolog_id=3, oda_id=2,
                              baslangic_zamani=BAS, bitis_zamani=BAS + timedelta(hours=1), **alanlar)
    with patch("sunucu.psycopg2.connect", return_value=conn):
        try:
            sonuc = randevu_olustur(randevu=randevu, kullanici_id=1)
        except HTTPException as hata:
            return hata, None
    ekleme = next(x.args[1] for x in c.execute.call_args_list if x.args[0].startswith("INSERT INTO randevular"))
    return sonuc, ekleme


def test_randevu_gorusme_tipi_ve_terapisi_kaydedilir_online_da_oda_ister():
    sonuc, ekleme = _randevu_olustur("COCUK", gorusme_tipi="ONLINE", terapi_turu="OYUN_TERAPISI")
    assert sonuc["randevu_id"] == 123
    assert ekleme[-2:] == ("ONLINE", "OYUN_TERAPISI") and ekleme[2] == 2                   # oda_id yine yazılır


def test_yetiskin_danisanin_randevusunda_terapi_otomatik_bireysel():
    _, ekleme = _randevu_olustur("YETISKIN", gorusme_tipi="YUZ_YUZE", terapi_turu=None)
    assert ekleme[-2:] == ("YUZ_YUZE", "BIREYSEL_TERAPI")


def test_randevu_terapisi_yas_grubuna_uymazsa_reddedilir():
    hata, ekleme = _randevu_olustur("YETISKIN", gorusme_tipi="YUZ_YUZE", terapi_turu="OYUN_TERAPISI")
    assert isinstance(hata, HTTPException) and hata.status_code == 422 and ekleme is None
    hata, _ = _randevu_olustur("COCUK", gorusme_tipi="YUZ_YUZE", terapi_turu=None)           # çocukta seçilmeli
    assert hata.status_code == 422


def test_eski_danisanda_randevu_terapisiz_olusabilir():
    _, ekleme = _randevu_olustur(None, gorusme_tipi="YUZ_YUZE", terapi_turu=None)
    assert ekleme[-2:] == ("YUZ_YUZE", None)


def test_randevu_listesi_yeni_alanlari_dondurur(istemci):
    conn = MagicMock()
    c = conn.cursor.return_value
    c.fetchone.side_effect = [(1,), ("ADMIN",)]
    simdi = datetime.now()
    c.fetchall.return_value = [
        (1, "D", 3, 2, simdi, simdi, "PLANLANDI", simdi, None, None, "ONLINE", "OYUN_TERAPISI"),
        (2, "D", 3, 2, simdi, simdi, "PLANLANDI", simdi),                                    # eski biçim
    ]
    with patch("sunucu.psycopg2.connect", return_value=conn):
        veri = istemci.get("/api/randevular").json()
    assert (veri[0]["gorusme_tipi"], veri[0]["terapi_turu"]) == ("ONLINE", "OYUN_TERAPISI")
    assert (veri[1]["gorusme_tipi"], veri[1]["terapi_turu"]) == ("YUZ_YUZE", None)


def _guncelle(istemci, govde, yas=("COCUK",)):
    conn = MagicMock()
    c = conn.cursor.return_value
    mevcut = ("DAN-2026-0001", 3, 2, datetime(2026, 12, 7, 10, 0), datetime(2026, 12, 7, 11, 0), "PLANLANDI", "YUZ_YUZE", None)
    c.fetchone.side_effect = [(1,), mevcut, ("MEMUR",), None, yas, None]      # izin, mevcut, rol, çakışma yok, danışan yaş grubu
    with patch("sunucu.psycopg2.connect", return_value=conn):
        yanit = istemci.patch("/api/randevular/7", json=govde)
    sorgular = [(x.args[0], x.args[1] if len(x.args) > 1 else None) for x in c.execute.call_args_list]
    return yanit, sorgular


def test_randevu_guncelleme_gorusme_tipi_ve_terapi_yazar_ve_yas_grubunu_denetler(istemci):
    yanit, sorgular = _guncelle(istemci, {"gorusme_tipi": "ONLINE", "terapi_turu": "OYUN_TERAPISI"})
    assert yanit.status_code == 200
    assert ("UPDATE randevular SET gorusme_tipi = %s, terapi_turu = %s WHERE randevu_id = %s;", ("ONLINE", "OYUN_TERAPISI", 7)) in sorgular
    yanit, sorgular = _guncelle(istemci, {"terapi_turu": "OYUN_TERAPISI"}, yas=("YETISKIN",))
    assert yanit.status_code == 422 and not any(s.startswith("UPDATE randevular SET gorusme") for s, _ in sorgular)
    yanit, _ = _guncelle(istemci, {"gorusme_tipi": "telefon"})
    assert yanit.status_code == 422


# ------------------------------------------------------------------ arayüz yardımcıları
@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def cevap(veri, durum=200):
    y = MagicMock()
    y.status_code = durum
    y.json.return_value = veri
    y.headers = {"content-type": "application/json"}
    y._tkys_oturum_reddedildi = False
    return y


DANISANLAR = [
    {"danisan_kod_id": "DAN-2026-0001", "ucretli_mi": True, "aktif_mi": True, "istisna_turu": "YOK", "olusturulma_tarihi": "2026-10-01T10:00:00",
     "olusturan_psikolog_id": 3, "yas_grubu": "YETISKIN", "terapi_turu": "BIREYSEL_TERAPI"},
    {"danisan_kod_id": "DAN-2026-0002", "ucretli_mi": True, "aktif_mi": True, "istisna_turu": "YOK", "olusturulma_tarihi": "2026-10-01T10:00:00",
     "olusturan_psikolog_id": 3, "yas_grubu": "COCUK", "terapi_turu": "OYUN_TERAPISI"},
    {"danisan_kod_id": "DAN-2026-0003", "ucretli_mi": True, "aktif_mi": True, "istisna_turu": "YOK", "olusturulma_tarihi": "2026-10-01T10:00:00",
     "olusturan_psikolog_id": 3, "yas_grubu": None, "terapi_turu": None},                         # eski danışan
]


class Sunucu:
    def __init__(self, randevular=(), patch_cevabi=None):
        self.randevular = list(randevular)
        self.patch_cevabi = patch_cevabi or cevap({"durum": "basarili"})
        self.istekler, self.govdeler = [], []

    def __call__(self, yontem, url, **kwargs):
        self.istekler.append((yontem, url))
        if yontem in ("PATCH", "POST"):
            self.govdeler.append(kwargs.get("json"))
            return self.patch_cevabi if yontem == "PATCH" else cevap({"durum": "basarili", "randevu_id": 1}, 201)
        if url.endswith("/api/danisan-kodlari"):
            return cevap(DANISANLAR)
        if url.endswith("/api/randevular"):
            return cevap(self.randevular)
        if url.endswith("/api/randevular/doluluk"):
            return cevap({"dolu_araliklar": []})
        if url.endswith("/api/psikologlar"):
            return cevap([{"personel_id": 3, "ad_soyad": "Ayşe", "kullanici_id": 13}])
        if "/odalar" in url:
            return cevap([{"oda_id": 2, "oda_adi": "Oda-1", "kapasite": 1, "aktif_mi": True}])
        return cevap([])


AKTIF = {}


@pytest.fixture(autouse=True)
def sahte_sunucu():
    AKTIF.clear()
    cagri = lambda *a, **k: AKTIF["s"](*a, **k)
    with patch.object(dmodul, "oturum_kontrollu_istek", side_effect=cagri), \
            patch.object(rmodul, "oturum_kontrollu_istek", side_effect=cagri), \
            patch("danisan_diyalog.oturum_kontrollu_istek", side_effect=cagri), \
            patch("danisan_bilgi_diyalogu.oturum_kontrollu_istek", side_effect=cagri):
        yield


def isle():
    QApplication.processEvents()
    QApplication.processEvents()


def secenekler(kutu):
    return [kutu.itemData(i) for i in range(kutu.count())]


def test_terapi_kutusu_yardimcisi(qt_app):
    from PySide6.QtWidgets import QComboBox
    k = QComboBox()
    siniflandirma.terapi_kutusunu_doldur(k, "YETISKIN")
    assert secenekler(k) == ["BIREYSEL_TERAPI"] and not k.isEnabled()
    siniflandirma.terapi_kutusunu_doldur(k, "COCUK", secili="BIREYSEL_TERAPI")
    assert secenekler(k) == ["OYUN_TERAPISI", "BIREYSEL_TERAPI"] and k.isEnabled() and k.currentData() == "BIREYSEL_TERAPI"
    siniflandirma.terapi_kutusunu_doldur(k, None)
    assert secenekler(k) == [None] and not k.isEnabled()
    siniflandirma.terapi_kutusunu_doldur(k, None, yas_bilinmiyor_secenekli=True)
    assert secenekler(k) == [None, "OYUN_TERAPISI", "BIREYSEL_TERAPI"] and k.isEnabled()


def test_etiketler():
    assert siniflandirma.yas_etiketi("COCUK") == "Çocuk" and siniflandirma.yas_etiketi(None) == "Belirtilmedi"
    assert siniflandirma.terapi_etiketi("OYUN_TERAPISI") == "Oyun terapisi" and siniflandirma.terapi_etiketi(None) == "Belirtilmedi"
    assert siniflandirma.terapi_etiketi(None, "-") == "-"
    assert siniflandirma.gorusme_etiketi("ONLINE") == "Online" and siniflandirma.gorusme_etiketi(None) == "Yüz yüze"


# ------------------------------------------------------------------ Yeni Danışan penceresi
def test_yeni_danisan_penceresi_yetiskin_ve_cocuk_secimi(qt_app):
    AKTIF["s"] = Sunucu()
    p = DanisanOlusturDialog("http://x", "T", mevcut_psikolog_id=3)
    assert secenekler(p.cmb_yas) == [None, "COCUK", "YETISKIN"] and not p.cmb_terapi.isEnabled()
    p.cmb_yas.setCurrentIndex(p.cmb_yas.findData("YETISKIN"))
    assert secenekler(p.cmb_terapi) == ["BIREYSEL_TERAPI"] and not p.cmb_terapi.isEnabled()
    p.cmb_yas.setCurrentIndex(p.cmb_yas.findData("COCUK"))
    assert secenekler(p.cmb_terapi) == ["OYUN_TERAPISI", "BIREYSEL_TERAPI"] and p.cmb_terapi.isEnabled()


def test_yaş_grubu_secilmeden_danisan_olusturulmaz(qt_app):
    sunucu = Sunucu()
    AKTIF["s"] = sunucu
    p = DanisanOlusturDialog("http://x", "T", mevcut_psikolog_id=3)
    with patch("danisan_diyalog.QMessageBox.warning") as uyari:
        p.kaydet()
    uyari.assert_called_once()
    assert not any(y == "POST" for y, _ in sunucu.istekler)


# ------------------------------------------------------------------ Danışan bilgileri penceresi
def test_bilgi_penceresi_mevcut_degerlerle_acilir_ve_kaydeder(qt_app):
    sunucu = Sunucu()
    AKTIF["s"] = sunucu
    p = DanisanBilgiDialog("http://x", "T", DANISANLAR[1])
    assert p.cmb_yas.currentData() == "COCUK" and p.cmb_terapi.currentData() == "OYUN_TERAPISI" and p.cmb_terapi.isEnabled()
    p.cmb_terapi.setCurrentIndex(p.cmb_terapi.findData("BIREYSEL_TERAPI"))
    with patch.object(p, "accept") as kabul:
        p.kaydet()
    assert ("PATCH", "http://x/api/danisan-kodlari/DAN-2026-0002/bilgiler") in sunucu.istekler
    assert sunucu.govdeler == [{"yas_grubu": "COCUK", "terapi_turu": "BIREYSEL_TERAPI"}]
    kabul.assert_called_once()


def test_eski_danisan_icin_bilgi_penceresi_belirtilmedi_ile_acilir_yas_secilmeden_kaydedilmez(qt_app):
    sunucu = Sunucu()
    AKTIF["s"] = sunucu
    p = DanisanBilgiDialog("http://x", "T", DANISANLAR[2])
    assert p.cmb_yas.currentData() is None
    with patch("danisan_bilgi_diyalogu.QMessageBox.warning") as uyari:
        p.kaydet()
    uyari.assert_called_once()
    assert not any(y == "PATCH" for y, _ in sunucu.istekler)


def test_bilgi_penceresi_sunucu_reddederse_mesaji_gosterir(qt_app):
    AKTIF["s"] = Sunucu(patch_cevabi=cevap({"detail": "Yalnızca kendi danışanınızın bilgilerini güncelleyebilirsiniz."}, 403))
    p = DanisanBilgiDialog("http://x", "T", DANISANLAR[0])
    with patch("danisan_bilgi_diyalogu.QMessageBox.warning") as uyari, patch.object(p, "accept") as kabul:
        p.kaydet()
    assert "kendi danışanınızın" in uyari.call_args.args[2]
    kabul.assert_not_called()


# ------------------------------------------------------------------ Danışanlar sayfası
def test_danisanlar_sayfasi_yas_grubu_ve_terapi_gosterir_eski_danisan_belirtilmedi(qt_app):
    AKTIF["s"] = Sunucu()
    ekran = dmodul.DanisanlarEkrani("http://x", "T", 11)
    t = ekran.tablo
    satir = {t.item(i, 0).text(): i for i in range(t.rowCount())}
    assert [t.item(satir["DAN-2026-0001"], c).text() for c in (2, 3)] == ["Yetişkin", "Bireysel terapi"]
    assert [t.item(satir["DAN-2026-0002"], c).text() for c in (2, 3)] == ["Çocuk", "Oyun terapisi"]
    assert [t.item(satir["DAN-2026-0003"], c).text() for c in (2, 3)] == ["Belirtilmedi", "Belirtilmedi"]
    t.selectRow(satir["DAN-2026-0002"])
    assert ekran.bilgi_alanlari["yas"].text() == "Çocuk" and ekran.bilgi_alanlari["terapi"].text() == "Oyun terapisi"
    ekran.close()


def test_bilgileri_duzenle_penceresi_acar_kabulde_listeyi_yeniler(qt_app):
    sunucu = Sunucu()
    AKTIF["s"] = sunucu
    ekran = dmodul.DanisanlarEkrani("http://x", "T", 11)
    ekran.tablo.selectRow(2)
    onceki = len(sunucu.istekler)
    sahte = MagicMock()
    sahte.exec.return_value = dmodul.QDialog.Accepted
    with patch.object(dmodul, "DanisanBilgiDialog", return_value=sahte) as sinif:
        ekran.btn_bilgi_duzenle.click()
    assert sinif.call_args.args[2]["danisan_kod_id"] == "DAN-2026-0003"
    assert len(sunucu.istekler) > onceki                                        # liste yenilendi
    sahte.exec.return_value = dmodul.QDialog.Rejected
    sonra = len(sunucu.istekler)
    with patch.object(dmodul, "DanisanBilgiDialog", return_value=sahte):
        ekran.btn_bilgi_duzenle.click()
    assert len(sunucu.istekler) == sonra                                         # vazgeçilirse yenilenmez
    ekran.close()


# ------------------------------------------------------------------ Yeni Randevu formu
def form_ac():
    AKTIF["s"] = Sunucu()
    form = RandevuOlusturFormu("http://x", "T", 11)
    isle()
    return form


def test_randevu_formunda_terapi_danisanin_yas_grubundan_gelir(qt_app):
    form = form_ac()
    assert secenekler(form.cmb_gorusme) == ["YUZ_YUZE", "ONLINE"] and form.cmb_gorusme.currentData() == "YUZ_YUZE"
    form.cmb_danisan_kodu.setCurrentIndex(form.cmb_danisan_kodu.findData("DAN-2026-0001"))      # yetişkin
    assert secenekler(form.cmb_terapi) == ["BIREYSEL_TERAPI"] and not form.cmb_terapi.isEnabled()
    form.cmb_danisan_kodu.setCurrentIndex(form.cmb_danisan_kodu.findData("DAN-2026-0002"))      # çocuk (oyun terapisi)
    assert secenekler(form.cmb_terapi) == ["OYUN_TERAPISI", "BIREYSEL_TERAPI"] and form.cmb_terapi.currentData() == "OYUN_TERAPISI"
    form.cmb_danisan_kodu.setCurrentIndex(form.cmb_danisan_kodu.findData("DAN-2026-0003"))      # eski danışan
    assert secenekler(form.cmb_terapi) == [None, "OYUN_TERAPISI", "BIREYSEL_TERAPI"] and form.cmb_terapi.isEnabled()
    form.close()


def test_randevu_kaydi_gorusme_tipi_ve_terapiyi_gonderir(qt_app):
    form = form_ac()
    form.cmb_danisan_kodu.setCurrentIndex(form.cmb_danisan_kodu.findData("DAN-2026-0002"))
    form.cmb_gorusme.setCurrentIndex(form.cmb_gorusme.findData("ONLINE"))
    form.cmb_terapi.setCurrentIndex(form.cmb_terapi.findData("BIREYSEL_TERAPI"))
    isle()
    with patch.object(QMessageBox, "information"):
        form.randevuyu_kaydet()
    govde = AKTIF["s"].govdeler[-1]
    assert govde["gorusme_tipi"] == "ONLINE" and govde["terapi_turu"] == "BIREYSEL_TERAPI" and govde["oda_id"] == 2
    form.close()


def test_eski_danisanda_terapi_secilmezse_govdede_yer_almaz(qt_app):
    form = form_ac()
    form.cmb_danisan_kodu.setCurrentIndex(form.cmb_danisan_kodu.findData("DAN-2026-0003"))
    isle()
    with patch.object(QMessageBox, "information"):
        form.randevuyu_kaydet()
    govde = AKTIF["s"].govdeler[-1]
    assert govde["gorusme_tipi"] == "YUZ_YUZE" and "terapi_turu" not in govde
    form.close()


# ------------------------------------------------------------------ Randevu Düzenle formu
def test_duzenleme_formu_mevcut_gorusme_ve_terapiyi_gosterir_ve_gonderir(qt_app):
    AKTIF["s"] = Sunucu()
    eski = {"danisan_kod_id": "DAN-2026-0002", "psikolog_id": 3, "oda_id": 2, "durum": "PLANLANDI",
            "baslangic_zamani": "2026-12-07T10:00:00", "bitis_zamani": "2026-12-07T11:00:00",
            "gorusme_tipi": "ONLINE", "terapi_turu": "OYUN_TERAPISI"}
    form = RandevuDuzenleFormu("http://x", "T", 11, 7, eski)
    isle()
    assert form.cmb_gorusme.currentData() == "ONLINE" and form.cmb_terapi.currentData() == "OYUN_TERAPISI"
    form.cmb_terapi.setCurrentIndex(form.cmb_terapi.findData("BIREYSEL_TERAPI"))
    with patch.object(QMessageBox, "information"):
        form.randevuyu_guncelle()
    govde = AKTIF["s"].govdeler[-1]
    assert govde["gorusme_tipi"] == "ONLINE" and govde["terapi_turu"] == "BIREYSEL_TERAPI"
    form.close()


# ------------------------------------------------------------------ Randevu Yönetimi tablosu
def test_randevu_tablosu_gorusme_ve_terapi_sutunlari(qt_app):
    simdi = datetime.now()

    def kayit(no, **ek):
        return {"randevu_id": no, "danisan_kod_id": f"DAN-2026-{no:04d}", "psikolog_id": 3, "oda_id": 2, "durum": "PLANLANDI",
                "baslangic_zamani": (simdi + timedelta(days=no)).isoformat(), "bitis_zamani": (simdi + timedelta(days=no, hours=1)).isoformat(), **ek}

    AKTIF["s"] = Sunucu([kayit(1, gorusme_tipi="ONLINE", terapi_turu="OYUN_TERAPISI"), kayit(2)])      # 2: eski randevu
    with patch.object(rmodul, "oturum_kontrollu_istek", side_effect=lambda *a, **k: AKTIF["s"](*a, **k)):
        ekran = RandevuAnaEkrani("http://x", "T", 11, "admin")
    t = ekran.tablo
    assert [t.horizontalHeaderItem(i).text() for i in (6, 7, 8)] == ["Görüşme", "Terapi", "Durum"]
    satir = {t.item(i, 0).text(): i for i in range(t.rowCount())}
    assert [t.item(satir["1"], c).text() for c in (6, 7)] == ["Online", "Oyun terapisi"]
    assert [t.item(satir["2"], c).text() for c in (6, 7)] == ["Yüz yüze", "-"]
    ekran.close()
