# TKYS Fonksiyonel Gereksinim İzlenebilirlik Tablosu

Bu tablo, `docs/requirements/D02_Requirements_v1.md` içindeki 67 fonksiyonel gereksinimin (FR) kodda ve testlerde
karşılığını gösterir. İlk hazırlanma: 6 Kasım 2026. Son güncelleme: 22 Kasım 2026, esas alınan sürüm: `develop` (`1252643`).

Durumlar:

- ✅ Karşılanıyor: kod var ve ilgili davranışı doğrulayan test var.
- ⚠️ Kısmen: kod var, ancak doğrudan test yok ya da bilinen bir sınır var (notta yazılı).
- ❌ Karşılanmıyor.

Testler `tests/` klasöründedir ve CI'da (`TKYS QA Tests`) çalışır. "(PG)" ile işaretli testler gerçek
PostgreSQL ister, ana veritabanını korumak için CI dışındadır ve `TKYS_PG_TEST_ONAY=EVET` ile elle çalıştırılır.

## Özet

| Durum | Adet | Maddeler |
|---|---|---|
| ✅ Karşılanıyor | 62 | Aşağıdaki ⚠️ ve ❌ satırları dışındaki tüm maddeler |
| ⚠️ Kısmen | 5 | FR-052, FR-053, FR-054, FR-055, FR-058 |
| ❌ Karşılanmıyor | 0 | — |

## Açık işler

1. **FR-012 Günlük takvim / FR-013 Haftalık takvim:** Menüye bağlı olmayan `client/haftalik_takvim.py` prototipi **silindi** (22 Kasım 2026);
   ayrı bir takvim ekranı **yapılmayacak**. Gereksinimler **Oda Kullanımı** ekranının **Gün** ve **Hafta** görünümleriyle karşılanıyor (randevular
   oda bazlı saatlik ızgarada); bu değerlendirme ürün sahibine bildirilecektir. İtiraz gelirse ayrı takvim ekranı yeniden ele alınır.
2. **FR-052 … FR-055 ve FR-058 (⚠️ Kısmen):** İlgili testler 20 Kasım 2026'da çalıştırıldı ve geçti (336 geçti). Gerçek veritabanı testlerinden
   dördü, test veritabanında hazır öğrenci olmadığında **atlanıyordu** (`test_ogrenci_yonetimi_postgresql_quality.py`,
   `test_faaliyet_turleri_postgresql_quality.py`); bu testler artık kendi verisini oluşturup temizlediği için CI'da da çalışır.
   Maddelerin durumu ürün sahibiyle gözden geçirilip ✅'e alınabilir. FR-056, FR-057 ve FR-059 … FR-067'nin testleri 22 Kasım 2026'da
   yeniden çalıştırılıp geçtiği (288 test) için bu maddeler ✅'e alındı.

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
| FR-007 | Danışan kodu oluşturma | ✅ | `otomatik_danisan_kodu_uret` (yıl bazlı: DAN-<yıl>-<sıra>, kayıt anında kilit altında), `GET /api/randevular/siradaki-kod` (önizleme, sayaç tüketmez) | `test_randevu_branch_quality.py`, `test_randevu_girdi_dogrulama.py` |
| FR-008 | Kişisel veri ayrımı | ✅ | `danisan_kodlari` tablosunda yalnızca kod, ücret/istisna, aktiflik, tarih ve oluşturan psikolog var; danışan koduna yalnızca `randevular` başvurur; kişi tablolarıyla (öğrenci, kullanıcı, personel) bağlantı yok; kodu oluşturan psikolog dışında kişi göstergesi yok | Şema: `test_kisisel_veri_ayrimi_pg_quality.py` (gerçek PostgreSQL; fazladan sütun, eşleştirme tablosu, serbest metin sütunu eklenirse kırılır); uygulama: `test_kisisel_veri_ayrimi.py` (modeller, yazılan sütunlar, uçlar, yanıtlar, fazladan kişisel alanlar yok sayılır). `istisna_turu` yalnızca YOK, KANSER, SEHIT_GAZI olabilir (başka metin 422; ücretli danışanda yalnızca YOK), serbest metin yazılamaz |

