# TKYS Fonksiyonel Gereksinim İzlenebilirlik Tablosu

Bu tablo, `docs/D02_Requirements_v1.md` içindeki 51 fonksiyonel gereksinimin (FR) kodda ve testlerde
karşılığını gösterir. İlk hazırlanma: 6 Kasım 2026. Son güncelleme: 11 Kasım 2026, esas alınan sürüm: `develop` (`7fa9a34`).

Durumlar:

- ✅ Karşılanıyor: kod var ve ilgili davranışı doğrulayan test var.
- ⚠️ Kısmen: kod var, ancak doğrudan test yok ya da bilinen bir sınır var (notta yazılı).
- ❌ Karşılanmıyor.

Testler `tests/` klasöründedir ve CI'da (`TKYS QA Tests`) çalışır. "(PG)" ile işaretli testler gerçek
PostgreSQL ister, ana veritabanını korumak için CI dışındadır ve `TKYS_PG_TEST_ONAY=EVET` ile elle çalıştırılır.

## Özet

| Durum | Adet | Maddeler |
|---|---|---|
| ✅ Karşılanıyor | 46 | Aşağıdaki ⚠️ ve ❌ satırları dışındaki tüm maddeler |
| ⚠️ Kısmen | 4 | FR-008, FR-013, FR-019, FR-041 |
| ❌ Karşılanmıyor | 1 | FR-012 |

## Açık işler

1. **FR-012 Günlük takvim:** Randevu Takvimi'ndeki "Hafta / Gün / Ay" seçicisinde "Gün" ve "Ay" seçilince
   bir şey olmuyor (seçici ekranda var, işlevi bağlı değil). Randevu takvimi arkadaşın alanı.
2. **FR-041 Temel raporlar:** Doküman "V1.0 kapsamındaki raporlar" diyor ama hangi raporların kapsamda olduğu
   yazılı değil. Cihaz raporu, danışma masası raporları ve Excel dışa aktarma var.

## Tablo

### 5.1 Kimlik doğrulama ve yetkilendirme

| FR | Gereksinim | Durum | Kodda nerede | Test kanıtı / not |
|---|---|---|---|---|
| FR-001 | Kullanıcı girişi | ✅ | `POST /api/login` (`sunucu.py`), `login_ekrani.py` | `test_guvenlik_jwt_kalite.py`, `test_kullanici_erisim_kalite.py`, `test_sec_t07_t08_auth.py` |
| FR-002 | Rol tabanlı yetkilendirme | ✅ | `roller`, `izinler`, `rol_izinleri` tabloları; `/api/yetkilerim`; 6 rol (Psikolog, Memur, Müdür, Admin, Danışma Öğrencisi, Proje Asistanı) | `test_menu_yetkileri.py`, `test_kritik_endpoint_rbac_quality.py` |
| FR-003 | Yetkiye göre erişim | ✅ | `izin_kontrol(...)` her uçta | `test_kalan_uclar_yetki.py`, `test_adm_privilege_validation.py`, `test_cihaz_kayit_uclari_yetki.py` |
| FR-004 | Pasif kullanıcı kontrolü | ✅ | `giris_yap` içinde `aktif_mi` kontrolü | `test_kullanici_pasiflestirme.py` |
| FR-005 | Oturum / token kontrolü | ✅ | `guvenlik.py` (`token_dogrula`), `GET /api/korumali-test` | `test_guvenlik_jwt_kalite.py`, `test_sec_t01_t02.py` |

### 5.2 Danışan kodu yönetimi

| FR | Gereksinim | Durum | Kodda nerede | Test kanıtı / not |
|---|---|---|---|---|
| FR-006 | Operasyonel danışan kodu | ✅ | `danisan_kodlari` tablosu, `GET /api/danisan-kodlari` | `test_randevu_branch_quality.py` |
| FR-007 | Danışan kodu oluşturma | ✅ | `otomatik_danisan_kodu_uret`, `danisan_kodu_seq`, `GET /api/randevular/siradaki-kod` | `test_randevu_branch_quality.py`, `test_randevu_girdi_dogrulama.py` |
| FR-008 | Kişisel veri ayrımı | ⚠️ | `danisan_kodlari` tablosunda yalnızca kod ve ücret/istisna alanları var; kişiyle eşleştiren tablo yok | Şema incelemesiyle doğrulandı; "eşleştirme tablosu yok" diyen özel bir test yok |

### 5.3 Randevu ve takvim yönetimi

