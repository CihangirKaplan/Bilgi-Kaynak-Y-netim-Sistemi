"""Son kontrol düzeltmeleri, gerçek PostgreSQL üzerinde (her test kendi işleminde çalışır, sonda geri alınır).

- Danışma masası görevi en fazla 10 saat (mesai süresi); daha uzun görev listede "uzun görev" diye işaretlenir.
- Denetim kaydı "neyden neye" değiştiğini yazar: faaliyet türü puanı, faaliyet kaydı, öğrenci aktifliği, görev saatleri.
- Faaliyet kaydında pasif türe geçiş doğru mesajla reddedilir.
- Faaliyet türü adı büyük/küçük harf farkıyla ikinci kez eklenemez.
"""
import os
import uuid
from datetime import datetime, timedelta
from unittest.mock import patch

import psycopg2
import pytest
from fastapi import HTTPException

from server.modeller import DanismaGorevDuzenleModeli, DanismaGorevOlusturModeli, FaaliyetKayitModeli
from server.sunucu import (
    VT_AYARLARI,
    FaaliyetTuruDuzenleModeli,
    FaaliyetTuruEkleModeli,
    OgrenciAktiflikModeli,
    danisma_yonetim_ogrencileri,
    danisma_yonetim_onay_geri_al,
    danisma_yonetim_oturum_duzenle,
    danisma_yonetim_oturum_olustur,
    danisma_yonetim_oturum_onayla,
    danisma_yonetim_oturumlari,
    faaliyet_kaydi_guncelle,
    faaliyet_turu_duzenle,
    faaliyet_turu_ekle,
    ogrenci_aktiflik_duzenle,
)


class SahteBaglanti:
    """Uç noktanın commit'ini engeller; her şey testin işleminde kalır ve sonda geri alınır.

    Uç noktanın kendi geri alması (hata durumunda) yalnızca test verisi hazırlandıktan sonraki noktaya döner."""

    def __init__(self, gercek):
        self.gercek = gercek

    def cursor(self, *args, **kwargs):
        return self.gercek.cursor(*args, **kwargs)

    def commit(self):
        pass

    def rollback(self):
        with self.gercek.cursor() as cur:
            cur.execute("ROLLBACK TO SAVEPOINT test_verisi_hazir")

    def close(self):
        pass


@pytest.fixture
def ortam():
    assert os.getenv("TKYS_PG_TEST_ONAY") == "EVET"
    assert VT_AYARLARI["dbname"] == "crkys_alembic_test"

    baglanti = psycopg2.connect(**VT_AYARLARI)
    etiket = uuid.uuid4().hex[:8]
    try:
        with baglanti.cursor() as cur:
            cur.execute("SELECT kullanici_id FROM kullanicilar ORDER BY kullanici_id LIMIT 1")
            kullanici = cur.fetchone()
            if kullanici is None:
                cur.execute("""
                    INSERT INTO kullanicilar (kullanici_adi, parola_hash, rol_id)
                    VALUES (%s, 'x', (SELECT rol_id FROM roller WHERE rol_adi = 'ADMIN')) RETURNING kullanici_id
                """, (f"qa_son_{etiket}",))
                kullanici = cur.fetchone()

            cur.execute("""
                INSERT INTO ogrenciler (ad_soyad, ogrenci_numarasi, tur)
                VALUES (%s, %s, 'DANISMA_MASASI') RETURNING ogrenci_id
            """, (f"QA Son {etiket}", f"QS{etiket}"))
            ogrenci_id = cur.fetchone()[0]

            cur.execute("INSERT INTO faaliyet_birimleri (birim_adi) VALUES (%s) RETURNING birim_id", (f"QA_B_{etiket}",))
            birim_id = cur.fetchone()[0]

            cur.execute("""
                INSERT INTO faaliyetler (faaliyet_adi, puan, aktif_mi) VALUES
                    (%s, 8, TRUE), (%s, 5, FALSE)
                RETURNING faaliyet_id
            """, (f"QA Seminer {etiket}", f"QA Pasif {etiket}"))
            aktif_faaliyet, pasif_faaliyet = [r[0] for r in cur.fetchall()]

            cur.execute("""
                INSERT INTO ogrenci_faaliyet_takip (ogrenci_id, faaliyet_id, birim_id, adet, faaliyet_tarihi, kayit_puani)
                VALUES (%s, %s, %s, 3, CURRENT_DATE, 8) RETURNING takip_id
            """, (ogrenci_id, aktif_faaliyet, birim_id))
            takip_id = cur.fetchone()[0]

            cur.execute("SAVEPOINT test_verisi_hazir")

        with patch("server.sunucu.psycopg2.connect", return_value=SahteBaglanti(baglanti)):
            yield {
                "conn": baglanti, "etiket": etiket, "kullanici_id": kullanici[0], "ogrenci_id": ogrenci_id,
                "birim_id": birim_id, "aktif_faaliyet": aktif_faaliyet, "pasif_faaliyet": pasif_faaliyet,
                "takip_id": takip_id,
            }
    finally:
        baglanti.rollback()
        baglanti.close()


