"""Dinamik atanabilir roller: yetki ve listeleme testleri."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

import sunucu


ENDPOINTLER = [
    ("/api/roller/atanabilir/olusturma", "KULLANICI_OLUSTUR"),
    ("/api/roller/atanabilir/degistirme", "ROL_ATAMA_DEGISTIRME"),
]


@pytest.fixture
def ortam(monkeypatch):
    baglanti = MagicMock()
    cursor = baglanti.cursor.return_value

    durum = {
        "izinler": set(),
        "sorgular": [],
    }

    roller = [
        (1, "PSIKOLOG", "Psikolog"),
        (9, "KLINIK_SORUMLUSU", "Klinik Sorumlusu"),
    ]

    def sorgula(sql, parametreler=None):
        durum["sorgular"].append((sql, parametreler))

    def tek_kayit():
        sql, parametreler = durum["sorgular"][-1]
        if "SELECT ri.izin_var" in sql:
            return (1,) if parametreler[1] in durum["izinler"] else None
        raise AssertionError(f"Beklenmeyen tek kayıt sorgusu: {sql}")

    cursor.execute.side_effect = sorgula
    cursor.fetchone.side_effect = tek_kayit
    cursor.fetchall.return_value = roller

    monkeypatch.setattr(
        sunucu.psycopg2,
        "connect",
        lambda **kwargs: baglanti,
    )

    # Kimliği doğrulanmış test kullanıcısı.
    sunucu.app.dependency_overrides[sunucu.mevcut_kullanici_id] = (
        lambda: 7
    )

    try:
        with TestClient(sunucu.app) as istemci:
            yield istemci, durum, baglanti
    finally:
        sunucu.app.dependency_overrides.pop(
            sunucu.mevcut_kullanici_id, None
        )


@pytest.mark.parametrize("adres,gerekli_izin", ENDPOINTLER)
def test_yetkili_kullanici_rollere_erisir(ortam, adres, gerekli_izin):
    istemci, durum, baglanti = ortam
    durum["izinler"].add(gerekli_izin)

    yanit = istemci.get(adres)

    assert yanit.status_code == 200
    assert yanit.json() == [
        {"rol_id": 1, "rol_adi": "PSIKOLOG", "gorunen_ad": "Psikolog"},
        {
            "rol_id": 9,
            "rol_adi": "KLINIK_SORUMLUSU",
            "gorunen_ad": "Klinik Sorumlusu",
        },
    ]

    sorgular = [sql for sql, _ in durum["sorgular"]]
    liste_sorgusu = next(sql for sql in sorgular if "FROM roller" in sql)

    assert "aktif_mi = TRUE" in liste_sorgusu
    assert "UPPER(rol_adi) <> 'ADMIN'" in liste_sorgusu
    assert baglanti.close.called


@pytest.mark.parametrize("adres,gerekli_izin", ENDPOINTLER)
def test_yetkisiz_kullanici_403_alir(ortam, adres, gerekli_izin):
    istemci, durum, _ = ortam

    yanit = istemci.get(adres)

    assert yanit.status_code == 403
    assert not any(
        "FROM roller" in sql
        for sql, _ in durum["sorgular"]
    )


@pytest.mark.parametrize("adres,gerekli_izin", ENDPOINTLER)
def test_diger_izin_erisime_yetmez(ortam, adres, gerekli_izin):
    istemci, durum, _ = ortam

    diger = (
        "ROL_ATAMA_DEGISTIRME"
        if gerekli_izin == "KULLANICI_OLUSTUR"
        else "KULLANICI_OLUSTUR"
    )
    durum["izinler"].add(diger)

    yanit = istemci.get(adres)

    assert yanit.status_code == 403
