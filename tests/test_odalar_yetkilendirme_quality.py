"""
TKYS - Quality Assurance (QA-001)
GitHub Issue: #186
Test Alani: Oda API Yetkilendirmesi

Amac:
Kimlik dogrulamasi bulunmayan kullanicilarin
oda listesine erisememesini dogrulamak.
"""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from sunucu import app


def test_quality_kimlik_dogrulamasiz_oda_listesi_engellenir():
    """
    Authorization basligi olmayan istek reddedilmelidir.
    """

    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value

    mock_cursor.fetchall.return_value = [
        (1, "Terapi Odasi", 2, True)
    ]

    with patch(
        "sunucu.psycopg2.connect",
        return_value=mock_conn
    ) as mock_connect:
        with TestClient(app) as client:
            response = client.get("/api/odalar")

    assert response.status_code in (401, 403)

    mock_connect.assert_not_called()


def test_quality_giris_yapmis_kullanici_odalari_listeleyebilir():
    """Kimligi dogrulanmis kullanici ozel rol izni olmadan odalari gorebilir."""
    from sunucu import mevcut_kullanici_id

    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value
    mock_cursor.fetchall.return_value = [
        (1, "Terapi Odasi", 2, True)
    ]

    app.dependency_overrides[mevcut_kullanici_id] = lambda: 42

    try:
        with patch("sunucu.psycopg2.connect", return_value=mock_conn):
            with TestClient(app) as client:
                response = client.get("/api/odalar")

        assert response.status_code == 200
        assert response.json() == [
            {
                "oda_id": 1,
                "oda_adi": "Terapi Odasi",
                "kapasite": 2,
                "aktif_mi": True,
            }
        ]

        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()

    finally:
        app.dependency_overrides.pop(mevcut_kullanici_id, None)
