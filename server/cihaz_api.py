"""Cihaz uçları: listeleme, ekleme, güncelleme, detay ve geçmiş. `server/sunucu.py` içinden ayrıldı."""
from fastapi import APIRouter, HTTPException
import psycopg2
import psycopg2.errors

from server.denetim import denetim_kaydi_olustur
from server.modeller import CihazGuncelleModeli, CihazOlusturModeli
from server.ortak_sabitler import ETKIN_CIHAZ_DURUMU_SQL
from server.rezervasyon_api import rezervasyon_gorunen_durumu
from server.vt_ayarlari import VT_AYARLARI
from server.vt_baglanti import vt_baglan
from server.yetki_baglama import yetkiyle_bagla


def cihaz_ekle(cihaz: CihazOlusturModeli, kullanici_id: int | None = None):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        # Envanter kodu büyük/küçük harf ayırt etmeden benzersiz olmalı (EEG-01 ile eeg-01 aynı cihazdır).
        cursor.execute("SELECT 1 FROM cihazlar WHERE lower(envanter_kodu) = lower(%s) OR (%s IS NOT NULL AND seri_no = %s);", (cihaz.envanter_kodu, cihaz.seri_no, cihaz.seri_no))
        if cursor.fetchone():
            raise HTTPException(status_code=409, detail="Bu envanter kodu veya seri no zaten kullanımda.")

        cursor.execute(
            "INSERT INTO cihazlar (envanter_kodu, cihaz_adi, marka_model, seri_no, durum) VALUES (%s, %s, %s, %s, %s) RETURNING cihaz_id;",
            (cihaz.envanter_kodu, cihaz.cihaz_adi, cihaz.marka_model, cihaz.seri_no, cihaz.durum.value)
        )
        cihaz_id = cursor.fetchone()[0]
        denetim_kaydi_olustur(
            VT_AYARLARI,
            olay_turu="CREATE",
            kullanici_id=kullanici_id,
            hedef_tablo="cihazlar",
            hedef_kayit_id=cihaz_id,
            mevcut_cursor=cursor
        )
        conn.commit()
        return {"durum": "basarili", "mesaj": "Cihaz başarıyla eklendi.", "cihaz_id": cihaz_id}
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


def cihaz_guncelle(
    cihaz_id: int,
    guncelleme: CihazGuncelleModeli,
    kullanici_id: int | None = None
):
    conn = None
    cursor = None

    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        degisiklikler = guncelleme.model_dump(exclude_unset=True)

        if not degisiklikler:
            raise HTTPException(
                status_code=422,
                detail="Güncellenecek alan bulunamadı."
            )

        if "durum" in degisiklikler and hasattr(degisiklikler["durum"], "value"):
            degisiklikler["durum"] = degisiklikler["durum"].value

        # Mevcut cihaz durumunu oku ve satırı kilitle.
        cursor.execute(
            "SELECT durum FROM cihazlar WHERE cihaz_id = %s FOR UPDATE;",
            (cihaz_id,)
        )
        kayit = cursor.fetchone()

        if kayit is None:
            raise HTTPException(status_code=404, detail="Cihaz bulunamadı.")

        eski_durum = kayit[0]

        # Açık arızası olan cihazın durumu elle değiştirilemez: etkin durum zaten arıza kaydından "Arızalı" çıkar ve elle girilen değer
        # bir şeyi değiştirmeden başarılı görünürdü. Kullanım dışına alma (cihaz hizmetten çıkarılıyor) her zaman yapılabilir.
        yeni_durum = degisiklikler.get("durum")
        if yeni_durum is not None and yeni_durum != eski_durum and yeni_durum != "Kullanim_Disi" and cihazin_acik_arizasi_var_mi(cursor, cihaz_id):
            raise HTTPException(
                status_code=409,
                detail="Bu cihazın çözülmemiş arıza kaydı var; durumu elle değiştirilemez. "
                       "Önce Arıza Kayıtları sayfasından arızayı çözüldü olarak işaretleyin.",
            )

        alanlar = ", ".join(f"{alan} = %s" for alan in degisiklikler)
        degerler = list(degisiklikler.values())

        cursor.execute(
            f"UPDATE cihazlar SET {alanlar} WHERE cihaz_id = %s RETURNING cihaz_id;",
            (*degerler, cihaz_id)
        )

        # Cihazın diğer bilgilerinin güncellenmesi.
        if any(alan != "durum" for alan in degisiklikler):
            denetim_kaydi_olustur(
                VT_AYARLARI,
                olay_turu="UPDATE",
                kullanici_id=kullanici_id,
                hedef_tablo="cihazlar",
                hedef_kayit_id=cihaz_id,
                mevcut_cursor=cursor
            )

        # Cihaz durumu gerçekten değiştiyse ayrıca audit kaydı oluştur.
        if "durum" in degisiklikler and eski_durum != degisiklikler["durum"]:
            denetim_kaydi_olustur(
                VT_AYARLARI,
                olay_turu="DEVICE_STATUS_CHANGE",
                kullanici_id=kullanici_id,
                hedef_tablo="cihazlar",
                hedef_kayit_id=cihaz_id,
                mevcut_cursor=cursor
            )

        conn.commit()

        return {"durum": "basarili", "mesaj": "Cihaz güncellendi."}

    except psycopg2.errors.UniqueViolation:
        if conn is not None:
            conn.rollback()
        raise HTTPException(status_code=409, detail="Bu seri no başka bir cihazda kullanımda.")

    except Exception:
        if conn is not None:
            conn.rollback()
        raise

    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


