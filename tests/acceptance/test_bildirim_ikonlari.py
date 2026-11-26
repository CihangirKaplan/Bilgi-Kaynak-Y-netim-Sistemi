"""Bildirimlerde emoji yok: küçük, kutusuz çizgi ikonlar kullanılır (ana panel kutusu, bildirim paneli, zil metinleri)."""
import re
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from client import bildirim_ikonlari as bi
from client.bildirim_paneli import BildirimPaneli
from client.dashboard_ekrani import DashboardEkrani

EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿⭐️]")
KOK = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def _tum_yazilar(kapsayici):
    return [w.text() for tur in (QLabel, QPushButton) for w in kapsayici.findChildren(tur)]


def _kaynak(dosya, baslangic, bitis):
    metin = (KOK / dosya).read_text(encoding="utf-8")
    return metin[metin.index(baslangic):metin.index(bitis, metin.index(baslangic))]


def test_uretici_kodlarda_bildirim_metinlerine_emoji_konmaz():
    parcalar = [
        _kaynak("client/main_window.py", "    def _bildirimleri_yenile(self):", "    def _parola_talepleri_gorebilir_mi"),
        _kaynak("client/dashboard_ekrani.py", "    def _bildirim_satirlari(self):", "    def _bildirim_tiklandi"),
        _kaynak("client/dashboard_ekrani.py", "    def _bildirimleri_olustur(self):", "        satir_kutusu = QWidget()"),
        (KOK / "client/bildirim_paneli.py").read_text(encoding="utf-8"),
    ]
    for parca in parcalar:
        # Eski emoji öneklerini tanıyan sözlük (bildirim_ikonlari) bu denetimin dışındadır; üreticiler emoji yazmaz.
        assert EMOJI.findall(parca) == []


def test_bildirim_paneli_emojisiz_cizilir_ve_her_satirin_ikonu_vardir(qt_app):
    bildirimler = [
        ("Parola Talepleri", "memur parola sıfırlama istedi (az önce)", "Kullanıcı & Personel"),
        ("Cihaz Uyarıları", "3 açık arıza kaydı çözüm bekliyor.", "Arıza Kayıtları"),
        ("Cihaz Uyarıları", "E2 - EEG — Bakım (24 gün gecikti)", "Bakım Kayıtları"),
        ("Cihaz Uyarıları", "E1 - EKG — Kalibrasyon (2 gün kaldı)", "Kalibrasyon"),
        ("Günlük", "Randevunuz: bugün 2", "Ana Kontrol Paneli"),
        ("Günlük", "Cihaz rezervasyonunuz: yarın 1", "Ana Kontrol Paneli"),
        ("Duyurular", "Bakım duyurusu", "Ana Kontrol Paneli"),
        ("Danışma Masası", "4 görev onay bekliyor", "Danışma Masası Yönetimi"),
    ]
    panel = BildirimPaneli(bildirimler, 8, True, lambda _h: None)
    assert EMOJI.findall(" ".join(_tum_yazilar(panel))) == []
    satirlar = [b for b in panel.findChildren(QPushButton) if b.objectName() == "bildirimSatiri"]
    assert len(satirlar) == len(bildirimler)
    assert all(not b.icon().isNull() for b in satirlar)
    # Başlıklar (bildirim zili ve grup başlıkları) çizgi ikon taşır: yazının yanında resim etiketi vardır.
    resimli = [l for l in panel.findChildren(QLabel) if l.pixmap() is not None and not l.pixmap().isNull()]
    assert len(resimli) >= 1 + 4 + 1          # zil + 4 grup başlığı + yüklenemedi uyarısı
    panel.deleteLater()


def test_bos_bildirim_paneli_tik_ikonuyla_gosterilir(qt_app):
    panel = BildirimPaneli([], 0, False, lambda _h: None)
    yazilar = _tum_yazilar(panel)
    assert any("Bekleyen bildirim yok." in y for y in yazilar) and EMOJI.findall(" ".join(yazilar)) == []
    panel.deleteLater()


