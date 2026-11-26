"""Öğrenci puan raporu ucu (salt okunur). `server/sunucu.py` içinden ayrıldı."""
from datetime import date as _ogr_date

from fastapi import APIRouter, HTTPException

from server.ortak_sabitler import OGRENCI_TUR_ETIKETLERI
from server.vt_ayarlari import VT_AYARLARI
from server.vt_baglanti import vt_baglan
from server.yetki_baglama import yetkiyle_bagla


PUAN_RAPORU_DURUMLARI = ("aktif", "pasif")


def puan_raporu(
    baslangic: _ogr_date | None = None,
    bitis: _ogr_date | None = None,
    tur: str | None = None,
    durum: str | None = None,
    puansizlari_goster: bool = True,
    detay: bool = False,
    yetkili_id: int | None = None
):
    """Öğrenci puan sıralaması: seçilen dönemdeki toplam puana göre en yüksekten en düşüğe.

    Puan = adet x kaydın girildiği andaki faaliyet puanı. Pasif öğrenciler listede kalır (durum alanıyla).
    Eşit puanlılar aynı sırayı alır (1, 2, 2, 4); puanı olmayanın sırası yoktur (None).
    detay=true ise listedeki öğrencilerin tek tek faaliyet kayıtları da döner (Excel için)."""
    if baslangic is not None and bitis is not None and baslangic > bitis:
        raise HTTPException(status_code=422, detail="Başlangıç tarihi bitişten büyük olamaz.")
    if tur is not None and tur not in OGRENCI_TUR_ETIKETLERI:
        raise HTTPException(status_code=422, detail="Geçersiz öğrenci türü.")
    if durum is not None and durum not in PUAN_RAPORU_DURUMLARI:
        raise HTTPException(status_code=422, detail="Geçersiz öğrenci durumu.")

    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        tarih_kosullari = []
        tarih_parametreleri = []
        if baslangic is not None:
            tarih_kosullari.append("t.faaliyet_tarihi >= %s")
            tarih_parametreleri.append(baslangic)
        if bitis is not None:
            tarih_kosullari.append("t.faaliyet_tarihi <= %s")
            tarih_parametreleri.append(bitis)

        kosullar = []
        kosul_parametreleri = []
        if tur is not None:
            kosullar.append("o.tur::text = %s")
            kosul_parametreleri.append(tur)
        if durum is not None:
            kosullar.append("o.aktif_mi = %s")
            kosul_parametreleri.append(durum == "aktif")

        birlesim = " AND ".join(["t.ogrenci_id = o.ogrenci_id"] + tarih_kosullari)
        where = "WHERE " + " AND ".join(kosullar) if kosullar else ""
        having = "" if puansizlari_goster else "HAVING COUNT(t.takip_id) > 0"

        cursor.execute(f"""
            SELECT
                o.ogrenci_id,
                o.ad_soyad,
                o.ogrenci_numarasi,
                o.tur::text,
                o.aktif_mi,
                COALESCE(SUM(t.adet * t.kayit_puani), 0) AS toplam_puan,
                COUNT(t.takip_id),
                MAX(t.faaliyet_tarihi)
            FROM ogrenciler o
            LEFT JOIN ogrenci_faaliyet_takip t
                ON {birlesim}
            {where}
            GROUP BY o.ogrenci_id, o.ad_soyad, o.ogrenci_numarasi, o.tur, o.aktif_mi
            {having}
            ORDER BY toplam_puan DESC, o.ad_soyad, o.ogrenci_id;
        """, tarih_parametreleri + kosul_parametreleri)

        ogrenciler = []
        onceki_puan = None
        onceki_sira = None
        for sira_no, (ogr_id, ad, numara, ogr_tur, aktif, puan, adet, son) in enumerate(cursor.fetchall(), start=1):
            puan = float(puan)
            if puan > 0:
                sira = onceki_sira if puan == onceki_puan else sira_no
                onceki_puan, onceki_sira = puan, sira
            else:
                sira = None
            ogrenciler.append({
                "sira": sira,
                "ogrenci_id": ogr_id,
                "ad_soyad": ad,
                "ogrenci_numarasi": numara,
                "tur": ogr_tur,
                "tur_etiketi": OGRENCI_TUR_ETIKETLERI.get(ogr_tur, ogr_tur),
                "aktif_mi": bool(aktif),
                "toplam_puan": puan,
                "faaliyet_sayisi": int(adet),
                "son_faaliyet_tarihi": son.isoformat() if son else None,
            })

        puanlilar = [o for o in ogrenciler if o["toplam_puan"] > 0]
        toplam = sum(o["toplam_puan"] for o in ogrenciler)
        en_yuksek = max((o["toplam_puan"] for o in ogrenciler), default=0)
        ozet = {
            "ogrenci_sayisi": len(ogrenciler),
            "puanli_ogrenci_sayisi": len(puanlilar),
            "faaliyet_kaydi_sayisi": sum(o["faaliyet_sayisi"] for o in ogrenciler),
            "toplam_puan": toplam,
            "ortalama_puan": (toplam / len(puanlilar)) if puanlilar else 0,
            "en_yuksek_puan": en_yuksek,
            "en_yuksek_ogrenciler": [o["ad_soyad"] for o in puanlilar if o["toplam_puan"] == en_yuksek],
        }

        sonuc = {
            "filtre": {
                "baslangic": baslangic.isoformat() if baslangic else None,
                "bitis": bitis.isoformat() if bitis else None,
                "tur": tur,
                "durum": durum,
                "puansizlari_goster": puansizlari_goster,
            },
            "ozet": ozet,
            "ogrenciler": ogrenciler,
        }

        if detay:
            detaylar = []
            tarih_sql = "".join(" AND " + k for k in tarih_kosullari)      # yalnızca sabit parçalar
            if ogrenciler:
                cursor.execute(f"""
                    SELECT
                        t.ogrenci_id,
                        t.faaliyet_tarihi,
                        f.faaliyet_adi,
                        t.adet,
                        COALESCE(b.birim_adi, ''),
                        t.kayit_puani,
                        (t.adet * t.kayit_puani)
                    FROM ogrenci_faaliyet_takip t
                    JOIN faaliyetler f ON f.faaliyet_id = t.faaliyet_id
                    LEFT JOIN faaliyet_birimleri b ON b.birim_id = t.birim_id
                    WHERE t.ogrenci_id = ANY(%s)
                    {tarih_sql}
                    ORDER BY t.ogrenci_id, t.faaliyet_tarihi DESC, t.takip_id DESC;
                """, [[o["ogrenci_id"] for o in ogrenciler]] + tarih_parametreleri)
                for ogr_id, tarih, faaliyet, adet, birim, birim_puan, toplam_puan in cursor.fetchall():
                    detaylar.append({
                        "ogrenci_id": ogr_id,
                        "tarih": tarih.isoformat(),
                        "faaliyet": faaliyet,
                        "adet": adet,
                        "birim": birim,
                        "birim_puan": float(birim_puan),
                        "toplam_puan": float(toplam_puan),
                    })
            sonuc["detaylar"] = detaylar

        return sonuc

    except HTTPException:
        raise

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Puan raporu alınamadı."
        )

    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


# (yol, uç fonksiyonu, yetki parametresi, gereken izin): yetki bağımlılığı kayıt sırasında eklenir.
# İzin None ise yalnızca oturum açmış olmak yeter (kimlik bağımlılığı).
UCLAR = [
    ("/api/puan-raporu", puan_raporu, "yetkili_id", "FAALIYET_KAYITLARI_DUZENLE"),
]


def router_olustur(izin_kontrol) -> APIRouter:
    """`izin_kontrol`: `server.sunucu.izin_kontrol`."""
    router = APIRouter()
    for yol, fonksiyon, parametre, izin in UCLAR:
        router.add_api_route(yol, yetkiyle_bagla(fonksiyon, parametre, izin_kontrol(izin)), methods=["GET"])
    return router
