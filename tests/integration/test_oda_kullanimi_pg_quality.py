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
