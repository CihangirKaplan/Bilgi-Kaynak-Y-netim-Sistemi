"""Oda Kullanımı: doluluk hesabı, sunucu ucu (kimlik gizleme dahil), ekran ve menü bağlantısı.

Sayfa yalnızca görüntülemedir; psikolog başkalarının randevularında yalnızca "Dolu" görür (kimlik bilgisi sunucudan hiç gelmez).
"""
from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from PySide6.QtWidgets import QMessageBox

import client.main_window as main_window
import client.oda_kullanimi_ekrani as modul
import client.tkys_sidebar_refined as tkys_sidebar_refined
from client.oda_kullanimi_ekrani import (
    OdaKullanimiEkrani, blok_haritasi, doluluk_hesapla, hafta_basi, hafta_basligi, saat_dilimleri, yuzde,
)
from server.sunucu import app, mevcut_kullanici_id

PZT = date(2026, 11, 16)
ODALAR = [{"oda_id": 1, "oda_adi": "Oda-1", "kapasite": 1, "aktif_mi": True}, {"oda_id": 2, "oda_adi": "Oda-2", "kapasite": 1, "aktif_mi": True},
          {"oda_id": 3, "oda_adi": "Eski", "kapasite": 1, "aktif_mi": False}]


def randevu(no, gun, saat, oda=1, durum="PLANLANDI", sure=1, psikolog="Ayşe", kod=None, gorusme="YUZ_YUZE", gizli=False):
    bas = datetime(2026, 11, 16 + gun, saat)
    bit = datetime(2026, 11, 16 + gun, saat + sure)
    return {"randevu_id": no, "oda_id": oda, "baslangic_zamani": bas.isoformat(), "bitis_zamani": bit.isoformat(), "durum": durum,
            "psikolog": None if gizli else psikolog, "danisan_kod_id": None if gizli else (kod or f"DAN-2026-{no:04d}"),
            "gorusme_tipi": None if gizli else gorusme, "benim": not gizli}


GUNLER = [date(2026, 11, 16 + i) for i in range(7)]
SAATLER = list(range(9, 16))


# ------------------------------------------------------------------ saf işlevler
def test_hafta_basi_ve_basligi():
    assert hafta_basi(date(2026, 11, 22)) == PZT and hafta_basi(PZT) == PZT
    assert hafta_basligi(PZT) == "16 – 22 Kasım 2026"
    assert hafta_basligi(date(2026, 10, 26)) == "26 Eki – 1 Kas 2026"                       # ay değişir
    assert hafta_basligi(date(2026, 12, 28)) == "28 Ara 2026 – 3 Oca 2027"                  # yıl değişir


def test_saat_dilimleri_form_saatleri_eski_randevu_aralik_genisletir():
    assert saat_dilimleri([]) == list(range(9, 16))
    assert saat_dilimleri([randevu(1, 0, 8)]) == list(range(8, 16))
    assert saat_dilimleri([randevu(1, 0, 17, sure=2)]) == list(range(9, 19))                 # 17:00-19:00 → 17 ve 18 dilimleri


def test_doluluk_aktif_odalar_calisma_gunleri_ve_sure_uzerinden():
    r = [randevu(1, 0, 9), randevu(2, 0, 10, sure=2), randevu(3, 1, 9, oda=2), randevu(4, 5, 9, oda=1),     # 4: cumartesi sayılmaz
         randevu(5, 0, 9, oda=3)]                                                                          # 5: pasif oda sayılmaz
    ozet = doluluk_hesapla(r, ODALAR, GUNLER, SAATLER)
    assert ozet["toplam"] == 2 * 5 * 7 and ozet["dolu"] == 4                                 # 1 + 2 (iki saatlik) + 1
    assert ozet["odalar"][1]["dolu"] == 3 and ozet["odalar"][2]["dolu"] == 1 and 3 not in ozet["odalar"]
    assert ozet["en_yogun"]["oda_id"] == 1 and abs(ozet["oran"] - 4 / 70) < 1e-9


def test_doluluk_bos_ve_aktif_oda_yok():
    assert doluluk_hesapla([], ODALAR, GUNLER, SAATLER)["en_yogun"] is None
    bos = doluluk_hesapla([], [], GUNLER, SAATLER)
    assert bos["toplam"] == 0 and bos["oran"] is None
    assert yuzde(None) == "—" and yuzde(0.214) == "%21" and yuzde(1) == "%100"


