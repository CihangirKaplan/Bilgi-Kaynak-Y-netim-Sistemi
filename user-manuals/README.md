# TKYS Kullanıcı Kılavuzları

Bu klasör, Travma Kaynak Yönetim Sistemi'ni (TKYS) kullanan herkesin ilk başvuracağı kılavuzları içerir.
Kılavuzlar uygulamada gördüğünüz düğme ve sayfa adlarıyla yazılmıştır; sürüm **1.0.0**, son güncelleme **20 Kasım 2026**.

## Hangi kılavuzu okumalıyım?

Önce herkes için ortak olan [Ortak Kullanım Kılavuzu](Ortak_Kullanim.md)'nu okuyun (giriş, şifre, arama, sıralama, Excel, kısayollar).
Sonra rolünüze uygun kılavuza geçin:

| Rolünüz | Kılavuz |
|---|---|
| **Psikolog** | [psychologist/Psikolog_Kilavuzu.md](psychologist/Psikolog_Kilavuzu.md) |
| **Danışma Öğrencisi** ve **Proje Asistanı** | [student-assistant/Danisma_Ogrencisi_ve_Proje_Asistani_Kilavuzu.md](student-assistant/Danisma_Ogrencisi_ve_Proje_Asistani_Kilavuzu.md) |
| **Memur** (cihaz, öğrenci, faaliyet, danışma masası işleri) | [administrative/Memur_Kilavuzu.md](administrative/Memur_Kilavuzu.md) |
| **Sistem Admin** (kullanıcı, rol, denetim, yedek) | [administrative/Sistem_Yoneticisi_Kilavuzu.md](administrative/Sistem_Yoneticisi_Kilavuzu.md) |
| **Müdür (Yönetici)** | [director/Mudur_Kilavuzu.md](director/Mudur_Kilavuzu.md) |

Raporların ayrıntılı tanımı için: [docs/Raporlama_Rehberi.md](../docs/Raporlama_Rehberi.md).
Kurulum ve bakım (yalnızca sistemi kuran kişi için): [docs/deployment/Sunucu_Kurulum_Kilavuzu.md](../docs/deployment/Sunucu_Kurulum_Kilavuzu.md).

## Hangi rol hangi sayfaları görür? (varsayılan yetkiler)

Aşağıdaki tablo sistemin kurulumdaki **varsayılan** yetkilerini gösterir. Sistem Admin, **Rol & İzin Yönetimi** sayfasından
yetkileri değiştirebilir; bu durumda menünüz farklı olabilir. Menüde göremediğiniz bir sayfa için yetkiniz yok demektir.

| Sayfa | Psikolog | Danışma Öğr. | Proje Asist. | Memur | Müdür | Admin |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| Ana Kontrol Paneli | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| Randevu Yönetimi | ✔ (kendi) | ✔ (oluştur/düzenle/iptal) | ✔ (görüntüle) | ✔ (görüntüle) | ✔ (görüntüle) | ✔ (tam) |
| Danışanlar | ✔ | ✔ | – | – | – | ✔ |
| Oda Kullanımı | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| Oda Etkinlikleri | ✔ | ✔ | – | ✔ | ✔ | ✔ |
| Randevu Raporları | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| Oda Kullanım Raporu | – | – | – | – | ✔ | ✔ |
| Öğrenciler | – | – | ✔ | ✔ | ✔ | ✔ |
| Faaliyet Kayıtları | – | – | ✔ | ✔ | ✔ | ✔ |
| Puan / Öğrenci / Faaliyet Raporu | – | – | ✔ | ✔ | ✔ | ✔ |
| Danışma Masası (görev başlat/bitir) | – | ✔ | – | – | – | – |
| Danışma Masası Yönetimi | – | – | – | ✔ | – | ✔ |
| Danışma Masası Raporları | – | – | – | ✔ | ✔ | ✔ |
| Cihaz Uygunluğu | ✔ | – | ✔ | ✔ | ✔ | ✔ |
| Cihaz Envanteri | – | – | – | ✔ | ✔ | ✔ |
| Cihaz Rezervasyonu | – | – | ✔ | ✔ | – | ✔ |
| Bakım Kayıtları, Bakım Planları, Kalibrasyon, Arıza Kayıtları | – | – | – | ✔ | ✔ | ✔ |

> **Not:** Bakım Kayıtları ve Kalibrasyon sayfaları iki ayrı izinle çalışır: **görüntüleme** (sayfayı açar, kayıtları gösterir, Excel'e aktarır) ve **yönetme** (kayıt ekleme, düzenleme, silme). Yalnızca görüntüleme izni olan kullanıcı düzenle/sil düğmelerini görmez. Mevcut Memur, Müdür ve Admin rollerinde ikisi de açıktır; yönetici **Rol-İzin** ekranından başka bir role yalnızca görüntüleme verebilir.
| Cihaz Raporları (beş sekme: Bakım Geçmişi, Kalibrasyon, Arızalar, Cihaz Rezervasyonu, Geciken Bakım Planları) | – | – | – | ✔ | ✔ | ✔ |
| Yönetim Raporları ve İstatistikler | – | – | – | – | ✔ | ✔ |
| Kullanıcı & Personel | – | – | – | – | ✔ | ✔ |
| Audit Kayıtları, Yetki Raporu, Sistem Durumu | – | – | – | – | ✔ | ✔ |
| Oda Yönetimi | – | – | – | ✔ | ✔ | ✔ |
| Rol & İzin Yönetimi | – | – | – | – | – | ✔ |

Not: Psikolog yalnızca **kendi** randevularını ve **kendi** danışanlarını görür.

## Yardım ve destek

- Uygulamada **F1** tuşu ya da üst çubuktaki **?** düğmesi Hakkında / Yardım penceresini açar.
- Bir sorunu bildirirken **Hakkında** sekmesindeki **Destek bilgisini kopyala** düğmesine basıp metni mesajınıza ekleyin;
  sürüm bilgileriniz destek ekibine hazır ulaşır (parola ya da oturum anahtarı içermez).
- Yetkiniz olmayan bir işlem için sistem yöneticinizle konuşun.