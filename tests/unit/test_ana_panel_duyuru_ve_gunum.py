"""Ana panel: duyurular (herkes okur, izinli yazar), "Benim günüm", Bugün/Yarın/Hafta seçici ve zil bildirimleri."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import inspect
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication

from client.dashboard_ekrani import DashboardEkrani


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    return QApplication.instance() or QApplication([])


def _zaman(gun_farki, saat):
    return (datetime.now() + timedelta(days=gun_farki)).replace(hour=saat, minute=0, second=0, microsecond=0)


# ---------------------------------------------------------------- sunucu
def test_aralik_haritasi_bugun_yarin_hafta():
    import server.sunucu as sunucu
    assert sunucu.DASHBOARD_ARALIKLARI == {"bugun": (0, 1), "yarin": (1, 2), "hafta": (0, 7)}


def test_randevu_ucu_secilen_araligi_sorguya_verir_ve_tarih_doner():
    import server.sunucu as sunucu
    conn = MagicMock()
    imlec = conn.cursor.return_value
    imlec.fetchall.return_value = [(1, "K1", "psk", "Oda 1", _zaman(1, 10), _zaman(1, 11), "PLANLANDI")]
    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        liste = sunucu.dashboard_bugunku_randevular(kullanici_id=3, aralik="yarin")
    assert imlec.execute.call_args.args[1] == (1, 2)
    assert liste[0]["tarih"] == _zaman(1, 10).strftime("%d.%m") and liste[0]["baslangic"] == "10:00"


def test_rezervasyon_ucu_hafta_gorunumunde_tarihli_saat_verir():
    import server.sunucu as sunucu
    conn = MagicMock()
    imlec = conn.cursor.return_value
    imlec.fetchall.return_value = [(1, "E-1", "EEG", "ayse", "Oda 1", _zaman(0, 10), _zaman(0, 11), 1)]
    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        liste = sunucu.dashboard_bugunku_rezervasyonlar(kullanici_id=3, aralik="hafta")
    assert imlec.execute.call_args.args[1] == (3, 7, 0)
    assert liste[0]["baslangic"] == _zaman(0, 10).strftime("%d.%m %H:%M")


def test_gecersiz_aralik_422():
    import server.sunucu as sunucu
    from fastapi.testclient import TestClient
    sunucu.app.dependency_overrides[sunucu.mevcut_kullanici_id] = lambda: 9
    try:
        with TestClient(sunucu.app) as istemci:
            assert istemci.get("/api/dashboard/bugunku-etkinlikler?aralik=yil").status_code == 422
    finally:
        sunucu.app.dependency_overrides.pop(sunucu.mevcut_kullanici_id, None)


def test_benim_gunum_yalniz_kendi_kaydini_sorgular():
    import server.sunucu as sunucu
    conn = MagicMock()
    imlec = conn.cursor.return_value
    imlec.fetchall.side_effect = [
        [(False, _zaman(0, 9), _zaman(0, 10), "K1", "Oda 1"), (True, _zaman(1, 9), _zaman(1, 10), "K2", "Oda 2")],
        [(False, _zaman(0, 13), _zaman(0, 14), "E-1", "EEG", "Oda 1")],
        [],                                                                            # izinler: hiçbiri yok → "isler" boş
    ]
    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        veri = sunucu.dashboard_benim_gunum(kullanici_id=7)
    assert veri["isler"] == []
    for cagri in imlec.execute.call_args_list[:2]:
        assert cagri.args[1] == (7,) and "p.kullanici_id = %s" in cagri.args[0]            # yalnızca çağıranın kendi kaydı
    assert [r["gun"] for r in veri["randevular"]] == ["bugun", "yarin"]
    assert veri["randevular"][0]["saat"] == "09:00 – 10:00" and veri["rezervasyonlar"][0]["cihaz"] == "E-1 - EEG"


def _isler(izinler, *sonuclar):
    import server.sunucu as sunucu
    imlec = MagicMock()
    imlec.fetchall.return_value = [(i,) for i in izinler]
    imlec.fetchone.side_effect = list(sonuclar)
    return sunucu._benim_islerim(imlec, 7), imlec


def test_isler_izni_olmayana_hicbir_sey_eklemez_ve_yalniz_izinli_konuyu_sorgular():
    isler, imlec = _isler([])
    assert isler == [] and imlec.execute.call_count == 1                              # yalnızca izin sorgusu
    isler, imlec = _isler(["ARIZA_KAYITLARI_YONET"], (3,))
    assert [i["metin"] for i in isler] == ["3 açık cihaz arızası çözüm bekliyor."] and isler[0]["hedef"] == "Arıza Kayıtları"
    assert imlec.execute.call_count == 2 and "cihaz_arizalari" in imlec.execute.call_args.args[0]


def test_isler_bekleyen_yoksa_satir_eklenmez():
    assert _isler(["ARIZA_KAYITLARI_YONET", "DANISMA_OTURUMU_YONETIM"], (0, 0), (0,))[0] == []


def test_isler_danisma_ogrencisi_acik_gorevini_gorur_yonetici_bekleyen_onayi_gorur():
    isler, _ = _isler(["DANISMA_OTURUMU_YONET"], (5400,))
    assert isler[0]["metin"].startswith("Danışma masası göreviniz devam ediyor (1 saat 30 dakika)") and isler[0]["onem"] == "uyari"
    isler, _ = _isler(["DANISMA_OTURUMU_YONET"], None)
    assert isler == []                                                               # açık görev yoksa satır yok
    isler, _ = _isler(["DANISMA_OTURUMU_YONETIM"], (2, 4))
    assert [i["metin"] for i in isler] == ["4 danışma masası oturumu onayınızı bekliyor.", "2 öğrenci şu an danışma masasında görevde."]


def test_isler_hatasi_gunumu_bozmaz():
    import server.sunucu as sunucu
    imlec = MagicMock()
    imlec.execute.side_effect = RuntimeError("sorgu hatası")
    assert sunucu._benim_islerim(imlec, 7) == []


def _gereken_yetki(fonksiyon):
    """Ana panel/duyuru ucunun gerektirdiği yetki (server/anasayfa_api.py UCLAR tablosundan): izin adı, izin tuple'ı (biri yeter) ya da None (yalnızca oturum)."""
    from server import anasayfa_api
    return next(u[4] for u in anasayfa_api.UCLAR if u[2] is fonksiyon)


