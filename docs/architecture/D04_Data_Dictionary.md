# Veritabanı Veri Sözlüğü (Data Dictionary)

Veritabanında kullanılan özel ENUM tipleri şu şekildedir:
*   **`cihaz_durumu`**: `'Kullanima_Hazir'`, `'Rezerve'`, `'Kullanimda'`, `'Arizali'`, `'Bakimda'`, `'Kalibrasyonda'`, `'Kullanim_Disi'`
*   **`denetim_olay_turu`**: `'LOGIN'`, `'LOGIN_FAILED'`, `'CREATE'`, `'UPDATE'`, `'CANCEL'`, `'ROLE_CHANGE'`, `'DEVICE_STATUS_CHANGE'`

## 1. Cihaz ve Bölüm Yönetimi Modülü

Bu modül, merkeze ait cihazların yaşam döngüsünü, zimmet durumlarını, arıza, bakım ve kalibrasyon süreçlerini yönetir.

**Tablo: `bolumler`** (Cihazların kiralandığı/verildiği yerler)
| Kolon Adı | Veri Tipi | Kısıtlamalar (Constraints) | Açıklama |
| :--- | :--- | :--- | :--- |
| `bolum_id` | SERIAL | PRIMARY KEY | Bölümün benzersiz kimliği. |
| `bolum_adi` | VARCHAR(150) | UNIQUE, NOT NULL | Bölümün adı (Örn: Nöroloji Lab). |
| `sorumlu_ad_soyad` | VARCHAR(100) | NOT NULL | Cihazı teslim alan yetkilinin adı soyadı. |
| `iletisim_bilgisi` | VARCHAR(100) | NULL | Telefon veya dahili numara. |
| `aktif_mi` | BOOLEAN | DEFAULT TRUE | Bölümün aktiflik durumu. |

**Tablo: `cihazlar`** (Ana cihaz envanteri)
| Kolon Adı | Veri Tipi | Kısıtlamalar (Constraints) | Açıklama |
| :--- | :--- | :--- | :--- |
| `cihaz_id` | SERIAL | PRIMARY KEY | Cihazın benzersiz kimliği. |
| `envanter_kodu` | VARCHAR(50) | UNIQUE, NOT NULL | Kurum içi cihaz takip kodu. |
| `cihaz_adi` | VARCHAR(100) | NOT NULL | Cihazın genel adı. |
| `marka_model` | VARCHAR(100) | NULL | Cihazın marka ve modeli. |
| `seri_no` | VARCHAR(100) | UNIQUE | Üretici seri numarası. |
| `zimmetli_oda_id` | INT | FK -> `odalar(oda_id)` | Cihazın sabit olarak bulunduğu oda. |
| `durum` | cihaz_durumu | DEFAULT 'Kullanima_Hazir' | Cihazın anlık operasyonel durumu. |
| `kayit_tarihi` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Sisteme eklenme zamanı. |

**Tablo: `cihaz_rezervasyonlari`** (Cihaz kiralama işlemleri)
| Kolon Adı | Veri Tipi | Kısıtlamalar (Constraints) | Açıklama |
| :--- | :--- | :--- | :--- |
| `rezervasyon_id` | SERIAL | PRIMARY KEY | Rezervasyonun benzersiz kimliği. |
| `cihaz_id` | INT | FK -> `cihazlar(cihaz_id)` | Rezerve edilen cihaz. |
| `bolum_id` | INT | FK -> `bolumler(bolum_id)` | Cihazın tahsis edildiği bölüm. |
| `rezervasyonu_yapan_personel_id` | INT | FK -> `personel(personel_id)` | İşlemi gerçekleştiren personel. |
| `baslangic_zamani` | TIMESTAMP | NOT NULL | Rezervasyon başlangıcı. |
| `bitis_zamani` | TIMESTAMP | NOT NULL | Rezervasyon bitişi. |
| `iptal_edildi_mi` | BOOLEAN | DEFAULT FALSE | İptal durumu. |
| `kullanilacak_oda_id` | INT | FK -> `odalar(oda_id)` | Cihazın kullanılacağı fiziksel oda. |

