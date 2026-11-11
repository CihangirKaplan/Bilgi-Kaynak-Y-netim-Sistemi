"""
ADMIN rolü her izne sahip olmalı: onarım migrasyonu (f1c8d6a32e75) ve izin_ekle'nin otomatik ADMIN yetkisi.

Gerçek PostgreSQL ile olan karşılıkları: test_admin_tum_izinler_pg_quality.py
"""

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sunucu import izin_ekle

MIGRASYON = Path(__file__).resolve().parent.parent / "alembic" / "versions" / "f1c8d6a32e75_admin_tum_izinlere_sahip.py"


def migrasyon():
    spec = importlib.util.spec_from_file_location("admin_onarim_migrasyonu", MIGRASYON)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def baglanti(yeni_id=42):
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchone.return_value = (yeni_id,)
    return conn, cursor


def test_yeni_izin_admine_otomatik_verilir_diger_roller_kapali_baslar():
    conn, cursor = baglanti(42)
    with patch("sunucu.psycopg2.connect", return_value=conn):
        sonuc = izin_ekle({"izin_adi": "YENI_DENEME_IZNI"}, kullanici_id=1)

    assert sonuc == {"mesaj": "İzin başarıyla eklendi", "izin_id": 42}

    ekleme = next(c for c in cursor.execute.call_args_list if "INSERT INTO izinler" in c.args[0])
    assert ekleme.args[1] == ("YENI_DENEME_IZNI",)

    verme = next(c for c in cursor.execute.call_args_list if "INSERT INTO rol_izinleri" in c.args[0])
    sql = verme.args[0]
    assert verme.args[1] == (42,)
    assert "UPPER(r.rol_adi) = 'ADMIN' THEN 1 ELSE 0" in sql      # yalnızca ADMIN açık
    assert "FROM roller r" in sql                                  # her rol için satır
    assert "ON CONFLICT (rol_id, izin_id) DO NOTHING" in sql
    conn.commit.assert_called_once()


def test_izin_ekleme_basarisizsa_rol_izni_yazilmaz_ve_geri_alinir():
    conn, cursor = baglanti()
    cursor.execute.side_effect = RuntimeError("UNIQUE ihlali")
    with patch("sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(Exception) as hata:
            izin_ekle({"izin_adi": "VAR_OLAN_IZIN"}, kullanici_id=1)
    assert getattr(hata.value, "status_code", None) == 500
    assert not any("INSERT INTO rol_izinleri" in c.args[0] for c in cursor.execute.call_args_list)
    conn.commit.assert_not_called()
    conn.rollback.assert_called()


def test_onarim_sorgusu_yalnizca_admini_hedefler_ve_dogru_satirlara_dokunmaz():
    m = migrasyon()
    sql = " ".join(m.ADMIN_ONARIM_SORGUSU.split())
    assert "WHERE UPPER(r.rol_adi) = 'ADMIN'" in sql                 # diğer roller etkilenmez
    assert "ON CONFLICT (rol_id, izin_id) DO UPDATE SET izin_var = 1" in sql
    assert "WHERE rol_izinleri.izin_var IS DISTINCT FROM 1" in sql    # zaten açık olanlar yeniden yazılmaz
    assert "izin_var = 0" not in sql                                   # hiçbir yetki geri alınmaz


def test_migrasyon_zincirin_basinda_ve_geri_alma_bilerek_bos():
    m = migrasyon()
    assert m.revision == "f1c8d6a32e75"
    assert m.down_revision == "d41c7e0a95b3"
    assert m.downgrade() is None
