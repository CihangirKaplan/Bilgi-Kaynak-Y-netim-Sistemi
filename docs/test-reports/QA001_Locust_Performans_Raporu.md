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


## 6. Kontrollu Stres Testi ve Veri Kumesi Karsilastirmasi

**Tarih:** 28.10.2026
**Endpoint:** GET /api/odalar
**Ortam:** Yerel FastAPI, JWT ve crkys_alembic_test
**Sure:** Her seviye icin 45 saniye

| Senaryo | Istek | Ortalama | P95 | P99 | Istek/sn | Hata |
|---|---:|---:|---:|---:|---:|---:|
| 40 kullanici, 0 oda | 1156 | 20 ms | 33 ms | 59 ms | 25.93 | %0 |
| 60 kullanici, 0 oda | 1701 | 19 ms | 41 ms | 62 ms | 37.90 | %0 |
| 60 kullanici, 20 oda | 1701 | 20 ms | 36 ms | 62 ms | 37.93 | %0 |

Bu sayilar Locust terminalinin son ozetlerinden alinmistir.
Kaydedilen CSV dosyalarindaki son istek sayilari farklilik
gosterebilir; ham CSV dosyalari ayri kanit olarak saklanmistir.

### Degerlendirme

- Uc senaryoda da gozlenen HTTP hata orani %0'dir.
- 60 kullanicida 20 odali tabloyla P95 36 ms olarak olculmustur.
- Bos ve 20 kayitli tablo arasinda belirgin bir performans
  bozulmasi gozlenmemistir.
- Bu kontrollu yuk olcumleri sistemin maksimum kapasitesini
  veya uzun sureli dayanikliligini belirlememektedir.
- Veritabani baglanti sayilari, CPU ve bellek kullanimi
  yuk altinda ayrica olculmemistir.
- Testler bir endpoint ve tek bir JWT hesabi ile sinirlidir.


## 7. PostgreSQL Baglanti Kesintisi ve Toparlanma

**Tarih:** 28.10.2026
**Test veritabani:** crkys_alembic_test
**Endpoint:** GET /api/odalar
**Yontem:** httpx.ASGITransport ve psycopg2.connect hata simulasyonu

| Asama | HTTP | Sonuc |
|---|---|---|
| Normal baglanti | 200 | Basarili |
| Baglanti hatasi simulasyonu | 500 | Hata algilandi |
| Simulasyon sonrasi toparlanma | 200 | Basarili |

### Guvenlik Kontrolu

Simulasyon icin kullanilan
`QA001_SIMULATED_DB_UNAVAILABLE`
hata metni HTTP yanitinda gorulmedi.

### Degerlendirme

- Normal durumda API basarili yanit vermistir.
- Veritabani baglantisi hata verdiginde API HTTP 500 donmustur.
- Hata simulasyonu kaldirildiginda API yeniden HTTP 200 donmustur.
- Simulasyona ait hata metni istemciye yansimamistir.
- Test sirasinda PostgreSQL servisi durdurulmamistir.
- Bu test, gercek servis kesintisini ve servis yeniden
  baslatildiktan sonraki toparlanmayi kanitlamaz.
- HTTP 500 yerine kontrollu HTTP 503 donulmesi
  ayri bir iyilestirme olarak degerlendirilebilir.


## 8. PostgreSQL Baglanti ve Istatistik Analizi

**Tarih:** 28.10.2026
**Veritabani:** crkys_alembic_test
**Olcum zamani:** Locust testleri tamamlandiktan sonra

| Metrik | Deger |
|---|---:|
| Aktif baglanti | 1 |
| Bosta baglanti | 1 |
| Maksimum sunucu baglanti limiti | 100 |
| COMMIT sayaci | 26220 |
| ROLLBACK sayaci | 12834 |
| Okunan blok | 41 |
| Onbellek isabeti | 4520042 |
| Deadlock sayaci | 33 |
| Veritabani boyutu | 9622 kB |
| Odalar sirali tarama | 6029 |
| Odalar indeks tarama | 110 |
| Odalar tahmini canli kayit | 0 |
| Odalar tahmini olu kayit | 28 |

### Degerlendirme

- Kontrol aninda 2 PostgreSQL baglantisi bulunmustur.
- Okumalarin buyuk kismi PostgreSQL onbelleginden karsilanmistir.
- Odalar tablosundaki 0 tahmini canli kayit, gecici test
  odalarinin temizlenmesiyle uyumludur.
- 33 deadlock kaydi gozlenmistir. Bunlarin hangi testlerden
  veya islemlerden kaynaklandigi belirlenememistir.
- COMMIT, ROLLBACK ve deadlock sayaclari birikimlidir.
- Bu olcum yuk testi sirasinda yapilmadigindan zirve
  baglanti sayisi, CPU ve bellek kullanimi bilinmemektedir.
- Deadlock nedenleri mevcut eszamanlilik ve transaction
  testleriyle birlikte ayrica incelenmelidir.

## 9. Eszamanlilik ve EXCLUDE Kisitlari

**Tarih:** 28.10.2026
**Veritabani:** crkys_alembic_test

PostgreSQL sistem kataloglari uzerinden asagidaki
EXCLUDE kisitlarinin mevcut oldugu dogrulandi:

- cihaz_rezervasyon_cakisma
- oda_randevu_cakisma
- psikolog_randevu_cakisma

Cihaz rezervasyonlarinda iptal edilmemis kayitlar,
randevularda ise PLANLANDI durumundaki kayitlar
icin zaman cakismalari veritabani seviyesinde
engellenmektedir.

Randevu ve cihaz rezervasyonu kodlarinda
deadlock sonrasi rollback ve sinirli yeniden
deneme mekanizmalari incelendi.

Onceki PostgreSQL entegrasyon testleri basarilidir.

PostgreSQL istatistiklerinde gorulen 33 deadlock
kaydinin tarihsel kaynagi belirlenememistir.
Bu sayinin Locust testlerinden kaynaklandigina
yonelik kanit bulunmamaktadir.

Bu incelemede yeni bir veri butunlugu hatasi
tespit edilmemistir.
