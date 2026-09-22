# TRAVMA UYGULAMA VE ARAŞTIRMA MERKEZİ

## Bilgi ve Kaynak Yönetim Sistemi

**D02 -- REQUIREMENTS v1**

**Gereksinim Analizi Dokümanı**

-   **Proje:** 8 Haftalık Yazılım Mühendisliği Staj Projesi

-   **Faz:** Hafta 1 -- Gün 2: Gereksinim Analizi

-   **Sürüm:** v1

-   **Kapsam:** V1.0

# 1. Dokümanın Amacı ve Kapsamı

Bu doküman, Bilgi ve Kaynak Yönetim Sistemi V1.0 için Hafta 1 -- Gün 2
kapsamında hazırlanan gereksinim analizinin ilk sürümüdür. Kullanıcı
rolleri, use case'ler, user story'ler, fonksiyonel gereksinimler,
fonksiyonel olmayan gereksinimler ve veri sınırlarını içerir.

Sistem klinik bilgi sistemi değildir. Amaç; randevu, oda, cihaz, bakım,
kalibrasyon, arıza, kullanıcı/rol, dashboard, audit ve yedekleme gibi
operasyonel süreçleri merkezi ve izlenebilir biçimde yönetmektir.

# 2. Kullanıcı Rolleri

## 2.1 Psikolog

-   Sisteme giriş yapabilmeli.

-   Danışan kodu işlemlerini gerçekleştirebilmeli.

-   Randevu oluşturabilmeli, düzenleyebilmeli ve iptal edebilmeli.

-   Günlük/haftalık randevu ve takvim işlemlerini gerçekleştirebilmeli.

-   Oda ve cihaz uygunluğunu kontrol edebilmeli.

-   Yalnızca rolüne tanımlanan yetkiler kapsamında işlem yapabilmeli.

## 2.2 Memur

-   Sisteme giriş yapabilmeli.

-   Cihaz envanteri işlemlerini gerçekleştirebilmeli.

-   Cihaz rezervasyonu yapabilmeli ve müsaitlik durumunu kontrol

    edebilmeli.

-   Bakım, kalibrasyon ve arıza kayıtlarını yönetebilmeli.

-   Yalnızca rolüne tanımlanan yetkiler kapsamında işlem yapabilmeli.

## 2.3 Müdür

-   Sisteme giriş yapabilmeli.

-   Kullanıcı/personel ekleyebilmeli ve pasifleştirebilmeli.

-   Kullanıcılara rol atayabilmeli.

-   Oda ve cihaz yönetimi yapabilmeli.

-   Bakım planlarını ve kalibrasyon periyotlarını tanımlayabilmeli.

-   Dashboard ve temel raporları görüntüleyebilmeli.

-   Audit kayıtlarını inceleyebilmeli.

# 3. Use Case'ler

Use case'ler, kullanıcı rollerinin sistemde gerçekleştirdiği temel

işlemleri tanımlar.

**UC-01 --- Sisteme Giriş Yapma**

**Aktör:** Psikolog, Memur, Müdür

Kullanıcı hesabı doğrulanır ve rolüne uygun yetkilerle sisteme erişim

sağlanır.

**UC-02 --- Danışan Kodu İşlemleri**

**Aktör:** Psikolog

Kişisel/klinik bilgi kaydedilmeden operasyonel danışan kodu üzerinden

işlem yapılır.

**UC-03 --- Randevu Oluşturma**

**Aktör:** Psikolog

Uygun tarih, saat ve kaynaklar kullanılarak yeni randevu oluşturulur.

**UC-04 --- Randevu Düzenleme**

**Aktör:** Psikolog

Mevcut randevunun izin verilen bilgileri güncellenir.

**UC-05 --- Randevu İptal Etme**

**Aktör:** Psikolog

Mevcut randevu iptal edilir.

**UC-06 --- Takvimi Görüntüleme**

**Aktör:** Psikolog

