# Müdür (Yönetici) Kılavuzu

Bu kılavuz **Müdür (Yönetici)** rolü içindir. Giriş, şifre, arama, sıralama, Excel ve kısayollar için önce
[Ortak Kullanım Kılavuzu](../Ortak_Kullanim.md)'na bakın.

Müdür rolü, merkezin işleyişini **izlemek ve yönetmek** için tasarlanmıştır: raporlar, kullanıcılar, denetim ve cihaz/öğrenci kayıtlarının çoğu size açıktır.
Randevuyu **siz oluşturmazsınız** (randevu sayfasını izlersiniz); psikolog ve danışma öğrencileri oluşturur.

## Menünüzde neler var?

| Bölüm | Sayfalar |
|---|---|
| **Genel** | Ana Kontrol Paneli |
| **Klinik Operasyon** | Randevu Yönetimi (görüntüleme), Oda Kullanımı, Oda Etkinlikleri, Randevu Raporları, **Oda Kullanım Raporu** |
| **Öğrenci & Faaliyet Yönetimi** | Öğrenciler, Faaliyet Kayıtları, Puan Raporu, Öğrenci Raporu, Faaliyet Raporu, Danışma Masası Raporları |
| **Cihaz Yaşam Döngüsü** | Cihaz Uygunluğu, Cihaz Envanteri, Bakım Kayıtları, Bakım Planları, Kalibrasyon, Arıza Kayıtları, Cihaz Raporları |
| **Yönetim & Denetim** | **Yönetim Raporları ve İstatistikler**, **Kullanıcı & Personel**, **Audit Kayıtları**, **Yetki Raporu**, **Sistem Durumu**, Oda Yönetimi |

Rol ve izinleri değiştirmek (**Rol & İzin Yönetimi**), kullanıcıya **parola sıfırlamak** ve danışma masası görev **onayı/yönetimi** varsayılan olarak **Sistem Admin** ve **Memur**'a aittir.
Yetkileriniz sistem yöneticisi tarafından değiştirilmiş olabilir; menüde olmayan bir sayfa için yetkiniz yoktur.

---

# 1. Yönetim Raporları ve İstatistikler

