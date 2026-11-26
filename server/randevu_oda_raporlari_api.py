"""Randevu raporu ve oda kullanımı uçları (salt okunur). `server/sunucu.py` içinden ayrıldı."""
from datetime import date
from datetime import date as _ogr_date
from datetime import datetime
from datetime import timedelta

from fastapi import APIRouter, HTTPException

from server.modeller import GORUSME_TIPLERI
from server.modeller import IPTAL_NEDENLERI
from server.modeller import TERAPI_TURLERI
from server.modeller import YAS_GRUPLARI
from server.ortak_yardimcilar import psikolog_rolu_mu
from server.randevu_rapor_hesapla import randevu_raporu_hesapla
from server.vt_ayarlari import VT_AYARLARI
from server.vt_baglanti import vt_baglan
from server.yetki_baglama import yetkiyle_bagla


def randevu_raporu_secenekleri(
    psikolog_id: int | None = None,
    kullanici_id: int | None = None,
):
    """Randevu raporu süzgeç listeleri: aktif psikologlar ve onların aktif odaları, ayrıca randevu geçmişi olan pasif/eski psikologlar
    ve odalar ("(pasif)" etiketiyle); böylece geçmiş kayıtlar da süzülebilir. psikolog_id verilirse odalar o psikologa daralır.
    Psikolog yalnızca kendisini ve kendi odalarını görür."""
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("SELECT r.rol_adi FROM kullanicilar k JOIN roller r ON k.rol_id = r.rol_id WHERE k.kullanici_id = %s;", (kullanici_id,))
        rol = cursor.fetchone()
        psikolog_mu = rol is not None and psikolog_rolu_mu(rol[0])

        kosullar, parametreler = [], []
        if psikolog_mu:
            kosullar.append("p.kullanici_id = %s")
            parametreler.append(kullanici_id)
        elif psikolog_id is not None:
            kosullar.append("p.personel_id = %s")
            parametreler.append(psikolog_id)
        ek_kosul = "".join(f" AND {k}" for k in kosullar)

        # Aktif psikologlar + randevusu olan (pasif, ya da psikolog rolünden ayrılmış) eski psikologlar
        cursor.execute(f"""
            SELECT DISTINCT p.personel_id, k.kullanici_adi,
                   (p.aktif_mi = TRUE AND k.aktif_mi = TRUE AND UPPER(r.rol_adi) = 'PSIKOLOG') AS aktif
            FROM personel p
            JOIN kullanicilar k ON k.kullanici_id = p.kullanici_id
            JOIN roller r ON r.rol_id = k.rol_id
            WHERE ((p.aktif_mi = TRUE AND k.aktif_mi = TRUE AND UPPER(r.rol_adi) = 'PSIKOLOG')
                   OR EXISTS (SELECT 1 FROM randevular x WHERE x.psikolog_id = p.personel_id)){" AND p.kullanici_id = %s" if psikolog_mu else ""}
            ORDER BY k.kullanici_adi;
        """, ((kullanici_id,) if psikolog_mu else ()))
        psikologlar = [
            {"personel_id": s[0], "ad_soyad": s[1] if s[2] else f"{s[1]} (pasif)", "aktif_mi": bool(s[2])}
            for s in cursor.fetchall()
        ]

        # Aktif psikologlara atanmış aktif odalar + (seçilen) psikologların randevu yaptığı odalar (pasif oda "(pasif)" etiketiyle)
        cursor.execute(f"""
            SELECT DISTINCT o.oda_id, o.oda_adi, o.aktif_mi
            FROM odalar o
            WHERE EXISTS (
                      SELECT 1 FROM psikolog_odalar po
                      JOIN personel p ON p.kullanici_id = po.kullanici_id
                      JOIN kullanicilar k ON k.kullanici_id = p.kullanici_id
                      JOIN roller r ON r.rol_id = k.rol_id
                      WHERE po.oda_id = o.oda_id AND o.aktif_mi = TRUE AND p.aktif_mi = TRUE AND UPPER(r.rol_adi) = 'PSIKOLOG'{ek_kosul})
               OR EXISTS (
                      SELECT 1 FROM randevular x
                      JOIN personel p ON p.personel_id = x.psikolog_id
                      WHERE x.oda_id = o.oda_id{ek_kosul})
            ORDER BY o.oda_adi;
        """, tuple(parametreler) * 2)
        odalar = [
            {"oda_id": o[0], "oda_adi": o[1] if o[2] else f"{o[1]} (pasif)", "aktif_mi": bool(o[2])}
            for o in cursor.fetchall()
        ]
        return {"psikologlar": psikologlar, "odalar": odalar}
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


