"""Öğrenci yönetimi uçları: listeleme, puan detayı, ekleme, aktiflik, saklama süresi ve silme. `server/sunucu.py` içinden ayrıldı."""
from fastapi import APIRouter, HTTPException
import psycopg2
import psycopg2.errors

from server.denetim import denetim_kaydi_olustur, satiri_sil_ve_ayrintisini_al
from server.modeller import OgrenciEkleModeli
from server.ortak_sabitler import OGRENCI_TUR_ETIKETLERI
from server.vt_ayarlari import VT_AYARLARI
from server.vt_baglanti import vt_baglan
from server.yetki_baglama import yetkiyle_bagla


# --- Faaliyet formundaki öğrenci listesi ---
def ogrencileri_getir(kullanici_id: int | None = None):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        # Ad Soyad, Öğrenci Numarası ve türü çek. Tüm öğrenciler listelenir;
        # her öğrencinin yanında türü (gönüllü, danışma masası, asistan) belirtilir.
        cursor.execute(
            "SELECT ogrenci_id, ad_soyad, ogrenci_numarasi, tur::text FROM ogrenciler WHERE aktif_mi = true "
            "ORDER BY ad_soyad, ogrenci_numarasi;"
        )

        liste = []
        for r in cursor.fetchall():
            metin = f"{r[1]} - [{r[2]}]"
            etiket = OGRENCI_TUR_ETIKETLERI.get(r[3])
            if etiket:
                metin += f" ({etiket})"
            liste.append({"id": r[0], "metin": metin, "tur": r[3]})
        return liste
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


from pydantic import BaseModel, ConfigDict, StrictBool


class OgrenciAktiflikModeli(BaseModel):
    model_config = ConfigDict(extra="forbid")
    aktif_mi: StrictBool


from datetime import date as _ogr_date


from pydantic import BaseModel as _OgrBaseModel


from pydantic import ConfigDict as _OgrConfigDict


from pydantic import StrictBool as _OgrStrictBool


from psycopg2 import sql as _ogr_sql


class OgrenciErteleModeli(_OgrBaseModel):
    model_config = _OgrConfigDict(extra="forbid")
    yeni_uyari_tarihi: _ogr_date


class OgrenciSilOnayModeli(_OgrBaseModel):
    model_config = _OgrConfigDict(extra="forbid")
    onayla: _OgrStrictBool


