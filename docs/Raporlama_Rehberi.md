# TKYS Raporlama Rehberi

Bu doküman, Terapi Kliniği Yönetim Sistemi'ndeki (TKYS) tüm raporları anlatır: hangi raporun ne gösterdiğini, kimlerin görebildiğini,
sayıların nasıl hesaplandığını, hangi verinin raporlara girmediğini ve raporların birbiriyle nasıl tutarlı tutulduğunu.
İlgili gereksinim: **FR-041** (Temel raporlar), FR-058 (Faaliyet puanları ve raporlama), FR-063 (Danışma masası raporları).

> Yetki bilgileri, sistemin varsayılan rol ve izin tanımlarından alınmıştır. Roller ve izinler "Rol & İzin Yönetimi" sayfasından
> değiştirilebilir; bu durumda raporları görebilen roller de değişir.

---

## 1. Genel bakış

| # | Rapor | Menüde nerede | Kimler görür (varsayılan) | Dönem | Çıktı |
|---|---|---|---|---|---|
| 1 | Randevu Raporları | Randevu & Oda | Takvimi görenler (psikolog yalnızca kendi randevularını görür) | Evet | Ekran + Excel |
| 2 | Oda Kullanım Raporu | Randevu & Oda | Admin, Müdür | Evet | Ekran + Excel |
| 3 | Puan Raporu | Öğrenci & Faaliyet | Admin, Müdür, Memur, Proje Asistanı | Evet | Ekran + Excel |
| 4 | Öğrenci Raporu | Öğrenci & Faaliyet | Admin, Müdür, Memur, Proje Asistanı | Hayır (güncel durum) | Ekran + Excel |
| 5 | Faaliyet Raporu | Öğrenci & Faaliyet | Admin, Müdür, Memur, Proje Asistanı | Evet | Ekran + Excel |
| 6 | Danışma Masası Raporları | Öğrenci & Faaliyet | Admin, Müdür, Memur | Evet | Ekran + Excel |
| 7 | Cihaz Raporları (sekmeler: Bakım Geçmişi, Kalibrasyon, Arızalar) | Cihaz | Admin, Müdür, Memur | Evet | Ekran + Excel |
| 8 | Cihaz Rezervasyon Raporu (Cihaz Raporları sayfasında sekme) | Cihaz | Admin, Müdür, Memur | Evet | Ekran + Excel |
| 9 | Geciken Bakım Planı Raporu (Cihaz Raporları sayfasında "Geciken Bakım Planları" sekmesi) | Cihaz | Admin, Müdür, Memur | Hayır (bugünkü durum) | Ekran + Excel |
| 10 | Yetki Raporu | Yönetim & Denetim | Admin, Müdür | Hayır (güncel durum) | Ekran + Excel |
| 11 | Audit Kayıtları | Yönetim & Denetim | Admin, Müdür | Evet | Ekran + Excel |
| 12 | Yönetim Raporları ve İstatistikler | Yönetim & Denetim | Admin, Müdür | Evet | Ekran + PDF |
| 13 | Ana Kontrol Paneli (Dashboard) | Ana sayfa | Giriş yapan herkes (bazı kartlar için ilgili izin gerekir) | Bugün | Ekran |

Yeni rapor sayfalarının hiçbiri yeni izin gerektirmez; mevcut izinler kullanılır. Menüde bir rapor, yalnızca o izne sahip kullanıcıya görünür;
sunucu da aynı izni her istekte ayrıca denetler (menüyü atlayarak doğrudan istek göndermek yetki sağlamaz).

## 2. Ortak özellikler

- **Süzgeçler kendiliğinden uygulanır.** Dönem, cihaz, oda gibi bir kutu değişince rapor yeniden yüklenir; ayrı bir "Getir" düğmesi yoktur.
- **Dönem seçenekleri** rapora göre değişir (örn. Bu Ay, Geçen Ay, Son 3 Ay, Bu Yıl, Geçen Yıl, Tarih Aralığı). Yeni raporlarda ve Yönetim
  Raporları'nda tek seferde **en fazla 366 gün** seçilebilir. Ters tarih aralığı ve fazla uzun aralık uyarıyla reddedilir.
