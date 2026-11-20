"""Gerçek PostgreSQL: psikolog pasife alınınca oda atamaları kalkar (geçmiş randevular kalır); aktifleşirken oda seçilir.

- Bugünden sonra planlı randevusu olan psikolog pasife alınamaz (409); geçmişte kalan "Planlandı" kayıt engellemez
- Pasifleşince psikolog_odalar temizlenir, randevular ve oda_id'leri aynen kalır
- Aktifleşirken oda zorunlu; cihaz rezervasyonlu oda reddedilir; seçilen odalar yazılır

CI'daki "PostgreSQL Entegrasyon Testleri" işinde (alembic upgrade head sonrası) çalışır; gerçek kayıt oluşturur, sonunda temizler.
"""
import os
from contextlib import closing
from datetime import datetime, timedelta
from uuid import uuid4

import psycopg2
import pytest
from fastapi.testclient import TestClient

from server.sunucu import VT_AYARLARI, app, mevcut_kullanici_id


def _dogru_veritabani(cursor):
    assert os.getenv("TKYS_PG_TEST_ONAY") == "EVET"
    assert VT_AYARLARI["dbname"] == "crkys_alembic_test"
    cursor.execute("SELECT current_database()")
    assert cursor.fetchone()[0] == "crkys_alembic_test"


def _kullanici(cursor, ad, rol):
    cursor.execute("INSERT INTO kullanicilar (kullanici_adi, parola_hash, rol_id) VALUES (%s, 'x', (SELECT rol_id FROM roller WHERE rol_adi = %s)) RETURNING kullanici_id", (ad, rol))
    return cursor.fetchone()[0]


@pytest.fixture
def ortam():
    etiket = uuid4().hex[:10]
    conn = psycopg2.connect(**VT_AYARLARI)
    conn.autocommit = True
    c = conn.cursor()
    _dogru_veritabani(c)
    admin = _kullanici(c, f"pa_{etiket}", "ADMIN")
    psikolog = _kullanici(c, f"pp_{etiket}", "PSIKOLOG")
    c.execute("INSERT INTO personel (kullanici_id, personel_kodu) VALUES (%s, %s) RETURNING personel_id", (psikolog, f"PO-{etiket}"))
    personel = c.fetchone()[0]
    odalar = []
    for ad in ("a", "b"):
        c.execute("INSERT INTO odalar (oda_adi, kapasite) VALUES (%s, 1) RETURNING oda_id", (f"pp_oda_{ad}_{etiket}",))
        odalar.append(c.fetchone()[0])
        c.execute("INSERT INTO psikolog_odalar (kullanici_id, oda_id) VALUES (%s, %s)", (psikolog, odalar[-1]))
    kod = f"PO-{etiket}-1"
    c.execute("INSERT INTO danisan_kodlari (danisan_kod_id, olusturan_psikolog_id) VALUES (%s, %s)", (kod, personel))
    c.execute("INSERT INTO cihazlar (envanter_kodu, cihaz_adi, durum) VALUES (%s, %s, 'Kullanima_Hazir') RETURNING cihaz_id", (f"PO-{etiket}", f"pp_cihaz_{etiket}"))
    cihaz = c.fetchone()[0]
    try:
        yield c, admin, psikolog, personel, odalar, kod, cihaz
    finally:
        app.dependency_overrides.pop(mevcut_kullanici_id, None)
        c.execute("DELETE FROM randevular WHERE danisan_kod_id = %s", (kod,))
        c.execute("DELETE FROM cihaz_rezervasyonlari WHERE cihaz_id = %s", (cihaz,))
        c.execute("DELETE FROM cihazlar WHERE cihaz_id = %s", (cihaz,))
        c.execute("DELETE FROM danisan_kodlari WHERE danisan_kod_id = %s", (kod,))
        c.execute("DELETE FROM psikolog_odalar WHERE kullanici_id = %s", (psikolog,))
        c.execute("DELETE FROM denetim_kayitlari WHERE kullanici_id = ANY(%s)", ([admin, psikolog],))
        c.execute("DELETE FROM odalar WHERE oda_id = ANY(%s)", (odalar,))
        c.execute("DELETE FROM personel WHERE personel_id = %s", (personel,))
        c.execute("DELETE FROM kullanicilar WHERE kullanici_id = ANY(%s)", ([admin, psikolog],))
        conn.close()


