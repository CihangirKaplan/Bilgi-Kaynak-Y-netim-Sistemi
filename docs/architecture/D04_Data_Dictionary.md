# Veritabanı Veri Sözlüğü (Data Dictionary)

> Kaynak: PostgreSQL `public` şeması. Bu belge gerçek veritabanı sütun tipleri ve tanımlı kısıtlara göre hazırlanmıştır.
> Veritabanı: `crkys` · Uygulama tablosu: **29** · Teknik sürüm tablosu: **1**.

## PostgreSQL ENUM tipleri

Aşağıdaki ENUM tipleri şemada tanımlıdır. Bir tipin tanımlı olması, benzer amaçlı `VARCHAR` sütunlarının o ENUM tipini kullandığı anlamına gelmez.

- **`cihaz_durumu`:** `Kullanima_Hazir`, `Rezerve`, `Kullanimda`, `Arizali`, `Bakimda`, `Kalibrasyonda`, `Kullanim_Disi`
- **`denetim_olay_turu`:** `LOGIN`, `LOGIN_FAILED`, `CREATE`, `UPDATE`, `CANCEL`, `ROLE_CHANGE`, `DEVICE_STATUS_CHANGE`, `DELETE`, `PASSWORD_RESET`, `PASSWORD_CHANGE`, `PASSWORD_CHANGE_FAILED`
- **`ogrenci_turu`:** `GONULLU`, `DANISMA_MASASI`, `ASISTAN`

## Notasyon

- **PK:** Primary Key; **FK:** Foreign Key; **UNIQUE:** benzersizlik; **CHECK:** veri doğrulama; **EXCLUDE:** çakışmayı engelleyen kısıt.
- `NULL` ve `NOT NULL` doğrudan PostgreSQL sütun tanımından alınmıştır. `DEFAULT` belirtilmemişse veritabanı varsayılanı yoktur.
- `SERIAL` ve `BIGSERIAL` ifadeleri, PostgreSQL'de sequence tabanlı otomatik artan `INTEGER`/`BIGINT` alanlarını açıklamak için kullanılmıştır.
- **FK olmayan kimlik alanları:** Bir sütunun adı başka tabloya işaret etse bile, veritabanında FK tanımlı değilse FK olarak gösterilmez.

## 1. Cihaz ve Bölüm Yönetimi Modülü

Merkeze ait cihazların envanter, rezervasyon, bakım, arıza, kalibrasyon ve takip süreçleri.

### Tablo: `bolumler`

| Kolon Adı | Veri Tipi | Kısıtlamalar (Constraints) | Açıklama |
| :--- | :--- | :--- | :--- |
| `bolum_id` | SERIAL (INTEGER) | PK; NOT NULL | Bölümün benzersiz kimliği. |
| `bolum_adi` | VARCHAR(150) | UNIQUE (büyük/küçük harf duyarsız: `ux_bolumler_bolum_adi_ci`); NOT NULL | Bölümün adı (Örn: Nöroloji Lab). |
| `sorumlu_ad_soyad` | VARCHAR(100) | NOT NULL | Cihazı teslim alan yetkilinin adı soyadı. |
| `iletisim_bilgisi` | VARCHAR(100) | NULL | Telefon veya dahili numara. |
| `aktif_mi` | BOOLEAN | NULL; DEFAULT `true` | Bölümün aktiflik durumu. |

Bölümler Cihaz Rezervasyonu formundaki "Bölüm" listesinden seçilir; listede olmayan bölüm aynı formdaki "＋ Yeni bölüm" düğmesiyle eklenir.

### Tablo: `proje_turleri`

| Kolon Adı | Veri Tipi | Kısıtlamalar (Constraints) | Açıklama |
| :--- | :--- | :--- | :--- |
| `proje_turu_id` | SERIAL (INTEGER) | PK; NOT NULL | Proje türünün benzersiz kimliği. |
| `ad` | VARCHAR(50) | NOT NULL; benzersiz indeks `ux_proje_turleri_ad` (`lower(ad)`) | Proje türü adı (Örn: Araştırma, Test). |
| `aktif_mi` | BOOLEAN | NOT NULL; DEFAULT `true` | Listede gösterilip gösterilmeyeceği. |

Cihaz Rezervasyonu formundaki "Proje türü" listesini besler; yeni tür aynı formdan eklenir. `cihaz_rezervasyonlari.proje_turu` sütunu metin olarak kalır (eski kayıtlar değişmez). Başlangıç listesi migrasyonla (`c8f2a5d1e704`) varsayılan türlerden ve mevcut rezervasyonlarda geçen türlerden oluşturulur.

### Tablo: `cihazlar`

| Kolon Adı | Veri Tipi | Kısıtlamalar (Constraints) | Açıklama |
| :--- | :--- | :--- | :--- |
| `cihaz_id` | SERIAL (INTEGER) | PK; NOT NULL | Cihazın benzersiz kimliği. |
| `envanter_kodu` | VARCHAR(50) | UNIQUE; NOT NULL | Kurum içi cihaz takip kodu. |
| `cihaz_adi` | VARCHAR(100) | NOT NULL | Cihazın genel adı. |
| `marka_model` | VARCHAR(100) | NULL | Cihazın marka ve modeli. |
| `seri_no` | VARCHAR(100) | UNIQUE; NULL | Üretici seri numarası. |
| `durum` | VARCHAR(50) | NULL; DEFAULT `'Kullanılabilir'::character varying` | Cihazın durumunu tutan metin alanı; PostgreSQL ENUM sütunu değildir. |
| `kayit_tarihi` | TIMESTAMP | NULL; DEFAULT `CURRENT_TIMESTAMP` | Sisteme eklenme zamanı. |

