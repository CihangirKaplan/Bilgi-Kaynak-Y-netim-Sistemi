"""Birden çok uç modülünün kullandığı ortak sabitler (`server/sunucu.py` içinden ayrıldı)."""

# Cihazın bugünkü ETKİN durumu: bakım/kalibrasyon kaydı kayıtlı durumu kendiliğinden değiştirmediğinden, bugün planlı bir bakım ya da
# kalibrasyon aralığındaki cihaz "bakımda"/"kalibrasyonda" sayılır. Öncelik: kullanım dışı > arızalı > bakımda > kalibrasyonda.
# "Arızalı", kayıtlı durum sütununa DEĞİL, çözülmemiş (açık) arıza kaydına bakılarak belirlenir: tek doğruluk kaynağı arıza kaydıdır.
# (Sütun, bakımdaki cihaza arıza açılınca değişmediği ya da elle yanlış girildiği için güvenilir değildir.)
# Ana panel, Cihaz Envanteri ve yönetim paneli aynı tanımı kullanır; böylece iki ekranda aynı cihaz farklı durumda görünmez.
ETKIN_CIHAZ_DURUMU_SQL = """
    CASE
        WHEN c.durum = 'Kullanim_Disi' THEN 'Kullanim_Disi'
        WHEN EXISTS (
            SELECT 1 FROM cihaz_arizalari a
            WHERE a.cihaz_id = c.cihaz_id AND a.cozuldu_mu IS NOT TRUE
        ) THEN 'Arizali'
        WHEN c.durum = 'Bakimda' OR EXISTS (
            SELECT 1 FROM cihaz_bakimlari b
            WHERE b.cihaz_id = c.cihaz_id
              AND COALESCE(b.bakim_baslangic_tarihi, b.bakim_tarihi::date) <= CURRENT_DATE
              AND COALESCE(b.bakim_bitis_tarihi, b.bakim_tarihi::date) >= CURRENT_DATE
        ) THEN 'Bakimda'
        WHEN c.durum = 'Kalibrasyonda' OR EXISTS (
            SELECT 1 FROM cihaz_kalibrasyonlari k
            WHERE k.cihaz_id = c.cihaz_id
              AND k.kalibrasyon_baslangic_tarihi <= CURRENT_DATE
              AND k.kalibrasyon_bitis_tarihi >= CURRENT_DATE
        ) THEN 'Kalibrasyonda'
        WHEN c.durum = 'Arizali' THEN 'Kullanima_Hazir'
        ELSE c.durum::text
    END
"""


# Öğrenci listelerinde her öğrencinin türünü belirtmek için kullanılan etiketler.
OGRENCI_TUR_ETIKETLERI = {
    "GONULLU": "Gönüllü Öğrenci",
    "DANISMA_MASASI": "Danışma Masası Öğrencisi",
    "ASISTAN": "Asistan Öğrenci",
}


# Cihaz odası = aktif ve AKTİF bir psikologa atanmamış oda. Psikologlara atanan görüşme odaları cihaz rezervasyonuna kapalıdır;
# pasif psikolog odayı tutmaz (atama kaydı kalmış olsa bile), yani oda cihaz rezervasyonuna açılır.
CIHAZ_ODALARI_SORGUSU = (
    "SELECT o.oda_id, o.oda_adi FROM odalar o WHERE o.aktif_mi = TRUE "
    "AND NOT EXISTS (SELECT 1 FROM psikolog_odalar po JOIN kullanicilar k ON k.kullanici_id = po.kullanici_id "
    "JOIN roller r ON r.rol_id = k.rol_id "
    "WHERE po.oda_id = o.oda_id AND k.aktif_mi = TRUE AND UPPER(r.rol_adi) = 'PSIKOLOG') ORDER BY o.oda_adi"
)