Günlük ve haftalık takvim üzerinden randevu durumları görüntülenir.

**UC-07 --- Oda ve Cihaz Uygunluğunu Kontrol Etme**

**Aktör:** Psikolog

Randevu planlamasında oda ve cihaz uygunluğu kontrol edilir.

**UC-08 --- Cihaz Envanterini Yönetme**

**Aktör:** Memur

Cihaz envanteri işlemleri gerçekleştirilir.

**UC-09 --- Cihaz Rezervasyonu Yapma**

**Aktör:** Memur

Uygun durumdaki cihaz için rezervasyon yapılır.

**UC-10 --- Bakım Kayıtlarını Yönetme**

**Aktör:** Memur

Cihaz bakım kayıtları oluşturulur ve takip edilir.

**UC-11 --- Kalibrasyon Kayıtlarını Yönetme**

**Aktör:** Memur

Kalibrasyon kayıtları oluşturulur ve takip edilir.

**UC-12 --- Arıza Kayıtlarını Yönetme**

**Aktör:** Memur

Arıza kayıtları oluşturulur ve durumları takip edilir.

**UC-13 --- Kullanıcı ve Personel Yönetimi**

**Aktör:** Müdür

Psikolog/memur kullanıcı-personel tanımlanır ve gerektiğinde

pasifleştirilir.

**UC-14 --- Rol Atama**

**Aktör:** Müdür

Kullanıcılara uygun roller atanır.

**UC-15 --- Oda Yönetimi**

**Aktör:** Müdür

Odalar tanımlanır ve durumları yönetilir.

**UC-16 --- Cihaz Yönetimi**

**Aktör:** Müdür

Cihaz ekleme ve cihaz yönetimi işlemleri gerçekleştirilir.

**UC-17 --- Bakım ve Kalibrasyon Yapılandırması**

**Aktör:** Müdür

Bakım planları ve kalibrasyon periyotları tanımlanır.

**UC-18 --- Dashboard ve Temel Raporları Görüntüleme**

**Aktör:** Müdür

Operasyonel durum dashboard ve temel raporlardan izlenir.

**UC-19 --- Audit Kayıtlarını İnceleme**

**Aktör:** Müdür

Audit kapsamındaki işlem kayıtları incelenir.

# 4. User Story'ler

**US-01 --- Sisteme Giriş**

Psikolog, Memur veya Müdür olarak, rolüme tanımlanan sistem

özelliklerine güvenli şekilde erişebilmek için hesabımla sisteme giriş

yapmak istiyorum.

**US-02 --- Danışan Kodu**

Psikolog olarak, kişisel veya klinik bilgi kaydetmeden işlem yapabilmek

için operasyonel danışan kodu üzerinden çalışmak istiyorum.

**US-03 --- Randevu Oluşturma**

Psikolog olarak, randevuları planlayabilmek için uygun tarih ve saatte

randevu oluşturmak istiyorum.

**US-04 --- Randevu Düzenleme**

Psikolog olarak, plan değişikliklerini sisteme yansıtabilmek için mevcut

randevuyu düzenlemek istiyorum.

**US-05 --- Randevu İptal Etme**

Psikolog olarak, gerçekleşmeyecek bir randevuyu sistemde aktif

bırakmamak için iptal etmek istiyorum.

**US-06 --- Takvim Görüntüleme**

Psikolog olarak, randevu planını takip edebilmek için günlük ve haftalık

takvimi görüntülemek istiyorum.

**US-07 --- Oda ve Cihaz Uygunluğu**

Psikolog olarak, randevuyu uygun kaynaklarla planlayabilmek için oda ve

cihaz uygunluğunu kontrol etmek istiyorum.

**US-08 --- Cihaz Envanteri**

Memur olarak, merkezde kullanılan cihazları takip edebilmek için cihaz

envanteri işlemlerini gerçekleştirmek istiyorum.

**US-09 --- Cihaz Rezervasyonu**

Memur olarak, cihaz kullanımını planlayabilmek için uygun cihaz için

