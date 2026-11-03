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
    """Ayni cihaza eszamanli iki rezervasyondan yalnizca biri basarili olmali."""

    from contextlib import closing
    from datetime import datetime, timedelta, timezone
    from uuid import uuid4

    etiket = uuid4().hex[:12]

    rol_adi = f"QA001_{etiket}"
    kullanici_adi = f"qa001_{etiket}"
    envanter_kodu = f"QA001-{etiket}"

    rol_id = None
    kullanici_id = None
    personel_id = None
    cihaz_id = None
    izin_bagimliligi = None
    kayitlar_hazir = False

    try:
        # 1. Yalnizca bu teste ait gecici kayitlari olustur.
        with closing(psycopg2.connect(**VT_AYARLARI)) as conn:
            with conn:
                with conn.cursor() as cursor:

                    cursor.execute(
                        """
                        INSERT INTO roller (rol_adi)
                        VALUES (%s)
                        RETURNING rol_id;
                        """,
                        (rol_adi,),
                    )
                    rol_id = cursor.fetchone()[0]

                    cursor.execute(
                        """
                        INSERT INTO kullanicilar
                            (kullanici_adi, parola_hash, rol_id)
                        VALUES (%s, %s, %s)
                        RETURNING kullanici_id;
                        """,
                        (
                            kullanici_adi,
                            "qa001-gecici-test-kaydi",
                            rol_id,
                        ),
                    )
                    kullanici_id = cursor.fetchone()[0]

                    cursor.execute(
                        """
                        INSERT INTO personel
                            (kullanici_id, personel_kodu)
                        VALUES (%s, %s)
                        RETURNING personel_id;
                        """,
                        (kullanici_id, envanter_kodu),
                    )
                    personel_id = cursor.fetchone()[0]

                    cursor.execute(
                        """
                        INSERT INTO cihazlar
                            (envanter_kodu, cihaz_adi)
                        VALUES (%s, %s)
                        RETURNING cihaz_id;
                        """,
                        (envanter_kodu, "QA001 Gecici Test Cihazi"),
                    )
                    cihaz_id = cursor.fetchone()[0]

        kayitlar_hazir = True

        # 2. Test icin zaman araligi olustur.
        baslangic = (
            datetime.now(timezone.utc)
            .replace(tzinfo=None, microsecond=0)
            + timedelta(days=30)
        )
        bitis = baslangic + timedelta(hours=1)

        # 3. Mevcut endpoint'in yetki bagimliligini kullan.
        route = next(
            route for route in app.routes
            if getattr(route, "path", None) == "/api/rezervasyonlar"
            and "POST" in route.methods
        )

        izin_bagimliligi = route.dependant.dependencies[0].call

        app.dependency_overrides[izin_bagimliligi] = lambda: kullanici_id

        istek = {
            "cihaz_id": cihaz_id,
            "kullanilacak_oda_id": None,
            "baslangic_zamani": baslangic.isoformat(),
            "bitis_zamani": bitis.isoformat(),
            "proje_turu": "Test",
            "proje_adi_aciklamasi": f"QA001-{etiket}",
        }

        # 4. Ayni anda iki rezervasyon istegi gonder.
        bariyer = Barrier(2)

        def rezervasyon_gonder():
            bariyer.wait(timeout=10)

            with TestClient(app) as client:
                return client.post(
                    "/api/rezervasyonlar",
                    json=istek,
                )

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(rezervasyon_gonder)
                for _ in range(2)
            ]

            yanitlar = [
                future.result(timeout=30)
                for future in futures
            ]

        # 5. Bir rezervasyon basarili, digeri cakisma olmali.
        durum_kodlari = sorted(
            yanit.status_code for yanit in yanitlar
        )

        assert durum_kodlari == [201, 409], (
            f"Beklenmeyen durum kodlari: {durum_kodlari}"
        )

        # 6. Veritabaninda yalnizca bir rezervasyon olmali.
        with closing(psycopg2.connect(**VT_AYARLARI)) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM cihaz_rezervasyonlari
                    WHERE cihaz_id = %s
                      AND iptal_edildi_mi = FALSE;
                    """,
                    (cihaz_id,),
                )

                assert cursor.fetchone()[0] == 1

    finally:
        # Yetki bagimliligini eski haline getir.
        if izin_bagimliligi is not None:
            app.dependency_overrides.pop(
                izin_bagimliligi,
                None,
            )

        # 7. Yalnizca bu testin olusturdugu kayitlari temizle.
        if kayitlar_hazir:
            with closing(psycopg2.connect(**VT_AYARLARI)) as conn:
                with conn:
                    with conn.cursor() as cursor:

                        cursor.execute(
                            """
                            DELETE FROM denetim_kayitlari
                            WHERE kullanici_id = %s;
                            """,
                            (kullanici_id,),
                        )

                        cursor.execute(
                            """
                            DELETE FROM cihaz_rezervasyonlari
                            WHERE cihaz_id = %s;
                            """,
                            (cihaz_id,),
                        )

                        cursor.execute(
                            """
                            DELETE FROM personel
                            WHERE personel_id = %s
                              AND kullanici_id = %s;
                            """,
                            (personel_id, kullanici_id),
                        )

                        cursor.execute(
                            """
                            DELETE FROM kullanicilar
                            WHERE kullanici_id = %s
                              AND kullanici_adi = %s;
                            """,
                            (kullanici_id, kullanici_adi),
                        )

                        cursor.execute(
                            """
                            DELETE FROM cihazlar
                            WHERE cihaz_id = %s
                              AND envanter_kodu = %s;
                            """,
                            (cihaz_id, envanter_kodu),
                        )

                        cursor.execute(
                            """
                            DELETE FROM roller
                            WHERE rol_id = %s
                              AND rol_adi = %s;
                            """,
                            (rol_id, rol_adi),
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