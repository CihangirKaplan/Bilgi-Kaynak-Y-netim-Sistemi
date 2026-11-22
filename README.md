# TKYS — Bilgi ve Kaynak Yönetim Sistemi

Travma Uygulama ve Araştırma Merkezi'nin operasyonel süreçlerini (randevu, oda, cihaz envanteri, rezervasyon, bakım, kalibrasyon, arıza, dashboard, audit, yedekleme) merkezi ve izlenebilir biçimde yöneten çok kullanıcılı masaüstü yazılımıdır.

> Bu yazılım **klinik bilgi sistemi değildir.** Danışanlar yalnızca operasyonel bir kod ile temsil edilir; ad, T.C. kimlik no, tanı, terapi notu gibi kişisel/klinik veri sisteme girilmez.

## Mimari

```
PySide6 masaüstü istemci  ──REST──►  FastAPI sunucu  ──►  PostgreSQL
```

İstemci veritabanına doğrudan bağlanmaz; tüm işlemler kimlik doğrulaması ve rol kontrolü yapan API üzerinden geçer.

| Bileşen | Dosyalar |
|---|---|
| Sunucu (API, yetki, audit) | `sunucu.py`, `guvenlik.py`, `denetim.py`, `modeller.py` |
| İstemci (arayüz) | `login_ekrani.py`, `main_window.py`, `*_ekrani.py`, `*_ekranlari.py` |
| Veritabanı şeması | `alembic/` (migration'lar), `database/` |
| Yedekleme | `scripts/` |
| Testler | `tests/` |
| Dokümanlar | `docs/` |
| Kullanıcı kılavuzları | `user-manuals/` (rol bazlı: psikolog, danışma öğrencisi/proje asistanı, memur, müdür, sistem yöneticisi) |

## Gereksinimler

- **Windows 10/11, 64-bit** (istemci ve sunucu için)
- **Python 3.11 veya üstü** (64-bit). Python 3.10 ve altında bağımlılıklar kurulamaz.
- **PostgreSQL** (yalnızca sunucu bilgisayarında gerekir; istemci bilgisayarlarında gerekmez)

## Kurulum (geliştirme ortamı)

PowerShell'de, proje klasöründe:

**1) Sanal ortam ve bağımlılıklar**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

**2) Veritabanını oluştur** (PostgreSQL'de boş bir veritabanı, örneğin `crkys`):
```powershell
psql -U postgres -c "CREATE DATABASE crkys;"
```

**3) `.env` dosyasını hazırla**
```powershell
Copy-Item .env.example .env
```
`.env` içindeki `DB_*` değerlerini kendi veritabanına göre doldur ve güçlü bir `JWT_SECRET` üret:
```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```
`.env` dosyası `.gitignore` ile gizlidir, **GitHub'a gönderilmemelidir.** Gizli bilgiler (şifre, anahtar) koda yazılmaz, yalnızca `.env` içinde durur.

**4) Tabloları oluştur**
```powershell
python -m alembic upgrade head
```

**5) Geliştirme kullanıcılarını ekle** (isteğe bağlı)
```powershell
> **Dikkat:** Bu komut yalnızca yerel `crkys_alembic_test` veritabanında, `TKYS_PG_TEST_ONAY=EVET` onayıyla kullanılmalıdır. Canlı veritabanında çalıştırılmamalıdır.

python -m scripts.ilk_kurulum
```
Bu betik her rol için (psikolog, memur, müdür, danışma öğrencisi, proje asistanı, admin) bir test kullanıcısı oluşturur. Parolaları betiğin içinde yazar ve bilinen parolalardır, bu yüzden **yalnızca geliştirme ortamında** kullanın, gerçek (canlı) veritabanında çalıştırmayın. Canlı kurulum için `docs/deployment/Sunucu_Kurulum_Kilavuzu.md` dosyasına ve `scripts/ilk_admin_olustur.py` betiğine bakın.

## Çalıştırma

**Sunucu** (bir terminalde):
```powershell
uvicorn server.sunucu:app --reload
```
API dokümantasyonu (varsayılan kapalıdır; açmak için `.env` dosyasına `TKYS_API_DOCS=1` yazıp sunucuyu yeniden başlatın): http://127.0.0.1:8000/docs

