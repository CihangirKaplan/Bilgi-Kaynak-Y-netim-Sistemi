"""TKYS yönetim cihaz raporları API testleri."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

import server.sunucu as sunucu


YOL = "/api/yonetim-raporlari/cihaz-ozet"
TARIHLER = {
    "baslangic": "2026-11-01",
    "bitis": "2026-11-03",
}


@pytest.fixture
def istemci_ve_durum(monkeypatch):
    durum = {"izin": 1, "sorgu": "", "parametreler": None}
    baglanti = MagicMock()
    imlec = baglanti.cursor.return_value

    def execute(sql, parametreler=None):
        durum["sorgu"] = sql
        durum["parametreler"] = parametreler

    def fetchone():
        sql = durum["sorgu"]

        if "SELECT ri.izin_var" in sql:
            return (durum["izin"],)

        if "SELECT COUNT(*)" in sql:
            tablo_sayilari = {
                "cihaz_bakimlari": (6, 3),
                "cihaz_kalibrasyonlari": (4, 2),
                "cihaz_arizalari": (3, 6),
                "cihaz_rezervasyonlari": (12, 8),
            }

            ilk = str(durum["parametreler"][0])
            indeks = 0 if ilk == "2026-11-01" else 1

            for tablo, sayilar in tablo_sayilari.items():
                if f"FROM {tablo}" in sql:
                    return (sayilar[indeks],)

        raise AssertionError("Beklenmeyen SQL sorgusu")

    imlec.execute.side_effect = execute
    imlec.fetchone.side_effect = fetchone

    monkeypatch.setattr(
        sunucu.psycopg2, "connect",
        lambda **kwargs: baglanti
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


def test_cihaz_istatistikleri(istemci_ve_durum):
    istemci, _ = istemci_ve_durum
    yanit = istemci.get(YOL, params=TARIHLER)

    assert yanit.status_code == 200, yanit.text
    veri = yanit.json()

    assert veri["ozet"] == {
        "bakim": 6,
        "kalibrasyon": 4,
        "ariza": 3,
        "rezervasyon": 12,
    }

    assert veri["onceki_ozet"] == {
        "bakim": 3,
        "kalibrasyon": 2,
        "ariza": 6,
        "rezervasyon": 8,
    }

    assert veri["degisim_yuzdeleri"] == {
        "bakim": 100.0,
        "kalibrasyon": 100.0,
        "ariza": -50.0,
        "rezervasyon": 50.0,
    }


def test_yetkisiz_kullanici_403(istemci_ve_durum):
    istemci, durum = istemci_ve_durum
    durum["izin"] = 0

    yanit = istemci.get(YOL, params=TARIHLER)
    assert yanit.status_code == 403


def test_ters_tarih_422(istemci_ve_durum):
    istemci, _ = istemci_ve_durum

    yanit = istemci.get(YOL, params={
        "baslangic": "2026-11-10",
        "bitis": "2026-11-01",
    })

    assert yanit.status_code == 422


def test_fazla_uzun_aralik_422(istemci_ve_durum):
    istemci, _ = istemci_ve_durum

    yanit = istemci.get(YOL, params={
        "baslangic": "2025-01-01",
        "bitis": "2026-11-01",
    })

    assert yanit.status_code == 422
