"""Kullanıcı yönetimi uçları: oluşturma, kullanıcı adı müsaitliği, rol değiştirme, durum değiştirme ve parola sıfırlama. `server/sunucu.py` içinden ayrıldı."""
from fastapi import APIRouter, HTTPException, Query, Response
from psycopg2.errors import DeadlockDetected
from pydantic import BaseModel as _DurumBaseModel, Field as _DurumField
import psycopg2

from server.denetim import ayrintili_kayit_yaz, durum_degisikligi_yaz, psikolog_oda_degisikligini_yaz, psikolog_odalarini_oku
from server.guvenlik import GECICI_PAROLA_BITIS_SQL, GECICI_PAROLA_GECERLILIK_SAAT, gecici_parola_uret, parola_hashle
from server.modeller import KullaniciOlusturModeli, RolDegistirModeli
from server.oda_api import cihaz_rezervasyonlu_odalari_denetle, etkinlik_oda_atama_kilitlerini_al, oda_etkinlikli_odalari_denetle, psikolog_planli_randevulari_denetle
from server.ortak_sabitler import PLANLI_RANDEVU_COZUMU
from server.ortak_yardimcilar import psikolog_rolu_mu
from server.rol_hiyerarsisi import HIYERARSI_MESAJI, hiyerarsi_ihlali_var_mi
from server.vt_ayarlari import VT_AYARLARI
from server.vt_baglanti import vt_baglan
from server.yetki_baglama import Hepsi, yetkiyle_bagla


ROL_PASIF_ATAMA_MESAJI = "Seçilen rol pasif; pasif role kullanıcı atanamaz. Önce rolü aktif edin."


def _siradaki_personel_kodu(cursor, rol_adi):
    """Rol bazında benzersiz personel kodu üretir."""
    import re

    rol_kodlari = {
        "PSIKOLOG": "PSK",
        "MEMUR": "MEM",
        "MUDUR": "MUD",
        "DANISMA_OGRENCISI": "OGR",
        "PROJE_ASISTANI": "AST",
        "ADMIN": "ADM",
    }

    rol_kodu = rol_kodlari.get(rol_adi, "SYS")
    onek = f"PER-{rol_kodu}-"

    # Kullanıcı oluşturmayla aynı kilit: eşzamanlı kod çakışmasını önler.
    cursor.execute(
        "SELECT pg_advisory_xact_lock(hashtext(%s));",
        (f"TKYS_PERSONEL_KODU_{rol_kodu}",),
    )

    cursor.execute(
        "SELECT personel_kodu FROM kullanicilar "
        "WHERE personel_kodu LIKE %s;",
        (onek + "%",),
    )

    numaralar = []
    for (kod,) in cursor.fetchall():
        if not isinstance(kod, str):
            continue

        eslesme = re.fullmatch(
            re.escape(onek) + r"([0-9]+)", kod
        )
        if eslesme:
            numaralar.append(int(eslesme.group(1)))

    return f"{onek}{max(numaralar, default=0) + 1:03d}"