def cihazin_acik_arizasi_var_mi(cursor, cihaz_id) -> bool:
    """Cihazın çözülmemiş (açık) arıza kaydı var mı? Cihaz durumunu elle değiştirmeden önce denetlenir."""
    cursor.execute("SELECT EXISTS (SELECT 1 FROM cihaz_arizalari WHERE cihaz_id = %s AND cozuldu_mu IS NOT TRUE);", (cihaz_id,))
    return bool(cursor.fetchone()[0])


def cihazlari_listele(kullanici_id: int | None = None):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT c.cihaz_id, c.envanter_kodu, c.cihaz_adi, c.marka_model, c.seri_no, c.durum, c.kayit_tarihi, "
            + ETKIN_CIHAZ_DURUMU_SQL + " AS etkin_durum FROM cihazlar c ORDER BY c.cihaz_id;"
        )
        kayitlar = cursor.fetchall()
        return [{"cihaz_id": k[0], "envanter_kodu": k[1], "cihaz_adi": k[2], "marka_model": k[3], "seri_no": k[4], "durum": k[5], "kayit_tarihi": k[6],
                 "etkin_durum": k[7] if len(k) > 7 else k[5]} for k in kayitlar]
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


GECMIS_OLAY_SINIRI = 300             # her tür için en fazla bu kadar en yeni kayıt döner (özet sayıları sınırsızdır)


def _gun_metni(deger):
    """date/datetime -> 'gg.aa.yyyy' (boşsa '—')."""
    return deger.strftime("%d.%m.%Y") if hasattr(deger, "strftime") else "—"


def _iso(deger):
    return deger.isoformat() if hasattr(deger, "isoformat") else (str(deger) if deger else None)


