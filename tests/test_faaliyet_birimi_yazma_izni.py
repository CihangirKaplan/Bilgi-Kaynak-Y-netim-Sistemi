"""Faaliyet birimi yazma uçları (ekle/güncelle/sil) yalnızca FAALIYET_BIRIMI_DUZENLE ister.

Eskiden bu uçlar FAALIYET_KAYITLARI_DUZENLE istiyordu; Memur, Müdür ve Proje Asistanı'nda
bu izin açık olduğundan API'yi doğrudan çağıran bu roller birim ekleyip silebiliyordu.
Birim yönetimi için ayrı ve yalnızca Admin'de açık olan FAALIYET_BIRIMI_DUZENLE izni var.
"""
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from sunucu import app, mevcut_kullanici_id

YAZMA_UCLARI = [
    ("post", "/api/faaliyet-birimleri", {"birim_adi": "YENI BIRIM"}),
    ("put", "/api/faaliyet-birimleri/3", {"birim_adi": "DEGISEN BIRIM"}),
    ("delete", "/api/faaliyet-birimleri/3", None),
]


@pytest.fixture(autouse=True)
def giris_yapmis_kullanici():
    app.dependency_overrides[mevcut_kullanici_id] = lambda: 5
    yield
    app.dependency_overrides.pop(mevcut_kullanici_id, None)


def sahte_baglanti(verilen_izinler):
    """Yalnızca 'verilen_izinler' içindeki izin adı için izin_var=1 döndüren sahte veritabanı."""
    conn = MagicMock()
    cursor = conn.cursor.return_value
    sorulan = []

    def calistir(sql, params=None):
        if "izin_adi" in sql:
            sorulan.append(params[1])
            cursor.fetchone.return_value = (1,) if params[1] in verilen_izinler else None

    cursor.execute.side_effect = calistir
    cursor.fetchall.return_value = []
    return conn, cursor, sorulan


def istek_at(yontem, yol, govde):
    with TestClient(app) as istemci:
        return getattr(istemci, yontem)(yol, **({"json": govde} if govde else {}))


@pytest.mark.parametrize("yontem, yol, govde", YAZMA_UCLARI)
def test_yalniz_kayit_izni_olan_rol_403_alir_ve_yazma_yapilmaz(yontem, yol, govde):
    conn, cursor, sorulan = sahte_baglanti({"FAALIYET_KAYITLARI_DUZENLE"})
    with patch("sunucu.psycopg2.connect", return_value=conn):
        yanit = istek_at(yontem, yol, govde)
    assert yanit.status_code == 403
    assert sorulan == ["FAALIYET_BIRIMI_DUZENLE"]
    sorgular = " ".join(c.args[0] for c in cursor.execute.call_args_list).upper()
    assert "INSERT" not in sorgular and "UPDATE" not in sorgular and "DELETE" not in sorgular
    conn.commit.assert_not_called()


@pytest.mark.parametrize("yontem, yol, govde", YAZMA_UCLARI)
def test_birim_izni_olan_rol_izin_kontrolunu_gecer(yontem, yol, govde):
    conn, _, sorulan = sahte_baglanti({"FAALIYET_BIRIMI_DUZENLE"})
    with patch("sunucu.psycopg2.connect", return_value=conn):
        yanit = istek_at(yontem, yol, govde)
    assert yanit.status_code != 403
    assert sorulan[0] == "FAALIYET_BIRIMI_DUZENLE"


def test_birim_listesi_okuma_ucu_kayit_iziniyle_calismaya_devam_eder():
    """Faaliyet Kayıtları ekranı birim listesini okur; okuma izni değişmedi."""
    conn, _, sorulan = sahte_baglanti({"FAALIYET_KAYITLARI_DUZENLE"})
    with patch("sunucu.psycopg2.connect", return_value=conn):
        with TestClient(app) as istemci:
            yanit = istemci.get("/api/faaliyet-birimleri")
    assert yanit.status_code == 200
    assert sorulan == ["FAALIYET_KAYITLARI_DUZENLE"]
