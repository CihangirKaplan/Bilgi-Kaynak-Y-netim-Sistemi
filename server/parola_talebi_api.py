"""Parola sıfırlama talebi uçları: giriş ekranından talep, yönetici listesi ve kapatma. `server/sunucu.py` içinden ayrıldı."""
from fastapi import APIRouter, HTTPException, Response

from server.modeller import ParolaSifirlamaTalebiModeli
from server.vt_ayarlari import VT_AYARLARI
from server.vt_baglanti import vt_baglan
from server.yetki_baglama import Hepsi, yetkiyle_bagla


PAROLA_TALEBI_ACIK_UST_SINIR = 50


# Kapalı ofis ağında kullanıcı adları gizli değildir; kullanıcı, yazım hatasını hemen anlasın diye var olmayan ve pasif
# hesaplar açıkça söylenir. (Giriş ekranı ise bilerek "kullanıcı adı veya parola hatalı" der.)
PAROLA_TALEBI_ALINDI_MESAJI = "Talebiniz yöneticiye iletildi. Geçici parolanızı yöneticinizden alın."


PAROLA_TALEBI_ZATEN_VAR_MESAJI = "Bu hesap için zaten bekleyen bir talebiniz var. Yöneticinizin size dönmesini bekleyin."


PAROLA_TALEBI_KULLANICI_YOK_MESAJI = "Bu kullanıcı adıyla kayıtlı bir hesap bulunamadı. Yazımı kontrol edip tekrar deneyin."


PAROLA_TALEBI_HESAP_PASIF_MESAJI = "Bu hesap pasif. Lütfen yöneticinize başvurun."


PAROLA_TALEBI_HESAP_YONETICI_MESAJI = (
    "Bu bir yönetici hesabı; parolası uygulamadan sıfırlanamaz. Sunucu bilgisayarından sorumlu kişiye (sistem sorumlusu) başvurun."
)


def parola_sifirlama_talebi_olustur(talep: ParolaSifirlamaTalebiModeli):
    """Giriş yapmadan parola sıfırlama talebi açar.

    Var olmayan kullanıcı adı 404 (KULLANICI_BULUNAMADI), pasif hesap 403 (HESAP_PASIF) ile açıkça bildirilir; bu
    durumlarda talep kaydedilmez. Her kullanıcı için en fazla bir açık talep tutulur (varsa durum "zaten_var")."""
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT k.kullanici_id, k.aktif_mi, r.rol_adi
            FROM kullanicilar k
            LEFT JOIN roller r ON r.rol_id = k.rol_id
            WHERE LOWER(k.kullanici_adi) = LOWER(%s)
            ORDER BY (k.kullanici_adi = %s) DESC
            LIMIT 1;
            """,
            (talep.kullanici_adi, talep.kullanici_adi)      # girişle aynı kural: kullanıcı adı harf duyarsız
        )
        kullanici = cursor.fetchone()
        alindi = {"durum": "alindi", "mesaj": PAROLA_TALEBI_ALINDI_MESAJI}
        zaten_var = {"durum": "zaten_var", "mesaj": PAROLA_TALEBI_ZATEN_VAR_MESAJI}

        if kullanici is None:
            raise HTTPException(
                status_code=404,
                detail={"kod": "KULLANICI_BULUNAMADI", "mesaj": PAROLA_TALEBI_KULLANICI_YOK_MESAJI},
            )
        if not kullanici[1]:
            raise HTTPException(
                status_code=403,
                detail={"kod": "HESAP_PASIF", "mesaj": PAROLA_TALEBI_HESAP_PASIF_MESAJI},
            )
        if len(kullanici) > 2 and kullanici[2] == "ADMIN":
            # Yönetici hesapları uygulamadan sıfırlanamadığı için talep açmak anlamsızdır (kimse karşılayamaz): kaydedilmez.
            raise HTTPException(
                status_code=403,
                detail={"kod": "HESAP_YONETICI", "mesaj": PAROLA_TALEBI_HESAP_YONETICI_MESAJI},
            )

        cursor.execute(
            "SELECT 1 FROM parola_sifirlama_talepleri WHERE kullanici_id = %s AND durum = 'ACIK';",
            (kullanici[0],)
        )
        if cursor.fetchone() is not None:
            return zaten_var                           # zaten bekleyen talebi var

        cursor.execute("SELECT COUNT(*) FROM parola_sifirlama_talepleri WHERE durum = 'ACIK';")
        if cursor.fetchone()[0] >= PAROLA_TALEBI_ACIK_UST_SINIR:
            raise HTTPException(
                status_code=429,
                detail="Çok fazla bekleyen talep var. Lütfen yöneticinize doğrudan ulaşın."
            )

        cursor.execute(
            """
            INSERT INTO parola_sifirlama_talepleri (kullanici_id)
            VALUES (%s)
            ON CONFLICT (kullanici_id) WHERE durum = 'ACIK' DO NOTHING
            RETURNING talep_id;
            """,
            (kullanici[0],)
        )
        yeni = cursor.fetchone()
        if yeni is None:
            return zaten_var                           # eşzamanlı başka bir istek az önce açtı
        from server.denetim import denetim_kaydi_olustur
        denetim_kaydi_olustur(
            VT_AYARLARI, olay_turu="CREATE", kullanici_id=kullanici[0],
            hedef_tablo="parola_sifirlama_talepleri", hedef_kayit_id=yeni[0], mevcut_cursor=cursor
        )
        conn.commit()
        return alindi

    except HTTPException:
        if conn is not None:
            conn.rollback()
        raise
    except Exception:
        if conn is not None:
            conn.rollback()
        raise HTTPException(status_code=500, detail="Talep şu anda alınamadı. Lütfen daha sonra tekrar deneyin.")
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


def parola_sifirlama_taleplerini_listele(
    response: Response,
    kullanici_id: int | None = None
):
    """Bekleyen (açık) parola sıfırlama talepleri; en eski talep önce."""
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT t.talep_id, k.kullanici_id, k.kullanici_adi, r.rol_adi, t.talep_zamani,
                   FLOOR(EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - t.talep_zamani)) / 60)::int
            FROM parola_sifirlama_talepleri t
            JOIN kullanicilar k ON k.kullanici_id = t.kullanici_id
            LEFT JOIN roller r ON r.rol_id = k.rol_id
            WHERE t.durum = 'ACIK' AND k.aktif_mi AND r.rol_adi IS DISTINCT FROM 'ADMIN'
            ORDER BY t.talep_zamani, t.talep_id;
            """
        )
        response.headers["Cache-Control"] = "no-store"
        return [
            {
                "talep_id": s[0], "kullanici_id": s[1], "kullanici_adi": s[2], "rol_adi": s[3],
                "talep_zamani": s[4].isoformat(), "bekleme_dakika": max(int(s[5] or 0), 0),
            }
            for s in cursor.fetchall()
        ]
    except Exception:
        raise HTTPException(status_code=500, detail="Parola sıfırlama talepleri alınamadı.")
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


