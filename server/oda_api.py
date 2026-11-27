"""Oda uçları: odalar, psikolog-oda yetkileri, planlı kayıt sayıları, psikolog listesi ve cihaz odaları. `server/sunucu.py` içinden ayrıldı."""
from fastapi import APIRouter, HTTPException
from psycopg2.errors import DeadlockDetected
from pydantic import BaseModel as _OdaYetkiBaseModel, Field as _OdaYetkiField
import psycopg2

from server.denetim import psikolog_oda_degisikligini_yaz, psikolog_odalarini_oku
from server.modeller import OdaGuncelleModeli, OdaOlusturModeli
from server.ortak_sabitler import CIHAZ_ODALARI_SORGUSU, PLANLI_RANDEVU_COZUMU
from server.ortak_yardimcilar import psikolog_rolu_mu
from server.vt_ayarlari import VT_AYARLARI
from server.vt_baglanti import vt_baglan
from server.yetki_baglama import Hepsi, yetkiyle_bagla


class OdaYetkileriModeli(_OdaYetkiBaseModel):
    oda_idleri: list[int] = _OdaYetkiField(min_length=1)


def psikolog_planli_randevulari_denetle(cursor, kullanici_id, kalacak_oda_idleri=None):
    """Psikologun bugün ve sonrası için planlı (PLANLANDI) randevusu varken odası boşalacak bir işlem yapılamaz (409).

    kalacak_oda_idleri verilmezse (rol değiştirme: tüm odalar kalkar) tüm planlı randevular sayılır. Verilirse (oda yetkisi
    güncelleme) yalnızca psikologa şu an atanmış, yeni kümede olmayan ve aktif odalardaki planlı randevular sayılır.
    Tarihi geçmiş "Planlandı" kayıtlar ve iptal edilmiş randevular engellemez."""
    if kalacak_oda_idleri is None:
        cursor.execute(
            """
            SELECT o.oda_adi, COUNT(*)
            FROM randevular r
            JOIN personel p ON p.personel_id = r.psikolog_id
            JOIN odalar o ON o.oda_id = r.oda_id
            WHERE p.kullanici_id = %s AND r.durum = 'PLANLANDI' AND r.baslangic_zamani >= CURRENT_DATE
            GROUP BY o.oda_id, o.oda_adi
            ORDER BY o.oda_adi;
            """,
            (kullanici_id,),
        )
    else:
        cursor.execute(
            """
            SELECT o.oda_adi, COUNT(*)
            FROM randevular r
            JOIN personel p ON p.personel_id = r.psikolog_id
            JOIN odalar o ON o.oda_id = r.oda_id
            WHERE p.kullanici_id = %s AND r.durum = 'PLANLANDI' AND r.baslangic_zamani >= CURRENT_DATE
              AND o.aktif_mi = TRUE AND r.oda_id <> ALL(%s)
              AND EXISTS (SELECT 1 FROM psikolog_odalar po WHERE po.kullanici_id = p.kullanici_id AND po.oda_id = r.oda_id)
            GROUP BY o.oda_id, o.oda_adi
            ORDER BY o.oda_adi;
            """,
            (kullanici_id, list(kalacak_oda_idleri)),
        )
    planlilar = cursor.fetchall()
    if not planlilar:
        return
    if kalacak_oda_idleri is None:
        toplam = sum(sayi for _, sayi in planlilar)
        detay = f"Bu psikologun bugün ve sonrası için {toplam} planlı randevusu var. Rolü değiştirmeden önce {PLANLI_RANDEVU_COZUMU}"
    else:
        ayrinti = ", ".join(f"{ad} ({sayi} randevu)" for ad, sayi in planlilar)
        detay = f"Kaldırılmak istenen odalarda bugün ve sonrası için planlı randevu var: {ayrinti}. Odayı kaldırmadan önce {PLANLI_RANDEVU_COZUMU}"
    raise HTTPException(status_code=409, detail=detay)


def etkinlik_oda_atama_kilitlerini_al(cursor, oda_idleri):
    """Oda etkinliği API'siyle aynı transaction kilitlerini kullan."""
    for oda_id in sorted(set(oda_idleri)):
        cursor.execute(
            "SELECT pg_advisory_xact_lock(%s, %s)",
            (391284, oda_id),
        )


