"""Danışma Masası uçları: öğrencinin kendi oturumu (görev) ve yönetici ekranı (onay, düzenleme, listeleme). `server/sunucu.py` içinden ayrıldı."""
from datetime import datetime

from fastapi import APIRouter, HTTPException
import psycopg2

from server.denetim import denetim_kaydi_olustur
from server.modeller import DanismaGorevDuzenleModeli, DanismaGorevOlusturModeli
from server.ortak_sabitler import OGRENCI_TUR_ETIKETLERI
from server.vt_ayarlari import VT_AYARLARI
from server.vt_baglanti import vt_baglan
from server.yetki_baglama import yetkiyle_bagla


def danisma_oturumu_baslat(
    kullanici_id: int | None = None
):
    conn = None
    cursor = None

    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        # Öğrencinin kaydını kilitle.
        # Eşzamanlı başlatma işlemlerini sıraya alır.
        cursor.execute(
            """
            SELECT ogrenci_id
            FROM ogrenciler
            WHERE kullanici_id = %s
              AND aktif_mi = TRUE
            FOR UPDATE;
            """,
            (kullanici_id,)
        )

        ogrenci = cursor.fetchone()

        if ogrenci is None:
            raise HTTPException(
                status_code=403,
                detail="Hesabınız bir öğrenci kaydına bağlı değil. Lütfen yöneticinize başvurun."
            )

        ogrenci_id = ogrenci[0]

        # Açık oturum kontrolü
        cursor.execute(
            """
            SELECT oturum_id
            FROM danisma_masasi_oturumlari
            WHERE ogrenci_id = %s
              AND bitis_zamani IS NULL;
            """,
            (ogrenci_id,)
        )

        if cursor.fetchone() is not None:
            raise HTTPException(
                status_code=409,
                detail="Zaten devam eden bir göreviniz bulunuyor."
            )

        # Yeni görev başlat
        cursor.execute(
            """
            INSERT INTO danisma_masasi_oturumlari
                (ogrenci_id, baslangic_zamani)
            VALUES (%s, CURRENT_TIMESTAMP)
            RETURNING oturum_id, baslangic_zamani;
            """,
            (ogrenci_id,)
        )

        oturum_id, baslangic = cursor.fetchone()

        # Audit kaydı
        cursor.execute(
            """
            INSERT INTO denetim_kayitlari
                (kullanici_id, olay_turu,
                 hedef_tablo, hedef_kayit_id)
            VALUES (%s, %s, %s, %s);
            """,
            (
                kullanici_id,
                "CREATE",
                "danisma_masasi_oturumlari",
                oturum_id
            )
        )

        conn.commit()

        return {
            "mesaj": "Danışma masası göreviniz başlatıldı.",
            "oturum_id": oturum_id,
            "baslangic_zamani": baslangic.isoformat(),
            "durum": "AKTIF"
        }
    except psycopg2.errors.UniqueViolation:
        if conn is not None:
            conn.rollback()

        raise HTTPException(
            status_code=409,
            detail="Zaten devam eden bir göreviniz bulunuyor."
        )
    except HTTPException:
        if conn is not None:
            conn.rollback()
        raise

    except Exception:
        if conn is not None:
            conn.rollback()

        raise HTTPException(
            status_code=500,
            detail="Görev başlatılırken bir hata oluştu."
        )

    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


