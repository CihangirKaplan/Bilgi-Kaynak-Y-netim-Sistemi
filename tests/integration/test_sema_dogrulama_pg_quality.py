"""Gerçek PostgreSQL: scripts/sema_dogrula.py gerçek bozulmaları yakalar, sağlam şemada sessiz kalır.

Bu test CI'daki "PostgreSQL Entegrasyon Testleri" işinde (alembic upgrade head sonrası) çalışır.
Sağlam veritabanı "uyumlu" çıkmalı; sütun/kural/indeks/tetikleyici/tablo silinince, tip değişince, enum değeri eksilince
ya da alembic sürümü geride kalınca araç bunu adıyla bildirmeli. Gerçek bir hatanın birebir benzeri de denenir: sürüm
"güncel" görünürken sütunların eksik olması (atlanmış migration).
"""

import importlib.util
import os
from pathlib import Path
from uuid import uuid4

import psycopg2
import pytest
from psycopg2 import sql

from server.sunucu import VT_AYARLARI

KOK = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("sema_dogrula_pg", KOK / "scripts" / "sema_dogrula.py")
sd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sd)


# conftest.py'deki genel güvenlik kilidi, testlerde psycopg2.connect'i YALNIZCA crkys_alembic_test'e izin verecek biçimde değiştirir.
# Bu dosya ise doğası gereği kendi ürettiği geçici veritabanlarına bağlanır (aracın ve testin işi budur). Bu yüzden kilidin yerine
# aşağıdaki DAHA DAR kural geçer: yalnızca yerel sunucu; yalnızca "postgres" (CREATE/DROP için), crkys_alembic_test ve
# "crkys_sema_" önekli geçici veritabanları. Canlı veritabanına (crkys) bağlanmak bu dosyada da imkânsızdır.
_ORIJINAL_BAGLAN = psycopg2.connect               # modül yüklenirken alınır; o an kilit henüz devrede değildir
_YEREL_HOSTLAR = {"localhost", "127.0.0.1", "::1", ""}
_IZINLI_VERITABANLARI = {"postgres", "crkys_alembic_test"}
_IZINLI_ONEK = "crkys_sema_"


def _dar_kilitli_baglan(*args, **kwargs):
    if args or kwargs.get("dsn"):
        raise RuntimeError("Guvenlik engeli: DSN ile baglantiya izin verilmiyor.")
    ad = str(kwargs.get("dbname") or "")
    host = str(kwargs.get("host") or "").lower().strip()
    if host not in _YEREL_HOSTLAR:
        raise RuntimeError("Guvenlik engeli: Yerel olmayan PostgreSQL sunucusu.")
    if ad not in _IZINLI_VERITABANLARI and not ad.startswith(_IZINLI_ONEK):
        raise RuntimeError(f"Guvenlik engeli: '{ad}' veritabanina bu testte baglanilamaz.")
    return _ORIJINAL_BAGLAN(**kwargs)


@pytest.fixture(autouse=True)
def dar_guvenlik_kilidi(monkeypatch, postgresql_test_guvenligi):
    """conftest'teki kilidin ARDINDAN çalışır (ona bağımlıdır) ve onu bu dosyaya özgü dar kuralla değiştirir."""
    monkeypatch.setattr(psycopg2, "connect", _dar_kilitli_baglan)


def _dogru_veritabani(imlec):
    # Yanlış veritabanında çalışmayı kesinlikle engelle.
    assert os.getenv("TKYS_PG_TEST_ONAY") == "EVET"
    assert VT_AYARLARI["dbname"] == "crkys_alembic_test"
    imlec.execute("SELECT current_database()")
    assert imlec.fetchone()[0] == "crkys_alembic_test"


YONETICI = VT_AYARLARI["user"]
PAROLA = VT_AYARLARI["password"]
HOST = VT_AYARLARI["host"]
PORT = VT_AYARLARI["port"]
BAGLANTI = {"user": YONETICI, "password": PAROLA, "host": HOST, "port": PORT}


def _calistir(veritabani, *sorgular):
    baglanti = psycopg2.connect(dbname=veritabani, **BAGLANTI)
    baglanti.autocommit = True
    try:
        for sorgu in sorgular:
            baglanti.cursor().execute(sorgu)
    finally:
        baglanti.close()


def _izi_al(veritabani):
    baglanti = psycopg2.connect(dbname=veritabani, **BAGLANTI)
    try:
        return sd.parmak_izi(baglanti.cursor())
    finally:
        baglanti.close()


def _surumler(veritabani):
    baglanti = psycopg2.connect(dbname=veritabani, **BAGLANTI)
    try:
        return sd.veritabani_surumleri(baglanti.cursor())
    finally:
        baglanti.close()


def _sema_veritabanlari(onek):
    baglanti = psycopg2.connect(dbname="postgres", **BAGLANTI)
    try:
        imlec = baglanti.cursor()
        imlec.execute("SELECT datname FROM pg_database WHERE datname LIKE %s", (onek + "%",))
        return [satir[0] for satir in imlec.fetchall()]
    finally:
        baglanti.close()


