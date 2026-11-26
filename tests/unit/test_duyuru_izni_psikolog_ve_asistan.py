"""Duyuru yayınlama izni (DUYURU_YONET) Psikolog ve Proje Asistanı için de açık; Danışma Öğrencisi kapalı."""
import re
from pathlib import Path

KOK = Path(__file__).resolve().parents[2]
MIGRASYON = KOK / "database" / "migrations" / "versions" / "e5b9c1d7f302_duyuru_izni_psikolog_ve_asistan.py"


def test_migrasyon_zinciri_ve_roller():
    kaynak = MIGRASYON.read_text(encoding="utf-8")
    assert 'revision = "e5b9c1d7f302"' in kaynak and 'down_revision = "d4a8b6c2e913"' in kaynak
    assert "UPPER(r.rol_adi) IN ('PSIKOLOG', 'PROJE_ASISTANI')" in kaynak and "i.izin_adi = 'DUYURU_YONET'" in kaynak
    assert "DANISMA" not in kaynak.split("def _izni_ayarla")[1]                      # Danışma Öğrencisi'ne dokunulmaz
    assert "_izni_ayarla(1)" in kaynak.split("def upgrade")[1].split("def downgrade")[0]
    assert "_izni_ayarla(0)" in kaynak.split("def downgrade")[1]


def test_zincirde_tek_head_vardir():
    import importlib.util
    spec = importlib.util.spec_from_file_location("tek_head", KOK / "scripts" / "alembic_tek_head_kontrol.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    kod, mesaj = modul.kontrol_et()
    assert kod == 0 and "e5b9c1d7f302" in mesaj, mesaj


def test_istemci_yedek_maskesi_sunucu_varsayilaniyla_ayni():
    """Sunucudan izin gelmezse kullanılan elle yazılmış maske, veritabanı varsayılanıyla tutarlı olmalı."""
    import client.main_window as mw
    acik = {r for r in mw.ROLLER if mw.izin_var(r, "Duyuruları yönetme")}
    assert acik == {"psikolog", "memur", "mudur", "asistan", "admin"} and "ogrenci" not in acik


def test_belgeler_guncel():
    assert "Danışma Öğrencisi dışında herkes" in (KOK / "user-manuals" / "Ortak_Kullanim.md").read_text(encoding="utf-8")
    satir = next(s for s in (KOK / "user-manuals" / "README.md").read_text(encoding="utf-8").splitlines() if "duyuru yayınlama" in s)
    assert [h.strip() for h in satir.strip("|").split("|")[1:]] == ["✔", "–", "✔", "✔", "✔", "✔"]       # Psikolog, Danışma Öğr., Proje Asist., Memur, Müdür, Admin
