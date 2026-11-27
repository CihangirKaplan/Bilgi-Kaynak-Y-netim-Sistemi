# TKYS v1.0.0 — Ekip Görev Dağılımı (yayına kadar)

Üç kişilik ekibin canlı doğrulamadan yayına kadar kim neyi, hangi sırayla, ne kadar sürede yapacağı. Her adımın yanındaki kutu işaretlenerek ilerlenir; bir adım başarısız olursa **durulur**, sorun GitHub'da P0–P4 etiketli issue olarak kaydedilir.

Ayrıntılı adımlar ve kanıt biçimi için: [`Canli_Dogrulama_Gunu_Kontrol_Listesi.md`](Canli_Dogrulama_Gunu_Kontrol_Listesi.md) (doğrulama), [`GO-NO-GO_Kontrol_Listesi.md`](../test-reports/GO-NO-GO_Kontrol_Listesi.md) (karar), [`Yayin_Gunu_Rehberi_v1.0.0.md`](Yayin_Gunu_Rehberi_v1.0.0.md) (yayın).

| Kişi | Kısaltma | Ağırlık alanı |
|---|---|---|
| Cihangir Kaplan | **C** | Repo sahibi: birleştirme (merge), sürüm etiketi, GitHub Release, istemci derlemesi; raporlar ve belgeler |
| Şehnaz | **Ş** | Sunucu iş mantığı, randevu/cihaz/oda akışları, ana panel; test verisi |
| Ayşe Berra | **A** | Canlı sunucu, güvenlik (SEC-001), yedekleme/geri yükleme, hesaplar ve izinler |

## 1. Şu anki durum (27.11.2026)

**Tamam**
- [x] Kod tamam; develop CI yeşil (son koşular başarılı).
- [x] Canlı sunucu güncel (bildirilen commit `c959e71`), şema doğrulaması ve otomatik yedekleme çalışıyor.
- [x] Güvenlik denemeleri (SEC-001) bitti: T01–T13 PASS, Bulgu #1–#5 kapalı, açık bulgu yok.
- [x] Yedekten geri yükleme kanıtlandı.
- [x] UAT pilotunun ertelenmesi kayda geçti (GO/NO-GO madde 12: ekip kararı, canlıya geçişten sonraki ilk hafta).
- [x] Yayın Günü Rehberi, Canlı Doğrulama Listesi ve otomatik ön kontrol betiği (`scripts/yayin_oncesi_kontrol.py`) hazır.

**Kalan:** canlı doğrulamanın elle kısmı → karar ve kayıt → yayın → ilk hafta (UAT pilotu dahil).

## 2. Kurallar

- Dondurma: bundan sonra develop'a yalnızca yayını engelleyen hata düzeltmeleri girer; yeni özellik yok.
- develop'a doğrudan push yok; her değişiklik PR ile, CI yeşil olunca birleşir.
- Canlı sunucuda her değişiklikten önce **elle yedek**.
- Klasör izinleri sıkılaştırıldığı için sunucudaki komutlar **yönetici PowerShell**'de çalıştırılır.
- Test hesapları ve kayıtları iş bitince temizlenir; gerçek kişisel veri girilmez.
- Parola, token ve `.env` içeriği kanıta, issue'ya ve sohbete yazılmaz.

## 3. Aşama 1 — Canlı doğrulama günü (kalan elle kısım)

Toplam yaklaşık 2,5–3 saat tek kişiyle; aşağıdaki gibi paylaşılırsa (2.2–2.3 ile 2.4–2.5 paralel) yaklaşık 1,5 saat. Bölüm numaraları Canlı Doğrulama Listesi'ne aittir.

