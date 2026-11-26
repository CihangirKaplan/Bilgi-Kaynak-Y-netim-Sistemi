"""server/sunucu.py parçalama 6b: cihaz, cihaz rezervasyonu, bölüm ve proje türü uçları ayrı modüllerde.

Her ucun yöntemi, gereken yetkisi ve başarı kodu AÇIKÇA yazılıdır: taşıma sırasında hiçbir ucun yetkisi değişmemelidir.
"""
import ast
import inspect
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import server.sunucu as sunucu
from server import bolum_proje_api, cihaz_api, ortak_sabitler, rezervasyon_api

KOK = Path(__file__).resolve().parents[2]
CIHAZ_EKLE = "CIHAZ_EKLE"
ENVANTER = "CIHAZ_ENVANTER_YONET"
UYGUNLUK = "CIHAZ_UYGUNLUK_GORUNTULE"
REZERVASYON = "CIHAZ_REZERVASYON"

# (modül, [(yöntem, yol, gereken izin, başarı kodu), ...]) — sıra, yönlendiricideki kayıt sırasıdır.
UC_MODULLERI = [
    (cihaz_api, [
        ("POST", "/api/cihazlar", CIHAZ_EKLE, "201"),
        ("PATCH", "/api/cihazlar/{cihaz_id}", ENVANTER, "200"),
        ("GET", "/api/cihazlar", UYGUNLUK, "200"),
        ("GET", "/api/cihazlar/{cihaz_id}/gecmis", ENVANTER, "200"),
        ("GET", "/api/cihazlar/{cihaz_id}", UYGUNLUK, "200"),
    ]),
    (rezervasyon_api, [
        ("POST", "/api/rezervasyonlar", REZERVASYON, "201"),
        ("PATCH", "/api/rezervasyonlar/{rezervasyon_id}/iptal", REZERVASYON, "200"),
        ("PUT", "/api/rezervasyonlar/{rezervasyon_id}", REZERVASYON, "200"),
        ("GET", "/api/rezervasyonlar", REZERVASYON, "200"),
    ]),
    (bolum_proje_api, [
        ("GET", "/api/bolumler", REZERVASYON, "200"),
        ("POST", "/api/bolumler", REZERVASYON, "201"),
        ("GET", "/api/proje-turleri", REZERVASYON, "200"),
        ("POST", "/api/proje-turleri", REZERVASYON, "201"),
    ]),
]
ORTAK_MODULLER = [ortak_sabitler]
TUM_UCLAR = [(m, y, yol, yetki, kod) for m, ucler in UC_MODULLERI for y, yol, yetki, kod in ucler]


def _ice_aktarilanlar(modul):
    agac = ast.parse(Path(modul.__file__).read_text(encoding="utf-8"))
    adlar = set()
    for d in ast.walk(agac):
        if isinstance(d, ast.Import):
            adlar.update(a.name for a in d.names)
        elif isinstance(d, ast.ImportFrom):
            adlar.add(d.module or "")
    return adlar


def _sahte_bagimliliklar(modul, kayit):
    """Yönlendirici üreticisinin istediği bağımlılık üreticileri (sahte); hangi yetkinin istendiğini `kayit`a yazar."""
    def izin_kontrol(ad):
        kayit.append(ad)
        return lambda: 1

    def izin_kontrol_biri(*adlar):
        kayit.append(tuple(adlar))
        return lambda: 1

    sahteler = {"izin_kontrol": izin_kontrol, "izin_kontrol_biri": izin_kontrol_biri, "mevcut_kullanici_id": lambda: 1}
    return [sahteler[ad] for ad in inspect.signature(modul.router_olustur).parameters]


@pytest.mark.parametrize("modul", [m for m, _ in UC_MODULLERI] + ORTAK_MODULLER)
def test_ayrilan_modul_sunucuyu_ice_aktarmaz_dongusel_bagimlilik_olmaz(modul):
    assert not {a for a in _ice_aktarilanlar(modul) if a == "server.sunucu" or a.startswith("server.sunucu.")}


@pytest.mark.parametrize("modul, yontem, yol, yetki, kod", TUM_UCLAR)
def test_uc_tam_bir_kez_kayitli_basari_kodu_dogru_ve_kimliksiz_istek_reddedilir(modul, yontem, yol, yetki, kod):
    sema = sunucu.app.openapi()["paths"]
    assert yol in sema and yontem.lower() in sema[yol]
    yanitlar = sema[yol][yontem.lower()]["responses"]
    assert kod in yanitlar and ("201" in yanitlar) == (kod == "201")                # oluşturan uçlar 201, diğerleri 200
    assert TestClient(sunucu.app).request(yontem, re.sub(r"\{[^}]+\}", "1", yol)).status_code == 401