**İstemci** (başka bir terminalde):
```powershell
python -m client.login_ekrani
```
İstemci varsayılan olarak `http://127.0.0.1:8000` adresindeki sunucuya bağlanır. Sunucu başka bir bilgisayardaysa adresi şöyle verin:
```powershell
$env:TKYS_API_URL = "http://SUNUCU_ADRESI:8000"
python -m client.login_ekrani
```

## Roller

Menü ve işlemler rol bazlı yetkilendirilir: **Psikolog, Memur, Müdür, Danışma Öğrencisi, Proje Asistanı, Admin.** Yetki sunucuda kontrol edilir; arayüzde bir menünün gizli olması tek başına güvenlik sayılmaz.

## Testler

```powershell
python -m pytest -q tests
```

Çoğu test sahte (mock) veritabanı bağlantısıyla çalışır ve gerçek veritabanına dokunmaz.

**Gerçek PostgreSQL gerektiren testler** (QA-001) ana veritabanını korumak için kilitlidir: yalnızca ayrı bir test veritabanında (`crkys_alembic_test`, önce `alembic upgrade head` ile hazırlanır) ve `TKYS_PG_TEST_ONAY=EVET` ortam değişkeni verilirse çalışır. Bu koşullar yoksa bu testler bilerek başarısız olur.

Depoda düz yazılı şifre/anahtar bulunmadığını doğrulayan bir test de vardır (`tests/security/test_gizli_bilgi_taramasi.py`).

## Yedekleme

PostgreSQL yedekleme, rotasyon ve geri yükleme betikleri `scripts/` altındadır. Hepsi varsayılan olarak `.env` içindeki `DB_NAME` veritabanı (uygulamanın kullandığı ana veritabanı) için çalışır; başka bir veritabanı için `--database` verilir.

| Amaç | Komut |
|---|---|
| Yedek al (`backups/<veritabani>_<tarih>.dump`) | `python scripts/backup/veritabani_yedekle.py` |
| Yedek al + 14 günden eski yedekleri sil (en yeni 3 yedek korunur) | `python scripts/backup/otomatik_yedekleme.py` |
| Eski yedekleri önizle / sil | `python scripts/backup/yedek_rotasyonu.py --days 14` (silmek için `--apply`; en yeni 3 yedek her zaman korunur, `--keep` ile değişir) |
| Yedeği **yeni** veritabanına geri yükle ve kontrol et | `python scripts/restore/veritabani_geri_yukle.py --hedef crkys_geri_yukleme_testi` |

- Yedekleme yalnızca okur, veritabanını değiştirmez. Rotasyon yalnızca seçilen veritabanının, tam ad biçimine uyan yedeklerini siler.
- Geri yükleme **hiçbir mevcut veritabanının üzerine yazmaz**: hedef veritabanı yeni olmalıdır, canlı veritabanı hedef olarak kabul edilmez, hata olursa oluşturulan yarım veritabanı silinir. Sonunda tablo satır sayıları ve migration sürümü yedeğin alındığı veritabanıyla yan yana gösterilir.
- Windows'ta zamanlanmış görev kurulumu için `scripts/windows/README.md` dosyasına bakın.

## Dokümanlar

- `docs/D01_Process_Analysis.md`, `docs/requirements/D02_Requirements_v1.md`: süreç ve gereksinim analizi
- `docs/architecture/`: mimari (D05), veri sözlüğü (D04), tehdit modeli (D06)
- `user-manuals/README.md`: **kullanıcı kılavuzları** (hangi rol hangi kılavuzu okumalı, varsayılan yetki tablosu)
- `docs/API/Uc_Listesi.md`: API uç ve izin listesi (`python scripts/api_uc_listesi_uret.py` ile yeniden üretilir)
- `docs/security/README.md`: uygulanan güvenlik önlemleri özeti
- `docs/test-reports/QA-001_Kalite_Test_Raporu.md` ve `docs/test-reports/`: kalite ve performans test raporları

## Katkı kuralları

- `main` ve `develop` dallarına doğrudan kod yazılmaz. Her iş için `develop`'tan bir **feature/fix branch** açılır.
- İş bitince **Pull Request** açılır (hedef: `develop`); en az bir başka ekip üyesi inceler.
- Değişikliğin testi yazılır ve testler geçmeden birleştirilmez.
- Yeni bağımlılık eklerken `requirements.txt` temiz bir sanal ortamda kurularak doğrulanır.
