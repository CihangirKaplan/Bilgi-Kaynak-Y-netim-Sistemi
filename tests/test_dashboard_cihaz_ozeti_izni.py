"""Ana paneldeki cihaz özeti rol adına değil, sunucudaki izne bağlıdır.

Gerçek API veya PostgreSQL kullanılmaz.
"""
import inspect

import pytest


class _GecikmeliModul:
    """main_window (PySide6) ilk kullanımda içe aktarılır; toplama aşamasında Qt yüklenmez."""

    def __getattr__(self, ad):
        import main_window
        return getattr(main_window, ad)


mw = _GecikmeliModul()

DASHBOARD_UCLARI = ("dashboard_ozet_getir", "dashboard_bugunku_rezervasyonlar", "yaklasan_islemler_getir")


@pytest.fixture(autouse=True)
def temiz_yetkiler():
    mw._SUNUCU_YETKILERI.clear()
    yield
    mw._SUNUCU_YETKILERI.clear()


def test_istemci_izni_cihaz_ozeti_sunucu_uclariyla_ayni_izin_kodudur():
    import sunucu
    assert mw.IZIN_KODLARI["Cihaz envanterini yönetme"] == ("CIHAZ_ENVANTER_YONET",)
    for ad in DASHBOARD_UCLARI:
        assert 'izin_kontrol("CIHAZ_ENVANTER_YONET")' in inspect.getsource(getattr(sunucu, ad)), ad


def test_sunucu_yetkisi_yokken_eski_tabloya_donulur():
    gorenler = {rol for rol in mw.ROLLER if mw.cihaz_ozeti_gorebilir_mi(rol)}
    assert gorenler == {"memur", "mudur", "admin"}


def test_ozeti_yalniz_cihaz_envanteri_izni_olan_rol_gorur():
    mw.yetkileri_ayarla("memur", ["CIHAZ_ENVANTER_YONET", "TAKVIM_GORUNTULE"])
    mw.yetkileri_ayarla("asistan", ["CIHAZ_REZERVASYON", "CIHAZ_UYGUNLUK_GORUNTULE"])
    mw.yetkileri_ayarla("psikolog", ["TAKVIM_GORUNTULE"])
    assert mw.cihaz_ozeti_gorebilir_mi("memur")
    assert not mw.cihaz_ozeti_gorebilir_mi("asistan")      # rezervasyon izni ozet uçlarına yetmez (403 alırdı)
    assert not mw.cihaz_ozeti_gorebilir_mi("psikolog")


def test_veritabaninda_izin_degisince_rol_adi_beklemeden_panel_degisir():
    # Memur'dan izin alınırsa özet kalkar (eskiden rol adı listede olduğu için 403'lü istek atardı).
    mw.yetkileri_ayarla("memur", ["TAKVIM_GORUNTULE"])
    assert not mw.cihaz_ozeti_gorebilir_mi("memur")
    # Psikolog'a izin verilirse, kodda değişiklik gerekmeden özet görünür.
    mw.yetkileri_ayarla("psikolog", ["TAKVIM_GORUNTULE", "CIHAZ_ENVANTER_YONET"])
    assert mw.cihaz_ozeti_gorebilir_mi("psikolog")


def test_roller_birbirinin_sunucu_yetkisini_kullanmaz():
    mw.yetkileri_ayarla("psikolog", ["CIHAZ_ENVANTER_YONET"])
    assert not mw.cihaz_ozeti_gorebilir_mi("ogrenci")       # öğrenci için sunucu yetkisi yok -> eski tablo (H)


def test_ana_panel_rol_adi_listesi_yerine_izin_fonksiyonunu_kullanir():
    kaynak = inspect.getsource(mw.AnaPencere.sayfa_dashboard)
    assert "cihaz_ozeti_gorebilir_mi(rol)" in kaynak
    assert '["mudur", "admin", "memur"]' not in kaynak
