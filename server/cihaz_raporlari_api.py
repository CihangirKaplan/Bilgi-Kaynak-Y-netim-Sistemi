"""Cihaz raporları ucu: bakım, kalibrasyon ve arıza kayıtları (salt okunur, DASH-003). `server/sunucu.py` içinden ayrıldı."""
from datetime import date

from fastapi import APIRouter, HTTPException

from server.vt_ayarlari import VT_AYARLARI
from server.vt_baglanti import vt_baglan
from server.yetki_baglama import yetkiyle_bagla

IZIN_ADI = "CIHAZ_ENVANTER_YONET"


def _tarih_metni(deger):
    return deger.isoformat() if deger is not None and hasattr(deger, "isoformat") else None


def cihaz_raporlari(
    baslangic_tarihi: date | None = None,
    bitis_tarihi: date | None = None,
    cihaz_id: int | None = None,
    kullanici_id: int | None = None,        # yetki bağımlılığı kayıt sırasında eklenir (router_olustur)
):
    """Bakım, kalibrasyon ve arıza kayıtlarını tarih/cihaz filtresiyle listeler (salt okunur)."""
    if (
        baslangic_tarihi is not None
        and bitis_tarihi is not None
        and bitis_tarihi < baslangic_tarihi
    ):
        raise HTTPException(status_code=422, detail="Bitiş tarihi başlangıç tarihinden önce olamaz.")

    if cihaz_id is not None and cihaz_id <= 0:
        raise HTTPException(status_code=422, detail="Geçerli bir cihaz seçilmelidir.")

    def kosul_olustur(tarih_sutunu, ek_tarih_sutunu=None):
        """Tarih sütunu seçilen aralıktaysa kayıt dahil edilir; ek sütun verilirse
        onun aralıkta olması da yeterlidir (örn. arıza: bildirim VEYA çözüm tarihi)."""
        kosullar = []
        parametreler = []

        def aralik(sutun):
            parcalar = []
            if baslangic_tarihi is not None:
                parcalar.append(f"{sutun} >= %s")
                parametreler.append(baslangic_tarihi)
            if bitis_tarihi is not None:
                parcalar.append(f"{sutun} < (%s::date + INTERVAL '1 day')")
                parametreler.append(bitis_tarihi)
            return "(" + " AND ".join(parcalar) + ")" if parcalar else None

        if baslangic_tarihi is not None or bitis_tarihi is not None:
            secenekler = [aralik(tarih_sutunu)]
            if ek_tarih_sutunu:
                secenekler.append(aralik(ek_tarih_sutunu))
            kosullar.append("(" + " OR ".join(secenekler) + ")")
        if cihaz_id is not None:
            kosullar.append("t.cihaz_id = %s")
            parametreler.append(cihaz_id)
        where = "WHERE " + " AND ".join(kosullar) if kosullar else ""
        return where, parametreler

    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        where, parametreler = kosul_olustur("t.bakim_tarihi")
        cursor.execute(f"""
            SELECT t.bakim_id, c.envanter_kodu, c.cihaz_adi, t.bakim_yapan_kisi,
                   t.yapilan_islem, t.maliyet, t.bakim_tarihi, t.sonraki_bakim_tarihi,
                   t.cihaz_id, t.bakim_baslangic_tarihi, t.bakim_bitis_tarihi
            FROM cihaz_bakimlari t
            JOIN cihazlar c ON t.cihaz_id = c.cihaz_id
            {where}
            ORDER BY t.bakim_tarihi DESC;
        """, parametreler)
        bakimlar = [
            {
                "bakim_id": k[0],
                "cihaz_id": k[8],
                "cihaz": f"{k[1]} - {k[2]}",
                "bakim_yapan_kisi": k[3],
                "yapilan_islem": k[4],
                "maliyet": float(k[5]) if k[5] is not None else 0.0,
                "bakim_tarihi": _tarih_metni(k[6]),
                "sonraki_bakim_tarihi": _tarih_metni(k[7]),
                # Eski kayıtlarda başlangıç/bitiş boşsa bakım tarihi kullanılır.
                "bakim_baslangic_tarihi": _tarih_metni(k[9] or k[6]),
                "bakim_bitis_tarihi": _tarih_metni(k[10] or k[6]),
            }
            for k in cursor.fetchall()
        ]

        # Filtre ve sıralama, kaydın girildiği zamana (islem_tarihi) değil kalibrasyonun gerçek başlangıç tarihine
        # göre yapılır (Kalibrasyon ekranı da bunu gösterir); eski kayıtlarda tarih boşsa islem_tarihi kullanılır.
        kalibrasyon_gunu = "COALESCE(t.kalibrasyon_baslangic_tarihi, t.islem_tarihi::date)"
        where, parametreler = kosul_olustur(kalibrasyon_gunu)
        cursor.execute(f"""
            SELECT t.kalibrasyon_id, c.envanter_kodu, c.cihaz_adi, t.kalibrasyon_yapan_kurum,
                   t.sertifika_no, t.islem_tarihi, t.gecerlilik_tarihi, t.cihaz_id,
                   t.kalibrasyon_baslangic_tarihi, t.kalibrasyon_bitis_tarihi
            FROM cihaz_kalibrasyonlari t
            JOIN cihazlar c ON t.cihaz_id = c.cihaz_id
            {where}
            ORDER BY {kalibrasyon_gunu} DESC, t.kalibrasyon_id DESC;
        """, parametreler)
        kalibrasyonlar = [
            {
                "kalibrasyon_id": k[0],
                "cihaz_id": k[7],
                "cihaz": f"{k[1]} - {k[2]}",
                "kalibrasyon_yapan_kurum": k[3],
                "sertifika_no": k[4],
                "islem_tarihi": _tarih_metni(k[5]),
                "gecerlilik_tarihi": _tarih_metni(k[6]),
                # Eski kayıtlarda başlangıç/bitiş boşsa işlem tarihinin günü kullanılır.
                "kalibrasyon_baslangic_tarihi": _tarih_metni(k[8] or (k[5].date() if k[5] else None)),
                "kalibrasyon_bitis_tarihi": _tarih_metni(k[9] or (k[5].date() if k[5] else None)),
            }
            for k in cursor.fetchall()
        ]

        where, parametreler = kosul_olustur("t.bildirim_tarihi", "t.cozum_tarihi")
        cursor.execute(f"""
            SELECT t.ariza_id, c.envanter_kodu, c.cihaz_adi, t.bildiren_personel,
                   t.ariza_aciklamasi, t.bildirim_tarihi, t.cozum_tarihi, t.cozuldu_mu,
                   t.cihaz_id, t.ariza_baslik, t.aciliyet
            FROM cihaz_arizalari t
            JOIN cihazlar c ON t.cihaz_id = c.cihaz_id
            {where}
            ORDER BY t.bildirim_tarihi DESC;
        """, parametreler)
        arizalar = [
            {
                "ariza_id": k[0],
                "cihaz_id": k[8],
                "cihaz": f"{k[1]} - {k[2]}",
                "bildiren_personel": k[3],
                "ariza_baslik": k[9],
                "aciliyet": k[10],
                # Raporda başlık ve açıklama tek metin olarak gösterilir.
                "ariza_aciklamasi": f"{k[9]}: {k[4]}" if k[4] else k[9],
                "bildirim_tarihi": _tarih_metni(k[5]),
                "cozum_tarihi": _tarih_metni(k[6]),
                "durum": "Çözüldü" if k[7] else "Açık",
            }
            for k in cursor.fetchall()
        ]

        # Cihazların güncel durumu (tarih filtresinden bağımsız; yalnızca cihaz filtresi uygulanır).
        if cihaz_id is not None:
            cursor.execute(
                "SELECT cihaz_id, envanter_kodu, cihaz_adi, marka_model, durum "
                "FROM cihazlar WHERE cihaz_id = %s ORDER BY envanter_kodu;",
                [cihaz_id],
            )
        else:
            cursor.execute(
                "SELECT cihaz_id, envanter_kodu, cihaz_adi, marka_model, durum "
                "FROM cihazlar ORDER BY envanter_kodu;"
            )
        cihazlar = [
            {
                "cihaz_id": k[0],
                "envanter_kodu": k[1],
                "cihaz_adi": k[2],
                "marka_model": k[3],
                "durum": k[4],
            }
            for k in cursor.fetchall()
        ]

        # Kalibrasyon geçerliliği ve planlı bakım "bugünkü durum"dur; tarih filtresinden bağımsızdır.
        cihaz_kosulu = "WHERE t.cihaz_id = %s" if cihaz_id is not None else ""
        cihaz_parametresi = [cihaz_id] if cihaz_id is not None else []

        cursor.execute(f"""
            SELECT DISTINCT ON (t.cihaz_id)
                   t.cihaz_id, t.kalibrasyon_yapan_kurum, t.sertifika_no,
                   t.islem_tarihi, t.gecerlilik_tarihi
            FROM cihaz_kalibrasyonlari t
            {cihaz_kosulu}
            ORDER BY t.cihaz_id, t.gecerlilik_tarihi DESC NULLS LAST, t.islem_tarihi DESC;
        """, cihaz_parametresi)
        son_kalibrasyonlar = {
            k[0]: {
                "kalibrasyon_yapan_kurum": k[1],
                "sertifika_no": k[2],
                "islem_tarihi": _tarih_metni(k[3]),
                "gecerlilik_tarihi": _tarih_metni(k[4]),
            }
            for k in cursor.fetchall()
        }

        planli_kosul = "WHERE t.sonraki_bakim_tarihi IS NOT NULL" + (
            " AND t.cihaz_id = %s" if cihaz_id is not None else ""
        )
        cursor.execute(f"""
            SELECT DISTINCT ON (t.cihaz_id) t.cihaz_id, t.sonraki_bakim_tarihi
            FROM cihaz_bakimlari t
            {planli_kosul}
            ORDER BY t.cihaz_id, t.bakim_tarihi DESC, t.bakim_id DESC;
        """, cihaz_parametresi)
        sonraki_bakimlar = {k[0]: _tarih_metni(k[1]) for k in cursor.fetchall()}

        for cihaz in cihazlar:
            cihaz["son_kalibrasyon"] = son_kalibrasyonlar.get(cihaz["cihaz_id"])
            cihaz["sonraki_bakim_tarihi"] = sonraki_bakimlar.get(cihaz["cihaz_id"])

        return {
            "ozet": {
                "bakim_sayisi": len(bakimlar),
                "toplam_bakim_maliyeti": round(sum(b["maliyet"] for b in bakimlar), 2),
                "kalibrasyon_sayisi": len(kalibrasyonlar),
                "ariza_sayisi": len(arizalar),
                "acik_ariza_sayisi": sum(1 for a in arizalar if a["durum"] == "Açık"),
            },
            "bakimlar": bakimlar,
            "kalibrasyonlar": kalibrasyonlar,
            "arizalar": arizalar,
            "cihazlar": cihazlar,
        }
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


def router_olustur(izin_kontrol) -> APIRouter:
    """`izin_kontrol`: `server.sunucu.izin_kontrol` (kimlik doğrulama + izin kontrolü bağımlılığı üreticisi)."""
    router = APIRouter()
    router.add_api_route(
        "/api/cihaz-raporlari",
        yetkiyle_bagla(cihaz_raporlari, "kullanici_id", izin_kontrol(IZIN_ADI)),
        methods=["GET"],
    )
    return router
