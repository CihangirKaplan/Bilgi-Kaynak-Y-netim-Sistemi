# QA-001 — Gerçek API Performans Testi Raporu

**Issue:** #186
**Tarih:** 28.10.2026
**Araç:** Locust 2.47.0
**Ortam:** Yerel FastAPI + gerçek PostgreSQL
**Test veritabanı:** crkys_alembic_test
**Endpoint:** GET /api/odalar
**Kimlik doğrulama:** JWT
**Test süresi:** Her kullanıcı seviyesi için 60 saniye

## 1. Test Sonuçları

| Kullanıcı | İstek | Ortalama | P95 | P99 | İstek/sn | Hata |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 39 | 28 ms | 35 ms | 100 ms | 0,66 | %0 |
| 5 | 200 | 25 ms | 34 ms | 63 ms | 3,37 | %0 |
| 10 | 393 | 25 ms | 32 ms | 38 ms | 6,58 | %0 |
| 20 | 805 | 24 ms | 33 ms | 69 ms | 13,44 | %0 |

**Toplam:** 1.437 istek, 0 başarısız istek.

**Kanıt dosyaları hakkında:** Yukarıdaki istek sayıları Locust'un terminalde gösterdiği son özetlere dayanmaktadır. Kaydedilmiş `stats.csv` dosyalarındaki sayılar ise sırasıyla 1: 38, 5: 198, 10: 389, 20: 796 şeklindedir. CSV ve terminal özetleri arasında küçük farklılıklar vardır; raporda bu iki kaynak ayrı belirtilmiştir. Testler yeniden çalıştırılmamıştır.

## 2. Değerlendirme

- Dört yük seviyesinde de gözlenen hata oranı %0'dır.
- 20 sanal kullanıcı seviyesinde ortalama yanıt süresi 24 ms'dir.
- 20 sanal kullanıcı seviyesinde yaklaşık P95 33 ms, P99 69 ms'dir.
- Ölçülen yük seviyelerinde belirgin bir yanıt süresi artışı gözlenmemiştir.
- Normal yük için resmi P95 kabul eşiği henüz belirlenmemiştir.

## 3. Kapsam ve Sınırlamalar

- Testler aynı bilgisayarda yerel HTTP bağlantısıyla gerçekleştirilmiştir.
- Testlerde gerçek JWT doğrulaması ve PostgreSQL bağlantısı kullanılmıştır.
- Yalnızca GET /api/odalar endpoint'i ölçülmüştür.
- Sanal kullanıcılar istekler arasında 1–2 saniye beklemiştir.
- 20 sanal kullanıcı, sürekli 20 eşzamanlı HTTP isteği anlamına gelmez.
- JWT tek bir test hesabından alınmıştır.
- P95 ve P99 değerleri Locust tarafından yaklaşık hesaplanmıştır.
- PostgreSQL bağlantı sayısı, sorgu süreleri ve kaynak kullanımı ayrıca ölçülmemiştir.
- Maksimum sistem kapasitesi, stres ve kesinti sonrası toparlanma henüz doğrulanmamıştır.

## 4. Sonuç

QA-001 Issue #186 kapsamında 1, 5, 10 ve 20 sanal kullanıcıyla
gerçek HTTP ve PostgreSQL performans ölçümleri gerçekleştirilmiştir.

Bu dört yük seviyesinde başarısız istek gözlenmemiştir.

Sonuçlar, ölçülen endpoint ve yerel test ortamı için geçerlidir.
TKYS'nin genel performans kabulü için diğer kritik endpoint'ler,
stres testleri ve veritabanı kaynak analizleri ayrıca değerlendirilmelidir.

## 5. Kanıt Dosyaları

Aynı klasörde her yük seviyesi için Locust tarafından oluşturulan
stats.csv, stats_history.csv, failures.csv ve exceptions.csv
dosyaları bulunmaktadır.
