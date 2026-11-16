"""Rezervasyon: bölüm seçimi ve proje türü listesi (sunucu tarafı).

Bölüm `bolumler` tablosundan, proje türü `proje_turleri` tablosundan gelir; formdan yeni kayıt eklenebilir.
Veritabanı sahte bağlantıyla taklit edilir (gerçek PostgreSQL ile ayrıca doğrulanmıştır, bkz. PR açıklaması).
"""
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import psycopg2
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

import server.sunucu as sunucu
from server.modeller import BolumOlusturModeli, ProjeTuruOlusturModeli, RezervasyonOlusturModeli


def baglanti(satirlar=None, bir_satir=None, hata=None):
    conn = MagicMock()
    imlec = conn.cursor.return_value
    imlec.fetchall.return_value = satirlar or []
    imlec.fetchone.return_value = bir_satir
    if hata:
        def calistir(sorgu, *a, **k):
            if "INSERT INTO" in str(sorgu) and "denetim" not in str(sorgu):
                raise hata
        imlec.execute.side_effect = calistir
    return conn, imlec


def sorgular(imlec):
    return [str(c.args[0]) for c in imlec.execute.call_args_list]


# ---------------------------------------------------------------- modeller
def test_bolum_modeli_bosluklari_atar_ve_bos_ada_izin_vermez():
    b = BolumOlusturModeli(bolum_adi="  Psikoloji  ", sorumlu_ad_soyad=" Ayşe Y. ", iletisim_bilgisi="  ")
    assert (b.bolum_adi, b.sorumlu_ad_soyad, b.iletisim_bilgisi) == ("Psikoloji", "Ayşe Y.", None)
    for kotu in ({"bolum_adi": "   ", "sorumlu_ad_soyad": "X"}, {"bolum_adi": "B", "sorumlu_ad_soyad": ""},
                 {"bolum_adi": "B" * 151, "sorumlu_ad_soyad": "X"}, {"bolum_adi": "B", "sorumlu_ad_soyad": "X", "ek": 1}):
        with pytest.raises(ValidationError):
            BolumOlusturModeli(**kotu)


def test_proje_turu_modeli_bosluklari_atar_ve_sinirlari_uygular():
    assert ProjeTuruOlusturModeli(ad="  Staj ").ad == "Staj"
    for kotu in ("", "   ", "A" * 51):
        with pytest.raises(ValidationError):
            ProjeTuruOlusturModeli(ad=kotu)


def test_rezervasyon_modeli_bolum_istege_bagli_ama_gecerli_olmali():
    gel = datetime(2027, 1, 5, 10)
    ortak = dict(cihaz_id=1, baslangic_zamani=gel, bitis_zamani=gel + timedelta(hours=1))
    assert RezervasyonOlusturModeli(**ortak).bolum_id is None                           # eski istemci
    assert RezervasyonOlusturModeli(**ortak, bolum_id=3).bolum_id == 3
    with pytest.raises(ValidationError):
        RezervasyonOlusturModeli(**ortak, bolum_id=0)


# ---------------------------------------------------------------- bölümler
def test_bolumler_yalniz_aktif_olanlari_adina_gore_listeler():
    conn, imlec = baglanti(satirlar=[(4, "Fizyoloji", "Can K."), (7, "Psikoloji", "Ayşe Y.")])
    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        sonuc = sunucu.bolumleri_listele(kullanici_id=1)
    assert sonuc == [{"bolum_id": 4, "bolum_adi": "Fizyoloji", "sorumlu_ad_soyad": "Can K."},
                     {"bolum_id": 7, "bolum_adi": "Psikoloji", "sorumlu_ad_soyad": "Ayşe Y."}]
    assert "aktif_mi IS NOT FALSE" in sorgular(imlec)[0] and "ORDER BY bolum_adi" in sorgular(imlec)[0]
    conn.close.assert_called_once()


def test_bolum_olusturma_kaydeder_denetim_yazar_ve_yeni_kaydi_doner():
    conn, imlec = baglanti(bir_satir=(12,))
    model = BolumOlusturModeli(bolum_adi="Nöroloji", sorumlu_ad_soyad="Zeynep T.")
    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        sonuc = sunucu.bolum_olustur(model, kullanici_id=5)
    assert sonuc["bolum_id"] == 12 and sonuc["bolum_adi"] == "Nöroloji"
    ekleme, denetim = imlec.execute.call_args_list[0], imlec.execute.call_args_list[1]
    assert "INSERT INTO bolumler" in ekleme.args[0] and ekleme.args[1] == ("Nöroloji", "Zeynep T.", None)
    assert denetim.args[1] == (5, "CREATE", "bolumler", 12)
    conn.commit.assert_called_once()


