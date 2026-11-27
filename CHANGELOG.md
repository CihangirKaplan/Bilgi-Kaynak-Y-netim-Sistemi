# Değişiklik Günlüğü (CHANGELOG)

Bu dosya TKYS'nin sürümler arasındaki önemli değişikliklerini listeler. Ayrıntılar ilgili Pull Request'lerdedir (GitHub, `develop` dalı).
Biçim: [Keep a Changelog](https://keepachangelog.com/tr/1.1.0/). Sürüm numaraları [Anlamsal Sürümleme](https://semver.org/lang/tr/) kuralına uyar.

## [1.0.0] — Yayın tarihi: GO/NO-GO kararından sonra yazılacak

İlk kararlı sürüm. 21 Eylül – 24 Kasım 2026 arasında, 8 haftalık yol haritasıyla geliştirildi (yaklaşık 500 Pull Request).
Mimari: PySide6 masaüstü istemci → REST (FastAPI) → PostgreSQL. Veritabanı şeması Alembic migration'larıyla yönetilir.

### Kimlik doğrulama ve oturum

- Kullanıcı adı ve parolayla giriş; parolalar bcrypt ile saklanır. Kullanıcı adı büyük/küçük harf duyarsız.
- JWT tabanlı oturum (varsayılan 45 dakika); süresi dolan ya da geçersiz oturumda istemci giriş ekranına döner.
- Çıkışta oturum anahtarı iptal edilir; parola değişince ya da sıfırlanınca eski oturumlar geçersiz olur.
- İlk girişte ve geçici parolayla girişte zorunlu şifre değiştirme; parola politikası ve canlı kural listesi.
- Hesap kilidi (5 hatada 1 dk, 10 hatada 15 dk) ve istemci (IP) bazlı deneme sınırı; şifre değiştirmede de aynı sınır.
- "Şifremi unuttum": giriş ekranından parola sıfırlama talebi; yönetici bildirimden görüp geçici parola (48 saat geçerli) verir.
- Yönetici parolası uygulamadan sıfırlanamaz; sunucudaki kurtarma aracıyla ve ek yönetici oluşturma seçeneğiyle yönetilir.

### Yetkilendirme (RBAC)

- Roller: Yönetici (ADMIN), Müdür, Memur, Psikolog, Danışma Öğrencisi, Proje Asistanı; özel rol eklenebilir.
- İzin tabanlı erişim: her API ucu bir izinle korunur; menüler sunucudan gelen yetkilere göre oluşur ve oturum açıkken yenilenir.
- Rol & İzin Yönetimi ekranı: rol oluşturma/düzenleme/pasife alma, izin matrisi, izin ön koşulu uyarıları.
- Rol hiyerarşisi: kullanıcı kendi seviyesindeki ya da üstündeki rolü yönetemez (kullanıcı ve personel işlemlerinde).

### Kullanıcı ve personel

- Kullanıcı ve personel kaydı tek işlemde, tek tabloda; personel kodu role göre otomatik üretilir.
- Kullanıcı pasifleştirme/aktifleştirme, rol değiştirme (psikolog için oda ve danışan kuralları), parola sıfırlama.

### Randevu

- Randevu oluşturma, düzenleme, iptal (nedeniyle); Tamamlandı / Gelmedi durumları.
- Psikolog ve oda çakışması veritabanı düzeyinde engellenir; formda dolu saatler soluk ve seçilemez.
- Saat kuralı (saat başı 09:00–15:00, her randevu 1 saat; ekranla sunucu aynı kuralı uygular), hafta sonu ve geçmiş tarih kuralları; psikolog yalnızca kendi randevularını yönetir.
- Danışan kodları (yıl bazlı), danışan yaş grubu, terapi türü ve görüşme tipi; Danışanlar sayfası.
- Randevu Raporları sayfası ve dört sayfalı Excel çıktısı.

### Oda ve oda etkinlikleri

- Oda yönetimi; psikolog oda yetkileri (her psikologun en az bir odası).
- Oda Kullanımı: gün/hafta görünümü, randevu, cihaz rezervasyonu ve etkinlik blokları, mesai doluluk oranı.
- Oda Etkinlikleri: tek ya da çok günlü etkinlikler, çakışma denetimi, katılımcı sayısı (bilgi amaçlıdır; oda kapasitesiyle karşılaştırılmaz).
  Proje Asistanı da etkinlikleri görüntüleyip ekleyebilir, düzenleyebilir ve iptal edebilir (varsayılan izin; migration `a7c3e5b9d014`, yükseltmede otomatik gelir).

### Cihaz yaşam döngüsü

- Cihaz envanteri (envanter kodu, durum, oda), cihaz geçmişi zaman çizgisi.
- Cihaz rezervasyonu: çakışma, mesai ve sahiplik kuralları; düzenleme ve iptal; arızalı/bakımdaki cihaz rezerve edilemez.
- Cihaz Uygunluğu: haftalık takvim, gün detayı, müsait cihaz bulma.
- Bakım ve kalibrasyon kayıtları ve planları (periyot, uyarı süresi, geciken plan bildirimleri).
- Arıza bildirimi, çözüm notu ve yeniden açma. Cihazın **Arızalı** durumu tek kaynaktan, çözülmemiş arıza kaydından türetilir (elle seçilemez;
  Envanter, Uygunluk, Rezervasyon ve panel aynı sonucu gösterir). Mevcut tutarsız kayıtlar bir migration ile düzeltilir (aşağıdaki yükseltme notuna bakın).
- Bakım Planları'nda **▶** ile plandan tek tıkla bakım/kalibrasyon kaydı açma (cihaz ve plan seçili gelir, kayıt eklenince plan ilerler);
  Arıza Kayıtları'nda **◷** ile arızanın cihazının geçmişine geçiş.
- Bakım, Kalibrasyon, Arıza ve Rezervasyon listeleri en yeni 300 kayıtla açılır; **＋ 300 kayıt daha yükle** ile en çok 5000 kayda kadar uzatılır
  (5000 kayıtlı denemede ekran açılışı 12–99 saniyeden 1 saniyenin altına indi). Arama yüklü kayıtlarda çalışır.
- Ana panelde **bugünkü cihaz rezervasyonları** artık Cihaz Uygunluğu'nu görenlere ve rezervasyon yapanlara da gösterilir (rezerve eden adı yalnızca
  cihazı yönetenlere ve rezervasyon yapanlara; yalnızca görüntüleyenlere kişi adı verilmez).
