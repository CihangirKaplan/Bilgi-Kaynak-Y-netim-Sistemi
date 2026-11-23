# Değişiklik Günlüğü (CHANGELOG)

Bu dosya TKYS'nin sürümler arasındaki önemli değişikliklerini listeler. Ayrıntılar ilgili Pull Request'lerdedir (GitHub, `develop` dalı).
Biçim: [Keep a Changelog](https://keepachangelog.com/tr/1.1.0/). Sürüm numaraları [Anlamsal Sürümleme](https://semver.org/lang/tr/) kuralına uyar.

## [1.0.0] — Yayın tarihi: GO/NO-GO kararından sonra yazılacak

İlk kararlı sürüm. 21 Eylül – 22 Kasım 2026 arasında, 8 haftalık yol haritasıyla geliştirildi (yaklaşık 340 Pull Request).
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
- Mesai (08:00–18:00), hafta sonu ve geçmiş tarih kuralları; psikolog yalnızca kendi randevularını yönetir.
- Danışan kodları (yıl bazlı), danışan yaş grubu, terapi türü ve görüşme tipi; Danışanlar sayfası.
- Randevu Raporları sayfası ve dört sayfalı Excel çıktısı.

### Oda ve oda etkinlikleri

- Oda yönetimi; psikolog oda yetkileri (her psikologun en az bir odası).
- Oda Kullanımı: gün/hafta görünümü, randevu, cihaz rezervasyonu ve etkinlik blokları, mesai doluluk oranı.
- Oda Etkinlikleri: tek ya da çok günlü etkinlikler, çakışma denetimi, katılımcı sayısı.

### Cihaz yaşam döngüsü

- Cihaz envanteri (envanter kodu, durum, oda), cihaz geçmişi zaman çizgisi.
- Cihaz rezervasyonu: çakışma, mesai ve sahiplik kuralları; düzenleme ve iptal; arızalı/bakımdaki cihaz rezerve edilemez.
- Cihaz Uygunluğu: haftalık takvim, gün detayı, müsait cihaz bulma.
- Bakım ve kalibrasyon kayıtları ve planları (periyot, uyarı süresi, geciken plan bildirimleri).
- Arıza bildirimi, çözüm notu ve yeniden açma; arıza cihaz durumunu tutarlı biçimde günceller.
- Cihaz raporları (rezervasyon, geciken bakım planı) ve Excel aktarımı.

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

### Test ve kalite

- Birim, entegrasyon, kabul ve güvenlik testleri (SEC-T01 … SEC-T15); gerçek PostgreSQL testleri; GitHub Actions'ta her PR'da.
- Performans (Locust) ve GUI entegrasyon raporları; FR izlenebilirlik tablosu.

### Bilinen sınırlar

- FR-012 günlük takvim ve FR-013 haftalık takvim için ayrı bir ekran yoktur; randevular Randevu Yönetimi listesinden,
  doluluk Oda Kullanımı ve Cihaz Uygunluk ekranlarından izlenir (bkz. `docs/requirements/FR_Izlenebilirlik_Tablosu.md`).
- HTTPS kurulumu isteğe bağlıdır; yapılmazsa istemci–sunucu trafiği ağda şifresiz gider.
