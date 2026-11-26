"""Bakım ve kalibrasyon planları uçları ve plan yardımcıları. `server/sunucu.py` içinden ayrıldı."""
from datetime import date
from datetime import timedelta

from fastapi import APIRouter, HTTPException

from server.denetim import denetim_kaydi_olustur, satiri_sil_ve_ayrintisini_al
from server.modeller import BakimPlaniGuncelleModeli, BakimPlaniOlusturModeli
from server.ortak_yardimcilar import plan_kalibrasyon_mu
from server.vt_ayarlari import VT_AYARLARI
from server.vt_baglanti import vt_baglan
from server.yetki_baglama import yetkiyle_bagla


def bakim_plani_durumu(kalan_gun, uyari_suresi_gun, aktif_mi):
    if not aktif_mi:
        return "Pasif"
    if kalan_gun < 0:
        return "Gecikmiş"
    if kalan_gun <= uyari_suresi_gun:
        return "Yaklaşıyor"
    return "Planlı"


def _plan_yetkileri(cursor, kullanici_id):
    """Giriş yapan kişinin bakım ve kalibrasyon izinlerini DB'den al."""
    cursor.execute("""
        SELECT i.izin_adi
        FROM kullanicilar k
        JOIN rol_izinleri ri ON ri.rol_id = k.rol_id
        JOIN izinler i ON i.izin_id = ri.izin_id
        WHERE k.kullanici_id = %s
          AND ri.izin_var = 1
          AND i.izin_adi = ANY(%s);
    """, (
        kullanici_id,
        ["BAKIM_KAYITLARI_YONET", "KALIBRASYON_KAYITLARI_YONET", "BAKIM_KAYITLARI_GORUNTULE", "KALIBRASYON_KAYITLARI_GORUNTULE"]
    ))
    return {satir[0] for satir in cursor.fetchall()}


def _plan_turu_yetkisini_dogrula(izinler, gorev_turu):
    gerekli = (
        "KALIBRASYON_KAYITLARI_YONET"
        if plan_kalibrasyon_mu(gorev_turu)
        else "BAKIM_KAYITLARI_YONET"
    )
    if gerekli not in izinler:
        raise HTTPException(
            status_code=403,
            detail="Bu plan türü için yetkiniz bulunmuyor."
        )


def bakim_planlarini_listele(
    cihaz_id: int | None = None,
    aktif_mi: bool | None = None,
    kullanici_id: int | None = None,
):
    """Cihazların tekrarlayan bakım/kalibrasyon planları (en yakın tarih önce)."""
    if cihaz_id is not None and cihaz_id <= 0:
        raise HTTPException(status_code=422, detail="Geçerli bir cihaz seçilmelidir.")
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        izinler = _plan_yetkileri(cursor, kullanici_id)
        # Planları görmek için görüntüleme YA DA yönetme izni yeter; ekleme/düzenleme/silme yalnızca yönetme ister
        # (_plan_turu_yetkisini_dogrula *_YONET arar).
        bakim = bool(izinler & {"BAKIM_KAYITLARI_YONET", "BAKIM_KAYITLARI_GORUNTULE"})
        kalibrasyon = bool(izinler & {"KALIBRASYON_KAYITLARI_YONET", "KALIBRASYON_KAYITLARI_GORUNTULE"})

        if not bakim and not kalibrasyon:
            raise HTTPException(
                status_code=403,
                detail="Planları görüntüleme yetkiniz bulunmuyor."
            )

        kosullar, parametreler = [], []

        if bakim and not kalibrasyon:
            kosullar.append(
                "LOWER(BTRIM(p.gorev_turu)) NOT LIKE 'kalibrasyon%%'"
            )
        elif kalibrasyon and not bakim:
            kosullar.append(
                "LOWER(BTRIM(p.gorev_turu)) LIKE 'kalibrasyon%%'"
            )
        if cihaz_id is not None:
            kosullar.append("p.cihaz_id = %s")
            parametreler.append(cihaz_id)
        if aktif_mi is not None:
            kosullar.append("COALESCE(p.aktif_mi, TRUE) = %s")
            parametreler.append(aktif_mi)
        where = "WHERE " + " AND ".join(kosullar) if kosullar else ""
        cursor.execute(
            f"""
            SELECT p.plan_id, p.cihaz_id, c.envanter_kodu, c.cihaz_adi, p.gorev_turu, p.periyot_gun,
                   COALESCE(p.uyari_suresi_gun, 0), p.sonraki_gorev_tarihi,
                   (p.sonraki_gorev_tarihi - CURRENT_DATE), COALESCE(p.aktif_mi, TRUE)
            FROM cihaz_bakim_planlari p
            JOIN cihazlar c ON c.cihaz_id = p.cihaz_id
            {where}
            ORDER BY p.sonraki_gorev_tarihi, p.plan_id;
            """,
            parametreler,
        )
        return [
            {
                "plan_id": k[0], "cihaz_id": k[1], "envanter_kodu": k[2], "cihaz_adi": k[3],
                "gorev_turu": k[4], "periyot_gun": k[5], "uyari_suresi_gun": k[6],
                "sonraki_gorev_tarihi": k[7].isoformat(), "kalan_gun": k[8], "aktif_mi": k[9],
                "durum": bakim_plani_durumu(k[8], k[6], k[9]),
            }
            for k in cursor.fetchall()
        ]
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Bakım planları alınamadı.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


