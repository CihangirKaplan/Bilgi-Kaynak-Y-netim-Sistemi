"""Danışma Masası raporları ucu (salt okunur). `server/sunucu.py` içinden ayrıldı."""
from datetime import date

from fastapi import APIRouter, HTTPException

from server.vt_ayarlari import VT_AYARLARI
from server.vt_baglanti import vt_baglan
from server.yetki_baglama import yetkiyle_bagla


def danisma_raporlari(
    baslangic_tarihi: date | None = None,
    bitis_tarihi: date | None = None,
    ogrenci_id: int | None = None,
    kullanici_id: int | None = None
):
    if (
        baslangic_tarihi is not None
        and bitis_tarihi is not None
        and bitis_tarihi < baslangic_tarihi
    ):
        raise HTTPException(
            status_code=422,
            detail="Bitiş tarihi başlangıç tarihinden önce olamaz."
        )

    if ogrenci_id is not None and ogrenci_id <= 0:
        raise HTTPException(
            status_code=422,
            detail="Geçerli bir öğrenci seçilmelidir."
        )

    conn = None
    cursor = None

    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        kosullar = []
        parametreler = []

        if baslangic_tarihi is not None:
            kosullar.append("d.baslangic_zamani >= %s")
            parametreler.append(baslangic_tarihi)

        if bitis_tarihi is not None:
            kosullar.append(
                "d.baslangic_zamani < (%s::date + INTERVAL '1 day')"
            )
            parametreler.append(bitis_tarihi)

        if ogrenci_id is not None:
            kosullar.append("d.ogrenci_id = %s")
            parametreler.append(ogrenci_id)

        where = (
            "WHERE " + " AND ".join(kosullar)
            if kosullar else ""
        )

        cursor.execute(f"""
            SELECT
                d.oturum_id,
                d.ogrenci_id,
                o.ad_soyad,
                o.ogrenci_numarasi,
                d.baslangic_zamani,
                d.bitis_zamani,
                d.onaylandi_mi,
                o.aktif_mi
            FROM danisma_masasi_oturumlari d
            JOIN ogrenciler o
                ON o.ogrenci_id = d.ogrenci_id
            {where}
            ORDER BY d.baslangic_zamani DESC, d.oturum_id DESC;
        """, parametreler)

        kayitlar = cursor.fetchall()

        ozet = {
            "toplam_gorev": 0,
            "devam_eden": 0,
            "tamamlanan": 0,
            "onay_bekleyen": 0,
            "onaylanan": 0,
            "toplam_calisma_saniye": 0,
            "onaylanan_calisma_saniye": 0
        }

        ogrenciler = {}
        oturumlar = []

        for (
            oturum_id,
            ogr_id,
            ad_soyad,
            ogrenci_no,
            baslangic,
            bitis,
            onaylandi,
            ogrenci_aktif
        ) in kayitlar:

            tamamlandi = bitis is not None

            # Rapor toplamlarına yalnızca tamamlanan
            # görevlerin kesinleşmiş süreleri eklenir.
            saniye = (
                max(0, int((bitis - baslangic).total_seconds()))
                if tamamlandi else 0
            )

            ozet["toplam_gorev"] += 1

            if tamamlandi:
                ozet["tamamlanan"] += 1
                ozet["toplam_calisma_saniye"] += saniye

                if onaylandi:
                    ozet["onaylanan"] += 1
                    ozet["onaylanan_calisma_saniye"] += saniye
                else:
                    ozet["onay_bekleyen"] += 1
            else:
                ozet["devam_eden"] += 1

            if ogr_id not in ogrenciler:
                ogrenciler[ogr_id] = {
                    "ogrenci_id": ogr_id,
                    "ad_soyad": ad_soyad,
                    "ogrenci_numarasi": ogrenci_no,
                    "aktif_mi": bool(ogrenci_aktif),
                    "toplam_gorev": 0,
                    "devam_eden": 0,
                    "onay_bekleyen": 0,
                    "onaylanan": 0,
                    "toplam_saniye": 0,
                    "onaylanan_saniye": 0
                }

            ogr_ozet = ogrenciler[ogr_id]
            ogr_ozet["toplam_gorev"] += 1
            ogr_ozet["toplam_saniye"] += saniye

            if not tamamlandi:
                ogr_ozet["devam_eden"] += 1
            elif onaylandi:
                ogr_ozet["onaylanan"] += 1
                ogr_ozet["onaylanan_saniye"] += saniye
            else:
                ogr_ozet["onay_bekleyen"] += 1

            oturumlar.append({
                "oturum_id": oturum_id,
                "ogrenci_id": ogr_id,
                "ad_soyad": ad_soyad,
                "ogrenci_numarasi": ogrenci_no,
                "ogrenci_aktif_mi": bool(ogrenci_aktif),
                "baslangic_zamani": baslangic.isoformat(),
                "bitis_zamani": (
                    bitis.isoformat() if bitis else None
                ),
                "toplam_saniye": saniye,
                "durum": (
                    "TAMAMLANDI" if tamamlandi else "AKTIF"
                ),
                "onaylandi_mi": onaylandi
            })

        return {
            "ozet": ozet,
            "ogrenci_ozetleri": sorted(
                ogrenciler.values(),
                key=lambda x: x["ad_soyad"].casefold()
            ),
            "oturumlar": oturumlar
        }

    except HTTPException:
        raise

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Danışma masası raporları alınamadı."
        )

    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


# (yol, uç fonksiyonu, gereken izin): yetki bağımlılığı kayıt sırasında eklenir.
UCLAR = [
    ("/api/danisma/raporlar", danisma_raporlari, "DANISMA_OTURUMU_GORUNTULE"),
]


def router_olustur(izin_kontrol) -> APIRouter:
    """`izin_kontrol`: `server.sunucu.izin_kontrol` (kimlik doğrulama + izin kontrolü bağımlılığı üreticisi)."""
    router = APIRouter()
    for yol, fonksiyon, izin in UCLAR:
        router.add_api_route(yol, yetkiyle_bagla(fonksiyon, "kullanici_id", izin_kontrol(izin)), methods=["GET"])
    return router
