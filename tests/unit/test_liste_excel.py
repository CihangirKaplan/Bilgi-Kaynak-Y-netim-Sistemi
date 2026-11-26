"""Liste sayfalarından Excel aktarımı: Cihaz Envanteri, Öğrenciler, Danışanlar ve ortak yardımcı."""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "acceptance"))

from unittest.mock import MagicMock, patch

import pytest
from openpyxl import load_workbook
from PySide6.QtWidgets import QApplication, QWidget

import client.cihaz_ekranlari as envanter
import client.liste_excel as liste_excel
import client.rapor_cikti as rapor_cikti
import client.ogrenci_yonetim_ekrani as ogr_modulu
from client.liste_excel import dosya_adi_olustur, listeyi_excele_aktar


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    return QApplication.instance() or QApplication([])


def _yanit(veri):
    y = MagicMock(status_code=200, _tkys_oturum_reddedildi=False)
    y.json.return_value = veri
    return y


def _oku(yol):
    kitap = load_workbook(yol)
    return kitap, kitap[kitap.sheetnames[1]]


def _hucreler(sayfa):
    return [[h.value for h in satir] for satir in sayfa.iter_rows()]


@pytest.fixture
def kaydet(tmp_path):
    """Dosya seçme penceresini ve açılan mesaj kutularını yakalar; dosya tmp_path'e yazılır."""
    yol = str(tmp_path / "cikti.xlsx")
    with patch.object(rapor_cikti.QFileDialog, "getSaveFileName", return_value=(yol, "")) as dosya, \
            patch.object(liste_excel.QMessageBox, "information") as bilgi, \
            patch.object(liste_excel.QMessageBox, "warning") as uyari, \
            patch.object(liste_excel, "oturum_kontrollu_istek", return_value=_yanit({"durum": "basarili"})) as denetim:
        yield type("K", (), {"yol": yol, "dosya": dosya, "bilgi": bilgi, "uyari": uyari, "denetim": denetim})


# ------------------------------------------------------------------ ortak yardımcı
def test_dosya_adi_tarih_saat_icerir():
    from datetime import datetime
    assert dosya_adi_olustur("cihaz_envanteri", datetime(2026, 11, 20, 9, 5)) == "cihaz_envanteri_20261120_0905.xlsx"


def test_yardimci_ozet_ve_liste_sayfasi_yazar_formulu_metin_yapar(kaydet):
    yol = listeyi_excele_aktar(
        QWidget(), "Deneme", "deneme", [("Ad", None), ("Sayı", "0")],
        [["=1+1", 5], ["Ayşe", 7]], [("Arama", "Yok")], sayfa_adi="Liste",
    )
    assert yol == kaydet.yol
    kitap, sayfa = _oku(yol)
    assert kitap.sheetnames == ["Özet", "Liste"]
    satirlar = _hucreler(sayfa)
    assert satirlar[0] == ["Ad", "Sayı"] and satirlar[1] == ["=1+1", 5] and satirlar[2] == ["Ayşe", 7]
    assert sayfa["A2"].data_type == "s"                                  # formül değil, düz metin
    ozet = [str(h.value) for satir in kitap["Özet"].iter_rows() for h in satir if h.value is not None]
    assert "Arama" in ozet and 2 in [h.value for satir in kitap["Özet"].iter_rows() for h in satir]   # aktarılan kayıt = 2
    kaydet.bilgi.assert_called_once()


def test_yardimci_kayit_yoksa_dosya_sormaz(kaydet):
    assert listeyi_excele_aktar(QWidget(), "Deneme", "deneme", [("Ad", None)], []) is None
    kaydet.dosya.assert_not_called()
    kaydet.bilgi.assert_called_once()


def test_yardimci_iptal_edilince_yazmaz(kaydet):
    kaydet.dosya.return_value = ("", "")
    assert listeyi_excele_aktar(QWidget(), "Deneme", "deneme", [("Ad", None)], [["a"]]) is None
    kaydet.bilgi.assert_not_called()


def test_yardimci_uzantiyi_tamamlar_ve_yazma_hatasini_bildirir(kaydet, tmp_path):
    kaydet.dosya.return_value = (str(tmp_path / "x"), "")
    assert listeyi_excele_aktar(QWidget(), "Deneme", "deneme", [("Ad", None)], [["a"]]).endswith("x.xlsx")
    with patch.object(liste_excel, "excel_olustur", side_effect=PermissionError("kilitli")):
        assert listeyi_excele_aktar(QWidget(), "Deneme", "deneme", [("Ad", None)], [["a"]]) is None
    kaydet.uyari.assert_called_once()
    kaydet.denetim.assert_not_called()                                   # kayit verilmediyse denetim isteği atılmaz


