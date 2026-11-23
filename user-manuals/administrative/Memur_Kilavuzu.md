# Memur Kılavuzu

Bu kılavuz **Memur** rolü içindir (cihaz, öğrenci, faaliyet ve danışma masası işleri). Giriş, şifre, arama, sıralama, Excel ve kısayollar için önce
[Ortak Kullanım Kılavuzu](../Ortak_Kullanim.md)'na bakın.

## Menünüzde neler var?

| Bölüm | Sayfalar |
|---|---|
| **Genel** | Ana Kontrol Paneli |
| **Klinik Operasyon** | Randevu Yönetimi (yalnızca görüntüleme), Oda Kullanımı, Oda Etkinlikleri, Randevu Raporları |
| **Öğrenci & Faaliyet Yönetimi** | Öğrenciler, Faaliyet Kayıtları, Puan Raporu, Öğrenci Raporu, Faaliyet Raporu, Danışma Masası Yönetimi, Danışma Masası Raporları |
| **Cihaz Yaşam Döngüsü** | Cihaz Uygunluğu, Cihaz Envanteri, Cihaz Rezervasyonu, Bakım Kayıtları, Bakım Planları, Kalibrasyon, Arıza Kayıtları, Cihaz Raporları |
| **Yönetim & Denetim** | Oda Yönetimi |

Randevu oluşturma/düzenleme sizin yetkinizde **değildir**; randevu sayfasını yalnızca izlersiniz.

---

# 1. Cihaz işleri

Cihazların bir **yaşam döngüsü** vardır: envantere girer → rezerve edilir ve kullanılır → bakım ve kalibrasyon görür → arızalanabilir → kullanım dışı kalır.
Bir cihazın **durumu** şunlardan biridir: *Kullanıma Hazır, Rezerve, Kullanımda, Bakımda, Kalibrasyonda, Arızalı, Kullanım Dışı.*

## 1.1 Cihaz Envanteri
Kayıtlı tüm cihazlar ve anlık durumları. Üstteki **sayaç çipleri** toplam cihaz, kullanıma hazır, bakım/kalibrasyondaki ve arızalı cihaz sayısını gösterir.

- **Aramak:** Arama kutusuna envanter kodu, cihaz adı, marka ya da seri no yazın.
- **Sıralamak:** Sütun başlığına tıklayın (Durum sütununda rozet metnine göre sıralanır).
- **＋ Cihaz Ekle:** Formda **Envanter Kodu \*** ve **Cihaz Adı \*** zorunludur; **Marka / Model**, **Seri No** isteğe bağlıdır; **Durum \*** seçilir (*Kullanıma Hazır, Bakımda, Kalibrasyonda, Kullanım Dışı*; **Arızalı** elle seçilemez, arıza bildirilince kendiliğinden belirlenir). Envanter kodu **benzersiz** olmalıdır ve **büyük/küçük harf fark etmez** (`EEG-01` ile `eeg-01` aynı kod sayılır). Seri no boş bırakılabilir (birden fazla cihazın seri nosu boş olabilir); doluysa o da benzersiz olmalıdır. Bunlardan biri kullanımdaysa "Bu envanter kodu veya seri no zaten kullanımda." uyarısı çıkar.
- **✎ Envanteri Düzenle** (ya da listede çift tıklama): Cihaz bilgilerini ve durumunu güncellersiniz. Bir cihazı kullanımdan kaldırmak için durumunu **Kullanım Dışı** yapın; cihaz silinmez, geçmişi korunur. **Çözülmemiş arızası olan** cihazın durumu elle değiştirilemez (durum kutusu kilitlenir; yalnızca *Kullanım Dışı* yapılabilir): önce **Arıza Kayıtları**'ndan arızayı *Çözüldü* olarak işaretleyin. Cihazın markası, seri nosu gibi diğer bilgileri arızalıyken de düzenlenebilir.
- **⬇ Excel'e Aktar:** Ekranda görünen cihazları **demirbaş sayımı** için Excel'e yazar (Envanter Kodu, Cihaz Adı, Marka/Model, Seri No, Durum, Kayıt Tarihi). Ana panelden bir durum kartına tıklayıp geldiyseniz yalnızca o durumdaki cihazlar listelenir ve aktarılır; hepsini istiyorsanız önce **Filtreyi kaldır, tümünü göster**'e basın. Aktarım denetim kaydına yazılır.
- **🕘 Cihaz geçmişi** (satır sonundaki düğme): Cihazın **bakım, kalibrasyon, arıza ve rezervasyon** kayıtlarını tek bir zaman çizgisinde (en yeni önce) gösterir. Üstte cihazın **bugünkü durumu** ve özet sayılar (toplam bakım maliyeti, kalibrasyon geçerliliği, açık arıza, rezervasyon saati) bulunur; **Bakım / Kalibrasyon / Arıza / Rezervasyon** düğmeleriyle tek türü süzebilirsiniz. Her türden en yeni 300 kayıt gösterilir.
- Listedeki **Durum**, bugünkü etkin durumu gösterir: bugün bakım ya da kalibrasyon tarih aralığında olan cihaz, kayıtlı durumu *Kullanıma Hazır* olsa da **Bakımda / Kalibrasyonda** görünür; **çözülmemiş arıza kaydı olan cihaz her zaman Arızalı** görünür (bakımda olsa bile). Arıza çözülünce eski durumuna döner. Bu tanım Ana Kontrol Paneli, Cihaz Uygunluğu ve rezervasyonla aynıdır.