rezervasyon yapmak istiyorum.

**US-10 --- Bakım Kayıtları**

Memur olarak, cihaz bakım süreçlerini takip edebilmek için bakım

kayıtlarını yönetmek istiyorum.

**US-11 --- Kalibrasyon Kayıtları**

Memur olarak, kalibrasyon süreçlerini takip edebilmek için kalibrasyon

kayıtlarını yönetmek istiyorum.

**US-12 --- Arıza Kayıtları**

Memur olarak, cihaz arızalarını takip edebilmek için arıza kayıtlarını

yönetmek istiyorum.

**US-13 --- Kullanıcı ve Personel Yönetimi**

Müdür olarak, sisteme erişecek personeli yönetebilmek için psikolog ve

memur tanımlamak ve gerektiğinde pasifleştirmek istiyorum.

**US-14 --- Rol Atama**

Müdür olarak, kullanıcıların doğru yetkilere sahip olmasını sağlamak

için rol atamak istiyorum.

**US-15 --- Oda Yönetimi**

Müdür olarak, randevu planlamasında kullanılacak odaları yönetmek

istiyorum.

**US-16 --- Cihaz Yönetimi**

Müdür olarak, merkez cihazlarının sistemde tanımlı olmasını sağlamak

için cihaz eklemek ve bilgilerini yönetmek istiyorum.

**US-17 --- Bakım ve Kalibrasyon Yapılandırması**

Müdür olarak, bakım ve kalibrasyon süreçlerini planlayabilmek için

periyotları tanımlamak istiyorum.

**US-18 --- Dashboard ve Raporlar**

Müdür olarak, merkezin operasyonel durumunu takip edebilmek için

dashboard ve temel raporları görüntülemek istiyorum.

**US-19 --- Audit Kayıtları**

Müdür olarak, kritik işlemleri inceleyebilmek için audit kayıtlarını

görüntülemek istiyorum.

# 5. Fonksiyonel Gereksinimler

## 5.1 Kimlik Doğrulama ve Yetkilendirme

**FR-001 --- Kullanıcı Girişi:** Sistem, kayıtlı

kullanıcıların

hesapları ile giriş yapabilmesini sağlamalıdır.

**FR-002 --- Rol Tabanlı Yetkilendirme:** Sistem,

kullanıcıların

Psikolog, Memur ve Müdür rollerine göre yetkilendirilmesini

sağlamalıdır.

**FR-003 --- Yetkiye Göre Erişim:** Sistem, kullanıcının

yalnızca rolüne

tanımlanmış işlemleri gerçekleştirmesine izin vermelidir.

**FR-004 --- Pasif Kullanıcı Kontrolü:** Sistem, pasif

kullanıcıların

giriş yapmasını engellemelidir.

**FR-005 --- Oturum/Token Kontrolü:** Sistem, korunan API

işlemlerinde

geçerli oturum/token kontrolü gerçekleştirmelidir.

## 5.2 Danışan Kodu Yönetimi

**FR-006 --- Operasyonel Danışan Kodu:** Danışanlar

operasyonel danışan

kodları ile temsil edilmelidir.

**FR-007 --- Danışan Kodu Oluşturma:** Sistem, operasyonel

danışan

kodlarının oluşturulmasını sağlamalıdır.

**FR-008 --- Kişisel Veri Ayrımı:** Operasyonel danışan

kodunu gerçek

kişiyle eşleştiren kayıt veya tablo bulunmamalıdır.

## 5.3 Randevu ve Takvim Yönetimi

**FR-009 --- Randevu Oluşturma:** Yetkili kullanıcı yeni

randevu

oluşturabilmelidir.

**FR-010 --- Randevu Düzenleme:** Yetkili kullanıcı mevcut

randevuyu

düzenleyebilmelidir.

**FR-011 --- Randevu İptali:** Yetkili kullanıcı mevcut

randevuyu iptal

edebilmelidir.

