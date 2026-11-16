# TKYS Sunucu Kurulum Kılavuzu (Windows)

Bu kılavuz, merkezdeki bir masaüstü bilgisayarı TKYS sunucusu yapmak içindir.
Sunucu bilgisayarında PostgreSQL ve FastAPI sunucusu çalışır; diğer bilgisayarlar
yalnızca istemci uygulamasını çalıştırır ve ağdan sunucuya bağlanır.

Komutlar PowerShell içindir. Sırayla ilerleyin; bir adım hata verirse sonrakine geçmeyin.

## 1. Gereksinimler (yalnızca sunucu bilgisayarı)

- Windows 10 veya 11
- Python 3.12 veya üstü (kurarken "Add python.exe to PATH" kutusunu işaretleyin)
- PostgreSQL 16 veya üstü (kurulumda belirlediğiniz `postgres` parolasını not edin)
- Git
- Bilgisayarın ağda sabit bir adresi olması (aşağıdaki 7. adım)

## 2. Projeyi indirin

    git clone https://github.com/CihangirKaplan/Bilgi-Kaynak-Y-netim-Sistemi.git
    cd Bilgi-Kaynak-Y-netim-Sistemi
    git checkout develop

## 3. Sanal ortam ve bağımlılıklar

    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install -r requirements.txt

## 4. Veritabanı ve `.env`

Boş veritabanını oluşturun:

    psql -U postgres -c "CREATE DATABASE crkys;"

`psql` bulunamazsa PostgreSQL'in `bin` klasörünün tam yolunu kullanın
(örn. `& "C:\Program Files\PostgreSQL\18\bin\psql.exe" ...`).

`.env` dosyasını hazırlayın:

    Copy-Item .env.example .env
    python -c "import secrets; print(secrets.token_urlsafe(48))"

`.env` içindeki `DB_PASSWORD` alanına PostgreSQL parolanızı, `JWT_SECRET` alanına
yukarıda üretilen değeri yazın. `.env` dosyasını kimseyle paylaşmayın ve GitHub'a göndermeyin.

## 5. Tabloları oluşturun

    python -m alembic upgrade head
    python -m alembic current

Son komut `(head)` ile biten bir sürüm göstermelidir.

`alembic current` yalnızca "hangi sürümdeyim" bilgisini verir. Tabloların gerçekten doğru kurulduğunu da doğrulayın:

    python scripts/sema_dogrula.py

Beklenen son satır: `SONUÇ: ŞEMA UYUMLU.` (araç ayrıntıları aşağıdaki "Veritabanı şeması kontrolü" bölümünde.)

## 6. İlk yönetici hesabı

Canlı veritabanında **`scripts/ilk_kurulum.py` çalıştırmayın**: bilinen parolalı test kullanıcıları ekler.
Onun yerine:

    python scripts/ilk_admin_olustur.py

Betik `admin` kullanıcısını oluşturur ve rastgele bir **geçici parolayı ekrana bir kez** yazar.
Parolayı hemen not edin; ilk girişte yeni parola belirlemeniz istenir. Veritabanında zaten
bir ADMIN varsa betik hiçbir şey eklemez. Diğer kullanıcıları ve rolleri, admin ile giriş yaptıktan
sonra uygulamadaki Kullanıcı & Personel ekranından ekleyin.

**Uygulamadan yönetici (ADMIN) hesabı açılamaz** (bilerek; güvenlik için yalnızca sunucu bilgisayarında açılır).
İkinci bir yönetici gerekiyorsa sunucu bilgisayarında şunu çalıştırın:

    python scripts/ilk_admin_olustur.py --ek-yonetici

Araç mevcut yöneticileri gösterir, yeni kullanıcı adını sorar ve **EVET** yazarak onayınızı ister. Ardından rastgele bir
geçici parolayı **bir kez** yazar; hesap ilk girişte yeni parola belirlemek zorundadır ve olay denetim kaydına yazılır.

### Yönetici parolasını unuttuysanız