## 1.2 Cihaz Uygunluğu
Cihazların hangi gün/saatlerde **uygun olmadığını** (bakım, kalibrasyon, arıza, rezervasyon) gösterir; yalnızca izlersiniz. Rezervasyon yapmadan önce buraya bakmak çakışmayı önler.

## 1.3 Cihaz Rezervasyonu
1. **＋ Yeni Rezervasyon**'a basın.
2. **Cihaz \*** seçin. **Bölüm \*** seçin (listede yoksa yanındaki düğmeyle yeni bölüm ekleyin: *Bölüm adı, Sorumlu kişi, İletişim*).
3. **Kullanılacak oda \***, **Başlangıç \*** ve **Bitiş \*** seçin.
4. İsterseniz **Proje türü** (yoksa yenisini ekleyebilirsiniz) ve **Açıklama** girin.
5. Kaydedin.

Sistem rezervasyonu **reddeder** ve nedenini yazar: bitiş başlangıçtan sonra değilse, başlangıç geçmişteyse, saatler **08:00–18:00** dışındaysa, süre **30 günü** aşıyorsa (daha uzun çalışmalar için ardışık rezervasyonlar açın), cihaz şu anda bakımda/arızalı gibi uygun olmayan bir durumdaysa,
aynı cihaz ya da oda o saatlerde doluysa (çakışma mesajı hangi kayıtla çakıştığını söyler) ya da oda bu iş için uygun değilse.
**Düzenleme ve iptal:** Rezervasyonun ayrıntısını çift tıklayarak açın. **✎ Rezervasyonu düzenle** ile saat, oda, bölüm ve proje bilgisini değiştirebilirsiniz (**cihaz değişmez**; başka cihaz için yeni rezervasyon açın). Saat ya da oda değişirse çakışmalar yeniden denetlenir; rezervasyonun kendisi çakışma sayılmaz. **Başlamış** rezervasyonda başlangıç saati ve oda değiştirilemez; yalnızca bitiş saati, bölüm ve proje bilgileri düzenlenir. Biten ve iptal edilmiş rezervasyonlar düzenlenemez.
**İptal** için ayrıntı penceresinde iptal düğmesine basın; kayıt silinmez, iptal edildi olarak kalır. Bir rezervasyonu **yalnızca oluşturan kişi ya da cihaz yöneticisi** (Memur, Müdür, Admin) düzenleyebilir ya da iptal edebilir; başkasının rezervasyonunda düğmeler görünmez. Biten (süresi dolmuş) rezervasyon iptal edilemez.
**⬇ Excel'e Aktar:** Ekranda görünen rezervasyonları aktarır (Envanter Kodu, Cihaz Adı, Bölüm, Oda, Proje, Tarih ve Saat, Durum); aktarım denetim kaydına yazılır. Aynı düğme **Bakım Kayıtları, Kalibrasyon, Arıza Kayıtları ve Bakım Planları** sayfalarında da vardır.

## 1.4 Bakım Kayıtları
Cihaza yapılan bakımın kaydı.
- **＋ Bakım Kaydı:** **Cihaz \***, **Bakım Yapan Kişi \***, **Yapılan İşlem \***, **Maliyet (₺)**, **Başlangıç Tarihi \*** ve **Bitiş Tarihi \*** girilir. Bitiş tarihi başlangıçtan önce olamaz ve bir bakım **en fazla bir yıl** sürebilir. **Sonraki bakım tarihi bitiş tarihinden sonra** olmalıdır. Ayrı bir "bakım tarihi" girilmez; her zaman başlangıç tarihidir. **Sonraki bakım** için **3 ay / 6 ay / 1 yıl / Tarih seç** düğmelerinden biri ve **Bildirim ne zaman** (tarihe kaç gün kala uyarı çıksın) seçilir; form kaydetmeden önce bu tarih kurallarını denetler ve sorun varsa nedenini yazar.
- Mevcut bir kaydı düzenlerken **cihaz değiştirilemez**; diğer alanlar düzeltilebilir.
- Bakım kaydı cihazın Envanter'deki durumunu **kendiliğinden değiştirmez**; ancak kaydın tarih aralığında cihaz **Cihaz Uygunluğu**'nda uygun değil görünür ve **Ana Kontrol Paneli**'nde "bakımda" sayılır.

