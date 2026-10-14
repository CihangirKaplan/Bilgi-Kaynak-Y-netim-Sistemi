from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from psycopg2.errors import ExclusionViolation

from modeller import RezervasyonOlusturModeli
from sunucu import cihaz_rezervasyonu_yap


def test_cihaz_rezervasyon_cakismasi_http_409():
    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value

    # Cihaz uygun, mevcut rezervasyon görünmüyor,
    # kullanıcıya ait personel kaydı bulunuyor.
    mock_cursor.fetchone.side_effect = [
        ("Kullanima_Hazir",),
        None,
        (1,),
    ]

    # INSERT sırasında PostgreSQL çakışma hatası oluşsun.
    def sorgu_calistir(sql, params=None):
        if "INSERT INTO cihaz_rezervasyonlari" in sql:
            raise ExclusionViolation("Rezervasyon çakışması")

    mock_cursor.execute.side_effect = sorgu_calistir

    rezervasyon = RezervasyonOlusturModeli(
        cihaz_id=1,
        kullanilacak_oda_id=None,
        baslangic_zamani="2026-10-22T10:00:00",
        bitis_zamani="2026-10-22T11:00:00",
        proje_turu="Test",
        proje_adi_aciklamasi="Issue 115 HTTP 409 testi",
    )

    with patch("sunucu.psycopg2.connect", return_value=mock_conn):
        with pytest.raises(HTTPException) as hata:
            cihaz_rezervasyonu_yap(
                rez=rezervasyon,
                kullanici_id=1,
            )

    assert hata.value.status_code == 409
    mock_conn.rollback.assert_called_once()
    mock_conn.commit.assert_not_called()
    mock_cursor.close.assert_called_once()
    mock_conn.close.assert_called_once()

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import psycopg2
from fastapi.testclient import TestClient

from sunucu import app, VT_AYARLARI


