"""Birden çok uç modülünün kullandığı küçük yardımcılar (`server/sunucu.py` içinden ayrıldı)."""


def psikolog_rolu_mu(rol_adi) -> bool:
    """Rol adı PSIKOLOG mu? Tek karşılaştırma yeri: büyük/küçük harf ve boşluk farkı önemsenmez, alt metin eşleşmesi yapılmaz."""
    return str(rol_adi or "").strip().upper() == "PSIKOLOG"
