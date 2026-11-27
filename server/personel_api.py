"""Personel uçları: oluşturma, listeleme, detay, güncelleme ve personeli olmayan kullanıcılar. `server/sunucu.py` içinden ayrıldı."""
from fastapi import APIRouter, HTTPException
import psycopg2

from server.denetim import ayrintili_kayit_yaz, durum_degisikligi_yaz
from server.modeller import PersonelGuncelleModeli, PersonelOlusturModeli
from server.personel_kaydi import personel_kaydi_ata
from server.rol_hiyerarsisi import HIYERARSI_MESAJI, hiyerarsi_ihlali_var_mi
from server.vt_ayarlari import VT_AYARLARI
from server.vt_baglanti import vt_baglan
from server.yetki_baglama import Hepsi, yetkiyle_bagla


def personel_olustur(yeni_personel: PersonelOlusturModeli, islem_yapan_id: int | None = None):
    conn = None
    cursor = None
    asama = "personel"
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        # Hedef kullanıcının durumu/rolü ve işlemi yapanın rolü tek sorguda alınır (rol hiyerarşisi denetimi için).
        cursor.execute(
            "SELECT k.aktif_mi, r.rol_adi, "
            "(SELECT ry.rol_adi FROM kullanicilar ky JOIN roller ry ON ry.rol_id = ky.rol_id WHERE ky.kullanici_id = %s) "
            "FROM kullanicilar k JOIN roller r ON k.rol_id = r.rol_id WHERE k.kullanici_id = %s;",
            (islem_yapan_id, yeni_personel.kullanici_id),
        )
        kullanici = cursor.fetchone()
        if kullanici is None:
            raise HTTPException(status_code=404, detail="Kullanıcı hesabı bulunamadı.")
        # Kullanıcı yönetimindeki kural personel kaydında da geçerli: kendi seviyesindeki ya da üstündeki rolün kaydına dokunulamaz.
        if hiyerarsi_ihlali_var_mi(kullanici[2], kullanici[1]):
            raise HTTPException(status_code=403, detail=HIYERARSI_MESAJI)
        if not kullanici[0]:
            raise HTTPException(status_code=422, detail="Pasif kullanıcı için personel kaydı oluşturulamaz.")

        # Danışma öğrencisi için aynı işlemde öğrenci kaydı da oluşturulur (Danışma Masası
        # ve faaliyet listeleri bu kaydı kullanır). Diğer roller için öğrenci bilgisi kabul edilmez.
        danisma_ogrencisi = kullanici[1] == "DANISMA_OGRENCISI"
        ogrenci_bilgisi_var = any([yeni_personel.ad_soyad, yeni_personel.ogrenci_numarasi, yeni_personel.telefon])
        if danisma_ogrencisi:
            if not yeni_personel.ad_soyad or not yeni_personel.ogrenci_numarasi:
                raise HTTPException(status_code=422, detail="Danışma öğrencisi için ad soyad ve öğrenci numarası zorunludur.")
        elif ogrenci_bilgisi_var:
            raise HTTPException(status_code=422, detail="Öğrenci bilgileri yalnızca danışma öğrencisi rolü için girilebilir.")

        personel_id = personel_kaydi_ata(cursor, yeni_personel.kullanici_id, yeni_personel.personel_kodu.strip())
        if personel_id is None:
            raise psycopg2.errors.UniqueViolation("Kullanıcının personel kaydı zaten mevcut.")

        ayrintili_kayit_yaz(cursor, islem_yapan_id, "UPDATE", "kullanicilar", yeni_personel.kullanici_id, neden="personel kaydı verildi", personel_kodu=yeni_personel.personel_kodu.strip())

        ogrenci_id = None
        if danisma_ogrencisi:
            cursor.execute("SELECT ogrenci_id FROM ogrenciler WHERE kullanici_id = %s;", (yeni_personel.kullanici_id,))
            mevcut_ogrenci = cursor.fetchone()
            if mevcut_ogrenci is not None:
                ogrenci_id = mevcut_ogrenci[0]
            else:
                asama = "ogrenci"
                cursor.execute(
                    "INSERT INTO ogrenciler (kullanici_id, ad_soyad, ogrenci_numarasi, telefon, tur) VALUES (%s, %s, %s, %s, 'DANISMA_MASASI') RETURNING ogrenci_id;",
                    (yeni_personel.kullanici_id, yeni_personel.ad_soyad, yeni_personel.ogrenci_numarasi, yeni_personel.telefon)
                )
                ogrenci_id = cursor.fetchone()[0]
                cursor.execute("INSERT INTO denetim_kayitlari (kullanici_id, olay_turu, hedef_tablo, hedef_kayit_id) VALUES (%s, %s, %s, %s);", (islem_yapan_id, "CREATE", "ogrenciler", ogrenci_id))
        conn.commit()

        return {
            "mesaj": "Personel başarıyla oluşturuldu.",
            "personel_id": personel_id,
            "kullanici_id": yeni_personel.kullanici_id,
            "personel_kodu": yeni_personel.personel_kodu.strip(),
            "aktif_mi": True,
            "ogrenci_id": ogrenci_id
        }
    except psycopg2.errors.UniqueViolation:
        if conn is not None: conn.rollback()
        if asama == "ogrenci":
            raise HTTPException(status_code=409, detail="Bu öğrenci numarası başka bir öğrenci kaydında kullanılıyor.")
        raise HTTPException(status_code=409, detail="Bu kullanıcıya ait personel kaydı veya personel kodu zaten mevcut.")
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


