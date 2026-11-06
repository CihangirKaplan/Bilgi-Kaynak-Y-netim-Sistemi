"""Canlı veritabanı için ilk yönetici (ADMIN) hesabını oluşturur.

ilk_kurulum.py bilinen parolalı TEST kullanıcıları ekler ve canlıda kullanılmamalıdır.
Bu betik onun yerine geçer: yalnızca bir ADMIN kullanıcısı oluşturur, rastgele bir
geçici parola üretip ekrana BİR KEZ yazar ve ilk girişte parola değiştirmeyi zorunlu kılar.
Veritabanında zaten bir ADMIN varsa hiçbir şey eklemez.

Kullanım:
    python scripts/ilk_admin_olustur.py
    python scripts/ilk_admin_olustur.py --kullanici-adi mudur_admin
"""

import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import psycopg2
from dotenv import load_dotenv

from guvenlik import gecici_parola_uret, parola_hashle

load_dotenv()

GECERLI_KULLANICI_ADI = re.compile(r"^[A-Za-z0-9_.-]{3,50}$")


class IlkAdminHatasi(Exception):
    """Kullanıcıya olduğu gibi gösterilecek, beklenen hata."""


def admin_olustur(cursor, kullanici_adi):
    """ADMIN kullanıcısı oluşturur. (kullanici_adi, gecici_parola, personel_kodu) döndürür."""
    if not GECERLI_KULLANICI_ADI.fullmatch(kullanici_adi or ""):
        raise IlkAdminHatasi("Kullanıcı adı 3-50 karakter olmalı; harf, rakam, _ . - içerebilir.")

    cursor.execute("SELECT rol_id FROM roller WHERE rol_adi = 'ADMIN';")
    rol = cursor.fetchone()
    if rol is None:
        raise IlkAdminHatasi("ADMIN rolü bulunamadı. Önce 'python -m alembic upgrade head' çalıştırın.")

    cursor.execute("SELECT 1 FROM kullanicilar WHERE rol_id = %s LIMIT 1;", (rol[0],))
    if cursor.fetchone() is not None:
        raise IlkAdminHatasi("Veritabanında zaten bir ADMIN kullanıcısı var; yeni hesap eklenmedi.")

    cursor.execute("SELECT 1 FROM kullanicilar WHERE kullanici_adi = %s;", (kullanici_adi,))
    if cursor.fetchone() is not None:
        raise IlkAdminHatasi(f"'{kullanici_adi}' kullanıcı adı zaten kullanılıyor.")

    gecici_parola = gecici_parola_uret()
    cursor.execute(
        """
        INSERT INTO kullanicilar (kullanici_adi, parola_hash, rol_id, aktif_mi, ilk_giris_mi)
        VALUES (%s, %s, %s, TRUE, TRUE)
        RETURNING kullanici_id;
        """,
        (kullanici_adi, parola_hashle(gecici_parola), rol[0]),
    )
    kullanici_id = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM personel WHERE personel_kodu LIKE 'PER-ADM-%';")
    personel_kodu = f"PER-ADM-{cursor.fetchone()[0] + 1:03d}"
    cursor.execute(
        "INSERT INTO personel (kullanici_id, personel_kodu, aktif_mi) VALUES (%s, %s, TRUE);",
        (kullanici_id, personel_kodu),
    )
    return kullanici_adi, gecici_parola, personel_kodu


def main(argv=None):
    ayrac = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ayrac.add_argument("--kullanici-adi", default="admin", help="Yönetici kullanıcı adı (varsayılan: admin)")
    args = ayrac.parse_args(argv)

    conn = None
    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432"),
            dbname=os.getenv("DB_NAME", "crkys"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD"),
        )
        with conn.cursor() as cursor:
            kullanici_adi, parola, personel_kodu = admin_olustur(cursor, args.kullanici_adi)
        conn.commit()
    except IlkAdminHatasi as hata:
        if conn is not None:
            conn.rollback()
        print(f"HATA: {hata}")
        return 1
    except psycopg2.Error:
        if conn is not None:
            conn.rollback()
        print("HATA: Veritabanına bağlanılamadı veya kayıt eklenemedi. .env ayarlarını kontrol edin.")
        return 1
    finally:
        if conn is not None:
            conn.close()

    print("Yönetici hesabı oluşturuldu.")
    print(f"  Kullanıcı adı : {kullanici_adi}")
    print(f"  Geçici parola : {parola}")
    print(f"  Personel kodu : {personel_kodu}")
    print("Bu parola bir daha gösterilmez. İlk girişte yeni parola belirlemeniz istenecek.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
