"""GET /api/cihaz-uygunluk: dönem üretimi, uyarılar, doğrulama, yetki, gizlilik."""
import datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from sunucu import (app, cihaz_uygunluk_getir, cihaz_uygunluk_hazirla, mevcut_kullanici_id,
                    UYGUNLUK_EN_FAZLA_GUN)

D, DT = datetime.date, datetime.datetime
BUGUN = D(2026, 11, 4)
BAS, BIT = D(2026, 11, 2), D(2026, 11, 8)


def hazirla(cihazlar=None, rez=(), bakim=(), kal=(), ariza=(), son_kal=(), son_bakim=(), bas=BAS, bit=BIT, bugun=BUGUN):
    cihazlar = cihazlar if cihazlar is not None else [(1, "E-1", "EEG", "Kullanima_Hazir")]
    return cihaz_uygunluk_hazirla(bugun, bas, bit, cihazlar, list(rez), list(bakim), list(kal),
                                  list(ariza), list(son_kal), list(son_bakim))


def donemler(sonuc, cihaz_id=1):
    return next(c for c in sonuc["cihazlar"] if c["cihaz_id"] == cihaz_id)["donemler"]


# ----------------------------------------------------------------- dönem üretimi
def test_rezervasyon_donemi_saatiyle_gelir():
    s = hazirla(rez=[(1, DT(2026, 11, 5, 10, 0), DT(2026, 11, 5, 12, 30))])
    assert donemler(s) == [{"tur": "REZERVASYON", "baslangic": "2026-11-05T10:00:00",
                            "bitis": "2026-11-05T12:30:00", "kaynak": "kayit"}]


def test_bakim_ve_kalibrasyon_gun_araligi_bitis_gunu_dahil_olarak_gelir():
    s = hazirla(bakim=[(1, D(2026, 11, 3), D(2026, 11, 4))], kal=[(1, D(2026, 11, 6), D(2026, 11, 6))])
    d = {x["tur"]: x for x in donemler(s)}
    assert (d["BAKIM"]["baslangic"], d["BAKIM"]["bitis"]) == ("2026-11-03T00:00:00", "2026-11-05T00:00:00")
    assert (d["KALIBRASYON"]["baslangic"], d["KALIBRASYON"]["bitis"]) == ("2026-11-06T00:00:00", "2026-11-07T00:00:00")


def test_acik_ariza_bitissiz_cozulen_ariza_bitisli_cozum_tarihsiz_cozulen_atlanir():
    s = hazirla(ariza=[(1, DT(2026, 11, 3, 14, 0), None, False),
                       (1, DT(2026, 11, 2, 9, 0), DT(2026, 11, 3, 9, 0), True),
                       (1, DT(2026, 11, 2, 8, 0), None, True)])
    ariza = [x for x in donemler(s) if x["tur"] == "ARIZA"]
    assert [(x["baslangic"], x["bitis"]) for x in ariza] == [("2026-11-02T09:00:00", "2026-11-03T09:00:00"),
                                                              ("2026-11-03T14:00:00", None)]


@pytest.mark.parametrize("durum, tur", [("Bakimda", "BAKIM"), ("Kalibrasyonda", "KALIBRASYON"),
                                        ("Arizali", "ARIZA"), ("Kullanim_Disi", "KULLANIM_DISI")])
def test_cihaz_durumundan_bugunden_baslayan_acik_uclu_donem_turer(durum, tur):
    s = hazirla(cihazlar=[(1, "E-1", "EEG", durum)])
    assert donemler(s) == [{"tur": tur, "baslangic": "2026-11-04T00:00:00", "bitis": None, "kaynak": "durum"}]


@pytest.mark.parametrize("durum", ["Kullanima_Hazir", "Rezerve", "Kullanimda"])
def test_diger_durumlar_donem_uretmez(durum):
    assert donemler(hazirla(cihazlar=[(1, "E-1", "EEG", durum)])) == []


def test_gecmis_haftada_durumdan_donem_uretilmez_ama_kayitlar_gelir():
    gecmis = hazirla(cihazlar=[(1, "E-1", "EEG", "Arizali")], bas=D(2026, 10, 12), bit=D(2026, 10, 18),
                     bakim=[(1, D(2026, 10, 14), D(2026, 10, 14))])
    assert [x["tur"] for x in donemler(gecmis)] == ["BAKIM"]          # arızalı durumu geçmiş haftaya yazılmaz


