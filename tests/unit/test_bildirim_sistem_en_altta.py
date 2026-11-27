"""Zil paneli: "Sistem uyarıları" grubu, hangi sırayla gelirse gelsin en altta durur."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QLabel

from client.bildirim_paneli import BildirimPaneli


def _baslik_sirasi(panel):
    basliklar = {"CİHAZ UYARILARI", "RANDEVU SONUÇLARI", "SİSTEM UYARILARI", "DANIŞMA MASASI ONAYLARI"}
    etiketler = [e for e in panel.findChildren(QLabel) if e.text() in basliklar]
    etiketler.sort(key=lambda e: e.mapTo(panel, e.rect().topLeft()).y())
    return [e.text() for e in etiketler]


def test_sistem_uyarilari_ortadayken_bile_en_alta_iner(tkys_qapplication):
    satirlar = [
        ("Cihaz Uyarıları", "1 açık arıza kaydı çözüm bekliyor.", "Arıza Kayıtları"),
        ("Randevu Sonuçları", "10 randevunun sonucu girilmedi", "Randevu Yönetimi"),
        ("Sistem", "Son yedek 12 gün önce alındı", "Sistem Durumu"),
        ("Danışma Masası", "6 görev onay bekliyor", "Danışma Masası Yönetimi"),
    ]
    panel = BildirimPaneli(satirlar, 4, False, lambda hedef: None)
    panel.show()
    sira = _baslik_sirasi(panel)
    assert sira[-1] == "SİSTEM UYARILARI" and sira[:-1] == ["CİHAZ UYARILARI", "RANDEVU SONUÇLARI", "DANIŞMA MASASI ONAYLARI"]


def test_sistem_yoksa_diger_gruplarin_sirasi_degismez(tkys_qapplication):
    satirlar = [("Randevu Sonuçları", "2 randevunun sonucu girilmedi", "Randevu Yönetimi"),
                ("Cihaz Uyarıları", "1 açık arıza kaydı çözüm bekliyor.", "Arıza Kayıtları")]
    panel = BildirimPaneli(satirlar, 2, False, lambda hedef: None)
    panel.show()
    assert _baslik_sirasi(panel) == ["RANDEVU SONUÇLARI", "CİHAZ UYARILARI"]
