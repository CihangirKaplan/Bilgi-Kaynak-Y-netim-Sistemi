"""
Gerçek PostgreSQL: danışan yaş grubu / terapi türü ve randevu görüşme tipi / terapi türü (kapalı listeler).

CI'daki "PostgreSQL Entegrasyon Testleri" işinde (alembic upgrade head sonrası) çalışır. Kısıt testleri işlemi geri alır;
uç testleri gerçek kayıt oluşturur ve sonunda temizler.
"""

import os
from contextlib import closing
from datetime import datetime, timedelta
from uuid import uuid4

import psycopg2
import pytest
from fastapi.testclient import TestClient
from psycopg2 import errors

from sunucu import VT_AYARLARI, app, mevcut_kullanici_id


def _dogru_veritabani(cursor):
    assert os.getenv("TKYS_PG_TEST_ONAY") == "EVET"
    assert VT_AYARLARI["dbname"] == "crkys_alembic_test"
    cursor.execute("SELECT current_database()")
    assert cursor.fetchone()[0] == "crkys_alembic_test"


def _kullanici(cursor, ad, rol):
    cursor.execute("INSERT INTO kullanicilar (kullanici_adi, parola_hash, rol_id) VALUES (%s, 'x', (SELECT rol_id FROM roller WHERE rol_adi = %s)) RETURNING kullanici_id", (ad, rol))
    return cursor.fetchone()[0]


def _psikolog_ve_oda(cursor, etiket):
    kullanici_id = _kullanici(cursor, f"t_{etiket}", "PSIKOLOG")
    cursor.execute("INSERT INTO personel (kullanici_id, personel_kodu) VALUES (%s, %s) RETURNING personel_id", (kullanici_id, f"T-{etiket}"))
    personel_id = cursor.fetchone()[0]
    cursor.execute("INSERT INTO odalar (oda_adi, kapasite) VALUES (%s, 1) RETURNING oda_id", (f"t_oda_{etiket}",))
    oda_id = cursor.fetchone()[0]
    cursor.execute("INSERT INTO psikolog_odalar (kullanici_id, oda_id) VALUES (%s, %s)", (kullanici_id, oda_id))
    return kullanici_id, personel_id, oda_id


def _danisan(cursor, kod, personel_id, yas=None, terapi=None):
    cursor.execute("INSERT INTO danisan_kodlari (danisan_kod_id, olusturan_psikolog_id, yas_grubu, terapi_turu) VALUES (%s, %s, %s, %s)",
                   (kod, personel_id, yas, terapi))


def test_danisan_yas_terapi_kisitlari():
    etiket = uuid4().hex[:10]
    with closing(psycopg2.connect(**VT_AYARLARI)) as conn:
        try:
            with conn.cursor() as c:
                _dogru_veritabani(c)
                _, pid, _ = _psikolog_ve_oda(c, etiket)

                def reddedilir(yas, terapi):
                    c.execute("SAVEPOINT sp")
                    with pytest.raises(errors.CheckViolation):
                        _danisan(c, f"T-{etiket}-X", pid, yas, terapi)
                    c.execute("ROLLBACK TO SAVEPOINT sp")

                reddedilir("YETISKIN", "OYUN_TERAPISI")          # yetişkinde oyun terapisi yok
                reddedilir("COCUK", None)                         # çocukta terapi zorunlu (yaş grubu varsa)
                reddedilir("YETISKIN", None)
                reddedilir(None, "BIREYSEL_TERAPI")               # yaş grubu olmadan terapi olmaz
                reddedilir("Ergen", "BIREYSEL_TERAPI")
                reddedilir("COCUK", "grup terapisi")
                _danisan(c, f"T-{etiket}-1", pid, "YETISKIN", "BIREYSEL_TERAPI")
                _danisan(c, f"T-{etiket}-2", pid, "COCUK", "OYUN_TERAPISI")
                _danisan(c, f"T-{etiket}-3", pid, "COCUK", "BIREYSEL_TERAPI")
                _danisan(c, f"T-{etiket}-4", pid, None, None)     # eski danışan: belirtilmedi
        finally:
            conn.rollback()


