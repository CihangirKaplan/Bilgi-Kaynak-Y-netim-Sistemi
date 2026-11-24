"""Plandan "kayıt aç" kısayolu ve arıza ekranından cihaz geçmişine bağlantı."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication, QPushButton

import client.bakim_plani_ekranlari as plan_modulu
import client.cihaz_ariza_ekranlari as ariza_modulu
import client.cihaz_bakim_ekranlari as bakim_modulu
import client.cihaz_kalibrasyon_ekranlari as kalib_modulu
from client.tablo_tasarimi import islem_dugmeleri


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    return QApplication.instance() or QApplication([])


def _yanit(veri, durum=200):
    y = MagicMock(status_code=durum, _tkys_oturum_reddedildi=False, headers={})
    y.json.return_value = veri
    return y


def _dugmeler(kap):
    return [d.toolTip() for d in kap.findChildren(QPushButton)]


def test_islem_dugmeleri_istenen_sayida_ve_renkli_dugme_uretir():
    cagri = []
    kap = islem_dugmeleri((lambda: cagri.append("a"), "▶", "Aç"), (lambda: cagri.append("b"), "✎", "Düzenle", "#B45309", "#FEF3C7", "#FDE68A"))
    dugmeler = kap.findChildren(QPushButton)
    assert [d.toolTip() for d in dugmeler] == ["Aç", "Düzenle"]
    dugmeler[0].click(); dugmeler[1].click()
    assert cagri == ["a", "b"]
    assert "#1D4ED8" in dugmeler[0].styleSheet() and "#B45309" in dugmeler[1].styleSheet()       # varsayılan mavi kısayol, verilirse kendi rengi


def test_sunucu_ariza_listesi_cihaz_id_dondurur():
    import server.sunucu as sunucu
    conn = MagicMock()
    imlec = conn.cursor.return_value
    imlec.fetchall.return_value = [(1, "EEG", "Başlık", "Açıklama", "Yüksek", False, datetime(2026, 11, 1, 10), "E-1", None, None, 42)]
    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        liste = sunucu.arizalari_listele(kullanici_id=1)
    assert liste[0]["cihaz_id"] == 42 and "a.cihaz_id" in imlec.execute.call_args.args[0]
    imlec.fetchall.return_value = [(1, "EEG", "Başlık", "Açıklama", "Yüksek", False, datetime(2026, 11, 1, 10), "E-1")]        # eski şekilli satır çökmez
    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        assert sunucu.arizalari_listele(kullanici_id=1)[0]["cihaz_id"] is None


# ----------------------------------------------------------------------------- plandan kayıt aç
def _plan(**ek):
    p = {"plan_id": 1, "cihaz_id": 7, "envanter_kodu": "CHZ-007", "cihaz_adi": "EEG Cihazı", "gorev_turu": "Yıllık bakım",
         "periyot_gun": 365, "uyari_suresi_gun": 30, "sonraki_gorev_tarihi": (date.today() + timedelta(days=20)).isoformat(),
         "kalan_gun": 20, "aktif_mi": True, "durum": "Planlı"}
    p.update(ek)
    return p


PLANLAR = [_plan(),
           _plan(plan_id=2, cihaz_id=8, envanter_kodu="CHZ-008", cihaz_adi="Biyofeedback", gorev_turu="Kalibrasyon", periyot_gun=180),
           _plan(plan_id=3, cihaz_id=9, envanter_kodu="CHZ-009", cihaz_adi="Nörofeedback", aktif_mi=False, durum="Pasif")]


def _plan_ekrani(**izinler):
    with patch.object(plan_modulu, "oturum_kontrollu_istek", return_value=_yanit(PLANLAR)):
        e = plan_modulu.BakimPlanlariEkrani("http://x", "t", **izinler)
    e.resize(1500, 500)
    e.show()
    QApplication.processEvents()
    return e


def _satir(e, plan_id):
    return next(s for s in range(e.tablo.rowCount()) if e.tablo.item(s, 0).data(0x0100) == plan_id)


def test_plan_ekrani_kayit_ac_dugmesi_izne_ve_plan_turune_gore():
    e = _plan_ekrani(yetkili_mi=True, bakim_kaydi_yetkili_mi=True, kalibrasyon_kaydi_yetkili_mi=False)
    assert _dugmeler(e.tablo.cellWidget(_satir(e, 1), 6)) == ["Bakım kaydı aç", "Düzenle", "Sil"]
    assert _dugmeler(e.tablo.cellWidget(_satir(e, 2), 6)) == ["Düzenle", "Sil"]                # kalibrasyon izni yok
    assert _dugmeler(e.tablo.cellWidget(_satir(e, 3), 6)) == ["Düzenle", "Sil"]                # pasif plandan kayıt açılmaz
    e.close()
    e = _plan_ekrani(yetkili_mi=True, bakim_kaydi_yetkili_mi=False, kalibrasyon_kaydi_yetkili_mi=True)
    assert _dugmeler(e.tablo.cellWidget(_satir(e, 1), 6)) == ["Düzenle", "Sil"]
    assert _dugmeler(e.tablo.cellWidget(_satir(e, 2), 6)) == ["Kalibrasyon kaydı aç", "Düzenle", "Sil"]
    e.close()


def test_plan_ekrani_yalniz_kayit_izni_olan_kullanici_yalniz_kisayolu_gorur():
    e = _plan_ekrani(yetkili_mi=False, bakim_kaydi_yetkili_mi=True)
    assert not e.tablo.isColumnHidden(6)
    assert _dugmeler(e.tablo.cellWidget(_satir(e, 1), 6)) == ["Bakım kaydı aç"]
    assert e.tablo.cellWidget(_satir(e, 2), 6) is None
    e.close()
    e = _plan_ekrani(yetkili_mi=False)                                                         # hiç izin yok: sütun gizli (eski davranış)
    assert e.tablo.isColumnHidden(6)
    e.close()


def test_kayit_ac_dugmesi_bakim_formunu_cihaz_ve_planla_acar_ve_listeyi_yeniler():
    e = _plan_ekrani(yetkili_mi=True, bakim_kaydi_yetkili_mi=True, kalibrasyon_kaydi_yetkili_mi=True)
    with patch("client.cihaz_bakim_ekranlari.YeniBakimFormu") as form, patch.object(e, "verileri_yukle") as yukle:
        form.return_value.exec.return_value = 1
        e.tablo.cellWidget(_satir(e, 1), 6).findChildren(QPushButton)[0].click()
    assert form.call_args.kwargs == {"cihaz_id": 7, "plan_id": 1, "islem_metni": "Yıllık bakım"}
    yukle.assert_called_once()                                                                   # kayıt eklenince plan listesi yenilenir
    with patch("client.cihaz_kalibrasyon_ekranlari.YeniKalibrasyonFormu") as form, patch.object(e, "verileri_yukle") as yukle:
        form.return_value.exec.return_value = 0
        e.tablo.cellWidget(_satir(e, 2), 6).findChildren(QPushButton)[0].click()
    assert form.call_args.kwargs == {"cihaz_id": 8, "plan_id": 2}
    yukle.assert_not_called()                                                                    # vazgeçilirse yenilenmez
    e.close()


def test_izinsiz_kayit_ac_cagrisi_form_acmaz():
    e = _plan_ekrani(yetkili_mi=True)
    with patch("client.cihaz_bakim_ekranlari.YeniBakimFormu") as form:
        e.kayit_ac(1)
    form.assert_not_called()
    e.close()


CIHAZLAR = [{"cihaz_id": 5, "envanter_kodu": "E-5", "cihaz_adi": "Diğer"}, {"cihaz_id": 7, "envanter_kodu": "CHZ-007", "cihaz_adi": "EEG Cihazı"}]


def _sunucu(plan_listesi):
    def istek(yontem, url, **k):
        if "bakim-planlari" in url:
            return _yanit([p for p in plan_listesi if f"cihaz_id={p['cihaz_id']}&" in url])
        return _yanit(CIHAZLAR)
    return istek


def test_bakim_formu_cihaz_plan_ve_islem_onceden_secili_acilir():
    planlar = [_plan(), _plan(plan_id=11, gorev_turu="Filtre değişimi", periyot_gun=90)]
    with patch.object(bakim_modulu, "oturum_kontrollu_istek", _sunucu(planlar)), \
         patch("client.plan_secimi.oturum_kontrollu_istek", _sunucu(planlar)):
        f = bakim_modulu.YeniBakimFormu("http://x", "t", cihaz_id=7, plan_id=11, islem_metni="Filtre değişimi")
    assert f.cmb_cihaz.currentData() == 7 and f.plan_secimi.plan_id() == 11
    assert f.txt_islem.toPlainText() == "Filtre değişimi"
    f.close()


def test_bakim_formu_onsecimsiz_eskisi_gibi_acilir_ve_olmayan_cihaz_sessizce_gecilir():
    with patch.object(bakim_modulu, "oturum_kontrollu_istek", _sunucu([])), patch("client.plan_secimi.oturum_kontrollu_istek", _sunucu([])):
        f = bakim_modulu.YeniBakimFormu("http://x", "t")
        assert f.cmb_cihaz.currentData() == 5 and f.txt_islem.toPlainText() == ""
        g = bakim_modulu.YeniBakimFormu("http://x", "t", cihaz_id=999, plan_id=1)
        assert g.cmb_cihaz.currentData() == 5                                                    # listede olmayan cihaz: ilk cihaz, hata yok
    f.close(); g.close()


def test_kalibrasyon_formu_cihaz_ve_plan_onceden_secili_acilir():
    planlar = [_plan(plan_id=12, gorev_turu="Kalibrasyon", periyot_gun=180)]
    with patch.object(kalib_modulu, "oturum_kontrollu_istek", _sunucu(planlar)), patch("client.plan_secimi.oturum_kontrollu_istek", _sunucu(planlar)):
        f = kalib_modulu.YeniKalibrasyonFormu("http://x", "t", cihaz_id=7, plan_id=12)
    assert f.cmb_cihaz.currentData() == 7 and f.plan_secimi.plan_id() == 12
    f.close()


# ----------------------------------------------------------------------------- arızadan cihaz geçmişi
ARIZALAR = [{"ariza_id": 1, "cihaz_id": 7, "cihaz_adi": "EEG", "envanter_kodu": "E-7", "ariza_baslik": "a", "durum": "Açık", "aciliyet": "Orta",
             "bildirim_tarihi": "2026-11-23T11:59:00"},
            {"ariza_id": 2, "cihaz_id": None, "cihaz_adi": "Eski", "ariza_baslik": "b", "durum": "Çözüldü", "aciliyet": "Orta",
             "bildirim_tarihi": "2026-11-20T09:00:00"}]


def _ariza_ekrani(**izinler):
    with patch.object(ariza_modulu, "oturum_kontrollu_istek", return_value=_yanit(ARIZALAR)):
        e = ariza_modulu.ArizaYonetimEkrani("http://x", "t", **izinler)
    e.resize(1500, 500)
    e.show()
    QApplication.processEvents()
    return e


def test_ariza_ekraninda_cihaz_gecmisi_dugmesi_izne_ve_cihaz_kimligine_gore():
    e = _ariza_ekrani(yetkili_mi=True, gecmis_yetkili_mi=True)
    assert _dugmeler(e.tablo.cellWidget(0, 6)) == ["Cihaz geçmişini aç", "Düzenle / Çöz"]
    assert _dugmeler(e.tablo.cellWidget(1, 6)) == ["Düzenle / yeniden aç"]                      # cihaz_id yoksa (eski sunucu) geçmiş düğmesi yok
    e.close()
    e = _ariza_ekrani(yetkili_mi=True)
    assert _dugmeler(e.tablo.cellWidget(0, 6)) == ["Düzenle / Çöz"]
    e.close()
    e = _ariza_ekrani(yetkili_mi=False, gecmis_yetkili_mi=True)                                  # yalnız geçmiş izni olan kullanıcı
    assert _dugmeler(e.tablo.cellWidget(0, 6)) == ["Cihaz geçmişini aç"] and e.tablo.cellWidget(1, 6) is None
    e.close()
    e = _ariza_ekrani()
    assert e.tablo.cellWidget(0, 6) is None
    e.close()


def test_cihaz_gecmisi_dugmesi_gecmis_penceresini_cihaz_kimligiyle_acar():
    e = _ariza_ekrani(yetkili_mi=True, gecmis_yetkili_mi=True)
    with patch("client.cihaz_gecmisi_penceresi.CihazGecmisiPenceresi") as pencere:
        e.tablo.cellWidget(0, 6).findChildren(QPushButton)[0].click()
    assert pencere.call_args.args[:3] == ("http://x", "t", 7)
    pencere.return_value.exec.assert_called_once()
    e.close()