def danisma_oturumu_bitir(
    kullanici_id: int | None = None
):
    conn = None
    cursor = None

    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        # Giriş yapan öğrenciyi bul ve kilitle
        cursor.execute("""
            SELECT ogrenci_id
            FROM ogrenciler
            WHERE kullanici_id = %s
              AND aktif_mi = TRUE
            FOR UPDATE;
        """, (kullanici_id,))

        ogrenci = cursor.fetchone()

        if ogrenci is None:
            raise HTTPException(
                status_code=403,
                detail="Hesabınız bir öğrenci kaydına bağlı değil. Lütfen yöneticinize başvurun."
            )

        ogrenci_id = ogrenci[0]

        # Öğrencinin açık görevini bul
        cursor.execute("""
            SELECT oturum_id
            FROM danisma_masasi_oturumlari
            WHERE ogrenci_id = %s
              AND bitis_zamani IS NULL
            FOR UPDATE;
        """, (ogrenci_id,))

        oturum = cursor.fetchone()

        if oturum is None:
            raise HTTPException(
                status_code=409,
                detail="Devam eden bir göreviniz bulunmuyor."
            )

        oturum_id = oturum[0]

        # Görevi sonlandır
        cursor.execute("""
            UPDATE danisma_masasi_oturumlari
            SET bitis_zamani = clock_timestamp()
            WHERE oturum_id = %s
            RETURNING baslangic_zamani, bitis_zamani;
        """, (oturum_id,))

        baslangic, bitis = cursor.fetchone()

        toplam_saniye = max(
            0, int((bitis - baslangic).total_seconds())
        )

        saat, kalan = divmod(toplam_saniye, 3600)
        dakika = kalan // 60

        # Audit kaydı
        cursor.execute("""
            INSERT INTO denetim_kayitlari
                (kullanici_id, olay_turu,
                 hedef_tablo, hedef_kayit_id)
            VALUES (%s, %s, %s, %s);
        """, (
            kullanici_id,
            "UPDATE",
            "danisma_masasi_oturumlari",
            oturum_id
        ))

        conn.commit()

        return {
            "mesaj": "Göreviniz başarıyla tamamlandı.",
            "oturum_id": oturum_id,
            "baslangic_zamani": baslangic.isoformat(),
            "bitis_zamani": bitis.isoformat(),
            "toplam_saniye": toplam_saniye,
            "toplam_dakika": toplam_saniye // 60,
            "calisilan_sure": f"{saat} saat {dakika} dakika",
            "durum": "TAMAMLANDI"
        }

    except HTTPException:
        if conn is not None:
            conn.rollback()
        raise

    except Exception:
        if conn is not None:
            conn.rollback()

        raise HTTPException(
            status_code=500,
            detail="Görev bitirilirken bir hata oluştu."
        )

    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


def danisma_aktif_oturum(
    kullanici_id: int | None = None
):
    conn = None
    cursor = None

    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        # Giriş yapan öğrenciyi bul
        cursor.execute("""
            SELECT ogrenci_id
            FROM ogrenciler
            WHERE kullanici_id = %s
              AND aktif_mi = TRUE;
        """, (kullanici_id,))

        ogrenci = cursor.fetchone()

        if ogrenci is None:
            raise HTTPException(
                status_code=403,
                detail="Hesabınız bir öğrenci kaydına bağlı değil. Lütfen yöneticinize başvurun."
            )

        # Devam eden görevi sorgula
        cursor.execute("""
            SELECT
                oturum_id,
                baslangic_zamani,
                clock_timestamp()::timestamp
            FROM danisma_masasi_oturumlari
            WHERE ogrenci_id = %s
              AND bitis_zamani IS NULL
            ORDER BY baslangic_zamani DESC
            LIMIT 1;
        """, (ogrenci[0],))

        oturum = cursor.fetchone()

        if oturum is None:
            return {
                "durum": "PASIF",
                "mesaj": "Devam eden göreviniz bulunmuyor.",
                "oturum_id": None,
                "calisilan_sure": "0 saat 0 dakika",
                "toplam_saniye": 0
            }

        oturum_id, baslangic, simdi = oturum

        toplam_saniye = max(
            0, int((simdi - baslangic).total_seconds())
        )

        saat, kalan = divmod(toplam_saniye, 3600)
        dakika = kalan // 60

        return {
            "durum": "AKTIF",
            "oturum_id": oturum_id,
            "baslangic_zamani": baslangic.isoformat(),
            "toplam_saniye": toplam_saniye,
            "toplam_dakika": toplam_saniye // 60,
            "calisilan_sure": f"{saat} saat {dakika} dakika"
        }

    except HTTPException:
        raise

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Aktif görev bilgisi alınamadı."
        )

    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


