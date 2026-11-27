# TKYS v1.0.0 — Canlı Doğrulama Günü Kontrol Listesi

**Amaç:** Yayından **önce**, sistemin son hâlini gerçek sunucuda (gerçek Windows, gerçek PostgreSQL, gerçek ağ) bir kez baştan sona denemek. Geliştirme ve CI testleri
tamamdır; bu liste yalnızca **canlı ortamda görülebilen** riskleri kapatır: veritabanı güncellemesi, yetkiler, yedekten geri dönüş, güvenlik denemeleri, yeni özelliklerin elle kontrolü.

Bu liste **yayın değildir**: `main` dalına geçilmez, `v1.0.0` etiketi atılmaz. Yayının adımları `docs/release/Yayin_Gunu_Rehberi_v1.0.0.md` dosyasındadır;
bu gün orada yazan sunucu güncelleme ve smoke test adımlarının **provasıdır**. Burada çıkan sorunlar yayın gününden önce düzeltilir.

| Alan | Bilgi |
|---|---|
| Doğrulama tarihi / saati | ________ (yaklaşık 3 saat ayırın) |
| Doğrulanan commit | ________ (develop ucu; sunucuda `git log -1 --format=%h`) |
| Sunucu işlemlerini yapan | ________ |
| İstemci denemelerini yapan | ________ |
| Kanıtları toplayan | ________ (hepsi `docs/test-reports/kanit/` altına) |
| Başlangıçtaki migration | ________ (sunucuda `python -m alembic current`) |
| Başlamadan elle alınan yedek | ________ |

**Kurallar**

