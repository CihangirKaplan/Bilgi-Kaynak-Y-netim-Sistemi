"""scripts/uygulama_kullanicisi_olustur.py: sahte bağlantıyla (gerçek veritabanı gerektirmeden) mantık denetimleri.

Gerçek PostgreSQL'de uçtan uca doğrulama: test_kisitli_kullanici_pg_quality.py
"""

import importlib.util
import sys
from pathlib import Path

import pytest
from psycopg2 import sql

KOK = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("uygulama_kullanicisi_olustur", KOK / "scripts" / "uygulama_kullanicisi_olustur.py")
betik = importlib.util.module_from_spec(spec)
spec.loader.exec_module(betik)

# yetkileri_dogrula sorgularının güvenli (beklenen) sonuçları
GUVENLI_ROL = (False, False, False, False, False)
GUVENLI_YETKI = (True, False, False, False, False, False, True, True, True, False)


def duzlestir(nesne):
    """psycopg2.sql nesnesini (bağlantı olmadan) okunur metne çevirir; Identifier'lar çift tırnakla yazılır."""
    if isinstance(nesne, sql.Composed):
        return "".join(duzlestir(parca) for parca in nesne.seq)
    if isinstance(nesne, sql.Identifier):
        return '"' + ".".join(nesne.strings) + '"'
    if isinstance(nesne, sql.SQL):
        return nesne.string
    return str(nesne)


class SahteImlec:
    def __init__(self, rol_var=False, rol_satiri=GUVENLI_ROL, yetki_satiri=GUVENLI_YETKI):
        self.sorgular = []
        self.parametreler = []
        self.rol_var = rol_var
        self.rol_satiri = rol_satiri
        self.yetki_satiri = yetki_satiri
        self._sonraki = None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sorgu, parametre=None):
        metin = duzlestir(sorgu)
        self.sorgular.append(metin)
        self.parametreler.append(parametre)
        if "FROM pg_roles WHERE rolname" in metin and "rolsuper" not in metin:
            self._sonraki = (1,) if self.rol_var else None
        elif "rolsuper" in metin:
            self._sonraki = self.rol_satiri
        elif "has_table_privilege" in metin:
            self._sonraki = self.yetki_satiri

    def fetchone(self):
        return self._sonraki


class SahteBaglanti:
    def __init__(self, imlec):
        self.imlec = imlec
        self.commit_sayisi = 0
        self.rollback_sayisi = 0
        self.kapali = False

    def cursor(self):
        return self.imlec

    def commit(self):
        self.commit_sayisi += 1

    def rollback(self):
        self.rollback_sayisi += 1

    def close(self):
        self.kapali = True


# ---------------------------------------------------------------- rol adı ve parola
@pytest.mark.parametrize("ad", ["tkys_uygulama", "a", "_x", "uygulama_2", "a" * 63])
def test_gecerli_rol_adlari_kabul_edilir(ad):
    betik.rol_adini_dogrula(ad)


@pytest.mark.parametrize("ad", ["", None, "Büyük", "UYGULAMA", "1abc", "a-b", "a b", "a;drop", "a" * 64, 'a"b'])
def test_gecersiz_rol_adlari_reddedilir(ad):
    with pytest.raises(betik.KullaniciOlusturmaHatasi):
        betik.rol_adini_dogrula(ad)


@pytest.mark.parametrize("ad", ["postgres", "public", "pg_monitor", "pg_database_owner"])
def test_korunan_roller_reddedilir(ad):
    with pytest.raises(betik.KullaniciOlusturmaHatasi, match="kullanılamaz"):
        betik.rol_adini_dogrula(ad)


def test_uretilen_parola_uzun_ve_her_seferinde_farkli():
    a, b = betik.yeni_parola_uret(), betik.yeni_parola_uret()
    assert a != b and len(a) >= 40