- **Excel çıktısı:** her raporun Excel dosyası bir **Özet** sayfasıyla başlar (rapor bilgileri, süzgeçler, genel özet ve "sayfa rehberi") ve ardından
  tablo sayfalarını içerir. Metin hücreleri formül olarak yorumlanmaz (formül enjeksiyonuna karşı korumalıdır). Excel açıkken aynı adlı dosyaya
  kaydedilirse kullanıcıya anlaşılır bir uyarı gösterilir.
- **Süzgece uygun veri:** ekrandaki sayılar ile Excel'deki sayılar aynı sunucu verisinden gelir.
- **Gizlilik:** bölüm 6'ya bakın.

## 3. Raporların ayrıntısı

### 3.1 Randevu Raporları
- **Ne gösterir:** seçilen dönemde (randevunun başlangıç günü) durum sayıları (planlı, tamamlanan, gelmedi, iptal), psikolog bazlı döküm, iptal nedenleri,
  görüşme tipi, terapi türü ve yaş grubu dağılımı.
- **Süzgeçler:** dönem (Tümü dahil), psikolog, oda. Psikolog rolündeki kullanıcı yalnızca kendi randevularını raporlar (sunucu uygular).
- **Excel sayfaları:** Özet, Psikolog Bazlı, Dağılımlar, Randevu Detayı.
- **Veri kaynağı:** `randevular`, `danisan_kodlari`, `odalar`.
- **Tanımlar:** bölüm 4.1.

### 3.2 Oda Kullanım Raporu
- **Ne gösterir:** oda bazlı randevu, cihaz rezervasyonu ve oda etkinliği saatleri; toplam saat; mesai doluluk oranı; hiç kullanılmayan odalar;
  haftanın günlerine göre dağılım.
- **Süzgeçler:** dönem, oda.
- **Excel sayfaları:** Özet, Oda Bazlı, Gün Dağılımı, Kullanım Kayıtları (danışan bilgisi içermez).
- **Veri kaynağı:** `randevular`, `cihaz_rezervasyonlari` (odası seçilenler), `oda_etkinlikleri`, `odalar`.
- **Tanımlar:** bölüm 4.2.

### 3.3 Puan Raporu
- **Ne gösterir:** öğrencilerin seçilen dönemdeki toplam faaliyet puanına göre sıralaması.
- **Süzgeçler:** dönem, öğrenci türü, öğrenci durumu, "puanı olmayanları göster".
- **Excel sayfaları:** Özet, Puan Sıralaması, Faaliyet Dağılımı, Faaliyet Detayı.
- **Veri kaynağı:** `ogrenciler`, `ogrenci_faaliyet_takip`, `faaliyetler`.

### 3.4 Öğrenci Raporu
- **Ne gösterir:** öğrenci mevcudu (aktif/pasif), öğrenci türüne ve bölüme göre dağılım, son 30 günde yeni kayıtlar, **Gönüllü öğrenci kayıt saklama süresi**
  (süresi dolmuş, ertelenen, 12 ay içinde dolacak) ve son 90 günde faaliyeti olmayan aktif öğrenciler.
- **Süzgeçler:** öğrenci türü, durum. Dönemsizdir; güncel durumu gösterir.
- **Excel sayfaları:** Özet, Öğrenci Listesi, Tür Dağılımı, Bölüm Dağılımı, Saklama Süresi.
- **Not:** rapor kayıt saklama süresini yalnızca listeler; kayıtları silmez. Silme işlemi ayrı ve onaylı bir süreçtir (bkz. 6).

### 3.5 Faaliyet Raporu
- **Ne gösterir:** dönemdeki faaliyet kayıtları: faaliyet türü, birim ve öğrenci türüne göre dağılım; toplam, onaylı ve onay bekleyen puanlar; onay bekleyen
  kayıtların listesi ve en eski bekleyen kaydın yaşı.
