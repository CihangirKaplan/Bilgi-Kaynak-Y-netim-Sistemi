# SEC-001 — Güvenlik Test Raporu (SEC-T01 … SEC-T15)

| Alan | Bilgi |
|---|---|
| Kapsam | Yol haritası belgesi, 23. bölüm: SEC-T01 … SEC-T15 |
| Biçim | Yol haritası belgesi, 24. bölüm (Test ID, Requirement, Environment, …) |
| Sorumlu | Öğrenci C (Backend, Security & Platform) |
| Hazırlanma | 22.11.2026 |
| Güncelleme | 27.11.2026 — canlı API denemeleri (T01, T02, T03, T07, T08: 23 PASS, 0 FAIL) ve sunucuda elle yapılan denemeler (T10–T13) `develop` `f1efdb2` ile güncellenen canlı sunucuda yapıldı; T13 ve T10'da iki bulgu bulunup düzeltildi |
| Sürüm | `develop` — `f8c0b00` (ilk sürüm: `5626337`) |

Bu rapor iki ortamı ayrı gösterir:

- **Geliştirme/CI:** Otomatik testler. Linux, Python 3.13, PostgreSQL test veritabanı `crkys_alembic_test`. Aynı testler GitHub'da her PR'da
  ("TKYS QA Tests") da çalışır. Sonuçlar 22.11.2026'da yerelde çalıştırılarak alınmıştır.
- **Canlı ortam:** Windows sunucu `https://172.24.4.66:8443` (HTTPS), istemci bilgisayardan yapılan denemeler. ⏳ olan satırlar sunucuda yapılıp
  sonuç, tarih ve kanıt (ekran görüntüsü ya da komut çıktısı) bu rapora eklenecektir.

Testleri tek komutla yeniden çalıştırmak için (proje klasöründe):

```
python -m pytest -q tests/security
```

## Özet

