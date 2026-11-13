"""
PR2: randevu iptal nedeni (hazır liste + kısa not) ve gerçek Tamamlandı/Gelmedi durumları.

- İptalde neden zorunlu; "Diğer" için kısa not zorunlu; not en çok 100 karakter; bilinmeyen alan reddedilir (FR-008).
- Tamamlandı/Gelmedi yalnızca başlangıcı geçmiş randevuya; psikolog yalnızca kendininkine; iptal edilmişe yapılamaz.
- Randevu Yönetimi: iptal penceresi, Tamamlandı/Gelmedi düğmeleri, seçili iptal satırında neden bilgi satırı.
- Danışanlar sayfasındaki sekme adı "Randevular".

Tarihler "şimdi"ye göre üretilir.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

import iptal_nedeni_diyalog as diyalog
import main_window as mw
import modeller
import randevu_ekranlari as modul
from iptal_nedeni_diyalog import IPTAL_NEDENLERI, IPTAL_NOTU_MAX, IptalNedeniDialog, iptal_girdisi_gecerli_mi
from modeller import RandevuDurumModeli, RandevuIptalModeli
from randevu_ekranlari import RandevuAnaEkrani, iptal_bilgisi_metni
from sunucu import app, mevcut_kullanici_id


# ------------------------------------------------------------------ model ve liste
def test_istemci_ve_sunucu_neden_listeleri_ayni():
    assert dict(IPTAL_NEDENLERI) == modeller.IPTAL_NEDENLERI
    assert [k for k, _ in IPTAL_NEDENLERI] == list(modeller.IPTAL_NEDENLERI)
    assert IPTAL_NOTU_MAX == modeller.IPTAL_NOTU_MAX == 100
    assert "KURUM_KAPALI" not in modeller.IPTAL_NEDENLERI                     # kaldırılan neden


def test_iptal_modeli_gecerli_girdiler():
    assert RandevuIptalModeli(iptal_nedeni="DANISAN_TALEBI").iptal_notu is None
    m = RandevuIptalModeli(iptal_nedeni="HATALI_KAYIT", iptal_notu="  yanlış gün  ")
    assert m.iptal_notu == "yanlış gün"                                       # boşluklar kırpılır
    assert RandevuIptalModeli(iptal_nedeni="PSIKOLOG_MAZERETI", iptal_notu="   ").iptal_notu is None
    assert RandevuIptalModeli(iptal_nedeni="DIGER", iptal_notu="x" * 100).iptal_notu == "x" * 100


@pytest.mark.parametrize("veri", [
    {},                                                                       # neden zorunlu
    {"iptal_nedeni": "KURUM_KAPALI"},                                         # listede olmayan
    {"iptal_nedeni": "DIGER"},                                                # Diğer notsuz
    {"iptal_nedeni": "DIGER", "iptal_notu": "   "},                           # Diğer, yalnızca boşluk
    {"iptal_nedeni": "DANISAN_TALEBI", "iptal_notu": "x" * 101},              # not çok uzun
    {"iptal_nedeni": "DANISAN_TALEBI", "ad_soyad": "Ali Veli"},               # bilinmeyen (kişisel) alan
])
def test_iptal_modeli_gecersiz_girdileri_reddeder(veri):
    with pytest.raises(ValidationError):
        RandevuIptalModeli(**veri)


@pytest.mark.parametrize("durum", ["PLANLANDI", "IPTAL_EDILDI", "tamamlandi", ""])
def test_durum_modeli_yalniz_tamamlandi_ve_gelmedi_kabul_eder(durum):
    with pytest.raises(ValidationError):
        RandevuDurumModeli(durum=durum)
    assert RandevuDurumModeli(durum="TAMAMLANDI").durum == "TAMAMLANDI"
    assert RandevuDurumModeli(durum="GELMEDI").durum == "GELMEDI"


# ------------------------------------------------------------------ sunucu uçları
@pytest.fixture
def istemci():
    app.dependency_overrides[mevcut_kullanici_id] = lambda: 5
    yield TestClient(app)
    app.dependency_overrides.pop(mevcut_kullanici_id, None)


def _iptal(istemci, govde, randevu=(3, "PLANLANDI"), rol="ADMIN", personel=(3,)):
    conn = MagicMock()
    c = conn.cursor.return_value
    sirali = [(1,), randevu, (rol,)]
    if rol == "PSIKOLOG":
        sirali.append(personel)
    c.fetchone.side_effect = sirali
    with patch("sunucu.psycopg2.connect", return_value=conn):
        yanit = istemci.patch("/api/randevular/7/iptal", json=govde)
    guncelleme = next((x.args[1] for x in c.execute.call_args_list if x.args[0].startswith("UPDATE randevular")), None)
    return yanit, guncelleme, conn


def test_iptal_nedenle_yapilir_ve_veritabanina_yazilir(istemci):
    yanit, guncelleme, conn = _iptal(istemci, {"iptal_nedeni": "DIGER", "iptal_notu": " kurum içi görev "})
    assert yanit.status_code == 200
    assert guncelleme == ("DIGER", "kurum içi görev", 7)
    conn.commit.assert_called_once()


def test_iptal_nedensiz_ya_da_govdesiz_422_ve_yazmaz(istemci):
    conn = MagicMock()
    conn.cursor.return_value.fetchone.return_value = (1,)
    with patch("sunucu.psycopg2.connect", return_value=conn):
        assert istemci.patch("/api/randevular/7/iptal").status_code == 422
        assert istemci.patch("/api/randevular/7/iptal", json={}).status_code == 422
        assert istemci.patch("/api/randevular/7/iptal", json={"iptal_nedeni": "DIGER"}).status_code == 422
    conn.commit.assert_not_called()


def test_planli_olmayan_randevu_iptal_edilemez_409(istemci):
    yanit, guncelleme, _ = _iptal(istemci, {"iptal_nedeni": "HATALI_KAYIT"}, randevu=(3, "TAMAMLANDI"))
    assert yanit.status_code == 409 and guncelleme is None


def _isaretle(istemci, durum, mevcut, rol="ADMIN", personel=(3,), yol="/api/randevular/7/durum"):
    conn = MagicMock()
    c = conn.cursor.return_value
    sirali = [(1,), mevcut, (rol,)]
    if rol == "PSIKOLOG":
        sirali.append(personel)
    c.fetchone.side_effect = sirali
    with patch("sunucu.psycopg2.connect", return_value=conn):
        yanit = istemci.patch(yol, json={"durum": durum})
    sorgular = [(x.args[0], x.args[1] if len(x.args) > 1 else None) for x in c.execute.call_args_list]
    return yanit, sorgular, conn


GECMIS = datetime.now() - timedelta(days=2)
GELECEK = datetime.now() + timedelta(days=2)


@pytest.mark.parametrize("onceki, yeni", [("PLANLANDI", "TAMAMLANDI"), ("PLANLANDI", "GELMEDI"),
                                          ("TAMAMLANDI", "GELMEDI"), ("GELMEDI", "TAMAMLANDI")])
def test_gecmis_randevu_isaretlenir_ve_duzeltilebilir(istemci, onceki, yeni):
    yanit, sorgular, conn = _isaretle(istemci, yeni, (3, onceki, GECMIS))
    assert yanit.status_code == 200 and yanit.json()["randevu_durumu"] == yeni
    assert ("UPDATE randevular SET durum = %s WHERE randevu_id = %s;", (yeni, 7)) in sorgular
    assert any("INSERT INTO denetim_kayitlari" in s for s, _ in sorgular)
    conn.commit.assert_called_once()


def test_ayni_duruma_isaretlemek_zararsiz(istemci):
    yanit, sorgular, conn = _isaretle(istemci, "TAMAMLANDI", (3, "TAMAMLANDI", GECMIS))
    assert yanit.status_code == 200 and not any(s.startswith("UPDATE randevular") for s, _ in sorgular)
    conn.commit.assert_not_called()


def test_henuz_baslamamis_randevu_isaretlenemez(istemci):
    yanit, sorgular, conn = _isaretle(istemci, "TAMAMLANDI", (3, "PLANLANDI", GELECEK))
    assert yanit.status_code == 409 and "başlamamış" in yanit.json()["detail"]
    conn.commit.assert_not_called()


def test_iptal_edilmis_randevu_isaretlenemez(istemci):
    yanit, _, conn = _isaretle(istemci, "GELMEDI", (3, "IPTAL_EDILDI", GECMIS))
    assert yanit.status_code == 409 and "İptal edilmiş" in yanit.json()["detail"]
    conn.commit.assert_not_called()


def test_psikolog_kendi_randevusunu_isaretler_baskasininkini_isaretleyemez(istemci):
    yanit, _, _ = _isaretle(istemci, "GELMEDI", (3, "PLANLANDI", GECMIS), rol="PSIKOLOG", personel=(3,))
    assert yanit.status_code == 200
    yanit, sorgular, conn = _isaretle(istemci, "GELMEDI", (3, "PLANLANDI", GECMIS), rol="PSIKOLOG", personel=(9,))
    assert yanit.status_code == 403 and not any(s.startswith("UPDATE randevular") for s, _ in sorgular)
    conn.commit.assert_not_called()


def test_olmayan_randevu_404(istemci):
    conn = MagicMock()
    conn.cursor.return_value.fetchone.side_effect = [(1,), None]
    with patch("sunucu.psycopg2.connect", return_value=conn):
        assert istemci.patch("/api/randevular/7/durum", json={"durum": "GELMEDI"}).status_code == 404


@pytest.mark.parametrize("govde", [{"durum": "PLANLANDI"}, {"durum": "IPTAL_EDILDI"}, {}, {"durum": "GELMEDI", "x": 1}])
def test_durum_ucu_gecersiz_govdeleri_reddeder(istemci, govde):
    conn = MagicMock()
    conn.cursor.return_value.fetchone.return_value = (1,)
    with patch("sunucu.psycopg2.connect", return_value=conn):
        assert istemci.patch("/api/randevular/7/durum", json=govde).status_code == 422


def test_randevu_listesi_iptal_alanlarini_dondurur(istemci):
    conn = MagicMock()
    c = conn.cursor.return_value
    c.fetchone.side_effect = [(1,), ("ADMIN",)]
    simdi = datetime.now()
    c.fetchall.return_value = [
        (1, "DAN-1", 3, 2, simdi, simdi, "IPTAL_EDILDI", simdi, "DIGER", "kurum içi görev"),
        (2, "DAN-2", 3, 2, simdi, simdi, "PLANLANDI", simdi),                  # eski biçim (8 sütun) de çalışır
    ]
    with patch("sunucu.psycopg2.connect", return_value=conn):
        yanit = istemci.get("/api/randevular")
    veri = yanit.json()
    assert yanit.status_code == 200
    assert (veri[0]["iptal_nedeni"], veri[0]["iptal_notu"]) == ("DIGER", "kurum içi görev")
    assert (veri[1]["iptal_nedeni"], veri[1]["iptal_notu"]) == (None, None)


# ------------------------------------------------------------------ iptal penceresi
@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def test_gecerlilik_kurallari():
    assert iptal_girdisi_gecerli_mi(None, "")[0] is False
    assert iptal_girdisi_gecerli_mi("DANISAN_TALEBI", "")[0] is True
    assert iptal_girdisi_gecerli_mi("DIGER", "  ")[0] is False
    assert iptal_girdisi_gecerli_mi("DIGER", "kısa not")[0] is True
    assert iptal_girdisi_gecerli_mi("HATALI_KAYIT", "x" * 101)[0] is False


def test_pencere_neden_secilmeden_iptal_edilemez(qt_app):
    p = IptalNedeniDialog(None, randevu_kodu="DAN-2026-0003")
    assert not p.btn_iptal_et.isEnabled() and p.sonuc() == (None, None)
    assert [p.cmb_neden.itemData(i) for i in range(p.cmb_neden.count())] == [None] + [k for k, _ in IPTAL_NEDENLERI]
    p.cmb_neden.setCurrentIndex(p.cmb_neden.findData("DANISAN_TALEBI"))
    assert p.btn_iptal_et.isEnabled() and p.sonuc() == ("DANISAN_TALEBI", None)


def test_pencere_diger_icin_not_zorunlu_ve_not_siniri(qt_app):
    p = IptalNedeniDialog()
    p.cmb_neden.setCurrentIndex(p.cmb_neden.findData("DIGER"))
    assert not p.btn_iptal_et.isEnabled() and "açıklama" in p.lbl_hata.text()
    assert "zorunlu" in p.txt_not.placeholderText()
    p.txt_not.setText("  kurum içi görev  ")
    assert p.btn_iptal_et.isEnabled() and p.sonuc() == ("DIGER", "kurum içi görev") and p.lbl_hata.text() == ""
    p.txt_not.setText("x" * 150)
    assert len(p.txt_not.text()) == 100                                     # alan 100 karakteri aşamaz
    assert "Kişisel bilgi" in p.lbl_uyari.text()


def test_pencere_vazgecilirse_reddedilir(qt_app):
    p = IptalNedeniDialog()
    p.reject()
    assert p.result() == QDialog.Rejected


# ------------------------------------------------------------------ Randevu Yönetimi
def zaman(gun=0, saat=10):
    return (datetime.now().replace(hour=saat, minute=0, second=0, microsecond=0) + timedelta(days=gun)).isoformat()


def randevu(no, durum="PLANLANDI", gun=1, neden=None, notu=None):
    return {"randevu_id": no, "danisan_kod_id": f"DAN-2026-{no:04d}", "psikolog_id": 3, "oda_id": 2, "durum": durum,
            "baslangic_zamani": zaman(gun), "bitis_zamani": zaman(gun, 11), "iptal_nedeni": neden, "iptal_notu": notu}


def cevap(veri, durum=200):
    y = MagicMock()
    y.status_code = durum
    y.json.return_value = veri
    y._tkys_oturum_reddedildi = False
    return y


class Sunucu:
    def __init__(self, randevular, patch_cevabi=None):
        self.randevular = randevular
        self.patch_cevabi = patch_cevabi or cevap({"durum": "basarili"})
        self.istekler, self.govdeler = [], []

    def __call__(self, yontem, url, **kwargs):
        self.istekler.append((yontem, url))
        if yontem == "PATCH":
            self.govdeler.append(kwargs.get("json"))
            return self.patch_cevabi
        if url.endswith("/api/randevular"):
            return cevap(self.randevular)
        if url.endswith("/api/psikologlar"):
            return cevap([{"personel_id": 3, "ad_soyad": "Ayşe", "kullanici_id": 13}])
        if url.endswith("/api/odalar"):
            return cevap([{"oda_id": 2, "oda_adi": "Oda-1", "kapasite": 1, "aktif_mi": True}])
        return cevap([])


@pytest.fixture
def ekran_ac(qt_app):
    acik = []
    aktif = {}

    def ac(sunucu):
        aktif["s"] = sunucu
        ekran = RandevuAnaEkrani("http://testserver", "TOKEN", 11, "admin")
        ekran.chk_iptal_gizle.setChecked(False)
        ekran._sunucu = sunucu
        acik.append(ekran)
        return ekran

    with patch.object(modul, "oturum_kontrollu_istek", side_effect=lambda *a, **k: aktif["s"](*a, **k)):
        yield ac
    for e in acik:
        e.close()


def sec(ekran, randevu_id):
    for satir in range(ekran.tablo.rowCount()):
        if ekran.tablo.item(satir, 0).text() == str(randevu_id):
            ekran.tablo.selectRow(satir)
            return
    raise AssertionError(randevu_id)


class SahtePencere:
    def __init__(self, kabul=True, neden="DANISAN_TALEBI", notu=None):
        self.kabul, self._sonuc = kabul, (neden, notu)

    def exec(self):
        return QDialog.Accepted if self.kabul else QDialog.Rejected

    def sonuc(self):
        return self._sonuc


def sahte_pencere(**kw):
    return patch.object(modul, "IptalNedeniDialog", side_effect=lambda *a, **k: SahtePencere(**kw))


def test_bilgi_metni_cesitleri():
    assert iptal_bilgisi_metni(None) == "" and iptal_bilgisi_metni(randevu(1)) == ""
    assert iptal_bilgisi_metni(randevu(1, "IPTAL_EDILDI", neden="DANISAN_TALEBI")) == "İptal nedeni:  Danışan talebi"
    assert iptal_bilgisi_metni(randevu(1, "IPTAL_EDILDI", neden="DIGER", notu="kurum içi görev")) == \
        "İptal nedeni:  Diğer — kurum içi görev"
    assert "kaydedilmemiş" in iptal_bilgisi_metni(randevu(1, "IPTAL_EDILDI"))      # eski iptaller


def test_secili_iptal_satirinda_neden_bilgi_satiri_gorunur(ekran_ac):
    ekran = ekran_ac(Sunucu([
        randevu(1), randevu(2, "IPTAL_EDILDI", neden="HATALI_KAYIT"),
        randevu(3, "IPTAL_EDILDI", neden="DIGER", notu="kurum içi görev"), randevu(4, "IPTAL_EDILDI"),
    ]))
    assert not ekran.lbl_iptal_bilgisi.isVisibleTo(ekran)                           # seçim yok
    sec(ekran, 1)
    assert not ekran.lbl_iptal_bilgisi.isVisibleTo(ekran)                           # planlı randevuda yok
    sec(ekran, 2)
    assert ekran.lbl_iptal_bilgisi.isVisibleTo(ekran) and ekran.lbl_iptal_bilgisi.text() == "İptal nedeni:  Hatalı kayıt"
    sec(ekran, 3)
    assert ekran.lbl_iptal_bilgisi.text() == "İptal nedeni:  Diğer — kurum içi görev"
    sec(ekran, 4)
    assert "kaydedilmemiş" in ekran.lbl_iptal_bilgisi.text()
    sec(ekran, 1)
    assert not ekran.lbl_iptal_bilgisi.isVisibleTo(ekran)


def test_iptal_pencereden_gelen_nedenle_gonderilir(ekran_ac):
    sunucu = Sunucu([randevu(3)])
    ekran = ekran_ac(sunucu)
    sec(ekran, 3)
    with sahte_pencere(neden="DIGER", notu="kurum içi görev"), patch.object(QMessageBox, "information") as bilgi:
        ekran.iptal_et_secilen()
    assert ("PATCH", "http://testserver/api/randevular/3/iptal") in sunucu.istekler
    assert sunucu.govdeler == [{"iptal_nedeni": "DIGER", "iptal_notu": "kurum içi görev"}]
    bilgi.assert_called_once()
    assert sunucu.istekler[-1][1].endswith("/api/randevular")


def test_iptalden_vazgecilirse_istek_gitmez(ekran_ac):
    sunucu = Sunucu([randevu(3)])
    ekran = ekran_ac(sunucu)
    sec(ekran, 3)
    with sahte_pencere(kabul=False):
        ekran.iptal_et_secilen()
    assert not any(y == "PATCH" for y, _ in sunucu.istekler)


@pytest.mark.parametrize("yeni", ["TAMAMLANDI", "GELMEDI"])
def test_gecmis_randevu_isaretlenir(ekran_ac, yeni):
    sunucu = Sunucu([randevu(5, gun=-2)])
    ekran = ekran_ac(sunucu)
    sec(ekran, 5)
    with patch.object(QMessageBox, "question") as soru:
        ekran.durum_isaretle(yeni)
    soru.assert_not_called()                                                         # onay penceresi yok
    assert ("PATCH", "http://testserver/api/randevular/5/durum") in sunucu.istekler
    assert sunucu.govdeler == [{"durum": yeni}]
    assert sunucu.istekler[-1][1].endswith("/api/randevular")                       # sonra liste yenilenir


@pytest.mark.parametrize("liste, parca", [
    ([randevu(5, gun=3)], "başlamamış"),
    ([randevu(5, "IPTAL_EDILDI", gun=-2, neden="HATALI_KAYIT")], "İptal edilmiş"),
    ([randevu(5, "TAMAMLANDI", gun=-2)], "zaten"),
])
def test_uygun_olmayan_randevu_istemcide_engellenir(ekran_ac, liste, parca):
    sunucu = Sunucu(liste)
    ekran = ekran_ac(sunucu)
    sec(ekran, 5)
    with patch.object(QMessageBox, "information") as bilgi, patch.object(QMessageBox, "question") as soru:
        ekran.durum_isaretle("TAMAMLANDI")
    assert parca in bilgi.call_args.args[2]
    soru.assert_not_called()
    assert not any(y == "PATCH" for y, _ in sunucu.istekler)


def test_secim_yokken_isaretleme_uyarir(ekran_ac):
    ekran = ekran_ac(Sunucu([randevu(5, gun=-2)]))
    with patch.object(QMessageBox, "warning") as uyari:
        ekran.durum_isaretle("GELMEDI")
    uyari.assert_called_once()


def test_sunucu_reddederse_mesaji_gosterilir(ekran_ac):
    ret = cevap({"detail": "Yalnızca kendi randevunuzun durumunu işaretleyebilirsiniz."}, 403)
    ekran = ekran_ac(Sunucu([randevu(5, gun=-2)], patch_cevabi=ret))
    sec(ekran, 5)
    with patch.object(QMessageBox, "question", return_value=QMessageBox.Yes), patch.object(QMessageBox, "warning") as uyari:
        ekran.durum_isaretle("GELMEDI")
    assert uyari.call_args.args[2] == "Yalnızca kendi randevunuzun durumunu işaretleyebilirsiniz."


# ------------------------------------------------------------------ menü ve adlar
def test_menude_ust_dugmeler_ve_yeni_danisan_yok():
    ogeler = {o["ad"]: o for _, liste in mw.MENU for o in liste}
    aksiyonlar = dict(ogeler["Randevu Yönetimi"]["aksiyon"])
    assert "Yeni Danışan" not in " ".join(aksiyonlar)
    assert not any("Tamamlandı" in e or "Gelmedi" in e for e in aksiyonlar)            # işaretleme rozetten yapılır


def test_danisanlar_sayfasinda_sekme_adi_randevular():
    import danisanlar_ekrani
    assert [e for e, _ in danisanlar_ekrani.BOLUMLER] == ["Bilgiler", "Özet", "Randevular"]
