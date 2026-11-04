"""Bakım/kalibrasyon planları API'si: doğrulama, ekleme, güncelleme, silme, listeleme, yetki.

Gerçek PostgreSQL kullanılmaz.
"""
import datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from modeller import BakimPlaniGuncelleModeli, BakimPlaniOlusturModeli
from sunucu import (
    app, bakim_plani_durumu, bakim_plani_ekle, bakim_plani_guncelle, bakim_plani_sil,
    bakim_planlarini_listele, mevcut_kullanici_id,
)

D = datetime.date


def baglanti(fetchone=None, fetchall=None):
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchone.side_effect = fetchone if fetchone is not None else []
    cursor.fetchall.return_value = fetchall if fetchall is not None else []
    return conn, cursor


def sorgular(cursor):
    return [" ".join(c.args[0].split()).upper() for c in cursor.execute.call_args_list]


def olay_turleri(cursor):
    return [c.args[1][1] for c in cursor.execute.call_args_list if "INSERT INTO denetim_kayitlari" in c.args[0]]


# ------------------------------------------------------------------ model doğrulama
def plan(**ek):
    veri = {"cihaz_id": 3, "gorev_turu": "Yıllık bakım", "periyot_gun": 365, "uyari_suresi_gun": 30}
    veri.update(ek)
    return BakimPlaniOlusturModeli(**veri)


def test_gecerli_plan_ve_varsayilan_uyari_suresi():
    p = BakimPlaniOlusturModeli(cihaz_id=1, gorev_turu="  Kalibrasyon ", periyot_gun=180)
    assert p.gorev_turu == "Kalibrasyon" and p.uyari_suresi_gun == 7 and p.sonraki_gorev_tarihi is None


@pytest.mark.parametrize("alan, deger", [
    ("cihaz_id", 0), ("cihaz_id", -1),
    ("gorev_turu", " "), ("gorev_turu", "a"), ("gorev_turu", "x" * 101),
    ("periyot_gun", 0), ("periyot_gun", 3651), ("periyot_gun", -5),
    ("uyari_suresi_gun", -1), ("uyari_suresi_gun", 366),
])
def test_gecersiz_degerler_reddedilir(alan, deger):
    with pytest.raises(ValidationError):
        plan(**{alan: deger})


def test_uyari_suresi_periyottan_uzun_olamaz():
    with pytest.raises(ValidationError):
        plan(periyot_gun=10, uyari_suresi_gun=11)
    assert plan(periyot_gun=10, uyari_suresi_gun=10).uyari_suresi_gun == 10


def test_beklenmeyen_alan_reddedilir_ayricalik_yukseltme_yok():
    with pytest.raises(ValidationError):
        plan(plan_id=99)
    with pytest.raises(ValidationError):
        BakimPlaniGuncelleModeli(cihaz_id=5)              # plan başka cihaza taşınamaz
    with pytest.raises(ValidationError):
        BakimPlaniGuncelleModeli(is_admin=True)


@pytest.mark.parametrize("kalan, uyari, aktif, beklenen", [
    (-1, 7, True, "Gecikmiş"), (0, 7, True, "Yaklaşıyor"), (7, 7, True, "Yaklaşıyor"),
    (8, 7, True, "Planlı"), (-30, 7, False, "Pasif"), (5, 0, True, "Planlı"), (0, 0, True, "Yaklaşıyor"),
])
def test_plan_durumu(kalan, uyari, aktif, beklenen):
    assert bakim_plani_durumu(kalan, uyari, aktif) == beklenen


# ------------------------------------------------------------------------ listeleme
def test_listeleme_alanlari_ve_durumu_dondurur():
    satir = (4, 3, "E1", "Cihaz", "Yıllık bakım", 365, 30, D(2026, 12, 1), 20, True)
    conn, cursor = baglanti(fetchall=[satir])
    with patch("sunucu.psycopg2.connect", return_value=conn):
        sonuc = bakim_planlarini_listele(cihaz_id=None, aktif_mi=None, kullanici_id=1)
    assert sonuc == [{
        "plan_id": 4, "cihaz_id": 3, "envanter_kodu": "E1", "cihaz_adi": "Cihaz", "gorev_turu": "Yıllık bakım",
        "periyot_gun": 365, "uyari_suresi_gun": 30, "sonraki_gorev_tarihi": "2026-12-01", "kalan_gun": 20,
        "aktif_mi": True, "durum": "Yaklaşıyor",
    }]


def test_listeleme_filtreleri_parametre_olarak_gecer():
    conn, cursor = baglanti()
    with patch("sunucu.psycopg2.connect", return_value=conn):
        bakim_planlarini_listele(cihaz_id=3, aktif_mi=True, kullanici_id=1)
    sorgu, parametreler = cursor.execute.call_args.args
    assert "p.cihaz_id = %s" in sorgu and parametreler == [3, True]


