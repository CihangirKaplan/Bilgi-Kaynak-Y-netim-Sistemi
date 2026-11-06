from types import SimpleNamespace
from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QApplication

from k_personel_ekranlari import RolDegistirFormu
from modeller import RolDegistirModeli


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def cevap(kod, veri):
    return SimpleNamespace(
        status_code=kod,
        json=lambda: veri,
        text=str(veri),
    )


def form_olustur():
    return RolDegistirFormu(
        "http://test", "test-token",
        5, "test_psikolog", "PSIKOLOG",
    )


def test_yeni_ogrenci_bilgileri_apiye_gonderilir(qt_app):
    with (
        patch(
            "k_personel_ekranlari.oturum_kontrollu_istek",
            side_effect=[
                cevap(200, {"ogrenci_kaydi_var": False}),
                cevap(200, {"mesaj": "Başarılı"}),
            ],
        ) as istek,
        patch(
            "k_personel_ekranlari.oturum_hatasi_mi",
            return_value=False,
        ),
        patch("k_personel_ekranlari.QMessageBox.information"),
    ):
        form = form_olustur()

        try:
            form.combo_rol.setCurrentIndex(
                form.combo_rol.findData(4)
            )

            assert form.ogrenci_kaydi_var is False
            assert not form.ogrenci_kutusu.isHidden()

            form.input_ad_soyad.setText("Ayşe Test")
            form.input_ogrenci_no.setText("202600123")
            form.input_telefon.setText("")

            form.kaydet()

            assert istek.call_count == 2
            assert istek.call_args_list[0].args[0] == "GET"

            son_istek = istek.call_args_list[1]
            assert son_istek.args[0] == "PATCH"

            veri = son_istek.kwargs["json"]
            assert veri["rol_id"] == 4
            assert veri["ad_soyad"] == "Ayşe Test"
            assert veri["ogrenci_numarasi"] == "202600123"

        finally:
            form.close()


def test_mevcut_ogrenci_kaydi_korunur(qt_app):
    with (
        patch(
            "k_personel_ekranlari.oturum_kontrollu_istek",
            side_effect=[
                cevap(200, {"ogrenci_kaydi_var": True}),
                cevap(200, {"mesaj": "Başarılı"}),
            ],
        ) as istek,
        patch(
            "k_personel_ekranlari.oturum_hatasi_mi",
            return_value=False,
        ),
        patch("k_personel_ekranlari.QMessageBox.information"),
    ):
        form = form_olustur()

        try:
            form.combo_rol.setCurrentIndex(
                form.combo_rol.findData(4)
            )

            assert form.ogrenci_kaydi_var is True
            assert form.ogrenci_kutusu.isHidden()

            form.kaydet()

            veri = istek.call_args_list[1].kwargs["json"]
            assert veri == {"rol_id": 4}

        finally:
            form.close()


def test_ogrenci_kaydi_sorgulanamazsa_kaydetme_engellenir(qt_app):
    with (
        patch(
            "k_personel_ekranlari.oturum_kontrollu_istek",
            return_value=cevap(503, {}),
        ) as istek,
        patch(
            "k_personel_ekranlari.oturum_hatasi_mi",
            return_value=False,
        ),
    ):
        form = form_olustur()

        try:
            form.combo_rol.setCurrentIndex(
                form.combo_rol.findData(4)
            )

            assert form.ogrenci_kaydi_var is None
            assert not form.btn_kaydet.isEnabled()
            assert istek.call_count == 1

        finally:
            form.close()


def test_ogrenci_numarasi_sadece_rakamlardan_olusur():
    with pytest.raises(ValueError):
        RolDegistirModeli(
            rol_id=4,
            ad_soyad="Ayşe Test",
            ogrenci_numarasi="ABC123",
        )

    model = RolDegistirModeli(
        rol_id=4,
        ad_soyad="Ayşe Test",
        ogrenci_numarasi="202600123",
    )

    assert model.ogrenci_numarasi == "202600123"


def test_gecmis_gorev_tarihi_turkce_bicimde():
    from danisma_masasi_ekrani import gecmis_gorev_tarihi_bicimle

    assert gecmis_gorev_tarihi_bicimle("2026-11-06") == "06.11.2026"
    assert gecmis_gorev_tarihi_bicimle(
        "2026-11-04T13:30:00"
    ) == "04.11.2026"
    assert gecmis_gorev_tarihi_bicimle(None) == "—"
