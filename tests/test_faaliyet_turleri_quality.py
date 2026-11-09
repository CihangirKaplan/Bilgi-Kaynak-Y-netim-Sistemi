"""TKYS - Faaliyet türleri ve geçmiş puan yönetimi QA testleri."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from sunucu import (
    FaaliyetTuruDuzenleModeli,
    faaliyet_turu_duzenle,
    app,
)


def model(ad="QA Test Faaliyeti", puan=10, gecmis=False):
    return FaaliyetTuruDuzenleModeli(
        faaliyet_adi=ad,
        puan=puan,
        gecmis_puanlari_guncelle=gecmis,
    )


def hazirla(eski_ad="QA Test Faaliyeti", eski_puan=8):
    conn = MagicMock()
    cursor = conn.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = (eski_ad, eski_puan)
    cursor.rowcount = 2
    return conn, cursor


def sql_cagrilari(cursor):
    return [
        (c.args[0], c.args[1] if len(c.args) > 1 else ())
        for c in cursor.execute.call_args_list
    ]


def gecmis_update_cagrilari(cursor):
    return [
        (sql, param)
        for sql, param in sql_cagrilari(cursor)
        if "UPDATE ogrenci_faaliyet_takip" in sql
    ]


def test_gecmis_puanlari_koru():
    conn, cursor = hazirla()

    with (
        patch("sunucu.psycopg2.connect", return_value=conn),
        patch("denetim.denetim_kaydi_olustur") as audit,
    ):
        sonuc = faaliyet_turu_duzenle(
            15, model(puan=10, gecmis=False), 1
        )

    assert sonuc["durum"] == "basarili"
    assert sonuc["gecmis_puanlari_guncellendi"] is False
    assert sonuc["guncellenen_gecmis_kayit"] == 0
    assert gecmis_update_cagrilari(cursor) == []
    audit.assert_called_once()
    conn.commit.assert_called_once()
    conn.rollback.assert_not_called()


def test_gecmis_puanlari_guncelle():
    conn, cursor = hazirla()

    with (
        patch("sunucu.psycopg2.connect", return_value=conn),
        patch("denetim.denetim_kaydi_olustur") as audit,
    ):
        sonuc = faaliyet_turu_duzenle(
            15, model(puan=10, gecmis=True), 1
        )

    assert sonuc["gecmis_puanlari_guncellendi"] is True
    assert sonuc["guncellenen_gecmis_kayit"] == 2

    guncellemeler = gecmis_update_cagrilari(cursor)
    assert len(guncellemeler) == 1
    assert guncellemeler[0][1] == (10, 15, 10)

    assert audit.call_count == 2
    assert all(
        c.kwargs["mevcut_cursor"] is cursor
        for c in audit.call_args_list
    )
    conn.commit.assert_called_once()
    conn.rollback.assert_not_called()


def test_yalnizca_isim_degisirse_gecmis_puanlar_korunur():
    conn, cursor = hazirla()

    with (
        patch("sunucu.psycopg2.connect", return_value=conn),
        patch("denetim.denetim_kaydi_olustur") as audit,
    ):
        sonuc = faaliyet_turu_duzenle(
            15,
            model(ad="Yeni QA Faaliyeti", puan=8, gecmis=True),
            1,
        )

    assert sonuc["durum"] == "basarili"
    assert sonuc["guncellenen_gecmis_kayit"] == 0
    assert gecmis_update_cagrilari(cursor) == []
    audit.assert_called_once()
    conn.commit.assert_called_once()


def test_degisen_bilgi_yoksa_audit_olusturulmaz():
    conn, cursor = hazirla()

    with (
        patch("sunucu.psycopg2.connect", return_value=conn),
        patch("denetim.denetim_kaydi_olustur") as audit,
    ):
        sonuc = faaliyet_turu_duzenle(
            15, model(puan=8), 1
        )

    assert sonuc["durum"] == "degisiklik_yok"
    assert gecmis_update_cagrilari(cursor) == []
    audit.assert_not_called()
    conn.commit.assert_called_once()


def test_audit_hatasinda_rollback():
    conn, cursor = hazirla()

    with (
        patch("sunucu.psycopg2.connect", return_value=conn),
        patch(
            "denetim.denetim_kaydi_olustur",
            side_effect=RuntimeError("QA_SECRET_AUDIT_ERROR"),
        ),
    ):
        with pytest.raises(HTTPException) as hata:
            faaliyet_turu_duzenle(
                15, model(puan=10, gecmis=True), 1
            )

    assert hata.value.status_code == 500
    assert "QA_SECRET_AUDIT_ERROR" not in str(hata.value.detail)
    assert len(gecmis_update_cagrilari(cursor)) == 1
    conn.rollback.assert_called_once()
    conn.commit.assert_not_called()


def test_faaliyet_bulunamazsa_404():
    conn, cursor = hazirla()
    cursor.fetchone.return_value = None

    with (
        patch("sunucu.psycopg2.connect", return_value=conn),
        patch("denetim.denetim_kaydi_olustur") as audit,
    ):
        with pytest.raises(HTTPException) as hata:
            faaliyet_turu_duzenle(
                999999, model(), 1
            )

    assert hata.value.status_code == 404
    audit.assert_not_called()
    conn.rollback.assert_called_once()
    conn.commit.assert_not_called()


def test_negatif_puan_reddedilir():
    with pytest.raises(ValidationError):
        model(puan=-1)


def test_gecmis_secimi_zorunludur():
    with pytest.raises(ValidationError):
        FaaliyetTuruDuzenleModeli(
            faaliyet_adi="QA Test",
            puan=10,
        )


def test_gecmis_secimi_boolean_olmali():
    with pytest.raises(ValidationError):
        FaaliyetTuruDuzenleModeli(
            faaliyet_adi="QA Test",
            puan=10,
            gecmis_puanlari_guncelle="evet",
        )


def test_api_yetki_kontrolu_tanimli():
    route = next(
        r for r in app.routes
        if getattr(r, "path", None)
        == "/api/faaliyetler/{faaliyet_id}"
        and "PUT" in getattr(r, "methods", set())
    )

    assert route.dependant.dependencies, (
        "Faaliyet türü düzenleme API'sinde "
        "yetki bağımlılığı bulunmuyor."
    )
