"""scripts/sema_dogrula.py: karşılaştırma, rapor ve hata yönetimi (gerçek veritabanı gerektirmez).

Gerçek PostgreSQL'de uçtan uca doğrulama: tests/integration/test_sema_dogrulama_pg_quality.py
"""

import importlib.util
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import psycopg2
import pytest

KOK = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("sema_dogrula", KOK / "scripts" / "sema_dogrula.py")
sd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sd)

HEAD = {"e1a7c4b9d3f6"}


BEKLENEN = {
    ("tablo", "randevular"): ("", ""),
    ("kolon", "randevular.durum"): ("character varying(20) NOT NULL", "'PLANLANDI'::character varying"),
    ("kolon", "randevular.iptal_nedeni"): ("character varying(30) NULL", ""),
    ("kisit", "randevular.randevular_iptal_nedeni_gecerli"): ("c", "CHECK (...)"),
    ("indeks", "randevular.randevular_pkey"): ("", "CREATE UNIQUE INDEX ..."),
    ("enum", "denetim_olay_turu"): ("CREATE,UPDATE", ""),
    ("tetikleyici", "denetim_kayitlari.degistirilemez"): ("", "CREATE TRIGGER ..."),
}


def kopya(**degisiklik):
    """BEKLENEN'in kopyası; 'kategori__ad' anahtarlarıyla (ad içindeki '.' yerine _NOKTA_) değiştirir, None ise siler."""
    yeni = dict(BEKLENEN)
    for anahtar, deger in degisiklik.items():
        kategori, ad = anahtar.split("__", 1)
        ad = ad.replace("_NOKTA_", ".")
        if deger is None:
            yeni.pop((kategori, ad), None)
        else:
            yeni[(kategori, ad)] = deger
    return yeni


# ---------------------------------------------------------------- karşılaştırma
def test_ayni_sema_fark_uretmez():
    sonuc = sd.karsilastir(BEKLENEN, dict(BEKLENEN))
    assert not (sonuc.eksik or sonuc.fazla or sonuc.farkli or sonuc.ayrinti)
    assert sonuc.sorunlu is False


def test_eksik_sutun_ve_kural_yakalanir():
    gercek = kopya(kolon__randevular_NOKTA_iptal_nedeni=None, kisit__randevular_NOKTA_randevular_iptal_nedeni_gecerli=None)
    sonuc = sd.karsilastir(BEKLENEN, gercek)
    assert sonuc.eksik == [("kisit", "randevular.randevular_iptal_nedeni_gecerli"), ("kolon", "randevular.iptal_nedeni")]
    assert sonuc.sorunlu is True


@pytest.mark.parametrize("kategori,anahtar", [
    ("tablo", "randevular"), ("indeks", "randevular.randevular_pkey"), ("enum", "denetim_olay_turu"),
    ("tetikleyici", "denetim_kayitlari.degistirilemez"),
])
def test_her_kategoride_eksik_nesne_yakalanir(kategori, anahtar):
    gercek = dict(BEKLENEN)
    del gercek[(kategori, anahtar)]
    assert sd.karsilastir(BEKLENEN, gercek).eksik == [(kategori, anahtar)]


def test_fazla_nesne_sorun_sayilmaz_ama_raporlanir():
    gercek = kopya(kolon__randevular_NOKTA_eski_sutun=("text NULL", ""))
    sonuc = sd.karsilastir(BEKLENEN, gercek)
    assert sonuc.fazla == [("kolon", "randevular.eski_sutun")]
    assert sonuc.sorunlu is False


def test_yapisal_fark_ve_ayrinti_farki_ayri_siniflanir():
    gercek = kopya(
        kolon__randevular_NOKTA_iptal_nedeni=("character varying(50) NULL", ""),                  # tip değişmiş: yapısal
        kolon__randevular_NOKTA_durum=("character varying(20) NOT NULL", "'IPTAL'::character varying"),  # yalnızca varsayılan
    )
    sonuc = sd.karsilastir(BEKLENEN, gercek)
    assert sonuc.farkli == [("kolon", "randevular.iptal_nedeni")]
    assert sonuc.ayrinti == [("kolon", "randevular.durum")]
    assert sonuc.sorunlu is True