## 1.5 Kalibrasyon
- **＋ Kalibrasyon Kaydı:** **Cihaz \***, **Yapan Kurum \***, **Sertifika No \***, **Başlangıç Tarihi \*** ve **Bitiş Tarihi \*** girilir; **Geçerlilik** (sertifikanın geçerli olduğu son tarih; **3 ay / 6 ay / 1 yıl / Tarih seç** düğmeleriyle) ve **Bildirim ne zaman** seçilir. **Geçerlilik tarihi kalibrasyon bitiş tarihinden önce olamaz.**
- Bakım kaydı gibi, kalibrasyon aralığı boyunca cihaz uygunluk takviminde "kalibrasyonda" görünür.

## 1.6 Arıza Kayıtları
- **＋ Arıza Kaydı:** **Arızalı Cihaz \***, **Aciliyet Seviyesi \*** (*Düşük, Orta, Yüksek, Kritik*), **Sorun Başlığı \*** ve **Açıklama \*** girilir.
  Arıza bildirimi oluşturulunca **cihazın durumu otomatik olarak Arızalı** olur ve arıza çözülene kadar öyle kalır (cihaz rezerve edilemez). **Bakımda ya da kalibrasyondaki** cihaza da arıza bildirilebilir: cihaz arıza çözülene kadar yine **Arızalı** görünür, çözülünce bakım/kalibrasyon durumu geçerli olmaya devam eder. Zaten arızalı cihaza ikinci bir arıza da eklenebilir. Yalnızca *Kullanım Dışı* cihaza arıza açılmaz.
- Arızayı düzeltirken **Mevcut Durum** alanında **Açık (devam ediyor)** ya da **Çözüldü (cihaz kullanıma açılır)** seçersiniz; *Çözüldü* cihazı yeniden kullanıma açar.
- **Çözüldü** seçince **Çözüm Notu \*** zorunlu olur: ne yapılarak çözüldüğünü kısaca yazın (en fazla 500 karakter). Not, listede sorun başlığının üzerine gelince ve **Cihaz geçmişi**'nde görünür; Excel aktarımında da yer alır. Çözülmüş bir arızanın satırındaki **↺** düğmesiyle (ya da çift tıklayarak) arızayı **yeniden açabilirsiniz** (yanlışlıkla çözüldü işaretlendiyse): çözüm notu ve çözüm tarihi silinir, cihaz tekrar *Arızalı* görünür.

## 1.7 Bakım Planları
Cihazlar için **tekrarlayan** bakım/kalibrasyon planları. Sistem sonraki tarihe yaklaşınca ve tarih geçince sizi uyarır.
- **＋ Yeni Plan:** **Cihaz \***, **Plan türü \*** (örneğin *Periyodik bakım, Yıllık bakım, 6 aylık bakım, Kalibrasyon, Temizlik ve kontrol* ya da kendi adınız),
  **Tekrar aralığı \*** (*Haftalık 7 gün, Aylık 30 gün, 3 aylık 90 gün, 6 aylık 180 gün, Yıllık 365 gün ya da Özel*), **Uyarı süresi** (kaç gün önceden uyarılsın), **Sonraki tarih** ve **Aktif** kutusu.
- Liste sütunları: **Cihaz, Plan, Tekrar, Uyarı, Sonraki Tarih, Durum, İşlem.** **Durum** rozeti: *Planlı, Yaklaşıyor, Gecikmiş* ve pasif planlar için *Pasif*; yanında "5 gün kaldı" ya da "5 gün gecikti" yazar.
- Satıra çift tıklayarak planı düzenleyebilir, satır sonundaki düğmelerle düzenleyip silebilirsiniz.
- Filtre: *Aktif planlar, Tüm planlar, Pasif planlar.*