### Tablo: `cihaz_rezervasyonlari`

| Kolon Adı | Veri Tipi | Kısıtlamalar (Constraints) | Açıklama |
| :--- | :--- | :--- | :--- |
| `rezervasyon_id` | SERIAL (INTEGER) | PK; NOT NULL | Rezervasyonun benzersiz kimliği. |
| `cihaz_id` | INTEGER | FK → `cihazlar(cihaz_id)`; NOT NULL | Rezerve edilen cihaz. |
| `bolum_id` | INTEGER | FK → `bolumler(bolum_id)`; NULL | Rezervasyonu yapan bölüm (formda seçilir; eski kayıtlarda boş olabilir). |
| `rezervasyonu_yapan_personel_id` | INTEGER | FK → `kullanicilar(personel_id)`; NULL | İşlemi gerçekleştiren personel. |
| `baslangic_zamani` | TIMESTAMP | NOT NULL | Rezervasyon başlangıcı. |
| `bitis_zamani` | TIMESTAMP | NOT NULL | Rezervasyon bitişi. |
| `iptal_edildi_mi` | BOOLEAN | NOT NULL; DEFAULT `false` | İptal durumu. |
| `kullanilacak_oda_id` | INTEGER | FK → `odalar(oda_id)`; NULL | Cihazın kullanılacağı fiziksel oda. |
| `proje_turu` | VARCHAR(50) | NULL | Rezervasyonun ilişkili olduğu proje türü. |
| `proje_adi_aciklamasi` | VARCHAR(255) | NULL | İlgili projenin adı veya açıklaması. |

**CHECK kısıtları:**

- `cihaz_rezervasyon_zaman_kontrol`: `baslangic_zamani < bitis_zamani`

**EXCLUDE kısıtları:**

- `cihaz_rezervasyon_cakisma`: `EXCLUDE USING gist (cihaz_id WITH =, tsrange(baslangic_zamani, bitis_zamani, '[)'::text) WITH &&) WHERE ((iptal_edildi_mi = false))`

### Tablo: `cihaz_arizalari`

| Kolon Adı | Veri Tipi | Kısıtlamalar (Constraints) | Açıklama |
| :--- | :--- | :--- | :--- |
| `ariza_id` | SERIAL (INTEGER) | PK; NOT NULL | Arıza kaydının kimliği. |
| `cihaz_id` | INTEGER | FK → `cihazlar(cihaz_id)`; NOT NULL | Arızalanan cihaz. |
| `bildiren_personel` | VARCHAR(100) | NULL | Arızayı tespit/ihbar eden kişi. |
| `ariza_baslik` | VARCHAR(150) | NOT NULL | Arızanın kısa başlığı. |
| `ariza_aciklamasi` | TEXT | NOT NULL | Arızanın detayı. |
| `aciliyet` | VARCHAR(20) | NOT NULL; DEFAULT `Orta`; CHECK (`Düşük`, `Orta`, `Yüksek`, `Kritik`) | Arıza aciliyet derecesi. |
| `bildirim_tarihi` | TIMESTAMP | NULL; DEFAULT `CURRENT_TIMESTAMP` | Arızanın sisteme girildiği tarih. |
| `cozum_tarihi` | TIMESTAMP | NULL | Arızanın giderildiği tarih. |
| `cozuldu_mu` | BOOLEAN | NULL; DEFAULT `false` | Arıza onarım durumu. |

### Tablo: `cihaz_bakimlari`

| Kolon Adı | Veri Tipi | Kısıtlamalar (Constraints) | Açıklama |
| :--- | :--- | :--- | :--- |
| `bakim_id` | SERIAL (INTEGER) | PK; NOT NULL | Bakım işleminin kimliği. |
| `cihaz_id` | INTEGER | FK → `cihazlar(cihaz_id)`; NOT NULL | Bakım yapılan cihaz. |
| `bakim_yapan_kisi` | VARCHAR(100) | NULL | İşlemi gerçekleştiren kişi/firma. |
| `yapilan_islem` | TEXT | NULL | Uygulanan bakımın detayı. |
| `maliyet` | NUMERIC(10, 2) | NULL | Bakım maliyeti. |
| `bakim_tarihi` | TIMESTAMP | NULL; DEFAULT `CURRENT_TIMESTAMP` | Bakımın gerçekleştiği tarih. |
| `sonraki_bakim_tarihi` | DATE | NULL | Planlanan bir sonraki bakım tarihi. |
| `bakim_baslangic_tarihi` | DATE | NULL | Bakım sürecinin başlangıç tarihi. |
| `bakim_bitis_tarihi` | DATE | NULL | Bakım sürecinin bitiş tarihi. |
| `uyari_suresi_gun` | INTEGER | NOT NULL; DEFAULT `30` | Bakım tarihi yaklaşırken kullanılacak gün cinsinden uyarı süresi. |
| `plan_id` | INTEGER | FK → `cihaz_bakim_planlari(plan_id)` ON DELETE SET NULL; NULL | Kaydın yerine getirdiği bakım planı (plansız kayıtta boş). |

