# TKYS Ortak Kullanım Kılavuzu

Bu bölüm, rolünüz ne olursa olsun sistemi kullanırken ihtiyaç duyacağınız temel şeyleri anlatır.

## 1. Giriş yapmak

1. Uygulamayı açın. **Hoş Geldiniz** ekranında **Kullanıcı Adı** ve **Şifre** alanlarını doldurun.
2. **GÜVENLİ OTURUM AÇ** düğmesine basın.

Hesabınızı sistem yöneticiniz oluşturur; kendiniz hesap açamazsınız.

### İlk giriş ve geçici şifre
Hesabınız yeni açıldıysa ya da şifreniz yönetici tarafından sıfırlandıysa size bir **geçici şifre** verilmiştir.
İlk girişte sistem **yeni bir şifre belirlemenizi** ister. Geçici şifrenin **süresi sınırlıdır** (varsayılan 48 saat);
süre dolmadan giriş yapıp yeni şifrenizi belirleyin, aksi halde yöneticiden yenisini isteyin.

Yeni şifre kuralları (ekranda anlık kontrol listesi olarak görünür; hepsi sağlanmadan düğme açılmaz):
- En az **8 karakter**
- En fazla 72 bayt (çok uzun olmasın)
- Eski şifrenizle **aynı olmamalı**
- İki yeni şifre alanı **birbiriyle aynı** olmalı

Şifrenizin gücü bir göstergeyle gösterilir; büyük/küçük harf, rakam ve sembol karıştırmak gücü artırır.
Şifrenizi kimseyle paylaşmayın; sistem yöneticisi bile şifrenizi **bilemez**, yalnızca yenisini verebilir.

### Şifremi unuttum
Giriş ekranındaki **Şifremi Unuttum?** bağlantısıyla yönetici için bir talep bırakırsınız. Yönetici kimliğinizi **yüz yüze ya da
telefonla doğruladıktan sonra** geçici bir şifre verir. (Güvenlik için talep ekranı hesabın var olup olmadığını belli etmez.)

### Hatalı giriş ve kilit
- Aynı hesapta art arda **5 hatalı** denemeden sonra hesap **1 dakika**, **10 hatalı** denemeden sonra **15 dakika** kilitlenir. Beklemeniz yeterlidir.
- Aynı bilgisayardan kısa sürede çok fazla hatalı deneme yapılırsa o bilgisayardan giriş kısa süre engellenir.
- Doğru giriş yapınca hatalı deneme sayacı sıfırlanır.

### Oturum süresi
Oturumunuz giriş yaptıktan yaklaşık **45 dakika** sonra sona erer. Süre dolduğunda sistem sizi uyarır ve yeniden giriş ister.
Yarım kalan bir formu kaydetmeden önce oturumunuzun süresine dikkat edin.

## 2. Ekran düzeni

- **Sol menü:** Yetkinize göre sayfalar bölümlere ayrılmış olarak listelenir. **☰** düğmesi menüyü daraltır/genişletir.
  Menüde bir sayfayı göremiyorsanız o sayfa için yetkiniz yoktur.
- **Üst çubuk:** Açık sayfanın adı, bildirimler (🔔), **?** (Hakkında / Yardım) ve **🏠 Ana Sayfa** düğmesi.
- **Ana Kontrol Paneli:** Günün özeti ve sık kullanılan sayfalara kısayol kartları. Bir karta tıklayınca ilgili sayfa açılır.
- **Sayfanın sağ üstündeki işlem düğmeleri:** Yetkinize göre görünür; örneğin **＋ Yeni Randevu**.

## 3. Listelerle çalışmak

Çoğu sayfa bir liste (tablo) gösterir. Ortak özellikler:

| Ne yapmak istiyorsunuz? | Nasıl? |
|---|---|
| Bir kaydı bulmak | Üstteki **arama kutusuna** yazın; liste siz yazdıkça daralır. Türkçe karakter ve büyük/küçük harf fark etmez |
| Sıralamak | Sütun **başlığına tıklayın** (artan), tekrar tıklayın (azalan). Başlıktaki ok yönü gösterir. Sayılar sayı gibi (9, 10'dan önce), tarihler tarih gibi, Türkçe harfler Türkçe sırayla sıralanır; boş değerler hep en sonda kalır. **İŞLEM** sütunu sıralanmaz |
| Güncel veriyi görmek | **⟳ Yenile** düğmesi ya da **F5**. Yenileyince sıralama sunucunun sırasına döner |
| Bir kaydı düzenlemek | Listede kaydın üstüne **çift tıklayın** (yetkiniz varsa) ya da satırın sonundaki ✎ düğmesini kullanın |
| Süzmek | Sayfadaki dönem, durum ve tür seçicilerini kullanın |

### Excel'e aktarmak
**Cihaz Envanteri**, **Öğrenciler** ve **Danışanlar** sayfalarında **⬇ Excel'e Aktar** düğmesi vardır; raporlarda da vardır.
- Dosyaya, ekranda **o an görünen** kayıtlar yazılır. Önce arama ya da süzgeç uygularsanız yalnızca onlar aktarılır.
- Dosya iki sayfadan oluşur: **Özet** (aktarım zamanı, kullandığınız süzgeçler, satır sayısı) ve tablonun kendisi.
- Aktarımlar sistemde **denetim kaydına yazılır** (kim, ne zaman, hangi liste, kaç satır). Bu bir güvenlik önlemidir.
- Excel'de açık olan aynı adlı dosyanın üstüne yazılamaz; farklı bir ad seçin ya da dosyayı kapatın.
- Aktardığınız dosya kişisel veri içerebilir (örneğin öğrenci adı ve telefonu); dosyayı **paylaşırken dikkatli olun**.

## 4. Klavye kısayolları

| Tuş | Ne yapar |
|---|---|
| **Ctrl + N** | Açık sayfadaki ilk **"＋ Yeni ..."** işlemini başlatır (örneğin Yeni Randevu, Öğrenci Ekle, Cihaz Ekle). Sayfada yeni kayıt işlemi yoksa ya da yetkiniz yoksa hiçbir şey olmaz |
| **Ctrl + F** | Açık sayfadaki arama kutusuna gider |
| **F5** | Açık sayfayı hemen yeniler |
| **F1** | Hakkında / Yardım penceresini açar |
| **Esc** | Açık pencere ya da formu kapatır |

## 5. Bildirimler ve mesajlar

- İşlem başarılı olunca ekranın altında kısa süre **yeşil bir bildirim** görünür ve kendiliğinden kaybolur; tıklamanız gerekmez.
- **Uyarı ve hata** pencereleri ise okumanız gerektiği için pencere olarak kalır; mesajı okuyup **Tamam**'a basın.
- Üst çubuktaki **🔔** bildirimleri listeler (örneğin bekleyen onaylar, parola talepleri). Bildirime tıklamak sizi ilgili sayfaya götürür.

## 6. Hakkında / Yardım

**F1** ya da üst çubuktaki **?** düğmesi, üç sekmeli bir pencere açar:
- **Hakkında:** İstemci ve sunucu sürümü, veritabanı şema sürümü, kullanıcı adınız/rolünüz. İstemci ve sunucu sürümü farklıysa uyarı çıkar.
  **Destek bilgisini kopyala** düğmesi tüm bu bilgiyi tek metin olarak panoya alır; sorun bildirirken mesajınıza yapıştırın.
- **Kısayollar:** Yukarıdaki kısayol listesi.
- **Yardım:** Kısa kullanım ipuçları.

## 7. Kişisel veri ve gizlilik

- **Danışanlar adla değil kodla** (örneğin `DAN-2026-0001`) kayıtlıdır. Danışanın adını, telefonunu ya da tanısını sisteme **yazmayın**.
- Randevu iptal ederken ya da açıklama alanlarına **kişisel bilgi (ad, telefon, tanı) yazmayın**. İptal notu en fazla 100 karakterdir.
- Sisteme yaptığınız önemli işlemler (giriş, kayıt ekleme/düzeltme/silme, rol değişikliği, Excel aktarımı) **denetim kaydına yazılır**.
- Ekranınızı açık bırakıp ayrılmayın; ayrılırken pencereyi kapatın.

## 8. Sık karşılaşılan durumlar

| Gördüğünüz | Ne anlama gelir / ne yapmalı? |
|---|---|
| **"Bu işlem için yetkiniz bulunmuyor."** | Rolünüzün bu işleme izni yok. Gerekiyorsa sistem yöneticinizden yetki isteyin |
| Menüde bir sayfa yok | O sayfa için yetkiniz yok (bkz. [kılavuz ana sayfası](README.md) yetki tablosu) |
| **"Sunucuya ulaşılamadı"** / liste yüklenmiyor | Sunucuyla bağlantı kesilmiş olabilir. Ağınızı kontrol edin, birkaç saniye sonra **F5** deneyin; sürerse yöneticinize bildirin |
| **"Token süresi dolmuş"** / oturum uyarısı | Oturum süreniz doldu; yeniden giriş yapın |
| **"Hesap geçici olarak kilitli."** | Çok fazla hatalı giriş yaptınız; 1 ya da 15 dakika bekleyip yeniden deneyin |
| Liste boş görünüyor | Arama kutusunu ve dönem/durum süzgeçlerini kontrol edin; **Filtreleri Temizle** ya da dönemi "Tüm tarihler" yapın |
| Randevu listesinde "(toplam N; en yeniler yüklendi, daraltmak için dönem seçin)" | Çok fazla randevu olduğundan en yeni 2000'i gösteriliyor; **Bu ay**, **Bu hafta** ya da **Özel aralık** seçerek eskilere ulaşın |
| Ekranda "veritabanı şeması güncel değil" benzeri bir uyarı (503) | Sistem yöneticisinin güncelleme (migration) yapması gerekir; yöneticinize bildirin |
| Sistem yavaş | **F5** ile yenileyin; sorun sürerse yöneticiye, **Destek bilgisini kopyala** metniyle birlikte bildirin |
