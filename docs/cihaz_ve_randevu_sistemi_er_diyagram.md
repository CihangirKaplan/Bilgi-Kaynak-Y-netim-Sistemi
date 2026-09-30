# Veritabanı ER Şeması, Değişken Listesi ve Lejant Rehberi

Bu doküman, sistemde bulunan tüm veritabanı tablolarını, veri tiplerini, birincil anahtarları (**PK**), yabancı anahtarları (**FK**), benzersiz kısıtlamaları (**UK**) ve modül ilişkilerini içermektedir.

---

## 🗺️ 1. ER Diyagramı Lejantı (Semboller ve Tipler)

| Sembol / Sütun Niteliği | Anlamı | Açıklama |
| :--- | :--- | :--- |
| **PK** | Primary Key | Tablodaki her kaydı benzersiz şekilde tanımlayan birincil anahtar. |
| **FK** | Foreign Key | Başka bir tablonun PK alanına bağlanarak ilişkileri oluşturan yabancı anahtar. |
| **UK** | Unique Key | Tekrarlanamaz (benzersiz) değerler içeren sütun. |
| **ENUM** | Enumerated Type | Belirli tanımlı metin değerlerinden birini alan özel tip. |
| `||--o{` | 1'e Çok (1..N) | Bir kaydın ilişkili tabloda birden fazla karşılığı olabilir. |
| `||--o|` | 1'e 1 (1..1) | Bir kaydın ilişkili tabloda tam olarak bir karşılığı vardır. |

---

## 📊 2. Bütün Değişkenleri İçeren ER Diyagramı (Mermaid)

