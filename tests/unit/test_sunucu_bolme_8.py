"""server/sunucu.py parçalama 8. adım: öğrenci yönetimi uçları ayrı modülde (server/ogrenci_api.py).

Her ucun yöntemi ve gereken izni AÇIKÇA yazılıdır: taşıma sırasında hiçbir ucun yetkisi değişmemelidir. Öğrenci kaydını kalıcı silme
(`saklama-suresi-sil`) ayrı bir izne (OGRENCI_KAYDI_SIL) bağlıdır; diğer öğrenci uçları FAALIYET_KAYITLARI_DUZENLE ister.
"""
import ast
import inspect
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import server.sunucu as sunucu
from server import ogrenci_api

KOK = Path(__file__).resolve().parents[2]
FAALIYET = "FAALIYET_KAYITLARI_DUZENLE"
KALICI_SIL = "OGRENCI_KAYDI_SIL"

# (yöntem, yol, gereken izin, yetki parametresi) — sıra, yönlendiricideki kayıt sırasıdır.
UCLAR = [
    ("GET", "/api/ogrenciler-liste", FAALIYET, "kullanici_id"),
    ("GET", "/api/ogrenciler-yonetim", FAALIYET, "yetkili_id"),
    ("GET", "/api/ogrenciler/{ogrenci_id}/puanlar", FAALIYET, "yetkili_id"),
    ("PATCH", "/api/ogrenciler/{ogrenci_id}/silme-ertele", FAALIYET, "yetkili_id"),
    ("DELETE", "/api/ogrenciler/{ogrenci_id}/saklama-suresi-sil", KALICI_SIL, "yetkili_id"),
    ("PATCH", "/api/ogrenciler/{ogrenci_id}/aktiflik", FAALIYET, "yetkili_id"),
    ("POST", "/api/ogrenci-ekle", FAALIYET, "yetkili_id"),
]
GERIYE_DONUK_ADLAR = (
    "ogrencileri_getir", "OgrenciAktiflikModeli", "OgrenciErteleModeli", "OgrenciSilOnayModeli", "ogrenciler_yonetim_listesi",
    "ogrenci_puan_detayi", "_ogrenci_saklama_suresi_kontrol", "ogrenci_silme_ertele", "ogrenci_saklama_suresi_sil",
    "ogrenci_aktiflik_duzenle", "ogrenci_ekle",
)


def test_modul_sunucuyu_ice_aktarmaz_dongusel_bagimlilik_olmaz():
    agac = ast.parse(Path(ogrenci_api.__file__).read_text(encoding="utf-8"))
    adlar = set()
    for d in ast.walk(agac):
        if isinstance(d, ast.Import):
            adlar.update(a.name for a in d.names)
        elif isinstance(d, ast.ImportFrom):
            adlar.add(d.module or "")
    assert not {a for a in adlar if a == "server.sunucu" or a.startswith("server.sunucu.")}


@pytest.mark.parametrize("yontem, yol, izin, parametre", UCLAR)
def test_uc_tam_bir_kez_kayitli_basari_kodu_200_ve_kimliksiz_istek_reddedilir(yontem, yol, izin, parametre):
    sema = sunucu.app.openapi()["paths"]
    assert yol in sema and yontem.lower() in sema[yol]
    assert "200" in sema[yol][yontem.lower()]["responses"]
    assert TestClient(sunucu.app).request(yontem, re.sub(r"\{[^}]+\}", "1", yol)).status_code == 401


def test_router_her_ucun_iznini_dogru_ve_sirayla_ister_yollar_ve_yontemler_ayni():
    istenen = []

    def sahte_izin_kontrol(ad):
        istenen.append(ad)
        return lambda: 1

    yonlendirici = ogrenci_api.router_olustur(sahte_izin_kontrol)
    assert istenen == [izin for _, _, izin, _ in UCLAR]
    assert [(sorted(r.methods)[0], r.path) for r in yonlendirici.routes] == [(y, yol) for y, yol, _, _ in UCLAR]


def test_yetki_parametresi_adi_korunur_ve_ham_fonksiyonda_bagimlilik_yok():
    yonlendirici = ogrenci_api.router_olustur(lambda izin: (lambda: 1))
    assert len(ogrenci_api.UCLAR) == len(UCLAR) == len(yonlendirici.routes)
    for r, (_, _, fonksiyon, parametre, _, _), (_, _, _, beklenen) in zip(yonlendirici.routes, ogrenci_api.UCLAR, UCLAR):
        assert parametre == beklenen
        assert parametre in inspect.signature(r.endpoint).parameters
        assert inspect.signature(fonksiyon).parameters[parametre].default is None


def test_yetki_tablosu_izin_disinda_bir_deger_alirsa_kayit_sirasinda_patlar(monkeypatch):
    metod, yol, fonksiyon, parametre, _, ek = ogrenci_api.UCLAR[0]
    monkeypatch.setattr(ogrenci_api, "UCLAR", [(metod, yol, fonksiyon, parametre, None, ek)])
    with pytest.raises(AssertionError):
        ogrenci_api.router_olustur(lambda ad: (lambda: 1))


def test_sunucudaki_geriye_donuk_adlar_ayrilan_nesnelerle_aynidir():
    for ad in GERIYE_DONUK_ADLAR:
        assert getattr(sunucu, ad) is getattr(ogrenci_api, ad), ad


def test_ayrilan_kod_sunucu_dosyasinda_yinelenmez():
    kaynak = (KOK / "server" / "sunucu.py").read_text(encoding="utf-8")
    for ad, deger in vars(ogrenci_api).items():
        if inspect.isfunction(deger) and deger.__module__ == ogrenci_api.__name__ and ad != "router_olustur":
            assert f"def {ad}(" not in kaynak, ad
    for ad in ("OgrenciAktiflikModeli", "OgrenciErteleModeli", "OgrenciSilOnayModeli"):
        assert f"class {ad}(" not in kaynak, ad
    for yontem, yol, _, _ in UCLAR:
        assert f'@app.{yontem.lower()}("{yol}"' not in kaynak, (yontem, yol)
