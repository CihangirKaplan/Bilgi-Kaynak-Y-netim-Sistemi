"""Audit Kayıtları sayfası düzeltmeleri.

- Sunucu: kayıt sayımı yalnızca ilk sayfada (ozet=false ile sonraki sayfalarda yok), kullanıcı aramasında % ve _ düz karakter,
  "Değişiklik İşlemleri" iptal ve cihaz durum değişikliğini de sayar, denetim kayıtlarının Excel aktarımı denetime yazılır.
- İstemci: tablo/ayrıntı etiketleri eksiksiz, "Görüntüle" düğmesi satıra sığar, sıralama yok, sonraki sayfa özeti korur,
  Excel aktarımı denetim kaydına yazılır.
"""
import json
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from PySide6.QtWidgets import QPushButton

import client.audit_kayitlari_ekrani as modul
import client.rapor_cikti as rapor_cikti
import server.sunucu as sunucu
from server import audit_api


# ------------------------------------------------------------------ sunucu
class _Imlec:
    def __init__(self):
        self.sorgular = []

    def execute(self, sorgu, parametreler=None):
        self.sorgular.append((" ".join(str(sorgu).split()), parametreler))

    def fetchone(self):
        return (671, 44, 168, 3)

    def fetchall(self):
        return []

    def close(self):
        pass


class _Baglanti:
    def __init__(self, imlec):
        self.imlec = imlec

    def cursor(self, *a, **k):
        return self.imlec

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


def _liste(**ek):
    imlec = _Imlec()
    varsayilan = dict(kullanici=None, olay_turu=None, baslangic_tarihi=None, bitis_tarihi=None, limit=50, offset=0, ozet=True, kullanici_id=1)
    varsayilan.update(ek)
    with patch.object(audit_api, "vt_baglan", return_value=_Baglanti(imlec)):     # kod server/audit_api.py'ye taşındı
        sonuc = sunucu.audit_kayitlarini_getir(**varsayilan)
    return sonuc, imlec


def test_ilk_sayfa_kayitlari_sayar_ozet_doner():
    sonuc, imlec = _liste()
    assert sonuc["ozet"] == {"toplam_kayit": 671, "basarisiz_giris": 44, "kullanici_islemleri": 168, "bugunku_islemler": 3}
    assert any("COUNT(*)" in s for s, _ in imlec.sorgular)


def test_sonraki_sayfalarda_sayim_yapilmaz():
    sonuc, imlec = _liste(offset=50, ozet=False)
    assert sonuc["ozet"] is None
    assert not any("COUNT(*)" in s for s, _ in imlec.sorgular)                  # tüm süzgeçli kayıtlar yeniden sayılmaz
    assert any("LIMIT" in s for s, _ in imlec.sorgular)                          # kayıtlar yine de gelir


def test_degisiklik_islemleri_iptal_ve_cihaz_durumunu_da_sayar():
    _, imlec = _liste()
    sayim = next(s for s, _ in imlec.sorgular if "COUNT(*)" in s)
    for olay in ("CREATE", "UPDATE", "ROLE_CHANGE", "DELETE", "CANCEL", "DEVICE_STATUS_CHANGE"):
        assert f"'{olay}'" in sayim


@pytest.mark.parametrize("yazilan,beklenen", [("%", "%\\%%"), ("a_b", "%a\\_b%"), ("100%_x", "%100\\%\\_x%"), ("adm", "%adm%"), ("a\\b", "%a\\\\b%")])
def test_kullanici_aramasinda_joker_karakterler_duz_karakterdir(yazilan, beklenen):
    _, imlec = _liste(kullanici=yazilan)
    sorgu, parametreler = next((s, p) for s, p in imlec.sorgular if "ILIKE" in s)
    assert "ESCAPE" in sorgu and beklenen in parametreler


class _AktarimImleci:
    def __init__(self, izinli):
        self.izinli = izinli

    def execute(self, sorgu, parametreler=None):
        self.parametreler = parametreler

    def fetchone(self):
        return (1,) if self.izinli else None

    def close(self):
        pass


