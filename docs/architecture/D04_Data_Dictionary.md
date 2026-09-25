# D04 - Veri Sözlüğü (Data Dictionary)
**Proje:** Travma Uygulama ve Araştırma Merkezi - Bilgi ve Kaynak Yönetim Sistemi
**Sürüm:** v1.0
**Açıklama:** Bu doküman, sistemdeki merkezi PostgreSQL veritabanında yer alan tabloların, sütunların ve veri tiplerinin güncel haritasıdır.

---

## 1. ÖZEL VERİ TİPLERİ (ENUMS)
*   **`cihaz_durumu`**: 'Kullanima_Hazir', 'Rezerve', 'Kullanimda', 'Arizali', 'Bakimda', 'Kalibrasyonda', 'Kullanim_Disi'
*   **`denetim_olay_turu`**: 'LOGIN', 'LOGIN_FAILED', 'CREATE', 'UPDATE', 'CANCEL', 'ROLE_CHANGE', 'DEVICE_STATUS_CHANGE'

---

## 2. KİMLİK DOĞRULAMA VE KULLANICI YÖNETİMİ

### 2.1. roller Tablosu
| Sütun Adı | Veri Tipi | Kısıtlama | Açıklama |
| :--- | :--- | :--- | :--- |
| `rol_id` | SERIAL | Primary Key | Rolün benzersiz kimliği. |
| `rol_adi` | VARCHAR(50) | UNIQUE, NOT NULL | Rolün sistem adı. |

### 2.2. kullanicilar Tablosu
| Sütun Adı | Veri Tipi | Kısıtlama | Açıklama |
| :--- | :--- | :--- | :--- |
| `kullanici_id` | SERIAL | Primary Key | Kullanıcının benzersiz kimliği. |
| `kullanici_adi` | VARCHAR(100)| UNIQUE, NOT NULL | Sisteme giriş kullanıcı adı. |
| `parola_hash` | VARCHAR(255)| NOT NULL | Şifrelenmiş parola. |
| `rol_id` | INT | NOT NULL, Foreign Key | `roller(rol_id)` tablosuna referans. |
| `aktif_mi` | BOOLEAN | NOT NULL, DEFAULT TRUE | Kullanıcının giriş izni durumu. |
| `olusturulma_tarihi`| TIMESTAMP | NOT NULL, DEFAULT CURRENT_TIMESTAMP | Hesabın oluşturulma zamanı. |

### 2.3. personel Tablosu
| Sütun Adı | Veri Tipi | Kısıtlama | Açıklama |
| :--- | :--- | :--- | :--- |
| `personel_id` | SERIAL | Primary Key | Personel kaydının benzersiz kimliği. |
| `kullanici_id`| INT | UNIQUE, NOT NULL, Foreign Key | `kullanicilar(kullanici_id)` referansı. |
| `personel_kodu`| VARCHAR(50) | UNIQUE, NOT NULL | Kurum içindeki personel sicil numarası. |
| `aktif_mi` | BOOLEAN | NOT NULL, DEFAULT TRUE | Personelin çalışma durumu. |
| `olusturulma_tarihi`| TIMESTAMP | NOT NULL, DEFAULT CURRENT_TIMESTAMP | Kaydın açıldığı tarih. |

### 2.4. danisma_ogrencileri Tablosu
| Sütun Adı | Veri Tipi | Kısıtlama | Açıklama |
| :--- | :--- | :--- | :--- |
| `ogrenci_id` | SERIAL | Primary Key | Danışma öğrencisi benzersiz kimliği. |
| `kullanici_id`| INT | UNIQUE, NOT NULL, Foreign Key | `kullanicilar(kullanici_id)` referansı. |
| `ad_soyad` | VARCHAR(100)| NOT NULL | Öğrencinin gerçek adı soyadı. |
| `ogrenci_numarasi`| VARCHAR(50) | UNIQUE, NOT NULL | Üniversite öğrenci numarası. |
| `telefon` | VARCHAR(20) | NULL | Öğrencinin iletişim numarası. |
| `aktif_mi` | BOOLEAN | NOT NULL, DEFAULT TRUE | Danışma masasında aktif görev durumu. |
| `olusturulma_tarihi`| TIMESTAMP | NOT NULL, DEFAULT CURRENT_TIMESTAMP | Hesabın oluşturulma zamanı. |

### 2.5. denetim_kayitlari Tablosu
| Sütun Adı | Veri Tipi | Kısıtlama | Açıklama |
| :--- | :--- | :--- | :--- |
| `denetim_id` | BIGSERIAL | Primary Key | Log kaydının benzersiz kimliği. |
| `kullanici_id` | INT | Foreign Key, NULL | İşlemi gerçekleştiren `kullanicilar` referansı. |
| `olay_turu` | ENUM | NOT NULL | Özel `denetim_olay_turu` tipinden işlem türü. |
| `hedef_tablo` | VARCHAR(100)| NULL | İşlemden etkilenen tablo adı. |
| `hedef_kayit_id`| INT | NULL | İşlemden etkilenen kaydın ID değeri. |
| `olusturulma_tarihi`| TIMESTAMP | NOT NULL, DEFAULT CURRENT_TIMESTAMP | İşlemin gerçekleştiği an. |