**Tablo: `cihaz_arizalari`**
| Kolon Adı | Veri Tipi | Kısıtlamalar (Constraints) | Açıklama |
| :--- | :--- | :--- | :--- |
| `ariza_id` | SERIAL | PRIMARY KEY | Arıza kaydının kimliği. |
| `cihaz_id` | INT | FK -> `cihazlar(cihaz_id)` | Arızalanan cihaz. |
| `bildiren_personel` | VARCHAR(100) | NULL | Arızayı tespit/ihbar eden kişi. |
| `ariza_aciklamasi` | TEXT | NOT NULL | Arızanın detayı. |
| `bildirim_tarihi` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Arızanın sisteme girildiği tarih. |
| `cozum_tarihi` | TIMESTAMP | NULL | Arızanın giderildiği tarih. |
| `cozuldu_mu` | BOOLEAN | DEFAULT FALSE | Arıza onarım durumu. |

**Tablo: `cihaz_bakimlari`**
| Kolon Adı | Veri Tipi | Kısıtlamalar (Constraints) | Açıklama |
| :--- | :--- | :--- | :--- |
| `bakim_id` | SERIAL | PRIMARY KEY | Bakım işleminin kimliği. |
| `cihaz_id` | INT | FK -> `cihazlar(cihaz_id)` | Bakım yapılan cihaz. |
| `bakim_yapan_kisi` | VARCHAR(100) | NULL | İşlemi gerçekleştiren kişi/firma. |
| `yapilan_islem` | TEXT | NULL | Uygulanan bakımın detayı. |
| `maliyet` | DECIMAL(10,2) | NULL | Bakım maliyeti. |
| `bakim_tarihi` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Bakımın gerçekleştiği tarih. |

**Tablo: `cihaz_kalibrasyonlari`**
| Kolon Adı | Veri Tipi | Kısıtlamalar (Constraints) | Açıklama |
| :--- | :--- | :--- | :--- |
| `kalibrasyon_id` | SERIAL | PRIMARY KEY | Kalibrasyon kaydının kimliği. |
| `cihaz_id` | INT | FK -> `cihazlar(cihaz_id)` | Kalibre edilen cihaz. |
| `kalibrasyon_yapan_kurum` | VARCHAR(100) | NULL | Kalibrasyonu sağlayan akredite kurum. |
| `gecerlilik_tarihi` | DATE | NULL | Sertifikanın son geçerlilik tarihi. |
| `sertifika_no` | VARCHAR(100) | NULL | Belge numarası. |
| `islem_tarihi` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | İşlemin yapıldığı tarih. |

## 2. Randevu ve Oda Yönetimi Modülü

Bu modül, danışanların anonim kodlarını, fiziksel odaları ve bu odalarda gerçekleşecek randevu ile etkinlikleri kapsar.

**Tablo: `danisan_kodlari`**
| Kolon Adı | Veri Tipi | Kısıtlamalar (Constraints) | Açıklama |
| :--- | :--- | :--- | :--- |
| `danisan_kod_id` | VARCHAR(50) | PRIMARY KEY | Danışanı temsil eden anonim operasyonel kod. |
| `ucretli_mi` | BOOLEAN | NOT NULL, DEFAULT TRUE | Hizmetin ücretli/ücretsiz durumu. |
| `istisna_turu` | VARCHAR(50) | DEFAULT 'YOK' | Ücretsiz olma gerekçesi (Örn: Şehit/Gazi yakını). |
| `aktif_mi` | BOOLEAN | NOT NULL, DEFAULT TRUE | Kodun geçerlilik durumu. |
| `olusturulma_tarihi` | TIMESTAMP | NOT NULL, DEFAULT CURRENT | Kodun sisteme eklendiği tarih. |

**Tablo: `odalar`**
| Kolon Adı | Veri Tipi | Kısıtlamalar (Constraints) | Açıklama |
| :--- | :--- | :--- | :--- |
| `oda_id` | SERIAL | PRIMARY KEY | Odanın benzersiz kimliği. |
| `oda_adi` | VARCHAR(50) | UNIQUE, NOT NULL | Odanın tabeladaki adı/numarası. |
| `kapasite` | INT | DEFAULT 1 | Maksimum kişi kapasitesi. |
| `aktif_mi` | BOOLEAN | NOT NULL, DEFAULT TRUE | Odanın kullanıma açıklık durumu. |

