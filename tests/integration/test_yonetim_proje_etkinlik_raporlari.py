"""Yönetim proje ve etkinlik API testleri."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

import server.sunucu as sunucu


YOL = "/api/yonetim-raporlari/proje-etkinlik-ozet"
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

        ilk = str(durum["parametreler"][0])
        mevcut = ilk == "2026-11-01"

        if "FROM cihaz_rezervasyonlari" in sql:
            return (12, 10, 2) if mevcut else (8, 7, 1)

        if "FROM oda_etkinlikleri" in sql:
            return (5, 4, 80) if mevcut else (4, 3, 60)

        raise AssertionError("Beklenmeyen SQL sorgusu")

    def fetchall():
        if "GROUP BY 1" in durum["sql"]:
            return [
                ("Araştırma", 6),
                ("Eğitim", 3),
                ("Belirtilmemiş", 1),
            ]

        raise AssertionError("Beklenmeyen liste sorgusu")

    imlec.execute.side_effect = execute
    imlec.fetchone.side_effect = fetchone
    imlec.fetchall.side_effect = fetchall

    monkeypatch.setattr(
        sunucu.psycopg2, "connect",
        lambda **kwargs: baglanti,
    )

    sunucu.app.dependency_overrides[
        sunucu.mevcut_kullanici_id
    ] = lambda: 5

    try:
        with TestClient(sunucu.app) as istemci:
            yield istemci, durum, imlec
    finally:
        sunucu.app.dependency_overrides.pop(
            sunucu.mevcut_kullanici_id, None
        )


def test_proje_etkinlik_istatistikleri(istemci_ve_durum):
    istemci, _, imlec = istemci_ve_durum

    yanit = istemci.get(YOL, params=TARIHLER)

    assert yanit.status_code == 200, yanit.text
    veri = yanit.json()

    assert veri["ozet"]["rezervasyon_toplam"] == 12
    assert veri["ozet"]["rezervasyon_iptal_edilmemis"] == 10
    assert veri["ozet"]["rezervasyon_iptal"] == 2

    assert veri["ozet"]["etkinlik_toplam"] == 5
    assert veri["ozet"]["etkinlik_iptal_edilmemis"] == 4
    assert veri["ozet"]["kayitli_katilimci_toplami"] == 80

    assert veri["onceki_ozet"]["rezervasyon_toplam"] == 8
    assert veri["onceki_ozet"]["kayitli_katilimci_toplami"] == 60

    assert veri["degisim_yuzdeleri"]["rezervasyon_toplam"] == 50.0
    assert veri["degisim_yuzdeleri"]["etkinlik_toplam"] == 25.0

    assert len(veri["proje_turu_dagilimi"]) == 3
    assert sum(
        x["rezervasyon_sayisi"]
        for x in veri["proje_turu_dagilimi"]
    ) == 10

    sql_metinleri = [
        c.args[0] for c in imlec.execute.call_args_list
    ]
    assert any(
        "iptal_edildi_mi IS NOT TRUE" in sql
        for sql in sql_metinleri
    )


def test_yetkisiz_kullanici_403(istemci_ve_durum):
    istemci, durum, _ = istemci_ve_durum
    durum["izin"] = 0

    yanit = istemci.get(YOL, params=TARIHLER)
    assert yanit.status_code == 403


def test_izin_kaydi_yoksa_403(istemci_ve_durum):
    istemci, durum, _ = istemci_ve_durum
    durum["izin"] = None

    yanit = istemci.get(YOL, params=TARIHLER)
    assert yanit.status_code == 403


def test_ters_tarih_araligi_422(istemci_ve_durum):
    istemci, _, _ = istemci_ve_durum

    yanit = istemci.get(
        YOL,
        params={
            "baslangic": "2026-11-10",
            "bitis": "2026-11-01",
        },
    )
    assert yanit.status_code == 422


def test_uzun_tarih_araligi_422(istemci_ve_durum):
    istemci, _, _ = istemci_ve_durum

    yanit = istemci.get(
        YOL,
        params={
            "baslangic": "2025-01-01",
            "bitis": "2026-11-01",
        },
    )
    assert yanit.status_code == 422