- **Süzgeçler:** dönem (faaliyet tarihi), faaliyet türü, onay durumu.
- **Excel sayfaları:** Özet, Faaliyet Türü, Birim, Öğrenci Türü, Onay Bekleyenler, Faaliyet Detayı.

### 3.6 Danışma Masası Raporları
- **Ne gösterir:** danışma masası görevleri: toplam, devam eden, tamamlanan, onay bekleyen ve onaylanan görev sayıları ile çalışma süreleri; öğrenci bazlı özet.
- **Süzgeçler:** dönem (Tümü, Bugün, Bu Hafta, Geçen Hafta, Tarih Aralığı), öğrenci.
- **Excel sayfaları:** Özet, Görev Kayıtları, Öğrenci Bazlı.

### 3.7 Cihaz Raporları
- **Ne gösterir:** bakım, kalibrasyon ve arıza kayıtları; cihazların güncel durumu; kalibrasyon geçerliliği ve planlı bakım tarihi.
- **Süzgeçler:** dönem (Tümü, Bugün, Bu Hafta, Bu Ay, Tarih Aralığı), cihaz.
- **Excel sayfaları:** Özet, Durum Raporu, Cihaz Özeti, Bakım Geçmişi, Kalibrasyon, Arızalar.

### 3.8 Cihaz Rezervasyon Raporu
- **Ne gösterir:** cihaz, proje türü ve bölüm bazlı rezervasyon sayısı ve planlanan kullanım saati; iptaller ayrıca; hiç kullanılmayan cihazlar.
- **Süzgeçler:** dönem, cihaz.
- **Excel sayfaları:** Özet, Cihaz Bazlı, Proje Türü, Bölüm, Rezervasyon Detayı.
- **Tanımlar:** bölüm 4.2.

### 3.9 Geciken Bakım Planı Raporu
- **Ne gösterir:** bugünkü durumda geciken ve yaklaşan bakım/kalibrasyon planları, her planın son yapılan bakım/kalibrasyon tarihi, cihaz ve plan türüne göre
  özet, **aktif planı olmayan cihazlar**.
- **Süzgeçler:** cihaz, plan türü (bakım/kalibrasyon), durum (gecikmiş, yaklaşıyor, planlı, pasif).
- **Excel sayfaları:** Özet, Geciken Planlar, Yaklaşan Planlar, Tüm Planlar, Cihaz Bazlı, Planı Olmayan Cihazlar.
- **Tanımlar:** bölüm 4.4.

### 3.10 Yetki Raporu
- **Ne gösterir:** kullanıcılar, rolleri, son giriş zamanları, kilitli hesaplar, hiç giriş yapmamış aktif hesaplar, geçici parolalı hesaplar, son 30 gündeki
  başarısız giriş sayısı ve rollere göre izin sayıları.
- **Süzgeçler:** rol, durum (aktif/pasif). Dönemsizdir.
- **Excel sayfaları:** Özet, Kullanıcılar, Roller, **Rol-İzin Matrisi** (hangi rol hangi izne sahip).
- **Not:** parola ve parola özeti raporlarda hiçbir yerde yer almaz.

### 3.11 Audit Kayıtları
- **Ne gösterir:** sistemde yapılan işlemlerin değiştirilemez izi: giriş, başarısız giriş, oluşturma, güncelleme, silme, iptal, rol değişikliği vb.
  Silme kayıtlarında **silinen verinin içeriği** de saklanır ("Silinen Veri").
- **Süzgeçler:** kullanıcı, işlem türü, dönem. **Excel'e aktar:** süzgece uyan kayıtlar, en çok 20.000 kayıt.
- **Excel sayfaları:** Özet, Denetim Kayıtları, Silmeler.

### 3.12 Yönetim Raporları ve İstatistikler
Merkez yöneticisi için dönemsel özet panelidir. Seçilen dönem, aynı uzunluktaki önceki dönemle karşılaştırılır. **PDF** olarak kaydedilebilir.