@pytest.mark.parametrize("modul, ucler", UC_MODULLERI)
def test_router_her_ucun_yetkisini_dogru_ve_sirayla_ister_yollar_ve_yontemler_ayni(modul, ucler):
    istenen = []
    yonlendirici = modul.router_olustur(*_sahte_bagimliliklar(modul, istenen))
    assert istenen == [yetki for _, _, yetki, _ in ucler if yetki]
    assert [(sorted(r.methods)[0], r.path) for r in yonlendirici.routes] == [(y, yol) for y, yol, _, _ in ucler]


@pytest.mark.parametrize("modul, ucler", UC_MODULLERI)
def test_ham_fonksiyonlarda_yetki_bagimliligi_yok_kayitli_uc_yetki_parametresini_tasir(modul, ucler):
    yonlendirici = modul.router_olustur(*_sahte_bagimliliklar(modul, []))
    assert len(modul.UCLAR) == len(ucler) == len(yonlendirici.routes)
    for r, (_, _, fonksiyon, parametre, _, _) in zip(yonlendirici.routes, modul.UCLAR):
        assert parametre in inspect.signature(r.endpoint).parameters
        assert inspect.signature(fonksiyon).parameters[parametre].default is None


def test_sunucudaki_geriye_donuk_adlar_ayrilan_nesnelerle_aynidir():
    esleme = {
        cihaz_api: ("cihaz_ekle", "cihaz_guncelle", "cihazin_acik_arizasi_var_mi", "cihazlari_listele", "GECMIS_OLAY_SINIRI", "_gun_metni", "_iso",
                    "cihaz_gecmisi_getir", "cihaz_detayi_getir"),
        rezervasyon_api: ("rezervasyon_uygunlugunu_denetle", "cihaz_rezervasyonu_yap", "REZERVASYON_YONETIM_YETKISI_SQL", "REZERVASYON_YETKI_MESAJI",
                          "rezervasyon_iptal", "rezervasyon_guncelle", "rezervasyon_gorunen_durumu", "rezervasyonlari_listele"),
        bolum_proje_api: ("bolumleri_listele", "bolum_olustur", "proje_turu_anahtari", "proje_turlerini_listele", "proje_turu_olustur"),
        ortak_sabitler: ("CIHAZ_ODALARI_SORGUSU",),
    }
    for modul, adlar in esleme.items():
        for ad in adlar:
            assert getattr(sunucu, ad) is getattr(modul, ad), ad


def test_ayrilan_kod_sunucu_dosyasinda_yinelenmez():
    kaynak = (KOK / "server" / "sunucu.py").read_text(encoding="utf-8")
    for modul in [m for m, _ in UC_MODULLERI] + ORTAK_MODULLER:
        for ad, deger in vars(modul).items():
            if inspect.isfunction(deger) and deger.__module__ == modul.__name__ and ad != "router_olustur":
                assert f"def {ad}(" not in kaynak, ad
    for _, ucler in UC_MODULLERI:
        for yontem, yol, _, _ in ucler:
            assert f'@app.{yontem.lower()}("{yol}"' not in kaynak, (yontem, yol)
    for sabit in ("CIHAZ_ODALARI_SORGUSU = ", "GECMIS_OLAY_SINIRI = ", "REZERVASYON_YONETIM_YETKISI_SQL = ", "REZERVASYON_YETKI_MESAJI = "):
        assert sabit not in kaynak, sabit


def test_yetki_tablosu_izin_disinda_bir_deger_alirsa_kayit_sirasinda_patlar(monkeypatch):
    """Yetki sütunu yönlendiricinin desteklemediği bir değere (ör. None) değiştirilirse kayıt sırasında patlamalı; yetki sessizce yok sayılmamalı."""
    metod, yol, fonksiyon, parametre, _, ek = cihaz_api.UCLAR[0]
    monkeypatch.setattr(cihaz_api, "UCLAR", [(metod, yol, fonksiyon, parametre, None, ek)])
    with pytest.raises(AssertionError):
        cihaz_api.router_olustur(lambda ad: (lambda: 1))