Normal kullanıcılar giriş ekranındaki **Şifremi unuttum** ile talep açar, bir yönetici parolayı sıfırlar.
Parolasını unutan kişi **tek yöneticiyse** talebi görecek kimse kalmaz; bu durumda yönetici hesabı
**sunucu bilgisayarında** şu araçla kurtarılır (veritabanı ayarlarına erişim gerektirdiği için yalnızca
sistem sorumlusu yapabilir):

- Kolay yol: sunucu bilgisayarında `scripts\windows\admin_parola_kurtar.bat` dosyasına çift tıklayın.
- Ya da proje klasöründe: `python scripts/admin_parola_kurtar.py`

Araç yönetici hesaplarını listeler, hangisi olduğunu sorar ve **EVET** yazarak onayınızı ister. Ardından
rastgele bir geçici parolayı ekrana **bir kez** yazar; hemen not edin. Uygulamaya bu parolayla giriş yapın,
ekran sizden yeni parola belirlemenizi ister. Araç hatalı giriş kilidini de kaldırır, bekleyen parola
talebini kapatır ve olayı denetim kaydına (`PASSWORD_RESET`) yazar. Yalnızca yönetici (ADMIN) hesapları
için çalışır; diğer kullanıcıların parolasını yönetici uygulamadan sıfırlar.

**Öneri:** Böyle bir durumla karşılaşmamak için sistemde en az **iki** yönetici hesabı bulundurun; biri
parolasını unutursa diğeri, Kullanıcı & Personel ekranındaki parola taleplerinden onu sıfırlayabilir. İkinci yönetici,
yukarıdaki `--ek-yonetici` seçeneğiyle sunucu bilgisayarında açılır.

### Acil durum: yönetici hesabına kimse giremiyorsa

Sırayla şu üç yola bakın; ilk yol yeterliyse diğerlerine gerek kalmaz.

1. **Başka bir yönetici varsa (en kolayı).** Şifresini unutan yönetici, giriş ekranındaki **Şifremi unuttum**
   penceresine kendi kullanıcı adını yazıp **Yöneticiye Bildir**'e basar. Diğer yönetici, ana panelde ve zil
   simgesinde **Parola Talepleri** bildirimini görür. Önce şifresini unutan kişinin kimliğini yüz yüze ya da
   telefonla doğrular, sonra Kullanıcı & Personel ekranından **Parolayı Sıfırla** der ve geçici parolayı o kişiye
   verir.
2. **Tüm yöneticiler şifresini unuttuysa.** Sunucu bilgisayarında kurtarma aracı çalıştırılır
   (`scripts\windows\admin_parola_kurtar.bat`). Araç bütün yöneticileri listeler. Biri seçilip kurtarılır; o kişi
   giriş yaptıktan sonra diğer yöneticinin parolasını uygulamadan sıfırlayabilir (ya da araç ikinci kez çalıştırılır).
3. **Sunucu bilgisayarına ya da `.env` dosyasına da ulaşılamıyorsa.** Veritabanı parolasını (`.env` içindeki
   `DB_PASSWORD` ve PostgreSQL `postgres` kullanıcısının parolası) bilen kişi veritabanı yöneticisi olarak
   müdahale eder. Bu teknik bir iştir; bir yazılım geliştiriciden yardım alın. Hiçbir veri kaybolmaz, en kötü
   durumda 10. bölümdeki yedekten geri dönülür.

Böyle bir durumda iş yavaşlamasın diye kurulumdan hemen sonra şunları yapın:

- [ ] En az **iki yönetici** hesabı açın (ikincisi için `python scripts/ilk_admin_olustur.py --ek-yonetici`) ve bunları
      **farklı kişilere** verin.
- [ ] `.env` içindeki `DB_PASSWORD` ile `postgres` parolasını **sunucu bilgisayarının dışında** güvenli bir yerde
      saklayın (kilitli çekmecede zarf ya da şifre yöneticisi). Parolaları kimseyle paylaşmayın.
