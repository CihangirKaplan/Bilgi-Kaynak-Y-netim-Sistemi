"""Liste uçlarının üst sınırı ve toplam kayıt bildirimi (ortak yardımcılar). `server/sunucu.py` içinden ayrıldı."""



# Zamanla büyüyen kayıt listeleri (rezervasyon, arıza, bakım, kalibrasyon) en yeni bu kadar kaydı döndürür. Normal kullanımda yıllarca sınıra
# ulaşılmaz; ulaşılırsa gerçek toplam X-Toplam-Kayit başlığında gönderilir ve ekran "en yeni N / toplam M" der (randevu listesindeki gibi).
LISTE_UST_SINIRI = 5000


def liste_siniri_coz(limit) -> int:
    """İstemcinin istediği kayıt sayısı (1..LISTE_UST_SINIRI); verilmediyse üst sınır. Uç fonksiyonları doğrudan çağrıldığında
    (testler) varsayılan olarak bir Query nesnesi gelir; o da "verilmedi" sayılır."""
    return limit if isinstance(limit, int) and not isinstance(limit, bool) and 1 <= limit <= LISTE_UST_SINIRI else LISTE_UST_SINIRI


def liste_toplamini_bildir(cursor, response, gelen_satir_sayisi: int, sayim_sql: str, sinir: int | None = None) -> None:
    """Liste istenen sınıra (verilmediyse üst sınıra) ulaştıysa gerçek toplamı X-Toplam-Kayit başlığına yazar; ulaşmadıysa ek sorgu yapmaz."""
    if response is None or gelen_satir_sayisi < (LISTE_UST_SINIRI if sinir is None else sinir):
        return
    cursor.execute(sayim_sql)
    response.headers["X-Toplam-Kayit"] = str(cursor.fetchone()[0])
