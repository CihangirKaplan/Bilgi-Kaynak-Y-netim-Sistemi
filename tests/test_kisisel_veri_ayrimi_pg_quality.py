"""FR-008 Kişisel veri ayrımı (gerçek PostgreSQL şeması).

Gereksinim: operasyonel danışan kodunu gerçek kişiyle eşleştiren kayıt veya tablo bulunmamalıdır.

Bu test CI'daki "PostgreSQL Entegrasyon Testleri" işinde (alembic upgrade head sonrası) çalışır. Biri danışan koduna
bağlı bir tabloya kişisel bir sütun ya da danışan koduna başvuran yeni bir tablo eklerse PR kırmızı olur; ekleyen
kişi bunu bilerek kabul edip aşağıdaki izinli listeleri güncellemek zorunda kalır.
"""

import os
import re

import psycopg2

from sunucu import VT_AYARLARI

# Danışan koduyla ilgili tabloların TÜM sütunları (başka sütun eklenirse test kırılır).
IZINLI_SUTUNLAR = {
    "danisan_kodlari": {"danisan_kod_id", "ucretli_mi", "istisna_turu", "aktif_mi", "olusturulma_tarihi",
                        "olusturan_psikolog_id"},
    "randevular": {"randevu_id", "danisan_kod_id", "psikolog_id", "oda_id", "baslangic_zamani", "bitis_zamani",
                   "durum", "olusturulma_tarihi", "iptal_nedeni", "iptal_notu"},
}
# FR-008 İSTİSNASI (PR2): iptal notu, danışan kodlu tabloda bilinçli olarak açılmış TEK kısa serbest metin alanıdır.
# En çok 100 karakter; arayüz "kişisel bilgi yazmayın" uyarısı verir. Başka bir sütun bu listeye ancak bilerek eklenir.
KISA_SERBEST_METIN_ISTISNALARI = {("randevular", "iptal_notu"): 100}
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
            if (tablo, sutun) in KISA_SERBEST_METIN_ISTISNALARI:
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
    """danisan_kodlari -> personel yalnızca kodu OLUŞTURAN psikologu gösterir (danışanı değil)."""
    conn = _baglan()
    try:
        with conn.cursor() as cursor:
            _dogru_veritabani(cursor)
            giden = _sorgu(
                cursor, "SELECT a.attname, confrelid::regclass::text FROM pg_constraint c "
                        "JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey) "
                        "WHERE c.contype = 'f' AND c.conrelid = 'danisan_kodlari'::regclass")
            assert giden == [("olusturan_psikolog_id", "personel")]

            # Hiçbir kişi tablosu (öğrenci, kullanıcı, personel) danışan koduna sütunla başvurmaz.
            for tablo in KISI_TABLOLARI:
                sutunlar = {r[0] for r in _sorgu(
                    cursor, "SELECT column_name FROM information_schema.columns "
                            "WHERE table_schema = 'public' AND table_name = %s", (tablo,))}
                assert not any("danisan" in s for s in sutunlar), f"{tablo} danışan koduna başvuruyor"
            # randevular da öğrenci/kullanıcı tablolarına değil yalnızca personel (psikolog) ve odaya bağlanır.
            hedefler = {r[0] for r in _sorgu(
                cursor, "SELECT confrelid::regclass::text FROM pg_constraint "
                        "WHERE contype = 'f' AND conrelid = 'randevular'::regclass")}
            assert hedefler == {"danisan_kodlari", "personel", "odalar"}
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
                    if (tablo, sutun) in KISA_SERBEST_METIN_ISTISNALARI:
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