| ☐ | Adım | Süre | Kim | Not |
|---|---|---|---|---|
| ☐ | Hazırlık: aday commit'i herkese duyur (`git log -1 --format=%h`); test hesaplarını hazırla (SEC-001 `sec_*` hesapları, gerekli rollerin aktifleştirilmesi, parola değişiklikleri) | 20 dk | **A** | Günlükte bazı parola değişiklikleri görünüyor; kimin ne yaptığını not edin |
| ☐ | 2.1 Rol rol giriş ve menüler (altı rol, hatalı parola; SMOKE S2, S10) | 20 dk | **A** | Her rolün menüleri doğru mu |
| ☐ | 2.2 Randevu: oluştur, düzenle, iptal, çakışma reddi; Danışanlar sayfası (S5–S8) | 20 dk | **Ş** | |
| ☐ | 2.3 Cihaz, bakım, arıza, **oda silme** | 20 dk | **Ş** | Oda silme yeni kurala göre: önce odayı **pasife al**, sonra sil; kullanılmış oda silinemez |
| ☐ | 2.4 Ana panel ve bildirimler: Benim Günüm "Bekleyen işlerim", Duyurular (Okudum), zil | 15 dk | **Ş + A** | İki farklı bilgisayar/rol ile |
| ☐ | 2.5 Raporlar ve **Excel/PDF dışa aktarma**: Randevu Raporları, Cihaz Envanteri, Denetim Kayıtları | 20 dk | **C** | Türkçe karakter, birimler, sayfa numarası; yeni biçim seçim penceresi |
| ☐ | 2.6 Denetim kayıtları: yapılan işlemler görünüyor (S9) | 10 dk | **A** | |
| ☐ | §5 İki bilgisayardan eşzamanlı deneme (biri randevu ekler, diğeri yeniler); `.exe` ile açılış | 15 dk | **Ş + C** | İkinci bir bilgisayar gerekir (SMOKE H4) |
| ☐ | §6 3–5 kişiyle 5 dakikalık performans gözlemi: ana panel, Danışanlar, bir rapor | 15 dk | **C + Ş + A** | Sayfalar saniyeler içinde açılmalı, 500 hatası olmamalı |
| ☐ | Temizlik: herkes kendi test kayıtlarını siler/iptal eder; A test hesaplarını pasife alır | 15 dk | **C + Ş + A** | Test hesabı kalmamalı |
| ☐ | Bulguları issue yap; GO/NO-GO eşleme tablosunu (bölüm 9) işaretle; kanıtları `docs/test-reports/kanit/` altına koy | — | **C** toplar, herkes kanıtını verir | |

**Zaman kısıtlıysa asgari kapsam:** 2.1 (rol/menü), 2.4 (bildirimler), 2.5 (dışa aktarma). Aynı gün çok değişiklik birleştiği için bu üçünü atlamak önerilmez.

**Bulgu çıkarsa:** P0/P1 ise Ş (sunucu/iş mantığı) ya da A (arayüz/izin) düzeltme hazırlar, C PR'ı birleştirir, ilgili adım yeniden denenir.

## 4. Aşama 2 — Karar ve kayıt

| ☐ | Adım | Kim |
|---|---|---|
| ☐ | GO/NO-GO listesi: 14 maddeden her biri için kanıt var mı? (madde 12 kayıtlı istisna) Birlikte işaretlenir; **madde 12 dışında bir madde eksikse karar NO-GO** | **C + Ş + A** |
| ☐ | Kanıt kaynakları: madde 1–2 Actions develop son koşusu (C); 3–4 P0/P1 issue listesi (C); 5–7 SEC-001 raporu (A); 8 eşzamanlılık (Ş); 9–10 yedek ve geri yükleme (A); 11 denetim (A); 13 kurulum (A + Ş); 14 belgeler (Ş) | ilgili kişi |
| ☐ | Karar GO ise yayın tarihi ve saati belirlenir; kullanıcılara kapalı kalınacak süre duyurulur | **C + Ş + A** |
| ☐ | **Hazırlık PR'ı** (develop'a): `python scripts/yayin_oncesi_kontrol.py --belgeleri-main-yap`; CHANGELOG ve RELEASE_NOTES yayın tarihi; GO/NO-GO'da commit, tarih, katılanlar, karar; "komutlar yönetici PowerShell'de çalıştırılır" notu; `python scripts/yayin_oncesi_kontrol.py --go` **tamamen yeşil**; CI yeşil olunca birleşir | **C** hazırlar/birleştirir, **Ş** inceler |

