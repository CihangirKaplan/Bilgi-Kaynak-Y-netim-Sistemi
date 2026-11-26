"""Sürüm bilgisi ve sistem durumu uçları (salt okunur). `server/sunucu.py` içinden ayrıldı."""
import logging

from fastapi import APIRouter, HTTPException

from server.vt_ayarlari import VT_AYARLARI
from server.vt_baglanti import vt_baglan
from server.yetki_baglama import yetkiyle_bagla


from server import sistem_durumu as _sistem_durumu
from server.surum import SURUM as _SURUM, UYGULAMA_ADI as _UYGULAMA_ADI


def surum_bilgisi(kullanici_id: int | None = None):
    """Hakkında penceresi için sunucu sürümü ve veritabanı şema sürümü (giriş yapmış herkes görebilir; kişisel veri içermez)."""
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        return {"uygulama": _UYGULAMA_ADI, "surum": _SURUM, "sema_surumu": _sistem_durumu.sema_surumu(cursor)}
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


def sistem_durumu_getir(kullanici_id: int | None = None):
    """Yönetici için sistem durumu: sürüm, şema, son yedek, son girişler, başarısız girişler ve temel sayılar."""
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        return _sistem_durumu.sistem_durumu(cursor, VT_AYARLARI["dbname"])
    except HTTPException:
        raise
    except Exception:
        if conn is not None: conn.rollback()
        logging.getLogger(__name__).exception("Sistem durumu alınamadı")
        raise HTTPException(status_code=500, detail="Sistem durumu alınırken bir hata oluştu.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


# (yol, uç fonksiyonu, yetki parametresi, gereken izin): yetki bağımlılığı kayıt sırasında eklenir.
# İzin None ise yalnızca oturum açmış olmak yeter (kimlik bağımlılığı).
UCLAR = [
    ("/api/surum", surum_bilgisi, "kullanici_id", None),
    ("/api/sistem-durumu", sistem_durumu_getir, "kullanici_id", "AUDIT_KAYITLARI_INCELE"),
]


def router_olustur(izin_kontrol, mevcut_kullanici_id) -> APIRouter:
    """`izin_kontrol`: `server.sunucu.izin_kontrol` ; `mevcut_kullanici_id`: oturum kimliği bağımlılığı."""
    router = APIRouter()
    for yol, fonksiyon, parametre, izin in UCLAR:
        router.add_api_route(yol, yetkiyle_bagla(fonksiyon, parametre, izin_kontrol(izin) if izin else mevcut_kullanici_id), methods=["GET"])
    return router
