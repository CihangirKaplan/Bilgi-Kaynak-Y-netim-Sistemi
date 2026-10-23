from unittest.mock import patch

import pytest
from fastapi import HTTPException

from modeller import OdaGuncelleModeli
from sunucu import oda_guncelle


def test_zararli_oda_adi_sql_sorgusuna_eklenmez():
    zararli_deger = "Oda'; DROP TABLE odalar; --"

    with patch("sunucu.psycopg2.connect") as mock_connect:
        cursor = mock_connect.return_value.cursor.return_value
        cursor.fetchone.side_effect = [
            (1,),
            (1, zararli_deger, 2, True),
        ]

        sonuc = oda_guncelle(
            oda_id=1,
            oda=OdaGuncelleModeli(oda_adi=zararli_deger),
            kullanici_id=1,
        )

        sorgular = cursor.execute.call_args_list
        update_cagrisi = next(
            c for c in sorgular
            if c.args[0].startswith("UPDATE odalar SET")
        )

        sql = update_cagrisi.args[0]
        parametreler = update_cagrisi.args[1]

        assert zararli_deger not in sql
        assert "oda_adi = %s" in sql
        assert parametreler == (zararli_deger, 1)
        assert sonuc["durum"] == "basarili"


def test_izin_verilmeyen_sql_alanlari_yok_sayilir():
    veri = OdaGuncelleModeli.model_validate({
        "oda_adi": "Test Odası",
        "aktif_mi; DROP TABLE odalar; --": True,
    })

    assert veri.model_dump(exclude_unset=True) == {
        "oda_adi": "Test Odası"
    }


def test_yalnizca_gecersiz_alan_gonderilirse_reddedilir():
    veri = OdaGuncelleModeli.model_validate({
        "oda_adi; DROP TABLE odalar; --": "zararli",
    })

    with patch("sunucu.psycopg2.connect") as mock_connect:
        with pytest.raises(HTTPException) as hata:
            oda_guncelle(
                oda_id=1,
                oda=veri,
                kullanici_id=1,
            )

        assert hata.value.status_code == 422
        mock_connect.assert_not_called()


@pytest.mark.parametrize(
    "yol,metot,model_sinifi,tablo,alan",
    [
        (
            "/api/bakimlar/{bakim_id}",
            "PUT",
            "BakimGuncelleModeli",
            "cihaz_bakimlari",
            "bakim_yapan_kisi",
        ),
        (
            "/api/kalibrasyonlar/{kalibrasyon_id}",
            "PUT",
            "KalibrasyonGuncelleModeli",
            "cihaz_kalibrasyonlari",
            "sertifika_no",
        ),
    ],
)
def test_bakim_kalibrasyon_sql_injection(
    yol, metot, model_sinifi, tablo, alan
):
    import modeller
    from sunucu import app

    zararli_deger = "Test'; DROP TABLE kullanicilar; --"

    model = getattr(modeller, model_sinifi)(
        **{alan: zararli_deger}
    )

    rota = next(
        r for r in app.routes
        if r.path == yol and metot in getattr(r, "methods", set())
    )

    kimlik_alani = (
        "bakim_id" if tablo == "cihaz_bakimlari"
        else "kalibrasyon_id"
    )

    with patch("sunucu.psycopg2.connect") as baglanti:
        with patch("sunucu.denetim_kaydi_olustur"):
            cursor = baglanti.return_value.cursor.return_value
            cursor.fetchone.return_value = (1,)

            rota.endpoint(
                **{
                    kimlik_alani: 1,
                    "guncelleme": model,
                    "kullanici_id": 1,
                }
            )

            sorgu_cagrisi = next(
                c for c in cursor.execute.call_args_list
                if c.args[0].startswith(f"UPDATE {tablo} SET")
            )

            sql = sorgu_cagrisi.args[0]
            parametreler = sorgu_cagrisi.args[1]

            assert zararli_deger not in sql
            assert f"{alan} = %s" in sql
            assert parametreler == (zararli_deger, 1)
