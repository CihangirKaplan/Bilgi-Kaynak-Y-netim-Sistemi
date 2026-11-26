"""Oda kullanımı, cihaz rezervasyonu ve yetki raporlarının veri hesapları (uç noktalardan ve ekrandan bağımsız).

Tüm tarih aralığı hesapları [başlangıç günü 00:00, bitiş günü + 1 gün 00:00) yarı açık aralığıyla yapılır. Süreler dönem
sınırlarına kırpılır: dönemi aşan bir rezervasyon yalnızca dönem içindeki kısmı kadar sayılır. İptal edilen randevu, rezervasyon
ve etkinlikler kullanım sayılmaz. Saatler planlanan süreyi gösterir (gerçekleşen süre ayrıca ölçülmez).
"""
from datetime import date, timedelta

GUNLUK_MESAI_SAATI = 8          # mesai doluluk oranı varsayımı: hafta içi günlük 8 saat
GUN_ADLARI = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]


def is_gunu_sayisi(baslangic: date, bitis: date) -> int:
    """Aralıktaki hafta içi (Pazartesi-Cuma) gün sayısı (uçlar dahil)."""
    return sum(1 for i in range((bitis - baslangic).days + 1) if (baslangic + timedelta(days=i)).weekday() < 5)


def _saat(bas_sutunu: str, bit_sutunu: str) -> str:
    """Dönem sınırlarına kırpılmış saat toplamı (SQL parçası; sabit metinlerden oluşur, kullanıcı girdisi içermez)."""
    return (
        f"ROUND(COALESCE(SUM(EXTRACT(EPOCH FROM (LEAST({bit_sutunu}, d.bit) - GREATEST({bas_sutunu}, d.bas))) / 3600.0), 0)::numeric, 1)"
    )


DONEM_CTE = "WITH d AS (SELECT %s::date::timestamp AS bas, (%s::date + INTERVAL '1 day')::timestamp AS bit)"


def oda_kullanimi(cursor, baslangic: date, bitis: date, oda_id: int | None = None) -> list:
    """Oda bazlı kullanım: randevu, cihaz rezervasyonu (odası seçilen) ve oda etkinliği sayı/saatleri + mesai doluluk oranı."""
    oda_kosulu = "AND o.oda_id = %s" if oda_id is not None else ""
    parametreler = [baslangic, bitis] + ([oda_id] if oda_id is not None else [])
    cursor.execute(f"""
        {DONEM_CTE},
        rnd AS (
            SELECT r.oda_id, COUNT(*) AS sayi, {_saat("r.baslangic_zamani", "r.bitis_zamani")} AS saat
            FROM randevular r, d
            WHERE r.durum <> 'IPTAL_EDILDI' AND r.baslangic_zamani < d.bit AND r.bitis_zamani > d.bas
            GROUP BY r.oda_id
        ),
        rez AS (
            SELECT cr.kullanilacak_oda_id AS oda_id, COUNT(*) AS sayi, {_saat("cr.baslangic_zamani", "cr.bitis_zamani")} AS saat
            FROM cihaz_rezervasyonlari cr, d
            WHERE cr.iptal_edildi_mi IS NOT TRUE AND cr.kullanilacak_oda_id IS NOT NULL
              AND cr.baslangic_zamani < d.bit AND cr.bitis_zamani > d.bas
            GROUP BY cr.kullanilacak_oda_id
        ),
        etk AS (
            SELECT e.oda_id, COUNT(*) AS sayi, {_saat("e.baslangic_zamani", "e.bitis_zamani")} AS saat
            FROM oda_etkinlikleri e, d
            WHERE e.iptal_edildi_mi IS NOT TRUE AND e.baslangic_zamani < d.bit AND e.bitis_zamani > d.bas
            GROUP BY e.oda_id
        )
        SELECT o.oda_id, o.oda_adi, o.aktif_mi,
               COALESCE(rnd.sayi, 0), COALESCE(rnd.saat, 0),
               COALESCE(rez.sayi, 0), COALESCE(rez.saat, 0),
               COALESCE(etk.sayi, 0), COALESCE(etk.saat, 0)
        FROM odalar o
        LEFT JOIN rnd ON rnd.oda_id = o.oda_id
        LEFT JOIN rez ON rez.oda_id = o.oda_id
        LEFT JOIN etk ON etk.oda_id = o.oda_id
        WHERE (o.aktif_mi IS TRUE OR rnd.sayi IS NOT NULL OR rez.sayi IS NOT NULL OR etk.sayi IS NOT NULL) {oda_kosulu}
        ORDER BY (COALESCE(rnd.saat, 0) + COALESCE(rez.saat, 0) + COALESCE(etk.saat, 0)) DESC, o.oda_adi;
    """, parametreler)
    kapasite = is_gunu_sayisi(baslangic, bitis) * GUNLUK_MESAI_SAATI
    odalar = []
    for k in cursor.fetchall():
        randevu_saati, rezervasyon_saati, etkinlik_saati = float(k[4]), float(k[6]), float(k[8])
        toplam = round(randevu_saati + rezervasyon_saati + etkinlik_saati, 1)
        odalar.append({
            "oda_id": k[0], "oda_adi": k[1], "aktif_mi": bool(k[2]),
            "randevu_sayisi": int(k[3]), "randevu_saati": randevu_saati,
            "cihaz_rezervasyon_sayisi": int(k[5]), "cihaz_rezervasyon_saati": rezervasyon_saati,
            "etkinlik_sayisi": int(k[7]), "etkinlik_saati": etkinlik_saati,
            "toplam_saat": toplam,
            "mesai_doluluk_orani": round(toplam / kapasite, 4) if kapasite else None,
        })
    return odalar


