"""
PR2 (gerçek PostgreSQL): randevu iptal nedeni/notu kısıtları ve iptal / Tamamlandı-Gelmedi uçları.

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


def _temel_kayitlar(cursor, etiket):
    """Geçici rol/kullanıcı/personel/oda/danışan kodu oluşturur; (kullanici_id, personel_id, oda_id, danisan_kodu)."""
    cursor.execute("SELECT rol_id FROM roller WHERE rol_adi = 'PSIKOLOG'")
    rol_id = cursor.fetchone()[0]
    cursor.execute("INSERT INTO kullanicilar (kullanici_adi, parola_hash, rol_id) VALUES (%s, 'x', %s) RETURNING kullanici_id",
                   (f"t_{etiket}", rol_id))
    kullanici_id = cursor.fetchone()[0]
    cursor.execute("INSERT INTO personel (kullanici_id, personel_kodu) VALUES (%s, %s) RETURNING personel_id",
                   (kullanici_id, f"T-{etiket}"))
    personel_id = cursor.fetchone()[0]
    cursor.execute("INSERT INTO odalar (oda_adi, kapasite) VALUES (%s, 1) RETURNING oda_id", (f"t_oda_{etiket}",))
    oda_id = cursor.fetchone()[0]
    kod = f"T-{etiket}"
    cursor.execute("INSERT INTO danisan_kodlari (danisan_kod_id, olusturan_psikolog_id) VALUES (%s, %s)", (kod, personel_id))
    return kullanici_id, personel_id, oda_id, kod


def _randevu_ekle(cursor, kod, personel_id, oda_id, bas, durum="PLANLANDI", neden=None, notu=None):
    cursor.execute(
        "INSERT INTO randevular (danisan_kod_id, psikolog_id, oda_id, baslangic_zamani, bitis_zamani, durum, iptal_nedeni, iptal_notu) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING randevu_id",
        (kod, personel_id, oda_id, bas, bas + timedelta(hours=1), durum, neden, notu))
    return cursor.fetchone()[0]


def test_iptal_nedeni_kisitlari():
    etiket = uuid4().hex[:10]
    with closing(psycopg2.connect(**VT_AYARLARI)) as conn:
        try:
            with conn.cursor() as c:
                _dogru_veritabani(c)
                _, pid, oda, kod = _temel_kayitlar(c, etiket)
                bas = datetime(2031, 3, 4, 10, 0)                          # salı; diğer testlerle çakışmaz

                def reddedilir(hata, **kw):
                    c.execute("SAVEPOINT sp")
                    with pytest.raises(hata):
                        _randevu_ekle(c, kod, pid, oda, bas, **kw)
                    c.execute("ROLLBACK TO SAVEPOINT sp")

                reddedilir(errors.CheckViolation, durum="IPTAL_EDILDI", neden="KURUM_KAPALI")       # listede yok
                reddedilir(errors.CheckViolation, durum="PLANLANDI", neden="DANISAN_TALEBI")        # iptal değilken neden
                reddedilir(errors.CheckViolation, durum="IPTAL_EDILDI", neden="DIGER")              # Diğer notsuz
                reddedilir(errors.CheckViolation, durum="IPTAL_EDILDI", neden="DIGER", notu="   ")  # Diğer boş not
                reddedilir(errors.CheckViolation, durum="IPTAL_EDILDI", neden=None, notu="nedensiz not")
                reddedilir(errors.StringDataRightTruncation, durum="IPTAL_EDILDI", neden="HATALI_KAYIT", notu="x" * 101)

                rid = _randevu_ekle(c, kod, pid, oda, bas, durum="IPTAL_EDILDI", neden="HATALI_KAYIT")
                rid2 = _randevu_ekle(c, kod, pid, oda, bas + timedelta(days=1), durum="IPTAL_EDILDI", neden="DIGER", notu="kurum içi görev")
                assert rid and rid2
                # eski kayıt biçimi (neden yok) hâlâ geçerli
                assert _randevu_ekle(c, kod, pid, oda, bas + timedelta(days=2), durum="IPTAL_EDILDI")
        finally:
            conn.rollback()


@pytest.fixture
def gercek_kayitlar():
    """Gerçek (commit edilen) geçici kayıtlar; testten sonra temizlenir."""
    etiket = uuid4().hex[:10]
    conn = psycopg2.connect(**VT_AYARLARI)
    conn.autocommit = True
    c = conn.cursor()
    _dogru_veritabani(c)
    c.execute("SELECT rol_id FROM roller WHERE rol_adi = 'ADMIN'")
    admin_rol = c.fetchone()[0]
    c.execute("INSERT INTO kullanicilar (kullanici_adi, parola_hash, rol_id) VALUES (%s, 'x', %s) RETURNING kullanici_id",
              (f"ta_{etiket}", admin_rol))
    admin_id = c.fetchone()[0]
    kullanici_id, pid, oda, kod = _temel_kayitlar(c, etiket)
    app.dependency_overrides[mevcut_kullanici_id] = lambda: admin_id
    try:
        yield c, admin_id, pid, oda, kod
    finally:
        app.dependency_overrides.pop(mevcut_kullanici_id, None)
        c.execute("DELETE FROM randevular WHERE danisan_kod_id = %s", (kod,))
        c.execute("DELETE FROM denetim_kayitlari WHERE kullanici_id = ANY(%s)", ([admin_id, kullanici_id],))
        c.execute("DELETE FROM danisan_kodlari WHERE danisan_kod_id = %s", (kod,))
        c.execute("DELETE FROM odalar WHERE oda_id = %s", (oda,))
        c.execute("DELETE FROM personel WHERE kullanici_id = %s", (kullanici_id,))
        c.execute("DELETE FROM kullanicilar WHERE kullanici_id = ANY(%s)", ([admin_id, kullanici_id],))
        conn.close()


def test_iptal_ve_isaretleme_uclari_gercek_veritabaninda(gercek_kayitlar):
    c, admin_id, pid, oda, kod = gercek_kayitlar
    istemci = TestClient(app)
    gecmis = datetime.now().replace(microsecond=0) - timedelta(days=3)
    gelecek = datetime.now().replace(microsecond=0) + timedelta(days=3)
    r_gecmis = _randevu_ekle(c, kod, pid, oda, gecmis)
    r_gelecek = _randevu_ekle(c, kod, pid, oda, gelecek)

    def durum(rid):
        c.execute("SELECT durum, iptal_nedeni, iptal_notu FROM randevular WHERE randevu_id = %s", (rid,))
        return c.fetchone()

    # iptal: nedensiz reddedilir, nedenle yapılır
    assert istemci.patch(f"/api/randevular/{r_gelecek}/iptal").status_code == 422
    assert istemci.patch(f"/api/randevular/{r_gelecek}/iptal", json={"iptal_nedeni": "DIGER"}).status_code == 422
    yanit = istemci.patch(f"/api/randevular/{r_gelecek}/iptal", json={"iptal_nedeni": "DIGER", "iptal_notu": " kurum içi görev "})
    assert yanit.status_code == 200
    assert durum(r_gelecek) == ("IPTAL_EDILDI", "DIGER", "kurum içi görev")
    assert istemci.patch(f"/api/randevular/{r_gelecek}/iptal", json={"iptal_nedeni": "HATALI_KAYIT"}).status_code == 409

    # Tamamlandı / Gelmedi: geçmiş randevu işaretlenir ve düzeltilir, iptal edilmiş işaretlenemez
    assert istemci.patch(f"/api/randevular/{r_gecmis}/durum", json={"durum": "TAMAMLANDI"}).status_code == 200
    assert durum(r_gecmis)[0] == "TAMAMLANDI"
    assert istemci.patch(f"/api/randevular/{r_gecmis}/durum", json={"durum": "GELMEDI"}).status_code == 200
    assert durum(r_gecmis)[0] == "GELMEDI"
    assert istemci.patch(f"/api/randevular/{r_gelecek}/durum", json={"durum": "GELMEDI"}).status_code == 409   # iptal edilmiş
    r_ileri = _randevu_ekle(c, kod, pid, oda, gelecek + timedelta(days=1))
    assert istemci.patch(f"/api/randevular/{r_ileri}/durum", json={"durum": "TAMAMLANDI"}).status_code == 409   # henüz başlamadı

    # liste iptal alanlarını döndürür
    kayitlar = {k["randevu_id"]: k for k in istemci.get("/api/randevular").json()}
    assert kayitlar[r_gelecek]["iptal_nedeni"] == "DIGER" and kayitlar[r_gelecek]["iptal_notu"] == "kurum içi görev"
    assert kayitlar[r_gecmis]["iptal_nedeni"] is None