def test_gelecek_haftada_durumdan_donem_haftanin_basindan_baslar():
    gelecek = hazirla(cihazlar=[(1, "E-1", "EEG", "Bakimda")], bas=D(2026, 11, 9), bit=D(2026, 11, 15))
    assert donemler(gelecek)[0]["baslangic"] == "2026-11-09T00:00:00"


def test_listede_olmayan_cihazin_kayitlari_yok_sayilir_ve_donemler_sirali():
    s = hazirla(rez=[(99, DT(2026, 11, 5, 9), DT(2026, 11, 5, 10)),
                     (1, DT(2026, 11, 6, 9), DT(2026, 11, 6, 10)), (1, DT(2026, 11, 5, 9), DT(2026, 11, 5, 10))])
    assert [x["baslangic"] for x in donemler(s)] == ["2026-11-05T09:00:00", "2026-11-06T09:00:00"]


# ----------------------------------------------------------------------- uyarılar
@pytest.mark.parametrize("gecerlilik, uyari, beklenen", [
    (D(2026, 11, 3), 30, "SURESI_DOLDU"), (D(2026, 11, 4), 30, "YAKLASIYOR"), (D(2026, 12, 4), 30, "YAKLASIYOR"),
    (D(2026, 12, 5), 30, None), (D(2026, 11, 4), 0, "YAKLASIYOR"), (D(2026, 11, 5), 0, None),
    (D(2026, 11, 20), None, "YAKLASIYOR")])                             # kayıtta süre yoksa 30 gün
def test_kalibrasyon_uyarisi_zil_ve_dashboard_kuraliyla_ayni(gecerlilik, uyari, beklenen):
    c = hazirla(son_kal=[(1, gecerlilik, uyari)])["cihazlar"][0]
    assert c["kalibrasyon_uyari"] == beklenen and c["kalibrasyon_gecerlilik"] == gecerlilik.isoformat()


@pytest.mark.parametrize("sonraki, uyari, beklenen", [
    (D(2026, 11, 1), 15, "GECIKTI"), (D(2026, 11, 10), 15, "YAKLASIYOR"), (D(2026, 12, 1), 15, None), (None, 15, None)])
def test_bakim_uyarisi(sonraki, uyari, beklenen):
    c = hazirla(son_bakim=[(1, sonraki, uyari)])["cihazlar"][0]
    assert c["bakim_uyari"] == beklenen and c["sonraki_bakim"] == (sonraki.isoformat() if sonraki else None)


def test_kaydi_olmayan_cihazda_uyari_alanlari_bos():
    c = hazirla()["cihazlar"][0]
    assert (c["kalibrasyon_uyari"], c["kalibrasyon_gecerlilik"], c["bakim_uyari"], c["sonraki_bakim"]) == (None,) * 4


# ----------------------------------------------------------------------- gizlilik
def test_cikti_yalnizca_izin_verilen_alanlari_icerir_kisisel_veri_yok():
    s = hazirla(rez=[(1, DT(2026, 11, 5, 9), DT(2026, 11, 5, 10))], bakim=[(1, BAS, BAS)], kal=[(1, BAS, BAS)],
                ariza=[(1, DT(2026, 11, 3, 9), None, False)], son_kal=[(1, BUGUN, 30)], son_bakim=[(1, BUGUN, 30)])
    assert set(s) == {"bugun", "baslangic", "bitis", "cihazlar"}
    assert set(s["cihazlar"][0]) == {"cihaz_id", "envanter_kodu", "cihaz_adi", "durum", "kalibrasyon_gecerlilik",
                                     "kalibrasyon_uyari", "sonraki_bakim", "bakim_uyari", "donemler"}
    assert all(set(d) == {"tur", "baslangic", "bitis", "kaynak"} for d in s["cihazlar"][0]["donemler"])


# ----------------------------------------------------------------------- uç noktası
def baglanti(satirlar=None):
    satirlar = satirlar if satirlar is not None else [[(1, "E-1", "EEG", "Kullanima_Hazir")], [], [], [], [], [], []]
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchall.side_effect = satirlar
    return conn, cursor


def cagir(**kw):
    conn, cursor = baglanti(kw.pop("satirlar", None))
    with patch("sunucu.psycopg2.connect", return_value=conn):
        return cihaz_uygunluk_getir(kullanici_id=1, **kw), cursor


def test_yedi_sorgu_calisir_ve_sonuc_doner_okuma_disinda_islem_yok():
    sonuc, cursor = cagir(baslangic=BAS, bitis=BIT)
    sorgular = [c.args[0] for c in cursor.execute.call_args_list]
    assert len(sorgular) == 7 and all(s.lstrip().upper().startswith("SELECT") for s in sorgular)
    assert sonuc["cihazlar"][0]["envanter_kodu"] == "E-1"


