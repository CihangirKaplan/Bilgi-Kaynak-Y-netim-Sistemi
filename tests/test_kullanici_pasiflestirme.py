from unittest.mock import MagicMock, patch

from sunucu import kullanici_durum_degistir


def test_mudur_psikolog_kullanicisini_pasiflestirebilir():
    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value

    mock_cursor.fetchone.side_effect = [
        ("MUDUR",),         # İşlemi yapan kullanıcının rolü
        ("PSIKOLOG", True), # Hedef kullanıcının rolü ve aktiflik durumu
    ]

    with patch("sunucu.psycopg2.connect", return_value=mock_conn):
        sonuc = kullanici_durum_degistir(
            kullanici_id=5,
            islem_yapan_id=10,
        )

    assert sonuc["kullanici_id"] == 5
    assert sonuc["yeni_durum"] is False

    sorgular = [
        call.args[0].strip().upper()
        for call in mock_cursor.execute.call_args_list
    ]

    # Kullanıcı pasifleştirilmeli
    for tablo in ("KULLANICILAR", "PERSONEL"):
        assert any(
            c.args[0].strip().upper().startswith(f"UPDATE {tablo}")
            and c.args[1] == (False, 5)
            for c in mock_cursor.execute.call_args_list
        )

    # Audit kaydı oluşturulmalı
    assert any(
        "INSERT INTO DENETIM_KAYITLARI" in sorgu
        for sorgu in sorgular
    )

    mock_conn.commit.assert_called_once()
    mock_conn.rollback.assert_not_called()
def test_mudur_admin_kullanicisini_pasiflestiremez():
    import pytest
    from fastapi import HTTPException

    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value

    mock_cursor.fetchone.side_effect = [
        ("MUDUR",),
        ("ADMIN", True),
    ]

    with patch("sunucu.psycopg2.connect", return_value=mock_conn):
        with pytest.raises(HTTPException) as hata:
            kullanici_durum_degistir(
                kullanici_id=5,
                islem_yapan_id=10,
            )

    assert hata.value.status_code == 403

    sorgular = [
        call.args[0].strip().upper()
        for call in mock_cursor.execute.call_args_list
    ]

    assert not any(
        sorgu.startswith("UPDATE KULLANICILAR")
        for sorgu in sorgular
    )

    mock_conn.rollback.assert_called_once()
    mock_conn.commit.assert_not_called()
def test_kullanici_kendi_hesabini_pasiflestiremez():
    import pytest
    from fastapi import HTTPException

    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value

    with patch("sunucu.psycopg2.connect", return_value=mock_conn):
        with pytest.raises(HTTPException) as hata:
            kullanici_durum_degistir(
                kullanici_id=10,
                islem_yapan_id=10,
            )

    assert hata.value.status_code == 403

    # Hiçbir UPDATE işlemi yapılmamalı
    mock_cursor.execute.assert_not_called()

    # İşlem geri alınmalı
    mock_conn.rollback.assert_called_once()
    mock_conn.commit.assert_not_called()
def test_pasif_kullanici_yeniden_aktiflestirilebilir():
    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value

    mock_cursor.fetchone.side_effect = [
        ("MUDUR",),
        ("PSIKOLOG", False),
    ]

    with patch("sunucu.psycopg2.connect", return_value=mock_conn):
        sonuc = kullanici_durum_degistir(
            kullanici_id=5,
            islem_yapan_id=10,
        )

    assert sonuc["yeni_durum"] is True

    for tablo in ("KULLANICILAR", "PERSONEL"):
        assert any(
            c.args[0].strip().upper().startswith(f"UPDATE {tablo}")
            and c.args[1] == (True, 5)
            for c in mock_cursor.execute.call_args_list
        )

    mock_conn.commit.assert_called_once()
    mock_conn.rollback.assert_not_called()


def test_yetkisiz_kullanici_pasiflestiremez():
    import pytest
    from fastapi import HTTPException
    from sunucu import izin_kontrol

    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value

    # Kullanıcının KULLANICI_PASIFLESTIR izni yok
    mock_cursor.fetchone.return_value = (0,)

    with patch("sunucu.psycopg2.connect", return_value=mock_conn):
        with pytest.raises(HTTPException) as hata:
            izin_kontrol("KULLANICI_PASIFLESTIR")(
                kullanici_id=10
            )

    assert hata.value.status_code == 403

    mock_conn.close.assert_called_once()


    mock_cursor.fetchone.side_effect = [
        ("MUDUR",),  # İşlemi yapan kullanıcı
        None,        # Hedef kullanıcı bulunamadı
    ]

    with patch("sunucu.psycopg2.connect", return_value=mock_conn):
        with pytest.raises(HTTPException) as hata:
            kullanici_durum_degistir(
                kullanici_id=999,
                islem_yapan_id=10,
            )

    assert hata.value.status_code == 404
    assert hata.value.detail == "Kullanıcı bulunamadı."

    # Kullanıcı güncellenmemeli
    sorgular = [
        call.args[0].strip().upper()
        for call in mock_cursor.execute.call_args_list
    ]

    assert not any(
        sorgu.startswith("UPDATE KULLANICILAR")
        for sorgu in sorgular
    )

    mock_conn.rollback.assert_called_once()
    mock_conn.commit.assert_not_called()
