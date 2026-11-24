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
    return (f"Liste en yeni {gorunen} kaydı gösterir (toplam {toplam}); arama yalnızca bu kayıtlarda yapılır. Eski kayıtlar silinmedi: "
            "“Daha fazla yükle” ile ekleyebilir ya da Raporlar bölümünden dönem seçerek ulaşabilirsiniz.")


# --- Ekranın sunucudan istediği kayıt sayısı ---
# İlk açılışta yalnızca en yeni ILK_YUKLEME kayıt istenir (3000 satırlık tabloyu çizmek saniyeler sürer); "Daha fazla yükle" her basışta
# ADIM kadar artırır. SUNUCU_EN_COK, sunucunun tek seferde verebileceği üst sınırdır (server.sunucu.LISTE_UST_SINIRI ile aynı).
ILK_YUKLEME = 300
ADIM = 300
SUNUCU_EN_COK = 5000


class ListeSiniri:
    """Bir liste ekranının o anki istek sınırı. Ekran her yüklemede parametreler()'i gönderir."""

    def __init__(self, ilk: int = ILK_YUKLEME):
        self.limit = ilk

    def parametreler(self) -> dict:
        return {"limit": self.limit}

    def artir(self) -> int:
        self.limit = min(self.limit + ADIM, SUNUCU_EN_COK)
        return self.limit

    def artirilabilir_mi(self, gorunen: int, toplam: int) -> bool:
        """Sunucuda gösterilenden fazla kayıt var ve sunucunun üst sınırına henüz ulaşılmadı."""
        return toplam > gorunen and self.limit < SUNUCU_EN_COK


def daha_fazla_guncelle(dugme, sinir: ListeSiniri, gorunen: int, toplam: int) -> None:
    """Düğmeyi yalnızca daha yüklenebilecek kayıt varsa gösterir ve kaç kayıt ekleneceğini yazar."""
    artirilabilir = sinir.artirilabilir_mi(gorunen, toplam)
    dugme.setVisible(artirilabilir)
    if artirilabilir:
        eklenecek = min(ADIM, SUNUCU_EN_COK - sinir.limit, toplam - gorunen)
        dugme.setText(f"＋  {eklenecek} kayıt daha yükle")
        dugme.setToolTip(f"Şu an en yeni {gorunen} kayıt yüklü (toplam {toplam}). Arama yalnızca yüklü kayıtlarda yapılır.")

