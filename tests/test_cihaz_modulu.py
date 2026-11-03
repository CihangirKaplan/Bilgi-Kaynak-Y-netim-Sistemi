"""Cihaz envanteri ve rezervasyon testleri (Öğrenci B - DEVICE / RES / SEC-T14).

Testler gerçek veritabanına bağlanmaz; psycopg2 bağlantısı sahte (mock) nesne
ile değiştirilir.
"""
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from modeller import (
    CihazDurumu,
    CihazGuncelleModeli,
    CihazOlusturModeli,
    RezervasyonOlusturModeli,
)
from sunucu import (
    app,
    cihaz_detayi_getir,
    cihaz_ekle,
    cihaz_guncelle,
    cihaz_rezervasyonu_yap,
    izin_kontrol,
)


def sahte_baglanti():
    conn = MagicMock()
    return conn, conn.cursor.return_value


def calisan_sorgular(cursor):
    return [call.args[0].strip().upper() for call in cursor.execute.call_args_list]


def rezervasyon_modeli():
    return RezervasyonOlusturModeli(
        cihaz_id=1,
        baslangic_zamani="2026-10-30T10:00:00",
        bitis_zamani="2026-10-30T11:00:00",
    )


# ---------- DEVICE-002: Cihaz ekleme ----------

def test_cihaz_ekle_basarili():
    conn, cursor = sahte_baglanti()
    # 1) çakışan kayıt yok  2) INSERT yeni cihaz_id döndürür
    cursor.fetchone.side_effect = [None, (7,)]

    with patch("sunucu.psycopg2.connect", return_value=conn):
        sonuc = cihaz_ekle(
            CihazOlusturModeli(envanter_kodu="CHZ-001", cihaz_adi="EEG"),
            kullanici_id=3,
        )

    assert sonuc["cihaz_id"] == 7
    conn.commit.assert_called_once()
    assert any(s.startswith("INSERT INTO CIHAZLAR") for s in calisan_sorgular(cursor))


def test_cihaz_ekle_ayni_envanter_kodu_409():
    conn, cursor = sahte_baglanti()
    cursor.fetchone.side_effect = [(1,)]  # aynı envanter kodu/seri no var

    with patch("sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            cihaz_ekle(
                CihazOlusturModeli(envanter_kodu="CHZ-001", cihaz_adi="EEG"),
                kullanici_id=3,
            )

    assert hata.value.status_code == 409
    conn.commit.assert_not_called()
    assert not any(s.startswith("INSERT") for s in calisan_sorgular(cursor))


@pytest.mark.parametrize(
    "alanlar",
    [
        {"envanter_kodu": "", "cihaz_adi": "EEG"},
        {"envanter_kodu": "X" * 51, "cihaz_adi": "EEG"},
        {"envanter_kodu": "CHZ-1", "cihaz_adi": ""},
        {"envanter_kodu": "CHZ-1", "cihaz_adi": "EEG", "zimmetli_oda_id": -1},
        {"envanter_kodu": "CHZ-1", "cihaz_adi": "EEG", "durum": "GECERSIZ"},
    ],
)
def test_cihaz_olusturma_gecersiz_girdi_reddedilir(alanlar):
    with pytest.raises(ValidationError):
        CihazOlusturModeli(**alanlar)


# ---------- DEVICE-003/004/005: Düzenleme, pasifleştirme, durum ----------

