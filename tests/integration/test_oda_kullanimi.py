"""Oda Kullanımı: doluluk hesabı, sunucu ucu (kimlik gizleme dahil), ekran ve menü bağlantısı.

Sayfa yalnızca görüntülemedir; psikolog başkalarının randevularında yalnızca "Dolu" görür (kimlik bilgisi sunucudan hiç gelmez).
Cihaz rezervasyonu odayı doldurur: yetkili cihaz adı ve bölümü görür, yetkisi olmayan "Dolu · Cihaz kullanımı" görür. Takvim 08:00-18:00.
"""
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from PySide6.QtWidgets import QMessageBox

import client.main_window as main_window
import client.oda_kullanimi_ekrani as modul
import client.tkys_sidebar_refined as tkys_sidebar_refined
from client.oda_kullanimi_ekrani import (
    OdaKullanimiEkrani, baslik_yuksekligi, blok_haritasi, doluluk_hesapla, hafta_basi, hafta_basligi, oda_basligi, rezervasyon_kayitlari,
    saat_dilimleri, yuzde,
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


def rezervasyon(no, gun, saat, oda=1, sure=1, cihaz="EEG Seti", bolum="Psikoloji", gizli=False):
    bas = datetime(2026, 11, 16 + gun, saat)
    return {"rezervasyon_id": no, "oda_id": oda, "baslangic_zamani": bas.isoformat(), "bitis_zamani": (bas + timedelta(hours=sure)).isoformat(),
            "cihaz_adi": None if gizli else cihaz, "bolum_adi": None if gizli else bolum}


GUNLER = [date(2026, 11, 16 + i) for i in range(7)]
SAATLER = list(range(9, 16))


# ------------------------------------------------------------------ saf işlevler
def test_hafta_basi_ve_basligi():
    assert hafta_basi(date(2026, 11, 22)) == PZT and hafta_basi(PZT) == PZT
    assert hafta_basligi(PZT) == "16 – 22 Kasım 2026"
    assert hafta_basligi(date(2026, 10, 26)) == "26 Eki – 1 Kas 2026"                       # ay değişir
    assert hafta_basligi(date(2026, 12, 28)) == "28 Ara 2026 – 3 Oca 2027"                  # yıl değişir


def test_saat_dilimleri_her_zaman_sabit_08_18_mesai_disi_kayit_genisletmez():
    assert saat_dilimleri([]) == saat_dilimleri() == list(range(8, 18))                      # 08:00-18:00 mesai
    assert saat_dilimleri([randevu(1, 0, 9)]) == list(range(8, 18))
    assert saat_dilimleri([randevu(1, 0, 7)]) == list(range(8, 18))                          # mesai öncesi kayıt ızgarayı genişletmez
    assert saat_dilimleri([randevu(1, 0, 17, sure=2)]) == list(range(8, 18))                 # 17:00-19:00 kaydı da genişletmez


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


def test_oda_basligi_uzun_adi_satirlara_boler_ve_dolulugu_altina_yazar():
    assert oda_basligi("Oda-1", "%43") == "Oda-1\n%43 dolu"
    assert oda_basligi("Gözlem ve Sanal Gerçeklik Odası", "%0").split("\n") == ["Gözlem ve Sanal", "Gerçeklik Odası", "%0 dolu"]
    assert oda_basligi("Göz İzleme ve Sanal Gerçeklik Odası", "%0").split("\n") == ["Göz İzleme ve", "Sanal Gerçeklik", "Odası", "%0 dolu"]   # üç satır
    cok_uzun = oda_basligi("Çok Uzun Adlı Bir Terapi Görüşme Gözlem Odası", "%10").split("\n")
    assert len(cok_uzun) == 4 and cok_uzun[3] == "%10 dolu"                                  # ad en çok üç satır
    assert oda_basligi("", "%0") == "\n%0 dolu"


def test_baslik_yuksekligi_satir_sayisina_gore():
    assert baslik_yuksekligi(["Pzt 16"]) == 27 and baslik_yuksekligi(["Oda-1\n%0 dolu"]) == 40
    assert baslik_yuksekligi(["A\nB\nC\n%0 dolu", "X\n%0 dolu"]) == 66 and baslik_yuksekligi([]) == 27


def test_rezervasyon_kayitlari_randevu_bicimine_cevrilir():
    (k,) = rezervasyon_kayitlari([rezervasyon(7, 0, 16, oda=2, sure=2)])
    assert (k["oda_id"], k["cihaz"], k["durum"], k["cihaz_adi"], k["bolum_adi"]) == (2, True, "CIHAZ", "EEG Seti", "Psikoloji")
    assert (k["baslangic_zamani"], k["bitis_zamani"]) == ("2026-11-16T16:00:00", "2026-11-16T18:00:00")
    assert k["psikolog"] is None and k["danisan_kod_id"] is None
    assert blok_haritasi([k])[(2, PZT, 16)] == [k]


def _kayit(bas, bit):
    return {"rezervasyon_id": 1, "oda_id": 1, "baslangic_zamani": bas.isoformat(), "bitis_zamani": bit.isoformat(), "cihaz_adi": "EEG", "bolum_adi": None}


def test_cok_gunlu_rezervasyon_tek_kayit_her_gun_yalnizca_mesai_kismi_cizilir():
    bas, bit = datetime(2026, 11, 18, 9), datetime(2026, 11, 20, 9)                           # 18.11 09:00 → 20.11 09:00
    parcalar = rezervasyon_kayitlari([_kayit(bas, bit)])
    assert [(p["baslangic_zamani"], p["bitis_zamani"]) for p in parcalar] == [
        ("2026-11-18T09:00:00", "2026-11-18T18:00:00"), ("2026-11-19T08:00:00", "2026-11-19T18:00:00"), ("2026-11-20T08:00:00", "2026-11-20T09:00:00")]
    assert {(p["gercek_baslangic"], p["gercek_bitis"]) for p in parcalar} == {(bas.isoformat(), bit.isoformat())}      # gerçek aralık korunur
    assert len(rezervasyon_kayitlari([_kayit(datetime(2026, 11, 16, 17), datetime(2026, 11, 17))])) == 1              # gece yarısında biten fazladan gün açmaz


def test_mesai_disina_dusen_rezervasyon_kismi_gosterilmez():
    assert rezervasyon_kayitlari([_kayit(datetime(2026, 11, 16, 19), datetime(2026, 11, 16, 22))]) == []             # tamamen mesai dışı
    assert rezervasyon_kayitlari([_kayit(datetime(2026, 11, 16, 18), datetime(2026, 11, 17, 8))]) == []              # gece boyunca: çizilecek mesai kısmı yok
    (k,) = rezervasyon_kayitlari([_kayit(datetime(2026, 11, 16, 6), datetime(2026, 11, 16, 9))])
    assert (k["baslangic_zamani"], k["bitis_zamani"]) == ("2026-11-16T08:00:00", "2026-11-16T09:00:00")              # sabah kısmı kırpılır
    (k,) = rezervasyon_kayitlari([_kayit(datetime(2026, 11, 16, 17), datetime(2026, 11, 16, 20))])
    assert (k["baslangic_zamani"], k["bitis_zamani"]) == ("2026-11-16T17:00:00", "2026-11-16T18:00:00")              # akşam kısmı kırpılır


def test_gecersiz_rezervasyon_kayitlari_atlanir():
    gecersiz = [{"oda_id": 1, "baslangic_zamani": None, "bitis_zamani": None},
                {"oda_id": 1, "baslangic_zamani": "2026-11-16T10:00:00", "bitis_zamani": "2026-11-16T09:00:00"}]
    assert rezervasyon_kayitlari(gecersiz) == [] and rezervasyon_kayitlari([]) == []


def test_doluluk_cihaz_rezervasyonunu_da_dolu_sayar_ve_ayni_dilimi_bir_kez():
    r = rezervasyon_kayitlari([rezervasyon(1, 0, 16, sure=2), rezervasyon(2, 1, 9, oda=2)])
    ozet = doluluk_hesapla(r + [randevu(5, 0, 16)], ODALAR, GUNLER, list(range(8, 18)))      # aynı odada aynı saatte randevu: dilim bir kez
    assert ozet["dolu"] == 3 and ozet["odalar"][1]["dolu"] == 2 and ozet["odalar"][2]["dolu"] == 1 and ozet["toplam"] == 2 * 5 * 10


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


def _cagir(istemci, sorgu, rol="ADMIN", cihaz_izni=None):
    """cihaz_izni verilmezse yalnızca psikolog rolünde izin yok sayılır (gerçek rol_izinleri düzeni)."""
    izin = (0 if "PSIKOLOG" in rol else 1) if cihaz_izni is None else int(cihaz_izni)
    conn = MagicMock()
    c = conn.cursor.return_value
    c.fetchone.side_effect = [(1,), (rol, izin)]
    c.fetchall.side_effect = [
        [(1, "Oda-1", 1, True)],
        [(10, 1, datetime(2026, 11, 16, 9), datetime(2026, 11, 16, 10), "PLANLANDI", "Ayşe", "DAN-2026-0001", "ONLINE", True),
         (11, 1, datetime(2026, 11, 16, 10), datetime(2026, 11, 16, 11), "TAMAMLANDI", "Fatma", "DAN-2026-0002", "YUZ_YUZE", False)],
        [(20, 1, datetime(2026, 11, 16, 16), datetime(2026, 11, 16, 18), "EEG Seti", "Psikoloji")],
    ]
    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        yanit = istemci.get("/api/oda-kullanimi" + sorgu)
    sorgular = [x.args for x in c.execute.call_args_list if "FROM randevular r" in x.args[0]]
    _cagir.rezervasyon_sorgusu = next((x.args for x in c.execute.call_args_list if "FROM cihaz_rezervasyonlari" in x.args[0]), None)
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


def test_admin_cihaz_rezervasyonunu_cihaz_adi_ve_bolumle_gorur(istemci):
    veri = _cagir(istemci, "?baslangic=2026-11-16&bitis=2026-11-22")[0].json()
    assert veri["rezervasyonlar"] == [{"rezervasyon_id": 20, "oda_id": 1, "baslangic_zamani": "2026-11-16T16:00:00",
                                       "bitis_zamani": "2026-11-16T18:00:00", "cihaz_adi": "EEG Seti", "bolum_adi": "Psikoloji"}]
    sql, parametreler = _cagir.rezervasyon_sorgusu
    assert "COALESCE(cr.iptal_edildi_mi, FALSE) = FALSE" in sql and "cr.kullanilacak_oda_id IS NOT NULL" in sql      # iptaller ve odasızlar elenir
    assert "cr.baslangic_zamani < %s AND cr.bitis_zamani > %s" in sql                                                # aralıkla kesişenler
    assert parametreler == (datetime(2026, 11, 23), datetime(2026, 11, 16))


def test_cihaz_izni_olmayan_yalnizca_odanin_dolu_oldugunu_gorur(istemci):
    veri = _cagir(istemci, "?baslangic=2026-11-16&bitis=2026-11-22", rol="PSIKOLOG")[0].json()
    (r,) = veri["rezervasyonlar"]
    assert (r["cihaz_adi"], r["bolum_adi"]) == (None, None)                                           # cihaz ve bölüm bilgisi sunucudan hiç gelmez
    assert r["oda_id"] == 1 and r["baslangic_zamani"] == "2026-11-16T16:00:00" and r["bitis_zamani"] == "2026-11-16T18:00:00"
    assert "EEG" not in str(veri) and "Psikoloji" not in str(veri)


def test_cihaz_izni_rol_adindan_degil_izinden_gelir(istemci):
    gorur = _cagir(istemci, "?baslangic=2026-11-16&bitis=2026-11-22", rol="PSIKOLOG", cihaz_izni=True)[0].json()["rezervasyonlar"][0]
    gormez = _cagir(istemci, "?baslangic=2026-11-16&bitis=2026-11-22", rol="MEMUR", cihaz_izni=False)[0].json()["rezervasyonlar"][0]
    assert gorur["cihaz_adi"] == "EEG Seti" and gormez["cihaz_adi"] is None


@pytest.mark.parametrize("sorgu", ["", "?baslangic=2026-11-16", "?baslangic=2026-11-22&bitis=2026-11-16", "?baslangic=2026-01-01&bitis=2026-12-31",
                                   "?baslangic=yarin&bitis=bugun"])
def test_gecersiz_aralik_reddedilir(istemci, sorgu):
    yanit, sorgusu = _cagir(istemci, sorgu)
    assert yanit.status_code == 422 and sorgusu is None


# ------------------------------------------------------------------ ekran
class Sunucu:
    def __init__(self, randevular=None, odalar=None, rezervasyonlar=None):
        self.randevular = [randevu(1, 0, 9, kod="DAN-2026-0001"), randevu(2, 0, 10, oda=2, durum="TAMAMLANDI", psikolog="Fatma", gorusme="ONLINE"),
                           randevu(3, 1, 11, gizli=True), randevu(4, 2, 9, durum="GELMEDI")] if randevular is None else randevular
        self.odalar = ODALAR if odalar is None else odalar
        self.rezervasyonlar = [] if rezervasyonlar is None else rezervasyonlar
        self.istekler = []

    def __call__(self, yontem, url, **kwargs):
        self.istekler.append((url, kwargs.get("params") or {}))
        veri = {"odalar": self.odalar, "randevular": self.randevular, "rezervasyonlar": self.rezervasyonlar}
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
    assert ekran.tablo.columnCount() == 2 and ekran.tablo.rowCount() == 10                   # iki aktif oda x 10 saat dilimi (08:00-18:00)
    basliklar = [ekran.tablo.horizontalHeaderItem(i).text() for i in range(2)]
    assert basliklar[0].startswith("Oda-1") and basliklar[1].startswith("Oda-2")
    assert [ekran.tablo.verticalHeaderItem(i).text() for i in range(10)] == [f"{h:02d}:00" for h in range(8, 18)]


def test_cok_odali_gunde_uzun_oda_adlari_tam_basliklarda_yer_alir(ekran_ac):
    odalar = [{"oda_id": i, "oda_adi": ad, "kapasite": 1, "aktif_mi": True} for i, ad in enumerate(
        ["Aynalı Görüşme Odası", "Bilişsel Test Odası", "Gözlem ve Sanal Gerçeklik Odası", "Oyun Terapi Odası", "Sanat Terapi Odası", "EEG Odası",
         "Deneme Odası-2", "Görüşme Odası-1", "Görüşme Odası-2", "Gözlem Odası"], start=1)]
    ekran, _ = ekran_ac(Sunucu([], odalar))
    assert ekran.tablo.columnCount() == 10 and ekran.tablo.horizontalHeader().minimumSectionSize() >= 110
    assert ekran.tablo.horizontalHeader().height() == 53                                      # en uzun ad iki satır + doluluk satırı
    basliklar = [ekran.tablo.horizontalHeaderItem(i).text() for i in range(10)]
    assert "Gerçeklik Odası" in basliklar[2] and basliklar[0].startswith("Aynalı Görüşme") and all(b.endswith("dolu") for b in basliklar)
    ekran.btn_hafta.click()
    assert ekran.tablo.horizontalHeader().height() == 27                                      # hafta görünümünde gün başlıkları tek satır


def test_gun_gorunumunde_bloklar_durum_ve_bilgi(ekran_ac):
    ekran, _ = ekran_ac()
    assert blok_metinleri(ekran, 1, 0)[:2] == ["Ayşe", "DAN-2026-0001"]                       # 09:00 Oda-1 (08:00 satırı ilk satır)
    ikinci = blok_metinleri(ekran, 2, 1)                                                      # 10:00 Oda-2, çevrimiçi
    assert ikinci[0] == "Fatma" and "Çevrimiçi" in ikinci[2]
    assert ekran.tablo.cellWidget(3, 0) is None and ekran.tablo.cellWidget(6, 1) is None       # boş hücreler


def test_ozet_kartlari(ekran_ac):
    ekran, _ = ekran_ac()
    kart = lambda anahtar: [e.text() for e in ekran.kartlar[anahtar]]
    assert kart("oda")[1] == "2" and kart("oda")[2] == "1 pasif oda"
    assert kart("gun")[0] == "Bugün" and kart("gun")[1] == "2" and "1 tamamlandı" in kart("gun")[2] and "1 planlı" in kart("gun")[2]
    assert kart("doluluk")[1] == yuzde(4 / 100) and "4 / 100" in kart("doluluk")[2]
    assert kart("yogun")[1] == "Oda-1"


def test_gun_seridi_ve_gun_secimi(ekran_ac):
    ekran, _ = ekran_ac()
    assert "2 randevu" in ekran.gun_dugmeleri[0].text() and "1 randevu" in ekran.gun_dugmeleri[1].text() and ekran.gun_dugmeleri[5].text() == "Cmt 21"
    ekran.gun_dugmeleri[1].click()                                                            # Salı: başka psikolog "Dolu" bloğu
    assert ekran.secili_gun == date(2026, 11, 17) and ekran.gorunum == "gun"
    assert blok_metinleri(ekran, 3, 0)[0] == "Dolu" and len(blok_metinleri(ekran, 3, 0)) == 2      # kimlik yok, yalnızca "Dolu" + saat
    assert ekran.kartlar["gun"][0].text() == "17 Kasım"


def test_hafta_gorunumu_secili_odanin_haftasini_gosterir(ekran_ac):
    ekran, _ = ekran_ac()
    ekran.btn_hafta.click()
    assert ekran.gorunum == "hafta" and ekran.tablo.columnCount() == 7 and ekran.oda_sec.isVisibleTo(ekran)
    assert blok_metinleri(ekran, 1, 0)[0] == "Ayşe"                                           # Pzt 09:00 Oda-1
    assert blok_metinleri(ekran, 1, 2)[0] == "Ayşe"                                           # Çar 09:00 Oda-1 (gelmedi)
    assert ekran.tablo.cellWidget(2, 0) is None                                               # Oda-1'de Pzt 10:00 boş (o Oda-2'de)
    ekran.oda_sec.setCurrentIndex(1)                                                          # Oda-2
    assert blok_metinleri(ekran, 2, 0)[0] == "Fatma"
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
    assert ekran.tablo.rowSpan(2, 0) == 2 and blok_metinleri(ekran, 2, 0)[0] == "Ayşe"           # 10:00 (08:00 satırı ilk satır)


def test_ayni_hucrede_iki_randevu_artı_bilgisi_gosterir(ekran_ac):
    ekran, _ = ekran_ac(Sunucu([randevu(1, 0, 9), randevu(2, 0, 9, psikolog="Fatma")]))
    assert "+1" in blok_metinleri(ekran, 1, 0)


# ------------------------------------------------------------------ cihaz rezervasyonu
def test_16_18_arasi_cihaz_rezervasyonu_gorunur_ve_iki_satiri_kaplar(ekran_ac):
    ekran, _ = ekran_ac(Sunucu([], rezervasyonlar=[rezervasyon(1, 0, 16, sure=2)]))
    assert ekran.tablo.rowCount() == 10 and ekran.tablo.verticalHeaderItem(8).text() == "16:00"      # 16:00 ve 17:00 satırları mesaide
    assert ekran.tablo.rowSpan(8, 0) == 2
    assert blok_metinleri(ekran, 8, 0) == ["EEG Seti", "Psikoloji", "16:00 – 18:00"]


def test_mesai_disi_kayitlar_cizilmez_ve_izgara_genislemez(ekran_ac):
    ekran, _ = ekran_ac(Sunucu([randevu(1, 0, 19), randevu(2, 0, 6)], rezervasyonlar=[rezervasyon(3, 0, 19, sure=3)]))
    assert ekran.tablo.rowCount() == 10 and [ekran.tablo.verticalHeaderItem(i).text() for i in range(10)] == [f"{h:02d}:00" for h in range(8, 18)]
    assert all(ekran.tablo.cellWidget(satir, sutun) is None for satir in range(10) for sutun in range(2))             # hiçbiri çizilmez


def test_cok_gunlu_rezervasyon_her_gun_mesai_kismiyla_ve_gercek_aralikla_gorunur(ekran_ac):
    r = rezervasyon(1, 2, 9)                                                                  # Çar 18.11 09:00
    r["bitis_zamani"] = datetime(2026, 11, 20, 9).isoformat()                                # → Cum 20.11 09:00
    ekran, _ = ekran_ac(Sunucu([], rezervasyonlar=[r]))
    ekran.btn_hafta.click()
    assert blok_metinleri(ekran, 1, 2) == ["EEG Seti", "Psikoloji", "18.11 09:00 – 20.11 09:00"]     # Çar: 09:00'dan, yazıda gerçek aralık
    assert ekran.tablo.rowSpan(1, 2) == 9                                                            # 09:00-18:00 (9 satır)
    assert ekran.tablo.rowSpan(0, 3) == 10 and blok_metinleri(ekran, 0, 3)[2] == "18.11 09:00 – 20.11 09:00"          # Per: 08:00-18:00 tam gün
    assert ekran.tablo.rowSpan(0, 4) == 1 and blok_metinleri(ekran, 0, 4)[0] == "EEG Seti"            # Cum: yalnızca 08:00-09:00
    assert ekran.tablo.rowCount() == 10


def test_yetkili_cihaz_adi_ve_bolumu_gorur(ekran_ac):
    ekran, _ = ekran_ac(Sunucu([], rezervasyonlar=[rezervasyon(1, 0, 9, bolum=None)]))
    assert blok_metinleri(ekran, 1, 0) == ["EEG Seti", "—", "09:00 – 10:00"]                       # bölüm yoksa "—"


def test_yetkisi_olmayan_odanin_cihaz_kullanimi_nedeniyle_dolu_oldugunu_gorur(ekran_ac):
    ekran, _ = ekran_ac(Sunucu([], rezervasyonlar=[rezervasyon(1, 0, 9, gizli=True)]))
    assert blok_metinleri(ekran, 1, 0) == ["Dolu", "Cihaz kullanımı", "09:00 – 10:00"]
    assert "EEG" not in " ".join(blok_metinleri(ekran, 1, 0))


def test_cihaz_rezervasyonu_randevu_sayaclarina_girmez_dolulugu_arttirir(ekran_ac):
    ekran, _ = ekran_ac(Sunucu([randevu(1, 0, 9)], rezervasyonlar=[rezervasyon(2, 0, 10, oda=2, sure=3), rezervasyon(3, 1, 9, oda=2)]))
    assert ekran.gun_dugmeleri[0].text() == "Pzt 16  ·  1 randevu" and ekran.gun_dugmeleri[1].text() == "Sal 17"      # randevu sayısı yalnızca randevu
    assert ekran.kartlar["gun"][1].text() == "1"
    assert "5 / 100" in ekran.kartlar["doluluk"][2].text() and ekran.kartlar["yogun"][1].text() == "Oda-2"            # 1 + 3 + 1 saat dilimi


def test_hafta_gorunumunde_cihaz_rezervasyonu_odanin_gununde_cizilir(ekran_ac):
    ekran, _ = ekran_ac(Sunucu([], rezervasyonlar=[rezervasyon(1, 2, 13, oda=2)]))
    ekran.btn_hafta.click()
    ekran.oda_sec.setCurrentIndex(1)                                                          # Oda-2
    assert blok_metinleri(ekran, 5, 2)[0] == "EEG Seti"                                       # Çar 13:00
    ekran.oda_sec.setCurrentIndex(0)
    assert ekran.tablo.cellWidget(5, 2) is None


def test_eski_sunucu_rezervasyon_alani_gondermezse_ekran_calisir(ekran_ac):
    ekran, _ = ekran_ac()
    veri = {"odalar": ODALAR, "randevular": []}
    with patch.object(modul, "oturum_kontrollu_istek", return_value=SimpleNamespace(status_code=200, json=lambda: veri, raise_for_status=lambda: None)):
        ekran.yenile()
    assert ekran.rezervasyonlar == []


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
def test_oda_kullanimi_kompakt_kenar_bosluklariyla_acilir_diger_sayfalar_varsayilanla():
    ana = MagicMock()
    ana.sayfa_bilgi = [("Ana Kontrol Paneli", ""), ("Oda Kullanımı", "")]
    ana.KOMPAKT_SAYFALAR = main_window.AnaPencere.KOMPAKT_SAYFALAR
    ana.SAYFA_KENAR_BOSLUKLARI = main_window.AnaPencere.SAYFA_KENAR_BOSLUKLARI
    main_window.AnaPencere.sayfa_ac(ana, 1)
    ana.sag_yerlesim.setContentsMargins.assert_called_with(28, 6, 28, 6)                      # üst ve alt boşluk daraltılır
    main_window.AnaPencere.sayfa_ac(ana, 0)
    ana.sag_yerlesim.setContentsMargins.assert_called_with(28, 24, 28, 18)                    # diğer sayfalar eskisi gibi


def test_sayfa_kendi_cevre_bosluk_eklemez(ekran_ac):
    ekran, _ = ekran_ac()
    m = ekran.layout().contentsMargins()
    assert (m.left(), m.top(), m.right(), m.bottom()) == (0, 0, 0, 0)


def test_menu_oda_kullanimi_normal_sayfa_olarak_baglidir():
    sayfalar = {oge["ad"]: oge for _, ogeler in main_window.MENU for oge in ogeler}
    assert sayfalar["Oda Kullanımı"]["izin"] == "Oda kullanım durumunu görüntüleme"
    assert main_window.AnaPencere.SAYFA_YENILEME["Oda Kullanımı"] == ("oda_kullanimi_ekrani", "yenile")
    assert "Oda Kullanımı" in tkys_sidebar_refined.PAGE_ICONS
    kaynak = open(main_window.__file__, encoding="utf-8").read()
    assert "master_stack.setCurrentIndex(1)" not in kaynak and "HaftalikTakvimEkrani" not in kaynak      # tam ekran takvim yolu kalktı