**Tablo: `randevular`**
| Kolon Adı | Veri Tipi | Kısıtlamalar (Constraints) | Açıklama |
| :--- | :--- | :--- | :--- |
| `randevu_id` | SERIAL | PRIMARY KEY | Randevunun kimliği. |
| `danisan_kod_id` | VARCHAR(50) | FK -> `danisan_kodlari`, NOT NULL | Randevu alınan danışan kodu. |
| `psikolog_id` | INT | FK -> `personel(personel_id)`, NOT NULL | Görüşmeyi yapacak uzman. |
| `oda_id` | INT | FK -> `odalar(oda_id)`, NOT NULL | Görüşmenin yapılacağı oda. |
| `baslangic_zamani` | TIMESTAMP | NOT NULL | Randevu başlangıcı. |
| `bitis_zamani` | TIMESTAMP | NOT NULL | Randevu bitişi. |
| `durum` | VARCHAR(30) | DEFAULT 'PLANLANDI' | Randevunun anlık durumu. |
| `olusturulma_tarihi` | TIMESTAMP | NOT NULL, DEFAULT CURRENT | Kaydın oluşturulma zamanı. |

**Tablo: `oda_etkinlikleri`**
| Kolon Adı | Veri Tipi | Kısıtlamalar (Constraints) | Açıklama |
| :--- | :--- | :--- | :--- |
| `etkinlik_id` | SERIAL | PRIMARY KEY | İdari toplantı/eğitim kimliği. |
| `oda_id` | INT | FK -> `odalar(oda_id)`, NOT NULL | Etkinliğin yapılacağı oda. |
| `organize_eden_personel_id` | INT | FK -> `personel(personel_id)`, NOT NULL| Düzenleyen yetkili. |
| `etkinlik_adi` | VARCHAR(150) | NOT NULL | Toplantı veya eğitim adı. |
| `katilimci_sayisi` | INT | NULL | Beklenen kişi sayısı (Kapasite kontrolü için). |
| `baslangic_zamani` | TIMESTAMP | NOT NULL | Etkinlik başlangıcı. |
| `bitis_zamani` | TIMESTAMP | NOT NULL | Etkinlik bitişi. |
| `iptal_edildi_mi` | BOOLEAN | DEFAULT FALSE | Etkinliğin iptal durumu. |

## 3. Kimlik, Rol ve Yetki Modülü (Security & Platform)

Sisteme erişim sağlayan kullanıcıları, personeli, öğrencileri ve Rol Tabanlı Erişim Kontrolü (RBAC) matrisini yönetir.

**Tablo: `roller` & `izinler`**
| Tablo Adı | Kolon Adı | Veri Tipi | Kısıtlamalar | Açıklama |
| :--- | :--- | :--- | :--- | :--- |
| **roller** | `rol_id` | SERIAL | PRIMARY KEY | Rol kimliği. |
| | `rol_adi` | VARCHAR(50) | UNIQUE, NOT NULL | Rolün sistemdeki adı. |
| **izinler** | `izin_id` | SERIAL | PRIMARY KEY | İznin kimliği. |
| | `izin_adi` | VARCHAR(100) | UNIQUE, NOT NULL | Kod tarafındaki yetki anahtarı. |
| | `aciklama` | VARCHAR(255) | NULL | İznin işlevsel açıklaması. |

**Tablo: `rol_izinleri`**
| Kolon Adı | Veri Tipi | Kısıtlamalar (Constraints) | Açıklama |
| :--- | :--- | :--- | :--- |
| `rol_id` | INT | FK -> `roller`, PK'nin parçası | İlgili rol. |
| `izin_id` | INT | FK -> `izinler`, PK'nin parçası | İlgili izin. |
| `izin_var` | SMALLINT | DEFAULT 0, CHECK(0,1) | İznin aktif olup olmadığı (Boolean mantığı). |