| Görünüm | İçerik |
|---|---|
| Genel Bakış | Randevu, bakım, kalibrasyon, arıza, rezervasyon, etkinlik ve öğrenci faaliyeti özeti |
| Randevular | Durum sayıları, günlük eğilim, oda kullanımı |
| Cihazlar | Bakım/kalibrasyon/arıza/rezervasyon sayıları, cihaz kullanımı |
| Öğrenciler | Faaliyet türüne göre puanlar, onaylı puan |
| Proje / Deney | Proje türü rezervasyonları ve oda etkinlikleri (rezervasyon, tamamlanmış deney demek değildir) |
| Oda Kullanımı | Oda Kullanım Raporu'nun özeti |
| Cihaz Kullanımı | Cihaz Rezervasyon Raporu'nun özeti |
| Yetkiler | Yetki Raporu'nun özeti (dönemden bağımsız) |
| Öğrenci Mevcudu | Öğrenci Raporu'nun özeti |
| Faaliyet Onayları | Faaliyet Raporu'nun özeti |
| Bakım Gecikmeleri | Geciken Bakım Planı Raporu'nun özeti |
| Bugün Merkezde | Seçilen günün zamanlı olayları ve günlük özeti |

Oda Kullanımı, Cihaz Kullanımı, Yetkiler, Öğrenci Mevcudu, Faaliyet Onayları ve Bakım Gecikmeleri görünümleri, ayrıntılı sayfalarla **aynı uç
noktalardan** beslenir; bu yüzden sayılar birebir aynıdır. Bu görünümlerin verisi başka bir izin gerektiriyorsa (örn. yönetici olup denetim izni
olmayan bir rol) yalnızca o görünümde "Bu rapor alınamadı" yazar, diğer görünümler çalışmaya devam eder.

### 3.13 Ana Kontrol Paneli
Bugünkü randevular, cihaz durum sayıları, açık arıza sayısı ve bugünkü rezervasyonlar. Cihaz durumunda bugün bakım veya kalibrasyon aralığında olan cihaz,
kayıt cihaz durumunu değiştirmemiş olsa bile "bakımda/kalibrasyonda" sayılır.

## 4. Hesaplama tanımları

### 4.1 Randevu
- **Dönem:** randevunun başlangıç günü seçilen aralıktaysa randevu o döneme aittir.
- **Tamamlanma oranı** = Tamamlandı / (Tamamlandı + Gelmedi). **Gelmeme oranı** = Gelmedi / (Tamamlandı + Gelmedi). Planlı (henüz yapılmamış) ve iptal edilen
  randevular oranlara girmez.
- **Görüşme tipi, terapi türü, yaş grubu dağılımı** iptal edilmeyen randevular üzerindendir. **İptal nedenleri** yalnızca iptal edilenler üzerindendir; nedeni
  kaydedilmemiş eski iptaller ayrı satırda görünür.

### 4.2 Oda ve cihaz kullanımı
- **Saatler planlanan süreyi gösterir**, gerçekleşen kullanım süresi ayrıca ölçülmez.
- **Dönem sınırlarına kırpılır:** dönemi aşan bir rezervasyon yalnızca dönem içindeki kısmı kadar sayılır (örn. 28 Şubat 23:00 – 1 Mart 02:00 rezervasyonu Mart raporunda
  2 saattir).
- **İptal edilen** randevu, rezervasyon ve etkinlikler kullanım sayılmaz; cihaz raporunda iptaller ayrıca gösterilir.
- **Oda toplamı** = randevu + (odası seçilmiş) cihaz rezervasyonu + oda etkinliği saatleri.
- **Mesai doluluk oranı** = toplam saat / (hafta içi gün sayısı × günlük 8 saat). Bu bir **varsayımdır** ve raporda belirtilir: normal çalışma günü 8 saat sayılır.
  Sistem istisnai durumlar için 08:00-18:00 arasındaki (10 saatlik) bir pencerede de kayıt kabul eder (cihaz rezervasyonu, oda etkinliği); bu yüzden
  günde 8 saatten fazla kullanım ya da hafta sonu kullanımı oranı **%100'ün üzerine çıkarabilir**. Bu bir hata değil, istisna kullanımının göstergesidir.

