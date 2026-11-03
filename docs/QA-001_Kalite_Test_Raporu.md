# TKYS – QA-001 Kalite ve Test Raporu

**Proje:** Travma Uygulama ve Araştırma Merkezi Bilgi ve Kaynak Yönetim Sistemi (TKYS)

**Görev:** QA-001 – Kalite ve Test Çalışmaları\
**GitHub Issue:** #186\
**Sorumlu:** Öğrenci C\
**Branch:** `test/qa-001-quality-testing`\
**İlk rapor:** 27.10.2026  
**Son güncelleme:** 30.10.2026

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

- Başarılı test: **336**
- Başarısız test: **0**
- Seçim filtresiyle hariç tutulan test: **1**
- Test süresi: **6,60 saniye**
- Ölçülen üç dosyada birleşik kod kapsamı: **%66**

### Dosya bazında Coverage

| Dosya | Coverage |
|---|---:|
| sunucu.py | %65 |
| guvenlik.py | %100 |
| denetim.py | %100 |
| TOPLAM | %66 |

Coverage ölçümü `sunucu.py`, `guvenlik.py` ve `denetim.py` dosyalarının satır ve branch kapsamını içermektedir. Bu oran tüm TKYS projesinin kapsamı değildir.

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

## 9. GitHub Actions ve Pull Request Durumu

QA-001 kapsamında otomatik testler GitHub Actions
iş akışına entegre edilmiştir.

- PR #189: Merge edildi.
- PR #190: Merge edildi.
- PR #191: GitHub Actions başarılı; ekip incelemesi bekleniyor.

CI, PostgreSQL servisi gerektiren belirli entegrasyon
testlerini hariç tutmaktadır. Bu testler yerel test
veritabanında ayrıca değerlendirilmiştir.

## 10. Gerçek PostgreSQL Entegrasyon Testleri

28 Ekim 2026 çalışmalarında `crkys_alembic_test`
veritabanında 7 gerçek PostgreSQL testi başarılı olmuştur.

Kontrol edilen alanlar:

- Transaction ve rollback davranışları
- Audit işlemleri
- Eşzamanlı rezervasyon senaryoları
- Test verilerinin izolasyonu ve temizlenmesi
- Randevu ve cihaz rezervasyonu EXCLUDE kısıtları

Bu sonuçlar, bütün PostgreSQL kısıtlarının tüm negatif
senaryolarının test edildiği anlamına gelmez.

İlgili çalışmalar PR #190 ile develop'a alınmıştır.

## 11. Gerçek API Performans Ölçümleri

Locust kullanılarak gerçek FastAPI ve PostgreSQL
üzerinden kontrollü yük testleri gerçekleştirilmiştir.

Test edilen sanal kullanıcı sayıları:
1, 5, 10, 20, 40 ve 60.

30 Ekim 2026 tarihli son 60 kullanıcı testinde:

| Metrik | Sonuç |
|---|---:|
| Test süresi | 45 saniye |
| Toplam HTTP isteği | 1707 |
| Başarısız istek | 0 |
| Ortalama yanıt süresi | 21 ms |
| P95 | 38 ms |
| P99 | 60 ms |
| İstek/saniye | 38,11 |
| Ortalama CPU | %17,23 |
| Maksimum CPU | %23,20 |
| Ortalama RAM | 51,43 MB |
| Maksimum RAM | 51,89 MB |

Test edilen endpoint: `GET /api/odalar`.

CPU/RAM değerleri FastAPI sürecine aittir;
PostgreSQL süreçlerinin kaynak tüketimini içermez.

Ayrıntılı sonuçlar:

`docs/test-reports/QA001_Locust_Performans_Raporu.md`

Son kaynak ölçümleri PR #191 kapsamındadır.

## 12. Gerçek GUI Entegrasyon Kontrolleri

PySide6 masaüstü uygulaması, MEMUR rolündeki test
hesabıyla gerçek FastAPI ve PostgreSQL ortamında
manuel olarak kontrol edilmiştir.