def _randevu(c, kod, personel, oda, baslangic, durum="PLANLANDI"):
    c.execute("INSERT INTO randevular (danisan_kod_id, psikolog_id, oda_id, baslangic_zamani, bitis_zamani, durum, gorusme_tipi, terapi_turu) "
              "VALUES (%s, %s, %s, %s, %s, %s, 'YUZ_YUZE', 'BIREYSEL_TERAPI') RETURNING randevu_id",
              (kod, personel, oda, baslangic, baslangic + timedelta(hours=1), durum))
    return c.fetchone()[0]


def _durum(c, psikolog):
    c.execute("SELECT k.aktif_mi, p.aktif_mi FROM kullanicilar k JOIN personel p ON p.kullanici_id = k.kullanici_id WHERE k.kullanici_id = %s", (psikolog,))
    return c.fetchone()


def _atanmis(c, psikolog):
    c.execute("SELECT oda_id FROM psikolog_odalar WHERE kullanici_id = %s ORDER BY oda_id", (psikolog,))
    return [k[0] for k in c.fetchall()]


def test_psikolog_pasife_alinirken_ve_aktiflesirken_odalar_gercek_veritabaninda(ortam):
    c, admin, psikolog, personel, (oda_a, oda_b), kod, cihaz = ortam
    istemci = TestClient(app)
    app.dependency_overrides[mevcut_kullanici_id] = lambda: admin
    degistir = lambda **govde: istemci.patch(f"/api/kullanicilar/{psikolog}/durum-degistir", **({"json": govde} if govde else {}))
    gelecek = datetime.now() + timedelta(days=3)

    # 1) bugünden sonra planlı randevu varsa pasife alınamaz
    gelecek_randevu = _randevu(c, kod, personel, oda_a, gelecek)
    yanit = degistir()
    assert yanit.status_code == 409 and "1 planlı randevusu var" in yanit.json()["detail"]
    assert _durum(c, psikolog) == (True, True) and _atanmis(c, psikolog) == [oda_a, oda_b]

    # 2) iptal edilince ve geçmişte kalan "Planlandı" kaydı engel olmaz; pasife alınır, odalar kalkar, randevular kalır
    c.execute("UPDATE randevular SET durum = 'IPTAL_EDILDI' WHERE randevu_id = %s", (gelecek_randevu,))
    eski_planli = _randevu(c, kod, personel, oda_b, datetime.now() - timedelta(days=5))
    yanit = degistir()
    assert yanit.status_code == 200 and yanit.json()["yeni_durum"] is False
    assert _durum(c, psikolog) == (False, False) and _atanmis(c, psikolog) == []
    c.execute("SELECT randevu_id, oda_id, psikolog_id FROM randevular WHERE danisan_kod_id = %s ORDER BY randevu_id", (kod,))
    assert c.fetchall() == [(gelecek_randevu, oda_a, personel), (eski_planli, oda_b, personel)]      # geçmiş kayıtlar ve oda bilgileri aynen
    c.execute("SELECT count(*) FROM denetim_kayitlari WHERE kullanici_id = %s AND hedef_tablo = 'psikolog_odalar' AND hedef_kayit_id = %s", (admin, psikolog))
    assert c.fetchone()[0] == 2      # UPDATE (önceki/yeni odalar) + DELETE (kaldırılan odalar)

    # 3) aktifleştirirken oda seçilmeli
    assert degistir().status_code == 422 and _durum(c, psikolog) == (False, False)
    assert degistir(oda_idleri=[]).status_code == 422

    # 4) cihaz rezervasyonlu oda seçilemez
    bas = datetime.now() + timedelta(days=2, hours=1)
    c.execute("INSERT INTO cihaz_rezervasyonlari (cihaz_id, kullanilacak_oda_id, baslangic_zamani, bitis_zamani) VALUES (%s, %s, %s, %s)", (cihaz, oda_a, bas, bas + timedelta(hours=1)))
    yanit = degistir(oda_idleri=[oda_a, oda_b])
    assert yanit.status_code == 409 and "psikologa atanamaz" in yanit.json()["detail"]
    assert _durum(c, psikolog) == (False, False) and _atanmis(c, psikolog) == []

    # 5) rezervasyonsuz oda ile aktifleşir; seçilen oda yazılır
    yanit = degistir(oda_idleri=[oda_b])
    assert yanit.status_code == 200 and yanit.json()["yeni_durum"] is True
    assert _durum(c, psikolog) == (True, True) and _atanmis(c, psikolog) == [oda_b]


