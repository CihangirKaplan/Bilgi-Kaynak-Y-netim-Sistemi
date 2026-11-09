"""FR-045: audit kayitlari veritabani duzeyinde degistirilemez / silinemez.

Gercek veritabani gerekmez; migration'in icerigi ve zincirdeki yeri denetlenir. Tetikleyicinin gercek
PostgreSQL'de calistigi ayrica elle dogrulanir (gecici `crkys` veritabaniyla).
"""
import importlib.util
import re
from pathlib import Path

import pytest

YOL = Path("alembic/versions/f3a9c2e47b18_denetim_kayitlari_degistirilemez.py")


@pytest.fixture(scope="module")
def migration():
    spec = importlib.util.spec_from_file_location("audit_kilidi", YOL)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def calistirilan_sql(fonksiyon):
    """upgrade()/downgrade() icinde op.execute ile gonderilen SQL metinleri."""
    from unittest.mock import patch
    with patch("alembic.op.execute") as yurut:
        fonksiyon()
    return [" ".join(c.args[0].split()) for c in yurut.call_args_list]


def test_migration_zincirin_icindedir_ve_zincir_tek_parcadir(migration):
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    betikler = ScriptDirectory.from_config(Config("alembic.ini"))
    heads = betikler.get_heads()

    assert len(heads) == 1
    assert betikler.get_revision("f3a9c2e47b18") is not None
    assert migration.revision in [
        r.revision for r in betikler.iterate_revisions(heads[0], "base")
    ]
    assert migration.down_revision == "d82c4a71f06b"


def test_update_delete_ve_truncate_uc_tetikleyiciyle_engellenir(migration):
    sql = " ".join(calistirilan_sql(migration.upgrade))
    assert "BEFORE UPDATE OR DELETE ON denetim_kayitlari FOR EACH ROW" in sql
    assert "BEFORE TRUNCATE ON denetim_kayitlari FOR EACH STATEMENT" in sql
    assert "RAISE EXCEPTION" in sql and "restrict_violation" in sql


def test_insert_engellenmez(migration):
    sql = " ".join(calistirilan_sql(migration.upgrade))
    olaylar = re.findall(r"BEFORE ([A-Z ]+?) ON denetim_kayitlari", sql)
    assert sorted(olaylar) == ["TRUNCATE", "UPDATE OR DELETE"]              # INSERT hicbir tetikleyicide yok


def test_yalniz_test_veritabani_muaftir(migration):
    sql = " ".join(calistirilan_sql(migration.upgrade))
    muaf = re.findall(r"current_database\(\)\s*=\s*'([^']+)'", sql)
    assert muaf == ["crkys_alembic_test"]                                  # gercek veritabani (crkys) muaf degil


def test_downgrade_tetikleyicileri_ve_fonksiyonu_kaldirir(migration):
    sql = calistirilan_sql(migration.downgrade)
    assert any("DROP TRIGGER IF EXISTS denetim_kayitlari_bosaltilamaz" in s for s in sql)
    assert any("DROP TRIGGER IF EXISTS denetim_kayitlari_degistirilemez" in s for s in sql)
    assert any("DROP FUNCTION IF EXISTS denetim_kaydi_degistirilemez" in s for s in sql)
    # tetikleyiciler fonksiyondan once kaldirilmali
    assert max(i for i, s in enumerate(sql) if "DROP TRIGGER" in s) < next(i for i, s in enumerate(sql) if "DROP FUNCTION" in s)


def test_uygulama_kodu_audit_tablosunu_degistirmez_ya_da_silmez():
    """Tetikleyici ek bir koruma; uygulama zaten yalnizca INSERT/SELECT yapmali."""
    for dosya in ("sunucu.py", "denetim.py"):
        metin = Path(dosya).read_text(encoding="utf-8")
        assert not re.search(r"(UPDATE|DELETE\s+FROM|TRUNCATE)\s+(TABLE\s+)?denetim_kayitlari", metin, re.I), dosya
