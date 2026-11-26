"""Randevu Raporları: hesaplama, sunucu ucu, Excel çıktısı ve ekran.

Rapor danışanları yalnızca kodla gösterir (kişisel veri yok); psikolog yalnızca kendi randevularını raporlar.
"""
import os
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from PySide6.QtWidgets import QFileDialog, QMessageBox

import client.main_window as main_window
import server.modeller as modeller
import client.randevu_raporlari_ekrani as ekranmodulu
import client.tkys_sidebar_refined as tkys_sidebar_refined
from client.randevu_rapor_excel import excel_dosyasi_olustur
from server.randevu_rapor_hesapla import randevu_raporu_hesapla
from client.randevu_raporlari_ekrani import RandevuRaporlariEkrani, yuzde_metni
from server.sunucu import app, mevcut_kullanici_id

ETIKETLER = {"iptal": modeller.IPTAL_NEDENLERI, "gorusme": modeller.GORUSME_TIPLERI, "terapi": modeller.TERAPI_TURLERI, "yas": modeller.YAS_GRUPLARI}


def satir(no, durum, psikolog=3, ad="Ayşe", yas="COCUK", terapi="OYUN_TERAPISI", gorusme="YUZ_YUZE", neden=None, kod=None):
    return {"randevu_id": no, "danisan_kod_id": kod or f"DAN-2026-{no:04d}", "psikolog_id": psikolog, "psikolog_adi": ad, "oda_id": 2,
            "oda_adi": "Oda-2", "baslangic_zamani": datetime(2026, 11, 2 + no, 10, 0), "bitis_zamani": datetime(2026, 11, 2 + no, 11, 0),
            "durum": durum, "iptal_nedeni": neden, "gorusme_tipi": gorusme, "terapi_turu": terapi, "yas_grubu": yas}


ORNEK = [
    satir(1, "TAMAMLANDI"), satir(2, "TAMAMLANDI", yas="YETISKIN", terapi="BIREYSEL_TERAPI", gorusme="ONLINE"),
    satir(3, "TAMAMLANDI", psikolog=7, ad="Fatma", yas="YETISKIN", terapi="BIREYSEL_TERAPI"),
    satir(4, "GELMEDI", psikolog=7, ad="Fatma"), satir(5, "PLANLANDI", yas=None, terapi=None),
    satir(6, "IPTAL_EDILDI", neden="DANISAN_TALEBI"), satir(7, "IPTAL_EDILDI", neden="DANISAN_TALEBI"),
    satir(8, "IPTAL_EDILDI", neden=None), satir(9, "IPTAL_EDILDI", neden="DIGER", kod="DAN-2026-0001"),
]


# ------------------------------------------------------------------ hesaplama
def test_ozet_sayilari_ve_oranlar():
    ozet = randevu_raporu_hesapla(ORNEK, ETIKETLER)["ozet"]
    assert (ozet["toplam"], ozet["planlandi"], ozet["tamamlandi"], ozet["gelmedi"], ozet["iptal_edildi"]) == (9, 1, 3, 1, 4)
    assert ozet["tamamlanma_orani"] == 0.75 and ozet["gelmeme_orani"] == 0.25           # planlı ve iptaller oranlara girmez
    assert ozet["danisan_sayisi"] == 8                                                   # DAN-2026-0001 iki kez geçer


def test_bos_donemde_oranlar_hesaplanamaz_ve_hata_vermez():
    sonuc = randevu_raporu_hesapla([], ETIKETLER)
    assert sonuc["ozet"]["toplam"] == 0 and sonuc["ozet"]["tamamlanma_orani"] is None and sonuc["ozet"]["gelmeme_orani"] is None
    assert sonuc["psikologlar"] == [] and sonuc["iptal_nedenleri"] == []


def test_psikolog_bazli_dokum_cokluktan_aza():
    liste = randevu_raporu_hesapla(ORNEK, ETIKETLER)["psikologlar"]
    assert [p["ad"] for p in liste] == ["Ayşe", "Fatma"]
    ayse, fatma = liste
    assert (ayse["toplam"], ayse["tamamlandi"], ayse["iptal_edildi"], ayse["planlandi"]) == (7, 2, 4, 1)
    assert (fatma["toplam"], fatma["tamamlandi"], fatma["gelmedi"]) == (2, 1, 1)


