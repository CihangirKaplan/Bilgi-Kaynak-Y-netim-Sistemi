"""Faaliyet türleri uçları (listeleme, ekleme, düzenleme). `server/sunucu.py` içinden ayrıldı."""
from fastapi import APIRouter, HTTPException
import psycopg2

from server.vt_ayarlari import VT_AYARLARI
from server.vt_baglanti import vt_baglan
from server.yetki_baglama import yetkiyle_bagla


def faaliyetleri_getir(kullanici_id: int | None = None):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        # Sadece aktif olan faaliyetleri listele
        cursor.execute("SELECT faaliyet_id, faaliyet_adi, puan FROM faaliyetler WHERE aktif_mi = true ORDER BY faaliyet_id;")

        faaliyetler = []
        for kayit in cursor.fetchall():
            faaliyetler.append({
                "id": kayit[0],
                "ad": kayit[1],
                "puan": kayit[2]
            })
        return faaliyetler
    except Exception:
        raise HTTPException(status_code=500, detail="İşlem sırasında beklenmeyen bir sunucu hatası oluştu.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


from pydantic import BaseModel as _FaaliyetBaseModel


from pydantic import Field as _FaaliyetField


# Faaliyet puanı üst sınırı: puan x miktar (en çok 10.000) çarpımı veritabanındaki INTEGER sınırını aşmasın.
FAALIYET_PUANI_EN_FAZLA = 10_000


class FaaliyetTuruEkleModeli(_FaaliyetBaseModel):
    faaliyet_adi: str = _FaaliyetField(
        min_length=1, max_length=100
    )
    puan: int = _FaaliyetField(
        ge=0, le=FAALIYET_PUANI_EN_FAZLA, strict=True
    )


FAALIYET_ADI_KAYITLI_MESAJI = "Bu adla bir faaliyet türü zaten kayıtlı (büyük/küçük harf farkı aynı ad sayılır)."


def _faaliyet_adi_kayitli_mi(cursor, ad, haric_id=None):
    """Aynı ad (büyük/küçük harf ve baş/son boşluk farkı gözetmeden) başka bir faaliyet türünde var mı?

    Pasif türler de sayılır: veritabanındaki benzersizlik kuralı onları da kapsar. Kontrol ile kayıt arasında başka bir
    isteğin aynı adı eklememesi için işlem boyunca tek bir kilit alınır."""
    cursor.execute("SELECT pg_advisory_xact_lock(hashtext('TKYS_FAALIYET_ADI'));")
    cursor.execute(
        "SELECT faaliyet_id FROM faaliyetler "
        "WHERE LOWER(BTRIM(faaliyet_adi)) = LOWER(%s) AND faaliyet_id <> %s;",
        (ad, haric_id if haric_id is not None else 0),
    )
    return len(list(cursor.fetchall())) > 0


def faaliyet_turu_ekle(
    veri: FaaliyetTuruEkleModeli,
    yetkili_id: int | None = None
):
    ad = veri.faaliyet_adi.strip()

    if not ad:
        raise HTTPException(
            status_code=422,
            detail="Faaliyet adı boş olamaz."
        )

    conn = None

    try:
        conn = vt_baglan(VT_AYARLARI)

        with conn.cursor() as cursor:
            if _faaliyet_adi_kayitli_mi(cursor, ad):
                raise HTTPException(status_code=409, detail=FAALIYET_ADI_KAYITLI_MESAJI)

            cursor.execute("""
                INSERT INTO faaliyetler
                    (faaliyet_adi, puan, aktif_mi)
                VALUES (%s, %s, TRUE)
                RETURNING faaliyet_id;
            """, (ad, veri.puan))

            yeni_id = cursor.fetchone()[0]

            from server.denetim import denetim_kaydi_olustur

            denetim_kaydi_olustur(
                VT_AYARLARI,
                "CREATE",
                yetkili_id,
                "faaliyetler",
                yeni_id,
                mevcut_cursor=cursor
            )

        conn.commit()

        return {
            "durum": "basarili",
            "id": yeni_id,
            "ad": ad,
            "puan": veri.puan
        }

    except psycopg2.errors.UniqueViolation:
        if conn:
            conn.rollback()
        raise HTTPException(
            status_code=409,
            detail="Bu faaliyet türü zaten kayıtlı."
        )

    except HTTPException:
        if conn:
            conn.rollback()
        raise

    except Exception:
        if conn:
            conn.rollback()
        raise HTTPException(
            status_code=500,
            detail="Faaliyet türü eklenemedi."
        )

    finally:
        if conn:
            conn.close()


class FaaliyetTuruDuzenleModeli(_FaaliyetBaseModel):
    faaliyet_adi: str = _FaaliyetField(
        min_length=1, max_length=100
    )
    puan: int = _FaaliyetField(
        ge=0, le=FAALIYET_PUANI_EN_FAZLA, strict=True
    )
    gecmis_puanlari_guncelle: bool = _FaaliyetField(
        strict=True
    )


def faaliyet_turu_duzenle(
    faaliyet_id: int,
    veri: FaaliyetTuruDuzenleModeli,
    yetkili_id: int | None = None
):
    ad = veri.faaliyet_adi.strip()

    if not ad:
        raise HTTPException(
            status_code=422,
            detail="Faaliyet adı boş olamaz."
        )

    conn = None

    try:
        conn = vt_baglan(VT_AYARLARI)

        with conn.cursor() as cursor:

            # Aynı faaliyet üzerinde eşzamanlı değişiklikleri
            # transaction tamamlanana kadar kilitle.
            cursor.execute("""
                SELECT faaliyet_adi, puan
                FROM faaliyetler
                WHERE faaliyet_id = %s
                  AND aktif_mi = TRUE
                FOR UPDATE;
            """, (faaliyet_id,))

            eski = cursor.fetchone()

            if eski is None:
                raise HTTPException(
                    status_code=404,
                    detail="Aktif faaliyet türü bulunamadı."
                )

            eski_ad, eski_puan = eski
            puan_degisti = eski_puan != veri.puan

            # Kayıt değişmemişse gereksiz audit oluşturma.
            if eski_ad == ad and not puan_degisti:
                conn.commit()
                return {
                    "durum": "degisiklik_yok",
                    "id": faaliyet_id,
                    "ad": ad,
                    "puan": veri.puan,
                    "guncellenen_gecmis_kayit": 0
                }

            if eski_ad != ad and _faaliyet_adi_kayitli_mi(cursor, ad, haric_id=faaliyet_id):
                raise HTTPException(status_code=409, detail=FAALIYET_ADI_KAYITLI_MESAJI)

            cursor.execute("""
                UPDATE faaliyetler
                SET faaliyet_adi = %s,
                    puan = %s
                WHERE faaliyet_id = %s;
            """, (ad, veri.puan, faaliyet_id))

            etkilenen = 0

            # Yalnızca puan değişmişse VE kullanıcı açıkça
            # geçmişi güncelle demişse geçmişe dokun.
            if (
                puan_degisti
                and veri.gecmis_puanlari_guncelle
            ):
                cursor.execute("""
                    UPDATE ogrenci_faaliyet_takip
                    SET kayit_puani = %s
                    WHERE faaliyet_id = %s
                      AND kayit_puani <> %s;
                """, (
                    veri.puan,
                    faaliyet_id,
                    veri.puan
                ))

                etkilenen = cursor.rowcount

            from server.denetim import denetim_kaydi_olustur

            # Denetim kaydı: ad ve puanın önceki/yeni değeri; geçmiş kayıtlara uygulandıysa kaç kayıt etkilendiği.
            degisiklik = {"onceki": {}, "yeni": {}}
            if eski_ad != ad:
                degisiklik["onceki"]["faaliyet_adi"] = eski_ad
                degisiklik["yeni"]["faaliyet_adi"] = ad
            if puan_degisti:
                degisiklik["onceki"]["puan"] = eski_puan
                degisiklik["yeni"]["puan"] = veri.puan
                degisiklik["gecmis_kayitlara_uygulandi"] = bool(veri.gecmis_puanlari_guncelle)
                degisiklik["guncellenen_gecmis_kayit"] = etkilenen

            denetim_kaydi_olustur(
                VT_AYARLARI,
                "UPDATE",
                yetkili_id,
                "faaliyetler",
                faaliyet_id,
                mevcut_cursor=cursor,
                ayrinti=degisiklik
            )

            # Toplu geçmiş güncellemesini ayrıca işaretle.
            if etkilenen:
                denetim_kaydi_olustur(
                    VT_AYARLARI,
                    "UPDATE",
                    yetkili_id,
                    "ogrenci_faaliyet_takip",
                    None,
                    mevcut_cursor=cursor,
                    ayrinti={
                        "neden": "faaliyet puanı geçmiş kayıtlara uygulandı",
                        "faaliyet_id": faaliyet_id,
                        "onceki": {"faaliyet_puani": eski_puan},
                        "yeni": {"faaliyet_puani": veri.puan},
                        "etkilenen_kayit": etkilenen,
                    }
                )

        conn.commit()

        return {
            "durum": "basarili",
            "id": faaliyet_id,
            "ad": ad,
            "puan": veri.puan,
            "gecmis_puanlari_guncellendi": (
                puan_degisti
                and veri.gecmis_puanlari_guncelle
            ),
            "guncellenen_gecmis_kayit": etkilenen
        }

    except psycopg2.errors.UniqueViolation:
        if conn:
            conn.rollback()
        raise HTTPException(
            status_code=409,
            detail="Bu faaliyet türü adı zaten kayıtlı."
        )

    except HTTPException:
        if conn:
            conn.rollback()
        raise

    except Exception:
        if conn:
            conn.rollback()
        raise HTTPException(
            status_code=500,
            detail="Faaliyet türü güncellenemedi."
        )

    finally:
        if conn:
            conn.close()


# (yöntem, yol, uç fonksiyonu, yetki parametresi, gereken izin, ek yol ayarları): yetki bağımlılığı kayıt sırasında eklenir.
UCLAR = [
    ("GET", "/api/faaliyetler", faaliyetleri_getir, "kullanici_id", "FAALIYET_KAYITLARI_DUZENLE", {}),
    ("POST", "/api/faaliyetler", faaliyet_turu_ekle, "yetkili_id", "FAALIYET_KAYITLARI_DUZENLE", {"status_code": 201}),
    ("PUT", "/api/faaliyetler/{faaliyet_id}", faaliyet_turu_duzenle, "yetkili_id", "FAALIYET_KAYITLARI_DUZENLE", {}),
]


def router_olustur(izin_kontrol) -> APIRouter:
    """`izin_kontrol`: `server.sunucu.izin_kontrol` (kimlik doğrulama + izin kontrolü bağımlılığı üreticisi)."""
    router = APIRouter()
    for metod, yol, fonksiyon, parametre, izin, ek in UCLAR:
        router.add_api_route(yol, yetkiyle_bagla(fonksiyon, parametre, izin_kontrol(izin)), methods=[metod], **ek)
    return router
