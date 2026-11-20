"""Yeni parola politikası (sunucu tarafı tek kaynak). İstemcideki client/parola_kurallari.py aynı kuralları gösterir.

Kurallar: en az 10 karakter, en az bir harf ve bir rakam, kullanıcı adını içermemek, çok yaygın/tahmin edilmesi kolay olmamak.
Üst sınır bcrypt'in 72 bayt sınırıdır (ayrıca denetlenir).
"""

EN_AZ_UZUNLUK = 10

# Küçük harfe çevrilmiş, sık kullanılan zayıf parolalar. Tam eşleşme ya da "yalnızca bu + rakam/noktalama" durumunda reddedilir.
YAYGIN_PAROLALAR = frozenset({
    "password", "parola", "sifre", "admin", "administrator", "qwerty", "qwertyuiop", "asdfghjkl", "azerty",
    "123456", "1234567", "12345678", "123456789", "1234567890", "0123456789", "111111", "000000",
    "abc123", "iloveyou", "letmein", "welcome", "tkys", "tkys2024", "tkys2025", "tkys2026",
    "123qwe", "qwe123", "passw0rd", "p@ssw0rd", "changeme", "degistir",
})


def _sadece_harf_kismi(parola: str) -> str:
    return "".join(c for c in parola.lower() if c.isalpha())


def parola_ihlalleri(parola: str, kullanici_adi: str | None = None) -> list[str]:
    """Parolanın ihlal ettiği kuralların Türkçe açıklamaları (boş liste = geçerli)."""
    ihlaller = []
    if len(parola) < EN_AZ_UZUNLUK:
        ihlaller.append(f"Şifre en az {EN_AZ_UZUNLUK} karakter olmalıdır.")
    if not any(c.isalpha() for c in parola):
        ihlaller.append("Şifre en az bir harf içermelidir.")
    if not any(c.isdigit() for c in parola):
        ihlaller.append("Şifre en az bir rakam içermelidir.")
    kucuk = parola.lower()
    if kullanici_adi and len(kullanici_adi.strip()) >= 3 and kullanici_adi.strip().lower() in kucuk:
        ihlaller.append("Şifre kullanıcı adınızı içeremez.")
    harf_kismi = _sadece_harf_kismi(parola)
    yaygin = kucuk in YAYGIN_PAROLALAR or (harf_kismi in YAYGIN_PAROLALAR and len(harf_kismi) >= 4)
    if yaygin or len(set(parola)) <= 3:
        ihlaller.append("Şifre çok yaygın ya da tahmin edilmesi kolay; farklı bir şifre seçin.")
    return ihlaller