def test_iptal_nedenleri_eski_iptaller_ayri_satirda():
    nedenler = {n["kod"]: n for n in randevu_raporu_hesapla(ORNEK, ETIKETLER)["iptal_nedenleri"]}
    assert nedenler["DANISAN_TALEBI"]["sayi"] == 2 and nedenler["DANISAN_TALEBI"]["etiket"] == "Danışan talebi" and nedenler["DANISAN_TALEBI"]["pay"] == 0.5
    assert nedenler["KAYDEDILMEMIS"]["sayi"] == 1 and nedenler["KAYDEDILMEMIS"]["etiket"] == "Neden kaydedilmemiş"
    assert nedenler["DIGER"]["sayi"] == 1


def test_dagilimlar_iptalleri_haric_tutar_belirtilmeyenleri_gosterir():
    d = randevu_raporu_hesapla(ORNEK, ETIKETLER)["dagilimlar"]
    assert sum(o["sayi"] for o in d["gorusme_tipi"]) == 5                                  # 9 randevu - 4 iptal
    assert {o["kod"]: o["sayi"] for o in d["gorusme_tipi"]} == {"YUZ_YUZE": 4, "ONLINE": 1}
    terapi = {o["kod"]: o["sayi"] for o in d["terapi_turu"]}
    assert terapi["BELIRTILMEDI"] == 1 and terapi["OYUN_TERAPISI"] == 2 and terapi["BIREYSEL_TERAPI"] == 2
    assert {o["kod"] for o in d["yas_grubu"]} == {"COCUK", "YETISKIN", "BELIRTILMEDI"}


def test_detay_yalnizca_istenince_gelir_ve_iptal_notu_icermez():
    assert "randevular" not in randevu_raporu_hesapla(ORNEK, ETIKETLER)
    detay = randevu_raporu_hesapla(ORNEK, ETIKETLER, detay=True)["randevular"]
    assert len(detay) == 9 and detay[1]["gorusme_tipi"] == "Çevrimiçi" and detay[5]["iptal_nedeni"] == "Danışan talebi" and detay[0]["iptal_nedeni"] is None
    assert not any("not" in anahtar for r in detay for anahtar in r)                      # serbest metin alanı rapora girmez
    assert detay[0]["psikolog"] == "Ayşe" and detay[0]["oda"] == "Oda-2"


# ------------------------------------------------------------------ sunucu ucu
@pytest.fixture
def istemci():
    app.dependency_overrides[mevcut_kullanici_id] = lambda: 5
    yield TestClient(app)
    app.dependency_overrides.pop(mevcut_kullanici_id, None)


def _cagir(istemci, sorgu="", rol="ADMIN"):
    conn = MagicMock()
    c = conn.cursor.return_value
    detay = "detay=true" in sorgu
    bugun = datetime.now().date()
    if detay:
        c.fetchone.side_effect = [(1,), (rol,)]                                           # izin denetimi, rol
        c.fetchall.return_value = [
            (r["randevu_id"], r["danisan_kod_id"], r["psikolog_id"], r["psikolog_adi"], r["oda_id"], r["oda_adi"], r["baslangic_zamani"],
             r["bitis_zamani"], r["durum"], r["iptal_nedeni"], r["gorusme_tipi"], r["terapi_turu"], r["yas_grubu"]) for r in ORNEK
        ]
    else:
        # Özet rapor SQL'de gruplanır: gerçek sorgudaki gibi (psikolog, ad, durum, neden, tip, terapi, yaş, geçmiş mi) -> adet
        gruplar = {}
        for r in ORNEK:
            anahtar = (r["psikolog_id"], r["psikolog_adi"], r["durum"], r["iptal_nedeni"], r["gorusme_tipi"], r["terapi_turu"], r["yas_grubu"],
                       r["baslangic_zamani"].date() < bugun)
            gruplar[anahtar] = gruplar.get(anahtar, 0) + 1
        c.fetchone.side_effect = [(1,), (rol,), (len({r["danisan_kod_id"] for r in ORNEK}),)]    # izin, rol, benzersiz danışan sayısı
        c.fetchall.return_value = [(*k, adet) for k, adet in gruplar.items()]
    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        yanit = istemci.get("/api/randevu-raporu" + sorgu)
    sorgular = [x for x in c.execute.call_args_list if "FROM randevular r" in x.args[0]]
    if not sorgular:
        return yanit, None
    sql, parametreler = sorgular[0].args
    if not detay:
        parametreler = parametreler[1:]                                                   # ilk parametre "bugün" (geçmiş/gelecek ayrımı)
    return yanit, (sql, parametreler)


