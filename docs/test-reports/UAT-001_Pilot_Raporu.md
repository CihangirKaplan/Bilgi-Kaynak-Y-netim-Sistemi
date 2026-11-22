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
| P5 | Cihaz rezervasyonu yapar | | |
| P6 | Kendi randevularını ve günlük akışını görür | | |

### İdari personel (memur)

| # | Senaryo | Sonuç | Kullanıcının yorumu |
|---|---|---|---|
| M1 | Giriş yapar, ilk girişte şifresini değiştirir | | |
| M2 | Cihaz envanterinde bir cihazı düzenler | | |
| M3 | Bakım ve kalibrasyon kaydı ekler | | |
| M4 | Arıza bildirir ve çözüldü olarak kapatır | | |
| M5 | Oda etkinliği oluşturur | | |
| M6 | Faaliyet kaydı ekler / düzenler | | |

### Müdür

| # | Senaryo | Sonuç | Kullanıcının yorumu |
|---|---|---|---|
| D1 | Giriş yapar, ana paneli inceler | | |
| D2 | Yönetim raporlarını farklı tarih aralıklarıyla açar, PDF/Excel alır | | |
| D3 | Danışma masası görevlerini inceler ve onaylar | | |
| D4 | Bir kullanıcı oluşturur, rolünü değiştirir, pasifleştirir | | |
| D5 | Yetkisi olmayan bir işlemin engellendiğini görür (ör. yönetici hesabını düzenleme) | | |

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
