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
