"""server/sunucu.py'nin parçalanması: ayrılan uç modülleri aynı yetkiyle ve aynı adlarla çalışır; sunucuya geri bağımlı olmaz."""
import ast
import inspect
from pathlib import Path

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient

import server.sunucu as sunucu
from server import audit_api, cihaz_raporlari_api, vt_ayarlari
from server.yetki_baglama import yetkiyle_bagla

KOK = Path(__file__).resolve().parents[2]
# Ayrılan modüller: (modül, uç yolu, gereken izin)
AYRILANLAR = [
    (audit_api, "/api/audit-kayitlari", "AUDIT_KAYITLARI_INCELE"),
    (cihaz_raporlari_api, "/api/cihaz-raporlari", "CIHAZ_ENVANTER_YONET"),
]


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


@pytest.mark.parametrize("modul, yol, izin", AYRILANLAR)
def test_ayrilan_modul_sunucuyu_ice_aktarmaz_dongusel_bagimlilik_olmaz(modul, yol, izin):
    assert not {a for a in _ice_aktarilan_modul_adlari(modul) if a == "server.sunucu" or a.startswith("server.sunucu.")}


@pytest.mark.parametrize("modul, yol, izin", AYRILANLAR)
def test_ayrilan_ucun_gerekli_izni_modulde_tek_yerde_tanimlidir(modul, yol, izin):
    assert modul.IZIN_ADI == izin


@pytest.mark.parametrize("modul, yol, izin", AYRILANLAR)
def test_uc_tam_bir_kez_kayitli_ve_kimliksiz_istek_reddedilir(modul, yol, izin):
    sema = sunucu.app.openapi()["paths"]
    assert yol in sema and list(sema[yol]) == ["get"]
    istemci = TestClient(sunucu.app)
    assert istemci.get(yol).status_code == 401                      # yetki bağımlılığı gerçekten bağlı (kimliksiz istek geçemez)


@pytest.mark.parametrize("modul, yol, izin", AYRILANLAR)
def test_uc_izin_kontrolunu_dogru_izinle_olusturur(modul, yol, izin, monkeypatch):
    istenen = []

    def sahte_izin_kontrol(ad):
        istenen.append(ad)
        return lambda: 1

    modul.router_olustur(sahte_izin_kontrol)
    assert istenen == [izin]


def test_sunucudaki_geriye_donuk_adlar_ayrilan_fonksiyonlarla_ayni_nesnedir():
    assert sunucu.audit_kayitlarini_getir is audit_api.audit_kayitlarini_getir
    assert sunucu.cihaz_raporlari is cihaz_raporlari_api.cihaz_raporlari
    assert sunucu.VT_AYARLARI is vt_ayarlari.VT_AYARLARI


def test_ayrilan_kod_sunucu_dosyasinda_yinelenmez():
    kaynak = (KOK / "server" / "sunucu.py").read_text(encoding="utf-8")
    assert "def audit_kayitlarini_getir(" not in kaynak and "def cihaz_raporlari(" not in kaynak and "def _tarih_metni(" not in kaynak
    assert '@app.get("/api/audit-kayitlari")' not in kaynak and '@app.get("/api/cihaz-raporlari")' not in kaynak


def test_ayrilan_fonksiyonlar_dogrudan_cagrilabilir_ve_yetki_parametresi_acik_kalir():
    for modul, _, _ in AYRILANLAR:
        fonksiyon = getattr(modul, "audit_kayitlarini_getir" if modul is audit_api else "cihaz_raporlari")
        assert inspect.signature(fonksiyon).parameters["kullanici_id"].default is None   # çıplak fonksiyonda bağımlılık yok


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
