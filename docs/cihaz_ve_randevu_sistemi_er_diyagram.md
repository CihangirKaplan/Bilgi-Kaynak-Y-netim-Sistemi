# Cihaz, Randevu, Kullanıcı Yönetim Sistemi - Varlık İlişki (ER) Diyagramı

```mermaid
erDiagram
    roller {
        int rol_id PK
        string rol_adi UK
    }

    izinler {
        int izin_id PK
        string izin_adi UK
        string aciklama
    }

    rol_izinleri {
        int rol_id PK, FK
        int izin_id PK, FK
        smallint izin_var
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
        int kullanici_id UK, FK
        string personel_kodu UK
        boolean aktif_mi
        timestamp olusturulma_tarihi
    }

    ogrenciler {
        int ogrenci_id PK
        int kullanici_id UK, FK
        string ad_soyad
        string ogrenci_numarasi UK
        string telefon
        ogrenci_turu tur
        boolean aktif_mi
        timestamp olusturulma_tarihi
    }

    odalar {
        int oda_id PK
        string oda_adi UK
        int kapasite
        boolean aktif_mi
    }

    bolumler {
        int bolum_id PK
        string bolum_adi UK
        string sorumlu_ad_soyad
        string iletisim_bilgisi
        boolean aktif_mi
    }

    danisan_kodlari {
        string danisan_kod_id PK
        boolean ucretli_mi
        string istisna_turu
        boolean aktif_mi
        timestamp olusturulma_tarihi
    }

    faaliyetler {
        int faaliyet_id PK
        string faaliyet_adi UK
        int puan
        boolean aktif_mi
    }

    faaliyet_birimleri {
        int birim_id PK
        string birim_adi UK
        boolean aktif_mi
    }

    danisma_masasi_oturumlari {
        int oturum_id PK
        int ogrenci_id FK
        timestamp baslangic_zamani
        timestamp bitis_zamani
        boolean onaylandi_mi
    }

    ogrenci_faaliyet_takip {
        int takip_id PK
        int ogrenci_id FK
        int faaliyet_id FK
        int adet
        int birim_id FK
        date faaliyet_tarihi
        string aciklama
        boolean onaylandi_mi
        timestamp olusturulma_tarihi
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
        string proje_turu
        string proje_adi_aciklamasi
    }

    cihaz_arizalari {
        int ariza_id PK
        int cihaz_id FK
        string bildiren_personel
        text ariza_aciklamasi
        timestamp bildirim_tarihi
        timestamp cozum_tarihi
        boolean cozuldu_mu
    }

    cihaz_bakimlari {
        int bakim_id PK
        int cihaz_id FK
        string bakim_yapan_kisi
        text yapilan_islem
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

    cihaz_bakim_planlari {
        int plan_id PK
        int cihaz_id FK
        string gorev_turu
        int periyot_gun
        int uyari_suresi_gun
        date sonraki_gorev_tarihi
        boolean aktif_mi
    }

    cihaz_takip_parametreleri {
        int parametre_id PK
        int cihaz_id FK
        string parametre_adi
        string parametre_degeri
        string birim
        timestamp son_guncelleme
    }

    %% İlişkiler (Foreign Key Bağlantıları)
    roller ||--o{ rol_izinleri : "sahiptir"
    izinler ||--o{ rol_izinleri : "ait"
    roller ||--o{ kullanicilar : "tanimlar"
    kullanicilar ||--o| personel : "personelidir"
    kullanicilar ||--o| ogrenciler : "ogrencisidir"
    ogrenciler ||--o{ danisma_masasi_oturumlari : "acar"
    ogrenciler ||--o{ ogrenci_faaliyet_takip : "gerceklestirir"
    faaliyetler ||--o{ ogrenci_faaliyet_takip : "turu"
    faaliyet_birimleri ||--o{ ogrenci_faaliyet_takip : "birimi"
    danisan_kodlari ||--o{ randevular : "kullanilir"
    personel ||--o{ randevular : "yurutur"
    odalar ||--o{ randevular : "gerceklesir"
    odalar ||--o{ oda_etkinlikleri : "ev_sahipligi_yapar"
    personel ||--o{ oda_etkinlikleri : "organize_eder"
    kullanicilar ||--o{ denetim_kayitlari : "tetikler"
    odalar ||--o{ cihazlar : "zimmetlidir"
    cihazlar ||--o{ cihaz_rezervasyonlari : "rezerve_edilir"
    bolumler ||--o{ cihaz_rezervasyonlari : "talep_eder"
    personel ||--o{ cihaz_rezervasyonlari : "yapar"
    odalar ||--o{ cihaz_rezervasyonlari : "kullanilir"
    cihazlar ||--o{ cihaz_arizalari : "arizalanir"
    cihazlar ||--o{ cihaz_bakimlari : "bakim_gorur"
    cihazlar ||--o{ cihaz_kalibrasyonlari : "kalibre_edilir"
    cihazlar ||--o{ cihaz_bakim_planlari : "planlanir"
    cihazlar ||--o{ cihaz_takip_parametreleri : "parametreleri_vardir"
