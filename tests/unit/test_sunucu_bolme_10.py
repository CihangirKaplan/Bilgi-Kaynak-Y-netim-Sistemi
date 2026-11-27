"""server/sunucu.py parçalama 10-13. adım: kullanıcı, oda, rol/izin, parola talebi ve personel uçları ayrı modüllerde.

Her ucun yöntemi, gereken yetkisi ve başarı kodu AÇIKÇA yazılıdır: taşıma sırasında hiçbir ucun yetkisi değişmemelidir.
Yetki türleri: düz metin = izin_kontrol (tek izin), `Hepsi(...)` = izin_kontrol_tumu (hepsi gerekir), `None` = herkese açık (kimlik doğrulaması yok).
"""
import ast
import inspect
import re
from pathlib import Path

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

import server.sunucu as sunucu
from server import kullanici_api, oda_api, parola_talebi_api, personel_api, rol_api
from server.yetki_baglama import Hepsi

KOK = Path(__file__).resolve().parents[2]
OLUSTUR = "KULLANICI_OLUSTUR"
ATAMA = "ROL_ATAMA_DEGISTIRME"
ROL_OLUSTUR = "ROL_OLUSTUR"
ROL_DUZENLE = "ROL_DUZENLE"
ROL_IZIN = "ROL_IZIN_YONET"
PAROLA = "KULLANICI_PAROLA_SIFIRLA"
PASIFLESTIR = "KULLANICI_PASIFLESTIR"
PERSONEL = "PERSONEL_TANIMLA"
ODA_EKLE = "ODA_EKLE"
ODA_DUZENLE = "ODA_DUZENLE"
ODA_GORUNTULE = "ODA_DURUMU_GORUNTULE"
CIHAZ_REZ = "CIHAZ_REZERVASYON"
RANDEVU = "RANDEVU_OLUSTUR"
TAKVIM = "TAKVIM_GORUNTULE"
IZIN_DUZENLE = "IZIN_DUZENLE"