def test_blok_haritasi_baslangic_saatine_koyar():
    r1, r2 = randevu(1, 0, 9), randevu(2, 0, 9)
    harita = blok_haritasi([r1, r2, randevu(3, 1, 14, oda=2)])
    assert harita[(1, PZT, 9)] == [r1, r2] and (2, date(2026, 11, 17), 14) in harita


# ------------------------------------------------------------------ sunucu ucu
@pytest.fixture
def istemci():
    app.dependency_overrides[mevcut_kullanici_id] = lambda: 5
    yield TestClient(app)
    app.dependency_overrides.pop(mevcut_kullanici_id, None)


def _cagir(istemci, sorgu, rol="ADMIN"):
    conn = MagicMock()
    c = conn.cursor.return_value
    c.fetchone.side_effect = [(1,), (rol,)]
    c.fetchall.side_effect = [
        [(1, "Oda-1", 1, True)],
        [(10, 1, datetime(2026, 11, 16, 9), datetime(2026, 11, 16, 10), "PLANLANDI", "Ayşe", "DAN-2026-0001", "ONLINE", True),
         (11, 1, datetime(2026, 11, 16, 10), datetime(2026, 11, 16, 11), "TAMAMLANDI", "Fatma", "DAN-2026-0002", "YUZ_YUZE", False)],
    ]
    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        yanit = istemci.get("/api/oda-kullanimi" + sorgu)
    sorgular = [x.args for x in c.execute.call_args_list if "FROM randevular r" in x.args[0]]
    return yanit, (sorgular[0] if sorgular else None)


def test_admin_tum_bilgiyi_gorur_ve_iptaller_sorguda_elenir(istemci):
    yanit, (sql, parametreler) = _cagir(istemci, "?baslangic=2026-11-16&bitis=2026-11-22")
    assert yanit.status_code == 200
    veri = yanit.json()
    assert veri["odalar"] == [{"oda_id": 1, "oda_adi": "Oda-1", "kapasite": 1, "aktif_mi": True}]
    assert [(r["psikolog"], r["danisan_kod_id"], r["gorusme_tipi"]) for r in veri["randevular"]] == [("Ayşe", "DAN-2026-0001", "ONLINE"), ("Fatma", "DAN-2026-0002", "YUZ_YUZE")]
    assert "r.durum <> 'IPTAL_EDILDI'" in sql and parametreler[0] == 5
    assert parametreler[1] == datetime(2026, 11, 16) and parametreler[2] == datetime(2026, 11, 23)       # bitiş günü dahil


def test_psikolog_baskasinin_randevusunda_kimlik_goremez(istemci):
    veri = _cagir(istemci, "?baslangic=2026-11-16&bitis=2026-11-22", rol="PSIKOLOG")[0].json()
    kendi, baskasi = veri["randevular"]
    assert kendi["psikolog"] == "Ayşe" and kendi["danisan_kod_id"] == "DAN-2026-0001" and kendi["benim"] is True
    assert (baskasi["psikolog"], baskasi["danisan_kod_id"], baskasi["gorusme_tipi"]) == (None, None, None) and baskasi["benim"] is False
    assert baskasi["baslangic_zamani"] and baskasi["oda_id"] == 1                                        # zaman ve oda (doluluk) görünür


@pytest.mark.parametrize("sorgu", ["", "?baslangic=2026-11-16", "?baslangic=2026-11-22&bitis=2026-11-16", "?baslangic=2026-01-01&bitis=2026-12-31",
                                   "?baslangic=yarin&bitis=bugun"])
def test_gecersiz_aralik_reddedilir(istemci, sorgu):
    yanit, sorgusu = _cagir(istemci, sorgu)
    assert yanit.status_code == 422 and sorgusu is None