**CHECK kısıtları:**

- `ck_cihaz_bakimlari_uyari_suresi_gun`: `uyari_suresi_gun >= 0 AND uyari_suresi_gun <= 365`

### Tablo: `cihaz_kalibrasyonlari`

| Kolon Adı | Veri Tipi | Kısıtlamalar (Constraints) | Açıklama |
| :--- | :--- | :--- | :--- |
| `kalibrasyon_id` | SERIAL (INTEGER) | PK; NOT NULL | Kalibrasyon kaydının kimliği. |
| `cihaz_id` | INTEGER | FK → `cihazlar(cihaz_id)`; NOT NULL | Kalibre edilen cihaz. |
| `kalibrasyon_yapan_kurum` | VARCHAR(100) | NULL | Kalibrasyonu sağlayan akredite kurum. |
| `gecerlilik_tarihi` | DATE | NULL | Sertifikanın son geçerlilik tarihi. |
| `sertifika_no` | VARCHAR(100) | NULL | Belge numarası. |
| `islem_tarihi` | TIMESTAMP | NULL; DEFAULT `CURRENT_TIMESTAMP` | İşlemin yapıldığı tarih. |
| `kalibrasyon_baslangic_tarihi` | DATE | NULL | Kalibrasyon sürecinin başlangıç tarihi. |
| `kalibrasyon_bitis_tarihi` | DATE | NULL | Kalibrasyon sürecinin bitiş tarihi. |
| `uyari_suresi_gun` | INTEGER | NOT NULL; DEFAULT `30` | Kalibrasyon tarihi yaklaşırken kullanılacak gün cinsinden uyarı süresi. |
| `plan_id` | INTEGER | FK → `cihaz_bakim_planlari(plan_id)` ON DELETE SET NULL; NULL | Kaydın yerine getirdiği kalibrasyon planı (plansız kayıtta boş). |

**CHECK kısıtları:**

- `ck_cihaz_kalibrasyonlari_uyari_suresi_gun`: `uyari_suresi_gun >= 0 AND uyari_suresi_gun <= 365`

### Tablo: `cihaz_bakim_planlari`

| Kolon Adı | Veri Tipi | Kısıtlamalar (Constraints) | Açıklama |
| :--- | :--- | :--- | :--- |
| `plan_id` | SERIAL (INTEGER) | PK; NOT NULL | Bakım veya takip planının benzersiz kimliği. |
| `cihaz_id` | INTEGER | FK → `cihazlar(cihaz_id)`; NOT NULL | Planın ilişkili olduğu cihaz. |
| `gorev_turu` | VARCHAR(100) | NOT NULL | Planlanan görev veya işlem türü. |
| `periyot_gun` | INTEGER | NOT NULL | Görevin tekrar aralığı (gün). |
| `uyari_suresi_gun` | INTEGER | NULL; DEFAULT `1` | Planlanan görev öncesindeki uyarı süresi (gün). |
| `sonraki_gorev_tarihi` | DATE | NOT NULL | Görevin bir sonraki planlanan tarihi. |
| `aktif_mi` | BOOLEAN | NULL; DEFAULT `true` | Planın etkinlik durumu. |

## 2. Randevu ve Oda Yönetimi Modülü

Danışan kodları, odalar, psikolog atamaları, randevular ve oda etkinlikleri.

### Tablo: `danisan_kodlari`

| Kolon Adı | Veri Tipi | Kısıtlamalar (Constraints) | Açıklama |
| :--- | :--- | :--- | :--- |
| `danisan_kod_id` | VARCHAR(50) | PK; NOT NULL | Danışanı temsil eden anonim operasyonel kod. |
| `ucretli_mi` | BOOLEAN | NOT NULL; DEFAULT `true` | Hizmetin ücretli/ücretsiz durumu. |
| `istisna_turu` | VARCHAR(50) | NULL; DEFAULT `'YOK'::character varying` | Ücretsiz olma gerekçesi (Örn: Şehit/Gazi yakını). |
| `aktif_mi` | BOOLEAN | NOT NULL; DEFAULT `true` | Kodun geçerlilik durumu. |
| `olusturulma_tarihi` | TIMESTAMP | NOT NULL; DEFAULT `CURRENT_TIMESTAMP` | Kodun sisteme eklendiği tarih. |
| `olusturan_psikolog_id` | INTEGER | FK → `kullanicilar(personel_id)`; NULL | Danışan kodunu oluşturan psikoloğun personel kimliği. |
| `yas_grubu` | VARCHAR(20) | NULL | Danışanın yaş grubu; COCUK veya YETISKIN olabilir. |
| `psikolog_pasifligi_nedeniyle_pasif` | BOOLEAN | NOT NULL; DEFAULT `false` | Kod, oluşturan psikolog pasife alındığı için pasife alındıysa `true`; psikolog yeniden aktif edilince yalnızca bu kodlar geri açılır. Elle yapılan durum değişikliği işareti temizler. |

**CHECK kısıtları:**

- `danisan_kodlari_yas_grubu_gecerli`: `yas_grubu IS NULL OR (yas_grubu::text = ANY (ARRAY['COCUK'::character varying, 'YETISKIN'::character varying]::text[]))`

### Tablo: `odalar`

