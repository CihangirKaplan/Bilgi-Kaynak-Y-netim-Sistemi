# SEC-001 — Güvenlik Test Raporu (SEC-T01 … SEC-T15)

| Alan | Bilgi |
|---|---|
| Kapsam | Yol haritası belgesi, 23. bölüm: SEC-T01 … SEC-T15 |
| Biçim | Yol haritası belgesi, 24. bölüm (Test ID, Requirement, Environment, …) |
| Sorumlu | Öğrenci C (Backend, Security & Platform) |
| Hazırlanma | 22.11.2026 |
| Sürüm | `develop` — `5626337` |

Bu rapor iki ortamı ayrı gösterir:

- **Geliştirme/CI:** Otomatik testler. Linux, Python 3.13, PostgreSQL test veritabanı `crkys_alembic_test`. Aynı testler GitHub'da her PR'da
  ("TKYS QA Tests") da çalışır. Sonuçlar 22.11.2026'da yerelde çalıştırılarak alınmıştır.
- **Canlı ortam:** Windows sunucu `172.24.4.66:8000`, istemci bilgisayardan elle yapılan denemeler. ⏳ olan satırlar sunucuda yapılıp
  sonuç, tarih ve kanıt (ekran görüntüsü ya da komut çıktısı) bu rapora eklenecektir.

Testleri tek komutla yeniden çalıştırmak için (proje klasöründe):

```
python -m pytest -q tests/security
```

## Özet

| Test ID | Konu | Geliştirme/CI | Canlı ortam |
|---|---|---|---|
| SEC-T01 | Authentication Bypass | ✅ PASS (6 test) | ✅ PASS (tokensiz istek 401) — tarih/kanıt eklenecek |
| SEC-T02 | Function-Level Authorization | ✅ PASS (24 test) | ⏳ |
| SEC-T03 | Object-Level Authorization | ✅ PASS (15 test) | ⏳ |
| SEC-T04 | Property-Level Authorization | ✅ PASS (10 test) | — (sunucu kodu aynı; ayrıca gerekmez) |
| SEC-T05 | Input Validation | ✅ PASS (129 test) | — |
| SEC-T06 | Injection | ✅ PASS (5 test) | — |
| SEC-T07 | Rate / Brute-Force | ✅ PASS (24 test) | ⏳ |
| SEC-T08 | Token | ✅ PASS (9 test) | ⏳ |
| SEC-T09 | Error Leakage | ✅ PASS (24 test) | — |
| SEC-T10 | Secret Scan | ✅ PASS (3 test) | ⏳ (`.env` ve JWT anahtarı) |
| SEC-T11 | Dependency Scan | ✅ PASS (40 bağımlılık, 0 bilinen açık) | ⏳ (sunucudaki kurulumla) |
| SEC-T12 | Audit Integrity | ✅ PASS (17 test) | ⏳ |
| SEC-T13 | Backup Security | ✅ PASS (3 test) | ⏳ (klasör izni) |
| SEC-T14 | Business Logic Abuse | ✅ PASS (11 test) | — |
| SEC-T15 | Concurrency | ✅ PASS (8 test) | — |

"—" olan maddeler sunucuda farklı davranamayacak kod kurallarıdır; geliştirme/CI testi yeterli kanıttır.
Bilinen açık bulgu yok (P0 = 0, P1 = 0).

## Ayrıntılar

### SEC-T01 — Authentication Bypass

```
Test ID:          SEC-T01
Requirement:      Kimlik doğrulaması olmadan korunan uca erişilemez (beklenen 401).
Environment:      Geliştirme/CI (develop 5626337) + Canlı (172.24.4.66:8000)
Precondition:     Sunucu çalışıyor; istekte token yok, süresi dolmuş ya da değiştirilmiş token var.
Steps:            1. Bütün API uçları taranır, /api/saglik dışında hepsinin token istediği doğrulanır.
                  2. Tokensiz ve süresi dolmuş token ile korunan uca istek atılır.
                  3. Canlı: istemci bilgisayardan GET http://172.24.4.66:8000/api/cihazlar (token yok).
Expected Result:  401 Unauthorized; veri dönmez.
Actual Result:    Geliştirme: 6/6 test geçti. Canlı: istemciden 401 alındı.
PASS / FAIL:      PASS
Tester:           Öğrenci C
Date:             22.11.2026 (canlı deneme tarihi eklenecek)
Evidence:         tests/security/test_uc_koruma_taramasi.py, test_sec_t01_t02.py, test_sec_t07_t08_auth.py;
                  canlı: istemcideki istek çıktısının ekran görüntüsü
```

