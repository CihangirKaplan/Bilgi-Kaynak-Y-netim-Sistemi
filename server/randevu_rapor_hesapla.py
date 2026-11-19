"""Randevu raporunun hesaplaması (veritabanından ve ekrandan bağımsız, saf işlev).

Sunucu uç noktası satırları okur, bu işlevle özetler; ekran ve Excel yalnızca sonucu gösterir. Danışanlar kodla tutulduğundan rapor
da yalnızca danışan KODU içerir (kişisel veri yok, FR-008).

Tanımlar
- Tamamlanma oranı = Tamamlandı / (Tamamlandı + Gelmedi); Gelmeme oranı = Gelmedi / (Tamamlandı + Gelmedi).
  Planlanmış (henüz yapılmamış) ve iptal edilmiş randevular oranlara girmez.
- Görüşme tipi, terapi türü ve yaş grubu dağılımı iptal edilmeyen randevular üzerindendir.
- İptal nedenleri yalnızca iptal edilen randevular üzerindendir; neden kaydedilmemiş eski iptaller ayrı satırda görünür.
- "Sonucu girilmemiş geçmiş" = durumu hâlâ Planlandı olan ama günü bugünden önce olan randevular; bunlar Tamamlandı/Gelmedi
  işaretlenmediği için oranlara girmez ve oranları olduğundan farklı gösterebilir (ayrı sayılarak fark ettirilir).
"""

from datetime import date, datetime

DURUMLAR = ("PLANLANDI", "TAMAMLANDI", "GELMEDI", "IPTAL_EDILDI")
BELIRTILMEDI = ("BELIRTILMEDI", "Belirtilmedi")
NEDEN_YOK = ("KAYDEDILMEMIS", "Neden kaydedilmemiş")


def _oran(pay, payda):
    return round(pay / payda, 4) if payda else None


def _say(satirlar, anahtar_fn, etiketler, bos):
    """Değerleri sayar; (kod, etiket, sayı, pay) sözlükleri döndürür (çoktan aza)."""
    sayac = {}
    for s in satirlar:
        kod = anahtar_fn(s) or bos[0]
        sayac[kod] = sayac.get(kod, 0) + 1
    toplam = sum(sayac.values())
    liste = [
        {"kod": kod, "etiket": etiketler.get(kod, bos[1]) if kod != bos[0] else bos[1], "sayi": sayi, "pay": _oran(sayi, toplam)}
        for kod, sayi in sayac.items()
    ]
    liste.sort(key=lambda x: (-x["sayi"], x["etiket"]))
    return liste


def _gun(deger):
    """datetime/date/ISO metin -> date (çözülemezse None)."""
    if isinstance(deger, datetime):
        return deger.date()
    if isinstance(deger, date):
        return deger
    try:
        return datetime.fromisoformat(str(deger)).date()
    except (TypeError, ValueError):
        return None


def _sonucsuz_gecmis(satirlar, bugun):
    return sum(1 for s in satirlar if s["durum"] == "PLANLANDI" and (_gun(s.get("baslangic_zamani")) or bugun) < bugun)


def _durum_sayilari(satirlar):
    sayilar = {d: 0 for d in DURUMLAR}
    for s in satirlar:
        if s["durum"] in sayilar:
            sayilar[s["durum"]] += 1
    return sayilar


def randevu_raporu_hesapla(satirlar, etiketler, detay=False, bugun=None):
    """satirlar: randevu sözlükleri; etiketler: {"iptal", "gorusme", "terapi", "yas"} kod -> görünen ad sözlükleri."""
    bugun = bugun or date.today()
    sayilar = _durum_sayilari(satirlar)
    gerceklesen = sayilar["TAMAMLANDI"] + sayilar["GELMEDI"]
    ozet = {
        "toplam": len(satirlar),
        "planlandi": sayilar["PLANLANDI"],
        "sonucsuz_gecmis": _sonucsuz_gecmis(satirlar, bugun),
        "tamamlandi": sayilar["TAMAMLANDI"],
        "gelmedi": sayilar["GELMEDI"],
        "iptal_edildi": sayilar["IPTAL_EDILDI"],
        "tamamlanma_orani": _oran(sayilar["TAMAMLANDI"], gerceklesen),
        "gelmeme_orani": _oran(sayilar["GELMEDI"], gerceklesen),
        "danisan_sayisi": len({s["danisan_kod_id"] for s in satirlar}),
    }

    psikologlar = {}
    for s in satirlar:
        g = psikologlar.setdefault(s["psikolog_id"], {"psikolog_id": s["psikolog_id"], "ad": s.get("psikolog_adi") or f"Psikolog #{s['psikolog_id']}", "satirlar": []})
        g["satirlar"].append(s)
    psikolog_listesi = []
    for g in psikologlar.values():
        c = _durum_sayilari(g["satirlar"])
        psikolog_listesi.append({
            "psikolog_id": g["psikolog_id"], "ad": g["ad"], "toplam": len(g["satirlar"]),
            "planlandi": c["PLANLANDI"], "tamamlandi": c["TAMAMLANDI"], "gelmedi": c["GELMEDI"], "iptal_edildi": c["IPTAL_EDILDI"],
        })
    psikolog_listesi.sort(key=lambda x: (-x["toplam"], x["ad"].casefold()))

    iptaller = [s for s in satirlar if s["durum"] == "IPTAL_EDILDI"]
    gecerli = [s for s in satirlar if s["durum"] != "IPTAL_EDILDI"]
    sonuc = {
        "ozet": ozet,
        "psikologlar": psikolog_listesi,
        "iptal_nedenleri": _say(iptaller, lambda s: s.get("iptal_nedeni"), etiketler["iptal"], NEDEN_YOK),
        "dagilimlar": {
            "gorusme_tipi": _say(gecerli, lambda s: s.get("gorusme_tipi"), etiketler["gorusme"], BELIRTILMEDI),
            "terapi_turu": _say(gecerli, lambda s: s.get("terapi_turu"), etiketler["terapi"], BELIRTILMEDI),
            "yas_grubu": _say(gecerli, lambda s: s.get("yas_grubu"), etiketler["yas"], BELIRTILMEDI),
        },
    }
    if detay:
        sonuc["randevular"] = [
            {
                "randevu_id": s["randevu_id"], "baslangic_zamani": s["baslangic_zamani"], "bitis_zamani": s["bitis_zamani"],
                "danisan_kod_id": s["danisan_kod_id"], "psikolog": s.get("psikolog_adi") or f"Psikolog #{s['psikolog_id']}",
                "oda": s.get("oda_adi") or f"Oda #{s['oda_id']}", "durum": s["durum"],
                "gorusme_tipi": etiketler["gorusme"].get(s.get("gorusme_tipi"), BELIRTILMEDI[1]),
                "terapi_turu": etiketler["terapi"].get(s.get("terapi_turu"), BELIRTILMEDI[1]),
                "yas_grubu": etiketler["yas"].get(s.get("yas_grubu"), BELIRTILMEDI[1]),
                "iptal_nedeni": etiketler["iptal"].get(s.get("iptal_nedeni"), NEDEN_YOK[1]) if s["durum"] == "IPTAL_EDILDI" else None,
            }
            for s in satirlar
        ]
    return sonuc