def cihaz_gecmisi_getir(cihaz_id: int, kullanici_id: int | None = None):
    """Bir cihazın yaşam döngüsü: bakım, kalibrasyon, arıza ve rezervasyon kayıtları tek zaman çizgisinde (en yeni önce) ve özet sayılar."""
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT c.cihaz_id, c.envanter_kodu, c.cihaz_adi, c.marka_model, c.seri_no, c.durum, c.kayit_tarihi, "
            + ETKIN_CIHAZ_DURUMU_SQL + " FROM cihazlar c WHERE c.cihaz_id = %s;", (cihaz_id,))
        c = cursor.fetchone()
        if c is None:
            raise HTTPException(status_code=404, detail="Cihaz bulunamadı.")
        cihaz = {"cihaz_id": c[0], "envanter_kodu": c[1], "cihaz_adi": c[2], "marka_model": c[3], "seri_no": c[4], "durum": c[5],
                 "kayit_tarihi": _iso(c[6]), "etkin_durum": c[7]}

        olaylar = []
        cursor.execute(
            """
            SELECT bakim_id, COALESCE(bakim_baslangic_tarihi, bakim_tarihi::date), COALESCE(bakim_bitis_tarihi, bakim_tarihi::date),
                   yapilan_islem, bakim_yapan_kisi, maliyet, sonraki_bakim_tarihi
            FROM cihaz_bakimlari WHERE cihaz_id = %s
            ORDER BY COALESCE(bakim_baslangic_tarihi, bakim_tarihi::date) DESC, bakim_id DESC LIMIT %s;
            """, (cihaz_id, GECMIS_OLAY_SINIRI))
        for k in cursor.fetchall():
            ayrinti = [f"Yapan: {k[4] or '—'}"]
            if k[5] is not None:
                ayrinti.append(f"Maliyet: {float(k[5]):,.2f} ₺".replace(",", "X").replace(".", ",").replace("X", "."))
            if k[6]:
                ayrinti.append(f"Sonraki bakım: {_gun_metni(k[6])}")
            olaylar.append({"tur": "Bakım", "kayit_id": k[0], "baslangic": _iso(k[1]), "bitis": _iso(k[2]), "baslik": k[3] or "Bakım",
                            "ayrinti": " · ".join(ayrinti), "durum": None})

        cursor.execute(
            """
            SELECT kalibrasyon_id, COALESCE(kalibrasyon_baslangic_tarihi, islem_tarihi::date), COALESCE(kalibrasyon_bitis_tarihi, islem_tarihi::date),
                   sertifika_no, kalibrasyon_yapan_kurum, gecerlilik_tarihi
            FROM cihaz_kalibrasyonlari WHERE cihaz_id = %s
            ORDER BY COALESCE(kalibrasyon_baslangic_tarihi, islem_tarihi::date) DESC, kalibrasyon_id DESC LIMIT %s;
            """, (cihaz_id, GECMIS_OLAY_SINIRI))
        for k in cursor.fetchall():
            olaylar.append({"tur": "Kalibrasyon", "kayit_id": k[0], "baslangic": _iso(k[1]), "bitis": _iso(k[2]),
                            "baslik": f"Sertifika {k[3] or '—'}",
                            "ayrinti": f"Kurum: {k[4] or '—'} · Geçerlilik: {_gun_metni(k[5])}", "durum": None})

        cursor.execute(
            """
            SELECT ariza_id, bildirim_tarihi, cozum_tarihi, ariza_baslik, ariza_aciklamasi, aciliyet, cozuldu_mu, bildiren_personel, cozum_notu
            FROM cihaz_arizalari WHERE cihaz_id = %s ORDER BY bildirim_tarihi DESC, ariza_id DESC LIMIT %s;
            """, (cihaz_id, GECMIS_OLAY_SINIRI))
        for k in cursor.fetchall():
            ayrinti = [f"Aciliyet: {k[5] or '—'}", f"Bildiren: {k[7] or '—'}"]
            if k[6] and k[8]:
                ayrinti.append(f"Çözüm: {k[8]}")
            olaylar.append({"tur": "Arıza", "kayit_id": k[0], "baslangic": _iso(k[1]), "bitis": _iso(k[2]) if k[6] else None,
                            "baslik": k[3] or "Arıza", "ayrinti": " · ".join(ayrinti), "durum": "Çözüldü" if k[6] else "Açık"})

        cursor.execute(
            """
            SELECT r.rezervasyon_id, r.baslangic_zamani, r.bitis_zamani, r.iptal_edildi_mi, b.bolum_adi, o.oda_adi, r.proje_turu,
                   r.proje_adi_aciklamasi, ky.kullanici_adi
            FROM cihaz_rezervasyonlari r
            LEFT JOIN bolumler b ON b.bolum_id = r.bolum_id
            LEFT JOIN odalar o ON o.oda_id = r.kullanilacak_oda_id
            LEFT JOIN kullanicilar ky ON ky.personel_id = r.rezervasyonu_yapan_personel_id
            WHERE r.cihaz_id = %s ORDER BY r.baslangic_zamani DESC, r.rezervasyon_id DESC LIMIT %s;
            """, (cihaz_id, GECMIS_OLAY_SINIRI))
        for k in cursor.fetchall():
            ayrinti = [f"Oda: {k[5] or '—'}"]
            if k[6]:
                ayrinti.append(f"Proje: {k[6]}")
            if k[8]:
                ayrinti.append(f"Yapan: {k[8]}")
            if k[7]:
                ayrinti.append(str(k[7]))
            olaylar.append({"tur": "Rezervasyon", "kayit_id": k[0], "baslangic": _iso(k[1]), "bitis": _iso(k[2]),
                            "baslik": k[4] or "Rezervasyon", "ayrinti": " · ".join(ayrinti),
                            "durum": rezervasyon_gorunen_durumu(k[3], k[2])})

        olaylar.sort(key=lambda o: (o["baslangic"] or ""), reverse=True)

        cursor.execute(
            """
            SELECT
              (SELECT COUNT(*) FROM cihaz_bakimlari WHERE cihaz_id = %(c)s),
              (SELECT COALESCE(SUM(maliyet), 0) FROM cihaz_bakimlari WHERE cihaz_id = %(c)s),
              (SELECT COUNT(*) FROM cihaz_kalibrasyonlari WHERE cihaz_id = %(c)s),
              (SELECT MAX(gecerlilik_tarihi) FROM cihaz_kalibrasyonlari WHERE cihaz_id = %(c)s),
              (SELECT COUNT(*) FROM cihaz_arizalari WHERE cihaz_id = %(c)s),
              (SELECT COUNT(*) FROM cihaz_arizalari WHERE cihaz_id = %(c)s AND cozuldu_mu = FALSE),
              (SELECT COUNT(*) FROM cihaz_rezervasyonlari WHERE cihaz_id = %(c)s AND iptal_edildi_mi = FALSE),
              (SELECT COALESCE(SUM(EXTRACT(EPOCH FROM (bitis_zamani - baslangic_zamani)) / 3600), 0)
                 FROM cihaz_rezervasyonlari WHERE cihaz_id = %(c)s AND iptal_edildi_mi = FALSE)
            """, {"c": cihaz_id})
        o = cursor.fetchone()
        ozet = {"bakim_sayisi": o[0], "toplam_bakim_maliyeti": float(o[1] or 0), "kalibrasyon_sayisi": o[2],
                "kalibrasyon_gecerlilik": _iso(o[3]), "ariza_sayisi": o[4], "acik_ariza_sayisi": o[5],
                "rezervasyon_sayisi": o[6], "rezervasyon_saati": round(float(o[7] or 0), 1)}
        return {"cihaz": cihaz, "ozet": ozet, "olaylar": olaylar, "sinir": GECMIS_OLAY_SINIRI}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="İşlem sırasında beklenmeyen bir sunucu hatası oluştu.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