### 5.3 Randevu ve takvim yönetimi

| FR | Gereksinim | Durum | Kodda nerede | Test kanıtı / not |
|---|---|---|---|---|
| FR-009 | Randevu oluşturma | ✅ | `POST /api/randevular`, `randevu_ekranlari.py` | `test_randevu_branch_quality.py`, `test_randevu_yetkilendirme.py`, `test_randevu_girdi_dogrulama.py` Ek: randevu formunda dolu saatler soluk ve seçilemez (`test_randevu_doluluk_arayuz.py`, `test_randevu_doluluk_sunucu.py`); oda ve psikolog seçimi kuralları `test_randevu_oda_atama_kontrolu.py`. |
| FR-010 | Randevu düzenleme | ✅ | `PATCH /api/randevular/{id}` | `test_randevu_guncelleme_quality.py` |
| FR-011 | Randevu iptali | ✅ | `PATCH /api/randevular/{id}/iptal` | `test_randevu_branch_quality.py`, `test_randevu_yetkilendirme.py` |
| FR-012 | Günlük takvim | ✅ | `client/oda_kullanimi_ekrani.py`: **Oda Kullanımı** ekranının **Gün** görünümü, seçilen günün randevularını (rezervasyon ve etkinliklerle birlikte) saatlik ızgarada gösterir; ayrıca Randevu Yönetimi listesi (dönem süzgeci) ve Dashboard "bugünkü randevular" | `test_oda_kullanimi.py`. Ayrı bir takvim ekranı yapılmadı (prototip silindi); gereksinim bu görünümle karşılanıyor, ürün sahibine bildirildi |
| FR-013 | Haftalık takvim | ✅ | `client/oda_kullanimi_ekrani.py`: **Oda Kullanımı** ekranının **Hafta** görünümü (Pazartesi-Pazar, gün gün, ileri/geri gezinme) randevuları haftalık ızgarada gösterir | `test_oda_kullanimi.py` (hafta gezinme). Ayrı bir takvim ekranı yapılmadı; gereksinim bu görünümle karşılanıyor, ürün sahibine bildirildi |
| FR-014 | Psikolog çakışma kontrolü | ✅ | Migration `d39bab18d6fe` (`psikolog_randevu_cakisma` EXCLUDE kısıtı), sunucuda 409 yanıtı | `test_randevu_branch_quality.py`, `test_randevu_deadlock_quality.py`; gerçek PostgreSQL ile `test_randevu_eszamanlilik_quality.py` (PG) |
| FR-015 | Oda çakışma kontrolü | ✅ | Migration `d39bab18d6fe` (`oda_randevu_cakisma` EXCLUDE kısıtı), sunucuda 409 yanıtı | FR-014 ile aynı testler |
| FR-016 | Cihaz çakışma kontrolü (cihaz rezervasyonunda) | ✅ | Cihaz rezervasyonu EXCLUDE kısıtı, `POST /api/rezervasyonlar` | `test_cihaz_rezervasyon_eszamanlilik.py`; gerçek PostgreSQL için aynı dosyada bir (PG) testi. Gereksinim metni PR #252 ile "cihaz rezervasyonu" olarak düzeltildi |

### 5.4 Oda yönetimi