def test_randevu_gorusme_tipi_ve_terapi_kisitlari():
    etiket = uuid4().hex[:10]
    with closing(psycopg2.connect(**VT_AYARLARI)) as conn:
        try:
            with conn.cursor() as c:
                _dogru_veritabani(c)
                _, pid, oda = _psikolog_ve_oda(c, etiket)
                kod = f"T-{etiket}-1"
                _danisan(c, kod, pid, "COCUK", "OYUN_TERAPISI")
                bas = datetime(2031, 3, 4, 10, 0)

                def ekle(gun, **ek):
                    sutunlar = ["danisan_kod_id", "psikolog_id", "oda_id", "baslangic_zamani", "bitis_zamani"] + list(ek)
                    t = bas + timedelta(days=gun)
                    c.execute(f"INSERT INTO randevular ({', '.join(sutunlar)}) VALUES ({', '.join(['%s'] * len(sutunlar))}) RETURNING randevu_id",
                              [kod, pid, oda, t, t + timedelta(hours=1), *ek.values()])
                    return c.fetchone()[0]

                for gun, kotu in ((0, {"gorusme_tipi": "telefon"}), (1, {"terapi_turu": "grup terapisi"}), (2, {"gorusme_tipi": None})):
                    c.execute("SAVEPOINT sp")
                    with pytest.raises((errors.CheckViolation, errors.NotNullViolation)):
                        ekle(gun, **kotu)
                    c.execute("ROLLBACK TO SAVEPOINT sp")
                rid = ekle(3)                                                                     # varsayılan
                c.execute("SELECT gorusme_tipi, terapi_turu FROM randevular WHERE randevu_id = %s", (rid,))
                assert c.fetchone() == ("YUZ_YUZE", None)
                assert ekle(4, gorusme_tipi="ONLINE", terapi_turu="OYUN_TERAPISI")
        finally:
            conn.rollback()


@pytest.fixture
def gercek_kayitlar():
    etiket = uuid4().hex[:10]
    conn = psycopg2.connect(**VT_AYARLARI)
    conn.autocommit = True
    c = conn.cursor()
    _dogru_veritabani(c)
    admin_id = _kullanici(c, f"ta_{etiket}", "ADMIN")
    kullanici_id, pid, oda = _psikolog_ve_oda(c, etiket)
    app.dependency_overrides[mevcut_kullanici_id] = lambda: admin_id
    try:
        yield c, admin_id, pid, oda, etiket
    finally:
        app.dependency_overrides.pop(mevcut_kullanici_id, None)
        c.execute("DELETE FROM randevular WHERE danisan_kod_id IN (SELECT danisan_kod_id FROM danisan_kodlari WHERE olusturan_psikolog_id = %s)", (pid,))
        c.execute("DELETE FROM denetim_kayitlari WHERE kullanici_id = ANY(%s)", ([admin_id, kullanici_id],))
        c.execute("DELETE FROM danisan_kodlari WHERE olusturan_psikolog_id = %s", (pid,))
        c.execute("DELETE FROM psikolog_odalar WHERE kullanici_id = %s", (kullanici_id,))
        c.execute("DELETE FROM odalar WHERE oda_id = %s", (oda,))
        c.execute("DELETE FROM personel WHERE kullanici_id = %s", (kullanici_id,))
        c.execute("DELETE FROM kullanicilar WHERE kullanici_id = ANY(%s)", ([admin_id, kullanici_id],))
        conn.close()