def kullanici_olustur(
    yeni_kullanici: KullaniciOlusturModeli,
    kullanici_id: int | None = None,
):

    conn = None
    cursor = None
    asama = "kullanici"
    personel_id = None
    personel_kodu = None
    ogrenci_id = None

    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        # İşlemi yapan kişinin rolünü öğren.
        cursor.execute(
            """
            SELECT r.rol_adi
            FROM kullanicilar k
            JOIN roller r ON k.rol_id = r.rol_id
            WHERE k.kullanici_id = %s;
            """,
            (kullanici_id,),
        )
        yapan = cursor.fetchone()

        # Birleşik oluşturma için iki yetki de gerekli.
        # Mevcut rol atama izni korunur.
        cursor.execute(
            """
            SELECT 1
            FROM kullanicilar k
            WHERE k.kullanici_id = %s
              AND EXISTS (
                  SELECT 1
                  FROM rol_izinleri ri
                  JOIN izinler i ON i.izin_id = ri.izin_id
                  WHERE ri.rol_id = k.rol_id
                    AND i.izin_adi = 'ROL_ATAMA_DEGISTIRME'
                    AND ri.izin_var = 1
              )
              AND EXISTS (
                  SELECT 1
                  FROM rol_izinleri ri
                  JOIN izinler i ON i.izin_id = ri.izin_id
                  WHERE ri.rol_id = k.rol_id
                    AND i.izin_adi = 'PERSONEL_TANIMLA'
                    AND ri.izin_var = 1
              );
            """,
            (kullanici_id,),
        )

        if cursor.fetchone() is None:
            raise HTTPException(
                status_code=403,
                detail="Kullanıcı oluşturma için gerekli yetkileriniz bulunmuyor.",
            )

        cursor.execute(
            "SELECT rol_adi, aktif_mi FROM roller WHERE rol_id = %s;",
            (yeni_kullanici.rol_id,),
        )
        hedef_rol = cursor.fetchone()

        if hedef_rol is None:
            raise HTTPException(
                status_code=422,
                detail="Geçersiz rol seçildi.",
            )
        if len(hedef_rol) > 1 and hedef_rol[1] is False:
            raise HTTPException(status_code=422, detail=ROL_PASIF_ATAMA_MESAJI)

        rol_adi = hedef_rol[0]

        if rol_adi == "ADMIN":
            raise HTTPException(
                status_code=403,
                detail="ADMIN kullanıcısı bu ekran üzerinden oluşturulamaz.",
            )
        if hiyerarsi_ihlali_var_mi(yapan[0] if yapan else None, rol_adi):
            raise HTTPException(status_code=403, detail=HIYERARSI_MESAJI)

        danisma_ogrencisi = rol_adi == "DANISMA_OGRENCISI"

        ogrenci_bilgisi_var = any([
            yeni_kullanici.ad_soyad,
            yeni_kullanici.ogrenci_numarasi,
            yeni_kullanici.telefon,
        ])

        if danisma_ogrencisi:
            if (
                not yeni_kullanici.ad_soyad
                or not yeni_kullanici.ogrenci_numarasi
            ):
                raise HTTPException(
                    status_code=422,
                    detail="Danışma öğrencisi için ad soyad ve öğrenci numarası zorunludur.",
                )
        elif ogrenci_bilgisi_var:
            raise HTTPException(
                status_code=422,
                detail="Öğrenci bilgileri yalnızca danışma öğrencisi rolü için girilebilir.",
            )

        psikolog_rolu = psikolog_rolu_mu(rol_adi)
        istenen_odalar = sorted(set(yeni_kullanici.oda_idleri or []))
        if psikolog_rolu:
            # Her psikologun en az bir (aktif) odası olmalı.
            if not istenen_odalar:
                raise HTTPException(
                    status_code=422,
                    detail="Psikolog için en az bir görüşme odası seçilmelidir.",
                )
            cursor.execute(
                "SELECT oda_id FROM odalar WHERE oda_id = ANY(%s) AND aktif_mi = TRUE;",
                (istenen_odalar,),
            )
            if {k[0] for k in cursor.fetchall()} != set(istenen_odalar):
                raise HTTPException(
                    status_code=422,
                    detail="Seçilen odalardan biri bulunamadı veya aktif değil.",
                )
            etkinlik_oda_atama_kilitlerini_al(
                cursor, istenen_odalar
            )
            cihaz_rezervasyonlu_odalari_denetle(cursor, istenen_odalar)
            oda_etkinlikli_odalari_denetle(cursor, istenen_odalar)
        elif istenen_odalar:
            raise HTTPException(
                status_code=422,
                detail="Oda yetkisi yalnızca psikolog rolü için tanımlanabilir.",
            )

        gecici_parola = gecici_parola_uret()
        parola_hash = parola_hashle(gecici_parola)
        personel_kodu = _siradaki_personel_kodu(cursor, rol_adi)

        cursor.execute(
            f"""
            INSERT INTO kullanicilar
                (kullanici_adi, parola_hash, rol_id, aktif_mi, ilk_giris_mi, gecici_parola_bitis,
                 personel_id, personel_kodu, personel_kaydi_tarihi)
            SELECT %s, %s, %s, TRUE, TRUE, {GECICI_PAROLA_BITIS_SQL},
                   nextval('personel_personel_id_seq'), %s, CURRENT_TIMESTAMP
            WHERE NOT EXISTS (SELECT 1 FROM kullanicilar WHERE LOWER(kullanici_adi) = LOWER(%s))
            RETURNING kullanici_id, personel_id;
            """,
            (
                yeni_kullanici.kullanici_adi,
                parola_hash,
                yeni_kullanici.rol_id,
                personel_kodu,
                yeni_kullanici.kullanici_adi,
            ),
        )
        satir = cursor.fetchone()
        if satir is None:                                   # aynı ad (büyük/küçük harf farkıyla da olsa) zaten var
            raise HTTPException(status_code=409, detail="Bu kullanıcı adı zaten kullanılıyor.")
        yeni_id, personel_id = satir

        # Tek denetim kaydı: kullanıcı ve personel bilgisi aynı kayıttır.
        ayrintili_kayit_yaz(
            cursor, kullanici_id, "CREATE", "kullanicilar", yeni_id,
            rol=rol_adi, personel_kodu=personel_kodu, oda_sayisi=len(istenen_odalar),
        )

        if danisma_ogrencisi:
            asama = "ogrenci"
            cursor.execute(
                """
                INSERT INTO ogrenciler
                    (kullanici_id, ad_soyad, ogrenci_numarasi, telefon, tur)
                VALUES (%s, %s, %s, %s, 'DANISMA_MASASI')
                RETURNING ogrenci_id;
                """,
                (
                    yeni_id,
                    yeni_kullanici.ad_soyad,
                    yeni_kullanici.ogrenci_numarasi,
                    yeni_kullanici.telefon,
                ),
            )
            ogrenci_id = cursor.fetchone()[0]
            cursor.execute(
                """
                INSERT INTO denetim_kayitlari
                    (kullanici_id, olay_turu, hedef_tablo, hedef_kayit_id)
                VALUES (%s, %s, %s, %s);
                """,
                (kullanici_id, "CREATE", "ogrenciler", ogrenci_id),
            )

        # Psikolog oda yetkileri.
        for oda_id in istenen_odalar:
            cursor.execute(
                "INSERT INTO psikolog_odalar (kullanici_id, oda_id) VALUES (%s, %s);",
                (yeni_id, oda_id),
            )

        # Her şey başarılıysa tek commit.
        conn.commit()

        return {
            "durum": "basarili",
            "kullanici_id": yeni_id,
            "kullanici_adi": yeni_kullanici.kullanici_adi,
            "gecici_parola": gecici_parola,
            "gecici_parola_gecerlilik_saat": GECICI_PAROLA_GECERLILIK_SAAT,
            "ilk_giris_mi": True,
            "personel_id": personel_id,
            "personel_kodu": personel_kodu,
            "ogrenci_id": ogrenci_id,
        }

    except psycopg2.errors.UniqueViolation as hata:
        if conn is not None:
            conn.rollback()

        kisit = getattr(getattr(hata, "diag", None), "constraint_name", None) or ""
        if asama == "ogrenci":
            mesaj = "Bu öğrenci numarası zaten kullanılıyor."
        elif kisit.startswith("kullanicilar_personel_"):
            mesaj = "Personel kodu veya personel kaydı zaten mevcut."
        else:
            mesaj = "Bu kullanıcı adı zaten kullanılıyor."

        raise HTTPException(status_code=409, detail=mesaj)

    except HTTPException:
        if conn is not None:
            conn.rollback()
        raise

    except Exception:
        if conn is not None:
            conn.rollback()
        raise HTTPException(
            status_code=500,
            detail="Kullanıcı oluşturulurken beklenmeyen bir hata oluştu.",
        )

    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


