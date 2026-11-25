# UAT-001 — Kullanıcı Kabul (Pilot) Raporu (Hafta 8, Gün 3–4)

UAT (kullanıcı kabul testi): sistemi yazanlar değil, **gerçekten kullanacak kişiler** kendi günlük işleriyle dener.
Yol haritasına göre pilotta bir psikolog, bir idari personel (memur) ve bir müdür sistemi kullanır. Bulunan her sorun GitHub'da issue
olarak açılır ve önemine göre sınıflanır (P0–P4, yol haritası 25. bölüm). Pilot sırasında yalnızca blocker, hata, güvenlik ve kritik
kullanım sorunları düzeltilir; yeni özellik eklenmez.

| Alan | Bilgi |
|---|---|
| Sürüm | commit ________ |
| Pilot tarihleri | ________ – ________ |
| Gözlemci | ________ |

## Katılımcılar

| Rol | Ad Soyad | Kullanıcı adı | Bilgisayar |
|---|---|---|---|
| Psikolog | | | |
| İdari personel (memur) | | | |
| Müdür | | | |

## Senaryolar

Her katılımcı kendi senaryolarını gerçek işleriyle yapar. "Sonuç": Başarılı / Zorlandı / Yapamadı. Senaryolar varsayılan rol izinlerine göre yazıldı;
merkezde bir rolün izni farklı ayarlandıysa o rolün yapamayacağı senaryo çıkarılır ve izni olan rolün listesine taşınır.

### Psikolog

| # | Senaryo | Sonuç | Kullanıcının yorumu |
|---|---|---|---|
| P1 | Giriş yapar, ilk girişte şifresini değiştirir | | |
| P2 | Yeni danışan kodu oluşturur | | |
| P3 | Randevu oluşturur, saatini değiştirir, birini iptal eder | | |
| P4 | Geçmiş randevunun sonucunu (tamamlandı / gelmedi) girer | | |
| P5 | Cihaz Uygunluğu sayfasında bir cihazın hangi saatlerde müsait olduğuna bakar | | |
| P6 | Ana panelde bugünkü randevuları, cihaz rezervasyonlarını ve oda etkinliklerini; Randevu Yönetimi listesinde kendi randevularını görür | | |

### İdari personel (memur)

| # | Senaryo | Sonuç | Kullanıcının yorumu |
|---|---|---|---|
| M1 | Giriş yapar, ilk girişte şifresini değiştirir | | |
| M2 | Cihaz envanterinde bir cihazı düzenler | | |
| M3 | Bakım ve kalibrasyon kaydı ekler | | |
| M4 | Arıza bildirir ve çözüldü olarak kapatır | | |
| M5 | Oda etkinliği oluşturur | | |
| M6 | Faaliyet kaydı ekler / düzenler | | |
| M7 | Danışma masasında bekleyen bir görevi onaylar | | |

### Müdür

| # | Senaryo | Sonuç | Kullanıcının yorumu |
|---|---|---|---|
| D1 | Giriş yapar, ana paneli inceler | | |
| D2 | Yönetim raporlarını farklı tarih aralıklarıyla açar, PDF/Excel alır | | |
| D3 | Danışma Masası Raporları'nda onay bekleyen görevleri inceler (onayı Memur verir; Müdür onaylayamaz) | | |
| D4 | Bir kullanıcı oluşturur, rolünü değiştirir, pasifleştirir | | |
| D5 | Yetkisi olmayan bir işlemin engellendiğini görür (ör. yönetici hesabını düzenleme) | | |

## Pilottan önce kontrol (hazırlık)

Pilot bir gün kaybetmeden başlasın diye aşağıdakiler **pilottan önce**, canlı sunucuda ve sistem sorumlusuyla yapılır.

**1. Senaryo – izin eşlemesi.** Senaryolar varsayılan rol izinlerine göre yazıldı. Her katılımcının hesabında şu izinlerin açık olduğunu **Rol & İzin Yönetimi**
ekranından doğrulayın (izin farklı ayarlanmışsa o senaryoyu çıkarın ya da izni olan role taşıyın):

