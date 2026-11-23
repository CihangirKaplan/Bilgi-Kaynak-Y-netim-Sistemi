"""Sunucunun üst sınırla (en yeni N kayıt) döndürdüğü listelerde ekranda gerçek toplamı gösterme yardımcıları.

Sunucu, liste sınıra ulaştığında gerçek toplamı `X-Toplam-Kayit` başlığında gönderir; ulaşmadıysa başlık yoktur ve görünüm eskisi gibidir.
"""


def liste_toplami(yanit, gorunen: int) -> int:
    """Yanıt başlığındaki gerçek toplam (görünenden büyükse); başlık yoksa ya da okunamazsa görünen sayı."""
    try:
        toplam = int(yanit.headers.get("X-Toplam-Kayit"))
    except (TypeError, ValueError, AttributeError):
        return gorunen
    return toplam if toplam > gorunen else gorunen


def toplam_etiketi(gorunen: int, toplam: int, birim: str = "kayıt") -> str:
    """'12 kayıt' (sınıra ulaşılmadıysa) ya da 'en yeni 5000 / toplam 7312 kayıt' (ulaşıldıysa)."""
    if toplam > gorunen:
        return f"en yeni {gorunen} / toplam {toplam} {birim}"
    return f"{gorunen} {birim}"


def kisaltma_ipucu(gorunen: int, toplam: int) -> str:
    """Toplam çipinin üstüne gelince çıkan açıklama; sınıra ulaşılmadıysa boş."""
    if toplam <= gorunen:
        return ""
    return (f"Liste en yeni {gorunen} kaydı gösterir (toplam {toplam}). Eski kayıtlar silinmedi; "
            "gerekirse Raporlar bölümünden dönem seçerek ulaşabilirsiniz.")
