"""Cihaz rezervasyonu uçları: yapma, iptal, güncelleme, listeleme ve uygunluk denetimi. `server/sunucu.py` içinden ayrıldı."""
from datetime import datetime
import time

from fastapi import APIRouter, HTTPException, Query, Response
from psycopg2.errors import DeadlockDetected
from psycopg2.errors import ExclusionViolation

from server.denetim import denetim_kaydi_olustur
from server.liste_siniri import LISTE_UST_SINIRI, liste_siniri_coz, liste_toplamini_bildir
from server.modeller import RezervasyonGuncelleModeli, RezervasyonOlusturModeli, rezervasyon_zaman_sorunu
from server.oda_etkinlikleri_kurallari import oda_cakismasi_bul, oda_kilidini_al
from server.ortak_sabitler import CIHAZ_ODALARI_SORGUSU
from server.rezervasyon_cakismasi import rezervasyon_cakisma_detayi
from server.vt_ayarlari import VT_AYARLARI
from server.vt_baglanti import vt_baglan
from server.yetki_baglama import yetkiyle_bagla


def rezervasyon_uygunlugunu_denetle(cursor, rez, haric_rezervasyon_id=None):
    """Cihaz rezervasyonunun (yeni ya da düzenlenen) uygun olup olmadığını denetler; sorun varsa HTTPException (403/409/422) fırlatır.

    `rez`: cihaz_id, kullanilacak_oda_id, bolum_id, baslangic_zamani, bitis_zamani alanlarına sahip nesne.
    `haric_rezervasyon_id`: düzenlemede rezervasyonun KENDİSİ çakışma sayılmasın diye çakışma sorgularından çıkarılır."""
    haric_sql = " AND r.rezervasyon_id <> %s" if haric_rezervasyon_id is not None else ""
    haric_param = (haric_rezervasyon_id,) if haric_rezervasyon_id is not None else ()
    # Çözülmemiş arızası olan cihaz, kayıtlı durum sütunu ne derse desin "Arızalı" sayılır (tek doğruluk kaynağı: arıza kaydı).
    cursor.execute(
        "SELECT CASE WHEN durum::text <> 'Kullanim_Disi' AND EXISTS ("
        "SELECT 1 FROM cihaz_arizalari a WHERE a.cihaz_id = cihazlar.cihaz_id AND a.cozuldu_mu IS NOT TRUE) "
        "THEN 'Arizali' ELSE durum::text END FROM cihazlar WHERE cihaz_id = %s;", (rez.cihaz_id,))
    cihaz = cursor.fetchone()
    if cihaz is None:
        raise HTTPException(status_code=404, detail="Cihaz bulunamadı.")
    if cihaz[0] not in ["Kullanima_Hazir", "Rezerve"]:
        raise HTTPException(status_code=403, detail=f"Cihaz şu anda {cihaz[0]} durumunda olduğu için rezerve edilemez!")

    # Bakım/kalibrasyon kaydı cihaz durumunu değiştirmediğinden, seçilen saat aralığı
    # planlı bir bakım veya kalibrasyonla kesişiyorsa da rezervasyon reddedilir.
    # Bakım/kalibrasyon günleri başlangıç ve bitiş dahil tam gün sayılır.
    cursor.execute(
        """
        SELECT tur, baslangic, bitis FROM (
            SELECT 'Bakım' AS tur,
                   COALESCE(bakim_baslangic_tarihi, bakim_tarihi::date) AS baslangic,
                   COALESCE(bakim_bitis_tarihi, bakim_tarihi::date) AS bitis
            FROM cihaz_bakimlari
            WHERE cihaz_id = %s
            UNION ALL
            SELECT 'Kalibrasyon', kalibrasyon_baslangic_tarihi, kalibrasyon_bitis_tarihi
            FROM cihaz_kalibrasyonlari
            WHERE cihaz_id = %s
        ) planlar
        WHERE baslangic IS NOT NULL AND bitis IS NOT NULL
          AND baslangic < %s AND bitis + 1 > %s
        ORDER BY baslangic
        LIMIT 1;
        """,
        (rez.cihaz_id, rez.cihaz_id, rez.bitis_zamani, rez.baslangic_zamani),
    )
    plan = cursor.fetchone()
    if plan is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Cihaz {plan[1].strftime('%d.%m.%Y')} - {plan[2].strftime('%d.%m.%Y')} "
                f"tarihleri arasında {plan[0].lower()} planında olduğu için "
                "seçilen saat aralığında rezerve edilemez."
            ),
        )

    cursor.execute("SELECT 1 FROM cihaz_rezervasyonlari WHERE cihaz_id = %s AND iptal_edildi_mi = FALSE AND baslangic_zamani < %s AND bitis_zamani > %s" + haric_sql.replace("r.", "") + " LIMIT 1;", (rez.cihaz_id, rez.bitis_zamani, rez.baslangic_zamani, *haric_param))
    if cursor.fetchone():
        cursor.execute(
            """
            SELECT r.rezervasyon_id, r.baslangic_zamani, r.bitis_zamani, COALESCE(k.kullanici_adi, '-')
            FROM cihaz_rezervasyonlari r
            LEFT JOIN personel p ON r.rezervasyonu_yapan_personel_id = p.personel_id
            LEFT JOIN kullanicilar k ON p.kullanici_id = k.kullanici_id
            WHERE r.cihaz_id = %s AND r.iptal_edildi_mi = FALSE
              AND r.baslangic_zamani < %s AND r.bitis_zamani > %s""" + haric_sql + """
            ORDER BY r.baslangic_zamani;
            """,
            (rez.cihaz_id, rez.bitis_zamani, rez.baslangic_zamani, *haric_param),
        )
        raise HTTPException(
            status_code=409,
            detail=rezervasyon_cakisma_detayi(
                "Cihaz seçilen saat aralığında zaten başka bir iş için rezerve edilmiş.",
                cursor.fetchall(),
            ),
        )

    if rez.kullanilacak_oda_id is not None:
        # Oda uygunluğu, aynı transaction kilidi altında kontrol edilmeli.
        oda_kilidini_al(cursor, rez.kullanilacak_oda_id)
        cursor.execute("SELECT 1 FROM (" + CIHAZ_ODALARI_SORGUSU + ") d WHERE d.oda_id = %s;", (rez.kullanilacak_oda_id,))
        if cursor.fetchone() is None:
            raise HTTPException(status_code=422, detail="Seçilen oda cihaz rezervasyonu için uygun değil (psikologa atanmış ya da aktif değil).")

    if rez.bolum_id is not None:
        cursor.execute("SELECT 1 FROM bolumler WHERE bolum_id = %s AND aktif_mi IS NOT FALSE;", (rez.bolum_id,))
        if cursor.fetchone() is None:
            raise HTTPException(status_code=422, detail="Bölüm bulunamadı veya aktif değil.")

    if rez.kullanilacak_oda_id is not None:
        # Oda kilidi, uygunluk kontrolünden önce alındı.
        cakisma = oda_cakismasi_bul(
            cursor,
            rez.kullanilacak_oda_id,
            rez.baslangic_zamani,
            rez.bitis_zamani,
            haric_cihaz_rezervasyon_id=haric_rezervasyon_id,
        )
        if cakisma:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Oda bu saatlerde dolu "
                    f"(çakışan kayıt: {cakisma})."
                ),
            )

        # Aynı oda aynı saatte yalnızca tek rezervasyona verilir (başka bir CİHAZ için de olsa).
        cursor.execute(
            """
            SELECT r.rezervasyon_id, r.baslangic_zamani, r.bitis_zamani, COALESCE(k.kullanici_adi, '-')
            FROM cihaz_rezervasyonlari r
            LEFT JOIN personel p ON r.rezervasyonu_yapan_personel_id = p.personel_id
            LEFT JOIN kullanicilar k ON p.kullanici_id = k.kullanici_id
            WHERE r.kullanilacak_oda_id = %s AND r.iptal_edildi_mi = FALSE
              AND r.baslangic_zamani < %s AND r.bitis_zamani > %s""" + haric_sql + """
            ORDER BY r.baslangic_zamani;
            """,
            (rez.kullanilacak_oda_id, rez.bitis_zamani, rez.baslangic_zamani, *haric_param),
        )
        oda_cakismalari = cursor.fetchall()
        if oda_cakismalari:
            raise HTTPException(
                status_code=409,
                detail=rezervasyon_cakisma_detayi(
                    "Oda seçilen saat aralığında başka bir cihaz rezervasyonu için ayrılmış.",
                    oda_cakismalari,
                ),
            )