def test_pasiflestirme_audit_kaydi_dogru_olusturulur():
    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value

    mock_cursor.fetchone.side_effect = [
        ("MUDUR",),
        ("PSIKOLOG", True),
    ]

    with patch("sunucu.psycopg2.connect", return_value=mock_conn):
        kullanici_durum_degistir(
            kullanici_id=5,
            islem_yapan_id=10,
        )

    audit_cagrilari = [
        call
        for call in mock_cursor.execute.call_args_list
        if "INSERT INTO denetim_kayitlari" in call.args[0]
    ]

    assert len(audit_cagrilari) == 1

    assert audit_cagrilari[0].args[1] == (
        10,             # İşlemi yapan kullanıcı
        "UPDATE",       # Audit olay türü
        "kullanicilar", # Hedef tablo
        5               # Pasifleştirilen kullanıcı
    )

    mock_conn.commit.assert_called_once()
def test_pasif_kullanici_mevcut_token_ile_erisim_saglayamaz():
    import pytest
    from fastapi import HTTPException
    from sunucu import mevcut_kullanici_id

    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value

    # Kullanıcı pasif durumda
    mock_cursor.fetchone.return_value = (False, False)

    # Token doğrulaması başarılı olsa bile erişim engellenmeli
    mock_credentials = MagicMock()
    mock_credentials.credentials = "gecerli-test-token"

    with patch("sunucu.token_dogrula", return_value=5):
        with patch("sunucu.psycopg2.connect", return_value=mock_conn):
            with pytest.raises(HTTPException) as hata:
                mevcut_kullanici_id(credentials=mock_credentials)

    assert hata.value.status_code == 403
    assert hata.value.detail == "Kullanıcı hesabı aktif değil."

    mock_conn.close.assert_called_once()


def test_pasif_kullanici_giris_yapamaz():
    import pytest
    from fastapi import HTTPException
    from modeller import GirisModeli
    from sunucu import giris_yap

    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value

    # Veritabanından dönen kullanıcı bilgileri
    mock_cursor.fetchone.return_value = (
        5,              # kullanici_id
        "test_psikolog", # kullanici_adi
        "hash",         # parola_hash
        2,              # rol_id
        False,          # aktif_mi
        0,              # basarisiz_giris_sayisi
        None,           # kilit_bitis_zamani
        False           # ilk_giris_mi
    )

    with patch("sunucu.psycopg2.connect", return_value=mock_conn):
        with patch("sunucu.denetim_kaydi_olustur") as mock_audit:
            with patch("sunucu.access_token_olustur") as mock_token:
                with pytest.raises(HTTPException) as hata:
                    giris_yap(
                        GirisModeli(
                            kullanici_adi="test_psikolog",
                            parola="test_parola"
                        )
                    )

    assert hata.value.status_code == 403
    assert hata.value.detail == "Kullanıcı hesabı aktif değil."

    # Pasif kullanıcıya token verilmemeli
    mock_token.assert_not_called()

    # Başarısız giriş denetim kaydına alınmalı
    assert mock_audit.call_args.kwargs["olay_turu"] == "LOGIN_FAILED"
def test_psikolog_http_uzerinden_kullanici_pasiflestiremez():
    from fastapi.testclient import TestClient
    from sunucu import app, mevcut_kullanici_id

    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value

    # Psikoloğun KULLANICI_PASIFLESTIR izni yok
    mock_cursor.fetchone.return_value = (0,)

    # Kimlik doğrulama aşamasını taklit ediyoruz
    app.dependency_overrides[mevcut_kullanici_id] = lambda: 10

    try:
        with patch("sunucu.psycopg2.connect", return_value=mock_conn):
            with TestClient(app) as client:
                yanit = client.patch(
                    "/api/kullanicilar/5/durum-degistir"
                )

        assert yanit.status_code == 403

        # Yetkisiz işlem veritabanına kaydedilmemeli
        mock_conn.commit.assert_not_called()

    finally:
        app.dependency_overrides.pop(mevcut_kullanici_id, None)
def test_mudur_http_uzerinden_kullanici_pasiflestirebilir():
    from fastapi.testclient import TestClient
    from sunucu import app

    endpoint = next(
        route for route in app.routes
        if getattr(route, "path", None)
        == "/api/kullanicilar/{kullanici_id}/durum-degistir"
        and "PATCH" in getattr(route, "methods", set())
    )

    yetki_bagimliligi = endpoint.dependant.dependencies[0].call

    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value
    mock_cursor.fetchone.side_effect = [
        ("MUDUR",),
        ("PSIKOLOG", True),
    ]

    # Yetkili kullanıcının kimliğini taklit ediyoruz
    app.dependency_overrides[yetki_bagimliligi] = lambda: 10

    try:
        with patch("sunucu.psycopg2.connect", return_value=mock_conn):
            with TestClient(app) as client:
                yanit = client.patch(
                    "/api/kullanicilar/5/durum-degistir"
                )

        assert yanit.status_code == 200
        assert yanit.json()["kullanici_id"] == 5
        assert yanit.json()["yeni_durum"] is False

        mock_conn.commit.assert_called_once()

    finally:
        app.dependency_overrides.pop(yetki_bagimliligi, None)