## 1.8 Cihaz raporları
**Cihaz Raporları** sayfasında beş sekme vardır: **Bakım Geçmişi**, **Kalibrasyon**, **Arızalar**, **Cihaz Rezervasyonu** (cihaz, proje türü ve bölüm bazlı kullanım) ve **Geciken Bakım Planları** (geciken/yaklaşan planlar ve planı olmayan cihazlar). Her sekmenin kendi süzgeçleri vardır ve **⬇ Excel'e Aktar** içerir. Ayrıntılar: [Raporlama Rehberi](../../docs/Raporlama_Rehberi.md).

---

# 2. Öğrenci işleri

## 2.1 Öğrenciler
Sütunlar: **Ad Soyad, Öğrenci No, Telefon, Öğrenci Grubu, Bağlı Hesap, Kayıt Tarihi, Durum.** Üstteki kartlar toplam, aktif, pasif ve **süresi dolan** öğrenci sayısını gösterir.
- **Aramak ve süzmek:** Ad, numara ya da telefon yazın; **öğrenci grubunu** (*Tüm Öğrenciler, Gönüllü Öğrenci, Danışma Masası Öğrencisi, Asistan Öğrenci*) ve **durumu** (*Her Durum, Aktif, Pasif*) seçin. **Filtreleri Temizle** hepsini sıfırlar.
- **＋ Öğrenci Ekle:** **Ad Soyad \***, **Öğrenci No \***, **Öğrenci Türü \*** (*Gönüllü Öğrenci* ya da *Asistan Öğrenci*), **Telefon** (11 haneli, `05XX...` biçiminde), **Bölüm** ve **Sınıf**.
  **Danışma Masası öğrencileri bu pencereden eklenmez**: onlar giriş hesabı gerektirdiği için **Kullanıcı & Personel** üzerinden oluşturulur (pencere sizi yönlendirir).
- **Aktiflik Düzenle:** Seçili öğrenciyi aktif ya da pasif yapar.
- **Detay / Puanlar:** Seçili öğrencinin faaliyetlerini ve puanlarını gösterir.
- **⬇ Excel'e Aktar:** Ekranda görünen öğrencileri (telefon dahil) yazar; aktarım denetim kaydına yazılır. Dosyayı paylaşırken dikkatli olun.

### 10 yıllık kayıt süresi
**Gönüllü öğrencilerin** kaydı **10 yıl** saklanır. Süresi dolan kayıtlar için sayfa açılınca uyarı çıkar ve **Süresi Dolan Kayıtlar (N)** düğmesi sayıyı gösterir.
- Düğmeye basınca süresi dolan gönüllü öğrencilerin listesi açılır (**Ad Soyad, Öğrenci No, Kayıt Tarihi, Erteleme Tarihi, Durum**). Durum **İşlem Bekliyor** ya da **Ertelendi** olur.
- Bir öğrenciyi seçince iki düğme açılır:
  - **Seçili Öğrenciyi Ertele:** Kayıt uyarısı için **yeni bir tarih** seçersiniz ve **Ertelemeyi Kaydet**'e basarsınız.
  - **Seçili Kaydı Sil:** Kaydı siler. **Erteleme tarihi gelmeden kayıt silinemez**; sistem silmeyi reddeder. Silme **geri alınamaz** ve denetim kaydına yazılır; emin olmadan basmayın.

## 2.2 Faaliyet Kayıtları
Öğrencilerin yaptığı faaliyetlerin kaydı; **puanı** buradan hesaplanır.
- **＋ Yeni Faaliyet Ekle:** **Öğrenci Seç**, **Faaliyet Türü**, **Birim** (*Kişi, Saat* gibi) ve **Miktar**. Kaydın puanı = **Miktar × kaydın girildiği andaki faaliyet puanı**; faaliyet puanı sonradan değişse de eski kayıtlar değişmez.
- **✎ Faaliyet Düzenle** ve **🗑️ Faaliyet Sil**: Listeden kaydı seçip kullanın. İşlemler denetim kaydına yazılır.
- **📋 Faaliyet Türleri:** Yeni faaliyet türü tanımlar, puanını belirler, düzenler. **Aynı ad yeniden eklenemez; büyük/küçük harf farkı aynı ad sayılır.** Pasif bir faaliyet türüne kayıt girilemez ya da kayıt taşınamaz ("Aktif faaliyet türü bulunamadı."). Puanı değişen bir türün önceki/yeni puanı ve etkilenen kayıt sayısı denetim kaydına yazılır.
- Liste **en yeni 1000** kaydı gösterir; altındaki not toplam sayıyı söyler. Tümü için **Faaliyet Raporu**'nu kullanın.
- Birimleri yönetmek (**🏢 Faaliyet Birimleri**) yalnızca **Sistem Admin**'e açıktır.

