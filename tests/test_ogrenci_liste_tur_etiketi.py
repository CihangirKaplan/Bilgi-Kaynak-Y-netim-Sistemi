"""Öğrenci listelerinde danışma masası öğrencilerinin belirtilmesi.

Tüm öğrenciler listelenir; her öğrencinin yanında türü (gönüllü, danışma masası,
asistan) belirtilir.
"""
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from sunucu import app, mevcut_kullanici_id


@pytest.fixture(autouse=True)
def giris_yapmis_kullanici():
    app.dependency_overrides[mevcut_kullanici_id] = lambda: 5
    yield
    app.dependency_overrides.pop(mevcut_kullanici_id, None)


def sahte_baglanti(satirlar):
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchone.return_value = (1,)  # izin_kontrol: izin var
    cursor.fetchall.return_value = satirlar
    return conn


def test_faaliyet_ogrenci_listesinde_her_ogrencinin_turu_belirtilir():
    satirlar = [
        (1, "Ali Yılmaz", "2021001", "GONULLU"),
        (2, "Veli Kaya", "2021002", "DANISMA_MASASI"),
        (3, "Ayşe Demir", "2021003", "ASISTAN"),
    ]
    with patch("sunucu.psycopg2.connect", return_value=sahte_baglanti(satirlar)):
        with TestClient(app) as istemci:
            yanit = istemci.get("/api/ogrenciler-liste")

    assert yanit.status_code == 200
    liste = {k["id"]: k for k in yanit.json()}
    assert len(liste) == 3  # tüm türler listelenir
    assert liste[1]["metin"] == "Ali Yılmaz - [2021001] (Gönüllü Öğrenci)"
    assert liste[2]["metin"] == "Veli Kaya - [2021002] (Danışma Masası Öğrencisi)"
    assert liste[3]["metin"] == "Ayşe Demir - [2021003] (Asistan Öğrenci)"
    assert liste[2]["tur"] == "DANISMA_MASASI"


def test_danisma_yonetimi_ogrenci_listesi_tur_bilgisi_dondurur():
    satirlar = [
        (1, "Ali Yılmaz", "2021001", "GONULLU"),
        (2, "Veli Kaya", "2021002", "DANISMA_MASASI"),
    ]
    with patch("sunucu.psycopg2.connect", return_value=sahte_baglanti(satirlar)):
        with TestClient(app) as istemci:
            yanit = istemci.get("/api/danisma/yonetim/ogrenciler")

    assert yanit.status_code == 200
    ogrenciler = yanit.json()["ogrenciler"]
    assert [o["tur"] for o in ogrenciler] == ["GONULLU", "DANISMA_MASASI"]
    assert [o["tur_etiketi"] for o in ogrenciler] == ["Gönüllü Öğrenci", "Danışma Masası Öğrencisi"]
    assert ogrenciler[1]["ad_soyad"] == "Veli Kaya"