def cihaz_rezervasyonu_yap(rez: RezervasyonOlusturModeli, kullanici_id: int | None = None):
    if rez.baslangic_zamani >= rez.bitis_zamani:
        raise HTTPException(status_code=422, detail="Bitiş zamanı, başlangıçtan sonra olmalıdır.")
    # Geçmiş bir zamana yeni cihaz rezervasyonu oluşturulamaz (mesai kuralından önce söylenir: saatten bağımsız, açık mesaj).
    if rez.baslangic_zamani < datetime.now(rez.baslangic_zamani.tzinfo):
        raise HTTPException(
            status_code=422,
            detail="Rezervasyon başlangıç zamanı geçmişte olamaz."
        )
    zaman_sorunu = rezervasyon_zaman_sorunu(rez.baslangic_zamani, rez.bitis_zamani)
    if zaman_sorunu:
        raise HTTPException(status_code=422, detail=zaman_sorunu)

    maksimum_deneme = 3
    for deneme in range(maksimum_deneme):
        conn = None
        cursor = None
        try:
            conn = vt_baglan(VT_AYARLARI)
            cursor = conn.cursor()
            rezervasyon_uygunlugunu_denetle(cursor, rez)

            cursor.execute("SELECT personel_id FROM personel WHERE kullanici_id = %s;", (kullanici_id,))
            pers = cursor.fetchone()
            personel_id = pers[0] if pers else None

            cursor.execute("INSERT INTO cihaz_rezervasyonlari (cihaz_id, bolum_id, rezervasyonu_yapan_personel_id, kullanilacak_oda_id, baslangic_zamani, bitis_zamani, proje_turu, proje_adi_aciklamasi) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING rezervasyon_id;", (rez.cihaz_id, rez.bolum_id, personel_id, rez.kullanilacak_oda_id, rez.baslangic_zamani, rez.bitis_zamani, rez.proje_turu, rez.proje_adi_aciklamasi))
            rez_id = cursor.fetchone()[0]

            cursor.execute("INSERT INTO denetim_kayitlari (kullanici_id, olay_turu, hedef_tablo, hedef_kayit_id) VALUES (%s, %s, %s, %s);", (kullanici_id, "CREATE", "cihaz_rezervasyonlari", rez_id))
            conn.commit()
            return {"durum": "basarili", "mesaj": "Rezervasyon başarıyla oluşturuldu.", "rezervasyon_id": rez_id}
        except DeadlockDetected:
            if conn is not None: conn.rollback()
            if deneme == maksimum_deneme - 1:
                raise HTTPException(status_code=503, detail="Rezervasyon işlemi eşzamanlı yoğunluk nedeniyle tamamlanamadı. Lütfen tekrar deneyin.")
            time.sleep(0.1 * (deneme + 1))
        except ExclusionViolation as hata:
            if conn is not None: conn.rollback()
            if getattr(getattr(hata, "diag", None), "constraint_name", None) == "cihaz_rezervasyon_oda_cakisma":
                raise HTTPException(status_code=409, detail="Oda seçilen saat aralığında başka bir cihaz rezervasyonu için ayrılmış.")
            raise HTTPException(status_code=409, detail="Cihaz seçilen saat aralığında zaten rezerve edilmiş.")
        finally:
            if cursor is not None: cursor.close()
            if conn is not None: conn.close()


