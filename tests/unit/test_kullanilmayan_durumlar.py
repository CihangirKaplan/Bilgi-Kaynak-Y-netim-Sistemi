"""Rezerve/Kullanımda cihaz durumları elle seçilemez (hesaplanır); ise yaramayan takip kontrol izni kalktı."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError
from PySide6.QtWidgets import QApplication

import client.cihaz_ekranlari as envanter
import client.main_window as mw
from server.modeller import CihazDurumu, CihazGuncelleModeli, CihazOlusturModeli


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize("durum", ["Rezerve", "Kullanimda"])
def test_sunucu_elle_rezerve_ya_da_kullanimda_durumunu_reddeder(durum):
    with pytest.raises(ValidationError, match="elle seçilemez"):
        CihazOlusturModeli(envanter_kodu="E-1", cihaz_adi="EEG", durum=durum)
    with pytest.raises(ValidationError, match="elle seçilemez"):
        CihazGuncelleModeli(durum=durum)


@pytest.mark.parametrize("durum", ["Kullanima_Hazir", "Bakimda", "Kalibrasyonda", "Kullanim_Disi"])      # "Arizali" arıza kaydından türer, elle seçilemez
def test_diger_durumlar_secilebilir(durum):
    assert CihazOlusturModeli(envanter_kodu="E-1", cihaz_adi="EEG", durum=durum).durum == CihazDurumu(durum)
    assert CihazGuncelleModeli(durum=durum).durum == CihazDurumu(durum)
    assert CihazGuncelleModeli(cihaz_adi="Yeni").durum is None                         # durum göndermeyen düzenleme serbest


def test_envanter_formunda_hesaplanan_durumlar_secenek_degil_ama_etiketleri_kalir():
    f = envanter.CihazIslemFormu("http://x", "t", "GUNCELLE", {"cihaz_id": 1, "envanter_kodu": "E", "cihaz_adi": "A", "durum": "Kullanima_Hazir"})
    secenekler = [f.cmb_durum.itemData(i) for i in range(f.cmb_durum.count())]
    assert "Rezerve" not in secenekler and "Kullanimda" not in secenekler and "Kullanima_Hazir" in secenekler and "Arizali" not in secenekler
    assert "Rezerve" in envanter.DURUMLAR and "Kullanimda" in envanter.DURUMLAR            # eski kayıtların rozeti hâlâ çizilir
    f.close()


def test_takip_kontrol_izni_menuden_ve_matristen_kalkti():
    assert "Cihaz takip kontrol listesini yönetme" not in mw.IZIN and "Cihaz takip kontrol listesini yönetme" not in mw.IZIN_KODLARI
    assert all("CIHAZ_TAKIP_KONTROL_LISTESI" not in kodlar for kodlar in mw.IZIN_KODLARI.values())


def test_migration_durumlari_normallestirir_ve_izni_siler():
    yol = Path("database/migrations/versions/c4e9a7d2b815_kullanilmayan_cihaz_durumu_ve_izni_temizligi.py")
    spec = importlib.util.spec_from_file_location("m_c4e9", yol)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    sorgular = []
    with patch.object(modul.op, "execute", side_effect=lambda s: sorgular.append(" ".join(str(s).split()))):
        modul.upgrade()
    toplam = " | ".join(sorgular)
    assert "UPDATE cihazlar SET durum = 'Kullanima_Hazir'" in toplam and "IN ('Rezerve', 'Kullanimda')" in toplam
    assert "DELETE FROM izinler WHERE izin_adi = 'CIHAZ_TAKIP_KONTROL_LISTESI'" in toplam
    assert modul.down_revision == "b8d3f5a1c492"


def test_yonetim_panelinde_durum_etiketleri_anlamli():
    kaynak = Path("client/yonetim_bugun_merkezde.py").read_text(encoding="utf-8")
    assert "Şu an kullanımda" in kaynak and "Bugün rezervasyonu olan" in kaynak