| FR | Gereksinim | Durum | Kodda nerede | Test kanıtı / not |
|---|---|---|---|---|
| FR-017 | Oda tanımlama | ✅ | `POST /api/odalar` (`ODA_EKLE`), `oda_yonetimi.py` | `test_oda_ekleme_pasiflestirme.py` (yetki, 201 yanıtı, yazılan SQL ve denetim kaydı, ad kırpma, aynı isim 409 ve geri alma, geçersiz girdi 422); yetki için `test_kalan_uclar_yetki.py`. Not: oda adı kırpılır ve yalnızca boşluktan oluşan ad reddedilir (422) |
| FR-018 | Oda pasifleştirme | ✅ | `PATCH /api/odalar/{id}` (`aktif_mi`, `ODA_DUZENLE`), `oda_yonetimi.py` | `test_oda_ekleme_pasiflestirme.py` (pasife alma kayıt silmeden, yeniden aktifleştirme, satır kilidi, 404, boş/null/geçersiz gövde 422, aynı isim 409, denetim kaydı); psikologun tek aktif odası kuralı `test_oda_yetkileri_sunucu.py`; yetki `test_odalar_yetkilendirme_quality.py` |
| FR-019 | Oda uygunluğu | ✅ | `GET /api/randevular/doluluk` (`TAKVIM_GORUNTULE`; seçilen gün için oda ve psikologun dolu saatleri, kimlik bilgisi dönmez), randevu formlarında dolu saatler soluk ve seçilemez (`randevu_ekranlari.py`); son karar randevu uçlarında oda çakışması 409; "Oda Kullanımı" sayfası (`ODA_DURUMU_GORUNTULE`) | `test_randevu_doluluk_sunucu.py`, `test_randevu_doluluk_arayuz.py`, `test_randevu_oda_atama_kontrolu.py`; çakışma 409 için FR-015'teki testler; sayfa yenileme `test_oda_yonetimi_yenileme.py` |

### 5.5 Cihaz yönetimi ve rezervasyon

| FR | Gereksinim | Durum | Kodda nerede | Test kanıtı / not |
|---|---|---|---|---|
| FR-020 | Cihaz ekleme | ✅ | `POST /api/cihazlar`, `cihaz_ekranlari.py` | `test_cihaz_modulu.py`, `test_cihaz_kayit_uclari_yetki.py` |
| FR-021 | Cihaz düzenleme | ✅ | `PATCH /api/cihazlar/{id}` | `test_cihaz_modulu.py`, `test_audit_security.py` |
| FR-022 | Cihaz pasifleştirme | ✅ | Durum "Kullanım Dışı" yapılarak (`PATCH /api/cihazlar/{id}`) | `test_cihaz_modulu.py`, `test_audit_security.py` |
| FR-023 | Cihaz durumları | ✅ | `cihaz_durumu` enum: Kullanıma Hazır, Rezerve, Kullanımda, Arızalı, Bakımda, Kalibrasyonda, Kullanım Dışı. Etkin durum tek kaynaktan türer (`ETKIN_CIHAZ_DURUMU_SQL`): Arızalı = çözülmemiş arıza kaydı, Bakımda/Kalibrasyonda = bugünkü tarih aralığı, Rezerve/Kullanımda = bugünkü rezervasyon. "Arızalı" elle seçilemez; açık arızalı cihazın durumu elle değiştirilemez (yalnızca Kullanım Dışı) | `test_cihaz_modulu.py`, `test_ariza_cihaz_durumu.py`, `test_ariza_durum_tutarliligi.py`; gerçek PostgreSQL: `test_cihaz_odasi_atama_pg_quality.py` |
| FR-024 | Cihaz rezervasyonu | ✅ | `POST /api/rezervasyonlar`, `cihaz_rezervasyon_ekranlari.py` | `test_cihaz_modulu.py`, `test_cihaz_rezervasyon_eszamanlilik.py` Ek: liste sayfası diğer cihaz sayfalarıyla aynı görünümde (cihaz, oda, proje, tarih/saat, durum etiketi, arama ve sayaçlar) (`test_rezervasyon_liste_arayuzu.py`, `test_rezervasyon_sure_durumu.py`); takvimde rezerve saatler (`test_cihaz_uygunluk_ekrani.py`) |
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
| FR-038 | Bakım yapılandırması (tür, periyot, ayar) | ✅ | Bakım Planları sayfası, `/api/bakim-planlari`, `plan_secimi.py` | `test_bakim_planlari_api.py`, `test_bakim_plani_ekrani.py`, `test_bakim_plani_baglanti.py`, `test_plan_secimi.py`, `test_cihaz_kisayollari_adim4.py` (plandan ▶ ile bakım/kalibrasyon kaydı açma). Not: Planları Memur, Müdür ve Admin yönetir |
| FR-039 | Kalibrasyon yapılandırması (periyot, ayar) | ✅ | Aynı sayfa; "Kalibrasyon" ile başlayan plan türü | FR-038 ile aynı testler |