def test_psikolog_adlari_pasifler_dahil_gercek_veritabaninda(ortam):
    """GET /api/psikologlar?pasifler_dahil=true: randevusu olan eski (başka role geçmiş) psikolog adıyla gelir, aktif_mi = false."""
    c, admin, psikolog, personel, (oda_a, oda_b), kod, cihaz = ortam
    etiket = uuid4().hex[:8]
    eski = _kullanici(c, f"eski_{etiket}", "MEMUR")
    sade = _kullanici(c, f"sade_{etiket}", "MEMUR")
    kayitlar = {}
    for ad, kullanici in (("eski", eski), ("sade", sade)):
        c.execute("INSERT INTO personel (kullanici_id, personel_kodu) VALUES (%s, %s) RETURNING personel_id", (kullanici, f"PA-{ad}-{etiket}"))
        kayitlar[ad] = c.fetchone()[0]
    try:
        _randevu(c, kod, kayitlar["eski"], oda_a, datetime.now() - timedelta(days=30), durum="TAMAMLANDI")     # geçmişte randevusu var
        istemci = TestClient(app)
        app.dependency_overrides[mevcut_kullanici_id] = lambda: admin

        varsayilan = {p["personel_id"] for p in istemci.get("/api/psikologlar").json()}
        assert personel in varsayilan and kayitlar["eski"] not in varsayilan                            # randevu formu: yalnızca aktif psikologlar

        liste = {p["personel_id"]: p for p in istemci.get("/api/psikologlar", params={"pasifler_dahil": "true"}).json()}
        assert liste[personel]["aktif_mi"] is True and liste[personel]["ad_soyad"].startswith("pp_")
        assert liste[kayitlar["eski"]] == {"personel_id": kayitlar["eski"], "ad_soyad": f"eski_{etiket}", "kullanici_id": eski, "aktif_mi": False}
        assert kayitlar["sade"] not in liste                                                            # geçmişi olmayan, psikolog olmayan gelmez

        c.execute("UPDATE kullanicilar SET aktif_mi = FALSE WHERE kullanici_id = %s", (psikolog,))     # pasif psikolog de adıyla gelir
        liste = {p["personel_id"]: p for p in istemci.get("/api/psikologlar", params={"pasifler_dahil": "true"}).json()}
        assert liste[personel]["aktif_mi"] is False and liste[personel]["ad_soyad"].startswith("pp_")
    finally:
        c.execute("DELETE FROM randevular WHERE psikolog_id = %s", (kayitlar["eski"],))
        c.execute("DELETE FROM personel WHERE personel_id = ANY(%s)", (list(kayitlar.values()),))
        c.execute("DELETE FROM kullanicilar WHERE kullanici_id = ANY(%s)", ([eski, sade],))


def test_psikolog_pasife_alininca_danisanlari_pasife_alinir_aktiflesince_geri_acilir_gercek_veritabaninda(ortam):
    """Danışanlar psikologla birlikte pasife alınır; geri açılırken yalnızca BU YÜZDEN pasifleşenler açılır (elle pasif olanlar pasif kalır)."""
    c, admin, psikolog, personel, (oda_a, oda_b), kod, cihaz = ortam
    etiket = uuid4().hex[:8]
    kod_elle, kod_elle_acilan = f"PD-{etiket}-E", f"PD-{etiket}-A"
    c.execute("INSERT INTO danisan_kodlari (danisan_kod_id, olusturan_psikolog_id, aktif_mi) VALUES (%s, %s, FALSE)", (kod_elle, personel))      # elle pasife alınmış
    c.execute("INSERT INTO danisan_kodlari (danisan_kod_id, olusturan_psikolog_id) VALUES (%s, %s)", (kod_elle_acilan, personel))                # aktif
    durum = lambda k: (c.execute("SELECT aktif_mi, psikolog_pasifligi_nedeniyle_pasif FROM danisan_kodlari WHERE danisan_kod_id = %s", (k,)), c.fetchone())[1]
    try:
        istemci = TestClient(app)
        app.dependency_overrides[mevcut_kullanici_id] = lambda: admin
        degistir = lambda **govde: istemci.patch(f"/api/kullanicilar/{psikolog}/durum-degistir", **({"json": govde} if govde else {}))

        yanit = degistir()                                                                       # psikolog pasife alınır
        assert yanit.status_code == 200 and yanit.json()["pasife_alinan_danisan"] == 2           # kod ve kod_elle_acilan (kod_elle zaten pasifti)
        assert durum(kod) == (False, True) and durum(kod_elle_acilan) == (False, True)           # psikolog yüzünden pasif, işaretli
        assert durum(kod_elle) == (False, False)                                                 # elle pasif olan işaretlenmez
        c.execute("SELECT count(*) FROM denetim_kayitlari WHERE kullanici_id = %s AND hedef_tablo = 'danisan_kodlari'", (admin,))
        assert c.fetchone()[0] == 1

        yanit = istemci.patch(f"/api/danisan-kodlari/{kod_elle_acilan}/durum", params={"aktif_mi": "true"})   # psikolog pasifken elle açılamaz
        assert yanit.status_code == 409 and "psikologu şu an pasif" in yanit.json()["detail"]
        assert durum(kod_elle_acilan) == (False, True)                                           # değişmedi, işaret duruyor

        yanit = degistir(oda_idleri=[oda_a])                                                     # psikolog yeniden aktif
        assert yanit.status_code == 200 and yanit.json()["aktif_edilen_danisan"] == 2            # psikolog yüzünden pasif olan ikisi geri açıldı
        assert durum(kod) == (True, False) and durum(kod_elle_acilan) == (True, False)
        assert durum(kod_elle) == (False, False)                                                 # elle pasif olan pasif kaldı
    finally:
        c.execute("DELETE FROM danisan_kodlari WHERE danisan_kod_id = ANY(%s)", ([kod_elle, kod_elle_acilan],))