| FR | Gereksinim | Durum | Kodda nerede | Test kanıtı / not |
|---|---|---|---|---|
| FR-009 | Randevu oluşturma | ✅ | `POST /api/randevular`, `randevu_ekranlari.py` | `test_randevu_branch_quality.py`, `test_randevu_yetkilendirme.py`, `test_randevu_girdi_dogrulama.py` Ek: randevu formunda dolu saatler soluk ve seçilemez (`test_randevu_doluluk_arayuz.py`, `test_randevu_doluluk_sunucu.py`); oda ve psikolog seçimi kuralları `test_randevu_oda_atama_kontrolu.py`. |
| FR-010 | Randevu düzenleme | ✅ | `PATCH /api/randevular/{id}` | `test_randevu_guncelleme_quality.py` |
| FR-011 | Randevu iptali | ✅ | `PATCH /api/randevular/{id}/iptal` | `test_randevu_branch_quality.py`, `test_randevu_yetkilendirme.py` |
| FR-012 | Günlük takvim | ❌ | `haftalik_takvim.py` içinde "Hafta / Gün / Ay" seçicisi var ama `cmb_gorunum` hiçbir işleve bağlı değil | Gün görünümü yok |
| FR-013 | Haftalık takvim | ⚠️ | `haftalik_takvim.py` | Ekran var; arayüz için doğrudan test yok, Randevu Takvimi'ndeki bilinen sorun arkadaşın takibinde |
| FR-014 | Psikolog çakışma kontrolü | ✅ | Migration `d39bab18d6fe` (`psikolog_randevu_cakisma` EXCLUDE kısıtı), sunucuda 409 yanıtı | `test_randevu_branch_quality.py`, `test_randevu_deadlock_quality.py`; gerçek PostgreSQL ile `test_randevu_eszamanlilik_quality.py` (PG) |
| FR-015 | Oda çakışma kontrolü | ✅ | Migration `d39bab18d6fe` (`oda_randevu_cakisma` EXCLUDE kısıtı), sunucuda 409 yanıtı | FR-014 ile aynı testler |
| FR-016 | Cihaz çakışma kontrolü (cihaz rezervasyonunda) | ✅ | Cihaz rezervasyonu EXCLUDE kısıtı, `POST /api/rezervasyonlar` | `test_cihaz_rezervasyon_eszamanlilik.py`; gerçek PostgreSQL için aynı dosyada bir (PG) testi. Gereksinim metni PR #252 ile "cihaz rezervasyonu" olarak düzeltildi |

### 5.4 Oda yönetimi

| FR | Gereksinim | Durum | Kodda nerede | Test kanıtı / not |
|---|---|---|---|---|
| FR-017 | Oda tanımlama | ✅ | `POST /api/odalar` (`ODA_EKLE`), `oda_yonetimi.py` | `test_oda_ekleme_pasiflestirme.py` (yetki, 201 yanıtı, yazılan SQL ve denetim kaydı, ad kırpma, aynı isim 409 ve geri alma, geçersiz girdi 422); yetki için `test_kalan_uclar_yetki.py`. Not: yalnızca boşluktan oluşan oda adı şu an kabul ediliyor (bilinen sınır) |
| FR-018 | Oda pasifleştirme | ✅ | `PATCH /api/odalar/{id}` (`aktif_mi`, `ODA_DUZENLE`), `oda_yonetimi.py` | `test_oda_ekleme_pasiflestirme.py` (pasife alma kayıt silmeden, yeniden aktifleştirme, satır kilidi, 404, boş/null/geçersiz gövde 422, aynı isim 409, denetim kaydı); psikologun tek aktif odası kuralı `test_oda_yetkileri_sunucu.py`; yetki `test_odalar_yetkilendirme_quality.py` |
| FR-019 | Oda uygunluğu | ⚠️ | "Oda Kullanımı" sayfası (`ODA_DURUMU_GORUNTULE`); randevuda oda çakışması 409 verir | Çakışma testleri FR-015'te; Oda Kullanımı sayfası için doğrudan test bulamadım |

### 5.5 Cihaz yönetimi ve rezervasyon