def oda_kullanim_olaylari(cursor, baslangic: date, bitis: date, oda_id: int | None = None) -> list:
    """Odayı kullanan tek tek kayıtlar (Excel detay sayfası ve gün dağılımı için); süre dönem sınırlarına kırpılmıştır."""
    parametreler = lambda: [baslangic, bitis] + ([oda_id] if oda_id is not None else [])
    olaylar = []
    # Üç kaynak (randevu, cihaz rezervasyonu, etkinlik) ayrı ve basit sorgularla okunur.
    cursor.execute(f"""
        {DONEM_CTE}
        SELECT r.oda_id, o.oda_adi, r.baslangic_zamani, r.bitis_zamani,
               ROUND((EXTRACT(EPOCH FROM (LEAST(r.bitis_zamani, d.bit) - GREATEST(r.baslangic_zamani, d.bas))) / 3600.0)::numeric, 2),
               COALESCE(ku.kullanici_adi, '—') || ' · ' || r.durum
        FROM randevular r
        JOIN odalar o ON o.oda_id = r.oda_id
        LEFT JOIN personel p ON p.personel_id = r.psikolog_id
        LEFT JOIN kullanicilar ku ON ku.kullanici_id = p.kullanici_id
        CROSS JOIN d
        WHERE r.durum <> 'IPTAL_EDILDI' AND r.baslangic_zamani < d.bit AND r.bitis_zamani > d.bas
          {"AND r.oda_id = %s" if oda_id is not None else ""}
        ORDER BY r.baslangic_zamani, r.randevu_id;
    """, parametreler())
    olaylar += [("Randevu",) + tuple(k) for k in cursor.fetchall()]

    cursor.execute(f"""
        {DONEM_CTE}
        SELECT cr.kullanilacak_oda_id, o.oda_adi, cr.baslangic_zamani, cr.bitis_zamani,
               ROUND((EXTRACT(EPOCH FROM (LEAST(cr.bitis_zamani, d.bit) - GREATEST(cr.baslangic_zamani, d.bas))) / 3600.0)::numeric, 2),
               c.cihaz_adi
        FROM cihaz_rezervasyonlari cr
        JOIN odalar o ON o.oda_id = cr.kullanilacak_oda_id
        JOIN cihazlar c ON c.cihaz_id = cr.cihaz_id
        CROSS JOIN d
        WHERE cr.iptal_edildi_mi IS NOT TRUE AND cr.baslangic_zamani < d.bit AND cr.bitis_zamani > d.bas
          {"AND cr.kullanilacak_oda_id = %s" if oda_id is not None else ""}
        ORDER BY cr.baslangic_zamani, cr.rezervasyon_id;
    """, parametreler())
    olaylar += [("Cihaz rezervasyonu",) + tuple(k) for k in cursor.fetchall()]

    cursor.execute(f"""
        {DONEM_CTE}
        SELECT e.oda_id, o.oda_adi, e.baslangic_zamani, e.bitis_zamani,
               ROUND((EXTRACT(EPOCH FROM (LEAST(e.bitis_zamani, d.bit) - GREATEST(e.baslangic_zamani, d.bas))) / 3600.0)::numeric, 2),
               e.etkinlik_adi
        FROM oda_etkinlikleri e
        JOIN odalar o ON o.oda_id = e.oda_id
        CROSS JOIN d
        WHERE e.iptal_edildi_mi IS NOT TRUE AND e.baslangic_zamani < d.bit AND e.bitis_zamani > d.bas
          {"AND e.oda_id = %s" if oda_id is not None else ""}
        ORDER BY e.baslangic_zamani, e.etkinlik_id;
    """, parametreler())
    olaylar += [("Etkinlik",) + tuple(k) for k in cursor.fetchall()]

    return [
        {"tur": o[0], "oda_id": o[1], "oda_adi": o[2], "baslangic_zamani": o[3], "bitis_zamani": o[4],
         "sure_saat": float(o[5]), "aciklama": o[6]}
        for o in sorted(olaylar, key=lambda x: (x[3], x[0], x[2]))
    ]


