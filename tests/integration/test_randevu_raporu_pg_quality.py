"""Gerçek PostgreSQL: randevu raporu ucu (sayılar, süzgeçler, psikolog yetkisi, detay).

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
    admin = _kullanici(c, f"ra_{etiket}", "ADMIN")
    psikologlar = []
    for ad in ("a", "b"):
        kullanici = _kullanici(c, f"rp{ad}_{etiket}", "PSIKOLOG")
        c.execute("INSERT INTO personel (kullanici_id, personel_kodu) VALUES (%s, %s) RETURNING personel_id", (kullanici, f"R-{ad}{etiket}"))
        pid = c.fetchone()[0]
        c.execute("INSERT INTO odalar (oda_adi, kapasite) VALUES (%s, 1) RETURNING oda_id", (f"r_oda_{ad}{etiket}",))
        oda = c.fetchone()[0]
        psikologlar.append((kullanici, pid, oda))
    kodlar = [f"R-{etiket}-{i}" for i in range(3)]
    for kod, yas in zip(kodlar, ("COCUK", "YETISKIN", None)):
        c.execute("INSERT INTO danisan_kodlari (danisan_kod_id, olusturan_psikolog_id, yas_grubu) VALUES (%s, %s, %s)", (kod, psikologlar[0][1], yas))
    try:
        yield c, admin, psikologlar, kodlar
    finally:
        app.dependency_overrides.pop(mevcut_kullanici_id, None)
        c.execute("DELETE FROM randevular WHERE danisan_kod_id = ANY(%s)", (kodlar,))
        c.execute("DELETE FROM denetim_kayitlari WHERE kullanici_id = ANY(%s)", ([admin] + [p[0] for p in psikologlar],))
        c.execute("DELETE FROM danisan_kodlari WHERE danisan_kod_id = ANY(%s)", (kodlar,))
        for kullanici, pid, oda in psikologlar:
            c.execute("DELETE FROM odalar WHERE oda_id = %s", (oda,))
            c.execute("DELETE FROM personel WHERE personel_id = %s", (pid,))
        c.execute("DELETE FROM kullanicilar WHERE kullanici_id = ANY(%s)", ([admin] + [p[0] for p in psikologlar],))
        conn.close()


def _ekle(c, kod, psikolog, gun, durum, gorusme="YUZ_YUZE", terapi=None, neden=None):
    kullanici, pid, oda = psikolog
    bas = datetime(2031, 3, 3, 10, 0) + timedelta(days=gun)
    c.execute("INSERT INTO randevular (danisan_kod_id, psikolog_id, oda_id, baslangic_zamani, bitis_zamani, durum, gorusme_tipi, terapi_turu, iptal_nedeni) "
              "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)", (kod, pid, oda, bas, bas + timedelta(hours=1), durum, gorusme, terapi, neden))


def test_rapor_gercek_veritabaninda(kayitlar):
    c, admin, (psi_a, psi_b), (cocuk, yetiskin, eski) = kayitlar
    _ekle(c, cocuk, psi_a, 0, "TAMAMLANDI", terapi="OYUN_TERAPISI")
    _ekle(c, yetiskin, psi_a, 1, "TAMAMLANDI", gorusme="ONLINE", terapi="BIREYSEL_TERAPI")
    _ekle(c, yetiskin, psi_a, 2, "GELMEDI", terapi="BIREYSEL_TERAPI")
    _ekle(c, eski, psi_a, 3, "PLANLANDI")
    _ekle(c, cocuk, psi_a, 4, "IPTAL_EDILDI", neden="DANISAN_TALEBI")
    _ekle(c, cocuk, psi_b, 5, "TAMAMLANDI", terapi="BIREYSEL_TERAPI")
    istemci = TestClient(app)
    app.dependency_overrides[mevcut_kullanici_id] = lambda: admin
    dar = f"baslangic=2031-03-01&bitis=2031-03-31"

    yanit = istemci.get(f"/api/randevu-raporu?{dar}&psikolog_id={psi_a[1]}&detay=true")
    assert yanit.status_code == 200, yanit.text
    veri = yanit.json()
    assert (veri["ozet"]["toplam"], veri["ozet"]["tamamlandi"], veri["ozet"]["gelmedi"], veri["ozet"]["iptal_edildi"], veri["ozet"]["planlandi"]) == (5, 2, 1, 1, 1)
    assert veri["ozet"]["tamamlanma_orani"] == round(2 / 3, 4) and veri["ozet"]["danisan_sayisi"] == 3
    assert [p["psikolog_id"] for p in veri["psikologlar"]] == [psi_a[1]]
    assert veri["iptal_nedenleri"][0]["kod"] == "DANISAN_TALEBI" and veri["iptal_nedenleri"][0]["etiket"] == "Danışan talebi"
    gorusme = {o["kod"]: o["sayi"] for o in veri["dagilimlar"]["gorusme_tipi"]}
    assert gorusme == {"YUZ_YUZE": 3, "ONLINE": 1}                                         # iptal hariç
    assert {o["kod"] for o in veri["dagilimlar"]["yas_grubu"]} == {"COCUK", "YETISKIN", "BELIRTILMEDI"}
    assert len(veri["randevular"]) == 5 and all(r["psikolog"].startswith("rpa_") for r in veri["randevular"])

    tum = istemci.get(f"/api/randevu-raporu?{dar}").json()                                  # süzgeçsiz: iki psikolog
    assert tum["ozet"]["toplam"] == 6 and len(tum["psikologlar"]) == 2
    oda = istemci.get(f"/api/randevu-raporu?{dar}&oda_id={psi_b[2]}").json()
    assert oda["ozet"]["toplam"] == 1
    bos = istemci.get("/api/randevu-raporu?baslangic=2040-01-01&bitis=2040-01-31").json()   # randevu olmayan dönem
    assert bos["ozet"]["toplam"] == 0 and bos["ozet"]["tamamlanma_orani"] is None
    ilk_gun = istemci.get("/api/randevu-raporu?baslangic=2031-03-03&bitis=2031-03-03").json()  # bitiş günü dahil
    assert ilk_gun["ozet"]["toplam"] == 1


def test_psikolog_yalnizca_kendi_randevularini_gorur(kayitlar):
    c, admin, (psi_a, psi_b), (cocuk, yetiskin, eski) = kayitlar
    _ekle(c, cocuk, psi_a, 0, "TAMAMLANDI", terapi="OYUN_TERAPISI")
    _ekle(c, cocuk, psi_b, 1, "TAMAMLANDI", terapi="BIREYSEL_TERAPI")
    _ekle(c, cocuk, psi_b, 2, "GELMEDI", terapi="BIREYSEL_TERAPI")
    istemci = TestClient(app)
    app.dependency_overrides[mevcut_kullanici_id] = lambda: psi_b[0]
    veri = istemci.get(f"/api/randevu-raporu?baslangic=2031-03-01&bitis=2031-03-31&psikolog_id={psi_a[1]}").json()   # başkasını istese de
    assert veri["ozet"]["toplam"] == 2 and [p["psikolog_id"] for p in veri["psikologlar"]] == [psi_b[1]]
