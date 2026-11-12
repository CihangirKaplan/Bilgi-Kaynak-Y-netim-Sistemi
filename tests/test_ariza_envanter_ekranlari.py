"""Arıza kayıtları ve cihaz envanteri ekranları (ortak tasarıma geçiş sonrası davranış kontrolleri)."""
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

import cihaz_ariza_ekranlari as ariza
import cihaz_ekranlari as envanter


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def cevap(durum=200, veri=None):
    r = MagicMock()
    r._tkys_oturum_reddedildi = False
    r.status_code = durum
    r.json.return_value = veri if veri is not None else []
    r.raise_for_status.return_value = None
    return r


def hap_metni(tablo, satir, sutun):
    return tablo.cellWidget(satir, sutun).findChild(QLabel).text()


ARIZALAR = [
    {"ariza_id": 1, "cihaz_adi": "EEG", "ariza_baslik": "Kablo kopuk", "ariza_aciklama": "x",
     "aciliyet": "Kritik", "durum": "Açık", "bildirim_tarihi": "2026-11-01T10:30:00"},
    {"ariza_id": 2, "cihaz_adi": "EKG Cihazı", "ariza_baslik": "Ekran bozuk", "ariza_aciklama": "y",
     "aciliyet": "Belirtilmedi", "durum": "Çözüldü", "bildirim_tarihi": None},
]


def ariza_ekrani(yetkili, veri=ARIZALAR):
    with patch.object(ariza, "oturum_kontrollu_istek", return_value=cevap(200, veri)):
        return ariza.ArizaYonetimEkrani("http://x", "T", yetkili_mi=yetkili)


# ------------------------------------------------------------------ arıza listesi
def test_ariza_listesi_satirlari_ve_cipleri(qt_app):
    e = ariza_ekrani(True)
    assert e.tablo.rowCount() == 2
    assert e.cip_toplam.text() == "2 kayıt" and e.cip_acik.text() == "1 açık" and e.cip_cozulen.text() == "1 çözüldü"
    assert hap_metni(e.tablo, 0, 3) == "Kritik" and hap_metni(e.tablo, 0, 4) == "Açık"
    assert hap_metni(e.tablo, 1, 3) == "Belirtilmedi" and hap_metni(e.tablo, 1, 4) == "Çözüldü"
    assert e.tablo.item(0, 5).text() == "2026-11-01 10:30"
    assert e.tablo.item(1, 5).text() == ""                 # tarih boşsa çökmez


def test_duzenle_butonu_yalniz_yetkili_ve_acik_arizada(qt_app):
    e = ariza_ekrani(True)
    assert e.tablo.cellWidget(0, 6) is not None and e.tablo.cellWidget(1, 6) is None
    assert ariza_ekrani(False).tablo.cellWidget(0, 6) is None


def test_ariza_arama_cihaz_ve_basliga_bakar(qt_app):
    e = ariza_ekrani(False)
    e.filtrele("kablo")
    assert not e.tablo.isRowHidden(0) and e.tablo.isRowHidden(1)
    e.filtrele("ekg")
    assert e.tablo.isRowHidden(0) and not e.tablo.isRowHidden(1)
    e.filtrele("")
    assert not e.tablo.isRowHidden(0) and not e.tablo.isRowHidden(1)


def test_ariza_bos_ve_hata_mesaji(qt_app):
    e = ariza_ekrani(True, veri=[])
    assert not e.bos_mesaj.isHidden() and e.tablo.isHidden()
    bozuk = cevap()
    bozuk.raise_for_status.side_effect = RuntimeError("sunucu yok")
    with patch.object(ariza, "oturum_kontrollu_istek", return_value=bozuk):
        e.verileri_yukle()
    assert "yüklenemedi" in e.bos_mesaj.text() and not e.bos_mesaj.isHidden()