- Ana panelde **bugünkü oda etkinlikleri** (saat, ad, oda, katılımcı sayısı) giriş yapmış herkese gösterilir (salt okunur); iptal edilenler listelenmez,
  organize eden adı verilmez.
- Ana panel: **Bugün | Yarın | Bu hafta** seçici (randevu, rezervasyon, etkinlik); **🙋 Benim Günüm** (kişinin kendi bugünkü/yarınki randevu ve cihaz
  rezervasyonları); **📢 Duyurular** (herkes okur; yayınlama/kaldırma yeni `DUYURU_YONET` izniyle, varsayılan Danışma Öğrencisi dışında herkes (migration `e5b9c1d7f302`); denetim kaydı tutulur). Duyuru **Okudum** düğmesiyle kullanıcı başına gizlenir (silinmez, diğerlerinde kalır; **Okunan duyurular** bölümünden geri getirilir); zilde yalnızca okunmamışlar görünür ve zilden de okundu işaretlenebilir (migration `f6c2d8a4b715`).
  Duyurular ve Benim Günüm kutuları boş olsa da görünür (boşken kısa bir açıklama yazar; sunucudan alınamazsa "yüklenemedi" yazar).
- Ana panel **Benim Günüm**: yetkiye göre "Bekleyen işlerim" satırları (devam eden danışma masası görevi, onay bekleyen danışma masası oturumları, açık cihaz arızaları); bekleyen yoksa görünmez.
  🔔 zil artık her rolde kişisel günlük bilgi ve okunmamış duyuruları da gösterir.
- Rezervasyon listesinde Rezerve eden sütunu ve satırda düzenle/iptal düğmeleri; arıza tarihleri gün.ay.yıl biçiminde; Raporlar'da
  "Tümü" döneminde tarih kutuları pasif. Bakım, Uygunluk, Rezervasyon ve Raporlar ekranları 1366 px'lik dizüstü ekranlarına sığar.
- Cihaz raporları (rezervasyon, geciken bakım planı) ve Excel aktarımı.
- **Dışa aktarma:** tüm rapor ve liste sayfalarında **⬇ Dışa Aktar** düğmesi; önce "Hangi türde kaydetmek istersiniz?" sorulur (Excel .xlsx ya da PDF), sonra
  dosya yeri seçilir. PDF: A4 yatay, sayfa numaralı, her sayfada tablo başlığı; tablo sayfası başına ilk 3000 satır (uzun listeler için Excel). Liste aktarımları
  denetim kaydına dosya türüyle (Excel/PDF) yazılır.
