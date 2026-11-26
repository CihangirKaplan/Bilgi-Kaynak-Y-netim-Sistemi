"""server/sunucu.py'nin parçalanması: ayrılan uç modülleri aynı yetkiyle ve aynı adlarla çalışır; sunucuya geri bağımlı olmaz."""
import ast
import inspect
from pathlib import Path

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient

import server.sunucu as sunucu
from server import (
    audit_api, cihaz_raporlari_api, danisma_raporlari_api, ortak_sabitler, vt_ayarlari, yonetim_raporlari_api,
)
from server.yetki_baglama import yetkiyle_bagla

KOK = Path(__file__).resolve().parents[2]

YONETIM = "YONETIM_RAPORLARI_GORUNTULE"
# Ayrılan modüller: (modül, [(uç yolu, gereken izin), ...]). Yetki eşlemesi güvenlik açısından AÇIKÇA yazılıdır:
# taşıma sırasında hiçbir ucun izni değişmemelidir.
AYRILANLAR = [
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


@pytest.mark.parametrize("modul", [m for m, _ in AYRILANLAR] + [ortak_sabitler, vt_ayarlari])
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

    yonlendirici = modul.router_olustur(sahte_izin_kontrol)
    assert istenen == [izin for _, izin in ucler]
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


def test_ayrilan_fonksiyonlar_dogrudan_cagrilabilir_yetki_parametresi_acik_kalir():
    for modul, ucler in AYRILANLAR:
        yonlendirici = modul.router_olustur(lambda izin: (lambda: 1))
        for r in yonlendirici.routes:
            imza = inspect.signature(r.endpoint)
            assert "kullanici_id" in imza.parameters
        # ham fonksiyonlarda Depends yok (varsayılan None)
        for ad, deger in vars(modul).items():
            if inspect.isfunction(deger) and deger.__module__ == modul.__name__ and "kullanici_id" in inspect.signature(deger).parameters:
                assert inspect.signature(deger).parameters["kullanici_id"].default is None, ad


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
