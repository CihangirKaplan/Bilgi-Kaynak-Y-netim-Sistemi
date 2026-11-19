"""Gerçek PostgreSQL: randevu ve faaliyet listelerinin pencereleme (tarih aralığı / limit) davranışı.

Liste uç noktaları süzgeç verilmezse eskisi gibi hepsini döndürür; süzgeç/limit verilince yalnızca isteneni döndürür ve
limit varsa toplam kayıt sayısını X-Toplam-Kayit başlığında bildirir (liste kesildiyse istemci kullanıcıya söyleyebilsin).
Test 2002 yılına ait özel kayıtlar kullanır ve işi bitince siler.
"""
import os
from datetime import date, datetime
from uuid import uuid4

import psycopg2
import pytest
from fastapi import HTTPException, Response

from server.sunucu import VT_AYARLARI, faaliyet_kayitlarini_getir, randevulari_listele


@pytest.fixture
def veri():
    assert os.getenv("TKYS_PG_TEST_ONAY") == "EVET"
    assert VT_AYARLARI["dbname"] == "crkys_alembic_test"
    conn = psycopg2.connect(**VT_AYARLARI)
    conn.autocommit = True
    c = conn.cursor()
    etiket = uuid4().hex[:8]
    k = {}
    c.execute("INSERT INTO kullanicilar (kullanici_adi, parola_hash, rol_id) VALUES (%s, 'x', "
              "(SELECT rol_id FROM roller WHERE rol_adi = 'PSIKOLOG')) RETURNING kullanici_id", (f"lp_{etiket}",))
    k["kullanici"] = c.fetchone()[0]
    c.execute("INSERT INTO personel (kullanici_id, personel_kodu) VALUES (%s, %s) RETURNING personel_id", (k["kullanici"], f"LP-{etiket}"))
    k["personel"] = c.fetchone()[0]
    for ad in ("oda1", "oda2"):
        c.execute("INSERT INTO odalar (oda_adi) VALUES (%s) RETURNING oda_id", (f"lp_{ad}_{etiket}",))
        k[ad] = c.fetchone()[0]
    c.execute("INSERT INTO danisan_kodlari (danisan_kod_id) VALUES (%s)", (f"LP-{etiket}",))
    k["kod"] = f"LP-{etiket}"
    # 2002-05-01 .. 2002-05-10 arası her gün bir randevu; çift günler oda1, tek günler oda2; 10'u iptal
    for gun in range(1, 11):
        oda = k["oda1"] if gun % 2 == 0 else k["oda2"]
        durum = "IPTAL_EDILDI" if gun == 10 else "TAMAMLANDI"
        neden = "DANISAN_TALEBI" if gun == 10 else None
        c.execute("INSERT INTO randevular (danisan_kod_id, psikolog_id, oda_id, baslangic_zamani, bitis_zamani, durum, iptal_nedeni) "
                  "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                  (k["kod"], k["personel"], oda, datetime(2002, 5, gun, 10), datetime(2002, 5, gun, 11), durum, neden))
    yield k
    c.execute("DELETE FROM randevular WHERE danisan_kod_id = %s", (k["kod"],))
    c.execute("DELETE FROM danisan_kodlari WHERE danisan_kod_id = %s", (k["kod"],))
    c.execute("DELETE FROM odalar WHERE oda_id IN (%s, %s)", (k["oda1"], k["oda2"]))
    c.execute("DELETE FROM personel WHERE personel_id = %s", (k["personel"],))
    c.execute("DELETE FROM kullanicilar WHERE kullanici_id = %s", (k["kullanici"],))
    conn.close()


def _liste(k, **parametreler):
    yanit = Response()
    taban = dict(baslangic=None, bitis=None, durum=None, danisan_kod_id=None, oda_id=None, limit=None, offset=0)
    taban.update(parametreler)
    sonuc = randevulari_listele(response=yanit, kullanici_id=k["kullanici"], **taban)
    return sonuc, yanit


def test_suzgec_yoksa_hepsi_eskisi_gibi_zaman_sirasiyla(veri):
    sonuc, yanit = _liste(veri)
    assert len(sonuc) == 10
    assert [r["baslangic_zamani"].day for r in sonuc] == list(range(1, 11))
    assert "X-Toplam-Kayit" not in yanit.headers


def test_tarih_araligi_iki_ucu_dahil(veri):
    sonuc, _ = _liste(veri, baslangic=date(2002, 5, 3), bitis=date(2002, 5, 5))
    assert [r["baslangic_zamani"].day for r in sonuc] == [3, 4, 5]   # bitiş günündeki 10:00 randevusu da dahil


def test_tek_gun_ve_bos_aralik(veri):
    assert len(_liste(veri, baslangic=date(2002, 5, 7), bitis=date(2002, 5, 7))[0]) == 1
    assert _liste(veri, baslangic=date(2003, 1, 1), bitis=date(2003, 1, 31))[0] == []


def test_durum_oda_ve_danisan_suzgecleri(veri):
    assert [r["durum"] for r in _liste(veri, durum="IPTAL_EDILDI")[0]] == ["IPTAL_EDILDI"]
    assert len(_liste(veri, oda_id=veri["oda1"])[0]) == 5
    assert len(_liste(veri, danisan_kod_id=veri["kod"])[0]) == 10
    assert _liste(veri, danisan_kod_id="YOK-000")[0] == []
    assert len(_liste(veri, oda_id=veri["oda2"], baslangic=date(2002, 5, 1), bitis=date(2002, 5, 4))[0]) == 2


def test_limit_en_yenileri_getirir_ve_toplami_bildirir(veri):
    sonuc, yanit = _liste(veri, limit=3)
    assert [r["baslangic_zamani"].day for r in sonuc] == [10, 9, 8]
    assert yanit.headers["X-Toplam-Kayit"] == "10"
    ikinci, _ = _liste(veri, limit=3, offset=3)
    assert [r["baslangic_zamani"].day for r in ikinci] == [7, 6, 5]


def test_gecersiz_parametreler_422(veri):
    for kotu in ({"limit": 0}, {"limit": 100000}, {"offset": -1}, {"durum": "YOK"},
                 {"baslangic": date(2002, 6, 1), "bitis": date(2002, 5, 1)}):
        with pytest.raises(HTTPException) as hata:
            _liste(veri, **kotu)
        assert hata.value.status_code == 422


def test_faaliyet_limit_ve_toplam_basligi():
    assert os.getenv("TKYS_PG_TEST_ONAY") == "EVET"
    yanit = Response()
    tum = faaliyet_kayitlarini_getir(limit=None, offset=0, response=yanit, kullanici_id=1)
    assert "X-Toplam-Kayit" not in yanit.headers
    yanit2 = Response()
    kesik = faaliyet_kayitlarini_getir(limit=1, offset=0, response=yanit2, kullanici_id=1)
    assert len(kesik) <= 1
    assert int(yanit2.headers["X-Toplam-Kayit"]) == len(tum)
    with pytest.raises(HTTPException):
        faaliyet_kayitlarini_getir(limit=0, offset=0, response=Response(), kullanici_id=1)
