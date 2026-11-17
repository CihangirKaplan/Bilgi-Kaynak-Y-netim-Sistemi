"""Cihazlardan "zimmetli oda" alanı kaldırıldı: model, uçlar, form ve migrasyon artık bu alanı bilmez."""
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import server.sunucu as sunucu
from server.modeller import CihazGuncelleModeli, CihazModeli, CihazOlusturModeli

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
KOK = Path(__file__).resolve().parents[2]


def baglanti(satirlar=None, bir_satir=None):
    conn = MagicMock()
    imlec = conn.cursor.return_value
    imlec.fetchall.return_value = satirlar or []
    imlec.fetchone.return_value = bir_satir
    return conn, imlec


def test_modeller_zimmetli_oda_alanini_tasimaz_eski_istemcinin_alani_yok_sayilir():
    for model in (CihazModeli, CihazOlusturModeli, CihazGuncelleModeli):
        assert "zimmetli_oda_id" not in model.model_fields
    yeni = CihazOlusturModeli(envanter_kodu="C-1", cihaz_adi="EEG", zimmetli_oda_id=3)           # eski istemci hâlâ gönderse de hata vermez
    assert "zimmetli_oda_id" not in yeni.model_dump()
    assert CihazGuncelleModeli(zimmetli_oda_id=3).model_dump(exclude_unset=True) == {}            # tek başına güncelleme alanı sayılmaz


def test_cihaz_listesi_ve_detayi_zimmetli_oda_dondurmez():
    satir = (1, "E-1", "EEG", "Marka", "SN1", "Kullanima_Hazir", "2026-10-13")
    conn, imlec = baglanti(satirlar=[satir], bir_satir=satir)
    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        liste = sunucu.cihazlari_listele(kullanici_id=1)
        detay = sunucu.cihaz_detayi_getir(1, kullanici_id=1)
    assert liste[0] == detay == {"cihaz_id": 1, "envanter_kodu": "E-1", "cihaz_adi": "EEG", "marka_model": "Marka", "seri_no": "SN1",
                                 "durum": "Kullanima_Hazir", "kayit_tarihi": "2026-10-13"}
    assert all("zimmetli" not in str(c.args[0]) for c in imlec.execute.call_args_list)


def test_cihaz_eklerken_zimmetli_oda_sutunu_kullanilmaz():
    conn, imlec = baglanti(bir_satir=None)
    imlec.fetchone.side_effect = [None, (7,)]                       # önce "var mı" kontrolü, sonra RETURNING cihaz_id
    with patch("server.sunucu.psycopg2.connect", return_value=conn), patch("server.sunucu.denetim_kaydi_olustur"):
        sonuc = sunucu.cihaz_ekle(CihazOlusturModeli(envanter_kodu="C-9", cihaz_adi="Yeni"), kullanici_id=1)
    assert sonuc["cihaz_id"] == 7
    ekleme = next(c for c in imlec.execute.call_args_list if "INSERT INTO cihazlar" in str(c.args[0]))
    assert "zimmetli" not in ekleme.args[0] and len(ekleme.args[1]) == 5


def test_cihaz_formunda_zimmetli_oda_kutusu_yok():
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    import client.cihaz_ekranlari as m
    with patch.object(m, "oturum_kontrollu_istek", side_effect=AssertionError("oda listesi istenmemeli")):
        form = m.CihazIslemFormu("http://x", "T")
    try:
        assert not hasattr(form, "cmb_oda") and not hasattr(form, "odalari_yukle")
    finally:
        from PySide6.QtCore import QCoreApplication, QEvent
        form.close()
        form.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_migrasyon_sutunu_kaldirir_ve_geri_almada_boş_sutunu_geri_ekler():
    metin = next((KOK / "database/migrations/versions").glob("d9a3f6b2c815_*.py")).read_text(encoding="utf-8")
    assert 'down_revision: Union[str, Sequence[str], None] = "d5b9f2c7a418"' in metin
    assert "DROP COLUMN IF EXISTS zimmetli_oda_id" in metin and "ADD COLUMN IF NOT EXISTS zimmetli_oda_id" in metin


@pytest.mark.parametrize("dosya", ["database/01_cihaz_tablolari.sql", "database/04_test_verisi.sql",
                                   "docs/architecture/D04_Data_Dictionary.md", "docs/architecture/cihaz_ve_randevu_sistemi_er_diyagram.md"])
def test_belge_ve_sql_dosyalari_zimmetli_odayi_anmaz(dosya):
    assert "zimmetli" not in (KOK / dosya).read_text(encoding="utf-8").lower()