def test_rol_degisince_danisanlar_pasife_alinir_psikolog_olunca_geri_acilir_gercek_veritabaninda(ortam):
    """Psikologluktan çıkan kişinin danışanları pasife alınır; yeniden psikolog olunca yalnızca BU YÜZDEN pasifleşenler geri açılır."""
    c, admin, psikolog, personel, (oda_a, oda_b), kod, cihaz = ortam
    kod_elle = f"{kod}-E"
    c.execute("INSERT INTO danisan_kodlari (danisan_kod_id, olusturan_psikolog_id, aktif_mi) VALUES (%s, %s, FALSE)", (kod_elle, personel))     # elle pasif
    durum = lambda k: (c.execute("SELECT aktif_mi, psikolog_pasifligi_nedeniyle_pasif FROM danisan_kodlari WHERE danisan_kod_id = %s", (k,)), c.fetchone())[1]
    c.execute("SELECT rol_adi, rol_id FROM roller WHERE rol_adi IN ('MEMUR', 'PSIKOLOG')")
    roller = dict(c.fetchall())
    try:
        istemci = TestClient(app)
        app.dependency_overrides[mevcut_kullanici_id] = lambda: admin
        yanit = istemci.patch(f"/api/kullanicilar/{psikolog}/rol", json={"rol_id": roller["MEMUR"]})
        assert yanit.status_code == 200 and yanit.json()["pasife_alinan_danisan"] == 1 and "1 danışan pasife alındı" in yanit.json()["mesaj"]
        assert durum(kod) == (False, True) and durum(kod_elle) == (False, False)

        yanit = istemci.patch(f"/api/kullanicilar/{psikolog}/rol", json={"rol_id": roller["PSIKOLOG"], "oda_idleri": [oda_a]})
        assert yanit.status_code == 200 and yanit.json()["aktif_edilen_danisan"] == 1
        assert durum(kod) == (True, False) and durum(kod_elle) == (False, False)               # elle pasif olan pasif kaldı
    finally:
        c.execute("DELETE FROM danisan_kodlari WHERE danisan_kod_id = %s", (kod_elle,))


def test_danisan_kodu_yil_bazli_ve_sayac_tuketmez_gercek_veritabaninda(ortam):
    from server.sunucu import otomatik_danisan_kodu_uret
    c = ortam[0]
    kodlar = ["DAN-2077-0004", "DAN-2077-0010", "DAN-2077-ABC"]                                 # sonuncusu kalıba uymaz, yok sayılır
    for k in kodlar:
        c.execute("INSERT INTO danisan_kodlari (danisan_kod_id) VALUES (%s)", (k,))
    try:
        assert otomatik_danisan_kodu_uret(c, yil=2077) == "DAN-2077-0011"                       # o yılın en büyüğü + 1
        assert otomatik_danisan_kodu_uret(c, yil=2077, kilitle=False) == "DAN-2077-0011"        # önizleme aynı kodu verir, tüketmez
        assert otomatik_danisan_kodu_uret(c, yil=2078) == "DAN-2078-0001"                       # yeni yıl 0001'den başlar
    finally:
        c.execute("DELETE FROM danisan_kodlari WHERE danisan_kod_id = ANY(%s)", (kodlar,))


