"""Gerçek PostgreSQL: cihaz rezervasyonu için kullanılan oda psikologa atanamaz (409); iptal edilmiş ya da bitmiş rezervasyon engellemez.

CI'daki "PostgreSQL Entegrasyon Testleri" işinde (alembic upgrade head sonrası) çalışır; gerçek kayıt oluşturur, sonunda temizler.
"""
import os
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
    admin = _kullanici(c, f"ca_{etiket}", "ADMIN")
    psikologlar = [_kullanici(c, f"cp{n}_{etiket}", "PSIKOLOG") for n in (1, 2)]
    odalar = {}
    for ad in ("cihaz", "bos", "gecmis"):
        c.execute("INSERT INTO odalar (oda_adi, kapasite) VALUES (%s, 1) RETURNING oda_id", (f"ca_oda_{ad}_{etiket}",))
        odalar[ad] = c.fetchone()[0]
    cihazlar = []
    for sira in range(4):
        c.execute("INSERT INTO cihazlar (envanter_kodu, cihaz_adi) VALUES (%s, %s) RETURNING cihaz_id", (f"CA-{etiket}-{sira}", f"ca_cihaz_{sira}"))
        cihazlar.append(c.fetchone()[0])
    try:
        yield c, admin, psikologlar, odalar, cihazlar, etiket
    finally:
        app.dependency_overrides.pop(mevcut_kullanici_id, None)
        kullanicilar = [admin] + psikologlar
        c.execute("DELETE FROM cihaz_rezervasyonlari WHERE cihaz_id = ANY(%s)", (cihazlar,))
        c.execute("DELETE FROM cihazlar WHERE cihaz_id = ANY(%s)", (cihazlar,))
        c.execute("DELETE FROM psikolog_odalar WHERE kullanici_id = ANY(%s)", (kullanicilar,))
        c.execute("DELETE FROM denetim_kayitlari WHERE kullanici_id = ANY(%s)", (kullanicilar,))
        c.execute("DELETE FROM odalar WHERE oda_id = ANY(%s)", (list(odalar.values()),))
        c.execute("DELETE FROM kullanicilar WHERE kullanici_id = ANY(%s)", (kullanicilar,))
        conn.close()


def _rezerve(c, cihaz, oda, baslangic, sure=2, iptal=False):
    c.execute("INSERT INTO cihaz_rezervasyonlari (cihaz_id, kullanilacak_oda_id, baslangic_zamani, bitis_zamani, iptal_edildi_mi) VALUES (%s, %s, %s, %s, %s) RETURNING rezervasyon_id",
              (cihaz, oda, baslangic, baslangic + timedelta(hours=sure), iptal))
    return c.fetchone()[0]


def _atanmis(c, kullanici):
    c.execute("SELECT oda_id FROM psikolog_odalar WHERE kullanici_id = %s ORDER BY oda_id", (kullanici,))
    return [k[0] for k in c.fetchall()]


def test_cihaz_rezervasyonlu_oda_psikologa_atanamaz_gercek_veritabaninda(ortam):
    c, admin, (psi1, psi2), odalar, cihazlar, etiket = ortam
    istemci = TestClient(app)
    app.dependency_overrides[mevcut_kullanici_id] = lambda: admin
    atama = lambda kullanici, *oda_idleri: istemci.put(f"/api/kullanicilar/{kullanici}/odalar", json={"oda_idleri": list(oda_idleri)})
    gelecek = datetime.now() + timedelta(days=3)

    rezervasyon = _rezerve(c, cihazlar[0], odalar["cihaz"], gelecek)                       # gelecekteki rezervasyon
    yanit = atama(psi1, odalar["cihaz"])
    assert yanit.status_code == 409
    assert f"ca_oda_cihaz_{etiket} (1 rezervasyon)" in yanit.json()["detail"] and "psikologa atanamaz" in yanit.json()["detail"]
    assert _atanmis(c, psi1) == []                                                          # atama yazılmadı

    yanit = atama(psi1, odalar["bos"], odalar["cihaz"])                                     # karışık liste de tamamen reddedilir
    assert yanit.status_code == 409 and _atanmis(c, psi1) == []

    assert atama(psi1, odalar["bos"]).status_code == 200                                    # rezervasyonsuz oda atanır
    assert _atanmis(c, psi1) == [odalar["bos"]]

    c.execute("UPDATE cihaz_rezervasyonlari SET iptal_edildi_mi = TRUE WHERE rezervasyon_id = %s", (rezervasyon,))
    assert atama(psi1, odalar["cihaz"]).status_code == 200                                  # iptal edilince oda serbest
    assert _atanmis(c, psi1) == [odalar["cihaz"]]

    _rezerve(c, cihazlar[1], odalar["gecmis"], datetime.now() - timedelta(days=5))          # bitmiş rezervasyon engellemez
    assert atama(psi2, odalar["gecmis"]).status_code == 200

    _rezerve(c, cihazlar[2], odalar["cihaz"], gelecek + timedelta(days=1))                  # psi1'e atanmış odaya sonradan rezervasyon girilmiş
    assert atama(psi1, odalar["cihaz"], odalar["bos"]).status_code == 200                   # mevcut atama korunur, güncelleme engellenmez
    assert sorted(_atanmis(c, psi1)) == sorted([odalar["cihaz"], odalar["bos"]])
    assert atama(psi2, odalar["cihaz"]).status_code == 409                                  # başka psikolog aynı odayı alamaz


