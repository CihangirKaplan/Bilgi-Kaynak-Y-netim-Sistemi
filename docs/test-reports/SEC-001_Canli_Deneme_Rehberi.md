# SEC-001 — Canlı Ortam Deneme Rehberi

`SEC-001_Guvenlik_Test_Raporu.md` içindeki **"Canlı ⏳"** satırlarını tamamlamak için adım adım rehber. Geliştirme/CI testleri tamamdır;
bu rehber yalnızca **canlı sunucuda** yapılması gerekenleri anlatır.

| Madde | Ne yapılır | Nasıl |
|---|---|---|
| SEC-T01, T02, T03, T07, T08 | API denemeleri (token yok, yetkisiz rol, başkasının kaydı, hesap kilidi, bozuk token) | **Betik**: `scripts/canli_guvenlik_denemesi.py` (istemci bilgisayardan) |
| SEC-T08 (son adım) | Açık oturumda hesap pasifleştirilince istemci giriş ekranına döner | **Elle**, istemci uygulamasında (bölüm 4) |
| SEC-T10, T11, T12, T13 | `.env` ve anahtar, bağımlılık taraması, denetim kaydı değiştirilemezliği, yedek klasörü izni | **Elle**, sunucuda (bölüm 3) |

Betik yalnızca HTTP(S) istekleri gönderir; veritabanına doğrudan bağlanmaz. Parola ve oturum anahtarı (token) **hiçbir yere yazılmaz**:
ekrandaki çıktı ve kanıt dosyası olduğu gibi rapora eklenebilir.

## 1. Hazırlık (bir kez)

Gerçek kullanıcılarla değil, bu iş için açılmış **test hesaplarıyla** çalışın. Kullanıcı & Personel ekranından açın, her hesapla bir kez giriş yapıp
geçici parolayı değiştirin (geçici parolayla ilk giriş tamamlanmadan deneme yapılamaz):

| Hesap (örnek ad) | Rol | Ne için |
|---|---|---|
| `sec_psikolog_a` | Psikolog | T02, T08 (yetkisiz hesap) ve T03 (randevu sahibi). **Bir planlı randevusu olmalı** (test danışanıyla, ileri tarihli). |
| `sec_psikolog_b` | Psikolog | T03: A'nın randevusuna yetkisi olmayan ikinci psikolog |
| `sec_memur` | Memur | T03: bir test cihazı için **aktif bir rezervasyon** oluşturur (bu rezervasyonun sahibi) |
| `sec_asistan` | Proje Asistanı | T03: cihaz rezervasyonu izni var ama rezervasyonları yönetemez (sahibi değil) |
| `sec_kilit` | Memur ya da Proje Asistanı | T07: 5 yanlış parolayla kilitlenir (1 dakika) |
| `sec_pasif` | Proje Asistanı | T08: yönetici pasifleştirip geri açar (**Psikolog olmamalı**) |
| Yönetici hesabınız | Yönetici | T08: `sec_pasif` hesabını pasifleştirir |

Test verisi: `sec_psikolog_a` adına ileri tarihli bir randevu (bir test danışan kodu ile) ve `sec_memur` adına bir test cihazı rezervasyonu.
Bunlar T03'te "başkasının kaydı" olarak kullanılır. İş bitince hesapları pasife alın, test randevu ve rezervasyonunu iptal edin.

## 2. API denemeleri (istemci bilgisayardan)

Proje klasöründe, sanal ortam açıkken. Sunucu HTTPS ise kendi imzalı sertifika dosyasını `--ca` ile verin
(ya da `TKYS_CA_BUNDLE` ortam değişkenini ayarlayın). Adres örneği: `https://172.24.4.66:8443`.

**Önce veri değiştirmeyen denemeler** (T01 tokensiz istekler, T02 yetkisiz hesap, T08 bozuk token):

```
python scripts/canli_guvenlik_denemesi.py --adres https://172.24.4.66:8443 --ca sertifika.pem --adimlar T01,T02,T08 --yetkisiz sec_psikolog_a
```

Betik her hesabın parolasını gizli olarak sorar (ekranda görünmez). Hepsi `PASS` ise çıkış kodu 0'dır.

