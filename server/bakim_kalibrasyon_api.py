"""Bakım ve kalibrasyon kayıtları uçları (listeleme, ekleme, güncelleme, silme). `server/sunucu.py` içinden ayrıldı."""
from datetime import timedelta

from fastapi import APIRouter, HTTPException, Query, Response

from server.bakim_plani_api import plan_periyodu, plani_ilerlet
from server.denetim import denetim_kaydi_olustur, satiri_sil_ve_ayrintisini_al
from server.liste_siniri import LISTE_UST_SINIRI, liste_siniri_coz, liste_toplamini_bildir
from server.modeller import BakimGuncelleModeli, BakimOlusturModeli, KalibrasyonGuncelleModeli, KalibrasyonOlusturModeli, bakim_tarihi_sorunu
from server.rezervasyon_cakismasi import cakisan_rezervasyonlari_denetle
from server.vt_ayarlari import VT_AYARLARI
from server.vt_baglanti import vt_baglan
from server.yetki_baglama import yetkiyle_bagla


def bakimlari_listele(response: Response = None, limit: int | None = Query(None, ge=1, le=LISTE_UST_SINIRI), kullanici_id: int | None = None):
    sinir = liste_siniri_coz(limit)
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        # EKSİK OLAN KISIM: SQL sorgusuna b.bakim_baslangic_tarihi ve b.bakim_bitis_tarihi EKLENDİ
        cursor.execute("""
            SELECT b.bakim_id, c.cihaz_adi, c.envanter_kodu,
                   b.bakim_yapan_kisi, b.yapilan_islem, b.maliyet,
                   b.bakim_tarihi, b.sonraki_bakim_tarihi,
                   b.bakim_baslangic_tarihi, b.bakim_bitis_tarihi, b.uyari_suresi_gun,
                   b.plan_id, p.gorev_turu
            FROM cihaz_bakimlari b
            JOIN cihazlar c ON b.cihaz_id = c.cihaz_id
            LEFT JOIN cihaz_bakim_planlari p ON p.plan_id = b.plan_id
            ORDER BY b.bakim_tarihi DESC
            LIMIT %s;
        """, (sinir,))
        kayitlar = cursor.fetchall()
        liste_toplamini_bildir(cursor, response, len(kayitlar), "SELECT COUNT(*) FROM cihaz_bakimlari;", sinir)

        return [
            {
                "bakim_id": k[0],
                "cihaz_adi": f"{k[2]} - {k[1]}",
                "bakim_yapan_kisi": k[3],
                "yapilan_islem": k[4],
                "maliyet": float(k[5]) if k[5] else 0.0,
                "bakim_tarihi": k[6].isoformat() if hasattr(k[6], 'isoformat') else str(k[6]),
                "sonraki_bakim_tarihi": k[7].isoformat() if k[7] and hasattr(k[7], 'isoformat') else (str(k[7]) if k[7] else "Belirtilmedi"),

                # EKSİK OLAN KISIM: JSON sözlüğüne başlangıç ve bitiş eklendi (eski kayıtlarda null gelirse bakim_tarihi kurtarır)
                "bakim_baslangic_tarihi": k[8].isoformat() if k[8] and hasattr(k[8], 'isoformat') else (str(k[6]) if k[6] else "Belirtilmedi"),
                "bakim_bitis_tarihi": k[9].isoformat() if k[9] and hasattr(k[9], 'isoformat') else (str(k[6]) if k[6] else "Belirtilmedi"),
                "uyari_suresi_gun": k[10],
                "plan_id": k[11],          # kaydın yerine getirdiği plan (yoksa None)
                "plan_adi": k[12]
            }
            for k in kayitlar
        ]
    except Exception:
        raise HTTPException(status_code=500, detail="İşlem sırasında beklenmeyen bir sunucu hatası oluştu.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


def bakim_kaydi_ekle(bakim: BakimOlusturModeli, kullanici_id: int | None = None):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        cakisan_rezervasyonlari_denetle(
            cursor, bakim.cihaz_id, bakim.bakim_baslangic_tarihi, bakim.bakim_bitis_tarihi
        )

        sonraki_bakim = bakim.sonraki_bakim_tarihi
        if bakim.plan_id is not None:
            # Tarih boş bırakıldıysa plan periyoduna göre otomatik doldurulur.
            if sonraki_bakim is None:
                periyot = plan_periyodu(cursor, bakim.plan_id)
                if periyot is not None:
                    sonraki_bakim = bakim.bakim_bitis_tarihi + timedelta(days=periyot)
            if sonraki_bakim is not None:
                plani_ilerlet(cursor, bakim.plan_id, bakim.cihaz_id, False, sonraki_bakim)
            else:
                raise HTTPException(status_code=404, detail="Plan bulunamadı.")

        cursor.execute("""
            INSERT INTO cihaz_bakimlari (
                cihaz_id, bakim_yapan_kisi, yapilan_islem, maliyet,
                bakim_tarihi, bakim_baslangic_tarihi, bakim_bitis_tarihi, sonraki_bakim_tarihi, uyari_suresi_gun,
                plan_id
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING bakim_id;
        """, (
            bakim.cihaz_id,
            bakim.bakim_yapan_kisi,
            bakim.yapilan_islem,
            bakim.maliyet,
            bakim.bakim_tarihi,
            bakim.bakim_baslangic_tarihi,
            bakim.bakim_bitis_tarihi,
            sonraki_bakim,
            bakim.uyari_suresi_gun,
            bakim.plan_id
        ))
        bakim_id = cursor.fetchone()[0]

        from server.denetim import denetim_kaydi_olustur
        denetim_kaydi_olustur(VT_AYARLARI, "CREATE", kullanici_id, "cihaz_bakimlari", bakim_id, mevcut_cursor=cursor)

        conn.commit()
        return {"durum": "basarili", "bakim_id": bakim_id,
                "sonraki_bakim_tarihi": sonraki_bakim.isoformat() if sonraki_bakim else None}
    except HTTPException:
        if conn is not None: conn.rollback()
        raise
    except Exception:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=500, detail="İşlem sırasında beklenmeyen bir sunucu hatası oluştu.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


def bakim_guncelle(bakim_id: int, guncelleme: BakimGuncelleModeli, kullanici_id: int | None = None):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        cursor.execute("SELECT 1 FROM cihaz_bakimlari WHERE bakim_id = %s FOR UPDATE;", (bakim_id,))
        if cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="Bakım kaydı bulunamadı.")

        degisiklikler = guncelleme.model_dump(exclude_unset=True)
        if not degisiklikler:
            raise HTTPException(status_code=422, detail="Güncellenecek veri bulunamadı.")

        # Bakım tarihi ayrı bir alan değildir: her zaman bakım başlangıç tarihine eşit tutulur.
        degisiklikler.pop("bakim_tarihi", None)
        if degisiklikler.get("bakim_baslangic_tarihi") is not None:
            degisiklikler["bakim_tarihi"] = degisiklikler["bakim_baslangic_tarihi"]

        # Tarih aralığı değiştiyse, yeni aralıkla kesişen rezervasyonlar kullanıcıya gösterilir.
        if "bakim_baslangic_tarihi" in degisiklikler or "bakim_bitis_tarihi" in degisiklikler or "sonraki_bakim_tarihi" in degisiklikler:
            cursor.execute(
                """
                SELECT cihaz_id, COALESCE(bakim_baslangic_tarihi, bakim_tarihi::date),
                       COALESCE(bakim_bitis_tarihi, bakim_tarihi::date), sonraki_bakim_tarihi
                FROM cihaz_bakimlari WHERE bakim_id = %s;
                """,
                (bakim_id,),
            )
            cihaz_id, mevcut_bas, mevcut_bit, mevcut_sonraki = cursor.fetchone()
            baslangic = degisiklikler.get("bakim_baslangic_tarihi") or mevcut_bas
            bitis = degisiklikler.get("bakim_bitis_tarihi") or mevcut_bit
            sonraki = degisiklikler["sonraki_bakim_tarihi"] if "sonraki_bakim_tarihi" in degisiklikler else mevcut_sonraki
            sorun = bakim_tarihi_sorunu(baslangic, bitis, sonraki)            # eksik gönderilen alan için kayıtlı değerle birlikte denetlenir
            if sorun:
                raise HTTPException(status_code=422, detail=sorun)
            # Yalnızca tarih aralığı gerçekten değiştiyse kontrol edilir (not/maliyet düzenlemesinde değil).
            if baslangic is not None and bitis is not None and (baslangic, bitis) != (mevcut_bas, mevcut_bit):
                cakisan_rezervasyonlari_denetle(cursor, cihaz_id, baslangic, bitis)

        alanlar = ", ".join(f"{alan} = %s" for alan in degisiklikler)
        degerler = list(degisiklikler.values())

        cursor.execute(f"UPDATE cihaz_bakimlari SET {alanlar} WHERE bakim_id = %s;", (*degerler, bakim_id))
        denetim_kaydi_olustur(VT_AYARLARI, olay_turu="UPDATE", kullanici_id=kullanici_id, hedef_tablo="cihaz_bakimlari", hedef_kayit_id=bakim_id, mevcut_cursor=cursor)

        conn.commit()
        return {"durum": "basarili", "mesaj": "Bakım kaydı başarıyla güncellendi."}
    except HTTPException:
        if conn is not None:
            conn.rollback()
        raise
    except Exception:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=500, detail="İşlem sırasında beklenmeyen bir sunucu hatası oluştu.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


