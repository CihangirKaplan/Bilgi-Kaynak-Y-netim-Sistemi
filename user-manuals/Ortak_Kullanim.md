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
- En az **10 karakter**; en az bir **harf** ve bir **rakam** içermeli
- Kullanıcı adınızı içermemeli ve `password123` gibi çok yaygın bir şifre olmamalı (sunucu reddeder)
- En fazla 72 bayt (çok uzun olmasın)
- Eski şifrenizle **aynı olmamalı**
- İki yeni şifre alanı **birbiriyle aynı** olmalı

Şifrenizin gücü bir göstergeyle gösterilir; büyük/küçük harf, rakam ve sembol karıştırmak gücü artırır.
**Çıkış Yap** düğmesi oturumunuzu sunucuda da kapatır; aynı hesapla başka bilgisayarda açık oturum varsa o da kapanır.
Şifrenizi kimseyle paylaşmayın; sistem yöneticisi bile şifrenizi **bilemez**, yalnızca yenisini verebilir.

### Şifremi unuttum
Giriş ekranındaki **Şifremi Unuttum?** bağlantısıyla yönetici için bir talep bırakırsınız. Yönetici kimliğinizi **yüz yüze ya da
telefonla doğruladıktan sonra** geçici bir şifre verir. (Güvenlik için talep ekranı hesabın var olup olmadığını belli etmez.)

### Hatalı giriş ve kilit
- Aynı hesapta art arda **5 hatalı** denemeden sonra hesap **1 dakika**, **10 hatalı** denemeden sonra **15 dakika** kilitlenir. Beklemeniz yeterlidir.
- Aynı bilgisayardan kısa sürede çok fazla hatalı deneme yapılırsa o bilgisayardan giriş kısa süre engellenir.
- **Şifre değiştirirken** eski şifrenizi art arda yanlış girerseniz de aynı kural geçerlidir: "Bu bilgisayardan çok fazla hatalı şifre denemesi yapıldı" uyarısı çıkar, biraz bekleyip yeniden deneyin.
- Doğru giriş yapınca hatalı deneme sayacı sıfırlanır.

### Oturum süresi
Oturumunuz giriş yaptıktan yaklaşık **45 dakika** sonra sona erer. Süre dolduğunda sistem sizi uyarır ve yeniden giriş ister.
Yarım kalan bir formu kaydetmeden önce oturumunuzun süresine dikkat edin.

**Çıkış Yap** ya da başka bir bilgisayarda aynı hesapla çıkış yapılması oturumu hemen kapatır; eski oturumla yapılan istek
"Oturum geçersiz. Yeniden giriş yapınız." uyarısıyla reddedilir. Ortak bilgisayarda işiniz bitince mutlaka **Çıkış Yap**'ı kullanın.

## 2. Ekran düzeni

- **Sol menü:** Yetkinize göre sayfalar bölümlere ayrılmış olarak listelenir. Program her açılışta menü **daraltılmış** (yalnızca bölüm simgeleri) gelir; sol üstteki **☰** düğmesi menüyü genişletir/daraltır.
  Menüde bir sayfayı göremiyorsanız o sayfa için yetkiniz yoktur.
