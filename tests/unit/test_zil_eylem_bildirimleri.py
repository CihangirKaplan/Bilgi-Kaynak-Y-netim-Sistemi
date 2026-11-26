"""Zil: süresi dolan öğrenci kayıtları, sonucu girilmemiş randevular, eski yedek (yetkiye göre, hafif sayı uçlarından)."""
import os
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

import client.main_window as mw
from client.bildirim_ikonlari import GRUP_BASLIKLARI, bildirim_ikonu


def _pencere(izinli_sayfalar=("Öğrenciler", "Randevu Yönetimi", "Sistem Durumu"), randevu_duzenleme=True):
    p = SimpleNamespace(aktif_rol="admin")
    p._sayfa_izinli_mi = lambda ad: ad in izinli_sayfalar
    p._yedek_yasi_metni = mw.AnaPencere._yedek_yasi_metni
    p.randevu_duzenleme = randevu_duzenleme
    return p


def _calistir(p, cevaplar):
    cagrilar = []

    def getir(yol):
        cagrilar.append(yol)
        return cevaplar.get(yol)

    with patch.object(mw, "izin_var", side_effect=lambda rol, izin: p.randevu_duzenleme if izin == "Randevu düzenleme" else True):
        return mw.AnaPencere._eylem_bildirimleri(p, getir), cagrilar


TAM = {
    "/api/bildirim/ogrenci-saklama": {"bekleyen": 3, "ertelenen": 1},
    "/api/bildirim/sonucu-girilmemis-randevu": {"sayi": 4},
    "/api/bildirim/yedek": {"var": True, "eski": True, "gecen_saat": 60.0},
}


def test_uc_bildirim_dogru_grup_metin_ve_hedefle_gelir():
    satirlar, _ = _calistir(_pencere(), TAM)
    assert [(g, h) for g, _, h in satirlar] == [
        ("Öğrenci Kayıtları", "Öğrenciler"), ("Randevu Sonuçları", "Randevu Yönetimi"), ("Sistem", "Sistem Durumu")]
    metinler = [m for _, m, _ in satirlar]
    assert metinler == ["3 gönüllü öğrencinin saklama süresi doldu", "4 randevunun sonucu girilmedi", "Son yedek 2 gün önce alındı"]
    assert all(len(m) <= 45 for m in metinler)                      # zil satırı tek satırdır: uzun metin kesilir


def test_yetkisiz_kullanici_hic_sorgu_yapmaz_ve_bildirim_gormez():
    satirlar, cagrilar = _calistir(_pencere(izinli_sayfalar=()), TAM)
    assert satirlar == [] and cagrilar == []


def test_randevu_bildirimi_duzenleme_izni_ister():
    satirlar, cagrilar = _calistir(_pencere(izinli_sayfalar=("Randevu Yönetimi",), randevu_duzenleme=False), TAM)
    assert satirlar == [] and cagrilar == []                                             # takvimi görür ama sonuç giremez: bildirim yok
    satirlar, _ = _calistir(_pencere(izinli_sayfalar=("Randevu Yönetimi",)), TAM)
    assert [g for g, _, _ in satirlar] == ["Randevu Sonuçları"]


@pytest.mark.parametrize("cevaplar", [
    {},                                                                                  # eski sunucu / yetki yok: uçlar None döner
    {"/api/bildirim/ogrenci-saklama": {"bekleyen": 0, "ertelenen": 5},
     "/api/bildirim/sonucu-girilmemis-randevu": {"sayi": 0},
     "/api/bildirim/yedek": {"var": True, "eski": False, "gecen_saat": 3.0}},            # sorun yok / yalnızca ertelenmiş: bildirim çıkmaz
])
def test_sayilar_sifirsa_ya_da_uc_yoksa_bildirim_cikmaz(cevaplar):
    satirlar, _ = _calistir(_pencere(), cevaplar)
    assert satirlar == []


def test_hic_yedek_yoksa_ayri_ve_net_uyari():
    satirlar, _ = _calistir(_pencere(izinli_sayfalar=("Sistem Durumu",)), {"/api/bildirim/yedek": {"var": False, "eski": True}})
    assert satirlar == [("Sistem", "Hiç yedek bulunamadı", "Sistem Durumu")]