def test_duyuru_okuma_herkese_acik_yazma_izinli():
    import server.sunucu as sunucu
    assert _gereken_yetki(sunucu.duyurulari_getir) is None                 # yalnızca oturum açmış olmak
    assert _gereken_yetki(sunucu.duyuru_yayinla) == "DUYURU_YONET"
    assert _gereken_yetki(sunucu.duyuru_kaldir) == "DUYURU_YONET"


def test_duyuru_yazan_adi_yalniz_yonetene_gosterilir():
    import server.sunucu as sunucu
    conn = MagicMock()
    imlec = conn.cursor.return_value
    imlec.fetchall.return_value = [(1, "Bakım", "Yarın bakım var", datetime(2026, 1, 2, 9, 30), None, "mudur1", True, 0, False),
                                   (2, "Diğer", "Metin", datetime(2026, 1, 1, 9, 30), date(2026, 2, 1), "mudur1", False, 1, True)]
    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        liste = sunucu.duyurulari_getir(kullanici_id=4)
    assert liste[0]["yazan"] is None and liste[0]["yonetebilir"] is False and liste[0]["yeni"] is True and liste[0]["okundu"] is False
    assert liste[1]["okundu"] is True
    assert liste[1]["yazan"] == "mudur1" and liste[1]["yonetebilir"] is True and liste[1]["son_gecerlilik"] == "01.02.2026"


def test_duyuru_modeli_dogrulama():
    from pydantic import ValidationError
    from server.modeller import DuyuruModeli
    assert DuyuruModeli(baslik="  Bakım ", metin=" Yarın ").baslik == "Bakım"
    for kotu in ({"baslik": " ", "metin": "x"}, {"baslik": "a", "metin": ""}, {"baslik": "a" * 121, "metin": "x"},
                 {"baslik": "a", "metin": "x" * 1001}, {"baslik": "a", "metin": "x", "son_gecerlilik_tarihi": date.today() - timedelta(days=1)},
                 {"baslik": "a", "metin": "x", "bilinmeyen": 1}):
        with pytest.raises(ValidationError):
            DuyuruModeli(**kotu)