### 5.8 Dashboard ve raporlama

| FR | Gereksinim | Durum | Kodda nerede | Test kanıtı / not |
|---|---|---|---|---|
| FR-040 | Dashboard | ✅ | `dashboard_ekrani.py`, `/api/dashboard/*` (özet, bugünkü randevular ve rezervasyonlar, yaklaşan işlemler) | `test_dashboard_kalibrasyondaki_cihaz.py`, `test_dashboard_cihaz_ozeti_izni.py`, `test_bakim_uyari_suresi.py` Ek: özet kartları tıklanabilir, tablolar kaydırılabilir, yaklaşan işlemler listesi 50 kayıtla sınırlı (`test_dashboard_kart_tiklama.py`, `test_dashboard_tablo_kaydirma.py`, `test_dashboard_tekerlek_kilidi.py`, `test_yaklasan_islemler_siniri.py`). |
| FR-041 | Temel raporlar | ✅ | `GET /api/cihaz-raporlari`, `GET /api/danisma/raporlar`, `GET /api/puan-raporu`, `GET /api/randevu-raporu`, `GET /api/oda-kullanim-raporu`, `GET /api/cihaz-rezervasyon-raporu`, `GET /api/bakim-plani-raporu`, `GET /api/ogrenci-raporu`, `GET /api/faaliyet-raporu`, `GET /api/yetki-raporu`, `GET /api/yonetim-raporlari/*`, `GET /api/audit-kayitlari` (Excel dışa aktarma); ilgili PySide6 rapor ekranları ve Excel dışa aktarma modülleri | `test_cihaz_raporlari.py`, `test_danisma_rapor_excel.py`, `test_puan_raporu.py`, `test_randevu_raporu.py`, `test_rapor_excel.py`, `test_rapor_sayfalari.py`, `test_rapor_ogrenci_faaliyet.py`, `test_rapor_bakim_plani.py`, `test_rapor_kullanim_tablolari.py` (164 test başarılı, 16.11.2026). Gerçek PostgreSQL testi: `test_randevu_raporu_pg_quality.py` (bu doğrulamada çalıştırılmadı), `test_rapor_tutarliligi_pg_quality.py` (raporlar arası tutarlılık, gerçek PostgreSQL). Ayrıntılı açıklama: `docs/Raporlama_Rehberi.md`. |

### 5.9 Audit

| FR | Gereksinim | Durum | Kodda nerede | Test kanıtı / not |
|---|---|---|---|---|
| FR-042 | Audit kaydı oluşturma | ✅ | `denetim.py`, uçlarda `denetim_kaydi_olustur` | `test_audit_zorunlulugu_quality.py`, `test_audit_transaction_calls_quality.py`, `test_audit_security.py` |
| FR-043 | Audit işlem türleri | ✅ | `denetim_olay_turu` enum: LOGIN, LOGIN_FAILED, CREATE, UPDATE, CANCEL, ROLE_CHANGE, DEVICE_STATUS_CHANGE (+ DELETE, PASSWORD_RESET, EXPORT) | `test_audit_security.py`, `test_audit_zorunlulugu_update_delete_quality.py` Not: `PASSWORD_RESET` olayı hem yönetici sıfırlamasında hem kurtarma aracında yazılır (`test_parola_sifirlama_audit_ui.py`, `test_admin_parola_kurtar.py`). |
| FR-044 | Audit görüntüleme | ✅ | `GET /api/audit-kayitlari` (`AUDIT_KAYITLARI_INCELE`), `audit_kayitlari_ekrani.py` | `test_audit_kayitlari_api.py` |
| FR-045 | Audit bütünlüğü | ✅ | API'de audit'i değiştiren veya silen uç yok (yalnızca `GET`); veritabanında `denetim_kayitlari` için UPDATE, DELETE ve TRUNCATE tetikleyiciyle engellenir (migration `f3a9c2e47b18`) | `test_audit_degistirilemez.py`; gerçek PostgreSQL'de elle doğrulandı. Not: Yalnızca `crkys_alembic_test` test veritabanı kilitten muaftır; veritabanı yöneticisi kilidi bilerek kaldırabilir |

