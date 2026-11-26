"""Randevu uçları: oluşturma, listeleme, doluluk, güncelleme, iptal ve durum işaretleme. `server/sunucu.py` içinden ayrıldı."""
from datetime import date
from datetime import datetime
from datetime import timedelta
from typing import Optional
import logging

from fastapi import APIRouter, HTTPException, Query, Response
from psycopg2.errors import DeadlockDetected
from psycopg2.errors import ExclusionViolation
import psycopg2

from server.denetim import durum_degisikligi_yaz
from server.modeller import RandevuDurumModeli, RandevuGuncelleModeli, RandevuIptalModeli, RandevuOlusturModeli, randevu_terapisini_belirle
from server.oda_etkinlikleri_kurallari import oda_cakismasi_bul, oda_kilidini_al
from server.ortak_yardimcilar import psikolog_rolu_mu
from server.vt_ayarlari import VT_AYARLARI
from server.vt_baglanti import vt_baglan
from server.yetki_baglama import yetkiyle_bagla


def psikolog_odasina_atanmis_mi(cursor, psikolog_id: int, oda_id: int) -> bool:
    """Oda, seçilen psikoloğa (personel_id) atanmış mı? Yetki kuralı sunucuda da uygulanır."""
    cursor.execute(
        "SELECT 1 FROM psikolog_odalar po "
        "JOIN personel p ON p.kullanici_id = po.kullanici_id "
        "WHERE p.personel_id = %s AND po.oda_id = %s;",
        (psikolog_id, oda_id),
    )
    return cursor.fetchone() is not None


def randevu_deadlock_yeniden_dene(fonksiyon):
    """QA-001 #186: Randevu deadlock durumunda sinirli yeniden deneme."""
    from functools import wraps
    import time

    @wraps(fonksiyon)
    def sarmalayici(*args, **kwargs):
        maksimum_deneme = 3

        for deneme in range(maksimum_deneme):
            try:
                return fonksiyon(*args, **kwargs)

            except DeadlockDetected:
                if deneme == maksimum_deneme - 1:
                    raise HTTPException(
                        status_code=503,
                        detail=(
                            "Randevu işlemi eşzamanlı yoğunluk nedeniyle "
                            "tamamlanamadı. Lütfen tekrar deneyin."
                        )
                    )

                time.sleep(0.1 * (deneme + 1))

    return sarmalayici


