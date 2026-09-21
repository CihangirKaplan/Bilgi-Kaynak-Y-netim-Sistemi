# Randevu Süreç Haritası 

## 1. Genel Bakış ve Amaç

Bu doküman, sistem üzerindeki **Randevu Oluşturma, Güncelleme, İptal ve Çakışma Yönetimi** süreç adımlarını detaylandırmak amacıyla hazırlanmıştır.

Süreç tasarlanırken kişisel verilerin korunması ilkesi gereği **hiçbir aşamada gerçek kişisel bilgi (PHI - Protected Health Information) kullanılmayacak**, randevular yalnızca **Danışan Kodu** (`DN-YYYY-XXXX`) üzerinden yürütülecektir.

## 2. Aktörler ve Rol Yetkileri

| Aktör | Randevu Oluşturma | Randevu Güncelleme | Randevu İptal | Takvim İzleme | 
 | ----- | ----- | ----- | ----- | ----- | 
| **Psikolog** | (Kendi adına) | (Kendi randevuları) | (Kendi randevuları) | (Kendi takvimi) | 
| **Memur** |  |  |  | (Genel oda kullanımı) | 
| **Müdür** |  |  |  | (Tüm takvimler) | 

## 3. End-to-End Randevu Oluşturma İş Akışı

Aşağıdaki diyagram, istemci (PySide6) tarafında başlayıp sunucu (FastAPI) ve veritabanı (PostgreSQL) doğrulamalarından geçerek tamamlanan randevu oluşturma sürecini göstermektedir.

```
[İstemci - PySide6]            [Sunucu - FastAPI]             [Veritabanı - PostgreSQL]
       │                                │                                │
       │ 1. Randevu Talebi (POST)       │                                │
       ├───────────────────────────────►│                                │
       │ (Danışan Kodu, Tarih/Saat,     │                                │
       │  Oda ID, Cihaz ID)             │                                │
       │                                │ 2. Validasyon & RBAC           │
       │                                ├──────────────────────────────┐ │
       │                                │ Input & Token Doğrulama      │ │
       │                                │◄─────────────────────────────┘ │
       │                                │                                │
       │                                │ 3. Çakışma Kontrolleri         │
       │                                ├──────────────────────────────┐ │
       │                                │ - Psikolog Musait mi?        │ │
       │                                │ - Oda Musait mi?             │ │
       │                                │ - Cihaz Musait/Calisir mi?    │ │
       │                                │◄─────────────────────────────┘ │
       │                                │                                │
       │                                │ 4. Kayıt Oluştur / Commit      │
       │                                ├───────────────────────────────►│
       │                                │                                │
       │ 5. Başarılı Yanıt (201 Created) │                                │
       │◄───────────────────────────────┤                                │
       │                                │                                │

```

## 4. Süreç Adımları Detayı

### Adım 1: Danışan Seçimi veya Oluşturulması

1. Kullanıcı (Psikolog) sistemden mevcut bir danışan kodunu seçer ya da "Yeni Danışan Kodu Oluştur" butonuna basar.

2. Sistem, benzersiz formatta bir kod üretir (Örn: `DN-2026-0102`).

3. Danışan koduna hiçbir kişisel bilgi bağlanmaz.

### Adım 2: Parametrelerin Belirlenmesi

* **Başlangıç Zamanı:** `YYYY-MM-DD HH:MM`

* **Bitiş Zamanı:** `YYYY-MM-DD HH:MM` (Geçmiş tarihlere randevu girilemez)

* **Oda Seçimi:** Aktif ve kullanıma uygun odalar listesinden seçilir.

* **Cihaz Seçimi (Opsiyonel):** Seans sırasında cihaz kullanılacaksa envanterden seçilir.

### Adım 3: Çakışma ve Durum Doğrulaması (Validation Logic)

Sistem randevuyu kaydetmeden önce sırasıyla aşağıdaki kuralları doğrular:

1. **Psikolog Zaman Çakışması:** Psikoloğun aynı zaman diliminde başka bir `SCHEDULED` randevusu var mı?

2. **Oda Zaman Çakışması:** Seçilen odanın aynı zaman diliminde başka bir randevuya tahsisi var mı?

3. **Cihaz Müsaitlik & Durum Kontrolü:**

   * Cihaz başka bir randevuda/rezervasyonda mı?

   * Cihazın durumu `Bakımda`, `Arızalı`, `Kalibrasyonda` veya `Kullanım Dışı` mı?

> **Hata Yönetimi:** Yukarıdaki koşullardan herhangi biri ihlal edilirse sistem `409 Conflict` veya `422 Unprocessable Entity` hatası döndürür ve işlem engellenir.

### Adım 4: Kayıt ve İletim

* Çakışma yoksa randevu `SCHEDULED` statüsü ile veritabanına işlenir.

* Sistem otomatik olarak audit log kaydı oluşturur: `EVENT: APPOINTMENT_CREATED`.

* PySide6 arayüzündeki takvim ekranı otomatik güncellenir.

## 5. Randevu İptal ve Güncelleme Senaryoları

### 5.1. Randevu İptali (Cancel)

* Sadece randevuyu oluşturan Psikolog veya yetkili müdür iptal edebilir.

* Randevu silinmez, statüsü `CANCELLED` olarak güncellenir.

* İptal edilen randevunun kullandığı oda ve cihaz anında yeniden kullanılabilir (müsait) hale gelir.

### 5.2. Randevu Zaman/Mekan Değişikliği (Reschedule)

* Zaman veya oda değişikliği talebinde Adım 3'teki tüm çakışma kontrolleri yeni zaman dilimi ve yeni kaynaklar için baştan çalıştırılır.