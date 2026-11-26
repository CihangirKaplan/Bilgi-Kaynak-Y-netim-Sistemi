"""Yönetim Raporları ve diğer rapor uçları (salt okunur). `server/sunucu.py` içinden ayrıldı."""
from fastapi import APIRouter, HTTPException, Query
import psycopg2

from server import rapor_bakim_plani, rapor_kullanim, rapor_ogrenci_faaliyet
from server.ortak_sabitler import ETKIN_CIHAZ_DURUMU_SQL, OGRENCI_TUR_ETIKETLERI
from server.vt_ayarlari import VT_AYARLARI
from server.vt_baglanti import vt_baglan
from server.yetki_baglama import yetkiyle_bagla


# TKYS_YONETIM_RAPORLARI_V1
from datetime import date as _yr_date
from datetime import timedelta as _yr_timedelta


def _yonetim_onceki_donem(baslangic, bitis):
    """Karşılaştırılacak önceki dönem (takvime göre; yöneticinin beklediği gibi):

    - Ayın 1'inden başlayıp aynı ay içinde biten dönem ("Bu Ay", "Geçen Ay"): geçen ayın aynı günleri;
      dönem ayın tamamıysa önceki ayın tamamı (31 Ekim'in karşılığı 30 Eylül'dür).
    - Tek gün ("Bugün") ya da pazartesi başlayan en fazla 7 günlük dönem ("Bu Hafta"): geçen haftanın aynı günleri
      (pazar ile cumartesi karşılaştırılmaz).
    - Diğer aralıklar: hemen önceki, aynı uzunluktaki aralık.
    """
    import calendar

    gun_sayisi = (bitis - baslangic).days + 1

    if baslangic.day == 1 and (bitis.year, bitis.month) == (baslangic.year, baslangic.month):
        onceki_ay_sonu = baslangic - _yr_timedelta(days=1)
        onceki_ay_basi = onceki_ay_sonu.replace(day=1)
        if bitis.day == calendar.monthrange(bitis.year, bitis.month)[1]:
            return onceki_ay_basi, onceki_ay_sonu
        return onceki_ay_basi, onceki_ay_basi.replace(day=min(bitis.day, onceki_ay_sonu.day))

    if gun_sayisi == 1 or (baslangic.weekday() == 0 and gun_sayisi <= 7):
        return baslangic - _yr_timedelta(days=7), bitis - _yr_timedelta(days=7)

    return baslangic - _yr_timedelta(days=gun_sayisi), baslangic - _yr_timedelta(days=1)


def yonetim_randevu_ozet(
    baslangic: _yr_date,
    bitis: _yr_date,
    kullanici_id: int | None = None,
):
    """Yetkili yöneticiler için dönemsel randevu istatistikleri."""

    if baslangic > bitis:
        raise HTTPException(
            status_code=422,
            detail="Başlangıç tarihi bitişten sonra olamaz."
        )

    gun_sayisi = (bitis - baslangic).days + 1

    if gun_sayisi > 366:
        raise HTTPException(
            status_code=422,
            detail="Tarih aralığı en fazla 366 gün olabilir."
        )

    onceki_baslangic, onceki_bitis = _yonetim_onceki_donem(baslangic, bitis)

    def donem_ozeti(cursor, ilk, son):
        cursor.execute("""
            SELECT
                COUNT(*) AS toplam,
                COUNT(*) FILTER (
                    WHERE durum = 'PLANLANDI'
                ) AS planlandi,
                COUNT(*) FILTER (
                    WHERE durum = 'TAMAMLANDI'
                ) AS tamamlandi,
                COUNT(*) FILTER (
                    WHERE durum = 'GELMEDI'
                ) AS gelmedi,
                COUNT(*) FILTER (
                    WHERE durum = 'IPTAL_EDILDI'
                ) AS iptal_edildi,
                COUNT(*) FILTER (
                    WHERE durum = 'PLANLANDI' AND baslangic_zamani < NOW()
                ) AS sonucu_girilmemis
            FROM randevular
            WHERE baslangic_zamani >= %s::date
              AND baslangic_zamani < (%s::date + INTERVAL '1 day')
        """, (ilk, son))

        sonuc = cursor.fetchone()

        return dict(zip(
            (
                "toplam", "planlandi", "tamamlandi",
                "gelmedi", "iptal_edildi", "sonucu_girilmemis"
            ),
            (int(deger) for deger in sonuc)
        ))

    conn = None
    cursor = None

    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        mevcut = donem_ozeti(cursor, baslangic, bitis)
        onceki = donem_ozeti(
            cursor, onceki_baslangic, onceki_bitis
        )

        cursor.execute("""
            SELECT
                baslangic_zamani::date AS gun,
                COUNT(*) AS sayi
            FROM randevular
            WHERE baslangic_zamani >= %s::date
              AND baslangic_zamani < (%s::date + INTERVAL '1 day')
            GROUP BY baslangic_zamani::date
            ORDER BY gun
        """, (baslangic, bitis))

        gunluk_sayilar = {
            gun: int(sayi)
            for gun, sayi in cursor.fetchall()
        }

        gunluk = [
            {
                "tarih": (
                    baslangic + _yr_timedelta(days=i)
                ).isoformat(),
                "sayi": gunluk_sayilar.get(
                    baslangic + _yr_timedelta(days=i), 0
                )
            }
            for i in range(gun_sayisi)
        ]

        eski_toplam = onceki["toplam"]

        degisim = (
            round(
                (mevcut["toplam"] - eski_toplam)
                / eski_toplam * 100,
                1
            )
            if eski_toplam > 0 else None
        )

        return {
            "donem": {
                "baslangic": baslangic.isoformat(),
                "bitis": bitis.isoformat()
            },
            "onceki_donem": {
                "baslangic": onceki_baslangic.isoformat(),
                "bitis": onceki_bitis.isoformat()
            },
            "ozet": mevcut,
            "onceki_ozet": onceki,
            "toplam_degisim_yuzde": degisim,
            "gunluk": gunluk
        }

    except psycopg2.Error:
        raise HTTPException(
            status_code=500,
            detail="Rapor verileri alınamadı."
        )
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


# TKYS_YONETIM_CIHAZ_RAPORLARI_V1

