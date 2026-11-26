"""server/sunucu.py'nin parçalanması: ayrılan uç modülleri aynı yetkiyle ve aynı adlarla çalışır; sunucuya geri bağımlı olmaz."""
import ast
import inspect
from pathlib import Path

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient

import server.sunucu as sunucu
from server import (
    audit_api, cihaz_raporlari_api, cihaz_uygunluk_api, danisma_raporlari_api, ortak_sabitler, ortak_yardimcilar, puan_raporu_api,
    randevu_oda_raporlari_api, surum_api, vt_ayarlari, yonetim_raporlari_api,
)
from server.yetki_baglama import yetkiyle_bagla

KOK = Path(__file__).resolve().parents[2]

YONETIM = "YONETIM_RAPORLARI_GORUNTULE"
# Ayrılan modüller: (modül, [(uç yolu, gereken izin), ...]). Yetki eşlemesi güvenlik açısından AÇIKÇA yazılıdır:
# taşıma sırasında hiçbir ucun izni değişmemelidir. İzin None = yalnızca oturum açmış olmak (kimlik bağımlılığı).
AYRILANLAR = [
    (cihaz_uygunluk_api, [("/api/cihaz-uygunluk", "CIHAZ_UYGUNLUK_GORUNTULE")]),
    (randevu_oda_raporlari_api, [
        ("/api/randevu-raporu/secenekler", "TAKVIM_GORUNTULE"),
        ("/api/oda-kullanimi", "ODA_DURUMU_GORUNTULE"),
        ("/api/randevu-raporu", "TAKVIM_GORUNTULE"),
    ]),
    (puan_raporu_api, [("/api/puan-raporu", "FAALIYET_KAYITLARI_DUZENLE")]),
    (surum_api, [("/api/surum", None), ("/api/sistem-durumu", "AUDIT_KAYITLARI_INCELE")]),
    (audit_api, [("/api/audit-kayitlari", "AUDIT_KAYITLARI_INCELE")]),
    (cihaz_raporlari_api, [("/api/cihaz-raporlari", "CIHAZ_ENVANTER_YONET")]),
    (danisma_raporlari_api, [("/api/danisma/raporlar", "DANISMA_OTURUMU_GORUNTULE")]),
    (yonetim_raporlari_api, [
        ("/api/yonetim-raporlari/randevu-ozet", YONETIM),
        ("/api/yonetim-raporlari/cihaz-ozet", YONETIM),
        ("/api/yonetim-raporlari/ogrenci-ozet", YONETIM),
        ("/api/yonetim-raporlari/proje-etkinlik-ozet", YONETIM),
        ("/api/yonetim-raporlari/kullanim-ozet", YONETIM),
        ("/api/cihaz-rezervasyon-raporu", "CIHAZ_ENVANTER_YONET"),
        ("/api/oda-kullanim-raporu", YONETIM),
        ("/api/yetki-raporu", "AUDIT_KAYITLARI_INCELE"),
        ("/api/ogrenci-raporu", "FAALIYET_KAYITLARI_DUZENLE"),
        ("/api/faaliyet-raporu", "FAALIYET_KAYITLARI_DUZENLE"),
        ("/api/bakim-plani-raporu", "CIHAZ_ENVANTER_YONET"),
        ("/api/yonetim-raporlari/bugun-merkezde", YONETIM),
        ("/api/yonetim-raporlari/gunluk-detay", YONETIM),
    ]),
]
TUM_UCLAR = [(m, yol, izin) for m, ucler in AYRILANLAR for yol, izin in ucler]


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


def _ek_bagimliliklar(modul):
    """Yalnızca `mevcut_kullanici_id` de isteyen yönlendiriciler (oturum açmış olmak yeterli uçlar)."""
    return (lambda: 1,) if "mevcut_kullanici_id" in inspect.signature(modul.router_olustur).parameters else ()


@pytest.mark.parametrize("modul", [m for m, _ in AYRILANLAR] + [ortak_sabitler, ortak_yardimcilar, vt_ayarlari])
def test_ayrilan_modul_sunucuyu_ice_aktarmaz_dongusel_bagimlilik_olmaz(modul):
    assert not {a for a in _ice_aktarilan_modul_adlari(modul) if a == "server.sunucu" or a.startswith("server.sunucu.")}


