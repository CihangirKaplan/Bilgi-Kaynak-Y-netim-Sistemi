# Psikolog Kılavuzu

Bu kılavuz **Psikolog** rolü içindir. Giriş, şifre, arama, sıralama ve kısayollar için önce [Ortak Kullanım Kılavuzu](../Ortak_Kullanim.md)'na bakın.

**Önemli:** Siz yalnızca **kendi randevularınızı** ve **kendi danışanlarınızı** görürsünüz. Başka bir psikoloğun kayıtları size görünmez.

## Menünüzde neler var?

| Sayfa | Ne için? |
|---|---|
| **Ana Kontrol Paneli** | Günün özeti ve kısayol kartları |
| **Randevu Yönetimi** | Randevularınızı görme, oluşturma, düzenleme, iptal etme, durum işaretleme |
| **Danışanlar** | Danışanlarınızın bilgileri, özeti ve randevu geçmişi; yeni danışan oluşturma |
| **Oda Kullanımı** | Odaların doluluk durumu |
| **Oda Etkinlikleri** | Odalarda planlanan etkinlikleri görme |
| **Randevu Raporları** | Randevu sayıları, durumlar, iptal nedenleri, dağılımlar (kendi randevularınız) ve Excel |
| **Cihaz Uygunluğu** | Cihazların ne zaman uygun olmadığını görme (bakım, kalibrasyon, arıza, rezervasyon) |

## 1. Yeni danışan oluşturmak

Danışanlar **adla değil kodla** kaydedilir. Danışanın adını, telefonunu ya da tanısını sisteme yazmayın.

1. **Danışanlar** sayfasında **＋ Yeni Danışan** düğmesine basın.
2. **Danışan Kodu** otomatik gelir (örneğin `DAN-2026-0001`; kod yıl bazlıdır). Değiştirilemez.
3. **Psikolog** alanında sizin adınız seçilidir.
4. **Yaş Grubu**'nu seçin: **Çocuk** ya da **Yetişkin**. Bu seçim, randevuda hangi terapi türünün seçilebileceğini belirler.
5. **Ücret Durumu**'nu seçin: **Ücretli** ya da **Ücretsiz**.
6. Ücretsiz seçtiyseniz **İstisna Türü**'nü seçin: **Kanser Hastası** ya da **Şehit / Gazi Yakını**. Ücretli seçili ise istisna **Yok** olur ve alan kapalıdır.
7. **Danışanı Oluştur**'a basın. Yeşil bir bildirim görürsünüz; danışan listede belirir.

> Not: Eski danışanların yaş grubu boş olabilir ("Belirtilmedi"). Bu danışanlar için randevu açabilmeniz amacıyla yaş grubunu tamamlayın (aşağıya bakın).

## 2. Danışanlarınızı görmek ve yönetmek

**Danışanlar** sayfasının solunda danışan listesi, sağında seçili danışanın ayrıntıları vardır.

- Listede **Danışan Kodu, Psikolog, Yaş Grubu, Ücret, Randevu (sayısı), Durum** sütunları görünür. Başlıklara tıklayarak sıralayabilir, arama kutusuyla (kod, yaş grubu, durum...) süzebilirsiniz.
- **Pasifleri göster** kutusunu işaretlerseniz pasif danışanlar da listelenir (sönük renkte).
- Bir danışana tıklayınca sağ tarafta üç bölüm görürsünüz: **Bilgiler**, **Özet** (durum sayıları, ilk randevu, son randevu, sıradaki planlı randevu) ve **Randevular** (geçmiş ve gelecek randevular).
- **Bilgileri Düzenle:** Danışanın **yaş grubunu** tamamlar/değiştirir. Yetişkin olarak değiştirirseniz ve danışanın **planlı oyun terapisi randevuları** varsa sistem bunu açıkça yazıp onay ister: o randevuların terapi türü **Bireysel terapi**'ye çevrilir (yetişkinlere oyun terapisi verilemez). **Geçmiş randevular değişmez.**
- **Pasife Al / Yeniden Aktif Et:** Danışanı pasife alırsanız **yeni randevu verilemez**; geçmiş randevuları **korunur**. Hiçbir danışan silinmez.
- **⬇ Excel'e Aktar:** Ekranda görünen danışan kodlarını Excel'e yazar (ad/telefon içermez). Aktarım denetim kaydına yazılır.

## 3. Randevu oluşturmak

1. **Randevu Yönetimi** sayfasında **＋ Yeni Randevu**'ya basın (ya da **Ctrl + N**).
2. Formu doldurun:
   - **Danışan Kodu:** Listeden kendi danışanınızı seçin.
   - **Psikolog Seçiniz:** Sizin adınız seçilidir.
   - **Görüşme Odası:** Yalnızca size **atanmış** odalar listelenir. Size atanmış oda yoksa kutuda **"Bu psikoloğa atanmış oda yok"** yazar; sistem yöneticinizden **Oda Yetkileri**'ni isteyin.
   - **Görüşme Tipi:** **Yüz yüze** ya da **Çevrimiçi**.
   - **Terapi Türü:** Danışanın yaş grubuna göre seçilir: **Çocuk** için *Oyun terapisi* ya da *Bireysel terapi*, **Yetişkin** için yalnızca *Bireysel terapi*. Danışanın yaş grubu boşsa önce danışanı düzenleyin.
   - **Randevu Tarihi** ve **Randevu Saati:** Saatler **09:00 ile 15:00** arasında **saat başıdır**; her randevu **1 saat** sürer.
