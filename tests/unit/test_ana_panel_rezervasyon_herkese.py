"""Ana panelde bugünkü cihaz rezervasyonları: cihaz özeti yetkisi olmayan ama rezervasyonları görebilen roller (proje asistanı, psikolog) de görür;
rezerve eden adı yalnızca cihazı yönetenlere / rezervasyon yapanlara gider."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication

from client.dashboard_ekrani import DashboardEkrani


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    return QApplication.instance() or QApplication([])


def _bugun(saat):
    return datetime.now().replace(hour=saat, minute=0, second=0, microsecond=0)


def test_sunucu_rezerve_eden_adini_yalniz_izinli_kullaniciya_verir():
    import server.sunucu as sunucu
    conn = MagicMock()
    imlec = conn.cursor.return_value
    imlec.fetchall.return_value = [(1, "E-1", "EEG", "ayse", "Oda 1", _bugun(10), _bugun(11), 1),
                                   (2, "E-2", "EKG", "mehmet", "Oda 2", _bugun(12), _bugun(13), 0)]
    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        liste = sunucu.dashboard_bugunku_rezervasyonlar(kullanici_id=5)
    assert [r["rezerve_eden"] for r in liste] == ["ayse", None]              # izni olana ad, olmayana null
    assert liste[0]["cihaz"] == "E-1 - EEG" and liste[0]["baslangic"] == "10:00" and liste[1]["oda"] == "Oda 2"
    assert imlec.execute.call_args.args[1] == (5,)                           # izin sorgusu çağıran kullanıcıya bağlanır
    assert "CIHAZ_REZERVASYON" in imlec.execute.call_args.args[0]


def test_sunucu_eski_sekilli_satirlarda_adi_korur():
    import server.sunucu as sunucu
    conn = MagicMock()
    conn.cursor.return_value.fetchall.return_value = [(1, "E-1", "EEG", "ayse", "Oda 1", _bugun(10), _bugun(11))]
    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        assert sunucu.dashboard_bugunku_rezervasyonlar(kullanici_id=5)[0]["rezerve_eden"] == "ayse"


def _panel(rezervasyonlar, **kw):
    def getir(yol):
        return {"/api/dashboard/bugunku-rezervasyonlar": rezervasyonlar, "/api/dashboard/ozet": {"acik_ariza_sayisi": 0}}.get(yol, [])
    with patch.object(DashboardEkrani, "_getir", side_effect=getir):
        p = DashboardEkrani("http://x", "T", **kw)
    p.zamanlayici.stop()
    return p


REZ = [{"rezervasyon_id": 1, "cihaz": "E-1 - EEG", "rezerve_eden": "ayse", "oda": "Oda 1", "baslangic": "10:00", "bitis": "11:00"},
       {"rezervasyon_id": 2, "cihaz": "E-2 - EKG", "rezerve_eden": "mehmet", "oda": "Oda 2", "baslangic": "12:00", "bitis": "13:00"}]
ISIMSIZ = [dict(r, rezerve_eden=None) for r in REZ]


def test_cihaz_ozeti_olmayan_rol_rezervasyon_panelini_gorur_ozet_kartlari_yok():
    p = _panel(REZ, cihaz_ozeti=False, rezervasyon_paneli=True)
    p.resize(1400, 900)
    p.show()
    QApplication.processEvents()
    assert p.rezervasyon_paneli and p.tablo_rez.rowCount() == 2 and "rezervasyon" not in p.kartlar and "aktif_cihaz" not in p.kartlar
    assert not p.tablo_rez.isColumnHidden(2) and p.tablo_rez.item(0, 2).text() == "ayse"
    p.close()


def test_yalniz_goruntuleyen_icin_rezerve_eden_sutunu_gizlenir():
    p = _panel(ISIMSIZ, cihaz_ozeti=False, rezervasyon_paneli=True)
    p.show()
    QApplication.processEvents()
    assert p.tablo_rez.rowCount() == 2 and p.tablo_rez.isColumnHidden(2)         # kişi adı yok: sütun görünmez
    assert p.tablo_rez.item(0, 1).text().startswith("E-1")
    p.close()


def test_rezervasyon_izni_hic_yoksa_panel_eskisi_gibi_yok():
    p = _panel(REZ, cihaz_ozeti=False)
    assert not p.rezervasyon_paneli and not hasattr(p, "tablo_rez")
    p.close()


def test_cihaz_ozetli_rol_icin_degisen_bir_sey_yok():
    p = _panel(REZ, cihaz_ozeti=True)
    assert p.rezervasyon_paneli and "rezervasyon" in p.kartlar and p.tablo_rez.rowCount() == 2 and not p.tablo_rez.isColumnHidden(2)
    p.close()


def test_gun_icinde_bos_liste_mesaj_gosterir_sutun_gizlenmez():
    p = _panel([], cihaz_ozeti=False, rezervasyon_paneli=True)
    assert p.tablo_rez.rowCount() == 0 and p.lbl_rez_bos.text().startswith("Bugün için") and not p.tablo_rez.isColumnHidden(2)
    p.close()
