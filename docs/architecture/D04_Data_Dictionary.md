# D04 - Veri Sözlüğü (Data Dictionary)
**Proje:** Travma Uygulama ve Araştırma Merkezi - Bilgi ve Kaynak Yönetim Sistemi
**Sürüm:** v1.0
**Açıklama:** Bu doküman, sistemdeki merkezi PostgreSQL veritabanında yer alan tüm tabloların, sütunların, veri tiplerinin ve ilişkilerin detaylı teknik haritasıdır.

---

## 1. KİMLİK DOĞRULAMA VE ERİŞİM (Öğrenci C Kapsamı)

### 1.1. roller Tablosu
Kullanıcıların sistemdeki yetki seviyelerini belirler.
| Sütun Adı | Veri Tipi | Kısıtlama | Açıklama |
| :--- | :--- | :--- | :--- |
| `rol_id` | SERIAL | Primary Key | Rolün benzersiz kimliği. |
| `rol_adi` | VARCHAR(50) | UNIQUE, NOT NULL | Rolün sistem adı. |

### 1.2. kullanicilar Tablosu
Sisteme giriş yapacak personelin kimlik doğrulama (login) verilerini tutar.
| Sütun Adı | Veri Tipi | Kısıtlama | Açıklama |
| :--- | :--- | :--- | :--- |
| `kullanici_id` | SERIAL | Primary Key | Kullanıcının benzersiz kimliği. |
| `kullanici_adi` | VARCHAR(100)| UNIQUE, NOT NULL | Sisteme giriş kullanıcı adı. |
| `parola_hash` | VARCHAR(255)| NOT NULL | Şifrelenmiş parola. Düz metin tutulmaz. |
| `rol_id` | INT | Foreign Key, NOT NULL | Kullanıcının sahip olduğu rol (`roller` tablosuna referans). |
| `aktif_mi` | BOOLEAN | NOT NULL, DEFAULT TRUE | Kullanıcının giriş izni (aktif/pasif) durumu. |
| `olusturulma_tarihi`| TIMESTAMP | NOT NULL, DEFAULT CURRENT_TIMESTAMP | Hesabın oluşturulma zamanı. |

### 1.3. personel Tablosu
Kullanıcıların kurumsal özlük bilgilerini ve sicil kodlarını tutar.
| Sütun Adı | Veri Tipi | Kısıtlama | Açıklama |
| :--- | :--- | :--- | :--- |
| `personel_id` | SERIAL | Primary Key | Personel kaydının benzersiz kimliği. |
| `kullanici_id`| INT | Foreign Key, UNIQUE, NOT NULL | `kullanicilar` tablosuyla 1-1 eşleşen bağlantı. |
| `personel_kodu`| VARCHAR(50) | UNIQUE, NOT NULL | Kurum içindeki personel/sicil numarası. |
| `aktif_mi` | BOOLEAN | NOT NULL, DEFAULT TRUE | Personelin kurumdaki güncel çalışma durumu. |
| `olusturulma_tarihi`| TIMESTAMP | NOT NULL, DEFAULT CURRENT_TIMESTAMP | Kaydın açıldığı tarih. |

### 1.4. denetim_kayitlari Tablosu
*(Özel Veri Tipi: `denetim_olay_turu` ENUM: 'LOGIN', 'LOGIN_FAILED', 'CREATE', 'UPDATE', 'CANCEL', 'ROLE_CHANGE', 'DEVICE_STATUS_CHANGE')*
Sistemdeki güvenlik ve veri değişikliklerini kayıt altına alır.
| Sütun Adı | Veri Tipi | Kısıtlama | Açıklama |
| :--- | :--- | :--- | :--- |
| `denetim_id` | BIGSERIAL | Primary Key | Log kaydının benzersiz, büyük ölçekli kimliği. |
| `kullanici_id` | INT | Foreign Key | İşlemi yapan kullanıcının kimliği (`kullanicilar` tablosuna referans). |
| `olay_turu` | ENUM | NOT NULL | Özel `denetim_olay_turu` listesinden seçilen işlem türü. |
| `hedef_tablo` | VARCHAR(100)| NULL | İşlem yapılan veritabanı tablosunun adı. |
| `hedef_kayit_id`| INT | NULL | İşlem yapılan ilgili kaydın ID'si. |
| `olusturulma_tarihi`| TIMESTAMP | NOT NULL, DEFAULT CURRENT_TIMESTAMP | İşlemin gerçekleştiği an. |

