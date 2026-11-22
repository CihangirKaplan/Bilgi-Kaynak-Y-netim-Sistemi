# Sistem Yöneticisi (Sistem Admin) Kılavuzu

Bu kılavuz **Sistem Admin** rolü içindir. Giriş, şifre, arama, sıralama, Excel ve kısayollar için önce
[Ortak Kullanım Kılavuzu](../Ortak_Kullanim.md)'na bakın.

Sistem Admin, **tüm sayfalara** erişir ve ayrıca şunlara yetkilidir (varsayılan olarak Müdür'de yoktur):
**Rol & İzin Yönetimi**, kullanıcıya **Parola Sıfırla** ve **Faaliyet Birimleri** yönetimi.
Kullanıcı, denetim, rapor ve sistem durumu sayfalarının kullanımı [Müdür Kılavuzu](../director/Mudur_Kilavuzu.md)'ndadır; cihaz/öğrenci/danışma masası işleri [Memur Kılavuzu](Memur_Kilavuzu.md)'ndadır. Bu kılavuz **yalnızca size özel** işleri anlatır.

> Yetkiniz geniştir. Yaptığınız önemli işlemler **denetim kaydına** yazılır. Hesabınızın şifresini kimseyle paylaşmayın.

---

# 1. Parola işlemleri

## 1.1 Kullanıcının parolasını sıfırlamak
Kullanıcı şifresini unuttuğunda **Şifremi Unuttum?** ile bir **talep** bırakır. Talepler **Kullanıcı & Personel** sayfasının üstünde
**🔐 Parola sıfırlama talepleri (N)** başlığı altında listelenir ve ayrıca **🔔 bildirim** olarak size gelir.

1. **Önce kişinin kimliğini doğrulayın:** *Parolayı vermeden önce kullanıcının kimliğini yüz yüze ya da telefonla doğrulayın.* Sistem bu uyarıyı gösterir.
2. Talep satırındaki **🔑 Parola Sıfırla**'ya basın (ya da listeden kullanıcıyı seçip sayfanın üstündeki **🔑 Parola Sıfırla**'yı kullanın).
3. **Parola Sıfırlama Onayı** penceresinde onaylayın.
4. Sistem bir **geçici parola** üretir ve **kopyalanabilir bir pencerede bir kez** gösterir; **pencere kapandıktan sonra tekrar gösterilemez.** Kullanıcıya güvenli biçimde iletin.
5. Geçici parolanın **süresi sınırlıdır** (varsayılan **48 saat**, `GECICI_PAROLA_GECERLILIK_SAAT` ile ayarlanır). Kullanıcı ilk girişte kendi şifresini belirler.
6. Talep satırındaki **Talebi Kapat** düğmesiyle talebi kapatın. Sıfırlama işlemi denetim kaydına **Parola Sıfırlama** olarak yazılır.

Kullanıcı şifresini **sizin görmeniz mümkün değildir**; yalnızca yenisini verebilirsiniz.

## 1.2 Yönetici hesabına kimse giremiyorsa
Tüm yöneticilerin şifresi unutulduysa uygulama içinden çözülemez; sunucuyu yöneten teknik kişi kurtarma aracını kullanır
([Sunucu Kurulum Kılavuzu → "Yönetici parolasını unuttuysanız"](../../docs/deployment/Sunucu_Kurulum_Kilavuzu.md)).

---

# 2. Rol & İzin Yönetimi

Sistem **rol tabanlı** çalışır: her kullanıcının bir **rolü**, her rolün bir **izin listesi** vardır. Menüler ve sunucu aynı izin kayıtlarına bakar;
yani bir izni bir rolden alırsanız o rol hem menüden hem sunucudan **o işlemi yapamaz.**

Varsayılan roller: **Sistem Admin, Müdür (Yönetici), Memur, Psikolog, Danışma Öğrencisi, Proje Asistanı.** İsterseniz yeni roller tanımlayabilirsiniz.
Sayfa **Rol & İzin Yönetimi** (menüde *Sistem* bölümü) üç işlem sunar:

## 2.1 Rol Oluştur
1. **＋ Rol Oluştur** → **ROL ADI**'nı yazın (örnek: *Gözlemci*) → **Kaydet**.
2. Yeni rol **hiç izinsiz** başlar; hiçbir şey yapamaz. İzinleri **İzin Düzenle** ile verirsiniz. Yeni roller **rol hiyerarşisinde en altta** sayılır (bkz. bölüm 3).
3. Yeni rolü **Kullanıcı & Personel → Kullanıcı Oluştur / Rol Ata** ekranlarından kullanıcılara verirsiniz.

