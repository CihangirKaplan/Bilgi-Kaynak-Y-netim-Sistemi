"""
TKYS - Quality Assurance (QA-001)
GitHub Issue: #186
Test Alani: Kritik API Endpoint RBAC Kontrolleri

Amac:
Yetkisiz kullanicilarin kritik API endpointlerine
erisiminin engellendigini dogrulamak.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from sunucu import app, mevcut_kullanici_id


@pytest.mark.parametrize(
    "endpoint, gerekli_izin",
    [
        (
            "/api/danisma/yonetim/oturumlar",
            "DANISMA_OTURUMU_YONETIM",
        ),
        (
            "/api/danisma/raporlar",
            "DANISMA_OTURUMU_GORUNTULE",
        ),
        (
            "/api/audit-kayitlari",
            "AUDIT_KAYITLARI_INCELE",
        ),
    ],
)
def test_quality_yetkisiz_kullanici_kritik_endpointlere_erisemez(
    endpoint,
    gerekli_izin,
):
    """Kimligi dogrulanmis fakat izni olmayan kullanici 403 almalidir."""

    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value

    mock_cursor.fetchone.return_value = (0,)

    app.dependency_overrides[mevcut_kullanici_id] = lambda: 42

    try:
        with patch(
            "sunucu.psycopg2.connect",
            return_value=mock_conn,
        ):
            with TestClient(app) as client:
                response = client.get(endpoint)

        assert response.status_code == 403
        assert response.json()["detail"] == (
            "Bu işlem için yetkiniz bulunmuyor."
        )

        sorgu, parametreler = mock_cursor.execute.call_args.args

        assert parametreler == (42, gerekli_izin)

        mock_conn.commit.assert_not_called()
        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()

    finally:
        app.dependency_overrides.pop(mevcut_kullanici_id, None)