---

## 2. DANIŞAN, RANDEVU VE ODA YÖNETİMİ (Öğrenci A Kapsamı)

### 2.1. danisan_kodlari Tablosu
Gerçek kişi kimliklerini maskelemek için kullanılan operasyonel kodları tutar. (Kişisel veri içeremez).
| Sütun Adı | Veri Tipi | Kısıtlama | Açıklama |
| :--- | :--- | :--- | :--- |
| `danisan_kod_id`| SERIAL | Primary Key | Danışanın sistemdeki referans kimliği. |
| `kod` | VARCHAR(50) | UNIQUE, NOT NULL | Üretilen operasyonel kod (Örn: DN-2026-0048). |
| `aktif_mi` | BOOLEAN | NOT NULL, DEFAULT TRUE | Kodun kullanımda olup olmadığı. |

### 2.2. odalar Tablosu
Merkezdeki terapi ve işlem odalarının envanterini tutar.
| Sütun Adı | Veri Tipi | Kısıtlama | Açıklama |
| :--- | :--- | :--- | :--- |
| `oda_id` | SERIAL | Primary Key | Odanın benzersiz kimliği. |
| `oda_numarasi` | VARCHAR(50) | UNIQUE, NOT NULL | Odanın adı veya numarası. |
| `kapasite` | INT | DEFAULT 1 | Odada aynı anda bulunabilecek kişi kapasitesi. |
| `aktif_mi` | BOOLEAN | NOT NULL, DEFAULT TRUE | Odanın rezervasyona açık olup olmadığı. |

### 2.3. randevular Tablosu
Hangi danışanın, hangi psikologla, hangi odada görüşeceğini yönetir.
| Sütun Adı | Veri Tipi | Kısıtlama | Açıklama |
| :--- | :--- | :--- | :--- |
| `randevu_id` | SERIAL | Primary Key | Randevunun benzersiz kimliği. |
| `danisan_kod_id`| INT | Foreign Key, NOT NULL | İşlem gören danışan (`danisan_kodlari` referansı). |
| `psikolog_id` | INT | Foreign Key, NOT NULL | İşlemi yapacak psikolog (`personel` referansı). |
| `oda_id` | INT | Foreign Key, NOT NULL | İşlemin yapılacağı oda (`odalar` referansı). |
| `baslangic_zamani`| TIMESTAMP | NOT NULL | Randevunun başlangıç zamanı. |
| `bitis_zamani` | TIMESTAMP | NOT NULL | Randevunun bitiş zamanı. |
| `durum` | VARCHAR(30) | DEFAULT 'PLANLANDI'| Randevu statüsü. |
| `olusturulma_tarihi`| TIMESTAMP | NOT NULL, DEFAULT CURRENT_TIMESTAMP | Randevu kaydının açıldığı an. |

---

## 3. CİHAZ VE OPERASYON YÖNETİMİ (Öğrenci B Kapsamı)

*(Özel Veri Tipi: `cihaz_durumu` ENUM: 'Kullanima_Hazir', 'Rezerve', 'Kullanimda', 'Arizali', 'Bakimda', 'Kalibrasyonda', 'Kullanim_Disi')*

### 3.1. cihazlar Tablosu
Merkezdeki tüm medikal ve teknolojik cihazların ana kaydını tutar.
| Sütun Adı | Veri Tipi | Kısıtlama | Açıklama |
| :--- | :--- | :--- | :--- |
| `cihaz_id` | SERIAL | Primary Key | Cihazın benzersiz sistem kimliği. |
| `envanter_kodu` | VARCHAR(50) | UNIQUE, NOT NULL | Kurum fiziksel demirbaş barkod numarası. |
| `cihaz_adi` | VARCHAR(100)| NOT NULL | Cihazın genel adı (Örn: EKG Cihazı, Projektör). |
| `marka_model` | VARCHAR(100)| NULL | Cihazın üreticisi ve model bilgisi. |
| `seri_no` | VARCHAR(100)| UNIQUE | Donanım seri numarası. |
| `zimmetli_oda_id`| INT | NULL | Sabit bulunduğu oda (İleride `odalar` tablosuna bağlanacak). |
| `durum` | ENUM | DEFAULT 'Kullanima_Hazir' | Özel `cihaz_durumu` listesinden anlık cihaz durumu. |
| `kayit_tarihi` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Sisteme eklendiği tarih ve saat. |

