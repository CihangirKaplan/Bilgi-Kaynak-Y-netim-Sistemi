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

## Geri yükleme (yedeğin işe yaradığını doğrulama)

Yedeği **yeni** bir veritabanına yükleyip kayıt sayılarını karşılaştırın:

    python scripts/veritabani_geri_yukle.py --hedef crkys_geri_yukleme_testi

Araç mevcut hiçbir veritabanının üzerine yazmaz. Doğrulamadan sonra test veritabanını kendiniz silin.

## Önemli

- Yedeklenen veritabanı .env dosyasındaki DB_NAME'dir (ana veritabanı). Yedekleme yalnızca okur,
  veritabanını değiştirmez. Başka bir veritabanı için: python scripts/veritabani_yedekle.py --database AD
- Daha önce kurulmuş görev varsa yeniden kurmaya gerek yoktur; betik güncellenince görev bir sonraki
  çalışmada ana veritabanını yedekler.
- Otomatik görev, bilgisayar kapalıyken çalışmaz.
- Windows üzerinde gerçek görev çalıştırma testi ayrıca yapılmalıdır.
- Yedek dosyaları, parolaların hash özetleri dahil tüm veritabanı verisini içerir; backups/ klasörünü paylaşmayın.
- Veritabanı parolalarını GitHub'a yüklemeyin.