| Test ID | Konu | Geliştirme/CI | Canlı ortam |
|---|---|---|---|
| SEC-T01 | Authentication Bypass | ✅ PASS (15 test) | ✅ PASS (27.11.2026: tokensiz ve bozuk token istekleri 401) |
| SEC-T02 | Function-Level Authorization | ✅ PASS (25 test) | ✅ PASS (27.11.2026: psikolog hesabı yönetim uçlarında 403) |
| SEC-T03 | Object-Level Authorization | ✅ PASS (15 test) | ✅ PASS (27.11.2026: başkasının randevusu ve rezervasyonu 403, kayıt değişmedi) |
| SEC-T04 | Property-Level Authorization | ✅ PASS (10 test) | — (sunucu kodu aynı; ayrıca gerekmez) |
| SEC-T05 | Input Validation | ✅ PASS (129 test) | — |
| SEC-T06 | Injection | ✅ PASS (5 test) | — |
| SEC-T07 | Rate / Brute-Force | ✅ PASS (24 test) | ✅ PASS (27.11.2026: 5. yanlış parolada 429, kilit sürerken doğru parola 429, 60 sn sonra 200) |
| SEC-T08 | Token | ✅ PASS (25 test; bkz. Bulgular) | ✅ PASS (27.11.2026: bozuk/imzasız token 401, pasifleştirilen hesabın token'ı 403; istemcide açık oturum "Oturumunuz geçersiz hâle gelmiştir" ile sonlanır, yeniden girişte "Kullanıcı hesabı aktif değil.") |
| SEC-T09 | Error Leakage | ✅ PASS (24 test) | — |
| SEC-T10 | Secret Scan | ✅ PASS (3 test) | ✅ PASS (27.11.2026: `.env` git dışı, JWT anahtarı 64 karakter ve örnek değil; `.env` ve `anahtar.pem` izinleri daraltıldı — Bulgular #4) |
| SEC-T11 | Dependency Scan | ✅ PASS (40 bağımlılık, 0 bilinen açık) | ✅ PASS (27.11.2026: sunucudaki kurulu paketlerde bilinen açık yok) |
| SEC-T12 | Audit Integrity | ✅ PASS (17 test) | ✅ PASS (27.11.2026: UPDATE/DELETE/TRUNCATE engellendi, kayıt sayısı 75 → 75) |
| SEC-T13 | Backup Security | ✅ PASS (3 test) | ✅ PASS (27.11.2026, düzeltmeden sonra; ilk denemede FAIL: miras izinler — Bulgular #3) |
| SEC-T14 | Business Logic Abuse | ✅ PASS (36 test) | — |
| SEC-T15 | Concurrency | ✅ PASS (8 test) | — |

"—" olan maddeler sunucuda farklı davranamayacak kod kurallarıdır; geliştirme/CI testi yeterli kanıttır.
Bilinen açık bulgu yok (P0 = 0, P1 = 0).

**25.11.2026 yeniden çalıştırma:** Her maddenin "Evidence" satırındaki dosyaların tamamı gerçek PostgreSQL ile çalıştırılmıştır (test sayıları o
dosyalardaki bütün testleri gösterir; 22.11.2026 listesine göre T01, T02, T08 ve T14 sayıları bu yüzden büyüdü). SEC-T11: `pip-audit -r requirements.txt`
→ 40 bağımlılık, "No known vulnerabilities found".

**Canlı satırların (⏳) nasıl tamamlanacağı:** `docs/test-reports/SEC-001_Canli_Deneme_Rehberi.md`. API denemeleri (T01, T02, T03, T07, T08)
`scripts/canli_guvenlik_denemesi.py` ile, sunucu denemeleri (T10–T13) rehberdeki komutlarla yapılır.

## Bulgular

| # | Madde | Bulgu | Önem | Durum |
|---|---|---|---|---|
| 1 | SEC-T08 | Oturum açıkken hesabı pasifleştirilen kullanıcının token'ı sunucuda **reddediliyordu** (403 "Kullanıcı hesabı aktif değil."; veri dönmez) ama istemci yalnızca 401'i "oturum bitti" saydığı için giriş ekranına dönmüyor, her işlemde hata gösteriyordu. | P2 (güvenlik açığı değil, kullanıcı deneyimi) | Düzeltildi: istemci bu 403'ü oturum sonu sayar (`client/api_yoneticisi.py`, test `test_oturum_pasif_hesap.py`) |
| 2 | SEC-T12 | Canlı deneme komutundaki `SET olay_turu = 'X'` tetikleyici yüzünden değil, 'X' geçerli bir değer olmadığı için hata veriyordu (yanlış nedenle PASS verebilirdi). | Rapor düzeltmesi | Düzeltildi: komut geçerli bir sütun/değerle (`SET hedef_tablo = 'deneme'`) yazıldı |
| 3 | SEC-T13 | Yedek klasörü (`C:\TKYS\backups`) üst klasörden miras kalan izinlerle `Users` (okuma) ve `Authenticated Users` (değiştirme) erişimine açıktı: sunucuya giriş yapan her kullanıcı veritabanı yedeklerini okuyabilir ya da silebilirdi. | P1 (veri gizliliği) | Düzeltildi 27.11.2026: miras kesildi, yalnızca Administrators ve SYSTEM (`icacls /inheritance:r`); otomatik yedekleme doğrulandı |
| 4 | SEC-T10 | `.env` (veritabanı ve JWT sırları) ve `sertifika\anahtar.pem` (TLS özel anahtarı) aynı mirasla her kullanıcıya açıktı. | P1 (sır gizliliği) | Düzeltildi 27.11.2026: yalnızca Administrators ve SYSTEM; sunucu çalışmaya devam ediyor |
| 5 | SEC-T10 / T12 | (a) `C:\TKYS` klasörünün kendisi `Authenticated Users` tarafından değiştirilebilir (sunucu kodu dahil). (b) Sunucu veritabanına `postgres` (tam yetkili) ile bağlanıyor; kurulum kılavuzu 6A'daki kısıtlı kullanıcı (`tkys_uygulama`) kurulmamış. | P2 (sertleştirme önerisi) | Açık: ekip kararı. Sunucuya yalnızca yönetici hesaplarının giriş yapabildiği ortamda risk düşüktür |

## Ayrıntılar

### SEC-T01 — Authentication Bypass

```
Test ID:          SEC-T01
Requirement:      Kimlik doğrulaması olmadan korunan uca erişilemez (beklenen 401).
Environment:      Geliştirme/CI (develop 5626337) + Canlı (https://172.24.4.66:8443)
Precondition:     Sunucu çalışıyor; istekte token yok, süresi dolmuş ya da değiştirilmiş token var.
Steps:            1. Bütün API uçları taranır, /api/saglik dışında hepsinin token istediği doğrulanır.
                  2. Tokensiz ve süresi dolmuş token ile korunan uca istek atılır.
                  3. Canlı: scripts/canli_guvenlik_denemesi.py (T01.1–T01.3): tokensiz ve bozuk token ile korunan uçlar.
Expected Result:  401 Unauthorized; veri dönmez.
Actual Result:    Geliştirme: 15/15 test geçti. Canlı (27.11.2026): 6/6 PASS; /api/saglik 200, korunan uçlar tokensiz 401, bozuk token 401.
PASS / FAIL:      PASS
Tester:           Öğrenci C
Date:             22.11.2026 (geliştirme) / 27.11.2026 (canlı)
Evidence:         tests/security/test_uc_koruma_taramasi.py, test_sec_t01_t02.py, test_sec_t07_t08_auth.py;
                  canlı: docs/test-reports/kanit/sec001_canli_kanit_20261127_1150.txt
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
Actual Result:    Geliştirme: 25/25 test geçti. Canlı (27.11.2026): 4/4 PASS; psikolog hesabı randevu-özet, denetim kayıtları, kullanıcı oluşturma ve
                  rol değiştirme uçlarında 403 "Bu işlem için yetkiniz bulunmuyor." aldı (hesabın geçici parolası değiştirilmiş olarak denendi).
PASS / FAIL:      PASS
Tester:           Öğrenci C
Date:             22.11.2026 (geliştirme) / 27.11.2026 (canlı)
Evidence:         test_sec_t01_t02.py, test_kritik_endpoint_rbac_quality.py, test_rbac_quality.py, test_kalan_uclar_yetki.py;
                  canlı: docs/test-reports/kanit/sec001_canli_kanit_20261127_1150.txt
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
Actual Result:    Geliştirme: 15/15 test geçti. Canlı (27.11.2026): 4/4 PASS; psikolog B, A'nın randevusunu iptal edemedi (403), randevu PLANLANDI
                  kaldı; asistan, başkasının rezervasyonunu iptal edemedi (403), rezervasyon Aktif kaldı.
PASS / FAIL:      PASS
Tester:           Öğrenci C
Date:             22.11.2026 (geliştirme) / 27.11.2026 (canlı)
Evidence-canlı:   docs/test-reports/kanit/sec001_canli_kanit_20261127_1150.txt
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
Actual Result:    Geliştirme: 24/24 test geçti. Canlı (27.11.2026): 4/4 PASS; 5. yanlış parolada 429 (ilk 4 deneme 401), kilit sürerken doğru parola
                  429 "Hesap geçici olarak kilitli.", Retry-After 60 sn, süre dolunca doğru parola 200.
PASS / FAIL:      PASS
Tester:           Öğrenci C
Date:             22.11.2026 (geliştirme) / 27.11.2026 (canlı)
Evidence:         test_sec_t07_t08_auth.py, test_giris_siniri_pg_quality.py (PG), tests/unit/test_son_kontrol_duzeltmeleri.py;
                  canlı: docs/test-reports/kanit/sec001_canli_kanit_20261127_1150.txt
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
Expected Result:  Token ile istek reddedilir (veri dönmez): bozuk/süresi dolmuş token 401; pasifleştirilen hesabın token'ı 403 "Kullanıcı hesabı aktif
                  değil."; her iki durumda istemci "Oturumunuz geçersiz hâle gelmiştir" uyarısıyla giriş ekranına döner.
Actual Result:    Geliştirme: 25/25 test geçti (25.11.2026). Pasifleştirilen hesabın token'ı 403 alır; istemcinin buna tepkisi eksikti, düzeltildi
                  (Bulgular #1). Canlı (27.11.2026, betik): 6/6 PASS; geçerli token 200, imzası bozulmuş ve imzasız (alg: none) token 401,
                  yönetici hesabı pasifleştirince eski token 403 "Kullanıcı hesabı aktif değil." (hesap betikle yeniden aktif edildi).
                  Canlı (27.11.2026, istemci, elle): `sec_pasif` oturumu açıkken yönetici hesabı pasife aldı; istemcide işlem denenince
                  "Oturumunuz geçersiz hâle gelmiştir. Uygulamayı kullanmaya devam etmek için lütfen yeniden giriş yapın." uyarısı çıktı ve giriş
                  ekranı açıldı; aynı hesapla yeniden girişte "Kullanıcı hesabı aktif değil." görüldü.
PASS / FAIL:      PASS (betik ve istemci)
Tester:           Öğrenci C
Date:             22.11.2026 (geliştirme) / 27.11.2026 (canlı)
Evidence:         test_token_api_kalite.py, test_guvenlik_jwt_kalite.py, test_kullanici_pasiflestirme.py, tests/unit/test_oturum_pasif_hesap.py;
                  canlı: scripts/canli_guvenlik_denemesi.py çıktısı (T08.1–T08.4);
                  istemci: docs/test-reports/kanit/sec001_t08_istemci_1_oturum_uyarisi.png,
                  docs/test-reports/kanit/sec001_t08_istemci_2_hesap_aktif_degil.png
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
Actual Result:    Geliştirme: 3/3 test geçti. Canlı (27.11.2026): `.env` git tarafından yok sayılıyor (git check-ignore .env); JWT_SECRET
                  64 karakter ve örnek dosyadaki değerle aynı değil (anahtarın kendisi yazdırılmadı). Bulgu: `.env` ve `sertifika\anahtar.pem`
                  dosyalarına üst klasörden miras kalan izinle her kullanıcı erişebiliyordu; yalnızca Administrators ve SYSTEM'e daraltıldı
                  (Bulgular #4) ve sunucunun çalışmaya devam ettiği doğrulandı.
PASS / FAIL:      PASS (bulgu düzeltildikten sonra)
Tester:           Öğrenci C
Date:             22.11.2026 (geliştirme) / 27.11.2026 (canlı)
Evidence:         test_gizli_bilgi_taramasi.py, test_jwt_secret_quality.py; canlı: docs/test-reports/kanit/sec001_sunucu_kanit_20261127.txt
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
Actual Result:    Geliştirme: 40 bağımlılık (doğrudan 16 + dolaylı) tarandı, bilinen açık yok. Canlı (27.11.2026): sunucunun sanal ortamında `pip_audit` (2.10.1): "No known vulnerabilities found".
PASS / FAIL:      PASS
Tester:           Öğrenci C
Date:             22.11.2026
Evidence:         pip-audit çıktısı; canlı: docs/test-reports/kanit/sec001_sunucu_kanit_20261127.txt
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
                     UPDATE denetim_kayitlari SET hedef_tablo = 'deneme' WHERE denetim_id = 1;   → tetikleyici hatası vermeli
                     (mesaj "...degistirilemez veya silinemez (UPDATE)"; DELETE ve TRUNCATE için de aynı).
Expected Result:  Değiştirme ve silme reddedilir; kayıt aynı kalır.
Actual Result:    Geliştirme: 17/17 test geçti. Canlı (27.11.2026, postgres kullanıcısıyla, BEGIN ... ROLLBACK içinde): UPDATE, DELETE ve
                  TRUNCATE "denetim_kayitlari tablosundaki kayitlar degistirilemez veya silinemez" hatasıyla engellendi; kayıt sayısı
                  75 → 75. Not: sunucu veritabanına `postgres` ile bağlanıyor (Bulgular #5).
PASS / FAIL:      PASS
Tester:           Öğrenci C
Date:             22.11.2026 (geliştirme) / 27.11.2026 (canlı)
Evidence:         test_audit_degistirilemez.py, test_audit_security.py; canlı: docs/test-reports/kanit/sec001_sunucu_kanit_20261127.txt
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
Actual Result:    Geliştirme: 3/3 test geçti. Canlı (27.11.2026): ilk denemede FAIL; yedek klasöründe üst klasörden miras kalan `Users` (okuma) ve
                  `Authenticated Users` (değiştirme) izinleri vardı (Bulgular #3). Miras kesilip yalnızca Administrators ve SYSTEM bırakıldıktan
                  sonra PASS: yönetici olmayan oturum klasörü listeleyemiyor ("Erişim engellendi"), `net share` listesinde yedek klasörü yok,
                  otomatik yedekleme (SYSTEM) çalışmaya devam ediyor (yeni yedek, çıkış kodu 0).
PASS / FAIL:      PASS (bulgu düzeltildikten sonra)
Tester:           Öğrenci C
Date:             22.11.2026 (geliştirme) / 27.11.2026 (canlı)
Evidence:         tests/security/test_sec_t13_yedek_erisimi.py; canlı: docs/test-reports/kanit/sec001_sunucu_kanit_20261127.txt
```

### SEC-T14 — Business Logic Abuse

```
Test ID:          SEC-T14
Requirement:      Arızalı (ya da bakımda / kalibrasyonda / kullanım dışı) cihaz için rezervasyon oluşturulamaz.
Environment:      Geliştirme/CI
Precondition:     Durumu uygun olmayan cihaz; planlı bakım/kalibrasyonla kesişen saat.
Steps:            Bu cihazlara ve kesişen saatlere rezervasyon denenir.
Expected Result:  Reddedilir; rezervasyon oluşmaz.
Actual Result:    36/36 test geçti.
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