def yonetim_cihaz_ozet(
    baslangic: _yr_date,
    bitis: _yr_date,
    kullanici_id: int | None = None,
):
    """Cihaz işlemlerinin dönemsel kayıt istatistikleri."""

    if baslangic > bitis:
        raise HTTPException(
            status_code=422,
            detail="Başlangıç tarihi bitişten sonra olamaz."
        )

    gun_sayisi = (bitis - baslangic).days + 1

    if gun_sayisi > 366:
        raise HTTPException(
            status_code=422,
            detail="Tarih aralığı en fazla 366 gün olabilir."
        )

    onceki_baslangic, onceki_bitis = _yonetim_onceki_donem(baslangic, bitis)

    # Sabit tablo/sütun eşleştirmeleri:
    # Kullanıcı girdisi SQL tablo veya sütun adına eklenmez.
    # Sayım kuralları Cihaz Raporları ekranıyla aynıdır (iki ekran aynı dönem için aynı sayıyı göstermelidir):
    # - kalibrasyon, kaydın girildiği güne değil kalibrasyonun gerçek başlangıç gününe göre sayılır
    #   (eski kayıtlarda tarih boşsa işlem tarihinin günü kullanılır);
    # - iptal edilen rezervasyonlar sayılmaz.
    kaynaklar = {
        "bakim": ("cihaz_bakimlari", "bakim_tarihi", ""),
        "kalibrasyon": (
            "cihaz_kalibrasyonlari",
            "COALESCE(kalibrasyon_baslangic_tarihi, islem_tarihi::date)",
            "",
        ),
        "ariza": ("cihaz_arizalari", "bildirim_tarihi", ""),
        "rezervasyon": (
            "cihaz_rezervasyonlari", "baslangic_zamani",
            "AND iptal_edildi_mi IS NOT TRUE",
        ),
    }

    conn = None
    cursor = None

    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        def ozet_hesapla(ilk, son):
            sayilar = {}

            for kod, (tablo, tarih_alani, ek_kosul) in kaynaklar.items():
                cursor.execute(
                    f"""
                    SELECT COUNT(*)
                    FROM {tablo}
                    WHERE {tarih_alani} >= %s::date
                      AND {tarih_alani}
                          < (%s::date + INTERVAL '1 day')
                      {ek_kosul}
                    """,
                    (ilk, son),
                )

                sayilar[kod] = int(cursor.fetchone()[0])

            return sayilar

        mevcut = ozet_hesapla(baslangic, bitis)
        onceki = ozet_hesapla(
            onceki_baslangic, onceki_bitis
        )

        degisimler = {}

        for kod, sayi in mevcut.items():
            eski = onceki[kod]

            degisimler[kod] = (
                round((sayi - eski) / eski * 100, 1)
                if eski > 0 else None
            )

        return {
            "donem": {
                "baslangic": baslangic.isoformat(),
                "bitis": bitis.isoformat(),
            },
            "onceki_donem": {
                "baslangic": onceki_baslangic.isoformat(),
                "bitis": onceki_bitis.isoformat(),
            },
            "ozet": mevcut,
            "onceki_ozet": onceki,
            "degisim_yuzdeleri": degisimler,
        }

    except psycopg2.Error:
        raise HTTPException(
            status_code=500,
            detail="Cihaz rapor verileri alınamadı."
        )
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


# TKYS_YONETIM_OGRENCI_RAPORLARI_V1

def yonetim_ogrenci_ozet(
    baslangic: _yr_date,
    bitis: _yr_date,
    kullanici_id: int | None = None,
):
    """Öğrenci faaliyetlerinin dönemsel istatistikleri."""

    if baslangic > bitis:
        raise HTTPException(
            status_code=422,
            detail="Başlangıç tarihi bitişten sonra olamaz."
        )

    gun_sayisi = (bitis - baslangic).days + 1

    if gun_sayisi > 366:
        raise HTTPException(
            status_code=422,
            detail="Tarih aralığı en fazla 366 gün olabilir."
        )

    onceki_baslangic, onceki_bitis = _yonetim_onceki_donem(baslangic, bitis)

    conn = None
    cursor = None

    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        # Öğrenci mevcudu tarihsel değil, güncel durumdur.
        cursor.execute("""
            SELECT
                COUNT(*),
                COUNT(*) FILTER (WHERE aktif_mi IS TRUE)
            FROM ogrenciler
        """)
        toplam_ogrenci, aktif_ogrenci = cursor.fetchone()

        def donem_hesapla(ilk, son):
            cursor.execute("""
                SELECT
                    COUNT(*) AS kayit_sayisi,
                    COALESCE(SUM(adet), 0) AS faaliyet_miktari,
                    COALESCE(SUM(adet * kayit_puani), 0)
                        AS toplam_puan,
                    COUNT(DISTINCT ogrenci_id)
                        AS faaliyet_yapan_ogrenci
                FROM ogrenci_faaliyet_takip
                WHERE faaliyet_tarihi >= %s
                  AND faaliyet_tarihi <= %s
            """, (ilk, son))

            kayit = cursor.fetchone()

            alanlar = (
                "kayit_sayisi",
                "faaliyet_miktari",
                "toplam_puan",
                "faaliyet_yapan_ogrenci",
            )

            return {
                alan: int(deger)
                for alan, deger in zip(alanlar, kayit)
            }

        mevcut = donem_hesapla(baslangic, bitis)
        onceki = donem_hesapla(
            onceki_baslangic, onceki_bitis
        )

        cursor.execute("""
            SELECT
                f.faaliyet_adi,
                COUNT(t.takip_id) AS kayit_sayisi,
                COALESCE(SUM(t.adet), 0) AS miktar,
                COALESCE(SUM(
                    t.adet * t.kayit_puani
                ), 0) AS toplam_puan
            FROM ogrenci_faaliyet_takip t
            JOIN faaliyetler f
              ON f.faaliyet_id = t.faaliyet_id
            WHERE t.faaliyet_tarihi >= %s
              AND t.faaliyet_tarihi <= %s
            GROUP BY f.faaliyet_id, f.faaliyet_adi
            ORDER BY toplam_puan DESC, f.faaliyet_adi
        """, (baslangic, bitis))

        faaliyetler = [
            {
                "faaliyet": ad,
                "kayit_sayisi": int(kayit),
                "miktar": int(miktar),
                "toplam_puan": int(puan),
            }
            for ad, kayit, miktar, puan in cursor.fetchall()
        ]

        degisimler = {}
        for alan in (
            "kayit_sayisi",
            "faaliyet_miktari",
            "toplam_puan",
            "faaliyet_yapan_ogrenci",
        ):
            eski = onceki[alan]
            degisimler[alan] = (
                round((mevcut[alan] - eski) / eski * 100, 1)
                if eski > 0 else None
            )

        return {
            "donem": {
                "baslangic": baslangic.isoformat(),
                "bitis": bitis.isoformat(),
            },
            "onceki_donem": {
                "baslangic": onceki_baslangic.isoformat(),
                "bitis": onceki_bitis.isoformat(),
            },
            "guncel_ogrenci": {
                "toplam": int(toplam_ogrenci),
                "aktif": int(aktif_ogrenci),
            },
            "ozet": mevcut,
            "onceki_ozet": onceki,
            "degisim_yuzdeleri": degisimler,
            "faaliyet_dagilimi": faaliyetler,
        }

    except psycopg2.Error:
        raise HTTPException(
            status_code=500,
            detail="Öğrenci rapor verileri alınamadı."
        )
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


# TKYS_YONETIM_PROJE_ETKINLIK_V1