- [ ] Kurtarma yolunu bilen **en az iki kişi** olsun (örneğin sistem sorumlusu ve müdür).
- [ ] Kurtarma aracını bir kez **deneme yönetici hesabıyla** deneyin; gerçek bir sorunda ilk kez çalıştırmayın.
- [ ] Yedeklerin bir kopyası sunucu bilgisayarının dışında dursun (10. bölüm).

Geçici parolayı vermeden önce her zaman kullanıcının kimliğini doğrulayın; parolayı telefonda ya da mesajla
değil, mümkünse yüz yüze iletin.

## 6A. Önerilen güvenlik adımı: sunucuyu kısıtlı veritabanı kullanıcısıyla çalıştırın

Şimdiye kadar sunucu veritabanına `postgres` (tam yetkili) kullanıcıyla bağlanıyordu. Sunucuda bir güvenlik açığı
çıksa, saldırgan veritabanının tamamını silebilir ya da değiştirebilirdi. Bu bölümde sunucu için **yalnızca veri okuyup
yazabilen** ayrı bir kullanıcı (`tkys_uygulama`) oluşturulur. Bu kullanıcı:

- tablo oluşturamaz, silemez, değiştiremez; süper kullanıcı değildir,
- denetim kayıtlarına yalnızca satır ekleyebilir (değiştiremez, silemez),
- ileride güncellemeyle eklenen yeni tablolara otomatik olarak okuma/yazma yetkisi alır.

Tablo oluşturma ve güncelleme işleri (`alembic upgrade head`, yedekten geri yükleme) tam yetkili kullanıcıyla yapılmaya
devam eder; onun bilgileri `.env` içinde ayrıca tutulur. Bu adım **zorunlu değildir**; yapılmazsa sistem eskisi gibi çalışır.
Ofis sunucusuna kurarken yapmanız önerilir.

**1. Şu anki tam yetkili kullanıcının bilgisini "şema kullanıcısı" olarak da yazın.** `.env` dosyasında `DB_USER` ve
`DB_PASSWORD` satırlarında yazan değerleri aşağıdaki iki satıra aynen kopyalayın (örnek):

    DB_MIGRATION_USER=postgres
    DB_MIGRATION_PASSWORD=BURAYA_POSTGRES_PAROLASI

**2. Önce önizleme çalıştırın** (hiçbir şeyi değiştirmez, ne yapacağını gösterir):

    python scripts/uygulama_kullanicisi_olustur.py

**3. Kullanıcıyı oluşturun:**

    python scripts/uygulama_kullanicisi_olustur.py --uygula

Araç kullanıcıyı oluşturur, yetkilerini ayarlar ve **gerçekten kısıtlı olduğunu kendisi doğrular**. Sonunda rastgele bir
parolayı ekrana **yalnızca bir kez** yazar; hemen kopyalayın.

**4. `.env` dosyasındaki `DB_USER` ve `DB_PASSWORD` satırlarını değiştirin:**

    DB_USER=tkys_uygulama
    DB_PASSWORD=ARACIN_GOSTERDIGI_YENI_PAROLA

`DB_MIGRATION_USER` ve `DB_MIGRATION_PASSWORD` satırları olduğu gibi kalmalıdır.

**5. Sunucuyu yeniden başlatın ve deneyin:**

    schtasks /End /TN TKYS_Sunucu
    schtasks /Run /TN TKYS_Sunucu

Tarayıcıda `http://SUNUCU_ADRESI:8000/api/saglik` açılmalı, uygulamadan giriş yapabilmelisiniz.

**Sonrasında bilmeniz gerekenler**

- **Güncelleme** (11. bölüm): `python -m alembic upgrade head` komutu `DB_MIGRATION_*` bilgisiyle kendiliğinden tam yetkiyle
  çalışır; yeni tablolar `tkys_uygulama` kullanıcısına otomatik yetkilendirilir.
