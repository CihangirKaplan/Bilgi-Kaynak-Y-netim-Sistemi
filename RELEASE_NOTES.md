# TKYS 1.0.0 — Sürüm Notları

**Travma Uygulama ve Araştırma Merkezi Yönetim Sistemi (TKYS)**, merkezin randevu, oda, cihaz, bakım, öğrenci/faaliyet ve
danışma masası süreçlerini tek bir sistemde, rol bazlı yetkiyle ve izlenebilir biçimde yürütmesini sağlar.

| Alan | Bilgi |
|---|---|
| Sürüm | 1.0.0 (ilk kararlı sürüm) |
| Yayın tarihi | ________ (GO/NO-GO kararından sonra) |
| Değişikliklerin tam listesi | `CHANGELOG.md` |

## Kimler ne yapabilir

| Rol | Başlıca işler |
|---|---|
| Psikolog | Kendi randevuları ve danışanları, randevu sonucu (Tamamlandı/Gelmedi), cihaz uygunluğunu görüntüleme |
| Memur (idari personel) | Cihaz envanteri, bakım/kalibrasyon/arıza, oda etkinlikleri, öğrenci ve faaliyet kayıtları |
| Müdür | Yönetim raporları, kullanıcı ve personel yönetimi, danışma masası raporları (görev onayını Memur verir) |
| Proje Asistanı | Öğrenci ve faaliyet kayıtları, cihaz rezervasyonu, oda etkinlikleri |
| Danışma Öğrencisi | Danışma masası görevini başlatma ve bitirme |
| Yönetici (ADMIN) | Bütün işlemler; rol ve izin yönetimi, parola sıfırlama, denetim kayıtları, sistem durumu |

Roller ve izinler merkeze göre Rol & İzin Yönetimi ekranından değiştirilebilir.

## Kurulum

- **Sunucu (tek bilgisayar):** Windows, Python, PostgreSQL. Adım adım: `docs/deployment/Sunucu_Kurulum_Kilavuzu.md`.
  Sunucu, Windows açılınca kendiliğinden başlar; her gün 05.00'te veritabanı yedeği alınır.
- **İstemci (kullanıcı bilgisayarları):** Uygulama ve sunucu adresi. Her istemcide sunucu adresi tanımlanmalıdır:

      setx TKYS_API_URL "http://SUNUCU_ADRESI:8000"

- **Yedekleme ve geri yükleme:** `scripts/windows/README.md` ve sunucu kurulum kılavuzunun 10. bölümü.

## Önceki bir test kurulumundan yükseltme

Sunucuda, sunucu durdurulduktan sonra:

1. `git pull` ile kodu güncelleyin.
2. `python -m alembic upgrade head` ile veritabanı şemasını güncelleyin; `python scripts/sema_dogrula.py` uyumlu demeli.
   Bu adım cihaz durumlarını da düzeltir: açık arızası olmayıp **Arızalı** görünen cihazlar **Kullanıma Hazır**'a, açık arızası olup
   **Kullanıma Hazır** görünen cihazlar **Arızalı**'ya çekilir (bakımdaki, kalibrasyondaki ve kullanım dışı cihazlara dokunulmaz).
   Her değişiklik denetim kaydına yazılır; yükseltmeden sonra Cihaz Envanteri'ni gözden geçirmeniz önerilir.
   Aynı adım **Proje Asistanı**'na Oda Etkinlikleri görüntüleme ve yönetme izinlerini de açar (varsayılan); bir kurulumda bu izin Rol & İzin Yönetimi'nde
   bilerek kapatılmışsa yükseltmeden sonra yeniden kapatın.
   Aynı adım **duyurular** tablosunu ve **DUYURU_YONET** iznini ekler (varsayılan: Admin, Müdür, Memur açık); duyuru yayınlama yetkisini başka role
   vermek için Rol & İzin Yönetimi'ni kullanın.
3. Görevleri yeni ayarlarla yeniden kurun (yönetici PowerShell):
   `python scripts/windows/sunucu_kurulum.py` ve `python scripts/windows/kurulum.py`.
4. Sunucuyu başlatın: `schtasks /Run /TN TKYS_Sunucu`.

## Güvenlik

- Parolalar bcrypt ile saklanır; oturumlar 45 dakika sonra kapanır.
- Hatalı giriş denemeleri hesap ve bilgisayar bazında sınırlanır.
- Her işlem denetim kaydına yazılır ve bu kayıtlar değiştirilemez.
- Güvenlik testleri (SEC-T01 … SEC-T15) ve sonuçları: `docs/test-reports/SEC-001_Guvenlik_Test_Raporu.md`.
- **Öneri:** Ağ üzerinde parolaların şifreli gitmesi için HTTPS kurulumu yapın (`docs/deployment/TLS_Kurulum_Rehberi.md`).

## Kullanıcı kılavuzları

`user-manuals/` klasöründe: Psikolog, Memur, Müdür, Danışma Öğrencisi ve Proje Asistanı, Sistem Yöneticisi kılavuzları
ile ortak kullanım kılavuzu.

## Bilinen sınırlar

- Ayrı bir günlük/haftalık takvim ekranı yoktur (FR-012, FR-013). Randevular Randevu Yönetimi listesinden, doluluk
  Oda Kullanımı ve Cihaz Uygunluk ekranlarından izlenir.
- HTTPS kurulmazsa istemci ile sunucu arasındaki trafik ağda şifresiz gider.
- Sunucu tek bilgisayarda çalışır; o bilgisayar kapalıyken sisteme erişilemez. Yedeklerin bir kopyası sunucu dışında
  (harici disk) saklanmalıdır.

## Destek

Sorun bildirirken ekran görüntüsü ve yapılan işlemle birlikte sistem sorumlusuna iletin. Sistem sorumlusu, sunucuda
`logs\sunucu.log` dosyasındaki ilgili kaydı geliştiriciye iletir.
