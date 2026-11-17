"""Gerçek PostgreSQL: Oda Kullanımı ucu (aralık süzgeci, iptallerin elenmesi, psikologda kimlik gizleme).

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
def kayitlar():
    etiket = uuid4().hex[:10]
    conn = psycopg2.connect(**VT_AYARLARI)
    conn.autocommit = True
    c = conn.cursor()
    _dogru_veritabani(c)
    admin = _kullanici(c, f"oa_{etiket}", "ADMIN")
    psikologlar = []
    for ad in ("a", "b"):
        kullanici = _kullanici(c, f"op{ad}_{etiket}", "PSIKOLOG")
        c.execute("INSERT INTO personel (kullanici_id, personel_kodu) VALUES (%s, %s) RETURNING personel_id", (kullanici, f"O-{ad}{etiket}"))
        pid = c.fetchone()[0]
        c.execute("INSERT INTO odalar (oda_adi, kapasite) VALUES (%s, 1) RETURNING oda_id", (f"o_oda_{ad}{etiket}",))
        psikologlar.append((kullanici, pid, c.fetchone()[0]))
    kod = f"O-{etiket}-1"
    c.execute("INSERT INTO danisan_kodlari (danisan_kod_id, olusturan_psikolog_id) VALUES (%s, %s)", (kod, psikologlar[0][1]))
    try:
        yield c, admin, psikologlar, kod
    finally:
        app.dependency_overrides.pop(mevcut_kullanici_id, None)
        c.execute("DELETE FROM randevular WHERE danisan_kod_id = %s", (kod,))
        c.execute("DELETE FROM denetim_kayitlari WHERE kullanici_id = ANY(%s)", ([admin] + [p[0] for p in psikologlar],))
        c.execute("DELETE FROM danisan_kodlari WHERE danisan_kod_id = %s", (kod,))
        for kullanici, pid, oda in psikologlar:
            c.execute("DELETE FROM odalar WHERE oda_id = %s", (oda,))
            c.execute("DELETE FROM personel WHERE personel_id = %s", (pid,))
        c.execute("DELETE FROM kullanicilar WHERE kullanici_id = ANY(%s)", ([admin] + [p[0] for p in psikologlar],))
        conn.close()


def _ekle(c, kod, psikolog, gun, saat, durum="PLANLANDI", gorusme="YUZ_YUZE"):
    kullanici, pid, oda = psikolog
    bas = datetime(2031, 3, 3, saat) + timedelta(days=gun)
    c.execute("INSERT INTO randevular (danisan_kod_id, psikolog_id, oda_id, baslangic_zamani, bitis_zamani, durum, gorusme_tipi, terapi_turu) "
              "VALUES (%s, %s, %s, %s, %s, %s, %s, 'BIREYSEL_TERAPI')", (kod, pid, oda, bas, bas + timedelta(hours=1), durum, gorusme))


def test_oda_kullanimi_gercek_veritabaninda(kayitlar):
    c, admin, (psi_a, psi_b), kod = kayitlar
    _ekle(c, kod, psi_a, 0, 9, gorusme="ONLINE")
    _ekle(c, kod, psi_b, 0, 10, durum="TAMAMLANDI")
    _ekle(c, kod, psi_b, 1, 11, durum="IPTAL_EDILDI")                 # iptaller gelmez
    _ekle(c, kod, psi_a, 20, 9)                                       # aralık dışı
    istemci = TestClient(app)
    app.dependency_overrides[mevcut_kullanici_id] = lambda: admin
    aralik = "baslangic=2031-03-03&bitis=2031-03-09"

    veri = istemci.get(f"/api/oda-kullanimi?{aralik}").json()
    assert {psi_a[2], psi_b[2]} <= {o["oda_id"] for o in veri["odalar"]}
    benimki = [r for r in veri["randevular"] if r["oda_id"] in (psi_a[2], psi_b[2])]
    assert [(r["oda_id"], r["durum"]) for r in benimki] == [(psi_a[2], "PLANLANDI"), (psi_b[2], "TAMAMLANDI")]
    assert benimki[0]["psikolog"].startswith("opa_") and benimki[0]["danisan_kod_id"] == kod and benimki[0]["gorusme_tipi"] == "ONLINE"

    app.dependency_overrides[mevcut_kullanici_id] = lambda: psi_a[0]
    veri = istemci.get(f"/api/oda-kullanimi?{aralik}").json()
    kendi = next(r for r in veri["randevular"] if r["oda_id"] == psi_a[2])
    baskasi = next(r for r in veri["randevular"] if r["oda_id"] == psi_b[2])
    assert kendi["psikolog"] and kendi["danisan_kod_id"] == kod and kendi["benim"] is True
    assert (baskasi["psikolog"], baskasi["danisan_kod_id"], baskasi["gorusme_tipi"], baskasi["benim"]) == (None, None, None, False)
    assert baskasi["baslangic_zamani"] and baskasi["durum"] == "TAMAMLANDI"          # doluluk bilgisi görünür

    assert istemci.get("/api/oda-kullanimi?baslangic=2031-03-09&bitis=2031-03-03").status_code == 422
    assert istemci.get("/api/oda-kullanimi?baslangic=2031-01-01&bitis=2031-12-31").status_code == 422


def test_cihaz_rezervasyonu_oda_kullanimina_gelir_gercek_veritabaninda(kayitlar):
    c, admin, (psi_a, psi_b), kod = kayitlar
    etiket = uuid4().hex[:8]
    c.execute("INSERT INTO odalar (oda_adi, kapasite) VALUES (%s, 1) RETURNING oda_id", (f"o_cihaz_oda_{etiket}",))
    oda = c.fetchone()[0]
    c.execute("INSERT INTO bolumler (bolum_adi, sorumlu_ad_soyad) VALUES (%s, %s) RETURNING bolum_id", (f"o_bolum_{etiket}", "Test Sorumlu"))
    bolum = c.fetchone()[0]
    cihazlar = []
    for sira in range(4):
        c.execute("INSERT INTO cihazlar (envanter_kodu, cihaz_adi) VALUES (%s, %s) RETURNING cihaz_id", (f"OK-{etiket}-{sira}", f"o_cihaz_{etiket}_{sira}"))
        cihazlar.append(c.fetchone()[0])
    try:
        def rezerve(cihaz, gun, saat, sure=2, oda_id=oda, iptal=False):
            bas = datetime(2031, 3, 3, saat) + timedelta(days=gun)
            c.execute("INSERT INTO cihaz_rezervasyonlari (cihaz_id, bolum_id, kullanilacak_oda_id, baslangic_zamani, bitis_zamani, iptal_edildi_mi) "
                      "VALUES (%s, %s, %s, %s, %s, %s)", (cihaz, bolum, oda_id, bas, bas + timedelta(hours=sure), iptal))

        rezerve(cihazlar[0], 0, 16)                                   # görünür: 16:00-18:00
        rezerve(cihazlar[1], 1, 9, iptal=True)                        # iptal gelmez
        rezerve(cihazlar[2], 2, 9, oda_id=None)                       # odası seçilmemiş gelmez
        rezerve(cihazlar[3], 20, 9)                                   # aralık dışı
        istemci = TestClient(app)
        aralik = "baslangic=2031-03-03&bitis=2031-03-09"

        app.dependency_overrides[mevcut_kullanici_id] = lambda: admin
        veri = istemci.get(f"/api/oda-kullanimi?{aralik}").json()
        benimki = [r for r in veri["rezervasyonlar"] if r["oda_id"] == oda]
        assert len(benimki) == 1
        assert benimki[0]["baslangic_zamani"].startswith("2031-03-03T16:00") and benimki[0]["bitis_zamani"].startswith("2031-03-03T18:00")
        assert benimki[0]["cihaz_adi"] == f"o_cihaz_{etiket}_0" and benimki[0]["bolum_adi"] == f"o_bolum_{etiket}"

        app.dependency_overrides[mevcut_kullanici_id] = lambda: psi_a[0]                   # PSIKOLOG rolünde CIHAZ_REZERVASYON izni yok
        gizli = [r for r in istemci.get(f"/api/oda-kullanimi?{aralik}").json()["rezervasyonlar"] if r["oda_id"] == oda]
        assert len(gizli) == 1 and (gizli[0]["cihaz_adi"], gizli[0]["bolum_adi"]) == (None, None)
        assert gizli[0]["baslangic_zamani"].startswith("2031-03-03T16:00")                  # oda doluluğu yine görünür
    finally:
        app.dependency_overrides.pop(mevcut_kullanici_id, None)
        c.execute("DELETE FROM cihaz_rezervasyonlari WHERE cihaz_id = ANY(%s)", (cihazlar,))
        c.execute("DELETE FROM cihazlar WHERE cihaz_id = ANY(%s)", (cihazlar,))
        c.execute("DELETE FROM bolumler WHERE bolum_id = %s", (bolum,))
        c.execute("DELETE FROM odalar WHERE oda_id = %s", (oda,))