**FR-012 --- Günlük Takvim:** Günlük randevu takvimi

görüntülenebilmelidir.

**FR-013 --- Haftalık Takvim:** Haftalık randevu takvimi

görüntülenebilmelidir.

**FR-014 --- Psikolog Çakışma Kontrolü:** Aynı psikolog

çakışan

zamanlarda iki aktif randevuya atanamamalıdır.

**FR-015 --- Oda Çakışma Kontrolü:** Aynı oda çakışan

zamanlarda iki

aktif randevuda kullanılamamalıdır.

**FR-016 --- Cihaz Çakışma Kontrolü:** Aynı cihaz çakışan

zamanlarda iki

aktif randevuda kullanılamamalıdır.

## 5.4 Oda Yönetimi

**FR-017 --- Oda Tanımlama:** Yetkili kullanıcı sisteme oda

ekleyebilmelidir.

**FR-018 --- Oda Pasifleştirme:** Yetkili kullanıcı odayı

pasifleştirebilmelidir.

**FR-019 --- Oda Uygunluğu:** Randevu planlamasında oda

uygunluğu

kontrol edilebilmelidir.

## 5.5 Cihaz Yönetimi ve Rezervasyon

**FR-020 --- Cihaz Ekleme:** Yetkili kullanıcı envantere

yeni cihaz

ekleyebilmelidir.

**FR-021 --- Cihaz Düzenleme:** Yetkili kullanıcı cihaz

bilgilerini

düzenleyebilmelidir.

**FR-022 --- Cihaz Pasifleştirme:** Cihaz gerektiğinde pasif

duruma

getirilebilmelidir.

**FR-023 --- Cihaz Durumu Yönetimi:** Cihaz durumları

Kullanılabilir,

Rezerve, Bakımda, Arızalı, Kalibrasyonda ve Kullanım Dışı değerlerini

desteklemelidir.

**FR-024 --- Cihaz Rezervasyonu:** Uygun durumdaki cihaz

için

rezervasyon oluşturulabilmelidir.

**FR-025 --- Cihaz Müsaitlik Kontrolü:** Rezervasyon/randevu

öncesinde

cihaz uygunluğu kontrol edilebilmelidir.

**FR-026 --- Rezervasyon Engelleme:** Bakımda, Arızalı,

Kalibrasyonda

veya Kullanım Dışı cihazlar rezerve edilememelidir.

**FR-027 --- Eşzamanlı Rezervasyon Kontrolü:** Aynı cihaz

için eşzamanlı

iki istekte yalnızca geçerli işlem oluşmalı ve veri bütünlüğü

korunmalıdır.

## 5.6 Bakım, Kalibrasyon ve Arıza Yönetimi

**FR-028 --- Bakım Kaydı:** Cihaz bakım kayıtları

oluşturulabilmelidir.

**FR-029 --- Bakım Geçmişi:** Cihaz bakım geçmişi takip

edilebilmelidir.

**FR-030 --- Sonraki Bakım:** Sonraki bakım bilgileri takip

edilebilmelidir.

**FR-031 --- Kalibrasyon Kaydı:** Kalibrasyon kayıtları

oluşturulabilmelidir.

**FR-032 --- Arıza Kaydı:** Arıza kayıtları

oluşturulabilmelidir.

**FR-033 --- Arıza Durumu:** Arıza durumları takip

edilebilmelidir.

## 5.7 Müdür Yönetim İşlemleri

**FR-034 --- Kullanıcı Oluşturma:** Müdür yeni kullanıcı

oluşturabilmelidir.

**FR-035 --- Personel Tanımlama:** Müdür psikolog ve memur

personel

tanımlayabilmelidir.

**FR-036 --- Rol Atama:** Müdür kullanıcılara rol

atayabilmelidir.

**FR-037 --- Kullanıcı Pasifleştirme:** Müdür

kullanıcı/personel

hesaplarını pasifleştirebilmelidir.

**FR-038 --- Bakım Yapılandırması:** Müdür bakım türü,