# Rezervasyonu değiştirme/iptal yetkisi: rezervasyonu yapan kişi YA DA cihaz envanterini yöneten (yönetici) rol.
# SQL parçası `r` takma adını bekler ve iki kez kullanıcı kimliği (sırayla) ister.
REZERVASYON_YONETIM_YETKISI_SQL = """(
    r.rezervasyonu_yapan_personel_id = (SELECT personel_id FROM kullanicilar WHERE kullanici_id = %s)
    OR EXISTS (
        SELECT 1 FROM kullanicilar ky
        JOIN rol_izinleri ri ON ri.rol_id = ky.rol_id
        JOIN izinler iz ON iz.izin_id = ri.izin_id
        WHERE ky.kullanici_id = %s AND iz.izin_adi = 'CIHAZ_ENVANTER_YONET' AND ri.izin_var = 1
    )
)"""


REZERVASYON_YETKI_MESAJI = "Bu rezervasyonu yalnızca oluşturan kişi ya da cihaz yöneticisi değiştirebilir."


def rezervasyon_iptal(rezervasyon_id: int, kullanici_id: int | None = None):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        # Yalnızca iptal edilmemiş, süresi dolmamış VE (oluşturan kişi ya da yönetici için) rezervasyon iptal edilir
        # (biten rezervasyonun geçmiş kullanım kaydı ve raporlardaki saati değişmesin).
        cursor.execute(
            "UPDATE cihaz_rezervasyonlari AS r SET iptal_edildi_mi = TRUE WHERE r.rezervasyon_id = %s AND r.iptal_edildi_mi = FALSE "
            "AND r.bitis_zamani > CURRENT_TIMESTAMP AND " + REZERVASYON_YONETIM_YETKISI_SQL + " RETURNING r.rezervasyon_id;",
            (rezervasyon_id, kullanici_id, kullanici_id))
        if cursor.fetchone() is None:
            # Nedeni kullanıcıya söyle: hiç yok mu, zaten iptal mi, süresi mi dolmuş, yoksa yetkisi mi yok?
            cursor.execute(
                "SELECT r.iptal_edildi_mi, r.bitis_zamani <= CURRENT_TIMESTAMP, " + REZERVASYON_YONETIM_YETKISI_SQL +
                " FROM cihaz_rezervasyonlari r WHERE r.rezervasyon_id = %s;", (kullanici_id, kullanici_id, rezervasyon_id))
            mevcut = cursor.fetchone()
            if mevcut is None:
                raise HTTPException(status_code=404, detail="Rezervasyon bulunamadı.")
            if mevcut[0]:
                raise HTTPException(status_code=409, detail="Bu rezervasyon zaten iptal edilmiş.")
            if mevcut[1]:
                raise HTTPException(status_code=409, detail="Süresi dolmuş (tamamlanmış) rezervasyon iptal edilemez.")
            raise HTTPException(status_code=403, detail=REZERVASYON_YETKI_MESAJI)
        denetim_kaydi_olustur(
            VT_AYARLARI,
            olay_turu="CANCEL",
            kullanici_id=kullanici_id,
            hedef_tablo="cihaz_rezervasyonlari",
            hedef_kayit_id=rezervasyon_id,
            mevcut_cursor=cursor
        )
        conn.commit()
        return {"durum": "basarili", "mesaj": "Rezervasyon iptal edildi."}
    except Exception:
        if conn is not None:
            conn.rollback()
        raise
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