def test_iptal_notunu_randevu_duzenleme_izni_olan_gorur_ve_durum_degisikligi_denetlenir_gercek_veritabaninda(ortam):
    c, admin, psikolog, personel, (oda_a, oda_b), kod, cihaz = ortam
    randevu = _randevu(c, kod, personel, oda_a, datetime.now() + timedelta(days=3))
    istemci = TestClient(app)
    app.dependency_overrides[mevcut_kullanici_id] = lambda: admin
    yanit = istemci.patch(f"/api/randevular/{randevu}/iptal", json={"iptal_nedeni": "DANISAN_TALEBI", "iptal_notu": "ozel not"})
    assert yanit.status_code == 200
    satir = next(r for r in istemci.get("/api/randevular").json() if r["randevu_id"] == randevu)
    assert satir["iptal_notu"] == "ozel not"                                                    # admin RANDEVU_DUZENLE iznine sahip
    c.execute("SELECT ayrinti FROM denetim_kayitlari WHERE kullanici_id = %s AND olay_turu = 'CANCEL' AND hedef_kayit_id = %s", (admin, randevu))
    assert c.fetchone()[0] == {"onceki": "PLANLANDI", "yeni": "IPTAL_EDILDI", "iptal_nedeni": "DANISAN_TALEBI"}   # neyden neye


def test_kullanilmayan_danisan_kodu_sayaci_kaldirilmistir_gercek_veritabaninda():
    """Kod artık yıl bazlı üretilir; global sayaç (danisan_kodu_seq) migration ile kaldırılmıştır."""
    with closing(psycopg2.connect(**VT_AYARLARI)) as conn:
        cur = conn.cursor()
        _dogru_veritabani(cur)
        cur.execute("SELECT to_regclass('danisan_kodu_seq')")
        assert cur.fetchone()[0] is None