def son_denetim(ortam, tablo, kayit_id):
    with ortam["conn"].cursor() as cur:
        cur.execute("""
            SELECT olay_turu, ayrinti FROM denetim_kayitlari
            WHERE hedef_tablo = %s AND hedef_kayit_id IS NOT DISTINCT FROM %s
            ORDER BY denetim_id DESC LIMIT 1
        """, (tablo, kayit_id))
        return cur.fetchone()


# ------------------------------------------------------------------ danışma masası görev süresi
def _gecmis(saat_once, sure_saat, dakika=0):
    bitis = (datetime.now() - timedelta(hours=saat_once)).replace(second=0, microsecond=0)
    return bitis - timedelta(hours=sure_saat, minutes=dakika), bitis


def test_on_saatten_uzun_gorev_eklenemez_on_saatlik_eklenir(ortam):
    bas, bit = _gecmis(24 * 60, 24 * 45)                                     # 45 günlük hatalı kayıt
    with pytest.raises(HTTPException) as hata:
        danisma_yonetim_oturum_olustur(
            DanismaGorevOlusturModeli(ogrenci_id=ortam["ogrenci_id"], baslangic_zamani=bas, bitis_zamani=bit),
            ortam["kullanici_id"])
    assert hata.value.status_code == 422 and "en fazla 10 saat" in hata.value.detail

    bas, bit = _gecmis(30, 10, dakika=1)                                       # 10 saat 1 dakika
    with pytest.raises(HTTPException) as hata:
        danisma_yonetim_oturum_olustur(
            DanismaGorevOlusturModeli(ogrenci_id=ortam["ogrenci_id"], baslangic_zamani=bas, bitis_zamani=bit),
            ortam["kullanici_id"])
    assert hata.value.status_code == 422

    bas, bit = _gecmis(30, 10)                                                 # tam mesai: kabul
    sonuc = danisma_yonetim_oturum_olustur(
        DanismaGorevOlusturModeli(ogrenci_id=ortam["ogrenci_id"], baslangic_zamani=bas, bitis_zamani=bit),
        ortam["kullanici_id"])
    assert sonuc["durum"] == "basarili"


def test_gorev_duzenlemede_sinir_ve_onceki_yeni_saatler_denetime_yazilir(ortam):
    bas, bit = _gecmis(30, 3)
    oturum_id = danisma_yonetim_oturum_olustur(
        DanismaGorevOlusturModeli(ogrenci_id=ortam["ogrenci_id"], baslangic_zamani=bas, bitis_zamani=bit),
        ortam["kullanici_id"])["oturum_id"]

    with pytest.raises(HTTPException) as hata:
        danisma_yonetim_oturum_duzenle(
            oturum_id, DanismaGorevDuzenleModeli(baslangic_zamani=bit - timedelta(hours=11), bitis_zamani=bit),
            ortam["kullanici_id"])
    assert hata.value.status_code == 422 and "en fazla 10 saat" in hata.value.detail

    yeni_bas = bas - timedelta(hours=1)
    danisma_yonetim_oturum_duzenle(
        oturum_id, DanismaGorevDuzenleModeli(baslangic_zamani=yeni_bas, bitis_zamani=bit), ortam["kullanici_id"])
    olay, ayrinti = son_denetim(ortam, "danisma_masasi_oturumlari", oturum_id)
    assert olay == "UPDATE"
    assert ayrinti["onceki"]["baslangic_zamani"] == bas.isoformat(sep=" ", timespec="minutes")
    assert ayrinti["yeni"]["baslangic_zamani"] == yeni_bas.isoformat(sep=" ", timespec="minutes")
    assert ayrinti["onceki"]["bitis_zamani"] == ayrinti["yeni"]["bitis_zamani"]