**Sonra veriyi değiştirebilecek denemeler.** Bunlar `--onay` ister, çünkü yetkisizlik çalışmazsa gerçek bir kayıt iptal olurdu (T03), hesap bir dakika
kilitlenir (T07) ya da test hesabı kısa süre pasif olur (T08). Yalnızca test hesaplarıyla çalıştırın:

```
python scripts/canli_guvenlik_denemesi.py --adres https://172.24.4.66:8443 --ca sertifika.pem --onay ^
  --yetkisiz sec_psikolog_a --psikolog-a sec_psikolog_a --psikolog-b sec_psikolog_b --asistan sec_asistan ^
  --kilit-hesabi sec_kilit --yonetici KENDI_YONETICI_HESABINIZ --pasiflestirme-hesabi sec_pasif
```

(PowerShell'de satır sonu `^` yerine ``` ` ``` kullanın ya da komutu tek satır yazın.) Betik 1 dakika kilit süresini bekler, test hesabını pasifleştirip
**yeniden aktif eder**. Aktif edilemezse ekrana büyük uyarı yazar; o durumda hesabı Kullanıcı & Personel ekranından elle aktif edin.

**Beklenen sonuç ve ne anlama geldiği**

| Adım | Beklenen |
|---|---|
| T01.1–T01.3 | `/api/saglik` açık (200); diğer uçlar tokensiz ve bozuk token ile **401** |
| T02.1 | Psikolog hesabı yönetim raporu, denetim kayıtları, kullanıcı oluşturma ve rol değiştirme uçlarında **403** |
| T03.1–T03.2 | Psikolog B, A'nın randevusunu iptal edemez (**403/404**) ve A'nın randevusu **PLANLANDI** kalır |
| T03.3–T03.4 | Asistan, başkasının rezervasyonunu iptal edemez (**403**) ve rezervasyon **Aktif** kalır |
| T07.1–T07.4 | 5. yanlış parolada **429**; kilit sürerken doğru parola da **429**; `Retry-After` var; süre dolunca doğru parola **200** |
| T08.1–T08.2 | İmzası bozulmuş ve imzasız (`alg: none`) token **401** |
| T08.3–T08.4 | Yönetici test hesabını pasifleştirir; hesabın eski token'ı **reddedilir** (401 ya da 403, veri dönmez); hesap geri açılır |

`ATLANDI` yazan adım, gerekli hesap ya da `--onay` verilmediği için çalışmamıştır; nedeni satırda yazar. Hiçbiri `FAIL` olmamalı.

**Kanıt:** Betik `sec001_canli_kanit_<tarih>.txt` dosyası yazar. Bu dosyayı `docs/test-reports/` altına (örn. `docs/test-reports/kanit/`) koyup rapora
bağlantı verin; içinde parola ya da token yoktur.

## 3. Sunucuda elle yapılan denemeler

Sunucu bilgisayarında, proje klasöründe, sanal ortam açıkken (yönetici PowerShell gerekmez; T13 hariç aynı kullanıcı yeterli).

**SEC-T10 — gizli bilgi:** `.env` yalnızca sunucuda ve anahtar yeterince uzun/rastgele olmalı.

```
git check-ignore .env
python -c "import os;from dotenv import load_dotenv,dotenv_values;load_dotenv();ornek=dotenv_values('.env.example').get('JWT_SECRET');s=os.getenv('JWT_SECRET','');print('uzunluk:',len(s),'| örnek değerle aynı mı:',s==ornek)"
```

Beklenen: ilk komut `.env` yazar (dosya git tarafından yok sayılıyor); ikincisi `uzunluk: 32` ya da daha fazla ve `örnek değerle aynı mı: False`.
Anahtarın kendisini ekrana yazdırmayın ve rapora koymayın.

**SEC-T11 — bağımlılık taraması:**

```
pip install pip-audit
pip-audit
```

Beklenen: `No known vulnerabilities found`. Çıktının ekran görüntüsünü ekleyin.

**SEC-T12 — denetim kayıtları değiştirilemez:** uygulamanın kullandığı veritabanı kullanıcısıyla (`.env` içindeki `DB_USER`, veritabanı `DB_NAME`):

```
psql -h 127.0.0.1 -U <DB_USER> -d <DB_NAME> -c "SELECT count(*) FROM denetim_kayitlari;"
psql -h 127.0.0.1 -U <DB_USER> -d <DB_NAME> -c "UPDATE denetim_kayitlari SET hedef_tablo = 'deneme' WHERE denetim_id = 1;"
psql -h 127.0.0.1 -U <DB_USER> -d <DB_NAME> -c "DELETE FROM denetim_kayitlari WHERE denetim_id = 1;"
psql -h 127.0.0.1 -U <DB_USER> -d <DB_NAME> -c "TRUNCATE denetim_kayitlari;"
psql -h 127.0.0.1 -U <DB_USER> -d <DB_NAME> -c "SELECT count(*) FROM denetim_kayitlari;"
```

Beklenen: üç komut da `denetim_kayitlari tablosundaki kayitlar degistirilemez veya silinemez (UPDATE / DELETE / TRUNCATE)` hatası verir ve baştaki
ile sondaki kayıt sayısı **aynıdır**. (Eski örnekteki `SET olay_turu = 'X'` kullanmayın: 'X' geçerli bir değer olmadığı için tetikleyici
çalışmadan başka bir hata verir ve yanlışlıkla "geçti" sanılır.)

**SEC-T13 — yedek klasörü:** yedek klasörü (varsayılan: proje klasöründeki `backups`, kurulumunuzda farklı olabilir) için, yönetici PowerShell'de:

```
icacls "<yedek klasörü>"
net share
```

Beklenen: `icacls` çıktısında yalnızca `Administrators`, `SYSTEM` ve sistem sorumlusu hesabı vardır; `Users`, `Everyone`, `Authenticated Users` yoktur.
`net share` listesinde yedek klasörü yoktur (ağda paylaşılmaz). İki çıktının ekran görüntüsünü ekleyin.

## 4. SEC-T08 — istemcide elle kontrol

Bu adım, pasifleştirilen kullanıcının **açık oturumunun** istemcide nasıl sonlandığını gösterir. (Eskiden istemci bu durumda giriş ekranına dönmüyor, her
işlemde hata gösteriyordu; düzeltme sonrası dönmesi gerekir. Test için **güncel istemci** gerekir.)

1. Bir bilgisayarda `sec_pasif` hesabıyla istemciye girin ve bir liste sayfası açın.
2. Başka bir bilgisayarda yönetici hesabıyla **Kullanıcı & Personel** ekranından `sec_pasif` hesabını **pasife alın**.
3. İlk bilgisayarda bir işlem deneyin (listeyi yenileyin, başka sayfaya geçin).
4. Beklenen: "Oturumunuz geçersiz hâle gelmiştir" uyarısı çıkar ve giriş ekranı açılır. Aynı hesapla yeniden girişte "Kullanıcı hesabı aktif değil." görünür.
5. Hesabı yeniden **aktif edin**. Uyarının ve giriş ekranının ekran görüntüsünü alın.

(Betiğin T08.3–T08.4 adımı aynı pasifleştirme/geri açmayı API düzeyinde yapar; bu madde istemci davranışını kanıtlar. İkisini birbirine
karıştırmadan, birinde betik, diğerinde istemci çıktısı kanıt olarak eklenir.)

## 5. Raporu tamamlama

Her madde için `SEC-001_Guvenlik_Test_Raporu.md` içinde:

1. İlgili bloktaki `Actual Result` satırındaki `Canlı: ⏳` ifadesini sonuçla değiştirin (örn. `Canlı: PASS, 25.11.2026`).
2. `PASS / FAIL` satırını `PASS` yapın; `Date` satırına canlı deneme tarihini, `Tester` satırına denemeyi yapanı yazın.
3. `Evidence` satırına kanıt dosyasını / ekran görüntüsünü ekleyin.
4. En üstteki **Özet** tablosunda "Canlı ortam" sütununu `✅ PASS` yapın.
5. Hepsi bitince **GO / NO-GO Kontrol Listesi**'nde 5–8 ve 11. maddeleri (SEC-001) işaretleyin.

Bir adım **FAIL** olursa: raporu PASS yapmayın; çıktıyı kayda alıp bir GitHub issue açın (P0/P1 etiketiyle) ve bana ya da geliştiriciye iletin.
Düzeltildikten sonra aynı komutla yeniden çalıştırılır.