# (modül, [(yöntem, yol, gereken yetki, başarı kodu), ...]) — sıra, yönlendiricideki kayıt sırasıdır.
UC_MODULLERI = [
    (kullanici_api, [
        ("POST", "/api/kullanicilar", OLUSTUR, "201"),
        ("GET", "/api/kullanicilar/musait-kullanici-adi", OLUSTUR, "200"),
        ("GET", "/api/kullanicilar/{kullanici_id}/ogrenci-kayit-durumu", ATAMA, "200"),
        ("PATCH", "/api/kullanicilar/{kullanici_id}/rol", ATAMA, "200"),
        ("POST", "/api/kullanicilar/{kullanici_id}/parola-sifirla", PAROLA, "200"),
        ("PATCH", "/api/kullanicilar/{kullanici_id}/durum-degistir", PASIFLESTIR, "200"),
    ]),
    (oda_api, [
        ("GET", "/api/kullanicilar/{hedef_kullanici_id}/odalar", ATAMA, "200"),
        ("PUT", "/api/kullanicilar/{hedef_kullanici_id}/odalar", ATAMA, "200"),
        ("GET", "/api/oda-planli-randevu-sayilari", Hepsi(ODA_EKLE, ODA_DUZENLE), "200"),
        ("GET", "/api/oda-psikolog-atamalari", Hepsi(ODA_EKLE, ODA_DUZENLE), "200"),
        ("POST", "/api/odalar", ODA_EKLE, "201"),
        ("GET", "/api/psikologlar/{personel_id}/odalar", RANDEVU, "200"),
        ("GET", "/api/odalar", ODA_GORUNTULE, "200"),
        ("GET", "/api/cihaz-odalari", CIHAZ_REZ, "200"),
        ("GET", "/api/odalar/{oda_id}", ODA_GORUNTULE, "200"),
        ("PATCH", "/api/odalar/{oda_id}", ODA_DUZENLE, "200"),
        ("GET", "/api/psikologlar", TAKVIM, "200"),
    ]),
    (parola_talebi_api, [
        ("POST", "/api/parola-sifirlama-talebi", None, "200"),
        ("GET", "/api/parola-sifirlama-talepleri", PAROLA, "200"),
        ("PATCH", "/api/parola-sifirlama-talepleri/{talep_id}/kapat", PAROLA, "200"),
    ]),
    (personel_api, [
        ("POST", "/api/personel", PERSONEL, "201"),
        ("GET", "/api/personel", PERSONEL, "200"),
        ("GET", "/api/kullanicilar/personel-olmayanlar", PERSONEL, "200"),
        ("GET", "/api/personel/{personel_id}", PERSONEL, "200"),
        ("PATCH", "/api/personel/{personel_id}", PERSONEL, "200"),
    ]),
    (rol_api, [
        ("POST", "/api/roller", ROL_OLUSTUR, "201"),
        ("PUT", "/api/roller/{rol_id}", ROL_DUZENLE, "200"),
        ("DELETE", "/api/roller/{rol_id}", ROL_DUZENLE, "200"),
        ("GET", "/api/roller/atanabilir/olusturma", OLUSTUR, "200"),
        ("GET", "/api/roller/atanabilir/degistirme", ATAMA, "200"),
        ("GET", "/api/roller", ROL_IZIN, "200"),
        ("GET", "/api/roller/{rol_id}/yetki-ozeti", OLUSTUR, "200"),
        ("GET", "/api/rol-izin-matrisi", ROL_IZIN, "200"),
        ("POST", "/api/izinler", ROL_DUZENLE, "201"),
        ("PUT", "/api/izinler/{izin_id}", IZIN_DUZENLE, "200"),
    ]),
]
TUM_UCLAR = [(m, y, yol, yetki, kod) for m, ucler in UC_MODULLERI for y, yol, yetki, kod in ucler]
KORUMALI_UCLAR = [u for u in TUM_UCLAR if u[3] is not None]


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
    """Yönlendirici üreticisinin istediği bağımlılık üreticileri (sahte); hangi yetkinin, hangi türle istendiğini `kayit`a yazar."""
    def izin_kontrol(ad):
        kayit.append(ad)
        return lambda: 1

    def izin_kontrol_biri(*adlar):
        kayit.append(("biri", tuple(adlar)))
        return lambda: 1

    def izin_kontrol_tumu(*adlar):
        kayit.append(Hepsi(*adlar))
        return lambda: 1

    sahteler = {"izin_kontrol": izin_kontrol, "izin_kontrol_biri": izin_kontrol_biri, "izin_kontrol_tumu": izin_kontrol_tumu,
                "mevcut_kullanici_id": lambda: 1}
    return [sahteler[ad] for ad in inspect.signature(modul.router_olustur).parameters]


def _rotalar(rotalar):
    for r in rotalar:
        if isinstance(r, APIRoute):
            yield r
        elif getattr(r, "original_router", None) is not None:
            yield from _rotalar(r.original_router.routes)


@pytest.mark.parametrize("modul", [m for m, _ in UC_MODULLERI])
def test_ayrilan_modul_sunucuyu_ice_aktarmaz_dongusel_bagimlilik_olmaz(modul):
    assert not {a for a in _ice_aktarilanlar(modul) if a == "server.sunucu" or a.startswith("server.sunucu.")}


@pytest.mark.parametrize("modul, yontem, yol, yetki, kod", TUM_UCLAR)
def test_uc_kayitli_basari_kodu_dogru(modul, yontem, yol, yetki, kod):
    sema = sunucu.app.openapi()["paths"]
    assert yol in sema and yontem.lower() in sema[yol]
    yanitlar = sema[yol][yontem.lower()]["responses"]
    assert kod in yanitlar and ("201" in yanitlar) == (kod == "201")                # oluşturan uçlar 201, diğerleri 200


@pytest.mark.parametrize("modul, yontem, yol, yetki, kod", KORUMALI_UCLAR)
def test_korumali_uc_kimliksiz_istekte_401_doner(modul, yontem, yol, yetki, kod):
    assert TestClient(sunucu.app).request(yontem, re.sub(r"\{[^}]+\}", "1", yol)).status_code == 401


def test_herkese_acik_tek_uc_parola_sifirlama_talebidir_digerleri_kimlik_ister():
    acik = [(y, yol) for _, y, yol, yetki, _ in TUM_UCLAR if yetki is None]
    assert acik == [("POST", "/api/parola-sifirlama-talebi")]
    kayit = next(r for r in _rotalar(sunucu.app.routes) if r.path == "/api/parola-sifirlama-talebi")
    assert kayit.dependant.dependencies == []                                         # giriş yapamayan kullanıcı talep gönderebilmeli


