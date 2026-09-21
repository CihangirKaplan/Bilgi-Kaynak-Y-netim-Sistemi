# Kullanıcı, Güvenlik ve Ağ Gereksinimleri

## 1. Kullanıcı Gereksinimleri

### Psikolog

- Sisteme giriş yapabilmeli.

- Danışan kodu işlemlerini gerçekleştirebilmeli.

- Randevu oluşturabilmeli.

- Randevu düzenleyebilmeli.

- Randevu iptal edebilmeli.

- Randevu ve takvim işlemlerini gerçekleştirebilmeli.

- Oda kullanım durumunu kontrol edebilmeli.

- Cihaz uygunluğunu kontrol edebilmeli.

- Yalnızca kendisine tanımlanan yetkiler kapsamında işlem yapabilmeli.

### Memur

- Sisteme giriş yapabilmeli.

- Cihaz envanteri işlemlerini gerçekleştirebilmeli.

- Cihaz rezervasyonu yapabilmeli.

- Cihazların müsaitlik durumunu kontrol edebilmeli.

- Bakım kayıtlarını yönetebilmeli.

- Kalibrasyon kayıtlarını yönetebilmeli.

- Arıza kayıtlarını yönetebilmeli.

- Yalnızca kendisine tanımlanan yetkiler kapsamında işlem yapabilmeli.

### Müdür

- Sisteme giriş yapabilmeli.

- Kullanıcı ekleyebilmeli.

- Psikolog ve memur personel tanımlayabilmeli.

- Kullanıcı/personel hesaplarını pasifleştirebilmeli.

- Kullanıcılara rol atayabilmeli.

- Oda ekleyebilmeli ve oda durumlarını yönetebilmeli.

- Cihaz ekleyebilmeli ve cihaz bilgilerini yönetebilmeli.

- Bakım planlarını ve periyotlarını tanımlayabilmeli.

- Kalibrasyon periyotlarını tanımlayabilmeli.

- Dashboard ve temel raporları görüntüleyebilmeli.

- Audit kayıtlarını inceleyebilmeli.

## 2. Güvenlik Gereksinimleri

- Kullanıcı şifreleri düz metin olarak saklanmayacak; güvenli bir parola hashleme yöntemi kullanılacak.

- Sistem kimlik doğrulama (authentication) mekanizmasına sahip olacak.

- Sistem rol tabanlı yetkilendirme (RBAC) uygulayacak.

- Kullanıcılar yalnızca kendilerine tanımlanan rol ve yetkiler kapsamında işlem yapabilecek.

- Pasif/deaktif kullanıcıların sisteme giriş yapması engellenecek.

- Kimlik doğrulaması yapılmadan korunan API endpointlerine erişim engellenecek.

- Yetkisi bulunmayan kullanıcının başka bir role ait işlemleri gerçekleştirmesi engellenecek.

- Kullanıcının API üzerinden yetkisi olmayan alanları değiştirerek ayrıcalık kazanması engellenecek.

- Geçersiz, süresi dolmuş veya bulunmayan token ile korunan kaynaklara erişim engellenecek.

- Çok sayıda hatalı parola denemesine karşı rate-control veya geçici kilitleme mekanizması uygulanacak.

- Kullanıcı girişleri ve kritik işlemler audit kayıtlarında tutulacak. Audit kapsamında LOGIN, LOGIN_FAILED, CREATE, UPDATE, CANCEL, ROLE_CHANGE ve DEVICE_STATUS_CHANGE gibi işlemler izlenebilir olacak.

- Audit kayıtlarını değiştirme veya silme yetkisi bulunmayan kullanıcıların bu kayıtlar üzerinde değişiklik yapması veya kayıtları silmesi engellenecek.

- Danışanlara ait kişisel ve klinik bilgiler sisteme girilmeyecek. Ad-soyad, T.C. kimlik numarası, telefon, kişisel e-posta, adres, tanı, terapi notu, travma öyküsü, ilaç bilgisi, psikolojik değerlendirme, test/ölçek sonucu, klinik gözlem ve sağlık bilgisi tutulmayacak.

- Danışanlar yalnızca operasyonel danışan kodları ile temsil edilecek ve sistem içerisinde bu kodları gerçek kişilerle eşleştiren bir tablo bulunmayacak.

- Sisteme gönderilen kullanıcı girdileri sunucu tarafında doğrulanacak.

- Null değer, aşırı uzun metin, geçersiz tarih, negatif ID, hatalı enum ve beklenmeyen alan gibi geçersiz girdiler kontrollü 4xx hata yanıtları ile reddedilecek.

- Veritabanı işlemlerinde ORM/parametrik sorgular kullanılacak ve kullanıcı girdilerinin SQL sorgularını doğrudan etkilemesi engellenecek.

- Hata mesajlarında stack trace, SQL sorgusu, dosya yolu, parola veya secret gibi hassas teknik bilgiler açığa çıkarılmayacak.

- Parola, veritabanı kimlik bilgileri ve token secret gibi gizli bilgiler kaynak kodda/repository içerisinde tutulmayacak.

- Yedek dosyalarına erişim yetkisi bulunmayan kullanıcıların bu dosyalara erişmesi engellenecek.

## 3. Ağ Gereksinimleri

- V1.0 kapsamında sistem için internet üzerinden dış erişim sağlanmayacak.

- Masaüstü istemci uygulaması PySide6 kullanılarak geliştirilecek.

- İstemci uygulaması backend sistemi ile REST API üzerinden haberleşecek.

- Backend katmanında FastAPI kullanılacak.

- Merkezi veritabanı olarak PostgreSQL kullanılacak.

- Masaüstü istemci bilgisayarların PostgreSQL veritabanına doğrudan bağlanmasına izin verilmeyecek.

- Sistem bağlantı mimarisi aşağıdaki şekilde olacak:

`PySide6 Masaüstü İstemci → REST API / FastAPI → Business Logic → PostgreSQL`

- İstemci bilgisayarların ana bilgisayarda çalışan API'ye erişebilmesi sağlanacak.

- İstemci bilgisayarların ana bilgisayarda çalışan API'ye erişimi test edilecek ve ağ bağlantısının düzgün çalıştığı doğrulanacak.