### 5.10 Yedekleme ve geri yükleme

| FR | Gereksinim | Durum | Kodda nerede | Test kanıtı / not |
|---|---|---|---|---|
| FR-046 | PostgreSQL yedekleme | ✅ | `scripts/backup/veritabani_yedekle.py` | `test_backup_restore.py` |
| FR-047 | Otomatik yedekleme | ✅ | `scripts/backup/otomatik_yedekleme.py`, `scripts/windows/kurulum.py` (Görev Zamanlayıcı) | `test_otomatik_yedekleme.py`, `test_windows_backup_setup.py` |
| FR-048 | Yedek tarih bilgisi | ✅ | Dosya adı `<veritabani>_<tarih>_<saat>_<mikrosaniye>.dump` | `test_backup_restore.py` |
| FR-049 | Yedek rotasyonu | ✅ | `scripts/backup/yedek_rotasyonu.py` (varsayılan 14 gün; en yeni 3 yedek her zaman korunur) | `test_backup_restore.py`, `test_otomatik_yedekleme.py` |
| FR-050 | Geri yükleme | ✅ | `scripts/restore/veritabani_geri_yukle.py` (yeni veritabanına) | `test_veritabani_geri_yukle.py` |
| FR-051 | Geri yükleme doğrulaması | ✅ | Betik sonunda tablo satır sayıları ve migration sürümü kaynak veritabanıyla yan yana gösterilir | `test_veritabani_geri_yukle.py` (`test_main_basarida_kayit_sayilarini_karsilastirir`) |

### 5.11 Öğrenci yönetimi

| FR | Gereksinim | Durum | Kodda nerede | Test kanıtı / not |
|---|---|---|---|---|
| FR-052 | Öğrenci listeleme | ⚠️ | `GET /api/ogrenciler-liste`, `GET /api/ogrenciler-yonetim`; `client/ogrenci_yonetim_ekrani.py` | `test_ogrenci_liste_tur_etiketi.py`, `test_ogrenci_liste_api_hatalari.py`; Doğrulama: öğrenci listeleme ve API hata testleri başarılı (16.11.2026). |
| FR-053 | Öğrenci ekleme | ⚠️ | `POST /api/ogrenci-ekle`; `client/ogrenci_dialog.py` | `test_ogrenci_ekleme_http_quality.py`, `test_ogrenci_ekleme_son_quality.py`; Doğrulama: öğrenci ekleme HTTP, kalite ve güvenlik testleri başarılı (16.11.2026). |
| FR-054 | Öğrenci aktiflik yönetimi | ⚠️ | `PATCH /api/ogrenciler/{ogrenci_id}/aktiflik` | `test_ogrenci_yonetimi_postgresql_quality.py` (PG) |
| FR-055 | Öğrenci silme ve erteleme | ⚠️ | `PATCH /api/ogrenciler/{ogrenci_id}/silme-ertele`, `DELETE /api/ogrenciler/{ogrenci_id}/on-yil-sil` | `test_ogrenci_yonetimi_postgresql_quality.py` (PG); saklama ve silme koşulları ayrıca doğrulanmalı |

### 5.12 Faaliyet ve puan yönetimi

