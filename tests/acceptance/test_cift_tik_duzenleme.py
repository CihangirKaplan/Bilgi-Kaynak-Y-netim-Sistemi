"""Cihaz yaşam döngüsü ekranlarında satıra çift tıklayınca düzenleme (ya da ayrıntı) açılır; düzenleme penceresinin altında
silme düğmesi bulunur: bakım, kalibrasyon ve plan silinebilir; cihaz silinmez ("kullanım dışına al"); rezervasyon iptal edilir.

Qt nesneleri her testte kapatılıp silinir (CI'da çıkışta oluşan aralıklı Qt çökmesine karşı)."""
import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication, QDialog, QPushButton, QTableWidgetItem

import client.bakim_plani_ekranlari as plan_modul
import client.cihaz_ariza_ekranlari as ariza
import client.cihaz_bakim_ekranlari as bakim
import client.cihaz_ekranlari as envanter
import client.cihaz_kalibrasyon_ekranlari as kalib
import client.cihaz_rezervasyon_ekranlari as rez_modul
from client.tablo_tasarimi import cift_tikla_ac, satir_kimligi, satira_kimlik_ata, tablo_olustur, tehlike_dugmesi


def gun(n):
    return (datetime.date.today() + datetime.timedelta(days=n)).isoformat()


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def temizle(qt_app):
    nesneler = []
    yield nesneler.append
    for n in nesneler:
        n.close()
        n.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def yanit(durum=200, veri=None):
    return SimpleNamespace(status_code=durum, json=lambda: veri, raise_for_status=lambda: None)


def cift_tikla(ekran, satir, sutun=1):
    ekran.tablo.cellDoubleClicked.emit(satir, sutun)


# ------------------------------------------------------------------- ortak yardımcılar
def test_satir_kimligi_atanir_okunur_ve_atanmamis_satir_yok_sayilir(temizle):
    tablo = tablo_olustur(["A", "B"])
    temizle(tablo)
    tablo.setRowCount(2)
    tablo.setItem(0, 0, QTableWidgetItem("x"))
    satira_kimlik_ata(tablo, 0, 41)
    satira_kimlik_ata(tablo, 1, 42)                                   # ilk sütunda öğe yoksa kendisi oluşturulur
    assert (satir_kimligi(tablo, 0), satir_kimligi(tablo, 1)) == (41, 42)
    acilanlar = []
    cift_tikla_ac(tablo, acilanlar.append)
    tablo.cellDoubleClicked.emit(1, 0)
    tablo.setRowCount(3)
    tablo.cellDoubleClicked.emit(2, 0)                                # kimliği olmayan satır
    assert acilanlar == [42]


def test_tehlike_dugmesi_kirmizi_ve_tiklaninca_calisir(temizle):
    cagri = []
    d = tehlike_dugmesi("Sil", lambda: cagri.append(1))
    temizle(d)
    assert d.objectName() == "tehlike" and "#B91C1C" in d.styleSheet()
    d.click()
    assert cagri == [1]


# ------------------------------------------------------------------- bakım
BAKIM = [{"bakim_id": 7, "cihaz_adi": "EEG", "bakim_yapan_kisi": "k", "yapilan_islem": "i", "maliyet": 0,
          "bakim_baslangic_tarihi": gun(-30), "bakim_bitis_tarihi": gun(-30), "sonraki_bakim_tarihi": gun(30), "uyari_suresi_gun": 7},
         {"bakim_id": 9, "cihaz_adi": "EKG", "bakim_yapan_kisi": "k", "yapilan_islem": "i", "maliyet": 0,
          "bakim_baslangic_tarihi": gun(-20), "bakim_bitis_tarihi": gun(-20), "sonraki_bakim_tarihi": gun(60), "uyari_suresi_gun": 7}]


def bakim_ekrani(temizle):
    with patch.object(bakim, "oturum_kontrollu_istek", return_value=yanit(200, BAKIM)):
        e = bakim.BakimYonetimEkrani("http://x", "T")
    temizle(e)
    return e