def rezervasyon_guncelle(rezervasyon_id: int, rez: RezervasyonGuncelleModeli, kullanici_id: int | None = None):
    """Rezervasyonu düzenler (cihaz değişmez). Yalnızca oluşturan kişi ya da cihaz yöneticisi; iptal edilmiş/bitmiş rezervasyon düzenlenemez.
    Başlamış rezervasyonda başlangıç saati ve oda değişmez. Saat/oda değişirse yeni aralık için tüm uygunluk kuralları yeniden denetlenir
    (rezervasyonun kendisi çakışma sayılmaz); yalnızca açıklama/proje/bölüm değişirse cihaz durumu ya da bakım planı engel olmaz."""
    maksimum_deneme = 3
    for deneme in range(maksimum_deneme):
        conn = None
        cursor = None
        try:
            conn = vt_baglan(VT_AYARLARI)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT r.cihaz_id, r.iptal_edildi_mi, r.baslangic_zamani, r.bitis_zamani, r.kullanilacak_oda_id, " + REZERVASYON_YONETIM_YETKISI_SQL +
                " FROM cihaz_rezervasyonlari r WHERE r.rezervasyon_id = %s FOR UPDATE OF r;", (kullanici_id, kullanici_id, rezervasyon_id))
            mevcut = cursor.fetchone()
            if mevcut is None:
                raise HTTPException(status_code=404, detail="Rezervasyon bulunamadı.")
            cihaz_id, iptal, mevcut_bas, mevcut_bit, mevcut_oda, yetkili = mevcut
            if iptal:
                raise HTTPException(status_code=409, detail="İptal edilmiş rezervasyon düzenlenemez.")
            simdi = datetime.now(rez.baslangic_zamani.tzinfo)
            if mevcut_bit <= simdi.replace(tzinfo=None):
                raise HTTPException(status_code=409, detail="Süresi dolmuş (tamamlanmış) rezervasyon düzenlenemez.")
            if not yetkili:
                raise HTTPException(status_code=403, detail=REZERVASYON_YETKI_MESAJI)

            bas, bit = rez.baslangic_zamani.replace(tzinfo=None), rez.bitis_zamani.replace(tzinfo=None)
            zaman_oda_degisti = (bas, bit, rez.kullanilacak_oda_id) != (mevcut_bas, mevcut_bit, mevcut_oda)
            basladi = mevcut_bas <= simdi.replace(tzinfo=None)
            if basladi:
                if bas != mevcut_bas or rez.kullanilacak_oda_id != mevcut_oda:
                    raise HTTPException(status_code=409, detail="Başlamış rezervasyonun başlangıç saati ve odası değiştirilemez; yalnızca bitiş saati, bölüm ve proje bilgileri düzenlenebilir.")
                if bit <= simdi.replace(tzinfo=None):
                    raise HTTPException(status_code=422, detail="Bitiş zamanı şu andan sonra olmalıdır.")
            elif bas < simdi.replace(tzinfo=None):
                raise HTTPException(status_code=422, detail="Rezervasyon başlangıç zamanı geçmişte olamaz.")

            if (bas, bit) != (mevcut_bas, mevcut_bit):
                # Saatler değişiyorsa mesai ve süre kuralı yeniden uygulanır (yalnızca açıklama/bölüm değişirse eski kayıtlar engellenmez).
                zaman_sorunu = rezervasyon_zaman_sorunu(rez.baslangic_zamani, rez.bitis_zamani)
                if zaman_sorunu:
                    raise HTTPException(status_code=422, detail=zaman_sorunu)

            if zaman_oda_degisti:
                from types import SimpleNamespace
                rezervasyon_uygunlugunu_denetle(
                    cursor,
                    SimpleNamespace(cihaz_id=cihaz_id, kullanilacak_oda_id=rez.kullanilacak_oda_id, bolum_id=rez.bolum_id,
                                    baslangic_zamani=rez.baslangic_zamani, bitis_zamani=rez.bitis_zamani),
                    haric_rezervasyon_id=rezervasyon_id,
                )
            elif rez.bolum_id is not None:
                cursor.execute("SELECT 1 FROM bolumler WHERE bolum_id = %s AND aktif_mi IS NOT FALSE;", (rez.bolum_id,))
                if cursor.fetchone() is None:
                    raise HTTPException(status_code=422, detail="Bölüm bulunamadı veya aktif değil.")

            cursor.execute(
                "UPDATE cihaz_rezervasyonlari SET bolum_id = %s, kullanilacak_oda_id = %s, baslangic_zamani = %s, bitis_zamani = %s, "
                "proje_turu = %s, proje_adi_aciklamasi = %s WHERE rezervasyon_id = %s;",
                (rez.bolum_id, rez.kullanilacak_oda_id, rez.baslangic_zamani, rez.bitis_zamani, rez.proje_turu, rez.proje_adi_aciklamasi, rezervasyon_id),
            )
            denetim_kaydi_olustur(VT_AYARLARI, olay_turu="UPDATE", kullanici_id=kullanici_id, hedef_tablo="cihaz_rezervasyonlari",
                                  hedef_kayit_id=rezervasyon_id, mevcut_cursor=cursor)
            conn.commit()
            return {"durum": "basarili", "mesaj": "Rezervasyon güncellendi.", "rezervasyon_id": rezervasyon_id}
        except DeadlockDetected:
            if conn is not None: conn.rollback()
            if deneme == maksimum_deneme - 1:
                raise HTTPException(status_code=503, detail="Rezervasyon işlemi eşzamanlı yoğunluk nedeniyle tamamlanamadı. Lütfen tekrar deneyin.")
            time.sleep(0.1 * (deneme + 1))
        except ExclusionViolation as hata:
            if conn is not None: conn.rollback()
            if getattr(getattr(hata, "diag", None), "constraint_name", None) == "cihaz_rezervasyon_oda_cakisma":
                raise HTTPException(status_code=409, detail="Oda seçilen saat aralığında başka bir cihaz rezervasyonu için ayrılmış.")
            raise HTTPException(status_code=409, detail="Cihaz seçilen saat aralığında zaten rezerve edilmiş.")
        except Exception:
            if conn is not None: conn.rollback()
            raise
        finally:
            if cursor is not None: cursor.close()
            if conn is not None: conn.close()