def plani_ilerlet(cursor, plan_id, cihaz_id, kalibrasyon_mi, sonraki_tarih):
    """Kayıt bir plana bağlıysa planın 'sonraki tarihini' ilerletir ve o tarihi döndürür.

    sonraki_tarih verilmişse (kullanıcının girdiği) o kullanılır; yoksa kayıt bitişi + periyot
    ayrıca hesaplanıp çağıran tarafından verilir. Plan başka cihaza ait, pasif ya da türü
    uyumsuzsa (bakım kaydı ile kalibrasyon planı gibi) kayıt hiç eklenmeden hata verilir.
    """
    cursor.execute(
        "SELECT cihaz_id, gorev_turu, COALESCE(aktif_mi, TRUE) FROM cihaz_bakim_planlari WHERE plan_id = %s FOR UPDATE;",
        (plan_id,),
    )
    plan = cursor.fetchone()
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan bulunamadı.")
    if plan[0] != cihaz_id:
        raise HTTPException(status_code=422, detail="Seçilen plan bu cihaza ait değil.")
    if not plan[2]:
        raise HTTPException(status_code=422, detail="Seçilen plan pasif durumda.")
    if plan_kalibrasyon_mu(plan[1]) != kalibrasyon_mi:
        raise HTTPException(status_code=422, detail="Plan türü bu kayıt türüyle uyuşmuyor.")
    cursor.execute("UPDATE cihaz_bakim_planlari SET sonraki_gorev_tarihi = %s WHERE plan_id = %s;", (sonraki_tarih, plan_id))
    return sonraki_tarih


def plan_periyodu(cursor, plan_id):
    cursor.execute("SELECT periyot_gun FROM cihaz_bakim_planlari WHERE plan_id = %s;", (plan_id,))
    satir = cursor.fetchone()
    return satir[0] if satir else None


def _ayni_planli_aktif_kayit_var_mi(cursor, cihaz_id, gorev_turu, haric_plan_id=None):
    cursor.execute(
        """
        SELECT 1 FROM cihaz_bakim_planlari
        WHERE cihaz_id = %s AND LOWER(gorev_turu) = LOWER(%s) AND COALESCE(aktif_mi, TRUE) = TRUE
          AND (%s::int IS NULL OR plan_id <> %s::int)
        LIMIT 1;
        """,
        (cihaz_id, gorev_turu, haric_plan_id, haric_plan_id),
    )
    return cursor.fetchone() is not None


def bakim_plani_ekle(plan: BakimPlaniOlusturModeli, kullanici_id: int | None = None):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        izinler = _plan_yetkileri(cursor, kullanici_id)
        _plan_turu_yetkisini_dogrula(izinler, plan.gorev_turu)
        cursor.execute("SELECT 1 FROM cihazlar WHERE cihaz_id = %s;", (plan.cihaz_id,))
        if cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="Cihaz bulunamadı.")
        if _ayni_planli_aktif_kayit_var_mi(cursor, plan.cihaz_id, plan.gorev_turu):
            raise HTTPException(status_code=409, detail="Bu cihaz için aynı türde aktif bir plan zaten var.")
        sonraki = plan.sonraki_gorev_tarihi or (date.today() + timedelta(days=plan.periyot_gun))
        cursor.execute(
            """
            INSERT INTO cihaz_bakim_planlari (cihaz_id, gorev_turu, periyot_gun, uyari_suresi_gun, sonraki_gorev_tarihi, aktif_mi)
            VALUES (%s, %s, %s, %s, %s, TRUE) RETURNING plan_id;
            """,
            (plan.cihaz_id, plan.gorev_turu, plan.periyot_gun, plan.uyari_suresi_gun, sonraki),
        )
        plan_id = cursor.fetchone()[0]
        denetim_kaydi_olustur(VT_AYARLARI, olay_turu="CREATE", kullanici_id=kullanici_id,
                              hedef_tablo="cihaz_bakim_planlari", hedef_kayit_id=plan_id, mevcut_cursor=cursor)
        conn.commit()
        return {"durum": "basarili", "mesaj": "Plan eklendi.", "plan_id": plan_id,
                "sonraki_gorev_tarihi": sonraki.isoformat()}
    except HTTPException:
        if conn is not None: conn.rollback()
        raise
    except Exception:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=500, detail="İşlem sırasında beklenmeyen bir sunucu hatası oluştu.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


