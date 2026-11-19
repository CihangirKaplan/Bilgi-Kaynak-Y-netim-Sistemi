"""Gerçek PostgreSQL: raporlar arası tutarlılık.

Aynı veriyi farklı raporlar sorduğunda aynı sayıyı vermelidir (hocaların/yöneticilerin raporları karşılaştırdığında çelişki
görmemesi için). Test, başka verilerden etkilenmemek için 2001 yılına ait özel bir dönem kullanır ve işi bitince verisini siler.
"""
import os
from datetime import date, datetime
from uuid import uuid4

import psycopg2
import pytest

from server.sunucu import (
    VT_AYARLARI,
    cihaz_raporlari,
    cihaz_rezervasyon_raporu,
    oda_kullanim_raporu,
    yetki_raporu_getir,
    puan_raporu,
    randevu_raporu,
    yonetim_cihaz_ozet,
    yonetim_kullanim_ozet,
    yonetim_ogrenci_ozet,
    yonetim_proje_etkinlik_ozet,
    yonetim_randevu_ozet,
)

BAS, BIT = date(2001, 3, 1), date(2001, 3, 31)


@pytest.fixture
def veri():
    assert os.getenv("TKYS_PG_TEST_ONAY") == "EVET"
    assert VT_AYARLARI["dbname"] == "crkys_alembic_test"
    conn = psycopg2.connect(**VT_AYARLARI)
    conn.autocommit = True
    c = conn.cursor()
    etiket = uuid4().hex[:8]
    kimlikler = {}

    c.execute("INSERT INTO kullanicilar (kullanici_adi, parola_hash, rol_id) VALUES (%s, 'x', "
              "(SELECT rol_id FROM roller WHERE rol_adi = 'PSIKOLOG')) RETURNING kullanici_id", (f"rt_{etiket}",))
    kimlikler["kullanici"] = c.fetchone()[0]
    c.execute("INSERT INTO personel (kullanici_id, personel_kodu) VALUES (%s, %s) RETURNING personel_id", (kimlikler["kullanici"], f"RT-{etiket}"))
    kimlikler["personel"] = c.fetchone()[0]
    c.execute("INSERT INTO odalar (oda_adi) VALUES (%s) RETURNING oda_id", (f"rt_oda_{etiket}",))
    kimlikler["oda"] = c.fetchone()[0]
    c.execute("INSERT INTO danisan_kodlari (danisan_kod_id) VALUES (%s)", (f"RT-{etiket}",))
    kimlikler["kod"] = f"RT-{etiket}"
    c.execute("INSERT INTO cihazlar (envanter_kodu, cihaz_adi) VALUES (%s, 'rt cihaz') RETURNING cihaz_id", (f"RT-{etiket}",))
    kimlikler["cihaz"] = c.fetchone()[0]

    # Randevular: her durumdan bir tane + dönem dışı bir tane
    for gun, durum, neden in [(2, "PLANLANDI", None), (3, "TAMAMLANDI", None), (4, "GELMEDI", None), (5, "IPTAL_EDILDI", "DANISAN_TALEBI")]:
        c.execute("INSERT INTO randevular (danisan_kod_id, psikolog_id, oda_id, baslangic_zamani, bitis_zamani, durum, iptal_nedeni) "
                  "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                  (kimlikler["kod"], kimlikler["personel"], kimlikler["oda"], datetime(2001, 3, gun, 10), datetime(2001, 3, gun, 11), durum, neden))
    c.execute("INSERT INTO randevular (danisan_kod_id, psikolog_id, oda_id, baslangic_zamani, bitis_zamani, durum) VALUES (%s, %s, %s, %s, %s, 'TAMAMLANDI')",
              (kimlikler["kod"], kimlikler["personel"], kimlikler["oda"], datetime(2001, 4, 2, 10), datetime(2001, 4, 2, 11)))

    # Cihaz: kalibrasyon dönemde yapıldı ama kayıt BUGÜN girildi (islem_tarihi bugün); 2 rezervasyon (1'i iptal) + 1 bakım + 1 arıza
    c.execute("INSERT INTO cihaz_kalibrasyonlari (cihaz_id, kalibrasyon_yapan_kurum, kalibrasyon_baslangic_tarihi, kalibrasyon_bitis_tarihi, gecerlilik_tarihi) "
              "VALUES (%s, 'kurum', '2001-03-10', '2001-03-10', '2002-03-10')", (kimlikler["cihaz"],))
    for gun, iptal in [(6, False), (7, True)]:
        c.execute("INSERT INTO cihaz_rezervasyonlari (cihaz_id, baslangic_zamani, bitis_zamani, iptal_edildi_mi) VALUES (%s, %s, %s, %s)",
                  (kimlikler["cihaz"], datetime(2001, 3, gun, 9), datetime(2001, 3, gun, 10), iptal))
    c.execute("INSERT INTO cihaz_bakimlari (cihaz_id, bakim_yapan_kisi, maliyet, bakim_tarihi) VALUES (%s, 'x', 100, '2001-03-12')", (kimlikler["cihaz"],))
    c.execute("INSERT INTO cihaz_arizalari (cihaz_id, ariza_baslik, ariza_aciklamasi, bildirim_tarihi) VALUES (%s, 'b', 'a', '2001-03-13')", (kimlikler["cihaz"],))

    # Öğrenci faaliyeti: puan 5 x adet 3 = 15 (onaysız), 2 x 2 = 4 (onaylı)
    c.execute("INSERT INTO ogrenciler (ad_soyad, ogrenci_numarasi, tur) VALUES (%s, %s, 'GONULLU') RETURNING ogrenci_id", (f"RT Ogr {etiket}", f"RT{etiket}"))
    kimlikler["ogrenci"] = c.fetchone()[0]
    c.execute("INSERT INTO faaliyetler (faaliyet_adi, puan) VALUES (%s, 5) RETURNING faaliyet_id", (f"rt faaliyet {etiket}",))
    kimlikler["faaliyet"] = c.fetchone()[0]
    c.execute("SELECT birim_id FROM faaliyet_birimleri LIMIT 1")
    satir = c.fetchone()
    if satir is None:
        c.execute("INSERT INTO faaliyet_birimleri (birim_adi) VALUES (%s) RETURNING birim_id", (f"RT BIRIM {etiket}",))
        satir = c.fetchone()
        kimlikler["birim_olusturuldu"] = satir[0]
    for adet, puan, onay, gun in [(3, 5, False, 8), (2, 2, True, 9)]:
        c.execute("INSERT INTO ogrenci_faaliyet_takip (ogrenci_id, faaliyet_id, adet, birim_id, faaliyet_tarihi, onaylandi_mi, kayit_puani) "
                  "VALUES (%s, %s, %s, %s, %s, %s, %s)", (kimlikler["ogrenci"], kimlikler["faaliyet"], adet, satir[0], date(2001, 3, gun), onay, puan))
    yield kimlikler

    c.execute("DELETE FROM ogrenci_faaliyet_takip WHERE ogrenci_id = %s", (kimlikler["ogrenci"],))
    c.execute("DELETE FROM faaliyetler WHERE faaliyet_id = %s", (kimlikler["faaliyet"],))
    if "birim_olusturuldu" in kimlikler:
        c.execute("DELETE FROM faaliyet_birimleri WHERE birim_id = %s", (kimlikler["birim_olusturuldu"],))
    c.execute("DELETE FROM ogrenciler WHERE ogrenci_id = %s", (kimlikler["ogrenci"],))
    for tablo in ("cihaz_arizalari", "cihaz_bakimlari", "cihaz_kalibrasyonlari", "cihaz_rezervasyonlari"):
        c.execute(f"DELETE FROM {tablo} WHERE cihaz_id = %s", (kimlikler["cihaz"],))
    c.execute("DELETE FROM cihazlar WHERE cihaz_id = %s", (kimlikler["cihaz"],))
    c.execute("DELETE FROM randevular WHERE danisan_kod_id = %s", (kimlikler["kod"],))
    c.execute("DELETE FROM danisan_kodlari WHERE danisan_kod_id = %s", (kimlikler["kod"],))
    c.execute("DELETE FROM odalar WHERE oda_id = %s", (kimlikler["oda"],))
    c.execute("DELETE FROM personel WHERE personel_id = %s", (kimlikler["personel"],))
    c.execute("DELETE FROM kullanicilar WHERE kullanici_id = %s", (kimlikler["kullanici"],))
    conn.close()


def test_randevu_raporu_ile_yonetim_randevu_ozeti_ayni_sayilari_verir(veri):
    rapor = randevu_raporu(baslangic=BAS, bitis=BIT, psikolog_id=veri["personel"], kullanici_id=0)["ozet"]
    yonetim = yonetim_randevu_ozet(baslangic=BAS, bitis=BIT, kullanici_id=0)["ozet"]
    assert (rapor["toplam"], rapor["planlandi"], rapor["tamamlandi"], rapor["gelmedi"], rapor["iptal_edildi"]) == (4, 1, 1, 1, 1)
    assert (yonetim["toplam"], yonetim["planlandi"], yonetim["tamamlandi"], yonetim["gelmedi"], yonetim["iptal_edildi"]) == (4, 1, 1, 1, 1)
    assert rapor["tamamlanma_orani"] == 0.5 and rapor["gelmeme_orani"] == 0.5      # iptal ve planlı oranlara girmez


def test_kalibrasyon_sayisi_cihaz_raporu_ve_yonetim_raporunda_ayni(veri):
    """Kalibrasyon dönemde yapıldı, kayıt bugün girildi: iki rapor da kalibrasyonu YAPILDIĞI döneme saymalı."""
    cihaz = cihaz_raporlari(baslangic_tarihi=BAS, bitis_tarihi=BIT, cihaz_id=veri["cihaz"], kullanici_id=0)["ozet"]
    yonetim = yonetim_cihaz_ozet(baslangic=BAS, bitis=BIT, kullanici_id=0)["ozet"]
    assert cihaz["kalibrasyon_sayisi"] == 1
    assert yonetim["kalibrasyon"] >= 1


def test_yonetim_cihaz_ozeti_iptal_edilen_rezervasyonu_saymaz(veri):
    yonetim = yonetim_cihaz_ozet(baslangic=BAS, bitis=BIT, kullanici_id=0)["ozet"]
    assert yonetim["rezervasyon"] == 1                                              # 2 rezervasyondan biri iptal
    proje = yonetim_proje_etkinlik_ozet(baslangic=BAS, bitis=BIT, kullanici_id=0)["ozet"]
    assert proje["rezervasyon_iptal_edilmemis"] == 1 and proje["rezervasyon_iptal"] == 1


def test_puan_toplamlari_puan_raporu_ve_yonetim_raporunda_ayni(veri):
    rapor = puan_raporu(baslangic=BAS, bitis=BIT, tur=None, durum=None, puansizlari_goster=False, detay=False, yetkili_id=0)
    satir = next(o for o in rapor["ogrenciler"] if o["ogrenci_id"] == veri["ogrenci"])
    assert satir["toplam_puan"] == 3 * 5 + 2 * 2 == 19
    yonetim = yonetim_ogrenci_ozet(baslangic=BAS, bitis=BIT, kullanici_id=0)["ozet"]
    assert yonetim["toplam_puan"] == 19 and yonetim["onayli_puan"] == 4
    assert yonetim["kayit_sayisi"] == 2 and yonetim["faaliyet_yapan_ogrenci"] == 1


def test_kullanim_raporu_saatleri_iptali_saymaz_ve_donem_sinirina_kirpar(veri):
    """Oda: 3 iptal edilmeyen randevu x 1 saat. Cihaz: 1 iptal edilmeyen rezervasyon (1 sa) + dönemi aşan bir rezervasyon
    (28 Şubat 23:00 - 1 Mart 02:00: yalnızca Mart'a düşen 2 saat sayılır); iptal edilen sayılmaz ama ayrıca gösterilir."""
    conn = psycopg2.connect(**VT_AYARLARI)
    conn.autocommit = True
    c = conn.cursor()
    c.execute("INSERT INTO cihaz_rezervasyonlari (cihaz_id, baslangic_zamani, bitis_zamani) VALUES (%s, '2001-02-28 23:00', '2001-03-01 02:00')",
              (veri["cihaz"],))
    c.execute("INSERT INTO cihaz_rezervasyonlari (cihaz_id, kullanilacak_oda_id, baslangic_zamani, bitis_zamani) VALUES (%s, %s, '2001-03-20 09:00', '2001-03-20 12:00')",
              (veri["cihaz"], veri["oda"]))
    conn.close()

    sonuc = yonetim_kullanim_ozet(baslangic=BAS, bitis=BIT, kullanici_id=0)
    oda = next(o for o in sonuc["odalar"] if o["oda_id"] == veri["oda"])
    assert (oda["randevu_sayisi"], oda["randevu_saati"]) == (3, 3.0)               # iptal edilen randevu sayılmaz
    assert (oda["cihaz_rezervasyon_sayisi"], oda["cihaz_rezervasyon_saati"]) == (1, 3.0)
    assert oda["toplam_saat"] == 6.0

    cihaz = next(x for x in sonuc["cihazlar"] if x["cihaz_id"] == veri["cihaz"])
    assert cihaz["rezervasyon_sayisi"] == 3                                        # 6 Mart, 20 Mart ve dönemi aşan; 7 Mart iptal
    assert cihaz["rezervasyon_saati"] == 1.0 + 2.0 + 3.0                           # aşan rezervasyonun yalnızca Mart'a düşen 2 saati
    assert cihaz["iptal_edilen_rezervasyon"] == 1 and cihaz["ariza_sayisi"] == 1


def test_kullanim_raporu_tarih_dogrulamasi(veri):
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as hata:
        yonetim_kullanim_ozet(baslangic=BIT, bitis=BAS, kullanici_id=0)
    assert hata.value.status_code == 422
    with pytest.raises(HTTPException) as hata:
        yonetim_kullanim_ozet(baslangic=date(2000, 1, 1), bitis=date(2001, 12, 31), kullanici_id=0)
    assert hata.value.status_code == 422


# ------------------------------------------------------------------ ayrıntılı rapor sayfaları (uç noktalar)
def test_cihaz_rezervasyon_raporu_iptali_saymaz_ve_detayda_durumu_gosterir(veri):
    sonuc = cihaz_rezervasyon_raporu(baslangic=BAS, bitis=BIT, cihaz_id=veri["cihaz"], proje_turu=None, detay=True, kullanici_id=0)
    assert sonuc["ozet"]["rezervasyon_sayisi"] == 1 and sonuc["ozet"]["iptal_edilen_rezervasyon"] == 1
    assert sonuc["ozet"]["toplam_saat"] == 1.0 and sonuc["ozet"]["ortalama_sure_saat"] == 1.0
    assert [c["cihaz_id"] for c in sonuc["cihazlar"]] == [veri["cihaz"]]
    assert sonuc["proje_turleri"][0]["ad"] == "Belirtilmemiş" and sonuc["bolumler"][0]["rezervasyon_sayisi"] == 1
    assert sorted(r["durum"] for r in sonuc["rezervasyonlar"]) == ["Aktif", "İptal"]
    assert "parola" not in str(sonuc).lower()


def test_cihaz_rezervasyon_raporu_proje_turu_suzgeci_ve_dogrulama(veri):
    from fastapi import HTTPException
    bos = cihaz_rezervasyon_raporu(baslangic=BAS, bitis=BIT, cihaz_id=veri["cihaz"], proje_turu="TÜBİTAK", detay=False, kullanici_id=0)
    assert bos["ozet"]["rezervasyon_sayisi"] == 0 and bos["ozet"]["ortalama_sure_saat"] is None
    for kwargs in ({"baslangic": BIT, "bitis": BAS}, {"baslangic": date(2000, 1, 1), "bitis": date(2001, 12, 31)}):
        with pytest.raises(HTTPException) as hata:
            cihaz_rezervasyon_raporu(cihaz_id=None, proje_turu=None, detay=False, kullanici_id=0, **kwargs)
        assert hata.value.status_code == 422
    with pytest.raises(HTTPException):
        cihaz_rezervasyon_raporu(baslangic=BAS, bitis=BIT, cihaz_id=0, proje_turu=None, detay=False, kullanici_id=0)


def test_oda_kullanim_raporu_doluluk_gun_dagilimi_ve_detay(veri):
    sonuc = oda_kullanim_raporu(baslangic=BAS, bitis=BIT, oda_id=veri["oda"], detay=True, kullanici_id=0)
    assert [o["oda_id"] for o in sonuc["odalar"]] == [veri["oda"]]
    oda = sonuc["odalar"][0]
    assert oda["randevu_saati"] == 3.0 and oda["toplam_saat"] == 3.0
    assert sonuc["varsayim"]["is_gunu_sayisi"] == 22                                # Mart 2001: 22 hafta içi gün
    assert oda["mesai_doluluk_orani"] == pytest.approx(3.0 / (22 * 8), abs=1e-4)
    gunler = {g["gun"]: g for g in sonuc["gun_dagilimi"]}
    assert (gunler["Cuma"]["saat"], gunler["Cumartesi"]["saat"], gunler["Pazar"]["saat"], gunler["Pazartesi"]["saat"]) == (1.0, 1.0, 1.0, 0.0)
    assert len(sonuc["kayitlar"]) == 3 and all(k["tur"] == "Randevu" for k in sonuc["kayitlar"])   # iptal edilen yok
    assert any(x["oda_id"] == veri["oda"] for x in sonuc["oda_secenekleri"])             # süzgeç listesi tüm aktif odaları içerir


def test_oda_kullanim_raporu_tum_odalar_ozeti_tutarli(veri):
    sonuc = oda_kullanim_raporu(baslangic=BAS, bitis=BIT, oda_id=None, detay=False, kullanici_id=0)
    assert sonuc["ozet"]["toplam_saat"] == round(sum(o["toplam_saat"] for o in sonuc["odalar"]), 1)
    assert "kayitlar" not in sonuc
    yonetim = yonetim_kullanim_ozet(baslangic=BAS, bitis=BIT, kullanici_id=0)
    assert yonetim["ozet"]["oda_toplam_saat"] == sonuc["ozet"]["toplam_saat"]       # iki rapor aynı toplamı verir


def test_yetki_raporu_kullanici_rol_ve_matris_parola_icermez(veri):
    sonuc = yetki_raporu_getir(rol_id=None, durum=None, detay=True, kullanici_id=0)
    satir = next(k for k in sonuc["kullanicilar"] if k["kullanici_id"] == veri["kullanici"])
    assert satir["rol_adi"] == "PSIKOLOG" and satir["aktif_mi"] is True and satir["son_giris"] is None
    assert sonuc["ozet"]["kullanici_sayisi"] == len(sonuc["kullanicilar"]) and sonuc["ozet"]["hic_giris_yapmamis"] >= 1
    assert {r["rol_adi"] for r in sonuc["roller"]} >= {"ADMIN", "PSIKOLOG"}
    assert sonuc["matris"]["izinler"] and set(sonuc["matris"]["roller"]) >= {"ADMIN", "PSIKOLOG"}
    assert "parola_hash" not in str(sonuc) and "$2" not in str(sonuc)               # parola özeti sızmaz
    pasif = yetki_raporu_getir(rol_id=None, durum="pasif", detay=False, kullanici_id=0)
    assert all(not k["aktif_mi"] for k in pasif["kullanicilar"]) and "matris" not in pasif
