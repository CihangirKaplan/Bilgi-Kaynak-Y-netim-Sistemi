"""FR-008 Kişisel veri ayrımı (gerçek PostgreSQL şeması).

Gereksinim: operasyonel danışan kodunu gerçek kişiyle eşleştiren kayıt veya tablo bulunmamalıdır.

Bu test CI'daki "PostgreSQL Entegrasyon Testleri" işinde (alembic upgrade head sonrası) çalışır. Biri danışan koduna
bağlı bir tabloya kişisel bir sütun ya da danışan koduna başvuran yeni bir tablo eklerse PR kırmızı olur; ekleyen
kişi bunu bilerek kabul edip aşağıdaki izinli listeleri güncellemek zorunda kalır.
"""

import os
import re

import psycopg2

from server.sunucu import VT_AYARLARI

# Danışan koduyla ilgili tabloların TÜM sütunları (başka sütun eklenirse test kırılır).
IZINLI_SUTUNLAR = {
    "danisan_kodlari": {"danisan_kod_id", "ucretli_mi", "istisna_turu", "aktif_mi", "olusturulma_tarihi",
                        "olusturan_psikolog_id", "yas_grubu",
                        "psikolog_pasifligi_nedeniyle_pasif"},          # durum işareti (boolean): psikolog pasife alınınca kodu pasife alan sürece ait, kişisel veri değil
    "randevular": {"randevu_id", "danisan_kod_id", "psikolog_id", "oda_id", "baslangic_zamani", "bitis_zamani",
                   "durum", "olusturulma_tarihi", "iptal_nedeni", "iptal_notu", "gorusme_tipi", "terapi_turu"},
}
# FR-008 İSTİSNASI (PR2): iptal notu, danışan kodlu tabloda bilinçli olarak açılmış TEK kısa serbest metin alanıdır.
# En çok 100 karakter; arayüz "kişisel bilgi yazmayın" uyarısı verir. Başka bir sütun bu listeye ancak bilerek eklenir.
KISA_SERBEST_METIN_ISTISNALARI = {("randevular", "iptal_notu"): 100}
# FR-008 İSTİSNASI (görüşme/terapi): kapalı listeli (serbest metin OLMAYAN) sütunlar ve izinli değerleri. Veritabanında CHECK
# kısıtıyla sınırlıdır (bkz. test_kapali_liste_sutunlari_check_kisitlidir). "terapi" sözcüğü klinik terim sayıldığı için
# terapi_turu bu listedeki sütunlar adı üzerinden denetimden muaftır; başka bir sütun buraya ancak bilerek eklenir.
KAPALI_LISTE_SUTUNLARI = {
    ("danisan_kodlari", "yas_grubu"): {"COCUK", "YETISKIN"},
    ("randevular", "gorusme_tipi"): {"YUZ_YUZE", "ONLINE"},
    ("randevular", "terapi_turu"): {"OYUN_TERAPISI", "BIREYSEL_TERAPI"},
}
# Danışan koduna başvuran tek tablo randevudur.
DANISAN_KODUNA_BASVURANLAR = {"randevular"}

# Sütun adının parçaları (alt çizgiyle bölünmüş) bunlardan biriyse kişisel/klinik veri sayılır.
KISISEL_PARCALAR = {
    "ad", "adi", "soyad", "soyadi", "tc", "kimlik", "telefon", "tel", "eposta", "email", "mail", "adres", "dogum",
    "tani", "ilac", "terapi", "travma", "aciklama", "not", "notu", "sikayet", "olcek", "gozlem", "saglik",
    "hastalik", "yorum",
}
# Danışan kodunun bağlanabileceği, kişi bilgisi tutan tablolar (öğrenciler ad-soyad ve telefon içerir).
KISI_TABLOLARI = {"ogrenciler", "kullanicilar", "personel"}


def _dogru_veritabani(cursor):
    # Yanlış veritabanında çalışmayı kesinlikle engelle.
    assert os.getenv("TKYS_PG_TEST_ONAY") == "EVET"
    assert VT_AYARLARI["dbname"] == "crkys_alembic_test"
    cursor.execute("SELECT current_database()")
    assert cursor.fetchone()[0] == "crkys_alembic_test"