def test_uc_rapor_doner_ve_tarih_suzgeci_uygulanir(istemci):
    yanit, (sql, parametreler) = _cagir(istemci, "?baslangic=2026-11-01&bitis=2026-11-30&psikolog_id=3&oda_id=2")
    assert yanit.status_code == 200 and yanit.json()["ozet"]["toplam"] == 9
    assert "r.baslangic_zamani >= %s" in sql and "r.baslangic_zamani < %s" in sql and "r.psikolog_id = %s" in sql and "r.oda_id = %s" in sql
    assert parametreler[0] == datetime(2026, 11, 1) and parametreler[1] == datetime(2026, 12, 1)    # bitiş günü dahil
    assert parametreler[2:] == (3, 2)
    assert "randevular" not in yanit.json()


def test_psikolog_yalnizca_kendi_randevularini_raporlar_psikolog_id_yok_sayilir(istemci):
    yanit, (sql, parametreler) = _cagir(istemci, "?psikolog_id=99", rol="PSIKOLOG")
    assert yanit.status_code == 200
    assert "p.kullanici_id = %s" in sql and "r.psikolog_id = %s" not in sql and parametreler == (5,)


def test_detay_istenince_randevu_satirlari_gelir(istemci):
    yanit, _ = _cagir(istemci, "?detay=true")
    assert len(yanit.json()["randevular"]) == 9


@pytest.mark.parametrize("sorgu", ["?baslangic=2026-12-01&bitis=2026-11-01", "?baslangic=yarin", "?psikolog_id=abc", "?oda_id=1;DROP"])
def test_gecersiz_girdi_reddedilir(istemci, sorgu):
    yanit, sorgusu = _cagir(istemci, sorgu)
    assert yanit.status_code == 422 and sorgusu is None


def _secenekler(istemci, sorgu="", rol="ADMIN"):
    conn = MagicMock()
    c = conn.cursor.return_value
    c.fetchone.side_effect = [(1,), (rol,)]
    c.fetchall.side_effect = [[(3, "Ayşe", True), (7, "Fatma", True), (9, "Eski", False)], [(2, "Oda-2", True), (4, "Oda-4", False)]]
    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        yanit = istemci.get("/api/randevu-raporu/secenekler" + sorgu)
    sorgular = [x.args for x in c.execute.call_args_list if "FROM odalar o" in x.args[0] or "FROM personel p" in x.args[0]]
    return yanit, sorgular


def test_secenekler_aktifleri_ve_randevu_gecmisi_olan_pasif_psikolog_ve_odalari_dondurur(istemci):
    yanit, sorgular = _secenekler(istemci)
    assert yanit.json() == {
        "psikologlar": [{"personel_id": 3, "ad_soyad": "Ayşe", "aktif_mi": True}, {"personel_id": 7, "ad_soyad": "Fatma", "aktif_mi": True},
                        {"personel_id": 9, "ad_soyad": "Eski (pasif)", "aktif_mi": False}],     # geçmiş kayıtları süzülebilsin
        "odalar": [{"oda_id": 2, "oda_adi": "Oda-2", "aktif_mi": True}, {"oda_id": 4, "oda_adi": "Oda-4 (pasif)", "aktif_mi": False}],
    }
    psikolog_sql, oda_sql = sorgular[0][0], sorgular[1][0]
    assert "FROM randevular x WHERE x.psikolog_id = p.personel_id" in psikolog_sql           # randevusu olan eski psikolog da gelir
    assert "psikolog_odalar" in oda_sql and "o.aktif_mi = TRUE" in oda_sql and "UPPER(r.rol_adi) = 'PSIKOLOG'" in oda_sql
    assert "FROM randevular x" in oda_sql and "x.oda_id = o.oda_id" in oda_sql                 # randevu yapılmış oda da gelir
    assert sorgular[1][1] == ()                                                           # psikolog seçilmediyse tümü