@pytest.mark.parametrize("modul, ucler", UC_MODULLERI)
def test_router_her_ucun_yetkisini_dogru_turde_ve_sirayla_ister_yollar_ve_yontemler_ayni(modul, ucler):
    istenen = []
    yonlendirici = modul.router_olustur(*_sahte_bagimliliklar(modul, istenen))
    beklenen = [yetki for _, _, yetki, _ in ucler if yetki is not None]
    assert istenen == beklenen
    assert [type(x) for x in istenen] == [type(x) for x in beklenen]                  # Hepsi (tümü gerekir) ile düz demet (biri yeter) karışmamalı
    assert [(sorted(r.methods)[0], r.path) for r in yonlendirici.routes] == [(y, yol) for y, yol, _, _ in ucler]


@pytest.mark.parametrize("modul, ucler", UC_MODULLERI)
def test_kayitli_uclarin_yetki_parametresi_var_ham_fonksiyonda_yetki_bagimliligi_yok(modul, ucler):
    yonlendirici = modul.router_olustur(*_sahte_bagimliliklar(modul, []))
    assert len(modul.UCLAR) == len(ucler) == len(yonlendirici.routes)
    for r, (_, _, fonksiyon, parametre, yetki, _) in zip(yonlendirici.routes, modul.UCLAR):
        if yetki is False:                                                                # herkese açık uç: yetki parametresi yok
            assert parametre is None
            continue
        assert parametre in inspect.signature(r.endpoint).parameters
        assert inspect.signature(fonksiyon).parameters[parametre].default is None


def test_sunucuya_kayitli_gercek_uclarin_yetkileri_tabloyla_ayni():
    """Uygulamaya gerçekten bağlanan (bağımlılığı sahte olmayan) uçlarda izin adları tablodakiyle aynı olmalı."""
    def izinler(dep):
        bulunan = []
        for alt in dep.dependencies:
            c, ad = alt.call, getattr(alt.call, "__qualname__", "")
            if ad.startswith("izin_kontrol.") and c.__closure__:
                bulunan += [h.cell_contents for h in c.__closure__ if isinstance(h.cell_contents, str)]
            elif ad.startswith("izin_kontrol_tumu.") and c.__closure__:
                bulunan += [Hepsi(*sorted(x)) for h in c.__closure__ for x in [h.cell_contents] if isinstance(x, (tuple, list))]
            bulunan += izinler(alt)
        return bulunan
    gercek = {(sorted(r.methods - {"HEAD", "OPTIONS"})[0], r.path): izinler(r.dependant) for r in _rotalar(sunucu.app.routes)}
    for _, y, yol, yetki, _ in TUM_UCLAR:
        beklenen = [] if yetki is None else [Hepsi(*sorted(yetki)) if isinstance(yetki, Hepsi) else yetki]
        assert gercek[(y, yol)] == beklenen, (y, yol)


def test_sunucudaki_geriye_donuk_adlar_ayrilan_nesnelerle_aynidir():
    esleme = {
        kullanici_api: (
            "ROL_PASIF_ATAMA_MESAJI",
            "_siradaki_personel_kodu",
            "kullanici_olustur",
            "musait_kullanici_adi",
            "kullanici_ogrenci_kayit_durumu",
            "kullanici_rol_degistir",
            "YONETICI_PAROLASI_ENGEL_MESAJI",
            "kullanici_parola_sifirla",
            "DurumDegistirModeli",
            "kullanici_durum_degistir",
        ),
        oda_api: (
            "OdaYetkileriModeli",
            "psikolog_planli_randevulari_denetle",
            "etkinlik_oda_atama_kilitlerini_al",
            "oda_etkinlikli_odalari_denetle",
            "cihaz_rezervasyonlu_odalari_denetle",
            "_hedef_psikolog_kontrol",
            "psikolog_oda_yetkilerini_getir",
            "psikolog_oda_yetkilerini_guncelle",
            "oda_planli_kayit_sayilari",
            "oda_planli_randevu_sayilari",
            "oda_psikolog_atamalari",
            "oda_olustur",
            "psikolog_odalarini_getir",
            "odalari_listele",
            "cihaz_odalarini_listele",
            "oda_detay",
            "oda_guncelle",
            "aktif_psikologlari_listele",
        ),
        rol_api: (
            "rol_olustur",
            "SISTEM_ROLLERI",
            "rol_guncelle",
            "rol_sil",
            "_atanabilir_rolleri_getir",
            "olusturma_rolleri",
            "degistirme_rolleri",
            "rolleri_listele",
            "rol_yetki_ozeti",
            "rol_izin_matrisi_getir",
            "izin_ekle",
            "izin_duzenle",
        ),
        parola_talebi_api: (
            "PAROLA_TALEBI_ACIK_UST_SINIR",
            "PAROLA_TALEBI_ALINDI_MESAJI",
            "PAROLA_TALEBI_ZATEN_VAR_MESAJI",
            "PAROLA_TALEBI_KULLANICI_YOK_MESAJI",
            "PAROLA_TALEBI_HESAP_PASIF_MESAJI",
            "PAROLA_TALEBI_HESAP_YONETICI_MESAJI",
            "parola_sifirlama_talebi_olustur",
            "parola_sifirlama_taleplerini_listele",
            "parola_sifirlama_talebini_kapat",
        ),
        personel_api: (
            "personel_olustur",
            "personel_listele",
            "personel_olmayan_kullanicilari_listele",
            "personel_detay",
            "personel_guncelle",
        ),
    }
    for modul, adlar in esleme.items():
        for ad in adlar:
            assert getattr(sunucu, ad) is getattr(modul, ad), ad


