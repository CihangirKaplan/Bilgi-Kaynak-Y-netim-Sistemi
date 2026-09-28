# D06 - Tehdit Modeli (Threat Model)

**Proje:** Travma Uygulama ve Araştırma Merkezi - Bilgi ve Kaynak Yönetim Sistemi  
**Sürüm:** v1.0  
**Doküman:** Tehdit Modeli

---

## 1. Dokümanın Amacı

Bu doküman, Bilgi ve Kaynak Yönetim Sistemi için temel güvenlik tehditlerini ve bu tehditlere karşı uygulanacak güvenlik kontrollerini tanımlar.

Temel tehditler:

1. Yetkisiz erişim
2. Yetki yükseltme
3. Veri değiştirme
4. Veri sızıntısı
5. Denetim kayıtlarının manipülasyonu
6. DoS ve tekrarlanan giriş denemeleri

---

# 2. Korunması Gereken Varlıklar

- kullanıcı hesapları ve kimlik doğrulama bilgileri,
- rol ve yetki bilgileri,
- personel ve danışma masası öğrencilerine ait operasyonel bilgiler,
- operasyonel danışan kodları,
- danışan kodlarıyla ilişkili istisna türü bilgileri,
- randevu, takvim, oda ve oda kullanım kayıtları,
- cihaz envanteri ve cihaz operasyon kayıtları,
- denetim kayıtları,
- veritabanı yedekleri,
- uygulama ve veritabanına ait gizli yapılandırma bilgileri.

---

# 3. Güven Sınırları

```text
Kullanıcı
    ↓
PySide6 Masaüstü Uygulaması
    ↓
REST API
    ↓
FastAPI Backend
    ↓
PostgreSQL
```

İstemciden backend'e gönderilen istekler doğrudan güvenilir kabul edilmeyecektir. FastAPI; kimlik doğrulama, yetkilendirme, veri doğrulama ve iş kuralı kontrollerini gerçekleştirecektir. İstemcilerin PostgreSQL'e doğrudan erişimine izin verilmeyecektir.

---

# 4. Yetkisiz Erişim

## 4.1. Tehdit Senaryosu
Kimliği doğrulanmamış veya eksik, geçersiz ya da süresi dolmuş kimlik doğrulama bilgisine sahip bir kullanıcının korunan kaynaklara erişmeye çalışması.

## 4.2. Olası Etki
- Korunan kayıtların yetkisiz görüntülenmesi
- Sistem fonksiyonlarının yetkisiz kullanılması
- Kullanıcı, randevu veya cihaz bilgilerinin yetkisiz görüntülenmesi

## 4.3. Güvenlik Kontrolleri
- Korunan endpointlerde kimlik doğrulama
- Geçersiz/eksik/süresi dolmuş kimlik doğrulama bilgisinin reddedilmesi
- Pasif kullanıcı girişinin engellenmesi
- Rol tabanlı erişim kontrolü
- Doğrudan PostgreSQL erişiminin engellenmesi

---

# 5. Yetki Yükseltme

## 5.1. Tehdit Senaryosu
Kullanıcının kendi rolünün izin vermediği işlemi gerçekleştirmeye veya rol/yetki gibi kritik alanları değiştirerek daha fazla yetki elde etmeye çalışması.

## 5.2. Olası Etki
- Yetkisiz yönetim erişimi
- Roller ve kritik kayıtların yetkisiz değiştirilmesi
- Kullanıcının sahip olmadığı yetkileri elde etmesi

## 5.3. Güvenlik Kontrolleri
- Backend tarafında RBAC
- Alan bazlı yetkilendirme
- Gerekli işlemlerde nesne seviyesinde yetkilendirme
- İstemcinin gönderdiği rol/yetki değerlerine güvenmeme
- Rol değişikliklerinin yetkili kullanıcılarla sınırlandırılması ve denetlenmesi

---

# 6. Veri Değiştirme

## 6.1. Tehdit Senaryosu
Yetkisiz randevu, kullanıcı, oda, cihaz veya diğer kayıt değişiklikleri ile geçersiz ya da iş kurallarına uymayan verilerin sisteme gönderilmesi.

