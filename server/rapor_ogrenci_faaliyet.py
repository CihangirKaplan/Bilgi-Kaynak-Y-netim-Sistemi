"""Öğrenci ve faaliyet raporlarının veri hesapları (uç noktalardan ve ekrandan bağımsız).

Öğrenci raporu mevcut durumu (anlık) gösterir; telefon raporda yer almaz. Faaliyet raporu seçilen dönemde (faaliyet tarihi) girilen
faaliyet kayıtlarını, onay durumunu ve puanları özetler. Puan = adet x kaydın girildiği andaki faaliyet puanı (Puan Raporu ile aynı).
"""
from datetime import date

SAKLAMA_YIL = 10                 # Gönüllü öğrenci kaydı saklama süresi (ogrenci_on_yil_sil kuralıyla aynı)
YAKLASAN_AY = 12                 # "yaklaşan" saklama süresi eşiği
FAALIYETSIZ_GUN = 90             # "faaliyetsiz aktif öğrenci" eşiği
BEKLEYEN_LISTE_SINIRI = 20


def ogrenci_raporu(cursor, etiketler: dict, tur: str | None = None, durum: str | None = None) -> dict:
    """Öğrenci mevcudu: tür/bölüm dağılımı, kayıt saklama süresi durumu ve öğrenci listesi (telefon yok)."""
    kosullar, parametreler = [], []
    if tur is not None:
        kosullar.append("o.tur::text = %s")
        parametreler.append(tur)
    if durum in ("aktif", "pasif"):
        kosullar.append("o.aktif_mi = %s")
        parametreler.append(durum == "aktif")
    where = "WHERE " + " AND ".join(kosullar) if kosullar else ""

    cursor.execute(f"""
        SELECT o.ogrenci_id, o.ad_soyad, o.ogrenci_numarasi, o.tur::text, o.aktif_mi, o.bolum, o.sinif, o.olusturulma_tarihi,
               (SELECT COUNT(*) FROM ogrenci_faaliyet_takip t WHERE t.ogrenci_id = o.ogrenci_id),
               (SELECT COALESCE(SUM(t.adet * t.kayit_puani), 0) FROM ogrenci_faaliyet_takip t WHERE t.ogrenci_id = o.ogrenci_id),
               (SELECT MAX(t.faaliyet_tarihi) FROM ogrenci_faaliyet_takip t WHERE t.ogrenci_id = o.ogrenci_id),
               (o.tur::text = 'GONULLU' AND o.olusturulma_tarihi::date <= (CURRENT_DATE - INTERVAL '{SAKLAMA_YIL} years')::date),
               (o.tur::text = 'GONULLU' AND o.olusturulma_tarihi::date > (CURRENT_DATE - INTERVAL '{SAKLAMA_YIL} years')::date
                    AND o.olusturulma_tarihi::date <= (CURRENT_DATE - INTERVAL '{SAKLAMA_YIL} years' + INTERVAL '{YAKLASAN_AY} months')::date),
               e.yeni_uyari_tarihi,
               (e.yeni_uyari_tarihi IS NOT NULL AND e.yeni_uyari_tarihi > CURRENT_DATE),
               (o.olusturulma_tarihi >= NOW() - INTERVAL '30 days'),
               (o.olusturulma_tarihi::date + INTERVAL '{SAKLAMA_YIL} years')::date
        FROM ogrenciler o
        LEFT JOIN LATERAL (
            SELECT yeni_uyari_tarihi FROM ogrenci_kayit_erteleme_gecmisi e
            WHERE e.ogrenci_id = o.ogrenci_id ORDER BY e.erteleme_id DESC LIMIT 1
        ) e ON TRUE
        {where}
        ORDER BY o.aktif_mi DESC, o.ad_soyad, o.ogrenci_id;
    """, parametreler)

    bugun = date.today()
    ogrenciler = []
    for k in cursor.fetchall():
        doldu, yaklasiyor, ertelendi = bool(k[11]), bool(k[12]), bool(k[14])
        if doldu and ertelendi:
            saklama = "Ertelendi"
        elif doldu:
            saklama = "Süresi doldu"
        elif yaklasiyor:
            saklama = f"{YAKLASAN_AY} ay içinde dolacak"
        else:
            saklama = None
        son = k[10]
        ogrenciler.append({
            "ogrenci_id": k[0], "ad_soyad": k[1], "ogrenci_numarasi": k[2], "tur": k[3],
            "tur_etiketi": etiketler.get(k[3], k[3]), "aktif_mi": bool(k[4]), "bolum": k[5], "sinif": k[6],
            "olusturulma_tarihi": k[7].isoformat() if k[7] else None,
            "faaliyet_sayisi": int(k[8]), "toplam_puan": float(k[9]),
            "son_faaliyet_tarihi": son.isoformat() if son else None,
            "saklama_durumu": saklama,
            "saklama_bitis": k[16].isoformat() if k[3] == "GONULLU" and k[16] else None,
            "erteleme_tarihi": k[13].isoformat() if k[13] else None,
            "yeni_kayit_mi": bool(k[15]),
            "faaliyetsiz_mi": bool(k[4]) and (son is None or (bugun - son).days > FAALIYETSIZ_GUN),
        })

    turler = {}
    for o in ogrenciler:
        g = turler.setdefault(o["tur"], {"tur": o["tur"], "etiket": o["tur_etiketi"], "toplam": 0, "aktif": 0, "pasif": 0})
        g["toplam"] += 1
        g["aktif" if o["aktif_mi"] else "pasif"] += 1
    bolumler = {}
    for o in ogrenciler:
        ad = (o["bolum"] or "").strip() or "Belirtilmemiş"
        bolumler[ad] = bolumler.get(ad, 0) + 1

    return {
        "ozet": {
            "toplam": len(ogrenciler),
            "aktif": sum(1 for o in ogrenciler if o["aktif_mi"]),
            "pasif": sum(1 for o in ogrenciler if not o["aktif_mi"]),
            "son_30_gun_yeni": sum(1 for o in ogrenciler if o["yeni_kayit_mi"]),
            "saklama_suresi_dolmus": sum(1 for o in ogrenciler if o["saklama_durumu"] == "Süresi doldu"),
            "saklama_ertelenen": sum(1 for o in ogrenciler if o["saklama_durumu"] == "Ertelendi"),
            "saklama_yaklasan": sum(1 for o in ogrenciler if (o["saklama_durumu"] or "").endswith("dolacak")),
            "faaliyetsiz_aktif": sum(1 for o in ogrenciler if o["faaliyetsiz_mi"]),
        },
        "tur_dagilimi": sorted(turler.values(), key=lambda g: (-g["toplam"], g["etiket"])),
        "bolum_dagilimi": [{"bolum": ad, "ogrenci": n} for ad, n in sorted(bolumler.items(), key=lambda x: (-x[1], x[0]))],
        "ogrenciler": ogrenciler,
        "kurallar": {"saklama_yil": SAKLAMA_YIL, "yaklasan_ay": YAKLASAN_AY, "faaliyetsiz_gun": FAALIYETSIZ_GUN},
    }