def test_bakim_satirina_cift_tiklayinca_duzenleme_acilir_ve_sil_dugmesi_baglidir(temizle):
    e = bakim_ekrani(temizle)
    with patch.object(bakim, "BakimDuzenleFormu") as form:
        form.return_value.exec.return_value = 0
        cift_tikla(e, 1)
    assert form.call_args.args[2]["bakim_id"] == 9 and callable(form.call_args.kwargs["sil_fn"])


def test_bakim_duzenleme_penceresinde_alt_kisimda_sil_dugmesi_vardir_ve_silinince_kapanir(temizle):
    kayit = dict(BAKIM[0])
    silinen = []
    f = bakim.BakimDuzenleFormu("http://x", "T", kayit, None, sil_fn=lambda: silinen.append(1) or True)
    temizle(f)
    assert f.btn_sil is not None and f.btn_sil.text() == "Bu bakım kaydını sil"
    f.btn_sil.click()
    assert silinen == [1] and f.result() == QDialog.Accepted
    yok = bakim.BakimDuzenleFormu("http://x", "T", kayit, None)                     # silme istenmezse düğme yok
    temizle(yok)
    assert yok.btn_sil is None


def test_bakim_silme_vazgecilirse_pencere_acik_kalir(temizle):
    f = bakim.BakimDuzenleFormu("http://x", "T", dict(BAKIM[0]), None, sil_fn=lambda: False)
    temizle(f)
    f.btn_sil.click()
    assert f.result() != QDialog.Accepted


def test_bakim_sil_onay_ve_sonuca_gore_true_false_doner(temizle):
    e = bakim_ekrani(temizle)
    with patch.object(bakim, "sil_onayi", return_value=False), patch.object(bakim, "oturum_kontrollu_istek") as istek:
        assert e.bakim_sil(7) is False
    istek.assert_not_called()
    with patch.object(bakim, "sil_onayi", return_value=True), \
         patch.object(bakim, "oturum_kontrollu_istek", side_effect=lambda y, u, **k: yanit(200, BAKIM if y == "GET" else {})) as istek:
        assert e.bakim_sil(7) is True
    assert istek.call_args_list[0].args[:2] == ("DELETE", "http://x/api/bakimlar/7")
    with patch.object(bakim, "sil_onayi", return_value=True), patch.object(bakim.QMessageBox, "warning") as uyari, \
         patch.object(bakim, "oturum_kontrollu_istek", return_value=yanit(409, {"detail": "Bağlı kayıt var."})):
        assert e.bakim_sil(7) is False
    assert "Bağlı kayıt" in uyari.call_args.args[2]


# ------------------------------------------------------------------- kalibrasyon
KALIB = [{"kalibrasyon_id": 3, "cihaz_adi": "EEG", "kalibrasyon_yapan_kurum": "k", "sertifika_no": "s",
          "kalibrasyon_baslangic_tarihi": gun(-300), "kalibrasyon_bitis_tarihi": gun(-300), "gecerlilik_tarihi": gun(20),
          "uyari_suresi_gun": 30}]


def kalib_ekrani(temizle):
    with patch.object(kalib, "oturum_kontrollu_istek", return_value=yanit(200, KALIB)):
        e = kalib.KalibrasyonYonetimEkrani("http://x", "T")
    temizle(e)
    return e


def test_kalibrasyon_satirina_cift_tiklayinca_duzenleme_acilir(temizle):
    e = kalib_ekrani(temizle)
    with patch.object(kalib, "KalibrasyonDuzenleFormu") as form:
        form.return_value.exec.return_value = 0
        cift_tikla(e, 0)
    assert form.call_args.args[2]["kalibrasyon_id"] == 3 and callable(form.call_args.kwargs["sil_fn"])


def test_kalibrasyon_duzenleme_penceresinde_sil_dugmesi(temizle):
    f = kalib.KalibrasyonDuzenleFormu("http://x", "T", dict(KALIB[0]), None, sil_fn=lambda: True)
    temizle(f)
    assert f.btn_sil.text() == "Bu kalibrasyon kaydını sil"
    f.btn_sil.click()
    assert f.result() == QDialog.Accepted
    yok = kalib.KalibrasyonDuzenleFormu("http://x", "T", dict(KALIB[0]), None)
    temizle(yok)
    assert yok.btn_sil is None


