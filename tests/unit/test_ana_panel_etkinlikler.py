"""Ana panelde bugünkü oda etkinlikleri: oda etkinliklerini görebilen roller görür; kişi adı verilmez."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import inspect
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication

from client.dashboard_ekrani import DashboardEkrani


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    return QApplication.instance() or QApplication([])


def _bugun(saat, dakika=0):
    return datetime.now().replace(hour=saat, minute=dakika, second=0, microsecond=0)


def test_sunucu_bugunku_etkinlikleri_ad_oda_saat_ve_katilimciyla_dondurur():
    import server.sunucu as sunucu
    conn = MagicMock()
    imlec = conn.cursor.return_value
    imlec.fetchall.return_value = [(1, "Aile Eğitimi", "Toplantı Odası", _bugun(10), _bugun(12), 15),
                                   (2, "Seminer", "Oda 2", _bugun(18), _bugun(19), None)]
    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        liste = sunucu.dashboard_bugunku_etkinlikler(kullanici_id=5)
    assert liste == [
        {"tarih": _bugun(10).strftime("%d.%m"), "etkinlik_id": 1, "etkinlik": "Aile Eğitimi", "oda": "Toplantı Odası", "baslangic": "10:00", "bitis": "12:00", "katilimci": 15},
        {"tarih": _bugun(18).strftime("%d.%m"), "etkinlik_id": 2, "etkinlik": "Seminer", "oda": "Oda 2", "baslangic": "18:00", "bitis": "19:00", "katilimci": None},
    ]
    sorgu = imlec.execute.call_args.args[0]
    assert "iptal_edildi_mi" in sorgu and "oda_etkinlik_gunleri" in sorgu                      # iptal edilenler gelmez; çok günlü etkinliğin günü
    assert "kullanici_adi" not in sorgu and "organize_eden" not in sorgu                       # kişi adı verilmez


def test_sunucu_gece_yarisinda_biten_gun_24_00_gosterilir():
    import server.sunucu as sunucu
    conn = MagicMock()
    baslangic = _bugun(22)
    conn.cursor.return_value.fetchall.return_value = [(1, "Gece Etkinliği", "Oda 1", baslangic, (baslangic + timedelta(days=1)).replace(hour=0), 5)]
    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        assert sunucu.dashboard_bugunku_etkinlikler(kullanici_id=5)[0]["bitis"] == "24:00"


def test_sunucu_uc_noktasi_giris_yapmis_herkese_aciktir_tokensiz_401():
    """Ana paneldeki salt okunur bilgi: ayrı görüntüleme izni aramaz (Proje Asistanı'nın Oda Etkinlikleri sayfası yoktur ama görür); token yine şart."""
    import server.sunucu as sunucu
    from fastapi.testclient import TestClient
    from server import anasayfa_api                                          # uç server/anasayfa_api.py'ye taşındı
    assert next(u[4] for u in anasayfa_api.UCLAR if u[2] is sunucu.dashboard_bugunku_etkinlikler) is None   # izin yok, yalnızca oturum (kimlik) bağımlılığı
    conn = MagicMock()
    conn.cursor.return_value.fetchall.return_value = [(1, "Seminer", "Oda 2", _bugun(18), _bugun(19), None)]
    sunucu.app.dependency_overrides[sunucu.mevcut_kullanici_id] = lambda: 9                  # hiçbir izni olmayan, giriş yapmış kullanıcı
    try:
        with patch("server.sunucu.psycopg2.connect", return_value=conn), TestClient(sunucu.app) as istemci:
            assert istemci.get("/api/dashboard/bugunku-etkinlikler").status_code == 200
    finally:
        sunucu.app.dependency_overrides.pop(sunucu.mevcut_kullanici_id, None)
    with TestClient(sunucu.app) as istemci:
        assert istemci.get("/api/dashboard/bugunku-etkinlikler").status_code == 401           # token olmadan yok


ETKINLIKLER = [{"etkinlik_id": 1, "etkinlik": "Aile Eğitimi", "oda": "Toplantı Odası", "baslangic": "10:00", "bitis": "12:00", "katilimci": 15},
               {"etkinlik_id": 2, "etkinlik": "Seminer", "oda": "Oda 2", "baslangic": "18:00", "bitis": "19:00", "katilimci": None}]


def _panel(etkinlikler=ETKINLIKLER, hata=False, **kw):
    def getir(yol):
        if yol == "/api/dashboard/bugunku-etkinlikler":
            if hata:
                raise RuntimeError("sunucu yok")
            return etkinlikler
        return {"/api/dashboard/ozet": {"acik_ariza_sayisi": 0}}.get(yol, [])
    with patch.object(DashboardEkrani, "_getir", side_effect=getir):
        p = DashboardEkrani("http://x", "T", **kw)
    p.zamanlayici.stop()
    return p


def test_cihaz_ozeti_olmayan_rol_etkinlik_panelini_gorur():
    p = _panel(cihaz_ozeti=False, etkinlik_paneli=True)
    p.resize(1400, 900)
    p.show()
    QApplication.processEvents()
    t = p.tablo_etkinlik
    assert t.rowCount() == 2 and "rezervasyon" not in p.kartlar
    assert [t.item(0, c).text() for c in range(4)] == ["10:00 – 12:00", "Aile Eğitimi", "Toplantı Odası", "15"]
    assert t.item(1, 3).text() == "—"                                                # katılımcı sayısı girilmemiş
    p.close()


def test_etkinlik_izni_yoksa_panel_yok():
    p = _panel(cihaz_ozeti=False)
    assert not p.etkinlik_paneli and not hasattr(p, "tablo_etkinlik")
    p.close()


def test_bos_liste_mesaj_gosterir_ve_yukleme_hatasi_anlasilir_mesaj_verir():
    p = _panel(etkinlikler=[], cihaz_ozeti=False, etkinlik_paneli=True)
    assert p.tablo_etkinlik.rowCount() == 0 and p.lbl_etkinlik_bos.text() == "Bugün için oda etkinliği bulunmuyor."
    p.close()
    p = _panel(hata=True, cihaz_ozeti=False, etkinlik_paneli=True)
    assert p.lbl_etkinlik_bos.text() == "Etkinlikler yüklenemedi." and p.tablo_etkinlik.rowCount() == 0
    p.close()


def test_cihaz_ozetli_rol_hem_rezervasyon_hem_etkinlik_panelini_gorur_ve_gun_degisimi_etiketi_yenilenir():
    p = _panel(cihaz_ozeti=True, etkinlik_paneli=True)
    assert p.rezervasyon_paneli and p.etkinlik_paneli and p.tablo_etkinlik.rowCount() == 2
    assert any(panel is p.panel_etkinlik for panel, _ in p.tarih_panelleri)            # her dakikalık yenilemede tarih rozeti güncellenir
    p.close()


def test_ana_pencere_etkinlik_panelini_her_role_acar():
    import client.main_window as mw
    kaynak = inspect.getsource(mw.AnaPencere.sayfa_dashboard)
    assert "etkinlik_paneli=True" in kaynak and 'izin_var(rol, "Oda etkinliklerini görüntüleme")' not in kaynak        # izne bağlı değil: herkes görür
