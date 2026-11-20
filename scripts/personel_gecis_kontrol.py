"""TKYS - Personel/kullanıcı birleşimi (migration b9d4f7a2c613) için geçiş ÖNCESİ ve SONRASI kontrol aracı.

Geçişten ÖNCE (yalnızca okur): geçişe hazır mı? Aktiflikleri farklı kayıt var mı? Verinin "sağlama özeti" bir dosyaya yazılır.
    python scripts/personel_gecis_kontrol.py on

Geçişten SONRA: veri aynı mı (sağlama özeti), yapı doğru mu (görünüm, tetikleyici, yabancı anahtarlar, sayaç) ve yazma denemesi
(personel ekleme/güncelleme/silme; HER ŞEY GERİ ALINIR, kalıcı kayıt kalmaz).
    python scripts/personel_gecis_kontrol.py son

Her iki komut da --dosya ile sağlama dosyasının yerini değiştirebilir (varsayılan: gecis_oncesi.json). Bağlantı bilgisi .env
dosyasındaki DB_* değerleridir. Çıkış kodu: 0 = tamam, 1 = sorun var.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK))

MIGRASYON = "b9d4f7a2c613"
BAGLI_TABLOLAR = (
    ("randevular", "psikolog_id", "randevu_id"),
    ("danisan_kodlari", "olusturan_psikolog_id", "danisan_kod_id"),
    ("cihaz_rezervasyonlari", "rezervasyonu_yapan_personel_id", "rezervasyon_id"),
    ("oda_etkinlikleri", "organize_eden_personel_id", "etkinlik_id"),
)
ESKI_FK_ADLARI = (
    "randevular_psikolog_id_fkey",
    "fk_danisankodlari_personel",
    "cihaz_rezervasyonlari_rezervasyonu_yapan_personel_id_fkey",
    "oda_etkinlikleri_organize_eden_personel_id_fkey",
)


# ----------------------------------------------------------------------------- veri okuma
def _ozet(cursor, sql_metni):
    """Sorgu satırlarının sıralı sağlama özeti ve satır sayısı."""
    cursor.execute(sql_metni)
    satirlar = cursor.fetchall()
    h = hashlib.sha256()
    for satir in satirlar:
        h.update(("|".join("" if v is None else str(v) for v in satir) + "\n").encode("utf-8"))
    return {"adet": len(satirlar), "ozet": h.hexdigest()}


def goruntu_al(cursor):
    """Geçişten etkilenebilecek verinin sağlama özetleri. aktif_mi bilerek dışarıda (geçişte uzlaştırılabilir)."""
    sonuc = {
        "personel": _ozet(cursor, "SELECT personel_id, kullanici_id, personel_kodu, olusturulma_tarihi FROM personel ORDER BY personel_id"),
        "kullanicilar": _ozet(cursor, "SELECT kullanici_id, kullanici_adi, parola_hash, rol_id, olusturulma_tarihi FROM kullanicilar ORDER BY kullanici_id"),
    }
    for tablo, sutun, anahtar in BAGLI_TABLOLAR:
        sonuc[tablo] = _ozet(cursor, f"SELECT {anahtar}, {sutun} FROM {tablo} ORDER BY {anahtar}")
    sonuc["denetim_personel_hedefleri"] = _ozet(
        cursor, "SELECT denetim_id, hedef_kayit_id FROM denetim_kayitlari WHERE hedef_tablo = 'personel' ORDER BY denetim_id")
    return sonuc


def uyumsuz_aktiflikler(cursor):
    cursor.execute(
        "SELECT k.kullanici_adi, k.aktif_mi, p.aktif_mi FROM kullanicilar k JOIN personel p ON p.kullanici_id = k.kullanici_id "
        "WHERE k.aktif_mi <> p.aktif_mi ORDER BY k.kullanici_adi")
    return [{"kullanici_adi": a, "kullanici_aktif": bool(b), "personel_aktif": bool(c)} for a, b, c in cursor.fetchall()]


def personel_turu(cursor):
    """'r' = tablo (geçiş yapılmamış), 'v' = görünüm (geçilmiş), None = yok."""
    cursor.execute("SELECT relkind FROM pg_class WHERE relname = 'personel' AND relnamespace = 'public'::regnamespace")
    satir = cursor.fetchone()
    return satir[0] if satir else None


def alembic_surumleri(cursor):
    cursor.execute("SELECT version_num FROM alembic_version")
    return [r[0] for r in cursor.fetchall()]


def yapi_bilgisi(cursor):
    """Geçiş sonrası beklenen yapının durumu (hepsi True olmalı)."""
    cursor.execute("SELECT count(*) FROM pg_trigger WHERE tgrelid = 'personel'::regclass AND tgname = 'personel_gorunumu_yaz' AND NOT tgisinternal")
    tetikleyici = cursor.fetchone()[0] == 1
    cursor.execute(
        "SELECT conrelid::regclass::text FROM pg_constraint c JOIN pg_attribute fa ON fa.attrelid = c.confrelid AND fa.attnum = ANY (c.confkey) "
        "WHERE c.contype = 'f' AND c.confrelid = 'kullanicilar'::regclass AND fa.attname = 'personel_id' ORDER BY 1")
    hedefler = sorted(r[0] for r in cursor.fetchall())
    cursor.execute("SELECT count(*) FROM pg_constraint WHERE confrelid = 'kullanicilar'::regclass AND conname = ANY(%s)", (list(ESKI_FK_ADLARI),))
    eski_adlar = cursor.fetchone()[0]
    cursor.execute("SELECT COALESCE(max(personel_id), 0) FROM kullanicilar")
    en_buyuk = cursor.fetchone()[0]
    cursor.execute("SELECT last_value, is_called FROM personel_personel_id_seq")
    son, cagrildi = cursor.fetchone()
    return {
        "tetikleyici_var": tetikleyici,
        "dort_baglanti_kullanicilara": hedefler == sorted(t for t, _, _ in BAGLI_TABLOLAR),
        "baglanti_adlari_korundu": eski_adlar == len(ESKI_FK_ADLARI),
        "sayac_eski_kimlikleri_asiyor": (son >= en_buyuk) if cagrildi else (son > en_buyuk or en_buyuk == 0),
    }


def yazma_denemesi(cursor):
    """Görünüme ekleme/güncelleme/silme; sonunda HER ŞEY geri alınır. (ok, aciklama) döndürür."""
    cursor.execute("SAVEPOINT gecis_denemesi")
    try:
        cursor.execute("INSERT INTO kullanicilar (kullanici_adi, parola_hash, rol_id) SELECT 'gecis_denemesi_x', 'x', rol_id FROM roller LIMIT 1 RETURNING kullanici_id")
        kimlik = cursor.fetchone()[0]
        cursor.execute("INSERT INTO personel (kullanici_id, personel_kodu) VALUES (%s, 'GECIS-DENEME') RETURNING personel_id", (kimlik,))
        pid = cursor.fetchone()[0]
        cursor.execute("UPDATE personel SET personel_kodu = 'GECIS-DENEME2', aktif_mi = FALSE WHERE personel_id = %s", (pid,))
        cursor.execute("SELECT personel_kodu, aktif_mi FROM kullanicilar WHERE kullanici_id = %s", (kimlik,))
        if cursor.fetchone() != ("GECIS-DENEME2", False):
            return False, "güncelleme kullanicilar tablosuna yansımadı"
        cursor.execute("DELETE FROM personel WHERE personel_id = %s", (pid,))
        cursor.execute("SELECT personel_id FROM kullanicilar WHERE kullanici_id = %s", (kimlik,))
        if cursor.fetchone()[0] is not None:
            return False, "silme kullanıcının personel alanlarını boşaltmadı"
        return True, "ekleme, güncelleme ve silme çalışıyor (geri alındı)"
    except Exception as hata:  # noqa: BLE001 - kullanıcıya olduğu gibi gösterilir
        return False, f"yazma denemesi hata verdi: {hata}"
    finally:
        cursor.execute("ROLLBACK TO SAVEPOINT gecis_denemesi")


# ----------------------------------------------------------------------------- karar mantığı (saf işlevler)
def on_karar(tur, surumler, uyumsuzlar):
    """(sorunlar, uyarilar, bilgiler). Sorun varsa geçiş yapılmamalıdır."""
    sorunlar, uyarilar, bilgiler = [], [], []
    if tur == "v":
        sorunlar.append("personel zaten görünüm: geçiş uygulanmış görünüyor. 'son' komutuyla sonucu doğrulayın.")
    elif tur is None:
        sorunlar.append("personel tablosu bulunamadı: veritabanı beklenen şemada değil (python scripts/sema_dogrula.py çalıştırın).")
    if MIGRASYON in surumler:
        sorunlar.append(f"migration {MIGRASYON} zaten uygulanmış.")
    if not surumler:
        sorunlar.append("alembic sürüm bilgisi yok: veritabanı migration ile kurulmamış.")
    if uyumsuzlar:
        ornek = ", ".join(f"{u['kullanici_adi']} (kullanıcı {'aktif' if u['kullanici_aktif'] else 'pasif'}, personel {'aktif' if u['personel_aktif'] else 'pasif'})" for u in uyumsuzlar[:10])
        uyarilar.append(
            f"{len(uyumsuzlar)} kayıtta kullanıcı ve personel aktifliği FARKLI. Geçişte ikisinden biri pasifse hesap PASİF olur ve denetim kaydına yazılır. "
            f"Örnekler: {ornek}")
    else:
        bilgiler.append("Kullanıcı ve personel aktiflikleri her kayıtta aynı: geçişte aktiflik değişmeyecek.")
    return sorunlar, uyarilar, bilgiler


def son_karar(onceki, simdi, tur, yapi, yazma):
    """(sorunlar, bilgiler). onceki: 'on' komutunun kaydettiği görüntü; simdi: şimdiki görüntü."""
    sorunlar, bilgiler = [], []
    if tur != "v":
        return ["personel görünüm değil: geçiş uygulanmamış (önce 'python -m alembic upgrade head')."], bilgiler
    for ad, deger in yapi.items():
        (bilgiler if deger else sorunlar).append(f"yapı: {ad} {'tamam' if deger else 'EKSİK/YANLIŞ'}")
    for anahtar, eski in (onceki or {}).get("goruntu", {}).items():
        yeni = simdi.get(anahtar)
        if yeni is None:
            sorunlar.append(f"veri: {anahtar} okunamadı")
        elif eski["adet"] != yeni["adet"]:
            sorunlar.append(f"veri: {anahtar} satır sayısı değişti ({eski['adet']} → {yeni['adet']})")
        elif eski["ozet"] != yeni["ozet"]:
            sorunlar.append(f"veri: {anahtar} içeriği değişti (sağlama özeti farklı)")
        else:
            bilgiler.append(f"veri: {anahtar} aynı ({yeni['adet']} satır)")
    if not onceki:
        sorunlar.append("geçiş öncesi sağlama dosyası bulunamadı: veri karşılaştırması yapılamadı ('on' komutu geçişten önce çalıştırılmalıydı).")
    ok, aciklama = yazma
    (bilgiler if ok else sorunlar).append(f"yazma denemesi: {aciklama}")
    if onceki and onceki.get("uyumsuz_aktiflik"):
        bilgiler.append(f"geçiş öncesi aktifliği farklı {onceki['uyumsuz_aktiflik']} kayıt vardı: bunlar pasif hesap olarak uzlaştırıldı (denetim kayıtlarına bakın)")
    return sorunlar, bilgiler


# ----------------------------------------------------------------------------- komut satırı
def _yaz(sorunlar, uyarilar, bilgiler):
    for b in bilgiler:
        print(f"[TAMAM]  {b}")
    for u in uyarilar:
        print(f"[UYARI]  {u}")
    for s in sorunlar:
        print(f"[SORUN]  {s}")


def _baglan():
    import os

    import psycopg2
    from dotenv import load_dotenv

    load_dotenv(KOK / ".env")
    return psycopg2.connect(dbname=os.getenv("DB_NAME"), user=os.getenv("DB_USER"), password=os.getenv("DB_PASSWORD"),
                            host=os.getenv("DB_HOST"), port=os.getenv("DB_PORT"))


def main(argv=None):
    ayrac = argparse.ArgumentParser(description="Personel/kullanıcı birleşimi geçiş kontrolü")
    ayrac.add_argument("asama", choices=("on", "son"), help="on = geçişten önce, son = geçişten sonra")
    ayrac.add_argument("--dosya", default="gecis_oncesi.json", help="sağlama dosyası (varsayılan: gecis_oncesi.json)")
    arg = ayrac.parse_args(argv)
    dosya = Path(arg.dosya)

    conn = _baglan()
    try:
        conn.autocommit = False
        with conn.cursor() as cursor:
            tur = personel_turu(cursor)
            if arg.asama == "on":
                surumler = alembic_surumleri(cursor)
                uyumsuzlar = uyumsuz_aktiflikler(cursor) if tur == "r" else []
                sorunlar, uyarilar, bilgiler = on_karar(tur, surumler, uyumsuzlar)
                if not sorunlar:
                    kayit = {"goruntu": goruntu_al(cursor), "uyumsuz_aktiflik": len(uyumsuzlar), "alembic": surumler}
                    dosya.write_text(json.dumps(kayit, ensure_ascii=False, indent=2), encoding="utf-8")
                    bilgiler.append(f"sağlama özeti kaydedildi: {dosya}")
                _yaz(sorunlar, uyarilar, bilgiler)
                print("\n" + ("GEÇİŞE HAZIR." if not sorunlar else "GEÇİŞ YAPMAYIN: yukarıdaki sorunları giderin."))
                return 1 if sorunlar else 0

            onceki = json.loads(dosya.read_text(encoding="utf-8")) if dosya.exists() else None
            if tur != "v":
                sorunlar, bilgiler = son_karar(onceki, {}, tur, {}, (False, "atlandı"))
            else:
                sorunlar, bilgiler = son_karar(onceki, goruntu_al(cursor), tur, yapi_bilgisi(cursor), yazma_denemesi(cursor))
            _yaz(sorunlar, [], bilgiler)
            print("\n" + ("GEÇİŞ DOĞRULANDI." if not sorunlar else "SORUN VAR: yedekten geri dönmeyi ya da 'python -m alembic downgrade -1' komutunu düşünün."))
            return 1 if sorunlar else 0
    finally:
        conn.rollback()
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