def yonetim_proje_etkinlik_ozet(
    baslangic: _yr_date,
    bitis: _yr_date,
    kullanici_id: int | None = None,
):
    """Proje türü rezervasyonları ve oda etkinliği kayıtları.

    Rezervasyonlar gerçekleşmiş deney olarak yorumlanmaz.
    Etkinlik katılımcıları kayıtlı sayılardır.
    """

    if baslangic > bitis:
        raise HTTPException(
            status_code=422,
            detail="Başlangıç tarihi bitişten sonra olamaz."
        )

    gun_sayisi = (bitis - baslangic).days + 1
    if gun_sayisi > 366:
        raise HTTPException(
            status_code=422,
            detail="Tarih aralığı en fazla 366 gün olabilir."
        )

    onceki_baslangic, onceki_bitis = _yonetim_onceki_donem(baslangic, bitis)

    conn = None
    cursor = None

    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        def donem_hesapla(ilk, son):
            cursor.execute("""
                SELECT
                    COUNT(*),
                    COUNT(*) FILTER (
                        WHERE iptal_edildi_mi IS NOT TRUE
                    ),
                    COUNT(*) FILTER (
                        WHERE iptal_edildi_mi IS TRUE
                    )
                FROM cihaz_rezervasyonlari
                WHERE baslangic_zamani >= %s::date
                  AND baslangic_zamani
                      < (%s::date + INTERVAL '1 day')
            """, (ilk, son))

            toplam, iptal_edilmemis, iptal = cursor.fetchone()

            cursor.execute("""
                SELECT
                    COUNT(*),
                    COUNT(*) FILTER (
                        WHERE iptal_edildi_mi IS NOT TRUE
                    ),
                    COALESCE(SUM(katilimci_sayisi) FILTER (
                        WHERE iptal_edildi_mi IS NOT TRUE
                    ), 0)
                FROM oda_etkinlikleri e
                WHERE EXISTS (
                    SELECT 1
                    FROM oda_etkinlik_gunleri g
                    WHERE g.etkinlik_id = e.etkinlik_id
                      AND g.baslangic_zamani >= %s::date
                      AND g.baslangic_zamani
                          < (%s::date + INTERVAL '1 day')
                )
            """, (ilk, son))

            etkinlik_toplam, etkinlik_iptal_edilmemis, katilimci = (
                cursor.fetchone()
            )

            return {
                "rezervasyon_toplam": int(toplam),
                "rezervasyon_iptal_edilmemis": int(iptal_edilmemis),
                "rezervasyon_iptal": int(iptal),
                "etkinlik_toplam": int(etkinlik_toplam),
                "etkinlik_iptal_edilmemis": int(
                    etkinlik_iptal_edilmemis
                ),
                "kayitli_katilimci_toplami": int(katilimci),
            }

        mevcut = donem_hesapla(baslangic, bitis)
        onceki = donem_hesapla(
            onceki_baslangic, onceki_bitis
        )

        cursor.execute("""
            SELECT
                COALESCE(
                    NULLIF(BTRIM(proje_turu), ''),
                    'Belirtilmemiş'
                ) AS tur,
                COUNT(*) AS sayi
            FROM cihaz_rezervasyonlari
            WHERE baslangic_zamani >= %s::date
              AND baslangic_zamani
                  < (%s::date + INTERVAL '1 day')
              AND iptal_edildi_mi IS NOT TRUE
            GROUP BY 1
            ORDER BY sayi DESC, tur
        """, (baslangic, bitis))

        proje_turleri = [
            {"tur": tur, "rezervasyon_sayisi": int(sayi)}
            for tur, sayi in cursor.fetchall()
        ]

        degisimler = {}
        for alan, deger in mevcut.items():
            eski = onceki[alan]
            degisimler[alan] = (
                round((deger - eski) / eski * 100, 1)
                if eski > 0 else None
            )

        return {
            "donem": {
                "baslangic": baslangic.isoformat(),
                "bitis": bitis.isoformat(),
            },
            "onceki_donem": {
                "baslangic": onceki_baslangic.isoformat(),
                "bitis": onceki_bitis.isoformat(),
            },
            "ozet": mevcut,
            "onceki_ozet": onceki,
            "degisim_yuzdeleri": degisimler,
            "proje_turu_dagilimi": proje_turleri,
            "aciklama": (
                "Rezervasyonlar tamamlanan deney sayısını "
                "göstermez. Katılımcı sayıları etkinlik "
                "kayıtlarına girilmiş değerlerdir."
            ),
        }

    except psycopg2.Error:
        raise HTTPException(
            status_code=500,
            detail="Proje ve etkinlik raporları alınamadı."
        )
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


# TKYS_YONETIM_KULLANIM_V1

def yonetim_kullanim_ozet(
    baslangic: _yr_date,
    bitis: _yr_date,
    kullanici_id: int | None = None,
):
    """Oda ve cihaz KULLANIM raporu (kayıt sayısı değil, ne kadar kullanıldı).

    Saatler dönem sınırlarına kırpılarak hesaplanır: dönemi aşan bir rezervasyon/etkinlik yalnızca dönem içindeki kısmı kadar
    sayılır. İptal edilen randevu, rezervasyon ve etkinlikler sayılmaz. Oda toplamı = randevu + cihaz rezervasyonu (odası seçilen) +
    oda etkinliği saatleri. Saatler planlanan süreyi gösterir (gerçekleşen kullanım süresi ayrıca ölçülmez).
    """
    if baslangic > bitis:
        raise HTTPException(
            status_code=422,
            detail="Başlangıç tarihi bitişten sonra olamaz."
        )
    if (bitis - baslangic).days + 1 > 366:
        raise HTTPException(
            status_code=422,
            detail="Tarih aralığı en fazla 366 gün olabilir."
        )

    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        odalar = rapor_kullanim.oda_kullanimi(cursor, baslangic, bitis)
        cihazlar = [
            {k: v for k, v in c.items() if k != "son_kullanim"}
            | {"ariza_sayisi": 0}
            for c in rapor_kullanim.cihaz_rezervasyonlari(cursor, baslangic, bitis)["cihazlar"]
        ]
        cursor.execute(
            "SELECT cihaz_id, COUNT(*) FROM cihaz_arizalari "
            "WHERE bildirim_tarihi >= %s::date AND bildirim_tarihi < (%s::date + INTERVAL '1 day') GROUP BY cihaz_id;",
            (baslangic, bitis),
        )
        arizalar = {k[0]: int(k[1]) for k in cursor.fetchall()}
        for c in cihazlar:
            c["ariza_sayisi"] = arizalar.get(c["cihaz_id"], 0)

        return {
            "donem": {"baslangic": baslangic.isoformat(), "bitis": bitis.isoformat()},
            "odalar": odalar,
            "cihazlar": cihazlar,
            "ozet": {
                "oda_toplam_saat": round(sum(o["toplam_saat"] for o in odalar), 1),
                "kullanilan_oda_sayisi": sum(1 for o in odalar if o["toplam_saat"] > 0),
                "kullanilmayan_oda_sayisi": sum(1 for o in odalar if o["aktif_mi"] and o["toplam_saat"] == 0),
                "cihaz_toplam_saat": round(sum(c["rezervasyon_saati"] for c in cihazlar), 1),
                "kullanilan_cihaz_sayisi": sum(1 for c in cihazlar if c["rezervasyon_sayisi"] > 0),
                "kullanilmayan_cihaz_sayisi": sum(1 for c in cihazlar if c["rezervasyon_sayisi"] == 0),
            },
            "aciklama": (
                "Saatler planlanan süreyi gösterir (iptaller hariç, dönem sınırlarına kırpılmış). "
                "Gerçekleşen kullanım süresi ayrıca ölçülmez."
            ),
        }

    except psycopg2.Error:
        raise HTTPException(
            status_code=500,
            detail="Kullanım raporu alınamadı."
        )
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


