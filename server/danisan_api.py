"""Danışan kodu uçları: sıradaki kod, oluşturma, listeleme, durum ve bilgi güncelleme. `server/sunucu.py` içinden ayrıldı."""
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from server.denetim import durum_degisikligi_yaz
from server.modeller import DanisanBilgiModeli, YAS_GRUPLARI
from server.ortak_sabitler import PLANLI_RANDEVU_COZUMU
from server.ortak_yardimcilar import psikolog_rolu_mu
from server.vt_ayarlari import VT_AYARLARI
from server.vt_baglanti import vt_baglan
from server.yetki_baglama import yetkiyle_bagla


def otomatik_danisan_kodu_uret(cursor, yil=None, kilitle=True) -> str:
    """Yıl bazlı sıradaki danışan kodu: DAN-<yıl>-<sıra>. Sıra, o yılın en büyük kodunun bir fazlasıdır; her yıl 0001'den başlar.

    kilitle=True (kayıt anı): aynı yılın kod üretimi transaction sonuna kadar kilitlenir, böylece iki kayıt aynı kodu almaz.
    kilitle=False (önizleme): kilit alınmaz ve hiçbir sayaç tüketilmez; ekran açılıp kapanınca numara atlamaz."""
    yil = int(yil or datetime.now().year)
    if kilitle:
        cursor.execute("SELECT pg_advisory_xact_lock(%s, %s);", (4210, yil))
    cursor.execute(
        "SELECT COALESCE(MAX(CAST(SUBSTRING(danisan_kod_id FROM %s) AS INTEGER)), 0) + 1 FROM danisan_kodlari WHERE danisan_kod_id ~ %s;",
        (f"^DAN-{yil}-([0-9]+)$", f"^DAN-{yil}-[0-9]+$"),
    )
    return f"DAN-{yil}-{cursor.fetchone()[0]:04d}"


