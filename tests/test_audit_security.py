
from unittest.mock import MagicMock, patch

import pytest

from denetim import denetim_kaydi_olustur


def test_mevcut_cursor_ile_audit_kaydi():
    cursor = MagicMock()

    with patch("denetim.psycopg2.connect") as mock_connect:
        denetim_kaydi_olustur(
            vt_ayarlari={},
            olay_turu="DEVICE_STATUS_CHANGE",
            kullanici_id=1,
            hedef_tablo="cihazlar",
            hedef_kayit_id=10,
            mevcut_cursor=cursor
        )

    cursor.execute.assert_called_once()
    assert cursor.execute.call_args.args[1] == (
        1, "DEVICE_STATUS_CHANGE", "cihazlar", 10
    )
    mock_connect.assert_not_called()
    cursor.close.assert_not_called()


def test_audit_hatasinda_exception_yukseltilir():
    cursor = MagicMock()
    cursor.execute.side_effect = RuntimeError("Audit yazılamadı")

    with pytest.raises(RuntimeError):
        denetim_kaydi_olustur(
            vt_ayarlari={},
            olay_turu="UPDATE",
            mevcut_cursor=cursor
        )

    cursor.close.assert_not_called()


def test_bagimsiz_audit_kaydi_commit_edilir():
    with patch("denetim.psycopg2.connect") as mock_connect:
        conn = mock_connect.return_value
        cursor = conn.cursor.return_value

        denetim_kaydi_olustur(
            vt_ayarlari={},
            olay_turu="LOGIN",
            kullanici_id=1
        )

    cursor.execute.assert_called_once()
    conn.commit.assert_called_once()
    cursor.close.assert_called_once()
    conn.close.assert_called_once()


def test_bagimsiz_audit_hatasinda_rollback():
    with patch("denetim.psycopg2.connect") as mock_connect:
        conn = mock_connect.return_value
        cursor = conn.cursor.return_value
        cursor.execute.side_effect = RuntimeError("Veritabanı hatası")

        with pytest.raises(RuntimeError):
            denetim_kaydi_olustur(
                vt_ayarlari={},
                olay_turu="LOGIN_FAILED"
            )

    conn.rollback.assert_called_once()
    conn.commit.assert_not_called()
    conn.close.assert_called_once()

from modeller import CihazGuncelleModeli
from sunucu import cihaz_guncelle


def test_cihaz_durum_degisikligi_audit():
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchone.side_effect = [
        ("Kullanima_Hazir",),
        (10,)
    ]

    with patch("sunucu.psycopg2.connect", return_value=conn):
        cihaz_guncelle(
            cihaz_id=10,
            guncelleme=CihazGuncelleModeli(durum="Bakimda"),
            kullanici_id=1
        )

    audit_kayitlari = [
        c.args[1][1]
        for c in cursor.execute.call_args_list
        if "INSERT INTO denetim_kayitlari" in c.args[0]
    ]

    assert audit_kayitlari == ["DEVICE_STATUS_CHANGE"]
    conn.commit.assert_called_once()


def test_cihaz_durumu_ayniysa_audit_olusturulmaz():
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchone.side_effect = [
        ("Bakimda",),
        (10,)
    ]

    with patch("sunucu.psycopg2.connect", return_value=conn):
        cihaz_guncelle(
            cihaz_id=10,
            guncelleme=CihazGuncelleModeli(durum="Bakimda"),
            kullanici_id=1
        )

    audit_sorgulari = [
        c for c in cursor.execute.call_args_list
        if "INSERT INTO denetim_kayitlari" in c.args[0]
    ]

    assert audit_sorgulari == []


