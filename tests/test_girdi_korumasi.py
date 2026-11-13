"""Bozuk girdiye karşı merkezi koruma: NUL karakter, taşan sayı, büyük gövde, veritabanı kural hataları, model sınırları.

Gerçek veritabanı kullanılmaz; veritabanı hataları taklit edilir (gerçek PostgreSQL ile deneme: test_girdi_fuzz_pg_quality.py).
"""
import asyncio
import importlib.util
import json
import os
from unittest.mock import MagicMock, patch

import psycopg2
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

import girdi_korumasi as gk
import guvenlik
import modeller
import sunucu
from sunucu import app, mevcut_kullanici_id


# ================================================================ mini uygulama (ara katman ve yakalayıcı denemesi)
def mini_uygulama():
    mini = FastAPI()
    mini.add_middleware(gk.NulVeSayiKorumasi)
    gk.merkezi_hata_yakalayicilari_kur(mini)

    @mini.post("/yankı")
    def yanki(veri: dict):
        return veri

    @mini.get("/sorgu")
    def sorgu(a: str = ""):
        return {"a": a}

    @mini.post("/metin", status_code=200)
    def metin(govde: str = ""):
        return {"tamam": True}

    @mini.get("/benzersiz-hata-http500")
    def http500_benzersiz():
        try:
            raise psycopg2.errors.UniqueViolation("duplicate key value violates unique constraint gizli_kisit")
        except Exception:
            raise HTTPException(status_code=500, detail="İşlem sırasında beklenmeyen bir sunucu hatası oluştu.")

    @mini.get("/yabanci-anahtar-http500")
    def http500_fk():
        try:
            raise psycopg2.errors.ForeignKeyViolation("insert or update violates foreign key")
        except Exception:
            raise HTTPException(status_code=500, detail="x") from None

    @mini.get("/nul-http500")
    def http500_nul():
        try:
            raise ValueError("A string literal cannot contain NUL (0x00) characters.")
        except Exception:
            raise HTTPException(status_code=500, detail="x")

    @mini.get("/baglamsiz-http500")
    def baglamsiz():
        raise HTTPException(status_code=500, detail="Kendi mesajım")

    @mini.get("/yabanci-hata-http500")
    def baska_hata():
        try:
            raise RuntimeError("beklenmedik")
        except Exception:
            raise HTTPException(status_code=500, detail="Genel mesaj")

    @mini.get("/ham-benzersiz")
    def ham_benzersiz():
        raise psycopg2.errors.UniqueViolation("duplicate key ... Key (seri_no)=(x) already exists.")

    @mini.get("/ham-yabanci")
    def ham_fk():
        raise psycopg2.errors.ForeignKeyViolation("insert or update on table violates foreign key")

    @mini.get("/ham-bilinmeyen")
    def ham_bilinmeyen():
        raise psycopg2.OperationalError('FATAL: password authentication failed for user "tkys" host=10.0.0.5')

    @mini.get("/bulunamadi")
    def bulunamadi():
        raise HTTPException(status_code=404, detail="Kayıt bulunamadı.")

    @mini.get("/yetkisiz")
    def yetkisiz():
        raise HTTPException(status_code=401, detail="Yetkisiz", headers={"WWW-Authenticate": "Bearer"})

    return mini


@pytest.fixture(scope="module")
def mini():
    return TestClient(mini_uygulama(), raise_server_exceptions=False)


# ================================================================ NUL karakter
@pytest.mark.parametrize("govde", [
    {"ad": "a\u0000b"},
    {"ic": {"ad": "x\u0000"}},
    {"liste": ["tamam", "kötü\u0000"]},
    {"derin": [{"a": [{"b": "\u0000"}]}]},
    {"anahtar\u0000": "değer"},
])
def test_json_icindeki_nul_karakter_422_ile_reddedilir(mini, govde):
    yanit = mini.post("/yankı", json=govde)
    assert yanit.status_code == 422 and yanit.json() == {"detail": gk.NUL_MESAJI}


@pytest.mark.parametrize("sorgu", ["?a=x%00y", "?a%00=1", "?b=1&a=%00"])
def test_sorgu_parametresindeki_nul_karakter_422_ile_reddedilir(mini, sorgu):
    yanit = mini.get("/sorgu" + sorgu)
    assert yanit.status_code == 422 and yanit.json() == {"detail": gk.NUL_MESAJI}