def parola_sifirlama_talebini_kapat(
    talep_id: int,
    islem_yapan_id: int | None = None
):
    """Bekleyen bir talebi parolayı sıfırlamadan kapatır (örn. kullanıcı parolasını hatırladı)."""
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE parola_sifirlama_talepleri
            SET durum = 'KAPATILDI', kapanis_zamani = CURRENT_TIMESTAMP, kapatan_kullanici_id = %s
            WHERE talep_id = %s AND durum = 'ACIK'
            RETURNING talep_id;
            """,
            (islem_yapan_id, talep_id)
        )
        if cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="Bekleyen talep bulunamadı.")
        from server.denetim import denetim_kaydi_olustur
        denetim_kaydi_olustur(
            VT_AYARLARI, olay_turu="UPDATE", kullanici_id=islem_yapan_id,
            hedef_tablo="parola_sifirlama_talepleri", hedef_kayit_id=talep_id, mevcut_cursor=cursor
        )
        conn.commit()
        return {"durum": "basarili", "mesaj": "Talep kapatıldı."}
    except HTTPException:
        if conn is not None:
            conn.rollback()
        raise
    except Exception:
        if conn is not None:
            conn.rollback()
        raise HTTPException(status_code=500, detail="Talep kapatılamadı.")
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


# (yöntem, yol, uç fonksiyonu, yetki parametresi, gereken yetki, ek yol ayarları): yetki bağımlılığı kayıt sırasında eklenir.
# Gereken yetki: "IZIN" (izin_kontrol), ("A", "B") (izin_kontrol_biri: biri yeter), Hepsi("A", "B") (izin_kontrol_tumu: hepsi gerekir)
# veya None (yalnızca oturum açmış olmak).
UCLAR = [
    ("POST", "/api/parola-sifirlama-talebi", parola_sifirlama_talebi_olustur, None, False, {}),
    ("GET", "/api/parola-sifirlama-talepleri", parola_sifirlama_taleplerini_listele, "kullanici_id", "KULLANICI_PAROLA_SIFIRLA", {}),
    ("PATCH", "/api/parola-sifirlama-talepleri/{talep_id}/kapat", parola_sifirlama_talebini_kapat, "islem_yapan_id", "KULLANICI_PAROLA_SIFIRLA", {}),
]


def router_olustur(izin_kontrol) -> APIRouter:
    """Yetki bağımlılığı üreticileri `server.sunucu` içindeki kimlik doğrulama bağımlılıklarıdır."""
    router = APIRouter()
    for metod, yol, fonksiyon, parametre, yetki, ek in UCLAR:
        if yetki is False:          # herkese açık uç: kimlik doğrulaması yok
            router.add_api_route(yol, fonksiyon, methods=[metod], **ek)
            continue
        elif isinstance(yetki, str):
            bagimlilik = izin_kontrol(yetki)
        else:
            raise ValueError(f"{yol}: desteklenmeyen yetki tanımı")
        router.add_api_route(yol, yetkiyle_bagla(fonksiyon, parametre, bagimlilik), methods=[metod], **ek)
    return router