def siradaki_danisan_kodunu_ver(kullanici_id: int | None = None):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        siradaki_kod = otomatik_danisan_kodu_uret(cursor, kilitle=False)     # önizleme: kilit ve sayaç tüketimi yok
        return {"siradaki_kod": siradaki_kod}
    except Exception:
        # Uydurma bir kod (DAN-yıl-0001) dönmek gerçek koda çarpabilir; kod alınamazsa açıkça hata verilir.
        raise HTTPException(status_code=503, detail="Sıradaki danışan kodu şu an alınamadı. Kod kayıt sırasında otomatik atanır.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


# istisna_turu yalnızca bu üç değerden biri olabilir; serbest metin (ad, tanı vb.) kişisel veri sızıntısına yol açar.
IZINLI_ISTISNA_TURLERI = ("YOK", "KANSER", "SEHIT_GAZI")


def danisan_kodu_olustur(
    ucretli_mi: bool = True,
    istisna_turu: str = "YOK",
    psikolog_id: int | None = Query(None, gt=0),
    yas_grubu: str = Query(...),
    kullanici_id: int | None = None,
):
    """Yeni danışan kodu üretir.

    Psikolog hesabında danışan kendi adına açılır (psikolog_id yok sayılır). Diğer roller (admin, danışma vb.)
    danışanın hangi psikologa ait olduğunu psikolog_id ile belirtmek zorundadır; böylece danışan sahipsiz kalmaz.
    """
    # Doğrulama veritabanına bağlanmadan önce yapılır; gelen metin hata mesajına da yazılmaz.
    if istisna_turu not in IZINLI_ISTISNA_TURLERI:
        raise HTTPException(status_code=422, detail="Geçersiz istisna türü. İzinli değerler: " + ", ".join(IZINLI_ISTISNA_TURLERI) + ".")
    if ucretli_mi and istisna_turu != "YOK":
        raise HTTPException(status_code=422, detail="Ücretli danışan için istisna türü YOK olmalıdır.")
    if not ucretli_mi and istisna_turu == "YOK":
        raise HTTPException(status_code=422, detail="Ücretsiz danışan için istisna türü (Kanser / Şehit-Gazi) seçilmelidir.")
    # Kapalı listeler: gelen metin doğrulanır ve hata mesajına yazılmaz (FR-008)
    if yas_grubu not in YAS_GRUPLARI:
        raise HTTPException(status_code=422, detail="Geçersiz yaş grubu. İzinli değerler: " + ", ".join(YAS_GRUPLARI) + ".")
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        # 1. İşlemi yapanın rolünü ve (varsa) aktif personel kaydını öğreniyoruz
        cursor.execute(
            "SELECT p.personel_id, UPPER(r.rol_adi) FROM kullanicilar k JOIN roller r ON k.rol_id = r.rol_id "
            "LEFT JOIN personel p ON p.kullanici_id = k.kullanici_id AND p.aktif_mi = TRUE "
            "WHERE k.kullanici_id = %s;",
            (kullanici_id,),
        )
        kimlik = cursor.fetchone()
        personel_id, rol_adi = (kimlik[0], kimlik[1]) if kimlik else (None, "")

        if psikolog_rolu_mu(rol_adi):
            # Psikolog danışanı yalnızca kendi adına açabilir
            if personel_id is None:
                raise HTTPException(status_code=403, detail="Personel/Psikolog kaydınız bulunamadığı için danışan kodu oluşturamazsınız.")
            olusturan_psikolog_id = personel_id
        else:
            # Diğer roller danışanı hangi psikologa açtığını belirtmelidir
            if psikolog_id is None:
                raise HTTPException(status_code=422, detail="Danışan için bir psikolog seçilmelidir.")
            cursor.execute(
                "SELECT p.personel_id FROM personel p JOIN kullanicilar k ON p.kullanici_id = k.kullanici_id "
                "JOIN roller r ON k.rol_id = r.rol_id "
                "WHERE p.personel_id = %s AND p.aktif_mi = TRUE AND k.aktif_mi = TRUE AND UPPER(r.rol_adi) = 'PSIKOLOG';",
                (psikolog_id,),
            )
            if not cursor.fetchone():
                raise HTTPException(status_code=422, detail="Seçilen psikolog bulunamadı.")
            olusturan_psikolog_id = psikolog_id

        # 2. Otomatik danışan kodunu üret
        yeni_kod = otomatik_danisan_kodu_uret(cursor)

        # 3. Veritabanına oluşturan psikoloğun ID'siyle birlikte kaydediyoruz
        cursor.execute(
            """
            INSERT INTO danisan_kodlari (danisan_kod_id, ucretli_mi, istisna_turu, aktif_mi, olusturan_psikolog_id, yas_grubu) 
            VALUES (%s, %s, %s, TRUE, %s, %s) 
            RETURNING danisan_kod_id, ucretli_mi, istisna_turu, aktif_mi, olusturulma_tarihi, olusturan_psikolog_id, yas_grubu;
            """, 
            (yeni_kod, ucretli_mi, istisna_turu, olusturan_psikolog_id, yas_grubu)
        )
        kayit = cursor.fetchone()

        # 4. Denetim (Audit) kaydı oluştur
        cursor.execute("INSERT INTO denetim_kayitlari (kullanici_id, olay_turu, hedef_tablo) VALUES (%s, %s, %s);", (kullanici_id, "CREATE", "danisan_kodlari"))
        conn.commit()

        return {
            "durum": "basarili", 
            "veri": {
                "danisan_kod_id": kayit[0],
                "ucretli_mi": kayit[1],
                "istisna_turu": kayit[2],
                "aktif_mi": kayit[3],
                "olusturulma_tarihi": kayit[4],
                "olusturan_psikolog_id": kayit[5],
                "yas_grubu": kayit[6] if len(kayit) > 6 else yas_grubu
            }
        }
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


def danisan_kodlari_listele(
    psikolog_id: int | None = Query(None, gt=0),
    pasifler_dahil: bool = Query(False),
    kullanici_id: int | None = None,
):
    """Aktif danışan kodlarını (kişisel veri içermez) döndürür; pasifler_dahil=true ise pasifleri de ekler.

    Psikolog yalnızca kendi oluşturduğu danışanları görür (psikolog_id parametresi yok sayılır). Diğer roller
    tüm danışanları görür; psikolog_id verilirse yalnızca o psikologun (personel_id) oluşturduğu danışanlar döner.
    """
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        # 1. Kullanıcının rolünü öğreniyoruz
        cursor.execute("SELECT r.rol_adi FROM kullanicilar k JOIN roller r ON k.rol_id = r.rol_id WHERE k.kullanici_id = %s;", (kullanici_id,))
        rol_kayit = cursor.fetchone()
        rol_adi = rol_kayit[0].upper() if rol_kayit else ""

        sutunlar = "danisan_kod_id, ucretli_mi, aktif_mi, istisna_turu, olusturulma_tarihi, olusturan_psikolog_id, yas_grubu"
        aktif_kosulu = "TRUE" if pasifler_dahil else "aktif_mi = TRUE"

        # 2. Psikolog yalnızca kendi oluşturduğu danışan kodlarını görür
        if psikolog_rolu_mu(rol_adi):
            cursor.execute("SELECT personel_id FROM personel WHERE kullanici_id = %s AND aktif_mi = TRUE;", (kullanici_id,))
            pers = cursor.fetchone()
            if not pers:
                raise HTTPException(status_code=403, detail="Personel kaydınız bulunamadı.")
            cursor.execute(
                f"SELECT {sutunlar} FROM danisan_kodlari "
                f"WHERE {aktif_kosulu} AND olusturan_psikolog_id = %s ORDER BY olusturulma_tarihi DESC;",
                (pers[0],),
            )
        elif psikolog_id is not None:
            # 3. Üst roller seçilen psikologun danışanlarını görür
            cursor.execute(
                f"SELECT {sutunlar} FROM danisan_kodlari "
                f"WHERE {aktif_kosulu} AND olusturan_psikolog_id = %s ORDER BY olusturulma_tarihi DESC;",
                (psikolog_id,),
            )
        else:
            # 4. Üst roller psikolog seçmediyse tüm aktif danışan kodlarını görür
            cursor.execute(
                f"SELECT {sutunlar} FROM danisan_kodlari "
                f"WHERE {aktif_kosulu} ORDER BY olusturulma_tarihi DESC;"
            )

        return [
            {
                "danisan_kod_id": k[0],
                "ucretli_mi": k[1],
                "aktif_mi": k[2],
                "istisna_turu": k[3],
                "olusturulma_tarihi": k[4].isoformat() if hasattr(k[4], "isoformat") else k[4],
                "olusturan_psikolog_id": k[5],
                "yas_grubu": k[6] if len(k) > 6 else None,
            }
            for k in cursor.fetchall()
        ]

    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


def danisan_durumunu_degistir(
    danisan_kod_id: str,
    aktif_mi: bool,
    kullanici_id: int | None = None,
):
    """Danışanı pasife alır ya da yeniden aktif eder.

    Danışan silinmez; randevu geçmişi korunur. Pasif danışana yeni randevu verilemez. Psikolog yalnızca kendi danışanının
    durumunu değiştirebilir. Geleceğe dönük planlanmış randevusu olan danışan pasife alınamaz (önce randevular iptal edilir).
    """
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT aktif_mi, olusturan_psikolog_id FROM danisan_kodlari WHERE danisan_kod_id = %s FOR UPDATE;",
            (danisan_kod_id,),
        )
        danisan = cursor.fetchone()
        if danisan is None:
            raise HTTPException(status_code=404, detail="Danışan bulunamadı.")

        cursor.execute("SELECT r.rol_adi FROM kullanicilar k JOIN roller r ON k.rol_id = r.rol_id WHERE k.kullanici_id = %s;", (kullanici_id,))
        rol = cursor.fetchone()
        if rol is not None and psikolog_rolu_mu(rol[0]):
            cursor.execute("SELECT personel_id FROM personel WHERE kullanici_id = %s AND aktif_mi = TRUE;", (kullanici_id,))
            personel = cursor.fetchone()
            if personel is None or personel[0] != danisan[1]:
                raise HTTPException(status_code=403, detail="Yalnızca kendi danışanınızın durumunu değiştirebilirsiniz.")

        if danisan[0] == aktif_mi:
            return {"durum": "basarili", "aktif_mi": aktif_mi, "mesaj": "Danışan zaten bu durumda."}

        if not aktif_mi:
            cursor.execute(
                "SELECT COUNT(*) FROM randevular WHERE danisan_kod_id = %s AND durum = 'PLANLANDI' AND baslangic_zamani >= CURRENT_DATE;",
                (danisan_kod_id,),
            )
            planli = cursor.fetchone()[0]
            if planli:
                raise HTTPException(
                    status_code=409,
                    detail=f"Bu danışanın bugün ve sonrası için {planli} planlı randevusu var. Pasife almadan önce {PLANLI_RANDEVU_COZUMU}",
                )
        elif danisan[1] is not None:
            # Danışanı aktifleştirmek için psikoloğu aktif bir psikolog olmalı; aksi halde danışan randevu alamaz (psikolog dönünce
            # psikolog pasifliği nedeniyle pasif olanlar zaten otomatik geri açılır).
            cursor.execute(
                "SELECT 1 FROM personel p JOIN kullanicilar k ON k.kullanici_id = p.kullanici_id JOIN roller r ON r.rol_id = k.rol_id "
                "WHERE p.personel_id = %s AND p.aktif_mi = TRUE AND k.aktif_mi = TRUE AND UPPER(r.rol_adi) = 'PSIKOLOG';",
                (danisan[1],),
            )
            if cursor.fetchone() is None:
                raise HTTPException(
                    status_code=409,
                    detail="Bu danışanın psikologu şu an pasif. Danışanı aktifleştirmeden önce psikoloğu aktifleştirin (danışan da otomatik açılır).",
                )

        # Elle yapılan durum değişikliği, "psikolog pasifliği nedeniyle pasif" işaretini temizler (psikolog dönünce otomatik geri açılmasın/kapanmasın).
        cursor.execute("UPDATE danisan_kodlari SET aktif_mi = %s, psikolog_pasifligi_nedeniyle_pasif = FALSE WHERE danisan_kod_id = %s;", (aktif_mi, danisan_kod_id))
        durum_degisikligi_yaz(cursor, kullanici_id, "UPDATE", "danisan_kodlari", None, onceki={"aktif_mi": danisan[0]}, yeni={"aktif_mi": aktif_mi}, danisan_kod_id=danisan_kod_id)
        conn.commit()
        return {"durum": "basarili", "aktif_mi": aktif_mi, "mesaj": "Danışan aktif edildi." if aktif_mi else "Danışan pasife alındı."}
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