def test_ariza_bildirim_formu_yalniz_uygun_cihazlari_listeler_ve_gonderir(qt_app):
    cihazlar = [
        {"cihaz_id": 1, "envanter_kodu": "E1", "cihaz_adi": "A", "durum": "Kullanima_Hazir"},
        {"cihaz_id": 2, "envanter_kodu": "E2", "cihaz_adi": "B", "durum": "Arizali"},
        {"cihaz_id": 3, "envanter_kodu": "E3", "cihaz_adi": "C", "durum": "Bakimda"},
        {"cihaz_id": 4, "envanter_kodu": "E4", "cihaz_adi": "D", "durum": "Rezerve"},
    ]
    with patch.object(ariza, "oturum_kontrollu_istek", return_value=cevap(200, cihazlar)):
        f = ariza.ArizaBildirimFormu("http://x", "T")
    assert [f.cmb_cihaz.itemData(i) for i in range(f.cmb_cihaz.count())] == [1, 4]
    f.txt_baslik.setText("Başlık")
    f.txt_aciklama.setPlainText("Açıklama")
    f.cmb_aciliyet.setCurrentText("Yüksek")
    with patch.object(ariza, "oturum_kontrollu_istek", return_value=cevap(201, {})) as istek, \
         patch.object(ariza.tmk, "bilgi"):
        f.kaydet()
    assert istek.call_args.args[:2] == ("POST", "http://x/api/arizalar")
    assert istek.call_args.kwargs["json"] == {"cihaz_id": 1, "ariza_baslik": "Başlık",
                                              "ariza_aciklama": "Açıklama", "aciliyet": "Yüksek"}
    assert f.result() == 1
    f.close()


def test_ariza_bildirim_formu_uygun_cihaz_yoksa_buton_kapanir(qt_app):
    with patch.object(ariza, "oturum_kontrollu_istek",
                      return_value=cevap(200, [{"cihaz_id": 2, "envanter_kodu": "E", "cihaz_adi": "B", "durum": "Arizali"}])):
        f = ariza.ArizaBildirimFormu("http://x", "T")
    assert not f.btn_kaydet.isEnabled()
    f.close()


def test_ariza_duzenle_cozuldu_isareti_gonderilir(qt_app):
    f = ariza.ArizaDuzenleFormu("http://x", "T", ARIZALAR[0])
    assert f.cmb_durum.currentIndex() == 0 and f.cmb_aciliyet.currentText() == "Kritik"
    f.cmb_durum.setCurrentIndex(1)
    with patch.object(ariza, "oturum_kontrollu_istek", return_value=cevap(200, {})) as istek, \
         patch.object(ariza.tmk, "bilgi"):
        f.kaydet()
    assert istek.call_args.args[:2] == ("PUT", "http://x/api/arizalar/1")
    assert istek.call_args.kwargs["json"]["cozuldu_mu"] is True
    f.close()


# ------------------------------------------------------------------ envanter
CIHAZLAR = [
    {"cihaz_id": 1, "envanter_kodu": "E-001", "cihaz_adi": "EEG Cihazı", "marka_model": "Brain X",
     "seri_no": "S1", "zimmetli_oda_id": 5, "durum": "Kullanima_Hazir"},
    {"cihaz_id": 2, "envanter_kodu": "E-002", "cihaz_adi": "EKG", "marka_model": None,
     "seri_no": None, "zimmetli_oda_id": None, "durum": "Arizali"},
    {"cihaz_id": 3, "envanter_kodu": "E-003", "cihaz_adi": "Tansiyon", "marka_model": "T",
     "seri_no": "S3", "zimmetli_oda_id": None, "durum": "Bakimda"},
    {"cihaz_id": 4, "envanter_kodu": "E-004", "cihaz_adi": "Spiro", "marka_model": "S",
     "seri_no": "S4", "zimmetli_oda_id": None, "durum": "Kalibrasyonda"},
]


def envanter_ekrani():
    with patch.object(envanter, "oturum_kontrollu_istek", return_value=cevap(200, CIHAZLAR)):
        return envanter.CihazYonetimEkrani("http://x", "T", yetkili_mi=True)


def test_envanter_durumlar_turkce_gorunur_ve_cipler_sayilir(qt_app):
    e = envanter_ekrani()
    assert [hap_metni(e.tablo, i, 4) for i in range(4)] == ["Kullanıma Hazır", "Arızalı", "Bakımda", "Kalibrasyonda"]
    assert e.cip_toplam.text() == "4 cihaz" and e.cip_hazir.text() == "1 kullanıma hazır"
    assert e.cip_bakimda.text() == "2 bakım/kalibrasyon" and e.cip_arizali.text() == "1 arızalı"
    assert e.tablo.item(1, 2).text() == "-" and e.tablo.item(1, 3).text() == "-"     # boş marka/seri


