"""Gerçek PostgreSQL: cihaz rezervasyonu ile psikolog oda ataması yarışı."""

import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timedelta
from threading import Barrier
from uuid import uuid4

import psycopg2
import pytest
from fastapi.testclient import TestClient

from server.sunucu import app, VT_AYARLARI, CIHAZ_ODALARI_SORGUSU


def test_rezervasyon_ve_psikolog_oda_atamasi_ayni_anda():
    # Production üzerinde çalıştırmayı kesin olarak engelle.
    assert os.environ.get("TKYS_PG_TEST_ONAY") == "EVET"
    assert VT_AYARLARI["dbname"] == "crkys_alembic_test"

    etiket = uuid4().hex[:12]
    kullanici_adi = f"qa_race_{etiket}"
    kod = f"QA-RACE-{etiket}"

    kullanici_id = None
    personel_id = None
    cihaz_id = None
    oda_id = None
    bagimliliklar = {}

    baslangic = (
        datetime.now() + timedelta(days=60)
    ).replace(hour=10, minute=0, second=0, microsecond=0)
    bitis = baslangic + timedelta(hours=1)

    try:
        # Yalnızca test veritabanında geçici kayıtlar oluştur.
        with closing(psycopg2.connect(**VT_AYARLARI)) as conn:
            with conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT current_database()")
                    assert cur.fetchone()[0] == "crkys_alembic_test"

                    cur.execute("""
                        SELECT rol_id FROM roller
                        WHERE UPPER(rol_adi) = 'PSIKOLOG'
                        LIMIT 1
                    """)
                    rol = cur.fetchone()
                    assert rol, "PSIKOLOG rolü bulunamadı."

                    # Cihaz rezervasyonuna uygun, atanmamış ve
                    # gelecekte rezervasyonu olmayan bir oda seç.
                    cur.execute(
                        "SELECT d.oda_id FROM ("
                        + CIHAZ_ODALARI_SORGUSU
                        + """) d
                        WHERE NOT EXISTS (
                            SELECT 1 FROM cihaz_rezervasyonlari r
                            WHERE r.kullanilacak_oda_id = d.oda_id
                              AND COALESCE(r.iptal_edildi_mi, FALSE) = FALSE
                              AND r.bitis_zamani > NOW()
                        )
                        AND NOT EXISTS (
                            SELECT 1
                            FROM oda_etkinlikleri e
                            JOIN oda_etkinlik_gunleri g
                              ON g.etkinlik_id = e.etkinlik_id
                            WHERE e.oda_id = d.oda_id
                              AND COALESCE(e.iptal_edildi_mi, FALSE) = FALSE
                              AND g.bitis_zamani > NOW()
                        )
                        ORDER BY d.oda_id
                        LIMIT 1
                        """
                    )
                    secilen = cur.fetchone()
                    if secilen is None:
                        pytest.skip("Test için uygun boş oda bulunamadı.")
                    oda_id = secilen[0]

                    cur.execute("""
                        INSERT INTO kullanicilar
                            (kullanici_adi, parola_hash, rol_id)
                        VALUES (%s, %s, %s)
                        RETURNING kullanici_id
                    """, (kullanici_adi, "qa-gecici-parola", rol[0]))
                    kullanici_id = cur.fetchone()[0]

                    cur.execute("""
                        INSERT INTO personel (kullanici_id, personel_kodu)
                        VALUES (%s, %s)
                        RETURNING personel_id
                    """, (kullanici_id, kod))
                    personel_id = cur.fetchone()[0]

                    cur.execute("""
                        INSERT INTO cihazlar (envanter_kodu, cihaz_adi)
                        VALUES (%s, %s)
                        RETURNING cihaz_id
                    """, (kod, "QA Yarış Testi Cihazı"))
                    cihaz_id = cur.fetchone()[0]

        def bagimlilik_bul(yol, metot):
            route = next(
                r for r in app.routes
                if getattr(r, "path", None) == yol
                and metot in getattr(r, "methods", set())
            )
            return route.dependant.dependencies[0].call

        rez_bag = bagimlilik_bul("/api/rezervasyonlar", "POST")
        oda_bag = bagimlilik_bul(
            "/api/kullanicilar/{hedef_kullanici_id}/odalar",
            "PUT",
        )

        bagimliliklar = {
            rez_bag: app.dependency_overrides.get(rez_bag),
            oda_bag: app.dependency_overrides.get(oda_bag),
        }

        app.dependency_overrides[rez_bag] = lambda: kullanici_id
        app.dependency_overrides[oda_bag] = lambda: kullanici_id

        bariyer = Barrier(2)

        def rezervasyon_yap():
            bariyer.wait(timeout=10)
            with TestClient(app) as client:
                return client.post("/api/rezervasyonlar", json={
                    "cihaz_id": cihaz_id,
                    "kullanilacak_oda_id": oda_id,
                    "baslangic_zamani": baslangic.isoformat(),
                    "bitis_zamani": bitis.isoformat(),
                    "proje_turu": "Test",
                    "proje_adi_aciklamasi": kod,
                })

        def oda_ata():
            bariyer.wait(timeout=10)
            with TestClient(app) as client:
                return client.put(
                    f"/api/kullanicilar/{kullanici_id}/odalar",
                    json={"oda_idleri": [oda_id]},
                )

        with ThreadPoolExecutor(max_workers=2) as executor:
            f_rez = executor.submit(rezervasyon_yap)
            f_oda = executor.submit(oda_ata)

            rez_cevap = f_rez.result(timeout=30)
            oda_cevap = f_oda.result(timeout=30)

        print("\nRezervasyon:", rez_cevap.status_code, rez_cevap.text)
        print("Oda ataması:", oda_cevap.status_code, oda_cevap.text)

        # Son durumu doğrudan PostgreSQL'den doğrula.
        with closing(psycopg2.connect(**VT_AYARLARI)) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*) FROM cihaz_rezervasyonlari
                    WHERE cihaz_id = %s AND kullanilacak_oda_id = %s
                      AND COALESCE(iptal_edildi_mi, FALSE) = FALSE
                """, (cihaz_id, oda_id))
                rezervasyon_sayisi = cur.fetchone()[0]

                cur.execute("""
                    SELECT COUNT(*) FROM psikolog_odalar
                    WHERE kullanici_id = %s AND oda_id = %s
                """, (kullanici_id, oda_id))
                atama_sayisi = cur.fetchone()[0]

        assert (rezervasyon_sayisi, atama_sayisi) in (
            (1, 0), (0, 1)
        ), (
            "Tutarsız oda tahsisi: "
            f"rezervasyon={rezervasyon_sayisi}, "
            f"atama={atama_sayisi}"
        )

        assert (
            rez_cevap.status_code,
            oda_cevap.status_code,
        ) in (
            (201, 409),
            (422, 200),
        ), (
            f"Beklenmeyen HTTP sonuçları: "
            f"{rez_cevap.status_code}, {oda_cevap.status_code}"
        )

    finally:
        for bag, eski in bagimliliklar.items():
            if eski is None:
                app.dependency_overrides.pop(bag, None)
            else:
                app.dependency_overrides[bag] = eski

        # Yalnızca bu teste ait kayıtları temizle.
        if kullanici_id is not None:
            with closing(psycopg2.connect(**VT_AYARLARI)) as conn:
                with conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            DELETE FROM denetim_kayitlari
                            WHERE kullanici_id = %s
                        """, (kullanici_id,))

                        if cihaz_id is not None:
                            cur.execute("""
                                DELETE FROM cihaz_rezervasyonlari
                                WHERE cihaz_id = %s
                            """, (cihaz_id,))

                        cur.execute("""
                            DELETE FROM psikolog_odalar
                            WHERE kullanici_id = %s
                        """, (kullanici_id,))

                        if personel_id is not None:
                            cur.execute("""
                                DELETE FROM personel
                                WHERE personel_id = %s
                            """, (personel_id,))

                        if cihaz_id is not None:
                            cur.execute("""
                                DELETE FROM cihazlar
                                WHERE cihaz_id = %s
                            """, (cihaz_id,))

                        cur.execute("""
                            DELETE FROM kullanicilar
                            WHERE kullanici_id = %s
                              AND kullanici_adi = %s
                        """, (kullanici_id, kullanici_adi))