def gun_dagilimi(olaylar: list) -> list:
    """Haftanın günlerine göre kullanım saati (kayıt, başladığı güne yazılır)."""
    saat = [0.0] * 7
    sayi = [0] * 7
    for o in olaylar:
        gun = o["baslangic_zamani"].weekday()
        saat[gun] += o["sure_saat"]
        sayi[gun] += 1
    return [{"gun": GUN_ADLARI[i], "kayit_sayisi": sayi[i], "saat": round(saat[i], 1)} for i in range(7)]


def cihaz_rezervasyonlari(cursor, baslangic: date, bitis: date, cihaz_id: int | None = None, proje_turu: str | None = None) -> dict:
    """Cihaz bazlı, proje türü ve bölüm bazlı rezervasyon kullanımı."""
    cihaz_kosulu = "AND cr.cihaz_id = %s" if cihaz_id is not None else ""
    tur_kosulu = "AND COALESCE(NULLIF(BTRIM(cr.proje_turu), ''), 'Belirtilmemiş') = %s" if proje_turu else ""
    ek = ([cihaz_id] if cihaz_id is not None else []) + ([proje_turu] if proje_turu else [])
    d = [baslangic, bitis]

    cursor.execute(f"""
        {DONEM_CTE},
        rez AS (
            SELECT cr.cihaz_id, COUNT(*) AS sayi, {_saat("cr.baslangic_zamani", "cr.bitis_zamani")} AS saat,
                   MAX(cr.bitis_zamani) AS son
            FROM cihaz_rezervasyonlari cr, d
            WHERE cr.iptal_edildi_mi IS NOT TRUE AND cr.baslangic_zamani < d.bit AND cr.bitis_zamani > d.bas
              {cihaz_kosulu} {tur_kosulu}
            GROUP BY cr.cihaz_id
        ),
        ipt AS (
            SELECT cr.cihaz_id, COUNT(*) AS sayi
            FROM cihaz_rezervasyonlari cr, d
            WHERE cr.iptal_edildi_mi IS TRUE AND cr.baslangic_zamani >= d.bas AND cr.baslangic_zamani < d.bit
              {cihaz_kosulu} {tur_kosulu}
            GROUP BY cr.cihaz_id
        )
        SELECT c.cihaz_id, c.envanter_kodu, c.cihaz_adi,
               COALESCE(rez.sayi, 0), COALESCE(rez.saat, 0), COALESCE(ipt.sayi, 0), rez.son
        FROM cihazlar c
        LEFT JOIN rez ON rez.cihaz_id = c.cihaz_id
        LEFT JOIN ipt ON ipt.cihaz_id = c.cihaz_id
        {"WHERE c.cihaz_id = %s" if cihaz_id is not None else ""}
        ORDER BY COALESCE(rez.saat, 0) DESC, c.cihaz_adi, c.cihaz_id;
    """, _cihaz_parametreleri(d, ek, cihaz_id))
    cihazlar = [
        {"cihaz_id": k[0], "envanter_kodu": k[1], "cihaz_adi": k[2], "rezervasyon_sayisi": int(k[3]),
         "rezervasyon_saati": float(k[4]), "iptal_edilen_rezervasyon": int(k[5]),
         "son_kullanim": k[6].isoformat() if k[6] else None}
        for k in cursor.fetchall()
    ]

    def gruplu(ifade: str, bos: str):
        cursor.execute(f"""
            {DONEM_CTE}
            SELECT COALESCE(NULLIF(BTRIM({ifade}), ''), '{bos}') AS ad, COUNT(*), {_saat("cr.baslangic_zamani", "cr.bitis_zamani")}
            FROM cihaz_rezervasyonlari cr
            LEFT JOIN bolumler b ON b.bolum_id = cr.bolum_id
            CROSS JOIN d
            WHERE cr.iptal_edildi_mi IS NOT TRUE AND cr.baslangic_zamani < d.bit AND cr.bitis_zamani > d.bas
              {cihaz_kosulu} {tur_kosulu}
            GROUP BY 1 ORDER BY 3 DESC, 1;
        """, d + ek)
        return [{"ad": k[0], "rezervasyon_sayisi": int(k[1]), "saat": float(k[2])} for k in cursor.fetchall()]

    return {
        "cihazlar": cihazlar,
        "proje_turleri": gruplu("cr.proje_turu", "Belirtilmemiş"),
        "bolumler": gruplu("b.bolum_adi", "Belirtilmemiş"),
    }


