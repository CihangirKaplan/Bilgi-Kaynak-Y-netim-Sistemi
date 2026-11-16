"""TKYS - Veritabanı şeması doğrulama: canlı veritabanı, migration'ların üretmesi gereken şemayla aynı mı?

Neden: `alembic current` yalnızca "hangi sürümdeyim" bilgisini gösterir. Bir migration atlanmışsa (örn. bir migration bir
bilgisayarda başka bir ebeveyne bağlıyken uygulandıysa) sürüm "güncel" görünür ama tablolarda sütun eksik kalır; kullanıcı
"beklenmeyen hata" görür. Bu araç gerçek tabloları kontrol eder.

Nasıl çalışır:
  1. Aynı PostgreSQL sunucusunda GEÇİCİ bir veritabanı oluşturur ve migration'ları baştan çalıştırır ("olması gereken" şema).
  2. Canlı veritabanının şemasını (tablolar, sütunlar ve tipleri, kurallar, indeksler, enum'lar, tetikleyiciler) okur.
  3. İkisini karşılaştırır, farkları anlaşılır biçimde yazar ve geçici veritabanını siler.
Canlı veritabanında hiçbir şey değiştirmez (yalnızca okur). Geçici veritabanını oluşturmak için tam yetkili kimlik gerekir
(.env içinde DB_MIGRATION_USER / DB_MIGRATION_PASSWORD, yoksa DB_USER / DB_PASSWORD).

Kullanım (proje klasöründe, sanal ortam açıkken):
    python scripts/sema_dogrula.py              # özet
    python scripts/sema_dogrula.py --ayrinti    # varsayılan değer / kural tanımı gibi ayrıntı farklarını da listeler

Çıkış kodu: 0 = şema uyumlu, 1 = fark var ya da kontrol edilemedi.
"""

import argparse
import os
import secrets
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK))

import psycopg2
from dotenv import load_dotenv
from psycopg2 import sql

from server.sema_kimligi import SemaKimligiHatasi, sema_kimligi

KATEGORI_ADLARI = {
    "tablo": "tablo", "kolon": "sütun", "kisit": "kural", "indeks": "indeks", "enum": "enum türü", "tetikleyici": "tetikleyici",
}
LISTE_SINIRI = 40

# Her sorgu (anahtar, yapısal özellik, ayrıntı) döndürür. Yapısal fark uygulamayı bozabilir; ayrıntı farkı genelde zararsızdır.
SORGULAR = {
    "tablo": """
        SELECT c.relname, '', ''
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')
    """,
    "kolon": """
        SELECT c.relname || '.' || a.attname,
               format_type(a.atttypid, a.atttypmod) || CASE WHEN a.attnotnull THEN ' NOT NULL' ELSE ' NULL' END,
               coalesce(pg_get_expr(d.adbin, d.adrelid), '')
        FROM pg_attribute a
        JOIN pg_class c ON c.oid = a.attrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
        WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p') AND a.attnum > 0 AND NOT a.attisdropped
    """,
    "kisit": """
        SELECT c.relname || '.' || k.conname, k.contype::text, pg_get_constraintdef(k.oid)
        FROM pg_constraint k
        JOIN pg_class c ON c.oid = k.conrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND k.contype IN ('c', 'u', 'p', 'f', 'x')
    """,
    "indeks": """
        SELECT tablename || '.' || indexname, '', indexdef FROM pg_indexes WHERE schemaname = 'public'
    """,
    "enum": """
        SELECT t.typname, string_agg(e.enumlabel, ',' ORDER BY e.enumsortorder), ''
        FROM pg_type t
        JOIN pg_enum e ON e.enumtypid = t.oid
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE n.nspname = 'public'
        GROUP BY t.typname
    """,
    "tetikleyici": """
        SELECT c.relname || '.' || t.tgname, '', pg_get_triggerdef(t.oid)
        FROM pg_trigger t
        JOIN pg_class c ON c.oid = t.tgrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND NOT t.tgisinternal
    """,
}


class SemaDogrulamaHatasi(Exception):
    """Beklenen, kullanıcıya mesajla bildirilecek hata."""


@dataclass
class Karsilastirma:
    eksik: list = field(default_factory=list)       # olması gerekip veritabanında olmayanlar
    fazla: list = field(default_factory=list)       # veritabanında olup olmaması gerekenler
    farkli: list = field(default_factory=list)      # ikisinde de var ama yapısal özelliği (tip, null, tür...) farklı
    ayrinti: list = field(default_factory=list)     # yapısı aynı, ayrıntısı (varsayılan değer, tanım) farklı

    @property
    def sorunlu(self):
        return bool(self.eksik or self.farkli)


def parmak_izi(imlec):
    """Şemanın parmak izi: {(kategori, anahtar): (yapısal, ayrıntı)}."""
    sonuc = {}
    for kategori, sorgu in SORGULAR.items():
        imlec.execute(sorgu)
        for anahtar, yapisal, ayrinti in imlec.fetchall():
            sonuc[(kategori, anahtar)] = (yapisal or "", ayrinti or "")
    return sonuc


