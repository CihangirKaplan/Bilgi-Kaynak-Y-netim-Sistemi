"""Menünün yetkileri sunucudan (/api/yetkilerim) alınır; elle yazılmış tablo yedek olarak kalır.

Gerçek API veya PostgreSQL kullanılmaz.
"""
import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest



class _GecikmeliModul:
    """main_window'u (PySide6) toplama aşamasında değil, ilk kullanımda içe aktarır.

    CI'da modül düzeyinde içe aktarma, sunucu testlerinden önce Qt'yi yükleyip
    segmentation fault'a yol açtı; diğer GUI testleri de aynı şekilde geç yüklüyor.
    """

    def __getattr__(self, ad):
        import main_window
        return getattr(main_window, ad)


mw = _GecikmeliModul()


@pytest.fixture(autouse=True)
def temiz_yetkiler():
    mw._SUNUCU_YETKILERI.clear()
    yield
    mw._SUNUCU_YETKILERI.clear()


# ------------------------------------------------------------ eşleştirme tablosu
def test_her_ekran_izninin_sunucu_karsiligi_vardir():
    assert set(mw.IZIN_KODLARI) == set(mw.IZIN)


def test_izin_kodlari_gecerli_bicimde_ve_bos_degil():
    for ad, kodlar in mw.IZIN_KODLARI.items():
        assert isinstance(kodlar, tuple) and kodlar, ad
        assert all(re.fullmatch(r"[A-Z_]+", kod) for kod in kodlar), ad


def test_izin_kodlari_veritabani_migrationlarinda_tanimlidir():
    """Eşleştirmede yazım hatası olmasın: her kod bir migration'da tanımlı olmalı."""
    metin = "\n".join(p.read_text(encoding="utf-8") for p in Path("alembic/versions").glob("*.py"))
    eksik = sorted({k for kodlar in mw.IZIN_KODLARI.values() for k in kodlar if f"'{k}'" not in metin})
    assert not eksik, f"Migration'larda tanımlı olmayan izin kodları: {eksik}"


def test_sadece_rol_istisnalari_gecerli_izin_ve_rol_icerir():
    for ad, roller in mw.IZIN_SADECE_ROL.items():
        assert ad in mw.IZIN
        assert roller <= set(mw.ROLLER)


def test_menu_ve_aksiyonlardaki_izin_adlari_tabloda_vardir():
    """Menüde yazım hatalı bir izin adı kalırsa (örn. 'REZERVASYON_IPTAL') o öğe sessizce gizlenir."""
    for bolum, ogeler in mw.MENU:
        for oge in ogeler:
            if oge["izin"] is not None:
                assert oge["izin"] in mw.IZIN, (oge["ad"], oge["izin"])
            for etiket, izin in oge.get("aksiyon", []):
                assert izin in mw.IZIN, (oge["ad"], etiket, izin)


# ------------------------------------------------------------------- izin_var
def test_sunucu_izinleri_varsa_menu_onlara_gore_belirlenir():
    mw.yetkileri_ayarla("psikolog", ["RANDEVU_OLUSTUR", "TAKVIM_GORUNTULE"])
    assert mw.izin_var("psikolog", "Randevu oluşturma")
    assert mw.izin_var("psikolog", "Randevu takvimini görüntüleme")
    assert not mw.izin_var("psikolog", "Randevu iptal etme")   # sunucu vermedi (eski tabloda 'E' idi)


def test_veritabaninda_degisen_izin_menuye_yansir():
    """Memur'a veritabanında randevu izni eklenirse, kod değişmeden menüde görünür."""
    mw.yetkileri_ayarla("memur", ["CIHAZ_UYGUNLUK_GORUNTULE"])
    assert not mw.izin_var("memur", "Randevu oluşturma")       # eski tabloda da 'H'
    mw.yetkileri_ayarla("memur", ["CIHAZ_UYGUNLUK_GORUNTULE", "RANDEVU_OLUSTUR"])
    assert mw.izin_var("memur", "Randevu oluşturma")


def test_sunucu_yetkisi_yoksa_eski_tabloya_donulur():
    # Eski tabloda psikolog 'Randevu oluşturma' = E, memur = H
    assert mw.izin_var("psikolog", "Randevu oluşturma")
    assert not mw.izin_var("memur", "Randevu oluşturma")


def test_birden_cok_kodlu_izin_icin_hepsi_gerekir():
    mw.yetkileri_ayarla("admin", ["ODA_EKLE"])
    assert not mw.izin_var("admin", "Oda yönetimi")             # ODA_DUZENLE eksik
    mw.yetkileri_ayarla("admin", ["ODA_EKLE", "ODA_DUZENLE"])
    assert mw.izin_var("admin", "Oda yönetimi")


