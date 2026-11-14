"""
TKYS - Quality Assurance (QA-001)
GitHub Issue: #186
Test Alani: Randevu Goruntuleme ve Danisan Kodu RBAC

Amac:
Yetkisiz rollerin randevulari goruntulemesini
ve danisan kodu olusturmasini engellemek.

Iki uc de artik RANDEVU_OLUSTUR iznine baglidir (izin_kontrol); rol adina
gore ic kontrol yapilmaz. Izin matrisinde bu izin PSIKOLOG,
DANISMA_OGRENCISI ve ADMIN rollerinde aciktir.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from sunucu import app, mevcut_kullanici_id

UCLAR = [
    ("get", "/api/randevular"),
    ("post", "/api/danisan-kodlari"),
]


@pytest.fixture(autouse=True)
def giris_yapmis_kullanici():
    app.dependency_overrides[mevcut_kullanici_id] = lambda: 10
    yield
    app.dependency_overrides.pop(mevcut_kullanici_id, None)


def istek_at(metot, yol):
    with TestClient(app) as istemci:
        return getattr(istemci, metot)(yol)


@pytest.mark.parametrize("metot, yol", UCLAR)
@pytest.mark.parametrize("izin_sonucu", [None, (0,)])
def test_quality_izni_olmayan_rol_403_alir(metot, yol, izin_sonucu):
    """
    QA-001 #186:
    Izni olmayan (veya izin satiri bulunmayan) kullanici
    randevu listesini goremez, danisan kodu olusturamaz.
    """
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchone.return_value = izin_sonucu

    with patch("sunucu.psycopg2.connect", return_value=conn):
        yanit = istek_at(metot, yol)

    assert yanit.status_code == 403

    sorgular = [c.args[0].strip().upper() for c in cursor.execute.call_args_list]
    assert not any(s.startswith(("INSERT", "UPDATE", "DELETE")) for s in sorgular)
    assert not any("FROM RANDEVULAR" in s for s in sorgular)
    conn.commit.assert_not_called()
    cursor.close.assert_called_once()
    conn.close.assert_called_once()


def test_quality_izni_olan_rol_randevulari_listeler():
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchone.return_value = (1,)
    cursor.fetchall.return_value = []

    with patch("sunucu.psycopg2.connect", return_value=conn):
        yanit = istek_at("get", "/api/randevular")

    assert yanit.status_code == 200
    assert yanit.json() == []


def test_quality_izni_olan_rol_danisan_kodu_olusturur():
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchone.side_effect = [
        (1,),  # izin_kontrol: izin var
        (3, "PSIKOLOG"),  # (personel_id, rol) - aktif psikolog
        (7,),  # danisan_kodu_seq
        ("DAN-2026-0007", True, "YOK", True, datetime(2026, 1, 1, 9, 0), 3),  # INSERT ... RETURNING
    ]

    with patch("sunucu.psycopg2.connect", return_value=conn):
        yanit = istek_at("post", "/api/danisan-kodlari?yas_grubu=YETISKIN")

    assert yanit.status_code == 201
    assert yanit.json()["durum"] == "basarili"
    conn.commit.assert_called_once()


@pytest.mark.parametrize("metot, yol", UCLAR)
def test_quality_tokensiz_istek_reddedilir(metot, yol):
    app.dependency_overrides.pop(mevcut_kullanici_id, None)
    assert istek_at(metot, yol).status_code in (401, 403)
