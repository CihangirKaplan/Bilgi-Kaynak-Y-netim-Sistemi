# D04 - Veri Sözlüğü (Data Dictionary)
**Proje:** Travma Uygulama ve Araştırma Merkezi - Bilgi ve Kaynak Yönetim Sistemi
**Sürüm:** v1.0
**Açıklama:** Bu doküman, sistemdeki merkezi PostgreSQL veritabanında yer alan tabloların, sütunların ve veri tiplerinin güncel haritasıdır.

---

## 1. KİMLİK DOĞRULAMA VE ERİŞİM (Öğrenci C Kapsamı)

### 1.1. roller Tablosu
| Sütun Adı | Veri Tipi | Kısıtlama | Açıklama |
| :--- | :--- | :--- | :--- |
| `rol_id` | SERIAL | Primary Key | Rolün benzersiz kimliği. |
| `rol_adi` | VARCHAR(50) | UNIQUE, NOT NULL | Rolün sistem adı. |

### 1.2. kullanicilar Tablosu
| Sütun Adı | Veri Tipi | Kısıtlama | Açıklama |
| :--- | :--- | :--- | :--- |
| `kullanici_id` | SERIAL | Primary Key | Kullanıcının benzersiz kimliği. |
| `kullanici_adi` | VARCHAR(100)| UNIQUE, NOT NULL | Sisteme giriş kullanıcı adı. |
| `parola_hash` | VARCHAR(255)| NOT NULL | Şifrelenmiş parola. |
| `rol_id` | INT | NOT NULL, Foreign Key | `roller(rol_id)` tablosuna referans. |
| `aktif_mi` | BOOLEAN | NOT NULL, DEFAULT TRUE | Kullanıcının giriş izni durumu. |
| `olusturulma_tarihi`| TIMESTAMP | NOT NULL, DEFAULT CURRENT_TIMESTAMP | Hesabın oluşturulma zamanı. |

### 1.3. personel Tablosu
| Sütun Adı | Veri Tipi | Kısıtlama | Açıklama |
| :--- | :--- | :--- | :--- |
| `personel_id` | SERIAL | Primary Key | Personel kaydının benzersiz kimliği. |
| `kullanici_id`| INT | UNIQUE, NOT NULL, Foreign Key | `kullanicilar(kullanici_id)` tablosuna referans. |
| `personel_kodu`| VARCHAR(50) | UNIQUE, NOT NULL | Kurum içindeki personel sicil numarası. |
| `aktif_mi` | BOOLEAN | NOT NULL, DEFAULT TRUE | Personelin kurumdaki çalışma durumu. |
| `olusturulma_tarihi`| TIMESTAMP | NOT NULL, DEFAULT CURRENT_TIMESTAMP | Kaydın açıldığı tarih. |

### 1.4. denetim_kayitlari Tablosu
*(Özel Veri Tipi: `denetim_olay_turu` ENUM: 'LOGIN', 'LOGIN_FAILED', 'CREATE', 'UPDATE', 'CANCEL', 'ROLE_CHANGE', 'DEVICE_STATUS_CHANGE')*
| Sütun Adı | Veri Tipi | Kısıtlama | Açıklama |
| :--- | :--- | :--- | :--- |
| `denetim_id` | BIGSERIAL | Primary Key | Log kaydının benzersiz kimliği. |
| `kullanici_id` | INT | Foreign Key | `kullanicilar(kullanici_id)` tablosuna referans. |
| `olay_turu` | ENUM | NOT NULL | Özel `denetim_olay_turu` listesinden işlem türü. |
| `hedef_tablo` | VARCHAR(100)| NULL | İşlem yapılan veritabanı tablosunun adı. |
| `hedef_kayit_id`| INT | NULL | İşlem yapılan ilgili kaydın ID'si. |
| `olusturulma_tarihi`| TIMESTAMP | NOT NULL, DEFAULT CURRENT_TIMESTAMP | İşlemin gerçekleştiği an. |

---

## 2. DANIŞAN, RANDEVU VE ODA YÖNETİMİ (Öğrenci A Kapsamı)

### 2.1. danisan_kodlari Tablosu
| Sütun Adı | Veri Tipi | Kısıtlama | Açıklama |
| :--- | :--- | :--- | :--- |
| `danisan_kod_id`| SERIAL | Primary Key | Danışanın sistemdeki referans kimliği. |
| `kod` | VARCHAR(50) | UNIQUE, NOT NULL | Üretilen operasyonel kod. |
| `aktif_mi` | BOOLEAN | NOT NULL, DEFAULT TRUE | Kodun kullanımda olup olmadığı. |

### 2.2. odalar Tablosu
| Sütun Adı | Veri Tipi | Kısıtlama | Açıklama |
| :--- | :--- | :--- | :--- |
| `oda_id` | SERIAL | Primary Key | Odanın benzersiz kimliği. |
| `oda_numarasi` | VARCHAR(50) | UNIQUE, NOT NULL | Odanın adı veya numarası. |
| `kapasite` | INT | DEFAULT 1 | Odada aynı anda bulunabilecek kişi kapasitesi. |
| `aktif_mi` | BOOLEAN | NOT NULL, DEFAULT TRUE | Odanın rezervasyona açık olup olmadığı. |