def oda_kullanimi(
    baslangic: date,
    bitis: date,
    kullanici_id: int | None = None,
):
    """Oda Kullanımı sayfası: odalar, seçilen tarih aralığındaki (başlangıç ve bitiş günü dahil) iptal edilmemiş randevular ve
    odası seçilmiş iptal edilmemiş cihaz rezervasyonları.

    Psikolog, başkalarının randevularında yalnızca "dolu" bilgisini görür: o satırlarda psikolog adı, danışan kodu ve görüşme tipi
    boş döner (kendi randevularında hepsi dolu). Diğer roller tüm bilgiyi görür. Cihaz rezervasyonunda odanın o saatlerde cihaz
    kullanımı nedeniyle dolu olduğu herkese görünür; cihaz adı ve bölüm yalnızca CIHAZ_REZERVASYON iznine sahip rollere gelir
    (izni olmayanda bu iki alan boş döner). En çok 62 günlük aralık istenebilir."""
    if baslangic > bitis:
        raise HTTPException(status_code=422, detail="Başlangıç tarihi bitişten büyük olamaz.")
    if (bitis - baslangic).days > 62:
        raise HTTPException(status_code=422, detail="En çok 62 günlük aralık istenebilir.")

    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT r.rol_adi,
                   COALESCE((SELECT ri.izin_var FROM rol_izinleri ri JOIN izinler i ON i.izin_id = ri.izin_id
                             WHERE ri.rol_id = k.rol_id AND i.izin_adi = 'CIHAZ_REZERVASYON'), 0),
                   COALESCE((SELECT ri.izin_var FROM rol_izinleri ri JOIN izinler i ON i.izin_id = ri.izin_id
                             WHERE ri.rol_id = k.rol_id AND i.izin_adi = 'ODA_ETKINLIK_GORUNTULE'), 0)
            FROM kullanicilar k JOIN roller r ON k.rol_id = r.rol_id WHERE k.kullanici_id = %s;
            """,
            (kullanici_id,),
        )
        rol = cursor.fetchone()
        psikolog_mu = rol is not None and psikolog_rolu_mu(rol[0])
        cihaz_detayi_gorur = rol is not None and rol[1] == 1
        etkinlik_detayi_gorur = (
            rol is not None and len(rol) > 2 and rol[2] == 1
        )

        cursor.execute("SELECT oda_id, oda_adi, kapasite, aktif_mi FROM odalar ORDER BY oda_adi, oda_id;")
        odalar = [{"oda_id": o[0], "oda_adi": o[1], "kapasite": o[2], "aktif_mi": o[3]} for o in cursor.fetchall()]

        cursor.execute("""
            SELECT r.randevu_id, r.oda_id, r.baslangic_zamani, r.bitis_zamani, r.durum, ku.kullanici_adi, r.danisan_kod_id,
                   r.gorusme_tipi, (p.kullanici_id = %s) AS benim
            FROM randevular r
            LEFT JOIN personel p ON p.personel_id = r.psikolog_id
            LEFT JOIN kullanicilar ku ON ku.kullanici_id = p.kullanici_id
            WHERE r.durum <> 'IPTAL_EDILDI' AND r.baslangic_zamani >= %s AND r.baslangic_zamani < %s
            ORDER BY r.baslangic_zamani, r.randevu_id;
        """, (kullanici_id, datetime.combine(baslangic, datetime.min.time()), datetime.combine(bitis, datetime.min.time()) + timedelta(days=1)))
        randevular = []
        for k in cursor.fetchall():
            gorunur = (not psikolog_mu) or bool(k[8])
            randevular.append({
                "randevu_id": k[0], "oda_id": k[1], "baslangic_zamani": k[2], "bitis_zamani": k[3], "durum": k[4],
                "psikolog": k[5] if gorunur else None, "danisan_kod_id": k[6] if gorunur else None,
                "gorusme_tipi": k[7] if gorunur else None, "benim": bool(k[8]),
            })

        # Cihaz rezervasyonu odayı seçilen saatlerde tamamen doldurur. Aralıkla kesişen (gün sınırını aşanlar dahil) iptal edilmemiş,
        # odası seçilmiş rezervasyonlar döner.
        cursor.execute("""
            SELECT cr.rezervasyon_id, cr.kullanilacak_oda_id, cr.baslangic_zamani, cr.bitis_zamani, c.cihaz_adi, b.bolum_adi
            FROM cihaz_rezervasyonlari cr
            JOIN cihazlar c ON c.cihaz_id = cr.cihaz_id
            LEFT JOIN bolumler b ON b.bolum_id = cr.bolum_id
            WHERE COALESCE(cr.iptal_edildi_mi, FALSE) = FALSE AND cr.kullanilacak_oda_id IS NOT NULL
              AND cr.baslangic_zamani < %s AND cr.bitis_zamani > %s
            ORDER BY cr.baslangic_zamani, cr.rezervasyon_id;
        """, (datetime.combine(bitis, datetime.min.time()) + timedelta(days=1), datetime.combine(baslangic, datetime.min.time())))
        rezervasyonlar = [
            {"rezervasyon_id": k[0], "oda_id": k[1], "baslangic_zamani": k[2], "bitis_zamani": k[3],
             "cihaz_adi": k[4] if cihaz_detayi_gorur else None, "bolum_adi": k[5] if cihaz_detayi_gorur else None}
            for k in cursor.fetchall()
        ]
        # Oda etkinlikleri: seçilen tarihlerle kesişen, iptal edilmemiş kayıtlar.
        cursor.execute("""
            SELECT
                e.etkinlik_id,
                e.oda_id,
                e.etkinlik_adi,
                e.katilimci_sayisi,
                g.baslangic_zamani,
                g.bitis_zamani,
                e.organize_eden_personel_id,
                COALESCE(e.iptal_edildi_mi, FALSE)
            FROM oda_etkinlikleri e
            JOIN oda_etkinlik_gunleri g
              ON g.etkinlik_id = e.etkinlik_id
            WHERE g.baslangic_zamani < %s
              AND g.bitis_zamani > %s
            ORDER BY g.baslangic_zamani, e.etkinlik_id;
        """, (
            datetime.combine(bitis, datetime.min.time()) + timedelta(days=1),
            datetime.combine(baslangic, datetime.min.time()),
        ))

        etkinlikler = [
            {
                "etkinlik_id": k[0],
                "oda_id": k[1],
                "etkinlik_adi": k[2] if etkinlik_detayi_gorur else None,
                "katilimci_sayisi": k[3] if etkinlik_detayi_gorur else None,
                "baslangic_zamani": k[4],
                "bitis_zamani": k[5],
                "organize_eden_personel_id": (
                    k[6] if etkinlik_detayi_gorur else None
                ),
                "iptal_edildi_mi": bool(k[7]),
            }
            for k in cursor.fetchall()
        ]

        return {
            "odalar": odalar,
            "randevular": randevular,
            "rezervasyonlar": rezervasyonlar,
            "etkinlikler": etkinlikler,
        }
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


def randevu_raporu(
    baslangic: _ogr_date | None = None,
    bitis: _ogr_date | None = None,
    psikolog_id: int | None = None,
    oda_id: int | None = None,
    detay: bool = False,
    kullanici_id: int | None = None,
):
    """Randevu raporu: seçilen dönemde (randevunun başlangıç günü) durum sayıları, psikolog bazlı döküm, iptal nedenleri ve
    görüşme tipi / terapi türü / yaş grubu dağılımı. Psikolog yalnızca kendi randevularını görür. detay=true ise tek tek
    randevular da döner (Excel için). Danışanlar yalnızca kodla görünür (kişisel veri yok)."""
    if baslangic is not None and bitis is not None and baslangic > bitis:
        raise HTTPException(status_code=422, detail="Başlangıç tarihi bitişten büyük olamaz.")

    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("SELECT r.rol_adi FROM kullanicilar k JOIN roller r ON k.rol_id = r.rol_id WHERE k.kullanici_id = %s;", (kullanici_id,))
        rol = cursor.fetchone()
        psikolog_mu = rol is not None and psikolog_rolu_mu(rol[0])

        kosullar, parametreler = [], []
        if baslangic is not None:
            kosullar.append("r.baslangic_zamani >= %s")
            parametreler.append(datetime.combine(baslangic, datetime.min.time()))
        if bitis is not None:
            kosullar.append("r.baslangic_zamani < %s")
            parametreler.append(datetime.combine(bitis, datetime.min.time()) + timedelta(days=1))
        if psikolog_mu:
            kosullar.append("p.kullanici_id = %s")      # psikolog yalnızca kendi randevularını raporlar
            parametreler.append(kullanici_id)
        elif psikolog_id is not None:
            kosullar.append("r.psikolog_id = %s")
            parametreler.append(psikolog_id)
        if oda_id is not None:
            kosullar.append("r.oda_id = %s")
            parametreler.append(oda_id)
        where = "WHERE " + " AND ".join(kosullar) if kosullar else ""

        etiketler = {"iptal": IPTAL_NEDENLERI, "gorusme": GORUSME_TIPLERI, "terapi": TERAPI_TURLERI, "yas": YAS_GRUPLARI}
        birlestirme = """
            FROM randevular r
            LEFT JOIN personel p ON p.personel_id = r.psikolog_id
            LEFT JOIN kullanicilar ku ON ku.kullanici_id = p.kullanici_id
            LEFT JOIN odalar o ON o.oda_id = r.oda_id
            LEFT JOIN danisan_kodlari d ON d.danisan_kod_id = r.danisan_kod_id
        """
        if not detay:
            # Özet rapor tek tek randevuyu Python'a taşımaz: SQL'de gruplanır (10 yıllık veride 1,6 sn -> milisaniyeler; sonuç satır satır hesapla aynıdır).
            bugun = date.today()
            cursor.execute(f"""
                SELECT r.psikolog_id, ku.kullanici_adi, r.durum, r.iptal_nedeni, r.gorusme_tipi, r.terapi_turu, d.yas_grubu,
                       (r.baslangic_zamani::date < %s::date) AS gecmis, COUNT(*) AS adet
                {birlestirme}
                {where}
                GROUP BY r.psikolog_id, ku.kullanici_adi, r.durum, r.iptal_nedeni, r.gorusme_tipi, r.terapi_turu, d.yas_grubu, gecmis;
            """, (bugun, *parametreler))
            gruplar = [
                {"psikolog_id": g[0], "psikolog_adi": g[1], "durum": g[2], "iptal_nedeni": g[3], "gorusme_tipi": g[4],
                 "terapi_turu": g[5], "yas_grubu": g[6], "gecmis": bool(g[7]), "adet": int(g[8])}
                for g in cursor.fetchall()
            ]
            cursor.execute(f"SELECT COUNT(DISTINCT r.danisan_kod_id) {birlestirme} {where};", tuple(parametreler))
            danisan_sayisi = int((cursor.fetchone() or (0,))[0])
            return randevu_raporu_hesapla(gruplar, etiketler, detay=False, bugun=bugun, danisan_sayisi=danisan_sayisi)

        cursor.execute(f"""
            SELECT r.randevu_id, r.danisan_kod_id, r.psikolog_id, ku.kullanici_adi, r.oda_id, o.oda_adi,
                   r.baslangic_zamani, r.bitis_zamani, r.durum, r.iptal_nedeni, r.gorusme_tipi, r.terapi_turu, d.yas_grubu
            {birlestirme}
            {where}
            ORDER BY r.baslangic_zamani, r.randevu_id;
        """, tuple(parametreler))
        anahtarlar = ("randevu_id", "danisan_kod_id", "psikolog_id", "psikolog_adi", "oda_id", "oda_adi",
                      "baslangic_zamani", "bitis_zamani", "durum", "iptal_nedeni", "gorusme_tipi", "terapi_turu", "yas_grubu")
        satirlar = [dict(zip(anahtarlar, kayit)) for kayit in cursor.fetchall()]
        return randevu_raporu_hesapla(satirlar, etiketler, detay=detay)
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


# (yol, uç fonksiyonu, yetki parametresi, gereken izin): yetki bağımlılığı kayıt sırasında eklenir.
# İzin None ise yalnızca oturum açmış olmak yeter (kimlik bağımlılığı).
UCLAR = [
    ("/api/randevu-raporu/secenekler", randevu_raporu_secenekleri, "kullanici_id", "TAKVIM_GORUNTULE"),
    ("/api/oda-kullanimi", oda_kullanimi, "kullanici_id", "ODA_DURUMU_GORUNTULE"),
    ("/api/randevu-raporu", randevu_raporu, "kullanici_id", "TAKVIM_GORUNTULE"),
]


def router_olustur(izin_kontrol) -> APIRouter:
    """`izin_kontrol`: `server.sunucu.izin_kontrol`."""
    router = APIRouter()
    for yol, fonksiyon, parametre, izin in UCLAR:
        router.add_api_route(yol, yetkiyle_bagla(fonksiyon, parametre, izin_kontrol(izin)), methods=["GET"])
    return router
