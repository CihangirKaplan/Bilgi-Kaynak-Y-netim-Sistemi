# Ürün Sahibi Doğrulama Listesi

Bu liste, gereksinim tablosunda ([FR_Izlenebilirlik_Tablosu.md](FR_Izlenebilirlik_Tablosu.md)) **"⚠️ Kısmen"** görünen maddeleri ve takvim gereksinimini (FR-012/013) ürün sahibinin
**yaklaşık 15-20 dakikada elle doğrulayabilmesi** için hazırlanmıştır. Maddelerin kodu ve otomatik testleri vardır; eksik olan, birinin "istediğimiz gibi çalışıyor" demesidir.

**Nasıl kullanılır?** Uygulamaya **Memur** (ya da Sistem Admin) hesabıyla girin; her satırdaki adımı yapın, "Beklenen sonuç" ile karşılaştırın ve "Sonuç" sütununa ✔ ya da ✘ yazın.
Bir satır ✘ ise "Not" sütununa gördüğünüzü yazıp geliştiriciye iletin. Tüm satırlar ✔ ise sonundaki onay kutusunu doldurun; geliştirici tablodaki durumu ✅ yapar.

> Deneme sırasında gerçek öğrenci bilgisi kullanmayın; uydurma ad ve numara yazın (örn. "Deneme Öğrenci", `20269999`). İş bitince deneme kayıtlarını pasife alın.

## FR-052: Öğrenci listeleme ve görüntüleme

| # | Adım | Beklenen sonuç | Sonuç | Not |
|---|---|---|---|---|
| 1 | Sol menüden **Öğrenciler** sayfasını açın | Liste şu sütunlarla açılır: Ad Soyad, Öğrenci No, Telefon, Öğrenci Grubu, Bağlı Hesap, Kayıt Tarihi, Durum. Üstte toplam / aktif / pasif / süresi dolan kartları görünür | ☐ | |
| 2 | Arama kutusuna bir öğrencinin adından bir parça yazın | Liste siz yazdıkça daralır; Türkçe karakter ve büyük/küçük harf fark etmez | ☐ | |
| 3 | **Öğrenci grubu** ve **Durum** seçicilerini değiştirin, sonra **Filtreleri Temizle**'ye basın | Liste seçime göre süzülür; temizleyince hepsi geri gelir | ☐ | |
| 4 | Bir öğrenciyi seçip **Detay / Puanlar**'a basın | Öğrencinin faaliyetleri ve puanları görüntülenir | ☐ | |

## FR-053: Öğrenci ekleme

| # | Adım | Beklenen sonuç | Sonuç | Not |
|---|---|---|---|---|
| 1 | **＋ Öğrenci Ekle**'ye basın; Ad Soyad, Öğrenci No, Öğrenci Türü (Gönüllü ya da Asistan), Telefon (`05XX…`, 11 hane) girip kaydedin | Öğrenci listede görünür; yeşil bildirim çıkar | ☐ | |
| 2 | Aynı öğrenci numarasıyla ikinci bir kayıt eklemeyi deneyin | Sistem reddeder ("zaten kayıtlı" benzeri uyarı); yinelenen kayıt oluşmaz | ☐ | |
| 3 | Zorunlu bir alanı (Ad Soyad ya da Öğrenci No) boş bırakıp kaydetmeyi deneyin | Sistem reddeder ve eksik alanı söyler | ☐ | |

## FR-054: Öğrenci aktiflik yönetimi

| # | Adım | Beklenen sonuç | Sonuç | Not |
|---|---|---|---|---|
| 1 | Deneme öğrencisini seçip **Aktiflik Düzenle** ile pasife alın | Durum **Pasif** olur; üstteki kartlarda aktif sayısı azalır | ☐ | |
| 2 | Aynı öğrenciyi yeniden aktif edin | Durum **Aktif** olur | ☐ | |

## FR-055: Öğrenci silme ve erteleme (pasife alındıktan 2 yıl saklama)

Bu madde, öğrencinin pasife alınmasından sonra 2 yıl geçmesiyle ilgilidir; arayüzden "2 yıl önce pasife alınmış" bir öğrenci oluşturulamaz. Bu yüzden adımları **geliştirici hazırlar**
(pasife alınma tarihi 2 yıldan eski bir deneme öğrencisi ekler) ve siz ekranda izlersiniz. Aktif bir öğrencinin süresi hiç işlemez.