@randevu_deadlock_yeniden_dene
def randevu_olustur(randevu: RandevuOlusturModeli, kullanici_id: int | None = None):
    if randevu.baslangic_zamani >= randevu.bitis_zamani:
        raise HTTPException(status_code=422, detail="Başlangıç zamanı bitiş zamanından önce olmalıdır.")
    if hafta_sonuna_denk_mi(randevu.baslangic_zamani, randevu.bitis_zamani):
        raise HTTPException(status_code=422, detail=HAFTA_SONU_MESAJI)
    if gecmis_tarihe_mi(randevu.baslangic_zamani):
        raise HTTPException(status_code=422, detail=GECMIS_TARIH_MESAJI)

    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        # 1. Psikolog yetki kontrolü
        # Rolü veritabanından çekiyoruz
        cursor.execute("SELECT r.rol_adi FROM kullanicilar k JOIN roller r ON k.rol_id = r.rol_id WHERE k.kullanici_id = %s;", (kullanici_id,))
        rol = cursor.fetchone()

        if rol is not None and psikolog_rolu_mu(rol[0]):
            cursor.execute("SELECT personel_id FROM personel WHERE kullanici_id = %s AND aktif_mi = TRUE;", (kullanici_id,))
            personel = cursor.fetchone()
            if personel is None or personel[0] != randevu.psikolog_id:
                raise HTTPException(status_code=403, detail="Yalnızca kendi adınıza randevu oluşturabilirsiniz.")

        # DİKKAT EDİN BURASI DEĞİŞTİ: Artık otomatik kod üretmiyoruz, frontend'den gelen kodu kontrol ediyoruz.
        cursor.execute("SELECT yas_grubu, olusturan_psikolog_id FROM danisan_kodlari WHERE danisan_kod_id = %s AND aktif_mi = TRUE FOR SHARE;", (randevu.danisan_kod_id,))
        danisan_kaydi = cursor.fetchone()
        if danisan_kaydi is None:
            raise HTTPException(status_code=422, detail="Seçilen danışan kodu bulunamadı veya aktif değil.")
        # Danışan başka bir psikoloğa aitse ona randevu verilemez (kodlar sıralı ve tahmin edilebilir olduğundan sunucuda da denetlenir)
        if not danisan_psikologa_ait_mi(danisan_kaydi[1] if len(danisan_kaydi) > 1 else None, randevu.psikolog_id):
            raise HTTPException(status_code=422, detail=DANISAN_PSIKOLOG_MESAJI)
        # Randevunun terapi türü danışanın yaş grubuna uymalıdır (yetişkin: bireysel terapi; çocuk: seçilmeli)
        try:
            terapi_turu = randevu_terapisini_belirle(danisan_kaydi[0], getattr(randevu, "terapi_turu", None))
        except ValueError as hata:
            raise HTTPException(status_code=422, detail=str(hata))

        # 2. Psikolog kontrolü
        cursor.execute(
            "SELECT 1 FROM personel p "
            "JOIN kullanicilar k ON p.kullanici_id = k.kullanici_id "
            "JOIN roller r ON k.rol_id = r.rol_id "
            "WHERE p.personel_id = %s AND p.aktif_mi = TRUE AND k.aktif_mi = TRUE AND r.rol_adi ILIKE 'Psikolog';", 
            (randevu.psikolog_id,)
        )
        if cursor.fetchone() is None:
            raise HTTPException(status_code=422, detail="Geçerli ve aktif bir psikolog seçilmelidir.")

        # 3. Oda kontrolü
        cursor.execute("SELECT 1 FROM odalar WHERE oda_id = %s AND aktif_mi = TRUE;", (randevu.oda_id,))
        if cursor.fetchone() is None:
            raise HTTPException(status_code=422, detail="Oda bulunamadı veya aktif değil.")

        if not psikolog_odasina_atanmis_mi(cursor, randevu.psikolog_id, randevu.oda_id):
            raise HTTPException(status_code=422, detail="Seçilen oda bu psikoloğa atanmamış.")

        # Tüm oda kullanım türleriyle ortak transaction kontrolü.
        oda_kilidini_al(cursor, randevu.oda_id)
        cakisma = oda_cakismasi_bul(
            cursor,
            randevu.oda_id,
            randevu.baslangic_zamani,
            randevu.bitis_zamani,
        )
        if cakisma:
            raise HTTPException(
                status_code=409,
                detail=f"Oda bu saatlerde dolu (çakışan kayıt: {cakisma}).",
            )

        # 4. Çakışma kontrolü
        cursor.execute("SELECT 1 FROM randevular WHERE durum = 'PLANLANDI' AND (psikolog_id = %s OR oda_id = %s) AND baslangic_zamani < %s AND bitis_zamani > %s LIMIT 1;", (randevu.psikolog_id, randevu.oda_id, randevu.bitis_zamani, randevu.baslangic_zamani))
        if cursor.fetchone() is not None:
            raise HTTPException(status_code=409, detail="Seçilen psikolog veya oda bu saatlerde dolu.")

        # 5. Randevuyu kaydetme (ARTIK randevu.danisan_kod_id KULLANILIYOR)
        cursor.execute(
            "INSERT INTO randevular (danisan_kod_id, psikolog_id, oda_id, baslangic_zamani, bitis_zamani, durum, gorusme_tipi, terapi_turu) VALUES (%s, %s, %s, %s, %s, 'PLANLANDI', %s, %s) RETURNING randevu_id;", 
            (randevu.danisan_kod_id, randevu.psikolog_id, randevu.oda_id, randevu.baslangic_zamani, randevu.bitis_zamani, getattr(randevu, 'gorusme_tipi', 'YUZ_YUZE'), terapi_turu)
        )
        randevu_id = cursor.fetchone()[0]

        cursor.execute("INSERT INTO denetim_kayitlari (kullanici_id, olay_turu, hedef_tablo, hedef_kayit_id) VALUES (%s, %s, %s, %s);", (kullanici_id, "CREATE", "randevular", randevu_id))
        
        conn.commit()
        return {"durum": "basarili", "mesaj": "Randevu oluşturuldu.", "randevu_id": randevu_id}
    except ExclusionViolation:
        if conn is not None:
            conn.rollback()
        raise HTTPException(
            status_code=409,
            detail="Seçilen psikolog veya oda bu saatlerde dolu."
        )
    except DeadlockDetected:
        if conn is not None:
            conn.rollback()
        raise
    except HTTPException:
        if conn is not None:
            conn.rollback()
        raise
    except Exception as e:
        if conn is not None:
            conn.rollback()
        # İç hata metni (SQL, tablo adı vb.) istemciye sızdırılmaz; ayrıntı yalnızca sunucu günlüğüne yazılır.
        logging.getLogger(__name__).exception("Randevu oluşturulurken beklenmeyen hata: %s", e)
        raise HTTPException(
            status_code=500,
            detail="Randevu oluşturulurken bir hata oluştu. Lütfen daha sonra tekrar deneyin."
        )
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


