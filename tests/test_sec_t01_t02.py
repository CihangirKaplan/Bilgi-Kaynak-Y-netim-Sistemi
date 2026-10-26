from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import jwt
from fastapi.testclient import TestClient

from guvenlik import JWT_ALGORITHM, JWT_SECRET
from sunucu import app, mevcut_kullanici_id


def test_sec_t01_suresi_dolmus_token_http_401():
    token = jwt.encode(
        {
            "sub": "5",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
        },
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )

    with TestClient(app) as client:
        yanit = client.get(
            "/api/korumali-test",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert yanit.status_code == 401
    assert yanit.json()["detail"] == "Token süresi dolmuş."


def test_sec_t02_yetkisiz_cihaz_islemi_http_403():
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchone.return_value = (0,)

    app.dependency_overrides[mevcut_kullanici_id] = lambda: 5

    try:
        with patch("sunucu.psycopg2.connect", return_value=conn):
            with TestClient(app) as client:
                yanit = client.get("/api/cihazlar")

        assert yanit.status_code == 403
        conn.commit.assert_not_called()
    finally:
        app.dependency_overrides.pop(mevcut_kullanici_id, None)
