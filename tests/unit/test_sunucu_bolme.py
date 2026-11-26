"""server/sunucu.py'nin parçalanması: ayrılan uç modülleri aynı yetkiyle ve aynı adlarla çalışır; sunucuya geri bağımlı olmaz."""
import ast
import inspect
import re
from pathlib import Path

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient

import server.sunucu as sunucu
from server import (
    anasayfa_api, audit_api, cihaz_raporlari_api, cihaz_uygunluk_api, danisma_raporlari_api, faaliyet_birimleri_api,
    faaliyet_kayitlari_api, faaliyet_turleri_api, ortak_sabitler, ortak_yardimcilar, puan_raporu_api, randevu_oda_raporlari_api,
    surum_api, vt_ayarlari, yonetim_raporlari_api,
)
from server.yetki_baglama import yetkiyle_bagla

KOK = Path(__file__).resolve().parents[2]

YONETIM = "YONETIM_RAPORLARI_GORUNTULE"
FAALIYET = "FAALIYET_KAYITLARI_DUZENLE"
BIRIM = "FAALIYET_BIRIMI_DUZENLE"
# Ayrılan modüller: (modül, [(yöntem, uç yolu, gereken yetki), ...]). Yetki eşlemesi güvenlik açısından AÇIKÇA yazılıdır:
# taşıma sırasında hiçbir ucun yetkisi değişmemelidir. Gereken yetki: "IZIN" (izin_kontrol), ("A", "B") (izin_kontrol_biri: biri yeter),
# None (yalnızca oturum açmış olmak: kimlik bağımlılığı).
AYRILANLAR = [
    (audit_api, [("GET", "/api/audit-kayitlari", "AUDIT_KAYITLARI_INCELE")]),
    (cihaz_raporlari_api, [("GET", "/api/cihaz-raporlari", "CIHAZ_ENVANTER_YONET")]),
    (danisma_raporlari_api, [("GET", "/api/danisma/raporlar", "DANISMA_OTURUMU_GORUNTULE")]),
    (yonetim_raporlari_api, [
        ("GET", "/api/yonetim-raporlari/randevu-ozet", YONETIM),
        ("GET", "/api/yonetim-raporlari/cihaz-ozet", YONETIM),
        ("GET", "/api/yonetim-raporlari/ogrenci-ozet", YONETIM),
        ("GET", "/api/yonetim-raporlari/proje-etkinlik-ozet", YONETIM),
        ("GET", "/api/yonetim-raporlari/kullanim-ozet", YONETIM),
        ("GET", "/api/cihaz-rezervasyon-raporu", "CIHAZ_ENVANTER_YONET"),
        ("GET", "/api/oda-kullanim-raporu", YONETIM),
        ("GET", "/api/yetki-raporu", "AUDIT_KAYITLARI_INCELE"),
        ("GET", "/api/ogrenci-raporu", "FAALIYET_KAYITLARI_DUZENLE"),
        ("GET", "/api/faaliyet-raporu", "FAALIYET_KAYITLARI_DUZENLE"),
        ("GET", "/api/bakim-plani-raporu", "CIHAZ_ENVANTER_YONET"),
        ("GET", "/api/yonetim-raporlari/bugun-merkezde", YONETIM),
        ("GET", "/api/yonetim-raporlari/gunluk-detay", YONETIM),
    ]),
    (cihaz_uygunluk_api, [("GET", "/api/cihaz-uygunluk", "CIHAZ_UYGUNLUK_GORUNTULE")]),
    (randevu_oda_raporlari_api, [
        ("GET", "/api/randevu-raporu/secenekler", "TAKVIM_GORUNTULE"),
        ("GET", "/api/oda-kullanimi", "ODA_DURUMU_GORUNTULE"),
        ("GET", "/api/randevu-raporu", "TAKVIM_GORUNTULE"),
    ]),
    (puan_raporu_api, [("GET", "/api/puan-raporu", "FAALIYET_KAYITLARI_DUZENLE")]),
    (surum_api, [("GET", "/api/surum", None), ("GET", "/api/sistem-durumu", "AUDIT_KAYITLARI_INCELE")]),
    (faaliyet_turleri_api, [
        ("GET", "/api/faaliyetler", FAALIYET),
        ("POST", "/api/faaliyetler", FAALIYET),
        ("PUT", "/api/faaliyetler/{faaliyet_id}", FAALIYET),
    ]),
    (faaliyet_birimleri_api, [
        ("GET", "/api/faaliyet-birimleri", FAALIYET),
        ("POST", "/api/faaliyet-birimleri", BIRIM),
        ("PUT", "/api/faaliyet-birimleri/{birim_id}", BIRIM),
        ("DELETE", "/api/faaliyet-birimleri/{birim_id}", BIRIM),
    ]),
    (faaliyet_kayitlari_api, [
        ("POST", "/api/faaliyet-kayitlari", FAALIYET),
        ("GET", "/api/faaliyet-kayitlari", FAALIYET),
        ("PUT", "/api/faaliyet-kayitlari/{takip_id}", FAALIYET),
        ("DELETE", "/api/faaliyet-kayitlari/{takip_id}", FAALIYET),
    ]),
    (anasayfa_api, [
        ("GET", "/api/dashboard/ozet", "CIHAZ_ENVANTER_YONET"),
        ("GET", "/api/dashboard/bugunku-randevular", "TAKVIM_GORUNTULE"),
        ("GET", "/api/dashboard/bugunku-rezervasyonlar", ("CIHAZ_ENVANTER_YONET", "CIHAZ_UYGUNLUK_GORUNTULE", "CIHAZ_REZERVASYON")),
        ("GET", "/api/dashboard/bugunku-etkinlikler", None),
        ("GET", "/api/dashboard/benim-gunum", None),
        ("GET", "/api/duyurular", None),
        ("POST", "/api/duyurular/okundu", None),
        ("POST", "/api/duyurular/{duyuru_id}/okundu", None),
        ("DELETE", "/api/duyurular/{duyuru_id}/okundu", None),
        ("POST", "/api/duyurular", "DUYURU_YONET"),
        ("DELETE", "/api/duyurular/{duyuru_id}", "DUYURU_YONET"),
        ("GET", "/api/dashboard/yaklasan-islemler", ("CIHAZ_ENVANTER_YONET", "BAKIM_KAYITLARI_GORUNTULE", "BAKIM_KAYITLARI_YONET",
                                                       "KALIBRASYON_KAYITLARI_GORUNTULE", "KALIBRASYON_KAYITLARI_YONET")),
    ]),
]
TUM_UCLAR = [(m, yontem, yol, yetki) for m, ucler in AYRILANLAR for yontem, yol, yetki in ucler]


