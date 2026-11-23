"""Faaliyet modülü son kontrol düzeltmeleri.

1. Düzenleme penceresi öğrenci/faaliyet/birimi ad yerine kimlikle seçer (aynı ad parçası taşıyan kayıtlar karışmaz).
2. Faaliyet puanı üst sınırı: puan x miktar çarpımı veritabanındaki INTEGER sınırını aşamaz.
3. Birim ekleme/yeniden adlandırmada ad tekrarı 500 değil 400 verir.
4. Kod yorumlarında hitap eden/uygunsuz ifadeler kalmaz.
"""
import json
import pathlib
from datetime import date
from unittest.mock import MagicMock, patch

import psycopg2.errors
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

import client.faaliyet_dialog as dialog_modulu
import client.faaliyet_turleri_dialog as turler_modulu
from server import sunucu
from server.sunucu import (
    FAALIYET_PUANI_EN_FAZLA,
    FaaliyetBirimIslemModeli,
    FaaliyetTuruDuzenleModeli,
    FaaliyetTuruEkleModeli,
)

KOK = pathlib.Path(__file__).resolve().parents[2]


# ------------------------------------------------------------------ 1. kimlikle seçim
def _yanit(veri):
    m = MagicMock()
    m.status_code = 200
    m.json.return_value = veri
    m.text = json.dumps(veri)
    m._tkys_oturum_reddedildi = False
    return m


def _sahte(ogrenciler, faaliyetler, birimler):
    def istek(method, url, **kwargs):
        if url.endswith("/api/ogrenciler-liste"):
            return _yanit(ogrenciler)
        if url.endswith("/api/faaliyetler"):
            return _yanit(faaliyetler)
        if url.endswith("/api/faaliyet-birimleri"):
            return _yanit(birimler)
        return _yanit([])
    return istek


OGRENCILER = [
    {"id": 1, "metin": "Ayşe Kaya - [2201001] (Gönüllü)", "tur": "GONULLU"},
    {"id": 2, "metin": "Ayşe - [2201002] (Danışma Masası)", "tur": "DANISMA_MASASI"},
]
FAALIYETLER = [{"id": 3, "ad": "Online Anket 2", "puan": 2}, {"id": 2, "ad": "Online Anket", "puan": 1}]
BIRIMLER = [{"id": 1, "ad": "KISI"}, {"id": 2, "ad": "SAAT"}]


def _duzenleme_penceresi(tkys_qapplication, mevcut_veri, ogrenciler=OGRENCILER):
    with patch.object(dialog_modulu, "oturum_kontrollu_istek", side_effect=_sahte(ogrenciler, FAALIYETLER, BIRIMLER)):
        return dialog_modulu.FaaliyetEkleDialog("http://x", "t", None, mevcut_veri=mevcut_veri)


def test_duzenleme_ad_parcasi_ayni_olan_ogrenciyi_karistirmaz(tkys_qapplication):
    """'Ayşe' adlı öğrencinin kaydı düzenlenirken 'Ayşe Kaya' seçilirse Güncelle kaydı sessizce başka öğrenciye taşırdı."""
    pencere = _duzenleme_penceresi(tkys_qapplication, {
        "takip_id": "5", "ogrenci_adi": "Ayşe", "ogrenci_no": "2201002", "faaliyet_adi": "Online Anket", "miktar": "3",
        "birim_adi": "SAAT", "ogrenci_id": 2, "faaliyet_id": 2, "birim_id": 2,
    })
    assert pencere.cb_ogrenci.currentData() == 2
    assert pencere.cb_faaliyet.currentData() == 2          # "Online Anket 2" listede önde olsa da doğru tür seçilir
    assert pencere.cb_birim.currentData() == 2 and pencere.sb_miktar.value() == 3