| Kolon Adı | Veri Tipi | Kısıtlamalar (Constraints) | Açıklama |
| :--- | :--- | :--- | :--- |
| `oda_id` | SERIAL (INTEGER) | PK; NOT NULL | Odanın benzersiz kimliği. |
| `oda_adi` | VARCHAR(50) | UNIQUE (büyük/küçük harf duyarsız: `ux_odalar_oda_adi_ci`); NOT NULL | Odanın tabeladaki adı/numarası. |
| `kapasite` | INTEGER | NULL; DEFAULT `1` | Maksimum kişi kapasitesi. |
| `aktif_mi` | BOOLEAN | NOT NULL; DEFAULT `true` | Odanın kullanıma açıklık durumu. |

### Tablo: `randevular`

| Kolon Adı | Veri Tipi | Kısıtlamalar (Constraints) | Açıklama |
| :--- | :--- | :--- | :--- |
| `randevu_id` | SERIAL (INTEGER) | PK; NOT NULL | Randevunun kimliği. |
| `danisan_kod_id` | VARCHAR(50) | FK → `danisan_kodlari(danisan_kod_id)`; NOT NULL | Randevu alınan danışan kodu. |
| `psikolog_id` | INTEGER | FK → `kullanicilar(personel_id)`; NOT NULL | Görüşmeyi yapacak uzman. |
| `oda_id` | INTEGER | FK → `odalar(oda_id)`; NOT NULL | Görüşmenin yapılacağı oda. |
| `baslangic_zamani` | TIMESTAMP | NOT NULL | Randevu başlangıcı. |
| `bitis_zamani` | TIMESTAMP | NOT NULL | Randevu bitişi. |
| `durum` | VARCHAR(30) | NOT NULL; DEFAULT `'PLANLANDI'`; CHECK (`PLANLANDI`, `TAMAMLANDI`, `GELMEDI`, `IPTAL_EDILDI`) | Randevunun anlık durumu. |
| `olusturulma_tarihi` | TIMESTAMP | NOT NULL; DEFAULT `CURRENT_TIMESTAMP` | Kaydın oluşturulma zamanı. |
| `iptal_nedeni` | VARCHAR(30) | NULL | Randevunun iptal edilme nedeni. |
| `iptal_notu` | VARCHAR(100) | NULL | İptale ilişkin açıklama; DIGER nedeni seçilirse zorunludur. |
| `gorusme_tipi` | VARCHAR(20) | NOT NULL; DEFAULT `'YUZ_YUZE'::character varying` | Görüşme biçimi; YUZ_YUZE veya ONLINE. |
| `terapi_turu` | VARCHAR(30) | NULL | Terapi türü; OYUN_TERAPISI veya BIREYSEL_TERAPI; boş olabilir. |

**CHECK kısıtları:**

- `randevular_diger_icin_not_zorunlu`: `iptal_nedeni::text IS DISTINCT FROM 'DIGER'::text OR iptal_notu IS NOT NULL AND btrim(iptal_notu::text) <> ''::text`
- `randevular_gorusme_tipi_gecerli`: `gorusme_tipi::text = ANY (ARRAY['YUZ_YUZE'::character varying, 'ONLINE'::character varying]::text[])`
- `randevular_iptal_nedeni_gecerli`: `iptal_nedeni IS NULL OR (iptal_nedeni::text = ANY (ARRAY['DANISAN_TALEBI'::character varying, 'PSIKOLOG_MAZERETI'::character varying, 'ODA_EKIPMAN_SORUNU'::character varying, 'HATALI_KAYIT'::character varying, 'DIGER'::character varying]::text[]))`
- `randevular_iptal_nedeni_yalniz_iptalde`: `iptal_nedeni IS NULL OR durum::text = 'IPTAL_EDILDI'::text`
- `randevular_iptal_notu_nedene_bagli`: `iptal_notu IS NULL OR iptal_nedeni IS NOT NULL`
- `randevular_terapi_turu_gecerli`: `terapi_turu IS NULL OR (terapi_turu::text = ANY (ARRAY['OYUN_TERAPISI'::character varying, 'BIREYSEL_TERAPI'::character varying]::text[]))`

**EXCLUDE kısıtları:**

- `oda_randevu_cakisma`: `EXCLUDE USING gist (oda_id WITH =, tsrange(baslangic_zamani, bitis_zamani, '[)'::text) WITH &&) WHERE (((durum)::text = 'PLANLANDI'::text))`
- `psikolog_randevu_cakisma`: `EXCLUDE USING gist (psikolog_id WITH =, tsrange(baslangic_zamani, bitis_zamani, '[)'::text) WITH &&) WHERE (((durum)::text = 'PLANLANDI'::text))`

### Tablo: `oda_etkinlikleri`

| Kolon Adı | Veri Tipi | Kısıtlamalar (Constraints) | Açıklama |
| :--- | :--- | :--- | :--- |
| `etkinlik_id` | SERIAL (INTEGER) | PK; NOT NULL | İdari toplantı/eğitim kimliği. |
| `oda_id` | INTEGER | FK → `odalar(oda_id)`; NOT NULL | Etkinliğin yapılacağı oda. |
| `organize_eden_personel_id` | INTEGER | FK → `kullanicilar(personel_id)`; NOT NULL | Düzenleyen yetkili. |
| `etkinlik_adi` | VARCHAR(150) | NOT NULL | Toplantı veya eğitim adı. |
| `katilimci_sayisi` | INTEGER | NULL | Beklenen kişi sayısı (Kapasite kontrolü için). |
| `baslangic_zamani` | TIMESTAMP | NOT NULL | Etkinlik başlangıcı. |
| `bitis_zamani` | TIMESTAMP | NOT NULL | Etkinlik bitişi. |
| `iptal_edildi_mi` | BOOLEAN | NULL; DEFAULT `false` | Etkinliğin iptal durumu. |