- **Üst çubuk:** Açık sayfanın adı, bildirimler (🔔), **?** (Hakkında / Yardım) ve **🏠 Ana Sayfa** düğmesi.
- **Ana Kontrol Paneli:** Günün özeti ve sayfanın altında **Hızlı Erişim** kutuları (sık kullanılan sayfalara kısayol). Bir kutuya tıklayınca ilgili sayfa açılır.
  Panelde **bugünkü danışan randevuları** ve, cihaz rezervasyonlarını görme yetkisi olanlarda (Cihaz Uygunluğu'nu görenler ve rezervasyon yapanlar dahil)
  **bugünkü cihaz rezervasyonları** listelenir; böylece merkezde o gün neyin ne zaman kullanıldığını herkes bilir. **Rezerve eden** adı yalnızca cihazı
  yönetenlere ve rezervasyon yapanlara gösterilir; yalnızca Cihaz Uygunluğu'nu görenlerde bu sütun yoktur (kişi adı verilmez).
  Ayrıca **herkesin** panelinde **bugünkü oda etkinlikleri** (saat, etkinlik adı, oda, katılımcı sayısı; iptal edilenler listelenmez, organize eden adı
  gösterilmez) listelenir. Bu bölümler yalnızca bilgi verir; etkinlik eklemek ya da cihaz rezervasyonu yapmak için ilgili sayfanın izni gerekir.
  - **Bugün | Yarın | Bu hafta (7 gün):** Randevu, cihaz rezervasyonu ve oda etkinliği panelleri seçtiğiniz güne göre değişir. Üstteki özet kartları her zaman **bugünü** sayar.
  - **🙋 Benim Günüm:** Size ait bugünkü ve yarınki randevular ile cihaz rezervasyonları (yalnızca kendi kayıtlarınız). Kaydınız yoksa bu kutu görünmez.
  - **📢 Duyurular:** Kurum içi duyurular **herkesin** panelinde görünür. Okumadıklarınız 🆕 ile en üstte durur; her duyurunun yanındaki **Okudum** düğmesi duyuruyu
    **yalnızca sizin için** gizler (duyuru silinmez, diğer kullanıcılarda yayında kalır). Birden fazla okunmamış varsa **Hepsini okudum** çıkar. Gizlediklerinize
    **Okunan duyurular** bölümünden ulaşır, **Tekrar göster** ile yeniden öne çıkarabilirsiniz. **Duyuru yönetme** izni olanlar (varsayılan: Danışma Öğrencisi dışında herkes)
    **＋ Yeni duyuru** ile yayınlar, isteğe bağlı son geçerlilik tarihi verir (tarih geçince kendiliğinden kalkar) ve **Kaldır** ile siler. Duyuruya kişisel bilgi
    (danışan adı, telefon vb.) yazmayın; duyuruyu kimin yazdığı yalnızca duyuru yönetenlere gösterilir.
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
- Üst çubuktaki **🔔** bildirimleri listeler. Bildirime tıklamak sizi ilgili sayfaya götürür. Herkes için: **🙋 Benim günüm** (bugünkü/yarınki randevu ve
  cihaz rezervasyonlarınızın sayısı) ve **okumadığınız duyurular** (satırın yanındaki **Okudum** düğmesiyle zilden de okundu işaretleyebilirsiniz; işaretlediğiniz duyuru zilde ve ana panelde sizin için gizlenir). Yetkinize göre ayrıca: bekleyen danışma görevi onayları, parola talepleri,
  açık arızalar, yaklaşan/geciken bakım ve kalibrasyonlar (yetkiniz olmayan sayfanın bildirimi gösterilmez).

## 6. Hakkında / Yardım

**F1** ya da üst çubuktaki **?** düğmesi, üç sekmeli bir pencere açar:
- **Hakkında:** İstemci ve sunucu sürümü, veritabanı şema sürümü, kullanıcı adınız/rolünüz. İstemci ve sunucu sürümü farklıysa uyarı çıkar.
  **Destek bilgisini kopyala** düğmesi tüm bu bilgiyi tek metin olarak panoya alır; sorun bildirirken mesajınıza yapıştırın.
- **Kısayollar:** Yukarıdaki kısayol listesi.
- **Yardım:** Kısa kullanım ipuçları.

## 7. Kişisel veri ve gizlilik

- **Danışanlar adla değil kodla** (örneğin `DAN-2026-0001`) kayıtlıdır. Danışanın adını, telefonunu ya da tanısını sisteme **yazmayın**.
- Randevu iptal ederken ya da açıklama alanlarına **kişisel bilgi (ad, telefon, tanı) yazmayın**. İptal notu en fazla 100 karakterdir.
- Sisteme yaptığınız önemli işlemler (giriş, çıkış, kayıt ekleme/düzeltme/silme, rol değişikliği, Excel aktarımı) **denetim kaydına yazılır**; kaydın yanında işlemi yapan bilgisayarın adresi de tutulur.
- Ekranınızı açık bırakıp ayrılmayın; ayrılırken pencereyi kapatın.

## 8. Sık karşılaşılan durumlar

| Gördüğünüz | Ne anlama gelir / ne yapmalı? |
|---|---|
| **"Bu işlem için yetkiniz bulunmuyor."** | Rolünüzün bu işleme izni yok. Gerekiyorsa sistem yöneticinizden yetki isteyin |
| Menüde bir sayfa yok | O sayfa için yetkiniz yok (bkz. [kılavuz ana sayfası](README.md) yetki tablosu) |
| **"Sunucuya ulaşılamadı"** / liste yüklenmiyor | Sunucuyla bağlantı kesilmiş olabilir. Ağınızı kontrol edin, birkaç saniye sonra **F5** deneyin; sürerse yöneticinize bildirin |
| **"Token süresi dolmuş"** / **"Oturum geçersiz"** | Oturum süreniz doldu ya da hesabınızdan çıkış yapıldı; yeniden giriş yapın |
| **"Bu bilgisayardan çok fazla hatalı giriş / şifre denemesi yapıldı."** | Aynı bilgisayardan çok sayıda hatalı deneme yapıldı; birkaç dakika bekleyip yeniden deneyin |
| **"Hesap geçici olarak kilitli."** | Çok fazla hatalı giriş yaptınız; 1 ya da 15 dakika bekleyip yeniden deneyin |
| Liste boş görünüyor | Arama kutusunu ve dönem/durum süzgeçlerini kontrol edin; **Filtreleri Temizle** ya da dönemi "Tüm tarihler" yapın |
| Randevu listesinde "(toplam N; en yeniler yüklendi, daraltmak için dönem seçin)" | Çok fazla randevu olduğundan en yeni 2000'i gösteriliyor; **Bu ay**, **Bu hafta** ya da **Özel aralık** seçerek eskilere ulaşın |
| Ekranda "veritabanı şeması güncel değil" benzeri bir uyarı (503) | Sistem yöneticisinin güncelleme (migration) yapması gerekir; yöneticinize bildirin |
| Sistem yavaş | **F5** ile yenileyin; sorun sürerse yöneticiye, **Destek bilgisini kopyala** metniyle birlikte bildirin |