def bakim_kaydi_sil(bakim_id: int, kullanici_id: int | None = None):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        silinen = satiri_sil_ve_ayrintisini_al(cursor, "cihaz_bakimlari", bakim_id)
        if silinen is None:
            raise HTTPException(status_code=404, detail="Bakım kaydı bulunamadı.")

        # Silme ile denetim kaydı (silinen içerikle birlikte) aynı işlemde (transaction) yazılır.
        denetim_kaydi_olustur(VT_AYARLARI, "DELETE", kullanici_id, "cihaz_bakimlari", bakim_id,
                              mevcut_cursor=cursor, ayrinti=silinen)

        conn.commit()
        return {"durum": "basarili", "mesaj": "Bakım kaydı silindi."}
    except HTTPException:
        if conn is not None: conn.rollback()
        raise
    except Exception:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=500, detail="Bakım kaydı silinemedi.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


def kalibrasyonlari_listele(response: Response = None, limit: int | None = Query(None, ge=1, le=LISTE_UST_SINIRI), kullanici_id: int | None = None):
    sinir = liste_siniri_coz(limit)
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        # SQL Sorgusuna yeni sütunlar eklendi
        cursor.execute("""
            SELECT k.kalibrasyon_id, c.cihaz_adi, c.envanter_kodu,
                   k.kalibrasyon_yapan_kurum, k.gecerlilik_tarihi, k.sertifika_no, k.islem_tarihi,
                   k.kalibrasyon_baslangic_tarihi, k.kalibrasyon_bitis_tarihi, k.uyari_suresi_gun,
                   k.plan_id, p.gorev_turu
            FROM cihaz_kalibrasyonlari k
            JOIN cihazlar c ON k.cihaz_id = c.cihaz_id
            LEFT JOIN cihaz_bakim_planlari p ON p.plan_id = k.plan_id
            ORDER BY k.islem_tarihi DESC
            LIMIT %s;
        """, (sinir,))
        kayitlar = cursor.fetchall()
        liste_toplamini_bildir(cursor, response, len(kayitlar), "SELECT COUNT(*) FROM cihaz_kalibrasyonlari;", sinir)

        return [
            {
                "kalibrasyon_id": k[0],
                "cihaz_adi": f"{k[2]} - {k[1]}",
                "kalibrasyon_yapan_kurum": k[3],
                "gecerlilik_tarihi": k[4].isoformat() if hasattr(k[4], 'isoformat') else str(k[4]),
                "sertifika_no": k[5],
                "islem_tarihi": k[6].isoformat() if hasattr(k[6], 'isoformat') else str(k[6]),
                # Yeni alanlar ve Fallback mantığı (Eski kayıtlarda null gelirse işlem tarihi baz alınır)
                "kalibrasyon_baslangic_tarihi": k[7].isoformat() if k[7] and hasattr(k[7], 'isoformat') else (str(k[6])[:10] if k[6] else "Belirtilmedi"),
                "kalibrasyon_bitis_tarihi": k[8].isoformat() if k[8] and hasattr(k[8], 'isoformat') else (str(k[6])[:10] if k[6] else "Belirtilmedi"),
                "uyari_suresi_gun": k[9],
                "plan_id": k[10],          # kaydın yerine getirdiği plan (yoksa None)
                "plan_adi": k[11]
            }
            for k in kayitlar
        ]
    except Exception:
        raise HTTPException(status_code=500, detail="İşlem sırasında beklenmeyen bir sunucu hatası oluştu.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


def kalibrasyon_kaydi_ekle(kalib: KalibrasyonOlusturModeli, kullanici_id: int | None = None):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        cakisan_rezervasyonlari_denetle(
            cursor, kalib.cihaz_id, kalib.kalibrasyon_baslangic_tarihi, kalib.kalibrasyon_bitis_tarihi
        )

        if kalib.plan_id is not None:
            plani_ilerlet(cursor, kalib.plan_id, kalib.cihaz_id, True, kalib.gecerlilik_tarihi)

        # INSERT sorgusuna ve VALUES kısmına yeni sütunlar eklendi
        cursor.execute("""
            INSERT INTO cihaz_kalibrasyonlari (
                cihaz_id, kalibrasyon_yapan_kurum, gecerlilik_tarihi, sertifika_no, islem_tarihi,
                kalibrasyon_baslangic_tarihi, kalibrasyon_bitis_tarihi, uyari_suresi_gun, plan_id
            )
            VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP, %s, %s, %s, %s) RETURNING kalibrasyon_id;
        """, (
            kalib.cihaz_id, 
            kalib.kalibrasyon_yapan_kurum, 
            kalib.gecerlilik_tarihi, 
            kalib.sertifika_no,
            kalib.kalibrasyon_baslangic_tarihi, # EKLENDİ
            kalib.kalibrasyon_bitis_tarihi,     # EKLENDİ
            kalib.uyari_suresi_gun,
            kalib.plan_id
        ))
        kalibrasyon_id = cursor.fetchone()[0]

        from server.denetim import denetim_kaydi_olustur
        denetim_kaydi_olustur(VT_AYARLARI, olay_turu="CREATE", kullanici_id=kullanici_id, hedef_tablo="cihaz_kalibrasyonlari", hedef_kayit_id=kalibrasyon_id, mevcut_cursor=cursor)

        conn.commit()
        return {"durum": "basarili", "mesaj": "Kalibrasyon başarıyla eklendi.", "kalibrasyon_id": kalibrasyon_id}
    except HTTPException:
        if conn is not None: conn.rollback()
        raise
    except Exception:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=500, detail="İşlem sırasında beklenmeyen bir sunucu hatası oluştu.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


def kalibrasyon_guncelle(kalibrasyon_id: int, guncelleme: KalibrasyonGuncelleModeli, kullanici_id: int | None = None):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        cursor.execute("SELECT 1 FROM cihaz_kalibrasyonlari WHERE kalibrasyon_id = %s FOR UPDATE;", (kalibrasyon_id,))
        if cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="Kayıt bulunamadı.")

        degisiklikler = guncelleme.model_dump(exclude_unset=True)
        if not degisiklikler:
            raise HTTPException(status_code=422, detail="Değişiklik yok.")

        # Tarih aralığı değiştiyse, yeni aralıkla kesişen rezervasyonlar kullanıcıya gösterilir.
        if "kalibrasyon_baslangic_tarihi" in degisiklikler or "kalibrasyon_bitis_tarihi" in degisiklikler:
            cursor.execute(
                """
                SELECT cihaz_id, kalibrasyon_baslangic_tarihi, kalibrasyon_bitis_tarihi
                FROM cihaz_kalibrasyonlari WHERE kalibrasyon_id = %s;
                """,
                (kalibrasyon_id,),
            )
            cihaz_id, mevcut_bas, mevcut_bit = cursor.fetchone()
            baslangic = degisiklikler.get("kalibrasyon_baslangic_tarihi") or mevcut_bas
            bitis = degisiklikler.get("kalibrasyon_bitis_tarihi") or mevcut_bit
            if baslangic is not None and bitis is not None and bitis < baslangic:
                raise HTTPException(status_code=422, detail="Kalibrasyon bitiş tarihi, başlangıç tarihinden önce olamaz.")
            if baslangic is not None and bitis is not None and (baslangic, bitis) != (mevcut_bas, mevcut_bit):
                cakisan_rezervasyonlari_denetle(cursor, cihaz_id, baslangic, bitis)

        alanlar = ", ".join(f"{alan} = %s" for alan in degisiklikler)
        degerler = list(degisiklikler.values())

        cursor.execute(f"UPDATE cihaz_kalibrasyonlari SET {alanlar} WHERE kalibrasyon_id = %s;", (*degerler, kalibrasyon_id))
        denetim_kaydi_olustur(VT_AYARLARI, olay_turu="UPDATE", kullanici_id=kullanici_id, hedef_tablo="cihaz_kalibrasyonlari", hedef_kayit_id=kalibrasyon_id, mevcut_cursor=cursor)

        conn.commit()
        return {"durum": "basarili"}
    except HTTPException:
        if conn is not None:
            conn.rollback()
        raise
    except Exception:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=500, detail="İşlem sırasında beklenmeyen bir sunucu hatası oluştu.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


