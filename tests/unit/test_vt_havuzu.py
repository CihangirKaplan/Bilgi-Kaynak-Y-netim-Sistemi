"""Bağlantı havuzu ayarı ve kapalıyken eski davranış (veritabanı gerektirmez; gerçek veritabanı testleri test_vt_havuzu_pg_quality.py)."""
from pathlib import Path
from unittest.mock import patch

import pytest

from server import vt_baglanti

KOK = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("deger, beklenen", [
    (None, 10), ("", 10), ("  ", 10), ("0", 0), ("3", 3), (" 25 ", 25), ("abc", 10), ("-4", 0), ("2.5", 10),
])
def test_havuz_boyutu_ortam_degiskeninden_okunur(monkeypatch, deger, beklenen):
    if deger is None:
        monkeypatch.delenv("TKYS_DB_HAVUZ_BOYUTU", raising=False)
    else:
        monkeypatch.setenv("TKYS_DB_HAVUZ_BOYUTU", deger)
    assert vt_baglanti.havuz_boyutu() == beklenen


def test_havuz_kapaliyken_psycopg2_connect_eskisi_gibi_dogrudan_cagrilir(monkeypatch):
    monkeypatch.setenv("TKYS_DB_HAVUZ_BOYUTU", "0")
    with patch("server.vt_baglanti.psycopg2.connect") as bagla:
        vt_baglanti.vt_baglan({"dbname": "x", "user": "u"})
    bagla.assert_called_once_with(dbname="x", user="u")                    # ek argüman (connection_factory) yok


def test_havuz_acikken_baglanti_havuzlu_sinifla_acilir_ve_ayni_ayarlar_ayni_havuzu_kullanir(monkeypatch):
    monkeypatch.setenv("TKYS_DB_HAVUZ_BOYUTU", "3")
    vt_baglanti.havuzlari_bosalt()
    try:
        with patch("server.vt_baglanti.psycopg2.connect") as bagla:
            vt_baglanti.vt_baglan({"dbname": "x", "user": "u"})
        assert bagla.call_args.kwargs["connection_factory"] is vt_baglanti.HavuzluBaglanti
        assert vt_baglanti._havuz_al({"dbname": "x", "user": "u"}, 3) is vt_baglanti._havuz_al({"user": "u", "dbname": "x"}, 3)
        assert vt_baglanti._havuz_al({"dbname": "y", "user": "u"}, 3) is not vt_baglanti._havuz_al({"dbname": "x", "user": "u"}, 3)
    finally:
        vt_baglanti.havuzlari_bosalt()


def test_havuz_acikken_ilk_baglantida_istemci_adresi_baslangic_secenegi_olarak_gider(monkeypatch):
    monkeypatch.setenv("TKYS_DB_HAVUZ_BOYUTU", "3")
    vt_baglanti.havuzlari_bosalt()
    belirtec = vt_baglanti.adresi_ayarla("203.0.113.7")
    try:
        with patch("server.vt_baglanti.psycopg2.connect") as bagla:
            vt_baglanti.vt_baglan({"dbname": "x"})
        assert bagla.call_args.kwargs["options"] == "-c tkys.istemci_adresi=203.0.113.7"
    finally:
        vt_baglanti.adresi_sifirla(belirtec)
        vt_baglanti.havuzlari_bosalt()


def test_catallanan_surecte_ust_surecin_baglantilari_kullanilmaz(monkeypatch):
    havuz = vt_baglanti._Havuz({"dbname": "x"}, 3)
    havuz.bosta.append((object(), 0.0))
    havuz.pid = -1                                                       # başka bir süreçten kalmış gibi
    with havuz.kilit:
        havuz._catal_kontrolu()
    assert havuz.bosta == []


def test_ortam_degiskeni_sablonda_ve_yonetici_kilavuzunda_belgelenmistir():
    assert "TKYS_DB_HAVUZ_BOYUTU" in (KOK / ".env.example").read_text(encoding="utf-8")
    assert "TKYS_DB_HAVUZ_BOYUTU" in (KOK / "user-manuals" / "administrative" / "Sistem_Yoneticisi_Kilavuzu.md").read_text(encoding="utf-8")


def test_giris_sinirlayici_veritabanina_ortak_baglanti_fonksiyonuyla_baglanir():
    kaynak = (KOK / "server" / "giris_siniri.py").read_text(encoding="utf-8")
    assert "psycopg2.connect(" not in kaynak and kaynak.count("vt_baglan(vt_ayarlari)") == 2
