"""İstemci günlüğü.

Beklenmeyen hatalar ve arka planda yüklenemeyen veriler, kullanıcıya teknik ayrıntı gösterilmeden
bu dosyaya yazılır. Windows'ta: %LOCALAPPDATA%\\TKYS\\istemci.log (1 MB dolunca döner, son 3 dosya saklanır).
Günlük yalnızca uygulama başlatılırken kurulur; testlerde ve modül içe aktarılırken dosya açılmaz.
"""
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

GUNLUK_KLASORU = Path(os.getenv("LOCALAPPDATA") or Path.home()) / "TKYS"
GUNLUK_DOSYASI = GUNLUK_KLASORU / "istemci.log"


def gunlugu_kur():
    """'client' günlüğüne dosya yazıcısını bir kez ekler. Klasör yazılamazsa sessizce vazgeçer (uygulama yine açılır)."""
    kok = logging.getLogger("client")
    if any(isinstance(yazici, RotatingFileHandler) for yazici in kok.handlers):
        return GUNLUK_DOSYASI
    try:
        GUNLUK_KLASORU.mkdir(parents=True, exist_ok=True)
        yazici = RotatingFileHandler(GUNLUK_DOSYASI, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    except OSError:
        return None
    yazici.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    kok.addHandler(yazici)
    kok.setLevel(logging.INFO)
    return GUNLUK_DOSYASI