def test_ayni_adli_bolum_409_verir_ve_geri_alinir():
    conn, imlec = baglanti(hata=psycopg2.errors.UniqueViolation("x"))
    with patch("server.sunucu.psycopg2.connect", return_value=conn), pytest.raises(HTTPException) as hata:
        sunucu.bolum_olustur(BolumOlusturModeli(bolum_adi="A", sorumlu_ad_soyad="B"), kullanici_id=5)
    assert hata.value.status_code == 409 and "zaten mevcut" in hata.value.detail
    conn.rollback.assert_called_once()
    conn.commit.assert_not_called()


# ---------------------------------------------------------------- proje türleri
def test_proje_turleri_listelenir():
    conn, imlec = baglanti(satirlar=[(1, "Araştırma"), (2, "Test")])
    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        assert sunucu.proje_turlerini_listele(kullanici_id=1) == [{"proje_turu_id": 1, "ad": "Araştırma"}, {"proje_turu_id": 2, "ad": "Test"}]
    assert "FROM proje_turleri" in sorgular(imlec)[0]


def test_proje_turu_anahtari_turkce_harf_farkini_yok_sayar():
    a = sunucu.proje_turu_anahtari
    assert a("ARAŞTIRMA") == a("araştırma") == a("  Araştırma ")
    assert a("İSTATİSTİK") == a("istatistik") and a("IŞIK") == a("ışık")
    assert a("Test") != a("Tez")


def test_proje_turu_olusturma_kaydeder_ve_denetim_yazar():
    conn, imlec = baglanti(satirlar=[("Araştırma",)], bir_satir=(9,))
    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        sonuc = sunucu.proje_turu_olustur(ProjeTuruOlusturModeli(ad="Staj"), kullanici_id=5)
    assert sonuc["proje_turu_id"] == 9 and sonuc["ad"] == "Staj"
    assert imlec.execute.call_args_list[-1].args[1] == (5, "CREATE", "proje_turleri", 9)
    conn.commit.assert_called_once()


@pytest.mark.parametrize("ad", ["araştırma", "ARAŞTIRMA", " Araştırma "])
def test_var_olan_proje_turu_buyuk_kucuk_harf_farkina_ragmen_409_verir(ad):
    conn, imlec = baglanti(satirlar=[("Araştırma",)])
    with patch("server.sunucu.psycopg2.connect", return_value=conn), pytest.raises(HTTPException) as hata:
        sunucu.proje_turu_olustur(ProjeTuruOlusturModeli(ad=ad), kullanici_id=5)
    assert hata.value.status_code == 409
    assert not [s for s in sorgular(imlec) if "INSERT" in s]
    conn.commit.assert_not_called()


def test_es_zamanli_ayni_proje_turu_veritabani_kisitiyla_409_verir():
    conn, imlec = baglanti(hata=psycopg2.errors.UniqueViolation("x"))
    with patch("server.sunucu.psycopg2.connect", return_value=conn), pytest.raises(HTTPException) as hata:
        sunucu.proje_turu_olustur(ProjeTuruOlusturModeli(ad="Yeni"), kullanici_id=5)
    assert hata.value.status_code == 409
    conn.rollback.assert_called_once()


# ---------------------------------------------------------------- rezervasyonda bölüm
def rezervasyon_yap(bolum_id, bolum_var):
    gel = datetime(2027, 1, 5, 10)
    conn = MagicMock()
    imlec = conn.cursor.return_value

    def calistir(sorgu, *a, **k):
        imlec.son = str(sorgu)
    imlec.execute.side_effect = calistir

    def bir():
        s = imlec.son
        if "FROM bolumler" in s:
            return (1,) if bolum_var else None
        if "FROM cihazlar" in s and "durum" in s:
            return ("Kullanima_Hazir",)
        if "RETURNING rezervasyon_id" in s:
            return (31,)
        if "personel_id FROM personel" in s:
            return (3,)
        return None
    imlec.fetchone.side_effect = bir
    imlec.fetchall.return_value = []
    model = RezervasyonOlusturModeli(cihaz_id=1, bolum_id=bolum_id, baslangic_zamani=gel, bitis_zamani=gel + timedelta(hours=1), proje_turu="Staj")
    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        try:
            return sunucu.cihaz_rezervasyonu_yap(model, kullanici_id=5), imlec
        except HTTPException as h:
            return h, imlec