def test_secenekler_psikolog_secilince_odalar_daralir_psikolog_yalnizca_kendini_gorur(istemci):
    _, sorgular = _secenekler(istemci, "?psikolog_id=7")
    assert "p.personel_id = %s" in sorgular[1][0] and sorgular[1][1] == (7, 7)          # iki alt sorgu (atanmış oda, randevu yapılmış oda)
    _, sorgular = _secenekler(istemci, "?psikolog_id=7", rol="PSIKOLOG")
    assert "p.kullanici_id = %s" in sorgular[1][0] and "p.personel_id = %s" not in sorgular[1][0] and sorgular[1][1] == (5, 5)
    assert "p.kullanici_id = %s" in sorgular[0][0] and sorgular[0][1] == (5,)             # psikolog listesinde de yalnızca kendisi


# ------------------------------------------------------------------ Excel
def test_excel_dort_sayfa_ve_icerik(tmp_path):
    veri = randevu_raporu_hesapla(ORNEK, ETIKETLER, detay=True)
    yol = tmp_path / "rapor.xlsx"
    excel_dosyasi_olustur(veri, [("Dönem", "01.11.2026 - 30.11.2026"), ("Psikolog", "Tümü"), ("Oda", "Tümü")], str(yol))
    kitap = load_workbook(yol)
    assert kitap.sheetnames == ["Özet", "Psikolog Bazlı", "Dağılımlar", "Randevu Detayı"]
    ozet = {r[0].value: r[1].value for r in kitap["Özet"].iter_rows() if r[0].value}
    assert ozet["Toplam randevu"] == 9 and ozet["Tamamlanan"] == 3 and ozet["Tamamlanma oranı"] == 0.75
    psikolog = [[h.value for h in r] for r in kitap["Psikolog Bazlı"].iter_rows(min_row=2)]
    assert psikolog[0][:2] == ["Ayşe", 7] and psikolog[1][:2] == ["Fatma", 2]
    dagilim = [[h.value for h in r] for r in kitap["Dağılımlar"].iter_rows(min_row=2)]
    assert ["İptal nedeni (iptal edilenler)", "Danışan talebi", 2, 0.5] in dagilim
    detay = [[h.value for h in r] for r in kitap["Randevu Detayı"].iter_rows(min_row=1)]
    assert detay[0] == ["Randevu ID", "Tarih", "Saat", "Danışan Kodu", "Psikolog", "Oda", "Görüşme", "Terapi", "Yaş Grubu", "Durum", "İptal Nedeni"]
    assert len(detay) == 10 and detay[1][2] == "10:00 – 11:00" and detay[6][9] == "İptal Edildi" and detay[6][10] == "Danışan talebi"


def test_excel_bos_rapor_ve_formul_benzeri_metinler(tmp_path):
    veri = randevu_raporu_hesapla([satir(1, "TAMAMLANDI", ad="=HYPERLINK(\"x\")")], ETIKETLER, detay=True)
    yol = tmp_path / "r.xlsx"
    excel_dosyasi_olustur(veri, [], str(yol))
    hucre = load_workbook(yol)["Randevu Detayı"]["E2"]
    assert hucre.data_type == "s" and hucre.quotePrefix                                    # formül olarak çalışmaz
    excel_dosyasi_olustur(randevu_raporu_hesapla([], ETIKETLER, detay=True), [], str(tmp_path / "bos.xlsx"))


