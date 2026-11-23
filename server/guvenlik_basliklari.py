"""Yanıtlara güvenlik başlıkları ekleyen ve istemci adresini istek bağlamına koyan saf ASGI ara katmanı.

- İstemci adresi (denetim kayıtları için): doğrudan bağlanan adres; TKYS_GUVENILIR_VEKIL=1 ise vekilin eklediği X-Forwarded-For değerinin
  SON girişi (vekilin kendi gördüğü istemci; istemcinin gönderdiği önceki girişlere güvenilmez).

- X-Content-Type-Options: nosniff  (her yanıtta)
- X-Frame-Options: DENY ve Referrer-Policy: no-referrer  (her yanıtta; sayfa içine gömülme ve adres sızdırma yok)
- Cache-Control: no-store  (/api yanıtlarında, uç ayrıca belirtmemişse): kişisel veri içeren yanıtlar ara sunucularda ya da tarayıcı
  önbelleğinde saklanmaz.
- Strict-Transport-Security        (yalnızca istek HTTPS ile geldiyse; tarayıcı/istemciye "bu adrese hep HTTPS ile bağlan" der).
  HTTPS sertifikası TLS sonlandıran bir ara sunucuda (ters vekil) ise vekil, isteği iletirken X-Forwarded-Proto: https ekliyorsa
  ve TKYS_GUVENILIR_VEKIL=1 verildiyse HTTPS sayılır. Aksi halde bu başlığa güvenilmez (istemci sahteleyebilir).
"""
import os

from server.vt_baglanti import adresi_ayarla, adresi_sifirla

HSTS_DEGERI = b"max-age=31536000"
API_ONEKI = "/api"


def _https_mi(scope) -> bool:
    if scope.get("scheme") in ("https", "wss"):
        return True
    if os.getenv("TKYS_GUVENILIR_VEKIL") == "1":
        basliklar = dict(scope.get("headers", []))
        return basliklar.get(b"x-forwarded-proto", b"").lower() == b"https"
    return False


def istemci_adresi(scope):
    if os.getenv("TKYS_GUVENILIR_VEKIL") == "1":
        iletilen = dict(scope.get("headers", [])).get(b"x-forwarded-for", b"").decode("latin-1")
        if iletilen.strip():
            return iletilen.split(",")[-1].strip()
    istemci = scope.get("client")
    return istemci[0] if istemci else None


class GuvenlikBasliklari:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        https = _https_mi(scope)
        api_mi = scope.get("path", "").startswith(API_ONEKI)
        belirtec = adresi_ayarla(istemci_adresi(scope))

        async def gonder(mesaj):
            if mesaj["type"] == "http.response.start":
                basliklar = list(mesaj.get("headers", []))
                basliklar.append((b"x-content-type-options", b"nosniff"))
                basliklar.append((b"x-frame-options", b"DENY"))
                basliklar.append((b"referrer-policy", b"no-referrer"))
                if api_mi and not any(ad.lower() == b"cache-control" for ad, _ in basliklar):
                    basliklar.append((b"cache-control", b"no-store"))
                if https:
                    basliklar.append((b"strict-transport-security", HSTS_DEGERI))
                mesaj = {**mesaj, "headers": basliklar}
            await send(mesaj)

        try:
            await self.app(scope, receive, gonder)
        finally:
            adresi_sifirla(belirtec)