| FR | Gereksinim | Durum | Kodda nerede | Test kanıtı / not |
|---|---|---|---|---|
| FR-056 | Faaliyet türü ve birimi yönetimi | ✅ | `/api/faaliyetler`, `/api/faaliyet-birimleri`; `client/faaliyet_turleri_dialog.py` | `test_faaliyet_turleri_quality.py`, `test_faaliyet_turleri_postgresql_quality.py` (PG), `test_faaliyet_birimi_yazma_izni.py`, `test_son_kontrol_duzeltmeleri_pg.py` (PG); Doğrulama: faaliyet türü/birimi, yazma yetkisi, büyük/küçük harf farkıyla aynı adın reddi ve puan değişikliğinin denetimde önceki/yeni değerle yazılması testleri başarılı (22.11.2026). |
| FR-057 | Faaliyet kaydı yönetimi | ✅ | `POST/GET /api/faaliyet-kayitlari`, `PUT/DELETE /api/faaliyet-kayitlari/{takip_id}`; `client/faaliyet_dialog.py` | `test_faaliyet_formu_kisayollari.py`, `test_faaliyet_okuma_uclari_yetki.py`, `test_modul_create_quality.py`, `test_modul_update_delete_quality.py`, `test_son_kontrol_duzeltmeleri_pg.py` (PG); Doğrulama: ekleme, listeleme, düzenleme ve silme; pasif türe geçişin reddi ve düzenlemede değişen alanların denetime yazılması testleri başarılı (22.11.2026). |
| FR-058 | Faaliyet puanları ve raporlama | ⚠️ | `GET /api/ogrenciler/{ogrenci_id}/puanlar`, `GET /api/puan-raporu`; `client/puan_raporu_ekrani.py`, `client/puan_rapor_excel.py` | `test_puan_raporu.py`; Doğrulama: puan raporu testleri başarılı (16.11.2026). |

### 5.13 Danışma masası yönetimi

| FR | Gereksinim | Durum | Kodda nerede | Test kanıtı / not |
|---|---|---|---|---|
| FR-059 | Görev başlatma | ✅ | `POST /api/danisma/oturum/baslat`; `client/danisma_masasi_ekrani.py` | `test_danisma_oturumu.py`; Doğrulama: danışma masası görev başlatma testleri başarılı. |
| FR-060 | Görev bitirme | ✅ | `PATCH /api/danisma/oturum/bitir`; `client/danisma_masasi_ekrani.py` | `test_danisma_oturumu.py`, `test_gui_danisma_gorev_quality.py`; Doğrulama: görev bitirme ve GUI kalite testleri başarılı. |
| FR-061 | Görev geçmişi | ✅ | `GET /api/danisma/oturum/aktif`, `GET /api/danisma/oturum/gecmis` | `test_danisma_oturumu.py`; Doğrulama: aktif oturum ve görev geçmişi testleri başarılı. |
| FR-062 | Görev onayı ve yönetimi | ✅ | `GET /api/danisma/yonetim/oturumlar`, `PATCH /api/danisma/yonetim/oturumlar/{oturum_id}/onayla`, `PATCH /api/danisma/yonetim/oturumlar/{oturum_id}/onay-geri-al`, yönetim oluşturma/düzenleme uçları | `test_danisma_oturumu.py`, `test_danisma_onay_bildirimleri.py`, `test_son_kontrol_duzeltmeleri_pg.py` (PG), `test_danisma_yonetimi_duzeltmeleri.py`; Doğrulama: görev yönetimi, onay ve bildirim; bir görevin en fazla 10 saat olabilmesi, uzun görevin işaretlenmesi ve düzenlemede önceki/yeni saatlerin denetime yazılması testleri başarılı (22.11.2026). |
| FR-063 | Danışma masası raporları | ✅ | `GET /api/danisma/raporlar`; `client/danisma_masasi_raporlari.py`, `client/danisma_rapor_excel.py` | `test_danisma_rapor_excel.py`; Doğrulama: danışma masası raporu ve Excel testleri başarılı. |

### 5.14 Parola yönetimi

| FR | Gereksinim | Durum | Kodda nerede | Test kanıtı / not |
|---|---|---|---|---|
| FR-064 | Parola sıfırlama talebi | ✅ | `POST /api/parola-sifirlama-talebi`; `client/parola_talebi_dialog.py` | `test_parola_sifirlama_talebi.py`, `test_parola_talebi_arayuz.py`; Doğrulama: parola sıfırlama talebi API ve arayüz testleri başarılı. |
| FR-065 | Yönetici tarafından parola sıfırlama | ✅ | `POST /api/kullanicilar/{kullanici_id}/parola-sifirla` | `test_parola_sifirlama_quality.py`, `test_parola_sifirlama_audit_ui.py`; Doğrulama: yönetici parola sıfırlama, audit ve arayüz testleri başarılı. |
| FR-066 | Parola taleplerinin yönetimi | ✅ | `GET /api/parola-sifirlama-talepleri`, `PATCH /api/parola-sifirlama-talepleri/{talep_id}/kapat` | `test_parola_sifirlama_talebi.py`, `test_parola_talepleri_hata_yonetimi.py`; Doğrulama: parola taleplerinin yönetimi ve hata işleme testleri başarılı. |