def test_bilinmeyen_izin_adi_cokmez_yok_sayilir():
    assert mw.izin_var("psikolog", "REZERVASYON_IPTAL") is False
    mw.yetkileri_ayarla("psikolog", ["RANDEVU_OLUSTUR"])
    assert mw.izin_var("psikolog", "REZERVASYON_IPTAL") is False


def test_danisma_ogrenci_paneli_adminde_izin_olsa_da_gorunmez():
    """Admin'in veritabanında DANISMA_OTURUMU_YONET izni var ama öğrenci kaydı yok: panel gösterilmez."""
    tum_izinler = {k for kodlar in mw.IZIN_KODLARI.values() for k in kodlar}
    mw.yetkileri_ayarla("admin", tum_izinler)
    mw.yetkileri_ayarla("ogrenci", ["DANISMA_OTURUMU_YONET"])
    assert not mw.izin_var("admin", "Danışma masası oturumunu yönetme")
    assert mw.izin_var("ogrenci", "Danışma masası oturumunu yönetme")


def test_roller_birbirinin_sunucu_yetkisini_gormez():
    mw.yetkileri_ayarla("psikolog", ["RANDEVU_OLUSTUR"])
    # memur için sunucu yetkisi yok: eski tabloya döner (H), psikologunkini kullanmaz
    assert not mw.izin_var("memur", "Randevu oluşturma")


# ------------------------------------------------- sunucudan alma (AnaPencere)
def pencere(token="TOKEN", onizleme=False, rol="psikolog"):
    return SimpleNamespace(aktif_rol=rol, token=token, rol_onizleme=onizleme, api_url="http://testserver")


def yanit(durum=200, veri=None, oturum_bitti=False):
    r = MagicMock()
    r.status_code = durum
    r.json.return_value = veri if veri is not None else {}
    r._tkys_oturum_reddedildi = oturum_bitti
    return r


def al(p, **kwargs):
    with patch("main_window.oturum_kontrollu_istek", **kwargs) as istek:
        mw.AnaPencere._yetkileri_sunucudan_al(p)
    return istek


def test_basarili_yanit_yetkileri_kaydeder_ve_dogru_adrese_sorar():
    istek = al(pencere(), return_value=yanit(200, {"rol_adi": "PSIKOLOG", "izinler": ["RANDEVU_OLUSTUR"]}))
    assert mw._SUNUCU_YETKILERI["psikolog"] == frozenset({"RANDEVU_OLUSTUR"})
    assert istek.call_args.args[:2] == ("GET", "http://testserver/api/yetkilerim")
    assert istek.call_args.kwargs["headers"] == {"Authorization": "Bearer TOKEN"}


@pytest.mark.parametrize("kwargs", [
    {"return_value": yanit(404)},                                  # eski sunucu: uç yok
    {"return_value": yanit(500)},
    {"return_value": yanit(200, {"izinler": "bozuk"})},            # beklenmeyen biçim
    {"return_value": yanit(200, {})},
    {"return_value": yanit(401, {"detail": "Token süresi dolmuş."}, oturum_bitti=True)},
    {"side_effect": OSError("sunucu kapalı")},
])
def test_alinamazsa_yerel_tabloya_donulur_ve_eski_yetki_kalmaz(kwargs):
    mw.yetkileri_ayarla("psikolog", ["ESKI_KALINTI"])             # önceki oturumdan kalmış olabilir
    al(pencere(), **kwargs)
    assert "psikolog" not in mw._SUNUCU_YETKILERI
    assert mw.izin_var("psikolog", "Randevu oluşturma")           # eski tablo (psikolog: E)


def test_token_yoksa_veya_rol_onizlemesinde_sunucuya_sorulmaz():
    for p in (pencere(token=""), pencere(onizleme=True)):
        istek = al(p, return_value=yanit(200, {"izinler": ["X"]}))
        istek.assert_not_called()
        assert "psikolog" not in mw._SUNUCU_YETKILERI


def test_faaliyet_birimleri_dugmesi_yalnizca_admin_iznine_baglidir():
    """Düğme Faaliyet Kayıtları sayfasında durur. Faaliyet kaydı izni (Memur, Müdür, Proje Asistanı'nda
    var) bu düğmeyi AÇMAMALI; yalnızca FAALIYET_BIRIMI_DUZENLE (Admin) açar."""
    kayit_izni = ["FAALIYET_KAYITLARI_DUZENLE"]
    for rol in ("memur", "mudur", "asistan"):
        mw.yetkileri_ayarla(rol, kayit_izni)
        assert mw.izin_var(rol, "Faaliyet kayıtlarını düzenleme")
        assert not mw.izin_var(rol, "Faaliyet birimlerini yönetme"), rol
    mw.yetkileri_ayarla("admin", kayit_izni + ["FAALIYET_BIRIMI_DUZENLE"])
    assert mw.izin_var("admin", "Faaliyet birimlerini yönetme")