### SEC-T02 — Function-Level Authorization

```
Test ID:          SEC-T02
Requirement:      Yetkisi olmayan rol, başka rolün işlevine erişemez (ör. psikolog → müdür ucu: 403).
Environment:      Geliştirme/CI + Canlı
Precondition:     Her rol için bir kullanıcı hesabı.
Steps:            1. Kritik uçlar her rolle çağrılır; izni olmayan roller için 403 beklenir.
                  2. Canlı: psikolog hesabıyla giriş yapılır; yönetim raporları / kullanıcı yönetimi menülerinin görünmediği
                     ve doğrudan istekle (ör. GET /api/yonetim-raporlari/...) 403 döndüğü görülür.
Expected Result:  403 Forbidden; menü görünmez.
Actual Result:    Geliştirme: 24/24 test geçti. Canlı: ⏳
PASS / FAIL:      Geliştirme PASS / Canlı ⏳
Tester:           Öğrenci C
Date:             22.11.2026
Evidence:         test_sec_t01_t02.py, test_kritik_endpoint_rbac_quality.py, test_rbac_quality.py, test_kalan_uclar_yetki.py
```

### SEC-T03 — Object-Level Authorization

```
Test ID:          SEC-T03
Requirement:      Kullanıcı yetkili olmadığı bir kaydı (başka psikoloğun randevusu, başkasının rezervasyonu) değiştiremez.
Environment:      Geliştirme/CI + Canlı
Precondition:     İki psikolog; birinin randevusu ve cihaz rezervasyonu var.
Steps:            1. Psikolog B, psikolog A'nın randevusunu düzenlemeye / iptal etmeye çalışır.
                  2. Kullanıcı başkasının cihaz rezervasyonunu düzenlemeye / iptal etmeye çalışır.
                  3. Canlı: iki psikolog hesabıyla aynı deneme istemciden yapılır.
Expected Result:  İşlem reddedilir (403/404); kayıt değişmez.
Actual Result:    Geliştirme: 15/15 test geçti. Canlı: ⏳
PASS / FAIL:      Geliştirme PASS / Canlı ⏳
Tester:           Öğrenci C
Date:             22.11.2026
Evidence:         test_sec_t03_http.py, test_randevu_yetkilendirme.py, tests/unit/test_rezervasyon_duzenleme.py
```

### SEC-T04 — Property-Level Authorization

```
Test ID:          SEC-T04
Requirement:      Normal kullanıcı isteğe "role = DIRECTOR" ya da benzeri bir alan ekleyerek yetki kazanamaz.
Environment:      Geliştirme/CI
Precondition:     Yetkisiz rol hesabı.
Steps:            1. Kullanıcı kendi rolünü değiştirmeye çalışır.
                  2. İsteğe is_admin gibi beklenmeyen bir yetki alanı eklenir.
                  3. Müdür, kendi seviyesindeki ya da üstündeki rolün personel kaydını değiştirmeye çalışır.
Expected Result:  Değişiklik uygulanmaz (403/422).
Actual Result:    10/10 test geçti.
PASS / FAIL:      PASS
Tester:           Öğrenci C
Date:             22.11.2026
Evidence:         test_adm_privilege_validation.py, tests/unit/test_personel_rol_hiyerarsisi.py
```

### SEC-T05 — Input Validation