---

## 3. DANIŞAN, RANDEVU VE ODA YÖNETİMİ

### 3.1. danisan_kodlari Tablosu
| Sütun Adı | Veri Tipi | Kısıtlama | Açıklama |
| :--- | :--- | :--- | :--- |
| `danisan_kod_id`| VARCHAR(50) | Primary Key | Üretilen operasyonel danışan kodu. |
| `ucretli_mi` | BOOLEAN | NOT NULL, DEFAULT TRUE | Seansın ücretli/ücretsiz olma durumu. |
| `istisna_turu`| VARCHAR(50) | DEFAULT 'YOK' | Ücretsiz seans sebebi (Örn: Şehit/Gazi Yakını). |
| `aktif_mi` | BOOLEAN | NOT NULL, DEFAULT TRUE | Kodun aktif kullanım durumu. |
| `olusturulma_tarihi`| TIMESTAMP | NOT NULL, DEFAULT CURRENT_TIMESTAMP | Kodun oluşturulma zamanı. |

### 3.2. odalar Tablosu
| Sütun Adı | Veri Tipi | Kısıtlama | Açıklama |
| :--- | :--- | :--- | :--- |
| `oda_id` | SERIAL | Primary Key | Odanın benzersiz kimliği. |
| `oda_adi` | VARCHAR(50) | UNIQUE, NOT NULL | Odanın numarası veya adı. |
| `kapasite` | INT | DEFAULT 1 | Odanın fiziksel kişi kapasitesi. |
| `aktif_mi` | BOOLEAN | NOT NULL, DEFAULT TRUE | Odanın rezervasyona/kullanıma açık durumu. |

### 3.3. randevular Tablosu
| Sütun Adı | Veri Tipi | Kısıtlama | Açıklama |
| :--- | :--- | :--- | :--- |
| `randevu_id` | SERIAL | Primary Key | Randevu kayıt kimliği. |
| `danisan_kod_id`| VARCHAR(50) | NOT NULL, Foreign Key | `danisan_kodlari(danisan_kod_id)` referansı. |
| `psikolog_id` | INT | NOT NULL, Foreign Key | Seansı yönetecek `personel(personel_id)` referansı. |
| `oda_id` | INT | NOT NULL, Foreign Key | Kullanılacak `odalar(oda_id)` referansı. |
| `baslangic_zamani`| TIMESTAMP | NOT NULL | Randevu başlangıç saati. |
| `bitis_zamani` | TIMESTAMP | NOT NULL | Randevu bitiş saati. |
| `durum` | VARCHAR(30) | DEFAULT 'PLANLANDI'| Randevu statüsü. |
| `olusturulma_tarihi`| TIMESTAMP | NOT NULL, DEFAULT CURRENT_TIMESTAMP | Randevu kaydının açıldığı an. |

### 3.4. oda_etkinlikleri Tablosu
| Sütun Adı | Veri Tipi | Kısıtlama | Açıklama |
| :--- | :--- | :--- | :--- |
| `etkinlik_id` | SERIAL | Primary Key | İdari etkinlik/toplantı kimliği. |
| `oda_id` | INT | NOT NULL, Foreign Key | Kullanılacak `odalar(oda_id)` referansı. |
| `organize_eden_personel_id`| INT | NOT NULL, Foreign Key | Eğitimi düzenleyen `personel(personel_id)` referansı. |
| `etkinlik_adi` | VARCHAR(150)| NOT NULL | Etkinlik/Eğitim başlığı. |
| `katilimci_sayisi`| INT | NULL | Odanın kapasitesini kontrol etmek için katılımcı sayısı. |
| `baslangic_zamani`| TIMESTAMP | NOT NULL | Etkinlik başlangıç saati. |
| `bitis_zamani` | TIMESTAMP | NOT NULL | Etkinlik bitiş saati. |
| `iptal_edildi_mi`| BOOLEAN | DEFAULT FALSE | Etkinliğin iptal statüsü. |

---

## 4. CİHAZ VE OPERASYON YÖNETİMİ

### 4.1. bolumler Tablosu
| Sütun Adı | Veri Tipi | Kısıtlama | Açıklama |
| :--- | :--- | :--- | :--- |
| `bolum_id` | SERIAL | Primary Key | Bölümün benzersiz kimliği. |
| `bolum_adi` | VARCHAR(150)| UNIQUE, NOT NULL | Kurum içindeki bölümün adı. |
| `sorumlu_ad_soyad`| VARCHAR(100)| NOT NULL | Teslim alan yetkilinin adı soyadı. |
| `iletisim_bilgisi`| VARCHAR(100)| NULL | İlgili bölümün dahili numarası veya telefonu. |
| `aktif_mi` | BOOLEAN | DEFAULT TRUE | Bölümün aktif kayıt statüsü. |

