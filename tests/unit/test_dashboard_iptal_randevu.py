"""Ana panel: iptal edilen randevular gösterilmez ve sayılmaz (liste, bugünkü randevu kartı)."""
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication

from client.dashboard_ekrani import DashboardEkrani
from server.anasayfa_api import dashboard_bugunku_randevular, dashboard_ozet_getir


def _randevu(no, durum, saat="09:00"):
    return {"tarih": "27.11", "randevu_id": no, "danisan_kod_id": f"D{no}", "psikolog": "psikolog1", "oda": "Oda 1",
            "baslangic": saat, "bitis": "10:00", "durum": durum}


# ------------------------------------------------------------------ sunucu
def _sorgular(islev, **kwargs):
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchall.return_value = []
    cursor.fetchone.return_value = (0,)
    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        islev(kullanici_id=1, **kwargs)
    return [" ".join(c.args[0].split()) for c in cursor.execute.call_args_list]


def test_bugunku_randevu_listesi_iptal_edilenleri_getirmez():
    sorgu = next(s for s in _sorgular(dashboard_bugunku_randevular, aralik="bugun") if "FROM randevular" in s)
    assert "r.durum <> 'IPTAL_EDILDI'" in sorgu


@pytest.mark.parametrize("aralik", ["bugun", "yarin", "hafta"])
def test_her_aralikta_iptal_edilenler_listeye_girmez(aralik):
    sorgu = next(s for s in _sorgular(dashboard_bugunku_randevular, aralik=aralik) if "FROM randevular" in s)
    assert "r.durum <> 'IPTAL_EDILDI'" in sorgu


def test_ozetteki_bugunku_randevu_sayisi_iptal_edilenleri_saymaz():
    sorgu = next(s for s in _sorgular(dashboard_ozet_getir) if "FROM randevular" in s)
    assert "durum <> 'IPTAL_EDILDI'" in sorgu


# ------------------------------------------------------------------ arayüz
@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def _pano(qt_app, randevular):
    def getir(self_yol):
        return randevular if "bugunku-randevular" in self_yol else []
    with patch.object(DashboardEkrani, "_getir", side_effect=getir):
        pano = DashboardEkrani("http://x", "T", cihaz_ozeti=False)
    pano.zamanlayici.stop()
    return pano


def test_iptal_edilen_randevu_tabloda_gorunmez_ve_kartta_sayilmaz(qt_app):
    pano = _pano(qt_app, [_randevu(1, "PLANLANDI", "09:00"), _randevu(2, "IPTAL_EDILDI", "10:00"), _randevu(3, "TAMAMLANDI", "11:00")])
    t = pano.tablo_randevu
    kodlar = [t.item(s, 1).text() for s in range(t.rowCount()) if t.item(s, 1) is not None]
    assert kodlar == ["D1", "D3"]
    assert pano.kartlar["randevu"][0].text() == "2"
    pano.close(); pano.deleteLater()


def test_yalnizca_iptal_varsa_bos_durum_gosterilir_sayi_sifir(qt_app):
    pano = _pano(qt_app, [_randevu(1, "IPTAL_EDILDI")])
    assert pano.kartlar["randevu"][0].text() == "0"
    assert pano.tablo_randevu.isHidden() or pano.tablo_randevu.rowCount() == 0 or not pano.lbl_randevu_bos.isHidden()
    pano.close(); pano.deleteLater()