## 6.2. Olası Etki
- Randevu veya kaynak planlamasının bozulması
- Yetkisiz kayıt oluşturma/düzenleme/iptal
- Kullanıcı veya rol bilgilerinin değiştirilmesi
- Veri bütünlüğünün bozulması

## 6.3. Güvenlik Kontrolleri
- Kimlik doğrulama
- Backend tarafında rol ve yetki kontrolü
- Sunucu tarafı validation
- İş kurallarının kontrolü
- Alan ve gerektiğinde nesne seviyesinde yetkilendirme
- ORM veya parametrik sorgular
- Kritik değişikliklerin denetim kayıtlarına aktarılması

## 6.4. Randevu İşlemlerinde Yetki Sınırı

Randevu oluşturma, düzenleme ve iptal etme yetkisi Psikolog ve Danışma Masası Öğrencisine aittir.

Memur ve Müdür randevuları ve takvimi görüntüleyebilir ancak oluşturamaz, düzenleyemez veya iptal edemez.

## 6.5. Cihaz İşlemlerinde Yetki Sınırı

Cihaz rezervasyonu yalnızca Memur tarafından yapılabilir. Psikolog ve Müdür cihaz uygunluğunu görüntüleyebilir ancak rezervasyon yapamaz. Danışma Masası Öğrencisinin cihaz işlemleri üzerinde yetkisi yoktur.

---

# 7. Veri Sızıntısı

## 7.1. Tehdit Senaryosu
Operasyonel verilerin, kullanıcı bilgilerinin, istisna türü bilgilerinin, gizli yapılandırma değerlerinin veya teknik sistem bilgilerinin yetkisiz kişilere açığa çıkması.

## 7.2. Olası Etki
- Kullanıcı veya operasyonel bilgilerin açığa çıkması
- İstisna türü bilgilerinin yetkisiz görüntülenmesi
- Veritabanı erişim bilgilerinin ele geçirilmesi
- Teknik bilgilerin kötüye kullanılması

## 7.3. Güvenlik Kontrolleri
- Kimlik doğrulama ve yetkilendirme
- Güvenli hata mesajları
- Parolaların hashlenmesi
- Gizli bilgilerin kaynak kod/Git deposunda tutulmaması
- Loglarda gereksiz hassas bilgi tutulmaması
- Yedek erişiminin sınırlandırılması
- Doğrudan PostgreSQL erişiminin engellenmesi

## 7.4. Veri Minimizasyonu ve Danışan Kodu

Danışan, benzersiz ve kalıcı operasyonel danışan kodu ile temsil edilecektir. Aynı danışanın sonraki randevularında aynı kod kullanılacaktır.

Danışan kodu ile ad, T.C. kimlik numarası veya benzeri doğrudan kimlik bilgileri arasında sistem içinde ayrı bir eşleştirme tutulmayacaktır.

Ayrıntılı klinik kayıtlar, terapi kayıtları ve psikolojik değerlendirme kayıtları sistem kapsamında tutulmayacaktır.

Raporlama gereksinimi kapsamında `istisna_turu` alanında:

- `YOK`
- `KANSER_HASTASI`
- `SEHIT_GAZI_YAKINI`

değerleri tutulacaktır. Bu bilgi yalnızca belirlenen operasyonel ve raporlama gereksinimleri kapsamında kullanılacaktır.

---

# 8. Denetim Kayıtlarının Manipülasyonu

## 8.1. Tehdit Senaryosu
Kullanıcının denetim kayıtlarını yetkisiz şekilde değiştirmeye veya silmeye çalışması.

## 8.2. Olası Etki
- Kritik işlem geçmişinin kaybolması
- Kullanıcı işlemlerinin takip edilememesi
- Güvenlik olaylarının incelenmesinin zorlaşması

## 8.3. Güvenlik Kontrolleri
- Normal kullanıcıların denetim kayıtlarını değiştirmesinin/silmesinin engellenmesi
- Denetim kayıtlarına erişimin yetki kontrolüne tabi olması
- Gerekli kayıtların backend tarafından oluşturulması
- İstemciden gönderilen audit bilgilerine doğrudan güvenilmemesi
- Audit kayıtlarında gereksiz hassas bilgi tutulmaması

Temel olaylar:

- `LOGIN`
- `LOGIN_FAILED`
- `CREATE`
- `UPDATE`
- `CANCEL`
- `ROLE_CHANGE`
- `DEVICE_STATUS_CHANGE`

---

# 9. DoS ve Tekrarlanan Giriş Denemeleri

## 9.1. Tehdit Senaryosu
Kısa sürede çok sayıda istek veya çok sayıda başarısız parola denemesi gerçekleştirilmesi.

## 9.2. Olası Etki
- Sistem kaynaklarının tüketilmesi
- Sistemin yavaşlaması
- Hizmet kullanılabilirliğinin azalması
- Parolaların tekrar tekrar tahmin edilmeye çalışılması

## 9.3. Güvenlik Kontrolleri
- Rate-control veya geçici hesap kilitleme mekanizmalarından biri
- Geçersiz girişlerin kontrollü işlenmesi
- `LOGIN_FAILED` olaylarının denetim kayıtlarına aktarılması
- API kötüye kullanımını sınırlandıracak kontroller

Kesin teknik yöntem geliştirme aşamasında belirlenecektir.

---

# 10. Güvenli Hata Yönetimi

Hata cevaplarında SQL sorguları, dosya yolları, stack trace, parola ve gizli yapılandırma değerleri açığa çıkarılmayacaktır.

---

# 11. Gizli Bilgilerin Korunması

Veritabanı parolaları, uygulama anahtarları ve diğer gizli yapılandırma değerleri kaynak kodda veya Git deposunda tutulmayacaktır. Loglarda parola veya benzeri gizli bilgiler tutulmayacaktır.

---

# 12. Yedek Güvenliği

Veritabanı yedeklerine erişim yetkili kullanıcılar veya yetkili sistem süreçleriyle sınırlandırılacaktır. Normal kullanıcıların yedek dosyalarını görüntülemesi veya değiştirmesi engellenecektir.

---

# 13. Genel Güvenlik Kontrolleri

- kimlik doğrulama,
- RBAC,
- endpoint seviyesinde yetkilendirme,
- gerektiğinde nesne seviyesinde yetkilendirme,
- alan bazlı yetkilendirme,
- sunucu tarafı veri doğrulama,
- ORM veya parametrik sorgular,
- parola hashleme,
- pasif kullanıcı girişinin engellenmesi,
- kontrollü hata yönetimi,
- gizli bilgilerin kaynak koddan ayrı tutulması,
- kritik işlemlerin denetim kayıtlarıyla izlenmesi,
- audit kayıtlarının değişiklik/silmeye karşı korunması,
- tekrarlanan giriş denemelerine karşı koruma,
- yedek erişiminin sınırlandırılması,
- doğrudan PostgreSQL erişiminin engellenmesi.

---

# 14. Tehdit Özeti

| Tehdit | Temel Risk | Başlıca Güvenlik Kontrolü |
|---|---|---|
| Yetkisiz erişim | Korunan kaynaklara izinsiz erişim | Kimlik doğrulama ve erişim kontrolü |
| Yetki yükseltme | Sahip olunmayan yetkilerin elde edilmesi | RBAC ve alan bazlı yetkilendirme |
| Veri değiştirme | Kayıtların yetkisiz/hatalı değiştirilmesi | Yetkilendirme, validation ve iş kuralları |
| Veri sızıntısı | Bilgilerin yetkisiz açığa çıkması | Erişim kontrolü ve güvenli bilgi yönetimi |
| Audit manipülasyonu | İşlem geçmişinin değiştirilmesi/silinmesi | Audit kayıtlarının korunması |
| DoS / Brute Force | Kaynak tüketimi veya parola denemeleri | Rate-control veya geçici hesap kilitleme |

---

# 15. Sonuç

Bu tehdit modeli, sistemin V1.0 sürümünde dikkate alınması gereken temel güvenlik tehditlerini ve planlanan güvenlik kontrollerini tanımlar.

Yetkilendirme yalnızca istemci arayüzüne bırakılmayacak, FastAPI backend katmanında uygulanacaktır.

Kullanıcı rolleri, mimari, veri modeli veya erişim yapısında önemli değişiklik yapılırsa tehdit modeli yeniden değerlendirilecektir.