RANDEVU_LISTE_SUTUNLARI = (
    "r.randevu_id, r.danisan_kod_id, r.psikolog_id, r.oda_id, r.baslangic_zamani, r.bitis_zamani, r.durum, "
    "r.olusturulma_tarihi, r.iptal_nedeni, r.iptal_notu, r.gorusme_tipi, r.terapi_turu"
)


RANDEVU_LISTE_ENCOK = 5000


def randevulari_listele(
    baslangic: Optional[date] = None,
    bitis: Optional[date] = None,
    durum: Optional[str] = None,
    danisan_kod_id: Optional[str] = None,
    oda_id: Optional[int] = None,
    limit: Optional[int] = None,
    offset: int = 0,
    response: Response = None,
    kullanici_id: int | None = None,
):
    """Randevu listesi. Süzgeçler isteğe bağlıdır; hiçbiri verilmezse eskisi gibi tüm kayıtlar döner.

    baslangic/bitis: başlangıç gününe göre (ikisi de dahil). limit verilirse en yeni randevular
    önce gelir ve toplam kayıt sayısı X-Toplam-Kayit başlığında bildirilir (liste kesilmişse
    istemci bunu kullanıcıya gösterebilsin diye).
    """
    if limit is not None:
        if limit < 1 or limit > RANDEVU_LISTE_ENCOK:
            raise HTTPException(status_code=422, detail=f"limit 1 ile {RANDEVU_LISTE_ENCOK} arasında olmalıdır.")
    if offset < 0:
        raise HTTPException(status_code=422, detail="offset negatif olamaz.")
    if baslangic is not None and bitis is not None and baslangic > bitis:
        raise HTTPException(status_code=422, detail="Başlangıç tarihi bitiş tarihinden sonra olamaz.")
    if durum is not None and durum not in ("PLANLANDI", "TAMAMLANDI", "GELMEDI", "IPTAL_EDILDI"):
        raise HTTPException(status_code=422, detail="Geçersiz randevu durumu.")

    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        # Rol adını net bir şekilde string olarak almak için tablodaki sütun adını garantiye alıyoruz
        cursor.execute("SELECT r.rol_adi FROM kullanicilar k JOIN roller r ON k.rol_id = r.rol_id WHERE k.kullanici_id = %s;", (kullanici_id,))
        rol_sonuc = cursor.fetchone()

        if not rol_sonuc:
            return []

        # Eğer rol_sonuc[0] sayı gelme ihtimaline karşı stringe çevirip .lower() yapıyoruz
        rol_adi = str(rol_sonuc[0]).lower() if rol_sonuc else ""

        # Serbest metin olan iptal notu yalnızca randevu düzenleme yetkisi olanlara gösterilir; diğerleri iptal NEDENİNİ (liste) görür.
        cursor.execute(
            "SELECT ri.izin_var FROM kullanicilar k JOIN rol_izinleri ri ON k.rol_id = ri.rol_id JOIN izinler i ON ri.izin_id = i.izin_id "
            "WHERE k.kullanici_id = %s AND i.izin_adi = 'RANDEVU_DUZENLE';",
            (kullanici_id,),
        )
        notu_gorebilir = (cursor.fetchone() or (0,))[0] == 1

        kosullar = []
        parametreler = []
        gelen = ""
        # Psikolog yalnızca kendi randevularını görür
        if psikolog_rolu_mu(rol_adi):
            gelen = "JOIN personel p ON p.personel_id = r.psikolog_id "
            kosullar.append("p.kullanici_id = %s")
            parametreler.append(kullanici_id)
        if baslangic is not None:
            kosullar.append("r.baslangic_zamani >= %s")
            parametreler.append(baslangic)
        if bitis is not None:
            kosullar.append("r.baslangic_zamani < %s::date + 1")
            parametreler.append(bitis)
        if durum is not None:
            kosullar.append("r.durum = %s")
            parametreler.append(durum)
        if danisan_kod_id is not None:
            kosullar.append("r.danisan_kod_id = %s")
            parametreler.append(danisan_kod_id)
        if oda_id is not None:
            kosullar.append("r.oda_id = %s")
            parametreler.append(oda_id)
        nerede = (" WHERE " + " AND ".join(kosullar)) if kosullar else ""

        # Hiçbir süzgeç ve limit verilmediyse (tüm geçmiş) liste en yeni RANDEVU_LISTE_ENCOK kayıtla sınırlanır: yıllar içinde tek istek onlarca MB
        # olup sunucuyu ve istemciyi kilitliyordu (10 yıllık veride 47 MB, 5 sn). Kesilmişse X-Toplam-Kayit başlığı gerçek toplamı bildirir; sıra eskisi gibi artandır.
        sinirsiz_istek = limit is None and not (baslangic or bitis or durum or danisan_kod_id or oda_id)
        if sinirsiz_istek:
            limit = RANDEVU_LISTE_ENCOK
        if limit is None:
            cursor.execute(
                f"SELECT {RANDEVU_LISTE_SUTUNLARI} FROM randevular r {gelen}{nerede} ORDER BY r.baslangic_zamani;",
                tuple(parametreler),
            )
        else:
            cursor.execute(f"SELECT COUNT(*) FROM randevular r {gelen}{nerede};", tuple(parametreler))
            toplam = (cursor.fetchone() or (0,))[0]
            if response is not None:
                response.headers["X-Toplam-Kayit"] = str(toplam)
            cursor.execute(
                f"SELECT {RANDEVU_LISTE_SUTUNLARI} FROM randevular r {gelen}{nerede} "
                "ORDER BY r.baslangic_zamani DESC, r.randevu_id DESC LIMIT %s OFFSET %s;",
                tuple(parametreler) + (limit, offset),
            )

        kayitlar = cursor.fetchall()
        if sinirsiz_istek:
            kayitlar = list(reversed(kayitlar))        # sınırlı sorgu en yeniden başlar; eski davranış gibi artan sırada döndür

        return [
            {
                "randevu_id": kayit[0],
                "danisan_kod_id": kayit[1],
                "psikolog_id": kayit[2],
                "oda_id": kayit[3],
                "baslangic_zamani": kayit[4],
                "bitis_zamani": kayit[5],
                "durum": kayit[6],
                "olusturma_tarihi": kayit[7] if len(kayit) > 7 else None,
                "iptal_nedeni": kayit[8] if len(kayit) > 8 else None,
                "iptal_notu": (kayit[9] if len(kayit) > 9 else None) if notu_gorebilir else None,
                "gorusme_tipi": kayit[10] if len(kayit) > 10 else "YUZ_YUZE",
                "terapi_turu": kayit[11] if len(kayit) > 11 else None
            } for kayit in kayitlar
        ]
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


