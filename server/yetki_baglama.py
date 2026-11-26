"""Ayrı modüllerdeki uç fonksiyonlarına yetki bağımlılığını kayıt sırasında bağlar.

`server.sunucu` içindeki `izin_kontrol(...)` kimlik doğrulama ve izin kontrolünü yapar; ayrılan modüller `server.sunucu`yu içe aktarmadan
(döngüsel bağımlılık olmasın) fonksiyonlarını saf olarak tanımlar ve yetki bağımlılığı `router_olustur(izin_kontrol)` içinde eklenir.
Fonksiyonlar doğrudan da çağrılabilir (testler `kullanici_id`yi kendileri verir).
"""
import functools
import inspect

from fastapi import Depends


def yetkiyle_bagla(fonksiyon, parametre_adi: str, bagimlilik):
    """`fonksiyon`un `parametre_adi` parametresinin varsayılanını `Depends(bagimlilik)` yapan, aynı işi gören sarmalayıcı döndürür."""
    imza = inspect.signature(fonksiyon)
    if parametre_adi not in imza.parameters:
        raise ValueError(f"{fonksiyon.__name__}: '{parametre_adi}' parametresi yok.")
    parametreler = [
        p.replace(default=Depends(bagimlilik)) if p.name == parametre_adi else p
        for p in imza.parameters.values()
    ]

    @functools.wraps(fonksiyon)
    def sarmalayici(*args, **kwargs):
        return fonksiyon(*args, **kwargs)

    sarmalayici.__signature__ = imza.replace(parameters=parametreler)
    return sarmalayici
