"""Bakım planı kayıtlara gerçekten bağlı mı?

Plan tek başına bir liste olmaktan çıkar: bakım/kalibrasyon kaydı plana bağlanınca sonraki tarih
plan periyoduna göre dolar ve planın tarihi ilerler; plan, dashboard'daki yaklaşan işlemlere girer.
Gerçek veritabanına dokunulmaz.
"""
import datetime
from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

import sunucu
from modeller import BakimOlusturModeli, KalibrasyonOlusturModeli


class SahteImlec:
    """Sorguya göre fetchone/fetchall döndürür; çalışan sorguları kaydeder."""

    def __init__(self, plan=None, periyot=30):
        self.plan = plan            # (cihaz_id, gorev_turu, aktif_mi) ya da None
        self.periyot = periyot
        self.sorgular = []
        self._son = ""

    def execute(self, sorgu, parametreler=None):
        self._son = " ".join(sorgu.split())
        self.sorgular.append((self._son, parametreler))

    def fetchone(self):
        if "SELECT periyot_gun" in self._son:
            return None if self.plan is None else (self.periyot,)
        if "SELECT cihaz_id, gorev_turu" in self._son:
            return self.plan
        if "RETURNING" in self._son:
            return (501,)
        return None

    def fetchall(self):
        return []

    def close(self):
        pass

    def calisan(self, parca):
        return [(s, p) for s, p in self.sorgular if parca in s]


def bagla(imlec):
    conn = MagicMock()
    conn.cursor.return_value = imlec
    return conn


def bakim_ekle(model, imlec):
    with patch("sunucu.psycopg2.connect", return_value=bagla(imlec)), patch("denetim.denetim_kaydi_olustur"):
        return sunucu.bakim_kaydi_ekle(model, 1)


def kalibrasyon_ekle(model, imlec):
    with patch("sunucu.psycopg2.connect", return_value=bagla(imlec)), patch("denetim.denetim_kaydi_olustur"):
        return sunucu.kalibrasyon_kaydi_ekle(model, 1)


def bakim(**ek):
    veri = dict(cihaz_id=1, bakim_tarihi=date(2026, 11, 1), bakim_yapan_kisi="Teknisyen", yapilan_islem="Genel kontrol",
                bakim_baslangic_tarihi=date(2026, 11, 1), bakim_bitis_tarihi=date(2026, 11, 1))
    veri.update(ek)
    return BakimOlusturModeli(**veri)


def kalibrasyon(**ek):
    veri = dict(cihaz_id=1, kalibrasyon_yapan_kurum="TSE", gecerlilik_tarihi=date(2027, 11, 1), sertifika_no="S-1",
                kalibrasyon_baslangic_tarihi=date(2026, 11, 1), kalibrasyon_bitis_tarihi=date(2026, 11, 1))
    veri.update(ek)
    return KalibrasyonOlusturModeli(**veri)


# ------------------------------------------------------------------ tür kuralı
@pytest.mark.parametrize("tur,beklenen", [
    ("Kalibrasyon", True), ("kalibrasyon yıllık", True), ("  Kalibrasyon ", True),
    ("Genel bakım", False), ("Filtre değişimi", False), ("", False), (None, False),
])
def test_plan_turu_kalibrasyon_mu(tur, beklenen):
    assert sunucu.plan_kalibrasyon_mu(tur) is beklenen


# ------------------------------------------------------------------ bakım + plan
def test_plansiz_bakim_eskisi_gibi_calisir_ve_plana_dokunmaz():
    imlec = SahteImlec()
    sonuc = bakim_ekle(bakim(sonraki_bakim_tarihi=date(2027, 5, 1)), imlec)
    assert sonuc["sonraki_bakim_tarihi"] == "2027-05-01"
    assert not imlec.calisan("cihaz_bakim_planlari")


def test_plana_bagli_bakimda_tarih_bossa_bitis_artı_periyot_olur_ve_plan_ilerler():
    imlec = SahteImlec(plan=(1, "Genel bakım", True), periyot=90)
    sonuc = bakim_ekle(bakim(plan_id=7), imlec)
    assert sonuc["sonraki_bakim_tarihi"] == "2027-01-30"                      # 1 Kasım 2026 + 90 gün
    guncelleme = imlec.calisan("UPDATE cihaz_bakim_planlari")
    assert len(guncelleme) == 1 and guncelleme[0][1] == (date(2026, 11, 1) + datetime.timedelta(days=90), 7)
    ekleme = imlec.calisan("INSERT INTO cihaz_bakimlari")[0][1]
    assert ekleme[7] == date(2026, 11, 1) + datetime.timedelta(days=90)        # kayda da aynı tarih yazılır


def test_plana_bagli_bakimda_kullanicinin_girdigi_tarih_korunur_ve_plan_ona_ilerler():
    imlec = SahteImlec(plan=(1, "Genel bakım", True), periyot=90)
    sonuc = bakim_ekle(bakim(plan_id=7, sonraki_bakim_tarihi=date(2027, 1, 15)), imlec)
    assert sonuc["sonraki_bakim_tarihi"] == "2027-01-15"
    assert imlec.calisan("UPDATE cihaz_bakim_planlari")[0][1] == (date(2027, 1, 15), 7)


