# TKYS - Windows Sunucu Kurulumu

Bu rehber, TKYS uygulamasını Windows sunucu bilgisayarında çalıştırmak için hazırlanmıştır.

## 1. Sistem kontrolü

PowerShell'de:

```powershell
hostname
python --version
git --version
Get-Service *postgres*
Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object {$_.IPAddress -notlike "127.*"} |
    Select-Object InterfaceAlias, IPAddress
```

## 2. Proje kodlarını alma

Git kurulduktan sonra mevcut TKYS reposunu Windows bilgisayarına klonlayın.

```powershell
git clone https://github.com/CihangirKaplan/Bilgi-Kaynak-Y-netim-Sistemi.git
cd Bilgi-Kaynak-Y-netim-Sistemi
git switch develop
git pull --ff-only origin develop
```

## 3. Python ortamı

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python --version
```

Bağımlılıkları projenin güncel bağımlılık dosyasına göre kurun.

## 4. PostgreSQL

- PostgreSQL servisinin çalıştığını doğrulayın.
- Veritabanı bağlantı ayarlarını kontrol edin.
- Var olan veritabanını silmeyin veya üzerine yazmayın.
- Migration öncesinde yedek alın.
- Alembic sürümünü kontrol edin.

## 5. Güvenlik

- Parolaları, JWT anahtarlarını ve `.env` dosyalarını GitHub'a yüklemeyin.
- Sunucu bilgisayarında kişisel hesap oturumlarını açık bırakmayın.
- Ağ erişimini yalnızca gerekli bilgisayarlarla sınırlandırın.