def danisan_bilgilerini_guncelle(
    danisan_kod_id: str,
    bilgi: DanisanBilgiModeli,
    kullanici_id: int | None = None,
):
    """Danışanın yaş grubunu günceller (kapalı liste; serbest metin yoktur). Terapi türü randevuda tutulur.

    Psikolog yalnızca kendi danışanını güncelleyebilir. Geçmiş randevuların terapi türü değişmez; yetişkin olarak kaydedilince
    gelecekteki planlı randevulardaki oyun terapisi bireysel terapiye çevrilir.
    """
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        cursor.execute("SELECT olusturan_psikolog_id, yas_grubu FROM danisan_kodlari WHERE danisan_kod_id = %s FOR UPDATE;", (danisan_kod_id,))
        danisan = cursor.fetchone()
        if danisan is None:
            raise HTTPException(status_code=404, detail="Danışan bulunamadı.")

        cursor.execute("SELECT r.rol_adi FROM kullanicilar k JOIN roller r ON k.rol_id = r.rol_id WHERE k.kullanici_id = %s;", (kullanici_id,))
        rol = cursor.fetchone()
        if rol is not None and psikolog_rolu_mu(rol[0]):
            cursor.execute("SELECT personel_id FROM personel WHERE kullanici_id = %s AND aktif_mi = TRUE;", (kullanici_id,))
            personel = cursor.fetchone()
            if personel is None or personel[0] != danisan[0]:
                raise HTTPException(status_code=403, detail="Yalnızca kendi danışanınızın bilgilerini güncelleyebilirsiniz.")

        cursor.execute(
            "UPDATE danisan_kodlari SET yas_grubu = %s WHERE danisan_kod_id = %s;",
            (bilgi.yas_grubu, danisan_kod_id),
        )
        durum_degisikligi_yaz(cursor, kullanici_id, "UPDATE", "danisan_kodlari", None, onceki={"yas_grubu": danisan[1] if len(danisan) > 1 else None},
                              yeni={"yas_grubu": bilgi.yas_grubu}, danisan_kod_id=danisan_kod_id)
        guncellenen = 0
        if bilgi.yas_grubu == "YETISKIN":
            # Yetişkinde oyun terapisi yoktur: GELECEKTEKİ planlı randevular bireysel terapiye çevrilir.
            # Geçmiş (tamamlanan, gelmedi, iptal) randevular seansta yapılanın kaydı olduğu için değişmez.
            cursor.execute(
                "UPDATE randevular SET terapi_turu = 'BIREYSEL_TERAPI' WHERE danisan_kod_id = %s AND durum = 'PLANLANDI' "
                "AND baslangic_zamani > NOW() AND terapi_turu = 'OYUN_TERAPISI';",
                (danisan_kod_id,),
            )
            guncellenen = cursor.rowcount if isinstance(cursor.rowcount, int) and cursor.rowcount > 0 else 0
            if guncellenen:
                cursor.execute("INSERT INTO denetim_kayitlari (kullanici_id, olay_turu, hedef_tablo) VALUES (%s, %s, %s);", (kullanici_id, "UPDATE", "randevular"))
        conn.commit()
        return {"durum": "basarili", "yas_grubu": bilgi.yas_grubu, "guncellenen_randevu_sayisi": guncellenen,
                "mesaj": "Danışan bilgileri güncellendi."}
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


