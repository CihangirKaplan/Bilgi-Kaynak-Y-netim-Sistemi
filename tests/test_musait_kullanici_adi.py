"""Boş kullanıcı adı önerisi: aynı isimli kişiler için ad çakışmasını önler.

'cihangir.kaplan' doluysa 'cihangir.kaplan2', o da doluysa 'cihangir.kaplan3' önerilir.
"""
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from sunucu import app, mevcut_kullanici_id

YOL = "/api/kullanicilar/musait-kullanici-adi"


@pytest.fixture(autouse=True)
def giris_yapmis_kullanici():
    app.dependency_overrides[mevcut_kullanici_id] = lambda: 5
    yield
    app.dependency_overrides.pop(mevcut_kullanici_id, None)


def istek(temel, kullanilan=(), izin_var=1):
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchone.return_value = (izin_var,)
    cursor.fetchall.return_value = [(ad,) for ad in kullanilan]
    with patch("sunucu.psycopg2.connect", return_value=conn):
        with TestClient(app) as istemci:
            return istemci.get(YOL, params={"temel": temel}), cursor


@pytest.mark.parametrize("kullanilan, beklenen", [
    ([], "cihangir.kaplan"),
    (["cihangir.kaplan"], "cihangir.kaplan2"),
    (["cihangir.kaplan", "cihangir.kaplan2"], "cihangir.kaplan3"),
    (["cihangir.kaplan", "cihangir.kaplan3"], "cihangir.kaplan2"),   # ilk boş sayı
    (["cihangir.kaplan2"], "cihangir.kaplan"),                       # asıl ad boş
    (["cihangir.kaplanoglu"], "cihangir.kaplan"),                    # sadece benzer, aynı değil
    (["cihangir.kaplan", "cihangir.kaplan10"], "cihangir.kaplan2"),
])
def test_ilk_bos_kullanici_adi_onerilir(kullanilan, beklenen):
    yanit, _ = istek("cihangir.kaplan", kullanilan)
    assert yanit.status_code == 200
    assert yanit.json() == {"kullanici_adi": beklenen}


def test_buyuk_kucuk_harf_farki_ayri_ad_sayilmaz():
    """'Cihangir.Kaplan' kayıtlıysa 'cihangir.kaplan' da dolu sayılır (karışıklık olmasın).

    Karşılaştırma SQL içinde lower() ile yapılır; sahte veritabanı da gerçekte döneceği gibi
    küçük harfli ad döndürür.
    """
    yanit, cursor = istek("cihangir.kaplan", ["cihangir.kaplan"])
    assert yanit.json() == {"kullanici_adi": "cihangir.kaplan2"}
    sorgu = cursor.execute.call_args.args[0]
    assert "lower(kullanici_adi)" in sorgu and "starts_with(lower(kullanici_adi)" in sorgu


def test_istenen_ad_temizlenir():
    yanit, cursor = istek("Cihangir Kaplan!")
    assert yanit.status_code == 200
    assert yanit.json() == {"kullanici_adi": "cihangirkaplan"}
    assert cursor.execute.call_args.args[1] == ("cihangirkaplan",)


@pytest.mark.parametrize("temel", ["", "ab", "...", "!!!"])
def test_cok_kisa_veya_gecersiz_ad_reddedilir(temel):
    yanit, _ = istek(temel)
    assert yanit.status_code == 422


def test_izni_olmayan_rol_403_alir_ve_kullanici_listesi_sorgulanmaz():
    yanit, cursor = istek("cihangir.kaplan", izin_var=0)
    assert yanit.status_code == 403
    assert not any("kullanicilar" in c.args[0] and "starts_with" in c.args[0]
                   for c in cursor.execute.call_args_list)


def test_tokensiz_istek_reddedilir():
    app.dependency_overrides.pop(mevcut_kullanici_id, None)
    with TestClient(app) as istemci:
        assert istemci.get(YOL, params={"temel": "ali.veli"}).status_code in (401, 403)
