"""Ana panel (dashboard) ve duyuru uçları. `server/sunucu.py` içinden ayrıldı."""
from datetime import date
from datetime import timedelta

from fastapi import APIRouter, HTTPException, Query

from server.denetim import ayrintili_kayit_yaz
from server.modeller import DuyuruModeli
from server.ortak_sabitler import ETKIN_CIHAZ_DURUMU_SQL
from server.ortak_yardimcilar import plan_kalibrasyon_mu
from server.vt_ayarlari import VT_AYARLARI
from server.vt_baglanti import vt_baglan
from server.yetki_baglama import yetkiyle_bagla


def dashboard_ozet_getir(kullanici_id: int | None = None):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        ozet = {
            "toplam_cihaz": 0, "aktif_cihaz": 0, "arizali_cihaz": 0,
            "bakimdaki_cihaz": 0, "kalibrasyondaki_cihaz": 0,
            "acik_ariza_sayisi": 0, "bugunku_randevu_sayisi": 0
        }

        # 1. Cihaz İstatistiklerini Çek
        # Bakım/kalibrasyon kaydı cihaz durumunu kendiliğinden değiştirmediğinden, bugün planlı bir
        # bakım ya da kalibrasyon aralığında olan cihaz da "bakımda"/"kalibrasyonda" sayılır.
        # Öncelik: arızalı/kullanım dışı > bakımda > kalibrasyonda.
        cursor.execute("SELECT " + ETKIN_CIHAZ_DURUMU_SQL + " AS etkin_durum, COUNT(*) FROM cihazlar c GROUP BY 1;")
        cihaz_durumlari = cursor.fetchall()
        for durum, sayi in cihaz_durumlari:
            ozet["toplam_cihaz"] += sayi
            if durum == "Kullanima_Hazir":
                ozet["aktif_cihaz"] = sayi
            elif durum == "Arizali":
                ozet["arizali_cihaz"] = sayi
            elif durum == "Bakimda":
                ozet["bakimdaki_cihaz"] = sayi
            elif durum == "Kalibrasyonda":
                ozet["kalibrasyondaki_cihaz"] = sayi

        # 2. Açık Arızaları Çek (cozuldu_mu sütunu FALSE olanlar)
        # Sorgu hata verirse sayı sessizce 0 kalmaz: ortak hata yakalayıcı 500 döner ve asıl nedeni günlüğe yazar.
        cursor.execute("SELECT COUNT(*) FROM cihaz_arizalari WHERE cozuldu_mu = False;")
        ozet["acik_ariza_sayisi"] = cursor.fetchone()[0]

        # 3. Bugünkü Randevuları Çek
        cursor.execute("SELECT COUNT(*) FROM randevular WHERE DATE(baslangic_zamani) = CURRENT_DATE;")
        ozet["bugunku_randevu_sayisi"] = cursor.fetchone()[0]

        return ozet

    except Exception:
        raise HTTPException(status_code=500, detail="İşlem sırasında beklenmeyen bir sunucu hatası oluştu.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

# Ana panel gün seçici: bugün, yarın ya da bugünden başlayan 7 günlük "hafta". (başlangıç, bitiş) = bugüne göre gün farkı, bitiş hariç.
DASHBOARD_ARALIKLARI = {"bugun": (0, 1), "yarin": (1, 2), "hafta": (0, 7)}
ARALIK_SORGU_DESENI = "^(bugun|yarin|hafta)$"


def _tarih_kisa(zaman):
    return zaman.strftime("%d.%m")


def dashboard_bugunku_randevular(kullanici_id: int | None = None,
                                 aralik: str = Query("bugun", pattern=ARALIK_SORGU_DESENI)):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        bas, son = DASHBOARD_ARALIKLARI.get(aralik, (0, 1))
        cursor.execute("""
            SELECT r.randevu_id, r.danisan_kod_id, k.kullanici_adi, o.oda_adi,
                   r.baslangic_zamani, r.bitis_zamani, r.durum
            FROM randevular r
            JOIN personel p ON r.psikolog_id = p.personel_id
            JOIN kullanicilar k ON p.kullanici_id = k.kullanici_id
            JOIN odalar o ON r.oda_id = o.oda_id
            WHERE r.baslangic_zamani >= CURRENT_DATE + %s AND r.baslangic_zamani < CURRENT_DATE + %s
            ORDER BY r.baslangic_zamani;
        """, (bas, son))
        return [{
            "tarih": _tarih_kisa(s[4]),
            "randevu_id": s[0],
            "danisan_kod_id": s[1],
            "psikolog": s[2],
            "oda": s[3],
            "baslangic": s[4].strftime("%H:%M"),
            "bitis": s[5].strftime("%H:%M"),
            "durum": s[6]
        } for s in cursor.fetchall()]
    except Exception:
        raise HTTPException(status_code=500, detail="Bugünkü randevular alınamadı.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

# Ana paneldeki "bugünkü cihaz rezervasyonları": cihazı yönetenler, rezervasyon yapanlar ve Cihaz Uygunluğu'nu görebilenler (ör. psikolog) görür;
# böylece herkes merkezde o gün hangi cihazın ne zaman kullanıldığını bilir. REZERVE EDEN adını yalnızca cihazı yönetenler ve rezervasyon yapanlar
# görür; Cihaz Uygunluğu sayfası gibi yalnızca görüntüleyenlere kişi adı verilmez (null).
def dashboard_bugunku_rezervasyonlar(kullanici_id: int | None = None,
                                     aralik: str = Query("bugun", pattern=ARALIK_SORGU_DESENI)):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        bas, son = DASHBOARD_ARALIKLARI.get(aralik, (0, 1))
        # Bugünle kesişen (bugün başlayan, biten veya bugünü kapsayan) aktif rezervasyonlar
        cursor.execute("""
            SELECT r.rezervasyon_id, c.envanter_kodu, c.cihaz_adi,
                   COALESCE(k.kullanici_adi, '-'), COALESCE(o.oda_adi, '-'),
                   r.baslangic_zamani, r.bitis_zamani,
                   (SELECT COALESCE(MAX(ri.izin_var), 0) FROM kullanicilar kk
                      JOIN rol_izinleri ri ON kk.rol_id = ri.rol_id JOIN izinler i ON ri.izin_id = i.izin_id
                     WHERE kk.kullanici_id = %s AND i.izin_adi IN ('CIHAZ_ENVANTER_YONET', 'CIHAZ_REZERVASYON')) AS isim_gorebilir
            FROM cihaz_rezervasyonlari r
            JOIN cihazlar c ON r.cihaz_id = c.cihaz_id
            LEFT JOIN personel p ON r.rezervasyonu_yapan_personel_id = p.personel_id
            LEFT JOIN kullanicilar k ON p.kullanici_id = k.kullanici_id
            LEFT JOIN odalar o ON r.kullanilacak_oda_id = o.oda_id
            WHERE COALESCE(r.iptal_edildi_mi, FALSE) = FALSE
              AND r.baslangic_zamani < CURRENT_DATE + %s
              AND r.bitis_zamani >= CURRENT_DATE + %s
            ORDER BY r.baslangic_zamani;
        """, (kullanici_id, son, bas))
        gosterilen_gun = date.today() + timedelta(days=bas)

        def zaman(z):
            return z.strftime("%H:%M") if (aralik != "hafta" and z.date() == gosterilen_gun) else z.strftime("%d.%m %H:%M")

        return [{
            "tarih": _tarih_kisa(s[5]),
            "rezervasyon_id": s[0],
            "cihaz": f"{s[1]} - {s[2]}",
            "rezerve_eden": s[3] if (len(s) <= 7 or s[7] == 1) else None,
            "oda": s[4],
            "baslangic": zaman(s[5]),
            "bitis": zaman(s[6])
        } for s in cursor.fetchall()]
    except Exception:
        raise HTTPException(status_code=500, detail="Bugünkü rezervasyonlar alınamadı.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

# Ana panel: bugünkü oda etkinlikleri (çok günlü etkinliğin bugüne düşen günü dahil). Yalnızca saat, ad, oda ve katılımcı sayısı döner;
# organize eden kişi adı verilmez. Salt okunur "bugün merkezde ne var" bilgisi olduğu için giriş yapmış HERKES görür (ayrı bir görüntüleme izni
# aramaz; örn. Proje Asistanı'nın Oda Etkinlikleri sayfası yoktur ama bugünkü etkinlikleri ana panelde görür). Etkinlik eklemek/düzenlemek/iptal etmek
# yine ODA_ETKINLIK_YONET ister.
BUGUNKU_ETKINLIK_UST_SINIR = 200


def dashboard_bugunku_etkinlikler(kullanici_id: int | None = None,
                                  aralik: str = Query("bugun", pattern=ARALIK_SORGU_DESENI)):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        bas, son = DASHBOARD_ARALIKLARI.get(aralik, (0, 1))
        cursor.execute("""
            SELECT e.etkinlik_id, e.etkinlik_adi, o.oda_adi, g.baslangic_zamani, g.bitis_zamani, e.katilimci_sayisi
            FROM oda_etkinlik_gunleri g
            JOIN oda_etkinlikleri e ON e.etkinlik_id = g.etkinlik_id
            JOIN odalar o ON o.oda_id = e.oda_id
            WHERE COALESCE(e.iptal_edildi_mi, FALSE) = FALSE
              AND g.baslangic_zamani < CURRENT_DATE + %s
              AND g.bitis_zamani > CURRENT_DATE + %s
            ORDER BY g.baslangic_zamani, e.etkinlik_id
            LIMIT %s;
        """, (son, bas, BUGUNKU_ETKINLIK_UST_SINIR))

        def saat(zaman, baslangic):
            return "24:00" if zaman.date() > baslangic.date() else zaman.strftime("%H:%M")      # gece yarısında biten gün "00:00" değil "24:00"

        return [{
            "tarih": _tarih_kisa(s[3]),
            "etkinlik_id": s[0],
            "etkinlik": s[1],
            "oda": s[2],
            "baslangic": s[3].strftime("%H:%M"),
            "bitis": saat(s[4], s[3]),
            "katilimci": s[5],
        } for s in cursor.fetchall()]
    except Exception:
        raise HTTPException(status_code=500, detail="Bugünkü etkinlikler alınamadı.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

# "Benim günüm"e rol bazlı "bekleyen işlerim" satırları: yalnızca kişinin KENDİ izinleri olan konularda, mevcut kayıtlardan hesaplanır (yeni veri tutulmaz).
# Hiçbir şey beklemiyorsa satır eklenmez. Bu bölüm hata verirse randevu/rezervasyon listesi yine de döner (isler boş gelir).
ISLER_IZINLERI = ("DANISMA_OTURUMU_YONET", "DANISMA_OTURUMU_YONETIM", "ARIZA_KAYITLARI_YONET")


def _benim_islerim(cursor, kullanici_id):
    try:
        cursor.execute("""
            SELECT i.izin_adi FROM kullanicilar k
            JOIN rol_izinleri ri ON k.rol_id = ri.rol_id
            JOIN izinler i ON ri.izin_id = i.izin_id
            WHERE k.kullanici_id = %s AND ri.izin_var = 1 AND i.izin_adi = ANY(%s);
        """, (kullanici_id, list(ISLER_IZINLERI)))
        izinler = {s[0] for s in cursor.fetchall()}
        isler = []
        if "DANISMA_OTURUMU_YONET" in izinler:
            cursor.execute("""
                SELECT EXTRACT(EPOCH FROM (clock_timestamp()::timestamp - d.baslangic_zamani))::bigint
                FROM danisma_masasi_oturumlari d
                JOIN ogrenciler o ON o.ogrenci_id = d.ogrenci_id
                WHERE o.kullanici_id = %s AND o.aktif_mi = TRUE AND d.bitis_zamani IS NULL
                ORDER BY d.baslangic_zamani DESC LIMIT 1;
            """, (kullanici_id,))
            satir = cursor.fetchone()
            if satir is not None:
                dakika = max(0, int(satir[0] or 0)) // 60
                isler.append({"metin": f"Danışma masası göreviniz devam ediyor ({dakika // 60} saat {dakika % 60} dakika). Bitirmeyi unutmayın.",
                              "hedef": "Danışma Masası", "onem": "uyari"})
        if "DANISMA_OTURUMU_YONETIM" in izinler:
            cursor.execute("""
                SELECT COUNT(*) FILTER (WHERE bitis_zamani IS NULL),
                       COUNT(*) FILTER (WHERE bitis_zamani IS NOT NULL AND onaylandi_mi IS NOT TRUE)
                FROM danisma_masasi_oturumlari;
            """)
            aktif, bekleyen = cursor.fetchone()
            if bekleyen:
                isler.append({"metin": f"{bekleyen} danışma masası oturumu onayınızı bekliyor.", "hedef": "Danışma Masası Yönetimi", "onem": "uyari"})
            if aktif:
                isler.append({"metin": f"{aktif} öğrenci şu an danışma masasında görevde.", "hedef": "Danışma Masası Yönetimi", "onem": "bilgi"})
        if "ARIZA_KAYITLARI_YONET" in izinler:
            cursor.execute("SELECT COUNT(*) FROM cihaz_arizalari WHERE COALESCE(cozuldu_mu, FALSE) = FALSE;")
            acik = cursor.fetchone()[0]
            if acik:
                isler.append({"metin": f"{acik} açık cihaz arızası çözüm bekliyor.", "hedef": "Arıza Kayıtları", "onem": "uyari"})
        return isler
    except Exception:
        return []


# Ana panel "Benim günüm": giriş yapan kişinin KENDİ bugünkü/yarınki randevuları ve cihaz rezervasyonları. Yalnızca kişinin kendi kaydı döner
# (başkasının bilgisi yok), bu yüzden ayrı bir izin aramaz; kaydı olmayan rolde (örn. danışma öğrencisi) listeler boş gelir.
def dashboard_benim_gunum(kullanici_id: int | None = None):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT (r.baslangic_zamani::date > CURRENT_DATE) AS yarin, r.baslangic_zamani, r.bitis_zamani, r.danisan_kod_id, o.oda_adi
            FROM randevular r
            JOIN personel p ON r.psikolog_id = p.personel_id
            JOIN odalar o ON r.oda_id = o.oda_id
            WHERE p.kullanici_id = %s
              AND r.durum <> 'IPTAL_EDILDI'
              AND r.baslangic_zamani >= CURRENT_DATE AND r.baslangic_zamani < CURRENT_DATE + 2
            ORDER BY r.baslangic_zamani
            LIMIT 100;
        """, (kullanici_id,))
        randevular = [{
            "gun": "yarin" if s[0] else "bugun",
            "saat": f"{s[1].strftime('%H:%M')} – {s[2].strftime('%H:%M')}",
            "danisan_kod_id": s[3],
            "oda": s[4],
        } for s in cursor.fetchall()]

        cursor.execute("""
            SELECT (r.baslangic_zamani::date > CURRENT_DATE) AS yarin, r.baslangic_zamani, r.bitis_zamani,
                   c.envanter_kodu, c.cihaz_adi, COALESCE(o.oda_adi, '-')
            FROM cihaz_rezervasyonlari r
            JOIN cihazlar c ON r.cihaz_id = c.cihaz_id
            JOIN personel p ON r.rezervasyonu_yapan_personel_id = p.personel_id
            LEFT JOIN odalar o ON r.kullanilacak_oda_id = o.oda_id
            WHERE p.kullanici_id = %s
              AND COALESCE(r.iptal_edildi_mi, FALSE) = FALSE
              AND r.baslangic_zamani < CURRENT_DATE + 2
              AND r.bitis_zamani >= CURRENT_DATE
            ORDER BY r.baslangic_zamani
            LIMIT 100;
        """, (kullanici_id,))
        rezervasyonlar = [{
            "gun": "yarin" if s[0] else "bugun",
            "saat": f"{s[1].strftime('%H:%M')} – {s[2].strftime('%H:%M')}" if s[1].date() == s[2].date()
                    else f"{s[1].strftime('%d.%m %H:%M')} – {s[2].strftime('%d.%m %H:%M')}",
            "cihaz": f"{s[3]} - {s[4]}",
            "oda": s[5],
        } for s in cursor.fetchall()]
        return {"randevular": randevular, "rezervasyonlar": rezervasyonlar, "isler": _benim_islerim(cursor, kullanici_id)}
    except Exception:
        raise HTTPException(status_code=500, detail="Günlük bilgileriniz alınamadı.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


# Duyurular: kurum içi genel bilgi ("yarın sistem bakımı var"). Okumak için giriş yapmak yeter (izin aranmaz; herkesin ana panelinde görünür),
# yayınlamak/kaldırmak DUYURU_YONET ister. Yazan kişinin adı yalnızca duyuruyu yönetenlere gösterilir. Duyuruya kişisel veri yazılmamalıdır.
DUYURU_UST_SINIR = 50
DUYURU_YENI_GUN = 3


def duyurulari_getir(kullanici_id: int | None = None):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT d.duyuru_id, d.baslik, d.metin, d.olusturma_zamani, d.son_gecerlilik_tarihi, k.kullanici_adi,
                   (d.olusturma_zamani >= CURRENT_TIMESTAMP - make_interval(days => %s)) AS yeni,
                   (SELECT COALESCE(MAX(ri.izin_var), 0) FROM kullanicilar kk
                      JOIN rol_izinleri ri ON kk.rol_id = ri.rol_id JOIN izinler i ON ri.izin_id = i.izin_id
                     WHERE kk.kullanici_id = %s AND i.izin_adi = 'DUYURU_YONET') AS yonetebilir,
                   EXISTS (SELECT 1 FROM duyuru_okundu o WHERE o.duyuru_id = d.duyuru_id AND o.kullanici_id = %s) AS okundu
            FROM duyurular d
            LEFT JOIN kullanicilar k ON k.kullanici_id = d.olusturan_kullanici_id
            WHERE d.son_gecerlilik_tarihi IS NULL OR d.son_gecerlilik_tarihi >= CURRENT_DATE
            ORDER BY d.olusturma_zamani DESC, d.duyuru_id DESC
            LIMIT %s;
        """, (DUYURU_YENI_GUN, kullanici_id, kullanici_id, DUYURU_UST_SINIR))
        return [{
            "duyuru_id": s[0],
            "baslik": s[1],
            "metin": s[2],
            "tarih": s[3].strftime("%d.%m.%Y %H:%M"),
            "son_gecerlilik": s[4].strftime("%d.%m.%Y") if s[4] else None,
            "yazan": s[5] if s[7] == 1 else None,
            "yeni": bool(s[6]),
            "yonetebilir": s[7] == 1,
            "okundu": bool(s[8]),                      # BU kullanıcı okundu işaretledi mi (başkalarını etkilemez)
        } for s in cursor.fetchall()]
    except Exception:
        raise HTTPException(status_code=500, detail="Duyurular alınamadı.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


# Duyuruyu "okundu" işaretleme: kullanıcı kendi ekranında gizler; duyuru SİLİNMEZ ve diğer kullanıcılar için yayında kalır. Yalnızca çağıranın kendi okundu bilgisini
# değiştirir (başkasınınkine dokunamaz), bu yüzden ayrı bir izin aramaz.
def duyurulari_okundu_isaretle(kullanici_id: int | None = None):
    """Yayındaki bütün duyuruları (çağıran için) okundu işaretler."""
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO duyuru_okundu (duyuru_id, kullanici_id)
            SELECT d.duyuru_id, %s FROM duyurular d
            WHERE d.son_gecerlilik_tarihi IS NULL OR d.son_gecerlilik_tarihi >= CURRENT_DATE
            ON CONFLICT (duyuru_id, kullanici_id) DO NOTHING;
        """, (kullanici_id,))
        conn.commit()
        return {"mesaj": "Duyurular okundu olarak işaretlendi."}
    except Exception:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=500, detail="Duyurular okundu işaretlenemedi.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


def duyuruyu_okundu_isaretle(duyuru_id: int, kullanici_id: int | None = None):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM duyurular WHERE duyuru_id = %s;", (duyuru_id,))
        if cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="Duyuru bulunamadı.")
        cursor.execute("INSERT INTO duyuru_okundu (duyuru_id, kullanici_id) VALUES (%s, %s) ON CONFLICT (duyuru_id, kullanici_id) DO NOTHING;",
                       (duyuru_id, kullanici_id))
        conn.commit()
        return {"mesaj": "Duyuru okundu olarak işaretlendi."}
    except HTTPException:
        raise
    except Exception:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=500, detail="Duyuru okundu işaretlenemedi.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


def duyuruyu_tekrar_goster(duyuru_id: int, kullanici_id: int | None = None):
    """Okundu işaretini kaldırır (duyuru bu kullanıcıya yeniden görünür). İşaret yoksa da başarılıdır."""
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM duyuru_okundu WHERE duyuru_id = %s AND kullanici_id = %s;", (duyuru_id, kullanici_id))
        conn.commit()
        return {"mesaj": "Duyuru yeniden gösterilecek."}
    except Exception:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=500, detail="Duyuru yeniden gösterilemedi.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


def duyuru_yayinla(duyuru: DuyuruModeli, kullanici_id: int | None = None):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO duyurular (baslik, metin, olusturan_kullanici_id, son_gecerlilik_tarihi) VALUES (%s, %s, %s, %s) RETURNING duyuru_id;",
            (duyuru.baslik, duyuru.metin, kullanici_id, duyuru.son_gecerlilik_tarihi))
        duyuru_id = cursor.fetchone()[0]
        ayrintili_kayit_yaz(cursor, kullanici_id, "CREATE", "duyurular", duyuru_id, baslik=duyuru.baslik)
        conn.commit()
        return {"mesaj": "Duyuru yayınlandı.", "duyuru_id": duyuru_id}
    except Exception:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=500, detail="Duyuru yayınlanamadı.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


def duyuru_kaldir(duyuru_id: int, kullanici_id: int | None = None):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM duyurular WHERE duyuru_id = %s RETURNING baslik;", (duyuru_id,))
        satir = cursor.fetchone()
        if satir is None:
            conn.rollback()
            raise HTTPException(status_code=404, detail="Duyuru bulunamadı.")
        ayrintili_kayit_yaz(cursor, kullanici_id, "DELETE", "duyurular", duyuru_id, silinen_baslik=satir[0])
        conn.commit()
        return {"mesaj": "Duyuru kaldırıldı."}
    except HTTPException:
        raise
    except Exception:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=500, detail="Duyuru kaldırılamadı.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


# En acil (en çok geciken) kayıtlar önce gelir. Sınır yalnızca yanıtı makul tutar; istemci listeyi kaydırılabilir
# gösterir. Eskiden 10'du: 10'dan fazla geciken kayıt varsa fazlası hiç görünmüyordu (güvenlik açısından riskli).
YAKLASAN_ISLEM_UST_SINIR = 50


def yaklasan_islemler_getir(kullanici_id: int | None = None):
    """Ana panel/zil bildirimleri için yaklaşan ve geciken bakım ve kalibrasyonlar. Cihaz envanterini yönetenler hepsini görür; yalnızca bakım ya da
    kalibrasyon izni olan kullanıcı yalnızca kendi türünün kayıtlarını görür."""
    import datetime
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        islemler = []
        bugun = datetime.date.today()
        cursor.execute("""
            SELECT COALESCE(array_agg(i.izin_adi), ARRAY[]::text[]) FROM kullanicilar k
            JOIN rol_izinleri ri ON ri.rol_id = k.rol_id JOIN izinler i ON i.izin_id = ri.izin_id
            WHERE k.kullanici_id = %s AND ri.izin_var = 1
              AND i.izin_adi IN ('CIHAZ_ENVANTER_YONET', 'BAKIM_KAYITLARI_GORUNTULE', 'BAKIM_KAYITLARI_YONET',
                                 'KALIBRASYON_KAYITLARI_GORUNTULE', 'KALIBRASYON_KAYITLARI_YONET');
        """, (kullanici_id,))
        satir = cursor.fetchone()
        sahip = set(satir[0] or []) if satir else set()
        hepsi = "CIHAZ_ENVANTER_YONET" in sahip or not sahip                     # (boş küme: taklit/eski ortam; sunucu izni zaten denetledi)
        bakim_gorur = hepsi or bool(sahip & {"BAKIM_KAYITLARI_GORUNTULE", "BAKIM_KAYITLARI_YONET"})
        kalibrasyon_gorur = hepsi or bool(sahip & {"KALIBRASYON_KAYITLARI_GORUNTULE", "KALIBRASYON_KAYITLARI_YONET"})

        # 1. YAKLAŞAN BAKIMLAR
        # Her cihaz için yalnızca SON bakım kaydı dikkate alınır (eski kayıtların planı geçersizdir).
        cursor.execute("""
            SELECT DISTINCT ON (b.cihaz_id) c.envanter_kodu, c.cihaz_adi, b.sonraki_bakim_tarihi, b.uyari_suresi_gun
            FROM cihaz_bakimlari b
            JOIN cihazlar c ON b.cihaz_id = c.cihaz_id
            WHERE c.durum::text <> 'Kullanim_Disi'
            ORDER BY b.cihaz_id,
                     COALESCE(b.bakim_baslangic_tarihi::date, b.bakim_tarihi::date) DESC,
                     b.bakim_id DESC
        """)
        for kayit in cursor.fetchall():
            hedef_tarih = kayit[2]
            if hedef_tarih is None:
                continue
            kalan_gun = (hedef_tarih - bugun).days
            if kalan_gun <= kayit[3]:                      # uyarı süresi içinde ya da tarihi geçmiş (gecikmiş)
                islemler.append({
                    "cihaz_adi": f"{kayit[0]} - {kayit[1]}",
                    "islem_turu": "Bakım",
                    "tarih": hedef_tarih.strftime("%d.%m.%Y"),
                    "kalan_gun": kalan_gun,
                    "gecikmis": kalan_gun < 0,
                    "durum_kodu": "KRITIK" if kalan_gun <= 5 else "UYARI"
                })

        # 2. YAKLAŞAN KALİBRASYONLAR
        # Her cihaz için geçerliliği en ileri olan (güncel) kalibrasyon kaydı dikkate alınır.
        cursor.execute("""
            SELECT DISTINCT ON (k.cihaz_id) c.envanter_kodu, c.cihaz_adi, k.gecerlilik_tarihi, k.uyari_suresi_gun
            FROM cihaz_kalibrasyonlari k
            JOIN cihazlar c ON k.cihaz_id = c.cihaz_id
            WHERE k.gecerlilik_tarihi IS NOT NULL AND c.durum::text <> 'Kullanim_Disi'
            ORDER BY k.cihaz_id, k.gecerlilik_tarihi DESC, k.kalibrasyon_id DESC
        """)
        for kayit in cursor.fetchall():
            hedef_tarih = kayit[2]
            kalan_gun = (hedef_tarih - bugun).days
            if kalan_gun <= kayit[3]:                      # uyarı süresi içinde ya da tarihi geçmiş (gecikmiş)
                islemler.append({
                    "cihaz_adi": f"{kayit[0]} - {kayit[1]}",
                    "islem_turu": "Kalibrasyon",
                    "tarih": hedef_tarih.strftime("%d.%m.%Y"),
                    "kalan_gun": kalan_gun,
                    "gecikmis": kalan_gun < 0,
                    "durum_kodu": "KRITIK" if kalan_gun <= 5 else "UYARI"
                })

        # 3. PLANLI BAKIM/KALİBRASYONLAR
        # Plan, kayıtla aynı cihaz ve tarihi gösteriyorsa (kayıt plana bağlıysa böyledir) tekrar listelenmez.
        mevcut = {(i["cihaz_adi"], i["tarih"]) for i in islemler}
        cursor.execute("""
            SELECT c.envanter_kodu, c.cihaz_adi, p.gorev_turu, p.sonraki_gorev_tarihi, COALESCE(p.uyari_suresi_gun, 0)
            FROM cihaz_bakim_planlari p
            JOIN cihazlar c ON c.cihaz_id = p.cihaz_id
            WHERE COALESCE(p.aktif_mi, TRUE) = TRUE AND c.durum::text <> 'Kullanim_Disi'
        """)
        for kod, ad, tur, hedef_tarih, uyari in cursor.fetchall():
            kalan_gun = (hedef_tarih - bugun).days
            etiket = f"{kod} - {ad}"
            if kalan_gun > uyari or (etiket, hedef_tarih.strftime("%d.%m.%Y")) in mevcut:
                continue
            islemler.append({
                "cihaz_adi": etiket,
                "islem_turu": "Kalibrasyon" if plan_kalibrasyon_mu(tur) else "Bakım",
                "tarih": hedef_tarih.strftime("%d.%m.%Y"),
                "kalan_gun": kalan_gun,
                "gecikmis": kalan_gun < 0,
                "durum_kodu": "KRITIK" if kalan_gun <= 5 else "UYARI"
            })

        islemler = [i for i in islemler if (bakim_gorur if i["islem_turu"] == "Bakım" else kalibrasyon_gorur)]
        islemler.sort(key=lambda x: x["kalan_gun"])
        return islemler[:YAKLASAN_ISLEM_UST_SINIR]

    except Exception:
        raise HTTPException(status_code=500, detail="İşlem sırasında beklenmeyen bir sunucu hatası oluştu.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


# (yöntem, yol, uç fonksiyonu, yetki parametresi, gereken yetki, ek yol ayarları): yetki bağımlılığı kayıt sırasında eklenir.
# Gereken yetki: "IZIN" (izin_kontrol), ("IZIN1", "IZIN2", ...) (izin_kontrol_biri: biri yeter) veya None (yalnızca oturum açmış olmak).
UCLAR = [
    ("GET", "/api/dashboard/ozet", dashboard_ozet_getir, "kullanici_id", "CIHAZ_ENVANTER_YONET", {}),
    ("GET", "/api/dashboard/bugunku-randevular", dashboard_bugunku_randevular, "kullanici_id", "TAKVIM_GORUNTULE", {}),
    ("GET", "/api/dashboard/bugunku-rezervasyonlar", dashboard_bugunku_rezervasyonlar, "kullanici_id", ("CIHAZ_ENVANTER_YONET", "CIHAZ_UYGUNLUK_GORUNTULE", "CIHAZ_REZERVASYON"), {}),
    ("GET", "/api/dashboard/bugunku-etkinlikler", dashboard_bugunku_etkinlikler, "kullanici_id", None, {}),
    ("GET", "/api/dashboard/benim-gunum", dashboard_benim_gunum, "kullanici_id", None, {}),
    ("GET", "/api/duyurular", duyurulari_getir, "kullanici_id", None, {}),
    ("POST", "/api/duyurular/okundu", duyurulari_okundu_isaretle, "kullanici_id", None, {}),
    ("POST", "/api/duyurular/{duyuru_id}/okundu", duyuruyu_okundu_isaretle, "kullanici_id", None, {}),
    ("DELETE", "/api/duyurular/{duyuru_id}/okundu", duyuruyu_tekrar_goster, "kullanici_id", None, {}),
    ("POST", "/api/duyurular", duyuru_yayinla, "kullanici_id", "DUYURU_YONET", {"status_code": 201}),
    ("DELETE", "/api/duyurular/{duyuru_id}", duyuru_kaldir, "kullanici_id", "DUYURU_YONET", {}),
    ("GET", "/api/dashboard/yaklasan-islemler", yaklasan_islemler_getir, "kullanici_id", ("CIHAZ_ENVANTER_YONET", "BAKIM_KAYITLARI_GORUNTULE", "BAKIM_KAYITLARI_YONET", "KALIBRASYON_KAYITLARI_GORUNTULE", "KALIBRASYON_KAYITLARI_YONET"), {}),
]


def router_olustur(izin_kontrol, izin_kontrol_biri, mevcut_kullanici_id) -> APIRouter:
    """Yetki bağımlılığı üreticileri `server.sunucu` içindeki kimlik doğrulama bağımlılıklarıdır."""
    router = APIRouter()
    for metod, yol, fonksiyon, parametre, yetki, ek in UCLAR:
        if yetki is None:
            bagimlilik = mevcut_kullanici_id
        elif isinstance(yetki, str):
            bagimlilik = izin_kontrol(yetki)
        else:
            bagimlilik = izin_kontrol_biri(*yetki)
        router.add_api_route(yol, yetkiyle_bagla(fonksiyon, parametre, bagimlilik), methods=[metod], **ek)
    return router
