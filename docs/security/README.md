# TKYS Güvenlik Özeti

Bu belge, sistemin **uyguladığı** güvenlik önlemlerini tek yerde toplar. Her madde kodda uygulanır ve testle korunur (ilgili test/dosya yanında).
Tehdit analizi için bkz. [architecture/D06_Threat_Model.md](../architecture/D06_Threat_Model.md); güvenlik gereksinimleri için [Kullanici_Guvenlik_Ag_Gereksinimleri.md](../Kullanici_Guvenlik_Ag_Gereksinimleri.md);
uç bazında yetki listesi için [API/Uc_Listesi.md](../API/Uc_Listesi.md).

## 1. Kimlik doğrulama

| Önlem | Ayrıntı | Kod / test |
|---|---|---|
| Parola saklama | Parolalar **bcrypt** ile özetlenip saklanır; düz parola hiçbir yerde tutulmaz. 72 baytı aşan parola reddedilir | `server/guvenlik.py`, `test_guvenlik_jwt_kalite.py` |
| Oturum anahtarı | **JWT (HS256)**; süre varsayılan **45 dakika** (`JWT_EXPIRE_MINUTES`). `JWT_SECRET` **en az 32 karakter** olmalıdır, değilse sunucu **açılmaz**. **Çıkış** (`POST /api/cikis`) kullanıcının oturum sürümünü artırır: o hesabın tüm açık anahtarları süresi dolmasını beklemeden geçersiz olur | `server/guvenlik.py`, `test_sec_t07_t08_auth.py` |
| Parola kuralları | En az **10** karakter, harf **ve** rakam içermeli, kullanıcı adını içeremez, yaygın/tahmini kolay parolalar (ör. `password123`) reddedilir; en fazla 72 bayt, eskisiyle aynı olamaz; ilk giriş/geçici parolada **zorunlu değiştirme**. Kurallar **sunucuda** uygulanır, ekran yalnızca yol gösterir | `server/parola_politikasi.py`, `client/parola_kurallari.py`, `test_guvenlik_paketi_c1.py` |
| Geçici parola | Yönetici sıfırlaması **tek seferlik** gösterilir; süresi sınırlı (varsayılan **48 saat**, `GECICI_PAROLA_GECERLILIK_SAAT`); süresi dolunca giriş reddedilir | `test_gecici_parola_suresi_pg_quality.py` |
| Hesap kilidi | **5** art arda hatalı girişte **60 sn**, **10**'da **15 dk** kilit; başarılı girişte sayaç sıfırlanır; sayaç atomik artırılır | `server/sunucu.py` (`giris_yap`) |
| İstemci (IP) sınırı | Aynı istemciden **5 dakikada 20**'den fazla başarısız deneme geçici engellenir; **var olmayan kullanıcı adıyla** yapılan denemeler de sayılır. Sınırlayıcı arızalanırsa giriş engellenmez (fail-open) | `server/giris_siniri.py`, `test_giris_siniri_pg_quality.py` |
| Kullanıcı adında büyük/küçük harf | `Ayse` ve `ayse` **aynı hesaptır**: giriş büyük/küçük harfe duyarsızdır, aynı ad farklı yazımla yeniden oluşturulamaz | `server/sunucu.py` (`giris_yap`, `kullanici_olustur`) |
| Kullanıcı adı sahteciliği | Yalnızca ASCII harf, rakam ve `. _ -`; boşluk, görünmez karakter ve **taklit (Kiril/Yunan) harfler reddedilir** | `server/modeller.py` |
| Hesap var mı bilgisi sızmaz | Var olmayan kullanıcı adında da bcrypt doğrulaması yapılır (yanıt süresi aynı); "parolamı unuttum" yanıtı hesabın varlığını belli etmez; pasif hesap/rol bilgisi yalnızca **doğru parolayla** söylenir | `server/sunucu.py` |
| Pasif kullanıcı/rol | Pasif kullanıcı ve **pasif roldeki kullanıcılar** giremez (açık oturumlar dahil) | `test_kullanici_pasiflestirme.py` |

## 2. Yetkilendirme (rol tabanlı)

- Her kullanıcının bir **rolü**, her rolün bir **izin listesi** vardır (`roller`, `izinler`, `rol_izinleri`). Sunucu **her istekte** izni veritabanından denetler
  (`izin_kontrol('...')`); menü de aynı kayıtlardan çizilir, yani arayüz ile sunucu ayrışamaz.
- **Her uç izinle korunur** ya da `tests/security/test_uc_koruma_taramasi.py` içinde **gerekçesiyle** istisna olarak listelenir; yeni bir uç korumasız eklenirse CI **kırılır**.
- Yetkisi olmayan işlem **403** döner; izin listesinde olmayan yeni rol **hiçbir şey yapamaz**.
- **Rol hiyerarşisi:** kullanıcı yönetimi yetkisi olan biri, **kendi seviyesindeki ya da daha yüksek** bir rolü atayamaz ve o roldeki kullanıcıları yönetemez (oluşturma, rol değiştirme, aktif/pasif yapma). Sıra: ADMIN › MÜDÜR › MEMUR › PSİKOLOG › PROJE ASİSTANI › DANIŞMA ÖĞRENCİSİ; sonradan eklenen roller en altta sayılır. Seviyeler `server/rol_hiyerarsisi.py` içindedir.
- Kişi **kendi rolünü değiştiremez**; pasif/geniş yetkili rol atamaları uyarı ve denetim kaydı üretir.
- Psikolog yalnızca **kendi** randevu ve danışanlarına erişir (sunucu uygular).

## 3. Denetim (audit)

