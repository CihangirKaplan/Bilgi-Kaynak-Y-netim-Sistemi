"""Yanıtlara güvenlik başlıkları ekleyen saf ASGI ara katmanı.

- X-Content-Type-Options: nosniff  (her yanıtta)
- Strict-Transport-Security        (yalnızca istek HTTPS ile geldiyse; tarayıcı/istemciye "bu adrese hep HTTPS ile bağlan" der).
  HTTPS sertifikası TLS sonlandıran bir ara sunucuda (ters vekil) ise vekil, isteği iletirken X-Forwarded-Proto: https ekliyorsa
  ve TKYS_GUVENILIR_VEKIL=1 verildiyse HTTPS sayılır. Aksi halde bu başlığa güvenilmez (istemci sahteleyebilir).
"""
import os

HSTS_DEGERI = b"max-age=31536000"


def _https_mi(scope) -> bool:
    if scope.get("scheme") in ("https", "wss"):
        return True
    if os.getenv("TKYS_GUVENILIR_VEKIL") == "1":
        basliklar = dict(scope.get("headers", []))
        return basliklar.get(b"x-forwarded-proto", b"").lower() == b"https"
    return False


class GuvenlikBasliklari:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        https = _https_mi(scope)

        async def gonder(mesaj):
            if mesaj["type"] == "http.response.start":
                basliklar = list(mesaj.get("headers", []))
                basliklar.append((b"x-content-type-options", b"nosniff"))
                if https:
                    basliklar.append((b"strict-transport-security", HSTS_DEGERI))
                mesaj = {**mesaj, "headers": basliklar}
            await send(mesaj)

        await self.app(scope, receive, gonder)