# TKYS_DETAYLI_RAPORLAR_V1

def _rapor_donemi_dogrula(baslangic, bitis):
    if baslangic > bitis:
        raise HTTPException(status_code=422, detail="Başlangıç tarihi bitişten sonra olamaz.")
    if (bitis - baslangic).days + 1 > 366:
        raise HTTPException(status_code=422, detail="Tarih aralığı en fazla 366 gün olabilir.")


def cihaz_rezervasyon_raporu(
    baslangic: _yr_date,
    bitis: _yr_date,
    cihaz_id: int | None = None,
    proje_turu: str | None = Query(None, max_length=50),
    detay: bool = False,
    kullanici_id: int | None = None,
):
    """Cihaz Rezervasyon Raporu: cihaz, proje türü ve bölüm bazlı rezervasyon sayısı ve planlanan kullanım saati.

    İptal edilen rezervasyonlar kullanım sayılmaz (ayrıca gösterilir). Saatler dönem sınırlarına kırpılır. detay=true ise tek tek
    rezervasyonlar da döner (Excel için; iptaller 'durum' sütunuyla ayrılır)."""
    _rapor_donemi_dogrula(baslangic, bitis)
    if cihaz_id is not None and cihaz_id <= 0:
        raise HTTPException(status_code=422, detail="Geçerli bir cihaz seçilmelidir.")

    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        veri = rapor_kullanim.cihaz_rezervasyonlari(cursor, baslangic, bitis, cihaz_id, proje_turu)
        cihazlar = veri["cihazlar"]
        kullanilan = [c for c in cihazlar if c["rezervasyon_sayisi"] > 0]
        toplam_rezervasyon = sum(c["rezervasyon_sayisi"] for c in cihazlar)
        toplam_saat = round(sum(c["rezervasyon_saati"] for c in cihazlar), 1)
        sonuc = {
            "donem": {"baslangic": baslangic.isoformat(), "bitis": bitis.isoformat()},
            "ozet": {
                "rezervasyon_sayisi": toplam_rezervasyon,
                "iptal_edilen_rezervasyon": sum(c["iptal_edilen_rezervasyon"] for c in cihazlar),
                "toplam_saat": toplam_saat,
                "ortalama_sure_saat": round(toplam_saat / toplam_rezervasyon, 1) if toplam_rezervasyon else None,
                "kullanilan_cihaz_sayisi": len(kullanilan),
                "kullanilmayan_cihaz_sayisi": len(cihazlar) - len(kullanilan),
            },
            "cihazlar": cihazlar,
            "proje_turleri": veri["proje_turleri"],
            "bolumler": veri["bolumler"],
            "aciklama": (
                "Saatler planlanan süreyi gösterir (iptaller hariç, dönem sınırlarına kırpılmış). "
                "Gerçekleşen kullanım süresi ayrıca ölçülmez."
            ),
        }
        if detay:
            sonuc["rezervasyonlar"] = [
                {**r, "baslangic_zamani": r["baslangic_zamani"].isoformat(), "bitis_zamani": r["bitis_zamani"].isoformat()}
                for r in rapor_kullanim.cihaz_rezervasyon_detaylari(cursor, baslangic, bitis, cihaz_id, proje_turu)
            ]
        return sonuc
    except psycopg2.Error:
        raise HTTPException(status_code=500, detail="Cihaz rezervasyon raporu alınamadı.")
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


def oda_kullanim_raporu(
    baslangic: _yr_date,
    bitis: _yr_date,
    oda_id: int | None = None,
    detay: bool = False,
    kullanici_id: int | None = None,
):
    """Oda Kullanım Raporu: oda bazlı randevu, cihaz rezervasyonu ve etkinlik saatleri, mesai doluluk oranı ve haftanın günlerine
    göre dağılım. Mesai doluluk oranı = toplam saat / (hafta içi gün sayısı x günlük 8 saat) varsayımıyla hesaplanır; hafta sonu
    kullanımı oranı %100'ün üzerine çıkarabilir. detay=true ise tek tek kayıtlar da döner (Excel için)."""
    _rapor_donemi_dogrula(baslangic, bitis)
    if oda_id is not None and oda_id <= 0:
        raise HTTPException(status_code=422, detail="Geçerli bir oda seçilmelidir.")

    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        odalar = rapor_kullanim.oda_kullanimi(cursor, baslangic, bitis, oda_id)
        olaylar = rapor_kullanim.oda_kullanim_olaylari(cursor, baslangic, bitis, oda_id)
        cursor.execute("SELECT oda_id, oda_adi FROM odalar WHERE aktif_mi IS TRUE ORDER BY oda_adi, oda_id;")
        secenekler = [{"oda_id": k[0], "oda_adi": k[1]} for k in cursor.fetchall()]

        toplam = round(sum(o["toplam_saat"] for o in odalar), 1)
        is_gunu = rapor_kullanim.is_gunu_sayisi(baslangic, bitis)
        kapasite = is_gunu * rapor_kullanim.GUNLUK_MESAI_SAATI * len([o for o in odalar if o["aktif_mi"]])
        sonuc = {
            "donem": {"baslangic": baslangic.isoformat(), "bitis": bitis.isoformat()},
            "varsayim": {"is_gunu_sayisi": is_gunu, "gunluk_mesai_saati": rapor_kullanim.GUNLUK_MESAI_SAATI},
            "ozet": {
                "toplam_saat": toplam,
                "randevu_saati": round(sum(o["randevu_saati"] for o in odalar), 1),
                "cihaz_rezervasyon_saati": round(sum(o["cihaz_rezervasyon_saati"] for o in odalar), 1),
                "etkinlik_saati": round(sum(o["etkinlik_saati"] for o in odalar), 1),
                "kullanilan_oda_sayisi": sum(1 for o in odalar if o["toplam_saat"] > 0),
                "kullanilmayan_oda_sayisi": sum(1 for o in odalar if o["aktif_mi"] and o["toplam_saat"] == 0),
                "mesai_doluluk_orani": round(toplam / kapasite, 4) if kapasite else None,
            },
            "odalar": odalar,
            "gun_dagilimi": rapor_kullanim.gun_dagilimi(olaylar),
            "oda_secenekleri": secenekler,
            "aciklama": (
                "Saatler planlanan süreyi gösterir (iptaller hariç, dönem sınırlarına kırpılmış). Mesai doluluk oranı, hafta içi günlük "
                f"{rapor_kullanim.GUNLUK_MESAI_SAATI} saat varsayımıyla hesaplanır."
            ),
        }
        if detay:
            sonuc["kayitlar"] = [
                {**o, "baslangic_zamani": o["baslangic_zamani"].isoformat(), "bitis_zamani": o["bitis_zamani"].isoformat()}
                for o in olaylar
            ]
        return sonuc
    except psycopg2.Error:
        raise HTTPException(status_code=500, detail="Oda kullanım raporu alınamadı.")
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


