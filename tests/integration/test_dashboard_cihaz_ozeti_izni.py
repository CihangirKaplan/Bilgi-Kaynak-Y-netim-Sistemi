"""Ana paneldeki cihaz özeti rol adına değil, sunucudaki izne bağlıdır.

Gerçek API veya PostgreSQL kullanılmaz.
"""
import inspect

import pytest


class _GecikmeliModul:
    """main_window (PySide6) ilk kullanımda içe aktarılır; toplama aşamasında Qt yüklenmez."""

    def __getattr__(self, ad):
        import client.main_window as main_window
        return getattr(main_window, ad)


mw = _GecikmeliModul()

DASHBOARD_UCLARI = ("dashboard_ozet_getir",)                                               # yalnızca cihaz envanteri yöneticisine
# Bugünkü rezervasyon listesi daha geniştir: cihazı yönetenler, rezervasyon yapanlar ve Cihaz Uygunluğu'nu görenler (kişi adı yalnızca ilk ikisine).
# Bildirim ucu daha geniştir: envanter yöneticisi VEYA bakım/kalibrasyon izni olan kullanıcı (her biri yalnızca kendi türünü görür).


@pytest.fixture(autouse=True)
def temiz_yetkiler():
    mw._SUNUCU_YETKILERI.clear()
    yield
    mw._SUNUCU_YETKILERI.clear()


def test_istemci_izni_cihaz_ozeti_sunucu_uclariyla_ayni_izin_kodudur():
    import server.sunucu as sunucu
    assert mw.IZIN_KODLARI["Cihaz envanterini yönetme"] == ("CIHAZ_ENVANTER_YONET",)
    for ad in DASHBOARD_UCLARI:
        assert 'izin_kontrol("CIHAZ_ENVANTER_YONET")' in inspect.getsource(getattr(sunucu, ad)), ad
    rezervasyon = inspect.getsource(sunucu.dashboard_bugunku_rezervasyonlar)
    assert "izin_kontrol_biri(" in rezervasyon
    for kod in ("CIHAZ_ENVANTER_YONET", "CIHAZ_UYGUNLUK_GORUNTULE", "CIHAZ_REZERVASYON"):
        assert f'"{kod}"' in rezervasyon
    bildirim = inspect.getsource(sunucu.yaklasan_islemler_getir)
    assert 'izin_kontrol_biri(' in bildirim and '"CIHAZ_ENVANTER_YONET"' in bildirim and "BAKIM_KAYITLARI_GORUNTULE" in bildirim


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


def test_rezervasyon_paneli_rezervasyon_yapan_ve_uygunluk_goren_rollere_de_acilir():
    mw.yetkileri_ayarla("memur", ["CIHAZ_ENVANTER_YONET", "TAKVIM_GORUNTULE"])
    mw.yetkileri_ayarla("asistan", ["CIHAZ_REZERVASYON", "CIHAZ_UYGUNLUK_GORUNTULE"])
    mw.yetkileri_ayarla("psikolog", ["TAKVIM_GORUNTULE", "CIHAZ_UYGUNLUK_GORUNTULE"])
    mw.yetkileri_ayarla("ogrenci", ["TAKVIM_GORUNTULE"])                  # cihazla ilgili hiçbir izni yok
    assert mw.rezervasyon_panelini_gorebilir_mi("memur")
    assert mw.rezervasyon_panelini_gorebilir_mi("asistan") and not mw.cihaz_ozeti_gorebilir_mi("asistan")       # panel var, özet kartları ve bildirimler yok
    assert mw.rezervasyon_panelini_gorebilir_mi("psikolog") and not mw.cihaz_ozeti_gorebilir_mi("psikolog")
    assert not mw.rezervasyon_panelini_gorebilir_mi("ogrenci")


def test_ana_panel_rezervasyon_panelini_izin_fonksiyonuyla_acar():
    assert "rezervasyon_paneli=rezervasyon_panelini_gorebilir_mi(rol)" in inspect.getsource(mw.AnaPencere.sayfa_dashboard)


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
