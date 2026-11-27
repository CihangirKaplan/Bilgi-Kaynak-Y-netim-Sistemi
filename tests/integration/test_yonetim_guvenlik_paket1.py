"""Yönetim güvenliği paketi 1: kullanıcı adı deseni, pasif rol kuralları, giriş sızıntısı, personel aktifliği.

Veritabanı sahte imleçle taklit edilir; PostgreSQL gerekmez (gerçek veritabanı karşılıkları test_psikolog_pasif_oda_pg_quality.py'de).
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from server.guvenlik import access_token_olustur
from server.modeller import GirisModeli, KullaniciOlusturModeli, RolDegistirModeli, RolGorunenAdModeli
from server.sunucu import (
    ROL_PASIF_ATAMA_MESAJI,
    ROL_PASIF_GIRIS_MESAJI,
    _sahte_parola_hash,
    giris_yap,
    kullanici_olustur,
    kullanici_rol_degistir,
    mevcut_kullanici_id,
    rol_guncelle,
    rolleri_listele,
)


# ------------------------------------------------------------------ kullanıcı adı deseni
@pytest.mark.parametrize("ad", ["ali", "ayse.yilmaz", "Mehmet_K-2", "a1b", "x" * 100])
def test_gecerli_kullanici_adlari_kabul_edilir(ad):
    assert KullaniciOlusturModeli(kullanici_adi=ad, rol_id=2).kullanici_adi == ad


@pytest.mark.parametrize("ad", ["   ", "al", "ali veli", "a\tb\n", "аli", "ali​veli", "ali.", ".ali", "ali@x", "ali/veli", "x" * 101, "çağrı", "ali\x00"])
def test_gecersiz_kullanici_adlari_reddedilir(ad):
    with pytest.raises(ValidationError):
        KullaniciOlusturModeli(kullanici_adi=ad, rol_id=2)


def test_basta_sonda_bosluk_kirpilir():
    assert KullaniciOlusturModeli(kullanici_adi="  ali  ", rol_id=2).kullanici_adi == "ali"


# ------------------------------------------------------------------ pasif role atama sunucuda reddedilir
def _cursor(sirali):
    conn = MagicMock()
    conn.cursor.return_value.fetchone.side_effect = list(sirali) + [None] * 4
    return conn


def test_pasif_role_kullanici_olusturulamaz():
    conn = _cursor([("ADMIN",), (1,), ("MEMUR", False)])                      # yapan rol, iki izin, hedef rol (pasif)
    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            kullanici_olustur(KullaniciOlusturModeli(kullanici_adi="yeni.kisi", rol_id=3), kullanici_id=1)
    assert hata.value.status_code == 422 and hata.value.detail == ROL_PASIF_ATAMA_MESAJI
    conn.commit.assert_not_called()


def test_pasif_role_rol_degistirilemez():
    conn = _cursor([("ADMIN",), ("MEMUR",), ("MUDUR", False)])                # islem yapan, hedef kullanıcının rolü, yeni rol (pasif)
    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            kullanici_rol_degistir(kullanici_id=7, veri=RolDegistirModeli(rol_id=3), islem_yapan_id=1)
    assert hata.value.status_code == 422 and hata.value.detail == ROL_PASIF_ATAMA_MESAJI
    conn.commit.assert_not_called()


# ------------------------------------------------------------------ rol pasife alma
def _rol_guncelle(kayit, yapanin_rol_id, sayi=0, aktif=False):
    conn = _cursor([kayit, (yapanin_rol_id,), (sayi,)])
    denetim = MagicMock()
    with patch("server.sunucu.psycopg2.connect", return_value=conn), patch("server.rol_api.denetim_kaydi_olustur", denetim):
        try:
            return rol_guncelle(3, RolGorunenAdModeli(gorunen_ad="Memur", aktif_mi=aktif), kullanici_id=1), conn, denetim
        except HTTPException as h:
            return h, conn, denetim


def test_rol_pasife_alinirken_etkilenen_kullanici_sayisi_donulur_ve_denetime_yazilir():
    yanit, conn, denetim = _rol_guncelle(("MEMUR", True, "Memur"), yapanin_rol_id=4, sayi=3)
    assert yanit["etkilenen_kullanici"] == 3 and "3 aktif kullanıcının sisteme girişi engellendi" in yanit["mesaj"]
    ayrinti = denetim.call_args.kwargs["ayrinti"]
    assert ayrinti["onceki"]["aktif_mi"] is True and ayrinti["yeni"]["aktif_mi"] is False and ayrinti["girisi_engellenen_kullanici"] == 3
    conn.commit.assert_called_once()


def test_kisi_kendi_rolunu_pasife_alamaz():
    hata, conn, _ = _rol_guncelle(("MUDUR", True, "Müdür"), yapanin_rol_id=3, sayi=2)           # yapan da aynı rolde (rol_id 3)
    assert isinstance(hata, HTTPException) and hata.status_code == 409 and "Kendi rolünüzü" in hata.detail
    conn.commit.assert_not_called()


def test_zaten_pasif_rol_yeniden_kaydedilince_kullanici_sayisi_hesaplanmaz():
    conn = _cursor([("MEMUR", False, "Memur")])
    with patch("server.sunucu.psycopg2.connect", return_value=conn), patch("server.rol_api.denetim_kaydi_olustur"):
        yanit = rol_guncelle(3, RolGorunenAdModeli(gorunen_ad="Memur", aktif_mi=False), kullanici_id=1)
    assert "etkilenen_kullanici" not in yanit


def test_rol_aktife_alinirken_uyari_yok():
    yanit, _, _ = _rol_guncelle(("MEMUR", False, "Memur"), yapanin_rol_id=4, aktif=True)
    assert yanit["mesaj"] == "Rol güncellendi." and "etkilenen_kullanici" not in yanit


def test_rol_listesi_aktif_kullanici_sayisini_icerir():
    conn = MagicMock()
    conn.cursor.return_value.fetchall.return_value = [(3, "MEMUR", "Memur", True, 3), (4, "ESKI", "Eski", False, 0)]
    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        roller = rolleri_listele(kullanici_id=1)
    assert [r["aktif_kullanici_sayisi"] for r in roller] == [3, 0]


# ------------------------------------------------------------------ her istekte rol aktifliği
def test_pasif_roldeki_kullanicinin_acik_oturumu_da_reddedilir():
    token = access_token_olustur(42, "HASH")
    conn = MagicMock()
    conn.cursor.return_value.fetchone.return_value = (True, False, "HASH", False)       # hesap aktif, ilk giriş değil, parola, ROL PASİF
    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            mevcut_kullanici_id(SimpleNamespace(credentials=token))
    assert hata.value.status_code == 403 and hata.value.detail == ROL_PASIF_GIRIS_MESAJI


# ------------------------------------------------------------------ giriş: sızıntı ve zamanlama
def _giris(satir, parola_dogru, ikinci=(1,)):
    conn = MagicMock()
    conn.cursor.return_value.fetchone.side_effect = [satir, ikinci]
    with patch("server.sunucu.psycopg2.connect", return_value=conn), patch("server.sunucu.parola_dogrula", return_value=parola_dogru), \
            patch("server.sunucu.denetim_kaydi_olustur"), patch("server.sunucu.giris_siniri") as sinir:
        sinir.engel_suresi.return_value = 0
        with pytest.raises(HTTPException) as hata:
            giris_yap(GirisModeli(kullanici_adi="ayse", parola="x"))
    return hata.value


ROL_PASIF_SATIR = (5, "ayse", "h", 3, True, 0, None, False, "MEMUR", None, False)


def test_pasif_rolde_dogru_parola_rolun_pasif_oldugunu_soyler():
    hata = _giris(ROL_PASIF_SATIR, parola_dogru=True)
    assert hata.status_code == 403 and hata.detail == ROL_PASIF_GIRIS_MESAJI


def test_pasif_rolde_yanlis_parola_hicbir_sey_ele_vermez():
    hata = _giris(ROL_PASIF_SATIR, parola_dogru=False)
    assert hata.status_code == 401 and hata.detail == "Kullanıcı adı veya parola hatalı."


def test_var_olmayan_kullanici_adinda_da_bcrypt_dogrulamasi_yapilir():
    conn = MagicMock()
    conn.cursor.return_value.fetchone.return_value = None
    with patch("server.sunucu.psycopg2.connect", return_value=conn), patch("server.sunucu.parola_dogrula", return_value=False) as dogrula, \
            patch("server.sunucu.denetim_kaydi_olustur"), patch("server.sunucu.giris_siniri") as sinir:
        sinir.engel_suresi.return_value = 0
        with pytest.raises(HTTPException) as hata:
            giris_yap(GirisModeli(kullanici_adi="yok", parola="x"))
    assert hata.value.status_code == 401
    dogrula.assert_called_once_with("x", _sahte_parola_hash())                          # yanıt süresi hesabın var olup olmadığını ele vermez
