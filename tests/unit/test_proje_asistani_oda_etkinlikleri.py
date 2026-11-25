"""Proje Asistanı'na Oda Etkinlikleri izni (varsayılan): istemci yedek maskesi, sunucu izinleriyle dinamik menü ve migration."""
import importlib.util
import os
import pathlib
from unittest.mock import patch

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class _GecikmeliModul:
    """main_window (PySide6) ilk kullanımda içe aktarılır; toplama aşamasında Qt yüklenmez."""

    def __getattr__(self, ad):
        import client.main_window as main_window
        return getattr(main_window, ad)


mw = _GecikmeliModul()
GORUNTULE, YONET = "Oda etkinliklerini görüntüleme", "Oda etkinliklerini yönetme"
MIGRATION = pathlib.Path(__file__).resolve().parents[2] / "database" / "migrations" / "versions" / "a7c3e5b9d014_proje_asistani_oda_etkinlik_izinleri.py"


@pytest.fixture(autouse=True)
def temiz_yetkiler():
    mw._SUNUCU_YETKILERI.clear()
    yield
    mw._SUNUCU_YETKILERI.clear()


def test_yedek_maske_proje_asistanina_goruntuleme_ve_yonetme_verir():
    """Sunucudan izin alınamazsa kullanılan yedek tablo da sunucudaki varsayılanla aynı olmalı."""
    beklenen_goruntuleme = {"psikolog", "memur", "mudur", "ogrenci", "asistan", "admin"}
    beklenen_yonetme = {"memur", "mudur", "asistan", "admin"}
    assert {r for r in mw.ROLLER if mw.izin_var(r, GORUNTULE)} == beklenen_goruntuleme
    assert {r for r in mw.ROLLER if mw.izin_var(r, YONET)} == beklenen_yonetme


def test_menu_sunucu_izinlerine_gore_dinamik_degisir_rol_adina_bakmaz():
    ad = "Oda Etkinlikleri"

    def gorunuyor(rol):
        return any(o["ad"] == ad and mw.izin_var(rol, o["izin"]) for _, ogeler in mw.MENU for o in ogeler)

    mw.yetkileri_ayarla("asistan", ["TAKVIM_GORUNTULE", "ODA_ETKINLIK_GORUNTULE", "ODA_ETKINLIK_YONET"])
    assert gorunuyor("asistan") and mw.izin_var("asistan", YONET)
    mw.yetkileri_ayarla("asistan", ["TAKVIM_GORUNTULE", "ODA_ETKINLIK_GORUNTULE"])               # yalnız görüntüleme: sayfa var, yönetme yok
    assert gorunuyor("asistan") and not mw.izin_var("asistan", YONET)
    mw.yetkileri_ayarla("asistan", ["TAKVIM_GORUNTULE"])                                          # yönetici izni kapatırsa yedek maske beklenmeden kalkar
    assert not gorunuyor("asistan") and not mw.izin_var("asistan", GORUNTULE)
    mw.yetkileri_ayarla("psikolog", ["ODA_ETKINLIK_GORUNTULE", "ODA_ETKINLIK_YONET"])             # izin psikologa verilirse kodda değişiklik gerekmeden açılır
    assert mw.izin_var("psikolog", YONET)


def _migration():
    ozellik = importlib.util.spec_from_file_location("a7c3e5b9d014", MIGRATION)
    modul = importlib.util.module_from_spec(ozellik)
    ozellik.loader.exec_module(modul)
    return modul


def test_migration_proje_asistani_icin_iki_izni_acar_geri_alinca_kapatir():
    modul = _migration()
    assert modul.revision == "a7c3e5b9d014" and modul.down_revision == "f4c8a2e6b917"
    sorgular = []
    with patch.object(modul.op, "execute", side_effect=sorgular.append):
        modul.upgrade()
        modul.downgrade()
    yukari, asagi = (s.replace("\n", " ") for s in sorgular)
    for sorgu, deger in ((yukari, 1), (asagi, 0)):
        assert "PROJE_ASISTANI" in sorgu and "ODA_ETKINLIK_GORUNTULE" in sorgu and "ODA_ETKINLIK_YONET" in sorgu
        assert f"SELECT r.rol_id, i.izin_id, {deger}" in sorgu and "ON CONFLICT (rol_id, izin_id) DO UPDATE" in sorgu
    for diger in ("ADMIN", "MEMUR", "MUDUR", "PSIKOLOG", "DANISMA_OGRENCISI"):
        assert diger not in yukari                                                                # başka rolün izni değişmez


def test_migration_zinciri_tek_head_ve_oncekine_baglanir():
    versiyonlar = MIGRATION.parent
    kaynak = {p.name: p.read_text(encoding="utf-8") for p in versiyonlar.glob("*.py")}
    assert 'down_revision = "f4c8a2e6b917"' in kaynak[MIGRATION.name]
    bagli = [ad for ad, metin in kaynak.items() if 'f4c8a2e6b917"' in metin and "down_revision" in metin and ad != "f4c8a2e6b917" and "down_revision = \"f4c8a2e6b917\"" in metin]
    assert bagli == [MIGRATION.name]                                                              # f4c8... tek bir sonraki geçişe sahip: dallanma yok