def yetki_raporu_getir(
    rol_id: int | None = None,
    durum: str | None = Query(None, pattern="^(aktif|pasif)$"),
    detay: bool = False,
    kullanici_id: int | None = None,
):
    """Yetki Raporu: kullanıcılar, rolleri, son giriş zamanları, kilit/pasiflik durumu ve rollere göre izin sayıları. detay=true ise
    rol-izin matrisi de döner (Excel için). Parola ya da parola özeti hiçbir zaman dönmez."""
    if rol_id is not None and rol_id <= 0:
        raise HTTPException(status_code=422, detail="Geçerli bir rol seçilmelidir.")
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        return rapor_kullanim.yetki_raporu(cursor, rol_id, durum, matris=detay)
    except psycopg2.Error:
        raise HTTPException(status_code=500, detail="Yetki raporu alınamadı.")
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


def ogrenci_raporu_getir(
    tur: str | None = None,
    durum: str | None = Query(None, pattern="^(aktif|pasif)$"),
    kullanici_id: int | None = None,
):
    """Öğrenci Raporu: tür ve bölüm dağılımı, aktif/pasif, Gönüllü öğrenci kayıt saklama süresi (pasife alındıktan 2 yıl) durumu, faaliyetsiz aktif
    öğrenciler ve öğrenci listesi. Telefon raporda yer almaz."""
    if tur is not None and tur not in OGRENCI_TUR_ETIKETLERI:
        raise HTTPException(status_code=422, detail="Geçersiz öğrenci türü.")
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        return rapor_ogrenci_faaliyet.ogrenci_raporu(cursor, OGRENCI_TUR_ETIKETLERI, tur, durum)
    except psycopg2.Error:
        raise HTTPException(status_code=500, detail="Öğrenci raporu alınamadı.")
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


def faaliyet_raporu_getir(
    baslangic: _yr_date,
    bitis: _yr_date,
    faaliyet_id: int | None = None,
    detay: bool = False,
    kullanici_id: int | None = None,
):
    """Faaliyet Raporu: dönemdeki (faaliyet tarihi) kayıtların faaliyet türü, birim ve öğrenci türü dağılımı ve puanlar. Puan = adet x kaydın girildiği andaki puan (Puan Raporu ile aynı). detay=true ise tek tek kayıtlar da döner."""
    _rapor_donemi_dogrula(baslangic, bitis)
    if faaliyet_id is not None and faaliyet_id <= 0:
        raise HTTPException(status_code=422, detail="Geçerli bir faaliyet seçilmelidir.")
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        sonuc = rapor_ogrenci_faaliyet.faaliyet_raporu(
            cursor, OGRENCI_TUR_ETIKETLERI, baslangic, bitis, faaliyet_id, detay,
        )
        sonuc["donem"] = {"baslangic": baslangic.isoformat(), "bitis": bitis.isoformat()}
        return sonuc
    except psycopg2.Error:
        raise HTTPException(status_code=500, detail="Faaliyet raporu alınamadı.")
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


def bakim_plani_raporu_getir(
    cihaz_id: int | None = None,
    tur: str | None = Query(None, pattern="^(bakim|kalibrasyon)$"),
    durum: str | None = Query(None, pattern="^(gecikmis|yaklasiyor|planli|pasif)$"),
    kullanici_id: int | None = None,
):
    """Geciken Bakım Planı Raporu: bugünkü durum. Geciken (sonraki görev tarihi geçmiş), yaklaşan ve planlı planlar, cihaz ve plan türü
    bazlı özet, son yapılan bakım/kalibrasyon ve planı olmayan cihazlar. Durum kuralı Bakım Planları ekranıyla aynıdır."""
    if cihaz_id is not None and cihaz_id <= 0:
        raise HTTPException(status_code=422, detail="Geçerli bir cihaz seçilmelidir.")
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        return rapor_bakim_plani.bakim_plani_raporu(cursor, cihaz_id, tur, durum)
    except psycopg2.Error:
        raise HTTPException(status_code=500, detail="Bakım planı raporu alınamadı.")
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


# TKYS_YONETIM_GUNLUK_OPERASYON_V1