def test_olmayan_ya_da_pasif_bolumle_rezervasyon_422_verir():
    sonuc, imlec = rezervasyon_yap(bolum_id=99, bolum_var=False)
    assert isinstance(sonuc, HTTPException) and sonuc.status_code == 422 and "Bölüm" in sonuc.detail
    assert not [s for s in sorgular(imlec) if "INSERT INTO cihaz_rezervasyonlari" in s]


def test_gecerli_bolumle_rezervasyon_bolum_kimligini_kaydeder():
    sonuc, imlec = rezervasyon_yap(bolum_id=4, bolum_var=True)
    assert not isinstance(sonuc, HTTPException), getattr(sonuc, "detail", "")
    ekleme = next(c for c in imlec.execute.call_args_list if "INSERT INTO cihaz_rezervasyonlari" in str(c.args[0]))
    assert "bolum_id" in ekleme.args[0] and ekleme.args[1][1] == 4


# ---------------------------------------------------------------- rezervasyonda oda: yalnızca cihaz odaları
def test_cihaz_odalari_yalniz_cihazin_zimmetli_oldugu_aktif_odalari_listeler():
    conn, imlec = baglanti(satirlar=[(1, "Cihaz Odası"), (3, "Lab")])
    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        sonuc = sunucu.cihaz_odalarini_listele(kullanici_id=1)
    assert sonuc == [{"oda_id": 1, "oda_adi": "Cihaz Odası", "aktif_mi": True}, {"oda_id": 3, "oda_adi": "Lab", "aktif_mi": True}]
    sorgu = sorgular(imlec)[0]
    assert "JOIN cihazlar c ON c.zimmetli_oda_id = o.oda_id" in sorgu and "o.aktif_mi = TRUE" in sorgu
    assert "psikolog_odalar" not in sorgu                                                # psikolog atamasından bağımsız, cihaz ilişkisine bakar


def oda_ile_rezervasyon(oda_id, oda_cihaz_odasi_mi):
    gel = datetime(2027, 1, 5, 10)
    conn = MagicMock()
    imlec = conn.cursor.return_value
    imlec.execute.side_effect = lambda sorgu, *a, **k: setattr(imlec, "son", str(sorgu))

    def bir():
        s = imlec.son
        if "zimmetli_oda_id" in s:
            return (1,) if oda_cihaz_odasi_mi else None
        if "FROM cihazlar" in s and "durum" in s:
            return ("Kullanima_Hazir",)
        if "RETURNING rezervasyon_id" in s:
            return (31,)
        if "personel_id FROM personel" in s:
            return (3,)
        return None
    imlec.fetchone.side_effect = bir
    imlec.fetchall.return_value = []
    model = RezervasyonOlusturModeli(cihaz_id=1, kullanilacak_oda_id=oda_id, baslangic_zamani=gel, bitis_zamani=gel + timedelta(hours=1))
    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        try:
            return sunucu.cihaz_rezervasyonu_yap(model, kullanici_id=5), imlec
        except HTTPException as h:
            return h, imlec


def test_cihaz_odasi_olmayan_odayla_rezervasyon_422_verir():
    sonuc, imlec = oda_ile_rezervasyon(oda_id=8, oda_cihaz_odasi_mi=False)
    assert isinstance(sonuc, HTTPException) and sonuc.status_code == 422 and "cihaz odası" in sonuc.detail
    assert not [s for s in sorgular(imlec) if "INSERT INTO cihaz_rezervasyonlari" in s]


def test_cihaz_odasiyla_rezervasyon_kaydedilir():
    sonuc, imlec = oda_ile_rezervasyon(oda_id=1, oda_cihaz_odasi_mi=True)
    assert not isinstance(sonuc, HTTPException), getattr(sonuc, "detail", "")
    assert [s for s in sorgular(imlec) if "INSERT INTO cihaz_rezervasyonlari" in s]