# ------------------------------------------------------------------ ekran
class Sunucu:
    def __init__(self, randevular=None, odalar=None):
        self.randevular = [randevu(1, 0, 9, kod="DAN-2026-0001"), randevu(2, 0, 10, oda=2, durum="TAMAMLANDI", psikolog="Fatma", gorusme="ONLINE"),
                           randevu(3, 1, 11, gizli=True), randevu(4, 2, 9, durum="GELMEDI")] if randevular is None else randevular
        self.odalar = ODALAR if odalar is None else odalar
        self.istekler = []

    def __call__(self, yontem, url, **kwargs):
        self.istekler.append((url, kwargs.get("params") or {}))
        veri = {"odalar": self.odalar, "randevular": self.randevular}
        return SimpleNamespace(status_code=200, json=lambda: veri, raise_for_status=lambda: None)


@pytest.fixture
def ekran_ac(tkys_qapplication):
    acilanlar = []

    def ac(sunucu=None, bugun=PZT):
        sunucu = sunucu or Sunucu()
        with patch.object(modul, "oturum_kontrollu_istek", side_effect=sunucu), patch.object(modul, "date") as sahte_tarih:
            sahte_tarih.today.return_value = bugun
            sahte_tarih.side_effect = lambda *a, **k: date(*a, **k)
            ekran = OdaKullanimiEkrani("http://x", "T")
            ekran._sunucu = sunucu
            acilanlar.append(ekran)
            return ekran, sunucu

    yield ac
    for e in acilanlar:
        e.close()


def blok_metinleri(ekran, satir, sutun):
    kutu = ekran.tablo.cellWidget(satir, sutun)
    return [e.text() for e in kutu.findChildren(modul.QLabel)] if kutu is not None else None


def test_acilista_bugunun_gun_gorunumu_ve_istek_araligi(ekran_ac):
    ekran, sunucu = ekran_ac()
    assert sunucu.istekler[0][1] == {"baslangic": "2026-11-16", "bitis": "2026-11-22"}
    assert ekran.lbl_baslik.text() == "16 – 22 Kasım 2026" and ekran.gorunum == "gun"
    assert ekran.tablo.columnCount() == 2 and ekran.tablo.rowCount() == 7                    # iki aktif oda x 7 saat dilimi
    basliklar = [ekran.tablo.horizontalHeaderItem(i).text() for i in range(2)]
    assert basliklar[0].startswith("Oda-1") and basliklar[1].startswith("Oda-2")
    assert [ekran.tablo.verticalHeaderItem(i).text() for i in range(7)] == [f"{h:02d}:00" for h in range(9, 16)]


def test_gun_gorunumunde_bloklar_durum_ve_bilgi(ekran_ac):
    ekran, _ = ekran_ac()
    assert blok_metinleri(ekran, 0, 0)[:2] == ["Ayşe", "DAN-2026-0001"]                       # 09:00 Oda-1
    ikinci = blok_metinleri(ekran, 1, 1)                                                      # 10:00 Oda-2, çevrimiçi
    assert ikinci[0] == "Fatma" and "Çevrimiçi" in ikinci[2]
    assert ekran.tablo.cellWidget(2, 0) is None and ekran.tablo.cellWidget(5, 1) is None       # boş hücreler


def test_ozet_kartlari(ekran_ac):
    ekran, _ = ekran_ac()
    kart = lambda anahtar: [e.text() for e in ekran.kartlar[anahtar]]
    assert kart("oda")[1] == "2" and kart("oda")[2] == "1 pasif oda"
    assert kart("gun")[0] == "Bugün" and kart("gun")[1] == "2" and "1 tamamlandı" in kart("gun")[2] and "1 planlı" in kart("gun")[2]
    assert kart("doluluk")[1] == yuzde(4 / 70) and "4 / 70" in kart("doluluk")[2]
    assert kart("yogun")[1] == "Oda-1"


def test_gun_seridi_ve_gun_secimi(ekran_ac):
    ekran, _ = ekran_ac()
    assert "2 randevu" in ekran.gun_dugmeleri[0].text() and "1 randevu" in ekran.gun_dugmeleri[1].text() and ekran.gun_dugmeleri[5].text().endswith("—")
    ekran.gun_dugmeleri[1].click()                                                            # Salı: başka psikolog "Dolu" bloğu
    assert ekran.secili_gun == date(2026, 11, 17) and ekran.gorunum == "gun"
    assert blok_metinleri(ekran, 2, 0)[0] == "Dolu" and len(blok_metinleri(ekran, 2, 0)) == 2      # kimlik yok, yalnızca "Dolu" + saat
    assert ekran.kartlar["gun"][0].text() == "17 Kasım"


