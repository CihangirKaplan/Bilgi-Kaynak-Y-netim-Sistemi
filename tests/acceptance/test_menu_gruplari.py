"""Sol menü grupları: GENEL BAKIŞ (panel + oda sayfaları), Oda Etkinlikleri öğrenci ve faaliyet grubunda."""
import client.main_window as mw


def _gruplar():
    return {ad: [o["ad"] for o in ogeler] for ad, ogeler in mw.MENU}


def test_genel_bakis_grubu_panel_ve_oda_sayfalarini_icerir():
    gruplar = _gruplar()
    assert "GENEL" not in gruplar
    assert gruplar["GENEL BAKIŞ"] == ["Ana Kontrol Paneli", "Oda Kullanımı", "Oda Kullanım Raporu"]


def test_oda_etkinlikleri_ogrenci_ve_faaliyet_grubunda():
    gruplar = _gruplar()
    assert "Oda Etkinlikleri" in gruplar["ÖĞRENCİ & FAALİYET YÖNETİMİ"]
    assert "Oda Etkinlikleri" not in gruplar["KLİNİK OPERASYON"]
    assert gruplar["KLİNİK OPERASYON"] == ["Randevu Yönetimi", "Danışanlar", "Randevu Raporları"]


def test_her_sayfa_tek_grupta_ve_izinleri_degismedi():
    adlar = [o["ad"] for _, ogeler in mw.MENU for o in ogeler]
    assert len(adlar) == len(set(adlar))
    izin = {o["ad"]: o["izin"] for _, ogeler in mw.MENU for o in ogeler}
    assert izin["Oda Etkinlikleri"] == "Oda etkinliklerini görüntüleme"
    assert izin["Oda Kullanım Raporu"] == "Yönetim raporlarını görüntüleme"
    assert izin["Oda Kullanımı"] == "Oda kullanım durumunu görüntüleme"


def test_kenar_cubugu_simge_ve_acik_grup_yeni_baslik_adini_kullanir():
    from client.tkys_sidebar_refined import CATEGORY_ICONS
    assert set(CATEGORY_ICONS) == {ad for ad, _ in mw.MENU}
