"""Bakım/kalibrasyon kaydına uyarı süresi: model, kayıt, listeleme ve dashboard/bildirim kuralı.

Gerçek PostgreSQL kullanılmaz.
"""
import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from modeller import (
    BakimGuncelleModeli, BakimOlusturModeli, KalibrasyonGuncelleModeli, KalibrasyonOlusturModeli,
)
from sunucu import (
    bakim_kaydi_ekle, bakimlari_listele, kalibrasyon_kaydi_ekle, kalibrasyonlari_listele,
    yaklasan_islemler_getir,
)

D = datetime.date


def bakim(**ek):
    return BakimOlusturModeli(
        cihaz_id=1, bakim_tarihi=D(2026, 11, 1), bakim_yapan_kisi="x", yapilan_islem="y",
        bakim_baslangic_tarihi=D(2026, 11, 1), bakim_bitis_tarihi=D(2026, 11, 2), **ek)


def kalibrasyon(**ek):
    return KalibrasyonOlusturModeli(
        cihaz_id=1, kalibrasyon_yapan_kurum="k", gecerlilik_tarihi=D(2027, 11, 2), sertifika_no="s",
        kalibrasyon_baslangic_tarihi=D(2026, 11, 1), kalibrasyon_bitis_tarihi=D(2026, 11, 2), **ek)


# --------------------------------------------------------------------------- model
@pytest.mark.parametrize("model", [bakim, kalibrasyon])
def test_varsayilan_uyari_suresi_30_gundur(model):
    assert model().uyari_suresi_gun == 30


@pytest.mark.parametrize("model", [bakim, kalibrasyon])
@pytest.mark.parametrize("gun", [0, 1, 30, 365])
def test_gecerli_uyari_sureleri(model, gun):
    assert model(uyari_suresi_gun=gun).uyari_suresi_gun == gun


@pytest.mark.parametrize("model", [bakim, kalibrasyon])
@pytest.mark.parametrize("gun", [-1, 366, 10_000])
def test_gecersiz_uyari_sureleri_reddedilir(model, gun):
    with pytest.raises(ValidationError):
        model(uyari_suresi_gun=gun)


@pytest.mark.parametrize("sinif", [BakimGuncelleModeli, KalibrasyonGuncelleModeli])
def test_guncelleme_modelinde_uyari_suresi_istege_baglidir_ve_sinirlidir(sinif):
    assert sinif().model_dump(exclude_unset=True) == {}
    assert sinif(uyari_suresi_gun=14).model_dump(exclude_unset=True) == {"uyari_suresi_gun": 14}
    with pytest.raises(ValidationError):
        sinif(uyari_suresi_gun=400)


# ----------------------------------------------------------------------- kaydetme
def kayit_et(fonk, model):
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchone.return_value = (501,)
    cursor.fetchall.return_value = []
    with patch("sunucu.psycopg2.connect", return_value=conn), patch("denetim.denetim_kaydi_olustur"):
        fonk(model, 1)
    return [c for c in cursor.execute.call_args_list if c.args[0].lstrip().upper().startswith("INSERT INTO CIHAZ_")][0]


def test_bakim_kaydi_uyari_suresini_veritabanina_yazar():
    insert = kayit_et(bakim_kaydi_ekle, bakim(uyari_suresi_gun=21))
    assert "uyari_suresi_gun" in insert.args[0]
    assert insert.args[1][-1] == 21 and len(insert.args[1]) == 9


def test_kalibrasyon_kaydi_uyari_suresini_veritabanina_yazar():
    insert = kayit_et(kalibrasyon_kaydi_ekle, kalibrasyon(uyari_suresi_gun=45))
    assert "uyari_suresi_gun" in insert.args[0]
    assert insert.args[1][-1] == 45 and len(insert.args[1]) == 7


# --------------------------------------------------------------------- listeleme
def test_bakim_listesi_uyari_suresini_dondurur():
    satir = (4, "Cihaz", "E1", "kişi", "işlem", 10.0, D(2026, 11, 1), D(2027, 5, 1), D(2026, 11, 1), D(2026, 11, 2), 21)
    conn = MagicMock()
    conn.cursor.return_value.fetchall.return_value = [satir]
    with patch("sunucu.psycopg2.connect", return_value=conn):
        sonuc = bakimlari_listele(kullanici_id=1)
    assert sonuc[0]["uyari_suresi_gun"] == 21 and sonuc[0]["bakim_id"] == 4