def test_envanter_arama_kod_ad_marka_seri(qt_app):
    e = envanter_ekrani()
    for aranan, gorunen in (("e-002", 1), ("brain", 0), ("s3", 2), ("spiro", 3)):
        e.filtrele(aranan)
        assert [not e.tablo.isRowHidden(i) for i in range(4)] == [i == gorunen for i in range(4)]
    e.filtrele("yok-boyle-cihaz")
    assert all(e.tablo.isRowHidden(i) for i in range(4))


def test_envanter_sunucu_hatasinda_mesaj_gosterir(qt_app):
    bozuk = cevap()
    bozuk.raise_for_status.side_effect = RuntimeError("x")
    with patch.object(envanter, "oturum_kontrollu_istek", return_value=bozuk):
        e = envanter.CihazYonetimEkrani("http://x", "T")
    assert "yüklenemedi" in e.bos_mesaj.text() and not e.bos_mesaj.isHidden()


def form_ac(cihaz=None):
    odalar = [{"oda_id": 5, "oda_adi": "Lab 1", "aktif_mi": True}, {"oda_id": 6, "oda_adi": "Eski", "aktif_mi": False}]
    with patch.object(envanter, "oturum_kontrollu_istek", return_value=cevap(200, odalar)):
        if cihaz:
            return envanter.CihazIslemFormu("http://x", "T", islem_turu="GUNCELLE", cihaz_veri=cihaz)
        return envanter.CihazIslemFormu("http://x", "T")


def test_duzenleme_formu_arizali_cihazi_arizali_gosterir_ve_ezmez(qt_app):
    """Eskiden sunucudaki 'Arizali' değeri listede bulunamayıp 'Kullanılabilir'e düşüyordu."""
    f = form_ac(CIHAZLAR[1])
    assert f.cmb_durum.currentText() == "Arızalı" and f.cmb_durum.currentData() == "Arizali"
    with patch.object(envanter, "oturum_kontrollu_istek", return_value=cevap(200, {})) as istek, \
         patch.object(envanter.tmk, "bilgi"):
        f.kaydet()
    assert istek.call_args.args[:2] == ("PATCH", "http://x/api/cihazlar/2")
    assert istek.call_args.kwargs["json"]["durum"] == "Arizali"
    f.close()


def test_duzenleme_formu_oda_secili_gelir_pasif_oda_listelenmez(qt_app):
    f = form_ac(CIHAZLAR[0])
    assert f.cmb_oda.currentData() == 5
    assert [f.cmb_oda.itemData(i) for i in range(f.cmb_oda.count())] == [None, 5]
    assert f.cmb_durum.currentData() == "Kullanima_Hazir"
    f.close()


def test_yeni_cihaz_kullanima_hazir_olarak_eklenir(qt_app):
    f = form_ac()
    f.txt_envanter.setText("E-9")
    f.txt_ad.setText("Yeni")
    with patch.object(envanter, "oturum_kontrollu_istek", return_value=cevap(201, {})) as istek, \
         patch.object(envanter.tmk, "bilgi"):
        f.kaydet()
    assert istek.call_args.args[:2] == ("POST", "http://x/api/cihazlar")
    assert istek.call_args.kwargs["json"]["durum"] == "Kullanima_Hazir"
    f.close()


def test_duzenleme_listesi_satir_butonu_formu_acar(qt_app):
    with patch.object(envanter, "oturum_kontrollu_istek", return_value=cevap(200, CIHAZLAR)):
        d = envanter.CihazDuzenlemeListesi("http://x", "T")
    assert d.tablo.rowCount() == 4 and hap_metni(d.tablo, 1, 2) == "Arızalı"
    dugme = d.tablo.cellWidget(1, 3).findChild(QPushButton)
    with patch.object(envanter, "CihazIslemFormu") as form:
        form.return_value.exec.return_value = 0
        dugme.click()
    assert form.call_args.kwargs["cihaz_veri"]["cihaz_id"] == 2 and form.call_args.kwargs["islem_turu"] == "GUNCELLE"
    d.close()
