"""Öğrenciler sayfası düzeltmeleri.

- Sunucu: öğrenci ekleme girdisi sunucuda doğrulanır (numara rakam, telefon biçimi); kalıcı silme ayrı izne bağlıdır;
  ekleme denetim kaydı yalnızca türü yazar; kimlik listesi sıralı gelir.
- İstemci: arama/yenileme sıralamayı ve seçimi korur, boş liste mesajı, kalıcı silme düğmesi izne göre, puan penceresi
  varsayılan dönemi, Öğrenci Ekle penceresi (telefon kuralı, hata ayrıntısı, çift tıklama).
"""
import json
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QDateEdit, QPushButton

import client.ogrenci_dialog as dialog_modulu
import client.ogrenci_yonetim_ekrani as modul
import server.sunucu as sunucu
from server.modeller import OgrenciEkleModeli
from server.sunucu import app, mevcut_kullanici_id


# ------------------------------------------------------------------ sunucu: giriş doğrulaması
def _ekle(**ek):
    veri = {"ad_soyad": "Ayşe Kaya", "ogrenci_numarasi": "2310001", "tur": "GONULLU"}
    veri.update(ek)
    return OgrenciEkleModeli(**veri)


@pytest.mark.parametrize("numara", ["abc123", "12 34", "12-34", "١٢٣٤"])
def test_ogrenci_numarasi_yalniz_rakam_olabilir(numara):
    with pytest.raises(ValidationError):
        _ekle(ogrenci_numarasi=numara)


@pytest.mark.parametrize("telefon,beklenen", [
    ("05551234567", "05551234567"), ("5551234567", "05551234567"), ("555 123 45 67", "05551234567"), (None, None), ("   ", None),
])
def test_telefon_sunucuda_duzenlenir(telefon, beklenen):
    assert _ekle(telefon=telefon).telefon == beklenen


@pytest.mark.parametrize("telefon", ["abc", "055512345", "0555123456789", "15551234567", "<script>"])
def test_gecersiz_telefon_reddedilir(telefon):
    with pytest.raises(ValidationError):
        _ekle(telefon=telefon)


# ------------------------------------------------------------------ sunucu: denetim, sıralama, izin
class _Imlec:
    def __init__(self, satirlar=None):
        self.sorgular, self.satirlar = [], satirlar or []

    def execute(self, sorgu, parametreler=None):
        self.sorgular.append(" ".join(str(sorgu).split()))

    def fetchone(self):
        return (7,)

    def fetchall(self):
        return self.satirlar

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


def test_ogrenci_ekleme_denetimi_yalniz_turu_yazar_kisisel_veri_yazmaz():
    imlec = _Imlec()
    with patch.object(sunucu, "vt_baglan", return_value=_Baglanti(imlec)), \
            patch.object(sunucu, "denetim_kaydi_olustur") as denetim:
        sunucu.ogrenci_ekle(_ekle(telefon="05551234567", bolum="Psikoloji"), yetkili_id=1)
    ayrinti = denetim.call_args.kwargs["ayrinti"]
    assert ayrinti == {"yeni": {"tur": "GONULLU"}}
    assert "Ayşe" not in json.dumps(ayrinti) and "2310001" not in json.dumps(ayrinti) and "0555" not in json.dumps(ayrinti)


def test_ogrenci_kimlik_listesi_sirali_gelir():
    imlec = _Imlec([(1, "Ali", "10", "GONULLU")])
    with patch.object(sunucu, "vt_baglan", return_value=_Baglanti(imlec)):
        sunucu.ogrencileri_getir(kullanici_id=1)
    assert "ORDER BY ad_soyad, ogrenci_numarasi" in imlec.sorgular[0]


@pytest.fixture
def giris_yapmis_kullanici():
    app.dependency_overrides[mevcut_kullanici_id] = lambda: 5
    yield
    app.dependency_overrides.pop(mevcut_kullanici_id, None)


def test_kalici_silme_listeleme_izniyle_yapilamaz_ayri_izin_ister(giris_yapmis_kullanici):
    conn = MagicMock()
    cursor = conn.cursor.return_value
    sorulan = []

    def calistir(sql, params=None):
        if "izin_adi" in sql:
            sorulan.append(params[1])
            cursor.fetchone.return_value = (1,) if params[1] == "FAALIYET_KAYITLARI_DUZENLE" else None

    cursor.execute.side_effect = calistir
    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        with TestClient(app) as istemci:
            yanit = istemci.request("DELETE", "/api/ogrenciler/3/saklama-suresi-sil", json={"onayla": True})
    assert yanit.status_code == 403 and sorulan == ["OGRENCI_KAYDI_SIL"]
    assert not any(c.args[0].lstrip().upper().startswith("DELETE") for c in cursor.execute.call_args_list)
    conn.commit.assert_not_called()


# ------------------------------------------------------------------ istemci ekranı
def _yanit(veri, kod=200):
    m = MagicMock()
    m.status_code = kod
    m.json.return_value = veri
    m.text = json.dumps(veri)
    m._tkys_oturum_reddedildi = False
    return m


