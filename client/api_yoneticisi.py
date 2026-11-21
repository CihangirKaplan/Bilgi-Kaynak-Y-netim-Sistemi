import requests

# Sunucunun ana adresi (bunu bir kere tanımlamak işleri kolaylaştırır)
BASE_URL = "http://127.0.0.1:8000/api"

def personel_listesini_getir(token):
    """Sunucudan personel verilerini çeker ve liste olarak döndürür."""
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{BASE_URL}/personel"
    
    try:
        cevap = requests.get(url, headers=headers, timeout=15)
        
        if cevap.status_code == 200:
            return cevap.json()  # Veriyi başarıyla aldık, geri gönderiyoruz
        else:
            print("Sunucudan veri çekilemedi. Hata Kodu:", cevap.status_code)
            return []  # Hata varsa boş liste dön
            
    except requests.exceptions.ConnectionError:
        print("Sunucuya ulaşılamıyor. FastAPI'nin çalıştığından emin ol.")
        return []  # Sunucu kapalıysa boş liste dön

from PySide6.QtCore import QObject, Signal


class OturumOlaylari(QObject):
    token_reddedildi = Signal(str, str)


oturum_olaylari = OturumOlaylari()


SEMA_UYUMSUZ_KODU = "SEMA_UYUMSUZ"


def sema_uyumsuz_detayi(yanit):
    """Sunucu "veritabanı şeması eski" (503 + kod=SEMA_UYUMSUZ) dediyse anlaşılır mesajı, değilse None döndürür."""
    if getattr(yanit, "status_code", None) != 503:
        return None
    try:
        veri = yanit.json()
    except (ValueError, TypeError, AttributeError):
        return None
    if isinstance(veri, dict) and veri.get("kod") == SEMA_UYUMSUZ_KODU and isinstance(veri.get("detail"), str):
        return veri["detail"]
    return None


def oturum_kontrollu_istek(method, url, **kwargs):
    """HTTP istegi gonderir ve token hatalarini bildirir."""

    yanit = requests.request(method, url, **kwargs)

    detay = sema_uyumsuz_detayi(yanit)
    if detay:
        # raise_for_status() hatası "503 Server Error: <bu metin> for url: ..." olur; ekranlar bunu olduğu gibi gösterir.
        yanit.reason = detay
        return yanit

    if yanit.status_code != 401:
        return yanit

    headers = kwargs.get("headers") or {}

    yetki = next(
        (
            str(deger)
            for anahtar, deger in headers.items()
            if str(anahtar).lower() == "authorization"
        ),
        ""
    )

    if not yetki.lower().startswith("bearer "):
        return yanit

    token = yetki[7:].strip()

    if not token:
        return yanit

    try:
        detay = yanit.json().get("detail", "")
    except (ValueError, TypeError, AttributeError):
        detay = ""

    token_hatalari = {
        "Token süresi dolmuş.",
        "Geçersiz token.",
        "Kullanıcı bulunamadı.",
        # Başka bilgisayardan çıkış yapıldığında (oturum sürümü arttı) ya da parola değiştiğinde/sıfırlandığında sunucu bunu döner.
        "Oturum geçersiz. Yeniden giriş yapınız.",
    }

    if isinstance(detay, str) and detay in token_hatalari:
        yanit._tkys_oturum_reddedildi = True
        oturum_olaylari.token_reddedildi.emit(
            token,
            "sure_doldu" if detay == "Token süresi dolmuş." else "gecersiz"
        )

    return yanit



class OturumSonaErdiHatasi(RuntimeError):
    """Merkezi sistemin yonettigi oturum hatasi."""


def oturum_hatasi_mi(hata_veya_yanit):
    """Merkezi sistemin isaretledigi 401 hatasini tanir."""

    if isinstance(hata_veya_yanit, requests.RequestException):
        yanit = getattr(hata_veya_yanit, "response", None)
    else:
        yanit = hata_veya_yanit

    return bool(
        getattr(yanit, "_tkys_oturum_reddedildi", False)
    )


def hata_detayi_metni(yanit, varsayilan="Bilinmeyen bir hata oluştu."):
    """Sunucunun 'detail' alanını her durumda düz metne çevirir.

    FastAPI doğrulama (422) hatalarında 'detail' bir liste döner; bu liste Qt mesaj kutusuna
    verilirse hata verir ya da ham Python listesi gösterilir. Metin aynen, liste okunur
    cümlelere, sözlük ise 'mesaj' alanına çevrilir.
    """
    try:
        detay = yanit.json().get("detail", varsayilan)
    except Exception:
        return varsayilan
    if isinstance(detay, str):
        return detay or varsayilan
    if isinstance(detay, dict):
        return str(detay.get("mesaj") or varsayilan)
    if isinstance(detay, list):
        parcalar = []
        for oge in detay:
            mesaj = str(oge.get("msg", "")) if isinstance(oge, dict) else str(oge)
            mesaj = mesaj.removeprefix("Value error, ").strip()
            if mesaj:
                parcalar.append(mesaj)
        return "\n".join(parcalar) or "Girilen bilgiler geçersiz. Lütfen kontrol edin."
    return varsayilan


def api_hata_mesaji(yanit=None, hata=None):
    """API ve bağlantı hatalarını kullanıcı dostu metne dönüştürür.

    Mevcut 401 oturum yönetimi bu fonksiyondan bağımsızdır.
    """
    if hata is not None:
        if isinstance(hata, requests.exceptions.Timeout):
            return "Sunucu yanıt vermedi. Lütfen tekrar deneyin."
        if isinstance(hata, requests.exceptions.ConnectionError):
            return "Sunucuya bağlanılamadı. Bağlantınızı kontrol edin."
        return "İşlem sırasında beklenmeyen bir hata oluştu."

    if yanit is None:
        return "Sunucudan yanıt alınamadı."

    durum = yanit.status_code

    mesajlar = {
        401: "Oturumunuz geçersiz. Lütfen yeniden giriş yapın.",
        403: (
            "Bu işlem için gerekli yetkiniz bulunmamaktadır. "
            "Lütfen sistem yöneticinizle iletişime geçin."
        ),
        404: "İstenen kayıt bulunamadı.",
        408: "İstek zaman aşımına uğradı. Lütfen tekrar deneyin.",
        422: "Girilen bilgiler geçersiz. Lütfen kontrol edin.",
        429: "Çok fazla istek gönderildi. Lütfen daha sonra tekrar deneyin.",
    }

    detay = sema_uyumsuz_detayi(yanit)
    if detay:
        return detay

    if durum in mesajlar:
        return mesajlar[durum]

    if durum >= 500:
        return "Sunucuda bir hata oluştu. Lütfen daha sonra tekrar deneyin."

    if durum >= 400:
        return f"İşlem gerçekleştirilemedi (HTTP {durum})."

    return ""