### 4.3 Öğrenci ve faaliyet
- **Puan** = adet × kaydın girildiği andaki faaliyet puanı. Faaliyetin puanı sonradan değişse bile eski kayıtların puanı, yöneticinin açıkça "geçmişi güncelle" demesi
  dışında değişmez. Puan Raporu, Faaliyet Raporu ve Yönetim Raporları aynı hesabı kullanır.
- **Sıralama** eşit puanlılarda aynı sırayı verir (1, 2, 2, 4); puanı olmayanın sırası yoktur. Pasif öğrenciler listede kalır.
- **Onaylı / onay bekleyen:** kaydın onay durumuna göredir. Toplam puana onay bekleyen kayıtlar da dahildir; onaylı puan ayrıca gösterilir.
- **Saklama süresi:** yalnızca **Gönüllü öğrenciler** için, kayıt tarihinden itibaren **10 yıl**. Süresi dolan ama ileri bir tarihe ertelenmiş kayıt "Ertelendi",
  önümüzdeki 12 ay içinde dolacak kayıt "12 ay içinde dolacak" olarak gösterilir.
- **Faaliyetsiz aktif öğrenci:** aktif olup son 90 günde (ya da hiç) faaliyet kaydı olmayan öğrenci.
- **Yeni kayıt:** son 30 günde kaydedilen öğrenci.
- **Danışma masası çalışma süresi:** yalnızca tamamlanan görevlerin kesinleşmiş süresi toplanır; devam eden görevin süresi toplama girmez.

### 4.4 Bakım planı
- **Gecikmiş:** aktif planın sonraki görev tarihi bugünden önceyse. **Yaklaşıyor:** gecikmemiş ve kalan gün, planın uyarı süresi içindeyse. **Planlı:** diğer aktif planlar.
  **Pasif** planlar gecikmiş sayılmaz. Bu kural Bakım Planları ekranındaki durumla aynıdır.
- **Gecikme (gün)** = bugün − planlanan tarih. **Gecikme oranı** = geciken plan / aktif plan.
- **Son yapılan:** plana bağlı en son bakım ya da kalibrasyon kaydının tarihi. Plana bağlanmamış eski kayıtlar bu sütunda görünmez.
- **Planı olmayan cihaz:** aktif planı bulunmayan, kullanım dışı olmayan cihaz.
- **Kalibrasyon planı:** görev türü "Kalibrasyon" ile başlayan plandır; diğerleri bakım planıdır.

### 4.5 Cihaz raporları
- Kalibrasyon, **kaydın girildiği güne değil kalibrasyonun gerçek başlangıç gününe** göre döneme sayılır (eski kayıtlarda tarih boşsa işlem tarihi kullanılır).
  Yönetim Raporları'ndaki kalibrasyon sayısı da aynı kuralı kullanır.
- Arıza kaydı, bildirim ya da çözüm tarihi dönem içindeyse dönem raporuna girer.

### 4.6 Yetki
- **Son giriş:** kullanıcının en son başarılı giriş kaydı. **Hiç giriş yapmamış:** aktif olup hiç giriş kaydı olmayan hesap. **Kilitli:** hatalı girişler nedeniyle
  şu an geçici olarak kilitli hesap. **Başarısız giriş (30 gün):** tüm sistemdeki son 30 günlük başarısız giriş denemeleri.

## 5. Raporlar arası tutarlılık

Aynı bilgi farklı raporlarda farklı sayı vermemelidir. Aşağıdaki eşleşmeler, gerçek PostgreSQL üzerinde çalışan otomatik testlerle doğrulanır
(`tests/integration/test_rapor_tutarliligi_pg_quality.py`):

| Kontrol | Eşleşen raporlar |
|---|---|
| Randevu durum sayıları | Randevu Raporları = Yönetim Raporları (Randevular) |
| Kalibrasyon sayısı | Cihaz Raporları = Yönetim Raporları (Cihazlar) |
| İptal edilen rezervasyonlar sayılmaz | Yönetim Raporları (Cihazlar) = Proje/Deney = Cihaz Rezervasyon Raporu |
| Toplam puan | Puan Raporu = Faaliyet Raporu = Yönetim Raporları (Öğrenciler) |
| Oda toplam kullanım saati | Oda Kullanım Raporu = Yönetim Raporları kullanım özeti |
| Bakım planı durumu | Geciken Bakım Planı Raporu = Bakım Planları ekranı |

