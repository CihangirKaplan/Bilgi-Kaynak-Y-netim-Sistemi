from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from sunucu import app


@pytest.mark.parametrize(
    "yol,veri,sonuclar",
    [
        (
            "/api/randevular/5",
            {"oda_id": 1},
            [
                (
                    "TEST-D-001",
                    2,
                    1,
                    "2026-10-15T10:00:00",
                    "2026-10-15T11:00:00",
                    "PLANLANDI",
                ),
                ("PSIKOLOG",),
                (1,),
            ],
        ),
        (
            "/api/randevular/5/iptal",
            None,
            [
                (2, "PLANLANDI"),
                ("PSIKOLOG",),
                (1,),
            ],
        ),
    ],
)
def test_psikolog_baskasinin_randevusunu_http_uzerinden_degistiremez(
    yol, veri, sonuclar
):
    endpoint = next(
        route for route in app.routes
        if getattr(route, "path", None)
        == (
            "/api/randevular/{randevu_id}/iptal"
            if yol.endswith("/iptal")
            else "/api/randevular/{randevu_id}"
        )
        and "PATCH" in getattr(route, "methods", set())
    )

    yetki_bagimliligi = endpoint.dependant.dependencies[0].call

    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchone.side_effect = sonuclar

    app.dependency_overrides[yetki_bagimliligi] = lambda: 10

    try:
        with patch("sunucu.psycopg2.connect", return_value=conn):
            with TestClient(app) as client:
                yanit = client.patch(yol, json=veri)

        assert yanit.status_code == 403

        sorgular = [
            c.args[0].strip().upper()
            for c in cursor.execute.call_args_list
        ]

        assert not any(
            sorgu.startswith(("UPDATE", "INSERT", "DELETE"))
            for sorgu in sorgular
        )

        conn.commit.assert_not_called()

    finally:
        app.dependency_overrides.pop(yetki_bagimliligi, None)