def danisma_oturum_gecmisi(
    kullanici_id: int | None = None
):
    conn = None
    cursor = None

    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT ogrenci_id
            FROM ogrenciler
            WHERE kullanici_id = %s
              AND aktif_mi = TRUE;
        """, (kullanici_id,))

        ogrenci = cursor.fetchone()

        if ogrenci is None:
            raise HTTPException(
                status_code=403,
                detail="Hesabınız bir öğrenci kaydına bağlı değil. Lütfen yöneticinize başvurun."
            )

        cursor.execute("""
            SELECT oturum_id,
                   baslangic_zamani,
                   bitis_zamani,
                   onaylandi_mi
            FROM danisma_masasi_oturumlari
            WHERE ogrenci_id = %s
              AND bitis_zamani IS NOT NULL
            ORDER BY baslangic_zamani DESC
            LIMIT 50;
        """, (ogrenci[0],))

        kayitlar = cursor.fetchall()
        gecmis = []

        for oturum_id, baslangic, bitis, onay in kayitlar:
            saniye = max(
                0, int((bitis - baslangic).total_seconds())
            )
            saat, kalan = divmod(saniye, 3600)
            dakika = kalan // 60

            gecmis.append({
                "oturum_id": oturum_id,
                "tarih": baslangic.date().isoformat(),
                "baslangic_zamani": baslangic.isoformat(),
                "bitis_zamani": bitis.isoformat(),
                "toplam_dakika": saniye // 60,
                "calisilan_sure": f"{saat} saat {dakika} dakika",
                "onaylandi_mi": onay
            })

        return {
            "toplam_kayit": len(gecmis),
            "oturumlar": gecmis
        }
    except psycopg2.errors.UniqueViolation:
        if conn is not None:
            conn.rollback()
        raise HTTPException(
            status_code=409,
            detail="Zaten devam eden bir göreviniz bulunuyor."
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Görev geçmişi alınamadı."
        )

    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


def danisma_onay_bildirimleri(
    kullanici_id: int | None = None
):
    """Tamamlanmis ve onay bekleyen danisma masasi gorevleri."""

    conn = None
    cursor = None

    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*)
            FROM danisma_masasi_oturumlari
            WHERE bitis_zamani IS NOT NULL
              AND COALESCE(onaylandi_mi, FALSE) = FALSE;
        """)

        toplam = cursor.fetchone()[0]

        cursor.execute("""
            SELECT
                d.oturum_id,
                o.ad_soyad,
                d.bitis_zamani
            FROM danisma_masasi_oturumlari d
            JOIN ogrenciler o
                ON d.ogrenci_id = o.ogrenci_id
            WHERE d.bitis_zamani IS NOT NULL
              AND COALESCE(d.onaylandi_mi, FALSE) = FALSE
            ORDER BY d.bitis_zamani DESC
            LIMIT 10;
        """)

        kayitlar = cursor.fetchall()

        return {
            "toplam": toplam,
            "oturumlar": [
                {
                    "oturum_id": kayit[0],
                    "ad_soyad": kayit[1],
                    "bitis_zamani": kayit[2].isoformat()
                }
                for kayit in kayitlar
            ]
        }

    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


# Bir danışma masası görevi en fazla mesai süresi kadar olabilir (08:00-18:00 = 10 saat). Elle girilen ya da düzenlenen
# daha uzun görev reddedilir; öğrencinin bitirmeyi unuttuğu görev ise kaydedilir ama onay listesinde "uzun görev" diye işaretlenir.
DANISMA_GOREV_EN_UZUN_SAAT = 10


DANISMA_GOREV_COK_UZUN_MESAJI = (
    f"Bir görev en fazla {DANISMA_GOREV_EN_UZUN_SAAT} saat olabilir. "
    "Daha uzun çalışmayı ayrı görevler olarak girin."
)


def danisma_gorevi_cok_uzun_mu(baslangic, bitis):
    return (bitis - baslangic).total_seconds() > DANISMA_GOREV_EN_UZUN_SAAT * 3600