def test_nul_olmayan_girdi_etkilenmez_ve_govde_ucta_aynen_okunur(mini):
    govde = {"ad": "Çağlar Öğrenci 🙂", "liste": [1, 2, {"x": "y"}], "bos": None, "ondalik": 1.5}
    yanit = mini.post("/yankı", json=govde)
    assert yanit.status_code == 200 and yanit.json() == govde
    assert mini.get("/sorgu?a=merhaba").json() == {"a": "merhaba"}


def test_metin_olarak_yazilmis_ters_bolu_u0000_nul_sayilmaz(mini):
    yanit = mini.post("/yankı", json={"ad": "\\u0000"})                         # "\u0000" yazısı, gerçek NUL değil
    assert yanit.status_code == 200


# ================================================================ taşan sayılar
@pytest.mark.parametrize("sayi,beklenen", [
    (2_147_483_647, 200), (-2_147_483_648, 200), (0, 200),
    (2_147_483_648, 422), (-2_147_483_649, 422), (922_337_203_685_477_580, 422),
])
def test_tamsayi_sinirlari(mini, sayi, beklenen):
    assert mini.post("/yankı", json={"id": sayi}).status_code == beklenen


def test_ic_ice_ve_listedeki_tasan_sayi_da_yakalanir(mini):
    assert mini.post("/yankı", json={"liste": [1, 2, 2**40]}).status_code == 422
    assert mini.post("/yankı", json={"a": {"b": [{"c": -2**40}]}}).status_code == 422


def test_ondalikli_sayi_ve_mantiksal_deger_tamsayi_siniriyla_karistirilmaz(mini):
    assert mini.post("/yankı", json={"maliyet": 1e10, "dogru": True, "yanlis": False}).status_code == 200


# ================================================================ gövde boyutu ve biçim
def test_birer_mebibaytin_ustundeki_json_govde_413_ile_reddedilir(mini):
    yanit = mini.post("/yankı", content=b'{"a":"' + b"x" * (gk.EN_BUYUK_GOVDE_BAYT + 10) + b'"}', headers={"content-type": "application/json"})
    assert yanit.status_code == 413 and yanit.json() == {"detail": gk.BUYUK_GOVDE_MESAJI}


def test_sinira_siginan_govde_kabul_edilir(mini):
    veri = {"a": "x" * 1000}
    assert mini.post("/yankı", json=veri).json() == veri


def test_gecersiz_json_ara_katmanca_degil_uygulamanin_kendi_422_siyle_bildirilir(mini):
    yanit = mini.post("/yankı", content=b'{"a": ', headers={"content-type": "application/json"})
    assert yanit.status_code == 422 and yanit.json()["detail"][0]["type"] == "json_invalid"


def test_bos_govde_ve_json_olmayan_icerik_ara_katmandan_gecer(mini):
    assert mini.post("/yankı", content=b"", headers={"content-type": "application/json"}).status_code == 422   # uygulama bildirir
    assert mini.post("/metin", content=b"a\x00b", headers={"content-type": "text/plain"}).status_code in (200, 422)


def test_parcali_gelen_govde_birlestirilir_ve_denetlenir():
    alinan = {}

    async def uygulama(scope, receive, send):
        mesaj = await receive()
        alinan["govde"] = mesaj["body"]
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"tamam"})

    katman = gk.NulVeSayiKorumasi(uygulama)

    async def calistir(parcalar):
        kuyruk = [{"type": "http.request", "body": p, "more_body": i < len(parcalar) - 1} for i, p in enumerate(parcalar)]
        gonderilen = []

        async def al():
            return kuyruk.pop(0)

        async def gonder(m):
            gonderilen.append(m)

        scope = {"type": "http", "method": "POST", "path": "/", "query_string": b"", "headers": [(b"content-type", b"application/json")]}
        await katman(scope, al, gonder)
        return gonderilen[0]["status"]

    assert asyncio.run(calistir([b'{"a":', b' "b", ', b'"c": 1}'])) == 200
    assert alinan["govde"] == b'{"a": "b", "c": 1}'
    assert asyncio.run(calistir([b'{"a": 2147', b'483648}'])) == 422                 # parçalar birleşince taşan sayı