def _ice_aktarilan_modul_adlari(modul):
    agac = ast.parse(Path(modul.__file__).read_text(encoding="utf-8"))
    adlar = set()
    for dugum in ast.walk(agac):
        if isinstance(dugum, ast.Import):
            adlar.update(a.name for a in dugum.names)
        elif isinstance(dugum, ast.ImportFrom):
            adlar.add(dugum.module or "")
            adlar.update(f"{dugum.module}.{a.name}" for a in dugum.names)
    return adlar


def _router_bagimliliklari(modul, kayit):
    """Yönlendirici üreticisinin istediği bağımlılık üreticilerini sahte olarak verir: `izin_kontrol`, varsa `izin_kontrol_biri` ve
    `mevcut_kullanici_id`. Sahteler hangi yetkinin istendiğini `kayit` listesine yazar."""
    def izin_kontrol(ad):
        kayit.append(ad)
        return lambda: 1

    def izin_kontrol_biri(*adlar):
        kayit.append(tuple(adlar))
        return lambda: 1

    sahteler = {"izin_kontrol": izin_kontrol, "izin_kontrol_biri": izin_kontrol_biri, "mevcut_kullanici_id": lambda: 1}
    return [sahteler[ad] for ad in inspect.signature(modul.router_olustur).parameters]


@pytest.mark.parametrize("modul", [m for m, _ in AYRILANLAR] + [ortak_sabitler, ortak_yardimcilar, vt_ayarlari])
def test_ayrilan_modul_sunucuyu_ice_aktarmaz_dongusel_bagimlilik_olmaz(modul):
    assert not {a for a in _ice_aktarilan_modul_adlari(modul) if a == "server.sunucu" or a.startswith("server.sunucu.")}


@pytest.mark.parametrize("modul, yontem, yol, yetki", TUM_UCLAR)
def test_uc_tam_bir_kez_kayitli_ve_kimliksiz_istek_reddedilir(modul, yontem, yol, yetki):
    sema = sunucu.app.openapi()["paths"]
    assert yol in sema and yontem.lower() in sema[yol]
    assert TestClient(sunucu.app).request(yontem, re.sub(r"\{[^}]+\}", "1", yol)).status_code == 401   # yetki bağımlılığı bağlı


@pytest.mark.parametrize("modul, ucler", AYRILANLAR)
def test_router_her_ucun_yetkisini_dogru_ve_sirayla_ister_yollar_ve_yontemler_ayni(modul, ucler):
    istenen = []
    yonlendirici = modul.router_olustur(*_router_bagimliliklari(modul, istenen))
    assert istenen == [yetki for _, _, yetki in ucler if yetki]
    kayitli = [(sorted(r.methods)[0], getattr(r, "path", None)) for r in yonlendirici.routes]
    assert kayitli == [(yontem, yol) for yontem, yol, _ in ucler]