def test_kalibrasyon_listesi_uyari_suresini_dondurur():
    satir = (7, "Cihaz", "E1", "kurum", D(2027, 11, 2), "no", datetime.datetime(2026, 11, 2, 9, 0),
             D(2026, 11, 1), D(2026, 11, 2), 45)
    conn = MagicMock()
    conn.cursor.return_value.fetchall.return_value = [satir]
    with patch("sunucu.psycopg2.connect", return_value=conn):
        sonuc = kalibrasyonlari_listele(kullanici_id=1)
    assert sonuc[0]["uyari_suresi_gun"] == 45 and sonuc[0]["kalibrasyon_id"] == 7


# ------------------------------------------------- dashboard / bildirim: yaklaşan işlemler
def yaklasanlar(bakimlar, kalibrasyonlar):
    """bakimlar/kalibrasyonlar: [(kod, ad, tarih, uyari)]"""
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchall.side_effect = [bakimlar, kalibrasyonlar]
    with patch("sunucu.psycopg2.connect", return_value=conn):
        return yaklasan_islemler_getir(kullanici_id=1)


BUGUN = D.today()


def gun(n):
    return BUGUN + datetime.timedelta(days=n)


def test_uyari_suresi_icindeki_bakim_listelenir_disindaki_listelenmez():
    sonuc = yaklasanlar([("E1", "A", gun(25), 30), ("E2", "B", gun(45), 30), ("E3", "C", gun(45), 60)], [])
    assert [(s["cihaz_adi"], s["kalan_gun"]) for s in sonuc] == [("E1 - A", 25), ("E3 - C", 45)]


def test_uyari_suresi_kayit_basina_gecerlidir_ayni_gune_farkli_sonuc():
    # İkisi de 10 gün sonra; birinin uyarısı 5 gün (henüz erken), diğerininki 15 gün (şimdi uyar).
    sonuc = yaklasanlar([("E1", "Gec", gun(10), 5), ("E2", "Erken", gun(10), 15)], [])
    assert [s["cihaz_adi"] for s in sonuc] == ["E2 - Erken"]


def test_sinir_gunleri_dahil_ve_sifir_uyari_yalniz_o_gun_listeler():
    sonuc = yaklasanlar([("E1", "Sinir", gun(30), 30), ("E2", "SifirBugun", gun(0), 0), ("E3", "SifirYarin", gun(1), 0)], [])
    assert sorted(s["cihaz_adi"] for s in sonuc) == ["E1 - Sinir", "E2 - SifirBugun"]


def test_gecmis_tarihli_kayit_listelenmez_eski_davranis_korunur():
    assert yaklasanlar([("E1", "Gecmis", gun(-3), 60)], []) == []


def test_kalibrasyon_da_ayni_kuralla_listelenir():
    sonuc = yaklasanlar([], [("E1", "Kal", gun(20), 14), ("E2", "Kal2", gun(20), 30)])
    assert [(s["cihaz_adi"], s["islem_turu"]) for s in sonuc] == [("E2 - Kal2", "Kalibrasyon")]


def test_uyari_suresi_60_olan_kayit_60_gun_kala_listelenir_61_gun_kala_listelenmez():
    sonuc = yaklasanlar([("E1", "A", gun(59), 60), ("E2", "B", gun(61), 60)], [])
    assert [s["cihaz_adi"] for s in sonuc] == ["E1 - A"]


def test_kritik_esigi_ve_siralama_degismedi():
    sonuc = yaklasanlar([("E1", "A", gun(20), 30), ("E2", "B", gun(3), 30)], [("E3", "C", gun(10), 30)])
    assert [s["cihaz_adi"] for s in sonuc] == ["E2 - B", "E3 - C", "E1 - A"]
    assert [s["durum_kodu"] for s in sonuc] == ["KRITIK", "UYARI", "UYARI"]


def test_sorgular_kayittaki_uyari_suresini_secer():
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchall.side_effect = [[], []]
    with patch("sunucu.psycopg2.connect", return_value=conn):
        yaklasan_islemler_getir(kullanici_id=1)
    sorgular = [c.args[0] for c in cursor.execute.call_args_list]
    assert "b.uyari_suresi_gun" in sorgular[0] and "k.uyari_suresi_gun" in sorgular[1]