def oda_etkinlikli_odalari_denetle(
    cursor, oda_idleri, haric_kullanici_id=None
):
    """Süren veya gelecekteki etkinliği olan odaları psikolog atamasına kapat."""
    if not oda_idleri:
        return

    cursor.execute(
        """
        SELECT o.oda_adi, COUNT(DISTINCT e.etkinlik_id)
        FROM oda_etkinlikleri e
        JOIN oda_etkinlik_gunleri g
          ON g.etkinlik_id = e.etkinlik_id
        JOIN odalar o
          ON o.oda_id = e.oda_id
        WHERE e.oda_id = ANY(%s)
          AND COALESCE(e.iptal_edildi_mi, FALSE) = FALSE
          AND g.bitis_zamani > NOW()
          AND NOT EXISTS (
              SELECT 1
              FROM psikolog_odalar po
              WHERE po.oda_id = e.oda_id
                AND po.kullanici_id = %s
          )
        GROUP BY o.oda_id, o.oda_adi
        ORDER BY o.oda_adi
        """,
        (list(oda_idleri), haric_kullanici_id),
    )

    etkinlikli_odalar = cursor.fetchall()

    if etkinlikli_odalar:
        ayrinti = ", ".join(
            f"{ad} ({sayi} etkinlik)"
            for ad, sayi in etkinlikli_odalar
        )
        raise HTTPException(
            status_code=409,
            detail=(
                "Devam eden veya gelecekte planlanmış oda etkinliği "
                f"bulunan oda psikoloğa atanamaz: {ayrinti}. "
                "Önce ilgili etkinlikleri iptal edin veya "
                "başka bir oda seçin."
            ),
        )


def cihaz_rezervasyonlu_odalari_denetle(cursor, oda_idleri, haric_kullanici_id=None):
    """Cihaz rezervasyonu için kullanılan oda psikologa atanamaz (409).

    "Kullanılan" = iptal edilmemiş ve henüz bitmemiş (süren ya da gelecekteki) cihaz rezervasyonu olan oda. Geçmişte kalmış
    rezervasyonlar engellemez; kullanıcı gelecek rezervasyonları iptal ederek odayı serbest bırakabilir. haric_kullanici_id
    verilirse o psikologa zaten atanmış odalar denetlenmez (oda yetkisi güncellenirken mevcut atamalar korunur)."""
    if not oda_idleri:
        return
    cursor.execute(
        """
        SELECT o.oda_adi, COUNT(*)
        FROM cihaz_rezervasyonlari cr
        JOIN odalar o ON o.oda_id = cr.kullanilacak_oda_id
        WHERE cr.kullanilacak_oda_id = ANY(%s)
          AND COALESCE(cr.iptal_edildi_mi, FALSE) = FALSE
          AND cr.bitis_zamani > NOW()
          AND NOT EXISTS (SELECT 1 FROM psikolog_odalar po WHERE po.oda_id = cr.kullanilacak_oda_id AND po.kullanici_id = %s)
        GROUP BY o.oda_id, o.oda_adi
        ORDER BY o.oda_adi;
        """,
        (list(oda_idleri), haric_kullanici_id),
    )
    kullanilanlar = cursor.fetchall()
    if kullanilanlar:
        ayrinti = ", ".join(f"{ad} ({sayi} rezervasyon)" for ad, sayi in kullanilanlar)
        raise HTTPException(
            status_code=409,
            detail=(
                f"Cihaz rezervasyonu için kullanılan oda psikologa atanamaz: {ayrinti}. "
                "Odayı psikologa atamak için önce bu odadaki süren ve gelecekteki cihaz rezervasyonlarını iptal edin."
            ),
        )