@pytest.mark.parametrize("modul, yol, izin", TUM_UCLAR)
def test_uc_tam_bir_kez_kayitli_ve_kimliksiz_istek_reddedilir(modul, yol, izin):
    sema = sunucu.app.openapi()["paths"]
    assert yol in sema and list(sema[yol]) == ["get"]
    assert TestClient(sunucu.app).get(yol).status_code == 401      # yetki bağımlılığı gerçekten bağlı (kimliksiz istek geçemez)


@pytest.mark.parametrize("modul, ucler", AYRILANLAR)
def test_router_her_ucun_izin_kontrolunu_dogru_izinle_ve_sirayla_olusturur(modul, ucler):
    istenen = []

    def sahte_izin_kontrol(ad):
        istenen.append(ad)
        return lambda: 1

    yonlendirici = modul.router_olustur(sahte_izin_kontrol, *_ek_bagimliliklar(modul))
    assert istenen == [izin for _, izin in ucler if izin]
    # kayıtlı yollar da beklenen listeyle aynı
    kayitli = [getattr(r, "path", None) for r in yonlendirici.routes]
    assert kayitli == [yol for yol, _ in ucler]


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
                         (surum_api, ("_sistem_durumu", "_SURUM", "_UYGULAMA_ADI", "surum_bilgisi", "sistem_durumu_getir"))):
        for ad in adlar:
            assert getattr(sunucu, ad) is getattr(modul, ad), ad
    assert sunucu.psikolog_rolu_mu is ortak_yardimcilar.psikolog_rolu_mu
    assert sunucu.VT_AYARLARI is vt_ayarlari.VT_AYARLARI
    assert sunucu.ETKIN_CIHAZ_DURUMU_SQL is ortak_sabitler.ETKIN_CIHAZ_DURUMU_SQL
    assert sunucu.OGRENCI_TUR_ETIKETLERI is ortak_sabitler.OGRENCI_TUR_ETIKETLERI


def test_ayrilan_kod_sunucu_dosyasinda_yinelenmez():
    kaynak = (KOK / "server" / "sunucu.py").read_text(encoding="utf-8")
    for modul, _ in AYRILANLAR:
        for ad, deger in vars(modul).items():
            if inspect.isfunction(deger) and deger.__module__ == modul.__name__ and ad != "router_olustur":
                assert f"def {ad}(" not in kaynak, ad
    for yol in [yol for _, ucler in AYRILANLAR for yol, _ in ucler]:
        assert f'("{yol}")' not in kaynak and f"('{yol}')" not in kaynak
    assert "ETKIN_CIHAZ_DURUMU_SQL = " not in kaynak and "OGRENCI_TUR_ETIKETLERI = " not in kaynak
    assert "def psikolog_rolu_mu(" not in kaynak and "PUAN_RAPORU_DURUMLARI = " not in kaynak and "UYGUNLUK_EN_FAZLA_GUN = " not in kaynak


def _yetkili_fonksiyonlar(modul):
    """(fonksiyon, yetki parametresi) listesi: UCLAR tablosu varsa ondan, yoksa `kullanici_id` parametresi olan modül fonksiyonlarından."""
    if hasattr(modul, "UCLAR"):
        # 2. adım modüllerinde (yol, fonksiyon, izin), sonrakilerde (yol, fonksiyon, parametre, izin)
        return [(u[1], u[2] if len(u) == 4 else "kullanici_id") for u in modul.UCLAR]
    return [(d, "kullanici_id") for ad, d in vars(modul).items()
            if inspect.isfunction(d) and d.__module__ == modul.__name__ and "kullanici_id" in inspect.signature(d).parameters]


def test_ayrilan_fonksiyonlar_dogrudan_cagrilabilir_yetki_parametresi_acik_kalir():
    for modul, ucler in AYRILANLAR:
        yonlendirici = modul.router_olustur(lambda izin: (lambda: 1), *_ek_bagimliliklar(modul))
        fonksiyonlar = _yetkili_fonksiyonlar(modul)
        assert len(fonksiyonlar) == len(ucler) == len(yonlendirici.routes)
        for r, (fonksiyon, parametre) in zip(yonlendirici.routes, fonksiyonlar):
            assert parametre in inspect.signature(r.endpoint).parameters          # kayıtlı uç yetki parametresini taşır
            assert inspect.signature(fonksiyon).parameters[parametre].default is None, fonksiyon.__name__   # ham fonksiyonda Depends yok


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