def test_null_olabilirlik_farki_yapisaldir():
    gercek = kopya(kolon__randevular_NOKTA_durum=("character varying(20) NULL", "'PLANLANDI'::character varying"))
    assert sd.karsilastir(BEKLENEN, gercek).farkli == [("kolon", "randevular.durum")]


def test_enum_degeri_eksikse_yapisal_fark():
    gercek = kopya(enum__denetim_olay_turu=("CREATE", ""))
    assert sd.karsilastir(BEKLENEN, gercek).farkli == [("enum", "denetim_olay_turu")]


def test_yalnizca_ayrinti_farki_sorun_degildir():
    gercek = kopya(indeks__randevular_NOKTA_randevular_pkey=("", "CREATE UNIQUE INDEX baska"))
    sonuc = sd.karsilastir(BEKLENEN, gercek)
    assert sonuc.ayrinti and sonuc.sorunlu is False


# ---------------------------------------------------------------- rapor
def rapor(gercek, db_surum=HEAD, kod_surum=HEAD, ayrinti=False):
    sonuc = sd.karsilastir(BEKLENEN, gercek)
    satirlar, basarili = sd.rapor_olustur("crkys", kod_surum, db_surum, sonuc, BEKLENEN, gercek, ayrinti)
    return "\n".join(satirlar), basarili


def test_uyumlu_sema_basarili_rapor():
    metin, basarili = rapor(dict(BEKLENEN))
    assert basarili is True and "ŞEMA UYUMLU" in metin


def test_surum_guncel_ama_nesne_eksikse_tutarsiz_sema_der_ve_alembic_onermez():
    metin, basarili = rapor(kopya(kolon__randevular_NOKTA_iptal_nedeni=None))
    assert basarili is False
    assert "TUTARSIZ ŞEMA" in metin and "randevular.iptal_nedeni" in metin
    assert "DÜZELTMEZ" in metin                                   # 'alembic upgrade head' çare değil


def test_surum_eskiyse_alembic_komutunu_onerir():
    metin, basarili = rapor(kopya(kolon__randevular_NOKTA_iptal_nedeni=None), db_surum={"c3d8e5a1f7b2"})
    assert basarili is False
    assert "python -m alembic upgrade head" in metin and "ŞEMA ESKİ" in metin and "TUTARSIZ" not in metin


def test_tablolar_uyumlu_ama_surum_eskiyse_basarisiz():
    metin, basarili = rapor(dict(BEKLENEN), db_surum={"c3d8e5a1f7b2"})
    assert basarili is False and "alembic sürümü eski" in metin


def test_surum_kaydi_yoksa_yok_yazar():
    metin, basarili = rapor(dict(BEKLENEN), db_surum=set())
    assert basarili is False and "YOK" in metin


def test_fazla_nesne_basariyi_bozmaz_ama_uyari_yazar():
    metin, basarili = rapor(kopya(kolon__randevular_NOKTA_eski=("text NULL", "")))
    assert basarili is True and "FAZLA" in metin and "randevular.eski" in metin


def test_ayrinti_farki_varsayilan_olarak_ozetlenir_ayrinti_istenince_listelenir():
    gercek = kopya(indeks__randevular_NOKTA_randevular_pkey=("", "baska"))
    ozet, _ = rapor(gercek)
    assert "1 nesnede ayrıntı farkı" in ozet and "randevular.randevular_pkey" not in ozet
    ayrintili, _ = rapor(gercek, ayrinti=True)
    assert "AYRINTI FARKI" in ayrintili and "randevular.randevular_pkey" in ayrintili