def yonetim_bugun_merkezde(
    gun: _yr_date | None = None,
    kullanici_id: int | None = None,
):
    """Günlük merkez özeti ve zamanlı operasyon kayıtları."""

    hedef_gun = gun or _yr_date.today()

    # Günlük ekranda tarih ileriye taşınsa da API yazma yapmaz.
    durum_adlari = (
        "Kullanima_Hazir",
        "Rezerve",
        "Kullanimda",
        "Arizali",
        "Bakimda",
        "Kalibrasyonda",
        "Kullanim_Disi",
    )

    baglanti = None
    imlec = None

    try:
        baglanti = vt_baglan(VT_AYARLARI)
        imlec = baglanti.cursor()

        def say(sql):
            imlec.execute(sql, (hedef_gun, hedef_gun))
            return int(imlec.fetchone()[0])

        randevu = say("""
            SELECT COUNT(*)
            FROM randevular
            WHERE baslangic_zamani >= %s::date
              AND baslangic_zamani <
                  (%s::date + INTERVAL '1 day')
        """)

        danisma = say("""
            SELECT COUNT(*)
            FROM danisma_masasi_oturumlari
            WHERE baslangic_zamani >= %s::date
              AND baslangic_zamani <
                  (%s::date + INTERVAL '1 day')
        """)

        faaliyet = say("""
            SELECT COUNT(*)
            FROM ogrenci_faaliyet_takip
            WHERE olusturulma_tarihi >= %s::date
              AND olusturulma_tarihi <
                  (%s::date + INTERVAL '1 day')
        """)

        ariza = say("""
            SELECT COUNT(*)
            FROM cihaz_arizalari
            WHERE bildirim_tarihi >= %s::date
              AND bildirim_tarihi <
                  (%s::date + INTERVAL '1 day')
        """)

        etkinlik = say("""
            SELECT COUNT(DISTINCT e.etkinlik_id)
            FROM oda_etkinlikleri e
            JOIN oda_etkinlik_gunleri g
              ON g.etkinlik_id = e.etkinlik_id
            WHERE g.baslangic_zamani >= %s::date
              AND g.baslangic_zamani <
                  (%s::date + INTERVAL '1 day')
              AND e.iptal_edildi_mi IS NOT TRUE
        """)

        # "Şu anki durum": bakım/kalibrasyon aralığı dahil etkin durum (Ana Panel ile aynı tanım). Hazır cihazlar ayrıca bugünkü rezervasyonlara göre
        # bölünür: şu an rezervasyonda olan "Kullanimda", henüz kullanılmayan ama bugün sonrası rezervasyonu olan "Rezerve", kalanı "Kullanima_Hazir".
        # (Bu iki durum artık elle seçilemez; hesaplanır.)
        imlec.execute(
            "SELECT etkin, simdi_kullanimda, bugun_rezerveli, COUNT(*) FROM (SELECT " + ETKIN_CIHAZ_DURUMU_SQL + " AS etkin, "
            "EXISTS (SELECT 1 FROM cihaz_rezervasyonlari r WHERE r.cihaz_id = c.cihaz_id AND r.iptal_edildi_mi = FALSE "
            "        AND r.baslangic_zamani <= NOW() AND r.bitis_zamani > NOW()) AS simdi_kullanimda, "
            "EXISTS (SELECT 1 FROM cihaz_rezervasyonlari r WHERE r.cihaz_id = c.cihaz_id AND r.iptal_edildi_mi = FALSE "
            "        AND r.baslangic_zamani > NOW() AND r.baslangic_zamani < CURRENT_DATE + 1) AS bugun_rezerveli "
            "FROM cihazlar c) t GROUP BY etkin, simdi_kullanimda, bugun_rezerveli"
        )
        cihaz_durumlari = {ad: 0 for ad in durum_adlari}
        for etkin, simdi_kullanimda, bugun_rezerveli, adet in imlec.fetchall():
            if etkin == "Kullanima_Hazir":
                etkin = "Kullanimda" if simdi_kullanimda else ("Rezerve" if bugun_rezerveli else "Kullanima_Hazir")
            cihaz_durumlari[etkin] = cihaz_durumlari.get(etkin, 0) + int(adet)

        # Yalnızca gerçekten zaman damgası bulunan işlemler
        # günlük olay akışına alınır. Kişisel bilgiler dönülmez.
        kaynaklar = (
            (
                "danisma",
                "Danışma masası görevi başladı",
                """
                SELECT oturum_id, baslangic_zamani
                FROM danisma_masasi_oturumlari
                WHERE baslangic_zamani >= %s::date
                  AND baslangic_zamani <
                      (%s::date + INTERVAL '1 day')
                ORDER BY baslangic_zamani DESC
                LIMIT 100
                """,
            ),
            (
                "ogrenci",
                "Öğrenci faaliyet kaydı girildi",
                """
                SELECT takip_id, olusturulma_tarihi
                FROM ogrenci_faaliyet_takip
                WHERE olusturulma_tarihi >= %s::date
                  AND olusturulma_tarihi <
                      (%s::date + INTERVAL '1 day')
                ORDER BY olusturulma_tarihi DESC
                LIMIT 100
                """,
            ),
            (
                "ariza",
                "Cihaz arızası bildirildi",
                """
                SELECT ariza_id, bildirim_tarihi
                FROM cihaz_arizalari
                WHERE bildirim_tarihi >= %s::date
                  AND bildirim_tarihi <
                      (%s::date + INTERVAL '1 day')
                ORDER BY bildirim_tarihi DESC
                LIMIT 100
                """,
            ),
            (
                "kalibrasyon",
                "Cihaz kalibrasyon işlemi kaydedildi",
                """
                SELECT kalibrasyon_id, islem_tarihi
                FROM cihaz_kalibrasyonlari
                WHERE islem_tarihi >= %s::date
                  AND islem_tarihi <
                      (%s::date + INTERVAL '1 day')
                ORDER BY islem_tarihi DESC
                LIMIT 100
                """,
            ),
            (
                "randevu",
                "Yeni randevu oluşturuldu",
                """
                SELECT randevu_id, olusturulma_tarihi
                FROM randevular
                WHERE olusturulma_tarihi >= %s::date
                  AND olusturulma_tarihi <
                      (%s::date + INTERVAL '1 day')
                ORDER BY olusturulma_tarihi DESC
                LIMIT 100
                """,
            ),
        )

        olaylar = []

        for tur, baslik, sorgu in kaynaklar:
            imlec.execute(sorgu, (hedef_gun, hedef_gun))

            for kayit_id, zaman in imlec.fetchall():
                if zaman is None:
                    continue

                olaylar.append({
                    "tur": tur,
                    "baslik": baslik,
                    "alt_bilgi": (
                        f"Randevu · No: {kayit_id}"
                        if tur == "randevu" else None
                    ),
                    "kayit_id": int(kayit_id),
                    "zaman": zaman.isoformat(),
                })

        # TKYS_GUNLUK_BAKIM_GRUPLAMA_V1
        # Bakım kayıtları cihaz bazında özetlenir.
        # bakim_tarihi saatinin gerçek kayıt saati olduğu
        # doğrulanmadığı için bu özet saatli olay sayılmaz.
        imlec.execute("""
            SELECT
                b.cihaz_id,
                COALESCE(c.cihaz_adi, 'Bilinmeyen cihaz'),
                COUNT(*)
            FROM cihaz_bakimlari b
            LEFT JOIN cihazlar c ON c.cihaz_id = b.cihaz_id
            WHERE b.bakim_tarihi >= %s::date
              AND b.bakim_tarihi < (%s::date + INTERVAL '1 day')
            GROUP BY b.cihaz_id, c.cihaz_adi
            ORDER BY COUNT(*) DESC, b.cihaz_id
        """, (hedef_gun, hedef_gun))

        for cihaz_id, cihaz_adi, adet in imlec.fetchall():
            olaylar.append({
                "tur": "bakim",
                "baslik": f"{cihaz_adi} · {adet} bakım kaydı",
                "kayit_id": None,
                "zaman": hedef_gun.isoformat() + "T00:00:00",
                "saat_belirsiz": True,
                "toplu_kayit": True,
                "kayit_sayisi": int(adet),
            })


        # TKYS_GUNLUK_EK_OLAYLAR_V2
        # Gerçekleşen işlemler ile planlananlar ayrı işaretlenir.
        ek_kaynaklar = [
            (
                "danisma_bitis",
                "Danışma masası görevi tamamlandı",
                """
                SELECT oturum_id, bitis_zamani
                FROM danisma_masasi_oturumlari
                WHERE bitis_zamani >= %s::date
                  AND bitis_zamani < (%s::date + INTERVAL '1 day')
                ORDER BY bitis_zamani DESC LIMIT 100
                """,
                False,
            ),
            (
                "ariza_cozum",
                "Cihaz arızası çözüldü",
                """
                SELECT ariza_id, cozum_tarihi
                FROM cihaz_arizalari
                WHERE cozuldu_mu IS TRUE
                  AND cozum_tarihi >= %s::date
                  AND cozum_tarihi < (%s::date + INTERVAL '1 day')
                ORDER BY cozum_tarihi DESC LIMIT 100
                """,
                False,
            ),
            (
                "oda_etkinligi",
                "Oda etkinliği planlandı",
                """
                SELECT e.etkinlik_id, g.baslangic_zamani
                FROM oda_etkinlikleri e
                JOIN oda_etkinlik_gunleri g
                  ON g.etkinlik_id = e.etkinlik_id
                WHERE e.iptal_edildi_mi IS NOT TRUE
                  AND g.baslangic_zamani >= %s::date
                  AND g.baslangic_zamani < (%s::date + INTERVAL '1 day')
                ORDER BY g.baslangic_zamani DESC LIMIT 100
                """,
                True,
            ),
            (
                "cihaz_rezervasyon",
                "Cihaz rezervasyonu başlangıcı planlandı",
                """
                SELECT rezervasyon_id, baslangic_zamani
                FROM cihaz_rezervasyonlari
                WHERE iptal_edildi_mi IS NOT TRUE
                  AND baslangic_zamani >= %s::date
                  AND baslangic_zamani < (%s::date + INTERVAL '1 day')
                ORDER BY baslangic_zamani DESC LIMIT 100
                """,
                True,
            ),
        ]

        for tur, baslik, sorgu, planli in ek_kaynaklar:
            imlec.execute(sorgu, (hedef_gun, hedef_gun))
            for kayit_id, zaman in imlec.fetchall():
                if zaman is None:
                    continue
                olaylar.append({
                    "tur": tur,
                    "baslik": baslik,
                    "kayit_id": int(kayit_id),
                    "zaman": zaman.isoformat(),
                    "planli": planli,
                })

        imlec.execute("""
            SELECT
                COUNT(*) FILTER (WHERE bitis_zamani IS NULL),
                COUNT(*) FILTER (
                    WHERE bitis_zamani IS NOT NULL
                      AND onaylandi_mi IS NOT TRUE
                )
            FROM danisma_masasi_oturumlari
        """)
        aktif_danisma, onay_bekleyen = imlec.fetchone()

        imlec.execute("""
            SELECT COUNT(*)
            FROM danisma_masasi_oturumlari
            WHERE bitis_zamani >= %s::date
              AND bitis_zamani < (%s::date + INTERVAL '1 day')
        """, (hedef_gun, hedef_gun))
        tamamlanan_danisma = int(imlec.fetchone()[0])

        imlec.execute("""
            SELECT COUNT(*)
            FROM cihaz_rezervasyonlari
            WHERE iptal_edildi_mi IS NOT TRUE
              AND baslangic_zamani < (%s::date + INTERVAL '1 day')
              AND bitis_zamani >= %s::date
        """, (hedef_gun, hedef_gun))
        gunluk_rezervasyon = int(imlec.fetchone()[0])

        olaylar.sort(
            key=lambda olay: (
                olay["zaman"],
                olay["tur"],
                olay["kayit_id"],
            ),
            reverse=True,
        )

        return {
            "gun": hedef_gun.isoformat(),
            "ozet": {
                "planlanan_randevu": randevu,
                "baslayan_danisma_gorevi": danisma,
                "girilen_ogrenci_faaliyeti": faaliyet,
                "bildirilen_ariza": ariza,
                "planlanan_oda_etkinligi": etkinlik,
                "aktif_danisma_gorevi": int(aktif_danisma),
                "onay_bekleyen_danisma": int(onay_bekleyen),
                "tamamlanan_danisma_gorevi": tamamlanan_danisma,
                "bugunku_cihaz_rezervasyonu": gunluk_rezervasyon,
            },
            "cihaz_durumlari": cihaz_durumlari,
            "olaylar": olaylar[:40],
            "toplam_listelenen_olay": min(len(olaylar), 40),
            "aciklama": (
                "Randevu ve oda etkinliği sayıları seçilen günün "
                "planlanan kayıtlarını gösterir. Olay akışında "
                "yalnızca zaman damgası doğrulanabilen işlemler "
                "bulunur. Cihaz durumları güncel anlık değerlerdir."
            ),
        }

    except psycopg2.Error:
        raise HTTPException(
            status_code=500,
            detail="Günlük operasyon verileri alınamadı."
        )

    finally:
        if imlec is not None:
            imlec.close()
        if baglanti is not None:
            baglanti.close()

