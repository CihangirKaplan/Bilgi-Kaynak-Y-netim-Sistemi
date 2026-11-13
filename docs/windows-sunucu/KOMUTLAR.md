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
```

Migration uygulamadan önce yedek ve veritabanı bağlantısı doğrulanmalıdır.

## FastAPI sunucusu

Proje klasöründe ve sanal ortam etkinleştirilmişken:

```powershell
python -m uvicorn sunucu:app --host 0.0.0.0 --port 8000
```

Sunucu başlatılmadan önce veritabanı bağlantısı ve migration sürümü kontrol edilmelidir.

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