def _hedef_psikolog_kontrol(cursor, hedef_kullanici_id: int, kilitle: bool = False):
    """Hedef kullanıcı var mı ve psikolog mu? Değilse uygun hatayı fırlatır."""
    cursor.execute(
        "SELECT r.rol_adi FROM kullanicilar k JOIN roller r ON r.rol_id = k.rol_id "
        "WHERE k.kullanici_id = %s" + (" FOR UPDATE OF k;" if kilitle else ";"),
        (hedef_kullanici_id,),
    )
    kayit = cursor.fetchone()
    if kayit is None:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı.")
    if not psikolog_rolu_mu(kayit[0]):
        raise HTTPException(status_code=422, detail="Oda yetkisi yalnızca psikolog rolündeki kullanıcılar için tanımlanabilir.")


def psikolog_oda_yetkilerini_getir(hedef_kullanici_id: int, kullanici_id: int | None = None):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        _hedef_psikolog_kontrol(cursor, hedef_kullanici_id)
        cursor.execute("SELECT oda_id FROM psikolog_odalar WHERE kullanici_id = %s ORDER BY oda_id;", (hedef_kullanici_id,))
        return {"kullanici_id": hedef_kullanici_id, "oda_idleri": [k[0] for k in cursor.fetchall()]}
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


def psikolog_oda_yetkilerini_guncelle(
    hedef_kullanici_id: int,
    yetki: OdaYetkileriModeli,
    kullanici_id: int | None = None,
):
    """Psikologun görüşme odalarını verilen kümeye eşitler. Her psikologun en az bir (aktif) odası olmalıdır."""
    oda_idleri = sorted(set(yetki.oda_idleri))

    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        # KİLİT SIRASI (deadlock önleme): önce oda kilitleri, sonra kullanıcı satırı. Rezervasyon/randevu yolları oda kilidini alıp sonra
        # denetim kaydıyla kullanıcı satırını (FK) okur; burada tersi sıra (önce satır, sonra oda kilidi) karşılıklı beklemeye yol açıyordu.
        etkinlik_oda_atama_kilitlerini_al(cursor, oda_idleri)
        _hedef_psikolog_kontrol(cursor, hedef_kullanici_id, kilitle=True)

        cursor.execute("SELECT oda_id FROM odalar WHERE oda_id = ANY(%s) AND aktif_mi = TRUE;", (oda_idleri,))
        if {k[0] for k in cursor.fetchall()} != set(oda_idleri):
            raise HTTPException(status_code=422, detail="Seçilen odalardan biri bulunamadı veya aktif değil.")
        cihaz_rezervasyonlu_odalari_denetle(cursor, oda_idleri, haric_kullanici_id=hedef_kullanici_id)
        oda_etkinlikli_odalari_denetle(cursor, oda_idleri, haric_kullanici_id=hedef_kullanici_id)
        psikolog_planli_randevulari_denetle(cursor, hedef_kullanici_id, kalacak_oda_idleri=oda_idleri)

        # Pasif odalardaki atamalara dokunma (oda yeniden aktif olunca yetki geri gelir).
        onceki_odalar = psikolog_odalarini_oku(cursor, hedef_kullanici_id)
        cursor.execute(
            """
            DELETE FROM psikolog_odalar po USING odalar o
            WHERE po.oda_id = o.oda_id AND o.aktif_mi = TRUE
              AND po.kullanici_id = %s AND po.oda_id <> ALL(%s);
            """,
            (hedef_kullanici_id, oda_idleri),
        )
        for oda_id in oda_idleri:
            cursor.execute(
                "INSERT INTO psikolog_odalar (kullanici_id, oda_id) VALUES (%s, %s) ON CONFLICT DO NOTHING;",
                (hedef_kullanici_id, oda_id),
            )
        psikolog_oda_degisikligini_yaz(cursor, kullanici_id, hedef_kullanici_id, onceki_odalar)
        conn.commit()
        return {"durum": "basarili", "kullanici_id": hedef_kullanici_id, "oda_idleri": oda_idleri}
    except HTTPException:
        if conn is not None: conn.rollback()
        raise
    except DeadlockDetected:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=503, detail="Oda ataması eşzamanlı yoğunluk nedeniyle tamamlanamadı. Lütfen tekrar deneyin.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