| # | Adım | Beklenen sonuç | Sonuç | Not |
|---|---|---|---|---|
| 1 | **Öğrenciler** sayfasını açın | Süresi dolan kayıt varsa sayfa açılışında uyarı çıkar; **Süresi Dolan Kayıtlar (N)** düğmesi sayıyı gösterir | ☐ | |
| 2 | **Süresi Dolan Kayıtlar**'a basın | Süresi dolan gönüllü öğrencilerin listesi açılır (Ad Soyad, Öğrenci No, Pasife Alındığı Tarih, Erteleme Tarihi, Durum: İşlem Bekliyor / Ertelendi) | ☐ | |
| 3 | Bir öğrenciyi seçip **Seçili Öğrenciyi Ertele** ile yeni bir tarih verin | Durum **Ertelendi** olur; erteleme tarihi kaydedilir | ☐ | |
| 4 | Ertelenmiş (erteleme tarihi gelmemiş) öğrenci için **Seçili Kaydı Sil**'i deneyin | Sistem silmeyi **reddeder** (erteleme tarihi gelmeden silinemez) | ☐ | |
| 5 | Erteleme tarihi gelmiş ya da hiç ertelenmemiş süresi dolan bir deneme kaydı için **Seçili Kaydı Sil**'e basıp onaylayın | Kayıt kalıcı olarak silinir; listeden kaybolur. (**Silme geri alınamaz**; yalnızca deneme kaydıyla yapın) | ☐ | |
| 6 | Sistem Admin ile **Audit Kayıtları**'na bakın | Silme işlemi kayıtlıdır; kayıtta öğrencinin adı/telefonu **yoktur** (yalnızca kimliksiz alanlar) | ☐ | |

## FR-058: Faaliyet puanları ve raporlama

| # | Adım | Beklenen sonuç | Sonuç | Not |
|---|---|---|---|---|
| 1 | **Faaliyet Kayıtları** sayfasında deneme öğrencisi için bir faaliyet ekleyin (Faaliyet Türü, Birim, Miktar) | Kayıt listede görünür; puan = Miktar × faaliyet puanı | ☐ | |
| 2 | **Öğrenciler → Detay / Puanlar** ekranını açın | Eklediğiniz faaliyet ve puanı görünür | ☐ | |
| 3 | **Puan Raporu** sayfasında dönemi seçin | Öğrenci başına toplam puan listelenir; deneme öğrencisinin toplamı adım 2'dekiyle tutarlıdır | ☐ | |
| 4 | Aynı sayfada **⬇ Excel'e Aktar**'a basıp dosyayı açın | Excel dosyası oluşur; iki sayfalıdır (Özet ve tablo); puanlar ekrandakiyle aynıdır | ☐ | |

## FR-012 ve FR-013: Günlük ve haftalık takvim

Ayrı bir takvim ekranı yapılmadı; gereksinim **Oda Kullanımı** ekranıyla karşılanıyor. Bunun yeterli olup olmadığına ürün sahibi karar verir.

| # | Adım | Beklenen sonuç | Sonuç | Not |
|---|---|---|---|---|
| 1 | **Oda Kullanımı** sayfasını açın, **Gün** düğmesini seçin | Seçilen günün randevuları (ve varsa rezervasyon/etkinlikler) saatlik ızgarada görünür | ☐ | |
| 2 | **Hafta** düğmesini seçin, **ileri / geri** ile haftalar arasında gezinin; **Bugün** düğmesine basın | Pazartesi-Pazar haftalık ızgara görünür; gezinme çalışır; Bugün bu haftaya döndürür | ☐ | |
| 3 | **Karar:** Bu görünüm "günlük randevu takvimi" ve "haftalık randevu takvimi" gereksinimini karşılıyor mu? | ☐ Evet, karşılıyor  ☐ Hayır, ayrı takvim ekranı istiyoruz | ☐ | |

## Onay

| | |
|---|---|
| Doğrulayan (ad, görev) | |
| Tarih | |
| Sonuç | ☐ Tüm satırlar ✔, maddeler ✅'e alınabilir  ☐ Aşağıdaki satırlar ✘ (geliştiriciye iletildi) |
| Notlar | |