### 5.15 Onay bildirimleri

| FR | Gereksinim | Durum | Kodda nerede | Test kanıtı / not |
|---|---|---|---|---|
| FR-067 | Danışma masası onay bildirimleri | ✅ | `GET /api/danisma/yonetim/onay-bildirimleri`; `client/bildirim_paneli.py` | `test_danisma_onay_bildirimleri.py`, `test_dashboard_bildirim_tiklama.py`; Doğrulama: onay bildirimleri ve dashboard etkileşim testleri başarılı. |

## Gereksinim listesi dışında eklenen güvenlik ve kullanılabilirlik işleri

Bunlar `D02` içindeki FR maddeleri değildir; Proje Detayları belgesindeki güvenlik ve kullanılabilirlik hedeflerini
(parola, yetki, izlenebilirlik) destekler. Doğrulayan testler yanda.

| İş | Ne yapar | Kodda nerede | Test kanıtı |
|---|---|---|---|
| Parola sıfırlama talebi | Giriş ekranından yöneticiye bildirim; var olmayan kullanıcı adı (404) ve pasif hesap (403) açıkça bildirilir ve talep kaydedilmez, her kullanıcı için en fazla bir açık talep (varsa "zaten bekleyen talep" denir) | `POST /api/parola-sifirlama-talebi`, `parola_talebi_dialog.py`, `login_ekrani.py` | `test_parola_sifirlama_talebi.py`, `test_parola_talebi_arayuz.py` |
| Açık oturumda yetki yenileme | Yönetici bir rolün iznini ya da kullanıcının rolünü değiştirdiğinde, kullanıcı uygulamayı kapatıp açmadan menüsü 20 saniye içinde güncellenir; rol değiştiyse yeniden giriş istenir | `main_window.py` (`_yetkileri_denetle`), `GET /api/yetkilerim` | `test_yetki_yenileme.py` |
| İzin bağımlılık notu ve ön koşul uyarısı | Rol & İzin Yönetimi'nde, tek başına sekme açmayan bir izin (örn. Rol atama: yalnızca Kullanıcı & Personel sayfasındaki düğmeyi açar) matriste mavi "i" düğmesiyle işaretlenir; düğmeye tıklayınca "hangi sayfada çalışır, hangi izin de gerekir" açıklaması çıkar. Ön koşulu (sayfayı açan izni) olmayan bir role bu izin verilmek istenirse İzin Düzenle penceresi kaydı durdurur ve "önce şu izin gerekiyor" uyarısı verir. Notlar ve ön koşullar menü tanımından otomatik üretilir | `izin_bagimliliklari.py`, `rol_izin_diyaloglari.py`, `sayfalar_rol_izin.py` | `test_izin_bagimlilik_notu.py` |
| Yönetici talepler paneli ve bildirimleri | Bekleyen talepler Kullanıcı & Personel sayfasında, ana panelde ve zil simgesinde görünür | `k_personel_ekranlari.py`, `dashboard_ekrani.py`, `main_window.py` | `test_parola_talebi_arayuz.py`, `test_gui_parola_sifirlama_quality.py` |
| Geçici parola penceresi | Kopyalanabilir; pano 60 saniye sonra temizlenir; onayda kimlik doğrulama hatırlatması | `gecici_parola_dialog.py` | `test_gecici_parola_ve_sifre_kurallari.py`, `test_gui_parola_sifirlama_quality.py` |
| Yeni şifre kuralları | Canlı kural listesi ve güç göstergesi; düğme kurallar sağlanınca açılır | `parola_kurallari.py`, `sifre_degistir_ekrani.py` | `test_gecici_parola_ve_sifre_kurallari.py` |
| Yönetici parola kurtarma | Tek yönetici şifresini unutursa sunucu bilgisayarında kurtarma aracı | `scripts/admin_parola_kurtar.py`, `scripts/windows/admin_parola_kurtar.bat` | `test_admin_parola_kurtar.py` (gerçek PostgreSQL'de elle doğrulandı) |
| Ek yönetici oluşturma | Uygulamadan yönetici açılamadığı için ikinci yönetici sunucuda açılır | `scripts/ilk_admin_olustur.py --ek-yonetici` | `test_ilk_admin_olustur.py` (gerçek PostgreSQL'de elle doğrulandı) |
| Bozuk girdi koruması | Taşan sayı, NUL karakteri, çok büyük gövde, hatalı saat dilimi, sınırsız metin gibi girdiler "500 sunucu hatası" yerine anlamlı 409/422/413 ile reddedilir; tekrar eden kayıt 409 olur; hata ayrıntısı istemciye sızmaz; JWT_SECRET en az 32 karakter olmalıdır | `girdi_korumasi.py`, `modeller.py`, `guvenlik.py`, `sunucu.py` | `test_girdi_korumasi.py`, `test_girdi_fuzz_pg_quality.py` (gerçek PostgreSQL, tüm yazma uçlarına bozuk girdi) |
| Yabancı anahtar indeksleri | 24 yabancı anahtar sütununa indeks eklendi; bağlı kayıt aramaları ve silme denetimleri tablo büyüdükçe yavaşlamaz. Yeni bir yabancı anahtar indekssiz eklenirse CI kırmızı olur | `database/migrations/versions/a7d3e9c1b254_yabanci_anahtar_indeksleri.py` | `test_yabanci_anahtar_indeks_pg_quality.py` (gerçek PostgreSQL), `test_yabanci_anahtar_indeks_migrasyonu.py` |
| Kısıtlı veritabanı kullanıcısı | Sunucu, tablo oluşturamayan/silemeyen ve denetim kaydını değiştiremeyen ayrı bir veritabanı kullanıcısıyla çalıştırılabilir; araç yetkileri kendi kendini doğrular; şema güncellemesi ve geri yükleme tam yetkili kimlikle (DB_MIGRATION_*) sürer | `scripts/uygulama_kullanicisi_olustur.py`, `server/sema_kimligi.py`, `database/migrations/env.py`, kılavuz bölüm 6A | `test_uygulama_kullanicisi_betigi.py`, `test_sema_kimligi.py`, `test_kisitli_kullanici_pg_quality.py` (gerçek PostgreSQL) |
| Veritabanı şeması kontrolü ve anlaşılır uyarı | Kod, veritabanında olmayan tablo/sütun beklerse kullanıcı “beklenmeyen hata” yerine ne yapılacağını söyleyen bir uyarı görür (503; teknik ayrıntı yalnızca günlüğe); `sema_dogrula.py` canlı veritabanını migration'lardan üretilen şemayla karşılaştırır ve atlanmış migration'ı (sürüm güncel görünürken eksik sütun) adıyla bulur | `server/girdi_korumasi.py`, `client/api_yoneticisi.py`, `scripts/sema_dogrula.py`, kılavuz bölüm 11 | `test_sema_uyumsuzlugu_mesaji.py`, `test_sema_dogrula.py`, `test_sema_dogrulama_pg_quality.py` (gerçek PostgreSQL) |
| Test güvenilirliği | Testlerde "bugün" modül yüklenirken sabitlenemez; gece yarısını geçen CI'da sebepsiz kırılma önlenir | — | `test_zaman_bagimsizligi.py` |

Proje Detayları belgesindeki güvenlik testi SEC-005 (çok sayıda hatalı parola → geçici kilitleme) `giris_yap` içindeki
hatalı giriş sayacı ve kilit süresiyle karşılanır (`test_sec_t07_t08_auth.py`, `test_kullanici_pasiflestirme.py`).