def test_rezervasyon_sahiplik_duzenleme_ve_iptal_gercek_veritabaninda():
    """Rezervasyonu yalnızca oluşturan ya da yönetici (CIHAZ_ENVANTER_YONET) değiştirir/iptal eder; düzenlemede rezervasyonun kendisi çakışma sayılmaz."""
    etiket = uuid4().hex[:8]
    conn = psycopg2.connect(**VT_AYARLARI)
    conn.autocommit = True
    c = conn.cursor()
    _dogru_veritabani(c)

    def kul(ad, rol):
        c.execute(
            "INSERT INTO kullanicilar (kullanici_adi, parola_hash, rol_id, personel_id, personel_kodu) VALUES "
            "(%s, 'x', (SELECT rol_id FROM roller WHERE rol_adi = %s), (SELECT COALESCE(MAX(personel_id), 0) + 1 FROM kullanicilar), %s) RETURNING kullanici_id",
            (f"{ad}_{etiket}", rol, f"P-{ad}-{etiket}"))
        return c.fetchone()[0]

    sahip, baskasi, yonetici = kul("rs1", "PROJE_ASISTANI"), kul("rs2", "PROJE_ASISTANI"), kul("rsm", "MEMUR")
    c.execute("INSERT INTO odalar (oda_adi, kapasite) VALUES (%s, 1), (%s, 1) RETURNING oda_id", (f"rs_oda1_{etiket}", f"rs_oda2_{etiket}"))
    odalar = [r[0] for r in c.fetchall()]
    c.execute("INSERT INTO bolumler (bolum_adi, sorumlu_ad_soyad) VALUES (%s, 'x') RETURNING bolum_id", (f"rs_b_{etiket}",))
    bolum = c.fetchone()[0]
    c.execute("INSERT INTO cihazlar (envanter_kodu, cihaz_adi) VALUES (%s, 'RS') RETURNING cihaz_id", (f"RS-{etiket}",))
    cihaz = c.fetchone()[0]
    istemci = TestClient(app)
    g = (datetime.now() + timedelta(days=2)).replace(hour=10, minute=0, second=0, microsecond=0)

    def ben(k):
        app.dependency_overrides[mevcut_kullanici_id] = lambda: k

    def govde(**k):
        veri = {"bolum_id": bolum, "kullanilacak_oda_id": odalar[0], "baslangic_zamani": g.isoformat(),
                "bitis_zamani": (g + timedelta(hours=2)).isoformat(), "proje_adi_aciklamasi": "yeni", "proje_turu": None}
        veri.update(k)
        return veri
    try:
        ben(sahip)
        r = istemci.post("/api/rezervasyonlar", json={"cihaz_id": cihaz, **{k: v for k, v in govde().items() if k not in ("proje_turu",)}})
        assert r.status_code == 201
        rid = r.json()["rezervasyon_id"]
        liste = {x["rezervasyon_id"]: x for x in istemci.get("/api/rezervasyonlar").json()}
        assert liste[rid]["yonetebilir"] is True and liste[rid]["rezerve_eden"] == f"rs1_{etiket}"

        ben(baskasi)
        assert {x["rezervasyon_id"]: x for x in istemci.get("/api/rezervasyonlar").json()}[rid]["yonetebilir"] is False
        assert istemci.put(f"/api/rezervasyonlar/{rid}", json=govde()).status_code == 403
        assert istemci.patch(f"/api/rezervasyonlar/{rid}/iptal").status_code == 403

        ben(sahip)
        kaydir = govde(baslangic_zamani=(g + timedelta(hours=1)).isoformat(), bitis_zamani=(g + timedelta(hours=3)).isoformat())
        assert istemci.put(f"/api/rezervasyonlar/{rid}", json=kaydir).status_code == 200                # kendisiyle çakışmaz
        oda_degis = govde(kullanilacak_oda_id=odalar[1], baslangic_zamani=kaydir["baslangic_zamani"], bitis_zamani=kaydir["bitis_zamani"])
        assert istemci.put(f"/api/rezervasyonlar/{rid}", json=oda_degis).status_code == 200
        gecmis = govde(baslangic_zamani=(g - timedelta(days=9)).isoformat(), bitis_zamani=(g - timedelta(days=9, hours=-1)).isoformat())
        assert istemci.put(f"/api/rezervasyonlar/{rid}", json=gecmis).status_code == 422

        ben(yonetici)
        assert istemci.patch(f"/api/rezervasyonlar/{rid}/iptal").status_code == 200                      # yönetici başkasınınkini iptal edebilir
        assert istemci.patch(f"/api/rezervasyonlar/{rid}/iptal").status_code == 409                      # zaten iptal
        assert istemci.put(f"/api/rezervasyonlar/{rid}", json=govde()).status_code == 409                # iptal edilmiş düzenlenmez
    finally:
        app.dependency_overrides.pop(mevcut_kullanici_id, None)
        c.execute("DELETE FROM cihaz_rezervasyonlari WHERE cihaz_id = %s", (cihaz,))
        c.execute("DELETE FROM cihazlar WHERE cihaz_id = %s", (cihaz,))
        kullanicilar = [sahip, baskasi, yonetici]
        c.execute("DELETE FROM denetim_kayitlari WHERE kullanici_id = ANY(%s)", (kullanicilar,))
        c.execute("DELETE FROM kullanicilar WHERE kullanici_id = ANY(%s)", (kullanicilar,))
        c.execute("DELETE FROM odalar WHERE oda_id = ANY(%s)", (odalar,))
        c.execute("DELETE FROM bolumler WHERE bolum_id = %s", (bolum,))
        conn.close()