**Tablo: `kullanicilar`**
| Kolon Adı | Veri Tipi | Kısıtlamalar (Constraints) | Açıklama |
| :--- | :--- | :--- | :--- |
| `kullanici_id` | SERIAL | PRIMARY KEY | Hesabın benzersiz kimliği. |
| `kullanici_adi` | VARCHAR(100) | UNIQUE, NOT NULL | Sisteme giriş (login) adı. |
| `parola_hash` | VARCHAR(255) | NOT NULL | Şifrelenmiş parola verisi. |
| `rol_id` | INT | FK -> `roller(rol_id)`, NOT NULL | Kullanıcının sistemdeki rolü. |
| `aktif_mi` | BOOLEAN | NOT NULL, DEFAULT TRUE | Hesabın erişime açıklık durumu. |
| `olusturulma_tarihi` | TIMESTAMP | NOT NULL, DEFAULT CURRENT | Hesabın açılış zamanı. |

**Tablo: `personel`**
| Kolon Adı | Veri Tipi | Kısıtlamalar (Constraints) | Açıklama |
| :--- | :--- | :--- | :--- |
| `personel_id` | SERIAL | PRIMARY KEY | Personel kaydının kimliği. |
| `kullanici_id` | INT | UNIQUE, FK -> `kullanicilar`, NOT NULL | Bağlı olduğu giriş hesabı. |
| `personel_kodu` | VARCHAR(50) | UNIQUE, NOT NULL | Kurum sicil/personel numarası. |
| `aktif_mi` | BOOLEAN | NOT NULL, DEFAULT TRUE | Kurumda çalışma durumu. |
| `olusturulma_tarihi` | TIMESTAMP | NOT NULL, DEFAULT CURRENT | Kaydın oluşturulma zamanı. |

**Tablo: `danisma_ogrencileri` & `danisma_masasi_oturumlari`**
| Tablo Adı | Kolon Adı | Veri Tipi | Kısıtlamalar | Açıklama |
| :--- | :--- | :--- | :--- | :--- |
| **danisma_ogrencileri** | `ogrenci_id` | SERIAL | PRIMARY KEY | Öğrencinin benzersiz kimliği. |
| | `kullanici_id` | INT | UNIQUE, FK -> `kullanicilar`, NOT NULL | Bağlı hesabı. |
| | `ad_soyad` | VARCHAR(100)| NOT NULL | Öğrencinin adı soyadı. |
| | `ogrenci_numarasi`| VARCHAR(50) | UNIQUE, NOT NULL | Üniversite öğrenci no. |
| | `telefon` | VARCHAR(20) | NULL | İletişim numarası. |
| | `aktif_mi` | BOOLEAN | NOT NULL, DEFAULT TRUE | Görev durumu. |
| **danisma_masasi_oturumlari** | `oturum_id` | SERIAL | PRIMARY KEY | Mesai oturum kimliği. |
| | `ogrenci_id` | INT | FK -> `danisma_ogrencileri`, NOT NULL | Nöbeti tutan öğrenci. |
| | `baslangic_zamani`| TIMESTAMP | NOT NULL, DEFAULT CURRENT | Mesai başlangıcı. |
| | `bitis_zamani` | TIMESTAMP | NOT NULL, CHECK(>baslangic) | Mesai bitişi. |
| | `onaylandi_mi` | BOOLEAN | NOT NULL, DEFAULT FALSE | Nöbetin idarece onayı. |
| | `guncellenme_tarihi`| TIMESTAMP | NOT NULL, DEFAULT CURRENT | Son değişiklik zamanı. |

## 4. Denetim (Audit) Modülü

Sistemdeki kritik güvenlik ve veri değişikliklerinin izlerini barındırır.

**Tablo: `denetim_kayitlari`**
| Kolon Adı | Veri Tipi | Kısıtlamalar (Constraints) | Açıklama |
| :--- | :--- | :--- | :--- |
| `denetim_id` | BIGSERIAL | PRIMARY KEY | Audit kaydının benzersiz kimliği. |
| `kullanici_id` | INT | FK -> `kullanicilar(kullanici_id)`, NULL | İşlemi yapan kullanıcı (Failed login durumunda NULL olabilir). |
| `olay_turu` | denetim_olay_turu | NOT NULL | Gerçekleşen eylemin tipi (Enum). |
| `hedef_tablo` | VARCHAR(100) | NULL | Veri değişikliğinden etkilenen tablo. |
| `hedef_kayit_id` | INT | NULL | Değiştirilen/Silinen kaydın PK değeri. |
| `olusturulma_tarihi` | TIMESTAMP | NOT NULL, DEFAULT CURRENT | Olayın gerçekleştiği tam zaman. |