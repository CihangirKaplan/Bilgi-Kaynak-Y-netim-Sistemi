from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from modeller import RolDegistirModeli
from sunucu import kullanici_rol_degistir


def test_mudur_admin_rolu_atayamaz():
    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value

    mock_cursor.fetchone.side_effect = [
        ("MUDUR",),      # İşlemi yapan kullanıcı
        ("PSIKOLOG",),   # Hedef kullanıcının mevcut rolü
        ("ADMIN",),      # Atanmak istenen yeni rol
    ]

    with patch("sunucu.psycopg2.connect", return_value=mock_conn):
        with pytest.raises(HTTPException) as hata:
            kullanici_rol_degistir(
                kullanici_id=5,
                veri=RolDegistirModeli(rol_id=1),
                islem_yapan_id=10,
            )

    assert hata.value.status_code == 403

    # Veritabanında rol değişikliği yapılmamalı
    sorgular = [
        call.args[0].strip().upper()
        for call in mock_cursor.execute.call_args_list
    ]

    assert not any(
        sorgu.startswith("UPDATE") for sorgu in sorgular
    )

    mock_conn.rollback.assert_called_once()
    mock_conn.commit.assert_not_called()
def test_mudur_admin_kullanicisinin_rolunu_degistiremez():
    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value

    mock_cursor.fetchone.side_effect = [
        ("MUDUR",),       # İşlemi yapan
        ("ADMIN",),       # Hedef kullanıcının mevcut rolü
        ("PSIKOLOG",),    # Atanmak istenen yeni rol
    ]

    with patch("sunucu.psycopg2.connect", return_value=mock_conn):
        with pytest.raises(HTTPException) as hata:
            kullanici_rol_degistir(
                kullanici_id=5,
                veri=RolDegistirModeli(rol_id=2),
                islem_yapan_id=10,
            )

    assert hata.value.status_code == 403

    sorgular = [
        call.args[0].strip().upper()
        for call in mock_cursor.execute.call_args_list
    ]

    assert not any(
        sorgu.startswith("UPDATE") for sorgu in sorgular
    )

    mock_conn.rollback.assert_called_once()
    mock_conn.commit.assert_not_called()
def test_mudur_psikolog_rolunu_memur_yapabilir():
    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value

    mock_cursor.fetchone.side_effect = [
        ("MUDUR",),       # İşlemi yapan
        ("PSIKOLOG",),    # Hedef kullanıcının mevcut rolü
        ("MEMUR",),       # Atanacak yeni rol
    ]

    with patch("sunucu.psycopg2.connect", return_value=mock_conn):
        sonuc = kullanici_rol_degistir(
            kullanici_id=5,
            veri=RolDegistirModeli(rol_id=3),
            islem_yapan_id=10,
        )

    assert sonuc["kullanici_id"] == 5
    assert sonuc["yeni_rol_id"] == 3
    assert sonuc["yeni_rol_adi"] == "MEMUR"

    # Rol güncellemesi yapılmış mı?
    sorgular = [
        call.args[0].strip().upper()
        for call in mock_cursor.execute.call_args_list
    ]

    assert any(
        sorgu.startswith("UPDATE KULLANICILAR")
        for sorgu in sorgular
    )

    # Audit kaydı oluşturulmuş mu?
    assert any(
        "INSERT INTO DENETIM_KAYITLARI" in sorgu
        for sorgu in sorgular
    )

    # İşlem kaydedilmiş mi?
    mock_conn.commit.assert_called_once()
    mock_conn.rollback.assert_not_called()
    audit_cagrilari = [
        call
        for call in mock_cursor.execute.call_args_list
        if "INSERT INTO denetim_kayitlari" in call.args[0]
    ]

    assert len(audit_cagrilari) == 1

    assert audit_cagrilari[0].args[1] == (
        10,             # İşlemi yapan müdürün kullanıcı ID'si
        "ROLE_CHANGE",  # Audit olay türü
        "kullanicilar", # Hedef tablo
        5               # Rolü değiştirilen kullanıcının ID'si
    )
