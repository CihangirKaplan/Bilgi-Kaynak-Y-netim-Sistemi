"""Aynı oda aynı saatte iki cihaz rezervasyonuna verilemez (oda + zaman aralığı çakışırsa 409).

Sunucu denetimi sahte bağlantıyla, veritabanı kısıtı migrasyon dosyası üzerinden denenir (gerçek PostgreSQL'de ayrıca doğrulanmıştır).
"""
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import psycopg2
import pytest
from fastapi import HTTPException

import server.sunucu as sunucu
from server.modeller import RezervasyonOlusturModeli

KOK = Path(__file__).resolve().parents[2]
GEL = datetime(2027, 1, 5, 10)


def rezervasyon(oda_cakismalari=None, oda_id=1, bitis_saat=1, hata_ekleme=None):
    conn = MagicMock()
    imlec = conn.cursor.return_value
    imlec.execute.side_effect = lambda sorgu, *a, **k: (setattr(imlec, "son", str(sorgu)),
                                                         _ekleme_hatasi(sorgu, hata_ekleme))[0]

    def bir():
        s = imlec.son
        if "FROM (SELECT o.oda_id" in s:
            return (1,)                                                    # oda aktif ve rezervasyon için uygun
        if "FROM cihazlar" in s and "durum" in s:
            return ("Kullanima_Hazir",)
        if "RETURNING rezervasyon_id" in s:
            return (31,)
        if "personel_id FROM personel" in s:
            return (3,)
        return None
    imlec.fetchone.side_effect = bir
    imlec.fetchall.side_effect = lambda: (oda_cakismalari or []) if "r.kullanilacak_oda_id = %s" in imlec.son else []
    model = RezervasyonOlusturModeli(cihaz_id=2, kullanilacak_oda_id=oda_id, baslangic_zamani=GEL, bitis_zamani=GEL + timedelta(hours=bitis_saat))
    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        try:
            return sunucu.cihaz_rezervasyonu_yap(model, kullanici_id=5), imlec
        except HTTPException as h:
            return h, imlec


def _ekleme_hatasi(sorgu, hata):
    if hata is not None and "INSERT INTO cihaz_rezervasyonlari" in str(sorgu):
        raise hata


def eklendi(imlec):
    return any("INSERT INTO cihaz_rezervasyonlari" in str(c.args[0]) for c in imlec.execute.call_args_list)


def test_ayni_odada_cakisan_rezervasyon_409_ve_cakisanlari_listeler():
    cakisan = [(17, GEL - timedelta(minutes=30), GEL + timedelta(minutes=30), "ayse")]
    sonuc, imlec = rezervasyon(oda_cakismalari=cakisan)
    assert isinstance(sonuc, HTTPException) and sonuc.status_code == 409
    assert sonuc.detail["kod"] == sunucu.REZERVASYON_CAKISMA_KODU and "Oda" in sonuc.detail["mesaj"]
    assert sonuc.detail["rezervasyonlar"] == [{"rezervasyon_id": 17, "baslangic": cakisan[0][1].isoformat(),
                                               "bitis": cakisan[0][2].isoformat(), "rezerve_eden": "ayse"}]    # istemci iptal ettirebilsin
    assert not eklendi(imlec)


def test_oda_cakismasi_sorgusu_iptalleri_saymaz_ve_yari_acik_araligi_kullanir():
    _, imlec = rezervasyon()
    sorgu = next(str(c.args[0]) for c in imlec.execute.call_args_list if "r.kullanilacak_oda_id = %s" in str(c.args[0]))
    assert "r.iptal_edildi_mi = FALSE" in sorgu
    assert "r.baslangic_zamani < %s AND r.bitis_zamani > %s" in sorgu                   # bitişle başlangıcı aynı olan ardışık rezervasyon çakışmaz
    parametre = next(c.args[1] for c in imlec.execute.call_args_list if "r.kullanilacak_oda_id = %s" in str(c.args[0]))
    assert parametre == (1, GEL + timedelta(hours=1), GEL)


def test_cakisma_yoksa_rezervasyon_kaydedilir():
    sonuc, imlec = rezervasyon(oda_cakismalari=[])
    assert not isinstance(sonuc, HTTPException), getattr(sonuc, "detail", "")
    assert eklendi(imlec)


def test_oda_secilmemisse_oda_denetimi_yapilmaz():
    gel = GEL
    conn = MagicMock()
    imlec = conn.cursor.return_value
    imlec.execute.side_effect = lambda sorgu, *a, **k: setattr(imlec, "son", str(sorgu))
    imlec.fetchone.side_effect = lambda: ("Kullanima_Hazir",) if "FROM cihazlar" in imlec.son and "durum" in imlec.son else (
        (31,) if "RETURNING rezervasyon_id" in imlec.son else None)
    imlec.fetchall.return_value = []
    model = RezervasyonOlusturModeli(cihaz_id=2, baslangic_zamani=gel, bitis_zamani=gel + timedelta(hours=1))
    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        sunucu.cihaz_rezervasyonu_yap(model, kullanici_id=5)
    assert not any("r.kullanilacak_oda_id = %s" in str(c.args[0]) for c in imlec.execute.call_args_list)


@pytest.mark.parametrize("kisit, beklenen", [
    ("cihaz_rezervasyon_oda_cakisma", "Oda seçilen saat aralığında"),
    ("cihaz_rezervasyon_cakisma", "Cihaz seçilen saat aralığında"),
])
def test_eszamanli_istekte_veritabani_kisiti_dogru_409_mesajini_verir(kisit, beklenen):
    class Hata(psycopg2.errors.ExclusionViolation):
        diag = SimpleNamespace(constraint_name=kisit)
    sonuc, imlec = rezervasyon(hata_ekleme=Hata("x"))
    assert isinstance(sonuc, HTTPException) and sonuc.status_code == 409 and beklenen in sonuc.detail


def test_migrasyon_odanin_zaman_cakismasini_veritabaninda_da_engeller():
    metin = next((KOK / "database/migrations/versions").glob("e7c4b1d9a603_*.py")).read_text(encoding="utf-8")
    assert 'down_revision: Union[str, Sequence[str], None] = "d9a3f6b2c815"' in metin
    assert "cihaz_rezervasyon_oda_cakisma" in metin and "kullanilacak_oda_id WITH =" in metin
    assert "tsrange(baslangic_zamani, bitis_zamani, '[)') WITH &&" in metin
    assert "iptal_edildi_mi = FALSE AND kullanilacak_oda_id IS NOT NULL" in metin          # iptaller ve odasız kayıtlar kuralın dışında
    assert "RAISE EXCEPTION" in metin and "DROP CONSTRAINT IF EXISTS cihaz_rezervasyon_oda_cakisma" in metin