@pytest.mark.parametrize("plan,durum,parca", [
    (None, 404, "bulunamadı"),
    ((2, "Genel bakım", True), 422, "bu cihaza ait değil"),
    ((1, "Genel bakım", False), 422, "pasif"),
    ((1, "Kalibrasyon", True), 422, "uyuşmuyor"),
])
def test_gecersiz_planli_bakim_kaydedilmez(plan, durum, parca):
    imlec = SahteImlec(plan=plan)
    with pytest.raises(HTTPException) as hata:
        bakim_ekle(bakim(plan_id=7, sonraki_bakim_tarihi=date(2027, 1, 15)), imlec)
    assert hata.value.status_code == durum and parca in hata.value.detail
    assert not imlec.calisan("INSERT INTO cihaz_bakimlari")
    assert not imlec.calisan("UPDATE cihaz_bakim_planlari")


def test_olmayan_plan_tarihsiz_bakimda_da_404_verir():
    imlec = SahteImlec(plan=None)
    with pytest.raises(HTTPException) as hata:
        bakim_ekle(bakim(plan_id=7), imlec)
    assert hata.value.status_code == 404 and not imlec.calisan("INSERT INTO cihaz_bakimlari")


# ------------------------------------------------------------ kalibrasyon + plan
def test_plana_bagli_kalibrasyonda_plan_gecerlilik_tarihine_ilerler():
    imlec = SahteImlec(plan=(1, "Kalibrasyon", True))
    sonuc = kalibrasyon_ekle(kalibrasyon(plan_id=3), imlec)
    assert sonuc["durum"] == "basarili"
    assert imlec.calisan("UPDATE cihaz_bakim_planlari")[0][1] == (date(2027, 11, 1), 3)


def test_kalibrasyon_kaydi_bakim_planina_baglanamaz():
    imlec = SahteImlec(plan=(1, "Genel bakım", True))
    with pytest.raises(HTTPException) as hata:
        kalibrasyon_ekle(kalibrasyon(plan_id=3), imlec)
    assert hata.value.status_code == 422 and not imlec.calisan("INSERT INTO cihaz_kalibrasyonlari")


def test_plansiz_kalibrasyon_plana_dokunmaz():
    imlec = SahteImlec()
    kalibrasyon_ekle(kalibrasyon(), imlec)
    assert not imlec.calisan("cihaz_bakim_planlari")


@pytest.mark.parametrize("sinif,alan", [(BakimOlusturModeli, "bakim"), (KalibrasyonOlusturModeli, "kalibrasyon")])
def test_plan_kimligi_pozitif_olmali(sinif, alan):
    uretici = bakim if alan == "bakim" else kalibrasyon
    assert uretici(plan_id=None).plan_id is None
    for kotu in (0, -1):
        with pytest.raises(ValueError):
            uretici(plan_id=kotu)


# ---------------------------------------------------------- dashboard: yaklaşan işlemler
BUGUN = date.today()


def gun(n):
    return BUGUN + datetime.timedelta(days=n)


def yaklasanlar(bakimlar=(), kalibrasyonlar=(), planlar=()):
    conn = MagicMock()
    conn.cursor.return_value.fetchall.side_effect = [list(bakimlar), list(kalibrasyonlar), list(planlar)]
    with patch("sunucu.psycopg2.connect", return_value=conn):
        return sunucu.yaklasan_islemler_getir(kullanici_id=1)


def test_yaklasan_plan_listede_gorunur_ve_turu_dogru_etiketlenir():
    sonuc = yaklasanlar(planlar=[("E1", "EEG", "Genel bakım", gun(5), 7), ("E2", "Tens", "Kalibrasyon", gun(3), 7)])
    assert [(s["cihaz_adi"], s["islem_turu"], s["kalan_gun"]) for s in sonuc] == [
        ("E2 - Tens", "Kalibrasyon", 3), ("E1 - EEG", "Bakım", 5)]
    assert all(s["durum_kodu"] == "KRITIK" for s in sonuc)


def test_uyari_suresi_disindaki_plan_listelenmez_gecikmis_plan_listelenir():
    sonuc = yaklasanlar(planlar=[("E1", "A", "Genel bakım", gun(30), 7), ("E2", "B", "Genel bakım", gun(-4), 0)])
    assert [(s["cihaz_adi"], s["gecikmis"]) for s in sonuc] == [("E2 - B", True)]


def test_kayitla_ayni_cihaz_ve_tarihi_gosteren_plan_tekrar_listelenmez():
    bakim_kaydi = ("E1", "A", gun(4), 30)
    sonuc = yaklasanlar(bakimlar=[bakim_kaydi], planlar=[("E1", "A", "Genel bakım", gun(4), 7)])
    assert len(sonuc) == 1


def test_baska_tarihli_plan_kayitla_birlikte_listelenir():
    sonuc = yaklasanlar(bakimlar=[("E1", "A", gun(4), 30)], planlar=[("E1", "A", "Filtre", gun(2), 7)])
    assert len(sonuc) == 2