def test_eski_emojili_metinler_ayiklanir_ve_ikona_cevrilir(qt_app):
    assert bi.bildirim_ikonu("Günlük", "📅 Randevunuz: bugün 2") == ("Randevunuz: bugün 2", "calendar", bi.MAVI)
    assert bi.bildirim_ikonu("Cihaz Uyarıları", "🔴 E2 — Bakım (3 gün gecikti)")[1:] == ("warning", bi.KIRMIZI)
    assert bi.bildirim_ikonu("Parola Talepleri", "🔐 ali parola sıfırlama istedi")[1] == "key"
    panel = BildirimPaneli([("Danışma Masası", "📋 Ayşe — Görev onayı bekliyor", "Danışma Masası Yönetimi"),
                            ("Danışma Masası", "📋 Ayşe — Görev onayı bekliyor", "Danışma Masası Yönetimi")],
                           2, False, lambda _h: None)
    yazilar = [b.text() for b in panel.findChildren(QPushButton) if b.objectName() == "bildirimSatiri"]
    assert yazilar == ["Ayşe — 2 görev onay bekliyor   →"]
    panel.deleteLater()


def test_ikon_secimi_gruptan_ve_icerikten_yapilir():
    assert bi.bildirim_ikonu("Cihaz Uyarıları", "2 açık arıza kaydı")[1:] == ("warning", bi.KIRMIZI)
    assert bi.bildirim_ikonu("Cihaz Uyarıları", "E2 — Bakım (24 gün gecikti)")[1:] == ("warning", bi.KIRMIZI)
    assert bi.bildirim_ikonu("Cihaz Uyarıları", "E1 — Kalibrasyon (2 gün kaldı)")[1] == "wrench"
    assert bi.bildirim_ikonu("Günlük", "Cihaz rezervasyonunuz: yarın 1")[1] == "chip"
    assert bi.bildirim_ikonu("Günlük", "Randevunuz: bugün 1")[1] == "calendar"
    assert bi.bildirim_ikonu("Duyurular", "Duyuru")[1] == "megaphone"
    assert bi.bildirim_ikonu("Danışma Masası", "3 görev onay bekliyor")[1] == "clipboard"


def test_kullanilan_tum_ikonlar_kayit_defterinde_vardir():
    from client.tkys_sidebar_refined import PATHS
    adlar = {i for _, i, _ in bi.GRUP_BASLIKLARI.values()} | {bi.VARSAYILAN_GRUP[1], "bell", "circle-check", "warning", "chip", "calendar"}
    assert adlar <= set(PATHS)


def test_ana_panel_bildirim_kutusu_emojisiz_ve_ikonludur(qt_app):
    from unittest.mock import patch
    islemler = [{"cihaz_adi": "E2 - EEG", "islem_turu": "Bakım", "kalan_gun": -24, "tarih": "16.10.2026"},
                {"cihaz_adi": "E1 - EKG", "islem_turu": "Kalibrasyon", "kalan_gun": 9, "tarih": "05.12.2026"}]
    with patch.object(DashboardEkrani, "_getir",
                      side_effect=lambda yol: {"/api/dashboard/ozet": {"acik_ariza_sayisi": 2}}.get(yol, [])):
        pano = DashboardEkrani("http://x", "T", cihaz_ozeti=True)
    pano.zamanlayici.stop()
    pano.islemler = islemler
    pano.ozet = {"acik_ariza_sayisi": 2}
    pano._bildirimleri_olustur()
    dugmeler = pano.bildirim_paneli.findChildren(QPushButton)
    assert len(dugmeler) == 3 and all(not d.icon().isNull() for d in dugmeler)
    assert EMOJI.findall(" ".join(_tum_yazilar(pano.bildirim_paneli))) == []
    assert any("Bildirimler" in y for y in _tum_yazilar(pano.bildirim_paneli))
    pano.close()
    pano.deleteLater()

    pano = DashboardEkrani.__new__(DashboardEkrani)       # boş durum (yetkili sayfa yok) da emojisiz
    with patch.object(DashboardEkrani, "_getir", side_effect=lambda yol: {} if "ozet" in yol else []):
        pano = DashboardEkrani("http://x", "T", cihaz_ozeti=True)
    pano.zamanlayici.stop()
    pano.islemler, pano.ozet = [], {"acik_ariza_sayisi": 0}
    pano._bildirimleri_olustur()
    assert EMOJI.findall(" ".join(_tum_yazilar(pano.bildirim_paneli))) == []
    assert any("Bekleyen uyarı yok" in y for y in _tum_yazilar(pano.bildirim_paneli))
    pano.close()
    pano.deleteLater()