def test_cihaz_gecmisi_tum_kayit_turlerini_zaman_cizgisinde_dondurur_ve_yonetici_izni_ister():
    """GET /api/cihazlar/{id}/gecmis: bakım, kalibrasyon, arıza, rezervasyon en yeni önce; özet sayılar; yetkisiz 403, olmayan cihaz 404."""
    etiket = uuid4().hex[:8]
    conn = psycopg2.connect(**VT_AYARLARI)
    conn.autocommit = True
    c = conn.cursor()
    _dogru_veritabani(c)

    def kul(ad, rol):
        c.execute(
            "INSERT INTO kullanicilar (kullanici_adi, parola_hash, rol_id, personel_id, personel_kodu) VALUES "
            "(%s, 'x', (SELECT rol_id FROM roller WHERE rol_adi = %s), (SELECT COALESCE(MAX(personel_id), 0) + 1 FROM kullanicilar), %s) RETURNING kullanici_id",
            (f"{ad}_{etiket}", rol, f"P-{ad}-{etiket}"))
        return c.fetchone()[0]

    yonetici, asistan = kul("cg1", "ADMIN"), kul("cg2", "PROJE_ASISTANI")
    c.execute("INSERT INTO odalar (oda_adi, kapasite) VALUES (%s, 1) RETURNING oda_id", (f"cg_oda_{etiket}",))
    oda = c.fetchone()[0]
    c.execute("INSERT INTO bolumler (bolum_adi, sorumlu_ad_soyad) VALUES (%s, 'x') RETURNING bolum_id", (f"cg_b_{etiket}",))
    bolum = c.fetchone()[0]
    c.execute("INSERT INTO cihazlar (envanter_kodu, cihaz_adi) VALUES (%s, 'CG') RETURNING cihaz_id", (f"CG-{etiket}",))
    cihaz = c.fetchone()[0]
    bugun = datetime.now().date()
    c.execute("INSERT INTO cihaz_bakimlari (cihaz_id, bakim_yapan_kisi, yapilan_islem, maliyet, bakim_tarihi, bakim_baslangic_tarihi, bakim_bitis_tarihi) "
              "VALUES (%s, 'Ece', 'Filtre', 1200.5, %s, %s, %s)", (cihaz, bugun - timedelta(days=60), bugun - timedelta(days=60), bugun - timedelta(days=60)))
    c.execute("INSERT INTO cihaz_kalibrasyonlari (cihaz_id, kalibrasyon_yapan_kurum, gecerlilik_tarihi, sertifika_no, kalibrasyon_baslangic_tarihi, kalibrasyon_bitis_tarihi) "
              "VALUES (%s, 'Kurum', %s, 'S-9', %s, %s)", (cihaz, bugun + timedelta(days=200), bugun - timedelta(days=30), bugun - timedelta(days=30)))
    c.execute("INSERT INTO cihaz_arizalari (cihaz_id, bildiren_personel, ariza_baslik, ariza_aciklamasi, aciliyet, bildirim_tarihi, cozuldu_mu) "
              "VALUES (%s, 'ali', 'Ses', 'yok', 'Düşük', now() - interval '2 days', FALSE)", (cihaz,))
    g = datetime.now() + timedelta(days=3)
    c.execute("INSERT INTO cihaz_rezervasyonlari (cihaz_id, bolum_id, kullanilacak_oda_id, baslangic_zamani, bitis_zamani) VALUES (%s, %s, %s, %s, %s)",
              (cihaz, bolum, oda, g, g + timedelta(hours=2)))
    istemci = TestClient(app)
    try:
        app.dependency_overrides[mevcut_kullanici_id] = lambda: yonetici
        yanit = istemci.get(f"/api/cihazlar/{cihaz}/gecmis")
        assert yanit.status_code == 200
        veri = yanit.json()
        assert [o["tur"] for o in veri["olaylar"]] == ["Rezervasyon", "Arıza", "Kalibrasyon", "Bakım"]          # en yeni önce
        assert veri["cihaz"]["envanter_kodu"] == f"CG-{etiket}" and veri["cihaz"]["etkin_durum"]
        assert veri["ozet"]["bakim_sayisi"] == 1 and veri["ozet"]["toplam_bakim_maliyeti"] == 1200.5 and veri["ozet"]["acik_ariza_sayisi"] == 1
        assert veri["ozet"]["rezervasyon_sayisi"] == 1 and veri["ozet"]["rezervasyon_saati"] == 2.0 and veri["ozet"]["kalibrasyon_sayisi"] == 1
        assert veri["olaylar"][1]["durum"] == "Açık" and "Maliyet: 1.200,50" in veri["olaylar"][3]["ayrinti"]
        assert istemci.get("/api/cihazlar/999999999/gecmis").status_code == 404
        app.dependency_overrides[mevcut_kullanici_id] = lambda: asistan
        assert istemci.get(f"/api/cihazlar/{cihaz}/gecmis").status_code == 403
    finally:
        app.dependency_overrides.pop(mevcut_kullanici_id, None)
        for tablo in ("cihaz_rezervasyonlari", "cihaz_arizalari", "cihaz_bakimlari", "cihaz_kalibrasyonlari"):
            c.execute(f"DELETE FROM {tablo} WHERE cihaz_id = %s", (cihaz,))
        c.execute("DELETE FROM cihazlar WHERE cihaz_id = %s", (cihaz,))
        c.execute("DELETE FROM denetim_kayitlari WHERE kullanici_id = ANY(%s)", ([yonetici, asistan],))
        c.execute("DELETE FROM kullanicilar WHERE kullanici_id = ANY(%s)", ([yonetici, asistan],))
        c.execute("DELETE FROM odalar WHERE oda_id = %s", (oda,))
        c.execute("DELETE FROM bolumler WHERE bolum_id = %s", (bolum,))
        conn.close()