def test_gercek_eszamanli_cihaz_rezervasyonu():
    # Yanlışlıkla ana veritabanında çalışmasını engelle.
    assert VT_AYARLARI["dbname"] == "crkys_alembic_test", (
        "Bu test yalnızca crkys_alembic_test üzerinde çalıştırılabilir."
    )

    # Test cihazının gerçekten mevcut olduğunu doğrula.
    with psycopg2.connect(**VT_AYARLARI) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT cihaz_id FROM cihazlar WHERE envanter_kodu = %s;",
                ("TEST-ISSUE-115",),
            )
            kayit = cursor.fetchone()

    assert kayit is not None, "Test cihazı bulunamadı."
    cihaz_id = kayit[0]
    # Test kullanıcısını sabit ID yerine kullanıcı adıyla bul.
    with psycopg2.connect(**VT_AYARLARI) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT kullanici_id
                FROM kullanicilar
                WHERE kullanici_adi = %s;
                """,
                ("test_issue_115",)
            )
            kullanici_kaydi = cursor.fetchone()

    assert kullanici_kaydi is not None, (
        "Test kullanıcısı bulunamadı: test_issue_115"
    )
    test_kullanici_id = kullanici_kaydi[0]
    # Test için benzersiz bir zaman aralığı kullan.
    from datetime import datetime, timedelta, timezone

    baslangic = datetime.now(timezone.utc).replace(
        tzinfo=None, microsecond=0
    ) + timedelta(days=30)
    bitis = baslangic + timedelta(hours=1)

    # Mevcut test rezervasyonlarıyla çakışma ihtimalini azaltmak
    # için önceden uygunluk kontrolü yap.
    with psycopg2.connect(**VT_AYARLARI) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM cihaz_rezervasyonlari
                WHERE cihaz_id = %s
                  AND iptal_edildi_mi = FALSE
                  AND baslangic_zamani < %s
                  AND bitis_zamani > %s;
                """,
                (cihaz_id, bitis, baslangic),
            )
            assert cursor.fetchone()[0] == 0

    # Endpoint'in mevcut izin bağımlılığını bul.
    route = next(
        route for route in app.routes
        if getattr(route, "path", None) == "/api/rezervasyonlar"
        and "POST" in route.methods
    )
    izin_bagimliligi = route.dependant.dependencies[0].call

    # Test süresince yetkili kullanıcıyı taklit et.
    app.dependency_overrides[izin_bagimliligi] = lambda: test_kullanici_id

    istek = {
        "cihaz_id": cihaz_id,
        "kullanilacak_oda_id": None,
        "baslangic_zamani": baslangic.isoformat(),
        "bitis_zamani": bitis.isoformat(),
        "proje_turu": "Test",
        "proje_adi_aciklamasi": "Issue 115 eszamanlilik testi",
    }

    bariyer = Barrier(2)

    def rezervasyon_gonder():
        bariyer.wait(timeout=10)
        with TestClient(app) as client:
            return client.post("/api/rezervasyonlar", json=istek)

    try:
        # Audit kaydı ayrı bağlantı kullandığından testte taklit ediyoruz.
        with patch("sunucu.denetim_kaydi_olustur"):
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [
                    executor.submit(rezervasyon_gonder)
                    for _ in range(2)
                ]
                yanitlar = [future.result(timeout=30) for future in futures]

        durum_kodlari = sorted(yanit.status_code for yanit in yanitlar)

        assert durum_kodlari == [201, 409], (
            f"Beklenmeyen durum kodları: {durum_kodlari}"
        )

        with psycopg2.connect(**VT_AYARLARI) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM cihaz_rezervasyonlari
                    WHERE cihaz_id = %s
                      AND baslangic_zamani = %s
                      AND bitis_zamani = %s
                      AND iptal_edildi_mi = FALSE;
                    """,
                    (cihaz_id, baslangic, bitis),
                )
                assert cursor.fetchone()[0] == 1

    finally:
        app.dependency_overrides.pop(izin_bagimliligi, None)

        # Yalnızca bu testin oluşturduğu rezervasyonu temizle.
        with psycopg2.connect(**VT_AYARLARI) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM cihaz_rezervasyonlari
                    WHERE cihaz_id = %s
                      AND baslangic_zamani = %s
                      AND bitis_zamani = %s
                      AND proje_adi_aciklamasi = %s;
                    """,
                    (
                        cihaz_id,
                        baslangic,
                        bitis,
                        "Issue 115 eszamanlilik testi",
                    ),
                )

def test_deadlock_sonrasi_yeniden_deneme():
    from psycopg2.errors import DeadlockDetected

    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value

    # İlk denemede deadlock, ikinci denemede başarılı işlem.
    mock_cursor.fetchone.side_effect = [
        ("Kullanima_Hazir",),
        None,
        (1,),
        ("Kullanima_Hazir",),
        None,
        (1,),
        (42,),
    ]

    def sorgu_calistir(sql, params=None):
        if "INSERT INTO cihaz_rezervasyonlari" in sql:
            if not hasattr(sorgu_calistir, "ilk_deneme"):
                sorgu_calistir.ilk_deneme = True
                raise DeadlockDetected("deadlock detected")

    mock_cursor.execute.side_effect = sorgu_calistir

    rezervasyon = RezervasyonOlusturModeli(
        cihaz_id=1,
        kullanilacak_oda_id=None,
        baslangic_zamani="2026-10-22T10:00:00",
        bitis_zamani="2026-10-22T11:00:00",
        proje_turu="Test",
        proje_adi_aciklamasi="Deadlock yeniden deneme testi",
    )

    with patch("sunucu.psycopg2.connect", return_value=mock_conn):
        with patch("sunucu.denetim_kaydi_olustur"):
            with patch("sunucu.time.sleep"):
                sonuc = cihaz_rezervasyonu_yap(
                    rez=rezervasyon,
                    kullanici_id=1,
                )

    assert sonuc["rezervasyon_id"] == 42
    assert mock_conn.rollback.call_count == 1
    assert mock_conn.commit.call_count == 1
    assert mock_conn.cursor.call_count == 2