def test_listelemede_gecersiz_cihaz_422():
    with pytest.raises(HTTPException) as hata:
        bakim_planlarini_listele(cihaz_id=0, aktif_mi=None, kullanici_id=1)
    assert hata.value.status_code == 422


# -------------------------------------------------------------------------- ekleme
def test_ekleme_basarili_tarih_bos_ise_bugun_artı_periyot_ve_denetim_ayni_islemde():
    conn, cursor = baglanti(fetchone=[(1,), None, (11,)])      # cihaz var, çakışan plan yok, yeni plan_id
    with patch("sunucu.psycopg2.connect", return_value=conn), patch("sunucu.date") as bugun:
        bugun.today.return_value = D(2026, 11, 4)
        sonuc = bakim_plani_ekle(plan(periyot_gun=90), 5)
    assert sonuc["plan_id"] == 11 and sonuc["sonraki_gorev_tarihi"] == "2027-02-02"
    insert = [c for c in cursor.execute.call_args_list if "INSERT INTO cihaz_bakim_planlari" in c.args[0]][0]
    assert insert.args[1] == (3, "Yıllık bakım", 90, 30, D(2027, 2, 2))
    assert olay_turleri(cursor) == ["CREATE"]
    conn.commit.assert_called_once()


def test_ekleme_verilen_tarih_korunur():
    conn, cursor = baglanti(fetchone=[(1,), None, (12,)])
    with patch("sunucu.psycopg2.connect", return_value=conn):
        sonuc = bakim_plani_ekle(plan(sonraki_gorev_tarihi=D(2026, 12, 24)), 5)
    assert sonuc["sonraki_gorev_tarihi"] == "2026-12-24"


