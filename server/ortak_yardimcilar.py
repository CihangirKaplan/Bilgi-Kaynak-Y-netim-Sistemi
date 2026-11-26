"""Birden çok uç modülünün kullandığı küçük yardımcılar (`server/sunucu.py` içinden ayrıldı)."""


def psikolog_rolu_mu(rol_adi) -> bool:
    """Rol adı PSIKOLOG mu? Tek karşılaştırma yeri: büyük/küçük harf ve boşluk farkı önemsenmez, alt metin eşleşmesi yapılmaz."""
    return str(rol_adi or "").strip().upper() == "PSIKOLOG"


def plan_kalibrasyon_mu(gorev_turu):
    """'Kalibrasyon' ile başlayan plan türleri kalibrasyon planıdır; diğerleri bakım planıdır."""
    return (gorev_turu or "").strip().lower().startswith("kalibrasyon")
