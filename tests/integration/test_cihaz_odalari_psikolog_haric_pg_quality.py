"""Gerçek PostgreSQL: aktif psikologa atanan oda cihaz rezervasyonuna kapalıdır; pasif psikologun odası açıktır.

- GET /api/cihaz-odalari: aktif psikologa atanmış oda listede yok, atanmamış oda var
- POST /api/rezervasyonlar: aktif psikologa atanmış odayla rezervasyon 422
- Psikolog pasife alınınca (atama kaydı kalsa bile) oda açılır; yeniden aktifleşince yine kapanır

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
    admin = _kullanici(c, f"ch_{etiket}", "ADMIN")
    psikolog = _kullanici(c, f"cp_{etiket}", "PSIKOLOG")
    odalar = {}
    for ad in ("psikolog", "bos"):
        c.execute("INSERT INTO odalar (oda_adi, kapasite) VALUES (%s, 1) RETURNING oda_id", (f"ch_oda_{ad}_{etiket}",))
        odalar[ad] = c.fetchone()[0]
    c.execute("INSERT INTO psikolog_odalar (kullanici_id, oda_id) VALUES (%s, %s)", (psikolog, odalar["psikolog"]))
    c.execute("INSERT INTO cihazlar (envanter_kodu, cihaz_adi, durum) VALUES (%s, %s, 'Kullanima_Hazir') RETURNING cihaz_id", (f"CH-{etiket}", f"ch_cihaz_{etiket}"))
    cihaz = c.fetchone()[0]
    try:
        yield c, admin, psikolog, odalar, cihaz
    finally:
        app.dependency_overrides.pop(mevcut_kullanici_id, None)
        c.execute("DELETE FROM cihaz_rezervasyonlari WHERE cihaz_id = %s", (cihaz,))
        c.execute("DELETE FROM cihazlar WHERE cihaz_id = %s", (cihaz,))
        c.execute("DELETE FROM psikolog_odalar WHERE kullanici_id = %s", (psikolog,))
        c.execute("DELETE FROM denetim_kayitlari WHERE kullanici_id = ANY(%s)", ([admin, psikolog],))
        c.execute("DELETE FROM odalar WHERE oda_id = ANY(%s)", (list(odalar.values()),))
        c.execute("DELETE FROM kullanicilar WHERE kullanici_id = ANY(%s)", ([admin, psikolog],))
        conn.close()


def test_psikolog_odasi_rezervasyona_kapali_pasif_psikologun_odasi_acik_gercek_veritabaninda(ortam):
    c, admin, psikolog, odalar, cihaz = ortam
    istemci = TestClient(app)
    app.dependency_overrides[mevcut_kullanici_id] = lambda: admin
    liste = lambda: {o["oda_id"] for o in istemci.get("/api/cihaz-odalari").json()}
    # Rezervasyon saatleri mesai içinde sabit (10:00): testin günün hangi saatinde çalıştığına bağlı olmasın (08:00-18:00 kuralı).
    saat = [(datetime.now() + timedelta(days=2 + n)).replace(hour=10, minute=0, second=0, microsecond=0) for n in range(3)]
    rezerve = lambda oda, n: istemci.post("/api/rezervasyonlar", json={
        "cihaz_id": cihaz, "kullanilacak_oda_id": oda, "baslangic_zamani": saat[n].isoformat(), "bitis_zamani": (saat[n] + timedelta(hours=1)).isoformat()})

    assert odalar["bos"] in liste() and odalar["psikolog"] not in liste()                  # aktif psikologun odası listede yok
    yanit = rezerve(odalar["psikolog"], 0)
    assert yanit.status_code == 422 and "cihaz rezervasyonu için uygun değil" in yanit.json()["detail"]
    assert rezerve(odalar["bos"], 0).status_code == 201                                     # atanmamış oda rezerve edilir

    c.execute("UPDATE kullanicilar SET aktif_mi = FALSE WHERE kullanici_id = %s", (psikolog,))
    assert odalar["psikolog"] in liste()                                                    # pasif psikolog: atama kaydı durur ama oda açılır
    assert rezerve(odalar["psikolog"], 1).status_code == 201

    c.execute("UPDATE kullanicilar SET aktif_mi = TRUE WHERE kullanici_id = %s", (psikolog,))
    assert odalar["psikolog"] not in liste()                                                # yeniden aktif: yine psikolog odası
    assert rezerve(odalar["psikolog"], 2).status_code == 422
