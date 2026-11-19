"""Deadlock önleme: oda kilidi HER ZAMAN kullanıcı satırı kilidinden (FOR UPDATE OF k) önce alınır.

Rezervasyon/randevu yolları oda kilidini alıp sonra denetim kaydıyla (FK) kullanıcı satırını okur. Oda ataması, rol ve durum değiştirme
yolları satırı önce kilitleyip sonra oda kilidini bekleyince iki işlem birbirini bekliyordu (DeadlockDetected → 500; CI'daki
test_rezervasyon_psikolog_yaris_pg.py rastgele kırmızı oluyordu). Veritabanı sahte imleçle taklit edilir.
"""
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from psycopg2.errors import DeadlockDetected

from server.modeller import RolDegistirModeli
from server.sunucu import (
    DurumDegistirModeli,
    OdaYetkileriModeli,
    kullanici_durum_degistir,
    kullanici_rol_degistir,
    psikolog_oda_yetkilerini_guncelle,
)


def _sira(cursor):
    """Çalışan SQL'lerin sırası: ('kilit' | 'satir_kilidi')."""
    sonuc = []
    for cagri in cursor.execute.call_args_list:
        sql = " ".join(cagri.args[0].split())
        if "pg_advisory_xact_lock" in sql:
            sonuc.append("kilit")
        elif "FOR UPDATE OF k" in sql:
            sonuc.append("satir_kilidi")
    return sonuc


def _kilitler_satirdan_once(sira, adet):
    """Tüm oda kilitleri (adet tane), ilk kullanıcı satırı kilidinden önce alınmış mı?"""
    return sira.count("kilit") >= adet and "satir_kilidi" in sira and sira.index("satir_kilidi") == sira.count("kilit") and sira[:adet] == ["kilit"] * adet


def _calistir(islev, fetchone, **kwargs):
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchone.side_effect = list(fetchone)
    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        try:
            islev(**kwargs)
        except HTTPException:
            pass                                                         # kilit sırası, erken hata alınsa da (404 vb.) ilk iki adımda belli olur
    return cursor


def test_oda_atamasi_once_oda_kilidini_sonra_kullanici_satirini_kilitler():
    imlec = _calistir(psikolog_oda_yetkilerini_guncelle, [None], hedef_kullanici_id=7, yetki=OdaYetkileriModeli(oda_idleri=[3, 2]), kullanici_id=1)
    assert _kilitler_satirdan_once(_sira(imlec), 2)
    kilitler = [c.args[1] for c in imlec.execute.call_args_list if "pg_advisory_xact_lock" in c.args[0]]
    assert kilitler == [(391284, 2), (391284, 3)]                        # kilitler her zaman artan oda sırasıyla alınır


def test_rol_degistirme_once_oda_kilidini_sonra_kullanici_satirini_kilitler():
    imlec = _calistir(kullanici_rol_degistir, [("ADMIN",), None], kullanici_id=7, veri=RolDegistirModeli(rol_id=2, oda_idleri=[5, 4]), islem_yapan_id=1)
    assert _kilitler_satirdan_once(_sira(imlec), 2)


def test_durum_degistirme_once_oda_kilidini_sonra_kullanici_satirini_kilitler():
    imlec = _calistir(kullanici_durum_degistir, [("ADMIN",), None], kullanici_id=7, veri=DurumDegistirModeli(oda_idleri=[5]), islem_yapan_id=1)
    assert _kilitler_satirdan_once(_sira(imlec), 1)


def test_oda_secilmeyen_durum_degistirmede_gereksiz_kilit_alinmaz():
    imlec = _calistir(kullanici_durum_degistir, [("ADMIN",), None], kullanici_id=7, veri=None, islem_yapan_id=1)
    assert _sira(imlec) == ["satir_kilidi"]


# ------------------------------------------------------------------ yine de deadlock olursa 500 değil 503
def test_oda_atamasinda_deadlock_503_verir_ve_geri_alir():
    conn = MagicMock()
    conn.cursor.return_value.execute.side_effect = DeadlockDetected()
    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            psikolog_oda_yetkilerini_guncelle(hedef_kullanici_id=7, yetki=OdaYetkileriModeli(oda_idleri=[2]), kullanici_id=1)
    assert hata.value.status_code == 503 and "tekrar deneyin" in hata.value.detail
    conn.rollback.assert_called()