def _sorgu(cursor, sql, parametre=()):
    cursor.execute(sql, parametre or None)      # parametre yokken % karakterli LIKE kalıpları biçim sanılmasın
    return cursor.fetchall()


def _baglan():
    return psycopg2.connect(**VT_AYARLARI)


def test_danisan_kodlari_ve_randevular_yalnizca_izinli_sutunlari_icerir():
    conn = _baglan()
    try:
        with conn.cursor() as cursor:
            _dogru_veritabani(cursor)
            for tablo, izinli in IZINLI_SUTUNLAR.items():
                sutunlar = {r[0] for r in _sorgu(
                    cursor, "SELECT column_name FROM information_schema.columns "
                            "WHERE table_schema = 'public' AND table_name = %s", (tablo,))}
                assert sutunlar, f"{tablo} tablosu bulunamadı"
                assert sutunlar == izinli, (
                    f"{tablo} sütunları değişti. Fazla: {sorted(sutunlar - izinli)}, eksik: {sorted(izinli - sutunlar)}. "
                    "Danışan kodunu kişiyle eşleştirebilecek sütun eklemeyin (FR-008)."
                )
    finally:
        conn.close()


def test_izinli_sutunlarin_hicbiri_kisisel_veri_adi_tasimaz():
    """İzinli liste yanlışlıkla kişisel bir sütunla genişletilirse yakalanır."""
    for tablo, sutunlar in IZINLI_SUTUNLAR.items():
        for sutun in sutunlar:
            if (tablo, sutun) in KISA_SERBEST_METIN_ISTISNALARI or (tablo, sutun) in KAPALI_LISTE_SUTUNLARI:
                continue
            parcalar = set(sutun.split("_"))
            assert not (parcalar & KISISEL_PARCALAR), f"{tablo}.{sutun} kişisel veri gibi görünüyor"


def test_danisan_koduna_yalnizca_randevu_tablosu_basvurur():
    conn = _baglan()
    try:
        with conn.cursor() as cursor:
            _dogru_veritabani(cursor)
            fk_veren = {r[0] for r in _sorgu(
                cursor, "SELECT conrelid::regclass::text FROM pg_constraint "
                        "WHERE contype = 'f' AND confrelid = 'danisan_kodlari'::regclass")}
            assert fk_veren == DANISAN_KODUNA_BASVURANLAR, (
                f"danisan_kodlari'na başvuran tablolar değişti: {sorted(fk_veren)}. Yeni bir tablo danışan koduna "
                "bağlanıyorsa içinde kişi bilgisi olmadığını doğrulayıp bu listeyi bilerek güncelleyin."
            )
            # Sütun adında 'danisan' geçen başka tablo da olmamalı (FK olmadan eşleştirme yapılmasın).
            danisanli = {r[0] for r in _sorgu(
                cursor, "SELECT DISTINCT table_name FROM information_schema.columns "
                        "WHERE table_schema = 'public' AND column_name ILIKE '%danisan%'")}
            assert danisanli == set(IZINLI_SUTUNLAR), f"'danisan' sütunu içeren tablolar: {sorted(danisanli)}"
    finally:
        conn.close()