def test_bitirilmesi_unutulan_gorev_listede_uzun_gorev_olarak_isaretlenir(ortam):
    bas, bit = _gecmis(50, 30)                                                 # öğrencinin kendi bitirdiği 30 saatlik görev
    with ortam["conn"].cursor() as cur:
        cur.execute("""
            INSERT INTO danisma_masasi_oturumlari (ogrenci_id, baslangic_zamani, bitis_zamani, onaylandi_mi)
            VALUES (%s, %s, %s, FALSE) RETURNING oturum_id
        """, (ortam["ogrenci_id"], bas, bit))
        uzun_id = cur.fetchone()[0]
    bas2, bit2 = _gecmis(10, 4)
    normal_id = danisma_yonetim_oturum_olustur(
        DanismaGorevOlusturModeli(ogrenci_id=ortam["ogrenci_id"], baslangic_zamani=bas2, bitis_zamani=bit2),
        ortam["kullanici_id"])["oturum_id"]

    oturumlar = {o["oturum_id"]: o for o in danisma_yonetim_oturumlari(ortam["kullanici_id"])["oturumlar"]}
    assert oturumlar[uzun_id]["uzun_gorev"] is True
    assert oturumlar[normal_id]["uzun_gorev"] is False


def _onayli_gorev(ortam, onayla=True):
    bas, bit = _gecmis(30, 3)
    oturum_id = danisma_yonetim_oturum_olustur(
        DanismaGorevOlusturModeli(ogrenci_id=ortam["ogrenci_id"], baslangic_zamani=bas, bitis_zamani=bit),
        ortam["kullanici_id"])["oturum_id"]
    if onayla:
        danisma_yonetim_oturum_onayla(oturum_id, ortam["kullanici_id"])
    return oturum_id, bas, bit


# Not: hata veren uç nokta işlemi geri aldığı için (testin SAVEPOINT'ine döner) hata beklenen adımlar testin sonunda yapılır.
def test_onay_geri_alinabilir_ve_geri_alinan_gorev_yeniden_duzenlenebilir(ortam):
    oturum_id, bas, bit = _onayli_gorev(ortam)
    assert son_denetim(ortam, "danisma_masasi_oturumlari", oturum_id)[1] == {
        "onceki": {"onaylandi_mi": False}, "yeni": {"onaylandi_mi": True}}

    sonuc = danisma_yonetim_onay_geri_al(oturum_id, ortam["kullanici_id"])
    assert sonuc["onaylandi_mi"] is False
    assert son_denetim(ortam, "danisma_masasi_oturumlari", oturum_id)[1] == {
        "onceki": {"onaylandi_mi": True}, "yeni": {"onaylandi_mi": False}}

    danisma_yonetim_oturum_duzenle(                                                         # geri alınınca yeniden düzenlenebilir
        oturum_id, DanismaGorevDuzenleModeli(baslangic_zamani=bas - timedelta(hours=1), bitis_zamani=bit),
        ortam["kullanici_id"])
    danisma_yonetim_oturum_onayla(oturum_id, ortam["kullanici_id"])                         # ve yeniden onaylanabilir


def test_gorev_olusturma_denetim_kaydinda_ogrenci_ve_saatler_bulunur(ortam):
    oturum_id, bas, bit = _onayli_gorev(ortam, onayla=False)
    olay, ayrinti = son_denetim(ortam, "danisma_masasi_oturumlari", oturum_id)
    assert olay == "CREATE"
    assert ayrinti["yeni"] == {
        "ogrenci_id": ortam["ogrenci_id"],
        "baslangic_zamani": bas.isoformat(sep=" ", timespec="minutes"),
        "bitis_zamani": bit.isoformat(sep=" ", timespec="minutes"),
    }


def test_onaysiz_gorevin_onayi_geri_alinamaz(ortam):
    oturum_id, _, _ = _onayli_gorev(ortam, onayla=False)
    with pytest.raises(HTTPException) as hata:
        danisma_yonetim_onay_geri_al(oturum_id, ortam["kullanici_id"])
    assert hata.value.status_code == 409


def test_olmayan_gorevin_onayi_geri_alinamaz(ortam):
    with pytest.raises(HTTPException) as hata:
        danisma_yonetim_onay_geri_al(99999999, ortam["kullanici_id"])
    assert hata.value.status_code == 404