```
Test ID:          SEC-T05
Requirement:      null, aşırı uzun metin, geçersiz tarih, negatif ID, hatalı enum, beklenmeyen alan → kontrollü 4xx.
Environment:      Geliştirme/CI
Precondition:     —
Steps:            Randevu ve diğer uçlara bozuk girdiler gönderilir; NUL karakteri, taşan sayı, 1 MiB üstü gövde ve
                  "Application/Json" / "application/merge-patch+json" ile atlatma denemeleri dahil.
Expected Result:  422 (ya da 413); 500 yok, veri değişmez.
Actual Result:    129/129 test geçti.
PASS / FAIL:      PASS
Tester:           Öğrenci C
Date:             22.11.2026
Evidence:         test_sec_t05_http.py, tests/integration/test_girdi_korumasi.py, test_randevu_girdi_dogrulama.py
```

### SEC-T06 — Injection

```
Test ID:          SEC-T06
Requirement:      Kullanıcı girdisi SQL sorgusunu etkileyemez.
Environment:      Geliştirme/CI
Precondition:     —
Steps:            Oda adı, bakım ve kalibrasyon alanlarına SQL parçası ("'; DROP TABLE ...") gönderilir; izin verilmeyen
                  alan adları denenir.
Expected Result:  Girdi parametre olarak işlenir, sorguya eklenmez; izinsiz alan yok sayılır ya da reddedilir.
Actual Result:    5/5 test geçti.
PASS / FAIL:      PASS
Tester:           Öğrenci C
Date:             22.11.2026
Evidence:         test_sec_t06_sql_injection.py
```

### SEC-T07 — Rate / Brute-Force

```
Test ID:          SEC-T07
Requirement:      Hızlı tekrarlanan giriş denemeleri engellenir.
Environment:      Geliştirme/CI (PostgreSQL dahil) + Canlı
Precondition:     Aktif bir test hesabı.
Steps:            1. Aynı hesaba 5 kez yanlış parola: hesap 1 dk kilitlenir; 10 kez: 15 dk.
                  2. Aynı bilgisayardan 5 dk içinde 20 başarısız deneme: istekler 429 ile reddedilir.
                  3. Şifre değiştirmede yanlış eski şifre de aynı sınıra sayılır.
                  4. Canlı: istemciden bir test hesabıyla 5 kez yanlış parola girilir, ardından doğru parolayla giriş denenir.
Expected Result:  Kilit mesajı; doğru parola da kilit süresince kabul edilmez; denemeler denetim kaydına yazılır.
Actual Result:    Geliştirme: 24/24 test geçti. Canlı: ⏳
PASS / FAIL:      Geliştirme PASS / Canlı ⏳
Tester:           Öğrenci C
Date:             22.11.2026
Evidence:         test_sec_t07_t08_auth.py, test_giris_siniri_pg_quality.py (PG), tests/unit/test_son_kontrol_duzeltmeleri.py
```

### SEC-T08 — Token

```
Test ID:          SEC-T08
Requirement:      Token yok, geçersiz, süresi dolmuş ya da pasif kullanıcıya ait token reddedilir.
Environment:      Geliştirme/CI + Canlı
Precondition:     Aktif ve pasifleştirilecek iki hesap.
Steps:            1. Değiştirilmiş ve süresi dolmuş token ile istek.
                  2. Kullanıcı pasifleştirilir; elindeki token ile istek.
                  3. Canlı: istemcide giriş yapılmışken yönetici o hesabı pasifleştirir; istemcide bir işlem denenir.
Expected Result:  401; istemci giriş ekranına döner.
Actual Result:    Geliştirme: 9/9 test geçti. Canlı: ⏳
PASS / FAIL:      Geliştirme PASS / Canlı ⏳
Tester:           Öğrenci C
Date:             22.11.2026
Evidence:         test_token_api_kalite.py, test_guvenlik_jwt_kalite.py, test_kullanici_pasiflestirme.py
```

### SEC-T09 — Error Leakage