| FR | Gereksinim | Durum | Kodda nerede | Test kanıtı / not |
|---|---|---|---|---|
| FR-020 | Cihaz ekleme | ✅ | `POST /api/cihazlar`, `cihaz_ekranlari.py` | `test_cihaz_modulu.py`, `test_cihaz_kayit_uclari_yetki.py` |
| FR-021 | Cihaz düzenleme | ✅ | `PATCH /api/cihazlar/{id}` | `test_cihaz_modulu.py`, `test_audit_security.py` |
| FR-022 | Cihaz pasifleştirme | ✅ | Durum "Kullanım Dışı" yapılarak (`PATCH /api/cihazlar/{id}`) | `test_cihaz_modulu.py`, `test_audit_security.py` |
| FR-023 | Cihaz durumları | ✅ | `cihaz_durumu` enum: Kullanıma Hazır, Rezerve, Kullanımda, Arızalı, Bakımda, Kalibrasyonda, Kullanım Dışı | `test_cihaz_modulu.py`, `test_ariza_cihaz_durumu.py` |
| FR-024 | Cihaz rezervasyonu | ✅ | `POST /api/rezervasyonlar`, `cihaz_rezervasyon_ekranlari.py` | `test_cihaz_modulu.py`, `test_cihaz_rezervasyon_eszamanlilik.py` |
| FR-025 | Cihaz müsaitlik kontrolü | ✅ | `GET /api/cihaz-uygunluk`, `cihaz_uygunluk_mantigi.py`, `cihaz_uygunluk_ekrani.py` (haftalık takvim, "Müsait cihaz bul") | `test_cihaz_uygunluk_api.py`, `test_cihaz_uygunluk_mantigi.py`, `test_cihaz_uygunluk_ekrani.py`, `test_cihaz_uygunluk_baglanti.py`. Not: Bu sayfa 6 Kasım 2026'ya kadar yalnızca yer tutucuydu; gereksinim bu tarihte gerçekten karşılandı |
| FR-026 | Rezervasyon engelleme | ✅ | `POST /api/rezervasyonlar` (durum ve bakım/kalibrasyon aralığı denetimi) | `test_cihaz_modulu.py`, `test_cihaz_uygunluk_mantigi.py` |
| FR-027 | Eşzamanlı rezervasyon kontrolü | ✅ | EXCLUDE kısıtı, çakışmada 409 | `test_cihaz_rezervasyon_eszamanlilik.py`; gerçek PostgreSQL ile bir (PG) testi |

### 5.6 Bakım, kalibrasyon ve arıza yönetimi

| FR | Gereksinim | Durum | Kodda nerede | Test kanıtı / not |
|---|---|---|---|---|
| FR-028 | Bakım kaydı | ✅ | `POST /api/bakimlar`, `cihaz_bakim_ekranlari.py` | `test_audit_zorunlulugu_quality.py`, `test_bakim_uyari_suresi.py` |
| FR-029 | Bakım geçmişi | ✅ | `GET /api/bakimlar`, Bakım Kayıtları listesi | `test_bakim_uyari_suresi.py`, `test_liste_hatirlatma_ve_yenileme.py` |
| FR-030 | Sonraki bakım | ✅ | `sonraki_bakim_tarihi`, uyarı süresi, plan bağlantısı | `test_bakim_uyari_suresi.py`, `test_bakim_plani_baglanti.py` |
| FR-031 | Kalibrasyon kaydı | ✅ | `POST /api/kalibrasyonlar`, `cihaz_kalibrasyon_ekranlari.py` | `test_audit_zorunlulugu_quality.py`, `test_bakim_uyari_suresi.py` |
| FR-032 | Arıza kaydı | ✅ | `POST /api/arizalar`, `cihaz_ariza_ekranlari.py` | `test_ariza_cihaz_durumu.py`, `test_ariza_envanter_ekranlari.py` |
| FR-033 | Arıza durumu | ✅ | `PUT /api/arizalar/{id}` (çözüldü bilgisi, cihaz durumu eşleşmesi) | `test_ariza_cihaz_durumu.py`, `test_audit_security.py` |

### 5.7 Müdür yönetim işlemleri