@pytest.fixture(scope="module")
def sablon():
    """Migration'larla sıfırdan kurulmuş şablon veritabanının adı. Her bozma denemesi ondan kopya alır (hızlı)."""
    baglanti = psycopg2.connect(dbname=VT_AYARLARI["dbname"], **BAGLANTI)
    try:
        _dogru_veritabani(baglanti.cursor())
    finally:
        baglanti.close()
    with sd.gecici_sema_veritabani(YONETICI, PAROLA, HOST, PORT, on_ek="crkys_sema_sablon") as (ad, _):
        yield ad


@pytest.fixture(scope="module")
def referans(sablon):
    return _izi_al(sablon)


@pytest.fixture
def kopya(sablon):
    """Şablondan taze bir kopya (bozulmaya hazır). Test bitince silinir."""
    ad = f"crkys_sema_test_{uuid4().hex[:8]}"
    yonetim = psycopg2.connect(dbname="postgres", **BAGLANTI)
    yonetim.autocommit = True
    try:
        yonetim.cursor().execute(
            sql.SQL("CREATE DATABASE {} TEMPLATE {}").format(sql.Identifier(ad), sql.Identifier(sablon))
        )
        yield ad
    finally:
        yonetim.cursor().execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(ad)))
        yonetim.close()


# ---------------------------------------------------------------- sağlam şema
def test_ci_veritabani_migrationlarin_urettigi_semayla_ayni(referans):
    """alembic upgrade head sonrası hazırlanan test veritabanı sıfırdan kurulmuşla aynı olmalı."""
    sonuc = sd.karsilastir(referans, _izi_al(VT_AYARLARI["dbname"]))
    assert not sonuc.sorunlu, f"eksik={sonuc.eksik} farklı={sonuc.farkli}"
    assert _surumler(VT_AYARLARI["dbname"]) == sd.kodun_surumleri()


def test_sablonun_kopyasi_tam_olarak_ayni_sema(kopya, referans):
    sonuc = sd.karsilastir(referans, _izi_al(kopya))
    assert not (sonuc.eksik or sonuc.fazla or sonuc.farkli or sonuc.ayrinti)


def test_referans_onemli_nesneleri_gercekten_iceriyor(referans):
    """Karşılaştırmanın boş bir kümeyi 'aynı' saymadığını garanti eder."""
    assert ("tablo", "randevular") in referans
    assert ("kolon", "randevular.iptal_nedeni") in referans
    assert ("kisit", "randevular.randevular_iptal_nedeni_gecerli") in referans
    assert ("indeks", "kullanicilar.ix_kullanicilar_rol_id") in referans
    assert ("tetikleyici", "denetim_kayitlari.denetim_kayitlari_degistirilemez") in referans
    assert ("enum", "denetim_olay_turu") in referans
    assert len(referans) > 300


# ---------------------------------------------------------------- gerçek bozulmalar
EKSIK_DENEMELERI = [
    ("sutun silindi", "ALTER TABLE randevular DROP COLUMN iptal_nedeni CASCADE", ("kolon", "randevular.iptal_nedeni")),
    ("kural silindi", "ALTER TABLE randevular DROP CONSTRAINT randevular_iptal_nedeni_gecerli",
     ("kisit", "randevular.randevular_iptal_nedeni_gecerli")),
    ("indeks silindi", "DROP INDEX ix_kullanicilar_rol_id", ("indeks", "kullanicilar.ix_kullanicilar_rol_id")),
    ("tetikleyici silindi", "DROP TRIGGER denetim_kayitlari_degistirilemez ON denetim_kayitlari",
     ("tetikleyici", "denetim_kayitlari.denetim_kayitlari_degistirilemez")),
    ("tablo silindi", "DROP TABLE cihaz_arizalari CASCADE", ("tablo", "cihaz_arizalari")),
]


@pytest.mark.parametrize("ad,bozma,beklenen", EKSIK_DENEMELERI, ids=[d[0] for d in EKSIK_DENEMELERI])
def test_eksik_nesne_adiyla_yakalanir(kopya, referans, ad, bozma, beklenen):
    _calistir(kopya, bozma)
    sonuc = sd.karsilastir(referans, _izi_al(kopya))
    assert beklenen in sonuc.eksik
    assert sonuc.sorunlu is True


FARKLI_DENEMELERI = [
    ("sutun tipi degisti", "ALTER TABLE randevular ALTER COLUMN iptal_notu TYPE VARCHAR(200)", ("kolon", "randevular.iptal_notu")),
    ("not null kalkti", "ALTER TABLE odalar ALTER COLUMN oda_adi DROP NOT NULL", ("kolon", "odalar.oda_adi")),
    ("enum degeri eklendi", "ALTER TYPE denetim_olay_turu ADD VALUE 'KOTU_DEGER'", ("enum", "denetim_olay_turu")),
]


@pytest.mark.parametrize("ad,bozma,beklenen", FARKLI_DENEMELERI, ids=[d[0] for d in FARKLI_DENEMELERI])
def test_yapisal_fark_yakalanir(kopya, referans, ad, bozma, beklenen):
    _calistir(kopya, bozma)
    sonuc = sd.karsilastir(referans, _izi_al(kopya))
    assert beklenen in sonuc.farkli
    assert sonuc.sorunlu is True