def karsilastir(beklenen, gercek):
    sonuc = Karsilastirma()
    for anahtar in sorted(beklenen):
        if anahtar not in gercek:
            sonuc.eksik.append(anahtar)
        elif beklenen[anahtar][0] != gercek[anahtar][0]:
            sonuc.farkli.append(anahtar)
        elif beklenen[anahtar][1] != gercek[anahtar][1]:
            sonuc.ayrinti.append(anahtar)
    sonuc.fazla = sorted(anahtar for anahtar in gercek if anahtar not in beklenen)
    return sonuc


def kodun_surumleri():
    """Koddaki migration zincirinin son sürüm(ler)i."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    return set(ScriptDirectory.from_config(Config(str(KOK / "alembic.ini"))).get_heads())


def veritabani_surumleri(imlec):
    imlec.execute("SELECT version_num FROM alembic_version")
    return {satir[0] for satir in imlec.fetchall()}


def _satirlar(baslik, anahtarlar, beklenen, gercek, sinir=LISTE_SINIRI):
    satirlar = [f"  {baslik} ({len(anahtarlar)}):"]
    for kategori, anahtar in anahtarlar[:sinir]:
        beklenen_ozet = beklenen.get((kategori, anahtar), ("",))[0]
        gercek_ozet = gercek.get((kategori, anahtar), ("",))[0]
        if baslik.startswith("FARKLI"):
            satirlar.append(f"    - {KATEGORI_ADLARI[kategori]}: {anahtar}   (olması gereken: {beklenen_ozet or '-'} | şu an: {gercek_ozet or '-'})")
        else:
            ozet = beklenen_ozet or gercek_ozet
            satirlar.append(f"    - {KATEGORI_ADLARI[kategori]}: {anahtar}" + (f"   ({ozet})" if ozet else ""))
    if len(anahtarlar) > sinir:
        satirlar.append(f"    ... ve {len(anahtarlar) - sinir} tane daha")
    return satirlar


def rapor_olustur(veritabani, kod_surumleri, db_surumleri, sonuc, beklenen, gercek, ayrinti_goster=False):
    """(rapor satırları, başarılı_mı) döndürür. Başarılı: sürüm eşleşiyor ve eksik/farklı nesne yok."""
    satirlar = [f"Veritabanı: {veritabani}",
                f"Alembic sürümü: veritabanında {sorted(db_surumleri) or 'YOK'} | kodda {sorted(kod_surumleri)}"]
    surum_uyumlu = db_surumleri == kod_surumleri
    if not surum_uyumlu:
        satirlar.append("SORUN: Veritabanının alembic sürümü kodun sürümüyle aynı değil. Önce şunu çalıştırın: python -m alembic upgrade head")

    if sonuc.eksik:
        satirlar += _satirlar("EKSİK (olması gereken ama veritabanında yok)", sonuc.eksik, beklenen, gercek)
    if sonuc.farkli:
        satirlar += _satirlar("FARKLI (yapısı olması gerekenden farklı)", sonuc.farkli, beklenen, gercek)
    if sonuc.fazla:
        satirlar += _satirlar("FAZLA (olması gerekenden fazla; genelde eski sürümden kalan, zararsız)", sonuc.fazla, beklenen, gercek)
    if sonuc.ayrinti:
        if ayrinti_goster:
            satirlar += _satirlar("AYRINTI FARKI (varsayılan değer / tanım)", sonuc.ayrinti, beklenen, gercek)
        else:
            satirlar.append(f"  Not: {len(sonuc.ayrinti)} nesnede ayrıntı farkı var (varsayılan değer / kural tanımı); --ayrinti ile listelenir.")

    if sonuc.sorunlu and surum_uyumlu:
        satirlar.append(
            "\nSONUÇ: TUTARSIZ ŞEMA. Alembic sürümü güncel görünüyor ama yukarıdaki nesneler eksik/farklı: bir migration atlanmış ya da "
            "tablolar elle değiştirilmiş olabilir. `alembic upgrade head` bunu DÜZELTMEZ; bir geliştiriciye danışın."
        )
    elif sonuc.sorunlu:
        satirlar.append("\nSONUÇ: ŞEMA ESKİ. Yukarıdaki alembic komutunu çalıştırdıktan sonra bu aracı tekrar çalıştırın.")
    elif not surum_uyumlu:
        satirlar.append("\nSONUÇ: Tablolar uyumlu görünüyor ama alembic sürümü eski. Yukarıdaki alembic komutunu çalıştırın.")
    else:
        satirlar.append("\nSONUÇ: ŞEMA UYUMLU. Veritabanı, migration'ların üretmesi gereken şemayla aynı.")
    return satirlar, surum_uyumlu and not sonuc.sorunlu


@contextmanager
def gecici_sema_veritabani(yonetici, yonetici_parola, host, port, on_ek="crkys_sema_referans"):
    """Migration'ları baştan çalıştırılmış GEÇİCİ bir veritabanı oluşturur; (ad, bağlantı bilgisi) verir, çıkışta siler."""
    ad = f"{on_ek}_{secrets.token_hex(4)}"
    baglanti_bilgisi = {"user": yonetici, "password": yonetici_parola, "host": host, "port": port}
    yonetim = psycopg2.connect(dbname="postgres", **baglanti_bilgisi)
    yonetim.autocommit = True
    try:
        try:
            yonetim.cursor().execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(ad)))
        except psycopg2.errors.InsufficientPrivilege as hata:
            raise SemaDogrulamaHatasi(
                "Geçici veritabanı oluşturulamadı: kullanıcının veritabanı oluşturma yetkisi yok. "
                ".env içinde DB_MIGRATION_USER ve DB_MIGRATION_PASSWORD olarak tam yetkili kullanıcıyı verin."
            ) from hata

        ortam = {**os.environ, "DB_NAME": ad, "DB_USER": yonetici, "DB_PASSWORD": yonetici_parola,
                 "DB_HOST": host, "DB_PORT": str(port)}
        ortam.pop("DB_MIGRATION_USER", None)
        ortam.pop("DB_MIGRATION_PASSWORD", None)
        islem = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=KOK, env=ortam, capture_output=True, text=True, timeout=600,
        )
        if islem.returncode != 0:
            son = "\n".join((islem.stderr or islem.stdout or "").strip().splitlines()[-5:])
            raise SemaDogrulamaHatasi("Referans şema için migration'lar çalıştırılamadı:\n" + son)
        yield ad, baglanti_bilgisi
    finally:
        try:
            yonetim.cursor().execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(ad)))
        finally:
            yonetim.close()


