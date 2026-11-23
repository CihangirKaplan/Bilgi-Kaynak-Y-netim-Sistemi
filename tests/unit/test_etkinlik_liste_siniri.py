"""Oda etkinlikleri listesi: en yeni N etkinlik döner; kesildiyse yanıt bunu bildirir (istemci yalnızca "etkinlikler" okur)."""
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server import oda_etkinlikleri_api as api


class SahteImlec:
    def __init__(self, toplam, kayitlar):
        self.toplam, self.kayitlar, self.sorgular = toplam, kayitlar, []

    def execute(self, sorgu, parametreler=None):
        self.sorgular.append((" ".join(sorgu.split()), parametreler))

    def fetchone(self):
        return {"toplam": self.toplam}

    def fetchall(self):
        return self.kayitlar

    def close(self):
        pass


class SahteBaglanti:
    def __init__(self, imlec):
        self.imlec = imlec

    def cursor(self, **kwargs):
        return self.imlec

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


def istemci(imlec):
    uygulama = FastAPI()
    uygulama.include_router(api.router_olustur(lambda izin: (lambda: 7), {}))
    patch_ = patch.object(api, "vt_baglan", return_value=SahteBaglanti(imlec))
    patch_.start()
    return TestClient(uygulama), patch_


def test_varsayilan_sinir_2000_ve_yanit_alanlari():
    imlec = SahteImlec(toplam=3, kayitlar=[{"etkinlik_id": 1}, {"etkinlik_id": 2}, {"etkinlik_id": 3}])
    istek, yama = istemci(imlec)
    try:
        yanit = istek.get("/api/oda-etkinlikleri")
    finally:
        yama.stop()
    assert yanit.status_code == 200
    assert yanit.json() == {"etkinlikler": [{"etkinlik_id": 1}, {"etkinlik_id": 2}, {"etkinlik_id": 3}], "toplam": 3, "kesildi": False}
    liste_sorgusu, parametreler = imlec.sorgular[1]
    assert "ORDER BY e.baslangic_zamani DESC" in liste_sorgusu and liste_sorgusu.endswith("LIMIT %s")
    assert parametreler[-1] == api.LISTE_VARSAYILAN_SINIR == 2000


def test_sinir_asildiysa_kesildi_isaretlenir():
    imlec = SahteImlec(toplam=5, kayitlar=[{"etkinlik_id": 5}, {"etkinlik_id": 4}])
    istek, yama = istemci(imlec)
    try:
        yanit = istek.get("/api/oda-etkinlikleri", params={"limit": 2})
    finally:
        yama.stop()
    assert yanit.json()["toplam"] == 5 and yanit.json()["kesildi"] is True and len(yanit.json()["etkinlikler"]) == 2
    assert imlec.sorgular[1][1][-1] == 2


@pytest.mark.parametrize("limit", [0, -1, api.LISTE_EN_COK_SINIR + 1, "abc"])
def test_gecersiz_sinir_reddedilir(limit):
    istek, yama = istemci(SahteImlec(0, []))
    try:
        assert istek.get("/api/oda-etkinlikleri", params={"limit": limit}).status_code == 422
    finally:
        yama.stop()


def test_tarih_suzgeci_toplama_ve_listeye_ayni_kosulla_uygulanir():
    imlec = SahteImlec(0, [])
    istek, yama = istemci(imlec)
    try:
        istek.get("/api/oda-etkinlikleri", params={"baslangic": "2026-11-01", "bitis": "2026-11-30"})
    finally:
        yama.stop()
    (sayim, sayim_par), (liste, liste_par) = imlec.sorgular[0], imlec.sorgular[1]
    assert "COUNT(*)" in sayim and "oda_etkinlik_gunleri" in sayim and "oda_etkinlik_gunleri" in liste
    assert liste_par[:-1] == sayim_par and len(sayim_par) == 2
