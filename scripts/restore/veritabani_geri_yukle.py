"""TKYS yedeğini YENİ bir veritabanına geri yükleme ve doğrulama aracı.

Güvenlik: Bu araç mevcut hiçbir veritabanının üzerine yazmaz. Hedef veritabanı henüz
var olmamalıdır; araç onu oluşturur, yedeği içine yükler ve kayıt sayılarını gösterir.
Uygulamanın kullandığı canlı veritabanı (.env içindeki DB_NAME) hedef olarak kabul edilmez.

Örnek:
    python scripts/restore/veritabani_geri_yukle.py --hedef crkys_geri_yukleme_testi
    python scripts/restore/veritabani_geri_yukle.py --hedef crkys_dene --dump backups/crkys_20261104_093000_123456.dump
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from psycopg2 import sql

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from server.sema_kimligi import SemaKimligiHatasi, sema_kimligi  # noqa: E402

load_dotenv()

# Yedekleme aracıyla aynı klasör: TKYS_BACKUP_DIR tanımlıysa (örn. C:\TKYS_Backups) en son yedek orada aranır.
YEDEK_KLASORU = Path(os.getenv("TKYS_BACKUP_DIR") or (Path(__file__).resolve().parents[2] / "backups")).resolve()
GECERLI_AD = re.compile(r"^[A-Za-z0-9_]{1,63}$")
KORUNAN_ADLAR = {"postgres", "template0", "template1"}
# Geri yükleme sonrası kayıt sayıları gösterilen tablolar (bulunmayanlar atlanır).
KONTROL_TABLOLARI = (
    "roller", "izinler", "rol_izinleri", "kullanicilar", "personel", "odalar", "danisan_kodlari",
    "randevular", "cihazlar", "cihaz_rezervasyonlari", "cihaz_bakimlari", "cihaz_kalibrasyonlari",
    "cihaz_arizalari", "denetim_kayitlari",
)


class GeriYuklemeHatasi(Exception):
    """Beklenen, kullanıcıya mesajla bildirilecek hata."""


def _sema_kimligi():
    """Yeni veritabanı oluşturup tablo yükleyebilen kimlik (kısıtlı uygulama kullanıcısı bunu yapamaz)."""
    try:
        return sema_kimligi()
    except SemaKimligiHatasi as hata:
        raise GeriYuklemeHatasi(str(hata)) from hata


def _baglan(veritabani):
    kullanici, parola = _sema_kimligi()
    return psycopg2.connect(
        dbname=veritabani,
        user=kullanici,
        password=parola,
        host=os.environ["DB_HOST"],
        port=os.environ["DB_PORT"],
    )


def pg_restore_yolu():
    acik = os.getenv("PG_RESTORE_PATH")
    if acik:
        return acik
    pg_dump = os.getenv("PG_DUMP_PATH")
    if pg_dump:                                            # aynı klasördeki pg_restore
        yan = Path(pg_dump).with_name("pg_restore" + Path(pg_dump).suffix)
        if yan.is_file():
            return str(yan)
    bulunan = shutil.which("pg_restore")
    if not bulunan:
        raise GeriYuklemeHatasi(
            "pg_restore bulunamadi. PostgreSQL bin klasorunu PATH'e ekleyin veya PG_RESTORE_PATH tanimlayin."
        )
    return bulunan


def en_yeni_yedek(kaynak):
    desen = re.compile(rf"^{re.escape(kaynak)}_\d{{8}}_\d{{6}}_\d{{6}}\.dump$")
    adaylar = [d for d in YEDEK_KLASORU.glob("*.dump") if desen.fullmatch(d.name) and d.is_file()] \
        if YEDEK_KLASORU.exists() else []
    if not adaylar:
        raise GeriYuklemeHatasi(f"'{kaynak}' icin backups/ klasorunde yedek bulunamadi. --dump ile dosya verin.")
    return max(adaylar, key=lambda d: d.name)


def kayit_sayilari(veritabani):
    """{tablo: satır sayısı, 'alembic': sürüm}; veritabanına bağlanılamazsa None."""
    try:
        baglanti = _baglan(veritabani)
    except psycopg2.Error:
        return None
    try:
        imlec = baglanti.cursor()
        imlec.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        mevcut = {satir[0] for satir in imlec.fetchall()}
        sonuc = {}
        for tablo in KONTROL_TABLOLARI:
            if tablo in mevcut:
                imlec.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(tablo)))
                sonuc[tablo] = imlec.fetchone()[0]
        if "alembic_version" in mevcut:
            imlec.execute("SELECT version_num FROM alembic_version")
            satir = imlec.fetchone()
            sonuc["alembic"] = satir[0] if satir else "-"
        return sonuc
    finally:
        baglanti.close()


def geri_yukle(dump, hedef, kaynak):
    """Yedeği yeni 'hedef' veritabanına yükler; yüklenen kayıt sayılarını döndürür."""
    for ad in (hedef, kaynak):
        if not ad or not GECERLI_AD.fullmatch(ad):
            raise GeriYuklemeHatasi("Veritabani adi yalnizca harf, rakam ve alt cizgi icerebilir.")
    canli = os.getenv("DB_NAME")
    if hedef == canli or hedef == kaynak or hedef in KORUNAN_ADLAR:
        raise GeriYuklemeHatasi(
            f"'{hedef}' hedef olarak kullanilamaz: canli/kaynak veritabaninin uzerine geri yukleme yapilmaz. "
            "Yeni bir ad secin."
        )
    dump = Path(dump)
    if not dump.is_file() or dump.stat().st_size == 0:
        raise GeriYuklemeHatasi(f"Yedek dosyasi bulunamadi veya bos: {dump}")
    pg_restore = pg_restore_yolu()

    yonetim = _baglan("postgres")
    yonetim.autocommit = True
    try:
        imlec = yonetim.cursor()
        imlec.execute("SELECT 1 FROM pg_database WHERE datname = %s", (hedef,))
        if imlec.fetchone():
            raise GeriYuklemeHatasi(
                f"'{hedef}' veritabani zaten var; mevcut veritabaninin uzerine yazilmaz. Yeni bir ad secin."
            )
        try:
            imlec.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(hedef)))
        except psycopg2.errors.InsufficientPrivilege as hata:
            raise GeriYuklemeHatasi(
                "Bağlanılan veritabanı kullanıcısı yeni veritabanı oluşturamaz (kısıtlı uygulama kullanıcısı). "
                ".env dosyasına tam yetkili kullanıcının bilgilerini DB_MIGRATION_USER ve DB_MIGRATION_PASSWORD "
                "olarak ekleyin, sonra geri yüklemeyi tekrar deneyin."
            ) from hata

        ortam = os.environ.copy()
        sema_kullanici, sema_parola = _sema_kimligi()
        ortam["PGPASSWORD"] = sema_parola
        komut = [
            pg_restore, "--no-password", "--no-owner", "--exit-on-error",
            "--host", ortam["DB_HOST"], "--port", ortam["DB_PORT"], "--username", sema_kullanici,
            "--dbname", hedef, str(dump),
        ]
        try:
            subprocess.run(komut, env=ortam, check=True, capture_output=True, text=True, timeout=600)
        except Exception as hata:
            # Hedefi biz oluşturduk; yarım kalan geri yüklemeyi temizle.
            imlec.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(hedef)))
            ayrinti = getattr(hata, "stderr", "") or str(hata)
            raise GeriYuklemeHatasi(f"Geri yukleme basarisiz, olusturulan '{hedef}' silindi.\n{ayrinti.strip()[-400:]}")
    finally:
        yonetim.close()
    return kayit_sayilari(hedef)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--hedef", required=True, help="Olusturulacak YENI veritabani adi")
    parser.add_argument("--dump", help="Yedek dosyasi (varsayilan: kaynak veritabaninin en yeni yedegi)")
    parser.add_argument("--kaynak", default=os.getenv("DB_NAME"),
                        help="Karsilastirilacak kaynak veritabani (varsayilan: .env icindeki DB_NAME)")
    args = parser.parse_args(argv)

    try:
        if not args.kaynak:
            raise GeriYuklemeHatasi("Kaynak veritabani belirtilmedi: --kaynak verin veya .env icinde DB_NAME tanimlayin.")
        dump = Path(args.dump) if args.dump else en_yeni_yedek(args.kaynak)
        print(f"Yedek: {dump.name}")
        geri = geri_yukle(dump, args.hedef, args.kaynak)
    except GeriYuklemeHatasi as hata:
        print(f"HATA: {hata}", file=sys.stderr)
        raise SystemExit(1)

    asil = kayit_sayilari(args.kaynak)
    print(f"\nGeri yuklendi: {args.hedef}")
    print(f"{'Tablo':28}{'Geri yuklenen':>15}{'Kaynak (su an)':>16}")
    for tablo, deger in geri.items():
        kaynak_degeri = "-" if asil is None else asil.get(tablo, "-")
        print(f"{tablo:28}{str(deger):>15}{str(kaynak_degeri):>16}")
    if asil is None:
        print("\nKaynak veritabanina baglanilamadi; karsilastirma yapilmadi.")
    else:
        print("\nNot: Kaynak sayilari yedek alindiktan sonra degismis olabilir; fark beklenen bir durumdur.")
    print("Dogrulama sonrasi gerekmiyorsa hedef veritabanini kendiniz silin (arac silmez).")


if __name__ == "__main__":
    main()