def test_http_disindaki_istekler_olduklari_gibi_gecer():
    cagrildi = []

    async def uygulama(scope, receive, send):
        cagrildi.append(scope["type"])

    asyncio.run(gk.NulVeSayiKorumasi(uygulama)({"type": "lifespan"}, None, None))
    assert cagrildi == ["lifespan"]


# ================================================================ veritabanı hatası çevirisi
@pytest.mark.parametrize("hata,durum", [
    (psycopg2.errors.UniqueViolation(), 409),
    (psycopg2.errors.ForeignKeyViolation(), 422),
    (psycopg2.errors.NotNullViolation(), 422),
    (psycopg2.errors.CheckViolation(), 422),
    (psycopg2.errors.StringDataRightTruncation(), 422),
    (psycopg2.errors.NumericValueOutOfRange(), 422),
    (psycopg2.errors.InvalidTextRepresentation(), 422),
    (psycopg2.errors.DatetimeFieldOverflow(), 422),
    (psycopg2.errors.ExclusionViolation(), 422),
])
def test_veritabani_hatalari_dogru_http_koduna_cevrilir(hata, durum):
    cevrilen = gk.veritabani_hatasini_cevir(hata)
    assert cevrilen is not None and cevrilen[0] == durum and isinstance(cevrilen[1], str) and len(cevrilen[1]) > 10


@pytest.mark.parametrize("hata", [psycopg2.OperationalError("x"), psycopg2.InterfaceError("x"), psycopg2.errors.DeadlockDetected(),
                                  RuntimeError("x"), ValueError("x")])
def test_tanimlanmayan_hatalar_cevrilmez(hata):
    assert gk.veritabani_hatasini_cevir(hata) is None


def test_mesajlar_veritabani_ayrintisi_icermez():
    for hata in (psycopg2.errors.UniqueViolation("Key (seri_no)=(SN-1) already exists"), psycopg2.errors.ForeignKeyViolation("table kullanicilar")):
        mesaj = gk.veritabani_hatasini_cevir(hata)[1]
        assert "seri_no" not in mesaj and "kullanicilar" not in mesaj and "Key" not in mesaj


# ================================================================ merkezi hata yakalayıcı
def test_http500_icindeki_benzersizlik_hatasi_409_olur_ve_ic_ayrinti_sizmaz(mini):
    yanit = mini.get("/benzersiz-hata-http500")
    assert yanit.status_code == 409 and "gizli_kisit" not in yanit.text and "zaten mevcut" in yanit.json()["detail"]


def test_from_none_ile_fırlatilan_http500_de_asil_hatadan_cevrilir(mini):
    yanit = mini.get("/yabanci-anahtar-http500")
    assert yanit.status_code == 422 and "bulunamadı" in yanit.json()["detail"]


def test_http500_icindeki_nul_hatasi_422_olur(mini):
    yanit = mini.get("/nul-http500")
    assert yanit.status_code == 422 and yanit.json() == {"detail": gk.NUL_MESAJI}


def test_nedeni_olmayan_ya_da_tanimsiz_http500_oldugu_gibi_kalir(mini):
    assert mini.get("/baglamsiz-http500").status_code == 500 and mini.get("/baglamsiz-http500").json() == {"detail": "Kendi mesajım"}
    assert mini.get("/yabanci-hata-http500").status_code == 500 and mini.get("/yabanci-hata-http500").json() == {"detail": "Genel mesaj"}


def test_uctan_geri_firlatilan_ham_veritabani_hatalari_cevrilir(mini):
    benzersiz = mini.get("/ham-benzersiz")
    assert benzersiz.status_code == 409 and "seri_no" not in benzersiz.text
    assert mini.get("/ham-yabanci").status_code == 422


def test_tanimsiz_ham_veritabani_hatasi_json_500_olur_ve_baglanti_bilgisi_sizmaz(mini):
    yanit = mini.get("/ham-bilinmeyen")
    assert yanit.status_code == 500 and yanit.json() == {"detail": gk.GENEL_HATA_MESAJI}
    assert "password" not in yanit.text and "10.0.0.5" not in yanit.text and "tkys" not in yanit.text