def faaliyet_raporu(cursor, etiketler: dict, baslangic: date, bitis: date, faaliyet_id: int | None = None,
                    onay: str | None = None, detay: bool = False, en_cok: int = 5000) -> dict:
    """Dönemdeki faaliyet kayıtları: faaliyet türü/birim/öğrenci türü dağılımı, onay durumu ve onay bekleyenler."""
    kosullar = ["t.faaliyet_tarihi >= %s", "t.faaliyet_tarihi <= %s"]
    parametreler = [baslangic, bitis]
    if faaliyet_id is not None:
        kosullar.append("t.faaliyet_id = %s")
        parametreler.append(faaliyet_id)
    if onay in ("onayli", "bekleyen"):
        kosullar.append("t.onaylandi_mi = %s")
        parametreler.append(onay == "onayli")
    where = "WHERE " + " AND ".join(kosullar)

    cursor.execute(f"""
        SELECT COUNT(*), COALESCE(SUM(t.adet), 0), COALESCE(SUM(t.adet * t.kayit_puani), 0),
               COUNT(*) FILTER (WHERE t.onaylandi_mi), COUNT(*) FILTER (WHERE NOT t.onaylandi_mi),
               COALESCE(SUM(t.adet * t.kayit_puani) FILTER (WHERE t.onaylandi_mi), 0),
               COALESCE(SUM(t.adet * t.kayit_puani) FILTER (WHERE NOT t.onaylandi_mi), 0),
               COUNT(DISTINCT t.ogrenci_id), MIN(t.faaliyet_tarihi) FILTER (WHERE NOT t.onaylandi_mi)
        FROM ogrenci_faaliyet_takip t {where};
    """, parametreler)
    k = cursor.fetchone()
    bugun = date.today()
    kayit = int(k[0])
    ozet = {
        "kayit_sayisi": kayit, "faaliyet_miktari": int(k[1]), "toplam_puan": float(k[2]),
        "onayli_kayit": int(k[3]), "onay_bekleyen_kayit": int(k[4]),
        "onayli_puan": float(k[5]), "onay_bekleyen_puan": float(k[6]),
        "faaliyet_yapan_ogrenci": int(k[7]),
        "ortalama_puan_kayit": round(float(k[2]) / kayit, 1) if kayit else None,
        "en_eski_bekleyen_gun": (bugun - k[8]).days if k[8] else None,
    }

    cursor.execute(f"""
        SELECT f.faaliyet_id, f.faaliyet_adi, COUNT(*), COALESCE(SUM(t.adet), 0), COALESCE(SUM(t.adet * t.kayit_puani), 0),
               COUNT(*) FILTER (WHERE NOT t.onaylandi_mi)
        FROM ogrenci_faaliyet_takip t JOIN faaliyetler f ON f.faaliyet_id = t.faaliyet_id {where}
        GROUP BY f.faaliyet_id, f.faaliyet_adi ORDER BY 5 DESC, f.faaliyet_adi;
    """, parametreler)
    faaliyetler = [{"faaliyet_id": r[0], "faaliyet": r[1], "kayit_sayisi": int(r[2]), "miktar": int(r[3]), "puan": float(r[4]),
                    "onay_bekleyen": int(r[5])} for r in cursor.fetchall()]

    cursor.execute(f"""
        SELECT COALESCE(b.birim_adi, 'Belirtilmemiş'), COUNT(*), COALESCE(SUM(t.adet), 0)
        FROM ogrenci_faaliyet_takip t LEFT JOIN faaliyet_birimleri b ON b.birim_id = t.birim_id {where}
        GROUP BY 1 ORDER BY 3 DESC, 1;
    """, parametreler)
    birimler = [{"birim": r[0], "kayit_sayisi": int(r[1]), "miktar": int(r[2])} for r in cursor.fetchall()]

    cursor.execute(f"""
        SELECT o.tur::text, COUNT(DISTINCT t.ogrenci_id), COUNT(*), COALESCE(SUM(t.adet * t.kayit_puani), 0)
        FROM ogrenci_faaliyet_takip t JOIN ogrenciler o ON o.ogrenci_id = t.ogrenci_id {where}
        GROUP BY o.tur ORDER BY 4 DESC;
    """, parametreler)
    turler = [{"tur": r[0], "etiket": etiketler.get(r[0], r[0]), "ogrenci_sayisi": int(r[1]), "kayit_sayisi": int(r[2]), "puan": float(r[3])}
              for r in cursor.fetchall()]

    cursor.execute(f"""
        SELECT t.takip_id, o.ad_soyad, f.faaliyet_adi, t.faaliyet_tarihi, t.adet, t.adet * t.kayit_puani
        FROM ogrenci_faaliyet_takip t
        JOIN ogrenciler o ON o.ogrenci_id = t.ogrenci_id JOIN faaliyetler f ON f.faaliyet_id = t.faaliyet_id
        {where} AND NOT t.onaylandi_mi
        ORDER BY t.faaliyet_tarihi, t.takip_id LIMIT %s;
    """, parametreler + [BEKLEYEN_LISTE_SINIRI])
    bekleyenler = [{"takip_id": r[0], "ogrenci": r[1], "faaliyet": r[2], "tarih": r[3].isoformat(), "bekleme_gun": (bugun - r[3]).days,
                    "adet": int(r[4]), "puan": float(r[5])} for r in cursor.fetchall()]

    cursor.execute("SELECT faaliyet_id, faaliyet_adi FROM faaliyetler ORDER BY faaliyet_adi, faaliyet_id;")
    sonuc = {
        "ozet": ozet, "faaliyetler": faaliyetler, "birimler": birimler, "ogrenci_turleri": turler, "onay_bekleyenler": bekleyenler,
        "faaliyet_secenekleri": [{"faaliyet_id": r[0], "faaliyet_adi": r[1]} for r in cursor.fetchall()],
    }

    if detay:
        cursor.execute(f"""
            SELECT t.takip_id, o.ad_soyad, o.ogrenci_numarasi, o.tur::text, f.faaliyet_adi, COALESCE(b.birim_adi, ''),
                   t.adet, t.kayit_puani, t.adet * t.kayit_puani, t.faaliyet_tarihi, t.onaylandi_mi
            FROM ogrenci_faaliyet_takip t
            JOIN ogrenciler o ON o.ogrenci_id = t.ogrenci_id JOIN faaliyetler f ON f.faaliyet_id = t.faaliyet_id
            LEFT JOIN faaliyet_birimleri b ON b.birim_id = t.birim_id
            {where} ORDER BY t.faaliyet_tarihi DESC, t.takip_id DESC LIMIT %s;
        """, parametreler + [en_cok])
        sonuc["kayitlar"] = [
            {"takip_id": r[0], "ogrenci": r[1], "ogrenci_numarasi": r[2], "tur": etiketler.get(r[3], r[3]), "faaliyet": r[4], "birim": r[5],
             "adet": int(r[6]), "birim_puan": float(r[7]), "toplam_puan": float(r[8]), "tarih": r[9].isoformat(),
             "durum": "Onaylandı" if r[10] else "Onay bekliyor"}
            for r in cursor.fetchall()
        ]
    return sonuc
