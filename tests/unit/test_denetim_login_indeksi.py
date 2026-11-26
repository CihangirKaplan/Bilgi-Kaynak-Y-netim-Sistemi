"""Yetki Raporu 'son giriş' sorgusu: kısmi indeksin migration'ı var, zincir tek head ve sorgu indeksin kullanılabileceği biçimde yazılmış."""
import re
from pathlib import Path

KOK = Path(__file__).resolve().parents[2]
MIGRASYON = KOK / "database" / "migrations" / "versions" / "d4a8b6c2e913_denetim_login_indeksi.py"


def test_migrasyon_kismi_indeksi_olusturur_ve_geri_alir():
    kaynak = MIGRASYON.read_text(encoding="utf-8")
    assert 'revision = "d4a8b6c2e913"' in kaynak and 'down_revision = "c9d2e4f6a801"' in kaynak
    assert re.search(r"CREATE INDEX IF NOT EXISTS ix_denetim_login_kullanici_tarih\s+ON denetim_kayitlari \(kullanici_id, olusturulma_tarihi DESC\)\s+WHERE olay_turu = 'LOGIN'", kaynak)
    assert "DROP INDEX IF EXISTS ix_denetim_login_kullanici_tarih" in kaynak


def test_son_giris_sorgusu_enum_dogrudan_karsilastirir():
    """`olay_turu::text = 'LOGIN'` yazılırsa kısmi indeks (WHERE olay_turu = 'LOGIN') planlayıcıca eşleşmez; sorgu enum karşılaştırması olmalı."""
    kaynak = (KOK / "server" / "rapor_kullanim.py").read_text(encoding="utf-8")
    son_giris = kaynak[kaynak.index("SELECT MAX(d.olusturulma_tarihi)"):][:200]
    assert "d.olay_turu = 'LOGIN'" in son_giris and "olay_turu::text" not in son_giris


def test_migrasyon_zincirinde_tek_head_vardir():
    import importlib.util
    spec = importlib.util.spec_from_file_location("tek_head", KOK / "scripts" / "alembic_tek_head_kontrol.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    kod, mesaj = modul.kontrol_et()
    assert kod == 0, mesaj
    assert "d4a8b6c2e913" in mesaj
