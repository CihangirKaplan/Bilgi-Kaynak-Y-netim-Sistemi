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
    """Kimligi dogrulanmis ve ODA_DURUMU_GORUNTULE izni olan kullanici odalari gorebilir."""
    from sunucu import mevcut_kullanici_id

    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value
    mock_cursor.fetchall.return_value = [
        (1, "Terapi Odasi", 2, True)
    ]
    mock_cursor.fetchone.return_value = (1,)  # izin_kontrol: izin var  

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

        assert mock_cursor.close.call_count == 2
        assert mock_conn.close.call_count == 2

    finally:
        app.dependency_overrides.pop(mevcut_kullanici_id, None)




def test_quality_izni_olmayan_kullanici_odalari_goremez():
    """ODA_DURUMU_GORUNTULE izni olmayan rol 403 alir, oda sorgusu calismaz."""
    from sunucu import mevcut_kullanici_id

    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value
    mock_cursor.fetchone.return_value = (0,)

    app.dependency_overrides[mevcut_kullanici_id] = lambda: 42

    try:
        with patch("sunucu.psycopg2.connect", return_value=mock_conn):
            with TestClient(app) as client:
                response = client.get("/api/odalar")

        assert response.status_code == 403
        sorgular = [c.args[0] for c in mock_cursor.execute.call_args_list]
        assert not any("FROM odalar" in s for s in sorgular)
    finally:
        app.dependency_overrides.pop(mevcut_kullanici_id, None)