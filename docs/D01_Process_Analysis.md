# Travma Merkezi - Cihaz Yaşam Döngüsü ve Süreç Analizi
**Sorumlu:** Öğrenci B (Cihaz ve Operasyon Mühendisi)
**Tarih:** 21 Eylül 2026
**Kapsam:** Travma merkezinde kullanılan ölçüm, terapi ve klinik cihazlarının sisteme girişinden hurdaya ayrılışına kadar geçen operasyonel süreçlerin ve durum (state) geçişlerinin tanımlanması[cite: 12].

---

## 1. Cihaz Durumları (State Yönetimi)
Bir cihaz sistemde aynı anda sadece tek bir operasyonel durumda bulunabilir. Randevu ve çakışma algoritmaları bu durumları baz alarak çalışacaktır.

*   🟢 **Kullanıma Hazır (Aktif):** Cihazın herhangi bir arızası yoktur, bakımı tamdır ve anlık olarak herhangi bir odaya/randevuya tahsis edilmemiştir. Rezervasyona tamamen açıktır.
*   🟡 **Rezerve (Beklemede):** Cihaz, ileri bir tarih/saat için belirli bir operasyonel koda (örn: DN-2026-0048) ve odaya atanmıştır. Belirtilen zaman diliminde başka bir işlem için seçilemez.
*   🔵 **Kullanımda (Operasyonda):** Randevu saati gelmiş ve cihaz anlık olarak seansta kullanılmaktadır. 
*   🔴 **Arızalı (Bloke):** Cihaz donanımsal veya yazılımsal bir hata vermiştir. Sekreter veya psikolog tarafından arıza kaydı açılmıştır. **Kritik Kural:** Arızalı durumundaki bir cihaz hiçbir yeni randevuya atanamaz.
*   🟠 **Bakımda / Kalibrasyonda:** Cihazın aylık veya yıllık periyodik bakım süresi gelmiştir veya arıza sonrası onarım sürecindedir. Sistemin randevu atamasına kapalıdır.
*   ⚫ **Kullanım Dışı (Hurda):** Cihazın kullanım ömrü dolmuş veya tamir edilemez durumdadır. Sistemden tamamen silinmez (geriye dönük audit/raporlama için), ancak durumu pasife çekilerek envanter listesinden düşürülür.

---

## 2. Süreç Akışları ve Kurallar

### 2.1. Cihaz Sisteme Giriş Süreci
1. Müdür veya yetkili personel cihazı (İsim, Model, Seri No, Zimmetli Oda) sisteme kaydeder.
2. Sistem cihaza otomatik olarak bir envanter kodu (örn: CHZ-001) atar.
3. Başlangıç durumu otomatik olarak **Kullanıma Hazır** olarak belirlenir.

### 2.2. Cihaz Rezervasyon Süreci (Randevu Modülü ile Entegrasyon)
1. Psikolog veya Sekreter, randevu oluştururken bir cihaz talep eder.
2. Sistem, talep edilen tarih ve saat aralığında cihazın durumunu kontrol eder.
3. Cihaz o saatte **Rezerve**, **Arızalı** veya **Bakımda** ise sistem rezervasyonu reddeder (Çakışma Kontrolü).
4. Cihaz uygunsa, durumu o zaman dilimi için **Rezerve** olarak işaretlenir ve ilgili oda ile eşleştirilir.

### 2.3. Arıza Bildirim ve Yönetim Süreci
1. Kullanım sırasında cihaz bozularak **Arızalı** duruma geçirilir.
2. Sistem, bu cihazın ileri tarihlerde rezerve edildiği tüm randevuları tespit eder.
3. Sistem, ilgili randevuların sahiplerine (Sekreter/Psikolog) uyarı verir: *"Dikkat: Yaklaşan randevunuzdaki cihaz arızalanmıştır, lütfen yeni bir cihaz atayınız."*
4. Teknik ekip müdahale eder ve onarım işlemi bitince durum tekrar **Kullanıma Hazır** yapılır.

### 2.4. Periyodik Kalibrasyon Süreci
1. Her cihazın sisteme girilen bir "Sonraki Kalibrasyon Tarihi" vardır.
2. Sistem, bu tarihe 7 gün kala Dashboard üzerinden yöneticilere otomatik uyarı düşer.
3. Bakım tarihi gelen cihaz, bakım personeli tarafından **Bakımda** durumuna alınır.

---
## 3. Teknik Riskler ve Önlemler
*   **Race Condition (Eşzamanlılık):** Aynı anda iki sekreterin tek bir **Kullanıma Hazır** cihaza aynı saniyede rezervasyon yapmaya çalışması. (Önlem: PostgreSQL seviyesinde transaction kilitlemesi ve zaman aralığı kısıtlaması kullanılacaktır).
*   **Veri Bütünlüğü:** Randevusu geçmişte tamamlanmış cihazların kaydının silinmesi. (Önlem: Geçmiş randevu kayıtları ve loglar asla veritabanından silinmeyecek (Soft Delete), sadece arayüzde gizlenecektir).