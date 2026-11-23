"""Danışma Masası Yönetimi son kontrol düzeltmeleri.

- Kart sayıları ve liste: sayılar tüm kayıtlardan gelir, liste kısaltıldığında not gösterilir.
- Otomatik yenileme kullanıcının seçtiği sıralamayı ve seçili görevi korur.
- Onay geri alma (yalnızca DANISMA_OTURUMU_YONETIM izniyle) ve düğme durumları.
- Boş liste mesajı; Öğrenci sütunu genişliği.
"""
import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHeaderView, QTableWidget, QTableWidgetItem

import client.danisma_masasi_yonetimi as modul
from client.tablo_siralama import siralama_durumunu_al, siralamayi_geri_yukle, siralanabilir_yap
from server.sunucu import app, mevcut_kullanici_id


# ------------------------------------------------------------------ sunucu: yetki
@pytest.fixture
def giris_yapmis_kullanici():
    app.dependency_overrides[mevcut_kullanici_id] = lambda: 5
    yield
    app.dependency_overrides.pop(mevcut_kullanici_id, None)


def test_onay_geri_alma_yalniz_yonetim_izniyle_yapilir(giris_yapmis_kullanici):
    conn = MagicMock()
    cursor = conn.cursor.return_value
    sorulan = []

    def calistir(sql, params=None):
        if "izin_adi" in sql:
            sorulan.append(params[1])
            cursor.fetchone.return_value = (1,) if params[1] == "DANISMA_OTURUMU_GORUNTULE" else None

    cursor.execute.side_effect = calistir
    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        with TestClient(app) as istemci:
            yanit = istemci.patch("/api/danisma/yonetim/oturumlar/3/onay-geri-al")
    assert yanit.status_code == 403 and sorulan == ["DANISMA_OTURUMU_YONETIM"]
    assert not any(c.args[0].lstrip().upper().startswith("UPDATE") for c in cursor.execute.call_args_list)
    conn.commit.assert_not_called()


# ------------------------------------------------------------------ sıralama durumu
def test_siralama_yeniden_doldurulunca_geri_yuklenir(tkys_qapplication):
    tablo = QTableWidget(0, 2)
    tablo.setHorizontalHeaderLabels(["Ad", "Sayı"])
    siralanabilir_yap(tablo)

    def doldur(adlar):
        tablo.setRowCount(0)
        tablo.setRowCount(len(adlar))
        for no, ad in enumerate(adlar):
            tablo.setItem(no, 0, QTableWidgetItem(ad))
            tablo.setItem(no, 1, QTableWidgetItem(str(no)))

    doldur(["Can", "Ali", "Zeynep", "Bora"])
    tablo._tiklandi_siralama(0)                                     # Ad, artan
    tablo._tiklandi_siralama(0)                                     # Ad, azalan
    durum = siralama_durumunu_al(tablo)
    assert durum == (0, Qt.DescendingOrder)
    doldur(["Can", "Ali", "Zeynep", "Bora"])                        # otomatik yenileme: sıra sunucu sırasına döner
    assert siralama_durumunu_al(tablo) is None and tablo.item(0, 0).text() == "Can"
    siralamayi_geri_yukle(tablo, durum)
    assert [tablo.item(s, 0).text() for s in range(4)] == ["Zeynep", "Can", "Bora", "Ali"]
    assert siralama_durumunu_al(tablo) == (0, Qt.DescendingOrder)
    assert siralama_durumunu_al(QTableWidget(0, 1)) is None         # sıralanabilir yapılmamış tablo


# ------------------------------------------------------------------ istemci ekranı
def _yanit(veri, kod=200):
    m = MagicMock()
    m.status_code = kod
    m.json.return_value = veri
    m.text = json.dumps(veri)
    m.headers = {}
    m._tkys_oturum_reddedildi = False
    m.raise_for_status = lambda: None
    return m


def _oturum(no, ad, onayli=False, bitti=True, saat=0):
    bas = datetime(2026, 11, 20, 8, 0) + timedelta(hours=saat)
    bit = bas + timedelta(minutes=30)
    return {
        "oturum_id": no, "ogrenci_id": 1, "ad_soyad": ad, "ogrenci_numarasi": "D1", "baslangic_zamani": bas.isoformat(),
        "bitis_zamani": bit.isoformat() if bitti else None, "toplam_saniye": 1800, "durum": "TAMAMLANDI" if bitti else "AKTIF",
        "onaylandi_mi": onayli, "uzun_gorev": False,
    }


def _ekran(tkys_qapplication, veri, istekler=None):
    def istek(method, url, **kw):
        if istekler is not None:
            istekler.append((method, url))
        return _yanit(veri["v"] if method == "GET" else {"durum": "basarili"})
    with patch.object(modul, "oturum_kontrollu_istek", side_effect=istek):
        ekran = modul.DanismaMasasiYonetimi("http://x", "t")
    ekran.yenile_timer.stop()
    return ekran, istek


def _satirlar(ekran):
    return [ekran.tablo.item(s, 0).text() for s in range(ekran.tablo.rowCount())]


