"""Parola sıfırlama talepleri: kullanıcı yöneticiye bildirir, yönetici listeden görür / kapatır / sıfırlayınca tamamlanır.

Gerçek veritabanı kullanılmaz; sorguya göre yanıt veren sahte imleç kullanılır.
"""
import datetime
import importlib.util
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException, Response
from pydantic import ValidationError

import sunucu
from modeller import ParolaSifirlamaTalebiModeli


class SahteImlec:
    """Çalışan sorguları kaydeder; sorgu metnine göre fetchone/fetchall döndürür."""

    def __init__(self, kullanici=None, acik_talep=None, acik_sayisi=0, eklenen=(77,), kapatilan=(5,), satirlar=()):
        self.kullanici, self.acik_talep, self.acik_sayisi = kullanici, acik_talep, acik_sayisi
        self.eklenen, self.kapatilan, self.satirlar = eklenen, kapatilan, list(satirlar)
        self.sorgular, self._son = [], ""

    def execute(self, sorgu, parametreler=None):
        self._son = " ".join(sorgu.split())
        self.sorgular.append((self._son, parametreler))

    def fetchone(self):
        s = self._son
        if s.startswith("SELECT kullanici_id, aktif_mi FROM kullanicilar"):
            return self.kullanici
        if "SELECT 1 FROM parola_sifirlama_talepleri" in s:
            return self.acik_talep
        if "SELECT COUNT(*)" in s:
            return (self.acik_sayisi,)
        if s.startswith("INSERT INTO parola_sifirlama_talepleri"):
            return self.eklenen
        if s.startswith("UPDATE parola_sifirlama_talepleri"):
            return self.kapatilan
        return None

    def fetchall(self):
        return self.satirlar

    def close(self):
        pass

    def calisan(self, parca):
        return [(s, p) for s, p in self.sorgular if parca in s]


def baglan(imlec):
    conn = MagicMock()
    conn.cursor.return_value = imlec
    return conn


def talep_et(imlec, ad="psikolog1"):
    audit = MagicMock()
    with patch("sunucu.psycopg2.connect", return_value=baglan(imlec)), patch("denetim.denetim_kaydi_olustur", audit):
        sonuc = sunucu.parola_sifirlama_talebi_olustur(ParolaSifirlamaTalebiModeli(kullanici_adi=ad))
    return sonuc, audit


# ----------------------------------------------------------------------- talep açma
def test_aktif_kullanici_icin_talep_olusur_ve_audit_yazilir():
    imlec = SahteImlec(kullanici=(12, True))
    sonuc, audit = talep_et(imlec)
    assert sonuc["durum"] == "alindi"
    ekle = imlec.calisan("INSERT INTO parola_sifirlama_talepleri")
    assert len(ekle) == 1 and ekle[0][1] == (12,)
    assert audit.call_args.kwargs["olay_turu"] == "CREATE" and audit.call_args.kwargs["kullanici_id"] == 12
    assert audit.call_args.kwargs["hedef_tablo"] == "parola_sifirlama_talepleri" and audit.call_args.kwargs["hedef_kayit_id"] == 77


def test_olmayan_kullanici_icin_talep_olusmaz_ama_yanit_ayni_kalir():
    gercek, _ = talep_et(SahteImlec(kullanici=(12, True)))
    imlec = SahteImlec(kullanici=None)
    sonuc, audit = talep_et(imlec, "yok_boyle_biri")
    assert sonuc == gercek                                           # yanıttan kullanıcının var olup olmadığı anlaşılmaz
    assert not imlec.calisan("INSERT") and not audit.called


def test_pasif_kullanici_icin_talep_olusmaz():
    imlec = SahteImlec(kullanici=(12, False))
    sonuc, audit = talep_et(imlec)
    assert sonuc["durum"] == "alindi" and not imlec.calisan("INSERT") and not audit.called


def test_zaten_acik_talebi_olan_kullanici_icin_ikinci_talep_olusmaz():
    imlec = SahteImlec(kullanici=(12, True), acik_talep=(1,))
    sonuc, audit = talep_et(imlec)
    assert sonuc["durum"] == "alindi" and not imlec.calisan("INSERT") and not audit.called


def test_cakisan_es_zamanli_ekleme_sessizce_yutulur_ve_audit_yazilmaz():
    imlec = SahteImlec(kullanici=(12, True), eklenen=None)            # ON CONFLICT DO NOTHING hiçbir satır döndürmedi
    sonuc, audit = talep_et(imlec)
    assert sonuc["durum"] == "alindi" and not audit.called


