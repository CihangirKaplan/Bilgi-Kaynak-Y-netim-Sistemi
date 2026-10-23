# TKYS - Windows Otomatik Yedekleme

## Gereksinimler

- Windows 10 veya 11
- Python ve proje sanal ortamı (.venv)
- PostgreSQL istemci araçları (pg_dump.exe)
- Proje bağımlılıklarının kurulmuş olması
- Veritabanı bağlantı ayarlarının .env dosyasında bulunması

## Kurulum

Proje klasöründe sanal ortamı etkinleştirin:

    .venv\Scripts\activate

PostgreSQL'in bin klasörünü PATH'e ekleyin veya
PG_DUMP_PATH ortam değişkenini pg_dump.exe dosyasının
tam yolu olarak tanımlayın.

Önce manuel yedeklemeyi test edin:

    python scripts/veritabani_yedekle.py

Ardından günlük otomatik görevi oluşturun:

    python scripts/windows/kurulum.py

Kurulum, Windows Görev Zamanlayıcı'da
TKYS_Otomatik_Yedekleme isimli günlük 09:00 görevini oluşturur.

## Kontrol

Görev Zamanlayıcı uygulamasında görevin oluştuğunu kontrol edin.

Yedekler proje içindeki backups/ klasörüne kaydedilir.
Başarılı yedekleme sonrasında 7 günden eski yedekler temizlenir.

## Önemli

- Mevcut yapı yalnızca crkys_alembic_test veritabanını yedekler.
- Ana crkys veritabanı bu işlemle yedeklenmez veya değiştirilmez.
- Otomatik görev, bilgisayar kapalıyken çalışmaz.
- Windows üzerinde gerçek görev çalıştırma testi ayrıca yapılmalıdır.
- Veritabanı parolalarını GitHub'a yüklemeyin.