def test_fazla_sutun_sorun_degil_uyari(kopya, referans):
    _calistir(kopya, "ALTER TABLE odalar ADD COLUMN eski_surumden_kalan TEXT")
    sonuc = sd.karsilastir(referans, _izi_al(kopya))
    assert ("kolon", "odalar.eski_surumden_kalan") in sonuc.fazla
    assert sonuc.sorunlu is False


def test_varsayilan_deger_farki_yalnizca_ayrinti(kopya, referans):
    _calistir(kopya, "ALTER TABLE randevular ALTER COLUMN iptal_notu SET DEFAULT 'x'")
    sonuc = sd.karsilastir(referans, _izi_al(kopya))
    assert ("kolon", "randevular.iptal_notu") in sonuc.ayrinti
    assert sonuc.sorunlu is False and not sonuc.farkli


# ---------------------------------------------------------------- uçtan uca (dogrula)
def _dogrula(veritabani, ayrinti=False):
    return sd.dogrula(veritabani, BAGLANTI, YONETICI, PAROLA, ayrinti)


def test_dogrula_saglam_sema_icin_basarili_der(kopya):
    satirlar, basarili = _dogrula(kopya)
    assert basarili is True and "ŞEMA UYUMLU" in "\n".join(satirlar)


def test_dogrula_atlanmis_migrationi_birebir_yakalar(kopya):
    """Gerçek olayın benzeri: alembic sürümü güncel ama iptal sütunları ve 4 kuralı yok."""
    _calistir(
        kopya,
        "ALTER TABLE randevular DROP CONSTRAINT randevular_diger_icin_not_zorunlu, "
        "DROP CONSTRAINT randevular_iptal_notu_nedene_bagli, DROP CONSTRAINT randevular_iptal_nedeni_yalniz_iptalde, "
        "DROP CONSTRAINT randevular_iptal_nedeni_gecerli, DROP COLUMN iptal_notu, DROP COLUMN iptal_nedeni",
    )
    assert _surumler(kopya) == sd.kodun_surumleri()                  # sürüm kaydı "güncel": alembic current bunu göstermezdi
    satirlar, basarili = _dogrula(kopya)
    metin = "\n".join(satirlar)
    assert basarili is False
    assert "TUTARSIZ ŞEMA" in metin and "randevular.iptal_nedeni" in metin and "randevular.iptal_notu" in metin
    assert "randevular_iptal_nedeni_gecerli" in metin


def test_dogrula_eski_alembic_surumunu_bildirir(kopya):
    _calistir(kopya, "UPDATE alembic_version SET version_num = 'c3d8e5a1f7b2'")
    satirlar, basarili = _dogrula(kopya)
    metin = "\n".join(satirlar)
    assert basarili is False and "python -m alembic upgrade head" in metin


def test_dogrula_ayrinti_secenegi_ayrinti_farkini_listeler(kopya):
    _calistir(kopya, "ALTER TABLE randevular ALTER COLUMN iptal_notu SET DEFAULT 'x'")
    ozet, basarili_ozet = _dogrula(kopya)
    ayrintili, basarili_ayrintili = _dogrula(kopya, ayrinti=True)
    assert basarili_ozet is True and basarili_ayrintili is True
    assert "AYRINTI FARKI" not in "\n".join(ozet) and "AYRINTI FARKI" in "\n".join(ayrintili)


def test_dogrula_canli_veritabaninda_hicbir_sey_degistirmez(kopya):
    _calistir(kopya, "ALTER TABLE randevular DROP COLUMN iptal_nedeni CASCADE")
    once = _izi_al(kopya)
    _dogrula(kopya)
    assert _izi_al(kopya) == once


def test_gecici_referans_veritabanlari_geride_birakilmaz(kopya):
    _dogrula(kopya)
    assert _sema_veritabanlari("crkys_sema_referans_") == []


def test_gecici_veritabani_hata_olsa_da_silinir(monkeypatch):
    class Basarisiz:
        returncode = 1
        stderr = "alembic patladı"
        stdout = ""

    monkeypatch.setattr(sd.subprocess, "run", lambda *a, **k: Basarisiz())
    with pytest.raises(sd.SemaDogrulamaHatasi, match="alembic patladı"):
        sd.referans_uret(YONETICI, PAROLA, HOST, PORT)
    assert _sema_veritabanlari("crkys_sema_referans_") == []


# ---------------------------------------------------------------- bu dosyanın güvenlik kilidi
def test_kilit_canli_veritabanina_baglanmayi_engeller():
    with pytest.raises(RuntimeError, match="baglanilamaz"):
        psycopg2.connect(dbname="crkys", **BAGLANTI)


def test_kilit_yerel_olmayan_sunucuyu_ve_dsn_baglantisini_engeller():
    with pytest.raises(RuntimeError, match="Yerel olmayan"):
        psycopg2.connect(dbname="crkys_sema_x", user="a", password="b", host="10.1.2.3", port="5432")
    with pytest.raises(RuntimeError, match="DSN"):
        psycopg2.connect("dbname=crkys_alembic_test")
