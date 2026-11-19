"""Ekranda gösterilen metinlerin okunur biçimleri. Veritabanındaki değerler değişmez; yalnızca görünüm düzeltilir."""

_BIRIM_ADLARI = {"KISI": "Kişi", "SAAT": "Saat", "ADET": "Adet", "GUN": "Gün", "DAKIKA": "Dakika"}


def birim_goster(ad):
    """Birim adını okunur yazar: 'KISI' -> 'Kişi'. Bilinmeyen adlar olduğu gibi kalır."""
    metin = str(ad or "").strip()
    return _BIRIM_ADLARI.get(metin.upper(), metin)


def telefon_goster(telefon, bos="—"):
    """'05550000000' -> '0555 000 00 00'. 10 haneli ('5550000000') ise başına 0 eklenir; tanınmayan biçim olduğu gibi gösterilir."""
    ham = str(telefon or "").strip()
    if not ham:
        return bos
    rakamlar = "".join(c for c in ham if c.isascii() and c.isdigit())
    if len(rakamlar) == 10 and not rakamlar.startswith("0"):
        rakamlar = "0" + rakamlar
    yalniz_numara = all(c.isdigit() or c in " ()-" for c in ham)
    if yalniz_numara and len(rakamlar) == 11 and rakamlar.startswith("0"):
        return f"{rakamlar[:4]} {rakamlar[4:7]} {rakamlar[7:9]} {rakamlar[9:]}"
    return ham
