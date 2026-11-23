"""Arıza ve cihaz durumu tek doğruluk kaynağı: "Arızalı" yalnızca açık arıza kaydından türer, elle seçilemez ve elle çözülemez."""
import os
import re
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

import client.cihaz_ekranlari as envanter
import server.sunucu as sunucu
from server.modeller import CihazGuncelleModeli, CihazOlusturModeli

KOK = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------- model: elle seçilemez
def test_arizali_durumu_elle_secilemez():
    with pytest.raises(ValidationError, match="Arıza Kayıtları"):
        CihazOlusturModeli(envanter_kodu="E-1", cihaz_adi="EEG", durum="Arizali")
    with pytest.raises(ValidationError, match="Arıza Kayıtları"):
        CihazGuncelleModeli(durum="Arizali")


@pytest.mark.parametrize("durum", ["Kullanima_Hazir", "Bakimda", "Kalibrasyonda", "Kullanim_Disi"])
def test_diger_durumlar_hala_secilebilir(durum):
    assert CihazGuncelleModeli(durum=durum).durum.value == durum


# ---------------------------------------------------------------- etkin durum SQL'i
def test_etkin_durum_arizayi_kayittan_turetir_ve_oncelik_dogrudur():
    sql = " ".join(sunucu.ETKIN_CIHAZ_DURUMU_SQL.split())
    sira = [sql.index(parca) for parca in ("'Kullanim_Disi' THEN 'Kullanim_Disi'", "cihaz_arizalari", "THEN 'Arizali'", "THEN 'Bakimda'", "THEN 'Kalibrasyonda'")]
    assert sira == sorted(sira)                                     # kullanım dışı > arızalı (arıza kaydı) > bakımda > kalibrasyonda
    assert "a.cozuldu_mu IS NOT TRUE" in sql
    assert "c.durum IN ('Arizali'" not in sql                       # sütundaki ham 'Arizali' artık doğruluk kaynağı değil
    assert "WHEN c.durum = 'Arizali' THEN 'Kullanima_Hazir'" in sql  # kayıtsız (bayat) 'Arızalı' sütunu hazır sayılır


def test_rezervasyon_denetimi_acik_arizayi_sutundan_bagimsiz_gorur():
    imlec = MagicMock()
    imlec.fetchone.return_value = ("Arizali",)
    rez = MagicMock(cihaz_id=7)
    with pytest.raises(HTTPException) as hata:
        sunucu.rezervasyon_uygunlugunu_denetle(imlec, rez)
    assert hata.value.status_code == 403
    sorgu = " ".join(imlec.execute.call_args_list[0].args[0].split())
    assert "cihaz_arizalari" in sorgu and "a.cozuldu_mu IS NOT TRUE" in sorgu and "'Kullanim_Disi'" in sorgu


# ---------------------------------------------------------------- PATCH /api/cihazlar: açık arızada elle durum değişmez
def _guncelle(eski_durum, govde, acik_ariza):
    imlec = MagicMock()
    sonuclar = [(eski_durum,)] + ([(acik_ariza,)] if acik_ariza is not None else [])
    imlec.fetchone.side_effect = sonuclar + [(1,)]
    baglanti = MagicMock()
    baglanti.cursor.return_value = imlec
    with patch("server.sunucu.vt_baglan", return_value=baglanti):
        try:
            sonuc = sunucu.cihaz_guncelle(5, CihazGuncelleModeli(**govde), kullanici_id=1)
        except HTTPException as hata:
            return hata, imlec
    return sonuc, imlec


def _guncelleme_sorgusu_calisti(imlec):
    return any("UPDATE cihazlar SET" in " ".join(c.args[0].split()) for c in imlec.execute.call_args_list)


def test_acik_arizasi_olan_cihazin_durumu_elle_degistirilemez():
    hata, imlec = _guncelle("Arizali", {"durum": "Kullanima_Hazir"}, acik_ariza=True)
    assert isinstance(hata, HTTPException) and hata.status_code == 409 and "çözüldü olarak işaretleyin" in hata.detail
    assert not _guncelleme_sorgusu_calisti(imlec)


def test_bakimdaki_cihazda_da_acik_ariza_varsa_durum_degistirilemez():
    hata, _ = _guncelle("Bakimda", {"durum": "Kullanima_Hazir"}, acik_ariza=True)
    assert isinstance(hata, HTTPException) and hata.status_code == 409


def test_acik_arizasi_olmayan_cihazin_durumu_degistirilebilir():
    sonuc, imlec = _guncelle("Kullanima_Hazir", {"durum": "Bakimda"}, acik_ariza=False)
    assert sonuc["durum"] == "basarili" and _guncelleme_sorgusu_calisti(imlec)


def test_acik_arizali_cihaz_her_zaman_kullanim_disi_birakilabilir():
    sonuc, imlec = _guncelle("Arizali", {"durum": "Kullanim_Disi"}, acik_ariza=None)       # arıza sorgusuna gerek kalmaz
    assert sonuc["durum"] == "basarili" and _guncelleme_sorgusu_calisti(imlec)


def test_durum_degismiyorsa_ya_da_gonderilmediyse_arizali_cihaz_duzenlenebilir():
    sonuc, imlec = _guncelle("Arizali", {"marka_model": "Yeni Model"}, acik_ariza=None)    # yalnızca marka: durum kontrolü yok
    assert sonuc["durum"] == "basarili" and _guncelleme_sorgusu_calisti(imlec)
    sonuc, _ = _guncelle("Bakimda", {"durum": "Bakimda"}, acik_ariza=None)                 # aynı değer: değişiklik değil
    assert sonuc["durum"] == "basarili"