# Yönetim listesinde en yeni kaç görev gösterilir. Devam eden ve onay bekleyen görevler bu sınırdan bağımsız olarak her zaman gelir
# (eski bir onay bekleyen görev listede kaybolup onaylanamaz hale gelmesin).
DANISMA_LISTE_EN_FAZLA = 200


def danisma_yonetim_oturumlari(
    kullanici_id: int | None = None
):
    conn = None
    cursor = None

    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        # Kartlardaki sayılar listeden değil, tüm kayıtlardan hesaplanır.
        cursor.execute("""
            SELECT
                COUNT(*),
                COUNT(*) FILTER (WHERE bitis_zamani IS NULL),
                COUNT(*) FILTER (WHERE bitis_zamani IS NOT NULL AND onaylandi_mi IS NOT TRUE),
                COUNT(*) FILTER (WHERE onaylandi_mi IS TRUE)
            FROM danisma_masasi_oturumlari;
        """)
        toplam, aktif, bekleyen, onaylanan = cursor.fetchone()

        cursor.execute("""
            SELECT
                d.oturum_id,
                d.ogrenci_id,
                o.ad_soyad,
                o.ogrenci_numarasi,
                d.baslangic_zamani,
                d.bitis_zamani,
                d.onaylandi_mi
            FROM danisma_masasi_oturumlari d
            JOIN ogrenciler o
                ON d.ogrenci_id = o.ogrenci_id
            WHERE d.oturum_id IN (
                    SELECT oturum_id
                    FROM danisma_masasi_oturumlari
                    ORDER BY baslangic_zamani DESC
                    LIMIT %s
                )
               OR d.bitis_zamani IS NULL
               OR d.onaylandi_mi IS NOT TRUE
            ORDER BY d.baslangic_zamani DESC;
        """, (DANISMA_LISTE_EN_FAZLA,))

        kayitlar = cursor.fetchall()
        oturumlar = []

        for (
            oturum_id,
            ogrenci_id,
            ad_soyad,
            ogrenci_numarasi,
            baslangic,
            bitis,
            onay
        ) in kayitlar:

            bitis_hesap = bitis if bitis is not None else datetime.now()
            toplam_saniye = max(
                0,
                int((bitis_hesap - baslangic).total_seconds())
            )

            oturumlar.append({
                "oturum_id": oturum_id,
                "ogrenci_id": ogrenci_id,
                "ad_soyad": ad_soyad,
                "ogrenci_numarasi": ogrenci_numarasi,
                "baslangic_zamani": baslangic.isoformat(),
                "bitis_zamani": bitis.isoformat() if bitis else None,
                "toplam_saniye": toplam_saniye,
                "durum": "AKTIF" if bitis is None else "TAMAMLANDI",
                "onaylandi_mi": onay,
                # Mesai süresini aşan görev: öğrenci bitirmeyi unutmuş olabilir, onaylamadan önce saatler kontrol edilmeli.
                "uzun_gorev": toplam_saniye > DANISMA_GOREV_EN_UZUN_SAAT * 3600,
            })

        return {
            "toplam_kayit": toplam,
            "ozet": {
                "toplam": toplam,
                "aktif": aktif,
                "bekleyen": bekleyen,
                "onaylanan": onaylanan,
            },
            "kisaltildi": len(oturumlar) < toplam,
            "oturumlar": oturumlar
        }

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Danışma masası görev kayıtları alınamadı."
        )
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


