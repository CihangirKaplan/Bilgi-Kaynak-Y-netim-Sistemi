"""Yönetici (ADMIN) parolasını unutulduğunda kurtarma aracı — yalnızca SUNUCU bilgisayarında çalıştırılır.

Yönetici hesaplarının parolası UYGULAMADAN sıfırlanamaz (başka bir yönetici de sıfırlayamaz); tek yol bu araçtır. Veritabanı
ayarlarına (.env) erişimi olan kişi, ADMIN hesabına rastgele bir geçici parola verir. Parola ekrana BİR KEZ yazılır ve
GEÇİCİ PAROLA SÜRESİ (varsayılan 48 saat) içinde kullanılmalıdır; hesap ilk girişte yeni parola belirlemeye zorlanır, hatalı giriş
kilidi kalkar, bekleyen parola talebi kapanır ve olay denetim kaydına (PASSWORD_RESET) yazılır.

Kimin yaptığı kayıt altına alınır: araç işlemi yapan kişinin adını sorar ve (sunucu kullanıcısı, bilgisayar adı, zaman ve hedef hesapla
birlikte) yalnızca-eklenebilen `logs/admin_kurtarma.log` dosyasına yazar. Denetim tablosunda serbest metin alanı bulunmadığı için bu
bilgi veritabanına değil dosyaya yazılır.

Yalnızca ADMIN hesapları için çalışır; diğer kullanıcıların parolasını yönetici uygulamadan sıfırlar.

Kullanım:
    python scripts/admin_parola_kurtar.py
    python scripts/admin_parola_kurtar.py --kullanici-adi admin --yapan "Ad Soyad"
"""

import argparse
import getpass
import os
import socket
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import psycopg2
from dotenv import load_dotenv

from server.denetim import denetim_kaydi_olustur
from server.guvenlik import GECICI_PAROLA_BITIS_SQL, GECICI_PAROLA_GECERLILIK_SAAT, gecici_parola_uret, parola_hashle

load_dotenv()

GUNLUK_DOSYASI = Path(__file__).resolve().parents[1] / "logs" / "admin_kurtarma.log"
YAPAN_EN_AZ, YAPAN_EN_COK = 3, 100


class KurtarmaHatasi(Exception):
    """Kullanıcıya olduğu gibi gösterilecek, beklenen hata."""


def yoneticileri_listele(cursor):
    """Aktif ADMIN hesaplarının kullanıcı adları (alfabetik)."""
    cursor.execute(
        """
        SELECT k.kullanici_adi
        FROM kullanicilar k
        JOIN roller r ON r.rol_id = k.rol_id
        WHERE r.rol_adi = 'ADMIN' AND k.aktif_mi = TRUE
        ORDER BY k.kullanici_adi;
        """
    )
    return [satir[0] for satir in cursor.fetchall()]


def admin_parolasini_sifirla(cursor, kullanici_adi):
    """ADMIN hesabına geçici parola verir. (kullanici_adi, gecici_parola) döndürür; commit çağırana aittir."""
    cursor.execute(
        """
        SELECT k.kullanici_id, k.aktif_mi
        FROM kullanicilar k
        JOIN roller r ON r.rol_id = k.rol_id
        WHERE k.kullanici_adi = %s AND r.rol_adi = 'ADMIN'
        FOR UPDATE OF k;
        """,
        (kullanici_adi,),
    )
    hesap = cursor.fetchone()
    if hesap is None:
        raise KurtarmaHatasi(
            f"'{kullanici_adi}' adında bir yönetici (ADMIN) hesabı bulunamadı. "
            "Bu araç yalnızca yönetici hesapları içindir."
        )
    kullanici_id, aktif = hesap
    if not aktif:
        raise KurtarmaHatasi(f"'{kullanici_adi}' hesabı pasif; bu araç pasif hesapları açmaz.")

    gecici_parola = gecici_parola_uret()
    cursor.execute(
        f"""
        UPDATE kullanicilar
        SET parola_hash = %s,
            ilk_giris_mi = TRUE,
            basarisiz_giris_sayisi = 0,
            kilit_bitis_zamani = NULL,
            gecici_parola_bitis = {GECICI_PAROLA_BITIS_SQL}
        WHERE kullanici_id = %s;
        """,
        (parola_hashle(gecici_parola), kullanici_id),
    )
    # Bu hesap için bekleyen parola talebi varsa karşılanmış olur (uygulamadan kimse kapatmadı).
    cursor.execute(
        """
        UPDATE parola_sifirlama_talepleri
        SET durum = 'TAMAMLANDI', kapanis_zamani = CURRENT_TIMESTAMP, kapatan_kullanici_id = NULL
        WHERE kullanici_id = %s AND durum = 'ACIK';
        """,
        (kullanici_id,),
    )
    denetim_kaydi_olustur(
        None, olay_turu="PASSWORD_RESET", kullanici_id=kullanici_id,
        hedef_tablo="kullanicilar", hedef_kayit_id=kullanici_id, mevcut_cursor=cursor,
    )
    return kullanici_adi, gecici_parola