### Tablo: `oda_etkinlik_gunleri`

Çok günlü bir etkinliğin her günü için ayrı bir satır tutar (örn. 3 günlük eğitim = 3 satır). Etkinlik silinirse günleri de silinir.

| Kolon Adı | Veri Tipi | Kısıtlamalar (Constraints) | Açıklama |
| :--- | :--- | :--- | :--- |
| `gun_id` | SERIAL (INTEGER) | PK; NOT NULL | Etkinlik günü kaydının kimliği. |
| `etkinlik_id` | INTEGER | FK → `oda_etkinlikleri(etkinlik_id)` ON DELETE CASCADE; NOT NULL | Günün ait olduğu etkinlik. |
| `baslangic_zamani` | TIMESTAMP | NOT NULL | O günkü başlangıç saati. |
| `bitis_zamani` | TIMESTAMP | NOT NULL | O günkü bitiş saati. |

**Kısıtlar:** `uq_oda_etkinlik_gun_baslangic` (`etkinlik_id`, `baslangic_zamani` benzersiz); `oda_etkinlik_gunleri_zaman_check` (`bitis_zamani > baslangic_zamani`);
`oda_etkinlik_gunleri_ayni_gun_check` (her satır tek bir takvim gününe sığmalıdır).

### Tablo: `psikolog_odalar`

| Kolon Adı | Veri Tipi | Kısıtlamalar (Constraints) | Açıklama |
| :--- | :--- | :--- | :--- |
| `kullanici_id` | INTEGER | Birleşik PK parçası; FK → `kullanicilar(kullanici_id)`; NOT NULL | Odayla ilişkilendirilen psikoloğun kullanıcı kimliği. |
| `oda_id` | INTEGER | Birleşik PK parçası; FK → `odalar(oda_id)`; NOT NULL | Psikoloğa ilişkilendirilen oda kimliği. |

## 3. Kimlik, Rol ve Yetki Modülü (Security & Platform)

Kullanıcı, personel, RBAC, oturum güvenliği ve parola sıfırlama süreçleri.

### Tablo: `roller`

| Kolon Adı | Veri Tipi | Kısıtlamalar (Constraints) | Açıklama |
| :--- | :--- | :--- | :--- |
| `rol_id` | SERIAL (INTEGER) | PK; NOT NULL | Rol kimliği. |
| `rol_adi` | VARCHAR(50) | UNIQUE; NOT NULL | Rolün sistemdeki adı. |
| `gorunen_ad` | VARCHAR(100) | NULL | Arayüzde gösterilebilen rol adı. |
| `aktif_mi` | BOOLEAN | NULL; DEFAULT `true` | Rolün etkinlik durumu. |

### Tablo: `izinler`

| Kolon Adı | Veri Tipi | Kısıtlamalar (Constraints) | Açıklama |
| :--- | :--- | :--- | :--- |
| `izin_id` | SERIAL (INTEGER) | PK; NOT NULL | İznin kimliği. |
| `izin_adi` | VARCHAR(100) | UNIQUE; NOT NULL | Yetkinin sistemde kullanılan benzersiz adı. |
| `aciklama` | VARCHAR(255) | NULL | Yetkinin işlevsel açıklaması. |
| `gorunen_ad` | VARCHAR(100) | NULL | Arayüzde gösterilebilen yetki adı. |

### Tablo: `rol_izinleri`

| Kolon Adı | Veri Tipi | Kısıtlamalar (Constraints) | Açıklama |
| :--- | :--- | :--- | :--- |
| `rol_id` | INTEGER | Birleşik PK parçası; FK → `roller(rol_id)`; NOT NULL | İlgili rol. |
| `izin_id` | INTEGER | Birleşik PK parçası; FK → `izinler(izin_id)`; NOT NULL | İlgili izin. |
| `izin_var` | SMALLINT | NOT NULL; DEFAULT `0` | İznin aktif olup olmadığı (Boolean mantığı). |

**CHECK kısıtları:**

- `rol_izinleri_izin_var_check`: `izin_var = ANY (ARRAY[0, 1])`

### Tablo: `kullanicilar`