3. **Randevuyu Kaydet**'e basın.

Saat listesinde **soluk ve seçilemeyen** saatler doludur; yanında nedeni yazar: **Oda dolu**, **Psikolog dolu** ya da **Dolu**.

Sistemin reddettiği durumlar (mesaj ekranda çıkar):
- **Hafta sonu** randevu verilemez.
- **Geçmiş** bir tarihe randevu verilemez.
- Seçilen **danışan, seçtiğiniz psikoloğa ait değilse** randevu verilemez.
- Seçilen **oda size atanmamışsa** randevu verilemez.
- **Pasif** bir danışana randevu verilemez.
- Aynı oda ya da aynı psikolog o saatte doluysa randevu verilemez.

## 4. Randevu listesi, durumlar ve düzenleme

Randevu listesinin sütunları: **Randevu ID, Danışan Kodu, Psikolog, Oda, Tarih, Saat, Görüşme, Terapi, Durum.**

- **Varsayılan sıra:** yaklaşan planlı randevular önce (en yakını en üstte), sonra geçmiş olanlar (en yenisi önce). Başlığa tıklayınca sıralamayı değiştirebilirsiniz (sonraki yenilemede varsayılana döner).
- **Dönem seçici:** *Tüm tarihler, Bugün, Bu hafta, Bu ay, Özel aralık.* *Tüm tarihler* en yeni 2000 randevuyu getirir; eskilere ulaşmak için bir dönem seçin.
- **Durum seçici** ve **İptalleri gizle** kutusu: İptal edilenler varsayılan olarak gizlidir; **İptal Edildi** durumunu seçerseniz görünürler.
- **Durum rozeti:** *Planlandı, Tamamlandı, Gelmedi, İptal Edildi.* Başlangıç saati **geçmiş** ve iptal edilmemiş bir randevunun rozetine (yanında ▾ vardır) tıklayıp **Tamamlandı** ya da **Gelmedi** olarak işaretleyebilirsiniz; yanlış işaretlediyseniz aynı yoldan düzeltebilirsiniz.
- **✎ Randevu Düzenle:** Listeden randevuyu seçin, düğmeye basın (ya da çift tıklayın). Tarih, saat, oda, görüşme tipi ve terapi türünü değiştirebilirsiniz; aynı kurallar geçerlidir.
- Üstteki sayaç, kaç randevudan kaçının gösterildiğini söyler (örneğin *4 / 5 randevu*).

## 5. Randevu iptal etmek

1. Listeden randevuyu seçin, **✕ Randevu İptal Et**'e basın.
2. **İptal nedeni** seçin: *Danışan talebi, Psikolog mazereti, Oda / ekipman sorunu, Hatalı kayıt, Diğer.*
3. İsterseniz kısa bir **not** yazın (en fazla **100 karakter**). **Not alanına kişisel bilgi (ad, telefon, tanı) yazmayın.**
4. Onaylayın. Randevu **silinmez**, **İptal Edildi** durumuna geçer ve kayıt altında kalır; iptal nedeni listede görünür.

## 6. Oda Kullanımı ve Oda Etkinlikleri

- **Oda Kullanımı:** Odaların hangi saatlerde dolu olduğunu gösterir. Randevu açmadan önce uygun saati görmek için kullanın.
- **Oda Etkinlikleri:** Odalarda planlanan etkinliklerin (çok günlü oturumlar dahil) listesi. **Durum** ve **Dönem** süzgeçleriyle daraltabilirsiniz. Etkinlik yönetme yetkiniz yoksa yalnızca görüntülersiniz.
  Bir odada etkinlik varsa o saatlerde o odaya randevu verilemez.

## 7. Randevu Raporları

**Randevu Raporları** sayfasında dönem seçerek randevu sayılarını, durum dağılımını, iptal nedenlerini ve yoğun günleri görürsünüz; **⬇ Excel'e Aktar** ile dosyaya alabilirsiniz.
Siz yalnızca **kendi** randevularınızın raporunu görürsünüz. Raporların hesaplama tanımları için [Raporlama Rehberi](../../docs/Raporlama_Rehberi.md)'ne bakın.

## 8. Cihaz Uygunluğu

Cihazların hangi gün ve saatlerde **uygun olmadığını** (bakım, kalibrasyon, arıza, rezervasyon) gösteren takvimdir. Yalnızca görüntülersiniz; kişi adı ya da işlem ayrıntısı görünmez.

## 9. İpuçları

- Danışan oluşturmadan randevu verilemez; önce danışanı oluşturun.
- Terapi türü kutusu boşsa danışanın **yaş grubu** eksiktir; **Danışanlar → Bilgileri Düzenle** ile tamamlayın.
- Oda listesi boşsa size **oda yetkisi** verilmemiştir; sistem yöneticinize başvurun.
- Gün sonunda geçmiş randevuları **Tamamlandı / Gelmedi** olarak işaretlemek raporların doğru çıkmasını sağlar.