## 2.3 Öğrenci ve faaliyet raporları
**Puan Raporu** (öğrenci başına toplam puan), **Öğrenci Raporu** (mevcut, tür/bölüm dağılımı, kayıt saklama süresi) ve **Faaliyet Raporu** (tür, birim, onay durumuna göre). Hepsinde dönem seçilir ve **⬇ Excel'e Aktar** vardır.

---

# 3. Danışma masası işleri

## 3.1 Danışma Masası Yönetimi
Danışma öğrencilerinin **görev kayıtlarını** yönetirsiniz. Liste, her görevin öğrencisini, başlangıç/bitişini, çalışma süresini ve **onay durumunu** gösterir; üstteki kartlarda tüm kayıtların sayıları (toplam, devam eden, onay bekleyen, onaylanan) vardır. Başlıklara tıklayarak listeyi sıralayabilirsiniz; sayfa kendini yenilediğinde seçtiğiniz sıralama ve seçili görev korunur. Çok sayıda kayıt varsa devam eden ve onay bekleyen görevlerin tümü ile en yeni görevler gösterilir; bunu listenin üstündeki not belirtir.
- **✓ Seçilen Görevi Onayla:** Biten bir görevi onaylar. **Devam eden** görev onaylanamaz; **zaten onaylanmış** görev tekrar onaylanamaz.
- **↶ Onayı Geri Al:** Onaylanmış bir görevin onayını kaldırır; görev yeniden "Onay Bekliyor" olur ve düzenlenebilir. Yanlışlıkla onayladıysanız ya da onaylanmış görevin saatlerini düzeltmeniz gerekiyorsa kullanın. İşlem denetim kaydına yazılır. (Görevler silinemez.)
- **＋ Yeni Görev Ekle:** Öğrencinin görevini elle girersiniz (**Öğrenci**, **Başlangıç**, **Bitiş**). Öğrenci listesinde yalnızca **danışma masası öğrencileri** bulunur. Öğrenci görevi başlatmayı/bitirmeyi unuttuysa bu yolla düzeltirsiniz. Aktif danışma masası öğrencisi yoksa sistem bunu söyler.
  **Bir görev en fazla 10 saat olabilir** (mesai süresi 08:00–18:00); daha uzun çalışmayı ayrı görevler olarak girin, aksi halde "Bir görev en fazla 10 saat olabilir" uyarısı çıkar.
- **✎ Seçilen Görevi Düzenle:** Başlangıç ve bitişi düzeltir (aynı 10 saat sınırı geçerlidir). Düzeltmede **önceki ve yeni saatler denetim kaydına** yazılır. **Onaylanmış** görev düzenlenemez; önce **Onayı Geri Al**'ı kullanın.
- **Uzun görev işareti:** Öğrenci görevi bitirmeyi unutmuşsa süre 10 saati aşar; listede böyle görevler işaretlenir ve üzerine gelince "öğrenci görevi bitirmeyi unutmuş olabilir; onaylamadan önce saatleri kontrol edin" ipucu çıkar. **Onaylamadan önce saatleri kontrol edip gerekirse Düzenle ile düzeltin.**
- Onay bekleyen görevler **🔔 bildirim** olarak da size gelir; bildirime tıklayınca ilgili sayfa açılır.

## 3.2 Danışma Masası Raporları
Dönem seçerek görev sürelerini ve öğrenci bazlı özetleri görürsünüz; **⬇ Excel'e Aktar** vardır.

---

# 4. Odalar

- **Oda Kullanımı:** Odaların saatlik doluluğu (randevu ve etkinlikler birlikte).
- **Oda Etkinlikleri:** Odalardaki etkinlikler; **Durum** ve **Dönem** süzgeçleri vardır. Yetkiniz varsa **＋ Yeni Etkinlik**, **Düzenle**, **İptal Et** ve **Oturumları Gör** düğmeleri görünür (çok günlü etkinliklerin her günü ayrı "oturum"dur).
- **Oda Yönetimi:** **＋ Yeni Oda Ekle**, **✎ Odayı Düzenle**, **✕ Odayı Pasife Al**. Pasife alınan oda yeni randevu ve rezervasyonlarda seçilemez; geçmiş kayıtlar korunur.

---

# 5. İpuçları

- Cihaz arızası bildirirken **Aciliyet**'i doğru seçin; **Kritik** arıza hemen takip edilmelidir.
- Günün sonunda **Bakım Planları**'ndaki **Gecikmiş** satırlara bakın.
- Bir cihazı rezerve etmeden önce **Cihaz Uygunluğu**'na bakın.
- Excel dosyalarında **öğrenci adı ve telefonu** bulunur; dosyayı yalnızca gerekli kişilerle paylaşın.