### 3.2. cihaz_rezervasyonlari Tablosu
Cihazların randevulara veya personellere tahsisini kontrol eder.
| Sütun Adı | Veri Tipi | Kısıtlama | Açıklama |
| :--- | :--- | :--- | :--- |
| `rezervasyon_id`| SERIAL | Primary Key | Rezervasyon işleminin benzersiz kimliği. |
| `cihaz_id` | INT | Foreign Key | Rezerve edilen cihazın ID'si. |
| `randevu_id` | INT | NULL | İşlemin hangi randevu için yapıldığı (İleride `randevular`a bağlanacak). |
| `personel_id` | INT | NULL | İşlemi gerçekleştiren personelin ID'si. |
| `baslangic_zamani`| TIMESTAMP | NOT NULL | Kullanımın başlayacağı tarih ve saat. |
| `bitis_zamani` | TIMESTAMP | NOT NULL | Kullanımın biteceği tarih ve saat. |
| `iptal_edildi_mi`| BOOLEAN | DEFAULT FALSE | Rezervasyonun iptal edilip edilmediği. |

### 3.3. cihaz_arizalari Tablosu
Bozulan cihazların arıza bildirimlerini ve onarım süreçlerini kayıt altına alır.
| Sütun Adı | Veri Tipi | Kısıtlama | Açıklama |
| :--- | :--- | :--- | :--- |
| `ariza_id` | SERIAL | Primary Key | Arıza kaydının benzersiz kimliği. |
| `cihaz_id` | INT | Foreign Key | Arızalanan cihazın ID'si. |
| `bildiren_personel`| VARCHAR(100)| NULL | Arızayı bildiren personelin adı/sicili (Metin olarak). |
| `ariza_aciklamasi`| TEXT | NOT NULL | Arızanın detaylı metinsel açıklaması. |
| `bildirim_tarihi` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Bildirim tarihi. |
| `cozum_tarihi` | TIMESTAMP | NULL | Arızanın giderildiği tarih. |
| `cozuldu_mu` | BOOLEAN | DEFAULT FALSE | Onarım sürecinin tamamlanma durumu. |

### 3.4. cihaz_bakimlari Tablosu
Cihazlara yapılan periyodik onarım ve rutin kontrollerin geçmişini saklar.
| Sütun Adı | Veri Tipi | Kısıtlama | Açıklama |
| :--- | :--- | :--- | :--- |
| `bakim_id` | SERIAL | Primary Key | Bakım kaydının benzersiz kimliği. |
| `cihaz_id` | INT | Foreign Key | Bakım gören cihazın ID'si. |
| `bakim_yapan_kisi`| VARCHAR(100)| NULL | Bakımı gerçekleştiren teknisyen/servis adı. |
| `yapilan_islem` | TEXT | NULL | Yapılan işlemlerin detayı. |
| `maliyet` | DECIMAL(10,2)| NULL | Harcanan onarım maliyeti. |
| `bakim_tarihi` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Bakımın yapıldığı tarih. |

### 3.5. cihaz_kalibrasyonlari Tablosu
Hassas ölçüm yapan cihazların yasal kalibrasyon sertifikasyonlarını tutar.
| Sütun Adı | Veri Tipi | Kısıtlama | Açıklama |
| :--- | :--- | :--- | :--- |
| `kalibrasyon_id`| SERIAL | Primary Key | Kalibrasyon kaydının benzersiz kimliği. |
| `cihaz_id` | INT | Foreign Key | Kalibre edilen cihazın ID'si. |
| `kalibrasyon_yapan_kurum`| VARCHAR(100)| NULL | Ölçümü sağlayan akredite kurum. |
| `gecerlilik_tarihi`| DATE | NULL | Belgenin son geçerlilik tarihi. |
| `sertifika_no` | VARCHAR(100)| NULL | Verilen resmi onay belge numarası. |
| `islem_tarihi` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Sisteme girildiği an. |