def danisma_yonetim_oturum_onayla(
    oturum_id: int,
    kullanici_id: int | None = None
):
    conn = None
    cursor = None

    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT bitis_zamani, onaylandi_mi
            FROM danisma_masasi_oturumlari
            WHERE oturum_id = %s
            FOR UPDATE;
        """, (oturum_id,))

        oturum = cursor.fetchone()

        if oturum is None:
            raise HTTPException(
                status_code=404,
                detail="Görev kaydı bulunamadı."
            )

        bitis_zamani, onaylandi_mi = oturum

        if bitis_zamani is None:
            raise HTTPException(
                status_code=409,
                detail="Devam eden görev onaylanamaz."
            )

        if onaylandi_mi:
            raise HTTPException(
                status_code=409,
                detail="Bu görev zaten onaylanmış."
            )

        cursor.execute("""
            UPDATE danisma_masasi_oturumlari
            SET onaylandi_mi = TRUE
            WHERE oturum_id = %s;
        """, (oturum_id,))

        denetim_kaydi_olustur(
            VT_AYARLARI,
            olay_turu="UPDATE",
            kullanici_id=kullanici_id,
            hedef_tablo="danisma_masasi_oturumlari",
            hedef_kayit_id=oturum_id,
            mevcut_cursor=cursor,
            ayrinti={"onceki": {"onaylandi_mi": False}, "yeni": {"onaylandi_mi": True}}
        )

        conn.commit()

        return {
            "durum": "basarili",
            "mesaj": "Danışma masası görevi onaylandı.",
            "oturum_id": oturum_id,
            "onaylandi_mi": True
        }

    except HTTPException:
        if conn is not None:
            conn.rollback()
        raise

    except Exception:
        if conn is not None:
            conn.rollback()
        raise HTTPException(
            status_code=500,
            detail="Görev onaylanırken bir hata oluştu."
        )

    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


def danisma_yonetim_onay_geri_al(
    oturum_id: int,
    kullanici_id: int | None = None
):
    """Onaylanmış görevin onayını kaldırır; görev yeniden onay bekler ve düzenlenebilir."""
    conn = None
    cursor = None

    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT onaylandi_mi
            FROM danisma_masasi_oturumlari
            WHERE oturum_id = %s
            FOR UPDATE;
        """, (oturum_id,))

        oturum = cursor.fetchone()

        if oturum is None:
            raise HTTPException(
                status_code=404,
                detail="Görev kaydı bulunamadı."
            )

        if not oturum[0]:
            raise HTTPException(
                status_code=409,
                detail="Bu görev onaylı değil."
            )

        cursor.execute("""
            UPDATE danisma_masasi_oturumlari
            SET onaylandi_mi = FALSE
            WHERE oturum_id = %s;
        """, (oturum_id,))

        denetim_kaydi_olustur(
            VT_AYARLARI,
            olay_turu="UPDATE",
            kullanici_id=kullanici_id,
            hedef_tablo="danisma_masasi_oturumlari",
            hedef_kayit_id=oturum_id,
            mevcut_cursor=cursor,
            ayrinti={"onceki": {"onaylandi_mi": True}, "yeni": {"onaylandi_mi": False}}
        )

        conn.commit()

        return {
            "durum": "basarili",
            "mesaj": "Görevin onayı geri alındı.",
            "oturum_id": oturum_id,
            "onaylandi_mi": False
        }

    except HTTPException:
        if conn is not None:
            conn.rollback()
        raise

    except Exception:
        if conn is not None:
            conn.rollback()
        raise HTTPException(
            status_code=500,
            detail="Görevin onayı geri alınırken bir hata oluştu."
        )

    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