def test_ekleme_olmayan_cihaz_404_ve_ayni_turde_aktif_plan_409():
    conn, cursor = baglanti(fetchone=[None])
    with patch("sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            bakim_plani_ekle(plan(), 5)
    assert hata.value.status_code == 404
    conn.commit.assert_not_called()

    conn, cursor = baglanti(fetchone=[(1,), (1,)])
    with patch("sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            bakim_plani_ekle(plan(), 5)
    assert hata.value.status_code == 409
    assert not any(s.startswith("INSERT INTO CIHAZ_BAKIM_PLANLARI") for s in sorgular(cursor))
    conn.rollback.assert_called()


def test_ekleme_beklenmeyen_hata_ayrinti_sizdirmaz_ve_geri_alinir():
    conn, cursor = baglanti(fetchone=[(1,), None, (11,)])

    def calistir(sql, params=None):
        if "INSERT INTO denetim_kayitlari" in sql:
            raise RuntimeError("GIZLI_SQL_AYRINTISI")
    cursor.execute.side_effect = calistir
    with patch("sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            bakim_plani_ekle(plan(), 5)
    assert hata.value.status_code == 500 and "GIZLI" not in str(hata.value.detail)
    conn.rollback.assert_called()
    conn.commit.assert_not_called()


# ---------------------------------------------------------------------- güncelleme
MEVCUT = (3, "Yıllık bakım", 365, 30, True)        # cihaz_id, tür, periyot, uyarı, aktif


def guncelle(model, fetchone):
    conn, cursor = baglanti(fetchone=fetchone)
    with patch("sunucu.psycopg2.connect", return_value=conn):
        try:
            sonuc, hata = bakim_plani_guncelle(7, model, 5), None
        except HTTPException as e:
            sonuc, hata = None, e
    return sonuc, hata, conn, cursor


def test_guncelleme_basarili_yalniz_gonderilen_alanlar_yazilir_ve_denetlenir():
    sonuc, hata, conn, cursor = guncelle(BakimPlaniGuncelleModeli(periyot_gun=180, uyari_suresi_gun=14),
                                         [MEVCUT, None])
    assert hata is None and sonuc["durum"] == "basarili"
    guncelleme = [c for c in cursor.execute.call_args_list if c.args[0].startswith("UPDATE cihaz_bakim_planlari")][0]
    assert guncelleme.args[0] == "UPDATE cihaz_bakim_planlari SET periyot_gun = %s, uyari_suresi_gun = %s WHERE plan_id = %s;"
    assert guncelleme.args[1] == (180, 14, 7)
    assert olay_turleri(cursor) == ["UPDATE"]
    conn.commit.assert_called_once()


def test_guncelleme_bos_istek_veya_bos_deger_422():
    _, hata, _, _ = guncelle(BakimPlaniGuncelleModeli(), [])
    assert hata.status_code == 422
    _, hata, _, _ = guncelle(BakimPlaniGuncelleModeli(gorev_turu=None), [])
    assert hata.status_code == 422


def test_guncelleme_olmayan_plan_404():
    _, hata, conn, _ = guncelle(BakimPlaniGuncelleModeli(periyot_gun=10), [None])
    assert hata.status_code == 404
    conn.commit.assert_not_called()


def test_guncellemede_uyari_periyottan_uzun_olamaz_birlesik_degerlerle_kontrol_edilir():
    # Mevcut uyarı 30; yalnızca periyot 20'ye düşürülürse uyarı (30) periyottan uzun kalır.
    _, hata, conn, cursor = guncelle(BakimPlaniGuncelleModeli(periyot_gun=20), [MEVCUT])
    assert hata.status_code == 422
    assert not any(s.startswith("UPDATE CIHAZ_BAKIM_PLANLARI") for s in sorgular(cursor))


def test_pasif_plan_yeniden_aktiflestirilirken_ayni_turde_aktif_plan_varsa_409():
    pasif = (3, "Yıllık bakım", 365, 30, False)
    _, hata, conn, cursor = guncelle(BakimPlaniGuncelleModeli(aktif_mi=True), [pasif, (1,)])
    assert hata.status_code == 409
    conn.commit.assert_not_called()


def test_pasiflestirme_cakisma_kontrolu_yapmaz():
    sonuc, hata, conn, cursor = guncelle(BakimPlaniGuncelleModeli(aktif_mi=False), [MEVCUT])
    assert hata is None
    assert not any("LOWER(GOREV_TURU)" in s for s in sorgular(cursor))


def test_tur_degisince_yeni_turle_cakisma_aranir_ve_kendi_plani_haric_tutulur():
    _, _, _, cursor = guncelle(BakimPlaniGuncelleModeli(gorev_turu="Kalibrasyon"), [MEVCUT, None])
    cakisma = [c for c in cursor.execute.call_args_list if "LOWER(gorev_turu)" in c.args[0]][0]
    assert cakisma.args[1] == (3, "Kalibrasyon", 7, 7)


# --------------------------------------------------------------------------- silme
def test_silme_basarili_ve_denetlenir():
    conn, cursor = baglanti(fetchone=[(7,)])
    with patch("sunucu.psycopg2.connect", return_value=conn):
        assert bakim_plani_sil(7, 5)["durum"] == "basarili"
    assert olay_turleri(cursor) == ["DELETE"]
    conn.commit.assert_called_once()


def test_silme_olmayan_plan_404():
    conn, cursor = baglanti(fetchone=[None])
    with patch("sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            bakim_plani_sil(7, 5)
    assert hata.value.status_code == 404
    conn.commit.assert_not_called()


# -------------------------------------------------------------------------- yetki
UCLAR = [
    ("get", "/api/bakim-planlari", None),
    ("post", "/api/bakim-planlari", {"cihaz_id": 1, "gorev_turu": "Bakım", "periyot_gun": 30}),
    ("put", "/api/bakim-planlari/1", {"periyot_gun": 30}),
    ("delete", "/api/bakim-planlari/1", None),
]


def istek(yontem, yol, govde, izin_var):
    app.dependency_overrides[mevcut_kullanici_id] = lambda: 5
    conn, cursor = baglanti(fetchone=[(izin_var,)])
    try:
        with patch("sunucu.psycopg2.connect", return_value=conn):
            with TestClient(app) as istemci:
                yanit = getattr(istemci, yontem)(yol, **({"json": govde} if govde else {}))
    finally:
        app.dependency_overrides.pop(mevcut_kullanici_id, None)
    return yanit, cursor


@pytest.mark.parametrize("yontem, yol, govde", UCLAR)
def test_izni_olmayan_rol_403_alir_ve_veriye_dokunulmaz(yontem, yol, govde):
    yanit, cursor = istek(yontem, yol, govde, izin_var=0)
    assert yanit.status_code == 403
    assert all("izin_adi" in s for s in (c.args[0] for c in cursor.execute.call_args_list))


@pytest.mark.parametrize("yontem, yol, govde", UCLAR)
def test_uclar_cihaz_envanter_iznini_ister(yontem, yol, govde):
    _, cursor = istek(yontem, yol, govde, izin_var=0)
    assert cursor.execute.call_args_list[0].args[1][1] == "CIHAZ_ENVANTER_YONET"


@pytest.mark.parametrize("yontem, yol, govde", UCLAR)
def test_tokensiz_istek_reddedilir(yontem, yol, govde):
    with TestClient(app) as istemci:
        assert getattr(istemci, yontem)(yol, **({"json": govde} if govde else {})).status_code in (401, 403)


def test_api_beklenmeyen_alani_422_ile_reddeder():
    yanit, cursor = istek("post", "/api/bakim-planlari",
                          {"cihaz_id": 1, "gorev_turu": "Bakım", "periyot_gun": 30, "plan_id": 9}, izin_var=1)
    assert yanit.status_code == 422
    assert not any("INSERT INTO cihaz_bakim_planlari" in c.args[0] for c in cursor.execute.call_args_list)