### 2.3. randevular Tablosu
| Sütun Adı | Veri Tipi | Kısıtlama | Açıklama |
| :--- | :--- | :--- | :--- |
| `randevu_id` | SERIAL | Primary Key | Randevunun benzersiz kimliği. |
| `danisan_kod_id`| INT | NOT NULL, Foreign Key | `danisan_kodlari(danisan_kod_id)` referansı. |
| `psikolog_id` | INT | NOT NULL, Foreign Key | `personel(personel_id)` referansı. |
| `oda_id` | INT | NOT NULL, Foreign Key | `odalar(oda_id)` referansı. |
| `baslangic_zamani`| TIMESTAMP | NOT NULL | Randevunun başlangıç zamanı. |
| `bitis_zamani` | TIMESTAMP | NOT NULL | Randevunun bitiş zamanı. |
| `durum` | VARCHAR(30) | DEFAULT 'PLANLANDI'| Randevu statüsü. |

---

## 3. CİHAZ VE OPERASYON YÖNETİMİ (Öğrenci B Kapsamı)

*(Özel Veri Tipi: `cihaz_durumu` ENUM: 'Kullanima_Hazir', 'Rezerve', 'Kullanimda', 'Arizali', 'Bakimda', 'Kalibrasyonda', 'Kullanim_Disi')*

### 3.1. cihazlar Tablosu
| Sütun Adı | Veri Tipi | Kısıtlama | Açıklama |
| :--- | :--- | :--- | :--- |
| `cihaz_id` | SERIAL | Primary Key | Cihazın benzersiz sistem kimliği. |
| `envanter_kodu` | VARCHAR(50) | UNIQUE, NOT NULL | Kurum fiziksel demirbaş barkod numarası. |
| `cihaz_adi` | VARCHAR(100)| NOT NULL | Cihazın genel adı. |
| `marka_model` | VARCHAR(100)| NULL | Cihazın üreticisi ve model bilgisi. |
| `seri_no` | VARCHAR(100)| UNIQUE | Donanım seri numarası. |
| `zimmetli_oda_id`| INT | Foreign Key, NULL | Sabit bulunduğu oda (`odalar` tablosuna referans). |
| `durum` | ENUM | DEFAULT 'Kullanima_Hazir' | Özel `cihaz_durumu` listesinden cihaz durumu. |
| `kayit_tarihi` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Sisteme eklendiği tarih ve saat. |

### 3.2. cihaz_rezervasyonlari Tablosu
| Sütun Adı | Veri Tipi | Kısıtlama | Açıklama |
| :--- | :--- | :--- | :--- |
| `rezervasyon_id`| SERIAL | Primary Key | Rezervasyon işleminin benzersiz kimliği. |
| `cihaz_id` | INT | Foreign Key, NOT NULL| `cihazlar(cihaz_id)` tablosuna referans. |
| `randevu_id` | INT | Foreign Key, NULL | İşlemin yapıldığı randevu (`randevular` tablosuna referans). |
| `personel_id` | INT | Foreign Key, NULL | İşlemi gerçekleştiren personel (`personel` tablosuna referans). |
| `baslangic_zamani`| TIMESTAMP | NOT NULL | Kullanımın başlayacağı tarih ve saat. |
| `bitis_zamani` | TIMESTAMP | NOT NULL | Kullanımın biteceği tarih ve saat. |
| `iptal_edildi_mi`| BOOLEAN | DEFAULT FALSE | İptal durumu. |

### 3.3. cihaz_arizalari Tablosu
| Sütun Adı | Veri Tipi | Kısıtlama | Açıklama |
| :--- | :--- | :--- | :--- |
| `ariza_id` | SERIAL | Primary Key | Arıza kaydının benzersiz kimliği. |
| `cihaz_id` | INT | Foreign Key, NOT NULL| `cihazlar(cihaz_id)` referansı. |
| `bildiren_personel`| VARCHAR(100)| NULL | Arızayı bildiren personelin adı/sicili (Metin). |
| `ariza_aciklamasi`| TEXT | NOT NULL | Arızanın detaylı metinsel açıklaması. |
| `bildirim_tarihi` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Bildirim tarihi. |
| `cozum_tarihi` | TIMESTAMP | NULL | Arızanın giderildiği tarih. |
| `cozuldu_mu` | BOOLEAN | DEFAULT FALSE | Onarım sürecinin tamamlanma durumu. |

### 3.4. cihaz_bakimlari Tablosu
| Sütun Adı | Veri Tipi | Kısıtlama | Açıklama |
| :--- | :--- | :--- | :--- |
| `bakim_id` | SERIAL | Primary Key | Bakım kaydının benzersiz kimliği. |
| `cihaz_id` | INT | Foreign Key, NOT NULL| `cihazlar(cihaz_id)` referansı. |
| `bakim_yapan_kisi`| VARCHAR(100)| NULL | Bakımı gerçekleştiren teknisyen/servis adı. |
| `yapilan_islem` | TEXT | NULL | Yapılan işlemlerin detayı. |
| `maliyet` | DECIMAL(10,2)| NULL | Harcanan onarım maliyeti. |
| `bakim_tarihi` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Bakımın yapıldığı tarih. |

### 3.5. cihaz_kalibrasyonlari Tablosu
| Sütun Adı | Veri Tipi | Kısıtlama | Açıklama |
| :--- | :--- | :--- | :--- |
| `kalibrasyon_id`| SERIAL | Primary Key | Kalibrasyon kaydının benzersiz kimliği. |
| `cihaz_id` | INT | Foreign Key, NOT NULL| `cihazlar(cihaz_id)` referansı. |
| `kalibrasyon_yapan_kurum`| VARCHAR(100)| NULL | Ölçümü sağlayan akredite kurum. |
| `gecerlilik_tarihi`| DATE | NULL | Belgenin son geçerlilik tarihi. |
| `sertifika_no` | VARCHAR(100)| NULL | Verilen resmi onay belge numarası. |
| `islem_tarihi` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Sisteme girildiği an. |