"""Veritabanı bağlantısı açar; isteği yapan istemcinin adresini oturum ayarı olarak bağlantıya iliştirir.

Denetim tablosundaki tetikleyici (`denetim_istemci_adresi_yaz`) bu ayarı `denetim_kayitlari.istemci_adresi` sütununa yazar; böylece
denetim kaydı yazan her kod yolu (hangi ucun yazdığına bakılmadan) istemci adresini taşır. İstek bağlamı dışında (betikler, testler)
ayar eklenmez ve bağlantı eskisi gibi açılır.
"""
import re
from contextvars import ContextVar

import psycopg2

_istemci_adresi: ContextVar[str | None] = ContextVar("tkys_istemci_adresi", default=None)
_GECERLI_ADRES = re.compile(r"^[0-9A-Fa-f:.]{2,45}$")      # yalnızca IPv4/IPv6 karakterleri (bağlantı seçeneğine kontrolsüz metin girmesin)


def adresi_ayarla(adres):
    """Geçerli bir IP adresi değilse None sayar. Geri alma için ContextVar belirtecini döndürür."""
    temiz = adres if isinstance(adres, str) and _GECERLI_ADRES.match(adres) else None
    return _istemci_adresi.set(temiz)


def adresi_sifirla(belirtec):
    _istemci_adresi.reset(belirtec)


def mevcut_adres():
    return _istemci_adresi.get()


def vt_baglan(ayarlar: dict):
    adres = _istemci_adresi.get()
    if adres:
        ayarlar = {**ayarlar, "options": f"-c tkys.istemci_adresi={adres}"}
    return psycopg2.connect(**ayarlar)