# ---------------------------------------------------------------- kullaniciyi_olustur
def test_yeni_rol_kisitli_ozelliklerle_olusturulur_ve_parola_doner():
    imlec = SahteImlec(rol_var=False)
    baglanti = SahteBaglanti(imlec)
    parola = betik.kullaniciyi_olustur(baglanti, "crkys", "tkys_uygulama", "postgres")

    assert parola and len(parola) >= 40
    olustur = [s for s in imlec.sorgular if s.startswith("CREATE ROLE")]
    assert len(olustur) == 1
    assert 'CREATE ROLE "tkys_uygulama" LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD' in olustur[0]
    assert (parola,) in imlec.parametreler                       # parola sorguya gömülmez, parametre olarak gider
    assert all(parola not in s for s in imlec.sorgular)
    assert baglanti.commit_sayisi == 1 and baglanti.rollback_sayisi == 0


def test_rol_olusturma_yetkilerden_once_yapilir():
    imlec = SahteImlec()
    betik.kullaniciyi_olustur(SahteBaglanti(imlec), "crkys", "tkys_uygulama", "postgres")
    sira = imlec.sorgular
    assert next(i for i, s in enumerate(sira) if s.startswith("CREATE ROLE")) < next(
        i for i, s in enumerate(sira) if s.startswith("GRANT")
    )


def test_yetkiler_veri_okuma_yazmayi_verir_tablo_degistirmeyi_vermez():
    imlec = SahteImlec()
    betik.kullaniciyi_olustur(SahteBaglanti(imlec), "crkys", "tkys_uygulama", "postgres")
    tum = "\n".join(imlec.sorgular)

    assert 'GRANT CONNECT ON DATABASE "crkys" TO "tkys_uygulama"' in tum
    assert 'GRANT USAGE ON SCHEMA public TO "tkys_uygulama"' in tum
    assert 'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "tkys_uygulama"' in tum
    assert 'GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO "tkys_uygulama"' in tum
    for yasak in ("SUPERUSER ", "CREATEDB ", "CREATEROLE ", "ALL PRIVILEGES", "TRUNCATE ON ALL", "WITH GRANT OPTION"):
        # NOSUPERUSER vb. serbest; "NO" ile başlamayan yetki verilmemeli
        assert f" {yasak}" not in tum.replace("NOSUPERUSER", "").replace("NOCREATEDB", "").replace("NOCREATEROLE", "")


def test_gelecekteki_tablolara_yonetici_adina_otomatik_yetki_verilir():
    imlec = SahteImlec()
    betik.kullaniciyi_olustur(SahteBaglanti(imlec), "crkys", "tkys_uygulama", "sema_sahibi")
    tum = "\n".join(imlec.sorgular)
    assert ('ALTER DEFAULT PRIVILEGES FOR ROLE "sema_sahibi" IN SCHEMA public '
            'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "tkys_uygulama"') in tum
    assert ('ALTER DEFAULT PRIVILEGES FOR ROLE "sema_sahibi" IN SCHEMA public '
            'GRANT USAGE, SELECT ON SEQUENCES TO "tkys_uygulama"') in tum


def test_denetim_kaydi_ve_alembic_surumu_korunur():
    imlec = SahteImlec()
    betik.kullaniciyi_olustur(SahteBaglanti(imlec), "crkys", "tkys_uygulama", "postgres")
    tum = "\n".join(imlec.sorgular)
    assert 'REVOKE UPDATE, DELETE, TRUNCATE ON TABLE public.denetim_kayitlari FROM "tkys_uygulama"' in tum
    assert 'REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON TABLE public.alembic_version FROM "tkys_uygulama"' in tum
    # REVOKE'lar GRANT'lerden sonra gelmeli, yoksa GRANT onları geri açardı.
    ilk_revoke = next(i for i, s in enumerate(imlec.sorgular) if s.startswith("REVOKE"))
    son_grant = max(i for i, s in enumerate(imlec.sorgular) if s.startswith("GRANT"))
    assert son_grant < ilk_revoke


def test_rol_zaten_varsa_olusturulmaz_parola_degismez():
    imlec = SahteImlec(rol_var=True)
    baglanti = SahteBaglanti(imlec)
    assert betik.kullaniciyi_olustur(baglanti, "crkys", "tkys_uygulama", "postgres") is None
    assert not any(s.startswith(("CREATE ROLE", "ALTER ROLE")) for s in imlec.sorgular)
    assert any(s.startswith("GRANT") for s in imlec.sorgular)       # yetkiler yine de yeniden uygulanır
    assert baglanti.commit_sayisi == 1