def ogrenciler_yonetim_listesi(
    yetkili_id: int | None = None
):
    conn = vt_baglan(VT_AYARLARI)

    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT
                    o.ogrenci_id,
                    o.ad_soyad,
                    o.ogrenci_numarasi,
                    o.tur::text,
                    o.aktif_mi,
                    o.kullanici_id,
                    k.kullanici_adi,
                    r.rol_adi,
                    o.telefon,
                    o.olusturulma_tarihi,

                    (
                        o.tur::text = 'GONULLU'
                        AND NOT o.aktif_mi
                        AND o.pasife_alinma_tarihi::date
                            <= (
                                CURRENT_DATE
                                - INTERVAL '2 years'
                            )::date
                    ) AS kayit_suresi_doldu,

                    e.yeni_uyari_tarihi,

                    (
                        e.yeni_uyari_tarihi > CURRENT_DATE
                    ) AS ertelendi_mi,

                    o.pasife_alinma_tarihi

                FROM ogrenciler o

                LEFT JOIN kullanicilar k
                    ON k.kullanici_id = o.kullanici_id

                LEFT JOIN roller r
                    ON r.rol_id = k.rol_id

                LEFT JOIN LATERAL (
                    SELECT yeni_uyari_tarihi
                    FROM ogrenci_kayit_erteleme_gecmisi e
                    WHERE e.ogrenci_id = o.ogrenci_id
                    ORDER BY e.erteleme_id DESC
                    LIMIT 1
                ) e ON TRUE

                ORDER BY o.ogrenci_id DESC;
            """)

            sonuc = []

            for v in cursor.fetchall():
                sonuc.append({
                    "ogrenci_id": v[0],
                    "ad_soyad": v[1],
                    "ogrenci_numarasi": v[2],
                    "tur": v[3],
                    "tur_etiketi":
                        OGRENCI_TUR_ETIKETLERI.get(
                            v[3], v[3]
                        ),
                    "aktif_mi": v[4],
                    "kullanici_id": v[5],
                    "kullanici_adi": v[6],
                    "rol_adi": v[7],
                    "telefon": v[8],
                    "olusturulma_tarihi":
                        v[9].isoformat() if v[9] else None,
                    "kayit_suresi_doldu": bool(v[10]),
                    "ertelemeye_kadar":
                        v[11].isoformat() if v[11] else None,
                    "ertelendi_mi": bool(v[12]),
                    "pasife_alinma_tarihi":
                        v[13].isoformat() if v[13] else None,
                })

            return sonuc

    finally:
        conn.close()


def ogrenci_puan_detayi(
    ogrenci_id: int,
    baslangic: _ogr_date,
    bitis: _ogr_date,
    yetkili_id: int | None = None
):
    if baslangic > bitis:
        raise HTTPException(
            status_code=422,
            detail="Başlangıç tarihi bitişten büyük olamaz."
        )

    conn = vt_baglan(VT_AYARLARI)

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM ogrenciler WHERE ogrenci_id=%s",
                (ogrenci_id,)
            )

            if cursor.fetchone() is None:
                raise HTTPException(
                    status_code=404,
                    detail="Öğrenci bulunamadı."
                )

            cursor.execute("""
                SELECT
                    t.faaliyet_tarihi,
                    f.faaliyet_adi,
                    t.adet,
                    COALESCE(b.birim_adi, ''),
                    t.kayit_puani,
                    (t.adet * t.kayit_puani)

                FROM ogrenci_faaliyet_takip t

                JOIN faaliyetler f
                    ON f.faaliyet_id = t.faaliyet_id

                LEFT JOIN faaliyet_birimleri b
                    ON b.birim_id = t.birim_id

                WHERE t.ogrenci_id = %s
                  AND t.faaliyet_tarihi BETWEEN %s AND %s

                ORDER BY
                    t.faaliyet_tarihi DESC,
                    t.takip_id DESC;
            """, (ogrenci_id, baslangic, bitis))

            faaliyetler = []

            for tarih, ad, adet, birim, puan, toplam in (
                cursor.fetchall()
            ):
                faaliyetler.append({
                    "tarih": tarih.isoformat(),
                    "faaliyet": ad,
                    "adet": adet,
                    "birim": birim,
                    "birim_puan": float(puan),
                    "toplam_puan": float(toplam),
                })

            return {
                "ogrenci_id": ogrenci_id,
                "baslangic": baslangic.isoformat(),
                "bitis": bitis.isoformat(),
                "toplam_puan": sum(
                    f["toplam_puan"] for f in faaliyetler
                ),
                "faaliyetler": faaliyetler,
            }

    finally:
        conn.close()


def _ogrenci_saklama_suresi_kontrol(cursor, ogrenci_id):
    """Gönüllü öğrencinin kaydı, pasife alındıktan 2 yıl geçmişse silinebilir ya da ertelenebilir (aktif öğrencinin süresi işlemez)."""
    cursor.execute("""
        SELECT
            tur::text,
            aktif_mi,
            pasife_alinma_tarihi,
            kullanici_id,
            ogrenci_numarasi
        FROM ogrenciler
        WHERE ogrenci_id = %s
        FOR UPDATE;
    """, (ogrenci_id,))

    ogrenci = cursor.fetchone()

    if ogrenci is None:
        raise HTTPException(
            status_code=404,
            detail="Öğrenci bulunamadı."
        )

    tur, aktif_mi, pasife_alinma, kullanici_id, ogrenci_no = ogrenci

    if tur != "GONULLU":
        raise HTTPException(
            status_code=409,
            detail=(
                "Saklama süresi işlemi yalnızca "
                "Gönüllü Öğrenciler içindir."
            )
        )

    if aktif_mi or pasife_alinma is None:
        raise HTTPException(
            status_code=409,
            detail=(
                "Saklama süresi yalnızca pasife alınmış "
                "öğrenciler için işler. Bu öğrenci aktif."
            )
        )

    cursor.execute("""
        SELECT (
            %s::date <= (
                CURRENT_DATE - INTERVAL '2 years'
            )::date
        );
    """, (pasife_alinma.date(),))

    if not cursor.fetchone()[0]:
        raise HTTPException(
            status_code=409,
            detail=(
                "Bu öğrencinin pasif kalma süresi "
                "(2 yıl) dolmadı."
            )
        )

    return kullanici_id, ogrenci_no


def ogrenci_silme_ertele(
    ogrenci_id: int,
    veri: OgrenciErteleModeli,
    yetkili_id: int | None = None
):
    conn = vt_baglan(VT_AYARLARI)

    try:
        with conn.cursor() as cursor:
            _, ogrenci_no = _ogrenci_saklama_suresi_kontrol(
                cursor, ogrenci_id
            )

            cursor.execute("SELECT CURRENT_DATE")
            bugun = cursor.fetchone()[0]

            if veri.yeni_uyari_tarihi <= bugun:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "Erteleme tarihi bugünden sonra olmalıdır."
                    )
                )

            cursor.execute("""
                INSERT INTO ogrenci_kayit_erteleme_gecmisi
                (
                    ogrenci_id,
                    ogrenci_numarasi,
                    yeni_uyari_tarihi,
                    erteleyen_kullanici_id
                )
                VALUES (%s, %s, %s, %s)
                RETURNING erteleme_id;
            """, (
                ogrenci_id,
                ogrenci_no,
                veri.yeni_uyari_tarihi,
                yetkili_id
            ))

            erteleme_id = cursor.fetchone()[0]

            denetim_kaydi_olustur(
                VT_AYARLARI,
                "CREATE",
                yetkili_id,
                "ogrenci_kayit_erteleme_gecmisi",
                erteleme_id,
                mevcut_cursor=cursor
            )

        conn.commit()

        return {
            "ogrenci_id": ogrenci_id,
            "yeni_uyari_tarihi":
                veri.yeni_uyari_tarihi.isoformat(),
        }

    except HTTPException:
        conn.rollback()
        raise

    except Exception:
        conn.rollback()
        raise HTTPException(
            status_code=500,
            detail="Erteleme kaydedilemedi."
        )

    finally:
        conn.close()


def ogrenci_saklama_suresi_sil(
    ogrenci_id: int,
    veri: OgrenciSilOnayModeli,
    yetkili_id: int | None = None
):
    if not veri.onayla:
        raise HTTPException(
            status_code=422,
            detail="Silme işlemi açık onay gerektirir."
        )

    conn = vt_baglan(VT_AYARLARI)

    try:
        with conn.cursor() as cursor:
            kullanici_id, _ = _ogrenci_saklama_suresi_kontrol(
                cursor, ogrenci_id
            )

            if kullanici_id is not None:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Öğrenciye bağlı kullanıcı hesabı var. "
                        "Bu ekrandan silinemez."
                    )
                )

            cursor.execute("""
                SELECT yeni_uyari_tarihi
                FROM ogrenci_kayit_erteleme_gecmisi
                WHERE ogrenci_id = %s
                ORDER BY erteleme_id DESC
                LIMIT 1;
            """, (ogrenci_id,))

            erteleme = cursor.fetchone()

            cursor.execute("SELECT CURRENT_DATE")
            bugun = cursor.fetchone()[0]

            if erteleme and erteleme[0] > bugun:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Bu kaydın erteleme tarihi "
                        "henüz gelmedi."
                    )
                )

            # Faaliyet kayıtları öğrenciyle birlikte silinecek.
            # Diğer beklenmedik FK ilişkilerinde silme engellenir.
            cursor.execute("""
                SELECT
                    n.nspname,
                    t.relname,
                    a.attname
                FROM pg_constraint c

                JOIN pg_class t
                    ON t.oid = c.conrelid

                JOIN pg_namespace n
                    ON n.oid = t.relnamespace

                JOIN LATERAL
                    unnest(c.conkey) AS k(attnum)
                    ON TRUE

                JOIN pg_attribute a
                    ON a.attrelid = t.oid
                   AND a.attnum = k.attnum

                WHERE c.contype = 'f'
                  AND c.confrelid = 'ogrenciler'::regclass
                  AND t.relname NOT IN (
                      'ogrenci_kayit_erteleme_gecmisi',
                      'ogrenci_faaliyet_takip'
                  );
            """)

            baglantilar = cursor.fetchall()

            for schema, tablo, sutun in baglantilar:
                sorgu = _ogr_sql.SQL(
                    "SELECT 1 FROM {}.{} "
                    "WHERE {} = %s LIMIT 1"
                ).format(
                    _ogr_sql.Identifier(schema),
                    _ogr_sql.Identifier(tablo),
                    _ogr_sql.Identifier(sutun)
                )

                cursor.execute(sorgu, (ogrenci_id,))

                if cursor.fetchone():
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            "Öğrencinin faaliyet dışındaki "
                            "ilişkili kayıtları nedeniyle "
                            "silme işlemi engellendi."
                        )
                    )

            # Yalnızca seçilen öğrencinin faaliyetlerini sil.
            cursor.execute(
                """
                DELETE FROM ogrenci_faaliyet_takip
                WHERE ogrenci_id = %s;
                """,
                (ogrenci_id,)
            )
            silinen_faaliyet_sayisi = cursor.rowcount

            # Erteleme geçmişi öğrenci numarasını taşır (öğrenciye bağlı kimlik bilgisi). Öğrenciyle birlikte imha edilir;
            # kimin ne zaman erteleme yaptığı denetim kayıtlarında (kimliksiz) zaten durur.
            cursor.execute(
                "DELETE FROM ogrenci_kayit_erteleme_gecmisi WHERE ogrenci_id = %s;",
                (ogrenci_id,)
            )
            silinen_erteleme_sayisi = cursor.rowcount

            # Saklama süresi (pasife alındıktan 2 yıl) sonunda yapılan imha: denetim kaydına kişisel veri (ad, telefon...) YAZILMAZ;
            # yalnızca kimliksiz alanlar ve silinen faaliyet sayısı tutulur.
            silinen = satiri_sil_ve_ayrintisini_al(cursor, "ogrenciler", ogrenci_id)
            if silinen is not None:
                silinen["silinen_faaliyet_kaydi_sayisi"] = silinen_faaliyet_sayisi
                silinen["silinen_erteleme_kaydi_sayisi"] = silinen_erteleme_sayisi

            denetim_kaydi_olustur(
                VT_AYARLARI,
                "DELETE",
                yetkili_id,
                "ogrenciler",
                ogrenci_id,
                mevcut_cursor=cursor,
                ayrinti=silinen,
            )

        conn.commit()

        return {
            "durum": "silindi",
            "ogrenci_id": ogrenci_id,
        }

    except HTTPException:
        conn.rollback()
        raise

    except psycopg2.errors.ForeignKeyViolation:
        conn.rollback()
        raise HTTPException(
            status_code=409,
            detail=(
                "Bağlı kayıtlar nedeniyle silinemedi. "
                "İşlem iptal edildi."
            )
        )

    except Exception:
        conn.rollback()
        raise HTTPException(
            status_code=500,
            detail="Öğrenci kaydı silinemedi."
        )

    finally:
        conn.close()


def ogrenci_aktiflik_duzenle(
    ogrenci_id: int,
    veri: OgrenciAktiflikModeli,
    yetkili_id: int | None = None
):
    conn = None

    try:
        conn = vt_baglan(VT_AYARLARI)

        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT kullanici_id FROM ogrenciler "
                "WHERE ogrenci_id = %s;",
                (ogrenci_id,)
            )

            kayit = cursor.fetchone()

            if kayit is None:
                raise HTTPException(
                    status_code=404,
                    detail="Öğrenci bulunamadı."
                )

            kullanici_id = kayit[0]
            rol = None

            if kullanici_id is not None:
                cursor.execute("""
                    SELECT r.rol_adi
                    FROM kullanicilar k
                    JOIN roller r ON r.rol_id = k.rol_id
                    WHERE k.kullanici_id = %s
                    FOR UPDATE OF k;
                """, (kullanici_id,))

                rol_kaydi = cursor.fetchone()

                if rol_kaydi is None:
                    raise HTTPException(
                        status_code=409,
                        detail="Bağlı kullanıcı bulunamadı."
                    )

                rol = rol_kaydi[0]

            cursor.execute("""
                SELECT tur::text, aktif_mi
                FROM ogrenciler
                WHERE ogrenci_id = %s
                FOR UPDATE;
            """, (ogrenci_id,))

            tur, eski_durum = cursor.fetchone()

            if tur == "DANISMA_MASASI" and not veri.aktif_mi:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Danışma Masası Öğrencileri "
                        "bu ekrandan pasife alınamaz."
                    )
                )

            if (
                veri.aktif_mi
                and tur == "DANISMA_MASASI"
                and kullanici_id is not None
                and rol != "DANISMA_OGRENCISI"
            ):
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Bu kullanıcı artık Danışma Öğrencisi "
                        "rolünde değil. Önce rolünü güncelleyin."
                    )
                )

            if not veri.aktif_mi:
                cursor.execute("""
                    SELECT 1
                    FROM danisma_masasi_oturumlari
                    WHERE ogrenci_id = %s
                      AND bitis_zamani IS NULL
                    LIMIT 1;
                """, (ogrenci_id,))

                if cursor.fetchone() is not None:
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            "Öğrencinin açık görevi var. "
                            "Önce görevi bitirin."
                        )
                    )

            hesap_guncellenecek = (
                tur == "DANISMA_MASASI"
                and rol == "DANISMA_OGRENCISI"
                and kullanici_id is not None
            )

            personel_id = None

            if hesap_guncellenecek:
                cursor.execute("""
                    SELECT personel_id
                    FROM personel
                    WHERE kullanici_id = %s
                    FOR UPDATE;
                """, (kullanici_id,))

                personel = cursor.fetchone()

                if personel is None:
                    raise HTTPException(
                        status_code=409,
                        detail="Bağlı personel kaydı bulunamadı."
                    )

                personel_id = personel[0]

            cursor.execute(
                "UPDATE ogrenciler SET aktif_mi = %s "
                "WHERE ogrenci_id = %s;",
                (veri.aktif_mi, ogrenci_id)
            )

            if hesap_guncellenecek:
                cursor.execute(
                    "UPDATE kullanicilar SET aktif_mi = %s "
                    "WHERE kullanici_id = %s;",
                    (veri.aktif_mi, kullanici_id)
                )

            if eski_durum != veri.aktif_mi:
                aktiflik_degisimi = {
                    "onceki": {"aktif_mi": eski_durum},
                    "yeni": {"aktif_mi": veri.aktif_mi},
                }
                denetim_kaydi_olustur(
                    VT_AYARLARI,
                    "UPDATE",
                    yetkili_id,
                    "ogrenciler",
                    ogrenci_id,
                    mevcut_cursor=cursor,
                    ayrinti=aktiflik_degisimi
                )

                if hesap_guncellenecek:
                    denetim_kaydi_olustur(
                        VT_AYARLARI,
                        "UPDATE",
                        yetkili_id,
                        "kullanicilar",
                        kullanici_id,
                        mevcut_cursor=cursor,
                        ayrinti={
                            **aktiflik_degisimi,
                            "neden": "danışma öğrencisinin aktifliği ile birlikte değişti",
                        }
                    )

                    denetim_kaydi_olustur(
                        VT_AYARLARI,
                        "UPDATE",
                        yetkili_id,
                        "personel",
                        personel_id,
                        mevcut_cursor=cursor
                    )

            conn.commit()

        return {
            "ogrenci_id": ogrenci_id,
            "aktif_mi": veri.aktif_mi,
            "hesap_guncellendi": hesap_guncellenecek,
        }

    except HTTPException:
        if conn is not None:
            conn.rollback()
        raise

    except Exception:
        if conn is not None:
            conn.rollback()

        raise HTTPException(
            status_code=500,
            detail="Öğrenci aktifliği güncellenemedi."
        )

    finally:
        if conn is not None:
            conn.close()


def ogrenci_ekle(ogr: OgrenciEkleModeli, yetkili_id: int | None = None):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO ogrenciler
            (ad_soyad, ogrenci_numarasi, telefon, tur, bolum, sinif)
            VALUES (%s, %s, %s, %s, %s, %s) RETURNING ogrenci_id;
        """, (ogr.ad_soyad, ogr.ogrenci_numarasi, ogr.telefon, ogr.tur, ogr.bolum, ogr.sinif))

        yeni_id = cursor.fetchone()[0]

        # Ad, numara ve telefon kişisel veridir (FR-008): denetime yalnızca öğrencinin türü yazılır.
        denetim_kaydi_olustur(
            VT_AYARLARI,
            olay_turu="CREATE",
            kullanici_id=yetkili_id,
            hedef_tablo="ogrenciler",
            hedef_kayit_id=yeni_id,
            mevcut_cursor=cursor,
            ayrinti={"yeni": {"tur": ogr.tur}}
        )

        conn.commit()
        return {"durum": "basarili", "mesaj": "Öğrenci başarıyla sisteme eklendi.", "ogrenci_id": yeni_id}

    except psycopg2.errors.UniqueViolation:
        if conn: conn.rollback()
        raise HTTPException(status_code=400, detail="Bu öğrenci numarası sistemde zaten kayıtlı!")
    except Exception:
        if conn: conn.rollback()
        raise HTTPException(status_code=500, detail="İşlem sırasında beklenmeyen bir sunucu hatası oluştu.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


# (yöntem, yol, uç fonksiyonu, yetki parametresi, gereken yetki, ek yol ayarları): yetki bağımlılığı kayıt sırasında eklenir.
# Gereken yetki: "IZIN" (izin_kontrol), ("A", "B") (izin_kontrol_biri: biri yeter) veya None (yalnızca oturum açmış olmak).
UCLAR = [
    ("GET", "/api/ogrenciler-liste", ogrencileri_getir, "kullanici_id", "FAALIYET_KAYITLARI_DUZENLE", {}),
    ("GET", "/api/ogrenciler-yonetim", ogrenciler_yonetim_listesi, "yetkili_id", "FAALIYET_KAYITLARI_DUZENLE", {}),
    ("GET", "/api/ogrenciler/{ogrenci_id}/puanlar", ogrenci_puan_detayi, "yetkili_id", "FAALIYET_KAYITLARI_DUZENLE", {}),
    ("PATCH", "/api/ogrenciler/{ogrenci_id}/silme-ertele", ogrenci_silme_ertele, "yetkili_id", "FAALIYET_KAYITLARI_DUZENLE", {}),
    ("DELETE", "/api/ogrenciler/{ogrenci_id}/saklama-suresi-sil", ogrenci_saklama_suresi_sil, "yetkili_id", "OGRENCI_KAYDI_SIL", {}),
    ("PATCH", "/api/ogrenciler/{ogrenci_id}/aktiflik", ogrenci_aktiflik_duzenle, "yetkili_id", "FAALIYET_KAYITLARI_DUZENLE", {}),
    ("POST", "/api/ogrenci-ekle", ogrenci_ekle, "yetkili_id", "FAALIYET_KAYITLARI_DUZENLE", {}),
]


def router_olustur(izin_kontrol) -> APIRouter:
    """Yetki bağımlılığı üreticileri `server.sunucu` içindeki kimlik doğrulama bağımlılıklarıdır."""
    router = APIRouter()
    for metod, yol, fonksiyon, parametre, yetki, ek in UCLAR:
        assert isinstance(yetki, str), yol          # bu modülde yalnızca tek izin tanımlı
        bagimlilik = izin_kontrol(yetki)
        router.add_api_route(yol, yetkiyle_bagla(fonksiyon, parametre, bagimlilik), methods=[metod], **ek)
    return router