```
Test ID:          SEC-T09
Requirement:      Hata yanıtlarında stack trace, SQL, dosya yolu, parola ya da gizli anahtar görünmez.
Environment:      Geliştirme/CI
Precondition:     —
Steps:            Uçlar veritabanı hatası ve beklenmeyen hata durumlarında çağrılır; yanıt metinleri taranır.
Expected Result:  Yalnızca genel Türkçe mesaj; ayrıntı yalnızca sunucudaki logs\sunucu.log dosyasında.
Actual Result:    24/24 test geçti. (Ayrıca 52 uca hatalı girdi gönderilen tarama yapıldı: hiçbirinde 500, SQL ya da
                  iz metni görülmedi.)
PASS / FAIL:      PASS
Tester:           Öğrenci C
Date:             22.11.2026
Evidence:         test_hata_mesaji_taramasi_quality.py, test_api_hata_sizintisi_ek_guvenlik.py, test_hata_mesaji_guvenligi_quality.py
```

### SEC-T10 — Secret Scan

```
Test ID:          SEC-T10
Requirement:      Depoda parola, veritabanı bilgisi ya da token anahtarı bulunmaz.
Environment:      Geliştirme/CI + Canlı
Precondition:     —
Steps:            1. Depo, düz yazılmış gizli bilgi kalıplarına karşı taranır; .env dosyasının depoda olmadığı doğrulanır.
                  2. JWT_SECRET 32 karakterden kısaysa sunucu açılmaz (kontrol edilir).
                  3. Canlı: sunucudaki .env yalnızca sunucuda; JWT_SECRET rastgele üretilmiş ve örnek dosyadaki değer değil:
                     python -c "import os;from dotenv import load_dotenv;load_dotenv();print(len(os.getenv('JWT_SECRET','')))"
Expected Result:  Depoda gizli bilgi yok; sunucudaki anahtar en az 32 karakter ve rastgele.
Actual Result:    Geliştirme: 3/3 test geçti. Canlı: ⏳
PASS / FAIL:      Geliştirme PASS / Canlı ⏳
Tester:           Öğrenci C
Date:             22.11.2026
Evidence:         test_gizli_bilgi_taramasi.py, test_jwt_secret_quality.py
```

### SEC-T11 — Dependency Scan

```
Test ID:          SEC-T11
Requirement:      Python bağımlılıklarında bilinen güvenlik açığı yok.
Environment:      Geliştirme (pip-audit 2.10.1, OSV/PyPI açık veritabanı) + Canlı
Precondition:     requirements.txt
Steps:            1. pip install pip-audit
                  2. pip-audit -r requirements.txt
                  3. Canlı: sunucuda, sanal ortam etkinken: pip-audit   (kurulu paketleri tarar)
Expected Result:  "No known vulnerabilities found"
Actual Result:    Geliştirme: 40 bağımlılık (doğrudan 16 + dolaylı) tarandı, bilinen açık yok. Canlı: ⏳
PASS / FAIL:      Geliştirme PASS / Canlı ⏳
Tester:           Öğrenci C
Date:             22.11.2026
Evidence:         pip-audit çıktısı (ekran görüntüsü eklenecek)
Not:              Tarama, o günkü açık veritabanına göredir; canlıya geçmeden hemen önce yeniden çalıştırılmalıdır.
```

### SEC-T12 — Audit Integrity

```
Test ID:          SEC-T12
Requirement:      Normal kullanıcı denetim kaydını değiştiremez ve silemez.
Environment:      Geliştirme/CI + Canlı
Precondition:     Denetim kayıtları var.
Steps:            1. denetim_kayitlari tablosunda UPDATE / DELETE / TRUNCATE veritabanı tetikleyicileriyle engellenir.
                  2. Uygulama kodunda denetim tablosunu değiştiren ya da silen sorgu olmadığı taranır.
                  3. API'de denetim kaydını değiştiren/silen uç yoktur; listeleme yalnızca yetkili role açıktır.
                  4. Canlı: sunucuda psql ile uygulama kullanıcısıyla
                     UPDATE denetim_kayitlari SET olay_turu = 'X' WHERE denetim_id = 1;   → hata vermeli.
Expected Result:  Değiştirme ve silme reddedilir; kayıt aynı kalır.
Actual Result:    Geliştirme: 17/17 test geçti. Canlı: ⏳
PASS / FAIL:      Geliştirme PASS / Canlı ⏳
Tester:           Öğrenci C
Date:             22.11.2026
Evidence:         test_audit_degistirilemez.py, test_audit_security.py
```