| FR | Gereksinim | Durum | Kodda nerede | Test kanıtı / not |
|---|---|---|---|---|
| FR-034 | Kullanıcı oluşturma | ✅ | `POST /api/kullanicilar` (`KULLANICI_OLUSTUR`) | `test_kullanici_olusturma.py`, `test_kullanici_personel_atomik_quality.py` Not: ADMIN hesabı uygulamadan açılamaz (`test_admin_hesap_korumasi.py`); ikinci yönetici yalnızca sunucuda `scripts/ilk_admin_olustur.py --ek-yonetici` ile açılır (`test_ilk_admin_olustur.py`). |
| FR-035 | Personel tanımlama | ✅ | `POST /api/personel` (`PERSONEL_TANIMLA`) | `test_kullanici_personel_atomik_quality.py`, `test_kullanici_personel_tarih_rol_uyarisi.py` |
| FR-036 | Rol atama | ✅ | `PATCH /api/kullanicilar/{id}/rol` (`ROL_ATAMA_DEGISTIRME`) | `test_adm_privilege_validation.py`, `test_kullanici_personel_tarih_rol_uyarisi.py` Not: ADMIN rolü atanamaz ve başka bir role dönüştürülemez; psikolog rolüne geçişte oda zorunludur (`test_rol_degistirme_oda_kurali.py`). |
| FR-037 | Kullanıcı pasifleştirme | ✅ | `PATCH /api/kullanicilar/{id}/durum-degistir` | `test_kullanici_pasiflestirme.py`, `test_kullanici_durum_degistir.py` Not: ADMIN hesabının aktiflik durumu değiştirilemez (`test_admin_hesap_korumasi.py`). |
| FR-038 | Bakım yapılandırması (tür, periyot, ayar) | ✅ | Bakım Planları sayfası, `/api/bakim-planlari`, `plan_secimi.py` | `test_bakim_planlari_api.py`, `test_bakim_plani_ekrani.py`, `test_bakim_plani_baglanti.py`, `test_plan_secimi.py`. Not: Planları Memur, Müdür ve Admin yönetir |
| FR-039 | Kalibrasyon yapılandırması (periyot, ayar) | ✅ | Aynı sayfa; "Kalibrasyon" ile başlayan plan türü | FR-038 ile aynı testler |

### 5.8 Dashboard ve raporlama

| FR | Gereksinim | Durum | Kodda nerede | Test kanıtı / not |
|---|---|---|---|---|
| FR-040 | Dashboard | ✅ | `dashboard_ekrani.py`, `/api/dashboard/*` (özet, bugünkü randevular ve rezervasyonlar, yaklaşan işlemler) | `test_dashboard_kalibrasyondaki_cihaz.py`, `test_dashboard_cihaz_ozeti_izni.py`, `test_bakim_uyari_suresi.py` Ek: özet kartları tıklanabilir, tablolar kaydırılabilir, yaklaşan işlemler listesi 50 kayıtla sınırlı (`test_dashboard_kart_tiklama.py`, `test_dashboard_tablo_kaydirma.py`, `test_dashboard_tekerlek_kilidi.py`, `test_yaklasan_islemler_siniri.py`). |
| FR-041 | Temel raporlar | ⚠️ | `GET /api/cihaz-raporlari`, `cihaz_raporlari_ekrani.py`, danışma masası raporları, `rapor_excel.py` | `test_cihaz_raporlari.py`, `test_rapor_excel.py`. Not: "V1.0 raporları" listesi dokümanda tanımlı değil |

### 5.9 Audit

| FR | Gereksinim | Durum | Kodda nerede | Test kanıtı / not |
|---|---|---|---|---|
| FR-042 | Audit kaydı oluşturma | ✅ | `denetim.py`, uçlarda `denetim_kaydi_olustur` | `test_audit_zorunlulugu_quality.py`, `test_audit_transaction_calls_quality.py`, `test_audit_security.py` |
| FR-043 | Audit işlem türleri | ✅ | `denetim_olay_turu` enum: LOGIN, LOGIN_FAILED, CREATE, UPDATE, CANCEL, ROLE_CHANGE, DEVICE_STATUS_CHANGE (+ DELETE, PASSWORD_RESET) | `test_audit_security.py`, `test_audit_zorunlulugu_update_delete_quality.py` Not: `PASSWORD_RESET` olayı hem yönetici sıfırlamasında hem kurtarma aracında yazılır (`test_parola_sifirlama_audit_ui.py`, `test_admin_parola_kurtar.py`). |
| FR-044 | Audit görüntüleme | ✅ | `GET /api/audit-kayitlari` (`AUDIT_KAYITLARI_INCELE`), `audit_kayitlari_ekrani.py` | `test_audit_kayitlari_api.py` |
| FR-045 | Audit bütünlüğü | ✅ | API'de audit'i değiştiren veya silen uç yok (yalnızca `GET`); veritabanında `denetim_kayitlari` için UPDATE, DELETE ve TRUNCATE tetikleyiciyle engellenir (migration `f3a9c2e47b18`) | `test_audit_degistirilemez.py`; gerçek PostgreSQL'de elle doğrulandı. Not: Yalnızca `crkys_alembic_test` test veritabanı kilitten muaftır; veritabanı yöneticisi kilidi bilerek kaldırabilir |

