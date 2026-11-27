"""Denetim kayıtlarına "önceki → yeni" ayrıntısı, izin oluşturma denetimi ve audit süzgeci (veritabanı sahte imleçle taklit edilir).

Gerçek veritabanı karşılıkları test_psikolog_pasif_oda_pg_quality.py'dedir.
"""
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from psycopg2.errors import UniqueViolation

from client.audit_kayitlari_ekrani import ayrinti_satirlari
from server.denetim import ayrintili_kayit_yaz
from server.modeller import IzinDuzenleModeli
from server.sunucu import audit_kayitlarini_getir, izin_duzenle, izin_ekle


# ------------------------------------------------------------------ yardımcı
def test_ayrintili_kayit_yazilan_alanlari_aynen_json_olarak_saklar():
    cursor = MagicMock()
    ayrintili_kayit_yaz(cursor, 5, "UPDATE", "izinler", 9, onceki={"a": 1}, yeni={"a": 2}, neden="Türkçe öğe")
    sql, parametreler = cursor.execute.call_args.args
    assert "ayrinti" in sql and parametreler[:4] == (5, "UPDATE", "izinler", 9)
    assert parametreler[4].adapted == {"onceki": {"a": 1}, "yeni": {"a": 2}, "neden": "Türkçe öğe"}


# ------------------------------------------------------------------ izin düzenleme
def _izin_duzenle(onceki_roller, secilen, eski_ad="Eski", yeni_ad="Yeni"):
    conn = MagicMock()
    c = conn.cursor.return_value
    c.fetchone.side_effect = [(9, "RANDEVU_DUZENLE", eski_ad)]
    c.fetchall.side_effect = [[(1, "ADMIN"), (2, "MEMUR"), (3, "MUDUR")], [(r,) for r in onceki_roller]]
    denetim = MagicMock()
    with patch("server.sunucu.psycopg2.connect", return_value=conn), patch("server.rol_api.denetim_kaydi_olustur", denetim):
        izin_duzenle(9, IzinDuzenleModeli(gorunen_ad=yeni_ad, verilen_rol_idleri=secilen), kullanici_id=1)
    return denetim.call_args.kwargs["ayrinti"]


def test_izin_duzenleme_hangi_rollere_verildi_alindi_kaydeder():
    ayrinti = _izin_duzenle(onceki_roller=[1, 2], secilen=[1, 3])
    assert ayrinti["izin"] == "RANDEVU_DUZENLE"
    assert ayrinti["onceki"] == {"gorunen_ad": "Eski", "verilen_roller": ["ADMIN", "MEMUR"]}
    assert ayrinti["yeni"] == {"gorunen_ad": "Yeni", "verilen_roller": ["ADMIN", "MUDUR"]}
    assert ayrinti["eklenen_roller"] == ["MUDUR"] and ayrinti["kaldirilan_roller"] == ["MEMUR"]


def test_izin_degismediyse_eklenen_ve_kaldirilan_bos():
    ayrinti = _izin_duzenle(onceki_roller=[1, 2], secilen=[1, 2], eski_ad="Aynı", yeni_ad="Aynı")
    assert ayrinti["eklenen_roller"] == [] and ayrinti["kaldirilan_roller"] == []


# ------------------------------------------------------------------ izin oluşturma
def test_izin_olusturma_denetime_yazilir_ve_nasil_verildigini_kaydeder():
    conn = MagicMock()
    conn.cursor.return_value.fetchone.return_value = (77,)
    with patch("server.sunucu.psycopg2.connect", return_value=conn), patch("server.rol_api.ayrintili_kayit_yaz") as yaz:
        yanit = izin_ekle({"izin_adi": "YENI_IZIN"}, kullanici_id=1)
    assert yanit["izin_id"] == 77
    assert yaz.call_args.args[2:5] == ("CREATE", "izinler", 77)
    assert yaz.call_args.kwargs["yeni"] == {"izin_adi": "YENI_IZIN", "verilen_roller": ["ADMIN"]}        # yeni izin yalnızca ADMIN'de açılır
    conn.commit.assert_called_once()


def test_ayni_adli_izin_500_degil_409_verir():
    conn = MagicMock()
    conn.cursor.return_value.execute.side_effect = UniqueViolation()
    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            izin_ekle({"izin_adi": "VAR_OLAN"}, kullanici_id=1)
    assert hata.value.status_code == 409 and "zaten" in hata.value.detail
    conn.rollback.assert_called()


# ------------------------------------------------------------------ audit süzgeci
@pytest.mark.parametrize("olay", ["PASSWORD_RESET", "PASSWORD_CHANGE", "PASSWORD_CHANGE_FAILED", "EXPORT", "ROLE_CHANGE"])
def test_audit_suzgeci_veritabanindaki_tum_olay_turlerini_kabul_eder(olay):
    conn = MagicMock()
    c = conn.cursor.return_value
    c.fetchone.return_value = (0, 0, 0, 0)
    c.fetchall.return_value = []
    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        yanit = audit_kayitlarini_getir(kullanici=None, olay_turu=[olay], baslangic_tarihi=None, bitis_tarihi=None, limit=50, offset=0, kullanici_id=1)
    assert yanit["kayitlar"] == []


def test_gecersiz_olay_turu_yine_reddedilir():
    with pytest.raises(HTTPException) as hata:
        audit_kayitlarini_getir(kullanici=None, olay_turu=["YOK_BOYLE"], baslangic_tarihi=None, bitis_tarihi=None, limit=50, offset=0, kullanici_id=1)
    assert hata.value.status_code == 422


# ------------------------------------------------------------------ ekranda gösterim
def test_onceki_yeni_degerler_okunur_etiket_ve_ic_ice_deger_olarak_gosterilir():
    satirlar = dict(ayrinti_satirlari({
        "onceki": {"rol": "PSIKOLOG", "personel_kodu": "PSK-001"}, "yeni": {"rol": "MEMUR", "personel_kodu": "MEM-004"},
        "eklenen_roller": ["MUDUR"], "kaldirilan_roller": [], "pasife_alinan_danisan": 3}))
    assert satirlar["Önceki değer"] == "Rol: PSIKOLOG, Personel kodu: PSK-001"
    assert satirlar["Yeni değer"] == "Rol: MEMUR, Personel kodu: MEM-004"
    assert satirlar["Rolü eklenenler"] == "MUDUR" and satirlar["Rolü kaldırılanlar"] == "—" and satirlar["Pasife alınan danışan"] == "3"


def test_bool_ve_bos_degerler_okunur_gosterilir():
    satirlar = dict(ayrinti_satirlari({"onceki": {"aktif_mi": True}, "yeni": {"aktif_mi": False}, "neden": None}))
    assert satirlar["Önceki değer"] == "Aktif mi: Evet" and satirlar["Yeni değer"] == "Aktif mi: Hayır" and satirlar["Neden"] == "—"