- **Yedekleme** (10. bölüm) kısıtlı kullanıcıyla çalışır; yalnızca okur.
- **Yedekten geri yükleme** yeni veritabanı oluşturduğu için `DB_MIGRATION_*` bilgisi gerekir. Yoksa araç bunu açıkça söyler.
- Parolayı unutursanız ya da yenilemek isterseniz: `python scripts/uygulama_kullanicisi_olustur.py --uygula --parolayi-yenile`
  (yeni parolayı `.env` içindeki `DB_PASSWORD` satırına yazın).
- **`.env` dosyası artık tam yetkili parolayı da içerir.** Dosyaya yalnızca sunucuyu yöneten kişinin erişebildiğinden emin olun;
  GitHub'a asla göndermeyin (zaten `.gitignore` ile gizlidir).
- Eski haline dönmek için `.env` içinde `DB_USER` ve `DB_PASSWORD` satırlarını tekrar tam yetkili kullanıcınınkilerle değiştirmeniz yeter.

## 7. Sunucuyu ağa açın

Sunucu bilgisayarının adresini öğrenin:

    ipconfig

"IPv4 Address" satırındaki adresi (örn. `192.168.1.20`) not edin. Bu adresin değişmemesi için
modem/ağ yöneticisinden bu bilgisayara sabit (rezerve) adres verilmesini isteyin.

Sunucuyu tüm ağ arayüzlerinde başlatın (`--reload` canlıda kullanılmaz):

    uvicorn server.sunucu:app --host 0.0.0.0 --port 8000