def test_oda_yardimcilari_kullanici_modulunde_ayni_nesnedir():
    """Kullanıcı oluşturma/rol/durum değiştirme, oda kilidi ve denetim yardımcılarını oda modülünden alır (ikinci bir kopya yok)."""
    for ad in ("cihaz_rezervasyonlu_odalari_denetle", "etkinlik_oda_atama_kilitlerini_al", "oda_etkinlikli_odalari_denetle",
               "psikolog_planli_randevulari_denetle"):
        assert getattr(kullanici_api, ad) is getattr(oda_api, ad), ad


def test_rol_pasif_atama_mesaji_tek_tanim_ve_giris_mesajindan_ayri():
    assert kullanici_api.ROL_PASIF_ATAMA_MESAJI == "Seçilen rol pasif; pasif role kullanıcı atanamaz. Önce rolü aktif edin."
    assert sunucu.ROL_PASIF_GIRIS_MESAJI != sunucu.ROL_PASIF_ATAMA_MESAJI


def test_ayrilan_kod_sunucu_dosyasinda_yinelenmez():
    kaynak = (KOK / "server" / "sunucu.py").read_text(encoding="utf-8")
    for modul, _ in UC_MODULLERI:
        for ad, deger in vars(modul).items():
            if inspect.isfunction(deger) and deger.__module__ == modul.__name__ and ad != "router_olustur":
                assert f"def {ad}(" not in kaynak, ad
    for _, ucler in UC_MODULLERI:
        for yontem, yol, _, _ in ucler:
            assert f'@app.{yontem.lower()}("{yol}"' not in kaynak, (yontem, yol)
    for sabit in ("SISTEM_ROLLERI = ", "PAROLA_TALEBI_ACIK_UST_SINIR = ", "YONETICI_PAROLASI_ENGEL_MESAJI = ", "ROL_PASIF_ATAMA_MESAJI = "):
        assert sabit not in kaynak, sabit


@pytest.mark.parametrize("modul", [kullanici_api, oda_api, rol_api, parola_talebi_api, personel_api])
def test_yetki_tablosu_desteklenmeyen_deger_alirsa_kayit_sirasinda_patlar(modul, monkeypatch):
    """Yetki sütunu yönlendiricinin desteklemediği bir değere (ör. sayı) değiştirilirse kayıt sırasında patlamalı; yetki sessizce yok sayılmamalı."""
    metod, yol, fonksiyon, parametre, _, ek = modul.UCLAR[0]
    monkeypatch.setattr(modul, "UCLAR", [(metod, yol, fonksiyon, parametre, 12345, ek)])
    with pytest.raises(ValueError):
        modul.router_olustur(*_sahte_bagimliliklar(modul, []))


def test_hepsi_demetten_ayirt_edilir_ve_izinleri_korur():
    assert isinstance(Hepsi("A", "B"), tuple) and tuple(Hepsi("A", "B")) == ("A", "B")
    assert type(Hepsi("A")) is not tuple