def test_kalibrasyon_sil_sonuca_gore_true_false_doner(temizle):
    e = kalib_ekrani(temizle)
    with patch.object(kalib, "sil_onayi", return_value=False):
        assert e.sil(3) is False
    with patch.object(kalib, "sil_onayi", return_value=True), \
         patch.object(kalib, "oturum_kontrollu_istek", side_effect=lambda y, u, **k: yanit(200, KALIB if y == "GET" else {})):
        assert e.sil(3) is True


# ------------------------------------------------------------------- plan
PLAN = {"plan_id": 5, "cihaz_id": 1, "envanter_kodu": "CHZ-001", "cihaz_adi": "EEG Cihazı", "gorev_turu": "Yıllık bakım",
        "periyot_gun": 365, "uyari_suresi_gun": 30, "sonraki_gorev_tarihi": "2026-11-20", "kalan_gun": 16, "aktif_mi": True,
        "durum": "Yaklaşıyor"}


def plan_sunucu(yontem, url, **kw):
    return yanit(200, [PLAN] if "bakim-planlari" in url else [{"cihaz_id": 1, "envanter_kodu": "CHZ-001", "cihaz_adi": "EEG Cihazı"}])


def plan_ekrani(temizle):
    with patch.object(plan_modul, "oturum_kontrollu_istek", side_effect=plan_sunucu):
        e = plan_modul.BakimPlanlariEkrani("http://x", "T")
    temizle(e)
    return e


def test_plan_satirina_cift_tiklayinca_duzenleme_acilir(temizle):
    e = plan_ekrani(temizle)
    with patch.object(plan_modul, "PlanFormu") as form:
        form.return_value.exec.return_value = 0
        cift_tikla(e, 0)
    assert form.call_args.args[2]["plan_id"] == 5 and callable(form.call_args.kwargs["sil_fn"])


def test_plan_duzenleme_penceresinde_sil_dugmesi_yeni_planda_yok(temizle):
    with patch.object(plan_modul, "oturum_kontrollu_istek", side_effect=plan_sunucu):
        duzenle = plan_modul.PlanFormu("http://x", "T", dict(PLAN), None, sil_fn=lambda: True)
        yeni = plan_modul.PlanFormu("http://x", "T", None, None, sil_fn=lambda: True)
    temizle(duzenle)
    temizle(yeni)
    assert duzenle.btn_sil.text() == "Bu planı sil" and yeni.btn_sil is None         # yeni planda silinecek kayıt yok
    duzenle.btn_sil.click()
    assert duzenle.result() == QDialog.Accepted


def test_plan_sil_sonuca_gore_true_false_doner(temizle):
    e = plan_ekrani(temizle)
    with patch.object(plan_modul, "sil_onayi", return_value=False):
        assert e.plan_sil(5) is False
    with patch.object(plan_modul, "sil_onayi", return_value=True), \
         patch.object(plan_modul, "oturum_kontrollu_istek", side_effect=lambda y, u, **k: yanit(200, [PLAN] if y == "GET" else {})):
        assert e.plan_sil(5) is True


# ------------------------------------------------------------------- arıza
ARIZALAR = [
    {"ariza_id": 1, "cihaz_adi": "EEG", "ariza_baslik": "Kablo", "ariza_aciklama": "x", "aciliyet": "Orta", "durum": "Açık",
     "bildirim_tarihi": "2026-11-01T10:00:00"},
    {"ariza_id": 2, "cihaz_adi": "EKG", "ariza_baslik": "Ekran", "ariza_aciklama": "y", "aciliyet": "Yüksek", "durum": "Çözüldü",
     "bildirim_tarihi": "2026-11-02T10:00:00"},
]


def ariza_ekrani(temizle, yetkili):
    with patch.object(ariza, "oturum_kontrollu_istek", return_value=yanit(200, ARIZALAR)):
        e = ariza.ArizaYonetimEkrani("http://x", "T", yetkili_mi=yetkili)
    temizle(e)
    return e