def test_kartlar_sunucunun_ozetinden_gelir_ve_kisaltma_notu_gosterilir(tkys_qapplication):
    veri = {"v": {
        "toplam_kayit": 514, "kisaltildi": True, "ozet": {"toplam": 514, "aktif": 1, "bekleyen": 9, "onaylanan": 504},
        "oturumlar": [_oturum(1, "Ayşe"), _oturum(2, "Bora", onayli=True)],
    }}
    ekran, _ = _ekran(tkys_qapplication, veri)
    assert [ekran.ozet_kartlari[k].text() for k in ("toplam", "aktif", "bekleyen", "onaylanan")] == ["514", "1", "9", "504"]
    assert not ekran.ozet.isHidden() and "514" in ekran.ozet.text()
    veri["v"] = {"toplam_kayit": 2, "kisaltildi": False, "ozet": {"toplam": 2, "aktif": 0, "bekleyen": 1, "onaylanan": 1},
                 "oturumlar": [_oturum(1, "Ayşe"), _oturum(2, "Bora", onayli=True)]}
    with patch.object(modul, "oturum_kontrollu_istek", return_value=_yanit(veri["v"])):
        ekran.yenile()
    assert ekran.ozet.isHidden()                                     # sayılar zaten kartlarda; tekrar eden yazı yok


def test_bos_liste_aciklayici_mesaj_gosterir(tkys_qapplication):
    veri = {"v": {"toplam_kayit": 0, "kisaltildi": False, "ozet": {"toplam": 0, "aktif": 0, "bekleyen": 0, "onaylanan": 0},
                  "oturumlar": []}}
    ekran, _ = _ekran(tkys_qapplication, veri)
    assert not ekran.bos_mesaj.isHidden() and ekran.tablo.isHidden()


def test_otomatik_yenileme_siralamayi_ve_secimi_korur(tkys_qapplication):
    oturumlar = [_oturum(1, "Zeynep", saat=3), _oturum(2, "Ali", saat=2), _oturum(3, "Can", saat=1), _oturum(4, "Bora", saat=0)]
    veri = {"v": {"toplam_kayit": 4, "kisaltildi": False, "ozet": {"toplam": 4, "aktif": 0, "bekleyen": 4, "onaylanan": 0},
                  "oturumlar": oturumlar}}
    ekran, istek = _ekran(tkys_qapplication, veri)
    ekran.tablo._tiklandi_siralama(0)                                # Öğrenci adına göre artan
    assert _satirlar(ekran) == ["Ali", "Bora", "Can", "Zeynep"]
    ekran.tablo.selectRow(2)                                         # "Can"
    with patch.object(modul, "oturum_kontrollu_istek", side_effect=istek):
        ekran.yenile(sessiz=True)
    assert _satirlar(ekran) == ["Ali", "Bora", "Can", "Zeynep"]
    assert ekran.tablo.item(ekran.tablo.currentRow(), 0).text() == "Can"


def test_dugme_durumlari_onayli_bekleyen_ve_devam_eden(tkys_qapplication):
    veri = {"v": {"toplam_kayit": 3, "kisaltildi": False, "ozet": {"toplam": 3, "aktif": 1, "bekleyen": 1, "onaylanan": 1},
                  "oturumlar": [_oturum(1, "Onaylı", onayli=True, saat=0), _oturum(2, "Bekleyen", saat=1),
                                _oturum(3, "Devam", bitti=False, saat=2)]}}
    ekran, _ = _ekran(tkys_qapplication, veri)
    durumlar = {}
    for satir in range(ekran.tablo.rowCount()):
        ekran.tablo.selectRow(satir)
        durumlar[ekran.tablo.item(satir, 0).text()] = (
            ekran.onay_btn.isEnabled(), ekran.duzenle_btn.isEnabled(), ekran.geri_al_btn.isEnabled())
    assert durumlar == {"Onaylı": (False, False, True), "Bekleyen": (True, True, False), "Devam": (False, False, False)}


def test_onayi_geri_al_dogru_adrese_istek_atar_evet_denmezse_atmaz(tkys_qapplication):
    veri = {"v": {"toplam_kayit": 1, "kisaltildi": False, "ozet": {"toplam": 1, "aktif": 0, "bekleyen": 0, "onaylanan": 1},
                  "oturumlar": [_oturum(7, "Onaylı", onayli=True)]}}
    istekler = []
    ekran, istek = _ekran(tkys_qapplication, veri, istekler)
    ekran.tablo.selectRow(0)
    istekler.clear()

    butonlar = []
    orijinal = modul.QMessageBox.addButton

    def ekle(kutu, *arg):
        dugme = orijinal(kutu, *arg)
        butonlar.append(dugme)
        return dugme

    def cevapla(evet):
        butonlar.clear()
        return patch.object(modul.QMessageBox, "clickedButton", lambda kutu: butonlar[0 if evet else 1])

    with patch.object(modul, "oturum_kontrollu_istek", side_effect=istek), patch.object(modul, "basari_bildirimi"), \
            patch.object(modul.QMessageBox, "addButton", ekle), patch.object(modul.QMessageBox, "exec", lambda kutu: 0):
        with cevapla(evet=False):
            ekran.onayi_geri_al()
        assert [i for i in istekler if i[0] == "PATCH"] == []
        with cevapla(evet=True):
            ekran.onayi_geri_al()
    assert ("PATCH", "http://x/api/danisma/yonetim/oturumlar/7/onay-geri-al") in istekler


def test_ogrenci_sutunu_kalan_genisligi_alir_satir_numarasi_gizli(tkys_qapplication):
    veri = {"v": {"toplam_kayit": 0, "kisaltildi": False, "ozet": {"toplam": 0, "aktif": 0, "bekleyen": 0, "onaylanan": 0},
                  "oturumlar": []}}
    ekran, _ = _ekran(tkys_qapplication, veri)
    baslik = ekran.tablo.horizontalHeader()
    assert baslik.sectionResizeMode(0) == QHeaderView.Stretch and baslik.sectionResizeMode(2) == QHeaderView.ResizeToContents
    assert ekran.tablo.verticalHeader().isHidden()