# ------------------------------------------------------------------ ekran
class Sunucu:
    def __init__(self, rapor=None):
        self.rapor = rapor or randevu_raporu_hesapla(ORNEK, ETIKETLER, detay=True)
        self.istekler = []

    def __call__(self, yontem, url, **kwargs):
        self.istekler.append((url, kwargs.get("params") or {}))
        if url.endswith("/api/randevu-raporu/secenekler"):
            psikolog = (kwargs.get("params") or {}).get("psikolog_id")
            odalar = [{"oda_id": 2, "oda_adi": "Oda-2"}, {"oda_id": 5, "oda_adi": "Oda-5"}]
            veri = {"psikologlar": [{"personel_id": 3, "ad_soyad": "Ayşe"}, {"personel_id": 7, "ad_soyad": "Fatma"}],
                    "odalar": [o for o in odalar if o["oda_id"] == 5] if psikolog == 7 else odalar}      # psikolog seçilince odalar daralır
        else:
            veri = self.rapor
        return SimpleNamespace(status_code=200, json=lambda: veri, raise_for_status=lambda: None)   # MagicMock "oturum reddedildi" sanılır


@pytest.fixture
def ekran_ac(tkys_qapplication):
    acilanlar = []

    def ac(psikolog_mu=False, sunucu=None):
        sunucu = sunucu or Sunucu()
        with patch.object(ekranmodulu, "oturum_kontrollu_istek", side_effect=sunucu):
            ekran = RandevuRaporlariEkrani("http://x", "T", psikolog_mu=psikolog_mu)
            ekran._sunucu = sunucu
            acilanlar.append(ekran)
            return ekran, sunucu

    yield ac
    for e in acilanlar:
        e.close()


def test_ekran_kartlar_ve_tablolar_dolar(ekran_ac):
    ekran, _ = ekran_ac()
    deger = lambda anahtar: ekran.kartlar[anahtar][0].text()
    assert [deger(k) for k in ("toplam", "tamamlandi", "gelmedi", "iptal")] == ["9", "3", "1", "4"]
    assert "%75" in ekran.kartlar["tamamlandi"][1].text() and "%25" in ekran.kartlar["gelmedi"][1].text()
    assert [ekran.tablo_psikolog.item(i, 0).text() for i in range(ekran.tablo_psikolog.rowCount())] == ["Ayşe", "Fatma"]
    assert ekran.tablo_neden.item(0, 0).text() == "Danışan talebi" and ekran.tablo_neden.item(0, 2).text() == "%50"
    assert ekran.tablo_gorusme.rowCount() == 2 and ekran.tablo_yas.rowCount() == 3
    assert ekran.excel_btn.isEnabled()


def test_ekran_suzgec_listeleri_ve_istek_parametreleri(ekran_ac):
    ekran, sunucu = ekran_ac()
    adlar = lambda kutu: [kutu.itemText(i) for i in range(kutu.count())]
    assert adlar(ekran.psikolog_sec) == ["Tümü", "Ayşe", "Fatma"]
    assert adlar(ekran.oda_sec) == ["Tümü", "Oda-2", "Oda-5"]            # yalnızca psikologlara atanmış odalar (sunucu süzer)
    with patch.object(ekranmodulu, "oturum_kontrollu_istek", side_effect=sunucu):
        ekran.psikolog_sec.setCurrentIndex(2)                             # Fatma (id 7)
        assert adlar(ekran.oda_sec) == ["Tümü", "Oda-5"]                 # oda listesi o psikologun odalarına daralır
        assert sunucu.istekler[-2][1] == {"psikolog_id": 7}
        ekran.oda_sec.setCurrentIndex(1)
        ekran.donem.setCurrentText("Tümü")
        params = [p for u, p in sunucu.istekler if u.endswith("/api/randevu-raporu")][-1]
        assert params == {"psikolog_id": 7, "oda_id": 5}                   # tüm tarihlerde tarih parametresi yok
        ekran.psikolog_sec.setCurrentIndex(0)                              # Tümü'ne dönünce oda listesi yeniden genişler
        assert adlar(ekran.oda_sec) == ["Tümü", "Oda-2", "Oda-5"] and ekran.oda_sec.currentData() == 5   # geçerli oda seçimi korunur
        ekran.donem.setCurrentText("Bu Yıl")
        assert ekran._parametreler()["baslangic"].endswith("-01-01") and ekran._parametreler()["bitis"].endswith("-12-31")