def kalibrasyon_kaydi_sil(kalibrasyon_id: int, kullanici_id: int | None = None):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        silinen = satiri_sil_ve_ayrintisini_al(cursor, "cihaz_kalibrasyonlari", kalibrasyon_id)
        if silinen is None:
            raise HTTPException(status_code=404, detail="Kalibrasyon kaydı bulunamadı.")

        denetim_kaydi_olustur(VT_AYARLARI, "DELETE", kullanici_id, "cihaz_kalibrasyonlari", kalibrasyon_id,
                              mevcut_cursor=cursor, ayrinti=silinen)

        conn.commit()
        return {"durum": "basarili", "mesaj": "Kalibrasyon kaydı silindi."}
    except HTTPException:
        if conn is not None: conn.rollback()
        raise
    except Exception:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=500, detail="Kalibrasyon kaydı silinemedi.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


# (yöntem, yol, uç fonksiyonu, yetki parametresi, gereken yetki, ek yol ayarları): yetki bağımlılığı kayıt sırasında eklenir.
# Gereken yetki: "IZIN" (izin_kontrol), ("A", "B") (izin_kontrol_biri: biri yeter) veya None (yalnızca oturum açmış olmak).
UCLAR = [
    ("GET", "/api/bakimlar", bakimlari_listele, "kullanici_id", ("BAKIM_KAYITLARI_GORUNTULE", "BAKIM_KAYITLARI_YONET"), {}),
    ("POST", "/api/bakimlar", bakim_kaydi_ekle, "kullanici_id", "BAKIM_KAYITLARI_YONET", {"status_code": 201}),
    ("PUT", "/api/bakimlar/{bakim_id}", bakim_guncelle, "kullanici_id", "BAKIM_KAYITLARI_YONET", {}),
    ("DELETE", "/api/bakimlar/{bakim_id}", bakim_kaydi_sil, "kullanici_id", "BAKIM_KAYITLARI_YONET", {}),
    ("GET", "/api/kalibrasyonlar", kalibrasyonlari_listele, "kullanici_id", ("KALIBRASYON_KAYITLARI_GORUNTULE", "KALIBRASYON_KAYITLARI_YONET"), {}),
    ("POST", "/api/kalibrasyonlar", kalibrasyon_kaydi_ekle, "kullanici_id", "KALIBRASYON_KAYITLARI_YONET", {"status_code": 201}),
    ("PUT", "/api/kalibrasyonlar/{kalibrasyon_id}", kalibrasyon_guncelle, "kullanici_id", "KALIBRASYON_KAYITLARI_YONET", {}),
    ("DELETE", "/api/kalibrasyonlar/{kalibrasyon_id}", kalibrasyon_kaydi_sil, "kullanici_id", "KALIBRASYON_KAYITLARI_YONET", {}),
]


def router_olustur(izin_kontrol, izin_kontrol_biri) -> APIRouter:
    """Yetki bağımlılığı üreticileri `server.sunucu` içindeki kimlik doğrulama bağımlılıklarıdır."""
    router = APIRouter()
    for metod, yol, fonksiyon, parametre, yetki, ek in UCLAR:
        if isinstance(yetki, str):
            bagimlilik = izin_kontrol(yetki)
        else:
            bagimlilik = izin_kontrol_biri(*yetki)
        router.add_api_route(yol, yetkiyle_bagla(fonksiyon, parametre, bagimlilik), methods=[metod], **ek)
    return router