## 5. Aşama 3 — Yayın (GO çıkarsa)

Ayrıntı: [`Yayin_Gunu_Rehberi_v1.0.0.md`](Yayin_Gunu_Rehberi_v1.0.0.md).

| ☐ | Adım | Kim |
|---|---|---|
| ☐ | T-1 gün: dondurma, develop CI yeşil, açık P0/P1 yok, `yayin_oncesi_kontrol.py` HATA vermiyor | **C** |
| ☐ | develop → **main** PR'ı, **"Create a merge commit"** ile birleştirme (Squash/Rebase seçilmez); main CI yeşil | **C** |
| ☐ | `v1.0.0` etiketi ve GitHub Release (`RELEASE_NOTES.md` içeriği) | **C** |
| ☐ | **İstemci derlemesi:** `v1.0.0` etiketli main'den istemci `.exe` paketini oluştur; temiz bir bilgisayarda aç; Hakkında'da sürüm **1.0.0**; paketi A ve Ş'ye ilet | **C** |
| ☐ | Kullanıcılara kısa duyuru (X dakika kapalı); **elle yedek**; sunucuyu main'e al (`git fetch --tags`, `checkout main`, `pull`, `pip install -r requirements.txt`); `alembic upgrade head`; `sema_dogrula.py` → ŞEMA UYUMLU; görevler; başlat; `/api/saglik` | **A** (C yanında) |
| ☐ | **İstemcileri güncelle:** her bilgisayarda yeni sürüm, `TKYS_API_URL` (HTTPS ise `TKYS_CA_BUNDLE`) doğru; Hakkında'da istemci ve sunucu sürümü aynı. Eski sürümlü istemciler yeni sunucuyla bağlanınca zilde hata görebilir: **hepsi güncellenmeden** kullanıcılara açılmaz | **Ş** (A destek) |
| ☐ | Yayın sonrası smoke test (en az 15 dk): her rolle giriş, randevu, rezervasyon, denetim, yedek görevi; test kayıtlarını temizle | **C + Ş + A** |
| ☐ | Sorun olursa geri dönüş kararı: yedekten **yeni** veritabanına geri yükleme (`alembic downgrade` yapılmaz) | **C** karar verir, **A** uygular |

## 6. Aşama 4 — Yayından sonra (ilk hafta)

| ☐ | Adım | Kim |
|---|---|---|
| ☐ | Günlük `logs\sunucu.log` ve yedek günlüğü kontrolü | **A** |
| ☐ | Gelen sorunlar GitHub issue (P0–P4); P0/P1 aynı gün yama (`hotfix/...` → develop → CI → main → `v1.0.1`) | **Ş + A** düzeltir, **C** yayınlar |
| ☐ | **UAT pilotu** (GO/NO-GO madde 12): bir psikolog, bir memur, bir müdür; gözlemci yazılım ekibinden dışarıdan; sonuç [`UAT-001_Pilot_Raporu.md`](../test-reports/UAT-001_Pilot_Raporu.md)'na işlenir, P0/P1 = 0 ve üç onay gelince madde 12 ☑ | **C** yürütür, **A** hesaplar/yedek, **Ş** test verisi |
| ☐ | Kullanıcılara destek, geri bildirim toplama, kılavuzların dağıtımı | **C** |

## 7. Ekibin netleştirmesi gerekenler

1. Canlı doğrulama günü ve saati (A'nın sunucu erişimi ve ikinci bir bilgisayar gerekir).
2. Yayın tarihi/saati ve kullanıcıların sistemi kullanamayacağı süre.
3. UAT gözlemcisi (yazılım ekibi dışından) ve üç katılımcı, yayından sonraki ilk hafta için.
4. İstemci `.exe` derleme yönteminin repoya yazılması (şu an belgelenmiş değil).