@pytest.mark.parametrize("saat, metin", [(0, "0 saat"), (5.4, "5 saat"), (47.9, "47 saat"), (60, "2 gün"), (170, "7 gün"), (None, "0 saat")])
def test_yedek_yasi_metni(saat, metin):
    assert mw.AnaPencere._yedek_yasi_metni(saat) == metin


def test_yeni_gruplarin_basligi_ve_ikonu_var():
    for grup in ("Öğrenci Kayıtları", "Randevu Sonuçları", "Sistem"):
        baslik, ikon, renk = GRUP_BASLIKLARI[grup]
        assert baslik == baslik.upper() and ikon and renk
    _, ikon, _ = bildirim_ikonu("Sistem", "Son yedek 2 gün önce alındı")
    assert ikon == "shield"


def test_zil_her_yenilemede_eylem_bildirimlerini_toplar():
    import inspect
    kaynak = inspect.getsource(mw.AnaPencere._bildirimleri_yenile)
    assert "_eylem_bildirimleri(getir)" in kaynak


def test_panel_yeni_gruplari_cizer(tkys_qapplication):
    from client.bildirim_paneli import BildirimPaneli
    satirlar = [("Öğrenci Kayıtları", "3 gönüllü öğrencinin saklama süresi doldu", "Öğrenciler"),
                ("Randevu Sonuçları", "4 randevunun sonucu girilmedi", "Randevu Yönetimi"),
                ("Sistem", "Son yedek 2 gün önce alındı", "Sistem Durumu")]
    panel = BildirimPaneli(satirlar, 3, False, lambda hedef: None)
    from PySide6.QtWidgets import QLabel
    metinler = " ".join(e.text() for e in panel.findChildren(QLabel))
    assert "ÖĞRENCİ KAYITLARI" in metinler and "RANDEVU SONUÇLARI" in metinler and "SİSTEM UYARILARI" in metinler


# ------------------------------------------------------------------ sunucu uçları
def test_uclar_kayitli_ve_oturumsuz_erisime_kapali():
    os.environ.setdefault("JWT_SECRET", "k" * 64)
    from fastapi.testclient import TestClient
    from server.sunucu import app
    istemci = TestClient(app)
    for yol in ("/api/bildirim/ogrenci-saklama", "/api/bildirim/sonucu-girilmemis-randevu", "/api/bildirim/yedek"):
        assert istemci.get(yol).status_code in (401, 403), yol


def test_uclarin_gereken_izinleri():
    from server import bildirim_ozeti_api as api
    assert {yol: izin for yol, _, izin in api.UCLAR} == {
        "/api/bildirim/ogrenci-saklama": "FAALIYET_KAYITLARI_DUZENLE",       # Öğrenciler sayfasıyla aynı
        "/api/bildirim/sonucu-girilmemis-randevu": "RANDEVU_DUZENLE",         # sonucu işaretleme izniyle aynı
        "/api/bildirim/yedek": "AUDIT_KAYITLARI_INCELE",                      # Sistem Durumu sayfasıyla aynı
    }


def test_yedek_ozeti_klasorden_okur(tmp_path):
    from server import bildirim_ozeti_api as api
    ad = "tkys_deneme_veritabani"
    with patch.dict(os.environ, {"TKYS_BACKUP_DIR": str(tmp_path)}), patch.dict(api.VT_AYARLARI, {"dbname": ad}):
        assert api.yedek_ozeti()["var"] is False                                                   # klasör boş
        eski = datetime.now() - timedelta(days=3)
        (tmp_path / f"{ad}_{eski:%Y%m%d_%H%M%S}_000001.dump").write_bytes(b"x")
        assert api.yedek_ozeti()["var"] is True and api.yedek_ozeti()["eski"] is True              # 3 günlük yedek eski
        yeni = datetime.now() - timedelta(hours=2)
        (tmp_path / f"{ad}_{yeni:%Y%m%d_%H%M%S}_000001.dump").write_bytes(b"x")
        assert api.yedek_ozeti()["eski"] is False


def test_ozet_ucu_hata_olursa_500_doner_ayrinti_sizdirmaz():
    from fastapi import HTTPException
    from server import bildirim_ozeti_api as api
    with patch.object(api, "vt_baglan", side_effect=RuntimeError("gizli baglanti ayrintisi")):
        with pytest.raises(HTTPException) as hata:
            api.ogrenci_saklama_ozeti()
    assert hata.value.status_code == 500 and "gizli" not in hata.value.detail