| Kolon Adı | Veri Tipi | Kısıtlamalar (Constraints) | Açıklama |
| :--- | :--- | :--- | :--- |
| `kullanici_id` | SERIAL (INTEGER) | PK; NOT NULL | Hesabın benzersiz kimliği. |
| `kullanici_adi` | VARCHAR(100) | UNIQUE (büyük/küçük harf duyarsız: `ux_kullanicilar_kullanici_adi_ci`); NOT NULL | Sisteme giriş (login) adı. |
| `parola_hash` | VARCHAR(255) | NOT NULL | Şifrelenmiş parola verisi. |
| `rol_id` | INTEGER | FK → `roller(rol_id)`; NOT NULL | Kullanıcının sistemdeki rolü. |
| `aktif_mi` | BOOLEAN | NOT NULL; DEFAULT `true` | Hesabın erişime açıklık durumu. |
| `olusturulma_tarihi` | TIMESTAMP | NOT NULL; DEFAULT `CURRENT_TIMESTAMP` | Hesabın açılış zamanı. |
| `basarisiz_giris_sayisi` | INTEGER | NOT NULL; DEFAULT `0` | Hesap için kaydedilen başarısız giriş denemesi sayısı. |
| `kilit_bitis_zamani` | TIMESTAMP | NULL | Hesap kilidinin sona ereceği zaman; kilit yoksa boş olabilir. |
| `ilk_giris_mi` | BOOLEAN | NOT NULL; DEFAULT `false` | Hesabın ilk giriş durumunu belirten işaret. |
| `gecici_parola_bitis` | TIMESTAMP | NULL | Geçici parolanın geçerli olduğu son zaman (yönetici/kurtarma aracı sıfırlaması ve yeni kullanıcı için; varsayılan 48 saat). Süre dolunca giriş reddedilir; parola değiştirilince boşaltılır. Boşsa süresizdir. |
| `personel_id` | INTEGER | UNIQUE; NULL | Personel kaydının kimliği (eski `personel.personel_id` değerleri aynen korunur; randevu, danışan, rezervasyon ve etkinlik tabloları buna bağlanır). Boşsa kullanıcının personel kaydı yoktur. |
| `personel_kodu` | VARCHAR(50) | UNIQUE; NULL | Kurum sicil/personel numarası. `personel_id` ile birlikte dolu ya da boştur (`kullanicilar_personel_alanlari_birlikte`). |
| `personel_kaydi_tarihi` | TIMESTAMP | NULL | Personel kaydının oluşturulma zamanı. |

### Görünüm: `personel`

`personel` artık ayrı bir tablo değil, `kullanicilar` üzerinde (personel kaydı olan satırlar için) bir **görünümdür**. Eski sorgular ve betikler değişmeden çalışsın diye yazılabilir (INSTEAD OF tetikleyicili) bırakılmıştır; yeni kod doğrudan `kullanicilar`'ı kullanmalıdır. Personel ve kullanıcı birebir aynı kişi olduğu, tek aktiflik bayrağı bulunduğu için iki kaydın birbirinden kopması mümkün değildir.

| Kolon Adı | Kaynak | Açıklama |
| :--- | :--- | :--- |
| `personel_id` | `kullanicilar.personel_id` | Personel kaydının kimliği (eski kimlikler korunmuştur). |
| `kullanici_id` | `kullanicilar.kullanici_id` | Bağlı olduğu giriş hesabı. |
| `personel_kodu` | `kullanicilar.personel_kodu` | Kurum sicil/personel numarası. |
| `aktif_mi` | `kullanicilar.aktif_mi` | Tek aktiflik bayrağı: personel pasifse hesap da pasiftir. |
| `olusturulma_tarihi` | `kullanicilar.personel_kaydi_tarihi` | Personel kaydının oluşturulma zamanı. |

**Davranış:** `INSERT INTO personel` ilgili kullanıcıya personel kimliği/kodu verir (kullanıcı yoksa yabancı anahtar, zaten personeli varsa benzersizlik hatası); `UPDATE` kod ve aktiflik değerini `kullanicilar`'a yazar; `DELETE` kullanıcının personel alanlarını boşaltır (başvuran kayıt varsa yabancı anahtar engeller; danışan kodlarının oluşturan psikologu boşalır). Geçiş migration'ı: `b9d4f7a2c613`.

### Tablo: `giris_istek_limitleri`

| Kolon Adı | Veri Tipi | Kısıtlamalar (Constraints) | Açıklama |
| :--- | :--- | :--- | :--- |
| `anahtar` | VARCHAR(64) | PK; NOT NULL | İstemci (IP) adresinin SHA-256 özeti; ham adres saklanmaz. |
| `pencere_baslangici` | TIMESTAMP | NOT NULL | Sayım penceresinin başlangıcı (pencere 5 dakikadır). |
| `istek_sayisi` | INTEGER | NOT NULL | Pencerede o istemciden gelen BAŞARISIZ giriş denemesi sayısı; 20'ye ulaşınca pencere bitene kadar giriş 429 ile reddedilir. |

**CHECK kısıtları:**

- `ck_giris_istek_sayisi`: `istek_sayisi >= 1`

### Tablo: `parola_sifirlama_talepleri`

| Kolon Adı | Veri Tipi | Kısıtlamalar (Constraints) | Açıklama |
| :--- | :--- | :--- | :--- |
| `talep_id` | SERIAL (INTEGER) | PK; NOT NULL | Parola sıfırlama talebinin benzersiz kimliği. |
| `kullanici_id` | INTEGER | FK → `kullanicilar(kullanici_id)`; NOT NULL | Parola sıfırlama talebinde bulunan kullanıcı. |
| `talep_zamani` | TIMESTAMP | NOT NULL; DEFAULT `CURRENT_TIMESTAMP` | Talebin oluşturulduğu zaman. |
| `durum` | VARCHAR(12) | NOT NULL; DEFAULT `'ACIK'::character varying` | Talep durumu: ACIK, TAMAMLANDI veya KAPATILDI. |
| `kapanis_zamani` | TIMESTAMP | NULL | Talebin kapatılma zamanı; açık taleplerde boştur. |
| `kapatan_kullanici_id` | INTEGER | FK → `kullanicilar(kullanici_id)`; NULL | Talebi kapatan kullanıcının kimliği. |