def oda_planli_kayit_sayilari(cursor, oda_id=None):
    """Odayı pasife almayı engelleyen kayıtların sayıları: {oda_id: {"planli_randevu", "cihaz_rezervasyonu", "etkinlik"}}.

    Tanımlar tek yerde durur (pasife alma kuralı ile Oda Yönetimi listesi aynı sayıyı görür):
    - randevu: durum PLANLANDI ve başlangıç bugün ya da sonrası,
    - cihaz rezervasyonu: iptal edilmemiş ve henüz bitmemiş (süren ya da gelecekteki) rezervasyonda kullanılacak oda,
    - etkinlik: iptal edilmemiş ve en az bir günü henüz bitmemiş oda etkinliği.
    Kaydı olmayan oda sonuçta yer almaz. oda_id verilirse yalnız o oda sorgulanır."""
    filtre = " AND oda_id = %(oda)s" if oda_id is not None else ""
    parametre = {"oda": oda_id}
    sonuc = {}

    def isle(anahtar, satirlar):
        for satir_oda_id, sayi in satirlar:
            sonuc.setdefault(satir_oda_id, {"planli_randevu": 0, "cihaz_rezervasyonu": 0, "etkinlik": 0})[anahtar] = sayi

    cursor.execute(
        "SELECT oda_id, COUNT(*) FROM randevular WHERE durum = 'PLANLANDI' AND baslangic_zamani >= CURRENT_DATE"
        + filtre + " GROUP BY oda_id;", parametre)
    isle("planli_randevu", cursor.fetchall())
    cursor.execute(
        "SELECT kullanilacak_oda_id AS oda_id, COUNT(*) FROM cihaz_rezervasyonlari "
        "WHERE COALESCE(iptal_edildi_mi, FALSE) = FALSE AND bitis_zamani > NOW() AND kullanilacak_oda_id IS NOT NULL"
        + filtre.replace("oda_id", "kullanilacak_oda_id") + " GROUP BY kullanilacak_oda_id;", parametre)
    isle("cihaz_rezervasyonu", cursor.fetchall())
    cursor.execute(
        "SELECT e.oda_id, COUNT(DISTINCT e.etkinlik_id) FROM oda_etkinlikleri e "
        "JOIN oda_etkinlik_gunleri g ON g.etkinlik_id = e.etkinlik_id "
        "WHERE COALESCE(e.iptal_edildi_mi, FALSE) = FALSE AND g.bitis_zamani > NOW()"
        + filtre.replace("oda_id", "e.oda_id") + " GROUP BY e.oda_id;", parametre)
    isle("etkinlik", cursor.fetchall())
    return sonuc


def oda_planli_randevu_sayilari(kullanici_id: int | None = None):
    """Oda Yönetimi ekranındaki "Planlı kayıt" sütunu için: odayı pasife almayı engelleyen kayıtların oda başına sayıları.

    Sayımlar pasife alma kuralıyla aynı yardımcıyı kullanır; kullanıcı pasife almayı denemeden önce engeli görür.
    Kaydı olmayan odalar listede yoktur."""
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        sayilar = oda_planli_kayit_sayilari(cursor)
        return [{"oda_id": oda, **sayilar[oda]} for oda in sorted(sayilar)]
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


