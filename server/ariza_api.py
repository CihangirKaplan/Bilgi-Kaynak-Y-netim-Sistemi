"""Arıza kayıtları uçları (listeleme, bildirme, güncelleme). `server/sunucu.py` içinden ayrıldı."""
from fastapi import APIRouter, HTTPException, Query, Response

from server.denetim import denetim_kaydi_olustur
from server.liste_siniri import LISTE_UST_SINIRI, liste_siniri_coz, liste_toplamini_bildir
from server.modeller import ArizaBildirimModeli, ArizaGuncelleModeli
from server.vt_ayarlari import VT_AYARLARI
from server.vt_baglanti import vt_baglan
from server.yetki_baglama import yetkiyle_bagla


# Arıza açılınca cihazın "Arızalı" olabileceği durumlar. Bakımda, kalibrasyonda veya kullanım
# dışı bir cihazın durumu arıza kaydıyla ezilmez (arıza kaydı yine de tutulur).
ARIZA_ILE_ARIZALI_OLABILEN_DURUMLAR = ("Kullanima_Hazir", "Rezerve", "Kullanimda", "Arizali")


def arizadan_sonra_cihaz_durumu(eski_durum, cozuldu_mu, baska_acik_ariza_var):
    """Arıza kaydı açıldığında/çözüldüğünde cihazın yeni durumunu belirler.

    - Çözüldü: cihaz yalnızca "Arızalı" durumdaysa ve başka açık arızası yoksa "Kullanıma Hazır" olur.
      Başka açık arıza varsa ya da cihaz bakımda/kalibrasyonda/kullanım dışıysa durumu korunur.
    - Açık: cihaz "Arızalı" olur; ancak bakımda/kalibrasyonda/kullanım dışı cihazın durumu değişmez.
    """
    if cozuldu_mu:
        if eski_durum == "Arizali" and not baska_acik_ariza_var:
            return "Kullanima_Hazir"
        return eski_durum
    if eski_durum in ARIZA_ILE_ARIZALI_OLABILEN_DURUMLAR:
        return "Arizali"
    return eski_durum


