"""Klinik operasyon paketi 3: rol karşılaştırması, iptal notu görünürlüğü, durum değişikliği denetimi, sonucsuz geçmiş randevu, kod önizlemesi.

Veritabanı sahte imleçle taklit edilir; PostgreSQL gerekmez (gerçek veritabanı karşılıkları test_psikolog_pasif_oda_pg_quality.py'de).
"""
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from server.denetim import durum_degisikligi_yaz
from server.randevu_rapor_hesapla import randevu_raporu_hesapla
from server.sunucu import psikolog_rolu_mu, randevulari_listele, siradaki_danisan_kodunu_ver


# ------------------------------------------------------------------ rol karşılaştırması (madde 13)
@pytest.mark.parametrize("rol, beklenen", [("PSIKOLOG", True), ("psikolog", True), (" Psikolog ", True), ("PSIKOLOG_YARDIMCISI", False),
                                           ("BAS PSIKOLOG", False), ("ADMIN", False), (None, False), ("", False)])
def test_psikolog_rolu_tek_yerde_karsilastirilir(rol, beklenen):
    assert psikolog_rolu_mu(rol) is beklenen


# ------------------------------------------------------------------ iptal notu görünürlüğü (madde 15)
def _liste(rol, izin):
    conn = MagicMock()
    c = conn.cursor.return_value
    c.fetchone.side_effect = [(rol,), izin, (1,)]                               # rol, RANDEVU_DUZENLE izin satırı, toplam sayı (süzgeçsiz liste sınırlı sorgudur)
    simdi = datetime.now()
    c.fetchall.return_value = [(1, "DAN-1", 3, 2, simdi, simdi, "IPTAL_EDILDI", simdi, "DIGER", "özel not", "YUZ_YUZE", None)]
    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        return randevulari_listele(kullanici_id=1)[0]


def test_randevu_duzenleme_izni_olan_iptal_notunu_gorur():
    satir = _liste("MUDUR", (1,))
    assert satir["iptal_notu"] == "özel not" and satir["iptal_nedeni"] == "DIGER"


@pytest.mark.parametrize("izin", [(0,), None])
def test_izni_olmayan_iptal_notunu_gormez_nedeni_gorur(izin):
    satir = _liste("MEMUR", izin)
    assert satir["iptal_notu"] is None and satir["iptal_nedeni"] == "DIGER"


# ------------------------------------------------------------------ durum değişikliği denetimi (madde 14)
def test_durum_degisikligi_onceki_ve_yeni_degerle_yazilir():
    c = MagicMock()
    durum_degisikligi_yaz(c, 5, "UPDATE", "randevular", 12, onceki="PLANLANDI", yeni="GELMEDI")
    sql, parametreler = c.execute.call_args.args
    assert "INSERT INTO denetim_kayitlari" in sql and "ayrinti" in sql
    assert parametreler[:4] == (5, "UPDATE", "randevular", 12)
    assert parametreler[4].adapted == {"onceki": "PLANLANDI", "yeni": "GELMEDI"}


# ------------------------------------------------------------------ sonucu girilmemiş geçmiş randevu (madde 7)
ETIKETLER = {"iptal": {}, "gorusme": {}, "terapi": {}, "yas": {}}


def _satir(i, durum, gun):
    z = datetime(2026, 11, 19, 10, 0) + timedelta(days=gun)
    return {"randevu_id": i, "baslangic_zamani": z, "bitis_zamani": z + timedelta(hours=1), "danisan_kod_id": f"D{i}", "psikolog_id": 1,
            "oda_id": 1, "durum": durum, "gorusme_tipi": None, "terapi_turu": None, "yas_grubu": None, "iptal_nedeni": None}


def test_gunu_gecmis_ama_planlandi_kalan_randevular_ayri_sayilir_oranlara_girmez():
    satirlar = [_satir(1, "TAMAMLANDI", -5), _satir(2, "GELMEDI", -4), _satir(3, "PLANLANDI", -3), _satir(4, "PLANLANDI", -1),
                _satir(5, "PLANLANDI", 0), _satir(6, "PLANLANDI", 2), _satir(7, "IPTAL_EDILDI", -2)]
    ozet = randevu_raporu_hesapla(satirlar, ETIKETLER, bugun=datetime(2026, 11, 19).date())["ozet"]
    assert ozet["sonucsuz_gecmis"] == 2                                                         # dün ve 3 gün önceki; bugünküler ve gelecek sayılmaz
    assert ozet["planlandi"] == 4 and ozet["tamamlanma_orani"] == 0.5                           # oranlar yalnızca Tamamlandı/Gelmedi üzerinden


def test_sonucsuz_gecmis_yoksa_sifir():
    assert randevu_raporu_hesapla([_satir(1, "TAMAMLANDI", -5)], ETIKETLER, bugun=datetime(2026, 11, 19).date())["ozet"]["sonucsuz_gecmis"] == 0


# ------------------------------------------------------------------ danışan kodu önizlemesi (madde 10)
def test_siradaki_kod_onizlemesi_kod_uretemezse_uydurma_kod_dondurmez():
    with patch("server.sunucu.psycopg2.connect", side_effect=RuntimeError("baglanti yok")):
        with pytest.raises(HTTPException) as hata:
            siradaki_danisan_kodunu_ver(kullanici_id=1)
    assert hata.value.status_code == 503 and "0001" not in hata.value.detail


def test_siradaki_kod_onizlemesi_kilit_almaz():
    conn = MagicMock()
    c = conn.cursor.return_value
    c.fetchone.return_value = (43,)
    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        sonuc = siradaki_danisan_kodunu_ver(kullanici_id=1)
    assert sonuc["siradaki_kod"].endswith("-0043")
    assert not any("pg_advisory" in x.args[0] for x in c.execute.call_args_list)
    conn.commit.assert_not_called()