def test_fark_listesi_sinirlanir():
    beklenen = {("kolon", f"t.k{i}"): ("text NULL", "") for i in range(60)}
    sonuc = sd.karsilastir(beklenen, {})
    satirlar, _ = sd.rapor_olustur("db", HEAD, HEAD, sonuc, beklenen, {})
    metin = "\n".join(satirlar)
    assert "(60)" in metin and "... ve 20 tane daha" in metin and "t.k0" in metin and "t.k59" not in metin


def test_farkli_nesne_olmasi_gereken_ve_su_an_degerlerini_gosterir():
    gercek = kopya(kolon__randevular_NOKTA_iptal_nedeni=("character varying(50) NULL", ""))
    metin, _ = rapor(gercek)
    assert "olması gereken: character varying(30) NULL" in metin and "şu an: character varying(50) NULL" in metin


# ---------------------------------------------------------------- parmak izi (sahte imleç)
def test_parmak_izi_her_kategoriyi_sorgular_ve_eslestirir():
    imlec = MagicMock()
    imlec.fetchall.side_effect = [
        [("randevular", "", "")],
        [("randevular.durum", "text NOT NULL", None)],
        [("randevular.pk", "p", "PRIMARY KEY (id)")],
        [("randevular.randevular_pkey", "", "CREATE UNIQUE INDEX")],
        [("durum_enum", "A,B", "")],
        [("randevular.tetik", "", "CREATE TRIGGER")],
    ]
    sonuc = sd.parmak_izi(imlec)
    assert imlec.execute.call_count == len(sd.SORGULAR) == 6
    assert sonuc[("kolon", "randevular.durum")] == ("text NOT NULL", "")           # None ayrıntı boş metne çevrilir
    assert sonuc[("kisit", "randevular.pk")] == ("p", "PRIMARY KEY (id)")
    assert sonuc[("enum", "durum_enum")] == ("A,B", "")
    assert len(sonuc) == 6


def test_sorgular_yalnizca_public_semasina_bakar_ve_dahili_nesneleri_dislar():
    for kategori, sorgu in sd.SORGULAR.items():
        assert "'public'" in sorgu, kategori
    assert "NOT t.tgisinternal" in sd.SORGULAR["tetikleyici"]
    assert "NOT a.attisdropped" in sd.SORGULAR["kolon"]
    assert "('c', 'u', 'p', 'f', 'x')" in sd.SORGULAR["kisit"]              # PostgreSQL 18'in 'n' (NOT NULL) kayıtları dışarıda


# ---------------------------------------------------------------- geçici veritabanı ve hatalar
class SahteYonetim:
    def __init__(self, olustur_hatasi=None):
        self.sorgular = []
        self.kapali = False
        self.autocommit = False
        self.olustur_hatasi = olustur_hatasi

    def cursor(self):
        yonetim = self

        class Imlec:
            def execute(self, sorgu, *a):
                metin = repr(sorgu)                      # psycopg2.sql nesnesinin metni ("CREATE DATABASE ..." içerir)
                yonetim.sorgular.append(metin)
                if "CREATE DATABASE" in metin and yonetim.olustur_hatasi:
                    raise yonetim.olustur_hatasi

        return Imlec()

    def close(self):
        self.kapali = True


def test_veritabani_olusturma_yetkisi_yoksa_yol_gosterir(monkeypatch):
    yonetim = SahteYonetim(psycopg2.errors.InsufficientPrivilege("permission denied to create database"))
    monkeypatch.setattr(sd.psycopg2, "connect", lambda **k: yonetim)
    with pytest.raises(sd.SemaDogrulamaHatasi, match="DB_MIGRATION_USER"):
        sd.referans_uret("kisitli", "p", "127.0.0.1", "5432")
    assert yonetim.kapali is True
    assert any("DROP DATABASE" in s for s in yonetim.sorgular)               # geçici veritabanı yine de silinmeye çalışılır


