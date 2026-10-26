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
          datetime(2026, 10, 1, 9, 0), date(2027, 4, 1), 1,
          date(2026, 10, 1), date(2026, 10, 3)),
         (2, "CHZ-2", "EKG", "Veli", "Genel bakım", 49.5,
          datetime(2026, 10, 5, 9, 0), None, 2, None, None)],
        # kalibrasyonlar
        [(1, "CHZ-1", "EEG", "Kurum A", "SRT-1",
          datetime(2026, 10, 2, 9, 0), date(2027, 10, 2), 1)],
        # arızalar
        [(1, "CHZ-1", "EEG", "Ayşe", "Ekran gitti",
          datetime(2026, 10, 3, 9, 0), None, False, 1),
         (2, "CHZ-2", "EKG", "Fatma", "Kablo kopuk",
          datetime(2026, 10, 4, 9, 0), datetime(2026, 10, 6, 9, 0), True, 2)],
        # cihazların güncel durumu
        [(1, "CHZ-1", "EEG", "Marka X", "Bakimda"),
         (2, "CHZ-2", "EKG", None, "Kullanima_Hazir")],
        # her cihazın son kalibrasyonu (tarih filtresinden bağımsız)
        [(1, "Kurum A", "SRT-1", datetime(2026, 10, 2, 9, 0), date(2027, 10, 2))],
        # her cihazın bir sonraki planlı bakımı
        [(1, date(2027, 4, 1))],
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
    assert sonuc["bakimlar"][0]["cihaz_id"] == 1
    assert [c["durum"] for c in sonuc["cihazlar"]] == ["Bakimda", "Kullanima_Hazir"]
    assert sonuc["cihazlar"][0]["marka_model"] == "Marka X"
    assert sonuc["cihazlar"][0]["son_kalibrasyon"]["sertifika_no"] == "SRT-1"
    assert sonuc["cihazlar"][0]["sonraki_bakim_tarihi"] == "2027-04-01"
    assert sonuc["cihazlar"][1]["son_kalibrasyon"] is None
    assert sonuc["cihazlar"][1]["sonraki_bakim_tarihi"] is None
    # başlangıç/bitiş tarihi boşsa bakım tarihi kullanılır
    assert sonuc["bakimlar"][0]["bakim_baslangic_tarihi"] == "2026-10-01"
    assert sonuc["bakimlar"][1]["bakim_bitis_tarihi"] == "2026-10-05T09:00:00"
    assert sonuc["bakimlar"][1]["sonraki_bakim_tarihi"] is None
    assert [a["durum"] for a in sonuc["arizalar"]] == ["Açık", "Çözüldü"]
    conn.close.assert_called_once()


def test_filtreler_sql_parametresi_olarak_gonderilir():
    conn, cursor = sahte_baglanti()
    cursor.fetchall.side_effect = [[], [], [], [], [], []]

    with patch("sunucu.psycopg2.connect", return_value=conn):
        cihaz_raporlari(
            baslangic_tarihi=date(2026, 10, 1),
            bitis_tarihi=date(2026, 10, 31),
            cihaz_id=7,
            kullanici_id=3,
        )

    sorgular = cursor.execute.call_args_list
    bakim, kalibrasyon, ariza = sorgular[0], sorgular[1], sorgular[2]

    for cagri in (bakim, kalibrasyon):
        sql, parametreler = cagri.args
        assert "%s" in sql
        assert parametreler == [date(2026, 10, 1), date(2026, 10, 31), 7]

    # Arızada bildirim VEYA çözüm tarihi aralıktaysa kayıt dahil edilir.
    ariza_sql, ariza_parametreleri = ariza.args
    assert "t.bildirim_tarihi" in ariza_sql and "t.cozum_tarihi" in ariza_sql
    assert " OR " in ariza_sql
    assert ariza_parametreleri == [
        date(2026, 10, 1), date(2026, 10, 31),
        date(2026, 10, 1), date(2026, 10, 31), 7,
    ]

    # Cihazların güncel durumu, son kalibrasyon ve planlı bakım tarihe bağlı değildir;
    # yalnızca cihaz filtresi uygulanır.
    for cagri in sorgular[3:]:
        sql, parametreler = cagri.args
        assert "baslangic" not in sql
        assert parametreler == [7]


def test_rapor_sadece_okuma_yapar():
    conn, cursor = sahte_baglanti()
    cursor.fetchall.side_effect = [[], [], [], [], [], []]

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