def _ogrenci(no, ad, tur="GONULLU", aktif=True, dolu=False, ertelendi=False):
    return {
        "ogrenci_id": no, "ad_soyad": ad, "ogrenci_numarasi": f"23100{no:03d}", "tur": tur,
        "tur_etiketi": "Gönüllü Öğrenci" if tur == "GONULLU" else "Asistan Öğrenci", "aktif_mi": aktif, "kullanici_id": None,
        "kullanici_adi": None, "rol_adi": None, "telefon": None, "olusturulma_tarihi": "2010-01-05T10:00:00",
        "kayit_suresi_doldu": dolu, "ertelemeye_kadar": "2030-01-01" if ertelendi else None, "ertelendi_mi": ertelendi,
    }


def _ekran(tkys_qapplication, kayitlar, **ek):
    with patch.object(modul, "oturum_kontrollu_istek", return_value=_yanit(kayitlar)), \
            patch.object(modul.QMessageBox, "information", lambda *a, **k: 0):
        ekran = modul.OgrenciYonetimEkrani("http://x", "t", **ek)
        ekran.yenile()
    return ekran


def _adlar(ekran):
    return [ekran.tablo.item(s, 0).text() for s in range(ekran.tablo.rowCount())]


def test_arama_ve_yenileme_siralamayi_ve_secimi_korur(tkys_qapplication):
    kayitlar = [_ogrenci(1, "Zeynep"), _ogrenci(2, "Ali"), _ogrenci(3, "Can"), _ogrenci(4, "Bora")]
    ekran = _ekran(tkys_qapplication, kayitlar)
    ekran.tablo._tiklandi_siralama(0)                                   # Ad Soyad, artan
    assert _adlar(ekran) == ["Ali", "Bora", "Can", "Zeynep"]
    ekran.tablo.selectRow(2)                                            # Can

    ekran.arama.setText("a")                                            # "a" geçenler: Ali, Bora, Can
    assert _adlar(ekran) == ["Ali", "Bora", "Can"]                      # sıralama korundu (sunucu sırası Ali, Can, Bora olurdu)
    ekran.arama.setText("")
    with patch.object(modul, "oturum_kontrollu_istek", return_value=_yanit(kayitlar)):
        ekran.yenile()
    assert _adlar(ekran) == ["Ali", "Bora", "Can", "Zeynep"]
    assert ekran.secili_ogrenci()["ad_soyad"] == "Can"


def test_bos_liste_ve_sonuc_yok_mesajlari(tkys_qapplication):
    ekran = _ekran(tkys_qapplication, [])
    assert not ekran.bos_mesaj.isHidden() and ekran.tablo.isHidden() and "Henüz" in ekran.bos_mesaj.text()
    ekran = _ekran(tkys_qapplication, [_ogrenci(1, "Ali")])
    ekran.arama.setText("bulunmayan")
    assert not ekran.bos_mesaj.isHidden() and "uyan öğrenci yok" in ekran.bos_mesaj.text()
    ekran.arama.setText("")
    assert ekran.bos_mesaj.isHidden() and not ekran.tablo.isHidden()


def test_sure_dolan_karti_ve_dugmesi_islem_bekleyenleri_sayar(tkys_qapplication):
    kayitlar = [_ogrenci(1, "A", dolu=True), _ogrenci(2, "B", dolu=True, ertelendi=True), _ogrenci(3, "C"),
                _ogrenci(4, "D", tur="ASISTAN", dolu=True)]
    ekran = _ekran(tkys_qapplication, kayitlar)
    assert ekran.degerler["expired"].text() == "1" and "(1)" in ekran.sure_btn.text()


def _pencere_incele(ekran, islev):
    """Yerel pencereyi gösterilmeden inceler: QDialog.exec yerine dialog içindeki düğmeleri/tarihleri toplar."""
    sonuc = {}

    def exec_(dialog):
        sonuc["dugmeler"] = {d.text(): d for d in dialog.findChildren(QPushButton)}
        sonuc["tarihler"] = dialog.findChildren(QDateEdit)
        return 0

    with patch.object(modul.QDialog, "exec", exec_):
        islev()
    return sonuc


@pytest.mark.parametrize("silebilir", [True, False])
def test_kalici_silme_dugmesi_izne_gore_gorunur(tkys_qapplication, silebilir):
    kayitlar = [_ogrenci(1, "Ali", dolu=True)]
    ekran = _ekran(tkys_qapplication, kayitlar, silebilir=silebilir)
    with patch.object(modul, "oturum_kontrollu_istek", return_value=_yanit(kayitlar)):        # pencere listeyi yeniden çeker
        incelenen = _pencere_incele(ekran, ekran.suresi_dolan_ac)
    assert incelenen["dugmeler"]["Seçili Kaydı Sil"].isHidden() is (not silebilir)