## 6. Kişisel veri ve güvenlik

- **Danışanlar yalnızca kodla** görünür; hiçbir raporda ad, telefon gibi kişisel bilgi yoktur (FR-008). Randevu iptal notu (serbest metin) rapora konmaz.
- **Öğrenci Raporu** ad, soyad ve öğrenci numarası içerir ancak **telefon içermez**. Puan, Faaliyet ve Danışma Masası raporlarında öğrenci adı ve numarası yalnızca
  yetkili rollere görünür.
- **Yetki Raporu** parola ya da parola özeti içermez.
- **Audit kayıtları** sonradan değiştirilemez (veritabanı tetikleyicisiyle korunur). Kalıcı silmelerde silinen verinin içeriği denetim kaydına yazılır; ancak
  10 yıllık süre dolumuyla yapılan **öğrenci silmesinde ad, telefon ve öğrenci numarası denetime yazılmaz** (yalnızca kimliksiz alanlar kaydedilir).
- **Yetki sunucuda uygulanır.** Menüde görünmeyen bir rapora doğrudan istek göndermek de reddedilir. Psikolog, randevu raporunda yalnızca kendi randevularını görür.
- Giriş güvenliği (rapor değil ama denetim izine yansır): aynı hesapta art arda hatalı girişte geçici kilit ve aynı bilgisayardan çok sayıda hatalı girişte geçici engel.

## 7. Bilinen sınırlar ve varsayımlar

- Oda ve cihaz kullanım saatleri **planlanan süredir**; gerçekleşen kullanım süresi ölçülmez.
- Mesai doluluk oranı **hafta içi günlük 8 saat** varsayımına dayanır (merkezin kararıdır, kodda sabit değerdir: `GUNLUK_MESAI_SAATI`). Psikolog randevuları ise 09:00-15:00 arasında saat başı, 1 saatliktir.
- **PDF** çıktısı yalnızca Yönetim Raporları'ndadır; diğer raporlar Excel olarak alınır.
- Excel detay sayfaları kayıt sayısıyla sınırlıdır (rezervasyon ve faaliyet detayı en çok 5.000 kayıt, audit en çok 20.000 kayıt, onay bekleyen listesi ilk 20).
- **Danışan bazlı devam raporu yoktur.** Danışan tarafı gizlilik açısından hassas olduğundan, ihtiyaç doğarsa yalnızca toplam sayılarla ve küçük gruplarda gizleme kuralıyla
  eklenmesi önerilir.
- Randevu Raporları, takvimi görebilen her role açıktır (Danışma öğrencisi ve Proje asistanı dahil). Psikolog dışındaki roller tüm randevuların toplamını görür.
  Bu davranış mevcut izin tanımından gelir; kısıtlanması isteniyorsa izin tanımı değiştirilmelidir.
- Rapor çıktıları sistemdeki veriyi yansıtır; veri girişindeki eksiklikler (örn. bölümü girilmemiş öğrenci, nedeni kaydedilmemiş iptal) "Belirtilmemiş" olarak görünür.

## 8. Varsayılan yetki matrisi

Raporu görmek için gereken izin ve bu izne varsayılan olarak sahip roller:

| Rapor | Gerekli izin | Admin | Müdür | Memur | Psikolog | Proje Asistanı | Danışma Öğrencisi |
|---|---|:-:|:-:|:-:|:-:|:-:|:-:|
| Randevu Raporları | Randevu takvimini görüntüleme | ✔ | ✔ | ✔ | ✔ (yalnızca kendi) | ✔ | ✔ |
| Puan / Öğrenci / Faaliyet Raporu | Faaliyet kayıtlarını düzenleme | ✔ | ✔ | ✔ | – | ✔ | – |
| Danışma Masası Raporları | Danışma masası raporlarını görüntüleme | ✔ | ✔ | ✔ | – | – | – |
| Cihaz Raporları (Cihaz Rezervasyonu ve Geciken Bakım Planları sekmeleri dahil) | Cihaz raporlarını görüntüleme | ✔ | ✔ | ✔ | – | – | – |
| Oda Kullanım Raporu, Yönetim Raporları ve İstatistikler | Yönetim raporlarını görüntüleme | ✔ | ✔ | – | – | – | – |
| Yetki Raporu, Audit Kayıtları | Audit kayıtlarını inceleme | ✔ | ✔ | – | – | – | – |

