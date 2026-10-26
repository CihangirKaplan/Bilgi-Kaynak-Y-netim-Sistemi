"""Cihaz raporları testleri (Öğrenci B - DASH-003).

Testler gerçek veritabanına bağlanmaz; psycopg2 bağlantısı sahte (mock) nesne
ile değiştirilir.
"""
from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from sunucu import app, cihaz_raporlari


def sahte_baglanti():
    conn = MagicMock()
    return conn, conn.cursor.return_value


def test_rapor_ozeti_ve_listeleri_dogru_doner():
    conn, cursor = sahte_baglanti()
    cursor.fetchall.side_effect = [
        # bakımlar
        [(1, "CHZ-1", "EEG", "Ali", "Filtre değişimi", 150.5,
          datetime(2026, 10, 1, 9, 0), date(2027, 4, 1)),
         (2, "CHZ-2", "EKG", "Veli", "Genel bakım", 49.5,
          datetime(2026, 10, 5, 9, 0), None)],
        # kalibrasyonlar
        [(1, "CHZ-1", "EEG", "Kurum A", "SRT-1",
          datetime(2026, 10, 2, 9, 0), date(2027, 10, 2))],
        # arızalar
        [(1, "CHZ-1", "EEG", "Ayşe", "Ekran gitti",
          datetime(2026, 10, 3, 9, 0), None, False),
         (2, "CHZ-2", "EKG", "Fatma", "Kablo kopuk",
          datetime(2026, 10, 4, 9, 0), datetime(2026, 10, 6, 9, 0), True)],
    ]

    with patch("sunucu.psycopg2.connect", return_value=conn):
        sonuc = cihaz_raporlari(kullanici_id=3)

    assert sonuc["ozet"] == {
        "bakim_sayisi": 2,
        "toplam_bakim_maliyeti": 200.0,
        "kalibrasyon_sayisi": 1,
        "ariza_sayisi": 2,
        "acik_ariza_sayisi": 1,
    }
    assert sonuc["bakimlar"][0]["cihaz"] == "CHZ-1 - EEG"
    assert sonuc["bakimlar"][1]["sonraki_bakim_tarihi"] is None
    assert [a["durum"] for a in sonuc["arizalar"]] == ["Açık", "Çözüldü"]
    conn.close.assert_called_once()


def test_filtreler_sql_parametresi_olarak_gonderilir():
    conn, cursor = sahte_baglanti()
    cursor.fetchall.side_effect = [[], [], []]

    with patch("sunucu.psycopg2.connect", return_value=conn):
        cihaz_raporlari(
            baslangic_tarihi=date(2026, 10, 1),
            bitis_tarihi=date(2026, 10, 31),
            cihaz_id=7,
            kullanici_id=3,
        )

    for cagri in cursor.execute.call_args_list:
        sql, parametreler = cagri.args
        assert "%s" in sql
        assert parametreler == [date(2026, 10, 1), date(2026, 10, 31), 7]


def test_rapor_sadece_okuma_yapar():
    conn, cursor = sahte_baglanti()
    cursor.fetchall.side_effect = [[], [], []]

    with patch("sunucu.psycopg2.connect", return_value=conn):
        cihaz_raporlari(kullanici_id=3)

    for cagri in cursor.execute.call_args_list:
        assert cagri.args[0].strip().upper().startswith("SELECT")
    conn.commit.assert_not_called()


def test_bitis_baslangictan_once_422():
    with pytest.raises(HTTPException) as hata:
        cihaz_raporlari(
            baslangic_tarihi=date(2026, 10, 10),
            bitis_tarihi=date(2026, 10, 1),
            kullanici_id=3,
        )

    assert hata.value.status_code == 422


@pytest.mark.parametrize("cihaz_id", [0, -5])
def test_gecersiz_cihaz_id_422(cihaz_id):
    with pytest.raises(HTTPException) as hata:
        cihaz_raporlari(cihaz_id=cihaz_id, kullanici_id=3)

    assert hata.value.status_code == 422


def test_tokensiz_rapor_istegi_reddedilir():
    """SEC-T01: Token olmadan rapora erişilemez."""
    yanit = TestClient(app).get("/api/cihaz-raporlari")
    assert yanit.status_code in (401, 403)