def personel_listele(islem_yapan_id: int | None = None):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.personel_id, p.kullanici_id, k.kullanici_adi, p.personel_kodu, r.rol_adi, p.aktif_mi, p.olusturulma_tarihi, r.gorunen_ad
            FROM personel p JOIN kullanicilar k ON p.kullanici_id = k.kullanici_id JOIN roller r ON k.rol_id = r.rol_id ORDER BY p.personel_id;
        """)
        kayitlar = cursor.fetchall()
        return [{"personel_id": k[0], "kullanici_id": k[1], "kullanici_adi": k[2], "personel_kodu": k[3], "rol_adi": k[4], "aktif_mi": k[5], "olusturulma_tarihi": k[6], "gorunen_ad": (k[7] if len(k) > 7 and k[7] else k[4])} for k in kayitlar]
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


def personel_olmayan_kullanicilari_listele(islem_yapan_id: int | None = None):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        # Sadece henüz personel tablosunda kaydı OLMAYAN aktif kullanıcıları getirir
        cursor.execute("""
            SELECT k.kullanici_id, k.kullanici_adi, r.rol_adi 
            FROM kullanicilar k 
            JOIN roller r ON k.rol_id = r.rol_id 
            LEFT JOIN personel p ON k.kullanici_id = p.kullanici_id
            WHERE p.personel_id IS NULL AND k.aktif_mi = TRUE
            ORDER BY k.kullanici_adi;
        """)
        kayitlar = cursor.fetchall()
        return [{"kullanici_id": k[0], "kullanici_adi": k[1], "rol_adi": k[2]} for k in kayitlar]
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


def personel_detay(personel_id: int, islem_yapan_id: int | None = None):
    if personel_id <= 0:
        raise HTTPException(
            status_code=422,
            detail="Geçerli bir personel ID girilmelidir."
        )

    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.personel_id, p.kullanici_id, k.kullanici_adi, p.personel_kodu, r.rol_adi, p.aktif_mi, p.olusturulma_tarihi
            FROM personel p JOIN kullanicilar k ON p.kullanici_id = k.kullanici_id JOIN roller r ON k.rol_id = r.rol_id WHERE p.personel_id = %s;
        """, (personel_id,))
        kayit = cursor.fetchone()
        if kayit is None:
            raise HTTPException(status_code=404, detail="Personel bulunamadı.")
        return {"personel_id": kayit[0], "kullanici_id": kayit[1], "kullanici_adi": kayit[2], "personel_kodu": kayit[3], "rol_adi": kayit[4], "aktif_mi": kayit[5], "olusturulma_tarihi": kayit[6]}
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


