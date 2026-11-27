"""Rol ve izin uçları: roller, atanabilir roller, yetki özeti, rol-izin matrisi, izin ekleme ve düzenleme. `server/sunucu.py` içinden ayrıldı."""
from fastapi import APIRouter, HTTPException
import psycopg2

from server.denetim import ayrintili_kayit_yaz, denetim_kaydi_olustur, satiri_sil_ve_ayrintisini_al
from server.modeller import IzinDuzenleModeli, RolGorunenAdModeli, RolModeli
from server.vt_ayarlari import VT_AYARLARI
from server.vt_baglanti import vt_baglan
from server.yetki_baglama import Hepsi, yetkiyle_bagla


def rol_olustur(rol: RolModeli, kullanici_id: int | None = None):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
 
        gorunen_ad = rol.rol_adi.strip()
        if not gorunen_ad:
            raise HTTPException(status_code=422, detail="Rol adı boş olamaz.")
 
        # Teknik ad: büyük harfe çevrilir. Yazılan ad olduğu gibi görünen ad olarak da saklanır.
        rol_adi_upper = gorunen_ad.upper()
 
        cursor.execute("SELECT 1 FROM roller WHERE rol_adi = %s;", (rol_adi_upper,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Bu rol zaten sistemde mevcut.")
 
        cursor.execute(
            "INSERT INTO roller (rol_adi, gorunen_ad) VALUES (%s, %s) RETURNING rol_id;",
            (rol_adi_upper, gorunen_ad),
        )
        yeni_id = cursor.fetchone()[0]
 
        denetim_kaydi_olustur(
            VT_AYARLARI,
            olay_turu="CREATE",
            kullanici_id=kullanici_id,
            hedef_tablo="roller",
            hedef_kayit_id=yeni_id,
            mevcut_cursor=cursor,
            ayrinti={"yeni": {"rol_adi": rol_adi_upper, "gorunen_ad": gorunen_ad}},
        )
        conn.commit()
        return {
            "durum": "basarili",
            "mesaj": "Rol başarıyla oluşturuldu.",
            "rol_id": yeni_id,
            "rol_adi": rol_adi_upper,
            "gorunen_ad": gorunen_ad,
        }
    except HTTPException:
        if conn:
            conn.rollback()
        raise
    except Exception:
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail="Rol oluşturulurken bir hata oluştu.")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


# Giriş ekranı ve sunucu kontrolleri bu rollerin teknik adlarına bağlıdır.
# (Modül düzeyinde tanımlanmalıdır; bir fonksiyonun içine yazılmaz.)
SISTEM_ROLLERI = {"ADMIN", "PSIKOLOG", "MEMUR", "MUDUR", "DANISMA_OGRENCISI", "PROJE_ASISTANI"}


def rol_guncelle(rol_id: int, veri: RolGorunenAdModeli, kullanici_id: int | None = None):
    """Rolün görünür adını ve aktiflik durumunu günceller."""
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
 
        # 1. Rolün teknik adını (rol_adi) çekip satırı kilitliyoruz
        cursor.execute("SELECT rol_adi, aktif_mi, gorunen_ad FROM roller WHERE rol_id = %s FOR UPDATE;", (rol_id,))
        kayit = cursor.fetchone()
        
        if kayit is None:
            raise HTTPException(status_code=404, detail="Güncellenecek rol bulunamadı.")
 
        # 2. GÜVENLİK KİLİDİ: Admin rolü asla değiştirilemez veya pasife alınamaz!
        if kayit[0] == "ADMIN":
            raise HTTPException(status_code=403, detail="SİSTEM UYARISI: ADMIN rolü düzenlenemez ve pasife alınamaz.")

        # 3. Pasif rol = o roldeki kullanıcılar sisteme giremez (giriş ve her istek rol aktifliğini denetler). Kişi kendi rolünü
        #    pasife alıp kendini dışarıda bırakamaz.
        etkilenen = 0
        onceki_aktif = kayit[1] if len(kayit) > 1 else True
        if veri.aktif_mi is False and onceki_aktif is not False:
            cursor.execute("SELECT rol_id FROM kullanicilar WHERE kullanici_id = %s;", (kullanici_id,))
            yapan = cursor.fetchone()
            if yapan is not None and yapan[0] == rol_id:
                raise HTTPException(status_code=409, detail="Kendi rolünüzü pasife alamazsınız; oturumunuz kapanırdı.")
            cursor.execute("SELECT COUNT(*) FROM kullanicilar WHERE rol_id = %s AND aktif_mi = TRUE;", (rol_id,))
            etkilenen = cursor.fetchone()[0]
 
        # 4. Güncelleme işlemi
        cursor.execute(
            "UPDATE roller SET gorunen_ad = %s, aktif_mi = %s WHERE rol_id = %s;",
            (veri.gorunen_ad.strip(), veri.aktif_mi, rol_id),
        )

        denetim_kaydi_olustur(
            VT_AYARLARI,
            olay_turu="UPDATE",
            kullanici_id=kullanici_id,
            hedef_tablo="roller",
            hedef_kayit_id=rol_id,
            mevcut_cursor=cursor,
            ayrinti={
                "onceki": {"gorunen_ad": kayit[2] if len(kayit) > 2 else None, "aktif_mi": onceki_aktif},
                "yeni": {"gorunen_ad": veri.gorunen_ad.strip(), "aktif_mi": veri.aktif_mi},
                "girisi_engellenen_kullanici": etkilenen,
            },
        )
        conn.commit()
        yanit = {"durum": "basarili", "mesaj": "Rol güncellendi."}
        if etkilenen:
            yanit["etkilenen_kullanici"] = etkilenen
            yanit["mesaj"] = f"Rol pasife alındı; bu roldeki {etkilenen} aktif kullanıcının sisteme girişi engellendi."
        return yanit
    except HTTPException:
        if conn is not None:
            conn.rollback()
        raise
    except Exception:
        if conn is not None:
            conn.rollback()
        raise HTTPException(status_code=500, detail="Rol güncellenirken bir hata oluştu.")
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


def rol_sil(rol_id: int, kullanici_id: int | None = None):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
 
        cursor.execute("SELECT rol_adi FROM roller WHERE rol_id = %s FOR UPDATE;", (rol_id,))
        rol = cursor.fetchone()
        if rol is None:
            raise HTTPException(status_code=404, detail="Silinecek rol bulunamadı.")
 
        if rol[0] in SISTEM_ROLLERI:
            raise HTTPException(status_code=403, detail="Sistem rolleri silinemez.")
 
        cursor.execute("SELECT COUNT(*) FROM kullanicilar WHERE rol_id = %s;", (rol_id,))
        kullanici_sayisi = cursor.fetchone()[0]
        if kullanici_sayisi > 0:
            raise HTTPException(
                status_code=409,
                detail=f"Bu role atanmış {kullanici_sayisi} kullanıcı var. Önce kullanıcıların rolünü değiştirin.",
            )
 
        # Yalnızca gerçekten verilmiş izinler sayılır (izin_var = 1).
        cursor.execute("SELECT COUNT(*) FROM rol_izinleri WHERE rol_id = %s AND izin_var = 1;", (rol_id,))
        izin_sayisi = cursor.fetchone()[0]
        if izin_sayisi > 0:
            raise HTTPException(
                status_code=409,
                detail=f"Bu role ait {izin_sayisi} izin var. Silmek için önce izinleri kaldırın.",
            )
 
        cursor.execute("DELETE FROM rol_izinleri WHERE rol_id = %s;", (rol_id,))
        silinen = satiri_sil_ve_ayrintisini_al(cursor, "roller", rol_id)
        denetim_kaydi_olustur(
            VT_AYARLARI,
            olay_turu="DELETE",
            kullanici_id=kullanici_id,
            hedef_tablo="roller",
            hedef_kayit_id=rol_id,
            mevcut_cursor=cursor,
            ayrinti=silinen,
        )
        conn.commit()
        return {"durum": "basarili", "mesaj": f"'{rol[0]}' rolü silindi."}
    except HTTPException:
        if conn is not None:
            conn.rollback()
        raise
    except Exception:
        if conn is not None:
            conn.rollback()
        raise HTTPException(status_code=500, detail="Rol silinirken bir hata oluştu.")
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


def _atanabilir_rolleri_getir():
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT rol_id, rol_adi, gorunen_ad
            FROM roller
            WHERE aktif_mi = TRUE
              AND UPPER(rol_adi) <> 'ADMIN'
            ORDER BY rol_id;
        """)
        return [
            {
                "rol_id": kayit[0],
                "rol_adi": kayit[1],
                "gorunen_ad": kayit[2] or kayit[1],
            }
            for kayit in cursor.fetchall()
        ]
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Atanabilir roller alınamadı."
        )
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


def olusturma_rolleri(
    kullanici_id: int | None = None
):
    return _atanabilir_rolleri_getir()


def degistirme_rolleri(
    kullanici_id: int | None = None
):
    return _atanabilir_rolleri_getir()


def rolleri_listele(kullanici_id: int | None = None):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT r.rol_id, r.rol_adi, r.gorunen_ad, r.aktif_mi, "
            "(SELECT COUNT(*) FROM kullanicilar k WHERE k.rol_id = r.rol_id AND k.aktif_mi = TRUE) "
            "FROM roller r ORDER BY r.rol_id ASC;"
        )
        return [
            {"rol_id": k[0], "rol_adi": k[1], "gorunen_ad": k[2], "aktif_mi": k[3], "aktif_kullanici_sayisi": k[4] if len(k) > 4 else 0}
            for k in cursor.fetchall()
        ]
    except Exception:
        raise HTTPException(status_code=500, detail="Roller alınamadı.")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def rol_yetki_ozeti(rol_id: int, kullanici_id: int | None = None):
    """Bir rolün yapabildiği işlemlerin özeti (kullanıcı oluştururken 'bu rol neler yapabilir?').

    Yalnızca o role AÇIK izinler döner. Kullanıcı oluşturabilen herkes görebilsin diye
    rol yönetim izni (ROL_IZIN_YONET) değil KULLANICI_OLUSTUR istenir.
    """
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("SELECT rol_id, rol_adi, gorunen_ad FROM roller WHERE rol_id = %s;", (rol_id,))
        rol = cursor.fetchone()
        if rol is None:
            raise HTTPException(status_code=404, detail="Rol bulunamadı.")
        cursor.execute(
            """
            SELECT i.izin_adi, i.gorunen_ad
            FROM rol_izinleri ri
            JOIN izinler i ON i.izin_id = ri.izin_id
            WHERE ri.rol_id = %s AND ri.izin_var = 1
            ORDER BY i.izin_id ASC;
            """,
            (rol_id,),
        )
        return {
            "rol_id": rol[0],
            "rol_adi": rol[1],
            "gorunen_ad": rol[2],
            "izinler": [{"izin_adi": k[0], "gorunen_ad": k[1] or k[0]} for k in cursor.fetchall()],
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Rol yetkileri alınamadı.")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def rol_izin_matrisi_getir(kullanici_id: int | None = None):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        
        # 1. Tüm Rolleri Çek
        cursor.execute("SELECT rol_id, rol_adi, gorunen_ad, aktif_mi FROM roller ORDER BY rol_id ASC")
        roller = [{"rol_id": r[0], "rol_adi": r[1], "gorunen_ad": r[2], "aktif_mi": r[3]} for r in cursor.fetchall()]
        
        # 2. Tüm İzinleri (Faaliyetleri/Yetkileri) Çek
        cursor.execute("SELECT izin_id, izin_adi, gorunen_ad FROM izinler ORDER BY izin_id ASC")
        izinler = [{"izin_id": i[0], "izin_adi": i[1], "gorunen_ad": i[2]} for i in cursor.fetchall()]
        
        # 3. Rol-İzin Eşleşmelerini Çek
        cursor.execute("SELECT rol_id, izin_id FROM rol_izinleri WHERE izin_var = 1")
        eslesmeler = cursor.fetchall()
        
        # Hangi rolün hangi izinleri olduğunu bir sözlükte topla (rol_id: [izin_id1, izin_id2...])
        rol_izin_map = {}
        for r_id, i_id in eslesmeler:
            if r_id not in rol_izin_map:
                rol_izin_map[r_id] = []
            rol_izin_map[r_id].append(i_id)
            
        return {
            "roller": roller,
            "izinler": izinler,
            "rol_izin_map": rol_izin_map
        }
        
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Rol ve izin bilgileri alınamadı."
        )
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# --- 1. YENİ İZİN EKLEME (POST) ---
def izin_ekle(izin_verisi: dict, kullanici_id: int | None = None):
    izin_adi = izin_verisi.get("izin_adi")
    if not isinstance(izin_adi, str) or not izin_adi.strip() or len(izin_adi) > 100:
        raise HTTPException(status_code=422, detail="İzin adı zorunludur ve en fazla 100 karakter olabilir.")
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO izinler (izin_adi) VALUES (%s) RETURNING izin_id",
            (izin_adi,)
        )
        yeni_id = cursor.fetchone()[0]
        # Yeni izin "kimsede yok" durumunda kalmasın: ADMIN otomatik sahip olur, diğer roller kapalı başlar.
        cursor.execute(
            """
            INSERT INTO rol_izinleri (rol_id, izin_id, izin_var)
            SELECT r.rol_id, %s, CASE WHEN UPPER(r.rol_adi) = 'ADMIN' THEN 1 ELSE 0 END
            FROM roller r
            ON CONFLICT (rol_id, izin_id) DO NOTHING;
            """,
            (yeni_id,),
        )
        ayrintili_kayit_yaz(cursor, kullanici_id, "CREATE", "izinler", yeni_id, yeni={"izin_adi": izin_adi, "verilen_roller": ["ADMIN"]})
        conn.commit()
        return {"mesaj": "İzin başarıyla eklendi", "izin_id": yeni_id}
    except psycopg2.errors.UniqueViolation:
        if conn:
            conn.rollback()
        raise HTTPException(status_code=409, detail="Bu izin adı zaten tanımlı.")
    except Exception:
        if conn:
            conn.rollback()
        raise HTTPException(
            status_code=500,
            detail="İzin eklenirken beklenmeyen bir hata oluştu."
        )
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


def izin_duzenle(izin_id: int, veri: IzinDuzenleModeli, kullanici_id: int | None = None):
    """Bir iznin GÖRÜNEN ADINI ve hangi rollere verildiğini günceller.
 
    Teknik ad (izin_adi) değiştirilmez: izin_kontrol("...") bu adla çalışır.
    """
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
 
        cursor.execute("SELECT izin_id, izin_adi, gorunen_ad FROM izinler WHERE izin_id = %s FOR UPDATE;", (izin_id,))
        izin_kaydi = cursor.fetchone()
        if izin_kaydi is None:
            raise HTTPException(status_code=404, detail="İzin bulunamadı.")
 
        cursor.execute("SELECT rol_id, rol_adi FROM roller;")
        roller = {r[0]: r[1] for r in cursor.fetchall()}
        cursor.execute("SELECT rol_id FROM rol_izinleri WHERE izin_id = %s AND izin_var = 1;", (izin_id,))
        onceki_roller = {r[0] for r in cursor.fetchall()}
 
        secilenler = set(veri.verilen_rol_idleri)
        if not secilenler.issubset(roller.keys()):
            raise HTTPException(status_code=422, detail="Geçersiz rol seçildi.")
 
        # ADMIN rolünden izin kaldırılamaz (sistemden kilitlenmeyi önler).
        admin_idleri = [rid for rid, ad in roller.items() if ad == "ADMIN"]
        if any(rid not in secilenler for rid in admin_idleri):
            raise HTTPException(status_code=422, detail="ADMIN rolünden izin kaldırılamaz.")
 
        cursor.execute(
            "UPDATE izinler SET gorunen_ad = %s WHERE izin_id = %s;",
            (veri.gorunen_ad.strip(), izin_id),
        )
 
        for rid in roller:
            deger = 1 if rid in secilenler else 0
            cursor.execute(
                "UPDATE rol_izinleri SET izin_var = %s WHERE rol_id = %s AND izin_id = %s;",
                (deger, rid, izin_id),
            )
            if cursor.rowcount == 0:
                cursor.execute(
                    "INSERT INTO rol_izinleri (rol_id, izin_id, izin_var) VALUES (%s, %s, %s);",
                    (rid, izin_id, deger),
                )
 
        # Kim, hangi izni, hangi rollere verdi/aldı: önceki ve yeni değer (rol adlarıyla) denetim kaydına yazılır.
        adlar = lambda kimlikler: sorted(roller[r] for r in kimlikler)
        denetim_kaydi_olustur(
            VT_AYARLARI,
            olay_turu="UPDATE",
            kullanici_id=kullanici_id,
            hedef_tablo="izinler",
            hedef_kayit_id=izin_id,
            mevcut_cursor=cursor,
            ayrinti={
                "izin": izin_kaydi[1] if len(izin_kaydi) > 1 else None,
                "onceki": {"gorunen_ad": izin_kaydi[2] if len(izin_kaydi) > 2 else None, "verilen_roller": adlar(onceki_roller & set(roller))},
                "yeni": {"gorunen_ad": veri.gorunen_ad.strip(), "verilen_roller": adlar(secilenler)},
                "eklenen_roller": adlar(secilenler - onceki_roller),
                "kaldirilan_roller": adlar((onceki_roller & set(roller)) - secilenler),
            },
        )
        conn.commit()
        return {"durum": "basarili", "mesaj": "İzin güncellendi."}
    except HTTPException:
        if conn is not None:
            conn.rollback()
        raise
    except Exception:
        if conn is not None:
            conn.rollback()
        raise HTTPException(status_code=500, detail="İzin güncellenirken bir hata oluştu.")
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


# (yöntem, yol, uç fonksiyonu, yetki parametresi, gereken yetki, ek yol ayarları): yetki bağımlılığı kayıt sırasında eklenir.
# Gereken yetki: "IZIN" (izin_kontrol), ("A", "B") (izin_kontrol_biri: biri yeter), Hepsi("A", "B") (izin_kontrol_tumu: hepsi gerekir)
# veya None (yalnızca oturum açmış olmak).
UCLAR = [
    ("POST", "/api/roller", rol_olustur, "kullanici_id", "ROL_OLUSTUR", {"status_code": 201}),
    ("PUT", "/api/roller/{rol_id}", rol_guncelle, "kullanici_id", "ROL_DUZENLE", {}),
    ("DELETE", "/api/roller/{rol_id}", rol_sil, "kullanici_id", "ROL_DUZENLE", {}),
    ("GET", "/api/roller/atanabilir/olusturma", olusturma_rolleri, "kullanici_id", "KULLANICI_OLUSTUR", {}),
    ("GET", "/api/roller/atanabilir/degistirme", degistirme_rolleri, "kullanici_id", "ROL_ATAMA_DEGISTIRME", {}),
    ("GET", "/api/roller", rolleri_listele, "kullanici_id", "ROL_IZIN_YONET", {}),
    ("GET", "/api/roller/{rol_id}/yetki-ozeti", rol_yetki_ozeti, "kullanici_id", "KULLANICI_OLUSTUR", {}),
    ("GET", "/api/rol-izin-matrisi", rol_izin_matrisi_getir, "kullanici_id", "ROL_IZIN_YONET", {}),
    ("POST", "/api/izinler", izin_ekle, "kullanici_id", "ROL_DUZENLE", {"status_code": 201}),
    ("PUT", "/api/izinler/{izin_id}", izin_duzenle, "kullanici_id", "IZIN_DUZENLE", {}),
]


def router_olustur(izin_kontrol) -> APIRouter:
    """Yetki bağımlılığı üreticileri `server.sunucu` içindeki kimlik doğrulama bağımlılıklarıdır."""
    router = APIRouter()
    for metod, yol, fonksiyon, parametre, yetki, ek in UCLAR:
        if isinstance(yetki, str):
            bagimlilik = izin_kontrol(yetki)
        else:
            raise ValueError(f"{yol}: desteklenmeyen yetki tanımı")
        router.add_api_route(yol, yetkiyle_bagla(fonksiyon, parametre, bagimlilik), methods=[metod], **ek)
    return router
