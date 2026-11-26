"""Rezervasyon formundaki bölüm ve proje türü uçları. `server/sunucu.py` içinden ayrıldı."""
from fastapi import APIRouter, HTTPException
import psycopg2
import psycopg2.errors

from server.modeller import BolumOlusturModeli, ProjeTuruOlusturModeli
from server.vt_ayarlari import VT_AYARLARI
from server.vt_baglanti import vt_baglan
from server.yetki_baglama import yetkiyle_bagla


def bolumleri_listele(kullanici_id: int | None = None):
    """Rezervasyon formundaki bölüm listesi (yalnızca aktif bölümler)."""
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("SELECT bolum_id, bolum_adi, sorumlu_ad_soyad FROM bolumler WHERE aktif_mi IS NOT FALSE ORDER BY bolum_adi;")
        return [{"bolum_id": k[0], "bolum_adi": k[1], "sorumlu_ad_soyad": k[2]} for k in cursor.fetchall()]
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


def bolum_olustur(bolum: BolumOlusturModeli, kullanici_id: int | None = None):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO bolumler (bolum_adi, sorumlu_ad_soyad, iletisim_bilgisi, aktif_mi) VALUES (%s, %s, %s, TRUE) RETURNING bolum_id;", (bolum.bolum_adi, bolum.sorumlu_ad_soyad, bolum.iletisim_bilgisi))
        bolum_id = cursor.fetchone()[0]
        cursor.execute("INSERT INTO denetim_kayitlari (kullanici_id, olay_turu, hedef_tablo, hedef_kayit_id) VALUES (%s, %s, %s, %s);", (kullanici_id, "CREATE", "bolumler", bolum_id))
        conn.commit()
        return {"durum": "basarili", "mesaj": "Bölüm eklendi.", "bolum_id": bolum_id, "bolum_adi": bolum.bolum_adi}
    except psycopg2.errors.UniqueViolation:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=409, detail="Bu isimde bir bölüm zaten mevcut.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


def proje_turu_anahtari(ad):
    """Proje türü karşılaştırma anahtarı: Türkçe büyük/küçük harf farkı (İ/i, I/ı) ve kenar boşlukları yok sayılır."""
    return str(ad).strip().replace("İ", "i").replace("I", "ı").lower()


def proje_turlerini_listele(kullanici_id: int | None = None):
    """Rezervasyon formundaki proje türü listesi."""
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("SELECT proje_turu_id, ad FROM proje_turleri WHERE aktif_mi ORDER BY ad;")
        return [{"proje_turu_id": k[0], "ad": k[1]} for k in cursor.fetchall()]
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


def proje_turu_olustur(tur: ProjeTuruOlusturModeli, kullanici_id: int | None = None):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("SELECT ad FROM proje_turleri;")
        if proje_turu_anahtari(tur.ad) in {proje_turu_anahtari(k[0]) for k in cursor.fetchall()}:     # büyük/küçük harf (İ/ı dahil) farkı yok sayılır
            raise HTTPException(status_code=409, detail="Bu proje türü zaten mevcut.")
        cursor.execute("INSERT INTO proje_turleri (ad) VALUES (%s) RETURNING proje_turu_id;", (tur.ad,))
        tur_id = cursor.fetchone()[0]
        cursor.execute("INSERT INTO denetim_kayitlari (kullanici_id, olay_turu, hedef_tablo, hedef_kayit_id) VALUES (%s, %s, %s, %s);", (kullanici_id, "CREATE", "proje_turleri", tur_id))
        conn.commit()
        return {"durum": "basarili", "mesaj": "Proje türü eklendi.", "proje_turu_id": tur_id, "ad": tur.ad}
    except psycopg2.errors.UniqueViolation:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=409, detail="Bu proje türü zaten mevcut.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


# (yöntem, yol, uç fonksiyonu, yetki parametresi, gereken yetki, ek yol ayarları): yetki bağımlılığı kayıt sırasında eklenir.
# Gereken yetki: "IZIN" (izin_kontrol), ("A", "B") (izin_kontrol_biri: biri yeter) veya None (yalnızca oturum açmış olmak).
UCLAR = [
    ("GET", "/api/bolumler", bolumleri_listele, "kullanici_id", "CIHAZ_REZERVASYON", {}),
    ("POST", "/api/bolumler", bolum_olustur, "kullanici_id", "CIHAZ_REZERVASYON", {"status_code": 201}),
    ("GET", "/api/proje-turleri", proje_turlerini_listele, "kullanici_id", "CIHAZ_REZERVASYON", {}),
    ("POST", "/api/proje-turleri", proje_turu_olustur, "kullanici_id", "CIHAZ_REZERVASYON", {"status_code": 201}),
]


def router_olustur(izin_kontrol) -> APIRouter:
    """Yetki bağımlılığı üreticileri `server.sunucu` içindeki kimlik doğrulama bağımlılıklarıdır."""
    router = APIRouter()
    for metod, yol, fonksiyon, parametre, yetki, ek in UCLAR:
        assert isinstance(yetki, str), yol          # bu modülde yalnızca tek izin tanımlı
        bagimlilik = izin_kontrol(yetki)
        router.add_api_route(yol, yetkiyle_bagla(fonksiyon, parametre, bagimlilik), methods=[metod], **ek)
    return router
