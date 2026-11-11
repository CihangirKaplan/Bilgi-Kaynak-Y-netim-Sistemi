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

## 6. İlk yönetici hesabı

Canlı veritabanında **`ilk_kurulum.py` çalıştırmayın**: bilinen parolalı test kullanıcıları ekler.
Onun yerine:

    python scripts/ilk_admin_olustur.py

Betik `admin` kullanıcısını oluşturur ve rastgele bir **geçici parolayı ekrana bir kez** yazar.
Parolayı hemen not edin; ilk girişte yeni parola belirlemeniz istenir. Veritabanında zaten
bir ADMIN varsa betik hiçbir şey eklemez. Diğer kullanıcıları ve rolleri, admin ile giriş yaptıktan
sonra uygulamadaki Kullanıcı & Personel ekranından ekleyin.

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
parolasını unutursa diğeri, Kullanıcı & Personel ekranındaki parola taleplerinden onu sıfırlayabilir.

## 7. Sunucuyu ağa açın

Sunucu bilgisayarının adresini öğrenin:

    ipconfig

"IPv4 Address" satırındaki adresi (örn. `192.168.1.20`) not edin. Bu adresin değişmemesi için
modem/ağ yöneticisinden bu bilgisayara sabit (rezerve) adres verilmesini isteyin.

Sunucuyu tüm ağ arayüzlerinde başlatın (`--reload` canlıda kullanılmaz):

    uvicorn sunucu:app --host 0.0.0.0 --port 8000

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

Sunucunun çalıştığını `http://SUNUCU_ADRESI:8000/docs` adresini tarayıcıda açarak görebilirsiniz.
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
    python login_ekrani.py

Bağlanamazsa önce istemci bilgisayarın tarayıcısından `http://192.168.1.20:8000/docs`
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
    python scripts/veritabani_yedekle.py
    python -m alembic upgrade head
    uvicorn sunucu:app --host 0.0.0.0 --port 8000

Migration'dan önce her zaman yedek alın. Sunucu kodu değiştiğinde çalışan sunucu yeniden
başlatılmalıdır.

## Bilinen sınırlar

- Sunucu şu an bağlantıları şifresiz HTTP ile alır. Yalnızca güvendiğiniz kapalı yerel ağda
  kullanın; internete açmayın.