def test_diger_http_hatalari_degismez(mini):
    assert mini.get("/bulunamadi").status_code == 404 and mini.get("/bulunamadi").json() == {"detail": "Kayıt bulunamadı."}
    yetkisiz = mini.get("/yetkisiz")
    assert yetkisiz.status_code == 401 and yetkisiz.headers.get("www-authenticate") == "Bearer"


def test_asil_hata_zincirde_uzaktaki_nedeni_bulur_ve_donguye_girmez():
    ic = psycopg2.errors.UniqueViolation("x")
    orta = RuntimeError("orta")
    orta.__cause__ = ic
    dis = HTTPException(status_code=500, detail="x")
    dis.__context__ = orta
    assert gk._asil_hata(dis) is ic
    a, b = RuntimeError("a"), RuntimeError("b")
    a.__context__, b.__context__ = b, a
    assert gk._asil_hata(a) is None


# ================================================================ gerçek uygulamada
@pytest.fixture
def istemci():
    app.dependency_overrides[mevcut_kullanici_id] = lambda: 5
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.pop(mevcut_kullanici_id, None)


def izinli_baglanti():
    """İzin kontrolünü geçen, başka hiçbir veri döndürmeyen sahte bağlantı."""
    conn = MagicMock()
    conn.cursor.return_value.fetchone.return_value = (1,)
    return conn


def veritabani_taklidi(hata, izin=True):
    conn = MagicMock()
    c = conn.cursor.return_value
    c.fetchone.side_effect = [(1,), ("Kullanima_Hazir",)] if izin else [None]
    sorgular = []

    def calistir(sorgu, *a, **k):
        sorgular.append(sorgu)
        if str(sorgu).lstrip().upper().startswith(("UPDATE", "INSERT")):
            raise hata
    c.execute.side_effect = calistir
    return conn


def test_gercek_uygulamada_cihaz_seri_no_cakismasi_500_degil_409_olur(istemci):
    hata = psycopg2.errors.UniqueViolation('duplicate key value violates unique constraint "cihazlar_seri_no_key"')
    with patch("sunucu.psycopg2.connect", return_value=veritabani_taklidi(hata)):
        yanit = istemci.patch("/api/cihazlar/1", json={"seri_no": "SN-1"})
    assert yanit.status_code == 409 and "cihazlar_seri_no_key" not in yanit.text


def test_gercek_uygulamada_login_nul_karakteri_db_ye_ulasmadan_reddedilir(istemci):
    with patch("sunucu.psycopg2.connect") as baglan:
        yanit = istemci.post("/api/login", json={"kullanici_adi": "a\u0000b", "parola": "x"})
    assert yanit.status_code == 422 and not baglan.called


def test_gercek_uygulamada_tasan_sayi_db_ye_ulasmadan_reddedilir(istemci):
    with patch("sunucu.psycopg2.connect") as baglan:
        yanit = istemci.post("/api/odalar", json={"oda_adi": "Oda", "kapasite": 2**40})
    assert yanit.status_code == 422 and not baglan.called


def test_izin_ekle_adi_olmayan_ya_da_cok_uzun_istegi_422_ile_reddeder(istemci):
    for gecersiz in ({}, {"izin_adi": ""}, {"izin_adi": "   "}, {"izin_adi": 5}, {"izin_adi": "x" * 101}, {"izin_adi": None}):
        conn = izinli_baglanti()
        with patch("sunucu.psycopg2.connect", return_value=conn):
            yanit = istemci.post("/api/izinler", json=gecersiz)
        assert yanit.status_code == 422, gecersiz
        assert not any("INSERT INTO izinler" in str(c.args[0]) for c in conn.cursor.return_value.execute.call_args_list), gecersiz


# ================================================================ model sınırları
def faaliyet(**kw):
    return modeller.FaaliyetKayitModeli(**{"ogrenci_id": 1, "faaliyet_id": 1, "birim_id": 1, "miktar": 1, **kw})