def test_puan_penceresi_varsayilan_donemi_ayin_basindan_bugune(tkys_qapplication):
    ekran = _ekran(tkys_qapplication, [_ogrenci(1, "Ali")])
    ekran.tablo.selectRow(0)
    bos = {"ogrenci_id": 1, "toplam_puan": 0, "faaliyetler": []}
    with patch.object(modul, "oturum_kontrollu_istek", return_value=_yanit(bos)):
        incelenen = _pencere_incele(ekran, ekran.detay_ac)
    baslangic, bitis = incelenen["tarihler"]
    bugun = QDate.currentDate()
    assert baslangic.date() == QDate(bugun.year(), bugun.month(), 1) and bitis.date() == bugun


def test_puan_penceresi_tarih_degisince_kendiliginden_hesaplar(tkys_qapplication):
    ekran = _ekran(tkys_qapplication, [_ogrenci(1, "Ali")])
    ekran.tablo.selectRow(0)
    istekler = []

    def istek(metot, url, **kw):
        istekler.append(kw.get("params"))
        return _yanit({"ogrenci_id": 1, "toplam_puan": 0, "faaliyetler": []})

    def exec_(dialog):
        baslangic, _ = dialog.findChildren(QDateEdit)
        istekler.clear()
        baslangic.setDate(baslangic.date().addDays(-3))                # düğmeye basmadan
        return 0

    with patch.object(modul, "oturum_kontrollu_istek", side_effect=istek), patch.object(modul.QDialog, "exec", exec_):
        ekran.detay_ac()
    assert len(istekler) == 1
    assert istekler[0]["baslangic"] == (date.today().replace(day=1) - timedelta(days=3)).isoformat()


def test_ortak_hata_metni_liste_bicimli_ayrintiyi_okunur_yapar():
    yanit = _yanit({"detail": [{"msg": "Value error, Öğrenci numarası yalnızca rakamlardan oluşmalıdır."}]}, 422)
    assert modul.OgrenciYonetimEkrani.hata(yanit) == "Öğrenci numarası yalnızca rakamlardan oluşmalıdır."


# ------------------------------------------------------------------ Öğrenci Ekle penceresi
def _doldur(pencere, telefon="", no="2310001"):
    pencere.le_ad_soyad.setText("Ayşe Kaya")
    pencere.le_ogrenci_no.setText(no)
    pencere.le_telefon.setText(telefon)


@pytest.mark.parametrize("yazilan,gonderilen", [("5551234567", "05551234567"), ("05551234567", "05551234567"), ("", "")])
def test_dialog_telefon_10_ya_da_11_hane_kabul_edilir_11_hane_gonderilir(tkys_qapplication, yazilan, gonderilen):
    pencere = dialog_modulu.OgrenciEkleDialog("http://x", "t")
    _doldur(pencere, yazilan)
    with patch.object(dialog_modulu, "oturum_kontrollu_istek", return_value=_yanit({}, 200)) as istek, \
            patch.object(dialog_modulu, "basari_bildirimi"):
        pencere.kaydet_tiklandi()
    assert istek.call_args.kwargs["json"]["telefon"] == gonderilen


@pytest.mark.parametrize("telefon", ["555123456", "55512345678", "15551234567"])
def test_dialog_gecersiz_telefonu_gondermez(tkys_qapplication, telefon):
    pencere = dialog_modulu.OgrenciEkleDialog("http://x", "t")
    _doldur(pencere, telefon)
    with patch.object(dialog_modulu, "oturum_kontrollu_istek") as istek, patch.object(dialog_modulu.QMessageBox, "warning") as uyari:
        pencere.kaydet_tiklandi()
    istek.assert_not_called()
    assert "10 haneli" in uyari.call_args.args[2]


def test_dialog_sunucu_hatasinda_aciklamayi_gosterir_ve_dugme_yeniden_acilir(tkys_qapplication):
    pencere = dialog_modulu.OgrenciEkleDialog("http://x", "t")
    _doldur(pencere)
    with patch.object(dialog_modulu, "oturum_kontrollu_istek", return_value=_yanit({"detail": "Bu işlem için yetkiniz yok."}, 403)), \
            patch.object(dialog_modulu.QMessageBox, "warning") as uyari:
        pencere.kaydet_tiklandi()
    assert "yetkiniz yok" in uyari.call_args.args[2]
    assert pencere.btn_kaydet.isEnabled()


def test_dialog_istek_surerken_kaydet_dugmesi_kilitlidir(tkys_qapplication):
    pencere = dialog_modulu.OgrenciEkleDialog("http://x", "t")
    _doldur(pencere)
    durumlar = []

    def istek(*a, **k):
        durumlar.append(pencere.btn_kaydet.isEnabled())
        return _yanit({}, 200)

    with patch.object(dialog_modulu, "oturum_kontrollu_istek", side_effect=istek), patch.object(dialog_modulu, "basari_bildirimi"):
        pencere.kaydet_tiklandi()
    assert durumlar == [False]
