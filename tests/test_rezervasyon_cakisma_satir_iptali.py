"""Rezervasyon çakışması: sunucu 409 + liste döner (kendiliğinden iptal etmez); istemci çakışan
rezervasyonları satır satır gösterir, kullanıcı isterse tek tek iptal eder.

Gerçek API veya PostgreSQL kullanılmaz.
"""
import datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QPushButton

import cihaz_bakim_ekranlari
import cihaz_kalibrasyon_ekranlari
import cihaz_rezervasyon_ekranlari
import rezervasyon_cakisma_uyarisi as uyari
from modeller import (
    BakimGuncelleModeli, BakimOlusturModeli, KalibrasyonGuncelleModeli,
    KalibrasyonOlusturModeli, RezervasyonOlusturModeli,
)
from sunucu import (
    bakim_guncelle, bakim_kaydi_ekle, cihaz_rezervasyonu_yap, kalibrasyon_guncelle,
    kalibrasyon_kaydi_ekle,
)

D = datetime.date
REZ = [
    (11, datetime.datetime(2026, 11, 10, 10, 0), datetime.datetime(2026, 11, 10, 11, 0), "ali"),
    (12, datetime.datetime(2026, 11, 11, 14, 0), datetime.datetime(2026, 11, 11, 15, 0), "ayse"),
]


def baglanti(fetchall, fetchone=None):
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchall.return_value = fetchall
    cursor.fetchone.side_effect = fetchone if fetchone is not None else [(501,)]
    return conn, cursor


def sorgular(cursor):
    return [" ".join(c.args[0].split()).upper() for c in cursor.execute.call_args_list]


def bakim():
    return BakimOlusturModeli(
        cihaz_id=7, bakim_tarihi=D(2026, 11, 9), bakim_yapan_kisi="x", yapilan_islem="y",
        bakim_baslangic_tarihi=D(2026, 11, 9), bakim_bitis_tarihi=D(2026, 11, 12),
    )


def kalibrasyon():
    return KalibrasyonOlusturModeli(
        cihaz_id=7, kalibrasyon_yapan_kurum="k", gecerlilik_tarihi=D(2027, 11, 12), sertifika_no="s",
        kalibrasyon_baslangic_tarihi=D(2026, 11, 9), kalibrasyon_bitis_tarihi=D(2026, 11, 12),
    )


EKLEME = [(bakim_kaydi_ekle, bakim, "CIHAZ_BAKIMLARI"), (kalibrasyon_kaydi_ekle, kalibrasyon, "CIHAZ_KALIBRASYONLARI")]