# ---------------------------------------------------------------- migration
def test_migrasyon_zincire_baglidir_ve_iki_yonde_onarir():
    yol = next((KOK / "database" / "migrations" / "versions").glob("d5f2a9c1b843_*.py"))
    kaynak = yol.read_text(encoding="utf-8")
    assert 'revision: str = "d5f2a9c1b843"' in kaynak and '"e6a1d4b8c273"' in kaynak
    assert "SET durum = 'Kullanima_Hazir'" in kaynak and "SET durum = 'Arizali'" in kaynak
    assert kaynak.count("INSERT INTO denetim_kayitlari") == 2 and "'DEVICE_STATUS_CHANGE'" in kaynak     # her onarım denetim kaydına yazılır
    assert "NOT EXISTS (SELECT 1 FROM cihaz_arizalari" in kaynak and "cozuldu_mu IS NOT TRUE" in kaynak
    assert "def downgrade():" in kaynak and not re.search(r"op\.execute", kaynak.split("def downgrade():")[1])   # veri onarımı geri alınmaz


def test_alembic_tek_head():
    sonuc = subprocess.run([sys.executable, "scripts/alembic_tek_head_kontrol.py"], cwd=KOK, capture_output=True, text=True,
                           env={**os.environ, "JWT_SECRET": os.environ.get("JWT_SECRET", "x" * 40)})
    assert sonuc.returncode == 0, sonuc.stdout + sonuc.stderr


# ---------------------------------------------------------------- istemci formu
@pytest.fixture
def form_ac(tkys_qapplication):
    acilanlar = []

    def ac(islem, cihaz=None):
        f = envanter.CihazIslemFormu("http://x", "t", islem, cihaz)
        acilanlar.append(f)
        return f

    yield ac
    for f in acilanlar:
        f.close()


def _cihaz(**ek):
    return {"cihaz_id": 4, "envanter_kodu": "E-4", "cihaz_adi": "EEG", "marka_model": "A", "seri_no": "S", "durum": "Kullanima_Hazir", **ek}


def _kaydedilen(form):
    cevap = MagicMock(status_code=200)
    with patch.object(envanter, "oturum_kontrollu_istek", return_value=cevap) as istek, patch.object(envanter, "oturum_hatasi_mi", return_value=False), \
            patch.object(envanter, "basari_bildirimi"), patch.object(form, "accept"):
        form.kaydet()
    return istek.call_args


def test_form_arizali_secenegini_sunmaz(form_ac):
    f = form_ac("GUNCELLE", _cihaz())
    secenekler = [f.cmb_durum.itemData(i) for i in range(f.cmb_durum.count())]
    assert "Arizali" not in secenekler and {"Kullanima_Hazir", "Bakimda", "Kalibrasyonda", "Kullanim_Disi"} <= set(secenekler)
    assert "Arizali" in envanter.DURUMLAR                                                  # rozeti hâlâ çizilir


def test_arizali_cihazda_durum_kutusu_kilitli_aciklamali_ve_arizali_gosterir(form_ac):
    f = form_ac("GUNCELLE", _cihaz(durum="Arizali", etkin_durum="Arizali"))
    assert not f.cmb_durum.isEnabled() and "arıza kaydı var" in f.cmb_durum.toolTip()
    assert f.cmb_durum.currentText() == "Arızalı" and f.cmb_durum.currentData() == "Arizali"       # yanıltıcı "Kullanıma Hazır" yazmaz


def test_bakimdaki_cihazda_acik_ariza_varsa_kutu_arizali_gosterir_ve_kilitlidir(form_ac):
    f = form_ac("GUNCELLE", _cihaz(durum="Bakimda", etkin_durum="Arizali"))                      # sütun Bakımda, etkin durum Arızalı
    assert f.cmb_durum.currentData() == "Arizali" and not f.cmb_durum.isEnabled()


def test_kayitsiz_arizali_sutun_cihazi_kilitlemez(form_ac):
    f = form_ac("GUNCELLE", _cihaz(durum="Arizali", etkin_durum="Kullanima_Hazir"))               # açık arıza yok: sütun bayat
    assert f.cmb_durum.isEnabled() and f.cmb_durum.currentData() == "Kullanima_Hazir"


def test_arizali_cihazin_markasi_duzeltilince_durum_gonderilmez(form_ac):
    f = form_ac("GUNCELLE", _cihaz(durum="Arizali", etkin_durum="Arizali"))
    f.txt_marka.setText("Düzeltilmiş Marka")
    cagri = _kaydedilen(f)
    assert cagri.args[0] == "PATCH" and "durum" not in cagri.kwargs["json"] and cagri.kwargs["json"]["marka_model"] == "Düzeltilmiş Marka"


def test_durum_degistirilirse_gonderilir_degistirilmezse_gonderilmez(form_ac):
    f = form_ac("GUNCELLE", _cihaz())
    assert "durum" not in _kaydedilen(f).kwargs["json"]
    f.cmb_durum.setCurrentIndex(f.cmb_durum.findData("Bakimda"))
    assert _kaydedilen(f).kwargs["json"]["durum"] == "Bakimda"


def test_yeni_cihaz_hazir_baslar(form_ac):
    f = form_ac("EKLE")
    f.txt_envanter.setText("N-1")
    f.txt_ad.setText("Yeni")
    cagri = _kaydedilen(f)
    assert cagri.args[0] == "POST" and cagri.kwargs["json"]["durum"] == "Kullanima_Hazir"