def test_sunucudaki_geriye_donuk_adlar_ayrilan_nesnelerle_aynidir():
    assert sunucu.audit_kayitlarini_getir is audit_api.audit_kayitlarini_getir
    assert sunucu.cihaz_raporlari is cihaz_raporlari_api.cihaz_raporlari
    assert sunucu.danisma_raporlari is danisma_raporlari_api.danisma_raporlari
    for ad in ("_yonetim_onceki_donem", "_rapor_donemi_dogrula", "yonetim_randevu_ozet", "yonetim_cihaz_ozet", "yonetim_ogrenci_ozet",
               "yonetim_proje_etkinlik_ozet", "yonetim_kullanim_ozet", "cihaz_rezervasyon_raporu", "oda_kullanim_raporu",
               "yetki_raporu_getir", "ogrenci_raporu_getir", "faaliyet_raporu_getir", "bakim_plani_raporu_getir",
               "yonetim_bugun_merkezde", "yonetim_gunluk_detay"):
        assert getattr(sunucu, ad) is getattr(yonetim_raporlari_api, ad), ad
    for modul, adlar in ((cihaz_uygunluk_api, ("UYGUNLUK_EN_FAZLA_GUN", "UYGUNLUK_ACIK_UCLU_DURUMLAR", "_uygunluk_uyari", "cihaz_uygunluk_hazirla", "cihaz_uygunluk_getir")),
                         (randevu_oda_raporlari_api, ("randevu_raporu_secenekleri", "oda_kullanimi", "randevu_raporu")),
                         (puan_raporu_api, ("PUAN_RAPORU_DURUMLARI", "puan_raporu")),
                         (surum_api, ("_sistem_durumu", "_SURUM", "_UYGULAMA_ADI", "surum_bilgisi", "sistem_durumu_getir")),
                         (faaliyet_turleri_api, ("FAALIYET_PUANI_EN_FAZLA", "FaaliyetTuruEkleModeli", "FAALIYET_ADI_KAYITLI_MESAJI", "_faaliyet_adi_kayitli_mi",
                                                 "FaaliyetTuruDuzenleModeli", "faaliyetleri_getir", "faaliyet_turu_ekle", "faaliyet_turu_duzenle")),
                         (faaliyet_birimleri_api, ("BIRIM_ADI_KAYITLI_MESAJI", "faaliyet_birimleri_getir", "faaliyet_birimi_ekle",
                                                    "faaliyet_birimi_guncelle", "faaliyet_birimi_sil")),
                         (faaliyet_kayitlari_api, ("faaliyet_kaydi_ekle", "faaliyet_kayitlarini_getir", "faaliyet_kaydi_guncelle", "faaliyet_kaydi_sil")),
                         (anasayfa_api, ("DASHBOARD_ARALIKLARI", "ARALIK_SORGU_DESENI", "_tarih_kisa", "BUGUNKU_ETKINLIK_UST_SINIR", "ISLER_IZINLERI",
                                         "_benim_islerim", "DUYURU_UST_SINIR", "DUYURU_YENI_GUN", "YAKLASAN_ISLEM_UST_SINIR", "dashboard_ozet_getir",
                                         "dashboard_bugunku_randevular", "dashboard_bugunku_rezervasyonlar", "dashboard_bugunku_etkinlikler",
                                         "dashboard_benim_gunum", "duyurulari_getir", "duyurulari_okundu_isaretle", "duyuruyu_okundu_isaretle",
                                         "duyuruyu_tekrar_goster", "duyuru_yayinla", "duyuru_kaldir", "yaklasan_islemler_getir"))):
        for ad in adlar:
            assert getattr(sunucu, ad) is getattr(modul, ad), ad
    assert sunucu.psikolog_rolu_mu is ortak_yardimcilar.psikolog_rolu_mu
    assert sunucu.plan_kalibrasyon_mu is ortak_yardimcilar.plan_kalibrasyon_mu
    assert sunucu.VT_AYARLARI is vt_ayarlari.VT_AYARLARI
    assert sunucu.ETKIN_CIHAZ_DURUMU_SQL is ortak_sabitler.ETKIN_CIHAZ_DURUMU_SQL
    assert sunucu.OGRENCI_TUR_ETIKETLERI is ortak_sabitler.OGRENCI_TUR_ETIKETLERI