Başarılı gözlemlenen işlemler:

- Kullanıcı girişi ve oturum kapatma
- Ana kontrol panelinin yüklenmesi
- Bakım ve kalibrasyon ekranları
- Cihaz raporları ekranı
- Rol bazlı menü ve erişim davranışları

Test sırasında eksik veritabanı sütunları nedeniyle
HTTP 500 hataları tespit edilmiştir.

Test veritabanı yedeklendikten sonra Alembic sürümü
`c01930448638` seviyesinden `b7e41c9d2a60`
seviyesine yükseltilmiştir.

Eksik bakım ve kalibrasyon tarihi sütunlarının
eklendiği doğrulanmış, ilgili ekranlar yeniden
kontrol edilmiştir.

Ayrıntılı manuel GUI raporu:

`docs/test-reports/QA001_GUI_Entegrasyon_Raporu.md`

Bu rapor PR #191 kapsamındadır.

## 13. Bağımlılık Güvenlik Taraması

30 Ekim 2026 tarihinde `pip-audit 2.10.1`
ile `requirements.txt` taranmıştır.

Tarama sonucu:

`No known vulnerabilities found`

Tarama sırasında önbellek uyarıları görülmüş,
ancak bilinen güvenlik açığı raporlanmamıştır.

Bu sonuç yalnızca tarama anında ve belirtilen
bağımlılıklar için geçerlidir. Taramanın terminal
çıktısı alınmış, ayrı bir tarama kanıt dosyası
henüz repoya eklenmemiştir.

## 14. Kapsam ve Açık Kalan Kriterler

Aşağıdaki konular henüz tamamen doğrulanmamıştır:

- Sistemin maksimum yük sınırı
- Uzun süreli dayanıklılık ve kaynak tüketimi
- Bütün desteklenen işletim sistemlerinde GUI kontrolü
- Diğer kullanıcı rollerinin tam uçtan uca testleri
- Tüm veritabanı kısıtlarının negatif senaryoları
- Normal yük için ekipçe onaylanmış sayısal P95 hedefi

30.10.2026 tarihinde bağımsız PostgreSQL 18 sunucusu
üzerinde (55432 portu) gerçek kesinti ve toparlanma
testi gerçekleştirilmiştir.

`GET /api/odalar` endpoint'i FastAPI TestClient ile
kontrol edilmiştir. Kimlik doğrulama bağımlılığı test
ortamında geçici olarak devre dışı bırakılmıştır.

Sonuç: HTTP 200 → 500 → 200.

PostgreSQL durdurulmuş, yeniden başlatılmış ve
API'nin yeniden çalıştığı doğrulanmıştır.
Geçici test ortamı güvenle temizlenmiştir.

Bu sonuç yalnızca test edilen endpoint ve bağlantı
senaryosu için geçerlidir.

Son güvenli regresyonda 336 test başarılı,
1 test seçim filtresiyle hariç tutulmuştur.
Ayrıca 5 PostgreSQL test dosyası güvenli regresyon
koşumuna dahil edilmemiştir.

## 15. Genel Değerlendirme

QA-001 kapsamında otomatik regresyon, güvenlik,
gerçek PostgreSQL entegrasyonu, kontrollü yük,
kaynak tüketimi ve GUI kontrollerinde önemli
doğrulamalar gerçekleştirilmiştir.

PR #189 ve #190 develop branch'ine alınmıştır.
PR #191 ekip incelemesi aşamasındadır.

Mevcut sonuçlar değerlendirilen senaryolarda
olumlu olsa da TKYS v1.0'ın bütün kurumsal
kabul kriterlerini karşıladığı henüz doğrulanmamıştır.

Issue #186'nın Definition of Done koşulları için
açık kalan kriterlerin ekip tarafından değerlendirilmesi
ve ilgili PR incelemelerinin tamamlanması gerekmektedir.
