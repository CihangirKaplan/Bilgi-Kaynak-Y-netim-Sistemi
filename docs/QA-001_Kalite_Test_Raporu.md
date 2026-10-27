# TKYS – QA-001 Kalite ve Test Raporu

**Proje:** Travma Uygulama ve Araştırma Merkezi Bilgi ve Kaynak Yönetim Sistemi (TKYS)

**Görev:** QA-001 – Kalite ve Test Çalışmaları\
**GitHub Issue:** #186\
**Sorumlu:** Öğrenci C\
**Branch:** `test/qa-001-quality-testing`\
**Tarih:** 27.10.2026

---

## 1. Amaç

Bu çalışma kapsamında TKYS uygulamasının backend, güvenlik,
veritabanı işlem bütünlüğü, API davranışları ve masaüstü arayüzü
üzerinde kalite kontrolleri gerçekleştirilmiştir.

Amaç; mevcut hataları tespit etmek, gerekli düzeltmeleri uygulamak
ve bu düzeltmeleri otomatik testlerle doğrulamaktır.

## 2. Kullanılan Teknolojiler

- Python 3.13
- FastAPI
- PostgreSQL
- PySide6
- pytest
- pytest-cov
- httpx
- Git ve GitHub Actions

## 3. Gerçekleştirilen Hata Düzeltmeleri

| Kod | Konu | Yapılan çalışma |
|---|---|---|
| QA-BUG-001 | Oda listesi yetkilendirmesi | Endpoint için kimlik doğrulama zorunlu hale getirildi. |
| QA-BUG-002 | Randevu eşzamanlılığı | Deadlock durumları için sınırlı yeniden deneme eklendi. |
| QA-BUG-003 | Cihaz rezervasyonu iptali | Tekrarlanan iptal işlemleri engellendi. |
| QA-BUG-004 | Audit transaction bütünlüğü | Denetim kayıtlarında ortak transaction kullanımı güçlendirildi. |
| QA-BUG-005 | Hata mesajlarında bilgi sızıntısı | Teknik hata ayrıntıları istemciye gösterilmekten çıkarıldı. |
| QA-BUG-006 | HTTP hata kodları | Bazı CRUD işlemlerinde 404/422 yanıtlarının korunması sağlandı. |
| QA-BUG-007 | Audit kayıtlarının zorunluluğu | Audit hatalarını sessizce atlayan ImportError yapıları kaldırıldı. |
| QA-BUG-008 | Öğrenci ekleme güvenliği | Mevcut faaliyet düzenleme izniyle RBAC ve transaction içi audit eklendi. |

## 4. Test Sonuçları

Son genel regresyon testi:

- Başarılı test: **313**
- Başarısız test: **0**
- Seçim filtresiyle hariç tutulan test: **1**
- Test süresi: **6,41 saniye**
- Genel kod kapsamı: **%65**

### Dosya bazında Coverage

| Dosya | Coverage |
|---|---:|
| sunucu.py | %64 |
| guvenlik.py | %100 |
| denetim.py | %100 |
| TOPLAM | %65 |

Coverage ölçümü, satır ve branch kapsamını içermektedir.

## 5. Güvenlik Testleri

Aşağıdaki alanlarda otomatik testler gerçekleştirilmiştir:

- JWT ve kimlik doğrulama kontrolleri
- Rol tabanlı yetkilendirme (RBAC)
- Yetkisiz API erişimlerinin engellenmesi
- Güvenli hata mesajları
- HTTP durum kodları
- Transaction ve rollback davranışları
- Audit kayıtlarının işlem bütünlüğü
- Randevu eşzamanlılığı
- Cihaz rezervasyonu işlemleri

## 6. API Performans Testleri

Gerçek veritabanı bağlantısı yerine mock kullanılarak
100 sıralı ve 100 eşzamanlı istek ölçülmüştür.

| Ölçüm | Sıralı | Eşzamanlı |
|---|---:|---:|
| İstek sayısı | 100 | 100 |
| Eşzamanlılık sınırı | 1 | 10 |
| Toplam süre | 0,112 sn | 0,121 sn |
| Ortalama yanıt | 1,11 ms | 10,28 ms |
| P95 yanıt | 1,27 ms | 20,30 ms |
| İstek/saniye | 895,44 | 827,87 |

**Sonuç:** Her iki test başarılıdır.

Bu sonuçlar kontrollü, mock tabanlı API ölçümleridir.
Gerçek PostgreSQL ve ağ performansını temsil etmez.

## 7. PySide6 Arayüz Testleri

### Öğrenci ekleme ekranı

3 test başarılı:

- Zorunlu alanların doğrulanması
- Öğrenci numarası formatının kontrolü
- Geçerli bilgilerin API'ye gönderilmesi

### Danışma masası ekranı

5 test başarılı:

- Görev başlatma işleminden vazgeçme
- Görev başlatmayı onaylama
- Aktif görev yokken bitirme girişimi
- Görev bitirmekten vazgeçme
- Görev bitirmeyi onaylama ve sürenin gösterilmesi

GUI testlerinde gerçek API ve veritabanı bağlantıları kullanılmamıştır.

## 8. Danışma Masası Oturum Kontrolleri

Mevcut oturum testleri incelenmiştir.

Aktif görev sorgusunun `bitis_zamani IS NULL` koşulunu
kullandığı ve çalışma süresinin başlangıç zamanı ile
güncel zaman üzerinden hesaplandığı doğrulanmıştır.

Uygulama kapatılıp yeniden açılarak yapılacak gerçek
uçtan uca oturum kontrolü manuel kabul testi olarak
ayrıca değerlendirilmelidir.

## 9. GitHub Actions

`.github/workflows/qa-tests.yml` oluşturulmuştur.

Hazırlanan CI yapılandırması:

- Python 3.13 ortamını hazırlar.
- Proje bağımlılıklarını kurar.
- Güvenli QA test grubunu çalıştırır.
- Coverage raporu oluşturur.
- Coverage XML çıktısını artifact olarak saklar.

**Durum:** Yerel yapılandırma tamamlanmıştır.
GitHub üzerinde başarılı çalıştığı henüz doğrulanmamıştır.

## 10. Kapsam ve Sınırlamalar

Son genel regresyonda gerçek PostgreSQL entegrasyonu
gerektiren belirli test dosyaları hariç tutulmuştur.

Bu nedenle 313 başarılı test sonucu, tüm entegrasyon
ve üretim ortamı senaryolarının doğrulandığı anlamına gelmez.

Test sırasında bir StarletteDeprecationWarning görülmüştür.
Bu uyarı testlerin başarısını etkilememiştir.

## 11. Sonuç

QA-001 kapsamında güvenlik, hata yönetimi, audit,
transaction ve arayüz davranışlarına yönelik iyileştirmeler
yapılmıştır.

Son genel regresyonda **313 test başarılı**, başarısız
test sayısı **0**, toplam Coverage oranı **%65** olmuştur.

Değişiklikler Pull Request ve ekip incelemesine
hazırlanmıştır.

**Bekleyen kontroller:**

- GitHub Actions çalışma sonucunun doğrulanması
- Ayrı PostgreSQL entegrasyon testlerinin değerlendirilmesi
- Danışma masası uygulama kapanma/açılma manuel testi
- Ekip arkadaşının PR incelemesi