def musait_kullanici_adi(
    temel: str = Query(..., min_length=1, max_length=90),
    kullanici_id: int | None = None
):
    """Verilen ad boşsa onu, doluysa sonuna sayı ekleyerek ilk boş adı döndürür.

    Örn. 'cihangir.kaplan' doluysa 'cihangir.kaplan2', o da doluysa 'cihangir.kaplan3'.
    Aynı isimli kişiler için kullanıcı adı çakışmasını önler.
    """
    temel = "".join(c for c in temel.lower() if c.isascii() and (c.isalnum() or c in "._-")).strip("._-")
    if len(temel) < 3:
        raise HTTPException(status_code=422, detail="Kullanıcı adı en az 3 karakter olmalıdır.")

    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT lower(kullanici_adi) FROM kullanicilar WHERE starts_with(lower(kullanici_adi), %s);",
            (temel,)
        )
        kullanilan = {satir[0] for satir in cursor.fetchall()}
        onerilen, sayi = temel, 1
        while onerilen in kullanilan:
            sayi += 1
            onerilen = f"{temel}{sayi}"
        return {"kullanici_adi": onerilen}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="İşlem sırasında beklenmeyen bir sunucu hatası oluştu.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


def kullanici_ogrenci_kayit_durumu(
    kullanici_id: int,
    islem_yapan_id: int | None = None,
):
    conn = vt_baglan(VT_AYARLARI)
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM kullanicilar WHERE kullanici_id = %s;",
                (kullanici_id,),
            )
            if cursor.fetchone() is None:
                raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı.")

            cursor.execute(
                "SELECT ogrenci_id FROM ogrenciler WHERE kullanici_id = %s;",
                (kullanici_id,),
            )
            return {"ogrenci_kaydi_var": cursor.fetchone() is not None}
    finally:
        conn.close()