def test_danisan_tablolari_kisi_tablolariyla_dogrudan_baglanmaz_yalniz_psikolog_atamasi_vardir():
    """danisan_kodlari -> kullanicilar(personel_id) yalnızca kodu OLUŞTURAN psikologu gösterir (danışanı değil).

    Personel ve kullanıcı tek tabloda birleşti (`personel` artık bir görünüm); bağlantı personel_id sütunu üzerindendir."""
    conn = _baglan()
    try:
        with conn.cursor() as cursor:
            _dogru_veritabani(cursor)
            giden = _sorgu(
                cursor, "SELECT a.attname, confrelid::regclass::text FROM pg_constraint c "
                        "JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey) "
                        "WHERE c.contype = 'f' AND c.conrelid = 'danisan_kodlari'::regclass")
            assert giden == [("olusturan_psikolog_id", "kullanicilar")]
            hedef_sutun = _sorgu(
                cursor, "SELECT a.attname FROM pg_constraint c JOIN pg_attribute a ON a.attrelid = c.confrelid AND a.attnum = ANY (c.confkey) "
                        "WHERE c.contype = 'f' AND c.conrelid = 'danisan_kodlari'::regclass")
            assert [r[0] for r in hedef_sutun] == ["personel_id"]          # kullanıcı kimliğine değil, personel kimliğine bağlıdır

            # Hiçbir kişi tablosu (öğrenci, kullanıcı, personel) danışan koduna sütunla başvurmaz.
            for tablo in KISI_TABLOLARI:
                sutunlar = {r[0] for r in _sorgu(
                    cursor, "SELECT column_name FROM information_schema.columns "
                            "WHERE table_schema = 'public' AND table_name = %s", (tablo,))}
                assert not any("danisan" in s for s in sutunlar), f"{tablo} danışan koduna başvuruyor"
            # randevular da öğrenci tablosuna değil yalnızca psikologa (kullanicilar.personel_id) ve odaya bağlanır.
            hedefler = {r[0] for r in _sorgu(
                cursor, "SELECT confrelid::regclass::text FROM pg_constraint "
                        "WHERE contype = 'f' AND conrelid = 'randevular'::regclass")}
            assert hedefler == {"danisan_kodlari", "kullanicilar", "odalar"}
            psikolog_baglantisi = [r[0] for r in _sorgu(
                cursor, "SELECT fa.attname FROM pg_constraint c JOIN pg_attribute fa ON fa.attrelid = c.confrelid AND fa.attnum = ANY (c.confkey) "
                        "WHERE c.contype = 'f' AND c.conrelid = 'randevular'::regclass AND c.confrelid = 'kullanicilar'::regclass")]
            assert psikolog_baglantisi == ["personel_id"]                   # hesaba (kullanici_id) değil, personel kimliğine bağlıdır
    finally:
        conn.close()


def test_danisan_tablolarinda_serbest_metin_sutunu_yok_metin_sutunlari_kisa_siniri_olan_kodlardir():
    """Serbest danışan açıklaması girilebilecek uzun/sınırsız metin sütunu bulunmamalı."""
    conn = _baglan()
    try:
        with conn.cursor() as cursor:
            _dogru_veritabani(cursor)
            for tablo in IZINLI_SUTUNLAR:
                for sutun, tur, uzunluk in _sorgu(
                        cursor, "SELECT column_name, data_type, character_maximum_length FROM information_schema.columns "
                                "WHERE table_schema = 'public' AND table_name = %s", (tablo,)):
                    assert tur not in ("text", "json", "jsonb", "xml", "bytea"), f"{tablo}.{sutun} serbest içerik tutabilir"
                    if tur == "character varying":
                        sinir = KISA_SERBEST_METIN_ISTISNALARI.get((tablo, sutun), 50)
                        assert uzunluk is not None and uzunluk <= sinir, f"{tablo}.{sutun} uzun metin tutabilir ({uzunluk})"
    finally:
        conn.close()


def test_hicbir_tabloda_danisan_koduyla_birlikte_kisisel_sutun_yok():
    """Genel koruma: 'danisan' sütunu olan HERHANGİ bir tabloda kişisel/klinik sütun olmamalı."""
    conn = _baglan()
    try:
        with conn.cursor() as cursor:
            _dogru_veritabani(cursor)
            tablolar = {r[0] for r in _sorgu(
                cursor, "SELECT DISTINCT table_name FROM information_schema.columns "
                        "WHERE table_schema = 'public' AND column_name ILIKE '%danisan%'")}
            for tablo in tablolar:
                for (sutun,) in _sorgu(cursor, "SELECT column_name FROM information_schema.columns "
                                               "WHERE table_schema = 'public' AND table_name = %s", (tablo,)):
                    if (tablo, sutun) in KISA_SERBEST_METIN_ISTISNALARI or (tablo, sutun) in KAPALI_LISTE_SUTUNLARI:
                        continue
                    assert not (set(re.split(r"_", sutun)) & KISISEL_PARCALAR), f"{tablo}.{sutun}"
    finally:
        conn.close()


