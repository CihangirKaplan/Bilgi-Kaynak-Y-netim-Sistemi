# Bilgi Kaynak Yönetim Sistemi - ER Diyagramı

## ER Diyagramı (Mermaid.js Formatında)

```mermaid
erDiagram
    bolumler {
        int bolum_id PK
        string bolum_adi UK
        string sorumlu_ad_soyad
        string iletisim_bilgisi
        boolean aktif_mi
    }

    odalar {
        int oda_id PK
        string oda_adi UK
        int kapasite
        boolean aktif_mi
    }

    roller {
        int rol_id PK
        string rol_adi UK
    }

    kullanicilar {
        int kullanici_id PK
        string kullanici_adi UK
        string parola_hash
        int rol_id FK
        boolean aktif_mi
        timestamp olusturulma_tarihi
    }

    personel {
        int personel_id PK
        int kullanici_id FK, UK
        string personel_kodu UK
        boolean aktif_mi
        timestamp olusturulma_tarihi
    }

    danisma_ogrencileri {
        int ogrenci_id PK
        int kullanici_id FK, UK
        string ad_soyad
        string ogrenci_numarasi UK
        string telefon
        boolean aktif_mi
        timestamp olusturulma_tarihi
    }

    danisan_kodlari {
        string danisan_kod_id PK
        boolean ucretli_mi
        string istisna_turu
        boolean aktif_mi
        timestamp olusturulma_tarihi
    }

    cihazlar {
        int cihaz_id PK
        string envanter_kodu UK
        string cihaz_adi
        string marka_model
        string seri_no UK
        int zimmetli_oda_id FK
        cihaz_durumu durum
        timestamp kayit_tarihi
    }

    cihaz_rezervasyonlari {
        int rezervasyon_id PK
        int cihaz_id FK
        int bolum_id FK
        int rezervasyonu_yapan_personel_id FK
        timestamp baslangic_zamani
        timestamp bitis_zamani
        boolean iptal_edildi_mi
        int kullanilacak_oda_id FK
    }

    cihaz_arizalari {
        int ariza_id PK
        int cihaz_id FK
        string bildiren_personel
        string ariza_aciklamasi
        timestamp bildirim_tarihi
        timestamp cozum_tarihi
        boolean cozuldu_mu
    }

    cihaz_bakimlari {
        int bakim_id PK
        int cihaz_id FK
        string bakim_yapan_kisi
        string yapilan_islem
        decimal maliyet
        timestamp bakim_tarihi
    }

    cihaz_kalibrasyonlari {
        int kalibrasyon_id PK
        int cihaz_id FK
        string kalibrasyon_yapan_kurum
        date gecerlilik_tarihi
        string sertifika_no
        timestamp islem_tarihi
    }

    randevular {
        int randevu_id PK
        string danisan_kod_id FK
        int psikolog_id FK
        int oda_id FK
        timestamp baslangic_zamani
        timestamp bitis_zamani
        string durum
        timestamp olusturulma_tarihi
    }

    oda_etkinlikleri {
        int etkinlik_id PK
        int oda_id FK
        int organize_eden_personel_id FK
        string etkinlik_adi
        int katilimci_sayisi
        timestamp baslangic_zamani
        timestamp bitis_zamani
        boolean iptal_edildi_mi
    }

    denetim_kayitlari {
        bigint denetim_id PK
        int kullanici_id FK
        denetim_olay_turu olay_turu
        string hedef_tablo
        int hedef_kayit_id
        timestamp olusturulma_tarihi
    }

    %% İlişkiler (Relationships)
    roller ||--o{ kullanicilar : "sahiptir"
    kullanicilar ||--o| personel : "ait_bir_personel"
    kullanicilar ||--o| danisma_ogrencileri : "ait_bir_ogrenci"
    kullanicilar ||--o{ denetim_kayitlari : "tetikler"
    
    odalar ||--o{ cihazlar : "zimmetlenir"
    odalar ||--o{ cihaz_rezervasyonlari : "kullanilir"
    odalar ||--o{ randevular : "gerceklesir"
    odalar ||--o{ oda_etkinlikleri : "ev_sahipligi_yapar"
    
    personel ||--o{ cihaz_rezervasyonlari : "yapar"
    personel ||--o{ randevular : "psikolog_olarak_atanir"
    personel ||--o{ oda_etkinlikleri : "organize_eder"
    
    bolumler ||--o{ cihaz_rezervasyonlari : "talep_eder"
    danisan_kodlari ||--o{ randevular : "kullanilir"
    
    cihazlar ||--o{ cihaz_rezervasyonlari : "rezerve_edilir"
    cihazlar ||--o{ cihaz_arizalari : "arizalanir"
    cihazlar ||--o{ cihaz_bakimlari : "bakim_görür"
    cihazlar ||--o{ cihaz_kalibrasyonlari : "kalibre_edilir"