**CHECK kısıtları:**

- `parola_sifirlama_talepleri_durum_check`: `durum::text = ANY (ARRAY['ACIK'::character varying, 'TAMAMLANDI'::character varying, 'KAPATILDI'::character varying]::text[])`
- `parola_talep_kapanis_tutarli`: `durum::text = 'ACIK'::text AND kapanis_zamani IS NULL OR durum::text <> 'ACIK'::text AND kapanis_zamani IS NOT NULL`

## 4. Öğrenci ve Faaliyet Yönetimi Modülü

Öğrenci kayıtları, danışma masası görevleri, faaliyet puanları ve erteleme geçmişi.

### Tablo: `ogrenciler`

| Kolon Adı | Veri Tipi | Kısıtlamalar (Constraints) | Açıklama |
| :--- | :--- | :--- | :--- |
| `ogrenci_id` | SERIAL (INTEGER) | PK; NOT NULL | Öğrencinin benzersiz kimliği. |
| `kullanici_id` | INTEGER | FK → `kullanicilar(kullanici_id)`; UNIQUE; NULL | Varsa öğrenciyle ilişkilendirilmiş kullanıcı hesabı. |
| `ad_soyad` | VARCHAR(100) | NOT NULL | Öğrencinin adı ve soyadı. |
| `ogrenci_numarasi` | VARCHAR(50) | UNIQUE; NOT NULL | Öğrencinin benzersiz öğrenci numarası. |
| `telefon` | VARCHAR(20) | NULL | Öğrencinin iletişim telefonu. |
| `tur` | `ogrenci_turu` (ENUM) | NOT NULL | Öğrenci türü: `GONULLU`, `DANISMA_MASASI` veya `ASISTAN`. |
| `aktif_mi` | BOOLEAN | NOT NULL; DEFAULT `true` | Öğrenci kaydının etkinlik durumu. |
| `olusturulma_tarihi` | TIMESTAMP | NOT NULL; DEFAULT `CURRENT_TIMESTAMP` | Öğrenci kaydının oluşturulma zamanı. |
| `bolum` | VARCHAR(100) | NULL | Öğrencinin bölümü (özellikle Asistan öğrenciler için). |
| `sinif` | VARCHAR(20) | NULL | Öğrencinin sınıfı. |

### Tablo: `danisma_masasi_oturumlari`

| Kolon Adı | Veri Tipi | Kısıtlamalar (Constraints) | Açıklama |
| :--- | :--- | :--- | :--- |
| `oturum_id` | SERIAL (INTEGER) | PK; NOT NULL | Mesai oturum kimliği. |
| `ogrenci_id` | INTEGER | FK → `ogrenciler(ogrenci_id)`; NOT NULL | Görevi gerçekleştiren öğrenci. |
| `baslangic_zamani` | TIMESTAMP | NOT NULL; DEFAULT `CURRENT_TIMESTAMP` | Danışma masası görevinin başlangıcı. |
| `bitis_zamani` | TIMESTAMP | NULL | Görev devam ederken NULL olabilir; doluysa başlangıçtan sonra olmalıdır. |
| `onaylandi_mi` | BOOLEAN | NOT NULL; DEFAULT `false` | Görev oturumunun onaylanıp onaylanmadığı. |

**CHECK kısıtları:**

- `danisma_masasi_oturumlari_check`: `bitis_zamani IS NULL OR bitis_zamani > baslangic_zamani`

### Tablo: `faaliyet_birimleri`

| Kolon Adı | Veri Tipi | Kısıtlamalar (Constraints) | Açıklama |
| :--- | :--- | :--- | :--- |
| `birim_id` | SERIAL (INTEGER) | PK; NOT NULL | Faaliyet biriminin benzersiz kimliği. |
| `birim_adi` | VARCHAR(50) | UNIQUE; NOT NULL | Faaliyet miktarını ifade eden birimin adı. |
| `aktif_mi` | BOOLEAN | NOT NULL; DEFAULT `true` | Faaliyet biriminin etkinlik durumu. |

### Tablo: `faaliyetler`

| Kolon Adı | Veri Tipi | Kısıtlamalar (Constraints) | Açıklama |
| :--- | :--- | :--- | :--- |
| `faaliyet_id` | SERIAL (INTEGER) | PK; NOT NULL | Faaliyet türünün benzersiz kimliği. |
| `faaliyet_adi` | VARCHAR(100) | UNIQUE; NOT NULL | Faaliyetin adı. |
| `puan` | INTEGER | NOT NULL | Faaliyet türüne tanımlanan puan. |
| `aktif_mi` | BOOLEAN | NOT NULL; DEFAULT `true` | Faaliyet türünün etkinlik durumu. |

**CHECK kısıtları:**

- `faaliyetler_puan_check`: `puan >= 0`

### Tablo: `ogrenci_faaliyet_takip`

