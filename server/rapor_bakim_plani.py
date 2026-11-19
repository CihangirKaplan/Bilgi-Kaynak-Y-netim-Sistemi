"""Geciken Bakım Planı Raporu'nun veri hesapları (uç noktadan ve ekrandan bağımsız).

Plan durumu, Bakım Planları ekranıyla (sunucu.bakim_plani_durumu) aynı kurala göre belirlenir:
pasif plan = Pasif; sonraki görev tarihi geçmişse = Gecikmiş; uyarı süresi içindeyse = Yaklaşıyor; aksi halde Planlı.
Rapor bugünkü durumdur (dönemden bağımsız). Kalibrasyon planı = görev türü 'Kalibrasyon' ile başlayan plan.
"""

DURUMLAR = {"gecikmis": "Gecikmiş", "yaklasiyor": "Yaklaşıyor", "planli": "Planlı", "pasif": "Pasif"}


def plan_durumu(kalan_gun: int, uyari_suresi_gun: int, aktif_mi: bool) -> str:
    """Bakım Planları ekranındaki durum kuralı (sunucu.bakim_plani_durumu ile aynı)."""
    if not aktif_mi:
        return "Pasif"
    if kalan_gun < 0:
        return "Gecikmiş"
    if kalan_gun <= uyari_suresi_gun:
        return "Yaklaşıyor"
    return "Planlı"


def _kalibrasyon_mu(gorev_turu: str) -> bool:
    return (gorev_turu or "").strip().lower().startswith("kalibrasyon")


def bakim_plani_raporu(cursor, cihaz_id: int | None = None, tur: str | None = None, durum: str | None = None) -> dict:
    """tur: None | 'bakim' | 'kalibrasyon'; durum: None | gecikmis | yaklasiyor | planli | pasif."""
    kosullar, parametreler = [], []
    if cihaz_id is not None:
        kosullar.append("p.cihaz_id = %s")
        parametreler.append(cihaz_id)
    if tur == "kalibrasyon":
        kosullar.append("LOWER(BTRIM(p.gorev_turu)) LIKE 'kalibrasyon%%'")
    elif tur == "bakim":
        kosullar.append("LOWER(BTRIM(p.gorev_turu)) NOT LIKE 'kalibrasyon%%'")
    where = "WHERE " + " AND ".join(kosullar) if kosullar else ""

    cursor.execute(f"""
        SELECT p.plan_id, p.cihaz_id, c.envanter_kodu, c.cihaz_adi, p.gorev_turu, p.periyot_gun, COALESCE(p.uyari_suresi_gun, 0),
               p.sonraki_gorev_tarihi, (p.sonraki_gorev_tarihi - CURRENT_DATE), COALESCE(p.aktif_mi, TRUE),
               CASE WHEN LOWER(BTRIM(p.gorev_turu)) LIKE 'kalibrasyon%%'
                    THEN (SELECT MAX(COALESCE(k.kalibrasyon_baslangic_tarihi, k.islem_tarihi::date))
                          FROM cihaz_kalibrasyonlari k WHERE k.plan_id = p.plan_id)
                    ELSE (SELECT MAX(b.bakim_tarihi::date) FROM cihaz_bakimlari b WHERE b.plan_id = p.plan_id) END
        FROM cihaz_bakim_planlari p
        JOIN cihazlar c ON c.cihaz_id = p.cihaz_id
        {where}
        ORDER BY p.sonraki_gorev_tarihi, p.plan_id;
    """, parametreler)

    planlar = []
    for k in cursor.fetchall():
        kalan = int(k[8])
        durum_adi = plan_durumu(kalan, int(k[6]), bool(k[9]))
        if durum is not None and DURUMLAR[durum] != durum_adi:
            continue
        planlar.append({
            "plan_id": k[0], "cihaz_id": k[1], "envanter_kodu": k[2], "cihaz_adi": k[3], "gorev_turu": k[4],
            "tur": "Kalibrasyon" if _kalibrasyon_mu(k[4]) else "Bakım", "periyot_gun": k[5], "uyari_suresi_gun": int(k[6]),
            "sonraki_gorev_tarihi": k[7].isoformat(), "kalan_gun": kalan, "gecikme_gun": max(0, -kalan) if bool(k[9]) else 0,
            "aktif_mi": bool(k[9]), "durum": durum_adi, "son_yapilan": k[10].isoformat() if k[10] else None,
        })

    # Planı olmayan cihazlar: yalnızca cihaz süzgecine bağlıdır (tür/durum süzgecinden bağımsız); kullanım dışı cihazlar sayılmaz.
    cursor.execute(f"""
        SELECT c.cihaz_id, c.envanter_kodu, c.cihaz_adi FROM cihazlar c
        WHERE c.durum::text <> 'Kullanim_Disi'
          AND NOT EXISTS (SELECT 1 FROM cihaz_bakim_planlari p WHERE p.cihaz_id = c.cihaz_id AND COALESCE(p.aktif_mi, TRUE))
          {"AND c.cihaz_id = %s" if cihaz_id is not None else ""}
        ORDER BY c.envanter_kodu;
    """, [cihaz_id] if cihaz_id is not None else [])
    planisiz = [{"cihaz_id": k[0], "envanter_kodu": k[1], "cihaz_adi": k[2]} for k in cursor.fetchall()]

    geciken = sorted((p for p in planlar if p["durum"] == "Gecikmiş"), key=lambda p: (-p["gecikme_gun"], p["plan_id"]))
    yaklasan = [p for p in planlar if p["durum"] == "Yaklaşıyor"]
    aktif = [p for p in planlar if p["aktif_mi"]]

    cihazlar = {}
    for p in aktif:
        g = cihazlar.setdefault(p["cihaz_id"], {"cihaz_id": p["cihaz_id"], "cihaz": f"{p['envanter_kodu']} - {p['cihaz_adi']}",
                                                "geciken": 0, "yaklasan": 0, "plan_sayisi": 0})
        g["plan_sayisi"] += 1
        g["geciken"] += p["durum"] == "Gecikmiş"
        g["yaklasan"] += p["durum"] == "Yaklaşıyor"
    turler = {}
    for p in planlar:
        g = turler.setdefault(p["tur"], {"tur": p["tur"], "gecikmis": 0, "yaklasiyor": 0, "planli": 0, "pasif": 0})
        g[{v: k for k, v in DURUMLAR.items()}[p["durum"]]] += 1

    return {
        "ozet": {
            "aktif_plan": len(aktif),
            "geciken_plan": len(geciken),
            "yaklasan_plan": len(yaklasan),
            "planli_plan": sum(1 for p in planlar if p["durum"] == "Planlı"),
            "pasif_plan": sum(1 for p in planlar if p["durum"] == "Pasif"),
            "gecikme_orani": round(len(geciken) / len(aktif), 4) if aktif else None,
            "ortalama_gecikme_gun": round(sum(p["gecikme_gun"] for p in geciken) / len(geciken), 1) if geciken else None,
            "en_cok_gecikme_gun": geciken[0]["gecikme_gun"] if geciken else None,
            "plani_olmayan_cihaz": len(planisiz),
        },
        "geciken": geciken,
        "yaklasan": yaklasan,
        "planlar": planlar,
        "cihaz_ozeti": sorted(cihazlar.values(), key=lambda g: (-g["geciken"], -g["yaklasan"], g["cihaz"])),
        "tur_ozeti": sorted(turler.values(), key=lambda g: g["tur"]),
        "planisiz_cihazlar": planisiz,
    }