# ------------------------------------------------------------------ cihaz envanteri
CIHAZLAR = [
    {"cihaz_id": 1, "envanter_kodu": "E-1", "cihaz_adi": "EEG", "marka_model": "Acme", "seri_no": "S1",
     "durum": "Kullanima_Hazir", "kayit_tarihi": "2026-01-05"},
    {"cihaz_id": 2, "envanter_kodu": "E-2", "cihaz_adi": "TMS", "marka_model": None, "seri_no": None,
     "durum": "Arizali", "kayit_tarihi": None},
    {"cihaz_id": 3, "envanter_kodu": "E-3", "cihaz_adi": "Monitör", "marka_model": "M", "seri_no": "S3",
     "durum": "Kullanima_Hazir", "kayit_tarihi": "2026-02-01T10:00:00"},
]


def _envanter():
    with patch.object(envanter, "oturum_kontrollu_istek", return_value=_yanit(CIHAZLAR)):
        return envanter.CihazYonetimEkrani("http://x", "T", yetkili_mi=True)


def test_envanter_excel_dugmesi_var_ve_tum_cihazlari_yazar(kaydet):
    ekran = _envanter()
    assert any("Dışa Aktar" in d.text() for d in ekran.findChildren(liste_excel.QPushButton))
    ekran.excele_aktar()
    _, sayfa = _oku(kaydet.yol)
    satirlar = _hucreler(sayfa)
    assert satirlar[0] == ["Envanter Kodu", "Cihaz Adı", "Marka / Model", "Seri No", "Durum", "Kayıt Tarihi"]
    assert [s[0] for s in satirlar[1:]] == ["E-1", "E-2", "E-3"]
    assert satirlar[1][4] == "Kullanıma Hazır" and satirlar[2][4] == "Arızalı"     # okunur durum adı, veritabanı kodu değil
    assert satirlar[2][2] in ("", None) and satirlar[2][5] is None                         # boş değerler boş kalır
    ekran.close()


def test_envanter_excel_yalniz_gorunen_cihazlari_yazar(kaydet):
    ekran = _envanter()
    ekran.arama.setText("tms")
    ekran.excele_aktar()
    _, sayfa = _oku(kaydet.yol)
    assert [s[0] for s in _hucreler(sayfa)[1:]] == ["E-2"]
    ekran.arama.setText("")
    ekran.durum_filtrele("Kullanima_Hazir")
    ekran.excele_aktar()
    _, sayfa = _oku(kaydet.yol)
    assert [s[0] for s in _hucreler(sayfa)[1:]] == ["E-1", "E-3"]
    ekran.close()


# ------------------------------------------------------------------ öğrenciler
OGRENCILER = [
    {"ogrenci_id": 1, "ad_soyad": "Ayşe Yılmaz", "ogrenci_numarasi": "0012", "telefon": "05550000000", "tur": "GONULLU",
     "tur_etiketi": "Gönüllü Öğrenci", "kullanici_adi": "ayse", "olusturulma_tarihi": "2026-03-04T10:00:00", "aktif_mi": True, "kayit_suresi_doldu": False, "ertelendi_mi": False},
    {"ogrenci_id": 2, "ad_soyad": "=HYPERLINK(\"x\")", "ogrenci_numarasi": "77", "telefon": None, "tur": "ASISTAN",
     "tur_etiketi": "Asistan Öğrenci", "kullanici_adi": None, "olusturulma_tarihi": "2026-03-05T10:00:00", "aktif_mi": False, "kayit_suresi_doldu": False, "ertelendi_mi": False},
]


def _ogrenci_ekrani():
    ekran = ogr_modulu.OgrenciYonetimEkrani("http://x", "T")
    with patch.object(ogr_modulu, "oturum_kontrollu_istek", return_value=_yanit(OGRENCILER)):
        ekran.yenile()
    return ekran


def test_ogrenci_excel_gorunen_ogrencileri_bicimli_telefonla_yazar(kaydet):
    ekran = _ogrenci_ekrani()
    ekran.excele_aktar()
    _, sayfa = _oku(kaydet.yol)
    satirlar = _hucreler(sayfa)
    assert satirlar[0] == ["Ad Soyad", "Öğrenci No", "Telefon", "Öğrenci Grubu", "Bağlı Hesap", "Kayıt Tarihi", "Durum"]
    assert satirlar[1][:3] == ["Ayşe Yılmaz", "0012", "0555 000 00 00"]        # baştaki sıfır korunur, telefon okunur
    assert satirlar[1][6] == "Aktif" and satirlar[2][6] == "Pasif"
    assert sayfa["A3"].data_type == "s"                                         # formül gibi görünen ad düz metin
    ekran.close()


