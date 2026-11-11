"""
Rol adı normalleştirme migrasyonu (d41c7e0a95b3).

SQL, gerçek bir veritabanında (sqlite, bellekte) çalıştırılarak sınanır: eski title-case adlar koda
çevrilir; zaten doğru olan veritabanlarında (CI) hiçbir şey değişmez; UNIQUE çakışması patlatmaz.
"""

import importlib.util
import sqlite3
from pathlib import Path

import pytest

DOSYA = Path(__file__).resolve().parent.parent / "alembic" / "versions" / "d41c7e0a95b3_rol_adlarini_normallestir.py"


def migrasyon():
    spec = importlib.util.spec_from_file_location("rol_adi_migrasyonu", DOSYA)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def veritabani(satirlar):
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE roller (rol_id INTEGER PRIMARY KEY, rol_adi TEXT NOT NULL UNIQUE, gorunen_ad TEXT)")
    conn.executemany("INSERT INTO roller VALUES (?, ?, ?)", satirlar)
    return conn


def calistir(conn):
    m = migrasyon()
    for eski, yeni in m.ESLESMELER:
        conn.execute(m.GORUNEN_AD_SORGUSU, {"eski": eski, "yeni": yeni})
        conn.execute(m.KOD_SORGUSU, {"eski": eski, "yeni": yeni})


def tablo(conn):
    return conn.execute("SELECT rol_id, rol_adi, gorunen_ad FROM roller ORDER BY rol_id").fetchall()


# Yerel veritabanında görülen durum
ESKI_KURULUM = [
    (1, "Psikolog", "Psikolog"), (2, "Memur", "Memur"), (3, "Müdür", "Müdür"),
    (4, "Danışma Öğrencisi", "Danışma Öğrencisi"), (5, "Proje Asistanı", "Proje Asistanı"),
    (6, "Admin", "Sistem Admin"), (14, "KLINIK PERSONELI", "Klinik Personeli"),
]
DOGRU_KURULUM = [
    (1, "PSIKOLOG", "Psikolog"), (2, "MEMUR", "Memur"), (3, "MUDUR", "Müdür"),
    (4, "DANISMA_OGRENCISI", "Danışma Öğrencisi"), (5, "PROJE_ASISTANI", "Proje Asistanı"),
    (6, "ADMIN", "Sistem Admin"), (14, "KLINIK PERSONELI", "Klinik Personeli"),
]


def test_eski_title_case_adlar_koda_cevrilir_gorunen_ad_ve_diger_roller_degismez():
    conn = veritabani(ESKI_KURULUM)
    calistir(conn)
    assert tablo(conn) == DOGRU_KURULUM


def test_zaten_dogru_veritabaninda_hicbir_sey_degismez():
    conn = veritabani(DOGRU_KURULUM)
    calistir(conn)
    assert tablo(conn) == DOGRU_KURULUM


def test_iki_kez_calistirmak_zararsizdir():
    conn = veritabani(ESKI_KURULUM)
    calistir(conn)
    calistir(conn)
    assert tablo(conn) == DOGRU_KURULUM


def test_gorunen_ad_bossa_okunur_eski_ad_saklanir():
    conn = veritabani([(1, "Psikolog", None), (2, "Memur", ""), (6, "Admin", "Sistem Admin")])
    calistir(conn)
    assert tablo(conn) == [(1, "PSIKOLOG", "Psikolog"), (2, "MEMUR", "Memur"), (6, "ADMIN", "Sistem Admin")]


def test_kucuk_harfli_yazimlar_da_duzelir():
    conn = veritabani([(1, "psikolog", "Psikolog"), (6, "admin", "Sistem Admin")])
    calistir(conn)
    assert [s[1] for s in tablo(conn)] == ["PSIKOLOG", "ADMIN"]


def test_ayni_kod_zaten_varsa_unique_cakismasi_olmaz_ve_eski_kayit_dokunulmaz():
    conn = veritabani([(1, "Admin", "Eski Admin"), (6, "ADMIN", "Sistem Admin")])
    calistir(conn)  # sqlite UNIQUE ihlali olsaydı burada patlardı
    assert tablo(conn) == [(1, "Admin", "Eski Admin"), (6, "ADMIN", "Sistem Admin")]


def test_migrasyon_zincirin_basinda_ve_geri_alma_bilerek_bos():
    m = migrasyon()
    assert m.revision == "d41c7e0a95b3"
    assert m.down_revision == "b3f7a1c92d84"
    assert m.downgrade() is None


@pytest.mark.parametrize("eski, yeni", [("Müdür", "MUDUR"), ("Danışma Öğrencisi", "DANISMA_OGRENCISI"), ("Proje Asistanı", "PROJE_ASISTANI")])
def test_turkce_karakterli_adlar_acikca_eslestirilir(eski, yeni):
    assert (eski, yeni) in migrasyon().ESLESMELER  # UPPER() bunları kodlara çeviremez