def test_migration_basarisizsa_hata_gosterir_ve_gecici_veritabanini_siler(monkeypatch):
    yonetim = SahteYonetim()
    monkeypatch.setattr(sd.psycopg2, "connect", lambda **k: yonetim)
    monkeypatch.setattr(sd.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 1, "", "satir1\nsatir2\nKRITIK HATA"))
    with pytest.raises(sd.SemaDogrulamaHatasi, match="KRITIK HATA"):
        sd.referans_uret("yon", "p", "127.0.0.1", "5432")
    assert any("DROP DATABASE" in s for s in yonetim.sorgular) and yonetim.kapali is True


def test_alembic_gecici_veritabanina_yonetici_kimligiyle_calistirilir(monkeypatch):
    yonetim = SahteYonetim()
    gorulen = {}

    def calistir(komut, **k):
        gorulen.update(komut=komut, **k)
        return subprocess.CompletedProcess(komut, 0, "", "")

    monkeypatch.setattr(sd.psycopg2, "connect", lambda **k: yonetim)
    monkeypatch.setattr(sd.subprocess, "run", calistir)
    monkeypatch.setenv("DB_MIGRATION_USER", "baska")
    monkeypatch.setenv("DB_MIGRATION_PASSWORD", "baska_parola")
    monkeypatch.setenv("DB_NAME", "canli_veritabani")
    with sd.gecici_sema_veritabani("yon", "yon_parola", "10.0.0.5", "5433") as (ad, bilgi):
        pass
    ortam = gorulen["env"]
    assert ad.startswith("crkys_sema_referans_") and ortam["DB_NAME"] == ad != "canli_veritabani"
    assert (ortam["DB_USER"], ortam["DB_PASSWORD"], ortam["DB_HOST"], ortam["DB_PORT"]) == ("yon", "yon_parola", "10.0.0.5", "5433")
    assert "DB_MIGRATION_USER" not in ortam and "DB_MIGRATION_PASSWORD" not in ortam
    assert gorulen["komut"][1:] == ["-m", "alembic", "upgrade", "head"]
    assert gorulen["cwd"] == sd.KOK
    assert bilgi == {"user": "yon", "password": "yon_parola", "host": "10.0.0.5", "port": "5433"}


def test_gecici_veritabani_adlari_her_seferinde_farklidir(monkeypatch):
    monkeypatch.setattr(sd.psycopg2, "connect", lambda **k: SahteYonetim())
    monkeypatch.setattr(sd.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0, "", ""))
    adlar = set()
    for _ in range(5):
        with sd.gecici_sema_veritabani("y", "p", "h", "1") as (ad, _):
            adlar.add(ad)
    assert len(adlar) == 5


# ---------------------------------------------------------------- main
@pytest.fixture
def ortam(monkeypatch):
    monkeypatch.setattr(sd, "load_dotenv", lambda *a, **k: None)
    for ad, deger in {"DB_NAME": "crkys", "DB_HOST": "127.0.0.1", "DB_PORT": "5432", "DB_USER": "postgres", "DB_PASSWORD": "p"}.items():
        monkeypatch.setenv(ad, deger)
    monkeypatch.delenv("DB_MIGRATION_USER", raising=False)
    monkeypatch.delenv("DB_MIGRATION_PASSWORD", raising=False)


def test_main_uyumluysa_sifir_doner(ortam, monkeypatch, capsys):
    monkeypatch.setattr(sd, "dogrula", lambda *a, **k: (["SONUÇ: ŞEMA UYUMLU"], True))
    assert sd.main([]) == 0
    assert "ŞEMA UYUMLU" in capsys.readouterr().out


def test_main_fark_varsa_bir_doner(ortam, monkeypatch, capsys):
    monkeypatch.setattr(sd, "dogrula", lambda *a, **k: (["SONUÇ: TUTARSIZ ŞEMA"], False))
    assert sd.main([]) == 1
    assert "TUTARSIZ" in capsys.readouterr().out


def test_main_ayrinti_secenegini_iletir(ortam, monkeypatch):
    gorulen = {}
    monkeypatch.setattr(sd, "dogrula", lambda *a, **k: gorulen.update(a=a, k=k) or ([], True))
    sd.main(["--ayrinti"])
    assert gorulen["a"][-1] is True