def test_yetkisiz_kullanici_rol_degistiremez():
    from sunucu import izin_kontrol

    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value

    # Kullanıcının ROL_ATAMA_DEGISTIRME izni bulunmuyor
    mock_cursor.fetchone.return_value = (0,)

    with patch("sunucu.psycopg2.connect", return_value=mock_conn):
        with pytest.raises(HTTPException) as hata:
            izin_kontrol("ROL_ATAMA_DEGISTIRME")(
                kullanici_id=10
            )

    assert hata.value.status_code == 403
    mock_conn.close.assert_called_once()
def test_olmayan_kullanicinin_rolu_degistirilemez():
    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value

    mock_cursor.fetchone.side_effect = [
        ("MUDUR",),  # İşlemi yapan kullanıcı
        None,        # Hedef kullanıcı bulunamadı
    ]

    with patch("sunucu.psycopg2.connect", return_value=mock_conn):
        with pytest.raises(HTTPException) as hata:
            kullanici_rol_degistir(
                kullanici_id=999,
                veri=RolDegistirModeli(rol_id=2),
                islem_yapan_id=10,
            )

    assert hata.value.status_code == 404
    assert hata.value.detail == "Kullanıcı bulunamadı."

    sorgular = [
        call.args[0].strip().upper()
        for call in mock_cursor.execute.call_args_list
    ]

    assert not any(
        sorgu.startswith("UPDATE") for sorgu in sorgular
    )

    mock_conn.rollback.assert_called_once()
    mock_conn.commit.assert_not_called()
def test_olmayan_rol_atanamaz():
    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value

    mock_cursor.fetchone.side_effect = [
        ("MUDUR",),     # İşlemi yapan kullanıcı
        ("PSIKOLOG",),  # Hedef kullanıcının mevcut rolü
        None,           # Yeni rol veritabanında bulunamadı
    ]

    with patch("sunucu.psycopg2.connect", return_value=mock_conn):
        with pytest.raises(HTTPException) as hata:
            kullanici_rol_degistir(
                kullanici_id=5,
                veri=RolDegistirModeli(rol_id=999),
                islem_yapan_id=10,
            )

    assert hata.value.status_code == 404
    assert hata.value.detail == "Atanacak rol bulunamadı."

    sorgular = [
        call.args[0].strip().upper()
        for call in mock_cursor.execute.call_args_list
    ]

    assert not any(
        sorgu.startswith("UPDATE") for sorgu in sorgular
    )

    mock_conn.rollback.assert_called_once()
    mock_conn.commit.assert_not_called()
def test_rol_degistirme_token_olmadan_reddedilir():
    from fastapi.testclient import TestClient
    from sunucu import app

    with TestClient(app) as client:
        yanit = client.patch(
            "/api/kullanicilar/5/rol",
            json={"rol_id": 2}
        )

    assert yanit.status_code in (401, 403)

def test_psikolog_http_uzerinden_rol_degistiremez():
    from fastapi.testclient import TestClient
    from sunucu import app, mevcut_kullanici_id

    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value

    # Psikoloğun rol değiştirme izni yok
    mock_cursor.fetchone.return_value = (0,)

    # Yalnızca kimlik doğrulama aşamasını taklit ediyoruz
    app.dependency_overrides[mevcut_kullanici_id] = lambda: 10

    try:
        with patch("sunucu.psycopg2.connect", return_value=mock_conn):
            with TestClient(app) as client:
                yanit = client.patch(
                    "/api/kullanicilar/5/rol",
                    json={"rol_id": 2},
                )

        assert yanit.status_code == 403
        mock_conn.commit.assert_not_called()

    finally:
        app.dependency_overrides.pop(mevcut_kullanici_id, None)