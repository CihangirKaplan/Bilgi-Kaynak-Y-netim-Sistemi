import pytest
from fastapi.testclient import TestClient

import sunucu


class SahteCursor:
    def __init__(self, yetkili):
        self.yetkili = yetkili
        self.sorgu = ""

    def execute(self, sorgu, parametreler=None):
        self.sorgu = sorgu

    def fetchone(self):
        if "SELECT ri.izin_var" in self.sorgu:
            return (1 if self.yetkili else 0,)
        return (2, 0, 1, 1)

    def fetchall(self):
        return [
            (1, 10, "test_user", "LOGIN", "kullanicilar", 10, None),
            (2, 10, "test_user", "UPDATE", "kullanicilar", 10, None),
        ]

    def close(self):
        pass


class SahteBaglanti:
    def __init__(self, yetkili):
        self.yetkili = yetkili

    def cursor(self):
        return SahteCursor(self.yetkili)

    def close(self):
        pass


@pytest.fixture
def istemci(monkeypatch):
    durum = {"yetkili": True}

    monkeypatch.setattr(
        sunucu.psycopg2,
        "connect",
        lambda **kwargs: SahteBaglanti(durum["yetkili"]),
    )

    sunucu.app.dependency_overrides[sunucu.mevcut_kullanici_id] = (
        lambda: 10
    )

    with TestClient(sunucu.app) as client:
        yield client, durum

    sunucu.app.dependency_overrides.pop(
        sunucu.mevcut_kullanici_id, None
    )


def test_yetkisiz_kullanici_engellenir(istemci):
    client, durum = istemci
    durum["yetkili"] = False

    cevap = client.get("/api/audit-kayitlari")

    assert cevap.status_code == 403


def test_yetkili_kullanici_kayitlari_gorur(istemci):
    client, _ = istemci

    cevap = client.get("/api/audit-kayitlari")

    assert cevap.status_code == 200
    veri = cevap.json()
    assert veri["ozet"]["toplam_kayit"] == 2
    assert len(veri["kayitlar"]) == 2


def test_coklu_islem_filtresi(istemci):
    client, _ = istemci

    cevap = client.get(
        "/api/audit-kayitlari",
        params=[
            ("olay_turu", "LOGIN"),
            ("olay_turu", "UPDATE"),
        ],
    )

    assert cevap.status_code == 200


def test_gecersiz_tarih_araligi(istemci):
    client, _ = istemci

    cevap = client.get(
        "/api/audit-kayitlari",
        params={
            "baslangic_tarihi": "2026-10-23",
            "bitis_tarihi": "2026-10-20",
        },
    )

    assert cevap.status_code == 422


def test_gecersiz_islem_turu(istemci):
    client, _ = istemci

    cevap = client.get(
        "/api/audit-kayitlari",
        params={"olay_turu": "GECERSIZ_ISLEM"},
    )

    assert cevap.status_code == 422