def test_tarih_parametreleri_sinirlari_dogru_gecer():
    _, cursor = cagir(baslangic=BAS, bitis=BIT)
    rez_parametre = cursor.execute.call_args_list[1].args[1]
    assert rez_parametre == (DT(2026, 11, 9), DT(2026, 11, 2))          # aralık sonu = bitiş günü + 1, 00:00
    assert cursor.execute.call_args_list[2].args[1] == (BIT, BAS)


def test_iptal_edilen_rezervasyon_sorguda_elenir():
    _, cursor = cagir(baslangic=BAS, bitis=BIT)
    assert "COALESCE(iptal_edildi_mi, FALSE) = FALSE" in cursor.execute.call_args_list[1].args[0]


def test_varsayilan_aralik_bugunden_yedi_gundur_tek_uc_verilince_digeri_hesaplanir():
    with patch("sunucu.date") as d:
        d.today.return_value = BUGUN
        d.side_effect = lambda *a, **k: D(*a, **k)
        sonuc, _ = cagir()
    assert (sonuc["baslangic"], sonuc["bitis"]) == ("2026-11-04", "2026-11-10")
    assert (cagir(baslangic=BAS)[0]["bitis"]) == "2026-11-08"
    assert (cagir(bitis=BIT)[0]["baslangic"]) == "2026-11-02"


@pytest.mark.parametrize("bas, bit", [(BIT, BAS), (BAS, BAS + datetime.timedelta(days=UYGUNLUK_EN_FAZLA_GUN))])
def test_gecersiz_aralik_422_ve_veritabanina_gidilmez(bas, bit):
    with patch("sunucu.psycopg2.connect") as baglan:
        with pytest.raises(HTTPException) as hata:
            cihaz_uygunluk_getir(baslangic=bas, bitis=bit, kullanici_id=1)
    assert hata.value.status_code == 422
    baglan.assert_not_called()


def test_en_genis_gecerli_aralik_kabul_edilir():
    cagir(baslangic=BAS, bitis=BAS + datetime.timedelta(days=UYGUNLUK_EN_FAZLA_GUN - 1))


def test_veritabani_hatasi_ayrinti_sizdirmaz():
    conn = MagicMock()
    conn.cursor.return_value.execute.side_effect = RuntimeError("GIZLI_SQL_AYRINTISI")
    with patch("sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            cihaz_uygunluk_getir(baslangic=BAS, bitis=BIT, kullanici_id=1)
    assert hata.value.status_code == 500 and "GIZLI" not in str(hata.value.detail)
    conn.cursor.return_value.close.assert_called()


# ----------------------------------------------------------------------- yetki
def istek(izin_var, yol="/api/cihaz-uygunluk?baslangic=2026-11-02&bitis=2026-11-08"):
    app.dependency_overrides[mevcut_kullanici_id] = lambda: 5
    conn, cursor = baglanti()
    cursor.fetchone.side_effect = [(izin_var,)]
    try:
        with patch("sunucu.psycopg2.connect", return_value=conn):
            with TestClient(app) as istemci:
                return istemci.get(yol), cursor
    finally:
        app.dependency_overrides.pop(mevcut_kullanici_id, None)


def test_izni_olmayan_rol_403_alir_ve_veriye_dokunulmaz():
    yanit, cursor = istek(0)
    assert yanit.status_code == 403
    assert cursor.fetchall.call_count == 0                              # izin kontrolünden sonra veri sorgusu yok


def test_uc_cihaz_uygunluk_goruntule_iznini_ister():
    _, cursor = istek(0)
    assert cursor.execute.call_args_list[0].args[1][1] == "CIHAZ_UYGUNLUK_GORUNTULE"


def test_izni_olan_rol_200_alir():
    yanit, _ = istek(1)
    assert yanit.status_code == 200 and yanit.json()["cihazlar"][0]["envanter_kodu"] == "E-1"


def test_tokensiz_istek_reddedilir():
    with TestClient(app) as istemci:
        assert istemci.get("/api/cihaz-uygunluk").status_code in (401, 403)


@pytest.mark.parametrize("sorgu", ["baslangic=gecersiz", "baslangic=2026-13-45", "bitis=abc"])
def test_gecersiz_tarih_bicimi_422(sorgu):
    yanit, _ = istek(1, f"/api/cihaz-uygunluk?{sorgu}")
    assert yanit.status_code == 422