def kullanici_rol_degistir(kullanici_id: int, veri: RolDegistirModeli, islem_yapan_id: int | None = None):
    conn = None
    cursor = None
    if kullanici_id == islem_yapan_id:
        raise HTTPException(
            status_code=403,
            detail="Kendi rolünüzü değiştiremezsiniz."
        )

    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        cursor.execute("SELECT r.rol_adi FROM kullanicilar k JOIN roller r ON k.rol_id = r.rol_id WHERE k.kullanici_id = %s;", (islem_yapan_id,))
        islem_yapan = cursor.fetchone()
        if islem_yapan is None:
            raise HTTPException(status_code=403, detail="Yetkisiz işlem.")
        islem_yapan_rol = islem_yapan[0]

        # KİLİT SIRASI (deadlock önleme): önce oda kilitleri, sonra kullanıcı satırı. Rezervasyon/randevu yolları oda kilidini alıp sonra
        # denetim kaydıyla kullanıcı satırını (FK) okur; burada tersi sıra (önce satır, sonra oda kilidi) karşılıklı beklemeye yol açıyordu.
        if veri.oda_idleri:
            etkinlik_oda_atama_kilitlerini_al(cursor, sorted(set(veri.oda_idleri)))

        cursor.execute("SELECT r.rol_adi FROM kullanicilar k JOIN roller r ON k.rol_id = r.rol_id WHERE k.kullanici_id = %s FOR UPDATE OF k;", (kullanici_id,))
        hedef_kullanici = cursor.fetchone()
        if hedef_kullanici is None:
            raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı.")
        mevcut_rol = hedef_kullanici[0]

        cursor.execute("SELECT rol_adi, aktif_mi FROM roller WHERE rol_id = %s;", (veri.rol_id,))
        yeni_rol = cursor.fetchone()
        if yeni_rol is None:
            raise HTTPException(status_code=404, detail="Atanacak rol bulunamadı.")
        if len(yeni_rol) > 1 and yeni_rol[1] is False:
            raise HTTPException(status_code=422, detail=ROL_PASIF_ATAMA_MESAJI)
        yeni_rol_adi = yeni_rol[0]

        # ADMIN rolu normal rol degistirme islemlerine kapali.
        # ADMIN kullanicilar da bu kisitlamadan muaf degildir.
        if mevcut_rol == "ADMIN" or yeni_rol_adi == "ADMIN":
            raise HTTPException(
                status_code=403,
                detail="ADMIN rolü atanamaz veya başka bir role dönüştürülemez."
            )

        if hiyerarsi_ihlali_var_mi(islem_yapan_rol, mevcut_rol, yeni_rol_adi):
            raise HTTPException(status_code=403, detail=HIYERARSI_MESAJI)

        if mevcut_rol == yeni_rol_adi:
            raise HTTPException(
                status_code=409,
                detail="Kullanıcı zaten seçilen role sahip."
            )

        # Her psikologun en az bir (aktif) odası olmalı: psikolog yapılırken oda seçilmesi zorunludur.
        psikolog_olacak = psikolog_rolu_mu(yeni_rol_adi)
        psikolog_idi = psikolog_rolu_mu(mevcut_rol)
        istenen_odalar = sorted(set(veri.oda_idleri or []))
        if psikolog_idi and not psikolog_olacak:
            # Psikologluktan çıkarken odaları kalkar: bugün ve sonrası için planlı randevusu varsa önce iptal edilmeli.
            psikolog_planli_randevulari_denetle(cursor, kullanici_id)
        if psikolog_olacak:
            if not istenen_odalar:
                raise HTTPException(
                    status_code=422,
                    detail="Psikolog rolü için en az bir görüşme odası seçilmelidir.",
                )
            cursor.execute(
                "SELECT oda_id FROM odalar WHERE oda_id = ANY(%s) AND aktif_mi = TRUE;",
                (istenen_odalar,),
            )
            if {k[0] for k in cursor.fetchall()} != set(istenen_odalar):
                raise HTTPException(
                    status_code=422,
                    detail="Seçilen odalardan biri bulunamadı veya aktif değil.",
                )
            etkinlik_oda_atama_kilitlerini_al(
                cursor, istenen_odalar
            )
            cihaz_rezervasyonlu_odalari_denetle(cursor, istenen_odalar)
            oda_etkinlikli_odalari_denetle(cursor, istenen_odalar)
        elif istenen_odalar:
            raise HTTPException(
                status_code=422,
                detail="Oda yetkisi yalnızca psikolog rolü için tanımlanabilir.",
            )

        ogrenci_kaydi = None
        bilgi_var = any((veri.ad_soyad, veri.ogrenci_numarasi, veri.telefon))

        if yeni_rol_adi == "DANISMA_OGRENCISI":
            cursor.execute(
                "SELECT ogrenci_id, tur::text FROM ogrenciler "
                "WHERE kullanici_id = %s FOR UPDATE;",
                (kullanici_id,),
            )
            ogrenci_kaydi = cursor.fetchone()

            if ogrenci_kaydi is None and (
                not veri.ad_soyad or not veri.ogrenci_numarasi
            ):
                raise HTTPException(
                    status_code=422,
                    detail="Ad soyad ve öğrenci numarası zorunludur.",
                )
        elif bilgi_var:
            raise HTTPException(
                status_code=422,
                detail="Öğrenci bilgileri yalnızca Danışma Öğrencisi rolü içindir.",
            )

        # Danışma öğrencisi rolünden ayrılırken açık görev bulunmamalı.
        pasiflestirilecek_ogrenci_id = None

        if (
            mevcut_rol == "DANISMA_OGRENCISI"
            and yeni_rol_adi != "DANISMA_OGRENCISI"
        ):
            cursor.execute(
                "SELECT ogrenci_id FROM ogrenciler "
                "WHERE kullanici_id = %s FOR UPDATE;",
                (kullanici_id,),
            )
            onceki_ogrenci = cursor.fetchone()

            if onceki_ogrenci is not None:
                pasiflestirilecek_ogrenci_id = onceki_ogrenci[0]

                cursor.execute(
                    "SELECT 1 FROM danisma_masasi_oturumlari "
                    "WHERE ogrenci_id = %s "
                    "AND bitis_zamani IS NULL LIMIT 1;",
                    (pasiflestirilecek_ogrenci_id,),
                )

                if cursor.fetchone() is not None:
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            "Bu öğrencinin devam eden danışma masası "
                            "görevi bulunuyor. Önce görevi bitirin."
                        ),
                    )

        # Personel bilgisi kullanıcı satırındadır; mevcut personel_id korunacak.
        cursor.execute(
            "SELECT personel_id, personel_kodu FROM kullanicilar "
            "WHERE kullanici_id = %s AND personel_id IS NOT NULL FOR UPDATE;",
            (kullanici_id,),
        )
        personel = cursor.fetchone()

        if personel is None:
            raise HTTPException(
                status_code=409,
                detail="Kullanıcıya ait personel kaydı bulunamadı."
            )

        yeni_personel_kodu = _siradaki_personel_kodu(
            cursor, yeni_rol_adi
        )

        cursor.execute(
            "UPDATE kullanicilar SET rol_id = %s, personel_kodu = %s WHERE kullanici_id = %s;",
            (veri.rol_id, yeni_personel_kodu, kullanici_id),
        )
        if yeni_rol_adi == "DANISMA_OGRENCISI":
            if ogrenci_kaydi is None:
                cursor.execute(
                    "INSERT INTO ogrenciler "
                    "(kullanici_id, ad_soyad, ogrenci_numarasi, telefon, tur) "
                    "VALUES (%s, %s, %s, %s, 'DANISMA_MASASI') "
                    "RETURNING ogrenci_id;",
                    (
                        kullanici_id,
                        veri.ad_soyad,
                        veri.ogrenci_numarasi,
                        veri.telefon,
                    ),
                )
                ogrenci_id = cursor.fetchone()[0]
                ogrenci_olay = "CREATE"
            else:
                ogrenci_id = ogrenci_kaydi[0]
                ogrenci_olay = None
                if ogrenci_kaydi[1] != "DANISMA_MASASI":
                    cursor.execute(
                        "UPDATE ogrenciler "
                        "SET tur = 'DANISMA_MASASI', aktif_mi = TRUE "
                        "WHERE ogrenci_id = %s;",
                        (ogrenci_id,),
                    )
                    ogrenci_olay = "UPDATE"
                else:
                    cursor.execute(
                        "UPDATE ogrenciler SET aktif_mi = TRUE "
                        "WHERE ogrenci_id = %s AND aktif_mi = FALSE;",
                        (ogrenci_id,),
                    )
                    if cursor.rowcount > 0:
                        ogrenci_olay = "UPDATE"

            if ogrenci_olay:
                cursor.execute(
                    "INSERT INTO denetim_kayitlari "
                    "(kullanici_id, olay_turu, hedef_tablo, hedef_kayit_id) "
                    "VALUES (%s, %s, %s, %s);",
                    (islem_yapan_id, ogrenci_olay, "ogrenciler", ogrenci_id),
                )
        if pasiflestirilecek_ogrenci_id is not None:
            cursor.execute(
                "UPDATE ogrenciler SET aktif_mi = FALSE "
                "WHERE ogrenci_id = %s AND aktif_mi = TRUE;",
                (pasiflestirilecek_ogrenci_id,),
            )

            if cursor.rowcount > 0:
                cursor.execute(
                    "INSERT INTO denetim_kayitlari "
                    "(kullanici_id, olay_turu, hedef_tablo, hedef_kayit_id) "
                    "VALUES (%s, %s, %s, %s);",
                    (
                        islem_yapan_id,
                        "UPDATE",
                        "ogrenciler",
                        pasiflestirilecek_ogrenci_id,
                    ),
                )

        # Bir danışanın tek psikoloğu vardır: psikologluktan çıkan kişinin danışanları pasife alınır (randevu geçmişi korunur); yeniden
        # psikolog olunca yalnızca BU YÜZDEN pasifleşenler geri açılır (elle pasif olanlar pasif kalır). Pasif kullanıcıda geri açma bekler.
        danisan_sayisi = 0
        if psikolog_idi and not psikolog_olacak:
            cursor.execute(
                "UPDATE danisan_kodlari SET aktif_mi = FALSE, psikolog_pasifligi_nedeniyle_pasif = TRUE "
                "WHERE aktif_mi = TRUE AND olusturan_psikolog_id IN (SELECT personel_id FROM personel WHERE kullanici_id = %s);",
                (kullanici_id,),
            )
        elif psikolog_olacak and not psikolog_idi:
            cursor.execute(
                "UPDATE danisan_kodlari SET aktif_mi = TRUE, psikolog_pasifligi_nedeniyle_pasif = FALSE "
                "WHERE psikolog_pasifligi_nedeniyle_pasif = TRUE "
                "AND olusturan_psikolog_id IN (SELECT personel_id FROM personel WHERE kullanici_id = %s) "
                "AND EXISTS (SELECT 1 FROM kullanicilar WHERE kullanici_id = %s AND aktif_mi = TRUE);",
                (kullanici_id, kullanici_id),
            )
        if psikolog_idi != psikolog_olacak:
            danisan_sayisi = cursor.rowcount if isinstance(cursor.rowcount, int) else 0
            if danisan_sayisi:
                ayrintili_kayit_yaz(cursor, islem_yapan_id, "UPDATE", "danisan_kodlari", None, neden="psikolog rolünden çıkıldı" if psikolog_idi else "psikolog rolüne geri dönüldü",
                                    etkilenen_danisan=danisan_sayisi, aktif_mi="pasif" if psikolog_idi else "aktif", psikolog_kullanici_id=kullanici_id)

        # Oda yetkileri yalnızca psikologlar içindir: psikolog olurken verilen odalar yazılır,
        # psikologluktan çıkarken silinir (yeniden psikolog olursa odalar yeniden seçilir).
        if psikolog_olacak or psikolog_idi:
            onceki_odalar = psikolog_odalarini_oku(cursor, kullanici_id)
            cursor.execute("DELETE FROM psikolog_odalar WHERE kullanici_id = %s;", (kullanici_id,))
            for oda_id in istenen_odalar:
                cursor.execute(
                    "INSERT INTO psikolog_odalar (kullanici_id, oda_id) VALUES (%s, %s);",
                    (kullanici_id, oda_id),
                )
            psikolog_oda_degisikligini_yaz(cursor, islem_yapan_id, kullanici_id, onceki_odalar)

        rol_ayrintisi = {"onceki": {"rol": mevcut_rol, "personel_kodu": personel[1]}, "yeni": {"rol": yeni_rol_adi, "personel_kodu": yeni_personel_kodu}}
        if danisan_sayisi:
            rol_ayrintisi["pasife_alinan_danisan" if psikolog_idi else "aktif_edilen_danisan"] = danisan_sayisi
        ayrintili_kayit_yaz(cursor, islem_yapan_id, "ROLE_CHANGE", "kullanicilar", kullanici_id, **rol_ayrintisi)
        conn.commit()

        yanit = {"mesaj": "Kullanıcı rolü ve personel kodu başarıyla değiştirildi.", "kullanici_id": kullanici_id, "yeni_rol_id": veri.rol_id, "yeni_rol_adi": yeni_rol_adi, "yeni_personel_kodu": yeni_personel_kodu}
        if danisan_sayisi:
            if psikolog_idi:
                yanit["pasife_alinan_danisan"] = danisan_sayisi
                yanit["mesaj"] += f" {danisan_sayisi} danışan pasife alındı (psikolog yeniden psikolog olunca geri açılır)."
            else:
                yanit["aktif_edilen_danisan"] = danisan_sayisi
                yanit["mesaj"] += f" {danisan_sayisi} danışan yeniden aktif edildi."
        return yanit
    except psycopg2.errors.UniqueViolation:
        if conn is not None:
            conn.rollback()
        raise HTTPException(
            status_code=409,
            detail="Öğrenci numarası veya personel kodu zaten kullanılıyor.",
        )
    except DeadlockDetected:
        if conn is not None:
            conn.rollback()
        raise HTTPException(status_code=503, detail="İşlem eşzamanlı yoğunluk nedeniyle tamamlanamadı. Lütfen tekrar deneyin.")
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


