# Veri Saklama Politikası

**Merkez kararı (23 Kasım 2026): kayıtlar 10 yıl saklanır.** Bu belge, sistemdeki hangi verinin ne kadar süre, nerede ve nasıl saklandığını özetler.
Hukuki uygunluğun merkezin KVKK sorumlusu tarafından da doğrulanması önerilir; süre değişirse yalnızca bu belge ve ilgili ayarlar güncellenir.

## 1. Özet tablo

| Veri | Kişisel veri içerir mi? | Saklama süresi | Süre dolunca |
|---|---|---|---|
| **Gönüllü öğrenci kayıtları** (ad, numara, telefon) | **Evet** | **10 yıl** (kayıt tarihinden) | Sistem uyarır (Öğrenciler sayfası, **Süresi Dolan Kayıtlar**). Yetkili kişi kaydı **erteler** ya da **siler**; silme kalıcıdır ve denetim kaydına yazılır |
| **Danışan kodları ve randevular** (kodla tutulur) | Hayır: ad, telefon, tanı yoktur (FR-008) | **10 yıl** | Otomatik silme **yoktur**; süre dolunca silme ya da arşivleme kararı merkeze aittir |
| **Cihaz, bakım, kalibrasyon, arıza, rezervasyon kayıtları** | Hayır (yalnızca işlemi yapan kullanıcının kullanıcı adı) | **10 yıl** | Otomatik silme yoktur |
| **Kullanıcı hesapları** | Kullanıcı adı, personel kodu | Hesap **silinmez**, pasife alınır (geçmiş kayıtlar korunur) | — |
| **Denetim kayıtları** (kim, ne zaman, ne yaptı; işlemin yapıldığı bilgisayarın adresi) | Personelin kullanıcı adı ve IP adresi | **10 yıl** | Kayıtlar veritabanı tarafından **değiştirilemez ve silinemez**; süre dolunca arşivleme kararı merkeze aittir |
| **Yedekler** (tüm veri) | Evet | **14 gün**; en yeni **3 yedek** her zaman saklanır | Otomatik temizlenir |
| **Sunucu günlüğü** (`logs\sunucu.log`) | Hata ayrıntılarında olabilir (örn. yinelenen öğrenci numarası) | 5 MB'ı aşınca yeni dosyaya geçilir; yalnızca son iki dosya kalır | Eski dosya otomatik değişir |
| **Giriş denemesi sayaçları** (hatalı giriş sınırı) | Hayır (adres özetlenmiş tutulur) | **1 saat** | Otomatik silinir |
| **Oturum anahtarı (token)** | Hayır | **45 dakika** (çıkışta hemen geçersiz olur) | — |

## 2. Uygulama notları

- **"Saklanır" ile "ekranda görünür" aynı şey değildir.** Cihaz rezervasyon, arıza, bakım ve kalibrasyon listeleri ekranda **en yeni 5000 kaydı** gösterir (normal kullanımda yıllarca sınıra ulaşılmaz). Daha eski kayıtlar silinmez, veritabanında durur; sınıra ulaşılırsa ekran "en yeni 5000 / toplam N kayıt" yazar.
- **Öğrenci kaydının silinmesi geri alınamaz.** Silmeden önce Excel dışa aktarımı ya da yedek gerekiyorsa alınmalıdır. Silme erteleme tarihi gelmeden reddedilir.
- Excel çıktıları kişisel veri içerebilir (öğrenci adı, telefon); aktarımlar denetim kaydına yazılır. Dosyalar kurum dışına verilmemelidir.
- **Yedekler 14 gün tutulduğu için** silinen bir öğrenci kaydı, 14 güne kadar eski yedeklerde durur. Kalıcı silme istenen durumlarda bu süre göz önünde bulundurulmalıdır.

## 3. Gözden geçirme

- **Yılda bir (örneğin Ocak ayında)**: Öğrenciler sayfasındaki **Süresi Dolan Kayıtlar** listesi işleme alınır (ertele ya da sil).
- 10 yılı dolan danışan/randevu/denetim kayıtları için merkez karar verdiğinde, silme ya da arşivleme işlemi için ayrı bir araç geliştirilir; **o zamana kadar hiçbir şey otomatik silinmez.**
- Süre (10 yıl) değişirse: bu belge, Memur Kılavuzu (öğrenci kayıt süresi) ve sunucudaki öğrenci saklama süresi sorguları (`server/sunucu.py` içinde `INTERVAL '10 years'` geçen yerler) birlikte güncellenmelidir; süre koda gömülüdür, ekrandan değiştirilemez.
