# Cihaz ve Randevu Yönetim Sistemi - Varlık-İlişki (ER) Diyagramı

Veritabanı şifrelerinize ve tablo yapınıza dayanarak hazırlanan Mermaid.js formatındaki ER diyagramı ve modül açıklamaları aşağıdadır.

## Mermaid ER Diyagramı

```mermaid
erDiagram
    bolumler {
        int bolum_id PK
        string bolum_adi
        string sorumlu_ad_soyad
        string iletisim_bilgisi
        boolean aktif_mi
    }

    odalar {
        int oda_id PK
        string oda_adi
        int kapasite
        boolean aktif_mi
    }

    roller {
        int rol_id PK
        string rol_adi
    }

    kullanicilar {
        int kullanici_id PK
        string kullanici_adi
        string parola_hash
        int rol_id FK
        boolean aktif_mi
        timestamp olusturulma_tarihi
    }

    personel {
        int personel_id PK
        int kullanici_id FK
        string personel_kodu
        boolean aktif_mi
        timestamp olusturulma_tarihi
    }

    danisma_ogrencileri {
        int ogrenci_id PK
        int kullanici_id FK
        string ad_soyad
        string ogrenci_numarasi
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
        string envanter_kodu
        string cihaz_adi
        string marka_model
        string seri_no
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
```

## Modül Bazlı İlişki Özeti

1. **Kullanıcı ve Yetkilendirme Modülü:** 
   - `roller` tablosu `kullanicilar` tablosuna 1-N ilişkiyle bağlanır.
   - Her kullanıcı `personel` veya `danisma_ogrencileri` tablosu ile birebir (1-1) ilişkilidir.
   - Gerçekleşen işlemler `denetim_kayitlari` tablosuyla takip edilir.

2. **Cihaz Yönetimi Modülü:**
   - `cihazlar` tablosu `odalar` tablosuna (zimmetli oda olarak) bağlıdır.
   - Cihazların; `cihaz_rezervasyonlari`, `cihaz_arizalari`, `cihaz_bakimlari` ve `cihaz_kalibrasyonlari` tabloları ile bire-çok (1-N) ilişkisi bulunur.

3. **Randevu ve Oda Yönetimi Modülü:**
   - `randevular` tablosu; `danisan_kodlari`, `personel` (psikolog) ve `odalar` tablolarına bağlanır.
   - Kurum içi etkinlikler `oda_etkinlikleri` tablosu ile yönetilir ve `odalar` / `personel` tablolarına referans verir.