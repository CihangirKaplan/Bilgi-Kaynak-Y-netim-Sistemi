# 6. Hafta - Yedekleme ve Geri Yukleme Test Raporu

Tarih: 20.10.2026
Sorumlu: Ogrenci C
Durum: Yedekleme modulu temel testleri basarili.
Not: 6. haftanin ekip genelindeki calismalari devam etmektedir.

## 1. Otomatik Testler

Komut:
python -m pytest tests/test_backup_restore.py tests/test_otomatik_yedekleme.py tests/test_windows_backup_setup.py -v

Sonuc: 7 passed in 0.68s

Dogrulanan senaryolar:
- Yedi gunluk yedek rotasyonu onizlemesi
- Eski yedeklerin silinmesi ve yeni yedeklerin korunmasi
- Gecersiz saklama suresinin kontrolu
- Yedekleme hatasinda eksik dosyanin temizlenmesi
- Basarili yedeklemeden sonra rotasyonun calismasi
- Basarisiz yedeklemeden sonra rotasyonun calismamasi
- Windows zamanlanmis gorev olusturma test senaryosu

## 2. PostgreSQL Geri Yukleme Dogrulamasi

Test veritabani: crkys_restore_test
Tablo sayisi: 24

Geri yuklenen veritabanina baglanti saglandi.
Tablo ve kayit sayilari sorgulanabildi.

## 3. FastAPI Dogrulamasi

Test veritabani: crkys_restore_test

GET /api/odalar:
- HTTP durum kodu: 200
- Yanit: []

Cihaz listeleme fonksiyonu:
- Gercek bir cihaz kaydi basariyla okundu.
- Envanter kodu: TEST-ISSUE-115

## 4. Sinirlamalar

- Tum uygulama modulleri test edilmedi.
- Masaustu istemci entegrasyonu henuz dogrulanmadi.
- Cihaz endpointinin HTTP uzerinden yetkilendirmesi test edilmedi.
- Windows kurulumu gercek bir Windows bilgisayarda dogrulanmadi.
- Ekip genelinde 6. hafta calismalari henuz tamamlanmadi.

## 5. Genel Sonuc

Yedekleme otomasyonuna ait 7 otomatik test basarili oldu.
Geri yuklenen PostgreSQL veritabanina baglanti ve FastAPI
uzerinden temel veri okuma islemleri dogrulandi.
Kalan entegrasyon ve ekip testleri sonraki asamalarda yapilacaktir.