def rezervasyon_gorunen_durumu(iptal_edildi_mi, bitis_zamani, simdi=None):
    """Rezervasyonun gorunen durumunu hesaplar; veritabanini degistirmez."""
    if iptal_edildi_mi:
        return "İptal Edildi"

    if bitis_zamani is None:
        return "Aktif"

    if simdi is None:
        simdi = datetime.now(bitis_zamani.tzinfo)

    if bitis_zamani <= simdi:
        return "Tamamlandı"

    return "Aktif"


def rezervasyonlari_listele(response: Response = None, limit: int | None = Query(None, ge=1, le=LISTE_UST_SINIRI), kullanici_id: int | None = None):
    sinir = liste_siniri_coz(limit)
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("SELECT r.rezervasyon_id, c.envanter_kodu, c.cihaz_adi, r.baslangic_zamani, r.bitis_zamani, r.iptal_edildi_mi, o.oda_adi, r.proje_turu, r.proje_adi_aciklamasi, r.bolum_id, b.bolum_adi, "
                       "ky.kullanici_adi, " + REZERVASYON_YONETIM_YETKISI_SQL + ", r.cihaz_id, r.kullanilacak_oda_id "
                       "FROM cihaz_rezervasyonlari r JOIN cihazlar c ON r.cihaz_id = c.cihaz_id LEFT JOIN odalar o ON r.kullanilacak_oda_id = o.oda_id LEFT JOIN bolumler b ON r.bolum_id = b.bolum_id "
                       "LEFT JOIN kullanicilar ky ON ky.personel_id = r.rezervasyonu_yapan_personel_id ORDER BY r.baslangic_zamani DESC LIMIT %s;", (kullanici_id, kullanici_id, sinir))
        kayitlar = cursor.fetchall()
        liste_toplamini_bildir(cursor, response, len(kayitlar), "SELECT COUNT(*) FROM cihaz_rezervasyonlari;", sinir)
        return [{"rezervasyon_id": k[0], "cihaz_id": f"{k[1]} - {k[2]}", "baslangic_zamani": k[3].isoformat() if hasattr(k[3], 'isoformat') else str(k[3]), "bitis_zamani": k[4].isoformat() if hasattr(k[4], 'isoformat') else str(k[4]), "durum": rezervasyon_gorunen_durumu(k[5], k[4]), "envanter_kodu": k[1], "cihaz_adi": k[2], "oda_adi": k[6], "proje_turu": k[7], "proje_adi_aciklamasi": k[8], "bolum_id": k[9], "bolum_adi": k[10],
                 "rezerve_eden": k[11] if len(k) > 11 else None,
                 "yonetebilir": bool(k[12]) if len(k) > 12 else False,
                 "cihaz_numarasi": k[13] if len(k) > 13 else None,
                 "oda_id": k[14] if len(k) > 14 else None} for k in kayitlar]
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