def cihaz_detayi_getir(cihaz_id: int, kullanici_id: int | None = None):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("SELECT cihaz_id, envanter_kodu, cihaz_adi, marka_model, seri_no, durum, kayit_tarihi FROM cihazlar WHERE cihaz_id = %s;", (cihaz_id,))
        kayit = cursor.fetchone()
        if kayit is None:
            raise HTTPException(status_code=404, detail="Cihaz bulunamadı.")
        return {"cihaz_id": kayit[0], "envanter_kodu": kayit[1], "cihaz_adi": kayit[2], "marka_model": kayit[3], "seri_no": kayit[4], "durum": kayit[5], "kayit_tarihi": kayit[6]}
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


# (yöntem, yol, uç fonksiyonu, yetki parametresi, gereken yetki, ek yol ayarları): yetki bağımlılığı kayıt sırasında eklenir.
# Gereken yetki: "IZIN" (izin_kontrol), ("A", "B") (izin_kontrol_biri: biri yeter) veya None (yalnızca oturum açmış olmak).
UCLAR = [
    ("POST", "/api/cihazlar", cihaz_ekle, "kullanici_id", "CIHAZ_EKLE", {"status_code": 201}),
    ("PATCH", "/api/cihazlar/{cihaz_id}", cihaz_guncelle, "kullanici_id", "CIHAZ_ENVANTER_YONET", {}),
    ("GET", "/api/cihazlar", cihazlari_listele, "kullanici_id", "CIHAZ_UYGUNLUK_GORUNTULE", {}),
    ("GET", "/api/cihazlar/{cihaz_id}/gecmis", cihaz_gecmisi_getir, "kullanici_id", "CIHAZ_ENVANTER_YONET", {}),
    ("GET", "/api/cihazlar/{cihaz_id}", cihaz_detayi_getir, "kullanici_id", "CIHAZ_UYGUNLUK_GORUNTULE", {}),
]


def router_olustur(izin_kontrol) -> APIRouter:
    """Yetki bağımlılığı üreticileri `server.sunucu` içindeki kimlik doğrulama bağımlılıklarıdır."""
    router = APIRouter()
    for metod, yol, fonksiyon, parametre, yetki, ek in UCLAR:
        assert isinstance(yetki, str), yol          # bu modülde yalnızca tek izin tanımlı
        bagimlilik = izin_kontrol(yetki)
        router.add_api_route(yol, yetkiyle_bagla(fonksiyon, parametre, bagimlilik), methods=[metod], **ek)
    return router