| Kolon Adı | Veri Tipi | Kısıtlamalar (Constraints) | Açıklama |
| :--- | :--- | :--- | :--- |
| `takip_id` | SERIAL (INTEGER) | PK; NOT NULL | Öğrenci faaliyet kaydının benzersiz kimliği. |
| `ogrenci_id` | INTEGER | FK → `ogrenciler(ogrenci_id)`; NOT NULL | Faaliyeti gerçekleştiren öğrenci. |
| `faaliyet_id` | INTEGER | FK → `faaliyetler(faaliyet_id)`; NOT NULL | Kaydın ilişkili olduğu faaliyet türü. |
| `adet` | INTEGER | NOT NULL | Kaydedilen faaliyet miktarı; sıfırdan büyük olmalıdır. |
| `birim_id` | INTEGER | FK → `faaliyet_birimleri(birim_id)`; NOT NULL | Faaliyet miktarının birimi. |
| `faaliyet_tarihi` | DATE | NOT NULL; DEFAULT `CURRENT_DATE` | Faaliyetin gerçekleştiği tarih. |
| `aciklama` | VARCHAR(255) | NULL | Faaliyet kaydına ilişkin ek açıklama. |
| `onaylandi_mi` | BOOLEAN | NOT NULL; DEFAULT `false` | Faaliyet kaydının onay durumu. |
| `olusturulma_tarihi` | TIMESTAMP | NOT NULL; DEFAULT `CURRENT_TIMESTAMP` | Faaliyet kaydının oluşturulma zamanı. |
| `kayit_puani` | INTEGER | NOT NULL | Bu faaliyet kaydına ait, sıfır veya daha büyük puan. |

**CHECK kısıtları:**

- `ck_ogrenci_faaliyet_kayit_puani`: `kayit_puani >= 0`
- `ogrenci_faaliyet_takip_adet_check`: `adet > 0`

### Tablo: `ogrenci_kayit_erteleme_gecmisi`

| Kolon Adı | Veri Tipi | Kısıtlamalar (Constraints) | Açıklama |
| :--- | :--- | :--- | :--- |
| `erteleme_id` | SERIAL (INTEGER) | PK; NOT NULL | Erteleme kaydının benzersiz kimliği. |
| `ogrenci_id` | INTEGER | FK → `ogrenciler(ogrenci_id)`; NULL | Varsa ertelemenin ilişkili olduğu öğrenci. |
| `ogrenci_numarasi` | VARCHAR(15) | NOT NULL | Erteleme kaydında saklanan öğrenci numarası. |
| `yeni_uyari_tarihi` | DATE | NOT NULL | Erteleme sonucunda belirlenen yeni uyarı tarihi. |
| `erteleyen_kullanici_id` | INTEGER | FK → `kullanicilar(kullanici_id)`; NULL | Erteleme işlemini yapan kullanıcı. |
| `olusturulma_tarihi` | TIMESTAMP | NOT NULL; DEFAULT `CURRENT_TIMESTAMP` | Erteleme kaydının oluşturulma zamanı. |

## 5. Denetim (Audit) Modülü

Kritik güvenlik ve veri değişikliği olaylarının kayıtları.

### Tablo: `denetim_kayitlari`

| Kolon Adı | Veri Tipi | Kısıtlamalar (Constraints) | Açıklama |
| :--- | :--- | :--- | :--- |
| `denetim_id` | BIGSERIAL (BIGINT) | PK; NOT NULL | Audit kaydının benzersiz kimliği. |
| `kullanici_id` | INTEGER | FK → `kullanicilar(kullanici_id)`; NULL | İşlemi yapan kullanıcı (Failed login durumunda NULL olabilir). |
| `olay_turu` | `denetim_olay_turu` (ENUM) | NOT NULL | Denetim olayının PostgreSQL ENUM türü. Geçerli değerler belgenin ENUM bölümünde listelenmiştir. |
| `hedef_tablo` | VARCHAR(100) | NULL | Veri değişikliğinden etkilenen tablo. |
| `hedef_kayit_id` | INTEGER | NULL | Değiştirilen/Silinen kaydın PK değeri. |
| `olusturulma_tarihi` | TIMESTAMP | NOT NULL; DEFAULT `CURRENT_TIMESTAMP` | Olayın gerçekleştiği tam zaman. |
| `ayrinti` | JSONB | NULL | Kalıcı silmelerde silinen satırın içeriği (`silinen`); oda atamalarında önceki/yeni oda kimlikleri. Kişisel veri içeren `ogrenciler` silmesinde ad, telefon vb. yazılmaz (yalnızca kimliksiz alanlar ve `maskelenen_alanlar` listesi). Tablo değiştirilemez olduğundan kayıt sonradan düzenlenemez. |

## Teknik tablo: `alembic_version`

Alembic migration sürümünü izler; uygulamanın iş verisi tablosu değildir.

| Kolon Adı | Veri Tipi | Kısıtlamalar | Açıklama |
| :--- | :--- | :--- | :--- |
| `version_num` | VARCHAR(32) | PK, NOT NULL | Uygulanmış migration revizyonu. |

## Doğrulama notları

- Sütunlar, veri tipleri, varsayılanlar, PK, FK, UNIQUE, CHECK ve EXCLUDE tanımları PostgreSQL üzerinden okunmuştur.
- Sütun açıklamaları, alan adları ve bilinen işlevleri esas alınarak tamamlanmıştır; uygulama düzeyindeki iş kuralları ayrıca kod ve testlerle doğrulanmalıdır.
- ENUM değerleri ile `VARCHAR` alanları ayrı gösterilmiştir. Veritabanında bulunmayan kısıtlar varsayılmamıştır.
- Bu belge şema tanımıdır; API davranışları ve uygulama düzeyindeki doğrulamalar ayrıca incelenmelidir.
