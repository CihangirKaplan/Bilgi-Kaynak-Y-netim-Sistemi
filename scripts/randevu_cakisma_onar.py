"""TKYS - Randevu çakışma kurallarının (EXCLUDE kısıtları) kontrolü ve onarımı.

Neden: `psikolog_randevu_cakisma` ve `oda_randevu_cakisma` kuralları, aynı psikoloğa ya da aynı odaya aynı saatte iki PLANLANDI randevu
verilmesini VERİTABANI seviyesinde engeller (migration d39bab18d6fe). Bu migration bazı kurulumlarda atlanmış olabilir
(`python scripts/sema_dogrula.py` çıktısında `randevular.oda_randevu_cakisma` / `psikolog_randevu_cakisma` EKSİK görünür). Kurallar yokken uygulama
çakışmayı kodla kontrol eder, ama aynı anda gelen iki istek birbirini geçebilir ve çakışan randevu kaydedilebilir.

Kontrol (yalnızca okur): hangi kural eksik, mevcut randevular arasında çakışma var mı?
    python scripts/randevu_cakisma_onar.py kontrol

Onarım: eksik kuralları ekler. Çakışan randevu VARSA kural eklenemez; araç çakışmaları listeler ve hiçbir şey yapmaz (önce arayüzden randevulardan
birini iptal edin ya da saatini değiştirin). Tam yetkili kimlik gerekir (.env: DB_MIGRATION_USER / DB_MIGRATION_PASSWORD; yoksa DB_USER).
    python scripts/randevu_cakisma_onar.py uygula --dene      # dener, SONUNDA GERİ ALIR (hiçbir şey değişmez)
    python scripts/randevu_cakisma_onar.py uygula             # uygular

Önce yedek alın: python scripts/backup/veritabani_yedekle.py. Kurallar yalnızca randevular tablosuna kısıt ekler; veri silmez ya da değiştirmez.
Çıkış kodu: 0 = tamam, 1 = sorun var.
"""
import argparse
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK))

# (kural adı, sütun, açıklama) - migration d39bab18d6fe ile aynı tanım
KURALLAR = (
    ("psikolog_randevu_cakisma", "psikolog_id", "aynı psikoloğa"),
    ("oda_randevu_cakisma", "oda_id", "aynı odaya"),
)
LISTE_SINIRI = 20


def kural_sql(ad, sutun):
    """Kuralı ekleyen SQL. Ad ve sütun bu dosyadaki sabitlerden gelir (kullanıcı girdisi değildir)."""
    return (f"ALTER TABLE randevular ADD CONSTRAINT {ad} EXCLUDE USING gist ({sutun} WITH =, "
            "tsrange(baslangic_zamani, bitis_zamani, '[)') WITH &&) WHERE (durum = 'PLANLANDI')")


# ----------------------------------------------------------------------------- veri okuma / yazma
def var_olan_kurallar(cursor):
    cursor.execute("SELECT conname FROM pg_constraint WHERE conrelid = 'randevular'::regclass AND contype = 'x'")
    return {r[0] for r in cursor.fetchall()}


def eksik_kurallar(cursor):
    var = var_olan_kurallar(cursor)
    return [(ad, sutun, aciklama) for ad, sutun, aciklama in KURALLAR if ad not in var]


def cakismalar(cursor, sutun):
    """PLANLANDI randevular arasında, aynı `sutun` (psikolog_id / oda_id) için zaman aralığı çakışan çiftler."""
    if sutun not in {s for _, s, _ in KURALLAR}:
        raise ValueError(f"beklenmeyen sütun: {sutun}")
    cursor.execute(
        f"SELECT a.randevu_id, a.danisan_kod_id, a.baslangic_zamani, a.bitis_zamani, "
        f"       b.randevu_id, b.danisan_kod_id, b.baslangic_zamani, b.bitis_zamani "
        f"FROM randevular a JOIN randevular b ON a.randevu_id < b.randevu_id AND a.{sutun} = b.{sutun} "
        f"WHERE a.durum = 'PLANLANDI' AND b.durum = 'PLANLANDI' "
        f"AND tsrange(a.baslangic_zamani, a.bitis_zamani, '[)') && tsrange(b.baslangic_zamani, b.bitis_zamani, '[)') "
        f"ORDER BY a.baslangic_zamani, a.randevu_id")
    return [{"a": r[0], "a_kod": r[1], "a_bas": r[2], "a_bit": r[3], "b": r[4], "b_kod": r[5], "b_bas": r[6], "b_bit": r[7]} for r in cursor.fetchall()]


def uygula(cursor, eksik):
    """Eksik kuralları ekler (btree_gist eklentisi gerekir)."""
    cursor.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    for ad, sutun, _ in eksik:
        cursor.execute(kural_sql(ad, sutun))