def test_onayli_gorev_duzenlenemez_ve_mesaj_geri_almayi_soyler(ortam):
    oturum_id, bas, bit = _onayli_gorev(ortam)
    with pytest.raises(HTTPException) as hata:
        danisma_yonetim_oturum_duzenle(
            oturum_id, DanismaGorevDuzenleModeli(baslangic_zamani=bas - timedelta(hours=1), bitis_zamani=bit),
            ortam["kullanici_id"])
    assert hata.value.status_code == 409 and "onayı geri alın" in hata.value.detail


def test_gorev_yalniz_danisma_masasi_ogrencisine_eklenir_ve_liste_yalniz_onlari_getirir(ortam):
    with ortam["conn"].cursor() as cur:
        cur.execute("""
            INSERT INTO ogrenciler (ad_soyad, ogrenci_numarasi, tur)
            VALUES (%s, %s, 'GONULLU') RETURNING ogrenci_id
        """, (f"QA Gonullu {ortam['etiket']}", f"QG{ortam['etiket']}"))
        gonullu_id = cur.fetchone()[0]

    bas, bit = _gecmis(30, 2)
    with pytest.raises(HTTPException) as hata:
        danisma_yonetim_oturum_olustur(
            DanismaGorevOlusturModeli(ogrenci_id=gonullu_id, baslangic_zamani=bas, bitis_zamani=bit), ortam["kullanici_id"])
    assert hata.value.status_code == 404 and "danışma masası öğrencisi" in hata.value.detail

    idler = {o["ogrenci_id"] for o in danisma_yonetim_ogrencileri(ortam["kullanici_id"])["ogrenciler"]}
    assert ortam["ogrenci_id"] in idler and gonullu_id not in idler


def test_yonetim_listesi_gercek_sayilari_verir_ve_eski_onay_bekleyen_gorev_kaybolmaz(ortam):
    with ortam["conn"].cursor() as cur:
        eski = datetime.now() - timedelta(days=900)
        cur.execute("""
            INSERT INTO danisma_masasi_oturumlari (ogrenci_id, baslangic_zamani, bitis_zamani, onaylandi_mi)
            VALUES (%s, %s, %s, FALSE) RETURNING oturum_id
        """, (ortam["ogrenci_id"], eski, eski + timedelta(hours=2)))
        eski_bekleyen = cur.fetchone()[0]
        for gun in range(1, 4):                                                # sınırı aşacak kadar yeni onaylı kayıt yerine: sayı denetimi
            cur.execute("""
                INSERT INTO danisma_masasi_oturumlari (ogrenci_id, baslangic_zamani, bitis_zamani, onaylandi_mi)
                VALUES (%s, %s, %s, TRUE)
            """, (ortam["ogrenci_id"], datetime.now() - timedelta(days=gun + 1),
                  datetime.now() - timedelta(days=gun + 1) + timedelta(hours=1)))

    with patch("server.sunucu.DANISMA_LISTE_EN_FAZLA", 2):                     # liste yalnızca en yeni 2 kaydı almaya zorlanır
        veri = danisma_yonetim_oturumlari(ortam["kullanici_id"])
    kimlikler = {o["oturum_id"] for o in veri["oturumlar"]}
    assert eski_bekleyen in kimlikler                                          # 900 gün önceki onay bekleyen görev yine de gelir
    assert veri["ozet"]["toplam"] == veri["toplam_kayit"] >= 4 and veri["ozet"]["onaylanan"] >= 3
    assert veri["ozet"]["bekleyen"] >= 1
    assert all("calisilan_sure" not in o for o in veri["oturumlar"])


# ------------------------------------------------------------------ faaliyet kaydı
def test_faaliyet_kaydi_pasif_ture_gecemez_ve_mesaj_dogrudur(ortam):
    with pytest.raises(HTTPException) as hata:
        faaliyet_kaydi_guncelle(
            ortam["takip_id"],
            FaaliyetKayitModeli(ogrenci_id=ortam["ogrenci_id"], faaliyet_id=ortam["pasif_faaliyet"],
                                birim_id=ortam["birim_id"], miktar=3),
            ortam["kullanici_id"])
    assert hata.value.status_code == 400 and hata.value.detail == "Aktif faaliyet türü bulunamadı."


