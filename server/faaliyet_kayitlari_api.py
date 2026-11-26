"""Faaliyet kayıtları uçları (öğrenci faaliyet kaydı ekleme, listeleme, düzenleme, silme). `server/sunucu.py` içinden ayrıldı."""
from typing import Optional

from fastapi import APIRouter, HTTPException, Response

from server.denetim import satiri_sil_ve_ayrintisini_al
from server.modeller import FaaliyetKayitModeli
from server.vt_ayarlari import VT_AYARLARI
from server.vt_baglanti import vt_baglan
from server.yetki_baglama import yetkiyle_bagla


# --- GÜNCELLENEN: YENİ TABLOYA (ÖĞRENCİ TAKİP) KAYIT ATAR ---
def faaliyet_kaydi_ekle(kayit: FaaliyetKayitModeli, yetkili_id: int | None = None):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        # Kayıt ogrenci_faaliyet_takip tablosuna yazılır (miktar "adet" sütununa gider).
        cursor.execute("""
            INSERT INTO ogrenci_faaliyet_takip
            (ogrenci_id, faaliyet_id, birim_id, adet,
             faaliyet_tarihi, kayit_puani)
            SELECT %s, f.faaliyet_id, %s, %s, CURRENT_DATE, f.puan
            FROM faaliyetler AS f
            WHERE f.faaliyet_id = %s AND f.aktif_mi = TRUE
            RETURNING takip_id;
        """, (
            kayit.ogrenci_id,
            kayit.birim_id,
            kayit.miktar,
            kayit.faaliyet_id
        ))
        if cursor.rowcount != 1:
            raise HTTPException(
                status_code=400,
                detail="Aktif faaliyet türü bulunamadı."
            )

        yeni_id = cursor.fetchone()[0]

        # Denetim kaydı
        from server.denetim import denetim_kaydi_olustur
        denetim_kaydi_olustur(VT_AYARLARI, "CREATE", yetkili_id, "ogrenci_faaliyet_takip", yeni_id, mevcut_cursor=cursor)

        conn.commit()
        return {"durum": "basarili", "mesaj": "Öğrenci faaliyeti başarıyla sisteme işlendi."}
    except HTTPException:
        if conn is not None:
            conn.rollback()
        raise
    except Exception:
        if conn is not None:
            conn.rollback()
        raise HTTPException(
            status_code=500,
            detail="İşlem sırasında beklenmeyen bir sunucu hatası oluştu."
        )
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


# --- Faaliyet kayıtları listesi ---
def faaliyet_kayitlarini_getir(
    limit: Optional[int] = None,
    offset: int = 0,
    response: Response = None,
    kullanici_id: int | None = None,
):
    """Faaliyet kayıtları (en yeni önce). limit verilirse toplam sayı X-Toplam-Kayit başlığında döner."""
    if limit is not None and (limit < 1 or limit > 5000):
        raise HTTPException(status_code=422, detail="limit 1 ile 5000 arasında olmalıdır.")
    if offset < 0:
        raise HTTPException(status_code=422, detail="offset negatif olamaz.")
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        # 4 tabloyu birleştirir; toplam puan = adet x kaydın puanı
        sorgu = """
        SELECT
            t.takip_id,
            o.ad_soyad,
            o.ogrenci_numarasi,
            f.faaliyet_adi,
            t.adet,
            b.birim_adi,
            (t.adet * t.kayit_puani) AS toplam_puan,
            t.faaliyet_tarihi,
            t.ogrenci_id,
            t.faaliyet_id,
            t.birim_id
        FROM ogrenci_faaliyet_takip t
        JOIN ogrenciler o ON t.ogrenci_id = o.ogrenci_id
        JOIN faaliyetler f ON t.faaliyet_id = f.faaliyet_id
        JOIN faaliyet_birimleri b ON t.birim_id = b.birim_id
        ORDER BY t.olusturulma_tarihi DESC, t.takip_id DESC
        """
        if limit is None:
            cursor.execute(sorgu + ";")
        else:
            cursor.execute("SELECT COUNT(*) FROM ogrenci_faaliyet_takip;")
            if response is not None:
                response.headers["X-Toplam-Kayit"] = str((cursor.fetchone() or (0,))[0])
            cursor.execute(sorgu + " LIMIT %s OFFSET %s;", (limit, offset))

        kayitlar = []
        for row in cursor.fetchall():
            kayitlar.append({
                "id": row[0],
                "ad_soyad": row[1],
                "ogrenci_no": row[2],
                "faaliyet_adi": row[3],
                "miktar": f"{row[4]} {row[5]}", # Örn: "3 KISI" veya "5 SAAT"
                "toplam_puan": row[6],
                "tarih": row[7].strftime("%d.%m.%Y") if row[7] else "",
                "ogrenci_id": row[8],
                "faaliyet_id": row[9],
                "birim_id": row[10],
            })
        return kayitlar
    except Exception:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=500, detail="İşlem sırasında beklenmeyen bir sunucu hatası oluştu.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