def test_parolayi_yenile_mevcut_rolun_parolasini_degistirir():
    imlec = SahteImlec(rol_var=True)
    parola = betik.kullaniciyi_olustur(SahteBaglanti(imlec), "crkys", "tkys_uygulama", "postgres", parolayi_yenile=True)
    assert parola and len(parola) >= 40
    assert 'ALTER ROLE "tkys_uygulama" PASSWORD' in "\n".join(imlec.sorgular)
    assert not any(s.startswith("CREATE ROLE") for s in imlec.sorgular)


def test_kisitli_kullanici_yonetici_ile_ayni_olamaz():
    imlec = SahteImlec()
    with pytest.raises(betik.KullaniciOlusturmaHatasi, match="aynı olamaz"):
        betik.kullaniciyi_olustur(SahteBaglanti(imlec), "crkys", "tkys_uygulama", "tkys_uygulama")
    assert imlec.sorgular == []                                     # hiçbir sorgu çalışmamalı


def test_gecersiz_ad_hicbir_sorgu_calistirmaz():
    imlec = SahteImlec()
    with pytest.raises(betik.KullaniciOlusturmaHatasi):
        betik.kullaniciyi_olustur(SahteBaglanti(imlec), "crkys", "Kötü-Ad", "postgres")
    assert imlec.sorgular == []


# ---------------------------------------------------------------- doğrulama
def test_guvenli_yetkiler_dogrulamadan_gecer():
    imlec = SahteImlec()
    betik.yetkileri_dogrula(imlec, "tkys_uygulama")


@pytest.mark.parametrize("sira", range(5))
def test_rol_ozellikleri_guvenli_degilse_hata_verir(sira):
    satir = list(GUVENLI_ROL)
    satir[sira] = True
    with pytest.raises(betik.KullaniciOlusturmaHatasi, match="güvenli değil"):
        betik.yetkileri_dogrula(SahteImlec(rol_satiri=tuple(satir)), "tkys_uygulama")


@pytest.mark.parametrize("sira", range(10))
def test_tablo_yetkileri_beklenenden_farkliysa_hata_verir(sira):
    satir = list(GUVENLI_YETKI)
    satir[sira] = not satir[sira]
    with pytest.raises(betik.KullaniciOlusturmaHatasi, match="güvenli değil"):
        betik.yetkileri_dogrula(SahteImlec(yetki_satiri=tuple(satir)), "tkys_uygulama")


def test_dogrulama_hatasi_islemi_kalici_yapmaz():
    imlec = SahteImlec(yetki_satiri=(True, True) + GUVENLI_YETKI[2:])     # denetim UPDATE açık
    baglanti = SahteBaglanti(imlec)
    with pytest.raises(betik.KullaniciOlusturmaHatasi):
        betik.kullaniciyi_olustur(baglanti, "crkys", "tkys_uygulama", "postgres")
    assert baglanti.commit_sayisi == 0


# ---------------------------------------------------------------- main
@pytest.fixture
def ortam(monkeypatch):
    monkeypatch.setattr(betik, "load_dotenv", lambda *a, **k: None)
    for ad, deger in {"DB_NAME": "crkys", "DB_HOST": "127.0.0.1", "DB_PORT": "5432",
                      "DB_USER": "postgres", "DB_PASSWORD": "yonetici_parolasi"}.items():
        monkeypatch.setenv(ad, deger)
    monkeypatch.delenv("DB_MIGRATION_USER", raising=False)
    monkeypatch.delenv("DB_MIGRATION_PASSWORD", raising=False)


def test_onizleme_veritabanina_baglanmaz(ortam, monkeypatch, capsys):
    def baglanma(*a, **k):
        raise AssertionError("Önizleme veritabanına bağlanmamalı.")

    monkeypatch.setattr(betik.psycopg2, "connect", baglanma)
    assert betik.main([]) == 0
    cikti = capsys.readouterr().out
    assert "ÖNİZLEME" in cikti and "--uygula" in cikti and "tkys_uygulama" in cikti