def referans_uret(yonetici, yonetici_parola, host, port):
    """Geçici veritabanında migration'ları baştan çalıştırıp 'olması gereken' şemanın parmak izini döndürür."""
    with gecici_sema_veritabani(yonetici, yonetici_parola, host, port) as (ad, baglanti_bilgisi):
        referans = psycopg2.connect(dbname=ad, **baglanti_bilgisi)
        try:
            return parmak_izi(referans.cursor())
        finally:
            referans.close()


def dogrula(veritabani, canli_baglanti_bilgisi, yonetici, yonetici_parola, ayrinti_goster=False):
    """Canlı veritabanını doğrular. (rapor satırları, başarılı_mı) döndürür."""
    host, port = canli_baglanti_bilgisi["host"], canli_baglanti_bilgisi["port"]
    beklenen = referans_uret(yonetici, yonetici_parola, host, port)
    canli = psycopg2.connect(dbname=veritabani, **canli_baglanti_bilgisi)
    try:
        imlec = canli.cursor()
        gercek = parmak_izi(imlec)
        db_surumleri = veritabani_surumleri(imlec)
    finally:
        canli.close()
    return rapor_olustur(veritabani, kodun_surumleri(), db_surumleri, karsilastir(beklenen, gercek), beklenen, gercek, ayrinti_goster)


def main(argv=None):
    load_dotenv(KOK / ".env")
    ayrac = argparse.ArgumentParser(description="Veritabanı şemasını migration'lardan üretilen şemayla karşılaştırır.")
    ayrac.add_argument("--ayrinti", action="store_true", help="Varsayılan değer / kural tanımı gibi ayrıntı farklarını da listele.")
    args = ayrac.parse_args(argv)
    try:
        yonetici, yonetici_parola = sema_kimligi()
        if not yonetici or not yonetici_parola:
            raise SemaDogrulamaHatasi(".env dosyasında DB_USER ve DB_PASSWORD (ya da DB_MIGRATION_*) tanımlı olmalı.")
        canli = {"user": os.environ["DB_USER"], "password": os.environ["DB_PASSWORD"],
                 "host": os.environ["DB_HOST"], "port": os.environ.get("DB_PORT", "5432")}
        print("Beklenen şema, geçici bir veritabanında migration'lar çalıştırılarak üretiliyor (biraz sürebilir)...")
        satirlar, basarili = dogrula(os.environ["DB_NAME"], canli, yonetici, yonetici_parola, args.ayrinti)
    except (SemaDogrulamaHatasi, SemaKimligiHatasi) as hata:
        print(f"HATA: {hata}")
        return 1
    except KeyError as hata:
        print(f"HATA: .env dosyasında {hata} ayarı eksik.")
        return 1
    except psycopg2.Error as hata:
        print(f"HATA: Veritabanı işlemi başarısız: {str(hata).strip().splitlines()[0]}")
        return 1
    print("\n".join(satirlar))
    return 0 if basarili else 1


if __name__ == "__main__":
    sys.exit(main())
