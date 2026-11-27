import json

import psycopg2  # noqa: F401  (kullanılmıyor görünür ama testler bağlantıyı server.denetim.psycopg2 üzerinden değiştirir)

from server.vt_baglanti import vt_baglan
from psycopg2 import sql
from psycopg2.extras import Json


def _json(ayrinti):
    """Denetim kaydının ayrıntı sütunu için JSON (Türkçe karakterler korunur, tarih gibi türler metne çevrilir)."""
    return Json(ayrinti, dumps=lambda nesne: json.dumps(nesne, ensure_ascii=False, default=str))

# Kalıcı silinirken içeriği denetim kaydına yazılabilen tablolar -> birincil anahtar sütunu.
SILINEBILIR_TABLOLAR = {
    "cihaz_bakimlari": "bakim_id",
    "cihaz_kalibrasyonlari": "kalibrasyon_id",
    "cihaz_bakim_planlari": "plan_id",
    "ogrenci_faaliyet_takip": "takip_id",
    "faaliyet_birimleri": "birim_id",
    "roller": "rol_id",
    "ogrenciler": "ogrenci_id",
    "odalar": "oda_id",
}

# Kişisel veri içeren tablolarda denetim kaydına YALNIZCA bu alanlar yazılır; kalanı (ad soyad, telefon, öğrenci numarası...)
# yazılmaz. Öğrencinin saklama süresi sonunda silinmesi (pasife alındıktan 2 yıl) bir kişisel veri imhasıdır: silinen kişinin bilgisi denetim kaydında kalmamalıdır.
SAKLANACAK_ALANLAR = {
    "ogrenciler": ("ogrenci_id", "tur", "aktif_mi", "olusturulma_tarihi"),
}


def silinen_ayrintisi(tablo: str, satir: dict) -> dict:
    """Silinen satırdan denetim kaydına yazılacak içeriği hazırlar (kişisel alanlar ayıklanır)."""
    izinli = SAKLANACAK_ALANLAR.get(tablo)
    if izinli is None:
        return {"silinen": satir}
    return {
        "silinen": {alan: satir.get(alan) for alan in izinli},
        "maskelenen_alanlar": sorted(set(satir) - set(izinli)),
    }


def satiri_sil_ve_ayrintisini_al(cursor, tablo: str, kimlik: int):
    """Satırı siler ve silinen içeriği döndürür (tek DELETE ... RETURNING: okuma ile silme arasında değişiklik olamaz).

    Satır yoksa None döner. Dönen değer, denetim_kaydi_olustur(..., ayrinti=...) ile aynı işlemde (transaction) denetim
    kaydına yazılmalıdır. Yalnızca SILINEBILIR_TABLOLAR içindeki tablolar kabul edilir (tablo adı koddan gelir, kullanıcıdan değil).
    """
    anahtar = SILINEBILIR_TABLOLAR[tablo]
    cursor.execute(
        sql.SQL("DELETE FROM {t} WHERE {k} = %s RETURNING to_jsonb({t})").format(
            t=sql.Identifier(tablo), k=sql.Identifier(anahtar)),
        (kimlik,),
    )
    satir = cursor.fetchone()
    if satir is None:
        return None
    return silinen_ayrintisi(tablo, satir[0])


def psikolog_odalarini_oku(cursor, kullanici_id: int) -> list:
    """Psikoloğa atanmış oda kimlikleri (denetim kaydında 'önceki/yeni odalar' için)."""
    cursor.execute("SELECT oda_id FROM psikolog_odalar WHERE kullanici_id = %s ORDER BY oda_id;", (kullanici_id,))
    return [satir[0] for satir in cursor.fetchall()]