## 2.2 Rol Düzenle
**✎ Rol Düzenle** → **DÜZENLENECEK ROL**'ü seçin → **ROL ADI DÜZENLE** ile görünen adı değiştirin, **DURUM (AKTİF/PASİF)** ile rolü pasife alın/aktif edin → **Kaydet**.
- **Pasif bir roldeki kullanıcılar sisteme giremez** (yeni girişler ve açık oturumlar dahil). Pasife almadan önce sistem **etkilenecek kullanıcı sayısını** gösterip onay ister.
- **Kendi rolünüzü pasife alamazsınız.**
- Pasif role yeni kullanıcı oluşturulamaz ve rol atanamaz.
- Rolün pasife alınması **önceki/yeni değerle ve etkilenen kullanıcı sayısıyla** denetim kaydına yazılır.

## 2.3 İzin Düzenle
**✎ İzin Düzenle** → **DÜZENLENEN İZİN**'i seçin → **BU İZNİN GEÇERLİ OLACAĞI ROLLER** listesinde rolleri işaretleyin/işareti kaldırın → **Değişiklikleri Kaydet**.
- Sunucu izinleri **hemen** uygular (yetkisi alınan kişi o işlemi artık yapamaz). Kullanıcının **menüsü** ise yetkiler yenilendiğinde (kısa süre içinde ya da yeniden girişte) güncellenir.
- **Geniş yetkili** izinleri (kullanıcı oluşturma, rol atama, audit gibi) yalnızca güvendiğiniz rollere verin.
- Çok yetkili bir izni kazara kaldırmamak için değişikliği **kaydetmeden önce** iki kez bakın; işlem denetim kaydına yazılır (hangi roller eklendi/çıkarıldı, önceki ve yeni durumla).
- **Bağlı izinler:** Bazı izinler tek başına bir sayfa açmaz, başka bir iznin sayfasına bağlıdır (örneğin bir sayfadaki düğme izni). Bir izin kaldırılırsa rolde kalan **bağlı izinler kullanılamaz hale** gelebilir; sistem bu durumda **"Bağlı izinler etkilenecek"** uyarısıyla hangi izinlerin etkileneceğini listeler ve onay ister. Tek başına sayfa açmayan izinlerin yanında bu bilgiyi veren bir not görünür.
- Pencerelerde **Enter** tuşu kaydeder; rol ve izin listelerinde satıra **çift tıklayarak** düzenleme açılır. Hata olursa teknik bir kod değil, okunur bir mesaj görürsünüz.

## 2.4 Faaliyet Birimleri
**Faaliyet Kayıtları** sayfasındaki **🏢 Faaliyet Birimleri** düğmesiyle (*Kişi, Saat* gibi) birimleri **eklersiniz, düzenlersiniz, silersiniz**. **Geçmiş faaliyet kayıtlarında kullanılmış** bir birim **silinemez** (sistem bunu uyarır); adını düzenleyebilirsiniz.

---

# 3. Kullanıcı ve oda yönetimi

Ayrıntı: [Müdür Kılavuzu → Kullanıcı & Personel](../director/Mudur_Kilavuzu.md). Kısa hatırlatma:
- Kullanıcı adı **yalnızca İngilizce harf, rakam ve `. _ -`** içerebilir; **büyük/küçük harf fark etmez** (`Ayse` ile `ayse` aynı hesaptır).
- **Rol hiyerarşisi:** Kullanıcı yönetimi yetkisi olan biri **kendi seviyesindeki ya da daha yüksek** bir rolü veremez ve o roldeki kullanıcıları yönetemez. Sıra: **Sistem Admin › Müdür › Memur › Psikolog › Proje Asistanı › Danışma Öğrencisi**; sonradan eklenen roller en altta sayılır. Sistem Admin bu kurala takılmaz; bu yüzden **başka bir Müdür açmak ya da pasife almak yalnızca sizdedir.** Ayrıntı: [Müdür Kılavuzu → Rol hiyerarşisi](../director/Mudur_Kilavuzu.md).
- **Psikologun en az bir odası** olmalıdır (**Oda Yetkileri**).
- Bir psikoloğu pasife alırken planlı randevusu, atanmış odası ve danışanları kontrol edilir.
- Hiçbir kullanıcı **silinmez**, yalnızca pasife alınır; geçmiş kayıtlar korunur.
- **Oda Yönetimi** → **＋ Yeni Oda Ekle / ✎ Odayı Düzenle / ✕ Odayı Pasife Al**.

---

# 4. İzleme: denetim, yetki raporu, sistem durumu

Ayrıntı: [Müdür Kılavuzu bölüm 3–5](../director/Mudur_Kilavuzu.md). Yönetici olarak düzenli yapmanız gerekenler:

| Sıklık | Ne? |
|---|---|
| **Her gün** | **Sistem Durumu** → *Son Yedek* kartı **yeşil** mi? Başarısız giriş sayısı olağan mı? |
| **Her hafta** | **Audit Kayıtları** → *Başarısız Giriş*, *Silme*, *Rol Değişikliği*, *Parola Sıfırlama*, *Excel Aktarımı* kayıtlarına göz atın; aynı hesabın alışılmadık bir **İstemci Adresi**'nden girip girmediğine bakın. *Görüntüleme* kayıtları denetim kayıtlarına kimin baktığını gösterir |
| **Her ay** | **Yetki Raporu** → kilitli, hiç giriş yapmamış, kullanılmayan hesaplar; artık çalışmayanları pasife alın |

---

# 5. Yedekleme ve geri yükleme

Yedek, **tüm veriyi** (parola özetleri dahil) içeren bir `.dump` dosyasıdır. **`backups` klasörünü paylaşmayın.**

## 5.1 Otomatik yedekleme
Sunucu bilgisayarında **Windows Görev Zamanlayıcı**'da `TKYS_Otomatik_Yedekleme` görevi her gün çalışır (kurulu saat bilgisayara göre değişebilir; saatin
bilgisayar açıkken gelmesine dikkat edin). Görev açık değilken kaçırılan yedeği bilgisayar açılınca alacak şekilde kurulmalıdır.
- Yedekler `backups` klasörüne (ya da `.env` içindeki `TKYS_BACKUP_DIR` klasörüne) yazılır; **14 günden eski** yedekler başarılı yedekten sonra otomatik silinir; en yeni 3 yedek, eski olsa bile her zaman saklanır.
- İşlem kayıtları `logs\yedekleme.log` dosyasındadır. Görev sonucu `0` ise başarılıdır.
- **Sistem Durumu** sayfasındaki *Son Yedek* kartı da son yedeğin tarihini gösterir; **36 saatten eski** olduğunda sarı, hiç yoksa kırmızı olur.

## 5.2 Elle yedek almak
Sunucu bilgisayarında proje klasöründe:

```powershell
python scripts\backup\veritabani_yedekle.py
```
- `pg_dump bulunamadi` hatası verirse `.env` dosyasına **kendi satırında** `PG_DUMP_PATH=C:\Program Files\PostgreSQL\<sürüm>\bin\pg_dump.exe` ekleyin.
- `server version mismatch` hatası verirse **`pg_dump` sürümü veritabanı sunucusunun sürümünden eski olmasın**; sunucu 18 ise 18 sürümünün `pg_dump.exe` dosyasını gösterin.

## 5.3 Yedeğin işe yaradığını sınamak
Yedek, geri yüklenebildiği sürece değerlidir. **Mevcut hiçbir veritabanının üzerine yazmayan** test aracı:

```powershell
python scripts\restore\veritabani_geri_yukle.py --hedef crkys_geri_yukleme_testi
```
Araç yedeği **yeni** bir veritabanına yükler ve kayıt sayılarını karşılaştırır. Doğrulamadan sonra test veritabanını kendiniz silin.

---

# 6. Güncelleme

Yeni bir sürüm geldiğinde (sunucu bilgisayarında, **önce yedek alın**):

```powershell
git pull origin develop
python -m alembic upgrade head
python scripts\sema_dogrula.py
```
- `alembic upgrade head` veritabanı değişikliklerini (migration) uygular. Sonra `sema_dogrula.py` **"ŞEMA UYUMLU"** demelidir.
- Ardından **sunucuyu yeniden başlatın** ve istemcilerin de güncel olduğundan emin olun (**Hakkında** penceresinde istemci ve sunucu sürümü aynı olmalı).
- Güncelleme sonrası kullanıcılar **503 / "veritabanı şeması güncel değil"** benzeri bir hata görürse `alembic upgrade head` çalıştırılmamıştır.
- Bir migration hata verirse **`alembic stamp` ile hatayı gizlemeyin**; ayrıntı için [Sunucu Kurulum Kılavuzu → Güncelleme](../../docs/deployment/Sunucu_Kurulum_Kilavuzu.md).

---

# 7. Ayarlar (`.env`)

Sunucu bilgisayarındaki `.env` dosyası **gizlidir; GitHub'a yüklenmez, kimseyle paylaşılmaz.** Başlıca ayarlar:

