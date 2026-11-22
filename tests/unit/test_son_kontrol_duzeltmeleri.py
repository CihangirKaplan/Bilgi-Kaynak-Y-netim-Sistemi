"""Son kontrol düzeltmeleri: şifre değiştirme deneme sınırı, uzun görev uyarısı, sunucu adresi, denetim etiketleri,
rol-izin ekranlarında oturum kontrolü."""
import importlib
import inspect
import os
import subprocess
import sys
from pathlib import Path
import re
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from server.modeller import SifreDegistirModeli
from server.sunucu import sifre_degistir

KOK = Path(__file__).resolve().parents[2]


def _veri():
    return SifreDegistirModeli(eski_parola="Eski.Sifre.2026!", yeni_parola="Yeni.Sifre.2026!",
                               yeni_parola_tekrar="Yeni.Sifre.2026!")


# ------------------------------------------------------------------ şifre değiştirme: eski şifre tahmini sınırlanır
def test_sinir_asildiysa_sifre_degistirme_429_doner_ve_veritabanina_gitmez():
    with (
        patch("server.sunucu.giris_siniri.engel_suresi", return_value=120),
        patch("server.sunucu.vt_baglan") as baglan,
    ):
        with pytest.raises(HTTPException) as hata:
            sifre_degistir(veri=_veri(), request=MagicMock(), kullanici_id=10)
    assert hata.value.status_code == 429 and hata.value.headers["Retry-After"] == "120"
    baglan.assert_not_called()


def test_yanlis_eski_sifre_basarisiz_deneme_olarak_sayilir():
    conn = MagicMock()
    conn.cursor.return_value.fetchone.return_value = ("hash", True, "kullanici")
    with (
        patch("server.sunucu.giris_siniri.istemci_anahtari", return_value="istemci"),
        patch("server.sunucu.giris_siniri.engel_suresi", return_value=0),
        patch("server.sunucu.giris_siniri.basarisiz_girisi_kaydet") as kaydet,
        patch("server.sunucu.vt_baglan", return_value=conn),
        patch("server.sunucu.parola_dogrula", return_value=False),
    ):
        with pytest.raises(HTTPException) as hata:
            sifre_degistir(veri=_veri(), request=MagicMock(), kullanici_id=10)
    assert hata.value.status_code == 401
    kaydet.assert_called_once()
    assert kaydet.call_args.args[1] == "istemci"


def test_dogru_eski_sifre_deneme_sayacini_artirmaz():
    conn = MagicMock()
    conn.cursor.return_value.fetchone.return_value = ("hash", True, "kullanici")
    with (
        patch("server.sunucu.giris_siniri.engel_suresi", return_value=0),
        patch("server.sunucu.giris_siniri.basarisiz_girisi_kaydet") as kaydet,
        patch("server.sunucu.vt_baglan", return_value=conn),
        patch("server.sunucu.parola_dogrula", return_value=True),
        patch("server.sunucu.parola_ihlalleri", return_value=[]),
        patch("server.sunucu.parola_hashle", return_value="yeni"),
    ):
        sonuc = sifre_degistir(veri=_veri(), request=MagicMock(), kullanici_id=10)
    assert sonuc["durum"] == "basarili"
    kaydet.assert_not_called()


# ------------------------------------------------------------------ danışma masası: uzun görev
def test_uzun_gorev_sunucudan_ya_da_eski_sunucuda_sureden_anlasilir():
    from client.danisma_masasi_yonetimi import GOREV_EN_UZUN_SAAT, gorev_suresi_cok_uzun_mu, gorev_uzun_mu

    assert GOREV_EN_UZUN_SAAT == 10
    assert gorev_uzun_mu({"uzun_gorev": True}) and not gorev_uzun_mu({"uzun_gorev": False, "toplam_saniye": 99999})
    assert gorev_uzun_mu({"toplam_saniye": 10 * 3600 + 60})                    # eski sunucu: alan yok
    assert not gorev_uzun_mu({"toplam_saniye": 10 * 3600}) and not gorev_uzun_mu(None)

    bas = datetime(2026, 11, 20, 8, 0)
    assert not gorev_suresi_cok_uzun_mu(bas, bas + timedelta(hours=10))
    assert gorev_suresi_cok_uzun_mu(bas, bas + timedelta(hours=10, minutes=1))


def test_istemci_ve_sunucu_ayni_siniri_kullanir():
    import client.danisma_masasi_yonetimi as istemci
    import server.sunucu as sunucu

    assert istemci.GOREV_EN_UZUN_SAAT == sunucu.DANISMA_GOREV_EN_UZUN_SAAT
    assert istemci.GOREV_COK_UZUN_MESAJI == sunucu.DANISMA_GOREV_COK_UZUN_MESAJI


# ------------------------------------------------------------------ sunucu adresi
@pytest.mark.parametrize("ayar, beklenen", [
    ("http://10.0.0.5:8001/", "http://10.0.0.5:8001/api"),
    (None, "http://127.0.0.1:8000/api"),
])
def test_api_yoneticisi_tkys_api_url_ayarini_kullanir(ayar, beklenen):
    # Ayrı süreçte denenir: modülü yeniden yüklemek, diğer testlerin bağlandığı oturum sinyalini değiştirirdi.
    ortam = {k: v for k, v in os.environ.items() if k != "TKYS_API_URL"}
    if ayar:
        ortam["TKYS_API_URL"] = ayar
    cikti = subprocess.run(
        [sys.executable, "-c", "import client.api_yoneticisi as a; print(a.BASE_URL)"],
        capture_output=True, text=True, env=ortam, cwd=KOK, check=True,
    ).stdout.strip()
    assert cikti == beklenen


# ------------------------------------------------------------------ denetim ekranı
def test_denetim_ekrani_yeni_ayrinti_alanlarini_turkce_gosterir():
    from client.audit_kayitlari_ekrani import ayrinti_satirlari

    satirlar = dict(ayrinti_satirlari({
        "onceki": {"puan": 8}, "yeni": {"puan": 12},
        "gecmis_kayitlara_uygulandi": True, "guncellenen_gecmis_kayit": 4,
    }))
    assert satirlar["Önceki değer"] == "Puan: 8" and satirlar["Yeni değer"] == "Puan: 12"
    assert satirlar["Geçmiş kayıtlara uygulandı"] == "Evet" and satirlar["Güncellenen geçmiş kayıt"] == "4"
    gorev = dict(ayrinti_satirlari({"onceki": {"baslangic_zamani": "2026-11-20 09:00"}}))
    assert gorev["Önceki değer"] == "Başlangıç: 2026-11-20 09:00"


# ------------------------------------------------------------------ rol-izin ekranları
@pytest.mark.parametrize("modul", ["client.rol_izin_diyaloglari", "client.sayfalar_rol_izin"])
def test_rol_izin_istekleri_oturum_kontrolunden_gecer_ve_teknik_hata_gostermez(modul):
    kaynak = inspect.getsource(importlib.import_module(modul))
    assert not re.search(r"requests\.(get|post|put|patch|delete)\(", kaynak)
    assert "Sunucuya ulaşılamadı:\\n" not in kaynak and "Sunucu hatası:" not in kaynak
