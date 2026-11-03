# QA-001 — Gerçek GUI Entegrasyon Test Raporu

**Tarih:** 30.10.2026
**İlgili Issue:** #186
**Çalışma branch'i:** test/qa-001-gui-entegrasyon
**Durum:** Gerçekleştirilen manuel kontroller başarılı

## 1. Test Ortamı

- İşletim sistemi: macOS
- Masaüstü arayüzü: PySide6
- Backend: FastAPI
- Veritabanı: PostgreSQL
- Test veritabanı: crkys_alembic_test
- API adresi: http://127.0.0.1:8001
- Test kullanıcısı: qa_performans
- Test rolü: MEMUR

Testler yalnızca yerel test ortamında gerçekleştirilmiştir.

## 2. Gerçekleştirilen GUI Kontrolleri

| No | Test senaryosu | Sonuç |
|---|---|---|
| GUI-01 | Masaüstü giriş ekranının açılması | BAŞARILI |
| GUI-02 | FastAPI sunucusuna bağlantı | BAŞARILI |
| GUI-03 | Geçerli kullanıcı bilgileriyle oturum açma | BAŞARILI |
| GUI-04 | MEMUR rolünün doğru görüntülenmesi | BAŞARILI |
| GUI-05 | Ana kontrol panelinin yüklenmesi | BAŞARILI |
| GUI-06 | Bakım kayıtları ekranının açılması | BAŞARILI |
| GUI-07 | Kalibrasyon ekranının açılması | BAŞARILI |
| GUI-08 | Cihaz raporları ekranının açılması | BAŞARILI |
| GUI-09 | Danışma Masası Yönetimi erişim davranışının kontrolü | BAŞARILI |
| GUI-10 | MEMUR yetkileriyle sol menünün uyumunun kontrolü | BAŞARILI |
| GUI-11 | Oturum kapatma işlemi | BAŞARILI |

Bu sonuçlar manuel kullanım sırasında gözlemlenmiştir.

## 3. Test Sırasında Karşılaşılan Sorunlar

İlk denemelerde bazı API endpoint'lerinde HTTP 500 hataları gözlemlenmiştir.

Etkilenen endpoint'ler:

- /api/bakimlar
- /api/kalibrasyonlar
- /api/cihaz-raporlari
- /api/dashboard/yaklasan-islemler

FastAPI hata kayıtlarında cihaz bakım tarihleri için eksik
PostgreSQL sütunları tespit edilmiştir.

Sorunun nedeni, test veritabanındaki Alembic migration
sürümünün uygulama kodunun gerisinde kalmasıdır.

## 4. Uygulanan Çözüm

Test veritabanının migration sürümü:

Önce: c01930448638
Sonra: b7e41c9d2a60 (head)

Migration öncesinde test veritabanının yedeği alınmıştır.

Güncelleme sonrasında aşağıdaki sütunların oluşturulduğu
doğrulanmıştır:

- cihaz_bakimlari.bakim_baslangic_tarihi
- cihaz_bakimlari.bakim_bitis_tarihi
- cihaz_kalibrasyonlari.kalibrasyon_baslangic_tarihi
- cihaz_kalibrasyonlari.kalibrasyon_bitis_tarihi

Uygulama yeniden başlatılarak ilgili ekranlar manuel
olarak kontrol edilmiş ve önceki hata pencereleri
gözlemlenmemiştir.

## 5. Rol Bazlı Erişim Kontrolü

MEMUR rolüyle oturum açılmıştır.

Kullanıcının rol bilgisi doğru gösterilmiş, sol menü
görünürlüğü ve Danışma Masası Yönetimi erişim davranışı
manuel olarak kontrol edilmiştir.

Önceki sunucu kayıtlarında bazı yetkisiz endpoint isteklerinin
HTTP 403 döndürdüğü gözlemlenmiştir.

HTTP 403 yanıtı tek başına bir güvenlik açığı değildir;
yetkisiz işlemlerin sunucu tarafından reddedildiğini gösterir.

## 6. Kapsam ve Sınırlamalar

- Kontroller gerçek masaüstü uygulamasında gerçekleştirilmiştir.
- Testler MEMUR rolündeki bir test hesabıyla yapılmıştır.
- Diğer kullanıcı rollerinin uçtan uca davranışı bu raporla
  doğrulanmış sayılmaz.
- Her modülde kayıt oluşturma, güncelleme ve silme akışları
  bu manuel test kapsamında çalıştırılmamıştır.
- Test veritabanına uygulanan migration işlemleri Git
  kaynak dosyalarını değiştirmemiştir.
- Bu rapor, QA-001 kapsamındaki diğer performans ve güvenlik
  testlerinin yerine geçmez.

## 7. Genel Değerlendirme

Gerçek masaüstü uygulaması, test ortamında MEMUR hesabıyla
başarıyla çalıştırılmıştır.

Giriş, ana kontrol paneli, bakım, kalibrasyon, cihaz raporları,
rol bazlı menü görünürlüğü ve oturum kapatma kontrolleri
başarıyla tamamlanmıştır.

Test sırasında tespit edilen veritabanı şema uyumsuzluğu,
eksik Alembic migration'larının test veritabanına
uygulanmasıyla giderilmiştir.

QA-001 Issue #186'nın genel kapanış değerlendirmesi,
diğer test sonuçlarıyla birlikte ayrıca yapılacaktır.