Windows Güvenlik Duvarı'nda 8000 numaralı port için gelen bağlantıya izin verin
(yönetici PowerShell'de):

    New-NetFirewallRule -DisplayName "TKYS Sunucu" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow -Profile Private

Bu kural yalnızca "Özel" (Private) ağ profilinde geçerlidir. Ağınız "Genel" görünüyorsa
ağ yöneticinize danışın. **PostgreSQL portunu (5432) ağa açmayın;** istemciler veritabanına
doğrudan değil, yalnızca sunucu üzerinden bağlanır.

## 8. Sunucunun bilgisayar açılınca kendiliğinden başlaması

Her sabah elle terminal açıp `uvicorn` yazmamak için sunucu, Windows Görev Zamanlayıcı ile bilgisayar
açılınca kendiliğinden başlatılır. **Yönetici olarak açılmış PowerShell'de**, proje klasöründe,
sanal ortam etkinken:

    python scripts/windows/sunucu_kurulum.py

Bu komut `TKYS_Sunucu` adlı görevi oluşturur. Görev, bilgisayar açıldıktan 30 saniye sonra (kimse giriş
yapmasa da) `scripts/windows/sunucu_baslat.py` betiğini çalıştırır. Betik önce PostgreSQL'in hazır olmasını
bekler, sunucuyu başlatır ve sunucu beklenmedik şekilde kapanırsa 10 saniye sonra yeniden başlatır.

Hemen denemek için (bilgisayarı yeniden başlatmadan):

    schtasks /Run /TN TKYS_Sunucu

Sunucunun çalıştığını `http://SUNUCU_ADRESI:8000/api/saglik` adresini tarayıcıda açarak görebilirsiniz (`{"durum":"calisiyor"}` yazmalı).
Sunucunun çıktıları ve hataları `logs\sunucu.log` dosyasına yazılır (5 MB'ı aşınca yeni dosyaya geçilir).

Sorun çıkarsa:

- Görev çalışmıyorsa ya da sunucu açılmıyorsa önce `logs\sunucu.log` dosyasına bakın.
- Python yolu başka bir kullanıcıya aitse ve "SYSTEM" hesabı ona erişemiyorsa, görevi bunun yerine
  kullanıcı giriş yapınca başlatın: `python scripts/windows/sunucu_kurulum.py --oturum`
  (bu durumda bilgisayar açıldıktan sonra o kullanıcının giriş yapması gerekir).
- Görevi silmek için: `python scripts/windows/sunucu_kurulum.py --kaldir`

Sunucu kodunu güncelledikten sonra çalışan sunucunun yeni kodu alması için görevi yeniden başlatın:

    schtasks /End /TN TKYS_Sunucu
    schtasks /Run /TN TKYS_Sunucu

## 9. İstemci bilgisayarlarında

Her istemcide proje kurulu olmalı (3. adımdaki sanal ortam ve bağımlılıklar yeterli;
PostgreSQL gerekmez). Sunucu adresini verip uygulamayı açın:

    $env:TKYS_API_URL = "http://192.168.1.20:8000"
    python -m client.login_ekrani

Bağlanamazsa önce istemci bilgisayarın tarayıcısından `http://192.168.1.20:8000/api/saglik`
adresini açmayı deneyin. Açılmıyorsa sorun ağ/güvenlik duvarındadır, uygulamada değil.

## 10. Yedekleme

Yedekleme için `scripts/windows/README.md` dosyasındaki adımları uygulayın
(günlük otomatik yedek, 7 günlük rotasyon, geri yükleme doğrulaması).
Yedeklerin en az bir kopyasını sunucu bilgisayarının dışında (harici disk gibi) saklayın.

## 11. Güncelleme

Yeni sürüm geldiğinde sunucu bilgisayarında, sunucuyu durdurduktan sonra:

    git checkout develop
    git pull origin develop
    python -m pip install -r requirements.txt
    python scripts/backup/veritabani_yedekle.py
    python -m alembic upgrade head
    python scripts/sema_dogrula.py
    uvicorn server.sunucu:app --host 0.0.0.0 --port 8000

Migration'dan önce her zaman yedek alın. `sema_dogrula.py` çıktısında `ŞEMA UYUMLU` görmeden sunucuyu başlatmayın.
Sunucu kodu değiştiğinde çalışan sunucu yeniden başlatılmalıdır.

### Veritabanı şeması kontrolü (`sema_dogrula.py`)

Kod yeni bir tablo ya da sütun beklediği hâlde veritabanında yoksa (migration çalıştırılmamış ya da atlanmış), kullanıcılar
ekranda **"Veritabanı şeması sunucu sürümüyle uyumlu değil... python -m alembic upgrade head"** uyarısını görür
(sunucu bu durumda 503 döner; hangi sütunun eksik olduğu `logs\sunucu.log` dosyasına yazılır).

Kontrol aracı canlı veritabanına hiçbir şey yazmaz. Aynı PostgreSQL sunucusunda geçici bir veritabanı oluşturup migration'ları
baştan çalıştırır, canlı veritabanını onunla karşılaştırır, geçici veritabanını siler (yaklaşık 10-30 saniye):

    python scripts/sema_dogrula.py              # özet
    python scripts/sema_dogrula.py --ayrinti    # varsayılan değer / kural tanımı gibi ayrıntıları da listeler

Veritabanı oluşturabilmesi için `.env` içinde tam yetkili kullanıcı gerekir (`DB_MIGRATION_USER` / `DB_MIGRATION_PASSWORD`;
bunlar yoksa `DB_USER` / `DB_PASSWORD` kullanılır). Sonuçlar:

| Son satır | Anlamı | Yapılacak |
|---|---|---|
| `ŞEMA UYUMLU` | Her şey yolunda | Bir şey yapmayın |
| `ŞEMA ESKİ` | Alembic sürümü geride | `python -m alembic upgrade head`, sonra aracı tekrar çalıştırın |
| `TUTARSIZ ŞEMA` | Sürüm güncel görünüyor ama bazı tablo/sütunlar eksik (bir migration atlanmış ya da tablolar elle değiştirilmiş) | `alembic upgrade head` bunu **düzeltmez**; yedek alın ve bir geliştiriciye danışın |

`FAZLA` olarak listelenen nesneler (eski sürümlerden kalan sütun gibi) genellikle zararsızdır, kontrolü başarısız saymaz.

## Bilinen sınırlar

- Sunucu şu an bağlantıları şifresiz HTTP ile alır. Yalnızca güvendiğiniz kapalı yerel ağda
  kullanın; internete açmayın.
