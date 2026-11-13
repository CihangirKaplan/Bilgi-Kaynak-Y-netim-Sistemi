"""Gerçek PostgreSQL: bozuk girdi hiçbir uçta "500 sunucu hatası" üretmemeli.

Bu test CI'daki "PostgreSQL Entegrasyon Testleri" işinde (alembic upgrade head sonrası) çalışır. OpenAPI şemasındaki
tüm POST/PUT/PATCH/DELETE uçlarına bozuk değerler (taşan sayı, NUL karakteri, çok uzun metin, yanlış tür, SQL
parçası...) gönderir; yanıt 5xx ise hangi uç ve hangi girdi olduğunu yazarak kırılır. Yeni bir uç eklenip girdisi
doğrulanmazsa PR kırmızı olur.

Veriyi bozmamak için yol parametreleri hep var olmayan bir kayıt numarasına (99999999) gider. Test, diğer PostgreSQL
testlerini etkilememesi için dosya adı sırasında sona yakın çalışır ve kendi geçici yönetici kullanıcısını oluşturur.
"""

import os
from uuid import uuid4

import psycopg2
import pytest
from fastapi.testclient import TestClient

from guvenlik import access_token_olustur, parola_hashle
from sunucu import VT_AYARLARI, app

OLMAYAN_KAYIT = "99999999"
YONTEMLER = ("post", "put", "patch", "delete")
ATLANANLAR = {("post", "/api/login")}                    # oturum açma hız sınırına takılır; ayrı testlerle kapsanır

BOZUK_DEGERLER = [
    0, -1, 2**31, 2**63, -(2**31) - 1, 1e308, "", "x" * 5000, "'; DROP TABLE kullanicilar;--", "\x00", "a\x00b",
    "🙂" * 50, None, [], {}, True, "abc", "0000-00-00", "9999-12-31", [1] * 200,
]


def _dogru_veritabani(cursor):
    # Yanlış veritabanında çalışmayı kesinlikle engelle.
    assert os.getenv("TKYS_PG_TEST_ONAY") == "EVET"
    assert VT_AYARLARI["dbname"] == "crkys_alembic_test"
    cursor.execute("SELECT current_database()")
    assert cursor.fetchone()[0] == "crkys_alembic_test"


@pytest.fixture(scope="module")
def yonetici_basligi():
    conn = psycopg2.connect(**VT_AYARLARI)
    try:
        with conn.cursor() as cursor:
            _dogru_veritabani(cursor)
            cursor.execute("SELECT rol_id FROM roller WHERE rol_adi = 'ADMIN'")
            rol_id = cursor.fetchone()[0]
            parola_hash = parola_hashle("Fuzz!Parola2026x")
            cursor.execute(
                "INSERT INTO kullanicilar (kullanici_adi, parola_hash, rol_id, aktif_mi, ilk_giris_mi) "
                "VALUES (%s, %s, %s, TRUE, FALSE) RETURNING kullanici_id",
                (f"fuzz_{uuid4().hex[:10]}", parola_hash, rol_id),
            )
            kullanici_id = cursor.fetchone()[0]
        conn.commit()
    finally:
        conn.close()
    return {"Authorization": "Bearer " + access_token_olustur(kullanici_id, parola_hash)}


def _coz(sema, parca):
    while "$ref" in parca:
        parca = sema["components"]["schemas"][parca["$ref"].split("/")[-1]]
    return parca


def _alan_tipi(sema, alan):
    alan = _coz(sema, alan)
    for secenek in alan.get("anyOf", []):
        secenek = _coz(sema, secenek)
        if secenek.get("type") != "null":
            return secenek
    return alan


def _ornek_deger(sema, alan):
    alan = _alan_tipi(sema, alan)
    tur = alan.get("type")
    if "enum" in alan:
        return alan["enum"][0]
    if tur == "integer":
        return 1
    if tur == "number":
        return 1.0
    if tur == "boolean":
        return True
    if tur == "array":
        return []
    if tur == "string":
        bicim = alan.get("format")
        return "2026-11-17" if bicim == "date" else "2026-11-17T10:00:00" if bicim == "date-time" else "x"
    return None


def _denemeler(sema, islem):
    """(ad, istek parametreleri) çiftleri: gövdesiz, boş gövde, alan alan bozuk değer, sorgu parametresi bozuk değer."""
    yield "gövde yok", {}
    yield "boş gövde", {"json": {}}
    govde_sema = islem.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema")
    alanlar = _coz(sema, govde_sema).get("properties", {}) if govde_sema else {}
    taban = {ad: _ornek_deger(sema, alan) for ad, alan in alanlar.items()}
    for ad in alanlar:
        for bozuk in BOZUK_DEGERLER:
            govde = dict(taban)
            govde[ad] = bozuk
            yield f"{ad}={str(bozuk)[:20]!r}", {"json": govde}
    for parametre in islem.get("parameters", []):
        if parametre["in"] != "query":
            continue
        for bozuk in BOZUK_DEGERLER[:12]:
            if isinstance(bozuk, (list, dict)) or bozuk is None:
                continue
            ek = {"json": taban} if taban else {}
            yield f"?{parametre['name']}={str(bozuk)[:20]!r}", {"params": {parametre["name"]: bozuk}, **ek}


def test_bozuk_girdi_hicbir_uçta_500_uretmez(yonetici_basligi):
    istemci = TestClient(app, raise_server_exceptions=False)
    sema = istemci.get("/openapi.json").json()

    sayac = 0
    bulgular = []
    for yol, islemler in sorted(sema["paths"].items()):
        for yontem, islem in islemler.items():
            if yontem not in YONTEMLER or (yontem, yol) in ATLANANLAR:
                continue
            url = yol
            for parametre in islem.get("parameters", []):
                if parametre["in"] == "path":
                    url = url.replace("{" + parametre["name"] + "}", OLMAYAN_KAYIT)
            for ad, istek in _denemeler(sema, islem):
                yanit = istemci.request(yontem.upper(), url, headers=yonetici_basligi, **istek)
                sayac += 1
                if yanit.status_code >= 500:
                    bulgular.append(f"{yontem.upper()} {yol} [{ad}] -> {yanit.status_code}")

    assert sayac > 500, f"Beklenenden az istek denendi ({sayac}); OpenAPI şeması okunamamış olabilir."
    assert not bulgular, (
        f"{len(bulgular)} bozuk girdi sunucu hatası (5xx) üretti:\n" + "\n".join(bulgular[:40])
    )