- Her adımın yanındaki kutuyu işaretleyin ve **kanıtı** (komut çıktısı ya da ekran görüntüsü) kaydedin. Parola ve oturum anahtarı kanıta girmez.
- Bir adım başarısız olursa **durun**, sonraki bölüme geçmeyin: sorunu bölüm 8'deki gibi kaydedin.
- Gerçek kullanıcı kayıtlarına dokunmayın. Deneme için ayrı **test hesapları** ve **test kayıtları** kullanılır; iş bitince bölüm 7'de temizlenir.
- Sunucu çalışırken kullanıcı varsa önceden haber verin (bölüm 1'de sunucu kısa süre kapanır).

## 0. Hazırlık (bir gün önce)

- [ ] GitHub Actions "TKYS QA Tests", develop son koşusu **yeşil**; açık P0/P1 issue yok. Doğrulanacak commit'i not edin (üstteki tablo).
- [ ] Bu gün için develop'a **yeni özellik girmez** (yalnızca hata düzeltmesi). Arkadaşların açık PR'ları ya merge edilir ya da doğrulama sonrasına bırakılır.
- [ ] Test hesapları hazır (Kullanıcı & Personel ekranından, her biriyle bir kez girip geçici parolayı değiştirin). Ayrıntı: `docs/test-reports/SEC-001_Canli_Deneme_Rehberi.md` → 1. Hazırlık.

  | Hesap | Rol | Kullanım |
  |---|---|---|
  | `sec_psikolog_a`, `sec_psikolog_b` | Psikolog | randevu denemeleri, yetkisizlik |
  | `sec_memur` | Memur | cihaz, bakım, danışma masası onayı |
  | `sec_asistan` | Proje Asistanı | rezervasyon, faaliyet |
  | `sec_ogrenci` | Danışma Öğrencisi | danışma masası görevi, "Bekleyen işlerim" (hesap bir **öğrenci kaydına bağlı** olmalı: Öğrenciler ekranında "Bağlı hesap") |
  | `sec_mudur` | Müdür | raporlar, kullanıcı yönetimi |
  | `sec_kilit`, `sec_pasif` | Memur / Asistan | hesap kilidi ve pasifleştirme denemeleri |
  | Yönetici hesabınız | Yönetici | yönetim işlemleri |

- [ ] İstemci bilgisayarında **güncel** uygulama kurulu ve `TKYS_API_URL` (HTTPS ise `TKYS_CA_BUNDLE`) doğru; ikinci bir bilgisayar da hazır (iki bilgisayarlı denemeler için).
- [ ] Ekip kimin hangi bölümü yapacağını belirledi (üstteki tablo).

## 1. Sunucuyu güncelleme provası (sunucu bilgisayarında)

Önce geri dönüş bilgilerini yukarıdaki tabloya yazın: `git log -1 --format=%h` ve `python -m alembic current`.

- [ ] Kullanıcılara haber verildi; kimsenin işlem yapmadığından emin olundu.
- [ ] **Elle yedek** alındı ve dosya adı tabloya yazıldı (sunucu çalışırken):

      python scripts/backup/veritabani_yedekle.py

- [ ] Sunucu durduruldu: `schtasks /End /TN TKYS_Sunucu`
- [ ] Kod güncellendi ve bağımlılıklar kuruldu:

      git fetch origin
      git checkout develop
      git pull origin develop
      python -m pip install -r requirements.txt

- [ ] Veritabanı güncellendi ve doğrulandı (**`ŞEMA UYUMLU` görmeden sunucuyu başlatmayın**):

      python -m alembic upgrade head
      python scripts/sema_dogrula.py

  `python -m alembic current` ile `python -m alembic heads` çıktıları **aynı** olmalı (tek head). Canlı sunucu en son 24.11.2026'da `f4c8a2e6b917` şemasındaydı
  (SMOKE-001). O sürümden bu yana eklenenler, sırayla (sunucunuzun `alembic current` çıktısı farklıysa yalnızca o noktadan sonrakiler çalışır):

  | Migration | Ne yapar |
  |---|---|
  | `a7c3e5b9d014` | Proje Asistanı'na Oda Etkinlikleri görüntüleme ve yönetme izinleri |
  | `c9d2e4f6a801` | Duyurular tablosu ve `DUYURU_YONET` izni |
  | `d4a8b6c2e913` | Denetim kayıtlarında "kullanıcının son girişi" sorgusu için kısmi indeks (Yetki Raporu hızlanır) |
  | `b3f7d9a1c452` | Öğrenci saklama süresi: pasife alındıktan sonra 2 yıl |
  | `e5b9c1d7f302` | Duyuru yayınlama izni Psikolog ve Proje Asistanı için de |
  | `f6c2d8a4b715` | Duyuru "Okudum" işaretleri (`duyuru_okundu` tablosu) |

  Her biri sonunda hatasız bitmeli. Hata çıkarsa **durun**, çıktıyı kaydedin ve bölüm 8'e bakın; veritabanını yedekten geri yükleyin (bölüm 3).
- [ ] Görevler yeniden kuruldu (yönetici PowerShell): `python scripts/windows/sunucu_kurulum.py` ve `python scripts/windows/kurulum.py`
- [ ] Sunucu başlatıldı: `schtasks /Run /TN TKYS_Sunucu`; `/api/saglik` açılıyor; `logs\sunucu.log` içinde hata yok.
- [ ] İstemciden **Yönetici → Sistem Durumu**: sürüm, şema ve veritabanı **yeşil**; **Hakkında** penceresinde istemci ve sunucu sürümü aynı.
- [ ] Veritabanı bağlantı havuzu: sunucu çalışırken en çok birkaç bağlantı açık (varsayılan havuz 10, `TKYS_DB_HAVUZ_BOYUTU`; 0 = kapalı):

      psql -h 127.0.0.1 -U <DB_USER> -d <DB_NAME> -c "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database();"

  Beklenen: kullanıcılar uygulamayı kullanırken bile bu sayı **havuz boyutunu ve birkaçını** aşmaz (yüzlerce değil).

## 2. Elle fonksiyon kontrolü (istemciden, rol rol)

SMOKE-001 (`docs/test-reports/SMOKE-001_Canli_Ortam_Smoke_Test.md`) içinde boş kalan **H4, S2, S5–S10** satırlarını bu bölümde tamamlayın; sonuçları orada da işleyin.

**2.1 Giriş ve menüler (S2, S10)**

- [ ] Yönetici, müdür, memur, psikolog, danışma öğrencisi ve proje asistanı hesaplarıyla giriş: rol adı doğru, **yalnızca kendi menüleri** görünüyor (psikologda yönetim menüleri yok).
- [ ] Hatalı parola: "Kullanıcı adı veya parola hatalı".

**2.2 Randevu (S5, S6)**

- [ ] `sec_psikolog_a`: test danışan koduyla randevu oluştur → saatini değiştir → iptal et; her adım listede doğru görünüyor.
- [ ] Aynı psikolog/oda/saate ikinci randevu **reddediliyor**, mesaj anlaşılır.
- [ ] **Danışanlar** sayfası hızlı açılıyor; her danışanın randevu sayısı görünüyor; bir danışana tıklayınca randevuları geliyor.

**2.3 Cihaz, bakım, arıza (S7, S8)**

- [ ] Cihaz rezervasyonu oluştur ve iptal et (aynı cihaz/saat için çakışma reddediliyor).
- [ ] `sec_memur`: bakım kaydı ekle → listede görünüyor; arıza bildir ve çözüldü yap.
- [ ] **Oda Yönetimi → odayı sil**: **test için açılmış, hiç kullanılmamış** bir odada uyarı çıkıyor ve silinince listeden kalkıyor (denetim kaydına yazılıyor). Randevusu/rezervasyonu/etkinliği olan bir odanın **silinemediği** ("... kaydı var", pasife alma önerilir) ve bir psikologun tek aktif odasının silinemediği doğrulanıyor; **gerçek odaları silmeyin**.

**2.4 Ana panel ve bildirimler**

- [ ] **Benim Günüm → Bekleyen işlerim:** `sec_ogrenci` ile danışma masası görevi başlat → görevin sürdüğü satırı görünüyor; `sec_memur`/yöneticide onay bekleyen görev ve açık arıza satırı görünüyor; bekleyen yoksa satır yok.
- [ ] **Duyurular:** bir test duyurusu yayınla (yönetici, psikolog ve proje asistanı da yayınlayabilir; danışma öğrencisi yayınlayamaz) → başka rolle **Okudum**de → o kullanıcıda gizleniyor, diğerinde duruyor; **Tekrar göster** çalışıyor; duyuruyu kaldırınca herkesten gidiyor.
- [ ] **🔔 Zil:** günlük bilgi ve okunmamış duyurular her rolde; sayı, Okudum/okundu ile azalıyor. Memur/yöneticide süresi dolan öğrenci kaydı, sonucu girilmemiş randevu ve yedek uyarısı uygun olduğunda görünüyor.

**2.5 Raporlar ve dışa aktarma**

- [ ] **Raporlar** (Randevu, Cihaz, Puan, Danışma Masası, Oda Kullanım ve diğerleri) dönem değiştirince doğru açılıyor; sayılar ekrandakiyle tutarlı.
- [ ] **⬇ Dışa Aktar** (en az: **Randevu Raporları**, **Cihaz Envanteri** ve **Denetim Kayıtları** sayfalarında): önce *Excel mi PDF mi* soruluyor.
  - [ ] **Excel** seçilince `.xlsx` kaydediliyor ve Excel'de açılıyor (Özet + tablo sayfaları).
  - [ ] **PDF** seçilince `.pdf` kaydediliyor: A4 yatay, Türkçe karakterler (ğ ü ş ı ö ç İ) doğru, tablo başlığı ve "Sayfa x / y" var, hiçbir sütun kelime ortasından bölünmüyor.
  - [ ] Yönetici → **Denetim Kayıtları**: liste aktarımları *Dışa Aktarım (Excel/PDF)* olarak görünüyor; PDF'te ayrıntıda "Biçim: PDF" yazıyor.
- [ ] **Yetki Raporu** ve **Randevu Raporu** hızlı açılıyor (saniyeler içinde), hata vermiyor.

**2.6 Denetim (S9)**

- [ ] Yönetici → **Denetim Kayıtları**: 2.1–2.5'teki işlemler (giriş, oluşturma, iptal, aktarım) görünüyor; silme/güncellemelerde önceki değerler kayıtlı.

## 3. Yedek ve geri yükleme kanıtı (GO/NO-GO 9 ve 10)

- [ ] **Yedek (S11):** `schtasks /Run /TN TKYS_Otomatik_Yedekleme` → `logs\yedekleme.log` son satır `çıkış kodu: 0` ve `backups` klasöründe yeni dosya.
- [ ] **Son yedek kartı (S12):** Yönetici → Sistem Durumu → Son Yedek, az önceki yedeğin tarihini ve yeşili gösteriyor.
- [ ] **Geri yükleme:** yedek, mevcut veritabanının **üzerine yazmayan** araçla YENİ bir veritabanına geri yüklenir ve kayıt sayıları kaynakla karşılaştırılır:

      python scripts/restore/veritabani_geri_yukle.py --hedef tkys_dogrulama_test

  Beklenen: araç "Geri yüklendi" der ve tablo tablo kayıt sayısını (geri yüklenen / kaynak) yazdırır; sayılar **aynıdır** ya da farkı yalnızca yedek alındıktan sonra girilen kayıtlar açıklar. Çıktıyı kanıt olarak kaydedin. (`DB_MIGRATION_*` bilgisi gerekir; araç deneme veritabanını silmez.)
- [ ] Geri yüklenen deneme veritabanı silindi (bölüm 7); canlı `.env` içindeki `DB_NAME` değişmedi.

## 4. Güvenlik denemeleri (SEC-001 canlı satırları; GO/NO-GO 5–7 ve 11)

Adım adım yönerge: **`docs/test-reports/SEC-001_Canli_Deneme_Rehberi.md`**. Burada yalnızca sırası ve kanıt yeri özetlenir.

- [ ] **API denemeleri (istemciden):** önce veri değiştirmeyenler (`--adimlar T01,T02,T08`), sonra `--onay` ile T03, T07, T08. Hepsi **PASS**, `FAIL` yok; `ATLANDI` varsa nedeni giderilip tekrarlandı. Kanıt: `sec001_canli_kanit_<tarih>.txt`.
- [ ] **Sunucuda elle:** SEC-T10 (`.env` gizli ve anahtar uzun), SEC-T11 (`pip-audit` temiz), SEC-T12 (denetim kaydı UPDATE/DELETE/TRUNCATE engelli, kayıt sayısı değişmedi), SEC-T13 (yedek klasörü yalnızca yönetici/sistem, ağda paylaşılmıyor).
- [ ] **İstemcide elle:** SEC-T08 son adımı (pasife alınan kullanıcının açık oturumu giriş ekranına dönüyor).
- [ ] `SEC-001_Guvenlik_Test_Raporu.md` içindeki `Canlı: ⏳` ifadeleri sonuç ve tarihle değiştirildi (rehberin 5. bölümü).

## 5. Kurulum ve istemci kontrolü (GO/NO-GO 13)

- [ ] SMOKE-001 H1–H5: sunucu görevi süre sınırsız (`PT0S`), yeniden başlatmada **oturum açmadan** kendiliğinden açılıyor, şema güncel, test hesabı kalmadı (`qa_`, `tarama_`, `test` ile başlayanlar yok), HTTPS sertifikalı erişim çalışıyor.
- [ ] En az **iki farklı bilgisayarda** istemci (`.exe` ve `TKYS_API_URL`) açılıyor, giriş yapılıyor.
- [ ] İki bilgisayardan aynı anda iş yapılırken (biri randevu ekler, diğeri listeyi yeniler) sistem takılmıyor ve veri tutarlı.

## 6. Kısa performans gözlemi

- [ ] 3–5 kişi aynı anda ana panel, Danışanlar ve bir rapor sayfasını açıp 5 dakika kullanır: sayfa açılışları **birkaç saniyeyi aşmıyor**, istemcide zaman aşımı hatası yok, `logs\sunucu.log` içinde 500 hatası yok.
- [ ] Bölüm 1'deki bağlantı sayısı kontrolü bu kullanım sırasında tekrarlandı; sayı sınırlı kalıyor.

## 7. Temizlik

- [ ] Test hesapları **pasife alındı** (`sec_*`); test randevuları, rezervasyonlar, duyurular, odalar iptal edildi/silindi.
- [ ] Geri yükleme için açılan deneme veritabanı silindi: `psql -U <yönetici> -c "DROP DATABASE tkys_dogrulama_test;"` (yalnızca bu deneme veritabanı, canlı veritabanı değil!).
- [ ] Kanıt dosyaları `docs/test-reports/kanit/` altına konuldu; içinde parola/token yok. Dışa aktarma denemelerinde oluşan örnek dosyalar paylaşılan bir yerde bırakılmadı.
- [ ] Sunucuda son durum: `git log -1 --format=%h`, `python -m alembic current` (head), görevler çalışıyor, bir sonraki otomatik yedek bekleniyor.

## 8. Bulgu çıkarsa

- Her sorunu GitHub'da **issue** olarak açın; etiket: **P0** (giriş yok/veri bozuluyor/güvenlik), **P1** (önemli iş yapılamıyor), P2–P4 (diğer). Başlıkta adım numarasını yazın (örn. "Canlı doğrulama 2.4: PDF'te ...").
- **P0/P1** sorunlar yayından önce düzeltilir; düzeltme develop'a girer, CI yeşil olunca **ilgili bölüm yeniden** denenir (gerekirse sunucu yeniden güncellenir).
- Veritabanı güncellemesi hata verdiyse sunucuyu açmayın; bölüm 3'teki yedeği yeni veritabanına geri yükleyin (üzerine yazılmaz), kayıt sayılarını karşılaştırın, sorun giderilene kadar eski kodla devam edin. `alembic downgrade` ile geri dönmeyin.

## 9. Sonuç ve GO/NO-GO eşlemesi

Bu günün çıktısı, `docs/test-reports/GO-NO-GO_Kontrol_Listesi.md` içindeki maddelerin kanıtlarıdır:

| GO/NO-GO maddesi | Bu listedeki kanıt | Tamam |
|---|---|---|
| 1 Build PASS, 2 Unit/Integration PASS | Bölüm 0: develop son CI koşusu yeşil | ☐ |
| 3 P0 = 0, 4 P1 = 0 | Bölüm 8: açık P0/P1 issue yok | ☐ |
| 5 Authentication, 6 Authorization, 7 Security | Bölüm 4 (SEC-001 canlı satırları) | ☐ |
| 8 Concurrency | SEC-T15 testleri (CI'da PASS) + bölüm 5'teki iki bilgisayarlı deneme | ☐ |
| 9 Backup, 10 Restore | Bölüm 3 (yedek günlüğü + geri yükleme çıktısı) | ☐ |
| 11 Audit | Bölüm 2.6 ve SEC-T12 | ☐ |
| 13 Installation | Bölüm 1 (sunucu güncelleme) ve bölüm 5 | ☐ |
| 12 UAT | **Bu günün kapsamında değil** (pilot, `UAT-001_Pilot_Raporu.md`) | — |
| 14 Documentation | Kılavuzların güncelliği; bu günde çıkan eksikler issue olarak kaydedilir | ☐ |

**Karar:** Canlı doğrulama tamam ☐  Tamam değil ☐ — eksik maddeler ve sorumlusu: ________

Tamamsa: UAT pilotu ve GO/NO-GO toplantısı sırada; GO çıkarsa `docs/release/Yayin_Gunu_Rehberi_v1.0.0.md` izlenir.