def test_duyuru_yayinla_ve_kaldir_denetim_kaydi_yazar():
    import server.sunucu as sunucu
    from server.modeller import DuyuruModeli
    conn = MagicMock()
    imlec = conn.cursor.return_value
    imlec.fetchone.side_effect = [(11,), ("Bakım",)]
    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        assert sunucu.duyuru_yayinla(DuyuruModeli(baslik="Bakım", metin="x"), kullanici_id=2)["duyuru_id"] == 11
        sunucu.duyuru_kaldir(11, kullanici_id=2)
    sorgular = " ".join(str(c.args[0]) for c in imlec.execute.call_args_list)
    assert "INSERT INTO duyurular" in sorgular and "DELETE FROM duyurular" in sorgular and sorgular.count("denetim_kayitlari") == 2


# ---------------------------------------------------------------- istemci
DUYURULAR = [{"duyuru_id": 5, "baslik": "Yarın bakım", "metin": "Sistem 18:00'de kapanır.", "tarih": "01.01.2026 09:00",
              "son_gecerlilik": None, "yazan": "mudur1", "yeni": True, "yonetebilir": True, "okundu": False}]
GUNUM = {"randevular": [{"gun": "bugun", "saat": "09:00 – 10:00", "danisan_kod_id": "K1", "oda": "Oda 1"},
                        {"gun": "yarin", "saat": "11:00 – 12:00", "danisan_kod_id": "K2", "oda": "Oda 1"}],
         "rezervasyonlar": [{"gun": "bugun", "saat": "13:00 – 14:00", "cihaz": "E-1 - EEG", "oda": "Oda 1"}]}


def _panel(duyurular=DUYURULAR, gunum=GUNUM, cagrilar=None, **kw):
    def getir(self, yol):
        if cagrilar is not None:
            cagrilar.append(yol)
        if yol == "/api/duyurular":
            return duyurular
        if yol == "/api/dashboard/benim-gunum":
            return gunum
        return {"/api/dashboard/ozet": {"acik_ariza_sayisi": 0}}.get(yol.split("?")[0], [])
    with patch.object(DashboardEkrani, "_getir", getir):
        p = DashboardEkrani("http://x", "T", **kw)
    p.zamanlayici.stop()
    return p


def _metinler(kutu):
    from PySide6.QtWidgets import QLabel, QPushButton
    return [w.text() for w in kutu.findChildren(QLabel) + kutu.findChildren(QPushButton)]


def test_herkes_duyuruyu_gorur_yonet_dugmeleri_yalniz_izinlide():
    p = _panel(cihaz_ozeti=False)
    assert not p.panel_duyuru.isHidden()
    metin = " | ".join(_metinler(p.panel_duyuru))
    assert "Yarın bakım" in metin and "Sistem 18:00" in metin
    assert "＋ Yeni duyuru" not in metin and "Kaldır" not in metin
    p.close()
    p = _panel(cihaz_ozeti=False, duyuru_yonetebilir=True)
    metin = " | ".join(_metinler(p.panel_duyuru))
    assert "＋ Yeni duyuru" in metin and "Kaldır" in metin
    p.close()


def test_duyuru_yoksa_kutu_yine_gorunur_aciklama_yazar_yonetende_yeni_duyuru_dugmesi_kalir():
    p = _panel(duyurular=[], cihaz_ozeti=False)
    assert not p.panel_duyuru.isHidden() and "Şu an yayında duyuru yok." in _metinler(p.panel_duyuru)
    assert "＋ Yeni duyuru" not in _metinler(p.panel_duyuru)
    p.close()
    p = _panel(duyurular=[], cihaz_ozeti=False, duyuru_yonetebilir=True)
    assert not p.panel_duyuru.isHidden() and "＋ Yeni duyuru" in _metinler(p.panel_duyuru)
    p.close()


