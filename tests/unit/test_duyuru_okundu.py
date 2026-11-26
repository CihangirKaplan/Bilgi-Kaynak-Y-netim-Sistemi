"""Duyuruyu "okundu" işaretleme: kullanıcı başına gizleme (duyuru silinmez), ana panel, zil paneli ve sunucu uçları."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import inspect
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from client.bildirim_paneli import BildirimPaneli
from client.dashboard_ekrani import DashboardEkrani


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    return QApplication.instance() or QApplication([])


# ---------------------------------------------------------------- sunucu
def _baglanti(fetchone=None):
    conn = MagicMock()
    c = conn.cursor.return_value
    c.fetchone.side_effect = fetchone or []
    return conn, c


def test_okundu_isaretle_ekler_ve_cakismayi_yok_sayar():
    import server.sunucu as sunucu
    conn, c = _baglanti([(1,)])
    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        sonuc = sunucu.duyuruyu_okundu_isaretle(5, kullanici_id=9)
    sorgular = [str(x.args[0]) for x in c.execute.call_args_list]
    assert "INSERT INTO duyuru_okundu" in sorgular[-1] and "ON CONFLICT (duyuru_id, kullanici_id) DO NOTHING" in sorgular[-1]
    assert c.execute.call_args_list[-1].args[1] == (5, 9)                       # çağıranın KENDİ kimliği
    conn.commit.assert_called_once()
    assert "okundu" in sonuc["mesaj"]


def test_olmayan_duyuru_404():
    import server.sunucu as sunucu
    from fastapi import HTTPException
    conn, c = _baglanti([None])
    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            sunucu.duyuruyu_okundu_isaretle(404, kullanici_id=9)
    assert hata.value.status_code == 404
    conn.commit.assert_not_called()


def test_tekrar_goster_yalniz_cagiranin_isaretini_siler():
    import server.sunucu as sunucu
    conn, c = _baglanti()
    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        sunucu.duyuruyu_tekrar_goster(5, kullanici_id=9)
    sql, par = c.execute.call_args_list[-1].args
    assert "DELETE FROM duyuru_okundu" in sql and "kullanici_id = %s" in sql and par == (5, 9)


def test_hepsini_okundu_yalniz_yayindakileri_ve_cagirani_isaretler():
    import server.sunucu as sunucu
    conn, c = _baglanti()
    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        sunucu.duyurulari_okundu_isaretle(kullanici_id=9)
    sql, par = c.execute.call_args_list[-1].args
    assert "INSERT INTO duyuru_okundu" in sql and "son_gecerlilik_tarihi" in sql and par == (9,)


def test_uclar_yalniz_token_ister_izin_aramaz_tokensiz_401():
    import server.sunucu as sunucu
    from fastapi.testclient import TestClient
    from server import anasayfa_api                                          # uçlar server/anasayfa_api.py'ye taşındı
    for fonksiyon in (sunucu.duyuruyu_okundu_isaretle, sunucu.duyuruyu_tekrar_goster, sunucu.duyurulari_okundu_isaretle):
        assert next(u[4] for u in anasayfa_api.UCLAR if u[2] is fonksiyon) is None    # izin yok, yalnızca oturum (kimlik) bağımlılığı
    with TestClient(sunucu.app) as istemci:
        assert istemci.post("/api/duyurular/okundu").status_code == 401
        assert istemci.post("/api/duyurular/3/okundu").status_code == 401
        assert istemci.delete("/api/duyurular/3/okundu").status_code == 401


# ---------------------------------------------------------------- ana panel
def _d(no, baslik, okundu, **ek):
    return {"duyuru_id": no, "baslik": baslik, "metin": f"{baslik} metni", "tarih": "01.01.2026 09:00", "son_gecerlilik": None,
            "yazan": None, "yeni": not okundu, "yonetebilir": False, "okundu": okundu, **ek}


def _panel(duyurular, **kw):
    def getir(self, yol):
        return duyurular if yol == "/api/duyurular" else ({"acik_ariza_sayisi": 0} if yol.endswith("/ozet") else [])
    with patch.object(DashboardEkrani, "_getir", getir):
        p = DashboardEkrani("http://x", "T", cihaz_ozeti=False, **kw)
    p.zamanlayici.stop()
    return p


def _metin(kutu):
    return [w.text() for w in kutu.findChildren(QLabel) + kutu.findChildren(QPushButton)]


def _dugme(kutu, ad):
    return kutu.findChild(QPushButton, ad)


def test_okunmamislar_gorunur_okunanlar_gizli_ama_silinmez():
    p = _panel([_d(1, "Bakım", False), _d(2, "Eski duyuru", True)])
    metin = " | ".join(_metin(p.panel_duyuru))
    assert "Bakım" in metin and "Eski duyuru" not in metin                              # okunan gizli
    assert "Okunan duyurular (1)" in metin and "(1 yeni)" in metin and "Okudum" in metin
    p.close()


def test_okunanlar_dugmesiyle_acilir_tekrar_goster_dugmesi_vardir():
    p = _panel([_d(1, "Bakım", False), _d(2, "Eski duyuru", True)])
    _dugme(p.panel_duyuru, "okunanlariGosterDugmesi").click()
    metin = " | ".join(_metin(p.panel_duyuru))
    assert "Eski duyuru" in metin and "Tekrar göster" in metin
    _dugme(p.panel_duyuru, "okunanlariGosterDugmesi").click()                          # tekrar kapanır
    assert "Eski duyuru" not in " | ".join(_metin(p.panel_duyuru))
    p.close()


def test_hepsi_okunduysa_bilgi_satiri_ve_okunanlar_bolumu():
    p = _panel([_d(1, "A", True), _d(2, "B", True)])
    metin = " | ".join(_metin(p.panel_duyuru))
    assert "Tüm duyuruları okudunuz" in metin and "Okunan duyurular (2)" in metin and "Okudum" not in metin.replace("Hepsini okudum", "")
    assert not p.panel_duyuru.isHidden()                                                # okunanları geri getirebilsin diye panel görünür
    p.close()


def test_hepsini_okudum_dugmesi_yalniz_birden_fazla_okunmamista():
    assert _dugme(_panel([_d(1, "A", False)]).panel_duyuru, "hepsiniOkuduDugmesi") is None
    assert _dugme(_panel([_d(1, "A", False), _d(2, "B", False)]).panel_duyuru, "hepsiniOkuduDugmesi") is not None


def test_eski_sunucuda_okundu_alani_yoksa_dugme_gosterilmez_duyuru_gorunur():
    eski = {k: v for k, v in _d(1, "Bakım", False).items() if k != "okundu"}
    p = _panel([eski])
    metin = " | ".join(_metin(p.panel_duyuru))
    assert "Bakım" in metin and "Okudum" not in metin and "Okunan duyurular" not in metin
    p.close()


def _istek_taklidi(durum=200):
    cagrilar = []

    def istek(yontem, url, **kw):
        cagrilar.append((yontem, url))
        yanit = MagicMock(status_code=durum)
        yanit.raise_for_status.side_effect = None if durum < 400 else RuntimeError("hata")
        return yanit
    istek.cagrilar = cagrilar
    return istek


def test_okudum_dugmesi_sunucuya_gonderir_listeyi_yeniler_ve_zili_haberdar_eder():
    p = _panel([_d(7, "Bakım", False)])
    sinyal = MagicMock()
    p.duyuru_degisti.connect(sinyal)
    istek = _istek_taklidi()
    yenilenen = []
    with patch("client.dashboard_ekrani.oturum_kontrollu_istek", istek), patch("client.dashboard_ekrani.oturum_hatasi_mi", return_value=False), \
            patch.object(p, "_duyurulari_yukle", lambda: yenilenen.append(1)):
        _dugme(p.panel_duyuru, "okunduDugmesi").click()
    assert istek.cagrilar == [("POST", "http://x/api/duyurular/7/okundu")]
    assert yenilenen == [1] and sinyal.call_count == 1
    p.close()


def test_tekrar_goster_ve_hepsini_okudum_dogru_istegi_gonderir():
    p = _panel([_d(1, "A", False), _d(2, "B", False), _d(3, "C", True)])
    istek = _istek_taklidi()
    with patch("client.dashboard_ekrani.oturum_kontrollu_istek", istek), patch("client.dashboard_ekrani.oturum_hatasi_mi", return_value=False), \
            patch.object(p, "_duyurulari_yukle", lambda: None):
        _dugme(p.panel_duyuru, "hepsiniOkuduDugmesi").click()
        _dugme(p.panel_duyuru, "okunanlariGosterDugmesi").click()
        _dugme(p.panel_duyuru, "tekrarGosterDugmesi").click()
    assert istek.cagrilar == [("POST", "http://x/api/duyurular/okundu"), ("DELETE", "http://x/api/duyurular/3/okundu")]
    p.close()


def test_istek_basarisizsa_uyari_gosterilir_ve_zil_degismez():
    p = _panel([_d(7, "Bakım", False)])
    sinyal = MagicMock()
    p.duyuru_degisti.connect(sinyal)
    with patch("client.dashboard_ekrani.oturum_kontrollu_istek", _istek_taklidi(500)), patch("client.dashboard_ekrani.oturum_hatasi_mi", return_value=False), \
            patch("client.dashboard_ekrani.QMessageBox.warning") as uyari:
        _dugme(p.panel_duyuru, "okunduDugmesi").click()
    assert uyari.call_count == 1 and sinyal.call_count == 0
    p.close()


def test_ana_panel_kodunda_lambda_baglantisi_yok():
    import client.dashboard_ekrani as d
    assert "connect(lambda" not in inspect.getsource(d)


# ---------------------------------------------------------------- zil paneli
def _zil(bildirimler, okundu=None):
    return BildirimPaneli(bildirimler=bildirimler, toplam=len(bildirimler), hata=False, sayfa_ac=lambda _: None, duyuru_okundu=okundu)


def test_zilde_duyuru_satirinda_okudum_dugmesi_var_diger_gruplarda_yok():
    panel = _zil([("Duyurular", "Bakım", "Ana Kontrol Paneli", {"duyuru_id": 4}), ("Günlük", "Randevunuz: bugün 1", "Ana Kontrol Paneli")],
                 okundu=lambda _id: True)
    dugmeler = panel.findChildren(QPushButton, "duyuruOkunduDugmesi")
    assert len(dugmeler) == 1 and dugmeler[0].property("duyuru_id") == 4
    panel.close()


def test_zilde_okudum_satiri_kaldirir_sayaci_azaltir_ve_kimligi_iletir():
    alinan = []
    panel = _zil([("Duyurular", "A", "Ana Kontrol Paneli", {"duyuru_id": 4}), ("Duyurular", "B", "Ana Kontrol Paneli", {"duyuru_id": 5})],
                 okundu=lambda kimlik: alinan.append(kimlik) or True)
    assert "Bildirimler (2)" in [e.text() for e in panel.findChildren(QLabel)]
    panel.findChildren(QPushButton, "duyuruOkunduDugmesi")[0].click()
    assert alinan == [4]
    etiketler = [e.text() for e in panel.findChildren(QLabel)]
    assert "Bildirimler (1)" in etiketler and "1 bildirim işlem bekliyor" in etiketler
    panel.close()


def test_zilde_okundu_basarisizsa_satir_ve_sayac_kalir():
    panel = _zil([("Duyurular", "A", "Ana Kontrol Paneli", {"duyuru_id": 4})], okundu=lambda _id: False)
    panel.findChildren(QPushButton, "duyuruOkunduDugmesi")[0].click()
    assert "Bildirimler (1)" in [e.text() for e in panel.findChildren(QLabel)] and len(panel.findChildren(QPushButton, "duyuruOkunduDugmesi")) == 1
    panel.close()


def test_zil_geri_uyumlu_uc_ogeli_satirlar_eskisi_gibi():
    panel = _zil([("Cihaz Uyarıları", "Arıza", "Arıza Kayıtları")])
    assert panel.findChildren(QPushButton, "duyuruOkunduDugmesi") == []
    panel.close()


def test_ana_pencere_zili_yalniz_okunmamis_duyurulari_getirir_ve_okundu_islevini_baglar():
    import client.main_window as mw
    kaynak = inspect.getsource(mw.AnaPencere._bildirimleri_yenile)
    assert 'd.get("okundu") is False' in kaynak and '{"duyuru_id": duyuru.get("duyuru_id")}' in kaynak
    assert "duyuru_okundu=self._duyuruyu_okundu_isaretle" in inspect.getsource(mw.AnaPencere._bildirim_menusunu_ac)
    assert "istatistik_paneli.duyuru_degisti.connect(self._bildirimleri_yenile)" in inspect.getsource(mw.AnaPencere.sayfa_dashboard)
