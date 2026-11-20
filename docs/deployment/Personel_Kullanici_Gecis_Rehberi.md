# Personel ve kullanıcı tablolarının birleşimi: geçiş rehberi

Bu rehber, `b9d4f7a2c613` numaralı migration'ı **önce bir kopyada deneyip, sonra gerçek veritabanına** uygulamak içindir.
Komutlar PowerShell içindir ve proje klasöründe, sanal ortam açıkken çalıştırılır.

## 1. Ne değişiyor

- `personel` tablosu kalkar; yerine aynı adlı, yazılabilir bir **görünüm** gelir. Eski sorgular, betikler ve uygulama koduna dokunulmaz.
- Personel bilgisi (`personel_id`, `personel_kodu`) `kullanicilar` tablosuna taşınır. **Eski `personel_id` değerleri aynen korunur**; hiçbir
  randevu, danışan, rezervasyon, etkinlik ya da denetim kaydının değeri değişmez.
- Tek aktiflik bayrağı kalır: `kullanicilar.aktif_mi`. Eskiden kullanıcı ve personel aktifliği farklı olan kayıtlar **güvenli yönde**
  birleştirilir: ikisinden biri pasifse hesap **pasif** olur ve bu, denetim kaydına yazılır.
- Geri alma mümkündür: `python -m alembic downgrade -1` tabloyu aynı kimliklerle yeniden kurar.

Ölçülen (sentetik veri: 120 bin randevu, 40 bin rezervasyon, 300 bin denetim kaydı, 3 bin kullanıcı): geçiş yaklaşık **0,6 saniye**, geri alma
yaklaşık **0,6 saniye**. Geçiş sırasında ilgili tablolar çok kısa süre kilitlenir; bu yüzden **sunucuyu durdurup** yapın.

## 2. Aşama A: bir kopyada deneme (gerçek veritabanına dokunmaz)

1. Güncel kodu alın:

    ```powershell
    git checkout develop
    git pull origin develop
    ```

2. Gerçek veritabanının yedeğini alın ve **yeni bir veritabanına** geri yükleyin (aracınız mevcut veritabanını silmez):

    ```powershell
    python scripts/backup/veritabani_yedekle.py
    python scripts/restore/veritabani_geri_yukle.py --hedef tkys_deneme
    ```

3. Bu PowerShell oturumunda betiklerin **kopyayı** kullanmasını sağlayın (`.env` dosyasına dokunmaz; pencereyi kapatınca sona erer):

    ```powershell
    $env:DB_NAME = "tkys_deneme"
    ```

4. Geçişten önce kontrol edin. Bu komut yalnızca okur ve verinin "sağlama özetini" `gecis_oncesi.json` dosyasına yazar:

    ```powershell
    python scripts/personel_gecis_kontrol.py on
    ```

    Çıktının sonunda `GEÇİŞE HAZIR.` görmelisiniz. `[UYARI]` satırı, aktifliği farklı kayıtlar olduğunu söyler: bu bir engel değildir ama
    hangi hesapların pasif olacağını gösterir. Bunları geçişten önce gözden geçirin.

5. Geçişi uygulayın ve doğrulayın:

    ```powershell
    python -m alembic upgrade head
    python scripts/sema_dogrula.py
    python scripts/personel_gecis_kontrol.py son
    ```

    `sema_dogrula.py` çıktısında `ŞEMA UYUMLU`, son komutun sonunda `GEÇİŞ DOĞRULANDI.` yazmalıdır. Herhangi biri `SORUN` derse **gerçek
    veritabanına geçmeyin** ve çıktıyı geliştiriciye gönderin.

6. Sunucuyu kopyaya bağlayıp (aynı PowerShell oturumunda) arayüzü elle gezin; kontrol listesi aşağıda (bölüm 4).

7. Geri almayı da deneyin:

    ```powershell
    python -m alembic downgrade -1
    python scripts/sema_dogrula.py
    python -m alembic upgrade head
    ```

8. Deneme bitince oturumu kopyadan ayırın ve kopyayı silin (kopyayı silmek isterseniz kendiniz silersiniz):

    ```powershell
    Remove-Item Env:DB_NAME
    ```

## 3. Aşama B: gerçek veritabanında

Aşama A'nın tamamı sorunsuz geçtiyse:

1. Sunucuyu **durdurun**. Kullanıcılara kısa bir bakım duyurusu yapın.
2. Yeni bir yedek alın (aşama A'dakinden sonra veri değişmiş olabilir):

    ```powershell
    python scripts/backup/veritabani_yedekle.py
    ```

3. Önceki aşamadan kalan `gecis_oncesi.json` dosyasını silin, sonra kontrol, geçiş ve doğrulama:

    ```powershell
    Remove-Item gecis_oncesi.json -ErrorAction SilentlyContinue
    python scripts/personel_gecis_kontrol.py on
    python -m alembic upgrade head
    python scripts/sema_dogrula.py
    python scripts/personel_gecis_kontrol.py son
    ```

4. Hepsi tamamsa sunucuyu başlatın ve bölüm 4'teki kontrol listesini gerçek veritabanında da bir kez gezin.
5. `gecis_oncesi.json` dosyası bir sonraki geçişe kadar saklanabilir; gerekmiyorsa silin (depoya eklemeyin).

## 4. Elle kontrol listesi (arayüz)

- Giriş yapın (psikolog, memur ve yönetici hesaplarıyla birer kez).
- **Kullanıcı & Personel:** listede tüm personel görünüyor mu, personel kodları doğru mu?
- Yeni bir kullanıcı oluşturun (personel kodu otomatik gelmeli), sonra pasife alıp tekrar aktif edin.
- **Randevu Yönetimi:** geçmiş ve gelecek randevular görünüyor mu? Psikolog adları doğru mu?
- Yeni bir randevu oluşturun ve iptal edin.
- **Danışanlar:** danışanların psikologları doğru mu?
- **Cihaz rezervasyonu:** mevcut rezervasyonlar ve yapan personel doğru mu? Yeni bir rezervasyon oluşturun.
- **Oda etkinlikleri:** mevcut etkinliklerin düzenleyenleri doğru mu?
- **Audit Kayıtları:** geçiş öncesi kayıtlar duruyor mu? Aktifliği uzlaştırılan hesaplar için "personel ve kullanici aktiflik bayraklari
  birlestirildi" ayrıntılı kayıtlar görünüyor mu?
- **Yönetim raporları:** sayılar geçiş öncesiyle tutarlı mı?

## 5. Sorun olursa

| Durum | Ne yapılır |
| :--- | :--- |
| Aşama A'da herhangi bir `SORUN` | Gerçek veritabanına geçmeyin; çıktıyı geliştiriciye gönderin. |
| Aşama B'de `son` komutu `SORUN` dedi | Sunucuyu başlatmayın. `python -m alembic downgrade -1` ile geri alın, ardından `python scripts/sema_dogrula.py` ile doğrulayın. |
| Geri alma da başarısız ya da veri bozuk görünüyor | Sunucuyu kapalı tutun ve **aldığınız yedekten** geri yükleyin (`scripts/restore/veritabani_geri_yukle.py`); sonra geliştiriciye bildirin. |
| Geçişten sonra bir arayüz sorunu fark ettiniz | Sunucuyu durdurup `downgrade -1` ile eski şemaya dönebilirsiniz; geri alma tabloyu aynı kimliklerle kurar. Geçişten sonra oluşan yeni kayıtlar korunur. |

**Geri almada tek kayıp:** aktifliği farklı olup uzlaştırılan hesapların eski "personel pasif / kullanıcı aktif" farkı geri gelmez (iki bayrak
yeniden aynı değeri taşır). Eski değer denetim kaydında saklıdır.

## 6. Bilinmesi gerekenler

- **Kısıtlı uygulama kullanıcısı (`tkys_uygulama`)** kullanıyorsanız yeni görünüm ve sayaç için ayrıca bir işlem gerekmez; yetkiler
  otomatik gelir (denendi). Migration'ı yine tam yetkili kimlikle (`DB_MIGRATION_*`) çalıştırın.
- Yedekleme ve geri yükleme betikleri değişmeden çalışır; görünüm ve tetikleyici yedeğe dahildir (denendi).
- Geçişten sonra uygulama kodu eskisi gibi `personel` adını kullanır. Kodun doğrudan `kullanicilar` tablosuna taşınması ve görünümün
  kaldırılması, ayrı ve isteğe bağlı sonraki adımlardır.
