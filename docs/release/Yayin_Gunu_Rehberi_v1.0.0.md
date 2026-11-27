# TKYS v1.0.0 — Yayın Günü Rehberi

Bu rehber, **GO/NO-GO toplantısında GO kararı çıktıktan sonra** (bkz. `docs/test-reports/GO-NO-GO_Kontrol_Listesi.md`) sırayla izlenir.
NO-GO ise hiçbir adım uygulanmaz. Her adımın yanındaki kutuyu işaretleyin; bir adım başarısız olursa **durun**, sonraki adıma geçmeyin.

Kısa özet: hazırlık PR'ı → develop'ı main'e birleştir → `v1.0.0` etiketi → canlı sunucuyu güncelle → istemcileri güncelle → smoke test.

| Alan | Bilgi |
|---|---|
| Yayın tarihi / saati | ________ |
| Yayını yapan | ________ |
| Yayından önceki sunucu commit'i (geri dönüş için) | ________ (sunucuda `git log -1 --format=%h`) |
| Yayından önceki migration | ________ (sunucuda `python -m alembic current`) |
| Elle alınan yedek dosyası | ________ |

## 0. Yayından önce (T-1 gün)

- [ ] **Dondurma:** Bu saatten sonra develop'a yalnızca yayını engelleyen hata düzeltmeleri girer. Açık PR'lar (arkadaşların PR'ları dahil) ya merge edilir ya da yayın sonrasına bırakılır.
- [ ] GitHub Actions "TKYS QA Tests", develop son koşusu **yeşil** (Actions sayfası → develop).
- [ ] GitHub'da açık **P0 / P1** issue yok.
- [ ] **Canlı doğrulama günü** yapıldı ve tamamlandı: [`Canli_Dogrulama_Gunu_Kontrol_Listesi.md`](Canli_Dogrulama_Gunu_Kontrol_Listesi.md) (sunucu güncelleme provası, elle kontroller, yedek/geri yükleme, SEC-001 canlı denemeleri). Orada çıkan P0/P1 sorunlar giderildi.
- [ ] GO/NO-GO listesindeki 14 madde kanıtlarıyla dolduruldu, karar **GO**.
- [ ] Yerelde (proje klasöründe, sanal ortam açık) otomatik kontrol çalıştırıldı ve **HATA** satırı yok:

      git checkout develop; git pull origin develop
      python scripts/yayin_oncesi_kontrol.py

  Yayın tarihi, GO/NO-GO ve belge **UYARI** satırları bu aşamada normaldir; 1. adımda giderilir.

## 1. Hazırlık PR'ı (develop'a)

Amaç: yayın tarihini, commit'i ve kurulum belgelerindeki dal adını (develop → main) yayınla birlikte `main`'e taşımak.

- [ ] Yeni dal: `git checkout develop; git pull origin develop; git checkout -b release/v1.0.0-hazirlik`
- [ ] Kurulum belgelerinde git komutlarını `main`'e çevirin (yalnızca komutları değiştirir; açıklama metinlerine dokunmaz):

      python scripts/yayin_oncesi_kontrol.py --belgeleri-main-yap

- [ ] Tarihleri doldurun:
  - `CHANGELOG.md` → `## [1.0.0] — Yayın tarihi: GG.AA.2026`
  - `RELEASE_NOTES.md` → tablodaki `Yayın tarihi` satırı
  - `docs/test-reports/GO-NO-GO_Kontrol_Listesi.md` → commit, toplantı tarihi, katılanlar; maddeler ☑; karar **GO ☑**
- [ ] Yayın anı kontrolü **tamamen yeşil** olmalı (UYARI da kalmamalı):

      python scripts/yayin_oncesi_kontrol.py --go

- [ ] Commit, push, PR (hedef: `develop`), CI **yeşil** olunca merge. Merge sonrası develop CI'ı da yeşil olana kadar bekleyin.

## 2. develop → main birleştirme

- [ ] GitHub → **Pull requests → New pull request** → base: `main`, compare: `develop`. Başlık: `Release v1.0.0`. Açıklamaya `RELEASE_NOTES.md` özetini yazın.
- [ ] CI yeşil ise **Merge pull request** açılır menüsünden **"Create a merge commit"** seçin (Squash ya da Rebase **seçmeyin**: ~1000 commit'lik geçmiş korunmalı).
- [ ] Merge sonrası `main` üzerindeki CI koşusu **yeşil** (Actions → branch: main).

## 3. Etiket ve GitHub Release

Proje klasöründe (yerelde):

    git fetch origin
    git checkout main
    git pull origin main
    git tag -a v1.0.0 -m "TKYS 1.0.0"
    git push origin v1.0.0

- [ ] GitHub → **Releases → Draft a new release** → tag: `v1.0.0` (mevcut), hedef `main`, başlık `TKYS v1.0.0`, açıklama = `RELEASE_NOTES.md` içeriği → **Publish release**.
- [ ] `git log -1 --format=%h` ile yayın commit'ini not edin (üstteki tablo).

## 4. Canlı sunucuyu güncelleme (sunucu bilgisayarında)

Önce **geri dönüş bilgilerini** yukarıdaki tabloya yazın: `git log -1 --format=%h` ve `python -m alembic current`.

- [ ] Kullanıcılara haber verin ("X dakika sistem kapalı"); kimsenin işlem yapmadığından emin olun.
- [ ] **Elle yedek** alın (sunucu çalışırken) ve dosya adını tabloya yazın:

      python scripts/backup/veritabani_yedekle.py

- [ ] Sunucuyu durdurun: `schtasks /End /TN TKYS_Sunucu`
- [ ] Kodu **main**'e alın:

      git fetch --tags origin
      git checkout main
      git pull origin main
      python -m pip install -r requirements.txt

- [ ] Veritabanını güncelleyin ve doğrulayın (`ŞEMA UYUMLU` görmeden sunucuyu başlatmayın):

      python -m alembic upgrade head
      python scripts/sema_dogrula.py

  Test kurulumundan gelen bir veritabanında bu adım şunları da yapar: cihaz durumlarını düzeltir, Proje Asistanı'na Oda Etkinlikleri izinlerini verir,
  duyurular tablosunu ve `DUYURU_YONET` iznini ekler, duyuru "Okudum" işaretleri için `duyuru_okundu` tablosunu ve denetim kayıtlarında giriş sorgusu için
  bir dizin ekler. Ayrıntı: `RELEASE_NOTES.md` → "Önceki bir test kurulumundan yükseltme".
  Sunucuda `python -m alembic current` çıktısı `python -m alembic heads` ile **aynı** olmalı (tek head).
- [ ] Görevleri yeniden kurun (yönetici PowerShell): `python scripts/windows/sunucu_kurulum.py` ve `python scripts/windows/kurulum.py`
- [ ] Sunucuyu başlatın: `schtasks /Run /TN TKYS_Sunucu`
- [ ] `git describe --tags` çıktısı `v1.0.0` (ya da `v1.0.0-0-g...`), `/api/saglik` açılıyor.

## 5. İstemciler

- [ ] Her istemci bilgisayarda yeni sürüm kuruldu/güncellendi; `TKYS_API_URL` (ve HTTPS ise `TKYS_CA_BUNDLE`) doğru.
- [ ] **Hakkında** penceresinde istemci ve sunucu sürümü aynı: **1.0.0**.

## 6. Yayın sonrası smoke test (en az 15 dakika)

`docs/test-reports/SMOKE-001_Canli_Ortam_Smoke_Test.md` içindeki S2–S11 adımlarını yeni sürümde tekrarlayın (canlı doğrulama gününde yapılan elle kontrollerin kısa tekrarıdır: [`Canli_Dogrulama_Gunu_Kontrol_Listesi.md`](Canli_Dogrulama_Gunu_Kontrol_Listesi.md) bölüm 2). En az şunlar:

- [ ] Her rolle giriş (yönetici, müdür, memur, psikolog, danışma öğrencisi, proje asistanı); ana panelde Duyurular / Benim Günüm / Bugün-Yarın-Hafta seçici açılıyor.
- [ ] **Benim Günüm → Bekleyen işlerim:** danışma öğrencisinde açık görevi, memur/yöneticide onay bekleyen danışma masası oturumunu ve açık arızayı gösteriyor; bekleyen yoksa satır yok.
- [ ] **Duyurular:** bir test duyurusu yayınla → başka rolle **Okudum** de → duyuru o kullanıcıda gizleniyor, diğerinde duruyor; zil sayısı buna göre azalıyor.
- [ ] **🔔 Zil:** günlük bilgi ve okunmamış duyurular her rolde görünüyor (memur/yöneticide süresi dolan öğrenci kaydı, sonucu girilmemiş randevu, yedek uyarısı da).
- [ ] **Dışa aktarma:** bir rapor sayfasında (örn. Randevu Raporları) **⬇ Dışa Aktar** → önce *Excel mi PDF mi* sorusu çıkıyor → **PDF** seçip kaydet → dosya açılıyor, Türkçe karakterler (ğ ü ş ı ö ç İ) doğru, tablo başlığı ve sayfa numarası var.
      Aynı işlemi **Excel** için ve bir liste sayfasından (örn. Cihaz Envanteri) tekrarlayın; Denetim Kayıtları'nda aktarımın "Dışa Aktarım (Excel/PDF)" olarak göründüğünü doğrulayın.
- [ ] Randevu oluştur → düzenle → iptal; cihaz rezervasyonu oluştur → iptal.
- [ ] Yönetici → Denetim Kayıtları: bu işlemler görünüyor. Yönetici → Sistem Durumu: yeşil.
- [ ] `schtasks /Run /TN TKYS_Otomatik_Yedekleme` → `logs\yedekleme.log` çıkış kodu 0.
- [ ] Smoke testte açılan test kayıtları (test randevusu, test rezervasyonu, test duyurusu) temizlendi; test hesabı kalmadı.

## 7. Geri dönüş planı

**Ne zaman:** giriş yapılamıyor, veri bozuluyor ya da kritik bir iş yapılamıyor **ve** hızlı düzeltme (aynı gün küçük bir yama) mümkün değil.
Yayından sonraki ilk saatlerde karar verin: geri dönüş, yayından sonra girilen kayıtları **kaybettirir**; kayıt girilmeye başlandıysa tercihen ileriye doğru düzeltme (yama) yapılır.

1. Sunucuyu durdurun: `schtasks /End /TN TKYS_Sunucu`
2. Kodu eski commit'e alın: `git checkout <yayından önceki commit>` (üstteki tablo).
3. Veritabanı: yayından önce **elle alınan yedeği YENİ bir veritabanına** geri yükleyin (araç mevcut veritabanının üzerine yazmaz):

       python scripts/restore/veritabani_geri_yukle.py --hedef tkys_yayin_oncesi --dump <elle alınan yedek dosyası>

   Kayıt sayılarını kontrol edin, sonra `.env` içindeki `DB_NAME` değerini `tkys_yayin_oncesi` yapın. (Bu işlem `DB_MIGRATION_*` bilgisini gerektirir.)
4. `python scripts/sema_dogrula.py` → `ŞEMA UYUMLU`; sunucuyu başlatın: `schtasks /Run /TN TKYS_Sunucu`.
5. Sorunu GitHub'da P0 issue olarak kaydedin, düzeltme `hotfix/...` dalıyla develop'a girer, CI yeşil olunca main'e ve yeni etikete (`v1.0.1`) taşınır.

`alembic downgrade` ile geri dönmeyin: yedekten geri yükleme daha güvenli ve test edilmiştir. Yayınlanmış `v1.0.0` etiketi silinmez.

## 8. Yayından sonra

- [ ] Ekibe ve kullanıcılara yayın duyurusu (tarih, sürüm, kılavuzlar, destek yolu: `RELEASE_NOTES.md` → Destek).
- [ ] İlk hafta: günlük `logs\sunucu.log` ve yedek log kontrolü; yeni sorunlar GitHub issue olarak P0/P1/P2 etiketiyle açılır.
- [ ] Bundan sonraki kod değişiklikleri yine `develop`'a gelir; yayınlar `develop → main` PR'ı ve yeni etiketle (`v1.0.1`, `v1.1.0`…) yapılır.