def test_ogrenci_excel_arama_ve_suzgece_uyar(kaydet):
    ekran = _ogrenci_ekrani()
    ekran.arama.setText("ayşe")
    ekran.excele_aktar()
    _, sayfa = _oku(kaydet.yol)
    assert [s[0] for s in _hucreler(sayfa)[1:]] == ["Ayşe Yılmaz"]
    ekran.arama.clear()
    ekran.durum_filtresi.setCurrentIndex(2)                                     # Pasif
    ekran.excele_aktar()
    _, sayfa = _oku(kaydet.yol)
    assert [s[6] for s in _hucreler(sayfa)[1:]] == ["Pasif"]
    ekran.close()


# ------------------------------------------------------------------ danışanlar
def test_danisan_excel_yalniz_gorunen_kodlari_yazar(kaydet):
    import test_danisanlar_ekrani as dt
    dt.AKTIF.clear()
    sunucu = dt.Sunucu()
    dt.AKTIF["s"] = sunucu
    with patch.object(dt.modul, "oturum_kontrollu_istek", side_effect=sunucu), \
            patch.object(dt.rmodul, "oturum_kontrollu_istek", side_effect=sunucu):
        ekran = dt.DanisanlarEkrani("http://testserver", "TOKEN", 11)
        tum = [ekran.tablo.item(i, 0).text() for i in range(ekran.tablo.rowCount())]
        ekran.excele_aktar()
        _, sayfa = _oku(kaydet.yol)
        satirlar = _hucreler(sayfa)
        assert satirlar[0] == ["Danışan Kodu", "Psikolog", "Yaş Grubu", "Ücret", "Randevu", "Durum"]
        assert [s[0] for s in satirlar[1:]] == tum and len(tum) >= 2
        ilk = next(s for s in satirlar[1:] if s[0] == "DAN-2026-0001")
        assert ilk[4] == 4                                                       # 4 randevu, sayı olarak
        ekran.arama.setText("DAN-2026-0003")
        ekran.excele_aktar()
        _, sayfa = _oku(kaydet.yol)
        assert [s[0] for s in _hucreler(sayfa)[1:]] == ["DAN-2026-0003"]
        ekran.close()


# ------------------------------------------------------------------ denetim kaydı
def test_aktarim_denetim_kaydina_yazilir_dogru_liste_ve_satir_sayisiyla(kaydet):
    ekran = _envanter()
    ekran.arama.setText("tms")
    ekran.excele_aktar()
    yontem, adres = kaydet.denetim.call_args.args[:2]
    assert (yontem, adres) == ("POST", "http://x/api/liste-aktarim-kaydi")
    assert kaydet.denetim.call_args.kwargs["json"] == {"liste": "CIHAZ", "satir_sayisi": 1}     # yalnızca görünen 1 cihaz
    assert kaydet.denetim.call_args.kwargs["headers"] == {"Authorization": "Bearer T"}
    kaydet.uyari.assert_not_called()
    ekran.close()


def test_ogrenci_ve_danisan_dogru_liste_kodunu_gonderir(kaydet):
    ekran = _ogrenci_ekrani()
    ekran.excele_aktar()
    assert kaydet.denetim.call_args.kwargs["json"] == {"liste": "OGRENCI", "satir_sayisi": 2}
    ekran.close()
    import test_danisanlar_ekrani as dt
    dt.AKTIF.clear()
    sunucu = dt.Sunucu()
    dt.AKTIF["s"] = sunucu
    with patch.object(dt.modul, "oturum_kontrollu_istek", side_effect=sunucu), patch.object(dt.rmodul, "oturum_kontrollu_istek", side_effect=sunucu):
        d = dt.DanisanlarEkrani("http://testserver", "TOKEN", 11)
        d.excele_aktar()
        assert kaydet.denetim.call_args.kwargs["json"]["liste"] == "DANISAN"
        d.close()


def test_denetim_kaydi_yazilamazsa_kullaniciya_acikca_soylenir(kaydet):
    kaydet.denetim.return_value = MagicMock(status_code=500, _tkys_oturum_reddedildi=False)
    ekran = _envanter()
    ekran.excele_aktar()
    kaydet.uyari.assert_called_once()
    assert "denetim kaydına yazılamadı" in kaydet.uyari.call_args.args[2]
    kaydet.denetim.side_effect = ConnectionError("yok")
    kaydet.uyari.reset_mock()
    ekran.excele_aktar()
    kaydet.uyari.assert_called_once()
    ekran.close()