@pytest.mark.parametrize("alan", ["ogrenci_id", "faaliyet_id", "birim_id"])
def test_faaliyet_kaydinda_kimlikler_pozitif_olmali(alan):
    for gecersiz in (0, -1):
        with pytest.raises(ValidationError):
            faaliyet(**{alan: gecersiz})
    assert faaliyet(**{alan: 7}) is not None


@pytest.mark.parametrize("miktar,gecerli", [(0, False), (-3, False), (1, True), (10000, True), (10001, False)])
def test_faaliyet_miktari_arayuzdeki_sinirla_ayni(miktar, gecerli):
    if gecerli:
        assert faaliyet(miktar=miktar).miktar == miktar
    else:
        with pytest.raises(ValidationError):
            faaliyet(miktar=miktar)


def kayit_sorgusu_var_mi(conn, parca):
    return any(parca in str(c.args[0]) for c in conn.cursor.return_value.execute.call_args_list)


def test_faaliyet_kaydi_miktar_sifir_http_422_verir_ve_kayit_yapilmaz(istemci):
    conn = izinli_baglanti()
    with patch("sunucu.psycopg2.connect", return_value=conn):
        yanit = istemci.post("/api/faaliyet-kayitlari", json={"ogrenci_id": 1, "faaliyet_id": 1, "birim_id": 1, "miktar": 0})
    assert yanit.status_code == 422 and not kayit_sorgusu_var_mi(conn, "INSERT INTO ogrenci_faaliyet_takip")


def test_kalibrasyon_metin_alanlari_veritabanindaki_100_karakter_siniriyla_sinirlidir():
    temel = dict(cihaz_id=1, kalibrasyon_yapan_kurum="K", gecerlilik_tarihi="2027-01-01", sertifika_no="S",
                 kalibrasyon_baslangic_tarihi="2026-01-01", kalibrasyon_bitis_tarihi="2026-01-02")
    assert modeller.KalibrasyonOlusturModeli(**temel) is not None
    for alan in ("kalibrasyon_yapan_kurum", "sertifika_no"):
        for gecersiz in ("", "x" * 101):
            with pytest.raises(ValidationError):
                modeller.KalibrasyonOlusturModeli(**{**temel, alan: gecersiz})
            with pytest.raises(ValidationError):
                modeller.KalibrasyonGuncelleModeli(**{alan: gecersiz})
    with pytest.raises(ValidationError):
        modeller.KalibrasyonOlusturModeli(**{**temel, "cihaz_id": 0})
    assert modeller.KalibrasyonGuncelleModeli().sertifika_no is None            # güncellemede alan atlanabilir


def test_rol_adi_bos_ya_da_50_karakterden_uzun_olamaz():
    assert modeller.RolModeli(rol_adi="Müdür Yardımcısı").rol_adi == "Müdür Yardımcısı"
    for gecersiz in ("", "x" * 51):
        with pytest.raises(ValidationError):
            modeller.RolModeli(rol_adi=gecersiz)


# ---------------------------------------------------------------- tarih ve saat
ZAMANLI = [modeller.RandevuOlusturModeli, modeller.DanismaGorevOlusturModeli, modeller.DanismaGorevDuzenleModeli]


def zamanli_kur(sinif, bas, bit):
    ek = {"danisan_kod_id": "DAN-1", "psikolog_id": 1, "oda_id": 1} if sinif is modeller.RandevuOlusturModeli else \
         {"ogrenci_id": 1} if sinif is modeller.DanismaGorevOlusturModeli else {}
    return sinif(baslangic_zamani=bas, bitis_zamani=bit, **ek)


@pytest.mark.parametrize("sinif", ZAMANLI)
def test_zaman_alanlari_sayi_kabul_etmez_metin_ya_da_datetime_kabul_eder(sinif):
    for sayi in (0, -1, 2**31, 1.5, True):
        with pytest.raises(ValidationError):
            zamanli_kur(sinif, sayi, "2030-01-02T10:00:00")
    sonuc = zamanli_kur(sinif, "2030-01-02T10:00:00", "2030-01-02T11:00:00")
    assert sonuc.baslangic_zamani.year == 2030 and sonuc.baslangic_zamani.tzinfo is None


