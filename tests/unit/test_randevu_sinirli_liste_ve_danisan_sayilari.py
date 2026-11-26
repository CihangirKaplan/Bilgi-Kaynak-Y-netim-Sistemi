"""Randevu listesi sınırı ve Danışanlar ekranının hafif randevu özeti.

Sorun: Danışanlar ekranı tüm randevu geçmişini tek istekte çekiyordu (10 yıllık veride 47 MB, 5 sn zaman aşımı; iki kullanıcı açınca sunucu donuyordu).
Çözüm: süzgeçsiz /api/randevular en yeni 5000 kayıtla sınırlı; ekran danışan başına sayıyı hafif uçtan, geçmişi ise seçilen danışan için ister."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import inspect
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication

import client.danisanlar_ekrani as modul
from client.danisanlar_ekrani import DanisanlarEkrani


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    return QApplication.instance() or QApplication([])


# ------------------------------------------------------------------ sunucu
def _liste(cursor_sonuclari, **kwargs):
    import server.sunucu as sunucu
    conn = MagicMock()
    c = conn.cursor.return_value
    c.fetchone.side_effect = cursor_sonuclari
    c.fetchall.return_value = kwargs.pop("satirlar", [])
    yanit = MagicMock(headers={})
    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        sonuc = sunucu.randevulari_listele(response=yanit, kullanici_id=1, **kwargs)
    return sonuc, c, yanit


def test_suzgecsiz_liste_en_yeni_sinirli_kayit_ister_ve_artan_dondurur():
    import server.sunucu as sunucu
    simdi = datetime.now()
    satirlar = [(3, "K-3", 1, 1, simdi, simdi, "PLANLANDI", simdi), (2, "K-2", 1, 1, simdi, simdi, "PLANLANDI", simdi)]   # en yeniden başlar
    sonuc, c, yanit = _liste([("ADMIN",), (1,), (99999,)], satirlar=satirlar)
    sorgular = [str(x.args[0]) for x in c.execute.call_args_list]
    asil = next(s for s in sorgular if "ORDER BY" in s)
    assert "DESC" in asil and "LIMIT" in asil
    assert c.execute.call_args_list[-1].args[1][-2:] == (sunucu.RANDEVU_LISTE_ENCOK, 0)
    assert [r["randevu_id"] for r in sonuc] == [2, 3]                      # eski davranış gibi artan sıra
    assert yanit.headers["X-Toplam-Kayit"] == "99999"                      # kesilmişse gerçek toplam bildirilir


@pytest.mark.parametrize("suzgec", [{"danisan_kod_id": "K-1"}, {"durum": "PLANLANDI"}, {"oda_id": 2}])
def test_suzgecli_liste_eskisi_gibi_sinirsiz_ve_artan(suzgec):
    sonuc, c, yanit = _liste([("ADMIN",), (1,)], **suzgec)
    sorgular = " ".join(str(x.args[0]) for x in c.execute.call_args_list)
    assert "LIMIT" not in sorgular and "ORDER BY r.baslangic_zamani;" in sorgular
    assert "X-Toplam-Kayit" not in yanit.headers


def test_istemci_limit_verirse_kendi_limiti_gecerli():
    sonuc, c, yanit = _liste([("ADMIN",), (1,), (7,)], limit=50)
    assert c.execute.call_args_list[-1].args[1][-2:] == (50, 0) and yanit.headers["X-Toplam-Kayit"] == "7"


def test_danisan_randevu_sayilari_uc_noktasi_gruplayarak_sayar():
    import server.sunucu as sunucu
    conn = MagicMock()
    c = conn.cursor.return_value
    c.fetchone.return_value = ("ADMIN",)
    c.fetchall.return_value = [("K-1", 12), ("K-2", 3)]
    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        assert sunucu.danisan_randevu_sayilari(kullanici_id=1) == {"K-1": 12, "K-2": 3}
    assert "GROUP BY" in str(c.execute.call_args_list[-1].args[0]) and "p.kullanici_id" not in str(c.execute.call_args_list[-1].args[0])


def test_danisan_randevu_sayilari_psikolog_yalniz_kendi_randevularini_sayar():
    import server.sunucu as sunucu
    conn = MagicMock()
    c = conn.cursor.return_value
    c.fetchone.return_value = ("PSIKOLOG",)
    c.fetchall.return_value = [("K-1", 4)]
    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        assert sunucu.danisan_randevu_sayilari(kullanici_id=7) == {"K-1": 4}
    son = c.execute.call_args_list[-1]
    assert "p.kullanici_id = %s" in son.args[0] and son.args[1] == (7,)


def test_danisan_randevu_sayilari_izinli(monkeypatch):
    import server.sunucu as sunucu
    from server import randevu_api                               # uç server/randevu_api.py'ye taşındı (izin UCLAR tablosunda)
    assert next(u[4] for u in randevu_api.UCLAR if u[2] is sunucu.danisan_randevu_sayilari) == "TAKVIM_GORUNTULE"


# ------------------------------------------------------------------ istemci
class Cevap:
    def __init__(self, veri, durum=200):
        self._v, self.status_code = veri, durum
        self.headers = {}

    def json(self):
        return self._v

    def raise_for_status(self):
        pass


def _sunucu(sayilar=None, randevular_ucu=None, eski=False):
    istekler = []

    def cagri(yontem, url, **kw):
        istekler.append((url, kw.get("params") or {}))
        if url.endswith("/api/danisan-kodlari"):
            return Cevap([{"danisan_kod_id": "K-1", "ucretli_mi": True, "aktif_mi": True, "olusturan_psikolog_id": 3, "yas_grubu": "YETISKIN"},
                          {"danisan_kod_id": "K-2", "ucretli_mi": True, "aktif_mi": True, "olusturan_psikolog_id": 3, "yas_grubu": "YETISKIN"}])
        if url.endswith("/api/danisan-randevu-sayilari"):
            return Cevap({}, 404) if eski else Cevap(sayilar or {})
        if url.endswith("/api/randevular"):
            return Cevap(randevular_ucu(kw.get("params") or {}))
        return Cevap([])
    cagri.istekler = istekler
    return cagri


def _ekran(sunucu):
    with patch.object(modul, "oturum_kontrollu_istek", side_effect=sunucu):
        e = DanisanlarEkrani("http://x", "T", mevcut_psikolog_id=None)
        e.verileri_cek()
    return e


def _randevu(no, kod):
    simdi = datetime.now()
    return {"randevu_id": no, "danisan_kod_id": kod, "psikolog_id": 3, "oda_id": 1, "baslangic_zamani": simdi.isoformat(),
            "bitis_zamani": simdi.isoformat(), "durum": "PLANLANDI"}


def test_yeni_sunucuda_tum_gecmis_cekilmez_yalniz_sayilar_gelir():
    s = _sunucu(sayilar={"K-1": 5, "K-2": 1}, randevular_ucu=lambda p: [_randevu(1, "K-1")])
    e = _ekran(s)
    assert [u for u, _ in s.istekler if u.endswith("/api/randevular")] == []               # açılışta randevu geçmişi istenmedi
    assert e.randevu_sayilari == {"K-1": 5, "K-2": 1}
    assert e.tablo.item(0, 4).text() == "5" or "5" in [e.tablo.item(0, c).text() for c in range(e.tablo.columnCount())]


def test_danisan_secilince_yalniz_o_danisanin_gecmisi_istenir_ve_onbellege_alinir():
    s = _sunucu(sayilar={"K-1": 2, "K-2": 1}, randevular_ucu=lambda p: [_randevu(1, p["danisan_kod_id"]), _randevu(2, p["danisan_kod_id"])])
    e = _ekran(s)
    with patch.object(modul, "oturum_kontrollu_istek", side_effect=s):
        liste = e._danisan_randevulari("K-1")
        e._danisan_randevulari("K-1")                                                          # ikinci kez sunucuya gitmez
    istekler = [(u, p) for u, p in s.istekler if u.endswith("/api/randevular")]
    assert len(istekler) == 1 and istekler[0][1] == {"danisan_kod_id": "K-1"}
    assert len(liste) == 2


def test_gecmis_yuklenemezse_bos_doner_ve_onbellege_yazilmaz():
    s = _sunucu(sayilar={"K-1": 2}, randevular_ucu=lambda p: [])
    e = _ekran(s)
    with patch.object(e, "_api_liste_getir", return_value=None):
        assert e._danisan_randevulari("K-1") == []
    assert "K-1" not in e.randevu_gruplari                                                     # sonraki seçimde yeniden denenir


def test_eski_sunucuda_onceki_davranisa_donulur():
    s = _sunucu(eski=True, randevular_ucu=lambda p: [_randevu(1, "K-1"), _randevu(2, "K-1"), _randevu(3, "K-2")])
    e = _ekran(s)
    assert e.randevu_sayilari == {"K-1": 2, "K-2": 1} and not e._randevular_tek_tek
    assert len(e._danisan_randevulari("K-1")) == 2


def test_ekran_artik_tum_gecmisi_sayarak_degil_ozetle_sayar():
    kaynak = inspect.getsource(DanisanlarEkrani)
    assert "len(self.randevu_gruplari" not in kaynak and "len(v) for k, v in self.randevu_gruplari.items()}\n" not in kaynak.split("def tabloyu_guncelle")[1].split("def _secim_degisti")[0]