def danisma_yonetim_ogrencileri(
    kullanici_id: int | None = None
):
    conn = None
    cursor = None

    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT ogrenci_id, ad_soyad, ogrenci_numarasi, tur::text
            FROM ogrenciler
            WHERE aktif_mi = TRUE
              AND tur::text = 'DANISMA_MASASI'
            ORDER BY ad_soyad, ogrenci_numarasi;
        """)

        ogrenciler = [
            {
                "ogrenci_id": ogrenci_id,
                "ad_soyad": ad_soyad,
                "ogrenci_numarasi": ogrenci_numarasi,
                "tur": tur,
                "tur_etiketi": OGRENCI_TUR_ETIKETLERI.get(tur)
            }
            for ogrenci_id, ad_soyad, ogrenci_numarasi, tur
            in cursor.fetchall()
        ]

        return {"ogrenciler": ogrenciler}

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Öğrenci listesi alınamadı."
        )

    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


def danisma_yonetim_oturum_olustur(
    veri: DanismaGorevOlusturModeli,
    kullanici_id: int | None = None
):
    conn = None
    cursor = None

    try:
        # Önce tarih ve saatleri doğrula.
        if veri.bitis_zamani <= veri.baslangic_zamani:
            raise HTTPException(
                status_code=422,
                detail="Bitiş zamanı başlangıçtan sonra olmalıdır."
            )

        if danisma_gorevi_cok_uzun_mu(veri.baslangic_zamani, veri.bitis_zamani):
            raise HTTPException(
                status_code=422,
                detail=DANISMA_GOREV_COK_UZUN_MESAJI
            )

        if veri.bitis_zamani > datetime.now():
            raise HTTPException(
                status_code=422,
                detail="Gelecekte biten görev kaydı oluşturulamaz."
            )

        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        # Öğrenci kaydını kilitleyerek eşzamanlı
        # görev ekleme işlemlerini sıraya al. Görev yalnızca danışma masası öğrencisine girilebilir.
        cursor.execute("""
            SELECT ogrenci_id
            FROM ogrenciler
            WHERE ogrenci_id = %s
              AND aktif_mi = TRUE
              AND tur::text = 'DANISMA_MASASI'
            FOR UPDATE;
        """, (veri.ogrenci_id,))

        if cursor.fetchone() is None:
            raise HTTPException(
                status_code=404,
                detail="Aktif danışma masası öğrencisi bulunamadı."
            )

        # Aynı öğrencinin görevleriyle zaman çakışması.
        # Açık görevlerde bitiş zamanı henüz bilinmediğinden
        # bitişi sonsuz kabul ediyoruz.
        cursor.execute("""
            SELECT oturum_id
            FROM danisma_masasi_oturumlari
            WHERE ogrenci_id = %s
              AND baslangic_zamani < %s
              AND (
                  bitis_zamani IS NULL
                  OR bitis_zamani > %s
              )
            LIMIT 1;
        """, (
            veri.ogrenci_id,
            veri.bitis_zamani,
            veri.baslangic_zamani
        ))

        if cursor.fetchone() is not None:
            raise HTTPException(
                status_code=409,
                detail="Öğrencinin bu saatlerle çakışan görevi var."
            )

        cursor.execute("""
            INSERT INTO danisma_masasi_oturumlari
                (
                    ogrenci_id,
                    baslangic_zamani,
                    bitis_zamani,
                    onaylandi_mi
                )
            VALUES (%s, %s, %s, FALSE)
            RETURNING oturum_id;
        """, (
            veri.ogrenci_id,
            veri.baslangic_zamani,
            veri.bitis_zamani
        ))

        oturum_id = cursor.fetchone()[0]

        denetim_kaydi_olustur(
            VT_AYARLARI,
            olay_turu="CREATE",
            kullanici_id=kullanici_id,
            hedef_tablo="danisma_masasi_oturumlari",
            hedef_kayit_id=oturum_id,
            mevcut_cursor=cursor,
            ayrinti={
                "yeni": {
                    "ogrenci_id": veri.ogrenci_id,
                    "baslangic_zamani": veri.baslangic_zamani.isoformat(sep=" ", timespec="minutes"),
                    "bitis_zamani": veri.bitis_zamani.isoformat(sep=" ", timespec="minutes"),
                }
            }
        )

        conn.commit()

        return {
            "durum": "basarili",
            "mesaj": "Danışma masası görevi oluşturuldu.",
            "oturum_id": oturum_id,
            "onaylandi_mi": False
        }

    except HTTPException:
        if conn is not None:
            conn.rollback()
        raise

    except Exception:
        if conn is not None:
            conn.rollback()
        raise HTTPException(
            status_code=500,
            detail="Görev oluşturulurken bir hata oluştu."
        )

    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


def danisma_yonetim_oturum_duzenle(
    oturum_id: int,
    veri: DanismaGorevDuzenleModeli,
    kullanici_id: int | None = None
):
    conn = None
    cursor = None

    try:
        # Tarih-saat doğrulamaları
        baslangic = veri.baslangic_zamani
        bitis = veri.bitis_zamani

        if baslangic.tzinfo is not None or bitis.tzinfo is not None:
            raise HTTPException(
                status_code=422,
                detail="Tarih ve saatler yerel saat biçiminde olmalıdır."
            )

        if bitis <= baslangic:
            raise HTTPException(
                status_code=422,
                detail="Bitiş zamanı başlangıçtan sonra olmalıdır."
            )

        if danisma_gorevi_cok_uzun_mu(baslangic, bitis):
            raise HTTPException(
                status_code=422,
                detail=DANISMA_GOREV_COK_UZUN_MESAJI
            )

        if bitis > datetime.now():
            raise HTTPException(
                status_code=422,
                detail="Gelecekte biten görev kaydı oluşturulamaz."
            )

        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        # Önce görevin hangi öğrenciye ait olduğunu belirle.
        cursor.execute("""
            SELECT ogrenci_id
            FROM danisma_masasi_oturumlari
            WHERE oturum_id = %s;
        """, (oturum_id,))

        sonuc = cursor.fetchone()

        if sonuc is None:
            raise HTTPException(
                status_code=404,
                detail="Düzenlenecek görev bulunamadı."
            )

        ogrenci_id = sonuc[0]

        # Diğer görev işlemleriyle eşzamanlı değişiklikleri
        # sıraya almak için öğrenci kaydını kilitle.
        cursor.execute("""
            SELECT ogrenci_id
            FROM ogrenciler
            WHERE ogrenci_id = %s
            FOR UPDATE;
        """, (ogrenci_id,))

        if cursor.fetchone() is None:
            raise HTTPException(
                status_code=404,
                detail="Öğrenci kaydı bulunamadı."
            )

        # Düzenlenecek görev kaydını kilitle.
        cursor.execute("""
            SELECT baslangic_zamani, bitis_zamani, onaylandi_mi
            FROM danisma_masasi_oturumlari
            WHERE oturum_id = %s
              AND ogrenci_id = %s
            FOR UPDATE;
        """, (oturum_id, ogrenci_id))

        oturum = cursor.fetchone()

        if oturum is None:
            raise HTTPException(
                status_code=404,
                detail="Düzenlenecek görev bulunamadı."
            )

        eski_baslangic, eski_bitis, onaylandi_mi = oturum

        if eski_bitis is None:
            raise HTTPException(
                status_code=409,
                detail="Devam eden görev düzenlenemez."
            )

        if onaylandi_mi:
            raise HTTPException(
                status_code=409,
                detail="Onaylanmış görev düzenlenemez. Önce onayı geri alın."
            )

        # Diğer görevlerle çakışma var mı?
        # Düzenlediğimiz kaydı kontrol dışında tutuyoruz.
        cursor.execute("""
            SELECT oturum_id
            FROM danisma_masasi_oturumlari
            WHERE ogrenci_id = %s
              AND oturum_id <> %s
              AND baslangic_zamani < %s
              AND (
                  bitis_zamani IS NULL
                  OR bitis_zamani > %s
              )
            LIMIT 1;
        """, (
            ogrenci_id,
            oturum_id,
            bitis,
            baslangic
        ))

        if cursor.fetchone() is not None:
            raise HTTPException(
                status_code=409,
                detail="Öğrencinin bu saatlerle çakışan görevi var."
            )

        # Görev saatlerini güncelle.
        cursor.execute("""
            UPDATE danisma_masasi_oturumlari
            SET baslangic_zamani = %s,
                bitis_zamani = %s
            WHERE oturum_id = %s;
        """, (baslangic, bitis, oturum_id))

        # Audit kaydı aynı transaction içinde tutulur: görev saatlerinin önceki ve yeni hali.
        def _saat(deger):
            return deger.isoformat(sep=" ", timespec="minutes")

        denetim_kaydi_olustur(
            VT_AYARLARI,
            olay_turu="UPDATE",
            kullanici_id=kullanici_id,
            hedef_tablo="danisma_masasi_oturumlari",
            hedef_kayit_id=oturum_id,
            mevcut_cursor=cursor,
            ayrinti={
                "onceki": {"baslangic_zamani": _saat(eski_baslangic), "bitis_zamani": _saat(eski_bitis)},
                "yeni": {"baslangic_zamani": _saat(baslangic), "bitis_zamani": _saat(bitis)},
            }
        )

        conn.commit()

        toplam_saniye = int(
            (bitis - baslangic).total_seconds()
        )

        return {
            "durum": "basarili",
            "mesaj": "Danışma masası görevi güncellendi.",
            "oturum_id": oturum_id,
            "baslangic_zamani": baslangic.isoformat(),
            "bitis_zamani": bitis.isoformat(),
            "toplam_saniye": toplam_saniye
        }

    except HTTPException:
        if conn is not None:
            conn.rollback()
        raise

    except Exception:
        if conn is not None:
            conn.rollback()
        raise HTTPException(
            status_code=500,
            detail="Görev düzenlenirken bir hata oluştu."
        )

    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


# (yöntem, yol, uç fonksiyonu, yetki parametresi, gereken yetki, ek yol ayarları): yetki bağımlılığı kayıt sırasında eklenir.
# Gereken yetki: "IZIN" (izin_kontrol), ("A", "B") (izin_kontrol_biri: biri yeter) veya None (yalnızca oturum açmış olmak).
UCLAR = [
    ("POST", "/api/danisma/oturum/baslat", danisma_oturumu_baslat, "kullanici_id", "DANISMA_OTURUMU_YONET", {"status_code": 201}),
    ("PATCH", "/api/danisma/oturum/bitir", danisma_oturumu_bitir, "kullanici_id", "DANISMA_OTURUMU_YONET", {}),
    ("GET", "/api/danisma/oturum/aktif", danisma_aktif_oturum, "kullanici_id", "DANISMA_OTURUMU_YONET", {}),
    ("GET", "/api/danisma/oturum/gecmis", danisma_oturum_gecmisi, "kullanici_id", "DANISMA_OTURUMU_YONET", {}),
    ("GET", "/api/danisma/yonetim/onay-bildirimleri", danisma_onay_bildirimleri, "kullanici_id", "DANISMA_OTURUMU_YONETIM", {}),
    ("GET", "/api/danisma/yonetim/oturumlar", danisma_yonetim_oturumlari, "kullanici_id", "DANISMA_OTURUMU_YONETIM", {}),
    ("PATCH", "/api/danisma/yonetim/oturumlar/{oturum_id}/onayla", danisma_yonetim_oturum_onayla, "kullanici_id", "DANISMA_OTURUMU_YONETIM", {}),
    ("PATCH", "/api/danisma/yonetim/oturumlar/{oturum_id}/onay-geri-al", danisma_yonetim_onay_geri_al, "kullanici_id", "DANISMA_OTURUMU_YONETIM", {}),
    ("GET", "/api/danisma/yonetim/ogrenciler", danisma_yonetim_ogrencileri, "kullanici_id", "DANISMA_OTURUMU_YONETIM", {}),
    ("POST", "/api/danisma/yonetim/oturumlar", danisma_yonetim_oturum_olustur, "kullanici_id", "DANISMA_OTURUMU_YONETIM", {"status_code": 201}),
    ("PATCH", "/api/danisma/yonetim/oturumlar/{oturum_id}", danisma_yonetim_oturum_duzenle, "kullanici_id", "DANISMA_OTURUMU_YONETIM", {}),
]


def router_olustur(izin_kontrol) -> APIRouter:
    """Yetki bağımlılığı üreticileri `server.sunucu` içindeki kimlik doğrulama bağımlılıklarıdır."""
    router = APIRouter()
    for metod, yol, fonksiyon, parametre, yetki, ek in UCLAR:
        assert isinstance(yetki, str), yol          # bu modülde yalnızca tek izin tanımlı
        bagimlilik = izin_kontrol(yetki)
        router.add_api_route(yol, yetkiyle_bagla(fonksiyon, parametre, bagimlilik), methods=[metod], **ek)
    return router