# (yöntem, yol, uç fonksiyonu, yetki parametresi, gereken yetki, ek yol ayarları): yetki bağımlılığı kayıt sırasında eklenir.
# Gereken yetki: "IZIN" (izin_kontrol), ("A", "B") (izin_kontrol_biri: biri yeter) veya None (yalnızca oturum açmış olmak).
UCLAR = [
    ("POST", "/api/rezervasyonlar", cihaz_rezervasyonu_yap, "kullanici_id", "CIHAZ_REZERVASYON", {"status_code": 201}),
    ("PATCH", "/api/rezervasyonlar/{rezervasyon_id}/iptal", rezervasyon_iptal, "kullanici_id", "CIHAZ_REZERVASYON", {}),
    ("PUT", "/api/rezervasyonlar/{rezervasyon_id}", rezervasyon_guncelle, "kullanici_id", "CIHAZ_REZERVASYON", {}),
    ("GET", "/api/rezervasyonlar", rezervasyonlari_listele, "kullanici_id", "CIHAZ_REZERVASYON", {}),
]


def router_olustur(izin_kontrol) -> APIRouter:
    """Yetki bağımlılığı üreticileri `server.sunucu` içindeki kimlik doğrulama bağımlılıklarıdır."""
    router = APIRouter()
    for metod, yol, fonksiyon, parametre, yetki, ek in UCLAR:
        assert isinstance(yetki, str), yol          # bu modülde yalnızca tek izin tanımlı
        bagimlilik = izin_kontrol(yetki)
        router.add_api_route(yol, yetkiyle_bagla(fonksiyon, parametre, bagimlilik), methods=[metod], **ek)
    return router