### SEC-T13 — Backup Security

```
Test ID:          SEC-T13
Requirement:      Normal kullanıcı yedek dosyasına erişemez.
Environment:      Geliştirme/CI + Canlı
Precondition:     Sunucuda C:\TKYS\backups klasöründe yedek var.
Steps:            1. Hiçbir API ucunun dosya sunmadığı ve statik klasör bağlanmadığı doğrulanır.
                  2. Yedek hakkında bilgi veren tek uç (Sistem Durumu) yalnızca yetkili role açık; dosya yolu ya da dosya adı
                     değil, yalnızca tarih/adet/boyut döndürür.
                  3. Canlı: klasör izinleri kontrol edilir:  icacls C:\TKYS\backups
                     Çıktıda yalnızca Administrators ve SYSTEM (ve sistem sorumlusu hesabı) olmalı; Users/Everyone olmamalı.
                     Klasör ağda paylaşılmamalı.
Expected Result:  API üzerinden yedeğe ulaşılamaz; klasöre yalnızca sistem sorumlusu erişir.
Actual Result:    Geliştirme: 3/3 test geçti. Canlı: ⏳
PASS / FAIL:      Geliştirme PASS / Canlı ⏳
Tester:           Öğrenci C
Date:             22.11.2026
Evidence:         tests/security/test_sec_t13_yedek_erisimi.py; canlı: icacls çıktısı
```

### SEC-T14 — Business Logic Abuse

```
Test ID:          SEC-T14
Requirement:      Arızalı (ya da bakımda / kalibrasyonda / kullanım dışı) cihaz için rezervasyon oluşturulamaz.
Environment:      Geliştirme/CI
Precondition:     Durumu uygun olmayan cihaz; planlı bakım/kalibrasyonla kesişen saat.
Steps:            Bu cihazlara ve kesişen saatlere rezervasyon denenir.
Expected Result:  Reddedilir; rezervasyon oluşmaz.
Actual Result:    11/11 test geçti.
PASS / FAIL:      PASS
Tester:           Öğrenci C
Date:             22.11.2026
Evidence:         test_cihaz_modulu.py (test_uygun_olmayan_cihaz_rezerve_edilemez), test_rezervasyon_bakim_kalibrasyon.py
```

### SEC-T15 — Concurrency

```
Test ID:          SEC-T15
Requirement:      Aynı kaynak için eşzamanlı iki işlem veri tutarsızlığı oluşturmaz.
Environment:      Geliştirme/CI (gerçek PostgreSQL ile eşzamanlı bağlantılar dahil)
Precondition:     Aynı psikolog/oda/cihaz için aynı saat aralığı.
Steps:            Aynı anda iki randevu, iki cihaz rezervasyonu ve iki oda etkinliği oluşturulmaya çalışılır.
Expected Result:  Yalnızca biri başarılı olur, diğeri 409 alır; kilitlenme (deadlock) olmaz.
Actual Result:    8/8 test geçti.
PASS / FAIL:      PASS
Tester:           Öğrenci C
Date:             22.11.2026
Evidence:         test_randevu_eszamanlilik_quality.py, test_cihaz_rezervasyon_eszamanlilik.py, test_randevu_deadlock_quality.py,
                  test_rezervasyon_psikolog_yaris_pg.py (PG), test_oda_etkinlikleri_eszamanlilik.py
```

## Bilinen sınırlar

- **HTTPS:** Canlı ortamda istemci ile sunucu arasındaki trafik şu an HTTP'dir; parolalar ve oturum anahtarları ağda şifresiz gider.
  Kurulum için `docs/deployment/TLS_Kurulum_Rehberi.md`. Yapılmayacaksa gerekçesi karar olarak yazılmalıdır.
- **Güvenlik duvarı:** 8000 numaralı port açık; erişimin yalnızca merkez ağıyla sınırlandırılması önerilir.