# --- Faaliyet kaydı düzenleme (PUT) ---
def faaliyet_kaydi_guncelle(takip_id: int, kayit: FaaliyetKayitModeli, yetkili_id: int | None = None):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        # Kaydı kilitleyip önceki değerlerini al (denetim kaydına "neyden neye" yazılır).
        alanlar = ("ogrenci_id", "faaliyet_id", "birim_id", "adet", "kayit_puani")
        cursor.execute(
            "SELECT ogrenci_id, faaliyet_id, birim_id, adet, kayit_puani "
            "FROM ogrenci_faaliyet_takip WHERE takip_id = %s FOR UPDATE;",
            (takip_id,)
        )
        eski_satir = cursor.fetchone()
        if not eski_satir:
            raise HTTPException(status_code=404, detail="Güncellenecek kayıt bulunamadı.")
        onceki = dict(zip(alanlar, eski_satir))

        # Faaliyet türü değişmediyse kayıttaki puan korunur (sonradan değişen tür puanı eski kaydı etkilemez).
        # Değiştiyse yeni tür aktif olmalı ve kayıt o türün güncel puanını alır.
        kayit_puani = onceki.get("kayit_puani")
        if onceki.get("faaliyet_id") != kayit.faaliyet_id:
            cursor.execute(
                "SELECT puan FROM faaliyetler WHERE faaliyet_id = %s AND aktif_mi = TRUE;",
                (kayit.faaliyet_id,)
            )
            puan = cursor.fetchone()
            if puan is None:
                raise HTTPException(status_code=400, detail="Aktif faaliyet türü bulunamadı.")
            kayit_puani = puan[0]

        yeni = {
            "ogrenci_id": kayit.ogrenci_id,
            "faaliyet_id": kayit.faaliyet_id,
            "birim_id": kayit.birim_id,
            "adet": kayit.miktar,
            "kayit_puani": kayit_puani,
        }
        if all(onceki.get(alan) == yeni[alan] for alan in alanlar):
            conn.commit()
            return {"durum": "basarili", "mesaj": "Kayıtta değişiklik yapılmadı."}

        cursor.execute("""
            UPDATE ogrenci_faaliyet_takip
            SET ogrenci_id = %s,
                faaliyet_id = %s,
                birim_id = %s,
                adet = %s,
                kayit_puani = %s
            WHERE takip_id = %s;
        """, (
            kayit.ogrenci_id,
            kayit.faaliyet_id,
            kayit.birim_id,
            kayit.miktar,
            kayit_puani,
            takip_id
        ))

        # Denetim kaydı: yalnızca değişen alanların önceki ve yeni değeri (kimlik ve sayı; kişisel veri yok).
        degisen = [alan for alan in alanlar if onceki.get(alan) != yeni[alan]]
        from server.denetim import denetim_kaydi_olustur
        denetim_kaydi_olustur(
            VT_AYARLARI, "UPDATE", yetkili_id, "ogrenci_faaliyet_takip", takip_id, mevcut_cursor=cursor,
            ayrinti={
                "onceki": {alan: onceki.get(alan) for alan in degisen},
                "yeni": {alan: yeni[alan] for alan in degisen},
            },
        )

        conn.commit()
        return {"durum": "basarili", "mesaj": "Kayıt başarıyla güncellendi."}
    except HTTPException:
        if conn is not None:
            conn.rollback()
        raise
    except Exception:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=500, detail="İşlem sırasında beklenmeyen bir sunucu hatası oluştu.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


# --- Faaliyet kaydı silme (DELETE) ---
def faaliyet_kaydi_sil(takip_id: int, yetkili_id: int | None = None):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        # Silinmeden önce kaydın var olup olmadığını kontrol edelim
        cursor.execute("SELECT * FROM ogrenci_faaliyet_takip WHERE takip_id = %s", (takip_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Silinecek kayıt zaten yok veya bulunamadı.")

        # Kaydı veritabanından siliyoruz; silinen içerik denetim kaydına yazılır (kim, neyi sildi).
        silinen = satiri_sil_ve_ayrintisini_al(cursor, "ogrenci_faaliyet_takip", takip_id)
        from server.denetim import denetim_kaydi_olustur
        denetim_kaydi_olustur(VT_AYARLARI, "DELETE", yetkili_id, "ogrenci_faaliyet_takip", takip_id,
                              mevcut_cursor=cursor, ayrinti=silinen)

        conn.commit()
        return {"durum": "basarili", "mesaj": "Kayıt başarıyla silindi!"}
    except HTTPException:
        if conn is not None:
            conn.rollback()
        raise
    except Exception:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=500, detail="İşlem sırasında beklenmeyen bir sunucu hatası oluştu.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


# (yöntem, yol, uç fonksiyonu, yetki parametresi, gereken izin, ek yol ayarları): yetki bağımlılığı kayıt sırasında eklenir.
UCLAR = [
    ("POST", "/api/faaliyet-kayitlari", faaliyet_kaydi_ekle, "yetkili_id", "FAALIYET_KAYITLARI_DUZENLE", {}),
    ("GET", "/api/faaliyet-kayitlari", faaliyet_kayitlarini_getir, "kullanici_id", "FAALIYET_KAYITLARI_DUZENLE", {}),
    ("PUT", "/api/faaliyet-kayitlari/{takip_id}", faaliyet_kaydi_guncelle, "yetkili_id", "FAALIYET_KAYITLARI_DUZENLE", {}),
    ("DELETE", "/api/faaliyet-kayitlari/{takip_id}", faaliyet_kaydi_sil, "yetkili_id", "FAALIYET_KAYITLARI_DUZENLE", {}),
]


def router_olustur(izin_kontrol) -> APIRouter:
    """`izin_kontrol`: `server.sunucu.izin_kontrol` (kimlik doğrulama + izin kontrolü bağımlılığı üreticisi)."""
    router = APIRouter()
    for metod, yol, fonksiyon, parametre, izin, ek in UCLAR:
        router.add_api_route(yol, yetkiyle_bagla(fonksiyon, parametre, izin_kontrol(izin)), methods=[metod], **ek)
    return router
