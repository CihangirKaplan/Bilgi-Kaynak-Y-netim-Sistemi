from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from PySide6.QtWidgets import QApplication

from k_personel_ekranlari import (
    KullaniciPersonelEkrani,
    RolDegistirFormu,
    kayit_tarihi_bicimle,
)
from modeller import RolDegistirModeli
from sunucu import kullanici_rol_degistir


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def sahte_rol_listesi(monkeypatch):
    """Rol değiştirme formu testlerinde gerçek API'ye bağlanma."""
    import k_personel_ekranlari as modul

    def rolleri_yukle(api_url, token, combo, islem):
        assert islem == "degistirme"
        combo.addItem("Psikolog", 1)
        combo.addItem("Memur", 2)
        combo.addItem("Danışma Masası Öğrencisi", 4)

    monkeypatch.setattr(
        modul,
        "atanabilir_rolleri_yukle",
        rolleri_yukle,
    )


def test_kayit_tarihi_turkce_bicimde():
    assert kayit_tarihi_bicimle("2026-11-06T09:33:24") == "06.11.2026"
    assert kayit_tarihi_bicimle("2026-01-05") == "05.01.2026"
    assert kayit_tarihi_bicimle(None) == "—"


def test_kayit_tarihi_tabloda_dogru_gosterilir(qt_app):
    cevap = SimpleNamespace(
        status_code=200,
        json=lambda: [{
            "personel_id": 1,
            "kullanici_id": 5,
            "kullanici_adi": "test_psikolog",
            "personel_kodu": "PSK001",
            "rol_adi": "PSIKOLOG",
            "aktif_mi": True,
            "olusturulma_tarihi": "2026-11-06T09:33:24",
        }],
    )

    with (
        patch(
            "k_personel_ekranlari.oturum_kontrollu_istek",
            return_value=cevap,
        ),
        patch(
            "k_personel_ekranlari.oturum_hatasi_mi",
            return_value=False,
        ),
    ):
        ekran = KullaniciPersonelEkrani("http://test", "test-token")

    try:
        assert ekran.tablo.item(0, 5).text() == "06.11.2026"
    finally:
        ekran.close()


def test_ayni_rol_seciminde_api_cagrilmaz(qt_app):
    form = RolDegistirFormu(
        "http://test", "test-token", 5,
        "test_psikolog", "PSIKOLOG",
    )
    form.combo_rol.setCurrentIndex(form.combo_rol.findData(1))

    try:
        with (
            patch("k_personel_ekranlari.QMessageBox.information") as bilgi,
            patch("k_personel_ekranlari.oturum_kontrollu_istek") as api,
        ):
            form.kaydet()

        bilgi.assert_called_once()
        assert "zaten" in bilgi.call_args.args[2]
        api.assert_not_called()
    finally:
        form.close()


def test_api_409_mesaji_bilgilendirme_olarak_gosterilir(qt_app):
    form = RolDegistirFormu(
        "http://test", "test-token", 5,
        "test_psikolog", "PSIKOLOG",
    )
    form.combo_rol.setCurrentIndex(form.combo_rol.findData(2))

    cevap = SimpleNamespace(
        status_code=409,
        json=lambda: {"detail": "Kullanıcı zaten seçilen role sahip."},
    )

    try:
        with (
            patch(
                "k_personel_ekranlari.oturum_kontrollu_istek",
                return_value=cevap,
            ) as api,
            patch(
                "k_personel_ekranlari.oturum_hatasi_mi",
                return_value=False,
            ),
            patch("k_personel_ekranlari.QMessageBox.information") as bilgi,
        ):
            form.kaydet()

        api.assert_called_once()
        bilgi.assert_called_once()
        assert "zaten" in bilgi.call_args.args[2]
    finally:
        form.close()


def test_ayni_rol_api_tarafinda_guncellenmez():
    baglanti = MagicMock()
    cursor = baglanti.cursor.return_value
    cursor.fetchone.side_effect = [
        ("ADMIN",),
        ("PSIKOLOG",),
        ("PSIKOLOG",),
    ]

    with patch("sunucu.psycopg2.connect", return_value=baglanti):
        with pytest.raises(HTTPException) as hata:
            kullanici_rol_degistir(
                kullanici_id=5,
                veri=RolDegistirModeli(rol_id=1),
                islem_yapan_id=10,
            )

    assert hata.value.status_code == 409

    sorgular = [
        cagri.args[0].upper()
        for cagri in cursor.execute.call_args_list
    ]

    assert not any(
        "UPDATE KULLANICILAR" in sorgu for sorgu in sorgular
    )
    assert not any(
        "INSERT INTO DENETIM_KAYITLARI" in sorgu
        for sorgu in sorgular
    )

    baglanti.commit.assert_not_called()
    baglanti.rollback.assert_called_once()
