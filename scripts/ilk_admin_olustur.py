"""Canlı veritabanı için ilk yönetici (ADMIN) hesabını oluşturur.

ilk_kurulum.py bilinen parolalı TEST kullanıcıları ekler ve canlıda kullanılmamalıdır.
Bu betik onun yerine geçer: yalnızca bir ADMIN kullanıcısı oluşturur, rastgele bir
geçici parola üretip ekrana BİR KEZ yazar ve ilk girişte parola değiştirmeyi zorunlu kılar.
Veritabanında zaten bir ADMIN varsa hiçbir şey eklemez.

Uygulamadan yönetici (ADMIN) hesabı açılamaz; bilerek yalnızca bu betikle, SUNUCU bilgisayarında açılır.
İkinci bir yönetici gerekiyorsa (biri şifresini unutursa diğeri sıfırlayabilsin diye) --ek-yonetici kullanılır:
onay (EVET) ister, rastgele geçici parola üretir, ilk girişte parola değiştirmeyi zorunlu kılar ve
denetim kaydına (CREATE) yazar.

Kullanım:
    python scripts/ilk_admin_olustur.py
    python scripts/ilk_admin_olustur.py --kullanici-adi mudur_admin
    python scripts/ilk_admin_olustur.py --ek-yonetici
    python scripts/ilk_admin_olustur.py --ek-yonetici --kullanici-adi yonetici2
"""

import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import psycopg2
from dotenv import load_dotenv

from denetim import denetim_kaydi_olustur
from guvenlik import gecici_parola_uret, parola_hashle

load_dotenv()

GECERLI_KULLANICI_ADI = re.compile(r"^[A-Za-z0-9_.-]{3,50}$")


class IlkAdminHatasi(Exception):
    """Kullanıcıya olduğu gibi gösterilecek, beklenen hata."""


def mevcut_yoneticiler(cursor):
    """Veritabanındaki ADMIN hesaplarının kullanıcı adları (alfabetik)."""
    cursor.execute(
        """
        SELECT k.kullanici_adi
        FROM kullanicilar k
        JOIN roller r ON r.rol_id = k.rol_id
        WHERE r.rol_adi = 'ADMIN'
        ORDER BY k.kullanici_adi;
        """
    )
    return [satir[0] for satir in cursor.fetchall()]


def admin_olustur(cursor, kullanici_adi, ek_yonetici=False):
    """ADMIN kullanıcısı oluşturur. (kullanici_adi, gecici_parola, personel_kodu) döndürür.

    ek_yonetici=False: yalnızca veritabanında hiç ADMIN yokken (ilk kurulum) çalışır.
    ek_yonetici=True : zaten ADMIN olsa da yeni bir yönetici ekler ve olayı denetim kaydına yazar."""
    if not GECERLI_KULLANICI_ADI.fullmatch(kullanici_adi or ""):
        raise IlkAdminHatasi("Kullanıcı adı 3-50 karakter olmalı; harf, rakam, _ . - içerebilir.")

    cursor.execute("SELECT rol_id FROM roller WHERE rol_adi = 'ADMIN';")
    rol = cursor.fetchone()
    if rol is None:
        raise IlkAdminHatasi("ADMIN rolü bulunamadı. Önce 'python -m alembic upgrade head' çalıştırın.")

    if not ek_yonetici:
        cursor.execute("SELECT 1 FROM kullanicilar WHERE rol_id = %s LIMIT 1;", (rol[0],))
        if cursor.fetchone() is not None:
            raise IlkAdminHatasi(
                "Veritabanında zaten bir ADMIN kullanıcısı var; yeni hesap eklenmedi. "
                "İkinci bir yönetici gerekiyorsa: python scripts/ilk_admin_olustur.py --ek-yonetici"
            )

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
    if ek_yonetici:
        denetim_kaydi_olustur(
            None, olay_turu="CREATE", kullanici_id=kullanici_id,
            hedef_tablo="kullanicilar", hedef_kayit_id=kullanici_id, mevcut_cursor=cursor,
        )
    return kullanici_adi, gecici_parola, personel_kodu


def main(argv=None, girdi=input):
    ayrac = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ayrac.add_argument("--kullanici-adi", default=None,
                       help="Yönetici kullanıcı adı (ilk kurulumda varsayılan: admin; --ek-yonetici ile sorulur)")
    ayrac.add_argument("--ek-yonetici", action="store_true",
                       help="Zaten bir yönetici varken ikinci bir yönetici hesabı ekler (onay ister)")
    ayrac.add_argument("--evet", action="store_true", help="--ek-yonetici için onay sormadan devam et")
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
            kullanici_adi = args.kullanici_adi
            if args.ek_yonetici:
                mevcut = mevcut_yoneticiler(cursor)
                print("Mevcut yöneticiler: " + (", ".join(mevcut) if mevcut else "(yok)"))
                if not kullanici_adi:
                    kullanici_adi = girdi("Yeni yöneticinin kullanıcı adı: ").strip()
                if not kullanici_adi:
                    raise IlkAdminHatasi("Kullanıcı adı boş bırakılamaz. Hiçbir şey değiştirilmedi.")
                if not args.evet:
                    print(f"'{kullanici_adi}' adında yeni bir YÖNETİCİ (ADMIN) hesabı açılacak.")
                    if girdi("Devam etmek için EVET yazın: ").strip() != "EVET":
                        print("Vazgeçildi. Hiçbir şey değiştirilmedi.")
                        return 0
            kullanici_adi, parola, personel_kodu = admin_olustur(
                cursor, kullanici_adi or "admin", ek_yonetici=args.ek_yonetici
            )
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
