# SMOKE-001 — Canlı Ortam Smoke Testi (Hafta 8, Gün 2)

Amaç: Canlı sunucuya kurulan sürümün temel işlevlerinin, **istemci bilgisayardan** ve **gerçek hesaplarla** çalıştığını göstermek.
Her satırda "Sonuç" (PASS/FAIL), "Tarih" ve "Kanıt" (ekran görüntüsü dosya adı ya da komut çıktısı) doldurulur.
FAIL olan her satır için GitHub'da issue açılır ve numarası "Not" sütununa yazılır.

| Alan | Bilgi |
|---|---|
| Sunucu | Windows, `https://172.24.4.66:8443` (kendi imzalı sertifika, 23.11.2031'e kadar geçerli) |
| Sürüm | `develop` — commit: f675e84 (sunucuda `git log -1 --format=%h`) |
| Veritabanı | `tkys`, migration: f4c8a2e6b917 (`python -m alembic current`) |
| İstemci | Bilgisayar adı: MacBook Air, `TKYS_API_URL` = `https://172.24.4.66:8443`, `TKYS_CA_BUNDLE` = sunucunun `sertifika.pem` dosyası |
| Testi yapan | ________ |
| Tarih | 24.11.2026 |

## Hazırlık (sunucu)

| # | Kontrol | Nasıl | Sonuç | Kanıt |
|---|---|---|---|---|
| H1 | Sunucu görevi süre sınırsız | `(Get-ScheduledTask -TaskName TKYS_Sunucu).Settings.ExecutionTimeLimit` → `PT0S` | PASS | Komut çıktısı: `PT0S` |
| H2 | Yeniden başlatma sonrası kendiliğinden açılıyor | Sunucuyu yeniden başlat, **oturum açmadan** istemciden `/api/saglik` | PASS | Açılış saati 24.11.2026 14:17:23 (`LastBootUpTime`); oturum açmadan Mac'ten `{"durum":"calisiyor"}` |
| H3 | Şema güncel | `python scripts/sema_dogrula.py` → uyumlu | PASS | `ŞEMA UYUMLU` (sürüm `f4c8a2e6b917`) |
| H4 | Test hesabı yok | Kullanıcılar ekranında `qa_`, `tarama_`, `test` ile başlayan hesap yok | | |
| H5 | HTTPS | Sunucuda `python -c "import requests; r = requests.get('https://172.24.4.66:8443/api/saglik', verify=r'C:\TKYS\sertifika\sertifika.pem'); print(r.status_code, r.headers.get('strict-transport-security'))"` | PASS | `200 max-age=31536000`; `X-Content-Type-Options: nosniff`; sertifika doğrulaması açık |

## Smoke testleri (istemciden)

| # | Başlık | Adımlar | Beklenen | Sonuç | Tarih | Kanıt | Not |
|---|---|---|---|---|---|---|---|
| S1 | API | İstemciden `https://172.24.4.66:8443/api/saglik` (sertifika doğrulamalı) | `{"durum":"calisiyor"}` | PASS | 24.11.2026 | Mac'te Python `requests` ile `200 {"durum":"calisiyor"}` | HTTP/8000 kapatıldı |
| S2 | Login | Her rolle (yönetici, müdür, memur, psikolog, danışma öğrencisi) giriş | Ana sayfa açılır, rol adı doğru | | | | |
| S3 | Login (hatalı) | Yanlış parolayla giriş | "Kullanıcı adı veya parola hatalı" | PASS | 24.11.2026 | Giriş ekranında hata mesajı ekran görüntüsü; sunucu günlüğünde `POST /api/login 401` | |
| S4 | DB | Yönetici → Sistem Durumu | Sürüm, şema ve veritabanı yeşil | PASS | 24.11.2026 | Sistem Durumu ekran görüntüsü: sürüm 1.0.0, şema `f4c8a2e6b917`, boyut 10.1 MB | |
| S5 | Randevu | Psikolog: randevu oluştur → düzenle → iptal et | Her adım başarılı; listede doğru durum | | | | |
| S6 | Randevu çakışması | Aynı psikolog/oda için aynı saate ikinci randevu | Reddedilir, anlaşılır mesaj | | | | |
| S7 | Cihaz | Cihaz rezervasyonu oluştur ve iptal et | Başarılı | | | | |
| S8 | Bakım | Memur: bakım kaydı ekle | Kayıt listede görünür | | | | |
| S9 | Audit | Yönetici → Denetim Kayıtları | S2–S8'deki işlemler (giriş, oluşturma, iptal) görünür | | | | |
| S10 | Yetki | Psikolog hesabında yönetim menüleri görünmüyor | Yalnızca kendi menüleri | | | | |
| S11 | Backup | Sunucuda `schtasks /Run /TN TKYS_Otomatik_Yedekleme`; `logs\yedekleme.log` | `çıkış kodu: 0`, `backups` klasöründe yeni dosya | PASS | 24.11.2026 | `çıkış kodu: 0`; `tkys_20261124_114734_010781.dump` (113 KB) | |
| S12 | Son yedek kartı | Yönetici → Sistem Durumu → Son Yedek | S11'deki yedeğin tarihi, yeşil | PASS | 24.11.2026 | Son Yedek kartı: 24.11.2026 11:47 (2 saat önce), yeşil, toplam 11 yedek | |

## Sonuç

- PASS: ___ / 17  FAIL: ___
- Açılan issue'lar: ________
- Karar: Pilot'a (Gün 3) geçilebilir ☐  Önce düzeltme gerekli ☐
