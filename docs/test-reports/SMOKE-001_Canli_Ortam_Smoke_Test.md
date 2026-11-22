# SMOKE-001 — Canlı Ortam Smoke Testi (Hafta 8, Gün 2)

Amaç: Canlı sunucuya kurulan sürümün temel işlevlerinin, **istemci bilgisayardan** ve **gerçek hesaplarla** çalıştığını göstermek.
Her satırda "Sonuç" (PASS/FAIL), "Tarih" ve "Kanıt" (ekran görüntüsü dosya adı ya da komut çıktısı) doldurulur.
FAIL olan her satır için GitHub'da issue açılır ve numarası "Not" sütununa yazılır.

| Alan | Bilgi |
|---|---|
| Sunucu | Windows, `172.24.4.66:8000` (HTTPS yapılırsa `https://…`) |
| Sürüm | `develop` — commit: ________ (sunucuda `git log -1 --format=%h`) |
| Veritabanı | `tkys`, migration: ________ (`python -m alembic current`) |
| İstemci | Bilgisayar adı: ________, `TKYS_API_URL` = ________ |
| Testi yapan | ________ |
| Tarih | ________ |

## Hazırlık (sunucu)

| # | Kontrol | Nasıl | Sonuç | Kanıt |
|---|---|---|---|---|
| H1 | Sunucu görevi süre sınırsız | `(Get-ScheduledTask -TaskName TKYS_Sunucu).Settings.ExecutionTimeLimit` → `PT0S` | | |
| H2 | Yeniden başlatma sonrası kendiliğinden açılıyor | Sunucuyu yeniden başlat, **oturum açmadan** istemciden `/api/saglik` | | |
| H3 | Şema güncel | `python scripts/sema_dogrula.py` → uyumlu | | |
| H4 | Test hesabı yok | Kullanıcılar ekranında `qa_`, `tarama_`, `test` ile başlayan hesap yok | | |

## Smoke testleri (istemciden)

| # | Başlık | Adımlar | Beklenen | Sonuç | Tarih | Kanıt | Not |
|---|---|---|---|---|---|---|---|
| S1 | API | Tarayıcıda `http://172.24.4.66:8000/api/saglik` | `{"durum":"calisiyor"}` | | | | |
| S2 | Login | Her rolle (yönetici, müdür, memur, psikolog, danışma öğrencisi) giriş | Ana sayfa açılır, rol adı doğru | | | | |
| S3 | Login (hatalı) | Yanlış parolayla giriş | "Kullanıcı adı veya parola hatalı" | | | | |
| S4 | DB | Yönetici → Sistem Durumu | Sürüm, şema ve veritabanı yeşil | | | | |
| S5 | Randevu | Psikolog: randevu oluştur → düzenle → iptal et | Her adım başarılı; listede doğru durum | | | | |
| S6 | Randevu çakışması | Aynı psikolog/oda için aynı saate ikinci randevu | Reddedilir, anlaşılır mesaj | | | | |
| S7 | Cihaz | Cihaz rezervasyonu oluştur ve iptal et | Başarılı | | | | |
| S8 | Bakım | Memur: bakım kaydı ekle | Kayıt listede görünür | | | | |
| S9 | Audit | Yönetici → Denetim Kayıtları | S2–S8'deki işlemler (giriş, oluşturma, iptal) görünür | | | | |
| S10 | Yetki | Psikolog hesabında yönetim menüleri görünmüyor | Yalnızca kendi menüleri | | | | |
| S11 | Backup | Sunucuda `schtasks /Run /TN TKYS_Otomatik_Yedekleme`; `logs\yedekleme.log` | `çıkış kodu: 0`, `backups` klasöründe yeni dosya | | | | |
| S12 | Son yedek kartı | Yönetici → Sistem Durumu → Son Yedek | S11'deki yedeğin tarihi, yeşil | | | | |

## Sonuç

- PASS: ___ / 16  FAIL: ___
- Açılan issue'lar: ________
- Karar: Pilot'a (Gün 3) geçilebilir ☐  Önce düzeltme gerekli ☐
