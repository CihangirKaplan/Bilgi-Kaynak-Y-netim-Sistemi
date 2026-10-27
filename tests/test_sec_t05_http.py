import pytest
from fastapi.testclient import TestClient

from sunucu import app, izin_kontrol


@pytest.mark.parametrize(
    "veri",
    [
        {},
        {"psikolog_id": -1, "oda_id": 1,
         "baslangic_zamani": "2026-10-15T10:00:00",
         "bitis_zamani": "2026-10-15T11:00:00"},
        {"psikolog_id": 1, "oda_id": 1,
         "baslangic_zamani": "gecersiz-tarih",
         "bitis_zamani": "2026-10-15T11:00:00"},
    ],
)
def test_gecersiz_randevu_http_422(veri):
    rota = next(
        r for r in app.routes
        if getattr(r, "path", None) == "/api/randevular"
        and "POST" in getattr(r, "methods", set())
    )

    yetki_bagimliligi = rota.dependant.dependencies[0].call
    app.dependency_overrides[yetki_bagimliligi] = lambda: 1

    try:
        with TestClient(app) as client:
            yanit = client.post("/api/randevular", json=veri)

        assert yanit.status_code == 422
    finally:
        app.dependency_overrides.pop(yetki_bagimliligi, None)