def test_serbest_metin_istisnasi_yalnizca_iptal_notu_ve_siniri_ayni():
    """Danışan kodlu tablolarda kısa serbest metne yalnızca iptal notu için izin var; veritabanındaki sınır beklenenle aynı."""
    assert KISA_SERBEST_METIN_ISTISNALARI == {("randevular", "iptal_notu"): 100}
    conn = _baglan()
    try:
        with conn.cursor() as cursor:
            _dogru_veritabani(cursor)
            (uzunluk,) = _sorgu(
                cursor, "SELECT character_maximum_length FROM information_schema.columns "
                        "WHERE table_schema = 'public' AND table_name = 'randevular' AND column_name = 'iptal_notu'")[0]
            assert uzunluk == 100
    finally:
        conn.close()


def test_kapali_liste_sutunlari_check_kisitlidir():
    """Kapalı liste istisnası yalnızca veritabanında CHECK kısıtıyla sınırlı sütunlar için geçerlidir (serbest metin girilemez)."""
    conn = _baglan()
    try:
        with conn.cursor() as cursor:
            _dogru_veritabani(cursor)
            for (tablo, sutun), degerler in KAPALI_LISTE_SUTUNLARI.items():
                tanimlar = [r[0] for r in _sorgu(
                    cursor, "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                            "WHERE contype = 'c' AND conrelid = %s::regclass", (tablo,))]
                uygun = [t for t in tanimlar if sutun in t and all(f"'{d}'" in t for d in degerler)]
                assert uygun, f"{tablo}.{sutun} için izinli değerleri sınırlayan CHECK kısıtı bulunamadı"
    finally:
        conn.close()


# ======================================================================================================================
# Personel ve kullanıcı birleşimi (migration b9d4f7a2c613): `personel` artık kullanicilar üzerinde yazılabilir bir görünümdür.
# Her test tek işlemde çalışır ve sonunda geri alınır (kalıcı kayıt bırakmaz).
# ======================================================================================================================
def _gecici_kullanici(cursor, ad):
    cursor.execute("INSERT INTO kullanicilar (kullanici_adi, parola_hash, rol_id) "
                   "VALUES (%s, 'x', (SELECT rol_id FROM roller WHERE rol_adi = 'PSIKOLOG')) RETURNING kullanici_id", (ad,))
    return cursor.fetchone()[0]


def _geri_alinabilir(test):
    """Testi tek işlemde çalıştırır; ne olursa olsun geri alır."""
    def sarmal():
        conn = _baglan()
        try:
            with conn.cursor() as cursor:
                _dogru_veritabani(cursor)
                test(cursor)
        finally:
            conn.rollback()
            conn.close()
    sarmal.__name__ = test.__name__
    sarmal.__doc__ = test.__doc__
    return sarmal


def _hata_veren(cursor, sql, parametre=()):
    """SQL'i savepoint içinde çalıştırır; fırlatılan psycopg2 hata sınıfını döndürür (hata yoksa None)."""
    cursor.execute("SAVEPOINT s")
    try:
        cursor.execute(sql, parametre or None)
    except psycopg2.Error as hata:
        cursor.execute("ROLLBACK TO SAVEPOINT s")
        return hata
    cursor.execute("RELEASE SAVEPOINT s")
    return None


@_geri_alinabilir
def test_personel_gorunumu_kullanicilar_uzerindedir_ve_yazma_kullaniciya_gider(cursor):
    cursor.execute("SELECT relkind FROM pg_class WHERE relname = 'personel' AND relnamespace = 'public'::regnamespace")
    assert cursor.fetchone()[0] == "v"                                                      # tablo değil, görünüm
    k = _gecici_kullanici(cursor, "pg_birlesim_1")
    cursor.execute("INSERT INTO personel (kullanici_id, personel_kodu) VALUES (%s, 'BIR-001') RETURNING personel_id, aktif_mi", (k,))
    personel_id, aktif = cursor.fetchone()
    assert aktif is True
    cursor.execute("SELECT personel_id, personel_kodu FROM kullanicilar WHERE kullanici_id = %s", (k,))
    assert cursor.fetchone() == (personel_id, "BIR-001")                                    # yazılan veri kullanicilar'da
    cursor.execute("SELECT personel_id, kullanici_id, personel_kodu, aktif_mi FROM personel WHERE kullanici_id = %s", (k,))
    assert cursor.fetchone() == (personel_id, k, "BIR-001", True)


@_geri_alinabilir
def test_tek_aktiflik_bayragi_personel_ve_kullanici_birbirinden_kopamaz(cursor):
    k = _gecici_kullanici(cursor, "pg_birlesim_2")
    cursor.execute("INSERT INTO personel (kullanici_id, personel_kodu) VALUES (%s, 'BIR-002')", (k,))
    cursor.execute("UPDATE personel SET aktif_mi = FALSE WHERE kullanici_id = %s", (k,))
    cursor.execute("SELECT aktif_mi FROM kullanicilar WHERE kullanici_id = %s", (k,))
    assert cursor.fetchone()[0] is False                                                    # personel pasifse hesap da pasif
    cursor.execute("UPDATE kullanicilar SET aktif_mi = TRUE WHERE kullanici_id = %s", (k,))
    cursor.execute("SELECT aktif_mi FROM personel WHERE kullanici_id = %s", (k,))
    assert cursor.fetchone()[0] is True                                                     # hesap aktifse personel de aktif


@_geri_alinabilir
def test_personel_kodu_guncellenir_ama_kimlikler_degistirilemez(cursor):
    k = _gecici_kullanici(cursor, "pg_birlesim_3")
    cursor.execute("INSERT INTO personel (kullanici_id, personel_kodu) VALUES (%s, 'BIR-003') RETURNING personel_id", (k,))
    pid = cursor.fetchone()[0]
    cursor.execute("UPDATE personel SET personel_kodu = 'BIR-033' WHERE personel_id = %s", (pid,))
    cursor.execute("SELECT personel_kodu FROM kullanicilar WHERE kullanici_id = %s", (k,))
    assert cursor.fetchone()[0] == "BIR-033"
    assert _hata_veren(cursor, "UPDATE personel SET personel_id = personel_id + 100000 WHERE personel_id = %s", (pid,)) is not None
    assert _hata_veren(cursor, "UPDATE personel SET kullanici_id = kullanici_id + 100000 WHERE personel_id = %s", (pid,)) is not None


@_geri_alinabilir
def test_eski_tablonun_hata_siniflari_korunur(cursor):
    """Uygulama bu hata sınıflarına göre 409/422 üretir; görünüm de aynı sınıfları fırlatmalıdır."""
    k = _gecici_kullanici(cursor, "pg_birlesim_4")
    k2 = _gecici_kullanici(cursor, "pg_birlesim_5")
    cursor.execute("INSERT INTO personel (kullanici_id, personel_kodu) VALUES (%s, 'BIR-004')", (k,))
    assert isinstance(_hata_veren(cursor, "INSERT INTO personel (kullanici_id, personel_kodu) VALUES (%s, 'BIR-X')", (k,)), psycopg2.errors.UniqueViolation)     # aynı kullanıcıya ikinci personel
    assert isinstance(_hata_veren(cursor, "INSERT INTO personel (kullanici_id, personel_kodu) VALUES (%s, 'BIR-004')", (k2,)), psycopg2.errors.UniqueViolation)  # aynı kod
    assert isinstance(_hata_veren(cursor, "INSERT INTO personel (kullanici_id, personel_kodu) VALUES (-1, 'BIR-Y')"), psycopg2.errors.ForeignKeyViolation)       # olmayan kullanıcı
    assert _hata_veren(cursor, "INSERT INTO personel (kullanici_id, personel_kodu) VALUES (%s, NULL)", (k2,)) is not None                                        # kodsuz personel olmaz


@_geri_alinabilir
def test_personel_silme_baglantilari_korur_eski_davranisla_ayni(cursor):
    k = _gecici_kullanici(cursor, "pg_birlesim_6")
    cursor.execute("INSERT INTO personel (kullanici_id, personel_kodu) VALUES (%s, 'BIR-006') RETURNING personel_id", (k,))
    pid = cursor.fetchone()[0]
    cursor.execute("INSERT INTO danisan_kodlari (danisan_kod_id, olusturan_psikolog_id) VALUES ('BIR-D-1', %s)", (pid,))
    cursor.execute("INSERT INTO odalar (oda_adi) VALUES ('pg_birlesim_oda') RETURNING oda_id")
    oda = cursor.fetchone()[0]
    cursor.execute("INSERT INTO randevular (danisan_kod_id, psikolog_id, oda_id, baslangic_zamani, bitis_zamani, durum) "
                   "VALUES ('BIR-D-1', %s, %s, '2031-01-01 10:00', '2031-01-01 11:00', 'PLANLANDI')", (pid, oda))
    hata = _hata_veren(cursor, "DELETE FROM personel WHERE personel_id = %s", (pid,))
    assert isinstance(hata, psycopg2.errors.ForeignKeyViolation)                            # randevusu olan personel silinemez
    cursor.execute("SELECT personel_id FROM kullanicilar WHERE kullanici_id = %s", (k,))
    assert cursor.fetchone()[0] == pid                                                      # silme geri alındı, bağlantı duruyor
    cursor.execute("DELETE FROM randevular WHERE danisan_kod_id = 'BIR-D-1'")
    cursor.execute("DELETE FROM personel WHERE personel_id = %s", (pid,))                   # randevusu yoksa silinir
    cursor.execute("SELECT personel_id, personel_kodu FROM kullanicilar WHERE kullanici_id = %s", (k,))
    assert cursor.fetchone() == (None, None)                                                # kullanıcı durur, personel alanları boşalır
    cursor.execute("SELECT olusturan_psikolog_id FROM danisan_kodlari WHERE danisan_kod_id = 'BIR-D-1'")
    assert cursor.fetchone()[0] is None                                                     # danışan kodunun oluşturan psikologu boşalır (eski ON DELETE SET NULL)


@_geri_alinabilir
def test_dort_bagli_tablonun_yabanci_anahtari_kullanicilar_personel_id_ye_baglidir(cursor):
    cursor.execute(
        "SELECT conrelid::regclass::text, a.attname, confrelid::regclass::text, fa.attname "
        "FROM pg_constraint c JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey) "
        "JOIN pg_attribute fa ON fa.attrelid = c.confrelid AND fa.attnum = ANY (c.confkey) "
        "WHERE c.contype = 'f' AND c.confrelid = 'kullanicilar'::regclass AND fa.attname = 'personel_id' ORDER BY 1")
    assert cursor.fetchall() == [
        ("cihaz_rezervasyonlari", "rezervasyonu_yapan_personel_id", "kullanicilar", "personel_id"),
        ("danisan_kodlari", "olusturan_psikolog_id", "kullanicilar", "personel_id"),
        ("oda_etkinlikleri", "organize_eden_personel_id", "kullanicilar", "personel_id"),
        ("randevular", "psikolog_id", "kullanicilar", "personel_id"),
    ]


@_geri_alinabilir
def test_personel_id_sayaci_gecmis_kimliklerin_uzerinden_devam_eder(cursor):
    k = _gecici_kullanici(cursor, "pg_birlesim_7")
    cursor.execute("SELECT COALESCE(MAX(personel_id), 0) FROM kullanicilar")
    en_buyuk = cursor.fetchone()[0]
    cursor.execute("INSERT INTO personel (kullanici_id, personel_kodu) VALUES (%s, 'BIR-007') RETURNING personel_id", (k,))
    assert cursor.fetchone()[0] > en_buyuk                                                  # eski kimlikler yeniden kullanılmaz


@_geri_alinabilir
def test_personeli_olmayan_kullanici_gorunumde_yoktur(cursor):
    k = _gecici_kullanici(cursor, "pg_birlesim_8")
    cursor.execute("SELECT count(*) FROM personel WHERE kullanici_id = %s", (k,))
    assert cursor.fetchone()[0] == 0                                                        # personel kaydı yoksa görünümde de yok
    assert _hata_veren(cursor, "UPDATE kullanicilar SET personel_kodu = 'BIR-008' WHERE kullanici_id = %s", (k,)) is not None   # personel_id olmadan kod yazılamaz


# ----------------------------------------------------------------------------------------------------------------------
# scripts/personel_gecis_kontrol.py: geçiş SONRASI kontrollerinin gerçek veritabanındaki karşılıkları
# ----------------------------------------------------------------------------------------------------------------------
@_geri_alinabilir
def test_gecis_kontrol_araci_gecilmis_veritabaninda_yapiyi_dogrular(cursor):
    from scripts import personel_gecis_kontrol as k

    assert k.personel_turu(cursor) == "v"
    assert all(k.yapi_bilgisi(cursor).values()), k.yapi_bilgisi(cursor)
    ok, aciklama = k.yazma_denemesi(cursor)
    assert ok, aciklama


@_geri_alinabilir
def test_gecis_kontrol_araci_yazma_denemesi_kalici_kayit_birakmaz(cursor):
    from scripts import personel_gecis_kontrol as k

    cursor.execute("SELECT count(*) FROM kullanicilar")
    once = cursor.fetchone()[0]
    assert k.yazma_denemesi(cursor)[0]
    cursor.execute("SELECT count(*) FROM kullanicilar")
    assert cursor.fetchone()[0] == once


@_geri_alinabilir
def test_gecis_kontrol_araci_goruntusu_tutarlidir(cursor):
    from scripts import personel_gecis_kontrol as k

    ilk, ikinci = k.goruntu_al(cursor), k.goruntu_al(cursor)
    assert ilk == ikinci                                                                    # aynı veri için sağlama özeti sabit
    assert set(ilk) == {"personel", "kullanicilar", "randevular", "danisan_kodlari", "cihaz_rezervasyonlari", "oda_etkinlikleri", "denetim_personel_hedefleri"}
    assert k.uyumsuz_aktiflikler(cursor) == []                                              # tek bayrak: uyumsuzluk artık mümkün değil


@_geri_alinabilir
def test_eski_sutundaki_dolu_degerler_gosterilir_bos_olanlar_ve_bilinen_sutunlar_gosterilmez(cursor):
    """Eski şemayı taklit eden GEÇİCİ tabloda (işlem sonunda geri alınır): beklenmeyen sütun ve yalnızca DOLU değerleri listelenir."""
    from scripts import personel_gecis_kontrol as k

    cursor.execute("INSERT INTO odalar (oda_adi) VALUES ('pg_ekstra_oda') RETURNING oda_id")
    oda = cursor.fetchone()[0]
    u1, u2 = _gecici_kullanici(cursor, "pg_ekstra_1"), _gecici_kullanici(cursor, "pg_ekstra_2")
    cursor.execute("CREATE TEMP TABLE personel_gecis_deneme (personel_id integer, kullanici_id integer, personel_kodu varchar(50), "
                   "aktif_mi boolean, olusturulma_tarihi timestamp, varsayilan_oda_id integer)")
    cursor.execute("INSERT INTO personel_gecis_deneme VALUES (900001, %s, 'E-1', true, now(), %s), (900002, %s, 'E-2', true, now(), NULL)", (u1, oda, u2))
    assert k.ekstra_sutunlar(cursor, "personel_gecis_deneme") == ["varsayilan_oda_id"]
    assert k.ekstra_degerler(cursor, "personel_gecis_deneme") == [
        {"sutun": "varsayilan_oda_id", "personel_id": 900001, "kullanici_adi": "pg_ekstra_1", "deger": str(oda), "oda_adi": "pg_ekstra_oda"}]


@_geri_alinabilir
def test_gecilmis_semada_ekstra_sutun_yoktur(cursor):
    from scripts import personel_gecis_kontrol as k

    assert k.ekstra_sutunlar(cursor, "personel") == [] and k.ekstra_degerler(cursor, "personel") == []