# TKYS_GUNLUK_DETAY_V1

def yonetim_gunluk_detay(
    tur: str,
    gun: _yr_date | None = None,
    kullanici_id: int | None = None,
):
    """Yönetim panelindeki özetlerin salt okunur kayıt listeleri."""
    hedef_gun = gun or _yr_date.today()

    # Sorgu adları sunucuda sabittir; istemci SQL gönderemez.
    sorgular = {
        "planlanan_randevu": (
            "Bugüne Planlanan Randevular",
            """
            SELECT randevu_id::text,
                   'Oda No: ' || COALESCE(oda_id::text, '—'),
                   TO_CHAR(baslangic_zamani, 'DD.MM.YYYY HH24:MI'),
                   COALESCE(durum, '—')
            FROM randevular
            WHERE baslangic_zamani >= %s::date
              AND baslangic_zamani < %s::date + INTERVAL '1 day'
            ORDER BY baslangic_zamani, randevu_id
            LIMIT 200
            """,
            True,
        ),
        "baslayan_danisma_gorevi": (
            "Bugün Başlayan Danışma Görevleri",
            """
            SELECT oturum_id::text,
                   'Öğrenci No: ' || ogrenci_id::text,
                   TO_CHAR(baslangic_zamani, 'DD.MM.YYYY HH24:MI'),
                   CASE WHEN bitis_zamani IS NULL
                        THEN 'Devam ediyor'
                        WHEN onaylandi_mi IS TRUE THEN 'Onaylandı'
                        ELSE 'Onay bekliyor' END
            FROM danisma_masasi_oturumlari
            WHERE baslangic_zamani >= %s::date
              AND baslangic_zamani < %s::date + INTERVAL '1 day'
            ORDER BY baslangic_zamani DESC
            LIMIT 200
            """,
            True,
        ),
        "girilen_ogrenci_faaliyeti": (
            "Bugün Girilen Öğrenci Faaliyetleri",
            """
            SELECT takip_id::text,
                   'Faaliyet No: ' || faaliyet_id::text ||
                   ' · Adet: ' || adet::text,
                   TO_CHAR(olusturulma_tarihi, 'DD.MM.YYYY HH24:MI'),
                   CASE WHEN onaylandi_mi IS TRUE
                        THEN 'Onaylandı' ELSE 'Onay bekliyor' END
            FROM ogrenci_faaliyet_takip
            WHERE olusturulma_tarihi >= %s::date
              AND olusturulma_tarihi < %s::date + INTERVAL '1 day'
            ORDER BY olusturulma_tarihi DESC
            LIMIT 200
            """,
            True,
        ),
        "bildirilen_ariza": (
            "Bugün Bildirilen Cihaz Arızaları",
            """
            SELECT a.ariza_id::text,
                   COALESCE(c.cihaz_adi, 'Cihaz No: ' || a.cihaz_id::text),
                   TO_CHAR(a.bildirim_tarihi, 'DD.MM.YYYY HH24:MI'),
                   CASE WHEN a.cozuldu_mu IS TRUE
                        THEN 'Çözüldü' ELSE 'Açık' END
            FROM cihaz_arizalari a
            LEFT JOIN cihazlar c ON c.cihaz_id = a.cihaz_id
            WHERE a.bildirim_tarihi >= %s::date
              AND a.bildirim_tarihi < %s::date + INTERVAL '1 day'
            ORDER BY a.bildirim_tarihi DESC
            LIMIT 200
            """,
            True,
        ),
        "planlanan_oda_etkinligi": (
            "Bugüne Planlanan Oda Etkinlikleri",
            """
            SELECT e.etkinlik_id::text,
                   COALESCE(e.etkinlik_adi, 'Oda etkinliği'),
                   TO_CHAR(g.baslangic_zamani, 'DD.MM.YYYY HH24:MI'),
                   'Planlandı'
            FROM oda_etkinlikleri e
            JOIN oda_etkinlik_gunleri g
              ON g.etkinlik_id = e.etkinlik_id
            WHERE e.iptal_edildi_mi IS NOT TRUE
              AND g.baslangic_zamani >= %s::date
              AND g.baslangic_zamani < %s::date + INTERVAL '1 day'
            ORDER BY g.baslangic_zamani
            LIMIT 200
            """,
            True,
        ),
        "aktif_danisma_gorevi": (
            "Aktif Danışma Görevleri",
            """
            SELECT oturum_id::text,
                   'Öğrenci No: ' || ogrenci_id::text,
                   TO_CHAR(baslangic_zamani, 'DD.MM.YYYY HH24:MI'),
                   'Devam ediyor'
            FROM danisma_masasi_oturumlari
            WHERE bitis_zamani IS NULL
            ORDER BY baslangic_zamani DESC
            LIMIT 200
            """,
            False,
        ),
        "tamamlanan_danisma_gorevi": (
            "Bugün Biten Danışma Görevleri",
            """
            SELECT oturum_id::text,
                   'Öğrenci No: ' || ogrenci_id::text,
                   TO_CHAR(bitis_zamani, 'DD.MM.YYYY HH24:MI'),
                   CASE WHEN onaylandi_mi IS TRUE
                        THEN 'Onaylandı' ELSE 'Onay bekliyor' END
            FROM danisma_masasi_oturumlari
            WHERE bitis_zamani >= %s::date
              AND bitis_zamani < %s::date + INTERVAL '1 day'
            ORDER BY bitis_zamani DESC
            LIMIT 200
            """,
            True,
        ),
        "onay_bekleyen_danisma": (
            "Toplam Onay Bekleyen Danışma Görevleri",
            """
            SELECT oturum_id::text,
                   'Öğrenci No: ' || ogrenci_id::text,
                   TO_CHAR(bitis_zamani, 'DD.MM.YYYY HH24:MI'),
                   'Onay bekliyor'
            FROM danisma_masasi_oturumlari
            WHERE bitis_zamani IS NOT NULL
              AND onaylandi_mi IS NOT TRUE
            ORDER BY bitis_zamani DESC
            LIMIT 200
            """,
            False,
        ),
        "bugunku_cihaz_rezervasyonu": (
            "Bugünkü Cihaz Rezervasyonları",
            """
            SELECT r.rezervasyon_id::text,
                   COALESCE(c.cihaz_adi, 'Cihaz No: ' || r.cihaz_id::text),
                   TO_CHAR(r.baslangic_zamani, 'DD.MM.YYYY HH24:MI'),
                   'Planlanan rezervasyon'
            FROM cihaz_rezervasyonlari r
            LEFT JOIN cihazlar c ON c.cihaz_id = r.cihaz_id
            WHERE r.iptal_edildi_mi IS NOT TRUE
              AND r.baslangic_zamani < %s::date + INTERVAL '1 day'
              AND r.bitis_zamani >= %s::date
            ORDER BY r.baslangic_zamani
            LIMIT 200
            """,
            True,
        ),
    }

    if tur not in sorgular:
        raise HTTPException(
            status_code=400, detail="Geçersiz rapor türü."
        )

    baslik, sorgu, tarihli = sorgular[tur]

    try:
        with vt_baglan(VT_AYARLARI) as baglanti:
            with baglanti.cursor() as imlec:
                parametreler = (
                    (hedef_gun, hedef_gun) if tarihli else ()
                )
                imlec.execute(sorgu, parametreler)
                satirlar = imlec.fetchall()
    except psycopg2.Error:
        raise HTTPException(
            status_code=500,
            detail="Ayrıntı kayıtları alınamadı."
        )

    return {
        "baslik": baslik,
        "gun": hedef_gun.isoformat(),
        "tur": tur,
        "sutunlar": ["Kayıt No", "Bilgi", "Tarih / Saat", "Durum"],
        "satirlar": [
            [str(deger) if deger is not None else "—"
             for deger in satir]
            for satir in satirlar
        ],
        "sinir": 200,
        "kapsam": "Seçilen gün" if tarihli else "Güncel / tüm dönemler",
    }