def test_ayrilan_kod_sunucu_dosyasinda_yinelenmez():
    kaynak = (KOK / "server" / "sunucu.py").read_text(encoding="utf-8")
    for modul, _ in AYRILANLAR:
        for ad, deger in vars(modul).items():
            if inspect.isfunction(deger) and deger.__module__ == modul.__name__ and ad != "router_olustur":
                assert f"def {ad}(" not in kaynak, ad
    for _, ucler in AYRILANLAR:
        for yontem, yol, _ in ucler:
            assert f'@app.{yontem.lower()}("{yol}"' not in kaynak and f"@app.{yontem.lower()}('{yol}'" not in kaynak, (yontem, yol)
    assert "ETKIN_CIHAZ_DURUMU_SQL = " not in kaynak and "OGRENCI_TUR_ETIKETLERI = " not in kaynak
    assert "def psikolog_rolu_mu(" not in kaynak and "def plan_kalibrasyon_mu(" not in kaynak
    assert "PUAN_RAPORU_DURUMLARI = " not in kaynak and "UYGUNLUK_EN_FAZLA_GUN = " not in kaynak and "DUYURU_UST_SINIR = " not in kaynak


def _uclar_tablosu(modul):
    """(yöntem, fonksiyon, yetki parametresi) listesi; modülün UCLAR tablosundan, yoksa `kullanici_id` parametresi olan fonksiyonlardan."""
    if not hasattr(modul, "UCLAR"):
        return [("GET", d, "kullanici_id") for _, d in vars(modul).items()
                if inspect.isfunction(d) and d.__module__ == modul.__name__ and "kullanici_id" in inspect.signature(d).parameters]
    sonuc = []
    for u in modul.UCLAR:
        if len(u) == 6:        # (yöntem, yol, fonksiyon, parametre, yetki, ek)
            sonuc.append((u[0], u[2], u[3]))
        elif len(u) == 4:      # (yol, fonksiyon, parametre, izin)
            sonuc.append(("GET", u[1], u[2]))
        else:                  # (yol, fonksiyon, izin)
            sonuc.append(("GET", u[1], "kullanici_id"))
    return sonuc


def test_ayrilan_fonksiyonlar_dogrudan_cagrilabilir_yetki_parametresi_acik_kalir():
    for modul, ucler in AYRILANLAR:
        yonlendirici = modul.router_olustur(*_router_bagimliliklari(modul, []))
        fonksiyonlar = _uclar_tablosu(modul)
        assert len(fonksiyonlar) == len(ucler) == len(yonlendirici.routes), modul.__name__
        for r, (_, fonksiyon, parametre) in zip(yonlendirici.routes, fonksiyonlar):
            assert parametre in inspect.signature(r.endpoint).parameters          # kayıtlı uç yetki parametresini taşır
            assert inspect.signature(fonksiyon).parameters[parametre].default is None, fonksiyon.__name__   # ham fonksiyonda Depends yok


def test_olusturma_uclari_201_doner_diger_uclar_200():
    """Yol ayarları (status_code) taşımada korunur: oluşturan uçlar 201, diğerleri 200."""
    sema = sunucu.app.openapi()["paths"]
    for yol in ("/api/duyurular", "/api/faaliyetler"):
        assert "201" in sema[yol]["post"]["responses"] and "200" not in sema[yol]["post"]["responses"], yol
    for yontem, yol in (("get", "/api/duyurular"), ("get", "/api/faaliyetler"), ("post", "/api/faaliyet-birimleri"),
                        ("post", "/api/faaliyet-kayitlari"), ("put", "/api/faaliyetler/{faaliyet_id}")):
        assert "200" in sema[yol][yontem]["responses"], (yontem, yol)


# --------------------------------------------------------------------------- yetkiyle_bagla
def test_yetkiyle_bagla_varsayilani_bagimliliga_cevirir_orijinali_degistirmez():
    def ornek(a: int, kullanici_id: int | None = None):
        return a, kullanici_id

    def bagimlilik():
        return 5

    sarilmis = yetkiyle_bagla(ornek, "kullanici_id", bagimlilik)
    imza = inspect.signature(sarilmis)
    assert isinstance(imza.parameters["kullanici_id"].default, type(Depends(bagimlilik)))
    assert imza.parameters["kullanici_id"].default.dependency is bagimlilik
    assert sarilmis.__name__ == "ornek" and ornek(1, 2) == (1, 2)
    assert inspect.signature(ornek).parameters["kullanici_id"].default is None


def test_yetkiyle_bagla_olmayan_parametre_icin_hata_verir():
    with pytest.raises(ValueError):
        yetkiyle_bagla(lambda: None, "kullanici_id", lambda: 1)


def test_yetkiyle_bagla_ile_baglanan_bagimlilik_istekte_cozulur():
    from fastapi import APIRouter, FastAPI

    def uc(kullanici_id: int | None = None):
        return {"kimlik": kullanici_id}

    yonlendirici = APIRouter()
    yonlendirici.add_api_route("/dene", yetkiyle_bagla(uc, "kullanici_id", lambda: 42), methods=["GET"])
    uygulama = FastAPI()
    uygulama.include_router(yonlendirici)
    assert TestClient(uygulama).get("/dene").json() == {"kimlik": 42}