@pytest.mark.parametrize("izinli", [True, False])
def test_denetim_listesi_aktarimi_ozel_izin_ister_ve_denetim_kayitlari_tablosuna_yazilir(izinli):
    imlec = _AktarimImleci(izinli)
    model = sunucu.ListeAktarimModeli(liste="DENETIM", satir_sayisi=120)
    with patch.object(sunucu, "vt_baglan", return_value=_Baglanti(imlec)), patch.object(sunucu, "denetim_kaydi_olustur") as denetim:
        if izinli:
            sunucu.liste_aktarim_kaydi(model, kullanici_id=7)
            assert denetim.call_args.kwargs["olay_turu"] == "EXPORT" and denetim.call_args.kwargs["hedef_tablo"] == "denetim_kayitlari"
            assert denetim.call_args.kwargs["ayrinti"] == {"liste": "DENETIM", "satir_sayisi": 120}
        else:
            with pytest.raises(sunucu.HTTPException) as hata:
                sunucu.liste_aktarim_kaydi(model, kullanici_id=7)
            assert hata.value.status_code == 403
            denetim.assert_not_called()
    assert imlec.parametreler == (7, ["AUDIT_KAYITLARI_INCELE"])


# ------------------------------------------------------------------ istemci: etiketler
def test_sunucunun_yazdigi_tum_hedef_tablolar_ekranda_okunur_adla_gorunur():
    kaynak = " ".join(p.read_text(encoding="utf-8") for p in Path("server").glob("*.py"))
    tablolar = set(re.findall(r'hedef_tablo\s*=\s*"([a-z_]+)"', kaynak))
    tablolar |= set(re.findall(r'ayrintili_kayit_yaz\([^)]*?"[A-Z_]+",\s*"([a-z_]+)"', kaynak))
    tablolar |= {"denetim_kayitlari", "oda_etkinlikleri", "faaliyetler", "ogrenci_kayit_erteleme_gecmisi", "parola_sifirlama_talepleri"}
    eksik = sorted(t for t in tablolar if t not in modul.HEDEF_TABLO_ADLARI)
    assert not eksik, f"Okunur adı olmayan hedef tablolar: {eksik}"


def test_ayrinti_alanlari_turkce_etiketle_gosterilir():
    satirlar = dict(modul.ayrinti_satirlari({
        "degisen_alanlar": ["etkinlik_adi", "gunler"], "gun_sayisi": 2, "tur": "GONULLU", "liste": "DENETIM", "satir_sayisi": 5,
        "silinen_erteleme_kaydi_sayisi": 1,
    }))
    assert satirlar["Değişen alanlar"] == "Etkinlik adı, Günler"
    assert satirlar["Gün sayısı"] == "2" and satirlar["Tür"] == "GONULLU"
    assert satirlar["Liste"] == "Denetim Kayıtları" and satirlar["Satır sayısı"] == "5"
    assert "Silinen erteleme kaydı" in satirlar


# ------------------------------------------------------------------ istemci: ekran
def _yanit(veri):
    m = MagicMock()
    m.status_code = 200
    m.json.return_value = veri
    m.text = json.dumps(veri)
    m._tkys_oturum_reddedildi = False
    m.raise_for_status = lambda: None
    return m


def _kayit(no, olay="LOGIN", tablo="kullanicilar"):
    return {
        "denetim_id": no, "kullanici_id": 1, "kullanici_adi": "admin", "olay_turu": olay, "hedef_tablo": tablo, "hedef_kayit_id": no,
        "olusturulma_tarihi": "2026-11-24T10:00:00", "ayrinti": None, "istemci_adresi": "10.0.0.1", "hedef_kullanici_adi": None,
    }


def _ekran(tkys_qapplication, istek):
    with patch.object(modul, "oturum_kontrollu_istek", side_effect=istek):
        return modul.AuditKayitlariEkrani("http://x", "t")


def _sayfa_istegi(kayitlar, ozet=None):
    gelen = []

    def istek(metot, url, **kw):
        gelen.append(kw.get("params"))
        return _yanit({"ozet": ozet if kw["params"].get("offset", 0) == 0 else None, "kayitlar": kayitlar, "limit": 50, "offset": 0})

    return istek, gelen


OZET = {"toplam_kayit": 120, "basarisiz_giris": 4, "kullanici_islemleri": 30, "bugunku_islemler": 2}


