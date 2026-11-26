"""İşlem yapılmayan sayfalarda başlığın yanındaki küçük "Görüntüleme sayfası" rozeti."""
import gc
import json
import weakref
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QLabel, QMessageBox

import client.audit_kayitlari_ekrani as audit
import client.cihaz_uygunluk_ekrani as uygunluk
import client.oda_kullanimi_ekrani as oda
import client.randevu_raporlari_ekrani as randevu_raporu
import client.sistem_durumu_ekrani as sistem
import client.yetki_raporu_ekrani as yetki
from client import bilgi_rozeti
from client.bilgi_rozeti import BilgiRozeti, ROZET_METNI


def _yanit(veri=None, kod=500):
    m = MagicMock()
    m.status_code, m.text = kod, json.dumps(veri or {})
    m.json.return_value = veri or {}
    m._tkys_oturum_reddedildi = False
    return m


def _sayfa(modul, sinif, **ek):
    """Sayfayı sunucuya gitmeden açar (istekler hata döner; iletişim kutuları bastırılır)."""
    yanit = _yanit(ek.pop("veri", None), ek.pop("kod", 500))
    with patch.object(modul, "oturum_kontrollu_istek", return_value=yanit, create=True), \
            patch("requests.get", return_value=yanit), patch("client.api_yoneticisi.oturum_kontrollu_istek", return_value=yanit), \
            patch.object(QMessageBox, "warning", return_value=0), patch.object(QMessageBox, "information", return_value=0):
        return sinif("http://127.0.0.1:9", "t")


def test_rozet_metni_ve_aciklama_ve_simge(tkys_qapplication):
    r = BilgiRozeti("Görüntüleme sayfası", "Açıklama metni")
    assert r.etiket.text() == "Görüntüleme sayfası" and r.aciklama == "Açıklama metni"
    assert not r.simge.pixmap().isNull()
    assert ROZET_METNI == "Görüntüleme sayfası"


def test_rozete_tiklayinca_aciklama_balonu_acilir(tkys_qapplication):
    """Fare üzerine gelince açılan ipuçları uygulamada kapalıdır (client/ipucu_kapat.py); açıklama tıklamayla açılan balondadır."""
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    r = BilgiRozeti("Görüntüleme sayfası", "Açıklama metni")
    r.show()
    QTest.mouseClick(r, Qt.LeftButton, pos=QPoint(5, 5))
    balonlar = [b for b in tkys_qapplication.topLevelWidgets() if isinstance(b, bilgi_rozeti.BilgiBalonu) and b.isVisible()]
    assert len(balonlar) == 1 and balonlar[0].etiket.text() == "Açıklama metni"
    balonlar[0].close()


def test_kaynakta_qtooltip_kullanilmaz():
    """Qt ipucu kutusunu doğrudan göstermek yasaktır (testlerde de tarandığı gibi): rozet kendi balonunu kullanır."""
    assert "QToolTip" not in Path(bilgi_rozeti.__file__).read_text(encoding="utf-8")


@pytest.mark.parametrize("modul, sinif, ek", [
    (oda, "OdaKullanimiEkrani", {}),
    (audit, "AuditKayitlariEkrani", {}),
    (sistem, "SistemDurumuEkrani", {}),
    (yetki, "YetkiRaporuEkrani", {}),
    (uygunluk, "CihazUygunlukEkrani", {"veri": {"cihazlar": [], "engeller": [], "rezervasyonlar": [], "tarihler": []}, "kod": 200}),
])
def test_islem_yapilmayan_sayfalarda_rozet_var_ve_aciklamasi_dolu(tkys_qapplication, modul, sinif, ek):
    sayfa = _sayfa(modul, getattr(modul, sinif), **ek)
    rozetler = sayfa.findChildren(BilgiRozeti)
    assert len(rozetler) == 1, sinif
    assert rozetler[0].etiket.text() == "Görüntüleme sayfası" and len(rozetler[0].aciklama) > 40


def test_islem_yapilan_ya_da_rapor_sayfalarinda_rozet_yok(tkys_qapplication):
    sayfa = _sayfa(randevu_raporu, randevu_raporu.RandevuRaporlariEkrani)
    assert not sayfa.findChildren(BilgiRozeti)


def test_denetim_sayfasinda_salt_okunur_dili_kalmadi(tkys_qapplication):
    sayfa = _sayfa(audit, audit.AuditKayitlariEkrani)
    metinler = " ".join(e.text() for e in sayfa.findChildren(QLabel)).lower()
    assert "salt okunur" not in metinler


def test_oda_kullanimi_kutulari_tiklaninca_islemin_yapilacagi_sayfayi_soyler(tkys_qapplication):
    sayfa = _sayfa(oda, oda.OdaKullanimiEkrani)
    ortak = {"baslangic_zamani": "2026-11-26T10:00:00", "bitis_zamani": "2026-11-26T11:00:00"}
    randevu = sayfa._blok({**ortak, "durum": "PLANLANDI", "psikolog": "Ayşe", "danisan_kod_id": "D1"})
    cihaz = sayfa._blok({**ortak, "cihaz": True, "cihaz_adi": "EEG"})
    etkinlik = sayfa._blok({**ortak, "etkinlik": True, "etkinlik_adi": "Deney"})
    assert "Randevu Yönetimi" in randevu.aciklama
    assert "Cihaz Rezervasyonu" in cihaz.aciklama
    assert "Oda Etkinlikleri" in etkinlik.aciklama
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    randevu.show()
    QTest.mouseClick(randevu, Qt.LeftButton, pos=QPoint(5, 5))
    balonlar = [b for b in tkys_qapplication.topLevelWidgets() if isinstance(b, bilgi_rozeti.BilgiBalonu) and b.isVisible()]
    assert balonlar and "Randevu Yönetimi" in balonlar[-1].etiket.text()
    for b in balonlar:
        b.close()


def test_sayfa_basligi_rozeti_yalnizca_verilince_koyar(tkys_qapplication):
    from PySide6.QtWidgets import QLineEdit, QPushButton
    from client.tablo_tasarimi import sayfa_basligi
    bos = sayfa_basligi("Başlık", "Alt", QLineEdit(), QPushButton("Yenile"), [])
    var = sayfa_basligi("Başlık", "Alt", QLineEdit(), QPushButton("Yenile"), [], rozet=BilgiRozeti("Görüntüleme sayfası", "x"))
    assert not bos.findChildren(BilgiRozeti) and len(var.findChildren(BilgiRozeti)) == 1


def test_rozet_sinyallerinde_lambda_yok_ve_sayfa_bellekten_serbest_kalir(tkys_qapplication):
    assert "lambda" not in Path(bilgi_rozeti.__file__).read_text(encoding="utf-8")
    sayfa = _sayfa(oda, oda.OdaKullanimiEkrani)
    referans = weakref.ref(sayfa)
    del sayfa
    gc.collect()
    assert referans() is None
