"""
Gerçek PostgreSQL: ADMIN her izne sahip olmalı.

Bu test CI'daki "PostgreSQL Entegrasyon Testleri" işinde (alembic upgrade head sonrası) çalışır. Biri yeni bir izni
migrasyonla ekleyip ADMIN'e vermeyi unutursa PR kırmızı olur (CASE WHEN rol_adi = 'ADMIN' gibi koşullar
bu tür hataları sessizce yapar: izin tabloya girer ama kimseye verilmez).
"""

import importlib.util
import os
from pathlib import Path
from uuid import uuid4

import psycopg2

from sunucu import VT_AYARLARI, izin_ekle

MIGRASYON = Path(__file__).resolve().parent.parent / "alembic" / "versions" / "f1c8d6a32e75_admin_tum_izinlere_sahip.py"


def _dogru_veritabani(cursor):
    # Yanlış veritabanında çalışmayı kesinlikle engelle.
    assert os.getenv("TKYS_PG_TEST_ONAY") == "EVET"
    assert VT_AYARLARI["dbname"] == "crkys_alembic_test"
    cursor.execute("SELECT current_database()")
    assert cursor.fetchone()[0] == "crkys_alembic_test"


ADMIN_EKSIKLERI = """
    SELECT i.izin_adi
    FROM izinler i
    CROSS JOIN roller r
    LEFT JOIN rol_izinleri ri ON ri.izin_id = i.izin_id AND ri.rol_id = r.rol_id
    WHERE r.rol_adi = 'ADMIN' AND COALESCE(ri.izin_var, 0) <> 1
    ORDER BY i.izin_adi
"""


def test_admin_tum_izinlerde_acik():
    conn = psycopg2.connect(**VT_AYARLARI)
    try:
        with conn.cursor() as cursor:
            _dogru_veritabani(cursor)
            cursor.execute("SELECT COUNT(*) FROM roller WHERE rol_adi = 'ADMIN'")
            assert cursor.fetchone()[0] == 1, "ADMIN rolü bulunamadı (rol adları büyük harfli kod olmalı)."
            cursor.execute("SELECT COUNT(*) FROM izinler")
            assert cursor.fetchone()[0] > 0

            cursor.execute(ADMIN_EKSIKLERI)
            eksikler = [satir[0] for satir in cursor.fetchall()]
            assert not eksikler, (
                "ADMIN rolünde kapalı ya da eksik izinler var: "
                + ", ".join(eksikler)
                + ". Yeni izin ekleyen migrasyon ADMIN'e de izin vermeli."
            )
    finally:
        conn.close()


def test_onarim_migrasyonu_bozulmus_admini_duzeltir_baskalarina_dokunmaz():
    spec = importlib.util.spec_from_file_location("admin_onarim_migrasyonu", MIGRASYON)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)

    conn = psycopg2.connect(**VT_AYARLARI)
    try:
        with conn.cursor() as cursor:
            _dogru_veritabani(cursor)
            cursor.execute("SELECT rol_id FROM roller WHERE rol_adi = 'ADMIN'")
            admin_id = cursor.fetchone()[0]
            cursor.execute("SELECT rol_id FROM roller WHERE rol_adi = 'MEMUR'")
            memur_id = cursor.fetchone()[0]
            cursor.execute("SELECT izin_id, izin_adi FROM izinler ORDER BY izin_id LIMIT 3")
            (kapali_id, _), (silinen_id, _), (acik_kalan_id, _) = cursor.fetchall()

            # Bozulmuş durum: bir izin kapalı, biri hiç satırsız; ayrıca MEMUR'un bir izni bilerek kapalı.
            cursor.execute("UPDATE rol_izinleri SET izin_var = 0 WHERE rol_id = %s AND izin_id = %s", (admin_id, kapali_id))
            cursor.execute("DELETE FROM rol_izinleri WHERE rol_id = %s AND izin_id = %s", (admin_id, silinen_id))
            cursor.execute("INSERT INTO rol_izinleri (rol_id, izin_id, izin_var) VALUES (%s, %s, 0) "
                           "ON CONFLICT (rol_id, izin_id) DO UPDATE SET izin_var = 0", (memur_id, kapali_id))
            cursor.execute(ADMIN_EKSIKLERI)
            assert len(cursor.fetchall()) >= 2

            cursor.execute(modul.ADMIN_ONARIM_SORGUSU)

            cursor.execute(ADMIN_EKSIKLERI)
            assert cursor.fetchall() == []                                   # ADMIN tamamen onarıldı
            cursor.execute("SELECT izin_var FROM rol_izinleri WHERE rol_id = %s AND izin_id = %s", (memur_id, kapali_id))
            assert cursor.fetchone()[0] == 0                                 # MEMUR'a dokunulmadı

            # İkinci çalıştırma hiçbir satırı değiştirmez (idempotent).
            cursor.execute(modul.ADMIN_ONARIM_SORGUSU)
            assert cursor.rowcount == 0
    finally:
        conn.rollback()   # veritabanını bozulmadan bırak
        conn.close()


def test_izin_ekle_ucu_yeni_izni_admine_otomatik_verir():
    izin_adi = f"QA_DENEME_IZNI_{uuid4().hex[:8].upper()}"
    sonuc = izin_ekle({"izin_adi": izin_adi}, kullanici_id=1)
    yeni_id = sonuc["izin_id"]

    conn = psycopg2.connect(**VT_AYARLARI)
    try:
        with conn.cursor() as cursor:
            _dogru_veritabani(cursor)
            cursor.execute(
                "SELECT r.rol_adi, ri.izin_var FROM roller r "
                "JOIN rol_izinleri ri ON ri.rol_id = r.rol_id WHERE ri.izin_id = %s",
                (yeni_id,),
            )
            satirlar = dict(cursor.fetchall())
            cursor.execute("SELECT COUNT(*) FROM roller")
            rol_sayisi = cursor.fetchone()[0]

            assert len(satirlar) == rol_sayisi                       # her rol için satır var
            assert satirlar["ADMIN"] == 1                            # ADMIN açık
            assert all(v == 0 for ad, v in satirlar.items() if ad != "ADMIN")   # diğerleri kapalı
    finally:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM rol_izinleri WHERE izin_id = %s", (yeni_id,))
            cursor.execute("DELETE FROM izinler WHERE izin_id = %s", (yeni_id,))
        conn.commit()
        conn.close()