def personel_guncelle(personel_id: int, guncelleme: PersonelGuncelleModeli, islem_yapan_id: int | None = None):
    degisiklikler = guncelleme.model_dump(exclude_unset=True)
    if not degisiklikler or any(deger is None for deger in degisiklikler.values()):
        raise HTTPException(status_code=422, detail="En az bir geçerli güncelleme alanı gönderilmelidir.")
    if "personel_kodu" in degisiklikler:
        degisiklikler["personel_kodu"] = degisiklikler["personel_kodu"].strip()

    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT k.personel_id, k.personel_kodu, k.aktif_mi, k.kullanici_id, r.rol_adi, "
            "(SELECT ry.rol_adi FROM kullanicilar ky JOIN roller ry ON ry.rol_id = ky.rol_id WHERE ky.kullanici_id = %s) "
            "FROM kullanicilar k JOIN roller r ON r.rol_id = k.rol_id WHERE k.personel_id = %s FOR UPDATE OF k;",
            (islem_yapan_id, personel_id),
        )
        mevcut = cursor.fetchone()
        if mevcut is None:
            raise HTTPException(status_code=404, detail="Personel bulunamadı.")
        # Örn. müdür, ADMIN'in ya da başka bir müdürün personel kodunu değiştiremez (ADMIN için hiyerarşi engel olmaz).
        if hiyerarsi_ihlali_var_mi(mevcut[5], mevcut[4]):
            raise HTTPException(status_code=403, detail=HIYERARSI_MESAJI)

        # Yalnızca personel kodu değişir; aktiflik kullanıcı durum ucundan yönetilir (kurallar atlanmasın).
        yeni_kod = degisiklikler.get("personel_kodu", mevcut[1])

        cursor.execute("UPDATE kullanicilar SET personel_kodu = %s WHERE personel_id = %s;", (yeni_kod, personel_id))
        durum_degisikligi_yaz(cursor, islem_yapan_id, "UPDATE", "kullanicilar", mevcut[3], onceki={"personel_kodu": mevcut[1]}, yeni={"personel_kodu": yeni_kod})
        conn.commit()
        return {"mesaj": "Personel başarıyla güncellendi.", "personel_id": personel_id, "personel_kodu": yeni_kod, "aktif_mi": mevcut[2]}
    except psycopg2.errors.UniqueViolation:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=409, detail="Bu personel kodu başka bir kayıtta kullanılıyor.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


# (yöntem, yol, uç fonksiyonu, yetki parametresi, gereken yetki, ek yol ayarları): yetki bağımlılığı kayıt sırasında eklenir.
# Gereken yetki: "IZIN" (izin_kontrol), ("A", "B") (izin_kontrol_biri: biri yeter), Hepsi("A", "B") (izin_kontrol_tumu: hepsi gerekir)
# veya None (yalnızca oturum açmış olmak).
UCLAR = [
    ("POST", "/api/personel", personel_olustur, "islem_yapan_id", "PERSONEL_TANIMLA", {"status_code": 201}),
    ("GET", "/api/personel", personel_listele, "islem_yapan_id", "PERSONEL_TANIMLA", {}),
    ("GET", "/api/kullanicilar/personel-olmayanlar", personel_olmayan_kullanicilari_listele, "islem_yapan_id", "PERSONEL_TANIMLA", {}),
    ("GET", "/api/personel/{personel_id}", personel_detay, "islem_yapan_id", "PERSONEL_TANIMLA", {}),
    ("PATCH", "/api/personel/{personel_id}", personel_guncelle, "islem_yapan_id", "PERSONEL_TANIMLA", {}),
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
