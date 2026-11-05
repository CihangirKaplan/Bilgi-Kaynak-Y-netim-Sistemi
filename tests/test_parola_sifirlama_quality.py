from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException, Response
from fastapi.security import HTTPAuthorizationCredentials

from guvenlik import access_token_olustur, token_parola_gecerli
from sunucu import (
    kullanici_parola_sifirla,
    mevcut_kullanici_id,
    token_kullanici_id,
)


def sahte_vt(*sonuclar):
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchone.side_effect = list(sonuclar)
    return conn, cursor


def kimlik(token):
    return HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=token,
    )


def sifirla(conn, hedef_id=20, yonetici_id=10):
    yanit = Response()

    with patch("sunucu.psycopg2.connect", return_value=conn):
        sonuc = kullanici_parola_sifirla(
            kullanici_id=hedef_id,
            response=yanit,
            islem_yapan_id=yonetici_id,
        )

    return sonuc, yanit


@pytest.mark.parametrize(
    "rol",
    ["MEMUR", "MUDUR", "PSIKOLOG", "DANISMA_OGRENCISI"],
)
def test_admin_olmayan_parola_sifirlayamaz(rol):
    conn, cursor = sahte_vt((rol,))

    with pytest.raises(HTTPException) as hata:
        sifirla(conn)

    assert hata.value.status_code == 403
    conn.commit.assert_not_called()
    cursor.execute.assert_called_once()


def test_yonetici_kendi_parolasini_sifirlayamaz():
    conn = MagicMock()

    with patch("sunucu.psycopg2.connect") as baglanti:
        with pytest.raises(HTTPException) as hata:
            kullanici_parola_sifirla(
                kullanici_id=10,
                response=Response(),
                islem_yapan_id=10,
            )

    assert hata.value.status_code == 403
    baglanti.assert_not_called()


def test_olmayan_kullanici_sifirlanamaz():
    conn, _ = sahte_vt(("ADMIN",), None)

    with pytest.raises(HTTPException) as hata:
        sifirla(conn)

    assert hata.value.status_code == 404
    conn.commit.assert_not_called()
    conn.rollback.assert_called_once()


def test_pasif_kullanici_sifirlanamaz():
    conn, _ = sahte_vt(("ADMIN",), (False,))

    with pytest.raises(HTTPException) as hata:
        sifirla(conn)

    assert hata.value.status_code == 409
    conn.commit.assert_not_called()
    conn.rollback.assert_called_once()


def test_admin_gecici_parola_uretir_ve_audit_yazar():
    conn, cursor = sahte_vt(("ADMIN",), (True,))

    with (
        patch(
            "sunucu.gecici_parola_uret",
            return_value="TEST_GECICI_PAROLA",
        ),
        patch(
            "sunucu.parola_hashle",
            return_value="TEST_HASH",
        ),
    ):
        sonuc, yanit = sifirla(conn)

    assert sonuc["durum"] == "basarili"
    assert sonuc["kullanici_id"] == 20
    assert sonuc["gecici_parola"] == "TEST_GECICI_PAROLA"
    assert yanit.headers["cache-control"] == "no-store"

    sorgular = cursor.execute.call_args_list

    guncellemeler = [
        cagri for cagri in sorgular
        if "UPDATE kullanicilar" in cagri.args[0]
    ]

    assert len(guncellemeler) == 1
    assert guncellemeler[0].args[1] == ("TEST_HASH", 20)
    assert "ilk_giris_mi = TRUE" in guncellemeler[0].args[0]

    audit = [
        cagri for cagri in sorgular
        if "INSERT INTO denetim_kayitlari" in cagri.args[0]
    ]

    assert len(audit) == 1
    assert audit[0].args[1] == (
        10,
        "PASSWORD_RESET",
        "kullanicilar",
        20,
    )

    conn.commit.assert_called_once()
    conn.rollback.assert_not_called()


def test_audit_hatasinda_transaction_geri_alinir():
    conn, cursor = sahte_vt(("ADMIN",), (True,))

    def sorgu(sql, *args):
        if "INSERT INTO denetim_kayitlari" in sql:
            raise RuntimeError("Test audit hatasi")

    cursor.execute.side_effect = sorgu

    with (
        patch(
            "sunucu.gecici_parola_uret",
            return_value="TEST_GECICI_PAROLA",
        ),
        patch(
            "sunucu.parola_hashle",
            return_value="TEST_HASH",
        ),
    ):
        with pytest.raises(HTTPException) as hata:
            sifirla(conn)

    assert hata.value.status_code == 500
    conn.rollback.assert_called_once()
    conn.commit.assert_not_called()


def test_parola_degisince_eski_jwt_gecersiz():
    eski_token = access_token_olustur(20, "ESKI_HASH")

    assert token_parola_gecerli(
        eski_token, "ESKI_HASH"
    )

    assert not token_parola_gecerli(
        eski_token, "YENI_HASH"
    )


def test_eski_jwt_korumali_api_tarafindan_reddedilir():
    eski_token = access_token_olustur(20, "ESKI_HASH")

    conn, _ = sahte_vt((True, False, "YENI_HASH"))

    with patch("sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            mevcut_kullanici_id(
                credentials=kimlik(eski_token)
            )

    assert hata.value.status_code == 401


def test_eski_jwt_sifre_degistirme_api_icin_de_reddedilir():
    eski_token = access_token_olustur(20, "ESKI_HASH")

    conn, _ = sahte_vt(("YENI_HASH", True))

    with patch("sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            token_kullanici_id(
                credentials=kimlik(eski_token)
            )

    assert hata.value.status_code == 401


def test_gecici_parola_sonrasi_sadece_sifre_degistirilebilir():
    yeni_token = access_token_olustur(20, "GECICI_HASH")

    conn, cursor = sahte_vt(("GECICI_HASH", True))

    with patch("sunucu.psycopg2.connect", return_value=conn):
        kullanici_id = token_kullanici_id(
            credentials=kimlik(yeni_token)
        )

    assert kullanici_id == 20

    cursor.fetchone.side_effect = None
    cursor.fetchone.return_value = (
        True, True, "GECICI_HASH"
    )

    with patch("sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            mevcut_kullanici_id(
                credentials=kimlik(yeni_token)
            )

    assert hata.value.status_code == 403
