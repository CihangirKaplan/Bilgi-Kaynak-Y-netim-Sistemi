"""Server yardımcı modüllerinin gözden geçirilmesi: JWT ayarları, geçici parola, giriş sınırı adresi, güvenlik başlıkları,
etkinlik modelleri ve etkinlik denetim özeti."""
import asyncio
import os
import subprocess
import sys
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from server import guvenlik, oda_etkinlikleri_api, oda_etkinlikleri_modelleri as em, sistem_durumu
from server.guvenlik_basliklari import GuvenlikBasliklari
from server.parola_politikasi import parola_ihlalleri


def _guvenlik_yukle(**ortam):
    """server.guvenlik modül düzeyinde ayar doğruladığı için ayrı bir süreçte, verilen ortamla yüklenir."""
    env = {**os.environ, "JWT_SECRET": "x" * 40, **ortam}
    return subprocess.run([sys.executable, "-c", "import server.guvenlik as g; print(g.JWT_EXPIRE_MINUTES, g.JWT_ALGORITHM)"],
                          env=env, capture_output=True, text=True, cwd=os.getcwd())


@pytest.mark.parametrize("ortam", [{"JWT_ALGORITHM": "none"}, {"JWT_ALGORITHM": "RS256"}, {"JWT_EXPIRE_MINUTES": "0"},
                                   {"JWT_EXPIRE_MINUTES": "-5"}, {"JWT_EXPIRE_MINUTES": "abc"}, {"JWT_EXPIRE_MINUTES": "99999"}])
def test_gecersiz_jwt_ayari_acik_hatayla_reddedilir(ortam):
    sonuc = _guvenlik_yukle(**ortam)
    assert sonuc.returncode != 0 and "RuntimeError" in sonuc.stderr


def test_gecerli_jwt_ayari_kabul_edilir():
    sonuc = _guvenlik_yukle(JWT_ALGORITHM="HS512", JWT_EXPIRE_MINUTES="30")
    assert sonuc.returncode == 0 and sonuc.stdout.split() == ["30", "HS512"]


def test_gecici_parola_her_zaman_politikaya_uyar():
    for _ in range(3000):
        parola = guvenlik.gecici_parola_uret()
        assert len(parola) == guvenlik.GECICI_PAROLA_UZUNLUK
        assert parola_ihlalleri(parola) == []
        assert any(c.islower() for c in parola) and any(c.isupper() for c in parola) and any(c.isdigit() for c in parola)
        assert any(c in "!@#$%&*" for c in parola)


def test_gecici_parolalar_birbirinden_farklidir():
    assert len({guvenlik.gecici_parola_uret() for _ in range(200)}) == 200


def test_sistem_durumu_oturum_suresi_tek_kaynaktan_gelir():
    assert sistem_durumu.OTURUM_SURESI_DK == guvenlik.JWT_EXPIRE_MINUTES


def _calistir(path, yanit_basliklari=None):
    gonderilen = []

    async def uygulama(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": list(yanit_basliklari or [])})
        await send({"type": "http.response.body", "body": b""})

    async def gonder(mesaj):
        gonderilen.append(mesaj)

    asyncio.run(GuvenlikBasliklari(uygulama)({"type": "http", "scheme": "http", "path": path, "headers": []}, None, gonder))
    return dict(gonderilen[0]["headers"])


def test_api_yanitlari_onbellege_alinmaz():
    basliklar = _calistir("/api/randevular")
    assert basliklar[b"cache-control"] == b"no-store"
    assert basliklar[b"x-frame-options"] == b"DENY" and basliklar[b"referrer-policy"] == b"no-referrer"
    assert basliklar[b"x-content-type-options"] == b"nosniff"


def test_api_disi_yollarda_onbellek_basligi_eklenmez():
    assert b"cache-control" not in _calistir("/docs")


def test_ucun_kendi_onbellek_basligi_ezilmez():
    basliklar = _calistir("/api/x", [(b"Cache-Control", b"max-age=60")])
    assert basliklar[b"Cache-Control"] == b"max-age=60" and b"cache-control" not in basliklar


GUN = {"baslangic_zamani": "2026-11-25T09:00:00", "bitis_zamani": "2026-11-25T10:00:00"}


def _olustur(**ek):
    return em.OdaEtkinlikOlusturModeli(**{"oda_id": 1, "organize_eden_personel_id": 1, "etkinlik_adi": "Seminer", **GUN, **ek})


@pytest.mark.parametrize("ad", ["", "   ", "\t\n"])
def test_bos_ya_da_bosluktan_olusan_etkinlik_adi_reddedilir(ad):
    with pytest.raises(ValidationError):
        _olustur(etkinlik_adi=ad)
    with pytest.raises(ValidationError):
        em.OdaEtkinlikGuncelleModeli(etkinlik_adi=ad)


def test_etkinlik_adinin_kenar_bosluklari_kirpilir():
    assert _olustur(etkinlik_adi="  Seminer  ").etkinlik_adi == "Seminer"
    assert em.OdaEtkinlikGuncelleModeli(katilimci_sayisi=3).model_dump(exclude_unset=True) == {"katilimci_sayisi": 3}


@pytest.mark.parametrize("zaman", ["2026-11-25T09:00:00+03:00", 1795000000, 1.5])
def test_saat_dilimli_ya_da_sayisal_zaman_reddedilir(zaman):
    with pytest.raises(ValidationError):
        em.OdaEtkinlikGunModeli(baslangic_zamani=zaman, bitis_zamani="2026-11-25T10:00:00")


def test_karisik_saat_dilimi_artik_500_degil_dogrulama_hatasidir():
    """Önceden naif ve saat dilimli oturumlar karışınca TypeError oluşuyor ve istek 500 ile bitiyordu."""
    gunler = [{"baslangic_zamani": "2026-11-25T09:00:00", "bitis_zamani": "2026-11-25T10:00:00"},
              {"baslangic_zamani": "2026-11-26T09:00:00Z", "bitis_zamani": "2026-11-26T10:00:00Z"}]
    modelle = em.OdaEtkinlikOlusturModeli(oda_id=1, organize_eden_personel_id=1, etkinlik_adi="x", gunler=gunler)
    assert all(g.baslangic_zamani.tzinfo is None for g in modelle.gunler)       # "Z" soneki atılıp saat dilimsiz yerel zaman olur


def test_denetim_ozeti_etkinlik_adi_ve_kisisel_veri_icermez():
    kayit = {"oda_id": 1, "organize_eden_personel_id": 7, "katilimci_sayisi": 12, "baslangic_zamani": "a", "bitis_zamani": "b",
             "etkinlik_adi": "Ayşe Hoca semineri", "iptal_edildi_mi": False}
    assert set(oda_etkinlikleri_api._denetim_ozeti(kayit)) == set(oda_etkinlikleri_api.DENETIME_YAZILAN_ALANLAR)
    assert "etkinlik_adi" not in oda_etkinlikleri_api._denetim_ozeti(kayit)