def test_uygula_yeni_parolayi_bir_kez_gosterir(ortam, monkeypatch, capsys):
    imlec = SahteImlec(rol_var=False)
    baglanti = SahteBaglanti(imlec)
    gorulen = {}
    monkeypatch.setattr(betik.psycopg2, "connect", lambda **k: gorulen.update(k) or baglanti)

    assert betik.main(["--uygula"]) == 0
    cikti = capsys.readouterr().out
    parola = next(s.split("=", 1)[1] for s in cikti.splitlines() if s.strip().startswith("DB_PASSWORD=") and "<" not in s)
    assert len(parola) >= 40
    assert "DB_USER=tkys_uygulama" in cikti and "DB_MIGRATION_USER=postgres" in cikti
    assert gorulen["user"] == "postgres" and gorulen["password"] == "yonetici_parolasi" and gorulen["dbname"] == "crkys"
    assert baglanti.kapali and baglanti.commit_sayisi == 1


def test_uygula_mevcut_kullanicida_parola_gostermez(ortam, monkeypatch, capsys):
    baglanti = SahteBaglanti(SahteImlec(rol_var=True))
    monkeypatch.setattr(betik.psycopg2, "connect", lambda **k: baglanti)
    assert betik.main(["--uygula"]) == 0
    cikti = capsys.readouterr().out
    assert "zaten vardı" in cikti and "DB_USER=tkys_uygulama" not in cikti


def test_migration_kimligi_varsa_yonetici_olarak_o_kullanilir(ortam, monkeypatch):
    monkeypatch.setenv("DB_MIGRATION_USER", "sema_sahibi")
    monkeypatch.setenv("DB_MIGRATION_PASSWORD", "sema_parolasi")
    monkeypatch.setenv("DB_USER", "tkys_uygulama")             # sunucu zaten kısıtlı kullanıcıyla ayarlı
    monkeypatch.setenv("DB_PASSWORD", "uygulama_parolasi")
    gorulen = {}
    baglanti = SahteBaglanti(SahteImlec(rol_var=True))
    monkeypatch.setattr(betik.psycopg2, "connect", lambda **k: gorulen.update(k) or baglanti)
    assert betik.main(["--uygula", "--parolayi-yenile"]) == 0
    assert gorulen["user"] == "sema_sahibi" and gorulen["password"] == "sema_parolasi"


def test_rol_yonetici_adiyla_ayniysa_hata_verir(ortam, monkeypatch, capsys):
    monkeypatch.setattr(betik.psycopg2, "connect", lambda **k: pytest.fail("bağlanılmamalı"))
    assert betik.main(["--rol", "postgres", "--uygula"]) == 1        # korunan ad
    monkeypatch.setenv("DB_USER", "benim_yoneticim")
    assert betik.main(["--rol", "benim_yoneticim", "--uygula"]) == 1
    assert "yönetici" in capsys.readouterr().out


def test_gecersiz_rol_adi_hata_kodu_doner(ortam, monkeypatch, capsys):
    monkeypatch.setattr(betik.psycopg2, "connect", lambda **k: pytest.fail("bağlanılmamalı"))
    assert betik.main(["--rol", "Kötü-Ad", "--uygula"]) == 1
    assert "HATA" in capsys.readouterr().out


def test_veritabani_hatasinda_geri_alinir_ve_anlasilir_hata_verir(ortam, monkeypatch, capsys):
    import psycopg2

    class Bozuk(SahteImlec):
        def execute(self, sorgu, parametre=None):
            raise psycopg2.errors.InsufficientPrivilege("permission denied to create role\nDETAIL: ...")

    baglanti = SahteBaglanti(Bozuk())
    monkeypatch.setattr(betik.psycopg2, "connect", lambda **k: baglanti)
    assert betik.main(["--uygula"]) == 1
    cikti = capsys.readouterr().out
    assert "HATA" in cikti and "permission denied" in cikti and "Traceback" not in cikti
    assert baglanti.rollback_sayisi == 1 and baglanti.kapali and baglanti.commit_sayisi == 0


def test_tutarsiz_migration_ayari_anlasilir_hata_verir(ortam, monkeypatch, capsys):
    monkeypatch.setenv("DB_MIGRATION_USER", "sema_sahibi")          # parola yok
    assert betik.main(["--uygula"]) == 1
    assert "DB_MIGRATION_PASSWORD" in capsys.readouterr().out
