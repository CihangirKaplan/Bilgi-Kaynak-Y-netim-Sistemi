"""Bildirimlerde kullanılan küçük çizgi ikonlar (kutusuz, yan menüyle aynı ikon kayıt defteri).

Bildirim metinleri artık emoji taşımaz; ikon, bildirimin grubundan ve içeriğinden seçilir. Eski biçimde (başında emoji olan)
gelen metinler de desteklenir: başındaki emoji ayıklanır ve karşılığı olan çizgi ikon kullanılır.
"""
from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon

from client.ikon_kutusu import ikon_pixmap

IKON_BOYUTU = 16

# Renkler: mavi = bilgi, kırmızı = acil/gecikmiş, amber = yaklaşan, yeşil = sorun yok
MAVI, KIRMIZI, AMBER, YESIL, GRI = "#1E3A8A", "#B91C1C", "#B45309", "#15803D", "#5072A6"

# Eski emoji önekleri -> (ikon, renk)
_EMOJI_IKON = {
    "🔐": ("key", MAVI),
    "⚠️": ("warning", KIRMIZI),
    "⚠": ("warning", KIRMIZI),
    "🔴": ("warning", KIRMIZI),
    "🟡": ("warning", AMBER),
    "🔧": ("wrench", AMBER),
    "📅": ("calendar", MAVI),
    "🔬": ("chip", MAVI),
    "📢": ("megaphone", MAVI),
    "📋": ("clipboard", MAVI),
    "🙋": ("user", MAVI),
    "🔔": ("bell", MAVI),
    "✅": ("circle-check", YESIL),
}

# Grup başlıkları ve varsayılan ikonları
GRUP_BASLIKLARI = {
    "Cihaz Uyarıları": ("CİHAZ UYARILARI", "wrench", AMBER),
    "Parola Talepleri": ("PAROLA SIFIRLAMA TALEPLERİ", "key", MAVI),
    "Günlük": ("BENİM GÜNÜM", "user", MAVI),
    "Duyurular": ("DUYURULAR", "megaphone", MAVI),
}
VARSAYILAN_GRUP = ("DANIŞMA MASASI ONAYLARI", "clipboard", MAVI)


def grup_basligi(grup):
    """(başlık metni, ikon, renk)."""
    return GRUP_BASLIKLARI.get(grup, VARSAYILAN_GRUP)


def emojisiz(metin):
    """Başındaki emoji (varsa) ve boşluk ayıklanır; (temiz metin, (ikon, renk) ya da None)."""
    metin = str(metin)
    for emoji, ikon in sorted(_EMOJI_IKON.items(), key=lambda oge: -len(oge[0])):
        if metin.startswith(emoji):
            return metin[len(emoji):].lstrip(), ikon
    return metin, None


def bildirim_ikonu(grup, metin):
    """Bildirim satırı için (temiz metin, ikon adı, renk)."""
    temiz, eski = emojisiz(metin)
    if eski is not None:
        return temiz, eski[0], eski[1]
    if "açık arıza" in temiz or "gün gecikti" in temiz:
        return temiz, "warning", KIRMIZI
    if grup == "Günlük":
        return temiz, ("chip" if "cihaz" in temiz.lower() else "calendar"), MAVI
    _, ikon, renk = grup_basligi(grup)
    return temiz, ikon, renk


def cizgi_ikonu(ad, renk, boyut=IKON_BOYUTU):
    return QIcon(ikon_pixmap(ad, renk, boyut))


def ikon_boyutu():
    return QSize(IKON_BOYUTU, IKON_BOYUTU)