def test_acik_arizaya_cift_tiklayinca_duzenleme_acilir_cozulen_ve_yetkisiz_acilmaz(temizle):
    e = ariza_ekrani(temizle, True)
    with patch.object(ariza, "ArizaDuzenleFormu") as form:
        form.return_value.exec.return_value = 0
        cift_tikla(e, 0)
        assert form.call_args.args[2]["ariza_id"] == 1
        form.reset_mock()
        cift_tikla(e, 1)                                              # çözülmüş kayıtta düzenleme simgesi yok, çift tık da yok
        form.assert_not_called()
    yetkisiz = ariza_ekrani(temizle, False)
    with patch.object(ariza, "ArizaDuzenleFormu") as form:
        cift_tikla(yetkisiz, 0)
        form.assert_not_called()


def test_ariza_duzenleme_penceresinde_silme_dugmesi_yok(temizle):
    f = ariza.ArizaDuzenleFormu("http://x", "T", dict(ARIZALAR[0]))
    temizle(f)
    assert not [b for b in f.findChildren(QPushButton) if "sil" in b.text().lower()]


# ------------------------------------------------------------------- cihaz envanteri
CIHAZLAR = [{"cihaz_id": 4, "envanter_kodu": "E-4", "cihaz_adi": "Monitör", "marka_model": "M", "seri_no": "S", "durum": "Kullanima_Hazir"},
            {"cihaz_id": 5, "envanter_kodu": "E-5", "cihaz_adi": "Eski", "marka_model": "M", "seri_no": "S5", "durum": "Kullanim_Disi"}]


def envanter_ekrani(temizle, yetkili=True):
    with patch.object(envanter, "oturum_kontrollu_istek", return_value=yanit(200, CIHAZLAR)):
        e = envanter.CihazYonetimEkrani("http://x", "T", yetkili_mi=yetkili)
    temizle(e)
    return e


def test_cihaz_satirina_cift_tiklayinca_guncelleme_formu_acilir_yetkisiz_acmaz(temizle):
    e = envanter_ekrani(temizle)
    with patch.object(envanter, "CihazIslemFormu") as form:
        form.return_value.exec.return_value = 0
        cift_tikla(e, 1, 2)
    assert form.call_args.kwargs["islem_turu"] == "GUNCELLE" and form.call_args.kwargs["cihaz_veri"]["cihaz_id"] == 5
    yetkisiz = envanter_ekrani(temizle, yetkili=False)
    with patch.object(envanter, "CihazIslemFormu") as form:
        cift_tikla(yetkisiz, 0)
        form.assert_not_called()


def form_ac(temizle, cihaz, **kw):
    f = envanter.CihazIslemFormu("http://x", "T", **kw, cihaz_veri=cihaz) if kw else envanter.CihazIslemFormu("http://x", "T")
    temizle(f)
    return f


def test_cihaz_formunda_kullanim_disi_dugmesi_yalniz_guncellemede_ve_zaten_disindaysa_yok(temizle):
    assert form_ac(temizle, None).btn_kullanim_disi is None                              # yeni cihaz
    guncel = form_ac(temizle, dict(CIHAZLAR[0]), islem_turu="GUNCELLE")
    assert guncel.btn_kullanim_disi.text() == "Cihazı kullanım dışına al"
    assert form_ac(temizle, dict(CIHAZLAR[1]), islem_turu="GUNCELLE").btn_kullanim_disi is None
    assert not [b for b in guncel.findChildren(QPushButton) if b.text().strip().lower() in ("sil", "cihazı sil")]   # cihaz silinmez


def test_kullanim_disi_onaylanirsa_durum_patch_ile_gonderilir_vazgecilirse_gonderilmez(temizle):
    f = form_ac(temizle, dict(CIHAZLAR[0]), islem_turu="GUNCELLE")
    with patch.object(f, "_kullanim_disi_onayi", return_value=False), patch.object(envanter, "oturum_kontrollu_istek") as istek:
        f.btn_kullanim_disi.click()
    istek.assert_not_called()
    with patch.object(f, "_kullanim_disi_onayi", return_value=True), patch.object(envanter.QMessageBox, "information"), \
         patch.object(envanter, "oturum_kontrollu_istek", return_value=yanit(200, {})) as istek:
        f.btn_kullanim_disi.click()
    assert istek.call_args.args[:2] == ("PATCH", "http://x/api/cihazlar/4")
    assert istek.call_args.kwargs["json"] == {"durum": "Kullanim_Disi"} and f.result() == QDialog.Accepted


