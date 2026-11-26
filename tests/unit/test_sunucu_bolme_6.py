"""server/sunucu.py parçalama 6. adım: arıza, bakım, kalibrasyon ve bakım planı uçları ile ortak yardımcılar ayrı modüllerde.

Her ucun yöntemi ve gereken yetkisi AÇIKÇA yazılıdır: taşıma sırasında hiçbir ucun yetkisi değişmemelidir. Gereken yetki:
"IZIN" (izin_kontrol), ("A", "B") (izin_kontrol_biri: biri yeter), None (yalnızca oturum açmış olmak: kimlik bağımlılığı).
"""
import ast
import inspect
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import server.sunucu as sunucu
from server import ariza_api, bakim_kalibrasyon_api, bakim_plani_api, liste_siniri, rezervasyon_cakismasi

KOK = Path(__file__).resolve().parents[2]
ARIZA = "ARIZA_KAYITLARI_YONET"
BAKIM_GORUNTULE = ("BAKIM_KAYITLARI_GORUNTULE", "BAKIM_KAYITLARI_YONET")
KALIBRASYON_GORUNTULE = ("KALIBRASYON_KAYITLARI_GORUNTULE", "KALIBRASYON_KAYITLARI_YONET")

# (modül, [(yöntem, yol, gereken yetki, başarılı yanıt kodu), ...]) — sıra, yönlendiricideki kayıt sırasıdır.
UC_MODULLERI = [
    (ariza_api, [
        ("GET", "/api/arizalar", ARIZA, "200"),
        ("POST", "/api/arizalar", ARIZA, "201"),
        ("PUT", "/api/arizalar/{ariza_id}", ARIZA, "200"),
    ]),
    (bakim_kalibrasyon_api, [
        ("GET", "/api/bakimlar", BAKIM_GORUNTULE, "200"),
        ("POST", "/api/bakimlar", "BAKIM_KAYITLARI_YONET", "201"),
        ("PUT", "/api/bakimlar/{bakim_id}", "BAKIM_KAYITLARI_YONET", "200"),
        ("DELETE", "/api/bakimlar/{bakim_id}", "BAKIM_KAYITLARI_YONET", "200"),
        ("GET", "/api/kalibrasyonlar", KALIBRASYON_GORUNTULE, "200"),
        ("POST", "/api/kalibrasyonlar", "KALIBRASYON_KAYITLARI_YONET", "201"),
        ("PUT", "/api/kalibrasyonlar/{kalibrasyon_id}", "KALIBRASYON_KAYITLARI_YONET", "200"),
        ("DELETE", "/api/kalibrasyonlar/{kalibrasyon_id}", "KALIBRASYON_KAYITLARI_YONET", "200"),
    ]),
    # Bakım planı uçları izin kontrolü yerine yalnızca oturum ister: plan türüne göre izin işlev içinde denetlenir
    # (bkz. tests/security/test_uc_koruma_taramasi.py ISTISNALAR).
    (bakim_plani_api, [
        ("GET", "/api/bakim-planlari", None, "200"),
        ("POST", "/api/bakim-planlari", None, "201"),
        ("PUT", "/api/bakim-planlari/{plan_id}", None, "200"),
        ("DELETE", "/api/bakim-planlari/{plan_id}", None, "200"),
    ]),
]
ORTAK_MODULLER = [liste_siniri, rezervasyon_cakismasi]
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
        liste_siniri: ("LISTE_UST_SINIRI", "liste_siniri_coz", "liste_toplamini_bildir"),
        rezervasyon_cakismasi: ("REZERVASYON_CAKISMA_KODU", "rezervasyon_cakisma_detayi", "cakisan_rezervasyonlari_denetle"),
        ariza_api: ("ARIZA_ILE_ARIZALI_OLABILEN_DURUMLAR", "arizadan_sonra_cihaz_durumu", "arizalari_listele", "ariza_bildir", "ariza_guncelle"),
        bakim_kalibrasyon_api: ("bakimlari_listele", "bakim_kaydi_ekle", "bakim_guncelle", "bakim_kaydi_sil", "kalibrasyonlari_listele",
                                "kalibrasyon_kaydi_ekle", "kalibrasyon_guncelle", "kalibrasyon_kaydi_sil"),
        bakim_plani_api: ("bakim_plani_durumu", "_plan_yetkileri", "_plan_turu_yetkisini_dogrula", "bakim_planlarini_listele", "plani_ilerlet",
                          "plan_periyodu", "_ayni_planli_aktif_kayit_var_mi", "bakim_plani_ekle", "bakim_plani_guncelle", "bakim_plani_sil"),
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
    for sabit in ("LISTE_UST_SINIRI = ", "REZERVASYON_CAKISMA_KODU = ", "ARIZA_ILE_ARIZALI_OLABILEN_DURUMLAR = "):
        assert sabit not in kaynak, sabit