# ------------------------------------------------------------------ sunucu: ekleme
@pytest.mark.parametrize("fonk, model, tablo", EKLEME)
def test_cakisma_varsa_liste_doner_kayit_yapilmaz_rezervasyon_iptal_edilmez(fonk, model, tablo):
    conn, cursor = baglanti(REZ)
    with patch("sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            fonk(model(), 3)
    assert hata.value.status_code == 409
    detay = hata.value.detail
    assert detay["kod"] == "REZERVASYON_CAKISMASI"
    assert [r["rezerve_eden"] for r in detay["rezervasyonlar"]] == ["ali", "ayse"]
    assert detay["rezervasyonlar"][0] == {
        "rezervasyon_id": 11, "baslangic": "2026-11-10T10:00:00",
        "bitis": "2026-11-10T11:00:00", "rezerve_eden": "ali",
    }
    assert not any(s.startswith("INSERT INTO " + tablo) for s in sorgular(cursor))
    assert not any(s.startswith("UPDATE CIHAZ_REZERVASYONLARI") for s in sorgular(cursor))   # sunucu iptal etmez
    conn.commit.assert_not_called()
    conn.rollback.assert_called()


@pytest.mark.parametrize("fonk, model, tablo", EKLEME)
def test_cakisma_yoksa_kayit_yapilir(fonk, model, tablo):
    conn, cursor = baglanti([])
    with patch("sunucu.psycopg2.connect", return_value=conn), patch("denetim.denetim_kaydi_olustur"):
        sonuc = fonk(model(), 3)
    assert sonuc["durum"] == "basarili"
    assert any(s.startswith("INSERT INTO " + tablo) for s in sorgular(cursor))


def test_sorgu_bitmis_rezervasyonlara_dokunmaz_ve_bitis_gununu_dahil_eder():
    conn, cursor = baglanti([])
    with patch("sunucu.psycopg2.connect", return_value=conn), patch("denetim.denetim_kaydi_olustur"):
        bakim_kaydi_ekle(bakim(), 3)
    sorgu = [c for c in cursor.execute.call_args_list if "FROM cihaz_rezervasyonlari" in c.args[0]][0]
    assert "bitis_zamani > NOW()" in sorgu.args[0] and "+ 1" in sorgu.args[0]
    assert sorgu.args[1] == (7, D(2026, 11, 12), D(2026, 11, 9))


# ---------------------------------------------------------------- sunucu: güncelleme
def test_bakim_tarihi_degisince_yeni_aralik_icin_liste_doner():
    conn, cursor = baglanti(REZ, fetchone=[(1,), (7, D(2026, 11, 1), D(2026, 11, 2))])
    with patch("sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            bakim_guncelle(5, BakimGuncelleModeli(bakim_bitis_tarihi=D(2026, 11, 12)), 3)
    assert hata.value.status_code == 409
    sorgu = [c for c in cursor.execute.call_args_list if "FROM cihaz_rezervasyonlari" in c.args[0]][0]
    assert sorgu.args[1] == (7, D(2026, 11, 12), D(2026, 11, 1))     # başlangıç mevcut kayıttan
    assert not any(s.startswith("UPDATE CIHAZ_BAKIMLARI") for s in sorgular(cursor))


def test_tarih_degismediyse_veya_alan_tarih_degilse_sorulmaz():
    conn, cursor = baglanti(REZ, fetchone=[(1,)])
    with patch("sunucu.psycopg2.connect", return_value=conn), patch("sunucu.denetim_kaydi_olustur"):
        bakim_guncelle(5, BakimGuncelleModeli(yapilan_islem="yeni not"), 3)
    assert not any("CIHAZ_REZERVASYONLARI" in s for s in sorgular(cursor))

    # Formlar tarihleri hep gönderir: değerler aynıysa yine sorulmaz.
    conn, cursor = baglanti(REZ, fetchone=[(1,), (7, D(2026, 11, 1), D(2026, 11, 2))])
    model = BakimGuncelleModeli(bakim_baslangic_tarihi=D(2026, 11, 1), bakim_bitis_tarihi=D(2026, 11, 2))
    with patch("sunucu.psycopg2.connect", return_value=conn), patch("sunucu.denetim_kaydi_olustur"):
        bakim_guncelle(5, model, 3)
    assert not any("FROM CIHAZ_REZERVASYONLARI" in s for s in sorgular(cursor))


def test_kalibrasyon_tarihi_degisince_sorulur_ve_eski_bos_kayitta_atlanir():
    conn, cursor = baglanti(REZ, fetchone=[(1,), (7, D(2026, 11, 1), D(2026, 11, 2))])
    with patch("sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            kalibrasyon_guncelle(5, KalibrasyonGuncelleModeli(kalibrasyon_bitis_tarihi=D(2026, 11, 12)), 3)
    assert hata.value.detail["kod"] == "REZERVASYON_CAKISMASI"

    conn, cursor = baglanti(REZ, fetchone=[(1,), (7, None, None)])
    with patch("sunucu.psycopg2.connect", return_value=conn), patch("sunucu.denetim_kaydi_olustur"):
        kalibrasyon_guncelle(5, KalibrasyonGuncelleModeli(kalibrasyon_bitis_tarihi=D(2026, 11, 12)), 3)
    assert not any("FROM CIHAZ_REZERVASYONLARI" in s for s in sorgular(cursor))


# ----------------------------------------------- sunucu: yeni rezervasyon aynı saate denk gelirse
def test_dolu_saate_rezervasyonda_cakisan_rezervasyonlar_listelenir():
    conn, cursor = baglanti(REZ[:1], fetchone=[("Kullanima_Hazir",), None, (1,)])
    # Sunucu geçmiş zamanlı rezervasyonu reddeder; bu yüzden zaman her zaman gelecekte olmalı (sabit tarih zamanla bozulur).
    gelecek = (datetime.datetime.now() + datetime.timedelta(days=7)).replace(hour=10, minute=30, second=0, microsecond=0)
    rez = RezervasyonOlusturModeli(
        cihaz_id=7, baslangic_zamani=gelecek.isoformat(), bitis_zamani=(gelecek + datetime.timedelta(hours=1)).isoformat()
    )
    with patch("sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            cihaz_rezervasyonu_yap(rez, 3)
    assert hata.value.status_code == 409
    assert hata.value.detail["kod"] == "REZERVASYON_CAKISMASI"
    assert hata.value.detail["rezervasyonlar"][0]["rezervasyon_id"] == 11
    assert hata.value.detail["rezervasyonlar"][0]["rezerve_eden"] == "ali"
    conn.commit.assert_not_called()


# ------------------------------------------------------------------ istemci yardımcıları
def cevap(durum, veri=None):
    r = MagicMock()
    r._tkys_oturum_reddedildi = False
    r.status_code = durum
    r.json.return_value = veri if veri is not None else {}
    return r


ISTEMCI_REZ = [
    {"rezervasyon_id": 11, "baslangic": "2026-11-10T10:00:00", "bitis": "2026-11-10T11:00:00", "rezerve_eden": "ali"},
    {"rezervasyon_id": 12, "baslangic": "2026-11-11T14:00:00", "bitis": "2026-11-11T15:00:00", "rezerve_eden": "ayse"},
]
CAKISMA_YANITI = {"detail": {"kod": "REZERVASYON_CAKISMASI", "mesaj": "m", "rezervasyonlar": ISTEMCI_REZ}}


def test_zaman_araligi_ayni_gun_ve_gunler_arasi():
    assert uyari.zaman_araligi("2026-11-10T10:00:00", "2026-11-10T11:30:00") == "10.11.2026 10:00 – 11:30"
    assert uyari.zaman_araligi("2026-11-10T22:00:00", "2026-11-11T02:00:00") == "10.11.2026 22:00 – 11.11.2026 02:00"


def test_cakisan_rezervasyonlar_yalniz_cakisma_409unu_taniyor():
    assert uyari.cakisan_rezervasyonlar(cevap(409, CAKISMA_YANITI)) == ISTEMCI_REZ
    assert uyari.cakisan_rezervasyonlar(cevap(409, {"detail": "Başka hata"})) is None
    assert uyari.cakisan_rezervasyonlar(cevap(400, CAKISMA_YANITI)) is None


@pytest.mark.parametrize("durum, basarili, mesaj_parcasi", [
    (200, True, None), (404, True, None), (403, False, "yetkiniz yok"), (500, False, "iptal edilemedi"),
])
def test_rezervasyon_iptali_sonuclari(durum, basarili, mesaj_parcasi):
    with patch.object(uyari, "oturum_kontrollu_istek", return_value=cevap(durum)) as istek:
        ok, mesaj = uyari.rezervasyonu_iptal_et("http://x", "T", 11)
    assert ok is basarili
    assert (mesaj is None) if mesaj_parcasi is None else (mesaj_parcasi in mesaj)
    assert istek.call_args.args == ("PATCH", "http://x/api/rezervasyonlar/11/iptal")
    assert istek.call_args.kwargs["headers"] == {"Authorization": "Bearer T"}


def test_rezervasyon_iptali_sunucuya_ulasilamazsa_cokmez():
    with patch.object(uyari, "oturum_kontrollu_istek", side_effect=OSError("yok")):
        ok, mesaj = uyari.rezervasyonu_iptal_et("http://x", "T", 11)
    assert ok is False and "ulaşılamadı" in mesaj


# ----------------------------------------------------------------------- pencere
@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def pencere(qt_app):
    p = uyari.CakisanRezervasyonlarDialog(
        None, ISTEMCI_REZ, "http://x", "T", "Bu saat dolu", "açıklama", "Rezervasyonu yeniden dene"
    )
    yield p
    p.close()
    p.deleteLater()


def iptal_dugmeleri(p):
    return [b for b in p.findChildren(QPushButton) if b.text() == "Rezervasyonu iptal et"]


def test_pencere_her_rezervasyonu_ayri_satirda_ve_devam_kapali_baslar(pencere):
    assert pencere.kalan() == 2
    assert len(iptal_dugmeleri(pencere)) == 2
    assert not pencere.btn_devam.isEnabled()
    assert pencere.btn_devam.text() == "Rezervasyonu yeniden dene"
    assert "2 rezervasyonu iptal edin" in pencere.lbl_ipucu.text()


def test_onaylanan_iptal_satiri_kaldirir_hepsi_bitince_devam_acilir(pencere):
    with patch.object(uyari.QMessageBox, "question", return_value=QMessageBox.Yes), \
         patch.object(uyari, "rezervasyonu_iptal_et", return_value=(True, None)) as iptal:
        iptal_dugmeleri(pencere)[0].click()
        assert pencere.kalan() == 1 and not pencere.btn_devam.isEnabled()
        iptal_dugmeleri(pencere)[0].click()
    assert [c.args[2] for c in iptal.call_args_list] == [11, 12]
    assert pencere.kalan() == 0
    assert pencere.btn_devam.isEnabled()
    assert "devam edebilirsiniz" in pencere.lbl_ipucu.text()


def test_onay_sorusuna_hayir_denirse_iptal_edilmez(pencere):
    with patch.object(uyari.QMessageBox, "question", return_value=QMessageBox.No), \
         patch.object(uyari, "rezervasyonu_iptal_et") as iptal:
        iptal_dugmeleri(pencere)[0].click()
    iptal.assert_not_called()
    assert pencere.kalan() == 2


def test_iptal_basarisizsa_satir_kalir_ve_hata_gosterilir(pencere):
    with patch.object(uyari.QMessageBox, "question", return_value=QMessageBox.Yes), \
         patch.object(uyari, "rezervasyonu_iptal_et", return_value=(False, "yetkiniz yok")), \
         patch.object(uyari.QMessageBox, "warning") as uyar:
        iptal_dugmeleri(pencere)[0].click()
    assert pencere.kalan() == 2
    assert "yetkiniz yok" in uyar.call_args.args[2]


def test_onay_sorusu_kimin_hangi_rezervasyonu_oldugunu_soyler(pencere):
    with patch.object(uyari.QMessageBox, "question", return_value=QMessageBox.No) as soru:
        iptal_dugmeleri(pencere)[1].click()
    metin = soru.call_args.args[2]
    assert "ayse" in metin and "11.11.2026 14:00 – 15:00" in metin and "denetim" in metin


# ------------------------------------------------------------ cakisma_cozumlu_istek
def istek_cagir(**ek):
    return uyari.cakisma_cozumlu_istek(
        None, "POST", "http://x/api/rezervasyonlar", {"a": 1}, {"Authorization": "Bearer T"},
        "Bu saat dolu", "açıklama", "Yeniden dene", **ek,
    )


def test_cakisma_yoksa_yanit_aynen_doner_pencere_acilmaz():
    with patch.object(uyari, "oturum_kontrollu_istek", return_value=cevap(201)) as istek, \
         patch.object(uyari, "CakisanRezervasyonlarDialog") as pen:
        assert istek_cagir().status_code == 201
    istek.assert_called_once()
    pen.assert_not_called()


def test_baska_409_hatasi_pencere_acmadan_doner():
    with patch.object(uyari, "oturum_kontrollu_istek", return_value=cevap(409, {"detail": "Başka"})), \
         patch.object(uyari, "CakisanRezervasyonlarDialog") as pen:
        assert istek_cagir().status_code == 409
    pen.assert_not_called()


def test_cakisma_cozulunce_istek_ayni_verilerle_yeniden_denenir():
    ikinci = cevap(201)
    with patch.object(uyari, "oturum_kontrollu_istek", side_effect=[cevap(409, CAKISMA_YANITI), ikinci]) as istek, \
         patch.object(uyari, "CakisanRezervasyonlarDialog") as pen:
        pen.return_value.exec.return_value = QDialog.Accepted
        sonuc = istek_cagir()
    assert sonuc is ikinci
    assert [c.kwargs["json"] for c in istek.call_args_list] == [{"a": 1}, {"a": 1}]   # bayrak/ek alan yok
    args = pen.call_args.args
    assert args[1] == ISTEMCI_REZ and args[2] == "http://x" and args[3] == "T"


def test_kullanici_vazgecerse_yeniden_denenmez_ve_none_doner():
    with patch.object(uyari, "oturum_kontrollu_istek", return_value=cevap(409, CAKISMA_YANITI)) as istek, \
         patch.object(uyari, "CakisanRezervasyonlarDialog") as pen:
        pen.return_value.exec.return_value = QDialog.Rejected
        assert istek_cagir() is None
    assert istek.call_count == 1


def test_surekli_yeni_cakisma_cikarsa_sonsuz_donguye_girilmez():
    with patch.object(uyari, "oturum_kontrollu_istek", return_value=cevap(409, CAKISMA_YANITI)) as istek, \
         patch.object(uyari, "CakisanRezervasyonlarDialog") as pen:
        pen.return_value.exec.return_value = QDialog.Accepted
        sonuc = istek_cagir()
    assert istek.call_count == uyari.EN_FAZLA_DENEME and sonuc.status_code == 409


def test_oturum_bitmisse_pencere_acilmaz():
    bitmis = cevap(401)
    bitmis._tkys_oturum_reddedildi = True
    with patch.object(uyari, "oturum_kontrollu_istek", return_value=bitmis), \
         patch.object(uyari, "CakisanRezervasyonlarDialog") as pen:
        assert istek_cagir() is bitmis
    pen.assert_not_called()


# ------------------------------------------------------------------ istemci: formlar
@pytest.mark.parametrize("modul, sinif, yontem, adres_parcasi, ek_arg", [
    (cihaz_bakim_ekranlari, "YeniBakimFormu", "POST", "/api/bakimlar", ()),
    (cihaz_kalibrasyon_ekranlari, "YeniKalibrasyonFormu", "POST", "/api/kalibrasyonlar", ()),
    (cihaz_bakim_ekranlari, "BakimDuzenleFormu", "PUT", "/api/bakimlar/9", ({"bakim_id": 9, "cihaz_adi": "E1 - C"},)),
    (cihaz_kalibrasyon_ekranlari, "KalibrasyonDuzenleFormu", "PUT", "/api/kalibrasyonlar/9", ({"kalibrasyon_id": 9, "cihaz_adi": "E1 - C"},)),
])
def test_bakim_ve_kalibrasyon_formlari_cakisma_cozumlu_istek_kullanir(qt_app, modul, sinif, yontem, adres_parcasi, ek_arg):
    with patch.object(modul, "oturum_kontrollu_istek", return_value=cevap(200, [])):
        form = getattr(modul, sinif)("http://x", "T", *ek_arg)
    for alan, deger in (("txt_kisi", "kişi"), ("txt_kurum", "kurum"), ("txt_sertifika", "no")):
        if hasattr(form, alan):
            getattr(form, alan).setText(deger)
    if hasattr(form, "txt_islem"):
        form.txt_islem.setPlainText("işlem")
    with patch.object(modul, "cakisma_cozumlu_istek", return_value=None) as gonder:
        form.kaydet()                       # kullanıcı vazgeçti -> form açık kalır, hata penceresi çıkmaz
    assert gonder.call_args.args[1] == yontem
    assert gonder.call_args.args[2] == "http://x" + adres_parcasi
    assert gonder.call_args.args[5] in ("Bu tarihlerde rezervasyon var",)
    assert gonder.call_args.args[7] in ("Bakımı kaydet", "Kalibrasyonu kaydet")
    assert form.result() == 0
    form.close()


def test_rezervasyon_formu_cakisma_cozumlu_istek_kullanir(qt_app):
    modul = cihaz_rezervasyon_ekranlari
    sinif = [n for n in dir(modul) if n.endswith("Formu") and "Rezervasyon" in n]
    assert sinif, "rezervasyon formu bulunamadı"
    assert "cakisma_cozumlu_istek" in open(modul.__file__, encoding="utf-8").read()
    assert modul.REZERVASYON_CAKISMA_METINLERI[0] == "Bu saat dolu"
    assert modul.REZERVASYON_CAKISMA_METINLERI[2] == "Rezervasyonu yeniden dene"