def test_kullanim_disi_sunucu_hatasinda_pencere_acik_kalir_ve_mesaj_gosterilir(temizle):
    f = form_ac(temizle, dict(CIHAZLAR[0]), islem_turu="GUNCELLE")
    with patch.object(f, "_kullanim_disi_onayi", return_value=True), patch.object(envanter.QMessageBox, "critical") as hata, \
         patch.object(envanter, "oturum_kontrollu_istek", return_value=yanit(409, {"detail": "Açık rezervasyon var."})):
        f.btn_kullanim_disi.click()
    assert "Açık rezervasyon" in hata.call_args.args[2] and f.result() != QDialog.Accepted


# ------------------------------------------------------------------- rezervasyon
REZERVASYONLAR = [
    {"rezervasyon_id": 11, "cihaz_id": "E-1 - EEG", "envanter_kodu": "E-1", "cihaz_adi": "EEG", "oda_adi": "Oda-1", "bolum_adi": "Psikoloji",
     "proje_turu": "Araştırma", "proje_adi_aciklamasi": "Pilot", "baslangic_zamani": "2026-11-20T10:00:00",
     "bitis_zamani": "2026-11-20T12:00:00", "durum": "Aktif"},
    {"rezervasyon_id": 12, "cihaz_id": "E-2 - EKG", "envanter_kodu": "E-2", "cihaz_adi": "EKG", "oda_adi": None, "bolum_adi": None,
     "proje_turu": None, "proje_adi_aciklamasi": None, "baslangic_zamani": "2026-10-05T09:00:00",
     "bitis_zamani": "2026-10-05T10:00:00", "durum": "Tamamlandı"},
]


def rez_ekrani(temizle, yetkili=True):
    with patch.object(rez_modul, "oturum_kontrollu_istek", return_value=yanit(200, REZERVASYONLAR)):
        e = rez_modul.RezervasyonYonetimEkrani("http://x", "T", yetkili_mi=yetkili)
    temizle(e)
    return e


def test_rezervasyon_satirina_cift_tiklayinca_ayrinti_acilir_aktifte_iptal_secenegiyle(temizle):
    e = rez_ekrani(temizle)
    with patch.object(rez_modul, "RezervasyonDetayPenceresi") as pencere:
        pencere.return_value.exec.return_value = 0
        cift_tikla(e, 0)
        assert pencere.call_args.args[0]["rezervasyon_id"] == 11 and callable(pencere.call_args.args[1])
        cift_tikla(e, 1)
        assert pencere.call_args.args[0]["rezervasyon_id"] == 12 and pencere.call_args.args[1] is None   # tamamlanmış: iptal yok
    yetkisiz = rez_ekrani(temizle, yetkili=False)
    with patch.object(rez_modul, "RezervasyonDetayPenceresi") as pencere:
        pencere.return_value.exec.return_value = 0
        cift_tikla(yetkisiz, 0)
        assert pencere.call_args.args[1] is None                                                       # yetkisiz: yalnız görüntüler


def test_rezervasyon_ayrinti_penceresi_bilgileri_gosterir_ve_alttaki_dugme_iptal_akisini_baslatir(temizle):
    cagri = []
    p = rez_modul.RezervasyonDetayPenceresi(dict(REZERVASYONLAR[0]), lambda: cagri.append("iptal"))
    temizle(p)
    assert p.degerler["Bölüm"] == "Psikoloji" and p.degerler["Oda"] == "Oda-1" and p.degerler["Proje türü"] == "Araştırma"
    assert p.degerler["Tarih ve saat"] == "20.11.2026  10:00 – 12:00" and p.lbl_durum.text() == "Aktif"
    assert p.btn_iptal.text() == "Rezervasyonu iptal et"
    p.btn_iptal.click()
    assert cagri == ["iptal"] and p.result() == QDialog.Accepted
    bos = rez_modul.RezervasyonDetayPenceresi(dict(REZERVASYONLAR[1]), None)
    temizle(bos)
    assert bos.btn_iptal is None and bos.degerler["Oda"] == "—" and bos.degerler["Açıklama"] == "—"