### 5.10 Yedekleme ve geri yükleme

| FR | Gereksinim | Durum | Kodda nerede | Test kanıtı / not |
|---|---|---|---|---|
| FR-046 | PostgreSQL yedekleme | ✅ | `scripts/veritabani_yedekle.py` | `test_backup_restore.py` |
| FR-047 | Otomatik yedekleme | ✅ | `scripts/otomatik_yedekleme.py`, `scripts/windows/kurulum.py` (Görev Zamanlayıcı), `scripts/launchd/kurulum.py` | `test_otomatik_yedekleme.py`, `test_windows_backup_setup.py` |
| FR-048 | Yedek tarih bilgisi | ✅ | Dosya adı `<veritabani>_<tarih>_<saat>_<mikrosaniye>.dump` | `test_backup_restore.py` |
| FR-049 | Yedek rotasyonu | ✅ | `scripts/yedek_rotasyonu.py` (varsayılan 7 gün) | `test_backup_restore.py`, `test_otomatik_yedekleme.py` |
| FR-050 | Geri yükleme | ✅ | `scripts/veritabani_geri_yukle.py` (yeni veritabanına) | `test_veritabani_geri_yukle.py` |
| FR-051 | Geri yükleme doğrulaması | ✅ | Betik sonunda tablo satır sayıları ve migration sürümü kaynak veritabanıyla yan yana gösterilir | `test_veritabani_geri_yukle.py` (`test_main_basarida_kayit_sayilarini_karsilastirir`) |

## Gereksinim listesi dışında eklenen güvenlik ve kullanılabilirlik işleri

Bunlar `D02` içindeki FR maddeleri değildir; Proje Detayları belgesindeki güvenlik ve kullanılabilirlik hedeflerini
(parola, yetki, izlenebilirlik) destekler. Doğrulayan testler yanda.

| İş | Ne yapar | Kodda nerede | Test kanıtı |
|---|---|---|---|
| Parola sıfırlama talebi | Giriş ekranından yöneticiye bildirim; kullanıcı adının var olup olmadığı belli olmaz, her kullanıcı için en fazla bir açık talep | `POST /api/parola-sifirlama-talebi`, `parola_talebi_dialog.py`, `login_ekrani.py` | `test_parola_sifirlama_talebi.py`, `test_parola_talebi_arayuz.py` |
| Yönetici talepler paneli ve bildirimleri | Bekleyen talepler Kullanıcı & Personel sayfasında, ana panelde ve zil simgesinde görünür | `k_personel_ekranlari.py`, `dashboard_ekrani.py`, `main_window.py` | `test_parola_talebi_arayuz.py`, `test_gui_parola_sifirlama_quality.py` |
| Geçici parola penceresi | Kopyalanabilir; pano 60 saniye sonra temizlenir; onayda kimlik doğrulama hatırlatması | `gecici_parola_dialog.py` | `test_gecici_parola_ve_sifre_kurallari.py`, `test_gui_parola_sifirlama_quality.py` |
| Yeni şifre kuralları | Canlı kural listesi ve güç göstergesi; düğme kurallar sağlanınca açılır | `parola_kurallari.py`, `sifre_degistir_ekrani.py` | `test_gecici_parola_ve_sifre_kurallari.py` |
| Yönetici parola kurtarma | Tek yönetici şifresini unutursa sunucu bilgisayarında kurtarma aracı | `scripts/admin_parola_kurtar.py`, `scripts/windows/admin_parola_kurtar.bat` | `test_admin_parola_kurtar.py` (gerçek PostgreSQL'de elle doğrulandı) |
| Ek yönetici oluşturma | Uygulamadan yönetici açılamadığı için ikinci yönetici sunucuda açılır | `scripts/ilk_admin_olustur.py --ek-yonetici` | `test_ilk_admin_olustur.py` (gerçek PostgreSQL'de elle doğrulandı) |
| Test güvenilirliği | Testlerde "bugün" modül yüklenirken sabitlenemez; gece yarısını geçen CI'da sebepsiz kırılma önlenir | — | `test_zaman_bagimsizligi.py` |

Proje Detayları belgesindeki güvenlik testi SEC-005 (çok sayıda hatalı parola → geçici kilitleme) `giris_yap` içindeki
hatalı giriş sayacı ve kilit süresiyle karşılanır (`test_sec_t07_t08_auth.py`, `test_kullanici_pasiflestirme.py`).