# (yöntem, yol, uç fonksiyonu, yetki parametresi, gereken yetki, ek yol ayarları): yetki bağımlılığı kayıt sırasında eklenir.
# Gereken yetki: "IZIN" (izin_kontrol), ("A", "B") (izin_kontrol_biri: biri yeter) veya None (yalnızca oturum açmış olmak).
UCLAR = [
    ("GET", "/api/randevular/siradaki-kod", siradaki_danisan_kodunu_ver, "kullanici_id", "RANDEVU_OLUSTUR", {}),
    ("POST", "/api/danisan-kodlari", danisan_kodu_olustur, "kullanici_id", "RANDEVU_OLUSTUR", {"status_code": 201}),
    ("GET", "/api/danisan-kodlari", danisan_kodlari_listele, "kullanici_id", "RANDEVU_OLUSTUR", {}),
    ("PATCH", "/api/danisan-kodlari/{danisan_kod_id}/durum", danisan_durumunu_degistir, "kullanici_id", "RANDEVU_OLUSTUR", {}),
    ("PATCH", "/api/danisan-kodlari/{danisan_kod_id}/bilgiler", danisan_bilgilerini_guncelle, "kullanici_id", "RANDEVU_OLUSTUR", {}),
]


def router_olustur(izin_kontrol) -> APIRouter:
    """Yetki bağımlılığı üreticileri `server.sunucu` içindeki kimlik doğrulama bağımlılıklarıdır."""
    router = APIRouter()
    for metod, yol, fonksiyon, parametre, yetki, ek in UCLAR:
        assert isinstance(yetki, str), yol          # bu modülde yalnızca tek izin tanımlı
        bagimlilik = izin_kontrol(yetki)
        router.add_api_route(yol, yetkiyle_bagla(fonksiyon, parametre, bagimlilik), methods=[metod], **ek)
    return router
