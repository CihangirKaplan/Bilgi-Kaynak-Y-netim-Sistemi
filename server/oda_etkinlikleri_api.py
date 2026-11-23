"""Oda Etkinlikleri CRUD API."""

from contextlib import contextmanager
from datetime import date, datetime, time, timedelta

from server.vt_baglanti import vt_baglan
from psycopg2.extras import RealDictCursor
from fastapi import APIRouter, Depends, HTTPException

from server.denetim import ayrintili_kayit_yaz
from server.oda_etkinlikleri_kurallari import oda_cakismasi_bul, oda_kilidini_al
from server.oda_etkinlikleri_modelleri import (
    OdaEtkinlikOlusturModeli,
    OdaEtkinlikGuncelleModeli,
    etkinlik_gunluk_araliklari,
    etkinlik_oturumlarini_dogrula,
)

# Denetim kaydına yazılan etkinlik alanları: yalnızca kimlik, sayı ve zaman. Etkinlik adı serbest metindir (kişi adı içerebilir);
# FR-008 gereği yazılmaz, yalnızca değişip değişmediği belirtilir.
DENETIME_YAZILAN_ALANLAR = (
    "oda_id", "organize_eden_personel_id", "katilimci_sayisi", "baslangic_zamani", "bitis_zamani",
)


def _denetim_ozeti(kayit):
    return {alan: kayit.get(alan) for alan in DENETIME_YAZILAN_ALANLAR}


def psikologa_atanmis_oda_kontrol(cursor, oda_id):
    """Aktif psikoloğa atanmış odalarda etkinlik işlemini engelle."""
    cursor.execute(
        """
        SELECT 1
        FROM psikolog_odalar po
        JOIN kullanicilar k
          ON k.kullanici_id = po.kullanici_id
        WHERE po.oda_id = %s
          AND k.aktif_mi IS TRUE
        LIMIT 1
        """,
        (oda_id,),
    )

    if cursor.fetchone() is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                "Bu oda aktif bir psikoloğa atanmıştır. "
                "Oda etkinliği için başka bir oda seçiniz."
            ),
        )