def _cihaz_parametreleri(donem, ek, cihaz_id):
    # İki CTE (rez, ipt) aynı süzgeçleri kullanır; sorgu parametre sırası: dönem, rez süzgeçleri, ipt süzgeçleri, cihaz süzgeci.
    return donem + ek + ek + ([cihaz_id] if cihaz_id is not None else [])


def cihaz_rezervasyon_detaylari(cursor, baslangic: date, bitis: date, cihaz_id: int | None = None,
                                proje_turu: str | None = None, en_cok: int = 5000) -> list:
    """Dönemle kesişen tek tek rezervasyonlar (iptaller dahil; durum sütunuyla ayrılır). Süre kaydın tamamının süresidir."""
    kosullar, ek = "", []
    if cihaz_id is not None:
        kosullar += " AND cr.cihaz_id = %s"
        ek.append(cihaz_id)
    if proje_turu:
        kosullar += " AND COALESCE(NULLIF(BTRIM(cr.proje_turu), ''), 'Belirtilmemiş') = %s"
        ek.append(proje_turu)
    cursor.execute(f"""
        {DONEM_CTE}
        SELECT cr.rezervasyon_id, c.envanter_kodu, c.cihaz_adi, COALESCE(b.bolum_adi, '—'), COALESCE(o.oda_adi, '—'),
               COALESCE(ku.kullanici_adi, '—'), cr.baslangic_zamani, cr.bitis_zamani,
               ROUND((EXTRACT(EPOCH FROM (cr.bitis_zamani - cr.baslangic_zamani)) / 3600.0)::numeric, 2),
               COALESCE(NULLIF(BTRIM(cr.proje_turu), ''), 'Belirtilmemiş'), COALESCE(cr.proje_adi_aciklamasi, ''),
               cr.iptal_edildi_mi
        FROM cihaz_rezervasyonlari cr
        JOIN cihazlar c ON c.cihaz_id = cr.cihaz_id
        LEFT JOIN bolumler b ON b.bolum_id = cr.bolum_id
        LEFT JOIN odalar o ON o.oda_id = cr.kullanilacak_oda_id
        LEFT JOIN personel p ON p.personel_id = cr.rezervasyonu_yapan_personel_id
        LEFT JOIN kullanicilar ku ON ku.kullanici_id = p.kullanici_id
        CROSS JOIN d
        WHERE cr.baslangic_zamani < d.bit AND cr.bitis_zamani > d.bas {kosullar}
        ORDER BY cr.baslangic_zamani, cr.rezervasyon_id
        LIMIT %s;
    """, [baslangic, bitis] + ek + [en_cok])
    return [
        {"rezervasyon_id": k[0], "envanter_kodu": k[1], "cihaz_adi": k[2], "bolum": k[3], "oda": k[4], "yapan": k[5],
         "baslangic_zamani": k[6], "bitis_zamani": k[7], "sure_saat": float(k[8]), "proje_turu": k[9], "proje_adi": k[10],
         "durum": "İptal" if k[11] else "Aktif"}
        for k in cursor.fetchall()
    ]