# Danışanlar ekranı: danışan başına toplam randevu sayısı (tüm geçmişi indirmeden). Görünürlük /api/randevular ile aynıdır: psikolog yalnızca kendi randevularının sayısını görür.
def danisan_randevu_sayilari(kullanici_id: int | None = None):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("SELECT r.rol_adi FROM kullanicilar k JOIN roller r ON k.rol_id = r.rol_id WHERE k.kullanici_id = %s;", (kullanici_id,))
        rol = cursor.fetchone()
        if not rol:
            return {}
        if psikolog_rolu_mu(str(rol[0]).lower()):
            cursor.execute(
                "SELECT r.danisan_kod_id, COUNT(*) FROM randevular r JOIN personel p ON p.personel_id = r.psikolog_id "
                "WHERE p.kullanici_id = %s GROUP BY r.danisan_kod_id;", (kullanici_id,))
        else:
            cursor.execute("SELECT r.danisan_kod_id, COUNT(*) FROM randevular r GROUP BY r.danisan_kod_id;")
        return {kod: int(sayi) for kod, sayi in cursor.fetchall()}
    except psycopg2.Error:
        raise HTTPException(status_code=500, detail="Randevu sayıları alınamadı.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


HAFTA_SONU_MESAJI = "Hafta sonu randevu verilemez. Lütfen hafta içi bir gün seçin."


def hafta_sonuna_denk_mi(*zamanlar) -> bool:
    """Verilen zamanlardan biri cumartesi ya da pazara denk geliyorsa True (kurum hafta sonu kapalıdır)."""
    return any(z.weekday() >= 5 for z in zamanlar)


GECMIS_TARIH_MESAJI = "Geçmiş bir tarihe randevu verilemez."


def gecmis_tarihe_mi(zaman) -> bool:
    """Başlangıç günü bugünden önceyse True. Bugünün geçmiş saatleri serbesttir (görüşme yapılıp sonradan girilebilir)."""
    return zaman.date() < datetime.now(zaman.tzinfo).date()


DANISAN_PSIKOLOG_MESAJI = "Seçilen danışan bu psikoloğa ait değil. Bir danışanın randevusu yalnızca kendi psikoloğuna verilebilir."


def danisan_psikologa_ait_mi(sahip_psikolog_id, psikolog_id) -> bool:
    """Danışanın kayıtlı psikoloğu varsa randevu o psikoloğa verilmelidir (eski kayıtlarda psikolog boş olabilir)."""
    return sahip_psikolog_id is None or sahip_psikolog_id == psikolog_id


def randevu_taraflarini_denetle(cursor, danisan_kod_id, psikolog_id):
    """Randevunun danışanı aktif mi, psikologu aktif bir psikolog mu ve danışan bu psikoloğa mı ait? Danışanın yaş grubunu döndürür."""
    cursor.execute("SELECT yas_grubu, olusturan_psikolog_id FROM danisan_kodlari WHERE danisan_kod_id = %s AND aktif_mi = TRUE FOR SHARE;", (danisan_kod_id,))
    danisan = cursor.fetchone()
    if danisan is None:
        raise HTTPException(status_code=422, detail="Seçilen danışan kodu bulunamadı veya aktif değil.")
    cursor.execute(
        "SELECT 1 FROM personel p JOIN kullanicilar k ON p.kullanici_id = k.kullanici_id JOIN roller r ON k.rol_id = r.rol_id "
        "WHERE p.personel_id = %s AND p.aktif_mi = TRUE AND k.aktif_mi = TRUE AND UPPER(r.rol_adi) = 'PSIKOLOG';",
        (psikolog_id,),
    )
    if cursor.fetchone() is None:
        raise HTTPException(status_code=422, detail="Geçerli ve aktif bir psikolog seçilmelidir.")
    if not danisan_psikologa_ait_mi(danisan[1] if len(danisan) > 1 else None, psikolog_id):
        raise HTTPException(status_code=422, detail=DANISAN_PSIKOLOG_MESAJI)
    return danisan[0]


def randevu_doluluk(
    tarih: date,
    oda_id: int | None = Query(None, gt=0),
    psikolog_id: int | None = Query(None, gt=0),
    haric_randevu_id: int | None = Query(None, gt=0),
    kullanici_id: int | None = None,
):
    """Seçilen gün için oda ve/veya psikologun dolu saat aralıklarını döndürür.

    Yalnızca zaman aralığı ve dolu olanın türü (oda / psikolog) döner; danışan kodu,
    psikolog adı gibi kimlik bilgisi içermez. Son karar yine randevu oluşturma ve
    güncelleme uçlarındadır (409 + veritabanı kısıtı).
    """
    if oda_id is None and psikolog_id is None:
        raise HTTPException(status_code=422, detail="oda_id veya psikolog_id gönderilmelidir.")

    gun_basi = datetime(tarih.year, tarih.month, tarih.day)
    gun_sonu = gun_basi + timedelta(days=1)

    sorgu = (
        "SELECT baslangic_zamani, bitis_zamani, oda_id = %s, psikolog_id = %s "
        "FROM randevular "
        "WHERE durum = 'PLANLANDI' AND (oda_id = %s OR psikolog_id = %s) "
        "AND baslangic_zamani < %s AND bitis_zamani > %s"
    )
    parametreler = [oda_id, psikolog_id, oda_id, psikolog_id, gun_sonu, gun_basi]
    if haric_randevu_id is not None:
        sorgu += " AND randevu_id <> %s"
        parametreler.append(haric_randevu_id)
    sorgu += " ORDER BY baslangic_zamani;"

    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute(sorgu, parametreler)
        kayitlar = cursor.fetchall()

        araliklar = []
        for baslangic, bitis, oda_dolu, psikolog_dolu in kayitlar:
            if oda_dolu and psikolog_dolu:
                sebep = "oda_ve_psikolog"
            elif oda_dolu:
                sebep = "oda"
            else:
                sebep = "psikolog"
            araliklar.append({
                "baslangic": baslangic.isoformat(),
                "bitis": bitis.isoformat(),
                "sebep": sebep,
            })
        return {"tarih": tarih.isoformat(), "dolu_araliklar": araliklar}
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


def randevu_guncelle(randevu_id: int, guncelleme: RandevuGuncelleModeli, kullanici_id: int | None = None):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        # Satır kilidinden önce mevcut odayı belirle.
        cursor.execute(
            "SELECT oda_id FROM randevular WHERE randevu_id = %s;",
            (randevu_id,),
        )
        ilk_kayit = cursor.fetchone()

        if ilk_kayit is None:
            raise HTTPException(status_code=404, detail="Randevu bulunamadı.")

        ilk_oda_id = ilk_kayit[0]
        istenen = guncelleme.model_dump(exclude_unset=True)

        # Boş/null güncellemeler oda kilidi alınmadan reddedilir.
        if not istenen or any(
            deger is None for deger in istenen.values()
        ):
            raise HTTPException(
                status_code=422,
                detail="Geçerli güncelleme alanları gönderilmelidir.",
            )

        hedef_oda_id = istenen.get("oda_id", ilk_oda_id)

        # Oda kilitleri her zaman sabit sırayla alınır.
        for kilit_oda_id in sorted({
            ilk_oda_id,
            hedef_oda_id,
        }):
            if kilit_oda_id is not None:
                oda_kilidini_al(cursor, kilit_oda_id)

        cursor.execute("SELECT danisan_kod_id, psikolog_id, oda_id, baslangic_zamani, bitis_zamani, durum, gorusme_tipi, terapi_turu FROM randevular WHERE randevu_id = %s FOR UPDATE;", (randevu_id,))
        mevcut = cursor.fetchone()

        if mevcut is not None and mevcut[2] != ilk_oda_id:
            raise HTTPException(
                status_code=409,
                detail="Randevunun odası başka bir işlemde değişti. "
                       "Listeyi yenileyip tekrar deneyiniz.",
            )
        if mevcut is None:
            raise HTTPException(status_code=404, detail="Randevu bulunamadı.")
        if mevcut[5] != "PLANLANDI":
            raise HTTPException(status_code=409, detail="Yalnızca planlanmış randevular güncellenebilir.")

        cursor.execute("SELECT r.rol_adi FROM kullanicilar k JOIN roller r ON k.rol_id = r.rol_id WHERE k.kullanici_id = %s;", (kullanici_id,))
        rol = cursor.fetchone()

        psikolog_mu = rol is not None and psikolog_rolu_mu(rol[0])
        if psikolog_mu:
            cursor.execute("SELECT personel_id FROM personel WHERE kullanici_id = %s AND aktif_mi = TRUE;", (kullanici_id,))
            personel = cursor.fetchone()
            if personel is None or personel[0] != mevcut[1]:
                raise HTTPException(status_code=403, detail="Yalnızca kendi randevunuzu düzenleyebilirsiniz.")

        degisiklikler = guncelleme.model_dump(exclude_unset=True)
        if not degisiklikler or any(deger is None for deger in degisiklikler.values()):
            raise HTTPException(status_code=422, detail="Geçerli güncelleme alanları gönderilmelidir.")

        danisan_kod_id = degisiklikler.get("danisan_kod_id", mevcut[0])
        psikolog_id = degisiklikler.get("psikolog_id", mevcut[1])
        oda_id = degisiklikler.get("oda_id", mevcut[2])
        baslangic = degisiklikler.get("baslangic_zamani", mevcut[3])
        bitis = degisiklikler.get("bitis_zamani", mevcut[4])

        if psikolog_mu and psikolog_id != mevcut[1]:
            raise HTTPException(status_code=403, detail="Randevuyu başka psikoloğa devredemezsiniz.")
        if baslangic >= bitis:
            raise HTTPException(status_code=422, detail="Başlangıç zamanı bitiş zamanından önce olmalıdır.")

        # TKYS_RANDEVU_MESAI_0800_1800
        # Saat değiştiriliyorsa mevcut kayıtla birlikte doğrula.
        if (
            "baslangic_zamani" in degisiklikler
            or "bitis_zamani" in degisiklikler
        ):
            from server.modeller import randevu_mesai_dogrula

            try:
                randevu_mesai_dogrula(baslangic, bitis)
            except ValueError as hata:
                raise HTTPException(
                    status_code=422,
                    detail=str(hata),
                ) from hata
        # Zaman değişiyorsa hafta sonuna alınamaz (eskiden kalan hafta sonu randevusunun yalnızca oda/danışanı değişebilir)
        if ("baslangic_zamani" in degisiklikler or "bitis_zamani" in degisiklikler) and hafta_sonuna_denk_mi(baslangic, bitis):
            raise HTTPException(status_code=422, detail=HAFTA_SONU_MESAJI)
        # Başlangıç değişiyorsa geçmiş bir tarihe alınamaz (geçmiş randevunun terapi türü vb. yine düzeltilebilir).
        if "baslangic_zamani" in degisiklikler and baslangic != mevcut[3] and gecmis_tarihe_mi(baslangic):
            raise HTTPException(status_code=422, detail=GECMIS_TARIH_MESAJI)
        # Danışan ya da psikolog DEĞİŞİYORSA yeni taraf oluşturmadakiyle aynı kurallardan geçer: danışan aktif mi, psikolog aktif bir
        # psikolog mu, danışan bu psikoloğa mı ait. Değişmeyen taraf oluşturulurken doğrulanmıştı (planlı randevusu olan taraf pasife alınamaz).
        if danisan_kod_id != mevcut[0] or psikolog_id != mevcut[1]:
            randevu_taraflarini_denetle(cursor, danisan_kod_id, psikolog_id)
        if (psikolog_id != mevcut[1] or oda_id != mevcut[2]) and not psikolog_odasina_atanmis_mi(cursor, psikolog_id, oda_id):
            raise HTTPException(status_code=422, detail="Seçilen oda bu psikoloğa atanmamış.")

        # Oda kilitleri satır kilidinden önce alındı.
        cakisma = oda_cakismasi_bul(
            cursor,
            oda_id,
            baslangic,
            bitis,
            haric_randevu_id=randevu_id,
        )
        if cakisma:
            raise HTTPException(
                status_code=409,
                detail=f"Oda bu saatlerde dolu (çakışan kayıt: {cakisma}).",
            )

        cursor.execute("SELECT 1 FROM randevular WHERE randevu_id != %s AND durum = 'PLANLANDI' AND (psikolog_id = %s OR oda_id = %s) AND baslangic_zamani < %s AND bitis_zamani > %s LIMIT 1;", (randevu_id, psikolog_id, oda_id, bitis, baslangic))
        if cursor.fetchone() is not None:
            raise HTTPException(status_code=409, detail="Seçilen psikolog veya oda bu saatlerde dolu.")

        # Görüşme tipi / terapi türü değişiyorsa: terapi, danışanın yaş grubuna uymalıdır
        yeni_gorusme = yeni_terapi = None
        siniflar_degisiyor = "gorusme_tipi" in degisiklikler or "terapi_turu" in degisiklikler
        if siniflar_degisiyor:
            yeni_gorusme = degisiklikler.get("gorusme_tipi", mevcut[6] if len(mevcut) > 6 else "YUZ_YUZE")
            yeni_terapi = degisiklikler.get("terapi_turu", mevcut[7] if len(mevcut) > 7 else None)
            if "terapi_turu" in degisiklikler:
                cursor.execute("SELECT yas_grubu FROM danisan_kodlari WHERE danisan_kod_id = %s;", (danisan_kod_id,))
                yas_kaydi = cursor.fetchone()
                try:
                    yeni_terapi = randevu_terapisini_belirle(yas_kaydi[0] if yas_kaydi else None, yeni_terapi)
                except ValueError as hata:
                    raise HTTPException(status_code=422, detail=str(hata))

        cursor.execute("UPDATE randevular SET danisan_kod_id = %s, psikolog_id = %s, oda_id = %s, baslangic_zamani = %s, bitis_zamani = %s WHERE randevu_id = %s;", (danisan_kod_id, psikolog_id, oda_id, baslangic, bitis, randevu_id))
        if siniflar_degisiyor:
            cursor.execute("UPDATE randevular SET gorusme_tipi = %s, terapi_turu = %s WHERE randevu_id = %s;", (yeni_gorusme, yeni_terapi, randevu_id))
        cursor.execute("INSERT INTO denetim_kayitlari (kullanici_id, olay_turu, hedef_tablo, hedef_kayit_id) VALUES (%s, %s, %s, %s);", (kullanici_id, "UPDATE", "randevular", randevu_id))
        conn.commit()
        return {"durum": "basarili", "mesaj": "Randevu güncellendi.", "randevu_id": randevu_id}
    except ExclusionViolation:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=409, detail="Seçilen psikolog veya oda bu saatlerde dolu.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


def randevu_iptal_et(randevu_id: int, iptal: RandevuIptalModeli, kullanici_id: int | None = None):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        cursor.execute("SELECT psikolog_id, durum FROM randevular WHERE randevu_id = %s FOR UPDATE;", (randevu_id,))
        randevu = cursor.fetchone()
        if randevu is None:
            raise HTTPException(status_code=404, detail="Randevu bulunamadı.")

        cursor.execute("SELECT r.rol_adi FROM kullanicilar k JOIN roller r ON k.rol_id = r.rol_id WHERE k.kullanici_id = %s;", (kullanici_id,))
        rol = cursor.fetchone()

        if rol is not None and psikolog_rolu_mu(rol[0]):
            cursor.execute("SELECT personel_id FROM personel WHERE kullanici_id = %s AND aktif_mi = TRUE;", (kullanici_id,))
            personel = cursor.fetchone()
            if personel is None or personel[0] != randevu[0]:
                raise HTTPException(status_code=403, detail="Yalnızca kendi randevunuzu iptal edebilirsiniz.")

        if randevu[1] != "PLANLANDI":
            raise HTTPException(status_code=409, detail="Bu randevu iptal edilemez.")

        cursor.execute("UPDATE randevular SET durum = 'IPTAL_EDILDI', iptal_nedeni = %s, iptal_notu = %s WHERE randevu_id = %s;", (iptal.iptal_nedeni, iptal.iptal_notu, randevu_id))
        durum_degisikligi_yaz(cursor, kullanici_id, "CANCEL", "randevular", randevu_id, onceki=randevu[1], yeni="IPTAL_EDILDI", iptal_nedeni=iptal.iptal_nedeni)
        conn.commit()
        return {"durum": "basarili", "mesaj": "Randevu iptal edildi.", "randevu_id": randevu_id}
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


def randevu_durumunu_isaretle(
    randevu_id: int,
    isaret: RandevuDurumModeli,
    kullanici_id: int | None = None,
):
    """Başlangıcı geçmiş randevuyu Tamamlandı ya da Gelmedi olarak işaretler (ikisi arasında düzeltme yapılabilir).

    Psikolog yalnızca kendi randevusunu işaretler. İptal edilmiş ve henüz başlamamış randevu işaretlenemez.
    """
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        cursor.execute("SELECT psikolog_id, durum, baslangic_zamani FROM randevular WHERE randevu_id = %s FOR UPDATE;", (randevu_id,))
        randevu = cursor.fetchone()
        if randevu is None:
            raise HTTPException(status_code=404, detail="Randevu bulunamadı.")

        cursor.execute("SELECT r.rol_adi FROM kullanicilar k JOIN roller r ON k.rol_id = r.rol_id WHERE k.kullanici_id = %s;", (kullanici_id,))
        rol = cursor.fetchone()
        if rol is not None and psikolog_rolu_mu(rol[0]):
            cursor.execute("SELECT personel_id FROM personel WHERE kullanici_id = %s AND aktif_mi = TRUE;", (kullanici_id,))
            personel = cursor.fetchone()
            if personel is None or personel[0] != randevu[0]:
                raise HTTPException(status_code=403, detail="Yalnızca kendi randevunuzun durumunu işaretleyebilirsiniz.")

        if randevu[1] == "IPTAL_EDILDI":
            raise HTTPException(status_code=409, detail="İptal edilmiş randevu Tamamlandı ya da Gelmedi olarak işaretlenemez.")
        if randevu[2] > datetime.now():
            raise HTTPException(status_code=409, detail="Henüz başlamamış randevu işaretlenemez. Randevu saatinden sonra tekrar deneyin.")
        if randevu[1] == isaret.durum:
            return {"durum": "basarili", "randevu_id": randevu_id, "randevu_durumu": isaret.durum, "mesaj": "Randevu zaten bu durumda."}

        cursor.execute("UPDATE randevular SET durum = %s WHERE randevu_id = %s;", (isaret.durum, randevu_id))
        durum_degisikligi_yaz(cursor, kullanici_id, "UPDATE", "randevular", randevu_id, onceki=randevu[1], yeni=isaret.durum)
        conn.commit()
        return {"durum": "basarili", "randevu_id": randevu_id, "randevu_durumu": isaret.durum, "mesaj": "Randevu durumu güncellendi."}
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


# (yöntem, yol, uç fonksiyonu, yetki parametresi, gereken yetki, ek yol ayarları): yetki bağımlılığı kayıt sırasında eklenir.
# Gereken yetki: "IZIN" (izin_kontrol), ("A", "B") (izin_kontrol_biri: biri yeter) veya None (yalnızca oturum açmış olmak).
UCLAR = [
    ("POST", "/api/randevular", randevu_olustur, "kullanici_id", "RANDEVU_OLUSTUR", {"status_code": 201}),
    ("GET", "/api/randevular", randevulari_listele, "kullanici_id", "TAKVIM_GORUNTULE", {}),
    ("GET", "/api/danisan-randevu-sayilari", danisan_randevu_sayilari, "kullanici_id", "TAKVIM_GORUNTULE", {}),
    ("GET", "/api/randevular/doluluk", randevu_doluluk, "kullanici_id", "TAKVIM_GORUNTULE", {}),
    ("PATCH", "/api/randevular/{randevu_id}", randevu_guncelle, "kullanici_id", "RANDEVU_DUZENLE", {}),
    ("PATCH", "/api/randevular/{randevu_id}/iptal", randevu_iptal_et, "kullanici_id", "RANDEVU_IPTAL", {}),
    ("PATCH", "/api/randevular/{randevu_id}/durum", randevu_durumunu_isaretle, "kullanici_id", "RANDEVU_DUZENLE", {}),
]


def router_olustur(izin_kontrol) -> APIRouter:
    """Yetki bağımlılığı üreticileri `server.sunucu` içindeki kimlik doğrulama bağımlılıklarıdır."""
    router = APIRouter()
    for metod, yol, fonksiyon, parametre, yetki, ek in UCLAR:
        assert isinstance(yetki, str), yol          # bu modülde yalnızca tek izin tanımlı
        bagimlilik = izin_kontrol(yetki)
        router.add_api_route(yol, yetkiyle_bagla(fonksiyon, parametre, bagimlilik), methods=[metod], **ek)
    return router