def test_cihaz_guncelle_bos_istek_422():
    conn, _ = sahte_baglanti()

    with patch("sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            cihaz_guncelle(1, CihazGuncelleModeli(), kullanici_id=3)

    assert hata.value.status_code == 422


def test_cihaz_guncelle_olmayan_cihaz_404():
    conn, cursor = sahte_baglanti()
    cursor.fetchone.side_effect = [None]

    with patch("sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            cihaz_guncelle(999, CihazGuncelleModeli(cihaz_adi="Yeni"), kullanici_id=3)

    assert hata.value.status_code == 404
    conn.rollback.assert_called_once()


def test_cihaz_durum_degisince_audit_kaydi_olusur():
    conn, cursor = sahte_baglanti()
    cursor.fetchone.side_effect = [("Kullanima_Hazir",)]

    with patch("sunucu.psycopg2.connect", return_value=conn):
        cihaz_guncelle(
            1, CihazGuncelleModeli(durum=CihazDurumu.KULLANIM_DISI), kullanici_id=3
        )

    olaylar = [c.args[1][1] for c in cursor.execute.call_args_list
               if "INSERT INTO denetim_kayitlari" in c.args[0]]
    assert olaylar == ["DEVICE_STATUS_CHANGE"]
    conn.commit.assert_called_once()


def test_cihaz_durum_ayni_kalirsa_status_audit_olusmaz():
    conn, cursor = sahte_baglanti()
    cursor.fetchone.side_effect = [("Arizali",)]

    with patch("sunucu.psycopg2.connect", return_value=conn):
        cihaz_guncelle(
            1, CihazGuncelleModeli(durum=CihazDurumu.ARIZALI), kullanici_id=3
        )

    assert not any(
        "INSERT INTO denetim_kayitlari" in c.args[0] for c in cursor.execute.call_args_list
    )


def test_cihaz_detayi_olmayan_cihaz_404():
    conn, cursor = sahte_baglanti()
    cursor.fetchone.side_effect = [None]

    with patch("sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            cihaz_detayi_getir(999, kullanici_id=3)

    assert hata.value.status_code == 404


# ---------- RES-001..003 + SEC-T14: Rezervasyon iş kuralları ----------

@pytest.mark.parametrize(
    "durum", ["Arizali", "Bakimda", "Kalibrasyonda", "Kullanim_Disi", "Kullanimda"]
)
def test_uygun_olmayan_cihaz_rezerve_edilemez(durum):
    """SEC-T14: Arızalı/bakımda/kalibrasyonda/kullanım dışı cihaz rezerve edilemez."""
    conn, cursor = sahte_baglanti()
    cursor.fetchone.side_effect = [(durum,)]

    with patch("sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            cihaz_rezervasyonu_yap(rezervasyon_modeli(), kullanici_id=3)

    assert hata.value.status_code == 403
    assert not any(s.startswith("INSERT INTO CIHAZ_REZERVASYONLARI")
                   for s in calisan_sorgular(cursor))
    conn.commit.assert_not_called()


def test_rezervasyon_olmayan_cihaz_404():
    conn, cursor = sahte_baglanti()
    cursor.fetchone.side_effect = [None]

    with patch("sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            cihaz_rezervasyonu_yap(rezervasyon_modeli(), kullanici_id=3)

    assert hata.value.status_code == 404


def test_rezervasyon_cakisan_saat_409():
    conn, cursor = sahte_baglanti()
    # cihaz uygun, aynı saatte aktif rezervasyon var
    cursor.fetchone.side_effect = [("Kullanima_Hazir",), (1,)]

    with patch("sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            cihaz_rezervasyonu_yap(rezervasyon_modeli(), kullanici_id=3)

    assert hata.value.status_code == 409
    conn.commit.assert_not_called()


def test_rezervasyon_basarili():
    conn, cursor = sahte_baglanti()
    # cihaz uygun, çakışma yok, personel kaydı var, yeni rezervasyon_id
    cursor.fetchone.side_effect = [("Kullanima_Hazir",), None, (5,), (42,)]

    with patch("sunucu.psycopg2.connect", return_value=conn):
        sonuc = cihaz_rezervasyonu_yap(rezervasyon_modeli(), kullanici_id=3)

    assert sonuc["rezervasyon_id"] == 42
    conn.commit.assert_called_once()


def test_rezervasyon_bitis_baslangictan_once_422():
    ters = RezervasyonOlusturModeli.model_construct(
        cihaz_id=1,
        kullanilacak_oda_id=None,
        baslangic_zamani=rezervasyon_modeli().bitis_zamani,
        bitis_zamani=rezervasyon_modeli().baslangic_zamani,
        proje_turu=None,
        proje_adi_aciklamasi=None,
    )

    with pytest.raises(HTTPException) as hata:
        cihaz_rezervasyonu_yap(ters, kullanici_id=3)

    assert hata.value.status_code == 422


# ---------- Yetkilendirme (RBAC) ----------

def test_izin_yoksa_403():
    conn, cursor = sahte_baglanti()
    cursor.fetchone.side_effect = [(0,)]  # rolün bu izni yok

    with patch("sunucu.psycopg2.connect", return_value=conn):
        kontrol = izin_kontrol("CIHAZ_EKLE")
        with pytest.raises(HTTPException) as hata:
            kontrol(kullanici_id=3)

    assert hata.value.status_code == 403


def test_izin_kaydi_hic_yoksa_403():
    conn, cursor = sahte_baglanti()
    cursor.fetchone.side_effect = [None]

    with patch("sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            izin_kontrol("CIHAZ_EKLE")(kullanici_id=3)

    assert hata.value.status_code == 403


def test_izin_varsa_kullanici_id_doner():
    conn, cursor = sahte_baglanti()
    cursor.fetchone.side_effect = [(1,)]

    with patch("sunucu.psycopg2.connect", return_value=conn):
        assert izin_kontrol("CIHAZ_EKLE")(kullanici_id=3) == 3


@pytest.mark.parametrize(
    "metot, yol",
    [
        ("get", "/api/cihazlar"),
        ("get", "/api/cihazlar/1"),
        ("post", "/api/cihazlar"),
        ("patch", "/api/cihazlar/1"),
        ("post", "/api/rezervasyonlar"),
        ("get", "/api/rezervasyonlar"),
    ],
)
def test_tokensiz_cihaz_endpointleri_reddedilir(metot, yol):
    """SEC-T01: Token olmadan korunan endpoint'e erişilemez."""
    istemci = TestClient(app)
    yanit = getattr(istemci, metot)(yol)
    assert yanit.status_code in (401, 403)


def test_gecersiz_token_401():
    """SEC-T08: Geçersiz token reddedilir."""
    istemci = TestClient(app)
    yanit = istemci.get("/api/cihazlar", headers={"Authorization": "Bearer sahte.token.degeri"})
    assert yanit.status_code == 401