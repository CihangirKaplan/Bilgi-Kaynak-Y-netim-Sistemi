"""TKYS - Bozuk girdiye karşı merkezi koruma: "beklenmeyen sunucu hatası (500)" yerine anlamlı hata döner.

İki katmandan oluşur:

1. NulVeSayiKorumasi (ara katman): istek sunucudaki ilgili ucun koduna girmeden önce
   - NUL karakteri (\\x00) içeren metinleri (JSON gövdesi ve sorgu parametreleri),
   - 32 bit tamsayı sınırını aşan sayıları (veritabanı INTEGER sütunlarına sığmaz),
   - 1 MiB'tan büyük gövdeleri
   reddeder. PostgreSQL NUL karakterini ve taşan sayıyı kabul etmez; reddedilmezse 500 hatası olurdu.

2. merkezi_hata_yakalayicilari_kur: uçlar veritabanı hatasını yakalayıp "raise HTTPException(500)" yapar. Python,
   bir hatayı başka hatanın except bloğunda fırlatınca asıl hatayı __context__ olarak saklar. Bu yakalayıcı o
   asıl PostgreSQL hatasına bakar ve kullanıcının anlayacağı bir yanıta çevirir:
   tekrar eden kayıt -> 409, geçersiz ilişki/boş değer/aralık dışı değer/çok uzun metin -> 422.
   Tanınmayan hatalar eskisi gibi 500 olarak kalır (iç ayrıntı istemciye asla yazılmaz).
"""

import json
import logging
from urllib.parse import parse_qsl

import psycopg2
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

INT32_ALT = -2_147_483_648
INT32_UST = 2_147_483_647
EN_BUYUK_GOVDE_BAYT = 1024 * 1024

GUNLUK = logging.getLogger("uvicorn.error")

GENEL_HATA_MESAJI = "İşlem sırasında beklenmeyen bir sunucu hatası oluştu."
NUL_MESAJI = "Girdi geçersiz karakter içeriyor."
SAYI_MESAJI = "Girilen sayı izin verilen aralığın dışında."
BUYUK_GOVDE_MESAJI = "İstek gövdesi çok büyük."


def _nul_var_mi(deger):
    return "\x00" in deger


def _gecersiz_girdi_bul(veri):
    """JSON ağacında NUL içeren metin ya da 32 bit dışı tamsayı varsa uygun hata metnini döndürür, yoksa None."""
    yigin = [veri]
    while yigin:
        oge = yigin.pop()
        if isinstance(oge, str):
            if _nul_var_mi(oge):
                return NUL_MESAJI
        elif isinstance(oge, bool):
            continue
        elif isinstance(oge, int):
            if not INT32_ALT <= oge <= INT32_UST:
                return SAYI_MESAJI
        elif isinstance(oge, dict):
            for anahtar, deger in oge.items():
                if isinstance(anahtar, str) and _nul_var_mi(anahtar):
                    return NUL_MESAJI
                yigin.append(deger)
        elif isinstance(oge, list):
            yigin.extend(oge)
    return None