def oda_psikolog_atamalari(kullanici_id: int | None = None):
    """Oda Yönetimi ekranındaki "Psikologlar" sütunu için (bilgi amaçlı). Ekranı görenler görebilir."""
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT po.oda_id, k.kullanici_adi
            FROM psikolog_odalar po
            JOIN kullanicilar k ON k.kullanici_id = po.kullanici_id
            JOIN roller r ON r.rol_id = k.rol_id
            WHERE k.aktif_mi = TRUE AND UPPER(r.rol_adi) = 'PSIKOLOG'
            ORDER BY po.oda_id, k.kullanici_adi;
            """
        )
        atamalar = {}
        for oda_id, kullanici_adi in cursor.fetchall():
            atamalar.setdefault(oda_id, []).append(kullanici_adi)
        return [{"oda_id": oda_id, "psikologlar": adlar} for oda_id, adlar in atamalar.items()]
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


def oda_olustur(oda: OdaOlusturModeli, kullanici_id: int | None = None):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        oda_adi = oda.oda_adi.strip()
        cursor.execute("INSERT INTO odalar (oda_adi, kapasite, aktif_mi) VALUES (%s, %s, %s) RETURNING oda_id;", (oda_adi, oda.kapasite, oda.aktif_mi))
        oda_id = cursor.fetchone()[0]
        cursor.execute("INSERT INTO denetim_kayitlari (kullanici_id, olay_turu, hedef_tablo, hedef_kayit_id) VALUES (%s, %s, %s, %s);", (kullanici_id, "CREATE", "odalar", oda_id))
        conn.commit()
        return {"durum": "basarili", "mesaj": "Oda başarıyla oluşturuldu.", "oda_id": oda_id}
    except psycopg2.errors.UniqueViolation:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=409, detail="Bu isimde bir oda zaten mevcut.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


def psikolog_odalarini_getir(
    personel_id: int,
    kullanici_id: int | None = None 
):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        
        # personel tablosunu araya koyarak personel_id üzerinden 
        # doğru kullanici_id'ye ulaşıyor ve sadece ona ait odaları çekiyoruz.
        sorgu = """
            SELECT o.oda_id, o.oda_adi, o.aktif_mi
            FROM odalar o
            JOIN psikolog_odalar po ON o.oda_id = po.oda_id
            JOIN personel p ON p.kullanici_id = po.kullanici_id
            WHERE p.personel_id = %s AND o.aktif_mi = TRUE;
        """
        cursor.execute(sorgu, (personel_id,))
        odalar = cursor.fetchall()
        
        return [{"oda_id": oda[0], "oda_adi": oda[1], "aktif_mi": oda[2]} for oda in odalar]
    except Exception:
        raise HTTPException(status_code=500, detail="Psikoloğun odaları alınırken bir hata oluştu.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


def odalari_listele(kullanici_id: int | None = None):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("SELECT oda_id, oda_adi, kapasite, aktif_mi FROM odalar ORDER BY oda_id;")
        odalar = cursor.fetchall()
        return [{"oda_id": oda[0], "oda_adi": oda[1], "kapasite": oda[2], "aktif_mi": oda[3]} for oda in odalar]
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


def cihaz_odalarini_listele(kullanici_id: int | None = None):
    """Cihaz rezervasyonunda seçilebilen odalar: aktif bir psikologa atanmamış aktif odalar.

    Psikologlara atanan görüşme odaları listeye girmez."""
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute(CIHAZ_ODALARI_SORGUSU + ";")
        return [{"oda_id": k[0], "oda_adi": k[1], "aktif_mi": True} for k in cursor.fetchall()]
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


def oda_detay(oda_id: int, kullanici_id: int | None = None):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("SELECT oda_id, oda_adi, kapasite, aktif_mi FROM odalar WHERE oda_id = %s;", (oda_id,))
        oda = cursor.fetchone()
        if oda is None:
            raise HTTPException(status_code=404, detail="Oda bulunamadı.")
        return {"oda_id": oda[0], "oda_adi": oda[1], "kapasite": oda[2], "aktif_mi": oda[3]}
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


def tek_aktif_odasi_olan_psikologlar(cursor, oda_id):
    """Tek aktif odası bu oda olan psikologların adları (oda pasife alınır ya da silinirse odasız kalırlar)."""
    cursor.execute(
        """
        SELECT k.kullanici_adi
        FROM psikolog_odalar po
        JOIN kullanicilar k ON k.kullanici_id = po.kullanici_id
        JOIN personel p ON p.kullanici_id = k.kullanici_id
        WHERE po.oda_id = %s AND k.aktif_mi = TRUE AND p.aktif_mi = TRUE
          AND EXISTS (SELECT 1 FROM odalar o0 WHERE o0.oda_id = po.oda_id AND o0.aktif_mi = TRUE)
          AND NOT EXISTS (
              SELECT 1 FROM psikolog_odalar po2
              JOIN odalar o2 ON o2.oda_id = po2.oda_id
              WHERE po2.kullanici_id = po.kullanici_id
                AND po2.oda_id <> po.oda_id AND o2.aktif_mi = TRUE
          )
        ORDER BY k.kullanici_adi;
        """,
        (oda_id,),
    )
    return [k[0] for k in cursor.fetchall()]


def oda_gecmis_kayit_sayilari(cursor, oda_id):
    """Odayı kullanan TÜM kayıtların (geçmiş ve gelecek, iptaller dahil) sayıları: bu kayıtlar varken oda silinemez."""
    cursor.execute("SELECT COUNT(*) FROM randevular WHERE oda_id = %s;", (oda_id,))
    randevu = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM cihaz_rezervasyonlari WHERE kullanilacak_oda_id = %s;", (oda_id,))
    rezervasyon = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM oda_etkinlikleri WHERE oda_id = %s;", (oda_id,))
    etkinlik = cursor.fetchone()[0]
    return {"randevu": randevu, "cihaz_rezervasyonu": rezervasyon, "etkinlik": etkinlik}


def oda_sil(oda_id: int, kullanici_id: int | None = None):
    """Odayı veritabanından kalıcı olarak siler (geri alınamaz).

    Yalnızca PASİF oda silinebilir: aktif oda önce pasife alınmalıdır (pasife alma; planlı randevu/rezervasyon/etkinlik ve psikologun tek aktif odası
    kurallarını zaten denetler, böylece silme bu kuralları ayrıca atlatamaz). Silinemez (409): oda aktifse ya da odayı kullanan herhangi bir randevu,
    cihaz rezervasyonu ya da oda etkinliği kaydı varsa (geçmiş kayıtlar ve raporlar bozulmasın; oda pasif olarak kalır). Psikolog-oda atamaları
    odayla birlikte kalkar. Silinen oda denetim kaydına yazılır."""
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("SELECT oda_adi, aktif_mi FROM odalar WHERE oda_id = %s FOR UPDATE;", (oda_id,))
        satir = cursor.fetchone()
        if satir is None:
            raise HTTPException(status_code=404, detail="Oda bulunamadı.")
        oda_adi, aktif_mi = satir
        if aktif_mi:
            raise HTTPException(
                status_code=409,
                detail="Aktif oda silinemez. Önce odayı pasife alın; ardından (pasif odalar listede görünür olduğunda) silebilirsiniz.",
            )

        sayilar = oda_gecmis_kayit_sayilari(cursor, oda_id)
        parcalar = []
        if sayilar["randevu"]:
            parcalar.append(f"{sayilar['randevu']} randevu")
        if sayilar["cihaz_rezervasyonu"]:
            parcalar.append(f"{sayilar['cihaz_rezervasyonu']} cihaz rezervasyonu")
        if sayilar["etkinlik"]:
            parcalar.append(f"{sayilar['etkinlik']} oda etkinliği")
        if parcalar:
            raise HTTPException(
                status_code=409,
                detail="Bu odayı kullanan " + ", ".join(parcalar) + " kaydı var. Geçmiş kayıtlar ve raporlar bozulmasın diye "
                       "kullanılmış oda silinemez; odayı pasife alarak kullanımdan kaldırabilirsiniz.",
            )

        from server.denetim import denetim_kaydi_olustur, satiri_sil_ve_ayrintisini_al
        silinen = satiri_sil_ve_ayrintisini_al(cursor, "odalar", oda_id)
        denetim_kaydi_olustur(VT_AYARLARI, "DELETE", kullanici_id, "odalar", oda_id, mevcut_cursor=cursor, ayrinti=silinen)
        conn.commit()
        return {"durum": "silindi", "mesaj": "Oda silindi.", "oda_id": oda_id, "oda_adi": oda_adi}
    except HTTPException:
        if conn is not None: conn.rollback()
        raise
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


def oda_guncelle(oda_id: int, oda: OdaGuncelleModeli, kullanici_id: int | None = None):
    degisiklikler = oda.model_dump(exclude_unset=True)
    if not degisiklikler or any(deger is None for deger in degisiklikler.values()):
        raise HTTPException(status_code=422, detail="Güncellenecek geçerli bir alan gönderilmelidir.")

    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("SELECT oda_id FROM odalar WHERE oda_id = %s FOR UPDATE;", (oda_id,))
        if cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="Oda bulunamadı.")

        if degisiklikler.get("aktif_mi") is False:
            # Her psikologun en az bir aktif odası olmalı: tek aktif odası bu oda olan psikolog varsa pasife alınamaz.
            etkilenenler = tek_aktif_odasi_olan_psikologlar(cursor, oda_id)
            if etkilenenler:
                raise HTTPException(
                    status_code=409,
                    detail="Bu oda şu psikologların tek aktif odası: " + ", ".join(etkilenenler)
                           + ". Önce onlara başka bir oda atayın.",
                )

            # Odada bugün ve sonrası için planlı randevu varsa pasife alınamaz (randevu sahibi psikolog odasız kalır).
            cursor.execute(
                "SELECT COUNT(*) FROM randevular WHERE oda_id = %s AND durum = 'PLANLANDI' AND baslangic_zamani >= CURRENT_DATE;",
                (oda_id,),
            )
            planli = cursor.fetchone()[0]
            if planli:
                raise HTTPException(
                    status_code=409,
                    detail=f"Bu odada bugün ve sonrası için {planli} planlı randevu var. Odayı pasife almadan önce {PLANLI_RANDEVU_COZUMU}",
                )

            # Gelecekteki cihaz rezervasyonu ya da oda etkinliği olan oda da pasife alınamaz.
            kayit = oda_planli_kayit_sayilari(cursor, oda_id).get(oda_id, {})
            if kayit.get("cihaz_rezervasyonu"):
                raise HTTPException(
                    status_code=409,
                    detail=f"Bu odada henüz bitmemiş {kayit['cihaz_rezervasyonu']} cihaz rezervasyonu var. "
                           "Odayı pasife almadan önce bu rezervasyonları iptal edin.",
                )
            if kayit.get("etkinlik"):
                raise HTTPException(
                    status_code=409,
                    detail=f"Bu odada henüz bitmemiş {kayit['etkinlik']} etkinlik var. "
                           "Odayı pasife almadan önce bu etkinlikleri iptal edin.",
                )

        alanlar = ", ".join(f"{alan} = %s" for alan in degisiklikler)
        degerler = list(degisiklikler.values())

        cursor.execute(f"UPDATE odalar SET {alanlar} WHERE oda_id = %s RETURNING oda_id, oda_adi, kapasite, aktif_mi;", (*degerler, oda_id))
        sonuc = cursor.fetchone()

        cursor.execute("INSERT INTO denetim_kayitlari (kullanici_id, olay_turu, hedef_tablo, hedef_kayit_id) VALUES (%s, %s, %s, %s);", (kullanici_id, "UPDATE", "odalar", oda_id))
        conn.commit()

        return {"durum": "basarili", "mesaj": "Oda başarıyla güncellendi.", "oda": {"oda_id": sonuc[0], "oda_adi": sonuc[1], "kapasite": sonuc[2], "aktif_mi": sonuc[3]}}
    except psycopg2.errors.UniqueViolation:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=409, detail="Bu isimde başka bir oda zaten mevcut.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


def aktif_psikologlari_listele(kullanici_id: int | None = None, pasifler_dahil: bool = False):
    """Aktif psikologlar (randevu formundaki psikolog seçimi bunu kullanır).

    pasifler_dahil=true: ad gösterimi içindir; randevusu ya da danışan kodu olan pasif ya da sonradan başka role geçmiş eski
    psikologlar da gelir ve her kayıtta aktif_mi bilgisi bulunur. Böylece eski randevularda "Psikolog #19" yerine gerçek ad görünür."""
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        if pasifler_dahil:
            cursor.execute("""
                SELECT p.personel_id, k.kullanici_adi, k.kullanici_id,
                       (p.aktif_mi = TRUE AND k.aktif_mi = TRUE AND UPPER(r.rol_adi) = 'PSIKOLOG') AS aktif_mi
                FROM personel p JOIN kullanicilar k ON p.kullanici_id = k.kullanici_id JOIN roller r ON k.rol_id = r.rol_id
                WHERE (p.aktif_mi = TRUE AND k.aktif_mi = TRUE AND UPPER(r.rol_adi) = 'PSIKOLOG')
                   OR EXISTS (SELECT 1 FROM randevular x WHERE x.psikolog_id = p.personel_id)
                   OR EXISTS (SELECT 1 FROM danisan_kodlari d WHERE d.olusturan_psikolog_id = p.personel_id)
                ORDER BY k.kullanici_adi;
            """)
            return [{"personel_id": k[0], "ad_soyad": k[1], "kullanici_id": k[2], "aktif_mi": bool(k[3])} for k in cursor.fetchall()]
        cursor.execute("""
            SELECT p.personel_id, k.kullanici_adi, k.kullanici_id
            FROM personel p JOIN kullanicilar k ON p.kullanici_id = k.kullanici_id JOIN roller r ON k.rol_id = r.rol_id
            WHERE p.aktif_mi = TRUE AND k.aktif_mi = TRUE AND UPPER(r.rol_adi) = 'PSIKOLOG';
        """)
        kayitlar = cursor.fetchall()
        return [{"personel_id": k[0], "ad_soyad": k[1], "kullanici_id": k[2]} for k in kayitlar]
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


# (yöntem, yol, uç fonksiyonu, yetki parametresi, gereken yetki, ek yol ayarları): yetki bağımlılığı kayıt sırasında eklenir.
# Gereken yetki: "IZIN" (izin_kontrol), ("A", "B") (izin_kontrol_biri: biri yeter), Hepsi("A", "B") (izin_kontrol_tumu: hepsi gerekir)
# veya None (yalnızca oturum açmış olmak).
UCLAR = [
    ("GET", "/api/kullanicilar/{hedef_kullanici_id}/odalar", psikolog_oda_yetkilerini_getir, "kullanici_id", "ROL_ATAMA_DEGISTIRME", {}),
    ("PUT", "/api/kullanicilar/{hedef_kullanici_id}/odalar", psikolog_oda_yetkilerini_guncelle, "kullanici_id", "ROL_ATAMA_DEGISTIRME", {}),
    ("GET", "/api/oda-planli-randevu-sayilari", oda_planli_randevu_sayilari, "kullanici_id", Hepsi("ODA_EKLE", "ODA_DUZENLE"), {}),
    ("GET", "/api/oda-psikolog-atamalari", oda_psikolog_atamalari, "kullanici_id", Hepsi("ODA_EKLE", "ODA_DUZENLE"), {}),
    ("POST", "/api/odalar", oda_olustur, "kullanici_id", "ODA_EKLE", {"status_code": 201}),
    ("GET", "/api/psikologlar/{personel_id}/odalar", psikolog_odalarini_getir, "kullanici_id", "RANDEVU_OLUSTUR", {}),
    ("GET", "/api/odalar", odalari_listele, "kullanici_id", "ODA_DURUMU_GORUNTULE", {}),
    ("GET", "/api/cihaz-odalari", cihaz_odalarini_listele, "kullanici_id", "CIHAZ_REZERVASYON", {}),
    ("GET", "/api/odalar/{oda_id}", oda_detay, "kullanici_id", "ODA_DURUMU_GORUNTULE", {}),
    ("PATCH", "/api/odalar/{oda_id}", oda_guncelle, "kullanici_id", "ODA_DUZENLE", {}),
    ("DELETE", "/api/odalar/{oda_id}", oda_sil, "kullanici_id", Hepsi("ODA_EKLE", "ODA_DUZENLE"), {}),
    ("GET", "/api/psikologlar", aktif_psikologlari_listele, "kullanici_id", "TAKVIM_GORUNTULE", {}),
]


def router_olustur(izin_kontrol, izin_kontrol_tumu) -> APIRouter:
    """Yetki bağımlılığı üreticileri `server.sunucu` içindeki kimlik doğrulama bağımlılıklarıdır."""
    router = APIRouter()
    for metod, yol, fonksiyon, parametre, yetki, ek in UCLAR:
        if isinstance(yetki, Hepsi):
            bagimlilik = izin_kontrol_tumu(*yetki)
        elif isinstance(yetki, str):
            bagimlilik = izin_kontrol(yetki)
        else:
            raise ValueError(f"{yol}: desteklenmeyen yetki tanımı")
        router.add_api_route(yol, yetkiyle_bagla(fonksiyon, parametre, bagimlilik), methods=[metod], **ek)
    return router