def test_benim_gunum_bugun_ve_yarini_listeler_kaydi_yoksa_da_kutu_gorunur():
    p = _panel(cihaz_ozeti=False)
    assert not p.panel_benim_gunum.isHidden()
    metin = " | ".join(_metinler(p.panel_benim_gunum))
    assert "09:00 – 10:00" in metin and "11:00 – 12:00" in metin and "E-1 - EEG" in metin and "Bugün" in metin and "Yarın" in metin
    p.close()
    p = _panel(gunum={"randevular": [], "rezervasyonlar": []}, cihaz_ozeti=False)
    assert not p.panel_benim_gunum.isHidden()                                       # kaydı olmasa da görünür
    assert "Bugün ve yarın için size ait randevu ya da cihaz rezervasyonu yok." in _metinler(p.panel_benim_gunum)
    assert "Benim Günüm" in _metinler(p.panel_benim_gunum)
    p.close()
    p = _panel(gunum=None, duyurular=None, cihaz_ozeti=False)                       # sunucu yanıtı bozuksa ekran çökmez; "boş" değil "yüklenemedi" yazar
    assert not p.panel_benim_gunum.isHidden() and not p.panel_duyuru.isHidden()
    assert "Günlük bilgileriniz yüklenemedi." in _metinler(p.panel_benim_gunum)
    assert "Duyurular yüklenemedi." in _metinler(p.panel_duyuru)
    p.close()


def test_gun_secici_yarin_ve_hafta_icin_aralik_ister_bugun_karti_bugunu_sayar():
    cagrilar = []
    p = _panel(cagrilar=cagrilar, cihaz_ozeti=True, etkinlik_paneli=True)
    assert "/api/dashboard/bugunku-randevular" in cagrilar and not any("aralik=" in c for c in cagrilar)      # varsayılan: eski yol
    cagrilar.clear()
    with patch.object(DashboardEkrani, "_getir", lambda self, yol: cagrilar.append(yol) or ({} if yol.endswith("/ozet") else [])):
        p.aralik_sec("yarin")
    assert "/api/dashboard/bugunku-randevular?aralik=yarin" in cagrilar
    assert "/api/dashboard/bugunku-randevular" in cagrilar                            # özet kartı bugünü saymaya devam eder
    assert "/api/dashboard/bugunku-rezervasyonlar?aralik=yarin" in cagrilar and "/api/dashboard/bugunku-etkinlikler?aralik=yarin" in cagrilar
    assert p.lbl_randevu_bos.text() == "Yarın için kayıtlı randevu bulunmuyor."
    assert p.aralik_dugmeleri["yarin"].isChecked() and not p.aralik_dugmeleri["bugun"].isChecked()
    with patch.object(DashboardEkrani, "_getir", lambda self, yol: {} if yol.endswith("/ozet") else []):
        p.aralik_sec("hafta")
    assert p.lbl_etkinlik_bos.text() == "Önümüzdeki 7 gün için oda etkinliği bulunmuyor."
    p.aralik_sec("gecersiz")
    assert p.aralik == "hafta"
    p.close()


def test_hafta_gorunumunde_saatin_onune_tarih_eklenir():
    p = _panel(cihaz_ozeti=False)
    p.aralik = "hafta"
    assert p._saat_metni({"baslangic": "09:00", "bitis": "10:00", "tarih": "26.11"}) == "26.11  09:00 – 10:00"
    assert p._saat_metni({"baslangic": "26.11 09:00", "bitis": "26.11 10:00", "tarih": "26.11"}) == "26.11 09:00 – 26.11 10:00"
    p.aralik = "bugun"
    assert p._saat_metni({"baslangic": "09:00", "bitis": "10:00", "tarih": "26.11"}) == "09:00 – 10:00"
    p.close()


# ---------------------------------------------------------------- izin ve zil
def test_duyuru_yonetme_izni_rol_maskesi_ve_ana_pencereye_baglanti():
    import client.main_window as mw
    assert mw.IZIN_KODLARI["Duyuruları yönetme"] == ("DUYURU_YONET",)
    assert [r for r in mw.ROLLER if mw.izin_var(r, "Duyuruları yönetme")] == ["psikolog", "memur", "mudur", "asistan", "admin"]      # Danışma Öğrencisi (ogrenci) dışında herkes
    assert "duyuru_yonetebilir=izin_var(rol," in inspect.getsource(mw.AnaPencere.sayfa_dashboard)