def test_pasif_rol_kullanicilarin_girisini_engeller_gercek_veritabaninda(ortam):
    """Rol pasife alınınca o roldekiler giremez (yeni giriş ve açık oturum); aktif edilince girebilirler; kendi rolünü kimse pasife alamaz."""
    from server.guvenlik import parola_hashle
    from server.sunucu import ROL_PASIF_GIRIS_MESAJI

    c, admin = ortam[0], ortam[1]
    etiket = uuid4().hex[:8]
    parola = "Test-Parola-1!"
    c.execute("INSERT INTO roller (rol_adi, gorunen_ad) VALUES (%s, %s) RETURNING rol_id", (f"PR_ROL_{etiket}".upper(), f"pr_rol_{etiket}"))
    rol_id = c.fetchone()[0]
    c.execute("INSERT INTO kullanicilar (kullanici_adi, parola_hash, rol_id, ilk_giris_mi) VALUES (%s, %s, %s, FALSE) RETURNING kullanici_id",
              (f"pr_k_{etiket}", parola_hashle(parola), rol_id))
    kullanici = c.fetchone()[0]
    c.execute("INSERT INTO personel (kullanici_id, personel_kodu) VALUES (%s, %s) RETURNING personel_id", (kullanici, f"PR-{etiket}"))
    personel = c.fetchone()[0]
    try:
        istemci = TestClient(app)
        giris = lambda: istemci.post("/api/login", json={"kullanici_adi": f"pr_k_{etiket}", "parola": parola})
        yanit = giris()
        assert yanit.status_code == 200
        baslik = {"Authorization": f"Bearer {yanit.json()['access_token']}"}
        assert istemci.get("/api/yetkilerim", headers=baslik).status_code == 200                # açık oturum çalışıyor

        app.dependency_overrides[mevcut_kullanici_id] = lambda: admin
        yanit = istemci.put(f"/api/roller/{rol_id}", json={"gorunen_ad": f"pr_rol_{etiket}", "aktif_mi": False})
        assert yanit.status_code == 200 and yanit.json()["etkilenen_kullanici"] == 1
        app.dependency_overrides.pop(mevcut_kullanici_id, None)

        yanit = giris()
        assert yanit.status_code == 403 and yanit.json()["detail"] == ROL_PASIF_GIRIS_MESAJI       # yeni giriş engellendi
        yanlis = istemci.post("/api/login", json={"kullanici_adi": f"pr_k_{etiket}", "parola": "Yanlis-Parola-1"})
        assert yanlis.status_code == 401                                                           # yanlış parola hiçbir şey ele vermez
        yanit = istemci.get("/api/yetkilerim", headers=baslik)
        assert yanit.status_code == 403 and yanit.json()["detail"] == ROL_PASIF_GIRIS_MESAJI       # açık oturum da düştü

        app.dependency_overrides[mevcut_kullanici_id] = lambda: admin
        assert istemci.put(f"/api/roller/{rol_id}", json={"gorunen_ad": f"pr_rol_{etiket}", "aktif_mi": True}).status_code == 200
        app.dependency_overrides.pop(mevcut_kullanici_id, None)
        assert giris().status_code == 200                                                          # aktif edilince geri girer

        # Kendi rolünü pasife alma: rolün kullanıcısı rolü pasife alamaz
        app.dependency_overrides[mevcut_kullanici_id] = lambda: kullanici
        c.execute("INSERT INTO rol_izinleri (rol_id, izin_id, izin_var) SELECT %s, izin_id, 1 FROM izinler WHERE izin_adi = 'ROL_DUZENLE'", (rol_id,))
        yanit = istemci.put(f"/api/roller/{rol_id}", json={"gorunen_ad": f"pr_rol_{etiket}", "aktif_mi": False})
        assert yanit.status_code == 409 and "Kendi rolünüzü" in yanit.json()["detail"]
    finally:
        app.dependency_overrides.pop(mevcut_kullanici_id, None)
        c.execute("DELETE FROM rol_izinleri WHERE rol_id = %s", (rol_id,))
        c.execute("DELETE FROM denetim_kayitlari WHERE kullanici_id = %s OR (hedef_tablo = 'roller' AND hedef_kayit_id = %s) OR (hedef_tablo = 'kullanicilar' AND hedef_kayit_id = %s)",
                  (kullanici, rol_id, kullanici))
        c.execute("DELETE FROM personel WHERE personel_id = %s", (personel,))
        c.execute("DELETE FROM kullanicilar WHERE kullanici_id = %s", (kullanici,))
        c.execute("DELETE FROM roller WHERE rol_id = %s", (rol_id,))


def test_personel_aktifligi_api_ile_degistirilemez_gercek_veritabaninda(ortam):
    c, admin, psikolog, personel = ortam[0], ortam[1], ortam[2], ortam[3]
    istemci = TestClient(app)
    app.dependency_overrides[mevcut_kullanici_id] = lambda: admin
    yanit = istemci.patch(f"/api/personel/{personel}", json={"aktif_mi": False})
    assert yanit.status_code == 422                                                              # alan artık kabul edilmiyor
    c.execute("SELECT aktif_mi FROM personel WHERE personel_id = %s", (personel,))
    assert c.fetchone()[0] is True


# ----------------------------------------------------------------------------------------------------------------------
# Denetim kayıtlarında "önceki → yeni" ayrıntısı (gerçek veritabanı)
# ----------------------------------------------------------------------------------------------------------------------
def test_rol_degistirme_ve_durum_degistirme_onceki_yeni_degeri_denetime_yazar_gercek_veritabaninda(ortam):
    c, admin, psikolog, personel, (oda_a, oda_b), kod, cihaz = ortam
    istemci = TestClient(app)
    app.dependency_overrides[mevcut_kullanici_id] = lambda: admin
    c.execute("SELECT rol_id FROM roller WHERE rol_adi = 'MEMUR'")
    memur = c.fetchone()[0]

    yanit = istemci.patch(f"/api/kullanicilar/{psikolog}/rol", json={"rol_id": memur})
    assert yanit.status_code == 200
    c.execute("SELECT ayrinti FROM denetim_kayitlari WHERE olay_turu = 'ROLE_CHANGE' AND hedef_kayit_id = %s AND kullanici_id = %s ORDER BY denetim_id DESC LIMIT 1", (psikolog, admin))
    ayrinti = c.fetchone()[0]
    assert ayrinti["onceki"]["rol"] == "PSIKOLOG" and ayrinti["yeni"]["rol"] == "MEMUR"
    assert ayrinti["onceki"]["personel_kodu"].startswith("PO-") and ayrinti["yeni"]["personel_kodu"] != ayrinti["onceki"]["personel_kodu"]
    assert ayrinti["pasife_alinan_danisan"] == 1
    c.execute("SELECT ayrinti FROM denetim_kayitlari WHERE hedef_tablo = 'danisan_kodlari' AND kullanici_id = %s AND ayrinti->>'psikolog_kullanici_id' = %s", (admin, str(psikolog)))
    assert c.fetchone()[0]["etkilenen_danisan"] == 1                                         # danışanların toplu pasife alınması da kim/neden/kaç ile kayıtlı

    yanit = istemci.patch(f"/api/kullanicilar/{psikolog}/durum-degistir")                     # memur artık: pasife al
    assert yanit.status_code == 200
    c.execute("SELECT ayrinti FROM denetim_kayitlari WHERE olay_turu = 'UPDATE' AND hedef_tablo = 'kullanicilar' AND hedef_kayit_id = %s AND kullanici_id = %s "
              "ORDER BY denetim_id DESC LIMIT 1", (psikolog, admin))
    ayrinti = c.fetchone()[0]
    assert ayrinti["onceki"] == {"aktif_mi": True} and ayrinti["yeni"] == {"aktif_mi": False} and ayrinti["rol"] == "MEMUR"


