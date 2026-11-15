"""Yeni şifre kuralları (sunucudaki /api/sifre-degistir ile aynı) ve gücü gösteren yardımcı.

Zorunlu kurallar sunucunun reddettiği durumlardır; ekran bunlar sağlanmadan düğmeyi açmaz. Güç göstergesi yalnızca
yol göstericidir, kaydı engellemez.
"""

EN_AZ_UZUNLUK = 8
EN_FAZLA_BAYT = 72


def kural_durumlari(yeni, tekrar, eski):
    """[(metin, sağlandı_mı)] — ekrandaki kontrol listesi sırasıyla."""
    return [
        (f"En az {EN_AZ_UZUNLUK} karakter", len(yeni) >= EN_AZ_UZUNLUK),
        (f"En fazla {EN_FAZLA_BAYT} bayt (çok uzun olmasın)", 0 < len(yeni.encode("utf-8")) <= EN_FAZLA_BAYT),
        ("Eski şifreyle aynı değil", bool(yeni) and yeni != eski),
        ("İki yeni şifre alanı aynı", bool(yeni) and yeni == tekrar),
    ]


def tum_kurallar_saglandi_mi(yeni, tekrar, eski):
    return all(saglandi for _, saglandi in kural_durumlari(yeni, tekrar, eski))


def guc_hesapla(yeni):
    """(0..3, etiket). 0 = çok zayıf/boş, 3 = güçlü. Yol göstericidir."""
    if not yeni:
        return 0, ""
    puan = 0
    if len(yeni) >= EN_AZ_UZUNLUK:
        puan += 1
    if len(yeni) >= 12:
        puan += 1
    cesit = sum([
        any(c.islower() for c in yeni),
        any(c.isupper() for c in yeni),
        any(c.isdigit() for c in yeni),
        any(not c.isalnum() for c in yeni),
    ])
    if cesit >= 3:
        puan += 1
    puan = min(puan, 3)
    if len(yeni) < EN_AZ_UZUNLUK:
        puan = 0
    return puan, {0: "Zayıf", 1: "Orta", 2: "İyi", 3: "Güçlü"}[puan]
