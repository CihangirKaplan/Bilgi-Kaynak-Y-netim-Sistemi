"""Oda etkinliklerinde katilimci sayisi oda kapasitesinden bagimsizdir."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.oda_etkinlikleri_api import router_olustur


class SahteCursor:
    def __init__(self):
        self.sorgu = ""
        self.kaydedilen_katilimci = None

    def execute(self, sorgu, parametreler=None):
        self.sorgu = sorgu

        if "INSERT INTO oda_etkinlikleri (" in sorgu:
            self.kaydedilen_katilimci = parametreler[3]

    def fetchone(self):
        if "FROM odalar" in self.sorgu:
            return {"?column?": 1}

        if "FROM personel" in self.sorgu:
            return {"personel_id": 1}

        if "RETURNING etkinlik_id" in self.sorgu:
            return {"etkinlik_id": 42}

        return None

    def close(self):
        pass


class SahteBaglanti:
    def __init__(self):
        self.cursor_nesnesi = SahteCursor()

    def cursor(self, **kwargs):
        return self.cursor_nesnesi

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


def test_katilimci_sayisi_oda_kapasitesini_asabilir(monkeypatch):
    baglanti = SahteBaglanti()

    monkeypatch.setattr(
        "server.oda_etkinlikleri_api.psycopg2.connect",
        lambda **kwargs: baglanti,
    )

    uygulama = FastAPI()
    uygulama.include_router(
        router_olustur(lambda izin: lambda: 1, {})
    )

    with TestClient(uygulama) as istemci:
        cevap = istemci.post(
            "/api/oda-etkinlikleri",
            json={
                "oda_id": 1,
                "organize_eden_personel_id": 1,
                "etkinlik_adi": "Kapasite bagimsizlik testi",
                "katilimci_sayisi": 12,
                "baslangic_zamani": "2048-06-15T10:00:00",
                "bitis_zamani": "2048-06-15T11:00:00",
            },
        )

    assert cevap.status_code == 201, cevap.text
    assert cevap.json()["etkinlik_id"] == 42
    assert baglanti.cursor_nesnesi.kaydedilen_katilimci == 12