def test_izin_sunucudan_gelince_menu_ve_duyuru_dugmesi_dinamik():
    import client.main_window as mw
    mw.yetkileri_ayarla("psikolog", ["TAKVIM_GORUNTULE"])
    assert not mw.izin_var("psikolog", "Duyuruları yönetme")
    mw.yetkileri_ayarla("psikolog", ["DUYURU_YONET"])
    assert mw.izin_var("psikolog", "Duyuruları yönetme")                              # admin izni verirse kodda değişiklik gerekmez
    mw._SUNUCU_YETKILERI.pop("psikolog", None)


def test_zil_kisisel_ve_duyuru_bildirimlerini_her_rol_icin_kaynakta_toplar():
    import client.main_window as mw
    kaynak = inspect.getsource(mw.AnaPencere._bildirimleri_yenile)
    assert 'getir("/api/dashboard/benim-gunum")' in kaynak and 'getir("/api/duyurular")' in kaynak
    ilk_if = kaynak.index('getir("/api/dashboard/benim-gunum")')
    assert 'if "Cihaz Envanteri" in self.nav_btnler' not in kaynak[ilk_if - 200:ilk_if]          # izne/sayfaya bağlı bir if içinde değil


def test_bildirim_paneli_yeni_gruplarin_basligini_gosterir():
    from client.bildirim_paneli import BildirimPaneli
    panel = BildirimPaneli(bildirimler=[("Günlük", "📅 Randevunuz: bugün 2", "Ana Kontrol Paneli"), ("Duyurular", "📢 Bakım", "Ana Kontrol Paneli")],
                           toplam=2, hata=False, sayfa_ac=lambda _: None)
    from PySide6.QtWidgets import QLabel
    metin = " ".join(l.text() for l in panel.findChildren(QLabel))
    assert "BENİM GÜNÜM" in metin and "DUYURULAR" in metin and "DANIŞMA MASASI ONAYLARI" not in metin
    panel.close()


def test_migrasyon_duyuru_tablosu_ve_izni():
    from pathlib import Path
    kaynak = Path("database/migrations/versions/c9d2e4f6a801_duyurular_ve_duyuru_izni.py").read_text(encoding="utf-8")
    assert 'down_revision = "a7c3e5b9d014"' in kaynak and "CREATE TABLE IF NOT EXISTS duyurular" in kaynak
    assert "'ADMIN', 'MUDUR', 'MEMUR'" in kaynak and "DUYURU_YONET" in kaynak


def test_ana_panel_baglantilarinda_lambda_yok_kapanista_cokme_yapar():
    """Düğmeye `connect(lambda ...: self...)` bağlamak panelle referans döngüsü kurar; süreç kapanırken Qt nesneleri yanlış sırada yok edilip
    'Segmentation fault' verir (CI'da dosya tek başına çalışınca yakalandı). Tek bir yuva + sender().property() kullanılır."""
    import client.dashboard_ekrani as d
    import client.duyuru_diyaloglari as dd
    for modul in (d, dd):
        assert "connect(lambda" not in inspect.getsource(modul)


def test_ana_panel_kaynaginda_cizgi_ikon_kuralini_bozan_emoji_yok():
    """Acceptance testi (test_ana_sayfa_ikon_ve_hizli_erisim) ana panel kaynağında bu emojileri yasaklar; Benim Günüm satırları düz metin etiketi kullanır."""
    import client.dashboard_ekrani as d
    kaynak = inspect.getsource(d)
    for emoji in ("📅", "📌", "🛠️", "📏", "🔬"):
        assert emoji not in kaynak