```mermaid
erDiagram
    roller {
        SERIAL rol_id PK
        VARCHAR rol_adi UK
    }
    
    izinler {
        SERIAL izin_id PK
        VARCHAR izin_adi UK
        VARCHAR aciklama
    }
    
    rol_izinleri {
        INT rol_id PK, FK
        INT izin_id PK, FK
        SMALLINT izin_var
    }
    
    kullanicilar {
        SERIAL kullanici_id PK
        VARCHAR kullanici_adi UK
        VARCHAR parola_hash
        INT rol_id FK
        BOOLEAN aktif_mi
        TIMESTAMP olusturulma_tarihi
    }
    
    personel {
        SERIAL personel_id PK
        INT kullanici_id UK, FK
        VARCHAR personel_kodu UK
        BOOLEAN aktif_mi
        TIMESTAMP olusturulma_tarihi
    }
    
    danisma_ogrencileri {
        SERIAL ogrenci_id PK
        INT kullanici_id UK, FK
        VARCHAR ad_soyad
        VARCHAR ogrenci_numarasi UK
        VARCHAR telefon
        BOOLEAN aktif_mi
        TIMESTAMP olusturulma_tarihi
    }
    
    danisma_masasi_oturumlari {
        SERIAL oturum_id PK
        INT ogrenci_id FK
        TIMESTAMP baslangic_zamani
        TIMESTAMP bitis_zamani
        BOOLEAN onaylandi_mi
        TIMESTAMP olusturulma_tarihi
        TIMESTAMP guncellenme_tarihi
    }
    
    denetim_kayitlari {
        BIGSERIAL denetim_id PK
        INT kullanici_id FK
        ENUM denetim_olay_turu
        VARCHAR hedef_tablo
        INT hedef_kayit_id
        TIMESTAMP olusturulma_tarihi
    }

    odalar {
        SERIAL oda_id PK
        VARCHAR oda_adi UK
        INT kapasite
        BOOLEAN aktif_mi
    }
    
    danisan_kodlari {
        VARCHAR danisan_kod_id PK
        BOOLEAN ucretli_mi
        VARCHAR istisna_turu
        BOOLEAN aktif_mi
        TIMESTAMP olusturulma_tarihi
    }
    
    randevular {
        SERIAL randevu_id PK
        VARCHAR danisan_kod_id FK
        INT psikolog_id FK
        INT oda_id FK
        TIMESTAMP baslangic_zamani
        TIMESTAMP bitis_zamani
        VARCHAR durum
        TIMESTAMP olusturulma_tarihi
    }
    
    oda_etkinlikleri {
        SERIAL etkinlik_id PK
        INT oda_id FK
        INT organize_eden_personel_id FK
        VARCHAR etkinlik_adi
        INT katilimci_sayisi
        TIMESTAMP baslangic_zamani
        TIMESTAMP bitis_zamani
        BOOLEAN iptal_edildi_mi
    }

    bolumler {
        SERIAL bolum_id PK
        VARCHAR bolum_adi UK
        VARCHAR sorumlu_ad_soyad
        VARCHAR iletisim_bilgisi
        BOOLEAN aktif_mi
    }
    
    cihazlar {
        SERIAL cihaz_id PK
        VARCHAR envanter_kodu UK
        VARCHAR cihaz_adi
        VARCHAR marka_model
        VARCHAR seri_no UK
        INT zimmetli_oda_id FK
        ENUM cihaz_durumu
        TIMESTAMP kayit_tarihi
    }
    
    cihaz_rezervasyonlari {
        SERIAL rezervasyon_id PK
        INT cihaz_id FK
        INT bolum_id FK
        INT rezervasyonu_yapan_personel_id FK
        TIMESTAMP baslangic_zamani
        TIMESTAMP bitis_zamani
        BOOLEAN iptal_edildi_mi
        INT kullanilacak_oda_id FK
    }
    
    cihaz_arizalari {
        SERIAL ariza_id PK
        INT cihaz_id FK
        VARCHAR bildiren_personel
        TEXT ariza_aciklamasi
        TIMESTAMP bildirim_tarihi
        TIMESTAMP cozum_tarihi
        BOOLEAN cozuldu_mu
    }
    
    cihaz_bakimlari {
        SERIAL bakim_id PK
        INT cihaz_id FK
        VARCHAR bakim_yapan_kisi
        TEXT yapilan_islem
        DECIMAL maliyet
        TIMESTAMP bakim_tarihi
    }
    
    cihaz_kalibrasyonlari {
        SERIAL kalibrasyon_id PK
        INT cihaz_id FK
        VARCHAR kalibrasyon_yapan_kurum
        DATE gecerlilik_tarihi
        VARCHAR sertifika_no
        TIMESTAMP islem_tarihi
    }

    %% --- İlişkiler (Relationships) ---
    roller ||--o{ kullanicilar : "sahiptir"
    roller ||--o{ rol_izinleri : "içerir"
    izinler ||--o{ rol_izinleri : "atanır"
    kullanicilar ||--o| personel : "detayıdır"
    kullanicilar ||--o| danisma_ogrencileri : "detayıdır"
    danisma_ogrencileri ||--o{ danisma_masasi_oturumlari : "gerçekleştirir"
    kullanicilar ||--o{ denetim_kayitlari : "tetikler"
    
    odalar ||--o{ cihazlar : "zimmetlidir"
    odalar ||--o{ randevular : "ev sahipliği yapar"
    odalar ||--o{ oda_etkinlikleri : "kullanılır"
    odalar ||--o{ cihaz_rezervasyonlari : "kullanılacak oda"
    
    bolumler ||--o{ cihaz_rezervasyonlari : "kiralar"
    cihazlar ||--o{ cihaz_rezervasyonlari : "rezervasyonu"
    cihazlar ||--o{ cihaz_arizalari : "bildirilir"
    cihazlar ||--o{ cihaz_bakimlari : "görür"
    cihazlar ||--o{ cihaz_kalibrasyonlari : "görür"
    
    danisan_kodlari ||--o{ randevular : "alır"
    personel ||--o{ randevular : "yürütür (psikolog)"
    personel ||--o{ oda_etkinlikleri : "organize eder"
    personel ||--o{ cihaz_rezervasyonlari : "yapar"
