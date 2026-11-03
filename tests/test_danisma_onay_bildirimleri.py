from datetime import datetime
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from sunucu import app, mevcut_kullanici_id


def test_yetkili_kullanici_bildirimleri_gorur():
    yetki_baglantisi = MagicMock()
    yetki_baglantisi.cursor.return_value.fetchone.return_value = (1,)

    veri_baglantisi = MagicMock()
    cursor = veri_baglantisi.cursor.return_value
    cursor.fetchone.return_value = (2,)
    cursor.fetchall.return_value = [
        (11, "Ogrenci A", datetime(2026, 11, 3, 9, 0)),
        (12, "Ogrenci B", datetime(2026, 11, 3, 9, 30)),
    ]

    app.dependency_overrides[mevcut_kullanici_id] = lambda: 10

    try:
        with patch(
            "sunucu.psycopg2.connect",
            side_effect=[yetki_baglantisi, veri_baglantisi]
        ):
            with TestClient(app) as istemci:
                yanit = istemci.get(
                    "/api/danisma/yonetim/onay-bildirimleri"
                )

        assert yanit.status_code == 200
        assert yanit.json()["toplam"] == 2
        assert len(yanit.json()["oturumlar"]) == 2
        assert yanit.json()["oturumlar"][0]["oturum_id"] == 11

        assert cursor.execute.call_count == 2
        veri_baglantisi.close.assert_called_once()

    finally:
        app.dependency_overrides.pop(mevcut_kullanici_id, None)


def test_yetkisiz_kullanici_bildirimleri_goremez():
    yetki_baglantisi = MagicMock()
    yetki_baglantisi.cursor.return_value.fetchone.return_value = (0,)

    app.dependency_overrides[mevcut_kullanici_id] = lambda: 10

    try:
        with patch(
            "sunucu.psycopg2.connect",
            return_value=yetki_baglantisi
        ) as baglanti:
            with TestClient(app) as istemci:
                yanit = istemci.get(
                    "/api/danisma/yonetim/onay-bildirimleri"
                )

        assert yanit.status_code == 403
        assert baglanti.call_count == 1

    finally:
        app.dependency_overrides.pop(mevcut_kullanici_id, None)
