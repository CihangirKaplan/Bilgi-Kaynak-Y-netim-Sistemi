"""Faaliyet birimleri uçları (listeleme, ekleme, düzenleme, silme). `server/sunucu.py` içinden ayrıldı."""
from fastapi import APIRouter, HTTPException
import psycopg2

from server.denetim import satiri_sil_ve_ayrintisini_al
from server.modeller import FaaliyetBirimIslemModeli
from server.vt_ayarlari import VT_AYARLARI
from server.vt_baglanti import vt_baglan
from server.yetki_baglama import yetkiyle_bagla


def faaliyet_birimleri_getir(kullanici_id: int | None = None):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        # Sadece aktif olan birimleri listele
        cursor.execute("SELECT birim_id, birim_adi FROM faaliyet_birimleri WHERE aktif_mi = true ORDER BY birim_id;")

        birimler = []
        for kayit in cursor.fetchall():
            birimler.append({
                "id": kayit[0],
                "ad": kayit[1]
            })
        return birimler
    except Exception:
        raise HTTPException(status_code=500, detail="İşlem sırasında beklenmeyen bir sunucu hatası oluştu.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


BIRIM_ADI_KAYITLI_MESAJI = "Bu birim adı zaten mevcut (büyük/küçük harf farkı aynı ad sayılır)."


def faaliyet_birimi_ekle(kayit: FaaliyetBirimIslemModeli, yetkili_id: int | None = None):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        # Birim adları büyük harfle saklanır; tekrar kontrolü de aynı biçimle yapılır.
        ad = kayit.birim_adi.strip().upper()
        if not ad:
            raise HTTPException(status_code=422, detail="Birim adı boş olamaz.")
        cursor.execute("SELECT birim_id FROM faaliyet_birimleri WHERE birim_adi = %s", (ad,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail=BIRIM_ADI_KAYITLI_MESAJI)

        cursor.execute(
            "INSERT INTO faaliyet_birimleri (birim_adi) VALUES (%s) RETURNING birim_id;",
            (ad,)
        )
        yeni_id = cursor.fetchone()[0]

        # Audit Log (Denetim Kaydı)
        from server.denetim import denetim_kaydi_olustur
        denetim_kaydi_olustur(VT_AYARLARI, "CREATE", yetkili_id, "faaliyet_birimleri", yeni_id, mevcut_cursor=cursor)

        conn.commit()
        return {"durum": "basarili", "mesaj": "Birim başarıyla eklendi.", "id": yeni_id}
    except HTTPException:
        raise
    except psycopg2.errors.UniqueViolation:
        # Kontrol ile kayıt arasında aynı adı başka bir istek eklediyse.
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=400, detail=BIRIM_ADI_KAYITLI_MESAJI)
    except Exception:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=500, detail="İşlem sırasında beklenmeyen bir sunucu hatası oluştu.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


def faaliyet_birimi_guncelle(birim_id: int, kayit: FaaliyetBirimIslemModeli, yetkili_id: int | None = None):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        ad = kayit.birim_adi.strip().upper()
        if not ad:
            raise HTTPException(status_code=422, detail="Birim adı boş olamaz.")

        cursor.execute("SELECT birim_adi FROM faaliyet_birimleri WHERE birim_id = %s FOR UPDATE", (birim_id,))
        eski = cursor.fetchone()
        if not eski:
            raise HTTPException(status_code=404, detail="Güncellenecek birim bulunamadı.")
        eski_ad = eski[0]
        if eski_ad == ad:
            conn.commit()
            return {"durum": "basarili", "mesaj": "Birimde değişiklik yapılmadı."}

        cursor.execute("SELECT 1 FROM faaliyet_birimleri WHERE birim_adi = %s AND birim_id <> %s", (ad, birim_id))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail=BIRIM_ADI_KAYITLI_MESAJI)

        cursor.execute("UPDATE faaliyet_birimleri SET birim_adi = %s WHERE birim_id = %s;", (ad, birim_id))

        from server.denetim import denetim_kaydi_olustur
        denetim_kaydi_olustur(
            VT_AYARLARI, "UPDATE", yetkili_id, "faaliyet_birimleri", birim_id, mevcut_cursor=cursor,
            ayrinti={"onceki": {"birim_adi": eski_ad}, "yeni": {"birim_adi": ad}},
        )

        conn.commit()
        return {"durum": "basarili", "mesaj": "Birim başarıyla güncellendi."}
    except HTTPException:
        raise
    except psycopg2.errors.UniqueViolation:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=400, detail=BIRIM_ADI_KAYITLI_MESAJI)
    except Exception:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=500, detail="İşlem sırasında beklenmeyen bir sunucu hatası oluştu.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


def faaliyet_birimi_sil(birim_id: int, yetkili_id: int | None = None):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        cursor.execute("SELECT 1 FROM ogrenci_faaliyet_takip WHERE birim_id = %s LIMIT 1", (birim_id,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="DİKKAT: Bu birim geçmiş faaliyet kayıtlarında kullanıldığı için SİLİNEMEZ! İsterseniz adını güncelleyebilirsiniz.")

        silinen = satiri_sil_ve_ayrintisini_al(cursor, "faaliyet_birimleri", birim_id)
        from server.denetim import denetim_kaydi_olustur
        denetim_kaydi_olustur(VT_AYARLARI, "DELETE", yetkili_id, "faaliyet_birimleri", birim_id,
                              mevcut_cursor=cursor, ayrinti=silinen)

        conn.commit()
        return {"durum": "basarili", "mesaj": "Birim başarıyla silindi."}
    except HTTPException:
        raise
    except Exception:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=500, detail="İşlem sırasında beklenmeyen bir sunucu hatası oluştu.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


# (yöntem, yol, uç fonksiyonu, yetki parametresi, gereken izin, ek yol ayarları): yetki bağımlılığı kayıt sırasında eklenir.
UCLAR = [
    ("GET", "/api/faaliyet-birimleri", faaliyet_birimleri_getir, "kullanici_id", "FAALIYET_KAYITLARI_DUZENLE", {}),
    ("POST", "/api/faaliyet-birimleri", faaliyet_birimi_ekle, "yetkili_id", "FAALIYET_BIRIMI_DUZENLE", {}),
    ("PUT", "/api/faaliyet-birimleri/{birim_id}", faaliyet_birimi_guncelle, "yetkili_id", "FAALIYET_BIRIMI_DUZENLE", {}),
    ("DELETE", "/api/faaliyet-birimleri/{birim_id}", faaliyet_birimi_sil, "yetkili_id", "FAALIYET_BIRIMI_DUZENLE", {}),
]


def router_olustur(izin_kontrol) -> APIRouter:
    """`izin_kontrol`: `server.sunucu.izin_kontrol` (kimlik doğrulama + izin kontrolü bağımlılığı üreticisi)."""
    router = APIRouter()
    for metod, yol, fonksiyon, parametre, izin, ek in UCLAR:
        router.add_api_route(yol, yetkiyle_bagla(fonksiyon, parametre, izin_kontrol(izin)), methods=[metod], **ek)
    return router
