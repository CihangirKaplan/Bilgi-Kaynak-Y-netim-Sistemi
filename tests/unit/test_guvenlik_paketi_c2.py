"""Çıkışta token iptali, istemci adresi bağlantı ayarı ve migrasyon dosyası (veritabanı gerektirmez)."""
import asyncio
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from server import vt_baglanti
from server.guvenlik import access_token_olustur, token_surumu_gecerli
from server.guvenlik_basliklari import GuvenlikBasliklari, istemci_adresi

SURUMLER = Path(__file__).resolve().parents[2] / "database" / "migrations" / "versions"


# ---------------- oturum sürümü ----------------
def test_token_surumu_eslesmeli():
    t = access_token_olustur(5, "hash", 2)
    assert token_surumu_gecerli(t, 2) and not token_surumu_gecerli(t, 3) and not token_surumu_gecerli(t, 0)


def test_surum_tasimayan_eski_token_surum_0_sayilir():
    t = access_token_olustur(5, "hash")
    assert token_surumu_gecerli(t, 0) and token_surumu_gecerli(t, None) and not token_surumu_gecerli(t, 1)


def test_bozuk_token_surumu_gecersiz():
    assert not token_surumu_gecerli("bozuk.token.degeri", 0)


# ---------------- bağlantı ayarı ----------------
@pytest.fixture(autouse=True)
def adres_temizle():
    belirtec = vt_baglanti.adresi_ayarla(None)
    yield
    vt_baglanti.adresi_sifirla(belirtec)


def test_adres_yoksa_baglanti_eskisi_gibi_acilir():
    with patch("server.vt_baglanti.psycopg2.connect") as bagla:
        vt_baglanti.vt_baglan({"dbname": "x", "user": "u"})
    bagla.assert_called_once_with(dbname="x", user="u")


def test_adres_varsa_oturum_ayari_olarak_eklenir_ve_ayar_sozlugu_degismez():
    ayarlar = {"dbname": "x"}
    vt_baglanti.adresi_ayarla("203.0.113.7")
    with patch("server.vt_baglanti.psycopg2.connect") as bagla:
        vt_baglanti.vt_baglan(ayarlar)
    bagla.assert_called_once_with(dbname="x", options="-c tkys.istemci_adresi=203.0.113.7")
    assert ayarlar == {"dbname": "x"}


@pytest.mark.parametrize("adres", ["10.0.0.1; DROP", "a b", "x" * 60, "", "testclient", None, 5, "-c evil=1"])
def test_gecersiz_adres_kabul_edilmez(adres):
    vt_baglanti.adresi_ayarla(adres)
    assert vt_baglanti.mevcut_adres() is None


@pytest.mark.parametrize("adres", ["192.168.1.20", "::1", "fe80::1a2b:3c4d"])
def test_ip_adresleri_kabul_edilir(adres):
    vt_baglanti.adresi_ayarla(adres)
    assert vt_baglanti.mevcut_adres() == adres


# ---------------- ara katman ----------------
def test_dogrudan_baglanan_adres_kullanilir_x_forwarded_for_gormezden_gelinir():
    scope = {"type": "http", "client": ("203.0.113.7", 1), "headers": [(b"x-forwarded-for", b"6.6.6.6")]}
    assert istemci_adresi(scope) == "203.0.113.7"


def test_guvenilir_vekilde_son_giris_kullanilir(monkeypatch):
    monkeypatch.setenv("TKYS_GUVENILIR_VEKIL", "1")
    scope = {"type": "http", "client": ("127.0.0.1", 1), "headers": [(b"x-forwarded-for", b"6.6.6.6, 198.51.100.4")]}
    assert istemci_adresi(scope) == "198.51.100.4"             # istemcinin yazdığı ilk girişe değil vekilin gördüğüne güvenilir


def test_ara_katman_istek_boyunca_adresi_tutar_ve_sonra_sifirlar():
    gorulen = []

    async def uygulama(scope, receive, send):
        gorulen.append(vt_baglanti.mevcut_adres())
        await send({"type": "http.response.start", "status": 200, "headers": []})

    async def gonder(mesaj):
        pass

    asyncio.run(GuvenlikBasliklari(uygulama)({"type": "http", "client": ("203.0.113.9", 1), "scheme": "http", "headers": []}, None, gonder))
    assert gorulen == ["203.0.113.9"] and vt_baglanti.mevcut_adres() is None


# ---------------- migrasyon ----------------
def _yukle():
    dosya = next(SURUMLER.glob("f4b7c2e9a186_*.py"))
    spec = importlib.util.spec_from_file_location("migrasyon_f4b7", dosya)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def test_migrasyon_zincire_baglanir():
    modul = _yukle()
    assert modul.revision == "f4b7c2e9a186"
    assert any(d.name.startswith(modul.down_revision) for d in SURUMLER.glob("*.py"))


def test_yukseltme_sutunlari_tetikleyiciyi_ve_olaylari_ekler_veriye_dokunmaz():
    modul = _yukle()
    with patch.object(modul, "op", MagicMock()) as op:
        modul.upgrade()
    sorgular = [" ".join(c.args[0].split()) for c in op.execute.call_args_list]
    metin = " ".join(sorgular)
    assert "ADD COLUMN IF NOT EXISTS token_surumu integer NOT NULL DEFAULT 0" in metin
    assert "ADD COLUMN IF NOT EXISTS istemci_adresi" in metin and "BEFORE INSERT ON denetim_kayitlari" in metin
    assert sorgular.index("COMMIT") < sorgular.index("ALTER TYPE denetim_olay_turu ADD VALUE IF NOT EXISTS 'LOGOUT'")   # ENUM değeri transaction dışında
    assert "'VIEW'" in metin
    assert not any(s.upper().startswith(("DELETE", "UPDATE", "TRUNCATE")) for s in sorgular)


def test_geri_alma_ekledigi_nesneleri_kaldirir():
    modul = _yukle()
    with patch.object(modul, "op", MagicMock()) as op:
        modul.downgrade()
    metin = " ".join(" ".join(c.args[0].split()) for c in op.execute.call_args_list)
    assert "DROP COLUMN IF EXISTS istemci_adresi" in metin and "DROP COLUMN IF EXISTS token_surumu" in metin
    assert "DROP TRIGGER IF EXISTS denetim_istemci_adresi_tetikleyici" in metin