def test_yalniz_oturum_ya_da_yalniz_tek_izin_isteyen_router_uyumsuz_yetki_tablosunu_sessizce_yok_saymaz(monkeypatch):
    """Yetki sütunu yönlendiricinin desteklemediği bir değere (ör. yalnızca oturum isteyen modülde bir izin adı) değiştirilirse
    kayıt sırasında patlamalı; yetki sessizce yok sayılmamalı."""
    satirlar = list(bakim_plani_api.UCLAR)
    metod, yol, fonksiyon, parametre, _, ek = satirlar[0]
    monkeypatch.setattr(bakim_plani_api, "UCLAR", [(metod, yol, fonksiyon, parametre, "BAKIM_KAYITLARI_YONET", ek)])
    with pytest.raises(AssertionError):
        bakim_plani_api.router_olustur(lambda: 1)
    satirlar = list(ariza_api.UCLAR)
    metod, yol, fonksiyon, parametre, _, ek = satirlar[0]
    monkeypatch.setattr(ariza_api, "UCLAR", [(metod, yol, fonksiyon, parametre, None, ek)])
    with pytest.raises(AssertionError):
        ariza_api.router_olustur(lambda ad: (lambda: 1))


def _tanimsiz_global_adlar(yol):
    """Kapsam duyarlı denetim: bir fonksiyonun yerel olmayan (global) kullandığı her ad modül düzeyinde tanımlı ya da yerleşik olmalı.

    Düz ad taraması yetmez: bir fonksiyonun kendi içinde yaptığı `from x import y` o adı tüm modül için tanımlıymış gibi gösterir,
    oysa diğer fonksiyonlar dosya düzeyinde içe aktarılmasına güvenir (kod taşınırken eksik içe aktarma böyle gözden kaçar)."""
    import builtins
    import symtable

    tablo = symtable.symtable(Path(yol).read_text(encoding="utf-8"), str(yol), "exec")
    modul_adlari = {s.get_name() for s in tablo.get_symbols() if s.is_assigned() or s.is_imported() or s.is_namespace()}
    bulunanlar = []

    def gez(t, ad):
        for s in t.get_symbols():
            if t.get_type() != "module" and s.is_global() and s.is_referenced():
                if s.get_name() not in modul_adlari and not hasattr(builtins, s.get_name()) and s.get_name() != "__file__":
                    bulunanlar.append((ad, s.get_name()))
        for alt in t.get_children():
            gez(alt, f"{ad}.{alt.get_name()}")

    gez(tablo, "")
    return bulunanlar


def test_server_modullerinde_tanimsiz_global_ad_yok_kapsam_duyarli():
    sorunlar = {str(d.name): _tanimsiz_global_adlar(d) for d in sorted((KOK / "server").glob("*.py"))}
    assert {d: s for d, s in sorunlar.items() if s} == {}


def test_kapsam_duyarli_denetim_gercekten_eksik_ice_aktarmayi_yakalar(tmp_path):
    dosya = tmp_path / "ornek.py"
    dosya.write_text(
        "def a():\n    from os import getcwd\n    return getcwd()\n\n\ndef b():\n    return getcwd()\n",   # b() için getcwd modülde tanımsız
        encoding="utf-8",
    )
    assert _tanimsiz_global_adlar(dosya) == [(".b", "getcwd")]