def denetim_kaydi_olustur(
    vt_ayarlari: dict,
    olay_turu: str,
    kullanici_id: int | None = None,
    hedef_tablo: str | None = None,
    hedef_kayit_id: int | None = None,
    mevcut_cursor=None,
    ayrinti: dict | None = None,
) -> None:
    conn = None
    cursor = mevcut_cursor

    try:
        # Mevcut cursor verilmediyse yeni bağlantı aç.
        if cursor is None:
            conn = vt_baglan(vt_ayarlari)
            cursor = conn.cursor()

        if ayrinti is None:
            cursor.execute(
                """
                INSERT INTO denetim_kayitlari (
                    kullanici_id,
                    olay_turu,
                    hedef_tablo,
                    hedef_kayit_id
                )
                VALUES (%s, %s, %s, %s);
                """,
                (
                    kullanici_id,
                    olay_turu,
                    hedef_tablo,
                    hedef_kayit_id
                )
            )
        else:
            # ayrinti: silinen verinin içeriği ya da önceki/yeni değerler (JSON).
            cursor.execute(
                """
                INSERT INTO denetim_kayitlari (
                    kullanici_id,
                    olay_turu,
                    hedef_tablo,
                    hedef_kayit_id,
                    ayrinti
                )
                VALUES (%s, %s, %s, %s, %s);
                """,
                (
                    kullanici_id,
                    olay_turu,
                    hedef_tablo,
                    hedef_kayit_id,
                    _json(ayrinti),
                )
            )

        # Yalnızca bağlantıyı bu fonksiyon açtıysa commit yap.
        if conn is not None:
            conn.commit()

    except Exception:
        if conn is not None:
            conn.rollback()
        raise

    finally:
        # Dışarıdan verilen cursor ve bağlantı burada kapatılmaz.
        if conn is not None:
            cursor.close()
            conn.close()


def psikolog_oda_degisikligini_yaz(cursor, islem_yapan_id: int, kullanici_id: int, onceki_odalar: list) -> None:
    """Psikolog oda atamaları değiştikten sonra denetim kaydı yazar (aynı işlemde).

    Her zaman UPDATE kaydı (önceki/yeni odalar); atamadan kaldırılan oda varsa ayrıca DELETE kaydı (kaldırılan odalar).
    """
    yeni_odalar = psikolog_odalarini_oku(cursor, kullanici_id)
    kaldirilan = sorted(set(onceki_odalar) - set(yeni_odalar))
    denetim_kaydi_olustur(
        None, "UPDATE", islem_yapan_id, "psikolog_odalar", kullanici_id, mevcut_cursor=cursor,
        ayrinti={"onceki_oda_idleri": sorted(onceki_odalar), "yeni_oda_idleri": yeni_odalar},
    )
    if kaldirilan:
        denetim_kaydi_olustur(
            None, "DELETE", islem_yapan_id, "psikolog_odalar", kullanici_id, mevcut_cursor=cursor,
            ayrinti={"silinen": {"kullanici_id": kullanici_id, "oda_idleri": kaldirilan}},
        )


def ayrintili_kayit_yaz(cursor, kullanici_id, olay_turu, hedef_tablo, hedef_kayit_id, **ayrinti):
    """Verilen alanları ayrıntı olarak denetim kaydına yazar (önceki/yeni değer, neden, etkilenen sayı...). Aynı işlemde çağrılır.

    Yalnızca kod/durum/rol adı gibi kişisel olmayan değerler verilmelidir (FR-008); parola, ad soyad, telefon gibi alanlar YAZILMAZ."""
    cursor.execute(
        "INSERT INTO denetim_kayitlari (kullanici_id, olay_turu, hedef_tablo, hedef_kayit_id, ayrinti) VALUES (%s, %s, %s, %s, %s);",
        (kullanici_id, olay_turu, hedef_tablo, hedef_kayit_id, _json(ayrinti)),
    )


def durum_degisikligi_yaz(cursor, kullanici_id, olay_turu, hedef_tablo, hedef_kayit_id, onceki, yeni, **ek):
    """Durum değişikliğini ÖNCEKİ ve YENİ değerle denetim kaydına yazar (kim, neyi, neyden neye). Aynı işlemde (transaction) çağrılır.

    Yalnızca kod/durum gibi kişisel olmayan değerler verilmelidir (FR-008); danışan kodu da kişisel veri değildir."""
    cursor.execute(
        "INSERT INTO denetim_kayitlari (kullanici_id, olay_turu, hedef_tablo, hedef_kayit_id, ayrinti) VALUES (%s, %s, %s, %s, %s);",
        (kullanici_id, olay_turu, hedef_tablo, hedef_kayit_id, _json({"onceki": onceki, "yeni": yeni, **ek})),
    )
