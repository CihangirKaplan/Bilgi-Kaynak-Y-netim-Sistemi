"""
Danışanı pasife alma / aktife alma.

- Danışan silinmez; pasif danışana yeni randevu verilemez (sunucu zaten engelliyor), geçmiş korunur.
- Psikolog yalnızca kendi danışanının durumunu değiştirir; yetkili roller herkesinkini.
- Geleceğe dönük planlanmış randevusu olan danışan pasife alınamaz (409).
- Danışanlar sayfasında "Pasifleri göster", pasif satırlar sönük, detayda Pasife Al / Aktife Al düğmesi.
- İpucu kutuları koyu ve okunaklı.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from PySide6.QtWidgets import QApplication, QMessageBox

import danisanlar_ekrani as modul
import main_window as mw
from danisanlar_ekrani import DanisanlarEkrani
from sunucu import app, mevcut_kullanici_id


# ------------------------------------------------------------------ sunucu ucu
@pytest.fixture
def istemci():
    app.dependency_overrides[mevcut_kullanici_id] = lambda: 5
    yield TestClient(app)
    app.dependency_overrides.pop(mevcut_kullanici_id, None)


def _degistir(istemci, sorgu, danisan=(True, 3), rol="ADMIN", personel=(3,), planli=0):
    """danisan: (aktif_mi, olusturan_psikolog_id) satırı; None ise danışan yok."""
    conn = MagicMock()
    c = conn.cursor.return_value
    sirali = [(1,), danisan]
    if danisan is not None:
        sirali.append((rol,))
        if rol == "PSIKOLOG":
            sirali.append(personel)
        sirali.append((planli,))
    c.fetchone.side_effect = sirali
    with patch("sunucu.psycopg2.connect", return_value=conn):
        yanit = istemci.patch("/api/danisan-kodlari/DAN-2026-0001/durum" + sorgu)
    sorgular = [(a[0], a[1] if len(a) > 1 else None) for a, _ in c.execute.call_args_list]
    return yanit, sorgular, conn


def guncelleme_var(sorgular):
    return [p for s, p in sorgular if s.startswith("UPDATE danisan_kodlari")]


def test_yetkili_rol_danisani_pasife_alir_ve_denetim_kaydi_tutulur(istemci):
    yanit, sorgular, conn = _degistir(istemci, "?aktif_mi=false")
    assert yanit.status_code == 200 and yanit.json()["aktif_mi"] is False
    assert guncelleme_var(sorgular) == [(False, "DAN-2026-0001")]
    assert any("INSERT INTO denetim_kayitlari" in s for s, _ in sorgular)
    conn.commit.assert_called_once()


def test_pasif_danisan_yeniden_aktif_edilir_planli_randevu_kontrolu_gerekmez(istemci):
    yanit, sorgular, _ = _degistir(istemci, "?aktif_mi=true", danisan=(False, 3))
    assert yanit.status_code == 200 and yanit.json()["aktif_mi"] is True
    assert guncelleme_var(sorgular) == [(True, "DAN-2026-0001")]
    assert not any("FROM randevular" in s for s, _ in sorgular)


def test_ayni_durum_istenirse_islem_yapilmaz_basarili_doner(istemci):
    yanit, sorgular, conn = _degistir(istemci, "?aktif_mi=true", danisan=(True, 3))
    assert yanit.status_code == 200 and guncelleme_var(sorgular) == []
    conn.commit.assert_not_called()


def test_planlanmis_randevusu_olan_danisan_pasife_alinamaz(istemci):
    yanit, sorgular, conn = _degistir(istemci, "?aktif_mi=false", planli=2)
    assert yanit.status_code == 409 and "2 planlanmış randevusu" in yanit.json()["detail"]
    assert guncelleme_var(sorgular) == []
    conn.commit.assert_not_called()


def test_planli_randevu_kontrolu_gelecekteki_planlilara_bakar(istemci):
    _, sorgular, _ = _degistir(istemci, "?aktif_mi=false")
    sql, parametre = next((s, p) for s, p in sorgular if "FROM randevular" in s)
    assert "durum = 'PLANLANDI'" in sql and "bitis_zamani > %s" in sql
    assert abs(parametre[1] - datetime.now()) < timedelta(seconds=30)


def test_psikolog_kendi_danisanini_degistirebilir(istemci):
    yanit, sorgular, _ = _degistir(istemci, "?aktif_mi=false", rol="PSIKOLOG", personel=(3,))
    assert yanit.status_code == 200 and guncelleme_var(sorgular)


def test_psikolog_baskasinin_danisanini_degistiremez(istemci):
    yanit, sorgular, conn = _degistir(istemci, "?aktif_mi=false", rol="PSIKOLOG", personel=(9,))
    assert yanit.status_code == 403 and guncelleme_var(sorgular) == []
    conn.commit.assert_not_called()


def test_olmayan_danisan_404(istemci):
    yanit, _, _ = _degistir(istemci, "?aktif_mi=false", danisan=None)
    assert yanit.status_code == 404


def test_aktif_mi_parametresi_zorunlu_ve_gecerli_olmali(istemci):
    conn = MagicMock()
    conn.cursor.return_value.fetchone.return_value = (1,)
    with patch("sunucu.psycopg2.connect", return_value=conn):
        assert istemci.patch("/api/danisan-kodlari/DAN-2026-0001/durum").status_code == 422
        assert istemci.patch("/api/danisan-kodlari/DAN-2026-0001/durum?aktif_mi=belki").status_code == 422


def _liste(istemci, sorgu=""):
    conn = MagicMock()
    c = conn.cursor.return_value
    c.fetchone.side_effect = [(1,), ("ADMIN",)]
    c.fetchall.return_value = []
    with patch("sunucu.psycopg2.connect", return_value=conn):
        yanit = istemci.get("/api/danisan-kodlari" + sorgu)
    return yanit, [a[0] for a, _ in c.execute.call_args_list][-1]


def test_liste_varsayilan_yalnizca_aktifleri_getirir(istemci):
    yanit, sql = _liste(istemci)
    assert yanit.status_code == 200 and "WHERE aktif_mi = TRUE" in sql


def test_liste_pasifler_dahil_isteginde_pasifleri_de_getirir(istemci):
    yanit, sql = _liste(istemci, "?pasifler_dahil=true")
    assert yanit.status_code == 200 and "WHERE TRUE" in sql and "aktif_mi = TRUE" not in sql


def test_randevu_olusturma_danisan_satirini_kilitler_pasife_alma_ile_yaris_olmaz():
    import sunucu
    kaynak = open(sunucu.__file__, encoding="utf-8").read()
    assert "AND aktif_mi = TRUE FOR SHARE;\", (randevu.danisan_kod_id,)" in kaynak


# ------------------------------------------------------------------ sayfa
PSIKOLOGLAR = {3: "Ayşe Yılmaz", 7: "Reyhan Kaya"}


def cevap(veri, durum=200):
    y = MagicMock()
    y.status_code = durum
    y.json.return_value = veri
    y._tkys_oturum_reddedildi = False
    return y


def kayit(kod, psikolog=3, aktif=True):
    return {"danisan_kod_id": kod, "ucretli_mi": True, "istisna_turu": "YOK", "aktif_mi": aktif,
            "olusturulma_tarihi": datetime.now().isoformat(), "olusturan_psikolog_id": psikolog}


class Sunucu:
    def __init__(self, patch_cevabi=None):
        self.patch_cevabi = patch_cevabi or cevap({"durum": "basarili"})
        self.istekler = []
        self.tumu = [kayit("DAN-2026-0001"), kayit("DAN-2026-0002", aktif=False), kayit("DAN-2026-0003", psikolog=7)]

    def __call__(self, yontem, url, **kwargs):
        params = kwargs.get("params") or {}
        self.istekler.append((yontem, url, params))
        if yontem == "PATCH":
            return self.patch_cevabi
        if url.endswith("/api/danisan-kodlari"):
            liste = [d for d in self.tumu if params.get("pasifler_dahil") == "true" or d["aktif_mi"]]
            pid = params.get("psikolog_id")
            return cevap([d for d in liste if pid is None or d["olusturan_psikolog_id"] == pid])
        if url.endswith("/api/psikologlar"):
            return cevap([{"personel_id": k, "ad_soyad": v, "kullanici_id": 100 + k} for k, v in PSIKOLOGLAR.items()])
        return cevap([])


@pytest.fixture
def ekran_ac():
    acik = []
    sunucu_taklidi = {}

    def ac(sunucu=None):
        sunucu = sunucu or Sunucu()
        sunucu_taklidi["s"] = sunucu
        ekran = DanisanlarEkrani("http://testserver", "TOKEN", 11)
        ekran._sunucu = sunucu
        acik.append(ekran)
        return ekran

    with patch.object(modul, "oturum_kontrollu_istek", side_effect=lambda *a, **k: sunucu_taklidi["s"](*a, **k)):
        yield ac
    for e in acik:
        e.close()


def kodlar(ekran):
    return [ekran.tablo.item(i, 0).text() for i in range(ekran.tablo.rowCount())]


def sec(ekran, kod):
    ekran.tablo.selectRow(kodlar(ekran).index(kod))


def test_pasifler_varsayilan_gizli_secenekle_gorunur_ve_soluk(ekran_ac):
    ekran = ekran_ac()
    assert kodlar(ekran) == ["DAN-2026-0001", "DAN-2026-0003"] and not ekran.chk_pasif.isChecked()
    ekran.chk_pasif.setChecked(True)
    assert kodlar(ekran) == ["DAN-2026-0001", "DAN-2026-0002", "DAN-2026-0003"]
    assert ekran._sunucu.istekler[-1][2].get("pasifler_dahil") == "true"
    pasif = ekran.tablo.item(1, 0)
    assert pasif.foreground().color().name().lower() == "#94a3b8"
    assert ekran.tablo.item(0, 0).foreground().color().name().lower() != "#94a3b8"
    assert ekran.tablo.item(1, 6).text() == "Pasif"


def test_dugme_metni_durumu_gosterir(ekran_ac):
    ekran = ekran_ac()
    ekran.chk_pasif.setChecked(True)
    sec(ekran, "DAN-2026-0001")
    assert ekran.btn_durum.text() == "Pasife Al"
    sec(ekran, "DAN-2026-0002")
    assert ekran.btn_durum.text() == "Aktife Al"


def test_pasife_alma_onaylaninca_istek_gider_ve_liste_yenilenir(ekran_ac):
    ekran = ekran_ac()
    sec(ekran, "DAN-2026-0001")
    with patch.object(modul.QMessageBox, "question", return_value=QMessageBox.Yes) as soru:
        ekran.btn_durum.click()
    assert "pasife alınsın mı" in soru.call_args.args[2]
    yontem, url, params = next(i for i in ekran._sunucu.istekler if i[0] == "PATCH")
    assert url.endswith("/api/danisan-kodlari/DAN-2026-0001/durum") and params == {"aktif_mi": "false"}
    assert ekran._sunucu.istekler[-1][0] == "GET"                      # sonra liste yenilendi


def test_onay_verilmezse_istek_gitmez(ekran_ac):
    ekran = ekran_ac()
    sec(ekran, "DAN-2026-0001")
    with patch.object(modul.QMessageBox, "question", return_value=QMessageBox.No):
        ekran.btn_durum.click()
    assert not [i for i in ekran._sunucu.istekler if i[0] == "PATCH"]


def test_aktife_alma_istegi(ekran_ac):
    ekran = ekran_ac()
    ekran.chk_pasif.setChecked(True)
    sec(ekran, "DAN-2026-0002")
    with patch.object(modul.QMessageBox, "question", return_value=QMessageBox.Yes):
        ekran.btn_durum.click()
    assert next(i for i in ekran._sunucu.istekler if i[0] == "PATCH")[2] == {"aktif_mi": "true"}


def test_planli_randevu_nedeniyle_reddedilince_sunucu_mesaji_gosterilir_liste_yenilenmez(ekran_ac):
    ret = cevap({"detail": "Bu danışanın 2 planlanmış randevusu var. Pasife almadan önce randevuları iptal edin."}, 409)
    ekran = ekran_ac(Sunucu(patch_cevabi=ret))
    sec(ekran, "DAN-2026-0001")
    onceki = len(ekran._sunucu.istekler)
    with patch.object(modul.QMessageBox, "question", return_value=QMessageBox.Yes), \
            patch.object(modul.QMessageBox, "warning") as uyari:
        ekran.btn_durum.click()
    assert "2 planlanmış randevusu" in uyari.call_args.args[2]
    assert len(ekran._sunucu.istekler) == onceki + 1                   # yalnızca PATCH; liste yenilenmedi


# ------------------------------------------------------------------ üst çubuk ve ipucu
def test_stil_ipucu_kutusunu_koyu_ve_okunakli_yapar():
    kural = mw.STIL.split("QToolTip {")[1].split("}")[0]
    assert "background-color: #0A1F5C" in kural and "color: white" in kural