def test_audit_hatasinda_cihaz_guncelleme_rollback():
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchone.side_effect = [
        ("Kullanima_Hazir",),
        (10,)
    ]

    def sorgu_calistir(sql, params=None):
        if "INSERT INTO denetim_kayitlari" in sql:
            raise RuntimeError("Audit kaydı oluşturulamadı")

    cursor.execute.side_effect = sorgu_calistir

    with patch("sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(RuntimeError):
            cihaz_guncelle(
                cihaz_id=10,
                guncelleme=CihazGuncelleModeli(durum="Bakimda"),
                kullanici_id=1
            )

    conn.rollback.assert_called_once()
    conn.commit.assert_not_called()

from modeller import ArizaBildirimModeli, ArizaGuncelleModeli
from sunucu import ariza_bildir, ariza_guncelle


def test_ariza_guncelleme_durum_degisikligi_audit():
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchone.side_effect = [
        (10,),                  # Arızaya bağlı cihaz
        ("Arizali",)            # Cihazın eski durumu
    ]

    ariza = ArizaGuncelleModeli(
        aciliyet="Orta",
        ariza_baslik="Test arızası",
        ariza_aciklama="Test açıklaması",
        cozuldu_mu=True
    )

    with patch("sunucu.psycopg2.connect", return_value=conn):
        ariza_guncelle(ariza_id=5, ariza=ariza, kullanici_id=1)

    olaylar = [
        c.args[1][1]
        for c in cursor.execute.call_args_list
        if "INSERT INTO denetim_kayitlari" in c.args[0]
    ]

    assert olaylar == ["UPDATE", "DEVICE_STATUS_CHANGE"]
    conn.commit.assert_called_once()
    conn.rollback.assert_not_called()


def test_ariza_guncelleme_audit_hatasinda_rollback():
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchone.side_effect = [
        (10,),
        ("Arizali",)
    ]

    def sorgu_calistir(sql, params=None):
        if "INSERT INTO denetim_kayitlari" in sql:
            raise RuntimeError("Audit yazılamadı")

    cursor.execute.side_effect = sorgu_calistir

    ariza = ArizaGuncelleModeli(
        aciliyet="Orta",
        ariza_baslik="Test arızası",
        ariza_aciklama="Test açıklaması",
        cozuldu_mu=True
    )

    with patch("sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(Exception):
            ariza_guncelle(ariza_id=5, ariza=ariza, kullanici_id=1)

    conn.rollback.assert_called_once()
    conn.commit.assert_not_called()

def test_ariza_bildir_durum_degisikligi_audit():
    conn = MagicMock()
    cursor = conn.cursor.return_value

    cursor.fetchone.side_effect = [
        ("Kullanima_Hazir",),  # Eski cihaz durumu
        ("test_kullanici",),   # Kullanıcı adı
        (5,)                  # Yeni arıza ID
    ]

    ariza = ArizaBildirimModeli(
        cihaz_id=10,
        aciliyet="Orta",
        ariza_baslik="Test arızası",
        ariza_aciklama="Test açıklaması"
    )

    with patch("sunucu.psycopg2.connect", return_value=conn):
        ariza_bildir(ariza=ariza, kullanici_id=1)

    olaylar = [
        c.args[1][1]
        for c in cursor.execute.call_args_list
        if "INSERT INTO denetim_kayitlari" in c.args[0]
    ]

    assert olaylar == ["CREATE", "DEVICE_STATUS_CHANGE"]
    conn.commit.assert_called_once()
    conn.rollback.assert_not_called()


def test_ariza_bildir_audit_hatasinda_rollback():
    conn = MagicMock()
    cursor = conn.cursor.return_value

    cursor.fetchone.side_effect = [
        ("Kullanima_Hazir",),
        ("test_kullanici",),
        (5,)
    ]

    def sorgu_calistir(sql, params=None):
        if "INSERT INTO denetim_kayitlari" in sql:
            raise RuntimeError("Audit yazılamadı")

    cursor.execute.side_effect = sorgu_calistir

    ariza = ArizaBildirimModeli(
        cihaz_id=10,
        aciliyet="Orta",
        ariza_baslik="Test arızası",
        ariza_aciklama="Test açıklaması"
    )

    with patch("sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(Exception):
            ariza_bildir(ariza=ariza, kullanici_id=1)

    conn.rollback.assert_called_once()
    conn.commit.assert_not_called()