def hesap_sec(yoneticiler, istenen, girdi):
    """Hangi yönetici hesabının kurtarılacağını belirler."""
    if not yoneticiler:
        raise KurtarmaHatasi("Veritabanında aktif bir yönetici (ADMIN) hesabı yok. "
                             "Yeni hesap için 'python scripts/ilk_admin_olustur.py' çalıştırın.")
    if istenen:
        return istenen
    if len(yoneticiler) == 1:
        return yoneticiler[0]
    print("Yönetici hesapları:")
    for sira, ad in enumerate(yoneticiler, 1):
        print(f"  {sira}) {ad}")
    secim = girdi("Hangisi? Numarasını yazın: ").strip()
    if not secim.isdigit() or not 1 <= int(secim) <= len(yoneticiler):
        raise KurtarmaHatasi("Geçersiz seçim. Hiçbir şey değiştirilmedi.")
    return yoneticiler[int(secim) - 1]


def yapan_kisiyi_al(istenen, girdi):
    """İşlemi yapan kişinin adı (zorunlu). Günlük satırını bozmasın diye satır sonu ve '|' temizlenir."""
    ad = istenen if istenen else girdi("Bu işlemi yapan kişinin adı soyadı: ")
    ad = " ".join(str(ad).replace("|", " ").split())
    if not YAPAN_EN_AZ <= len(ad) <= YAPAN_EN_COK:
        raise KurtarmaHatasi(f"İşlemi yapan kişinin adı {YAPAN_EN_AZ}-{YAPAN_EN_COK} karakter olmalıdır. Hiçbir şey değiştirilmedi.")
    return ad


def kurtarma_gunlugune_yaz(yapan, hedef, gunluk_dosyasi=None, simdi=None):
    """Kurtarmayı yapan kişiyi, sunucu kullanıcısını ve bilgisayarı yalnızca-eklenebilen günlüğe yazar."""
    dosya = Path(gunluk_dosyasi or GUNLUK_DOSYASI)
    dosya.parent.mkdir(parents=True, exist_ok=True)
    satir = " | ".join([
        (simdi or datetime.now()).isoformat(timespec="seconds"),
        f"yapan={yapan}",
        f"hedef={hedef}",
        f"sunucu_kullanicisi={getpass.getuser()}",
        f"bilgisayar={socket.gethostname()}",
    ])
    with open(dosya, "a", encoding="utf-8") as akis:
        akis.write(satir + "\n")
    return satir


def main(argv=None, girdi=input):
    ayrac = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ayrac.add_argument("--kullanici-adi", help="Kurtarılacak yönetici hesabı (verilmezse listeden seçilir)")
    ayrac.add_argument("--yapan", help="İşlemi yapan kişinin adı soyadı (verilmezse sorulur; günlüğe yazılır)")
    ayrac.add_argument("--evet", action="store_true", help="Onay sormadan devam et")
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
            hedef = hesap_sec(yoneticileri_listele(cursor), args.kullanici_adi, girdi)
            yapan = yapan_kisiyi_al(args.yapan, girdi)
            if not args.evet:
                print(f"'{hedef}' hesabının parolası sıfırlanacak. Eski parola artık geçmeyecek.")
                if girdi("Devam etmek için EVET yazın: ").strip() != "EVET":
                    print("Vazgeçildi. Hiçbir şey değiştirilmedi.")
                    return 0
            kullanici_adi, parola = admin_parolasini_sifirla(cursor, hedef)
        conn.commit()
    except KurtarmaHatasi as hata:
        if conn is not None:
            conn.rollback()
        print(f"HATA: {hata}")
        return 1
    except psycopg2.Error:
        if conn is not None:
            conn.rollback()
        print("HATA: Veritabanına bağlanılamadı veya işlem yapılamadı. .env ayarlarını ve PostgreSQL'in "
              "çalıştığını kontrol edin. Hiçbir şey değiştirilmedi.")
        return 1
    finally:
        if conn is not None:
            conn.close()

    gunluk_uyarisi = None
    try:
        kurtarma_gunlugune_yaz(yapan, kullanici_adi)
    except OSError:
        gunluk_uyarisi = f"UYARI: Kurtarma günlüğüne yazılamadı ({GUNLUK_DOSYASI}). İşlemi kendiniz not edin."

    print()
    print("Parola sıfırlandı.")
    print(f"  Kullanıcı adı : {kullanici_adi}")
    print(f"  Geçici parola : {parola}")
    print(f"  Geçerlilik    : {GECICI_PAROLA_GECERLILIK_SAAT} saat (bu sürede giriş yapılmazsa araç yeniden çalıştırılmalıdır)")
    print()
    print("Bu parola bir daha gösterilmez; şimdi not alın. Uygulamaya bu parolayla girin,")
    print("ekran sizden yeni parola belirlemenizi isteyecek.")
    if gunluk_uyarisi:
        print()
        print(gunluk_uyarisi)
    return 0


if __name__ == "__main__":
    sys.exit(main())
