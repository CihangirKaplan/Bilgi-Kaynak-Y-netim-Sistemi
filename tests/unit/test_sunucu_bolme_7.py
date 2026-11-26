"""server/sunucu.py parçalama 7. adım: Danışma Masası uçları ayrı modülde (server/danisma_masasi_api.py).

Her ucun yöntemi, gereken izni ve başarı kodu AÇIKÇA yazılıdır: taşıma sırasında hiçbir ucun yetkisi değişmemelidir.
"""
import ast
import inspect
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import server.sunucu as sunucu
from server import danisma_masasi_api

KOK = Path(__file__).resolve().parents[2]
OTURUM = "DANISMA_OTURUMU_YONET"                 # öğrencinin kendi oturumu
YONETIM = "DANISMA_OTURUMU_YONETIM"              # yönetici ekranı

# (yöntem, yol, gereken izin, başarı kodu) — sıra, yönlendiricideki kayıt sırasıdır.
UCLAR = [
    ("POST", "/api/danisma/oturum/baslat", OTURUM, "201"),
    ("PATCH", "/api/danisma/oturum/bitir", OTURUM, "200"),
    ("GET", "/api/danisma/oturum/aktif", OTURUM, "200"),
    ("GET", "/api/danisma/oturum/gecmis", OTURUM, "200"),
    ("GET", "/api/danisma/yonetim/onay-bildirimleri", YONETIM, "200"),
    ("GET", "/api/danisma/yonetim/oturumlar", YONETIM, "200"),
    ("PATCH", "/api/danisma/yonetim/oturumlar/{oturum_id}/onayla", YONETIM, "200"),
    ("PATCH", "/api/danisma/yonetim/oturumlar/{oturum_id}/onay-geri-al", YONETIM, "200"),
    ("GET", "/api/danisma/yonetim/ogrenciler", YONETIM, "200"),
    ("POST", "/api/danisma/yonetim/oturumlar", YONETIM, "201"),
    ("PATCH", "/api/danisma/yonetim/oturumlar/{oturum_id}", YONETIM, "200"),
]
GERIYE_DONUK_ADLAR = (
    "danisma_oturumu_baslat", "danisma_oturumu_bitir", "danisma_aktif_oturum", "danisma_oturum_gecmisi", "danisma_onay_bildirimleri",
    "DANISMA_GOREV_EN_UZUN_SAAT", "DANISMA_GOREV_COK_UZUN_MESAJI", "danisma_gorevi_cok_uzun_mu", "DANISMA_LISTE_EN_FAZLA",
    "danisma_yonetim_oturumlari", "danisma_yonetim_oturum_onayla", "danisma_yonetim_onay_geri_al", "danisma_yonetim_ogrencileri",
    "danisma_yonetim_oturum_olustur", "danisma_yonetim_oturum_duzenle",
)


def test_modul_sunucuyu_ice_aktarmaz_dongusel_bagimlilik_olmaz():
    agac = ast.parse(Path(danisma_masasi_api.__file__).read_text(encoding="utf-8"))
    adlar = set()
    for d in ast.walk(agac):
        if isinstance(d, ast.Import):
            adlar.update(a.name for a in d.names)
        elif isinstance(d, ast.ImportFrom):
            adlar.add(d.module or "")
    assert not {a for a in adlar if a == "server.sunucu" or a.startswith("server.sunucu.")}


@pytest.mark.parametrize("yontem, yol, izin, kod", UCLAR)
def test_uc_tam_bir_kez_kayitli_basari_kodu_dogru_ve_kimliksiz_istek_reddedilir(yontem, yol, izin, kod):
    sema = sunucu.app.openapi()["paths"]
    assert yol in sema and yontem.lower() in sema[yol]
    yanitlar = sema[yol][yontem.lower()]["responses"]
    assert kod in yanitlar and ("201" in yanitlar) == (kod == "201")                   # oluşturan uçlar 201, diğerleri 200
    assert TestClient(sunucu.app).request(yontem, re.sub(r"\{[^}]+\}", "1", yol)).status_code == 401


def test_router_her_ucun_iznini_dogru_ve_sirayla_ister_yollar_ve_yontemler_ayni():
    istenen = []

    def sahte_izin_kontrol(ad):
        istenen.append(ad)
        return lambda: 1

    yonlendirici = danisma_masasi_api.router_olustur(sahte_izin_kontrol)
    assert istenen == [izin for _, _, izin, _ in UCLAR]
    assert [(sorted(r.methods)[0], r.path) for r in yonlendirici.routes] == [(y, yol) for y, yol, _, _ in UCLAR]


def test_ham_fonksiyonlarda_yetki_bagimliligi_yok_kayitli_uc_yetki_parametresini_tasir():
    yonlendirici = danisma_masasi_api.router_olustur(lambda izin: (lambda: 1))
    assert len(danisma_masasi_api.UCLAR) == len(UCLAR) == len(yonlendirici.routes)
    for r, (_, _, fonksiyon, parametre, _, _) in zip(yonlendirici.routes, danisma_masasi_api.UCLAR):
        assert parametre in inspect.signature(r.endpoint).parameters
        assert inspect.signature(fonksiyon).parameters[parametre].default is None


def test_yetki_tablosu_izin_disinda_bir_deger_alirsa_kayit_sirasinda_patlar(monkeypatch):
    metod, yol, fonksiyon, parametre, _, ek = danisma_masasi_api.UCLAR[0]
    monkeypatch.setattr(danisma_masasi_api, "UCLAR", [(metod, yol, fonksiyon, parametre, None, ek)])
    with pytest.raises(AssertionError):
        danisma_masasi_api.router_olustur(lambda ad: (lambda: 1))


def test_sunucudaki_geriye_donuk_adlar_ayrilan_nesnelerle_aynidir():
    for ad in GERIYE_DONUK_ADLAR:
        assert getattr(sunucu, ad) is getattr(danisma_masasi_api, ad), ad


def test_ayrilan_kod_sunucu_dosyasinda_yinelenmez():
    kaynak = (KOK / "server" / "sunucu.py").read_text(encoding="utf-8")
    for ad, deger in vars(danisma_masasi_api).items():
        if inspect.isfunction(deger) and deger.__module__ == danisma_masasi_api.__name__ and ad != "router_olustur":
            assert f"def {ad}(" not in kaynak, ad
    for yontem, yol, _, _ in UCLAR:
        assert f'@app.{yontem.lower()}("{yol}"' not in kaynak, (yontem, yol)
    for sabit in ("DANISMA_GOREV_EN_UZUN_SAAT = ", "DANISMA_LISTE_EN_FAZLA = ", "DANISMA_GOREV_COK_UZUN_MESAJI = "):
        assert sabit not in kaynak, sabit
