"""Dashboard: 'Kalibrasyondaki cihaz' sayısı; bakım/kalibrasyon aralığındaki cihazlar etkin durumla sayılır.

Gerçek API veya PostgreSQL kullanılmaz.
"""
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication

import dashboard_ekrani
from dashboard_ekrani import DashboardEkrani
from sunucu import dashboard_ozet_getir


# ------------------------------------------------------------------ sunucu
def ozet_al(durum_sayilari, acik_ariza=3, randevu=5):
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchall.return_value = durum_sayilari
    cursor.fetchone.side_effect = [(acik_ariza,), (randevu,)]
    with patch("sunucu.psycopg2.connect", return_value=conn):
        return dashboard_ozet_getir(kullanici_id=1), cursor


def test_ozet_kalibrasyondaki_cihaz_sayisini_dondurur():
    ozet, _ = ozet_al([
        ("Kullanima_Hazir", 6), ("Bakimda", 2), ("Kalibrasyonda", 4), ("Arizali", 3), ("Kullanim_Disi", 1),
    ])
    assert ozet == {
        "toplam_cihaz": 16, "aktif_cihaz": 6, "arizali_cihaz": 3, "bakimdaki_cihaz": 2,
        "kalibrasyondaki_cihaz": 4, "acik_ariza_sayisi": 3, "bugunku_randevu_sayisi": 5,
    }


def test_kalibrasyondaki_cihaz_yoksa_sifir_doner():
    ozet, _ = ozet_al([("Kullanima_Hazir", 6)])
    assert ozet["kalibrasyondaki_cihaz"] == 0 and ozet["bakimdaki_cihaz"] == 0


def test_sorgu_bugun_planli_bakim_ve_kalibrasyondaki_cihazi_etkin_durumla_sayar():
    _, cursor = ozet_al([("Kullanima_Hazir", 1)])
    sorgu = " ".join(cursor.execute.call_args_list[0].args[0].split())
    # Öncelik: arızalı/kullanım dışı > bakımda > kalibrasyonda
    assert sorgu.index("'Arizali', 'Kullanim_Disi'") < sorgu.index("'Bakimda'") < sorgu.index("'Kalibrasyonda'")
    # Bugün bakım/kalibrasyon aralığı içinde olan cihaz (başlangıç ve bitiş günü dahil)
    assert "COALESCE(b.bakim_baslangic_tarihi, b.bakim_tarihi::date) <= CURRENT_DATE" in sorgu
    assert "COALESCE(b.bakim_bitis_tarihi, b.bakim_tarihi::date) >= CURRENT_DATE" in sorgu
    assert "k.kalibrasyon_baslangic_tarihi <= CURRENT_DATE" in sorgu
    assert "k.kalibrasyon_bitis_tarihi >= CURRENT_DATE" in sorgu


# ------------------------------------------------------------------ arayüz
@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


OZET = {
    "toplam_cihaz": 16, "aktif_cihaz": 6, "arizali_cihaz": 3, "bakimdaki_cihaz": 2,
    "kalibrasyondaki_cihaz": 4, "acik_ariza_sayisi": 3, "bugunku_randevu_sayisi": 5,
}


def getir(yol):
    return {"/api/dashboard/ozet": OZET}.get(yol, [])


@pytest.fixture
def pano(qt_app):
    with patch.object(DashboardEkrani, "_getir", side_effect=lambda self_yol: getir(self_yol)):
        p = DashboardEkrani("http://x", "T", cihaz_ozeti=True)
    p.zamanlayici.stop()
    yield p
    p.close()
    p.deleteLater()


def test_kalibrasyondaki_cihaz_karti_degeri_gosterir(pano):
    deger, alt = pano.kartlar["kalibrasyondaki_cihaz"]
    assert deger.text() == "4"
    assert "kullanılamaz" in alt.text()
    assert pano.kartlar["bakimdaki_cihaz"][0].text() == "2"
    assert pano.kartlar["aktif_cihaz"][0].text() == "6"
    assert pano.kartlar["arizali_cihaz"][0].text() == "3"


def test_cihaz_yetkisiz_rolde_kart_yoktur(qt_app):
    with patch.object(DashboardEkrani, "_getir", side_effect=lambda yol: getir(yol)):
        p = DashboardEkrani("http://x", "T", cihaz_ozeti=False)
    p.zamanlayici.stop()
    assert "kalibrasyondaki_cihaz" not in p.kartlar
    p.close()
    p.deleteLater()


def kart_konumlari(pano):
    konumlar = []
    for kart in pano.kart_widgetleri:
        i = pano.kart_grid.indexOf(kart)
        satir, sutun, _, _ = pano.kart_grid.getItemPosition(i)
        konumlar.append((satir, sutun))
    return konumlar


@pytest.mark.parametrize("genislik, beklenen_kolon", [(1000, 3), (1500, 3), (1900, 6)])
def test_kartlar_pencere_genisligine_gore_dizilir_ve_yetim_kart_kalmaz(pano, genislik, beklenen_kolon):
    assert len(pano.kart_widgetleri) == 6
    assert pano._kolon_sayisi(genislik) == beklenen_kolon
    pano._kolon = None
    pano._kartlari_diz(pano._kolon_sayisi(genislik))
    konumlar = kart_konumlari(pano)
    assert max(sutun for _, sutun in konumlar) == beklenen_kolon - 1
    assert len(set(konumlar)) == 6                        # üst üste binen kart yok
    satir_sayilari = [sum(1 for s, _ in konumlar if s == r) for r in sorted({s for s, _ in konumlar})]
    assert satir_sayilari == ([6] if beklenen_kolon == 6 else [3, 3])


def test_dashboard_ozet_yukleme_hatasinda_eski_sayilar_gizlenir(pano):
    with patch.object(
        pano, "_getir", side_effect=ConnectionError("Teknik detay")
    ):
        pano._ozet_yukle()

    for anahtar in (
        "aktif_cihaz",
        "bakimdaki_cihaz",
        "kalibrasyondaki_cihaz",
        "arizali_cihaz",
    ):
        deger, alt = pano.kartlar[anahtar]
        assert deger.text() == "?"
        assert "yüklenemedi" in alt.text().lower()


def test_dashboard_yaklasan_islemler_hatasi_bos_liste_sanilmaz(pano):
    with patch.object(
        pano, "_getir", side_effect=ConnectionError("Teknik detay")
    ):
        pano._islemleri_yukle()

    assert "yüklenemedi" in pano.lbl_islem_bos.text().lower()

    with patch.object(pano, "_getir", return_value=[]):
        pano._islemleri_yukle()

    assert "yüklenemedi" not in pano.lbl_islem_bos.text().lower()