- **Rapor çıktıları:** özet satırlarında sayılar birimiyle görünür ("13 cihaz", "18 kayıt", "14.101,50 ₺", "6,1 gün", "97,33 saat"); hücre yine sayıdır (Excel'de toplanabilir).
  Liste boşken "Yok" tekrarı yazılmaz; PDF yüksek çözünürlükte (eşit harf aralığı), başlık şeritli, bölüm başlığı altındaki içerikle birlikte ve satırlar sayfa sonunda
  bölünmeden yerleşir, tablo başlığı her sayfada tekrarlanır. Excel dosyaları A4 yatay, sayfaya sığdırılmış, altbilgide sayfa numarasıyla yazdırılır.
- **🔔 Zil bildirimleri:** süresi dolan öğrenci kayıtları, sonucu girilmemiş randevular ve yedek uyarısı.
- Oda Yönetimi: kullanılmamış odayı uyarıyla veritabanından kalıcı silme.

### Öğrenci, faaliyet ve danışma masası

- Öğrenci yönetimi (gönüllü, asistan, danışma masası), aktiflik, on yıllık kayıt silme ve erteleme.
- Faaliyet türleri ve birimleri; faaliyet kayıtları; puan raporu ve Excel aktarımı.
- Danışma masası: öğrencinin görev başlatma/bitirme, yönetici onayı, elle görev ekleme/düzenleme (en fazla 10 saat),
  uzun görev uyarısı, onay bildirimleri, raporlar ve Excel aktarımı.

### Panel, bildirimler ve raporlar

- Ana panel: tıklanabilir özet kartları, bugünkü randevular, yaklaşan işlemler, günlük akış.
- Bildirim merkezi (bakım/kalibrasyon, parola talepleri, onay bekleyen görevler).
- Yönetim Raporları: dönem karşılaştırması (önceki dönem kuralıyla), grafikler (sütun/çizgi/pasta), PDF/Excel;
  Bugün Merkezde, öğrenci, faaliyet, oda ve cihaz kullanım raporları.
- Liste sayfalarında Excel aktarımı ve sütun sıralama.

### Denetim (audit)

- Giriş, başarısız giriş, oluşturma, güncelleme, silme, iptal, rol ve cihaz durumu değişiklikleri denetim kaydına yazılır;
  istemci adresi, silinen veri ve önceki/yeni değerler dahil.
- Denetim kayıtları veritabanı tetikleyicileriyle değiştirilemez ve silinemez.
- Denetim Kayıtları ekranı: süzgeçler, ayrıntı penceresi, Excel aktarımı.

### Güvenlik

- Merkezi girdi koruması: NUL karakteri, taşan sayı ve 1 MiB üstü gövde reddedilir (içerik türüyle atlatılamaz).
- Hata yanıtlarında iç ayrıntı (SQL, iz, dosya yolu) gösterilmez; asıl neden sunucu günlüğüne yazılır.
- Depoda gizli bilgi yok; JWT anahtarı en az 32 karakter olmadan sunucu açılmaz; API dokümantasyon sayfaları varsayılan kapalı.
- İsteğe bağlı HTTPS (TLS) kurulum rehberi; sunucu kısıtlı yetkili veritabanı kullanıcısıyla çalışabilir.

### Yedekleme ve kurulum

- PostgreSQL yedekleme (tarih damgalı), günlük otomatik yedek (Windows Görev Zamanlayıcı, 05.00), 14 günlük temizlik
  (en yeni 3 yedek her zaman korunur), yeni veritabanına geri yükleme ve kayıt sayısı doğrulaması.
- Sunucunun Windows açılışında kendiliğinden başlaması; süre sınırı olmadan ve kapanırsa yeniden başlatılarak.
- Sistem Durumu sayfası (sürüm, şema, son yedek); veritabanı şeması uyumsuzsa anlaşılır uyarı ve doğrulama aracı.
- İlk yönetici oluşturma, kısıtlı veritabanı kullanıcısı ve personel/kullanıcı geçiş araçları.

### Performans ve ölçeklenme

- Yetki Raporu'nun "son giriş" sorgusu için denetim tablosunda kısmi indeks (`ix_denetim_login_kullanici_tarih`); 1 milyon denetim kaydında rapor 3,5 sn → 50 ms. Yeni migration: `d4a8b6c2e913` (`alembic upgrade head`).
- Danışanlar ekranı tüm randevu geçmişini tek istekte çekmez: danışan başına randevu sayısı hafif bir uçtan (`/api/danisan-randevu-sayilari`) gelir, geçmiş danışan seçilince yalnızca o danışan için istenir (10 yıllık veride 47,7 MB / 5 sn → 216 KB / 92 ms). Süzgeçsiz `/api/randevular` en yeni 5000 kayıtla sınırlıdır; `X-Toplam-Kayit` başlığı gerçek toplamı bildirir.
- Randevu Raporu (özet) SQL'de gruplanır; tarih seçilmeden tüm zamanlar için 1,6 sn → 0,3 sn. Sonuç, satır satır hesapla birebir aynıdır (testle doğrulanır). Excel için `detay=true` değişmedi.

### Test ve kalite

- Birim, entegrasyon, kabul ve güvenlik testleri (SEC-T01 … SEC-T15); gerçek PostgreSQL testleri; GitHub Actions'ta her PR'da.
- Performans (Locust) ve GUI entegrasyon raporları; FR izlenebilirlik tablosu.

### Bilinen sınırlar

- FR-012 günlük takvim ve FR-013 haftalık takvim için ayrı bir ekran yoktur; randevular Randevu Yönetimi listesinden,
  doluluk Oda Kullanımı ve Cihaz Uygunluk ekranlarından izlenir (bkz. `docs/requirements/FR_Izlenebilirlik_Tablosu.md`).
- HTTPS kurulumu isteğe bağlıdır; yapılmazsa istemci–sunucu trafiği ağda şifresiz gider.