YONETICI_PAROLASI_ENGEL_MESAJI = (
    "Yönetici (ADMIN) hesaplarının parolası uygulamadan sıfırlanamaz; başka bir yönetici de sıfırlayamaz. "
    "Sunucu bilgisayarında kurtarma aracı kullanılmalıdır (scripts/admin_parola_kurtar.py)."
)


def kullanici_parola_sifirla(
    kullanici_id: int,
    response: Response,
    islem_yapan_id: int | None = None
):
    """Yalnızca ADMIN başka bir aktif kullanıcının parolasını sıfırlar."""

    if kullanici_id == islem_yapan_id:
        raise HTTPException(
            status_code=403,
            detail="Kendi parolanızı bu işlemle sıfırlayamazsınız."
        )

    conn = None
    cursor = None

    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        # Kullanıcı arayüzüne güvenmeden sunucuda ADMIN kontrolü
        cursor.execute(
            """
            SELECT r.rol_adi
            FROM kullanicilar k
            JOIN roller r ON r.rol_id = k.rol_id
            WHERE k.kullanici_id = %s;
            """,
            (islem_yapan_id,)
        )
        yonetici = cursor.fetchone()

        if yonetici is None or yonetici[0] != "ADMIN":
            raise HTTPException(
                status_code=403,
                detail="Bu işlem yalnızca ADMIN tarafından yapılabilir."
            )

        cursor.execute(
            """
            SELECT k.aktif_mi, r.rol_adi
            FROM kullanicilar k
            LEFT JOIN roller r ON r.rol_id = k.rol_id
            WHERE k.kullanici_id = %s
            FOR UPDATE OF k;
            """,
            (kullanici_id,)
        )
        hedef = cursor.fetchone()

        if hedef is None:
            raise HTTPException(
                status_code=404,
                detail="Kullanıcı bulunamadı."
            )

        # Yönetici hesapları uygulamadan sıfırlanamaz: bir yöneticinin başka bir yönetici hesabını ele geçirmesi engellenir.
        # Tek yol, sunucu bilgisayarındaki kurtarma aracıdır (kimin çalıştırdığı günlüğe yazılır).
        if len(hedef) > 1 and hedef[1] == "ADMIN":
            raise HTTPException(
                status_code=403,
                detail=YONETICI_PAROLASI_ENGEL_MESAJI
            )

        if not hedef[0]:
            raise HTTPException(
                status_code=409,
                detail="Pasif kullanıcının parolası sıfırlanamaz."
            )

        gecici_parola = gecici_parola_uret()
        yeni_hash = parola_hashle(gecici_parola)

        cursor.execute(
            f"""
            UPDATE kullanicilar
            SET parola_hash = %s,
                ilk_giris_mi = TRUE,
                basarisiz_giris_sayisi = 0,
                kilit_bitis_zamani = NULL,
                gecici_parola_bitis = {GECICI_PAROLA_BITIS_SQL}
            WHERE kullanici_id = %s;
            """,
            (yeni_hash, kullanici_id)
        )

        cursor.execute(
            """
            INSERT INTO denetim_kayitlari
                (kullanici_id, olay_turu, hedef_tablo, hedef_kayit_id)
            VALUES (%s, %s, %s, %s);
            """,
            (
                islem_yapan_id,
                "PASSWORD_RESET",
                "kullanicilar",
                kullanici_id
            )
        )

        # Bu kullanıcının bekleyen parola sıfırlama talebi varsa karşılanmış olur.
        cursor.execute(
            """
            UPDATE parola_sifirlama_talepleri
            SET durum = 'TAMAMLANDI', kapanis_zamani = CURRENT_TIMESTAMP, kapatan_kullanici_id = %s
            WHERE kullanici_id = %s AND durum = 'ACIK';
            """,
            (islem_yapan_id, kullanici_id)
        )

        conn.commit()

        response.headers["Cache-Control"] = "no-store"

        return {
            "durum": "basarili",
            "mesaj": "Geçici parola oluşturuldu.",
            "kullanici_id": kullanici_id,
            "gecici_parola": gecici_parola,
            "gecici_parola_gecerlilik_saat": GECICI_PAROLA_GECERLILIK_SAAT
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
            detail="Parola sıfırlama işlemi tamamlanamadı."
        )

    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


