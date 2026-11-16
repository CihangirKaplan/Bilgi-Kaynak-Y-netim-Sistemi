# TKYS - Windows Sunucu Komutları

Komutlar Windows PowerShell içindir.

## Bilgisayar bilgileri

```powershell
hostname
Get-ComputerInfo | Select-Object WindowsProductName, OsArchitecture
```

## IP adresi

```powershell
ipconfig
Get-NetIPAddress -AddressFamily IPv4
```

## Python ve Git

```powershell
python --version
git --version
```

## PostgreSQL

```powershell
Get-Service *postgres*
```

## Git güncelleme

Proje klasöründe:

```powershell
git status -sb
git switch develop
git pull --ff-only origin develop
```

## Alembic kontrolü

Proje ortamında:

```powershell
alembic current
alembic heads
python scripts/sema_dogrula.py
```

Migration uygulamadan önce yedek ve veritabanı bağlantısı doğrulanmalıdır.
`sema_dogrula.py`, tabloların migration'ların üretmesi gereken şemayla aynı olduğunu doğrular (sonuç: `ŞEMA UYUMLU`).


## TKYS sunucusunu elle başlatma

Windows PowerShell'de, proje klasöründe ve sanal ortam etkinleştirilmişken:

```powershell
python scripts/windows/sunucu_baslat.py
```

Bu betik PostgreSQL bağlantısını bekler, FastAPI'yi başlatır ve sunucu beklenmedik şekilde kapanırsa yeniden başlatır.

## Windows açılışında otomatik başlatma

Önce `.env` ayarlarını, veritabanı bağlantısını ve migration durumunu doğrulayın.

Yönetici yetkili PowerShell'de:

```powershell
python scripts/windows/sunucu_kurulum.py
```

Bu işlem `TKYS_Sunucu` adlı zamanlanmış görevi oluşturur.

Görevi kontrol etmek için:

```powershell
schtasks /Query /TN TKYS_Sunucu
```

Görevi kaldırmak için:

```powershell
python scripts/windows/sunucu_kurulum.py --kaldir
```

Varsayılan görev SYSTEM hesabıyla çalışır. Windows üzerinde dosya izinleri, veritabanı erişimi ve `logs/sunucu.log` kontrol edilmelidir.

## Yerel API kontrolü

```powershell
Test-NetConnection 127.0.0.1 -Port 8000
```

## İstemci bilgisayarından bağlantı kontrolü

SUNUCU_IP yerine gerçek sunucu IP adresini yazın.

```powershell
ping SUNUCU_IP
Test-NetConnection SUNUCU_IP -Port 8000
```

## Sunucuyu durdurma

Sunucunun çalıştığı terminalde Ctrl+C.