def yetki_raporu(cursor, rol_id: int | None = None, durum: str | None = None, matris: bool = False) -> dict:
    """Kullanıcı, rol ve izin dökümü (güvenlik denetimi). Parola, parola özeti ya da kişisel veri içermez.

    durum: None (hepsi) | "aktif" | "pasif". matris=True ise rol-izin matrisi de döner (Excel için)."""
    kosullar, parametreler = [], []
    if rol_id is not None:
        kosullar.append("k.rol_id = %s")
        parametreler.append(rol_id)
    if durum in ("aktif", "pasif"):
        kosullar.append("k.aktif_mi = %s")
        parametreler.append(durum == "aktif")
    where = "WHERE " + " AND ".join(kosullar) if kosullar else ""

    cursor.execute(f"""
        SELECT k.kullanici_id, k.kullanici_adi, r.rol_adi, k.aktif_mi, p.personel_kodu,
               (SELECT MAX(d.olusturulma_tarihi) FROM denetim_kayitlari d
                 WHERE d.kullanici_id = k.kullanici_id AND d.olay_turu = 'LOGIN'),       -- ::text dönüşümü YOK: kısmi indeks (ix_denetim_login_kullanici_tarih) kullanılsın
               k.basarisiz_giris_sayisi, (k.kilit_bitis_zamani IS NOT NULL AND k.kilit_bitis_zamani > NOW()),
               COALESCE(k.ilk_giris_mi, FALSE)
        FROM kullanicilar k
        JOIN roller r ON r.rol_id = k.rol_id
        LEFT JOIN personel p ON p.kullanici_id = k.kullanici_id
        {where}
        ORDER BY r.rol_adi, k.kullanici_adi;
    """, parametreler)
    kullanicilar = [
        {"kullanici_id": k[0], "kullanici_adi": k[1], "rol_adi": k[2], "aktif_mi": bool(k[3]), "personel_kodu": k[4],
         "son_giris": k[5].isoformat() if k[5] else None, "basarisiz_giris_sayisi": int(k[6]),
         "kilitli_mi": bool(k[7]), "gecici_parola_mi": bool(k[8])}
        for k in cursor.fetchall()
    ]

    cursor.execute("""
        SELECT r.rol_id, r.rol_adi,
               (SELECT COUNT(*) FROM kullanicilar k WHERE k.rol_id = r.rol_id),
               (SELECT COUNT(*) FROM kullanicilar k WHERE k.rol_id = r.rol_id AND k.aktif_mi),
               (SELECT COUNT(*) FROM rol_izinleri ri WHERE ri.rol_id = r.rol_id AND ri.izin_var = 1)
        FROM roller r ORDER BY r.rol_adi;
    """)
    roller = [
        {"rol_id": k[0], "rol_adi": k[1], "kullanici_sayisi": int(k[2]), "aktif_kullanici_sayisi": int(k[3]), "izin_sayisi": int(k[4])}
        for k in cursor.fetchall()
    ]

    cursor.execute("SELECT COUNT(*) FROM izinler;")
    izin_sayisi = int(cursor.fetchone()[0])
    cursor.execute("""
        SELECT COUNT(*) FROM denetim_kayitlari
        WHERE olay_turu::text = 'LOGIN_FAILED' AND olusturulma_tarihi >= NOW() - INTERVAL '30 days';
    """)
    basarisiz_30 = int(cursor.fetchone()[0])

    sonuc = {
        "ozet": {
            "kullanici_sayisi": len(kullanicilar),
            "aktif_kullanici": sum(1 for k in kullanicilar if k["aktif_mi"]),
            "pasif_kullanici": sum(1 for k in kullanicilar if not k["aktif_mi"]),
            "kilitli_kullanici": sum(1 for k in kullanicilar if k["kilitli_mi"]),
            "hic_giris_yapmamis": sum(1 for k in kullanicilar if k["aktif_mi"] and k["son_giris"] is None),
            "gecici_parolali": sum(1 for k in kullanicilar if k["gecici_parola_mi"]),
            "rol_sayisi": len(roller),
            "izin_sayisi": izin_sayisi,
            "son_30_gun_basarisiz_giris": basarisiz_30,
        },
        "kullanicilar": kullanicilar,
        "roller": roller,
    }
    if matris:
        cursor.execute("""
            SELECT i.izin_adi, COALESCE(i.aciklama, ''), r.rol_adi, COALESCE(ri.izin_var, 0)
            FROM izinler i CROSS JOIN roller r
            LEFT JOIN rol_izinleri ri ON ri.izin_id = i.izin_id AND ri.rol_id = r.rol_id
            ORDER BY i.izin_adi, r.rol_adi;
        """)
        izinler = {}
        for izin_adi, aciklama, rol_adi, var in cursor.fetchall():
            izinler.setdefault(izin_adi, {"izin_adi": izin_adi, "aciklama": aciklama, "roller": {}})["roller"][rol_adi] = bool(var)
        sonuc["matris"] = {"roller": [r["rol_adi"] for r in roller], "izinler": list(izinler.values())}
    return sonuc