| Senaryo | Gerekli izin(ler) | Varsayılan olarak verilen roller |
|---|---|---|
| P2, P3 | Randevu oluşturma, düzenleme, iptal etme (`RANDEVU_OLUSTUR`, `RANDEVU_DUZENLE`, `RANDEVU_IPTAL`) | Psikolog |
| P4 | `RANDEVU_DUZENLE` | Psikolog |
| P5 | `CIHAZ_UYGUNLUK_GORUNTULE` | Psikolog, Memur, Müdür |
| P6 | `TAKVIM_GORUNTULE`, `CIHAZ_UYGUNLUK_GORUNTULE` (etkinlik listesi izin istemez) | Psikolog, Memur, Müdür |
| M2 | `CIHAZ_ENVANTER_YONET` | Memur, Müdür |
| M3 | `BAKIM_KAYITLARI_YONET`, `KALIBRASYON_KAYITLARI_YONET` | Memur, Müdür |
| M4 | `ARIZA_KAYITLARI_YONET` | Memur, Müdür |
| M5 | `ODA_ETKINLIK_YONET` | Memur, Müdür |
| M6 | `FAALIYET_KAYITLARI_DUZENLE` | Memur, Müdür |
| M7 | `DANISMA_OTURUMU_YONETIM` | Memur |
| D2 | `YONETIM_RAPORLARI_GORUNTULE` | Müdür |
| D3 | `DANISMA_OTURUMU_GORUNTULE` (raporlar) | Memur, Müdür |
| D4 | `KULLANICI_OLUSTUR`, `ROL_ATAMA_DEGISTIRME`, `KULLANICI_PASIFLESTIR` | Müdür |

(Psikolog rolünde cihaz rezervasyonu izni varsayılan olarak **yoktur**; rezervasyonu Memur ve Proje Asistanı yapar. Danışma masası görev onayı Müdür'de değil
Memur'dadır.)

**2. Hesaplar.** Her katılımcıya gerçek adıyla bir hesap açın (Psikolog hesabına en az bir görüşme odası atayın); her hesapla bir kez girip geçici
parolayı değiştirin (P1, M1 senaryoları bunu katılımcıyla birlikte, ilk girişte yaptırmak isterseniz hesabı pilot günü açın ve geçici parolayı yüz yüze verin).

**3. Test verisi** (gerçek kişisel veri girmeyin; test danışan kodu kullanın):
- **P4 için:** Başlangıcı *geçmiş* olan planlı bir randevu gerekir. Sistem geçmişe randevu açtırmaz; bu yüzden pilot günü sabah saatli (09:00–11:00) bir
  randevuyu **bir gün önceden** psikolog hesabıyla oluşturun, pilot günü saati geçince sonucu (Tamamlandı / Gelmedi) girilir.
- **M2–M4 için:** Düzenlenip arıza bildirilebilecek bir test cihazı (Cihaz Envanteri'nde).
- **M7 için:** Onay bekleyen bir danışma masası görevi: bir Danışma Öğrencisi test hesabıyla bir görev başlatıp bitirin (onay bekler).
- **D4 için:** Müdürün oluşturup pasifleştireceği bir test kullanıcısı için serbest bir kullanıcı adı.

**4. Gözlem ve kayıt.** Gözlemci (sistemi yazan biri olmamalı) her senaryoda katılımcının takıldığı yeri not eder, **yardım etmeden** bekler; senaryo sonucu ve
katılımcının cümlesi tabloya yazılır. Bulunan her sorun GitHub'da issue olarak açılır; `P0`–`P4` etiketlerinin repoda var olduğunu kontrol edin.

**5. Başlamadan hemen önce:** canlı veritabanının elle yedeğini alın (`scripts/backup/veritabani_yedekle.py`), açık P0/P1 olmadığını doğrulayın, pilot sırasında
yalnızca blocker/hata/güvenlik/kritik kullanım sorunları düzeltilip yeni özellik eklenmeyeceğini katılımcılara bildirin.

## Bulunan sorunlar

| # | Kim buldu | Açıklama | Önem (P0–P4) | Issue | Durum |
|---|---|---|---|---|---|
| 1 | | | | # | Açık / Düzeltildi |

Önem: P0 kritik (veri kaybı, giriş atlatma, yetkisiz müdür yetkisi, geri yüklenemeyen yedek) · P1 yüksek (temel işlev çalışmıyor,
yetki sorunu, yanlış kullanıcı veri görüyor) · P2 orta (iş akışını etkiliyor, geçici çözümü var) · P3 düşük · P4 kozmetik.

## Sonuç ve onay

- Açık P0: ___  Açık P1: ___
- Kullanıcıların genel görüşü: ________

| Rol | Ad Soyad | Kabul ediyorum (✓) | Tarih | İmza |
|---|---|---|---|---|
| Psikolog | | | | |
| İdari personel | | | | |
| Müdür | | | | |

UAT sonucu: PASS ☐ (açık P0 = 0 ve P1 = 0, üç katılımcı da kabul etti)  FAIL ☐