Merkezin dönemsel özet panelidir. Sayfayı açtığınızda ve süzgeçleri değiştirdiğinizde veri **kendiliğinden yüklenir**; **Yenile**'ye basmanız gerekmez
(yalnızca **Tarih Aralığı** seçince tarihleri seçip **Yenile**'ye basarsınız).

**Dönem:** *Bugün, Bu Hafta, Bu Ay, Geçen Ay, Tarih Aralığı.* Seçilen dönem, **önceki dönemle karşılaştırılır** (önceki dönemin nasıl seçildiği aşağıda).

**Görünüm** (rapor türü) listesi:

| Görünüm | Ne gösterir? |
|---|---|
| **Genel Bakış** | Randevu, bakım, kalibrasyon, arıza, rezervasyon, etkinlik ve öğrenci faaliyeti özeti |
| **Randevular** | Durum sayıları, günlük eğilim, oda kullanımı |
| **Cihazlar** | Bakım/kalibrasyon/arıza/rezervasyon sayıları, cihaz kullanımı |
| **Öğrenciler** | Faaliyet türüne göre puanlar, onaylı puan |
| **Proje / Deney** | Proje türü rezervasyonları ve oda etkinlikleri (rezervasyon, "tamamlanmış deney" demek değildir) |
| **Oda Kullanımı** | Oda Kullanım Raporu'nun özeti |
| **Cihaz Kullanımı** | Cihaz Rezervasyon Raporu'nun özeti |
| **Yetkiler** | Yetki Raporu'nun özeti (dönemden bağımsız) |
| **Öğrenci Mevcudu** | Öğrenci Raporu'nun özeti |
| **Faaliyet Onayları** | Faaliyet Raporu'nun özeti (onay bekleyen puanlar) |
| **Bakım Gecikmeleri** | Geciken Bakım Planı Raporu'nun özeti |
| **Bugün Merkezde** | Seçilen günün zamanlı olayları (randevu, rezervasyon, etkinlik) ve günlük özeti; dönemden bağımsızdır |

**Sayılar nasıl okunur?**
- Randevu, rezervasyon ve etkinlik sayılarında **iptal edilenler hariçtir**; iptaller ayrıca ("iptal hariç · N iptal ayrıca") gösterilir.
- **Gelmeme oranı** = gelmeyenler / sonuçlanan randevular (tamamlanan + gelmeyen); **Tamamlanma oranı** de aynı paydayla hesaplanır.
  Başlangıç saati geçtiği hâlde **sonucu girilmemiş** (ne Tamamlandı ne Gelmedi işaretlenmiş) randevu varsa kartta **"⚠ N randevunun sonucu girilmemiş"** uyarısı çıkar; oranlar bu yüzden eksik olabilir. Psikologlardan gün sonunda randevuları işaretlemelerini isteyin.
- Kartlardaki **değişim rozeti** seçilen dönemi **takvime göre** seçilen önceki dönemle karşılaştırır: *Bu Ay* için geçen ayın aynı günleri (1–21 Kasım ↔ 1–21 Ekim), *Geçen Ay* için bir önceki ayın tamamı, *Bugün* ve *Bu Hafta* için geçen haftanın aynı günleri, diğer tarih aralıkları için hemen önceki aynı uzunluktaki aralık. Önceki dönemde hiç kayıt yoksa yüzde hesaplanamaz ve "önceki dönemde yok" yazar. Aynı bilgi **ⓘ Dönemler Hakkında** düğmesindedir.
- Her grafikte **Sütun / Çizgi / Pasta** seçici vardır; grafiğin türünü ihtiyacınıza göre değiştirebilirsiniz.

Önemli: **Oda Kullanımı, Cihaz Kullanımı, Yetkiler, Öğrenci Mevcudu, Faaliyet Onayları ve Bakım Gecikmeleri** görünümleri, ayrıntılı rapor sayfalarıyla **aynı veriden** beslenir; sayılar birebir aynıdır.
Bir görünümün verisi için yetkiniz yoksa yalnızca o görünümde **"Bu rapor alınamadı"** yazar, diğerleri çalışır.
Hesaplama tanımları (doluluk oranı, iptal sayımı vb.) için [Raporlama Rehberi](../../docs/Raporlama_Rehberi.md)'ne bakın.

## Ayrıntılı rapor sayfaları
Yönetim panelindeki özetin ayrıntısı için ilgili sayfayı açın; her birinde dönem seçilir ve **⬇ Excel'e Aktar** vardır:

| Sayfa | İçerik |
|---|---|
| **Randevu Raporları** | Durum sayıları, psikolog bazlı döküm, iptal nedenleri, görüşme tipi/terapi türü/yaş grubu dağılımı |
| **Oda Kullanım Raporu** | Oda bazlı saat, mesai doluluk oranı, hiç kullanılmayan odalar, gün dağılımı |
| **Cihaz Raporları** (5 sekme) | Bakım-kalibrasyon-arıza; Cihaz Rezervasyonu sekmesinde cihaz/proje/bölüm bazlı kullanım; Geciken Bakım Planları sekmesinde geciken ve yaklaşan planlar |
| **Puan / Öğrenci / Faaliyet Raporu** | Öğrenci puanları, mevcut ve dağılım, faaliyet ve onay durumları |
| **Danışma Masası Raporları** | Görev sayıları ve çalışma süreleri, öğrenci bazlı özet |

Excel dosyaları kişisel veri içerebilir (öğrenci adı vb.); paylaşırken dikkatli olun.

## Ana Kontrol Paneli
Bugünkü randevular, cihaz durum sayıları, **açık arıza** sayısı ve bugünkü rezervasyonlar. Kartlara tıklayarak ilgili sayfaya gidersiniz.
Cihaz durumunda, bugün bakım/kalibrasyon aralığında olan cihaz "bakımda/kalibrasyonda" sayılır.

---

# 2. Kullanıcı & Personel

Sistemi kullanan kişilerin hesaplarını yönetirsiniz. Liste sütunları: **Personel ID, Kullanıcı Adı, Personel Kodu, Rolü, Durum, Kayıt Tarihi.**
Başlığa tıklayarak sıralayabilir, arama ile süzebilirsiniz. Sayfanın sağ üstündeki düğmeler:

- **＋ Kullanıcı Oluştur**
- **⏸ Aktiflik Düzenle**
- **🔁 Rol Ata / Değiştir**
- **🏠 Oda Yetkileri**

(**🔑 Parola Sıfırla** varsayılan olarak yalnızca Sistem Admin'dedir.)

## 2.1 Yeni kullanıcı oluşturmak
1. **＋ Kullanıcı Oluştur**'a basın.
2. **Sistem Rolü**'nü seçin. (Atayabileceğiniz roller yetkinize göre listelenir. **Geniş yetkili** bir rol seçince sistem uyarı gösterir: yalnızca güvendiğiniz kişilere verin.)
3. **Kullanıcı Adı**'nı yazın. Kullanıcı adı **yalnızca İngilizce harf, rakam ve `.` `_` `-`** içerebilir; **boşluk, görünmez karakter ve benzer görünen yabancı harfler (Kiril, Yunan)** kabul edilmez. Başındaki/sonundaki boşluklar silinir. Kullanıcı adı **benzersiz** olmalıdır; **büyük/küçük harf fark etmez** (`Ayse` ile `ayse` aynı hesaptır, ikisi birlikte açılamaz ve girişte hangisini yazdığınız önemli değildir).
4. Rol **Psikolog** ise **Kullanacağı Odaları** seçin: **her psikologun en az bir odası olmalıdır.**
5. Rol **Danışma Öğrencisi** ise öğrencinin **Ad Soyad**, **Öğrenci Numarası** ve (isteğe bağlı) **Telefon** bilgisi de girilir.
6. Kaydedin. Sistem kişiye bir **geçici parola** üretir ve **bir kez** gösterir (kopyalanabilir pencerede). **Pencere kapandıktan sonra bu parola tekrar gösterilemez**; kişiye hemen iletin. Kişi ilk girişte kendi şifresini belirler.

## 2.2 Aktiflik, rol ve oda yetkisi
- **Aktiflik Düzenle:** Seçili kullanıcıyı **pasife** alır ya da yeniden **aktif** eder. Pasif kullanıcı sisteme giremez. Hiçbir hesap silinmez; geçmişi korunur.
  Bir **psikoloğu pasife alırken** sistem bazı koşullar arar (örneğin ilerideki planlı randevuları, atanmış odaları, danışanları); bunlar çözülmeden pasife alma reddedilebilir ve nedenini yazar.
- **Rol Ata / Değiştir:** Seçili kullanıcının rolünü değiştirir. **Kendi rolünüzü değiştiremezsiniz.** Rol değişikliği **denetim kaydına** yazılır (önceki ve yeni rol, personel kodu ve etkilenen danışan sayısıyla).
- **Oda Yetkileri:** Psikologun randevu verebileceği odaları belirler. Bir psikolog randevu açarken yalnızca kendisine atanmış odaları görür; "oda listesi boş" şikâyeti genellikle buradan çözülür. **Her psikologun en az bir odası olmalıdır.**

## 2.3 Rol hiyerarşisi
Kullanıcı yönetimi yetkisi olan biri, **kendi seviyesindeki ya da daha yüksek** bir rolü kullanıcıya veremez ve o roldeki kullanıcıları yönetemez
(oluşturma, rol değiştirme, aktif/pasif yapma). Sıra yukarıdan aşağıya: **Sistem Admin › Müdür › Memur › Psikolog › Proje Asistanı › Danışma Öğrencisi**;
sonradan tanımlanan roller en altta sayılır. Örneğin Müdür bir Memur ya da Psikolog oluşturabilir, ama **başka bir Müdür** oluşturamaz ya da pasife alamaz; bunu yalnızca Sistem Admin yapar.
Engellenen işlemde "Kendi rolünüzle aynı ya da daha yüksek seviyedeki bir rolü atayamaz veya bu roldeki kullanıcıları yönetemezsiniz." mesajı çıkar.

---

# 3. Audit Kayıtları

Sistemde yapılan önemli işlemlerin **değiştirilemez** izidir (kim, ne zaman, ne yaptı). **Salt okunur**dur; kayıt silinemez ya da değiştirilemez.

- **Süzgeçler:** **Dönem** (hazır ya da **Başlangıç / Bitiş** tarihi), **işlem türü** (aşağıdaki liste), **kullanıcı adı ara**; **Filtrele**, **Filtreleri Temizle**, **Yenile**.
- Liste sayfalıdır (**← Önceki / Sonraki →**). Bir satırın **Görüntüle** düğmesi **Denetim Kaydı Detayları** penceresini açar; silme ve güncelleme kayıtlarında **silinen veri ya da önceki/yeni değerler** burada görünür (kişisel veri olduğu için bazı alanlar kaydedilmez ve "kaydedilmeyen alanlar" olarak belirtilir).
- **⬇ Excel'e Aktar:** Süzgeçlerinize uyan kayıtları dosyaya yazar.

İşlem türleri: *Giriş Başarılı, Başarısız Giriş, Oluşturma, Güncelleme, İptal, Silme, Rol Değişikliği, Cihaz Durum Değişikliği, Parola Sıfırlama, Parola Değiştirme, Başarısız Parola Değiştirme, Çıkış, Görüntüleme* ve **Excel Aktarımı** (Cihaz, Öğrenci ve Danışan listelerinden Excel'e aktarım: kim, ne zaman, hangi liste, kaç satır).
**Görüntüleme**, denetim kayıtlarına **kimin baktığını** gösterir (ilk sayfa açıldığında, aynı kişi için 10 dakikada bir kaydedilir; sayfa yenilemeleri günlüğü doldurmaz).
Her kaydın **Görüntüle** penceresinde ve Excel çıktısında işlemin hangi bilgisayardan yapıldığını gösteren **İstemci Adresi** vardır (eski kayıtlarda boş olabilir).

**Neye dikkat edilmeli?** Aynı kullanıcıdan art arda *Başarısız Giriş*, beklenmedik saatlerde *Silme* ya da çok satırlı *Excel Aktarımı* kayıtları incelenmeye değerdir; aynı hesabın alışılmadık bir **İstemci Adresi**'nden girmesi de dikkat çekicidir.

# 4. Yetki Raporu

Kullanıcıların ve rollerin **güvenlik özeti**: kullanıcılar ve rolleri, **son giriş** zamanları, **kilitli hesaplar**, **hiç giriş yapmamış aktif hesaplar**, **geçici parolalı hesaplar**, son 30 gündeki başarısız girişler ve rol bazında izin sayıları.
Parola ya da parola özeti **hiçbir zaman** gösterilmez. **⬇ Excel'e Aktar** ayrıca **rol-izin matrisini** de içerir. Düzenli (örneğin ayda bir) bakıp artık çalışmayan kişilerin hesaplarını pasife almanız önerilir.

# 5. Sistem Durumu

Teknik bir bilgi gerekmeden sistemin sağlığını görürsünüz:

| Kart | Anlamı |
|---|---|
| **Uygulama Sürümü** | Sunucu sürümü; istemci sürümünden farklıysa sarı uyarı çıkar (istemciyi güncelleyin) |
| **Veritabanı Şeması** | Veritabanının güncellik sürümü |
| **Veritabanı Boyutu** | Disk üzerindeki boyut |
| **Son Yedek** | Son yedeğin tarihi ve kaç saat önce alındığı. **Yeşil:** güncel. **Sarı:** son yedek **36 saatten eski**. **Kırmızı:** yedek yok |
| **Son girişler** tablosu | Son **45 dakikada** giriş yapanlar (oturumu hâlâ açık olabilecek kişiler) |
| Alt satır | Son 24 saatteki başarısız giriş sayısı, aktif kullanıcı, randevu ve danışan kodu sayıları |

**Son Yedek** kartı sarı ya da kırmızıysa sistem yöneticisini/teknik sorumluyu haberdar edin.

---

# 6. Cihaz, öğrenci ve oda işleri

Aşağıdaki sayfalar için adım adım anlatım [Memur Kılavuzu](../administrative/Memur_Kilavuzu.md)'ndadır; sizin için de aynı şekilde çalışırlar:
- **Cihaz Envanteri, Bakım Kayıtları, Bakım Planları, Kalibrasyon, Arıza Kayıtları, Cihaz Uygunluğu** → Memur Kılavuzu **Bölüm 1**.
  (Cihaz **rezervasyonu** yapma yetkisi varsayılan olarak sizde değildir; rezervasyon raporunu görürsünüz.)
- **Öğrenciler, Faaliyet Kayıtları** (10 yıllık kayıt süresi, ertele/sil dahil) → Memur Kılavuzu **Bölüm 2**.
- **Oda Yönetimi, Oda Etkinlikleri** → Memur Kılavuzu **Bölüm 4**.

---

# 7. Müdür için kısa kontrol listesi

**Her gün**
- Ana Kontrol Paneli: açık arıza, bugünkü randevular.
- Yönetim Raporları → **Bugün Merkezde**.

**Her hafta**
- **Cihaz Raporları → Geciken Bakım Planları** sekmesi ve **Bakım Planları**'ndaki *Gecikmiş* satırlar.
- **Faaliyet Raporu** → onay bekleyen puanlar; **Danışma Masası Raporları** → onay bekleyen görevler (onayı Memur/Admin verir).
- **Sistem Durumu** → son yedek yeşil mi?

**Her ay**
- Yönetim Raporları → **Bu Ay / Geçen Ay** karşılaştırması ve Excel.
- **Yetki Raporu** → kullanılmayan hesaplar, kilitli hesaplar.
- **Audit Kayıtları** → olağandışı silme, rol değişikliği ya da çok satırlı Excel aktarımları.
- **Öğrenciler** → süresi dolan gönüllü kayıtları.