class NulVeSayiKorumasi:
    """Saf ASGI ara katmanı: bozuk girdiyi uca ulaşmadan 422/413 ile reddeder."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        hata = self._sorgu_hatasi(scope)
        if hata:
            await JSONResponse({"detail": hata}, status_code=422)(scope, receive, send)
            return

        icerik_turu = dict(scope.get("headers", [])).get(b"content-type", b"")
        if b"application/json" not in icerik_turu:
            await self.app(scope, receive, send)
            return

        govde = b""
        while True:
            mesaj = await receive()
            govde += mesaj.get("body", b"")
            if len(govde) > EN_BUYUK_GOVDE_BAYT:
                await JSONResponse({"detail": BUYUK_GOVDE_MESAJI}, status_code=413)(scope, receive, send)
                return
            if not mesaj.get("more_body", False):
                break

        hata = self._govde_hatasi(govde)
        if hata:
            await JSONResponse({"detail": hata}, status_code=422)(scope, receive, send)
            return

        tekrar_verildi = False

        async def tekrar_oku():
            nonlocal tekrar_verildi
            if not tekrar_verildi:
                tekrar_verildi = True
                return {"type": "http.request", "body": govde, "more_body": False}
            return await receive()                       # bağlantı kopması gibi sonraki olaylar

        await self.app(scope, tekrar_oku, send)

    @staticmethod
    def _sorgu_hatasi(scope):
        sorgu = scope.get("query_string", b"")
        if not sorgu:
            return None
        for anahtar, deger in parse_qsl(sorgu.decode("latin-1"), keep_blank_values=True, errors="replace"):
            if _nul_var_mi(anahtar) or _nul_var_mi(deger):
                return NUL_MESAJI
        return None

    @staticmethod
    def _govde_hatasi(govde):
        if not govde:
            return None
        try:
            veri = json.loads(govde)
        except (ValueError, RecursionError):
            return None                                  # geçersiz JSON'u FastAPI kendi 422'siyle bildirir
        return _gecersiz_girdi_bul(veri)


def veritabani_hatasini_cevir(hata):
    """Bir PostgreSQL hatasını (durum kodu, kullanıcı mesajı) çiftine çevirir; tanınmıyorsa None."""
    if isinstance(hata, psycopg2.errors.UniqueViolation):
        return 409, "Bu kayıt zaten mevcut (aynı değerle kayıtlı bir kayıt var)."
    if isinstance(hata, psycopg2.errors.ForeignKeyViolation):
        return 422, "Seçilen ilişkili kayıt bulunamadı."
    if isinstance(hata, psycopg2.errors.NotNullViolation):
        return 422, "Zorunlu bir alan boş bırakılamaz."
    if isinstance(hata, psycopg2.errors.CheckViolation):
        return 422, "Girilen değer izin verilen kuralların dışında."
    if isinstance(hata, psycopg2.errors.StringDataRightTruncation):
        return 422, "Girilen metin izin verilen uzunluktan fazla."
    if isinstance(hata, psycopg2.errors.NumericValueOutOfRange):
        return 422, SAYI_MESAJI
    if isinstance(hata, psycopg2.DataError):
        return 422, "Girilen değer geçersiz."
    if isinstance(hata, psycopg2.IntegrityError):
        return 422, "Girilen değer veritabanı kurallarına uymuyor."
    return None


def _asil_hata(hata):
    """Hata zincirinde (__context__/__cause__) ilk PostgreSQL ya da NUL kaynaklı hatayı bulur."""
    gorulen = set()
    while hata is not None and id(hata) not in gorulen:
        gorulen.add(id(hata))
        if isinstance(hata, psycopg2.Error):
            return hata
        if isinstance(hata, ValueError) and "NUL" in str(hata):
            return hata
        hata = hata.__cause__ or hata.__context__
    return None


def merkezi_hata_yakalayicilari_kur(app):
    """500 olarak fırlatılan ama kökü kullanıcı girdisi olan veritabanı hatalarını 409/422'ye çevirir."""

    @app.exception_handler(psycopg2.Error)
    async def veritabani_hatasi(request, hata):
        """Uç noktanın yakalamadan geri fırlattığı veritabanı hataları: tanınıyorsa 409/422, değilse JSON 500."""
        cevrilen = veritabani_hatasini_cevir(hata)
        if cevrilen is not None:
            durum, mesaj = cevrilen
            return JSONResponse({"detail": mesaj}, status_code=durum)
        GUNLUK.error("Beklenmeyen veritabanı hatası: %s %s", type(hata).__name__, request.url.path, exc_info=hata)
        return JSONResponse({"detail": GENEL_HATA_MESAJI}, status_code=500)

    @app.exception_handler(StarletteHTTPException)
    async def http_hatasi(request, hata):
        if hata.status_code == 500:
            asil = _asil_hata(hata)
            if isinstance(asil, ValueError):
                return JSONResponse({"detail": NUL_MESAJI}, status_code=422)
            if asil is not None:
                cevrilen = veritabani_hatasini_cevir(asil)
                if cevrilen is not None:
                    durum, mesaj = cevrilen
                    return JSONResponse({"detail": mesaj}, status_code=durum)
        return await http_exception_handler(request, hata)
