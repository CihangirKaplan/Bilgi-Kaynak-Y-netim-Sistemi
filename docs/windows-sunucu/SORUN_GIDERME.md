# TKYS - Windows Sunucu Sorun Giderme

## Python bulunamıyor

```powershell
py --version
python --version
```

Python kurulumu ve PATH ayarlarını kontrol edin.

## Sanal ortam etkinleştirilemiyor

PowerShell yerine doğrudan sanal ortamdaki Python kullanılabilir:

```powershell
.\.venv\Scripts\python.exe -m pip --version
```

## PostgreSQL bağlantısı kurulamıyor

```powershell
Get-Service *postgres*
```

Veritabanı servisinin çalıştığını ve bağlantı ayarlarını kontrol edin.

## Port 8000 kullanılıyor

```powershell
Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
```

Portu kullanan işlemi belirlemeden sonlandırmayın.

## İstemci sunucuya bağlanamıyor

- Sunucunun doğru IP adresini kontrol edin.
- İki bilgisayarın ağ bağlantısını kontrol edin.
- Windows Güvenlik Duvarı kurallarını kontrol edin.
- FastAPI sunucusunun çalıştığından emin olun.

## Migration hatası

```powershell
alembic current
alembic heads
```

Veritabanı yedeği ve migration zinciri doğrulanmadan `upgrade` veya `downgrade` çalıştırmayın.

## Git güncelleme hatası

```powershell
git status -sb
git branch --show-current
```

Yerel değişiklikleri incelemeden `reset --hard` kullanmayın.
