"""Yönetim öğrenci raporu API testleri; gerçek DB kullanılmaz."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

import server.sunucu as sunucu


YOL = "/api/yonetim-raporlari/ogrenci-ozet"
TARIHLER = {
    "baslangic": "2026-11-01",
    "bitis": "2026-11-03",
}


@pytest.fixture
def istemci_ve_durum(monkeypatch):
    durum = {"izin": 1, "sql": "", "parametreler": None}

    baglanti = MagicMock()
    imlec = baglanti.cursor.return_value

    def execute(sql, parametreler=None):
        durum["sql"] = sql
        durum["parametreler"] = parametreler

    def fetchone():
        sql = durum["sql"]

        if "SELECT ri.izin_var" in sql:
            return (durum["izin"],)

        if "FROM ogrenciler" in sql:
            return (20, 16)

        if "FROM ogrenci_faaliyet_takip" in sql:
            ilk = str(durum["parametreler"][0])

            if ilk == "2026-11-01":
                return (10, 25, 150, 5)

            if ilk == "2026-10-01":
                return (5, 12, 100, 3)

        raise AssertionError("Beklenmeyen SQL sorgusu")

    def fetchall():
        if "JOIN faaliyetler f" in durum["sql"]:
            return [
                ("Yüz Yüze Anket", 6, 20, 100),
                ("Online Anket", 4, 5, 50),
            ]

        raise AssertionError("Beklenmeyen liste sorgusu")

    imlec.execute.side_effect = execute
    imlec.fetchone.side_effect = fetchone
    imlec.fetchall.side_effect = fetchall

    monkeypatch.setattr(
        sunucu.psycopg2,
        "connect",
        lambda **kwargs: baglanti,
    )

    sunucu.app.dependency_overrides[
        sunucu.mevcut_kullanici_id
    ] = lambda: 5

    try:
        with TestClient(sunucu.app) as istemci:
            yield istemci, durum
    finally:
        sunucu.app.dependency_overrides.pop(
            sunucu.mevcut_kullanici_id, None
        )


def test_ogrenci_istatistikleri(istemci_ve_durum):
    istemci, _ = istemci_ve_durum

    yanit = istemci.get(YOL, params=TARIHLER)

    assert yanit.status_code == 200, yanit.text

    veri = yanit.json()

    assert veri["guncel_ogrenci"] == {
        "toplam": 20,
        "aktif": 16,
    }

    assert veri["ozet"]["kayit_sayisi"] == 10
    assert veri["ozet"]["faaliyet_miktari"] == 25
    assert veri["ozet"]["toplam_puan"] == 150
    assert "onayli_kayit" not in veri["ozet"] and "onayli_puan" not in veri["ozet"]
    assert veri["ozet"]["faaliyet_yapan_ogrenci"] == 5

    assert veri["onceki_ozet"]["toplam_puan"] == 100
    assert veri["degisim_yuzdeleri"]["toplam_puan"] == 50.0

    assert len(veri["faaliyet_dagilimi"]) == 2


def test_yetkisiz_kullanici_403(istemci_ve_durum):
    istemci, durum = istemci_ve_durum

    durum["izin"] = 0
    yanit = istemci.get(YOL, params=TARIHLER)

    assert yanit.status_code == 403


def test_ters_tarih_araligi_422(istemci_ve_durum):
    istemci, _ = istemci_ve_durum

    yanit = istemci.get(
        YOL,
        params={
            "baslangic": "2026-11-10",
            "bitis": "2026-11-01",
        },
    )

    assert yanit.status_code == 422


def test_uzun_tarih_araligi_422(istemci_ve_durum):
    istemci, _ = istemci_ve_durum

    yanit = istemci.get(
        YOL,
        params={
            "baslangic": "2025-01-01",
            "bitis": "2026-11-01",
        },
    )

    assert yanit.status_code == 422