- Her kayıt, isteği yapan **istemci adresini** (`istemci_adresi`) taşır; sunucu adresi her veritabanı bağlantısına iliştirir, tetikleyici sütuna yazar (hangi uçtan yazıldığına bakılmaz). `X-Forwarded-For` varsayılan olarak **güvenilmez**; yalnızca `TKYS_GUVENILIR_VEKIL=1` iken vekilin eklediği son giriş kullanılır.
- **Çıkış** (`LOGOUT`) ve denetim kayıtlarının **görüntülenmesi** (`VIEW`; aynı kullanıcı için 10 dakikada bir, ilk sayfa) de kayda geçer.
- Giriş, başarısız giriş, oluşturma, güncelleme, silme, iptal, rol değişikliği, cihaz durum değişikliği, parola sıfırlama/değiştirme ve **liste Excel aktarımı** (`EXPORT`) **denetim kaydına** yazılır.
- Denetim tablosu **değiştirilemez ve boşaltılamaz** (veritabanı tetikleyicileri; migration `f3a9c2e47b18`).
- Silme işlemlerinde silinen verinin **kopyası** kayda yazılır; **kişisel veri alanları maskelenir** ve "kaydedilmeyen alanlar" olarak belirtilir.
- Kayıt gerektiren işlem **aynı veritabanı işleminde** (transaction) yazılır: denetim yazılamazsa işlem **geri alınır** (`test_api_audit_rollback_quality.py`).

## 4. Kişisel veri

- **Danışanlar ad/telefon ile değil kodla** (`DAN-YYYY-NNNN`) tutulur; sistemde danışan adı ya da tanısı alanı yoktur.
- Randevu iptal **notu** serbest metindir; yalnızca randevu düzenleme izni olanlara gösterilir, diğerleri yalnızca iptal **nedenini** görür. Nota kişisel bilgi yazılmaması ekranda hatırlatılır.
- Öğrenci adı/telefonu yalnızca öğrenci yönetimi yetkisi olanlara görünür; Excel aktarımı denetim kaydına yazılır.
- Yönetim raporları ve oda/cihaz raporları **kişisel veri içermez** (kişi adı, tanı, danışan bilgisi dışarıya verilmez) (`test_kisisel_veri_ayrimi_pg_quality.py`, `docs/Raporlama_Rehberi.md` bölüm 6).
- Excel çıktılarında metin hücreleri **formül olarak yorumlanmaz** (formül enjeksiyonuna karşı).

## 5. Veri ve sunucu güvenliği

- Tüm veritabanı sorguları **parametreli**dir (psycopg2); girdiler sunucuda doğrulanır (uzunluk, biçim, izinli değer listeleri). Hatalarda iç ayrıntı kullanıcıya sızdırılmaz; genel mesaj döner.
- **Eşzamanlılık:** randevu/rezervasyon/oda çakışmaları veritabanı **kısıtları ve kilitleriyle** korunur (aynı anda iki kayıt çakışamaz).
- **Veri bütünlüğü:** durum alanlarında `CHECK`, yabancı anahtarlar, benzersizlik kısıtları; silme yerine **pasife alma** (geçmiş korunur).
- **Gizli bilgi:** `.env` dosyası depoya **eklenmez**; `tests/security/test_gizli_bilgi_taramasi.py` depoda parola/anahtar sızıntısı arar.
- **API belge sayfaları** (`/docs`, `/openapi.json`) **varsayılan kapalıdır** (`TKYS_API_DOCS=1` ile açılır).
- Sunucunun **kısıtlı yetkili veritabanı kullanıcısıyla** çalıştırılması önerilir ([Sunucu Kurulum Kılavuzu §6A](../deployment/Sunucu_Kurulum_Kilavuzu.md)).

## 6. Yedekleme

Günlük otomatik yedek (Görev Zamanlayıcı), 14 gün saklama, yedeğin **ayrı bir veritabanına geri yüklenip** sayılarla doğrulanması
(`scripts/restore/veritabani_geri_yukle.py`). Yedekler parola özetlerini de içerdiğinden `backups` klasörü **paylaşılmaz**.
Yöneticiler **Sistem Durumu** sayfasından son yedeğin tarihini izler (36 saatten eskiyse uyarı).

## 7. Bilinen sınırlar (dürüst liste)

- Çıkış, hesabın **tüm** açık oturumlarını kapatır (başka bilgisayarda açık oturum da düşer). Hesap pasife alınınca anahtar teknik olarak geçerli kalır, ama sunucu pasif kullanıcı/rolü her istekte yeniden denetler; pratikte işlem yapılamaz.
- Sistem **tek sunuculu** ve **yerel ağ içindir**; sunucu internete doğrudan açılmamalıdır. TLS (HTTPS) desteği vardır ama **isteğe bağlıdır**: [TLS Kurulum Rehberi](../deployment/TLS_Kurulum_Rehberi.md). Sunucu internete doğrudan açılmamalı; dışarıdan erişim gerekirse ters vekil ve ağ güvenlik duvarı kurulmalıdır. Yerel ağa açma adımları: [Sunucu Kurulum Kılavuzu §7](../deployment/Sunucu_Kurulum_Kilavuzu.md).
- İki aşamalı doğrulama (2FA) yoktur.
- Kayıtlı parola özetleri `bcrypt` ile korunur; ancak **zayıf parola seçimi** kullanıcıya bırakılmıştır (kurallar yalnızca uzunluk ve tekrar denetler, güç göstergesi yol göstericidir).

## Ek: Ağ şifrelemesi (TLS)
HTTPS kurulumu, istemci ayarı ve ters vekil seçeneği için bkz. [TLS Kurulum Rehberi](../deployment/TLS_Kurulum_Rehberi.md).
