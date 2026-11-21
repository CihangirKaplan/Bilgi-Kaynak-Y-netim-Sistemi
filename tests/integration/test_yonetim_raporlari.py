"""Yönetim raporları API davranış testleri (gerçek DB kullanılmaz)."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

import server.sunucu as sunucu


@pytest.fixture
def rapor_istemcisi(monkeypatch):
    durum = {"izin": 1, "son_sorgu": "", "parametreler": None}

    baglanti = MagicMock()
    imlec = baglanti.cursor.return_value

    def sorgu_calistir(sql, parametreler=None):
        durum["son_sorgu"] = sql
        durum["parametreler"] = parametreler

    def tek_kayit():
        sql = durum["son_sorgu"]

        if "SELECT ri.izin_var" in sql:
            return (durum["izin"],)

        if "COUNT(*) AS toplam" in sql:
            ilk = str(durum["parametreler"][0])

            if ilk == "2026-11-01":
                return (12, 3, 6, 1, 2, 1)

            if ilk == "2026-10-01":
                return (8, 2, 4, 1, 1, 0)

            return (0, 0, 0, 0, 0, 0)

        raise AssertionError("Beklenmeyen SQL sorgusu")

    def coklu_kayit():
        if "GROUP BY baslangic_zamani::date" in durum["son_sorgu"]:
            from datetime import date
            return [
                (date(2026, 11, 1), 3),
                (date(2026, 11, 2), 4),
                (date(2026, 11, 3), 5),
            ]
        raise AssertionError("Beklenmeyen liste sorgusu")

    imlec.execute.side_effect = sorgu_calistir
    imlec.fetchone.side_effect = tek_kayit
    imlec.fetchall.side_effect = coklu_kayit

    monkeypatch.setattr(
        sunucu.psycopg2,
        "connect",
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


YOL = "/api/yonetim-raporlari/randevu-ozet"

TARIHLER = {
    "baslangic": "2026-11-01",
    "bitis": "2026-11-03",
}


def test_yetkili_raporu_gorebilir(rapor_istemcisi):
    istemci, durum = rapor_istemcisi
    durum["izin"] = 1

    yanit = istemci.get(YOL, params=TARIHLER)

    assert yanit.status_code == 200, yanit.text

    veri = yanit.json()
    assert veri["ozet"]["toplam"] == 12
    assert veri["ozet"]["tamamlandi"] == 6
    assert veri["ozet"]["iptal_edildi"] == 2
    assert veri["onceki_ozet"]["toplam"] == 8
    assert veri["ozet"]["sonucu_girilmemis"] == 1          # tarihi geçmiş, hâlâ "Planlandı"
    assert veri["onceki_donem"] == {"baslangic": "2026-10-01", "bitis": "2026-10-03"}   # geçen ayın aynı günleri
    assert veri["toplam_degisim_yuzde"] == 50.0
    assert len(veri["gunluk"]) == 3
    assert sum(g["sayi"] for g in veri["gunluk"]) == 12


def test_yetkisiz_kullanici_403(rapor_istemcisi):
    istemci, durum = rapor_istemcisi
    durum["izin"] = 0

    yanit = istemci.get(YOL, params=TARIHLER)

    assert yanit.status_code == 403


def test_izin_kaydi_yoksa_403(rapor_istemcisi):
    istemci, durum = rapor_istemcisi
    durum["izin"] = None

    yanit = istemci.get(YOL, params=TARIHLER)

    assert yanit.status_code == 403


def test_ters_tarih_araligi_422(rapor_istemcisi):
    istemci, _ = rapor_istemcisi

    yanit = istemci.get(
        YOL,
        params={
            "baslangic": "2026-11-10",
            "bitis": "2026-11-01"
        }
    )

    assert yanit.status_code == 422


def test_366_gunden_uzun_aralik_422(rapor_istemcisi):
    istemci, _ = rapor_istemcisi

    yanit = istemci.get(
        YOL,
        params={
            "baslangic": "2025-01-01",
            "bitis": "2026-11-01"
        }
    )

    assert yanit.status_code == 422


def test_tarih_parametresi_zorunlu(rapor_istemcisi):
    istemci, _ = rapor_istemcisi

    yanit = istemci.get(YOL)

    assert yanit.status_code == 422
