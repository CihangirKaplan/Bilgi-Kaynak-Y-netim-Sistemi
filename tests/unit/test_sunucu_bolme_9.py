"""server/sunucu.py parçalama 9. adım: randevu ve danışan kodu uçları ayrı modüllerde.\n\nHer ucun yöntemi, gereken yetkisi ve başarı kodu AÇIKÇA yazılıdır: taşıma sırasında hiçbir ucun yetkisi değişmemelidir.\n"""
import ast
import inspect
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import server.sunucu as sunucu
from server import danisan_api, ortak_sabitler, randevu_api

KOK = Path(__file__).resolve().parents[2]
OLUSTUR = "RANDEVU_OLUSTUR"
TAKVIM = "TAKVIM_GORUNTULE"
DUZENLE = "RANDEVU_DUZENLE"
IPTAL = "RANDEVU_IPTAL"

# (modül, [(yöntem, yol, gereken izin, başarı kodu), ...]) — sıra, yönlendiricideki kayıt sırasıdır.
UC_MODULLERI = [
    (randevu_api, [
        ("POST", "/api/randevular", OLUSTUR, "201"),
        ("GET", "/api/randevular", TAKVIM, "200"),
        ("GET", "/api/danisan-randevu-sayilari", TAKVIM, "200"),
        ("GET", "/api/randevular/doluluk", TAKVIM, "200"),
        ("PATCH", "/api/randevular/{randevu_id}", DUZENLE, "200"),
        ("PATCH", "/api/randevular/{randevu_id}/iptal", IPTAL, "200"),
        ("PATCH", "/api/randevular/{randevu_id}/durum", DUZENLE, "200"),
    ]),
    (danisan_api, [
        ("GET", "/api/randevular/siradaki-kod", OLUSTUR, "200"),
        ("POST", "/api/danisan-kodlari", OLUSTUR, "201"),
        ("GET", "/api/danisan-kodlari", OLUSTUR, "200"),
        ("PATCH", "/api/danisan-kodlari/{danisan_kod_id}/durum", OLUSTUR, "200"),
        ("PATCH", "/api/danisan-kodlari/{danisan_kod_id}/bilgiler", OLUSTUR, "200"),
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
        randevu_api: ("psikolog_odasina_atanmis_mi", "randevu_deadlock_yeniden_dene", "randevu_olustur", "RANDEVU_LISTE_SUTUNLARI", "RANDEVU_LISTE_ENCOK",
                      "randevulari_listele", "danisan_randevu_sayilari", "HAFTA_SONU_MESAJI", "hafta_sonuna_denk_mi", "GECMIS_TARIH_MESAJI",
                      "gecmis_tarihe_mi", "DANISAN_PSIKOLOG_MESAJI", "danisan_psikologa_ait_mi", "randevu_taraflarini_denetle", "randevu_doluluk",
                      "randevu_guncelle", "randevu_iptal_et", "randevu_durumunu_isaretle"),
        danisan_api: ("otomatik_danisan_kodu_uret", "siradaki_danisan_kodunu_ver", "IZINLI_ISTISNA_TURLERI", "danisan_kodu_olustur",
                      "danisan_kodlari_listele", "danisan_durumunu_degistir", "danisan_bilgilerini_guncelle"),
        ortak_sabitler: ("PLANLI_RANDEVU_COZUMU",),
    }
    for modul, adlar in esleme.items():
        for ad in adlar:
            assert getattr(sunucu, ad) is getattr(modul, ad), ad


def test_yol_disindaki_dekoratorler_tasimada_korunur_randevu_olusturma_deadlock_yeniden_denemesi():
    """Taşıma yalnızca YOL dekoratörünü (`@app.post(...)`) kaldırır; uca ayrıca bağlı dekoratörler (burada deadlock'ta 3 kez yeniden deneyip
    503 dönen `randevu_deadlock_yeniden_dene`) korunur. OpenAPI şeması bunu göstermez, bu yüzden ayrıca denetlenir."""
    uc = randevu_api.randevu_olustur
    assert hasattr(uc, "__wrapped__"), "randevu_olustur'dan deadlock yeniden deneme dekoratörü düşmüş"
    kaynak = (KOK / "server" / "randevu_api.py").read_text(encoding="utf-8")
    assert "@randevu_deadlock_yeniden_dene\ndef randevu_olustur(" in kaynak
    # kayıtlı uç da sarılı fonksiyonu çağırır (yetki sarmalayıcısı içeriden sarılı fonksiyona gider)
    kayit = next(f for _, _, f, _, _, _ in randevu_api.UCLAR if f.__name__ == "randevu_olustur")
    assert kayit is uc


def test_ayrilan_kod_sunucu_dosyasinda_yinelenmez():
    kaynak = (KOK / "server" / "sunucu.py").read_text(encoding="utf-8")
    for modul in [m for m, _ in UC_MODULLERI] + ORTAK_MODULLER:
        for ad, deger in vars(modul).items():
            if inspect.isfunction(deger) and deger.__module__ == modul.__name__ and ad != "router_olustur":
                assert f"def {ad}(" not in kaynak, ad
    for _, ucler in UC_MODULLERI:
        for yontem, yol, _, _ in ucler:
            assert f'@app.{yontem.lower()}("{yol}"' not in kaynak, (yontem, yol)
    for sabit in ("PLANLI_RANDEVU_COZUMU = ", "RANDEVU_LISTE_ENCOK = ", "IZINLI_ISTISNA_TURLERI = ", "HAFTA_SONU_MESAJI = "):
        assert sabit not in kaynak, sabit


def test_yetki_tablosu_izin_disinda_bir_deger_alirsa_kayit_sirasinda_patlar(monkeypatch):
    """Yetki sütunu yönlendiricinin desteklemediği bir değere (ör. None) değiştirilirse kayıt sırasında patlamalı; yetki sessizce yok sayılmamalı."""
    metod, yol, fonksiyon, parametre, _, ek = randevu_api.UCLAR[0]
    monkeypatch.setattr(randevu_api, "UCLAR", [(metod, yol, fonksiyon, parametre, None, ek)])
    with pytest.raises(AssertionError):
        randevu_api.router_olustur(lambda ad: (lambda: 1))