def arizalari_listele(response: Response = None, limit: int | None = Query(None, ge=1, le=LISTE_UST_SINIRI), kullanici_id: int | None = None):
    sinir = liste_siniri_coz(limit)
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT a.ariza_id, c.cihaz_adi, a.ariza_baslik, a.ariza_aciklamasi, a.aciliyet,
                   a.cozuldu_mu, a.bildirim_tarihi, c.envanter_kodu, a.cozum_tarihi, a.cozum_notu, a.cihaz_id
            FROM cihaz_arizalari a
            JOIN cihazlar c ON a.cihaz_id = c.cihaz_id
            ORDER BY a.bildirim_tarihi DESC
            LIMIT %s;
        """, (sinir,))
        satirlar = cursor.fetchall()
        liste_toplamini_bildir(cursor, response, len(satirlar), "SELECT COUNT(*) FROM cihaz_arizalari;", sinir)
        return [
            {
                "ariza_id": k[0],
                "cihaz_adi": k[1],
                "ariza_baslik": k[2],
                "ariza_aciklama": k[3],
                "aciliyet": k[4],
                "durum": "Çözüldü" if k[5] else "Açık",
                "bildirim_tarihi": k[6].isoformat() if hasattr(k[6], 'isoformat') else str(k[6]),
                "envanter_kodu": k[7] if len(k) > 7 else None,
                "cozum_tarihi": (k[8].isoformat() if hasattr(k[8], "isoformat") else k[8]) if len(k) > 8 else None,
                "cozum_notu": k[9] if len(k) > 9 else None,
                "cihaz_id": k[10] if len(k) > 10 else None,          # cihaz geçmişine bağlantı için
            }
            for k in satirlar
        ]
    except Exception:
        raise HTTPException(status_code=500, detail="İşlem sırasında beklenmeyen bir sunucu hatası oluştu.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


def ariza_bildir(ariza: ArizaBildirimModeli, kullanici_id: int | None = None):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        # 1. Cihaz var mı ve durumu uygun mu kontrolü
        cursor.execute("SELECT durum FROM cihazlar WHERE cihaz_id = %s FOR UPDATE;", (ariza.cihaz_id,))
        cihaz = cursor.fetchone()
        if cihaz is None:
            raise HTTPException(status_code=404, detail="Cihaz bulunamadı.")

        # 2. Bildiren personelin adını (kullanıcı adını) bulalım (DB varchar bekliyor)
        cursor.execute("SELECT kullanici_adi FROM kullanicilar WHERE kullanici_id = %s;", (kullanici_id,))
        kullanici = cursor.fetchone()
        bildiren_kisi = kullanici[0] if kullanici else f"Kullanıcı-{kullanici_id}"

        # 3. Arıza kaydını ekle (başlık ve aciliyet kendi sütunlarında tutulur)
        cursor.execute("""
            INSERT INTO cihaz_arizalari (cihaz_id, bildiren_personel, ariza_baslik, ariza_aciklamasi, aciliyet,
                                         bildirim_tarihi, cozuldu_mu)
            VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, FALSE) RETURNING ariza_id;
        """, (ariza.cihaz_id, bildiren_kisi, ariza.ariza_baslik.strip(), ariza.ariza_aciklama.strip(), ariza.aciliyet))
        ariza_id = cursor.fetchone()[0]

        # 5. Cihazı 'Arizali' yap; bakımda/kalibrasyonda/kullanım dışı cihazın durumu korunur.
        yeni_durum = arizadan_sonra_cihaz_durumu(cihaz[0], False, True)
        if yeni_durum != cihaz[0]:
            cursor.execute("UPDATE cihazlar SET durum = %s WHERE cihaz_id = %s;", (yeni_durum, ariza.cihaz_id))
        # 6. Denetim (Audit) logları
        # Arıza oluşturma kaydını aynı transaction içinde tut.
        denetim_kaydi_olustur(
            VT_AYARLARI,
            olay_turu="CREATE",
            kullanici_id=kullanici_id,
            hedef_tablo="cihaz_arizalari",
            hedef_kayit_id=ariza_id,
            mevcut_cursor=cursor
        )

        # Cihazın durumu gerçekten değiştiyse ayrıca kaydet.
        if yeni_durum != cihaz[0]:
            denetim_kaydi_olustur(
                VT_AYARLARI,
                olay_turu="DEVICE_STATUS_CHANGE",
                kullanici_id=kullanici_id,
                hedef_tablo="cihazlar",
                hedef_kayit_id=ariza.cihaz_id,
                mevcut_cursor=cursor
            )
        conn.commit()
        if yeni_durum == "Arizali":
            mesaj = "Arıza bildirimi alındı ve cihaz arızalı konuma çekildi."
        else:
            mesaj = f"Arıza bildirimi alındı. Cihaz '{cihaz[0]}' durumunda olduğu için cihaz durumu değiştirilmedi."
        return {"durum": "basarili", "mesaj": mesaj, "ariza_id": ariza_id}
    except HTTPException:
        if conn is not None:
            conn.rollback()
        raise
    except Exception:
        if conn is not None:
            conn.rollback()
        raise HTTPException(
            status_code=500,
            detail="İşlem sırasında bir sunucu hatası oluştu."
        )
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


def ariza_guncelle(ariza_id: int, ariza: ArizaGuncelleModeli, kullanici_id: int | None = None):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        # Cihaz IDsini bulalım
        cursor.execute("SELECT cihaz_id FROM cihaz_arizalari WHERE ariza_id = %s FOR UPDATE;", (ariza_id,))
        kayit = cursor.fetchone()
        if kayit is None:
            raise HTTPException(status_code=404, detail="Arıza kaydı bulunamadı.")
        cihaz_id = kayit[0]

        # Çözüldüyse çözüm tarihini anlık at, çözülmediyse NULL (Boş) yap. Çözüm notu: çözüldüyse yazılan not (gönderilmediyse eskisi
        # korunur), yeniden açıldıysa temizlenir.
        cozum_sql = "CURRENT_TIMESTAMP" if ariza.cozuldu_mu else "NULL"
        not_sql = "COALESCE(%s, cozum_notu)" if ariza.cozuldu_mu else "NULL"
        not_parametresi = (ariza.cozum_notu,) if ariza.cozuldu_mu else ()

        # Arıza Tablosunu Güncelle
        cursor.execute(f"""
            UPDATE cihaz_arizalari
            SET ariza_baslik = %s, ariza_aciklamasi = %s, aciliyet = %s,
                cozuldu_mu = %s, cozum_tarihi = {cozum_sql}, cozum_notu = {not_sql}
            WHERE ariza_id = %s;
        """, (ariza.ariza_baslik.strip(), ariza.ariza_aciklama.strip(), ariza.aciliyet, ariza.cozuldu_mu, *not_parametresi, ariza_id))

        # Cihazın mevcut durumunu oku, satırı kilitle ve cihazın BAŞKA açık arızası var mı bak.
        cursor.execute(
            """
            SELECT durum,
                   EXISTS (SELECT 1 FROM cihaz_arizalari
                           WHERE cihaz_id = %s AND cozuldu_mu = FALSE AND ariza_id <> %s)
            FROM cihazlar WHERE cihaz_id = %s FOR UPDATE;
            """,
            (cihaz_id, ariza_id, cihaz_id)
        )
        cihaz_kaydi = cursor.fetchone()

        if cihaz_kaydi is None:
            raise HTTPException(status_code=404, detail="Cihaz bulunamadı.")

        eski_cihaz_durum, baska_acik_ariza_var = cihaz_kaydi
        yeni_cihaz_durum = arizadan_sonra_cihaz_durumu(
            eski_cihaz_durum, ariza.cozuldu_mu, baska_acik_ariza_var
        )

        # Arıza güncellemesini audit'e kaydet.
        denetim_kaydi_olustur(
            VT_AYARLARI,
            olay_turu="UPDATE",
            kullanici_id=kullanici_id,
            hedef_tablo="cihaz_arizalari",
            hedef_kayit_id=ariza_id,
            mevcut_cursor=cursor
        )

        # Yalnızca gerçek durum değişikliğinde cihazı güncelle ve audit oluştur.
        if eski_cihaz_durum != yeni_cihaz_durum:
            cursor.execute(
                "UPDATE cihazlar SET durum = %s WHERE cihaz_id = %s;",
                (yeni_cihaz_durum, cihaz_id)
            )

            denetim_kaydi_olustur(
                VT_AYARLARI,
                olay_turu="DEVICE_STATUS_CHANGE",
                kullanici_id=kullanici_id,
                hedef_tablo="cihazlar",
                hedef_kayit_id=cihaz_id,
                mevcut_cursor=cursor
            )
        conn.commit()
        return {"durum": "basarili", "mesaj": "Arıza başarıyla güncellendi."}
    except HTTPException:
        if conn is not None:
            conn.rollback()
        raise
    except Exception:
        if conn is not None:
            conn.rollback()
        raise HTTPException(
            status_code=500,
            detail="İşlem sırasında bir sunucu hatası oluştu."
        )
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


# (yöntem, yol, uç fonksiyonu, yetki parametresi, gereken yetki, ek yol ayarları): yetki bağımlılığı kayıt sırasında eklenir.
# Gereken yetki: "IZIN" (izin_kontrol), ("A", "B") (izin_kontrol_biri: biri yeter) veya None (yalnızca oturum açmış olmak).
UCLAR = [
    ("GET", "/api/arizalar", arizalari_listele, "kullanici_id", "ARIZA_KAYITLARI_YONET", {}),
    ("POST", "/api/arizalar", ariza_bildir, "kullanici_id", "ARIZA_KAYITLARI_YONET", {"status_code": 201}),
    ("PUT", "/api/arizalar/{ariza_id}", ariza_guncelle, "kullanici_id", "ARIZA_KAYITLARI_YONET", {}),
]


def router_olustur(izin_kontrol) -> APIRouter:
    """Yetki bağımlılığı üreticileri `server.sunucu` içindeki kimlik doğrulama bağımlılıklarıdır."""
    router = APIRouter()
    for metod, yol, fonksiyon, parametre, yetki, ek in UCLAR:
        assert isinstance(yetki, str), yol          # bu modülde yalnızca tek izin tanımlı
        bagimlilik = izin_kontrol(yetki)
        router.add_api_route(yol, yetkiyle_bagla(fonksiyon, parametre, bagimlilik), methods=[metod], **ek)
    return router
