
TKYS — Bilgi ve Kaynak Yönetim Sistemi
Travma Uygulama ve Araştırma Merkezi'nin operasyonel süreçlerini (randevu, oda, cihaz envanteri, rezervasyon, bakım, kalibrasyon, arıza, dashboard, audit, yedekleme) merkezi ve izlenebilir biçimde yöneten çok kullanıcılı masaüstü yazılımıdır.

Bu yazılım klinik bilgi sistemi değildir. Danışanlar yalnızca operasyonel bir kod ile temsil edilir; ad, T.C. kimlik no, tanı, terapi notu gibi kişisel/klinik veri sisteme girilmez.

Mimari
PySide6 masaüstü istemci  ──REST──►  FastAPI sunucu  ──►  PostgreSQL
İstemci veritabanına doğrudan bağlanmaz; tüm işlemler kimlik doğrulaması ve rol kontrolü yapan API üzerinden geçer.

Bileşen	Dosyalar
Sunucu (API, yetki, audit)	sunucu.py, guvenlik.py, denetim.py, modeller.py
İstemci (arayüz)	login_ekrani.py, main_window.py, *_ekrani.py, *_ekranlari.py
Veritabanı şeması	alembic/ (migration'lar), database/
Yedekleme	scripts/
Testler	tests/
Dokümanlar	docs/
Gereksinimler
Windows 10/11, 64-bit (istemci ve sunucu için)
Python 3.11 veya üstü (64-bit). Python 3.10 ve altında bağımlılıklar kurulamaz.
PostgreSQL (yalnızca sunucu bilgisayarında gerekir; istemci bilgisayarlarında gerekmez)
Kurulum (geliştirme ortamı)
PowerShell'de, proje klasöründe:

1) Sanal ortam ve bağımlılıklar

python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
2) Veritabanını oluştur (PostgreSQL'de boş bir veritabanı, örneğin crkys):

psql -U postgres -c "CREATE DATABASE crkys;"
3) .env dosyasını hazırla

Copy-Item .env.example .env
.env içindeki DB_* değerlerini kendi veritabanına göre doldur ve güçlü bir JWT_SECRET üret:

python -c "import secrets; print(secrets.token_urlsafe(48))"
.env dosyası .gitignore ile gizlidir, GitHub'a gönderilmemelidir. Gizli bilgiler (şifre, anahtar) koda yazılmaz, yalnızca .env içinde durur.

4) Tabloları oluştur

python -m alembic upgrade head
5) Geliştirme kullanıcılarını ekle (isteğe bağlı)

python ilk_kurulum.py
Bu betik her rol için (psikolog, memur, müdür, danışma öğrencisi, proje asistanı, admin) bir test kullanıcısı oluşturur. Parolaları betiğin içinde yazar ve bilinen parolalardır, bu yüzden yalnızca geliştirme ortamında kullanın, gerçek (canlı) veritabanında çalıştırmayın. Canlı kurulum için docs/Sunucu_Kurulum_Kilavuzu.md dosyasına ve scripts/ilk_admin_olustur.py betiğine bakın.

Çalıştırma
Sunucu (bir terminalde):

uvicorn sunucu:app --reload
API dokümantasyonu: http://127.0.0.1:8000/docs

İstemci (başka bir terminalde):

python login_ekrani.py
İstemci varsayılan olarak http://127.0.0.1:8000 adresindeki sunucuya bağlanır. Sunucu başka bir bilgisayardaysa adresi şöyle verin:

$env:TKYS_API_URL = "http://SUNUCU_ADRESI:8000"
python login_ekrani.py
Roller
Menü ve işlemler rol bazlı yetkilendirilir: Psikolog, Memur, Müdür, Danışma Öğrencisi, Proje Asistanı, Admin. Yetki sunucuda kontrol edilir; arayüzde bir menünün gizli olması tek başına güvenlik sayılmaz.

Testler
python -m pytest -q tests
Çoğu test sahte (mock) veritabanı bağlantısıyla çalışır ve gerçek veritabanına dokunmaz.

Gerçek PostgreSQL gerektiren testler (QA-001) ana veritabanını korumak için kilitlidir: yalnızca ayrı bir test veritabanında (crkys_alembic_test, önce alembic upgrade head ile hazırlanır) ve TKYS_PG_TEST_ONAY=EVET ortam değişkeni verilirse çalışır. Bu koşullar yoksa bu testler bilerek başarısız olur.

Depoda düz yazılı şifre/anahtar bulunmadığını doğrulayan bir test de vardır (tests/test_gizli_bilgi_taramasi.py).

Yedekleme
PostgreSQL yedekleme, rotasyon ve geri yükleme betikleri scripts/ altındadır. Hepsi varsayılan olarak .env içindeki DB_NAME veritabanı (uygulamanın kullandığı ana veritabanı) için çalışır; başka bir veritabanı için --database verilir.

Amaç	Komut
Yedek al (backups/<veritabani>_<tarih>.dump)	python scripts/veritabani_yedekle.py
Yedek al + 7 günden eski yedekleri sil	python scripts/otomatik_yedekleme.py
Eski yedekleri önizle / sil	python scripts/yedek_rotasyonu.py --days 7 (silmek için --apply)
Yedeği yeni veritabanına geri yükle ve kontrol et	python scripts/veritabani_geri_yukle.py --hedef crkys_geri_yukleme_testi
Yedekleme yalnızca okur, veritabanını değiştirmez. Rotasyon yalnızca seçilen veritabanının, tam ad biçimine uyan yedeklerini siler.
Geri yükleme hiçbir mevcut veritabanının üzerine yazmaz: hedef veritabanı yeni olmalıdır, canlı veritabanı hedef olarak kabul edilmez, hata olursa oluşturulan yarım veritabanı silinir. Sonunda tablo satır sayıları ve migration sürümü yedeğin alındığı veritabanıyla yan yana gösterilir.
Windows'ta zamanlanmış görev kurulumu için scripts/windows/README.md dosyasına bakın.
Dokümanlar
docs/D01_Process_Analysis.md, docs/D02_Requirements_v1.md: süreç ve gereksinim analizi
docs/architecture/: mimari (D05), veri sözlüğü (D04), tehdit modeli (D06)
docs/QA-001_Kalite_Test_Raporu.md ve docs/test-reports/: kalite ve performans test raporları
Katkı kuralları
main ve develop dallarına doğrudan kod yazılmaz. Her iş için develop'tan bir feature/fix branch açılır.
İş bitince Pull Request açılır (hedef: develop); en az bir başka ekip üyesi inceler.
Değişikliğin testi yazılır ve testler geçmeden birleştirilmez.
Yeni bağımlılık eklerken requirements.txt temiz bir sanal ortamda kurularak doğrulanır.