def test_duzenleme_pasif_ogrenci_listede_yoksa_eklenip_secilir(tkys_qapplication):
    pencere = _duzenleme_penceresi(tkys_qapplication, {
        "takip_id": "5", "ogrenci_adi": "Eski Öğrenci", "ogrenci_no": "1900001", "faaliyet_adi": "Online Anket", "miktar": "1",
        "birim_adi": "KISI", "ogrenci_id": 99, "faaliyet_id": 2, "birim_id": 1,
    })
    assert pencere.cb_ogrenci.currentData() == 99
    assert "Eski Öğrenci" in pencere.cb_ogrenci.currentText()


def test_duzenleme_kimliksiz_eski_veride_tam_ad_eslesmesi(tkys_qapplication):
    pencere = _duzenleme_penceresi(tkys_qapplication, {
        "takip_id": "5", "ogrenci_adi": "Ayşe", "ogrenci_no": "2201002", "faaliyet_adi": "Online Anket", "miktar": "2",
        "birim_adi": "SAAT",
    })
    assert pencere.cb_ogrenci.currentData() == 2 and pencere.cb_faaliyet.currentData() == 2 and pencere.cb_birim.currentData() == 2


def test_faaliyet_kayitlari_listesi_kimlikleri_dondurur():
    """İstemci düzenleme penceresine kimlikleri bu listeden verir."""
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchall.return_value = [(7, "Ayşe", "2201002", "Online Anket", 3, "SAAT", 3, date(2026, 11, 2), 2, 2, 2)]
    with patch.object(sunucu, "vt_baglan", return_value=conn):
        kayitlar = sunucu.faaliyet_kayitlarini_getir(limit=None, offset=0, response=None, kullanici_id=1)
    assert kayitlar[0]["ogrenci_id"] == 2 and kayitlar[0]["faaliyet_id"] == 2 and kayitlar[0]["birim_id"] == 2
    assert kayitlar[0]["miktar"] == "3 SAAT" and kayitlar[0]["tarih"] == "02.11.2026"


# ------------------------------------------------------------------ 2. puan üst sınırı
def test_puan_ust_siniri_carpimin_integer_sinirini_asmasini_engeller():
    assert FAALIYET_PUANI_EN_FAZLA * 10_000 < 2**31                 # en büyük miktar (10.000) ile çarpım INTEGER'a sığar
    assert turler_modulu.FAALIYET_PUANI_EN_FAZLA == FAALIYET_PUANI_EN_FAZLA
    FaaliyetTuruEkleModeli(faaliyet_adi="Seminer", puan=FAALIYET_PUANI_EN_FAZLA)
    with pytest.raises(ValidationError):
        FaaliyetTuruEkleModeli(faaliyet_adi="Seminer", puan=FAALIYET_PUANI_EN_FAZLA + 1)
    with pytest.raises(ValidationError):
        FaaliyetTuruDuzenleModeli(faaliyet_adi="Seminer", puan=1_000_000, gecmis_puanlari_guncelle=False)


def test_faaliyet_turleri_penceresi_puan_kutusu_ust_sinirla_sinirli(tkys_qapplication):
    with patch.object(turler_modulu, "oturum_kontrollu_istek", return_value=_yanit([])):
        pencere = turler_modulu.FaaliyetTurleriDialog("http://x", "t", None)
    assert pencere.puan.maximum() == FAALIYET_PUANI_EN_FAZLA


# ------------------------------------------------------------------ 3. birim ekle / yeniden adlandır
def _baglanti(secimler):
    """secimler: sırayla fetchone sonuçları."""
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchone.side_effect = list(secimler)
    return conn, cursor


def _yazma_sorgusu_var(cursor):
    """UPDATE/INSERT/DELETE ile başlayan bir sorgu çalıştırıldı mı ('FOR UPDATE' kilidi yazma sayılmaz)."""
    return any(c.args[0].lstrip().upper().startswith(("UPDATE", "INSERT", "DELETE")) for c in cursor.execute.call_args_list)