def router_olustur(izin_kontrol, vt_ayarlari):
    router = APIRouter(prefix="/api/oda-etkinlikleri")

    @contextmanager
    def islem():
        conn = vt_baglan(vt_ayarlari)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def etkinlik_getir(cursor, etkinlik_id, kilitle=False):
        cursor.execute(
            """
            SELECT *
            FROM oda_etkinlikleri
            WHERE etkinlik_id = %s
            """ + (" FOR UPDATE" if kilitle else ""),
            (etkinlik_id,),
        )
        kayit = cursor.fetchone()
        if kayit is None:
            raise HTTPException(404, "Etkinlik bulunamadı.")
        return dict(kayit)

    def oda_ve_personel_kontrol(
        cursor, oda_id, personel_id, katilimci,
        eski_personel_id=None,
    ):
        cursor.execute(
            """
            SELECT kapasite
            FROM odalar
            WHERE oda_id = %s AND aktif_mi = TRUE
            """,
            (oda_id,),
        )
        oda = cursor.fetchone()
        if oda is None:
            raise HTTPException(422, "Seçilen oda bulunamadı veya pasif.")

        cursor.execute(
            """
            SELECT 1
            FROM personel
            WHERE personel_id = %s AND aktif_mi = TRUE
            """,
            (personel_id,),
        )
        if cursor.fetchone() is None:
            raise HTTPException(422, "Geçerli ve aktif bir personel seçilmeli.")

        # Mevcut Admin atamalarını koru, yeni Admin seçimini engelle.
        if personel_id != eski_personel_id:
            cursor.execute(
                """
                SELECT 1
                FROM personel p
                JOIN kullanicilar k
                  ON k.kullanici_id = p.kullanici_id
                JOIN roller r
                  ON r.rol_id = k.rol_id
                WHERE p.personel_id = %s
                  AND p.aktif_mi IS TRUE
                  AND k.aktif_mi IS TRUE
                  AND UPPER(TRIM(r.rol_adi)) <> 'ADMIN'
                """,
                (personel_id,),
            )
            if cursor.fetchone() is None:
                raise HTTPException(
                    422,
                    "Düzenleyen personel olarak aktif ve "
                    "Admin olmayan bir personel seçilmelidir.",
                )

    def oda_kilitle(cursor, oda_idleri):
        # Kilitler küçük oda kimliğinden büyüğe alınır (kilitlenme/deadlock olmasın).
        for oda_id in sorted(set(oda_idleri)):
            oda_kilidini_al(cursor, oda_id)

    def cakisma_kontrol(cursor, oda_id, baslangic, bitis, haric=None):
        cakisma = oda_cakismasi_bul(
            cursor, oda_id, baslangic, bitis, haric
        )
        if cakisma:
            tur = {
                "randevu": "randevu",
                "cihaz": "cihaz rezervasyonu",
                "etkinlik": "oda etkinliği",
            }[cakisma]
            raise HTTPException(
                409,
                f"Seçilen oda bu saatlerde başka bir {tur} nedeniyle dolu.",
            )

    def gunleri_kaydet(cursor, etkinlik_id, araliklar):
        for ilk, son in araliklar:
            cursor.execute(
                """
                INSERT INTO oda_etkinlik_gunleri
                    (etkinlik_id, baslangic_zamani, bitis_zamani)
                VALUES (%s, %s, %s)
                """,
                (etkinlik_id, ilk, son),
            )

    def denetim(cursor, kullanici_id, olay, etkinlik_id, **ayrinti):
        """Denetim kaydı (aynı işlemde): ne yapıldığı ve etkilenen oda/zaman bilgisi."""
        ayrintili_kayit_yaz(cursor, kullanici_id, olay, "oda_etkinlikleri", etkinlik_id, **ayrinti)

    @router.get("/secenekler")
    def etkinlik_secenekleri(
        kullanici_id: int = Depends(
            izin_kontrol("ODA_ETKINLIK_GORUNTULE")
        ),
    ):
        with islem() as cursor:
            cursor.execute("""
                SELECT o.oda_id, o.oda_adi, o.kapasite
                FROM odalar o
                WHERE o.aktif_mi = TRUE
                  AND NOT EXISTS (
                      SELECT 1
                      FROM psikolog_odalar po
                      JOIN kullanicilar k
                        ON k.kullanici_id = po.kullanici_id
                      WHERE po.oda_id = o.oda_id
                        AND k.aktif_mi IS TRUE
                  )
                ORDER BY o.oda_adi, o.oda_id
            """)
            odalar = [dict(k) for k in cursor.fetchall()]

            cursor.execute("""
                SELECT
                    p.personel_id,
                    k.kullanici_adi,
                    p.personel_kodu
                FROM personel p
                JOIN kullanicilar k ON k.kullanici_id = p.kullanici_id
                JOIN roller r ON r.rol_id = k.rol_id
                WHERE p.aktif_mi = TRUE
                  AND k.aktif_mi = TRUE
                  AND UPPER(TRIM(r.rol_adi)) <> 'ADMIN'
                ORDER BY k.kullanici_adi, p.personel_id
            """)
            personeller = [dict(k) for k in cursor.fetchall()]

            cursor.execute("""
                SELECT COALESCE(ri.izin_var, 0) AS yonetebilir
                FROM kullanicilar k
                JOIN izinler i ON i.izin_adi = 'ODA_ETKINLIK_YONET'
                LEFT JOIN rol_izinleri ri
                  ON ri.rol_id = k.rol_id
                 AND ri.izin_id = i.izin_id
                WHERE k.kullanici_id = %s
            """, (kullanici_id,))
            kayit = cursor.fetchone()
            yonetebilir = bool(kayit and kayit["yonetebilir"] == 1)

        return {
            "odalar": odalar,
            "personeller": personeller,
            "yonetebilir": yonetebilir,
        }

    @router.get("")
    def etkinlikleri_listele(
        baslangic: date | None = None,
        bitis: date | None = None,
        kullanici_id: int = Depends(
            izin_kontrol("ODA_ETKINLIK_GORUNTULE")
        ),
    ):
        if baslangic and bitis and baslangic > bitis:
            raise HTTPException(422, "Geçersiz tarih aralığı.")

        gun_kosullari = ["g.etkinlik_id = e.etkinlik_id"]
        parametreler = []

        if baslangic:
            gun_kosullari.append("g.bitis_zamani > %s")
            parametreler.append(
                datetime.combine(baslangic, time.min)
            )
        if bitis:
            gun_kosullari.append("g.baslangic_zamani < %s")
            parametreler.append(
                datetime.combine(bitis + timedelta(days=1), time.min)
            )

        where = ""
        if baslangic or bitis:
            where = (
                "WHERE EXISTS ("
                "SELECT 1 FROM oda_etkinlik_gunleri g WHERE "
                + " AND ".join(gun_kosullari)
                + ")"
            )

        with islem() as cursor:
            cursor.execute(
                f"""
                SELECT e.*, o.oda_adi,
                       COALESCE(
                           (
                               SELECT json_agg(
                                   json_build_object(
                                       'baslangic_zamani',
                                       g.baslangic_zamani,
                                       'bitis_zamani',
                                       g.bitis_zamani
                                   )
                                   ORDER BY g.baslangic_zamani
                               )
                               FROM oda_etkinlik_gunleri g
                               WHERE g.etkinlik_id = e.etkinlik_id
                           ),
                           '[]'::json
                       ) AS gunler
                FROM oda_etkinlikleri e
                JOIN odalar o ON o.oda_id = e.oda_id
                {where}
                ORDER BY e.baslangic_zamani DESC, e.etkinlik_id DESC
                """,
                tuple(parametreler),
            )
            return {"etkinlikler": [dict(r) for r in cursor.fetchall()]}

    @router.post("", status_code=201)
    def etkinlik_olustur(
        veri: OdaEtkinlikOlusturModeli,
        kullanici_id: int = Depends(
            izin_kontrol("ODA_ETKINLIK_YONET")
        ),
    ):
        with islem() as cursor:
            oda_kilitle(cursor, [veri.oda_id])
            psikologa_atanmis_oda_kontrol(
                cursor, veri.oda_id
            )
            oda_ve_personel_kontrol(
                cursor, veri.oda_id,
                veri.organize_eden_personel_id,
                veri.katilimci_sayisi,
            )
            if veri.gunler is not None:
                araliklar = etkinlik_oturumlarini_dogrula([
                    (g.baslangic_zamani, g.bitis_zamani)
                    for g in veri.gunler
                ])
            else:
                araliklar = etkinlik_gunluk_araliklari(
                    veri.baslangic_zamani, veri.bitis_zamani
                )

            # Ana kayıt tüm etkinliğin ilk ve son zamanını tutar.
            # Gerçek oda dolulukları yalnızca günlük tablodadır.
            genel_bas = araliklar[0][0]
            genel_bit = araliklar[-1][1]

            for ilk, son in araliklar:
                cakisma_kontrol(cursor, veri.oda_id, ilk, son)
            cursor.execute(
                """
                INSERT INTO oda_etkinlikleri (
                    oda_id, organize_eden_personel_id,
                    etkinlik_adi, katilimci_sayisi,
                    baslangic_zamani, bitis_zamani,
                    iptal_edildi_mi
                )
                VALUES (%s, %s, %s, %s, %s, %s, FALSE)
                RETURNING etkinlik_id
                """,
                (
                    veri.oda_id, veri.organize_eden_personel_id,
                    veri.etkinlik_adi.strip(), veri.katilimci_sayisi,
                    genel_bas, genel_bit,
                ),
            )
            etkinlik_id = cursor.fetchone()["etkinlik_id"]
            gunleri_kaydet(cursor, etkinlik_id, araliklar)
            denetim(
                cursor, kullanici_id, "CREATE", etkinlik_id,
                yeni=_denetim_ozeti({
                    "oda_id": veri.oda_id, "organize_eden_personel_id": veri.organize_eden_personel_id,
                    "katilimci_sayisi": veri.katilimci_sayisi, "baslangic_zamani": genel_bas, "bitis_zamani": genel_bit,
                }),
                gun_sayisi=len(araliklar),
            )
            return {"etkinlik_id": etkinlik_id, "durum": "basarili"}

    @router.patch("/{etkinlik_id}")
    def etkinlik_guncelle(
        etkinlik_id: int,
        veri: OdaEtkinlikGuncelleModeli,
        kullanici_id: int = Depends(
            izin_kontrol("ODA_ETKINLIK_YONET")
        ),
    ):
        degisiklikler = veri.model_dump(exclude_unset=True)
        gunler_gonderildi = "gunler" in degisiklikler
        degisiklikler.pop("gunler", None)

        if not degisiklikler and not gunler_gonderildi:
            raise HTTPException(422, "Güncellenecek alan belirtilmeli.")

        if gunler_gonderildi:
            if veri.gunler is None:
                raise HTTPException(
                    422, "Etkinlik günleri boş olamaz."
                )
            if (
                "baslangic_zamani" in degisiklikler
                or "bitis_zamani" in degisiklikler
            ):
                raise HTTPException(
                    422,
                    "Günler listesi ile başlangıç/bitiş alanları "
                    "aynı istekte birlikte gönderilemez.",
                )

        for alan, deger in degisiklikler.items():
            if deger is None and alan != "katilimci_sayisi":
                raise HTTPException(422, f"{alan} boş olamaz.")

        with islem() as cursor:
            # Önce mevcut oda bilgisini satır kilidi almadan oku.
            ilk = etkinlik_getir(cursor, etkinlik_id, kilitle=False)

            hedef_oda = degisiklikler.get("oda_id", ilk["oda_id"])

            # Tüm oda kilitleri satır kilidinden ÖNCE,
            # küçük oda ID'sinden büyüğe alınır.
            oda_kilitle(cursor, [ilk["oda_id"], hedef_oda])

            mevcut = etkinlik_getir(cursor, etkinlik_id, kilitle=True)

            # Kilit beklerken kayıt başka bir odaya taşınmış olabilir.
            if mevcut["oda_id"] != ilk["oda_id"]:
                raise HTTPException(
                    409,
                    "Etkinliğin odası başka bir işlemde değişti. "
                    "Listeyi yenileyip tekrar deneyiniz.",
                )

            if mevcut["iptal_edildi_mi"]:
                raise HTTPException(409, "İptal edilen etkinlik düzenlenemez.")

            yeni = {
                **{alan: mevcut[alan] for alan in (
                    "oda_id",
                    "organize_eden_personel_id",
                    "etkinlik_adi",
                    "katilimci_sayisi",
                    "baslangic_zamani",
                    "bitis_zamani",
                )},
                **degisiklikler,
            }

            if gunler_gonderildi:
                yeni_araliklar = etkinlik_oturumlarini_dogrula([
                    (g.baslangic_zamani, g.bitis_zamani)
                    for g in veri.gunler
                ])
                yeni["baslangic_zamani"] = yeni_araliklar[0][0]
                yeni["bitis_zamani"] = yeni_araliklar[-1][1]

            if yeni["baslangic_zamani"] >= yeni["bitis_zamani"]:
                raise HTTPException(
                    422, "Bitiş zamanı başlangıçtan sonra olmalıdır."
                )

            zaman_degisti = gunler_gonderildi or bool(
                {"baslangic_zamani", "bitis_zamani"}
                & degisiklikler.keys()
            )

            if gunler_gonderildi:
                araliklar = yeni_araliklar
            elif zaman_degisti:
                try:
                    araliklar = etkinlik_gunluk_araliklari(
                        yeni["baslangic_zamani"],
                        yeni["bitis_zamani"],
                    )
                except ValueError as hata:
                    raise HTTPException(422, str(hata)) from hata
            else:
                cursor.execute(
                    """
                    SELECT baslangic_zamani, bitis_zamani
                    FROM oda_etkinlik_gunleri
                    WHERE etkinlik_id = %s
                    ORDER BY baslangic_zamani
                    """,
                    (etkinlik_id,),
                )
                araliklar = [
                    (r["baslangic_zamani"], r["bitis_zamani"])
                    for r in cursor.fetchall()
                ]
                if not araliklar:
                    raise HTTPException(
                        409,
                        "Etkinliğin günlük kayıtları bulunamadı.",
                    )

            # Oda kilitleri işlem başında zaten alındı.
            psikologa_atanmis_oda_kontrol(
                cursor, yeni["oda_id"]
            )
            oda_ve_personel_kontrol(
                cursor, yeni["oda_id"],
                yeni["organize_eden_personel_id"],
                yeni["katilimci_sayisi"],
                eski_personel_id=mevcut["organize_eden_personel_id"],
            )
            for ilk, son in araliklar:
                cakisma_kontrol(
                    cursor, yeni["oda_id"], ilk, son,
                    etkinlik_id,
                )

            cursor.execute(
                """
                UPDATE oda_etkinlikleri
                SET oda_id = %s,
                    organize_eden_personel_id = %s,
                    etkinlik_adi = %s,
                    katilimci_sayisi = %s,
                    baslangic_zamani = %s,
                    bitis_zamani = %s
                WHERE etkinlik_id = %s
                """,
                (
                    yeni["oda_id"], yeni["organize_eden_personel_id"],
                    yeni["etkinlik_adi"].strip(),
                    yeni["katilimci_sayisi"],
                    yeni["baslangic_zamani"], yeni["bitis_zamani"],
                    etkinlik_id,
                ),
            )
            if zaman_degisti:
                cursor.execute(
                    "DELETE FROM oda_etkinlik_gunleri "
                    "WHERE etkinlik_id = %s",
                    (etkinlik_id,),
                )
                gunleri_kaydet(cursor, etkinlik_id, araliklar)

            denetim(
                cursor, kullanici_id, "UPDATE", etkinlik_id,
                degisen_alanlar=sorted(set(degisiklikler) | ({"gunler"} if gunler_gonderildi else set())),
                onceki=_denetim_ozeti(mevcut), yeni=_denetim_ozeti(yeni),
                gun_sayisi=len(araliklar),
            )
            return {"etkinlik_id": etkinlik_id, "durum": "basarili"}

    @router.patch("/{etkinlik_id}/iptal")
    def etkinlik_iptal(
        etkinlik_id: int,
        kullanici_id: int = Depends(
            izin_kontrol("ODA_ETKINLIK_YONET")
        ),
    ):
        with islem() as cursor:
            mevcut = etkinlik_getir(cursor, etkinlik_id, kilitle=True)
            if mevcut["iptal_edildi_mi"]:
                raise HTTPException(409, "Etkinlik zaten iptal edilmiş.")

            cursor.execute(
                """
                UPDATE oda_etkinlikleri
                SET iptal_edildi_mi = TRUE
                WHERE etkinlik_id = %s
                """,
                (etkinlik_id,),
            )
            denetim(cursor, kullanici_id, "CANCEL", etkinlik_id, onceki=_denetim_ozeti(mevcut))
            return {"etkinlik_id": etkinlik_id, "durum": "iptal_edildi"}

    return router