periyodu ve

ilgili ayarları tanımlayabilmelidir.

**FR-039 --- Kalibrasyon Yapılandırması:** Müdür kalibrasyon

periyodu ve

ilgili ayarları tanımlayabilmelidir.

## 5.8 Dashboard ve Raporlama

**FR-040 --- Dashboard:** Dashboard; bugünkü randevular,

aktif/arızalı/bakımda cihazlar, yaklaşan bakımlar, kalibrasyonlar ve

açık arızalar gibi temel bilgileri göstermelidir.

**FR-041 --- Temel Raporlar:** V1.0 kapsamındaki temel

operasyonel

raporlar görüntülenebilmelidir.

## 5.9 Audit

**FR-042 --- Audit Kaydı Oluşturma:** Audit kapsamındaki

kullanıcı ve

sistem işlemleri kayıt altına alınmalıdır.

**FR-043 --- Audit İşlem Türleri:** Audit en az LOGIN,

LOGIN_FAILED,

CREATE, UPDATE, CANCEL, ROLE_CHANGE ve DEVICE_STATUS_CHANGE türlerini

desteklemelidir.

**FR-044 --- Audit Görüntüleme:** Müdür audit kayıtlarını

inceleyebilmelidir.

**FR-045 --- Audit Bütünlüğü:** Normal kullanıcılar audit

kayıtlarını

değiştirememeli veya silememelidir.

## 5.10 Yedekleme ve Geri Yükleme

**FR-046 --- PostgreSQL Yedekleme:** PostgreSQL veritabanı

yedeklenebilmelidir.

**FR-047 --- Otomatik Yedekleme:** Otomatik yedekleme

desteklenmelidir.

**FR-048 --- Yedek Tarih Bilgisi:** Yedekler tarih damgası

ile takip

edilebilmelidir.

**FR-049 --- Yedek Rotasyonu:** Yedek rotasyonu

gerçekleştirilebilmelidir.

**FR-050 --- Geri Yükleme:** Yedek yeni bir veritabanına

geri

yüklenebilmelidir.

**FR-051 --- Geri Yükleme Doğrulaması:** Restore sonrası

uygulama ve

veriler doğrulanabilmelidir.

# 6. Fonksiyonel Olmayan Gereksinimler

## 6.1 Güvenlik

-   Sistem kimlik doğrulama ve RBAC mekanizmalarına sahip olmalıdır.

-   Parolalar düz metin tutulmamalı, güvenli şekilde hashlenmelidir.

-   Pasif kullanıcıların girişi engellenmelidir.

-   Çok sayıda hatalı girişe karşı rate-control veya geçici kilitleme

    uygulanmalıdır.

-   Kullanıcı girdileri sunucu tarafında doğrulanmalıdır.

-   ORM/parametrik sorgular kullanılmalı; SQL injection riski

    azaltılmalıdır.

-   Hata mesajları stack trace, SQL, dosya yolu, parola veya secret gibi

    hassas teknik bilgi sızdırmamalıdır.

-   Parola, database credential ve token secret gibi gizli bilgiler

    repository içerisinde tutulmamalıdır.

-   Normal kullanıcılar audit kayıtlarını değiştirememeli veya

    silememelidir.

## 6.2 Güvenilirlik ve Veri Bütünlüğü

-   İşlemler sırasında veri bütünlüğü korunmalıdır.

-   Yarım kalan/başarısız işlemler tutarsız kayıt oluşturmamalıdır.

-   Eşzamanlı işlemler veri tutarsızlığına yol açmamalıdır.

-   Çakışan psikolog, oda veya cihaz kullanımı engellenmelidir.

-   Uygun olmayan cihaz durumlarında rezervasyon engellenmelidir.

-   Yedekleme ve geri yükleme mekanizması bulunmalı; restore test

    edilmelidir.

## 6.3 Test Edilebilirlik

-   Unit, integration, security ve acceptance testleri

    uygulanabilmelidir.