## 9. Teknik ek: uç noktalar ve ilgili dosyalar

| Rapor | API | Ekran | Excel/PDF |
|---|---|---|---|
| Randevu Raporları | `GET /api/randevu-raporu` | `client/randevu_raporlari_ekrani.py` | `client/randevu_rapor_excel.py` |
| Oda Kullanım Raporu | `GET /api/oda-kullanim-raporu` | `client/oda_kullanim_raporu_ekrani.py` | `client/rapor_excel_genel.py` |
| Puan Raporu | `GET /api/puan-raporu` | `client/puan_raporu_ekrani.py` | `client/puan_rapor_excel.py` |
| Öğrenci Raporu | `GET /api/ogrenci-raporu` | `client/ogrenci_raporu_ekrani.py` | `client/rapor_excel_genel.py` |
| Faaliyet Raporu | `GET /api/faaliyet-raporu` | `client/faaliyet_raporu_ekrani.py` | `client/rapor_excel_genel.py` |
| Danışma Masası Raporları | `GET /api/danisma/raporlar` | `client/danisma_masasi_raporlari.py` | `client/danisma_rapor_excel.py` |
| Cihaz Raporları | `GET /api/cihaz-raporlari` | `client/cihaz_raporlari_ekrani.py` | `client/rapor_excel.py` |
| Cihaz Rezervasyon Raporu | `GET /api/cihaz-rezervasyon-raporu` | `client/cihaz_rezervasyon_raporu_ekrani.py` | `client/rapor_excel_genel.py` |
| Geciken Bakım Planı Raporu | `GET /api/bakim-plani-raporu` | `client/bakim_plani_raporu_ekrani.py` | `client/rapor_excel_genel.py` |
| Yetki Raporu | `GET /api/yetki-raporu` | `client/yetki_raporu_ekrani.py` | `client/rapor_excel_genel.py` |
| Audit Kayıtları | `GET /api/audit-kayitlari` | `client/audit_kayitlari_ekrani.py` | `client/audit_excel.py` |
| Yönetim Raporları | `GET /api/yonetim-raporlari/*` (randevu-ozet, cihaz-ozet, ogrenci-ozet, proje-etkinlik-ozet, kullanim-ozet, bugun-merkezde, gunluk-detay) ve yukarıdaki ayrıntılı rapor uçları | `client/yonetim_raporlari_panel.py` | `client/yonetim_raporlari_pdf.py` |

Hesaplamalar: `server/rapor_kullanim.py` (oda/cihaz kullanımı, yetki), `server/rapor_ogrenci_faaliyet.py` (öğrenci, faaliyet), `server/rapor_bakim_plani.py` (bakım planı),
`server/randevu_rapor_hesapla.py` (randevu). Ortak ekran tabanı: `client/rapor_sayfasi_taban.py`.

Testler: `tests/unit/test_rapor_sayfalari.py`, `test_rapor_ogrenci_faaliyet.py`, `test_rapor_bakim_plani.py`, `test_rapor_kullanim_tablolari.py` ve gerçek PostgreSQL üzerinde
`tests/integration/test_rapor_tutarliligi_pg_quality.py`.

## 10. Sürüm notu

| Tarih | Değişiklik |
|---|---|
| 19.11.2026 | İlk sürüm. Oda Kullanım, Cihaz Rezervasyon, Yetki, Öğrenci, Faaliyet ve Geciken Bakım Planı raporları, Audit Excel çıktısı ve Yönetim Raporları'nın yeni görünümleri eklendi; rapor tutarsızlıkları düzeltildi. |