@pytest.mark.parametrize("sinif", ZAMANLI)
def test_randevu_ve_danisma_modelleri_saat_dilimli_zamani_reddeder(sinif):
    with pytest.raises(ValidationError):
        zamanli_kur(sinif, "2030-01-02T10:00:00+03:00", "2030-01-02T11:00:00+03:00")


@pytest.mark.parametrize("bozuk", ["abc", "", "2030-13-45T99:00:00", "0000-00-00"])
def test_bozuk_tarih_metni_422_dogurur(bozuk):
    with pytest.raises(ValidationError):
        zamanli_kur(modeller.RandevuOlusturModeli, bozuk, "2030-01-02T11:00:00")


def test_z_soneki_saat_dilimsiz_sayilir_geriye_donuk_uyum():
    sonuc = zamanli_kur(modeller.RandevuOlusturModeli, "2030-01-02T10:00:00Z", "2030-01-02T11:00:00Z")
    assert sonuc.baslangic_zamani.tzinfo is None


def rezervasyon(bas, bit):
    return modeller.RezervasyonOlusturModeli(cihaz_id=1, baslangic_zamani=bas, bitis_zamani=bit)


def test_rezervasyon_saat_dilimli_zamani_destekler_ama_ikisi_ayni_bicimde_olmali():
    assert rezervasyon("2030-01-02T10:00:00+03:00", "2030-01-02T11:00:00+03:00").baslangic_zamani.tzinfo is not None
    assert rezervasyon("2030-01-02T10:00:00", "2030-01-02T11:00:00").baslangic_zamani.tzinfo is None
    for bas, bit in (("2030-01-02T10:00:00+03:00", "2030-01-02T11:00:00"), ("2030-01-02T10:00:00", "2030-01-02T11:00:00+03:00")):
        with pytest.raises(ValidationError, match="aynı biçimde"):
            rezervasyon(bas, bit)


def test_rezervasyon_sayi_zaman_kabul_etmez_ve_karisik_biçim_http_422_verir(istemci):
    for govde in ({"cihaz_id": 1, "baslangic_zamani": 0, "bitis_zamani": "2030-01-02T10:00:00"},
                  {"cihaz_id": 1, "baslangic_zamani": "2030-01-02T10:00:00+03:00", "bitis_zamani": "2030-01-02T11:00:00"}):
        conn = izinli_baglanti()
        with patch("sunucu.psycopg2.connect", return_value=conn):
            yanit = istemci.post("/api/rezervasyonlar", json=govde)
        assert yanit.status_code == 422 and not kayit_sorgusu_var_mi(conn, "INSERT INTO cihaz_rezervasyonlari")


# ================================================================ JWT_SECRET asgari uzunluk
def guvenlik_yukle(gizli):
    spec = importlib.util.spec_from_file_location("guvenlik_uzunluk_denemesi", guvenlik.__file__)
    modul = importlib.util.module_from_spec(spec)
    with patch.dict(os.environ, {"JWT_SECRET": gizli}), patch("dotenv.load_dotenv", return_value=False):
        spec.loader.exec_module(modul)
    return modul


@pytest.mark.parametrize("gizli", ["a", "kisa_anahtar", "x" * 31])
def test_32_karakterden_kisa_jwt_anahtari_sunucuyu_baslatmaz(gizli):
    with pytest.raises(RuntimeError, match="en az 32 karakter"):
        guvenlik_yukle(gizli)


@pytest.mark.parametrize("gizli", ["x" * 32, "y" * 64])
def test_en_az_32_karakterlik_anahtar_kabul_edilir(gizli):
    assert guvenlik_yukle(gizli).JWT_SECRET == gizli


def test_kisa_anahtar_hatasi_uzunlugu_ve_uretim_komutunu_soyler_anahtarin_kendisini_yazmaz():
    gizli = "cok_gizli_kisa"
    with pytest.raises(RuntimeError) as hata:
        guvenlik_yukle(gizli)
    mesaj = str(hata.value)
    assert f"şu an {len(gizli)}" in mesaj and "secrets.token_urlsafe" in mesaj and gizli not in mesaj


def test_eksik_anahtar_mesaji_degismedi():
    with pytest.raises(RuntimeError, match="JWT_SECRET ortam değişkeni tanımlı değil"):
        guvenlik_yukle("")