def test_acik_talep_ust_siniri_asilirsa_429_verilir_ve_talep_eklenmez():
    imlec = SahteImlec(kullanici=(12, True), acik_sayisi=sunucu.PAROLA_TALEBI_ACIK_UST_SINIR)
    with pytest.raises(HTTPException) as hata:
        talep_et(imlec)
    assert hata.value.status_code == 429 and not imlec.calisan("INSERT")


def test_sinirin_hemen_altinda_talep_kabul_edilir():
    imlec = SahteImlec(kullanici=(12, True), acik_sayisi=sunucu.PAROLA_TALEBI_ACIK_UST_SINIR - 1)
    sonuc, _ = talep_et(imlec)
    assert sonuc["durum"] == "alindi" and imlec.calisan("INSERT INTO parola_sifirlama_talepleri")


def test_sorgular_parametreli_ve_kullanici_adi_sorguya_yapistirilmaz():
    imlec = SahteImlec(kullanici=None)
    talep_et(imlec, "x'; DROP TABLE kullanicilar;--")
    sorgu, parametre = imlec.sorgular[0]
    assert "DROP" not in sorgu and parametre == ("x'; DROP TABLE kullanicilar;--",)


def test_beklenmeyen_hata_icerigi_sizdirmadan_500_verir():
    conn = MagicMock()
    conn.cursor.return_value.execute.side_effect = RuntimeError("tablo yok: parola_sifirlama_talepleri")
    with patch("sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            sunucu.parola_sifirlama_talebi_olustur(ParolaSifirlamaTalebiModeli(kullanici_adi="a"))
    assert hata.value.status_code == 500 and "tablo" not in hata.value.detail
    conn.rollback.assert_called()


@pytest.mark.parametrize("veri", [{}, {"kullanici_adi": ""}, {"kullanici_adi": "   "}, {"kullanici_adi": "x" * 101},
                                  {"kullanici_adi": "a", "ek_alan": 1}, {"kullanici_adi": None}])
def test_gecersiz_talep_govdesi_reddedilir(veri):
    with pytest.raises(ValidationError):
        ParolaSifirlamaTalebiModeli(**veri)


def test_kullanici_adi_bosluklardan_arindirilir():
    assert ParolaSifirlamaTalebiModeli(kullanici_adi="  psikolog1 ").kullanici_adi == "psikolog1"


# ------------------------------------------------------------------------- listeleme
def test_bekleyen_talepler_listelenir_zaman_ve_bekleme_dakikasi_ile():
    zaman = datetime.datetime(2026, 11, 9, 10, 0, 0)
    imlec = SahteImlec(satirlar=[(5, 12, "psikolog1", "PSIKOLOG", zaman, 7), (6, 13, "memur", "MEMUR", zaman, -1)])
    yanit = Response()
    with patch("sunucu.psycopg2.connect", return_value=baglan(imlec)):
        sonuc = sunucu.parola_sifirlama_taleplerini_listele(yanit, kullanici_id=1)
    assert sonuc[0] == {"talep_id": 5, "kullanici_id": 12, "kullanici_adi": "psikolog1", "rol_adi": "PSIKOLOG",
                        "talep_zamani": "2026-11-09T10:00:00", "bekleme_dakika": 7}
    assert sonuc[1]["bekleme_dakika"] == 0                            # saat farkından negatif çıkarsa 0'a çekilir
    assert yanit.headers["Cache-Control"] == "no-store"


def test_liste_sorgusu_yalniz_acik_talepleri_ve_aktif_kullanicilari_eski_once_getirir():
    imlec = SahteImlec()
    with patch("sunucu.psycopg2.connect", return_value=baglan(imlec)):
        sunucu.parola_sifirlama_taleplerini_listele(Response(), kullanici_id=1)
    sorgu = imlec.sorgular[0][0]
    assert "t.durum = 'ACIK'" in sorgu and "k.aktif_mi" in sorgu and "ORDER BY t.talep_zamani" in sorgu


def test_liste_ve_kapat_uclari_parola_sifirlama_iznini_ister():
    import inspect
    for ad in ("parola_sifirlama_taleplerini_listele", "parola_sifirlama_talebini_kapat"):
        assert 'izin_kontrol("KULLANICI_PAROLA_SIFIRLA")' in inspect.getsource(getattr(sunucu, ad)), ad


def test_talep_acma_ucu_tek_izinsiz_uctur_ve_bu_bilincli_istisnadir():
    from tests.test_uc_koruma_taramasi import ISTISNALAR
    assert ("POST", "/api/parola-sifirlama-talebi") in ISTISNALAR


# --------------------------------------------------------------------------- kapatma
def kapat(imlec, talep_id=5, yonetici=1):
    audit = MagicMock()
    with patch("sunucu.psycopg2.connect", return_value=baglan(imlec)), patch("denetim.denetim_kaydi_olustur", audit):
        return sunucu.parola_sifirlama_talebini_kapat(talep_id, islem_yapan_id=yonetici), audit


def test_talep_kapatilinca_durum_kapatildi_olur_ve_audit_yazilir():
    imlec = SahteImlec()
    sonuc, audit = kapat(imlec)
    assert sonuc["durum"] == "basarili"
    guncelle = imlec.calisan("SET durum = 'KAPATILDI'")
    assert len(guncelle) == 1 and guncelle[0][1] == (1, 5) and "durum = 'ACIK'" in guncelle[0][0]
    assert audit.call_args.kwargs["olay_turu"] == "UPDATE" and audit.call_args.kwargs["hedef_kayit_id"] == 5


def test_olmayan_ya_da_zaten_kapali_talep_404_verir_ve_audit_yazmaz():
    imlec = SahteImlec(kapatilan=None)
    audit = MagicMock()
    with patch("sunucu.psycopg2.connect", return_value=baglan(imlec)), patch("denetim.denetim_kaydi_olustur", audit):
        with pytest.raises(HTTPException) as hata:
            sunucu.parola_sifirlama_talebini_kapat(99, islem_yapan_id=1)
    assert hata.value.status_code == 404 and not audit.called


# ------------------------------------------------ parola sıfırlayınca talep tamamlanır
def test_parola_sifirlaninca_o_kullanicinin_acik_talebi_tamamlanir():
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchone.side_effect = [("ADMIN",), (True,)]
    with patch("sunucu.psycopg2.connect", return_value=conn):
        sunucu.kullanici_parola_sifirla(kullanici_id=20, response=Response(), islem_yapan_id=10)
    sorgular = [(" ".join(c.args[0].split()), c.args[1] if len(c.args) > 1 else None) for c in cursor.execute.call_args_list]
    tamamla = [(s, p) for s, p in sorgular if s.startswith("UPDATE parola_sifirlama_talepleri")]
    assert len(tamamla) == 1 and tamamla[0][1] == (10, 20) and "'TAMAMLANDI'" in tamamla[0][0] and "durum = 'ACIK'" in tamamla[0][0]
    # talebin tamamlanması, parolanın sıfırlanmasıyla aynı işlemde (commit'ten önce) yapılır
    assert [i for i, (s, _) in enumerate(sorgular) if s.startswith("UPDATE parola_sifirlama_talepleri")][0] > \
           [i for i, (s, _) in enumerate(sorgular) if s.startswith("UPDATE kullanicilar")][0]
    conn.commit.assert_called_once()


# ------------------------------------------------------------------------- migration
YOL = Path("alembic/versions/a7d3e91c5f42_parola_sifirlama_talepleri.py")


@pytest.fixture(scope="module")
def migration():
    spec = importlib.util.spec_from_file_location("talep_migration", YOL)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def sql_listesi(fonksiyon):
    with patch("alembic.op.execute") as yurut:
        fonksiyon()
    return [" ".join(c.args[0].split()) for c in yurut.call_args_list]


def test_migration_zincirin_icinde_ve_zincir_tek_parcadir(migration):
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    betikler = ScriptDirectory.from_config(Config("alembic.ini"))
    heads = betikler.get_heads()
    assert len(heads) == 1                                           # zincir tek parça
    assert migration.revision in [r.revision for r in betikler.iterate_revisions(heads[0], "base")]   # sonradan eklenenler bozmaz
    assert migration.down_revision == "f3a9c2e47b18"


def test_migration_tabloyu_tutarlilik_kurallariyla_ve_kismi_tekil_indeksle_olusturur(migration):
    sql = " ".join(sql_listesi(migration.upgrade))
    assert "CREATE TABLE parola_sifirlama_talepleri" in sql
    assert "durum IN ('ACIK', 'TAMAMLANDI', 'KAPATILDI')" in sql
    assert "(durum = 'ACIK' AND kapanis_zamani IS NULL) OR (durum <> 'ACIK' AND kapanis_zamani IS NOT NULL)" in sql
    assert re.search(r"CREATE UNIQUE INDEX parola_sifirlama_acik_talep_tekil ON parola_sifirlama_talepleri \(kullanici_id\) WHERE durum = 'ACIK'", sql)


def test_migration_geri_alinabilir_indeks_tablodan_once_kalkar(migration):
    sql = sql_listesi(migration.downgrade)
    assert "DROP INDEX" in sql[0] and "DROP TABLE" in sql[1]