-   Her geliştirilen özellik için uygun testler yazılmalıdır.

-   Authentication, authorization, input validation, injection,

    brute-force, token ve error leakage senaryoları test

    edilebilmelidir.

-   Test sonuçları PASS/FAIL olarak kayıt altına alınabilmelidir.

-   Kritik testlerin geçmesi canlıya geçiş ön koşulu olmalıdır.

## 6.4 Bakım Yapılabilirlik ve Sürdürülebilirlik

-   Kod ekipteki diğer geliştiriciler tarafından okunabilir ve

    incelenebilir olmalıdır.

-   Proje istemci, sunucu, veritabanı, test ve dokümantasyon

    bileşenlerine ayrılmalıdır.

-   Değişiklikler Git ile takip edilmelidir.

-   Doğrudan main dalında geliştirme yapılmamalıdır.

-   Her görev Issue ve feature branch ile ilişkilendirilmeli; Pull

    Request ve Code Review sürecinden geçmelidir.

-   CI ve testler geçmeden merge yapılmamalıdır.

-   Dokümantasyon güncel tutulmalıdır.

## 6.5 Mimari ve Erişim

-   Sistem üç katmanlı mimariye uygun geliştirilmelidir.

-   PySide6 istemci backend ile REST API üzerinden haberleşmelidir.

-   İstemciler PostgreSQL'e doğrudan bağlanmamalıdır.

-   Veritabanı erişimi backend/business logic üzerinden

    gerçekleştirilmelidir.

-   V1.0 kapsamında internet üzerinden dış erişim sağlanmamalıdır.

-   İstemci bilgisayarların ana bilgisayardaki API'ye erişimi

    doğrulanmalıdır.

## 6.6 Kurulum ve Çalıştırılabilirlik

-   Sistem kontrollü şekilde kurulabilir ve çalıştırılabilir bir ürün

    olarak hazırlanmalıdır.

-   İstemci uygulaması kullanıcı bilgisayarlarına kurulabilir biçimde

    hazırlanmalıdır.

-   API ve PostgreSQL production ortamında çalıştırılabilir olmalıdır.

-   Kurulum, backup ve restore işlemleri dokümante edilmelidir.

## 6.7 Performans -- Netleştirilecek Gereksinimler

Ana proje belgesinde kesin eşzamanlı kullanıcı sayısı veya API yanıt

süresi belirtilmemiştir. Aşağıdaki değerler ekip ve merkez

gereksinimleri doğrultusunda daha sonra ölçülebilir kabul kriterlerine

dönüştürülmelidir:

-   Desteklenecek eşzamanlı kullanıcı sayısı.

-   Normal API işlemleri için kabul edilebilir maksimum yanıt süresi.

-   Randevu ve cihaz rezervasyonu gibi kritik işlemler için kabul

    edilebilir maksimum işlem süresi.

-   Gerekli görülürse performans testlerinin kapsamı.

# 7. Veri Sınırları

Sistem bir klinik bilgi sistemi değildir. Danışan yalnızca operasyonel

kod ile temsil edilir.

## 7.1 Sisteme Girilmeyecek Veriler

-   Ad-soyad

-   T.C. kimlik numarası

-   Telefon

-   Kişisel e-posta

-   Adres

-   Tanı

-   Terapi notu

-   Travma öyküsü

-   İlaç bilgisi

-   Psikolojik değerlendirme

-   Test/ölçek sonucu

-   Klinik gözlem

-   Sağlık bilgisi

-   Serbest danışan açıklaması

## 7.2 Operasyonel Danışan Kodu

-   Danışan yalnızca operasyonel bir kod ile temsil edilmelidir (ör.

    DN-2026-0048).

-   Sistem içinde operasyonel kodu gerçek kişiyle eşleştiren tablo

    bulunmamalıdır.

-   Hassas kişisel/klinik bilgiler audit veya diğer log kayıtlarına

    yazılmamalıdır.