def test_bekleyen_islerim_satirlari_cizilir_yalniz_isi_olanda_gorunur():
    gunum = dict(GUNUM, isler=[{"metin": "4 danışma masası oturumu onayınızı bekliyor.", "hedef": "Danışma Masası Yönetimi", "onem": "uyari"}])
    p = _panel(gunum=gunum, cihaz_ozeti=False)
    metin = _metinler(p.panel_benim_gunum)
    assert "Bekleyen işlerim" in metin and "4 danışma masası oturumu onayınızı bekliyor.   →  Danışma Masası Yönetimi" in metin
    p.close()
    p = _panel(gunum=GUNUM, cihaz_ozeti=False)                                       # eski sunucu / iş yok: başlık da yok
    assert "Bekleyen işlerim" not in _metinler(p.panel_benim_gunum)
    p.close()
    p = _panel(gunum={"randevular": [], "rezervasyonlar": [], "isler": gunum["isler"]}, cihaz_ozeti=False)
    assert "Bekleyen işlerim" in _metinler(p.panel_benim_gunum) and "Bugün ve yarın için size ait randevu ya da cihaz rezervasyonu yok." not in _metinler(p.panel_benim_gunum)
    p.close()


# ---------------------------------------------------------------- başlık ikonları (emoji yok, kartlardaki gibi renkli kutulu çizgi ikon)
def _ikonlu_baslik(kutu):
    from PySide6.QtWidgets import QLabel
    return [e for e in kutu.findChildren(QLabel) if e.objectName() == "panelBaslikIkonu"]


@pytest.mark.parametrize("panel_adi, baslik", [("panel_duyuru", "Duyurular"), ("panel_benim_gunum", "Benim Günüm")])
def test_panel_basliklari_emoji_yerine_cizgi_ikon_kullanir(panel_adi, baslik):
    p = _panel(cihaz_ozeti=False)
    kutu = getattr(p, panel_adi)
    ikonlar = _ikonlu_baslik(kutu)
    assert len(ikonlar) == 1 and not ikonlar[0].pixmap().isNull() and ikonlar[0].width() == ikonlar[0].height() == 30
    basliklar = [m for m in _metinler(kutu) if m.startswith(baslik)]
    assert basliklar and all(ord(c) < 0x2000 or c in "ğüşıöçĞÜŞİÖÇ" for b in basliklar for c in b)           # başlık metninde emoji yok
    assert "📢" not in " ".join(_metinler(kutu)) and "🙋" not in " ".join(_metinler(kutu))
    p.close()


def test_duyuru_basligi_okunmamis_sayisini_ikonla_birlikte_gosterir():
    p = _panel(cihaz_ozeti=False)
    metin = " | ".join(_metinler(p.panel_duyuru))
    assert "Duyurular  (" in metin and "yeni)" in metin and len(_ikonlu_baslik(p.panel_duyuru)) == 1
    p.close()


def test_baslik_ikonlari_farkli_ve_projenin_ortak_ikon_kayit_defterinden():
    from client.tkys_sidebar_refined import PATHS
    assert "megaphone" in PATHS and "user" in PATHS                       # ikon adları ortak kayıt defterinde tanımlı (eksikse düz dosya ikonu çıkar)
    p = _panel(cihaz_ozeti=False)
    a = _ikonlu_baslik(p.panel_duyuru)[0].pixmap().toImage()
    b = _ikonlu_baslik(p.panel_benim_gunum)[0].pixmap().toImage()
    assert a != b                                                          # iki panelin ikonu/rengi farklı
    p.close()


def test_okunmamis_duyuru_emoji_yerine_yeni_rozeti_tasir_okunmus_tasimaz():
    from PySide6.QtWidgets import QLabel
    p = _panel(cihaz_ozeti=False)
    rozetler = [e for e in p.panel_duyuru.findChildren(QLabel) if e.objectName() == "yeniRozeti"]
    assert len(rozetler) == 1 and rozetler[0].text() == "Yeni"                       # 1 okunmamış duyuru, 1 rozet
    assert "🆕" not in " ".join(_metinler(p.panel_duyuru))
    okunmus = _panel(duyurular=[dict(DUYURULAR[0], okundu=True, yeni=False)], cihaz_ozeti=False)
    okunmus._okunanlar_acik = True
    okunmus._duyurulari_ciz()
    assert [e for e in okunmus.panel_duyuru.findChildren(QLabel) if e.objectName() == "yeniRozeti"] == []
    p.close(); okunmus.close()