def test_faaliyet_kaydi_duzenlemesi_yalnizca_degisen_alanlari_denetime_yazar(ortam):
    faaliyet_kaydi_guncelle(
        ortam["takip_id"],
        FaaliyetKayitModeli(ogrenci_id=ortam["ogrenci_id"], faaliyet_id=ortam["aktif_faaliyet"],
                            birim_id=ortam["birim_id"], miktar=5),
        ortam["kullanici_id"])
    olay, ayrinti = son_denetim(ortam, "ogrenci_faaliyet_takip", ortam["takip_id"])
    assert olay == "UPDATE"
    assert ayrinti == {"onceki": {"adet": 3}, "yeni": {"adet": 5}}

    sonuc = faaliyet_kaydi_guncelle(                                           # aynı değerler: kayıt ve denetim yok
        ortam["takip_id"],
        FaaliyetKayitModeli(ogrenci_id=ortam["ogrenci_id"], faaliyet_id=ortam["aktif_faaliyet"],
                            birim_id=ortam["birim_id"], miktar=5),
        ortam["kullanici_id"])
    assert sonuc["mesaj"] == "Kayıtta değişiklik yapılmadı."


# ------------------------------------------------------------------ faaliyet türü
def test_faaliyet_turu_adi_buyuk_kucuk_harf_farkiyla_tekrar_eklenemez(ortam):
    ad = f"QA Seminer {ortam['etiket']}"
    for deneme in (ad.lower(), ad.upper(), f"  {ad}  "):
        with pytest.raises(HTTPException) as hata:
            faaliyet_turu_ekle(FaaliyetTuruEkleModeli(faaliyet_adi=deneme, puan=3), ortam["kullanici_id"])
        assert hata.value.status_code == 409

    with pytest.raises(HTTPException) as hata:                                 # başka bir türü bu ada çevirmek de olmaz
        faaliyet_turu_duzenle(
            ortam["pasif_faaliyet"], FaaliyetTuruDuzenleModeli(faaliyet_adi=ad.lower(), puan=5,
                                                               gecmis_puanlari_guncelle=False),
            ortam["kullanici_id"])
    assert hata.value.status_code in (404, 409)                                # pasif tür düzenlenemez (404)

    sonuc = faaliyet_turu_duzenle(                                             # kendi adının harf düzeltmesi serbest
        ortam["aktif_faaliyet"], FaaliyetTuruDuzenleModeli(faaliyet_adi=ad.upper(), puan=8,
                                                           gecmis_puanlari_guncelle=False),
        ortam["kullanici_id"])
    assert sonuc["durum"] == "basarili"


def test_faaliyet_puani_degisince_denetimde_onceki_yeni_ve_etkilenen_sayi_var(ortam):
    ad = f"QA Seminer {ortam['etiket']}"
    faaliyet_turu_duzenle(
        ortam["aktif_faaliyet"], FaaliyetTuruDuzenleModeli(faaliyet_adi=ad, puan=12, gecmis_puanlari_guncelle=True),
        ortam["kullanici_id"])
    olay, ayrinti = son_denetim(ortam, "faaliyetler", ortam["aktif_faaliyet"])
    assert olay == "UPDATE"
    assert ayrinti["onceki"] == {"puan": 8} and ayrinti["yeni"] == {"puan": 12}
    assert ayrinti["gecmis_kayitlara_uygulandi"] is True and ayrinti["guncellenen_gecmis_kayit"] == 1

    _, toplu = son_denetim(ortam, "ogrenci_faaliyet_takip", None)
    assert toplu["faaliyet_id"] == ortam["aktif_faaliyet"] and toplu["etkilenen_kayit"] == 1


# ------------------------------------------------------------------ öğrenci aktifliği
def test_ogrenci_aktifligi_onceki_ve_yeni_durumla_denetime_yazilir(ortam):
    with ortam["conn"].cursor() as cur:                                       # danışma masası öğrencileri bu ekrandan pasife alınamaz
        cur.execute("UPDATE ogrenciler SET tur = 'GONULLU' WHERE ogrenci_id = %s", (ortam["ogrenci_id"],))
    ogrenci_aktiflik_duzenle(ortam["ogrenci_id"], OgrenciAktiflikModeli(aktif_mi=False), ortam["kullanici_id"])
    olay, ayrinti = son_denetim(ortam, "ogrenciler", ortam["ogrenci_id"])
    assert olay == "UPDATE"
    assert ayrinti == {"onceki": {"aktif_mi": True}, "yeni": {"aktif_mi": False}}