def test_psikolog_hesabinda_psikolog_suzgeci_gizli_ve_gonderilmez(ekran_ac):
    ekran, sunucu = ekran_ac(psikolog_mu=True)
    assert not ekran.psikolog_sec.isVisibleTo(ekran) and not ekran.etiket_psikolog.isVisibleTo(ekran)
    assert not any(u.endswith("/api/psikologlar") for u, _ in sunucu.istekler)
    assert ekran.psikolog_sec.count() == 1                                  # psikolog listesi doldurulmaz
    assert "psikolog_id" not in ekran._parametreler()
    assert dict(ekran._son_filtre)["Psikolog"] == "Yalnızca kendi randevularınız"


def test_rapor_kendiliginden_yenilenir_raporu_getir_dugmesi_yok_ve_arayuz_sikismaz(ekran_ac):
    ekran, sunucu = ekran_ac()
    assert not hasattr(ekran, "yenile_btn") and ekran.excel_btn.minimumWidth() >= 150
    assert ekran.kartlar["iptal"][1].text() == ""                           # iptal kartında açıklama yazısı yok
    for ad in ("etiket_baslangic", "baslangic", "etiket_bitis", "bitis"):  # tarih kutuları yalnızca "Tarih Aralığı"nda görünür
        assert not getattr(ekran, ad).isVisibleTo(ekran), ad
    sayi = len([u for u, _ in sunucu.istekler if u.endswith("/api/randevu-raporu")])
    with patch.object(ekranmodulu, "oturum_kontrollu_istek", side_effect=sunucu):
        ekran.donem.setCurrentText("Tarih Aralığı")                        # süzgeç değişince rapor kendiliğinden gelir
    assert len([u for u, _ in sunucu.istekler if u.endswith("/api/randevu-raporu")]) == sayi + 1
    for ad in ("etiket_baslangic", "baslangic", "etiket_bitis", "bitis"):
        assert getattr(ekran, ad).isVisibleTo(ekran), ad


def test_gecersiz_tarih_araligi_uyarir_istek_atmaz(ekran_ac):
    ekran, sunucu = ekran_ac()
    with patch.object(QMessageBox, "warning") as uyari, patch.object(ekranmodulu, "oturum_kontrollu_istek", side_effect=sunucu):
        ekran.donem.setCurrentText("Tarih Aralığı")
        sayi = len(sunucu.istekler)
        ekran.baslangic.setDate(ekran.bitis.date().addDays(3))
    uyari.assert_called()
    assert len(sunucu.istekler) == sayi


def test_excel_aktar_dosyayi_yazar(ekran_ac, tmp_path):
    ekran, sunucu = ekran_ac()
    yol = str(tmp_path / "cikti.xlsx")
    with patch.object(QFileDialog, "getSaveFileName", return_value=(yol, "")), patch.object(QMessageBox, "information"), \
            patch.object(ekranmodulu, "oturum_kontrollu_istek", side_effect=sunucu):
        ekran.excel_aktar()
    assert os.path.exists(yol) and load_workbook(yol).sheetnames[0] == "Özet"
    assert sunucu.istekler[-1][1].get("detay") == "true"                                  # ayrıntı sayfası için kayıt kayıt veri istenir
    with patch.object(QFileDialog, "getSaveFileName", return_value=("", "")), patch.object(ekranmodulu, "oturum_kontrollu_istek", side_effect=sunucu):
        sayi = len(sunucu.istekler)
        ekran.excel_aktar()                                                                # vazgeçilirse istek atılmaz
        assert len(sunucu.istekler) == sayi


def test_yuzde_metni():
    assert yuzde_metni(None) == "—" and yuzde_metni(0.4) == "%40" and yuzde_metni(0.3333) == "%33,3" and yuzde_metni(0) == "%0"


# ------------------------------------------------------------------ menü
def test_menude_randevu_raporlari_mevcut_izinle_ve_simgeli():
    sayfalar = {oge["ad"]: oge for _, ogeler in main_window.MENU for oge in ogeler}
    oge = sayfalar["Randevu Raporları"]
    assert oge["izin"] == "Randevu takvimini görüntüleme"
    assert "Randevu Raporları" in tkys_sidebar_refined.PAGE_ICONS
    assert "Randevu Raporları" in main_window.AnaPencere.SAYFA_YENILEME
