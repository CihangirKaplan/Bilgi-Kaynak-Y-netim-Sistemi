from types import SimpleNamespace
from unittest.mock import patch

import pytest
import requests

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QMessageBox,
    QTableWidgetItem,
)

from k_personel_ekranlari import KullaniciPersonelEkrani


APP = QApplication.instance() or QApplication([])


@pytest.fixture
def ekran():
    # Gerçek sunucuya bağlanmadan ekranı oluştur.
    with patch.object(KullaniciPersonelEkrani, "verileri_cek"):
        pencere = KullaniciPersonelEkrani(
            "http://127.0.0.1:8001",
            "test-token"
        )

    yield pencere
    pencere.close()


def kullanici_sec(ekran, kullanici_id=20):
    ekran.tablo.setRowCount(1)

    item = QTableWidgetItem("test_kullanici")
    item.setData(Qt.UserRole, kullanici_id)

    ekran.tablo.setItem(0, 1, item)
    ekran.tablo.selectRow(0)


def sahte_cevap(kod, veri):
    return SimpleNamespace(
        status_code=kod,
        json=lambda: veri
    )


def test_kullanici_secilmeden_sifirlama_yapilamaz(ekran):
    with (
        patch("k_personel_ekranlari.QMessageBox.warning") as uyari,
        patch("k_personel_ekranlari.oturum_kontrollu_istek") as api,
    ):
        ekran.secili_kullanici_parola_sifirla()

    uyari.assert_called_once()
    api.assert_not_called()


def test_islem_iptal_edilince_api_cagrilmaz(ekran):
    kullanici_sec(ekran)

    with (
        patch(
            "k_personel_ekranlari.QMessageBox.question",
            return_value=QMessageBox.No,
        ),
        patch("k_personel_ekranlari.oturum_kontrollu_istek") as api,
    ):
        ekran.secili_kullanici_parola_sifirla()

    api.assert_not_called()


def test_basarili_sifirlama_dogru_apiyi_cagirir(ekran):
    kullanici_sec(ekran)

    cevap = sahte_cevap(
        200,
        {
            "durum": "basarili",
            "gecici_parola": "GUVENLI_GECICI_PAROLA",
        },
    )

    with (
        patch(
            "k_personel_ekranlari.QMessageBox.question",
            return_value=QMessageBox.Yes,
        ),
        patch(
            "k_personel_ekranlari.oturum_kontrollu_istek",
            return_value=cevap,
        ) as api,
        patch(
            "k_personel_ekranlari.oturum_hatasi_mi",
            return_value=False,
        ),
        patch(
            "k_personel_ekranlari.GeciciParolaDialog"
        ) as bilgi,
    ):
        ekran.secili_kullanici_parola_sifirla()

    # İlk istek sıfırlamadır; ardından bekleyen talepler paneli tazelenir (ikinci istek, GET).
    assert api.call_count == 2
    assert api.call_args_list[1].args[:2] == ("GET", "http://127.0.0.1:8001/api/parola-sifirlama-talepleri")

    args, kwargs = api.call_args_list[0]

    assert args[0] == "POST"
    assert args[1].endswith(
        "/api/kullanicilar/20/parola-sifirla"
    )
    assert kwargs["headers"]["Authorization"] == (
        "Bearer test-token"
    )

    bilgi.assert_called_once()

    # Pencereye kullanıcı adı ve geçici parola verilir ve pencere gösterilir (exec).
    assert bilgi.call_args.args[:2] == ("test_kullanici", "GUVENLI_GECICI_PAROLA")
    bilgi.return_value.exec.assert_called_once()


def test_yetki_hatasinda_parola_gosterilmez(ekran):
    kullanici_sec(ekran)

    cevap = sahte_cevap(
        403,
        {"detail": "Bu işlem için yetkiniz yok."},
    )

    with (
        patch(
            "k_personel_ekranlari.QMessageBox.question",
            return_value=QMessageBox.Yes,
        ),
        patch(
            "k_personel_ekranlari.oturum_kontrollu_istek",
            return_value=cevap,
        ),
        patch(
            "k_personel_ekranlari.oturum_hatasi_mi",
            return_value=False,
        ),
        patch(
            "k_personel_ekranlari.QMessageBox.warning"
        ) as uyari,
        patch(
            "k_personel_ekranlari.GeciciParolaDialog"
        ) as bilgi,
    ):
        ekran.secili_kullanici_parola_sifirla()

    uyari.assert_called_once()
    bilgi.assert_not_called()


def test_baglanti_hatasinda_tekrar_istek_atilmaz(ekran):
    kullanici_sec(ekran)

    with (
        patch(
            "k_personel_ekranlari.QMessageBox.question",
            return_value=QMessageBox.Yes,
        ),
        patch(
            "k_personel_ekranlari.oturum_kontrollu_istek",
            side_effect=requests.Timeout("Test timeout"),
        ) as api,
        patch(
            "k_personel_ekranlari.QMessageBox.critical"
        ) as hata,
    ):
        ekran.secili_kullanici_parola_sifirla()

    api.assert_called_once()
    hata.assert_called_once()


def test_basarili_yanit_gecici_parola_icermiyorsa_uyar(ekran):
    kullanici_sec(ekran)

    cevap = sahte_cevap(
        200,
        {"durum": "basarili"},
    )

    with (
        patch(
            "k_personel_ekranlari.QMessageBox.question",
            return_value=QMessageBox.Yes,
        ),
        patch(
            "k_personel_ekranlari.oturum_kontrollu_istek",
            return_value=cevap,
        ),
        patch(
            "k_personel_ekranlari.oturum_hatasi_mi",
            return_value=False,
        ),
        patch(
            "k_personel_ekranlari.QMessageBox.warning"
        ) as uyari,
        patch(
            "k_personel_ekranlari.GeciciParolaDialog"
        ) as bilgi,
    ):
        ekran.secili_kullanici_parola_sifirla()

    uyari.assert_called_once()
    bilgi.assert_not_called()