class DurumDegistirModeli(_DurumBaseModel):
    """Psikolog aktifleştirilirken görüşme odaları seçilir; diğer durumlarda gövde gerekmez."""
    oda_idleri: list[int] | None = _DurumField(default=None, max_length=100)


def kullanici_durum_degistir(
    kullanici_id: int,
    veri: DurumDegistirModeli | None = None,
    islem_yapan_id: int | None = None,
):
    """Kullanıcıyı aktif/pasif yapar (geçiş).

    Psikolog pasife alınırken: bugün ve sonrası için planlı randevusu varsa işlem 409 ile reddedilir; yoksa kendi danışanları da pasife
    alınır (yanıtta pasife_alinan_danisan; yeniden aktifleşince yalnızca bu yüzden pasifleşenler geri açılır, aktif_edilen_danisan) ve oda atamaları kaldırılır
    (geçmiş randevular ve raporlar etkilenmez, çünkü oda bilgisi randevunun kendisinde durur). Psikolog aktife alınırken en az
    bir görüşme odası seçilmelidir (oda_idleri); seçilen odalar cihaz rezervasyonu için kullanılıyorsa 409 döner."""
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        if kullanici_id == islem_yapan_id:
            raise HTTPException(status_code=403, detail="Kendi hesabınızın durumunu değiştiremezsiniz.")

        cursor.execute("SELECT r.rol_adi FROM kullanicilar k JOIN roller r ON k.rol_id = r.rol_id WHERE k.kullanici_id = %s;", (islem_yapan_id,))
        islem_yapan = cursor.fetchone()

        # KİLİT SIRASI (deadlock önleme): önce oda kilitleri, sonra kullanıcı satırı. Rezervasyon/randevu yolları oda kilidini alıp sonra
        # denetim kaydıyla kullanıcı satırını (FK) okur; burada tersi sıra (önce satır, sonra oda kilidi) karşılıklı beklemeye yol açıyordu.
        if veri is not None and veri.oda_idleri:
            etkinlik_oda_atama_kilitlerini_al(cursor, sorted(set(veri.oda_idleri)))

        cursor.execute("SELECT r.rol_adi, k.aktif_mi FROM kullanicilar k JOIN roller r ON k.rol_id = r.rol_id WHERE k.kullanici_id = %s FOR UPDATE OF k;", (kullanici_id,))
        hedef = cursor.fetchone()
        
        if hedef is None:
            raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı.")

        hedef_rol, mevcut_durum = hedef
        if hedef_rol == "ADMIN":
            raise HTTPException(
                status_code=403,
                detail="ADMIN kullanıcısının aktiflik durumu değiştirilemez."
            )

        if hiyerarsi_ihlali_var_mi(islem_yapan[0] if islem_yapan else None, hedef_rol):
            raise HTTPException(status_code=403, detail=HIYERARSI_MESAJI)

        # YENİ MANTIK: Mevcut durum neyse tam tersini yap (Toggle)
        yeni_durum = not mevcut_durum

        psikolog_mu = psikolog_rolu_mu(hedef_rol)
        istenen_odalar = sorted(set((veri.oda_idleri if veri is not None else None) or []))
        psikolog_aktiflesiyor = psikolog_mu and yeni_durum
        psikolog_pasiflesiyor = psikolog_mu and not yeni_durum

        if istenen_odalar and not psikolog_aktiflesiyor:
            raise HTTPException(status_code=422, detail="Oda seçimi yalnızca psikolog aktifleştirilirken yapılır.")

        if psikolog_aktiflesiyor:
            # Her psikologun en az bir (aktif) odası olmalı; pasife alınırken odalar kaldırıldığı için yeniden seçilir.
            if not istenen_odalar:
                raise HTTPException(status_code=422, detail="Psikolog aktifleştirilirken en az bir görüşme odası seçilmelidir.")
            cursor.execute("SELECT oda_id FROM odalar WHERE oda_id = ANY(%s) AND aktif_mi = TRUE;", (istenen_odalar,))
            if {k[0] for k in cursor.fetchall()} != set(istenen_odalar):
                raise HTTPException(status_code=422, detail="Seçilen odalardan biri bulunamadı veya aktif değil.")
            etkinlik_oda_atama_kilitlerini_al(
                cursor, istenen_odalar
            )
            cihaz_rezervasyonlu_odalari_denetle(cursor, istenen_odalar)
            oda_etkinlikli_odalari_denetle(cursor, istenen_odalar)
        elif psikolog_pasiflesiyor:
            # Oda boşa düşeceği için bugün ve sonrasındaki planlı randevular önce sonuçlandırılmalı ya da iptal edilmeli. Dünden önceki kayıtlar engellemez.
            cursor.execute(
                "SELECT COUNT(*) FROM randevular r JOIN personel p ON p.personel_id = r.psikolog_id "
                "WHERE p.kullanici_id = %s AND r.durum = 'PLANLANDI' AND r.baslangic_zamani >= CURRENT_DATE;",
                (kullanici_id,),
            )
            planli = cursor.fetchone()[0]
            if planli:
                raise HTTPException(
                    status_code=409,
                    detail=f"Bu psikologun bugün ve sonrası için {planli} planlı randevusu var. Pasife almadan önce {PLANLI_RANDEVU_COZUMU}",
                )

        # Tek aktiflik bilgisi kullanıcı satırındadır (personel görünümü bunu okur).
        cursor.execute("UPDATE kullanicilar SET aktif_mi = %s WHERE kullanici_id = %s;", (yeni_durum, kullanici_id))

        danisan_sayisi = 0
        if psikolog_mu:
            # Bir danışanın tek psikoloğu vardır: psikolog pasife alınınca kendi danışanları da pasife alınır (randevu geçmişi korunur).
            # Yeniden aktifleşince yalnızca BU YÜZDEN pasifleşenler geri açılır; daha önce elle pasife alınmış danışanlar pasif kalır.
            if psikolog_pasiflesiyor:
                cursor.execute(
                    "UPDATE danisan_kodlari SET aktif_mi = FALSE, psikolog_pasifligi_nedeniyle_pasif = TRUE "
                    "WHERE aktif_mi = TRUE AND olusturan_psikolog_id IN (SELECT personel_id FROM personel WHERE kullanici_id = %s);",
                    (kullanici_id,),
                )
            else:
                cursor.execute(
                    "UPDATE danisan_kodlari SET aktif_mi = TRUE, psikolog_pasifligi_nedeniyle_pasif = FALSE "
                    "WHERE psikolog_pasifligi_nedeniyle_pasif = TRUE AND olusturan_psikolog_id IN (SELECT personel_id FROM personel WHERE kullanici_id = %s);",
                    (kullanici_id,),
                )
            danisan_sayisi = cursor.rowcount
            if danisan_sayisi:
                ayrintili_kayit_yaz(cursor, islem_yapan_id, "UPDATE", "danisan_kodlari", None, neden="psikolog pasife alındı" if psikolog_pasiflesiyor else "psikolog aktif edildi",
                                    etkilenen_danisan=danisan_sayisi, aktif_mi="pasif" if psikolog_pasiflesiyor else "aktif", psikolog_kullanici_id=kullanici_id)

            # Pasifte oda ataması kalkar; aktifleşirken seçilen odalar yazılır (eski artık kayıtlar varsa değiştirilir).
            onceki_odalar = psikolog_odalarini_oku(cursor, kullanici_id)
            cursor.execute("DELETE FROM psikolog_odalar WHERE kullanici_id = %s;", (kullanici_id,))
            for oda_id in istenen_odalar:
                cursor.execute("INSERT INTO psikolog_odalar (kullanici_id, oda_id) VALUES (%s, %s);", (kullanici_id, oda_id))
            psikolog_oda_degisikligini_yaz(cursor, islem_yapan_id, kullanici_id, onceki_odalar)

        durum_ayrintisi = {"rol": hedef_rol}
        if psikolog_mu and danisan_sayisi:
            durum_ayrintisi["etkilenen_danisan"] = danisan_sayisi
        durum_degisikligi_yaz(cursor, islem_yapan_id, "UPDATE", "kullanicilar", kullanici_id, onceki={"aktif_mi": mevcut_durum}, yeni={"aktif_mi": yeni_durum}, **durum_ayrintisi)
        conn.commit()

        yanit = {"mesaj": "Durum başarıyla güncellendi.", "kullanici_id": kullanici_id, "yeni_durum": yeni_durum}
        if psikolog_pasiflesiyor:
            yanit["pasife_alinan_danisan"] = danisan_sayisi
        elif psikolog_aktiflesiyor:
            yanit["aktif_edilen_danisan"] = danisan_sayisi
        return yanit
    except HTTPException:
        if conn is not None: conn.rollback()
        raise
    except DeadlockDetected:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=503, detail="İşlem eşzamanlı yoğunluk nedeniyle tamamlanamadı. Lütfen tekrar deneyin.")
    except Exception:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=500, detail="İşlem sırasında beklenmeyen bir sunucu hatası oluştu.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