def test_sonraki_sayfa_ozeti_korur_ve_sayim_istemez(tkys_qapplication):
    istek, gelen = _sayfa_istegi([_kayit(i) for i in range(50)], OZET)
    ekran = _ekran(tkys_qapplication, istek)
    assert "ozet" not in gelen[0] and ekran.toplam == 120
    with patch.object(modul, "oturum_kontrollu_istek", side_effect=istek):
        ekran.sonraki_sayfa()
    assert gelen[1]["offset"] == 50 and gelen[1]["ozet"] == "false"
    assert ekran.toplam == 120 and ekran.ozet_degerleri["toplam_kayit"].text() == "120"      # kartlar ilk sayfanınkini korur
    assert "120 kayıttan 51-100" in ekran.durum.text()


def test_gecersiz_tarih_araligi_istek_gondermez(tkys_qapplication):
    istek, gelen = _sayfa_istegi([], OZET)
    ekran = _ekran(tkys_qapplication, istek)
    gelen.clear()
    ekran.donem_secimi.setCurrentText("Tarih Aralığı")
    ekran.baslangic.setDate(ekran.bitis.date().addDays(3))
    with patch.object(modul, "oturum_kontrollu_istek", side_effect=istek):
        ekran.kayitlari_getir()
    assert gelen == [] and "sonra olamaz" in ekran.durum.text()


def test_tabloda_siralama_yok_detay_dugmesi_satira_sigar(tkys_qapplication):
    istek, _ = _sayfa_istegi([_kayit(i) for i in range(3)], OZET)
    ekran = _ekran(tkys_qapplication, istek)
    assert not hasattr(ekran.tablo, "_tiklandi_siralama")                      # sunucu sayfalı: başlıktan sıralama yanıltıcı olurdu
    ekran.resize(1300, 700)
    ekran.show()
    hucre = ekran.tablo.cellWidget(0, 4)
    dugme = hucre.findChildren(QPushButton)[0]
    assert hucre.minimumSizeHint().height() <= ekran.tablo.rowHeight(0)
    assert dugme.geometry().top() >= 0 and dugme.geometry().bottom() < hucre.height()


def test_excel_aktarimi_denetim_kaydina_yazilir_ve_sayfalarda_ozet_yalniz_ilkinde(tkys_qapplication):
    istek, _ = _sayfa_istegi([_kayit(i) for i in range(2)], OZET)
    ekran = _ekran(tkys_qapplication, istek)
    gelen = []

    def sayfali(metot, url, **kw):
        gelen.append(kw["params"])
        sayfa = [_kayit(i) for i in range(200 if kw["params"]["offset"] == 0 else 50)]
        return _yanit({"ozet": {**OZET, "toplam_kayit": 250} if kw["params"]["offset"] == 0 else None, "kayitlar": sayfa})

    with patch.object(modul, "oturum_kontrollu_istek", side_effect=sayfali), \
            patch.object(rapor_cikti.QFileDialog, "getSaveFileName", return_value=("/tmp/denetim.xlsx", "")), \
            patch("client.audit_excel.audit_excel_olustur") as olustur, patch.object(modul, "aktarimi_denetime_yaz") as yaz, \
            patch.object(modul.QMessageBox, "information"):
        ekran.excel_aktar()
    assert [p.get("ozet") for p in gelen] == [None, "false"]
    assert olustur.call_args.args[1].__len__() == 250
    assert yaz.call_args.args[1]["liste"] == "DENETIM" and yaz.call_args.args[2] == 250


def test_excel_dosya_yazilamazsa_denetim_kaydi_yazilmaz(tkys_qapplication):
    istek, _ = _sayfa_istegi([_kayit(1)], OZET)
    ekran = _ekran(tkys_qapplication, istek)
    with patch.object(modul, "oturum_kontrollu_istek", side_effect=istek), \
            patch.object(rapor_cikti.QFileDialog, "getSaveFileName", return_value=("/tmp/denetim.xlsx", "")), \
            patch("client.audit_excel.audit_excel_olustur", side_effect=OSError("kilitli")), \
            patch.object(modul, "aktarimi_denetime_yaz") as yaz, patch.object(modul.QMessageBox, "warning"):
        ekran.excel_aktar()
    yaz.assert_not_called()