### 4.2. cihazlar Tablosu
| Sütun Adı | Veri Tipi | Kısıtlama | Açıklama |
| :--- | :--- | :--- | :--- |
| `cihaz_id` | SERIAL | Primary Key | Cihazın sistem kimliği. |
| `envanter_kodu` | VARCHAR(50) | UNIQUE, NOT NULL | Kurumsal demirbaş/barkod numarası. |
| `cihaz_adi` | VARCHAR(100)| NOT NULL | Cihazın adı. |
| `marka_model` | VARCHAR(100)| NULL | Üretici firma ve cihaz modeli. |
| `seri_no` | VARCHAR(100)| UNIQUE, NULL | Fabrika üretim seri numarası. |
| `zimmetli_oda_id`| INT | Foreign Key, NULL | Cihazın sabit bulunduğu `odalar(oda_id)` referansı. |
| `durum` | ENUM | DEFAULT 'Kullanima_Hazir'| Özel `cihaz_durumu` listesinden mevcut durum. |
| `kayit_tarihi` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Sisteme giriş yapıldığı tarih. |

### 4.3. cihaz_rezervasyonlari Tablosu
| Sütun Adı | Veri Tipi | Kısıtlama | Açıklama |
| :--- | :--- | :--- | :--- |
| `rezervasyon_id`| SERIAL | Primary Key | Kiralama/rezervasyon işleminin kimliği. |
| `cihaz_id` | INT | NOT NULL, Foreign Key | Kiralanan `cihazlar(cihaz_id)` referansı. |
| `bolum_id` | INT | Foreign Key, NULL | Cihazın kiralandığı `bolumler(bolum_id)` referansı. |
| `rezervasyonu_yapan_personel_id`| INT | Foreign Key, NULL | İşlemi gerçekleştiren `personel(personel_id)` referansı. |
| `baslangic_zamani`| TIMESTAMP | NOT NULL | Rezervasyon başlangıç saati. |
| `bitis_zamani` | TIMESTAMP | NOT NULL | Rezervasyon bitiş saati. |
| `iptal_edildi_mi`| BOOLEAN | DEFAULT FALSE | Rezervasyonun iptal durumu. |
| `kullanilacak_oda_id`| INT | Foreign Key, NULL | Cihazın tahsis edildiği geçici `odalar(oda_id)` referansı. |

### 4.4. cihaz_arizalari Tablosu
| Sütun Adı | Veri Tipi | Kısıtlama | Açıklama |
| :--- | :--- | :--- | :--- |
| `ariza_id` | SERIAL | Primary Key | Arıza kaydının benzersiz kimliği. |
| `cihaz_id` | INT | NOT NULL, Foreign Key | Arızalanan `cihazlar(cihaz_id)` referansı. |
| `bildiren_personel`| VARCHAR(100)| NULL | Arızayı bildiren personelin adı (Metin). |
| `ariza_aciklamasi`| TEXT | NOT NULL | Arızanın detaylı metinsel açıklaması. |
| `bildirim_tarihi` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Arızanın bildirildiği tarih ve saat. |
| `cozum_tarihi` | TIMESTAMP | NULL | Arızanın tamir edilip giderildiği tarih. |
| `cozuldu_mu` | BOOLEAN | DEFAULT FALSE | Onarım sürecinin güncel statüsü. |

### 4.5. cihaz_bakimlari Tablosu
| Sütun Adı | Veri Tipi | Kısıtlama | Açıklama |
| :--- | :--- | :--- | :--- |
| `bakim_id` | SERIAL | Primary Key | Bakım kaydının benzersiz kimliği. |
| `cihaz_id` | INT | NOT NULL, Foreign Key | Bakımı yapılan `cihazlar(cihaz_id)` referansı. |
| `bakim_yapan_kisi`| VARCHAR(100)| NULL | İşlemi gerçekleştiren teknisyen veya servis. |
| `yapilan_islem` | TEXT | NULL | Bakım esnasında yapılan işlemlerin açıklaması. |
| `maliyet` | DECIMAL(10,2)| NULL | İşlemin fatura veya harcama maliyeti. |
| `bakim_tarihi` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Bakımın gerçekleştirildiği tarih. |

### 4.6. cihaz_kalibrasyonlari Tablosu
| Sütun Adı | Veri Tipi | Kısıtlama | Açıklama |
| :--- | :--- | :--- | :--- |
| `kalibrasyon_id`| SERIAL | Primary Key | Kalibrasyon kaydının benzersiz kimliği. |
| `cihaz_id` | INT | NOT NULL, Foreign Key | Kalibrasyonu yapılan `cihazlar(cihaz_id)` referansı. |
| `kalibrasyon_yapan_kurum`| VARCHAR(100)| NULL | Ölçümü sağlayan yetkili/akredite kurum. |
| `gecerlilik_tarihi`| DATE | NULL | Kalibrasyon belgesinin son geçerlilik tarihi. |
| `sertifika_no` | VARCHAR(100)| NULL | Kurumun verdiği resmi onay belge numarası. |
| `islem_tarihi` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Kaydın sisteme işlendiği an. |