# (yöntem, yol, uç fonksiyonu, yetki parametresi, gereken yetki, ek yol ayarları): yetki bağımlılığı kayıt sırasında eklenir.
# Gereken yetki: "IZIN" (izin_kontrol), ("A", "B") (izin_kontrol_biri: biri yeter), Hepsi("A", "B") (izin_kontrol_tumu: hepsi gerekir)
# veya None (yalnızca oturum açmış olmak).
UCLAR = [
    ("POST", "/api/kullanicilar", kullanici_olustur, "kullanici_id", "KULLANICI_OLUSTUR", {"status_code": 201}),
    ("GET", "/api/kullanicilar/musait-kullanici-adi", musait_kullanici_adi, "kullanici_id", "KULLANICI_OLUSTUR", {}),
    ("GET", "/api/kullanicilar/{kullanici_id}/ogrenci-kayit-durumu", kullanici_ogrenci_kayit_durumu, "islem_yapan_id", "ROL_ATAMA_DEGISTIRME", {}),
    ("PATCH", "/api/kullanicilar/{kullanici_id}/rol", kullanici_rol_degistir, "islem_yapan_id", "ROL_ATAMA_DEGISTIRME", {}),
    ("POST", "/api/kullanicilar/{kullanici_id}/parola-sifirla", kullanici_parola_sifirla, "islem_yapan_id", "KULLANICI_PAROLA_SIFIRLA", {}),
    ("PATCH", "/api/kullanicilar/{kullanici_id}/durum-degistir", kullanici_durum_degistir, "islem_yapan_id", "KULLANICI_PASIFLESTIR", {}),
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