def test_main_migration_kimligini_kullanir(ortam, monkeypatch):
    monkeypatch.setenv("DB_MIGRATION_USER", "sema_sahibi")
    monkeypatch.setenv("DB_MIGRATION_PASSWORD", "sema_p")
    monkeypatch.setenv("DB_USER", "tkys_uygulama")
    monkeypatch.setenv("DB_PASSWORD", "uyg_p")
    gorulen = {}
    monkeypatch.setattr(sd, "dogrula", lambda veritabani, canli, yonetici, yonetici_parola, ayrinti: gorulen.update(
        canli=canli, yonetici=yonetici, yonetici_parola=yonetici_parola) or ([], True))
    assert sd.main([]) == 0
    assert (gorulen["yonetici"], gorulen["yonetici_parola"]) == ("sema_sahibi", "sema_p")          # geçici veritabanı için
    assert (gorulen["canli"]["user"], gorulen["canli"]["password"]) == ("tkys_uygulama", "uyg_p")  # canlı kontrol kısıtlı kullanıcıyla


@pytest.mark.parametrize("silinecek,beklenen", [("DB_NAME", "DB_NAME"), ("DB_HOST", "DB_HOST")])
def test_main_eksik_ayari_anlasilir_bildirir(ortam, monkeypatch, capsys, silinecek, beklenen):
    monkeypatch.delenv(silinecek)
    monkeypatch.setattr(sd, "dogrula", lambda *a, **k: pytest.fail("çağrılmamalı"))
    assert sd.main([]) == 1
    assert beklenen in capsys.readouterr().out


def test_main_tutarsiz_migration_ayarini_bildirir(ortam, monkeypatch, capsys):
    monkeypatch.setenv("DB_MIGRATION_USER", "sema_sahibi")                  # parola yok
    assert sd.main([]) == 1
    assert "DB_MIGRATION_PASSWORD" in capsys.readouterr().out


def test_main_veritabani_hatasinda_traceback_vermez(ortam, monkeypatch, capsys):
    def patla(*a, **k):
        raise psycopg2.OperationalError("connection refused\nDETAIL: ...")

    monkeypatch.setattr(sd, "dogrula", patla)
    assert sd.main([]) == 1
    cikti = capsys.readouterr().out
    assert "HATA" in cikti and "connection refused" in cikti and "Traceback" not in cikti


def test_main_sema_dogrulama_hatasini_mesajla_bildirir(ortam, monkeypatch, capsys):
    def patla(*a, **k):
        raise sd.SemaDogrulamaHatasi("Geçici veritabanı oluşturulamadı")

    monkeypatch.setattr(sd, "dogrula", patla)
    assert sd.main([]) == 1
    assert "Geçici veritabanı oluşturulamadı" in capsys.readouterr().out


# ---------------------------------------------------------------- belgeler
def test_kilavuz_ve_windows_rehberi_sema_kontrolunu_anlatir():
    kilavuz = (KOK / "docs" / "deployment" / "Sunucu_Kurulum_Kilavuzu.md").read_text(encoding="utf-8")
    for beklenen in ("scripts/sema_dogrula.py", "ŞEMA UYUMLU", "TUTARSIZ ŞEMA", "ŞEMA ESKİ", "--ayrinti", "Veritabanı şeması kontrolü"):
        assert beklenen in kilavuz, beklenen
    guncelleme = kilavuz[kilavuz.index("## 11. Güncelleme"):]
    assert guncelleme.index("alembic upgrade head") < guncelleme.index("sema_dogrula.py") < guncelleme.index("uvicorn server.sunucu")
    for ad in ("KOMUTLAR.md", "SORUN_GIDERME.md"):
        assert "sema_dogrula.py" in (KOK / "docs" / "deployment" / "windows-sunucu" / ad).read_text(encoding="utf-8"), ad