# ---------------------------------------------------------------------- migration
def test_migration_tek_head_ve_iki_tabloya_sinirli_sutun_ekler():
    metin = Path("alembic/versions/c4e8a1b7d205_bakim_kalibrasyon_uyari_suresi.py").read_text(encoding="utf-8")
    assert "down_revision: Union[str, Sequence[str], None] = '1d62d049bc61'" in metin
    assert '"cihaz_bakimlari", "cihaz_kalibrasyonlari"' in metin
    assert 'server_default="30"' in metin and "BETWEEN 0 AND 365" in metin
    assert "def downgrade" in metin and "drop_column" in metin


# ------------------------------------------------- zil ve dashboard bildirim kutusu aynı kuralı izler
def test_zil_kayittaki_uyari_suresine_uyar_15_gun_siniri_yok():
    """Eskiden zil, uyarı süresi ne olursa olsun yalnızca son 15 günü gösteriyordu."""
    import main_window as mw
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])          # zil simgesi için Qt uygulaması gerekir

    def istek(yontem, url, **kwargs):
        yanit = MagicMock()
        yanit._tkys_oturum_reddedildi = False
        yanit.status_code = 200
        yanit.json.return_value = (
            {"acik_ariza_sayisi": 2} if url.endswith("/ozet") else
            [{"cihaz_adi": "A", "islem_turu": "Bakım", "kalan_gun": 3},
             {"cihaz_adi": "B", "islem_turu": "Kalibrasyon", "kalan_gun": 25},
             {"cihaz_adi": "C", "islem_turu": "Bakım", "kalan_gun": 58}]
        )
        return yanit

    ana = MagicMock()
    ana._oturum_kapatiliyor = False
    ana.api_url, ana.token = "http://x", "T"
    ana.nav_btnler = {"Cihaz Envanteri": object()}
    with patch.object(mw, "oturum_kontrollu_istek", side_effect=istek):
        mw.AnaPencere._bildirimleri_yenile(ana)
    metinler = [b[1] for b in ana._bildirimler]
    assert any("2 açık arıza" in m for m in metinler)                    # arıza bildirimi değişmedi
    assert any("A —" in m and "(3 gün)" in m for m in metinler)
    assert any("B —" in m and "(25 gün)" in m for m in metinler)          # 15 günden uzak ama listede
    assert any("C —" in m and "(58 gün)" in m for m in metinler)
    assert ana._bildirim_sayisi == 4                                      # 1 arıza + 3 bakım/kalibrasyon


def test_dashboard_bildirim_kutusu_listedeki_her_islemi_gosterir():
    from PySide6.QtWidgets import QApplication, QLabel
    import dashboard_ekrani
    from dashboard_ekrani import DashboardEkrani
    QApplication.instance() or QApplication([])
    islemler = [
        {"cihaz_adi": "A", "islem_turu": "Bakım", "kalan_gun": 3, "tarih": "07.11.2026"},
        {"cihaz_adi": "B", "islem_turu": "Kalibrasyon", "kalan_gun": 40, "tarih": "14.12.2026"},
    ]
    with patch.object(DashboardEkrani, "_getir", side_effect=lambda yol: {"/api/dashboard/ozet": {}}.get(yol, [])):
        pano = DashboardEkrani("http://x", "T", cihaz_ozeti=True)
    pano.zamanlayici.stop()
    pano.islemler = islemler
    pano.ozet = {"acik_ariza_sayisi": 0}
    pano._bildirimleri_olustur()
    metinler = [l.text() for l in pano.bildirim_paneli.findChildren(QLabel)]
    assert any("B  —  Kalibrasyon 40 gün içinde" in m for m in metinler)  # 15 günden uzak ama listede
    assert any("Bildirimler  (2)" in m for m in metinler)
    pano.close()
    pano.deleteLater()


def test_dashboard_yazilari_artik_sabit_60_gunden_bahsetmez():
    kaynak = Path("dashboard_ekrani.py").read_text(encoding="utf-8")
    assert "60 gün" not in kaynak
    assert "uyarı süresi" in kaynak
