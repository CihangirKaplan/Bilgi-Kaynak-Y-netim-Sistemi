"""Bakım kaydı tarihleri: bakım tarihi başlangıca eşitlenir; sonraki bakım bitişten sonra olmalı; süre en fazla bir yıl."""
from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

import server.sunucu as sunucu
from server.modeller import BakimGuncelleModeli, BakimOlusturModeli, bakim_tarihlerini_denetle


def _olustur(**k):
    veri = dict(cihaz_id=1, bakim_yapan_kisi="Ali", yapilan_islem="Filtre", maliyet=10,
                bakim_baslangic_tarihi=date(2026, 11, 1), bakim_bitis_tarihi=date(2026, 11, 3))
    veri.update(k)
    return BakimOlusturModeli(**veri)


def test_bakim_tarihi_gonderilmese_de_olur_ve_hep_baslangica_esitlenir():
    assert _olustur().bakim_tarihi == date(2026, 11, 1)
    assert _olustur(bakim_tarihi=date(2027, 1, 1)).bakim_tarihi == date(2026, 11, 1)       # eski istemcinin tutarsız değeri yok sayılır


def test_sonraki_bakim_bitisten_sonra_olmali():
    _olustur(sonraki_bakim_tarihi=date(2027, 5, 1))
    _olustur()                                                                              # sonraki bakım boş olabilir
    for kotu in (date(2026, 11, 3), date(2026, 11, 2), date(2026, 10, 1)):
        with pytest.raises(ValidationError, match="Sonraki bakım tarihi"):
            _olustur(sonraki_bakim_tarihi=kotu)


def test_bakim_suresi_bir_yili_asamaz_ve_bitis_baslangictan_once_olamaz():
    _olustur(bakim_bitis_tarihi=date(2027, 11, 2))                                          # 366 gün: sınırda
    with pytest.raises(ValidationError, match="bir yılı"):
        _olustur(bakim_bitis_tarihi=date(2027, 11, 3))
    with pytest.raises(ValidationError, match="bitiş tarihi"):
        _olustur(bakim_bitis_tarihi=date(2026, 10, 1))


def test_guncelleme_modeli_gonderilen_alanlari_denetler():
    BakimGuncelleModeli(yapilan_islem="Yeni")                                               # tarih göndermeyen düzenleme serbest
    with pytest.raises(ValidationError, match="Sonraki bakım tarihi"):
        BakimGuncelleModeli(bakim_bitis_tarihi=date(2026, 11, 3), sonraki_bakim_tarihi=date(2026, 11, 3))


def _guncelle(degisiklik, kayitli=(7, date(2026, 11, 1), date(2026, 11, 3), date(2027, 5, 1))):
    conn = MagicMock()
    imlec = conn.cursor.return_value
    imlec.fetchone.side_effect = [(1,), kayitli]
    with patch("server.sunucu.psycopg2.connect", return_value=conn), patch("server.sunucu.denetim_kaydi_olustur"), \
         patch("server.sunucu.cakisan_rezervasyonlari_denetle"):
        sunucu.bakim_guncelle(9, BakimGuncelleModeli(**degisiklik), kullanici_id=1)
    return [c for c in imlec.execute.call_args_list if "UPDATE cihaz_bakimlari" in str(c.args[0])][0].args


def test_guncellemede_baslangic_degisince_bakim_tarihi_eslenir_gonderilen_bakim_tarihi_yok_sayilir():
    sorgu, parametreler = _guncelle({"bakim_baslangic_tarihi": date(2026, 11, 2), "bakim_tarihi": date(2030, 1, 1)})
    assert "bakim_tarihi = %s" in sorgu and date(2026, 11, 2) in parametreler and date(2030, 1, 1) not in parametreler
    sorgu, parametreler = _guncelle({"yapilan_islem": "Not"})
    assert "bakim_tarihi" not in sorgu


def test_guncellemede_eksik_gonderilen_tarih_kayitliyla_birlikte_denetlenir():
    with pytest.raises(HTTPException) as hata:
        _guncelle({"bakim_bitis_tarihi": date(2027, 6, 1)})                                 # kayıtlı sonraki bakım 2027-05-01 → bitişten önce kalır
    assert hata.value.status_code == 422 and "Sonraki bakım tarihi" in hata.value.detail
    _guncelle({"bakim_bitis_tarihi": date(2026, 11, 4)})                                    # tutarlı: serbest


def test_ortak_denetim_fonksiyonu():
    bakim_tarihlerini_denetle(None, None, None)
    bakim_tarihlerini_denetle(date(2026, 1, 1), date(2026, 1, 2), date(2026, 7, 1))


# ------------------------------------------------------------------ ekran
def test_ekran_tarih_denetimi_sorunu_soyler():
    from PySide6.QtCore import QDate
    from PySide6.QtWidgets import QApplication, QMessageBox
    QApplication.instance() or QApplication([])
    import client.cihaz_bakim_ekranlari as m
    d = QDate(2026, 11, 1)
    with patch.object(QMessageBox, "warning") as uyari:
        assert m.tarihleri_denetle(None, d, d.addDays(2), d.addMonths(6)) is True
        uyari.assert_not_called()
        assert m.tarihleri_denetle(None, d, d.addDays(-1), d.addMonths(6)) is False
        assert m.tarihleri_denetle(None, d, d.addDays(400), d.addMonths(24)) is False
        assert m.tarihleri_denetle(None, d, d.addDays(2), d.addDays(2)) is False                 # sonraki = bitiş
        assert uyari.call_count == 3