def test_hafta_gorunumu_secili_odanin_haftasini_gosterir(ekran_ac):
    ekran, _ = ekran_ac()
    ekran.btn_hafta.click()
    assert ekran.gorunum == "hafta" and ekran.tablo.columnCount() == 7 and ekran.oda_sec.isVisibleTo(ekran)
    assert blok_metinleri(ekran, 0, 0)[0] == "Ayşe"                                           # Pzt 09:00 Oda-1
    assert blok_metinleri(ekran, 0, 2)[0] == "Ayşe"                                           # Çar 09:00 Oda-1 (gelmedi)
    assert ekran.tablo.cellWidget(1, 0) is None                                               # Oda-1'de Pzt 10:00 boş (o Oda-2'de)
    ekran.oda_sec.setCurrentIndex(1)                                                          # Oda-2
    assert blok_metinleri(ekran, 1, 0)[0] == "Fatma"
    ekran.btn_gun.click()
    assert ekran.gorunum == "gun" and not ekran.oda_sec.isVisibleTo(ekran)


def test_hafta_gezinme_veriyi_yeniden_ister_ve_bugune_doner(ekran_ac):
    ekran, sunucu = ekran_ac()
    with patch.object(modul, "oturum_kontrollu_istek", side_effect=sunucu):
        ekran.btn_ileri.click()
        assert sunucu.istekler[-1][1] == {"baslangic": "2026-11-23", "bitis": "2026-11-29"} and ekran.secili_gun == date(2026, 11, 23)
        ekran.btn_geri.click()
        ekran.btn_geri.click()
        assert sunucu.istekler[-1][1]["baslangic"] == "2026-11-09"
        ekran.btn_bugun.click()
        assert sunucu.istekler[-1][1]["baslangic"] == "2026-11-16" and ekran.secili_gun == ekran.bugun


def test_iki_saatlik_randevu_iki_satiri_kaplar(ekran_ac):
    ekran, _ = ekran_ac(Sunucu([randevu(1, 0, 10, sure=2)]))
    assert ekran.tablo.rowSpan(1, 0) == 2 and blok_metinleri(ekran, 1, 0)[0] == "Ayşe"


def test_ayni_hucrede_iki_randevu_artı_bilgisi_gosterir(ekran_ac):
    ekran, _ = ekran_ac(Sunucu([randevu(1, 0, 9), randevu(2, 0, 9, psikolog="Fatma")]))
    assert "+1" in blok_metinleri(ekran, 0, 0)


def test_aktif_oda_yoksa_bos_mesaj(ekran_ac):
    ekran, _ = ekran_ac(Sunucu([], [{"oda_id": 1, "oda_adi": "Eski", "kapasite": 1, "aktif_mi": False}]))
    assert not ekran.tablo.isVisibleTo(ekran) and ekran.bos_mesaj.isVisibleTo(ekran) and "aktif oda yok" in ekran.bos_mesaj.text()


def test_sunucu_hatasinda_uyari_cokmez(tkys_qapplication):
    import requests
    hata = MagicMock(side_effect=requests.ConnectionError("yok"))
    with patch.object(modul, "oturum_kontrollu_istek", hata), patch.object(QMessageBox, "warning") as uyari:
        ekran = OdaKullanimiEkrani("http://x", "T")
    uyari.assert_called_once()
    ekran.close()


# ------------------------------------------------------------------ menü bağlantısı
def test_menu_oda_kullanimi_normal_sayfa_olarak_baglidir():
    sayfalar = {oge["ad"]: oge for _, ogeler in main_window.MENU for oge in ogeler}
    assert sayfalar["Oda Kullanımı"]["izin"] == "Oda kullanım durumunu görüntüleme"
    assert main_window.AnaPencere.SAYFA_YENILEME["Oda Kullanımı"] == ("oda_kullanimi_ekrani", "yenile")
    assert "Oda Kullanımı" in tkys_sidebar_refined.PAGE_ICONS
    kaynak = open(main_window.__file__, encoding="utf-8").read()
    assert "master_stack.setCurrentIndex(1)" not in kaynak and "HaftalikTakvimEkrani" not in kaynak      # tam ekran takvim yolu kalktı