def bakim_plani_guncelle(plan_id: int, guncelleme: BakimPlaniGuncelleModeli,
                         kullanici_id: int | None = None):
    degisiklikler = guncelleme.model_dump(exclude_unset=True)
    if not degisiklikler:
        raise HTTPException(status_code=422, detail="Güncellenecek veri bulunamadı.")
    if any(deger is None for deger in degisiklikler.values()):
        raise HTTPException(status_code=422, detail="Alanlar boş bırakılamaz.")
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT cihaz_id, gorev_turu, periyot_gun, COALESCE(uyari_suresi_gun, 0), COALESCE(aktif_mi, TRUE)
            FROM cihaz_bakim_planlari WHERE plan_id = %s FOR UPDATE;
            """,
            (plan_id,),
        )
        mevcut = cursor.fetchone()
        if mevcut is None:
            raise HTTPException(status_code=404, detail="Plan bulunamadı.")
        cihaz_id, tur, periyot, uyari, aktif = mevcut
        izinler = _plan_yetkileri(cursor, kullanici_id)
        _plan_turu_yetkisini_dogrula(izinler, tur)
        yeni_tur = degisiklikler.get("gorev_turu", tur)
        _plan_turu_yetkisini_dogrula(izinler, yeni_tur)
        tur = yeni_tur
        periyot = degisiklikler.get("periyot_gun", periyot)
        uyari = degisiklikler.get("uyari_suresi_gun", uyari)
        aktif = degisiklikler.get("aktif_mi", aktif)
        if uyari > periyot:
            raise HTTPException(status_code=422, detail="Uyarı süresi periyottan uzun olamaz.")
        if aktif and _ayni_planli_aktif_kayit_var_mi(cursor, cihaz_id, tur, plan_id):
            raise HTTPException(status_code=409, detail="Bu cihaz için aynı türde aktif bir plan zaten var.")
        alanlar = ", ".join(f"{alan} = %s" for alan in degisiklikler)
        cursor.execute(f"UPDATE cihaz_bakim_planlari SET {alanlar} WHERE plan_id = %s;",
                       (*degisiklikler.values(), plan_id))
        denetim_kaydi_olustur(VT_AYARLARI, olay_turu="UPDATE", kullanici_id=kullanici_id,
                              hedef_tablo="cihaz_bakim_planlari", hedef_kayit_id=plan_id, mevcut_cursor=cursor)
        conn.commit()
        return {"durum": "basarili", "mesaj": "Plan güncellendi."}
    except HTTPException:
        if conn is not None: conn.rollback()
        raise
    except Exception:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=500, detail="İşlem sırasında beklenmeyen bir sunucu hatası oluştu.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


def bakim_plani_sil(plan_id: int, kullanici_id: int | None = None):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT gorev_turu FROM cihaz_bakim_planlari "
            "WHERE plan_id = %s FOR UPDATE;",
            (plan_id,)
        )
        mevcut = cursor.fetchone()
        if mevcut is None:
            raise HTTPException(
                status_code=404, detail="Plan bulunamadı."
            )
        izinler = _plan_yetkileri(cursor, kullanici_id)
        _plan_turu_yetkisini_dogrula(izinler, mevcut[0])
        silinen = satiri_sil_ve_ayrintisini_al(cursor, "cihaz_bakim_planlari", plan_id)
        if silinen is None:
            raise HTTPException(status_code=404, detail="Plan bulunamadı.")
        denetim_kaydi_olustur(VT_AYARLARI, olay_turu="DELETE", kullanici_id=kullanici_id,
                              hedef_tablo="cihaz_bakim_planlari", hedef_kayit_id=plan_id, mevcut_cursor=cursor,
                              ayrinti=silinen)
        conn.commit()
        return {"durum": "basarili", "mesaj": "Plan silindi."}
    except HTTPException:
        if conn is not None: conn.rollback()
        raise
    except Exception:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=500, detail="İşlem sırasında beklenmeyen bir sunucu hatası oluştu.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


# (yöntem, yol, uç fonksiyonu, yetki parametresi, gereken yetki, ek yol ayarları): yetki bağımlılığı kayıt sırasında eklenir.
# Gereken yetki: "IZIN" (izin_kontrol), ("A", "B") (izin_kontrol_biri: biri yeter) veya None (yalnızca oturum açmış olmak).
UCLAR = [
    ("GET", "/api/bakim-planlari", bakim_planlarini_listele, "kullanici_id", None, {}),
    ("POST", "/api/bakim-planlari", bakim_plani_ekle, "kullanici_id", None, {"status_code": 201}),
    ("PUT", "/api/bakim-planlari/{plan_id}", bakim_plani_guncelle, "kullanici_id", None, {}),
    ("DELETE", "/api/bakim-planlari/{plan_id}", bakim_plani_sil, "kullanici_id", None, {}),
]


def router_olustur(mevcut_kullanici_id) -> APIRouter:
    """Yetki bağımlılığı üreticileri `server.sunucu` içindeki kimlik doğrulama bağımlılıklarıdır."""
    router = APIRouter()
    for metod, yol, fonksiyon, parametre, yetki, ek in UCLAR:
        assert yetki is None, yol          # bu modülde yalnızca oturum bağımlılığı tanımlı
        bagimlilik = mevcut_kullanici_id
        router.add_api_route(yol, yetkiyle_bagla(fonksiyon, parametre, bagimlilik), methods=[metod], **ek)
    return router
