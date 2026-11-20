"""Parola politikası, rol hiyerarşisi, güvenlik başlıkları ve TLS ayarları (veritabanı gerektirmez)."""
import asyncio

import pytest

from server.guvenlik_basliklari import GuvenlikBasliklari
from server.parola_politikasi import EN_AZ_UZUNLUK, parola_ihlalleri
from server.rol_hiyerarsisi import ROL_SEVIYELERI, hiyerarsi_ihlali_var_mi, rol_seviyesi


# ---------------- parola politikası ----------------
@pytest.mark.parametrize("parola", ["Guzel-Parola-2026", "kedi köpek 4 kuş", "Zx9!kLm2pQ"])
def test_gecerli_parolalar_kabul_edilir(parola):
    assert parola_ihlalleri(parola, "ayse") == []


@pytest.mark.parametrize("parola, parca", [
    ("Kisa1", "en az"),
    ("sadeceharflerburada", "rakam"),
    ("12345678901234", "harf"),
    ("password1234", "yaygın"),
    ("Password123", "yaygın"),           # yaygın parola + rakam
    ("aaaaaaaaaa1", "yaygın"),           # çok az farklı karakter
    ("AyseYilmaz2026!", "kullanıcı adı"),
])
def test_zayif_parolalar_reddedilir(parola, parca):
    mesajlar = " ".join(parola_ihlalleri(parola, "ayse" if "Ayse" in parola else "bulut"))
    assert parca in mesajlar.lower(), mesajlar


def test_kullanici_adi_cok_kisaysa_parola_icinde_aranmaz():
    assert parola_ihlalleri("Ab-123-Kalem-9", "ab") == []


def test_istemci_ve_sunucu_ayni_asgari_uzunlugu_kullanir():
    from client.parola_kurallari import EN_AZ_UZUNLUK as istemci_uzunlugu
    assert istemci_uzunlugu == EN_AZ_UZUNLUK


# ---------------- rol hiyerarşisi ----------------
def test_seviyeler_sirali_ve_bilinmeyen_rol_en_dusuk():
    assert ROL_SEVIYELERI["ADMIN"] > ROL_SEVIYELERI["MUDUR"] > ROL_SEVIYELERI["MEMUR"] > ROL_SEVIYELERI["PSIKOLOG"]
    assert rol_seviyesi("OZEL_ROL") < rol_seviyesi("DANISMA_OGRENCISI")
    assert rol_seviyesi("danisma_ogrencisi") == rol_seviyesi("DANISMA OGRENCISI")      # büyük/küçük harf ve alt çizgi farkı önemsenmez


@pytest.mark.parametrize("yapan, hedefler, beklenen", [
    ("MUDUR", ("PSIKOLOG", "MEMUR"), False),
    ("MUDUR", ("MUDUR",), True),                 # eşit seviye
    ("MEMUR", ("MUDUR",), True),                 # üst seviye
    ("MEMUR", ("PSIKOLOG", "MUDUR"), True),      # biri bile üstteyse engellenir
    ("MEMUR", ("PSIKOLOG",), False),
    ("ADMIN", ("MUDUR", "MEMUR"), False),        # ADMIN hiyerarşiye takılmaz
    ("PSIKOLOG", (None,), False),
    ("OZEL_ROL", ("DANISMA_OGRENCISI",), True),  # bilinmeyen rol en altta
])
def test_hiyerarsi_kurali(yapan, hedefler, beklenen):
    assert hiyerarsi_ihlali_var_mi(yapan, *hedefler) is beklenen


# ---------------- güvenlik başlıkları ----------------
def _calistir(scope):
    gonderilen = []

    async def uygulama(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": [(b"content-type", b"text/plain")]})
        await send({"type": "http.response.body", "body": b"ok"})

    async def gonder(mesaj):
        gonderilen.append(mesaj)

    asyncio.run(GuvenlikBasliklari(uygulama)(scope, None, gonder))
    return dict(gonderilen[0]["headers"])


def test_https_isteginde_hsts_ve_nosniff_eklenir():
    basliklar = _calistir({"type": "http", "scheme": "https", "headers": []})
    assert basliklar[b"strict-transport-security"].startswith(b"max-age=")
    assert basliklar[b"x-content-type-options"] == b"nosniff"


def test_http_isteginde_hsts_eklenmez():
    basliklar = _calistir({"type": "http", "scheme": "http", "headers": []})
    assert b"strict-transport-security" not in basliklar and basliklar[b"x-content-type-options"] == b"nosniff"


def test_vekil_basligina_yalniz_acikca_guvenilirse_inanilir(monkeypatch):
    scope = {"type": "http", "scheme": "http", "headers": [(b"x-forwarded-proto", b"https")]}
    assert b"strict-transport-security" not in _calistir(scope)             # varsayılan: sahteleyebilir, güvenilmez
    monkeypatch.setenv("TKYS_GUVENILIR_VEKIL", "1")
    assert b"strict-transport-security" in _calistir(scope)


# ---------------- TLS ayarları (sunucu başlatıcı) ----------------
def test_tls_dosyalari_verilirse_uvicorn_komutuna_eklenir(tmp_path, monkeypatch):
    from scripts.windows import sunucu_baslat as b
    sertifika, anahtar = tmp_path / "s.pem", tmp_path / "k.pem"
    sertifika.write_text("x"); anahtar.write_text("y")
    monkeypatch.setenv("TKYS_SSL_CERTFILE", str(sertifika))
    monkeypatch.setenv("TKYS_SSL_KEYFILE", str(anahtar))
    komut = b.sunucu_komutu("0.0.0.0", 8443)
    assert komut[-4:] == ["--ssl-certfile", str(sertifika), "--ssl-keyfile", str(anahtar)]


def test_tls_icin_yalniz_biri_ya_da_olmayan_dosya_acik_hatayla_durur(tmp_path, monkeypatch):
    from scripts.windows import sunucu_baslat as b
    monkeypatch.setenv("TKYS_SSL_CERTFILE", str(tmp_path / "yok.pem"))
    monkeypatch.delenv("TKYS_SSL_KEYFILE", raising=False)
    with pytest.raises(SystemExit, match="birlikte"):
        b.tls_ayarlari()
    monkeypatch.setenv("TKYS_SSL_KEYFILE", str(tmp_path / "yok2.pem"))
    with pytest.raises(SystemExit, match="bulunamadı"):
        b.tls_ayarlari()


def test_tls_yoksa_komut_eskisi_gibi(monkeypatch):
    from scripts.windows import sunucu_baslat as b
    monkeypatch.delenv("TKYS_SSL_CERTFILE", raising=False)
    monkeypatch.delenv("TKYS_SSL_KEYFILE", raising=False)
    assert "--ssl-certfile" not in b.sunucu_komutu("0.0.0.0", 8000)
