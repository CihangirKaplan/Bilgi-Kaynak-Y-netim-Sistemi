"""Denetim (audit) kayıtlarını listeleyen uç (salt okunur). `server/sunucu.py` içinden ayrıldı."""
from datetime import date

from fastapi import APIRouter, HTTPException, Query
from psycopg2.extras import Json

from server.vt_ayarlari import VT_AYARLARI
from server.vt_baglanti import vt_baglan
from server.yetki_baglama import yetkiyle_bagla

IZIN_ADI = "AUDIT_KAYITLARI_INCELE"


def audit_kayitlarini_getir(
    kullanici: str | None = Query(None, max_length=100),
    olay_turu: list[str] | None = Query(None),
    baslangic_tarihi: date | None = None,
    bitis_tarihi: date | None = None,
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    ozet: bool = Query(True),
    kullanici_id: int | None = None,        # yetki bağımlılığı kayıt sırasında eklenir (router_olustur)
):
    """Denetim kayıtları (salt okunur, sayfalı; ozet=false ile sayım atlanır).

    `ozet=false` ilk sayfadan sonraki sayfalarda verilir: süzgeçli kayıt sayımı yalnızca ilk sayfada yapılır, böylece her
    sayfa geçişi tüm süzgeçli kayıtları yeniden saymaz (kayıt sayısı büyüdükçe yavaşlamaz)."""
    if (
        baslangic_tarihi is not None
        and bitis_tarihi is not None
        and baslangic_tarihi > bitis_tarihi
    ):
        raise HTTPException(
            status_code=422,
            detail="Başlangıç tarihi bitiş tarihinden sonra olamaz."
        )

    if olay_turu:
        gecerli_olaylar = {
            "LOGIN", "LOGIN_FAILED", "CREATE", "UPDATE",
            "CANCEL", "ROLE_CHANGE", "DEVICE_STATUS_CHANGE", "DELETE", "EXPORT",
            "PASSWORD_RESET", "PASSWORD_CHANGE", "PASSWORD_CHANGE_FAILED", "LOGOUT", "VIEW"
        }
        if (
            len(olay_turu) > len(gecerli_olaylar)
            or not set(olay_turu).issubset(gecerli_olaylar)
        ):
            raise HTTPException(
                status_code=422,
                detail="Geçersiz işlem türü seçildi."
            )

    kosullar = []
    parametreler = []

    if kullanici:
        # % ve _ aramada joker değil, düz karakter sayılır (aksi halde "%" yazınca herkes listelenirdi).
        kacisli = kullanici.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        kosullar.append("k.kullanici_adi ILIKE %s ESCAPE '\\'")
        parametreler.append(f"%{kacisli}%")

    if olay_turu:
        kosullar.append("d.olay_turu::text = ANY(%s)")
        parametreler.append(olay_turu)

    if baslangic_tarihi:
        kosullar.append("d.olusturulma_tarihi >= %s")
        parametreler.append(baslangic_tarihi)

    if bitis_tarihi:
        kosullar.append(
            "d.olusturulma_tarihi < (%s::date + INTERVAL '1 day')"
        )
        parametreler.append(bitis_tarihi)

    where_sql = (
        "WHERE " + " AND ".join(kosullar)
        if kosullar else ""
    )

    from_sql = """
        FROM denetim_kayitlari d
        LEFT JOIN kullanicilar k
            ON k.kullanici_id = d.kullanici_id
    """

    conn = None
    cursor = None

    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        ozet_verisi = None
        if ozet:
            cursor.execute(
                f"""
                SELECT
                    COUNT(*),
                    COUNT(*) FILTER (
                        WHERE d.olay_turu::text = 'LOGIN_FAILED'
                    ),
                    COUNT(*) FILTER (
                        WHERE d.olay_turu::text IN (
                            'CREATE', 'UPDATE', 'ROLE_CHANGE', 'DELETE',
                            'CANCEL', 'DEVICE_STATUS_CHANGE'
                        )
                    ),
                    COUNT(*) FILTER (
                        WHERE d.olusturulma_tarihi >= CURRENT_DATE
                          AND d.olusturulma_tarihi <
                              CURRENT_DATE + INTERVAL '1 day'
                    )
                {from_sql}
                {where_sql}
                """,
                tuple(parametreler)
            )

            toplam, basarisiz, islemler, bugun = cursor.fetchone()
            ozet_verisi = {
                "toplam_kayit": toplam,
                "basarisiz_giris": basarisiz,
                "kullanici_islemleri": islemler,
                "bugunku_islemler": bugun
            }

        cursor.execute(
            f"""
            SELECT
                d.denetim_id,
                d.kullanici_id,
                k.kullanici_adi,
                d.olay_turu::text,
                d.hedef_tablo,
                d.hedef_kayit_id,
                d.olusturulma_tarihi,
                (
                    SELECT hedef.kullanici_adi
                    FROM kullanicilar hedef
                    WHERE d.hedef_tablo = 'kullanicilar'
                      AND hedef.kullanici_id = d.hedef_kayit_id
                ) AS hedef_kullanici_adi,
                d.ayrinti,
                d.istemci_adresi
            {from_sql}
            {where_sql}
            ORDER BY d.olusturulma_tarihi DESC, d.denetim_id DESC
            LIMIT %s OFFSET %s
            """,
            tuple(parametreler) + (limit, offset)
        )

        kayitlar = []

        for satir in cursor.fetchall():
            kayitlar.append({
                "denetim_id": satir[0],
                "kullanici_id": satir[1],
                "kullanici_adi": satir[2] or "Bilinmeyen kullanıcı",
                "olay_turu": satir[3],
                "hedef_tablo": satir[4],
                "hedef_kayit_id": satir[5],
                "hedef_kullanici_adi": satir[7],
                "ayrinti": satir[8],
                "istemci_adresi": satir[9],
                "olusturulma_tarihi": (
                    satir[6].isoformat() if satir[6] else None
                )
            })

        if offset == 0:
            # Denetim kayıtlarına kimin baktığı da kayıt altına alınır (ilk sayfa; aynı kullanıcı için 10 dakikada bir, sayfa yenilemeleri günlüğü doldurmasın).
            cursor.execute(
                """
                INSERT INTO denetim_kayitlari (kullanici_id, olay_turu, hedef_tablo, ayrinti)
                SELECT %s, 'VIEW'::denetim_olay_turu, 'denetim_kayitlari', %s
                WHERE NOT EXISTS (
                    SELECT 1 FROM denetim_kayitlari
                    WHERE kullanici_id = %s AND olay_turu = 'VIEW'::denetim_olay_turu AND hedef_tablo = 'denetim_kayitlari'
                      AND olusturulma_tarihi > CURRENT_TIMESTAMP - INTERVAL '10 minutes'
                );
                """,
                (kullanici_id, Json({"ne": "denetim kayıtları görüntülendi"}), kullanici_id),
            )
            conn.commit()

        return {
            "ozet": ozet_verisi,
            "kayitlar": kayitlar,
            "limit": limit,
            "offset": offset
        }

    except HTTPException:
        raise

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Denetim kayıtları alınamadı."
        )

    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


def router_olustur(izin_kontrol) -> APIRouter:
    """`izin_kontrol`: `server.sunucu.izin_kontrol` (kimlik doğrulama + izin kontrolü bağımlılığı üreticisi)."""
    router = APIRouter()
    router.add_api_route(
        "/api/audit-kayitlari",
        yetkiyle_bagla(audit_kayitlarini_getir, "kullanici_id", izin_kontrol(IZIN_ADI)),
        methods=["GET"],
    )
    return router
