"""Adım 9: ana pencere düzeltmeleri (izin maskesi, Yardım düğmesi, ağ hatasında hızlı vazgeçme)."""
import os
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import requests

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from client import main_window as mw


def test_oda_etkinligi_yedek_maskesi_rol_kodlariyla_eslesir():
    gor = mw.IZIN["Oda etkinliklerini görüntüleme"][1]
    yon = mw.IZIN["Oda etkinliklerini yönetme"][1]
    beklenen_gor = {"psikolog": "E", "memur": "E", "mudur": "E", "ogrenci": "E", "asistan": "H", "admin": "E"}
    beklenen_yon = {"psikolog": "H", "memur": "E", "mudur": "E", "ogrenci": "H", "asistan": "H", "admin": "E"}
    for rol in mw.ROLLER[:6]:
        assert gor[mw.ROLLER.index(rol)] == beklenen_gor[rol], rol
        assert yon[mw.ROLLER.index(rol)] == beklenen_yon[rol], rol


def test_olu_kodlar_kaldirildi():
    kaynak = open(mw.__file__, encoding="utf-8").read()
    assert "def rolleri_getir" not in kaynak
    assert "REZERVASYON_IPTAL" not in kaynak
    assert "aktif = sum(" not in kaynak


def _ana():
    ana = SimpleNamespace(
        _oturum_kapatiliyor=False, api_url="http://x", token="t", aktif_rol="admin",
        nav_btnler={"Cihaz Envanteri": 1, "Danışma Masası Yönetimi": 1},
        btn_bildirim=MagicMock(),
        _parola_talepleri_gorebilir_mi=lambda: True,
        _sayfa_izinli_mi=lambda ad: True,
        _bekleme_metni=lambda d: "",
    )
    return ana


def test_ag_yokken_ilk_hatadan_sonra_kalan_istekler_denenmez(monkeypatch):
    cagrilar = []

    def sahte(yontem, url, **kw):
        cagrilar.append(url)
        assert kw["timeout"] == mw.AnaPencere.BILDIRIM_ISTEK_ZAMAN_ASIMI
        raise requests.ConnectionError("yok")

    monkeypatch.setattr(mw, "oturum_kontrollu_istek", sahte)
    ana = _ana()
    mw.AnaPencere._bildirimleri_yenile(ana)
    assert len(cagrilar) == 1                       # tek deneme, kalan istekler atlandı
    assert ana._bildirim_hata is True
    assert ana._bildirim_atlanan_tur == mw.AnaPencere.BILDIRIM_AG_HATASI_SONRASI_ATLANAN_TUR


def test_sunucu_hatasi_diger_bildirimleri_engellemez(monkeypatch):
    cagrilar = []

    def sahte(yontem, url, **kw):
        cagrilar.append(url)
        yanit = MagicMock(status_code=500)
        yanit.raise_for_status.side_effect = requests.HTTPError("500")
        return yanit

    monkeypatch.setattr(mw, "oturum_kontrollu_istek", sahte)
    monkeypatch.setattr(mw, "oturum_hatasi_mi", lambda y: False)
    ana = _ana()
    mw.AnaPencere._bildirimleri_yenile(ana)
    assert len(cagrilar) >= 3                       # 500 hatası ağ kopukluğu sayılmaz; hepsi denenir
    assert ana._bildirim_atlanan_tur == 0


def test_zamanlayici_ag_hatasindan_sonra_tur_atlar():
    ana = SimpleNamespace(_bildirim_atlanan_tur=2, _bildirimleri_yenile=MagicMock())
    mw.AnaPencere._bildirimleri_zamanlayicidan_yenile(ana)
    mw.AnaPencere._bildirimleri_zamanlayicidan_yenile(ana)
    assert not ana._bildirimleri_yenile.called
    mw.AnaPencere._bildirimleri_zamanlayicidan_yenile(ana)
    assert ana._bildirimleri_yenile.called


def test_yardim_dugmesi_bildirim_dugmesiyle_ayni_koyu_stili_kullanir():
    kaynak = open(mw.__file__, encoding="utf-8").read()
    assert "self.btn_yardim.setStyleSheet(self.btn_bildirim.styleSheet())" not in kaynak
    assert "self.btn_yardim.setStyleSheet(ust_buton_stili)" in kaynak