# (yol, uç fonksiyonu, gereken izin): yetki bağımlılığı kayıt sırasında eklenir.
UCLAR = [
    ("/api/yonetim-raporlari/randevu-ozet", yonetim_randevu_ozet, "YONETIM_RAPORLARI_GORUNTULE"),
    ("/api/yonetim-raporlari/cihaz-ozet", yonetim_cihaz_ozet, "YONETIM_RAPORLARI_GORUNTULE"),
    ("/api/yonetim-raporlari/ogrenci-ozet", yonetim_ogrenci_ozet, "YONETIM_RAPORLARI_GORUNTULE"),
    ("/api/yonetim-raporlari/proje-etkinlik-ozet", yonetim_proje_etkinlik_ozet, "YONETIM_RAPORLARI_GORUNTULE"),
    ("/api/yonetim-raporlari/kullanim-ozet", yonetim_kullanim_ozet, "YONETIM_RAPORLARI_GORUNTULE"),
    ("/api/cihaz-rezervasyon-raporu", cihaz_rezervasyon_raporu, "CIHAZ_ENVANTER_YONET"),
    ("/api/oda-kullanim-raporu", oda_kullanim_raporu, "YONETIM_RAPORLARI_GORUNTULE"),
    ("/api/yetki-raporu", yetki_raporu_getir, "AUDIT_KAYITLARI_INCELE"),
    ("/api/ogrenci-raporu", ogrenci_raporu_getir, "FAALIYET_KAYITLARI_DUZENLE"),
    ("/api/faaliyet-raporu", faaliyet_raporu_getir, "FAALIYET_KAYITLARI_DUZENLE"),
    ("/api/bakim-plani-raporu", bakim_plani_raporu_getir, "CIHAZ_ENVANTER_YONET"),
    ("/api/yonetim-raporlari/bugun-merkezde", yonetim_bugun_merkezde, "YONETIM_RAPORLARI_GORUNTULE"),
    ("/api/yonetim-raporlari/gunluk-detay", yonetim_gunluk_detay, "YONETIM_RAPORLARI_GORUNTULE"),
]


def router_olustur(izin_kontrol) -> APIRouter:
    """`izin_kontrol`: `server.sunucu.izin_kontrol` (kimlik doğrulama + izin kontrolü bağımlılığı üreticisi)."""
    router = APIRouter()
    for yol, fonksiyon, izin in UCLAR:
        router.add_api_route(yol, yetkiyle_bagla(fonksiyon, "kullanici_id", izin_kontrol(izin)), methods=["GET"])
    return router