def test_uclar_gercek_veritabaninda(gercek_kayitlar):
    c, admin_id, pid, oda, etiket = gercek_kayitlar
    istemci = TestClient(app)

    def olustur(sorgu):
        r = istemci.post(f"/api/danisan-kodlari?psikolog_id={pid}&{sorgu}")
        return r.status_code, (r.json().get("veri") or r.json())

    # danışan oluşturma: yaş grubu zorunlu; yetişkinde otomatik bireysel terapi; çocukta seçilmeli
    assert istemci.post(f"/api/danisan-kodlari?psikolog_id={pid}").status_code == 422
    assert olustur("yas_grubu=COCUK")[0] == 422
    assert olustur("yas_grubu=YETISKIN&terapi_turu=OYUN_TERAPISI")[0] == 422
    durum, veri = olustur("yas_grubu=YETISKIN")
    assert durum == 201 and (veri["yas_grubu"], veri["terapi_turu"]) == ("YETISKIN", "BIREYSEL_TERAPI")
    yetiskin = veri["danisan_kod_id"]
    durum, veri = olustur("yas_grubu=COCUK&terapi_turu=OYUN_TERAPISI")
    assert durum == 201 and (veri["yas_grubu"], veri["terapi_turu"]) == ("COCUK", "OYUN_TERAPISI")
    cocuk = veri["danisan_kod_id"]
    _danisan(c, f"T-{etiket}-ESKI", pid, None, None)                                          # eski danışan

    # liste yeni alanları döndürür
    liste = {d["danisan_kod_id"]: d for d in istemci.get(f"/api/danisan-kodlari?psikolog_id={pid}").json()}
    assert (liste[cocuk]["yas_grubu"], liste[cocuk]["terapi_turu"]) == ("COCUK", "OYUN_TERAPISI")
    assert (liste[f"T-{etiket}-ESKI"]["yas_grubu"], liste[f"T-{etiket}-ESKI"]["terapi_turu"]) == (None, None)

    # randevu: online da oda ister; terapi yaş grubuna uymalı
    ileri = datetime.now().replace(microsecond=0, minute=0, second=0, hour=10) + timedelta(days=40)
    while ileri.weekday() >= 5:
        ileri += timedelta(days=1)

    def randevu(kod, gun, **ek):
        t = ileri + timedelta(days=gun)
        while t.weekday() >= 5:
            t += timedelta(days=1)
        return istemci.post("/api/randevular", json={"danisan_kod_id": kod, "psikolog_id": pid, "oda_id": oda,
                                                      "baslangic_zamani": t.isoformat(), "bitis_zamani": (t + timedelta(hours=1)).isoformat(), **ek})

    r = randevu(cocuk, 0, gorusme_tipi="ONLINE", terapi_turu="BIREYSEL_TERAPI")
    assert r.status_code == 201, r.text
    rid = r.json()["randevu_id"]
    c.execute("SELECT gorusme_tipi, terapi_turu, oda_id FROM randevular WHERE randevu_id = %s", (rid,))
    assert c.fetchone() == ("ONLINE", "BIREYSEL_TERAPI", oda)
    assert randevu(yetiskin, 1, terapi_turu="OYUN_TERAPISI").status_code == 422               # yetişkinde oyun terapisi yok
    r = randevu(yetiskin, 1)                                                                    # terapi otomatik bireysel
    assert r.status_code == 201
    c.execute("SELECT gorusme_tipi, terapi_turu FROM randevular WHERE randevu_id = %s", (r.json()["randevu_id"],))
    assert c.fetchone() == ("YUZ_YUZE", "BIREYSEL_TERAPI")
    assert randevu(cocuk, 2).status_code == 422                                                 # çocukta terapi seçilmeli
    assert randevu(f"T-{etiket}-ESKI", 3).status_code == 201                                    # eski danışan: terapisiz olur

    # randevu güncelleme: görüşme tipi / terapi; yaş grubuna uygunluk
    assert istemci.patch(f"/api/randevular/{rid}", json={"gorusme_tipi": "YUZ_YUZE", "terapi_turu": "OYUN_TERAPISI"}).status_code == 200
    c.execute("SELECT gorusme_tipi, terapi_turu FROM randevular WHERE randevu_id = %s", (rid,))
    assert c.fetchone() == ("YUZ_YUZE", "OYUN_TERAPISI")
    assert istemci.patch(f"/api/randevular/{rid}", json={"gorusme_tipi": "telefon"}).status_code == 422

    # danışan bilgileri: eski danışan tamamlanır; yetişkin yapılınca terapi otomatik; geçmiş randevular değişmez
    assert istemci.patch(f"/api/danisan-kodlari/T-{etiket}-ESKI/bilgiler", json={"yas_grubu": "YETISKIN"}).status_code == 200
    c.execute("SELECT yas_grubu, terapi_turu FROM danisan_kodlari WHERE danisan_kod_id = %s", (f"T-{etiket}-ESKI",))
    assert c.fetchone() == ("YETISKIN", "BIREYSEL_TERAPI")
    assert istemci.patch(f"/api/danisan-kodlari/{cocuk}/bilgiler", json={"yas_grubu": "YETISKIN"}).status_code == 200
    c.execute("SELECT terapi_turu FROM randevular WHERE randevu_id = %s", (rid,))
    assert c.fetchone() == ("OYUN_TERAPISI",)                                                    # eski randevunun terapisi korunur
    assert istemci.patch(f"/api/danisan-kodlari/{cocuk}/bilgiler", json={"yas_grubu": "YETISKIN", "terapi_turu": "OYUN_TERAPISI"}).status_code == 422

    # randevu listesi yeni alanları döndürür
    kayit = {k["randevu_id"]: k for k in istemci.get("/api/randevular").json()}
    assert (kayit[rid]["gorusme_tipi"], kayit[rid]["terapi_turu"]) == ("YUZ_YUZE", "OYUN_TERAPISI")