def test_birim_ekle_kucuk_harfle_yazilan_mevcut_adi_400_ile_reddeder():
    conn, cursor = _baglanti([(1,)])                                   # "SAAT" zaten var
    with patch.object(sunucu, "vt_baglan", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            sunucu.faaliyet_birimi_ekle(FaaliyetBirimIslemModeli(birim_adi="saat"), yetkili_id=1)
    assert hata.value.status_code == 400 and "zaten mevcut" in hata.value.detail
    assert cursor.execute.call_args_list[0].args[1] == ("SAAT",)       # kontrol kayıt biçimiyle (büyük harf) yapılır
    conn.commit.assert_not_called()


def test_birim_ekle_es_zamanli_cakismada_500_degil_400_verir():
    conn, cursor = _baglanti([None])

    def calistir(sql, params=None):
        if sql.lstrip().upper().startswith("INSERT"):
            raise psycopg2.errors.UniqueViolation()
    cursor.execute.side_effect = calistir
    with patch.object(sunucu, "vt_baglan", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            sunucu.faaliyet_birimi_ekle(FaaliyetBirimIslemModeli(birim_adi="Yeni"), yetkili_id=1)
    assert hata.value.status_code == 400
    conn.rollback.assert_called()


def test_birim_ekle_bos_ad_422():
    conn, _ = _baglanti([])
    with patch.object(sunucu, "vt_baglan", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            sunucu.faaliyet_birimi_ekle(FaaliyetBirimIslemModeli(birim_adi="   "), yetkili_id=1)
    assert hata.value.status_code == 422


def test_birim_guncelle_baska_birimin_adina_400_verir():
    conn, cursor = _baglanti([("KISI",), (2,)])                        # mevcut ad KISI; "SAAT" adı başka birimde var
    with patch.object(sunucu, "vt_baglan", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            sunucu.faaliyet_birimi_guncelle(1, FaaliyetBirimIslemModeli(birim_adi="saat"), yetkili_id=1)
    assert hata.value.status_code == 400 and "zaten mevcut" in hata.value.detail
    assert not _yazma_sorgusu_var(cursor)
    conn.commit.assert_not_called()


def test_birim_guncelle_degisiklik_yoksa_yazmaz():
    conn, cursor = _baglanti([("SAAT",)])
    with patch.object(sunucu, "vt_baglan", return_value=conn):
        sonuc = sunucu.faaliyet_birimi_guncelle(2, FaaliyetBirimIslemModeli(birim_adi="saat"), yetkili_id=1)
    assert "değişiklik yapılmadı" in sonuc["mesaj"]
    assert not _yazma_sorgusu_var(cursor)


def test_birim_guncelle_basarida_denetim_kaydina_onceki_ve_yeni_ad_yazilir():
    conn, cursor = _baglanti([("KISI",), None])
    with patch.object(sunucu, "vt_baglan", return_value=conn), patch("server.denetim.denetim_kaydi_olustur") as denetim:
        sunucu.faaliyet_birimi_guncelle(1, FaaliyetBirimIslemModeli(birim_adi="Kişi Sayısı"), yetkili_id=7)
    cagri = denetim.call_args
    assert cagri.args[1] == "UPDATE" and cagri.args[2] == 7 and cagri.args[3] == "faaliyet_birimleri"
    assert cagri.kwargs["ayrinti"]["onceki"] == {"birim_adi": "KISI"}
    assert cagri.kwargs["ayrinti"]["yeni"]["birim_adi"] == "Kişi Sayısı".strip().upper()
    conn.commit.assert_called_once()


# ------------------------------------------------------------------ 4. yorumlar
YASAKLI = ("Sizin kodunuz", "SİZİN", "sizin diğer", "senin şemanda", "şemandaki", "EFSANE", "efsane SQL", "Öğrenci C'nin",
           "YENİ EKLENDİ", "EKLENEN KISIM")


@pytest.mark.parametrize("klasor", ["client", "server"])
def test_kodda_hitap_eden_ya_da_eski_degisiklik_yorumlari_yok(klasor):
    bulunanlar = []
    for dosya in sorted((KOK / klasor).glob("*.py")):
        for no, satir in enumerate(dosya.read_text(encoding="utf-8").splitlines(), 1):
            if any(ifade in satir for ifade in YASAKLI):
                bulunanlar.append(f"{dosya.name}:{no}: {satir.strip()[:80]}")
    assert not bulunanlar, "\n".join(bulunanlar)
