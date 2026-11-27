# GO / NO-GO Kontrol Listesi (Hafta 8, Gün 5)

Canlıya geçiş kararı bu listeyle verilir (yol haritası 27. ve 41. bölümler). **Her madde kanıtıyla işaretlenir; tek bir madde bile
eksikse karar NO-GO'dur**: eksik giderilir, liste yeniden kontrol edilir. Hepsi tamamsa `v1.0.0` yayınlanır.

| Alan | Bilgi |
|---|---|
| Sürüm | `v1.0.0` adayı — commit ________ |
| Toplantı tarihi | ________ |
| Katılanlar | ________ |

| # | Madde | Sorumlu | Kanıt | Durum |
|---|---|---|---|---|
| 1 | Build PASS | Ekip | GitHub Actions "TKYS QA Tests", develop son çalıştırma yeşil | ☐ |
| 2 | Unit / Integration Tests PASS | Ekip | Aynı CI çalıştırması | ☐ |
| 3 | P0 hata = 0 | Ekip | GitHub issue listesi (P0 etiketi) | ☐ |
| 4 | P1 hata = 0 | Ekip | GitHub issue listesi (P1 etiketi) | ☐ |
| 5 | Authentication PASS | Öğrenci C | SEC-001: SEC-T01, T07, T08 (canlı satırları dahil) | ☐ |
| 6 | Authorization PASS | Öğrenci C | SEC-001: SEC-T02, T03, T04 | ☐ |
| 7 | Security Test PASS | Öğrenci C | SEC-001: SEC-T01 … T15 hepsi PASS | ☐ |
| 8 | Concurrency Tests PASS | Öğrenci C | SEC-001: SEC-T15 | ☐ |
| 9 | Backup PASS | Öğrenci C | SMOKE-001 S11–S12; 05.00 görevinin log'u | ☐ |
| 10 | Restore PASS | Öğrenci C | Yedeğin yeni veritabanına geri yüklenip kayıt sayılarının karşılaştırıldığı çıktı | ☐ |
| 11 | Audit PASS | Öğrenci C | SEC-001: SEC-T12; SMOKE-001 S9 | ☐ |
| 12 | UAT PASS | Ekip | UAT-001: üç katılımcının onayı, açık P0/P1 yok | ☐ |
| 13 | Installation PASS | Öğrenci A/B + C | Sunucu kurulumu (SMOKE-001 H1–H4) ve her istemcide `.exe` + `TKYS_API_URL` | ☐ |
| 14 | Documentation complete | Ekip | Kurulum, yedekleme, geri yükleme kılavuzları; psikolog, memur, müdür kılavuzları güncel | ☐ |

## Karar

GO ☐  NO-GO ☐

NO-GO ise eksik maddeler ve sorumlusu: ________

GO ise: develop → main birleştirilir, `v1.0.0` etiketi oluşturulur, canlıya geçmeden hemen önce elle yedek alınır.
Adım adım uygulama, geri dönüş planı ve otomatik ön kontrol (`python scripts/yayin_oncesi_kontrol.py`): [`docs/release/Yayin_Gunu_Rehberi_v1.0.0.md`](../release/Yayin_Gunu_Rehberi_v1.0.0.md).
Maddelerin kanıtlarını canlı ortamda toplamak için: [`docs/release/Canli_Dogrulama_Gunu_Kontrol_Listesi.md`](../release/Canli_Dogrulama_Gunu_Kontrol_Listesi.md) (bölüm 9: hangi madde hangi kanıtla kapanır).