def test_izin_olusturma_ve_duzenleme_denetime_yazilir_yinelenen_ad_409_gercek_veritabaninda(ortam):
    c, admin = ortam[0], ortam[1]
    etiket = uuid4().hex[:8].upper()
    istemci = TestClient(app)
    app.dependency_overrides[mevcut_kullanici_id] = lambda: admin
    c.execute("SELECT rol_id, rol_adi FROM roller WHERE rol_adi IN ('ADMIN', 'MEMUR')")
    roller = {ad: rid for rid, ad in c.fetchall()}
    izin_id = None
    try:
        yanit = istemci.post("/api/izinler", json={"izin_adi": f"TEST_IZIN_{etiket}"})
        assert yanit.status_code == 201
        izin_id = yanit.json()["izin_id"]
        assert istemci.post("/api/izinler", json={"izin_adi": f"TEST_IZIN_{etiket}"}).status_code == 409           # aynı ad: 500 değil 409

        yanit = istemci.put(f"/api/izinler/{izin_id}", json={"gorunen_ad": "Deneme izni", "verilen_rol_idleri": [roller["ADMIN"], roller["MEMUR"]]})
        assert yanit.status_code == 200
        c.execute("SELECT olay_turu::text, ayrinti FROM denetim_kayitlari WHERE hedef_tablo = 'izinler' AND hedef_kayit_id = %s AND kullanici_id = %s ORDER BY denetim_id", (izin_id, admin))
        (olay1, olusturma), (olay2, duzenleme) = c.fetchall()
        assert olay1 == "CREATE" and olusturma["yeni"] == {"izin_adi": f"TEST_IZIN_{etiket}", "verilen_roller": ["ADMIN"]}
        assert olay2 == "UPDATE" and duzenleme["izin"] == f"TEST_IZIN_{etiket}"
        assert duzenleme["onceki"]["verilen_roller"] == ["ADMIN"] and duzenleme["yeni"]["verilen_roller"] == ["ADMIN", "MEMUR"]
        assert duzenleme["eklenen_roller"] == ["MEMUR"] and duzenleme["kaldirilan_roller"] == []
        assert duzenleme["yeni"]["gorunen_ad"] == "Deneme izni"
    finally:
        if izin_id is not None:
            c.execute("DELETE FROM denetim_kayitlari WHERE hedef_tablo = 'izinler' AND hedef_kayit_id = %s", (izin_id,))
            c.execute("DELETE FROM rol_izinleri WHERE izin_id = %s", (izin_id,))
            c.execute("DELETE FROM izinler WHERE izin_id = %s", (izin_id,))


def test_audit_suzgeci_parola_olaylarini_kabul_eder_gercek_veritabaninda(ortam):
    admin = ortam[1]
    istemci = TestClient(app)
    app.dependency_overrides[mevcut_kullanici_id] = lambda: admin
    for olay in ("PASSWORD_RESET", "PASSWORD_CHANGE", "PASSWORD_CHANGE_FAILED", "EXPORT"):
        assert istemci.get("/api/audit-kayitlari", params={"olay_turu": olay}).status_code == 200, olay