| Ayar | Anlamı |
|---|---|
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | PostgreSQL bağlantısı |
| `JWT_SECRET` | Oturum anahtarlarını imzalayan gizli anahtar; **en az 32 karakter**, rastgele olmalı. Değiştirirseniz herkes bir kez yeniden giriş yapar |
| `JWT_EXPIRE_MINUTES` | Oturum süresi (varsayılan **45** dakika) |
| `GECICI_PAROLA_GECERLILIK_SAAT` | Geçici parolanın geçerlilik süresi (varsayılan **48** saat) |
| `TKYS_BACKUP_DIR` | Yedeklerin yazılacağı klasör (ayarsızsa projenin `backups` klasörü) |
| `PG_DUMP_PATH` | `pg_dump.exe` dosyasının tam yolu |
| `TKYS_API_DOCS` | `1` ise API belge sayfaları (`/docs`) açılır; **varsayılan kapalıdır**, yalnızca teknik kişi gerektiğinde açmalı |
| `TKYS_SSL_CERTFILE`, `TKYS_SSL_KEYFILE` | Sunucu için HTTPS: sertifika ve gizli anahtar dosyalarının yolu (ikisi birlikte verilir). Ayarlanmazsa sunucu düz HTTP ile çalışır; ağa açıksa günlüğe uyarı yazılır. Kurulum: [TLS Kurulum Rehberi](../../docs/deployment/TLS_Kurulum_Rehberi.md) |
| `TKYS_GUVENILIR_VEKIL` | `1` yalnızca TLS'i başka bir sunucu (ters vekil) sonlandırıyorsa verilir; denetim kaydındaki istemci adresi ve HTTPS başlığı vekilin gönderdiği bilgiden alınır. Vekil yoksa **vermeyin** |
| `TKYS_API_URL`, `TKYS_CA_BUNDLE` | **İstemci bilgisayarlarda:** sunucu adresi (HTTPS için `https://...`) ve kendi imzalı sertifikayı güvenilir saymak için sertifika dosyasının yolu |

**Dikkat:** `.env` dosyasına satır eklerken önceki satırın **sonunda yeni satır** olduğundan emin olun; aksi halde iki ayar **aynı satırda** birleşir ve ikisi de bozulur.
`.env` içeriğini (özellikle `JWT_SECRET` ve parolayı) sohbetlere, e-postalara ya da ekran görüntülerine **yapıştırmayın.**

---

# 8. Sorun giderme

| Belirti | Nedeni / çözüm |
|---|---|
| Kullanıcılar giriş yapamıyor: "Hesap geçici olarak kilitli" | 5 hatalı denemede 1 dk, 10'da 15 dk kilit; beklemek yeterli. **Yetki Raporu**'nda *kilitli hesaplar* görünür |
| Kullanıcı rolünü kaybetmiş/menü boş | **Rol & İzin Yönetimi**'nde rolün izinlerini ve **aktif** olduğunu kontrol edin |
| Bir rol pasif olduğu için kimse giremiyor | Rol Düzenle → rolü yeniden **Aktif** yapın (kendi rolünüzü pasife alamazsınız) |
| Psikolog randevuda oda göremiyor | **Oda Yetkileri** verilmemiş |
| Randevu listesinde çok eski kayıt yok | "Tüm tarihler" en yeni 2000 randevuyu getirir; dönem seçilir |
| **Sistem Durumu → Son Yedek: Yedek bulunamadı** | Yedekleme görevi çalışmıyor ya da yedekler başka klasörde; `TKYS_BACKUP_DIR`'i ve `logs\yedekleme.log`'u kontrol edin |
| **Sistem Durumu → Uygulama Sürümü sarı** | İstemci ile sunucu sürümü farklı; istemcileri güncelleyin |
| İstemci "veritabanı şeması güncel değil" diyor | Sunucuda `python -m alembic upgrade head` çalıştırın, sunucuyu yeniden başlatın |
| Kullanıcı "beklenmeyen hata" mesajı görüyor | Ekranda yalnızca genel mesaj çıkar; gerçek neden `logs\sunucu.log` dosyasında, hangi işlemin bozulduğu (yöntem ve adres) ve hata satırıyla yazılıdır. Geliştiriciye bu bloğu olduğu gibi iletin ([Sunucu Kurulum Kılavuzu](../../docs/deployment/Sunucu_Kurulum_Kilavuzu.md)) |
| Kullanıcı "Oturum geçersiz. Yeniden giriş yapınız." görüyor | Hesabından çıkış yapılmış ya da şifresi değişmiş; yeniden giriş yapması yeterli |
| `JWT_SECRET en az 32 karakter olmalıdır` hatasıyla sunucu açılmıyor | `.env`'deki anahtarı uzun rastgele bir değerle değiştirin: `python -c "import secrets; print(secrets.token_urlsafe(48))"` |

Ek kaynaklar: [Sunucu Kurulum Kılavuzu](../../docs/deployment/Sunucu_Kurulum_Kilavuzu.md), [Windows sunucu sorun giderme](../../docs/deployment/windows-sunucu/SORUN_GIDERME.md), [Raporlama Rehberi](../../docs/Raporlama_Rehberi.md).