# ----------------------------------------------------------------------------- karar mantığı (saf işlev)
def karar(eksik, cakisma_sayilari):
    """(sorunlar, bilgiler, uygulanabilir_mi). eksik: [(ad, sutun, aciklama)]; cakisma_sayilari: {sutun: adet}."""
    sorunlar, bilgiler = [], []
    if not eksik:
        bilgiler.append("iki çakışma kuralı da veritabanında var: yapılacak bir şey yok.")
        return sorunlar, bilgiler, False
    engel = False
    for ad, sutun, aciklama in eksik:
        sorunlar.append(f"kural eksik: {ad} ({aciklama} aynı saatte iki randevu veritabanı seviyesinde engellenmiyor)")
        adet = cakisma_sayilari.get(sutun, 0)
        if adet:
            engel = True
            sorunlar.append(f"{sutun}: {adet} çakışan randevu çifti var; kural eklenemez, önce çözün.")
        else:
            bilgiler.append(f"{sutun}: çakışan randevu yok, kural eklenebilir.")
    return sorunlar, bilgiler, not engel


# ----------------------------------------------------------------------------- komut satırı
def _yaz_cakismalar(sutun, liste):
    for c in liste[:LISTE_SINIRI]:
        print(f"         {sutun}: randevu {c['a']} ({c['a_kod']}) {c['a_bas']:%d.%m.%Y %H:%M}-{c['a_bit']:%H:%M}  ↔  "
              f"randevu {c['b']} ({c['b_kod']}) {c['b_bas']:%d.%m.%Y %H:%M}-{c['b_bit']:%H:%M}")
    if len(liste) > LISTE_SINIRI:
        print(f"         ... ve {len(liste) - LISTE_SINIRI} çift daha")


def _baglan(tam_yetki):
    import os

    import psycopg2
    from dotenv import load_dotenv

    load_dotenv(KOK / ".env")
    kullanici, parola = os.getenv("DB_USER"), os.getenv("DB_PASSWORD")
    if tam_yetki:
        from server.sema_kimligi import sema_kimligi

        kullanici, parola = sema_kimligi()
    return psycopg2.connect(dbname=os.getenv("DB_NAME"), user=kullanici, password=parola, host=os.getenv("DB_HOST"), port=os.getenv("DB_PORT"))


def main(argv=None):
    ayrac = argparse.ArgumentParser(description="Randevu çakışma kurallarının kontrolü ve onarımı")
    ayrac.add_argument("komut", choices=("kontrol", "uygula"))
    ayrac.add_argument("--dene", action="store_true", help="uygula komutunda: dener ama sonunda GERİ ALIR (hiçbir şey değişmez)")
    arg = ayrac.parse_args(argv)

    conn = _baglan(tam_yetki=arg.komut == "uygula")
    try:
        with conn.cursor() as cursor:
            eksik = eksik_kurallar(cursor)
            sayilar, ayrintilar = {}, {}
            for _, sutun, _ in eksik:
                ayrintilar[sutun] = cakismalar(cursor, sutun)
                sayilar[sutun] = len(ayrintilar[sutun])
            sorunlar, bilgiler, uygulanabilir = karar(eksik, sayilar)
            for b in bilgiler:
                print(f"[TAMAM]  {b}")
            for s in sorunlar:
                print(f"[SORUN]  {s}")
            for sutun, liste in ayrintilar.items():
                _yaz_cakismalar(sutun, liste)

            if arg.komut == "kontrol":
                if not eksik:
                    print("\nKURALLAR YERİNDE.")
                    return 0
                print("\n" + ("Kurallar eklenebilir: 'uygula' komutunu çalıştırın (önce --dene ile deneyin)." if uygulanabilir
                              else "Önce yukarıdaki çakışan randevuları arayüzden çözün (birini iptal edin ya da saatini değiştirin), sonra yeniden kontrol edin."))
                return 1

            if not eksik:
                return 0
            if not uygulanabilir:
                print("\nHİÇBİR ŞEY DEĞİŞTİRİLMEDİ: çakışan randevular varken kural eklenemez.")
                return 1
            uygula(cursor, eksik)
            kalan = eksik_kurallar(cursor)
            if kalan:
                print(f"\n[SORUN]  uygulandı ama {len(kalan)} kural hâlâ eksik görünüyor; geri alınıyor.")
                conn.rollback()
                return 1
            if arg.dene:
                conn.rollback()
                print("\nDENEME BAŞARILI (geri alındı, hiçbir şey değişmedi). Uygulamak için --dene olmadan çalıştırın.")
                return 0
            conn.commit()
            print(f"\nUYGULANDI: {len(eksik)} kural eklendi. Doğrulamak için: python scripts/sema_dogrula.py")
            return 0
    except Exception as hata:  # noqa: BLE001 - kullanıcıya olduğu gibi gösterilir
        conn.rollback()
        print(f"\n[SORUN]  işlem hata verdi, hiçbir şey değişmedi: {hata}")
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
