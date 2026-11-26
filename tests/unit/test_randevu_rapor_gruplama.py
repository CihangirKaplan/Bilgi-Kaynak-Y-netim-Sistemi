"""Randevu raporu: SQL'de gruplanmış satırlarla hesap, satır satır hesapla birebir aynı sonucu vermeli (rastgele verilerle)."""
import random
from datetime import date, datetime, timedelta

import pytest

from server.randevu_rapor_hesapla import randevu_raporu_hesapla

ETIKET = {"iptal": {"DANISAN_TALEBI": "Danışan talebi", "DIGER": "Diğer"}, "gorusme": {"YUZ_YUZE": "Yüz yüze", "ONLINE": "Online"},
          "terapi": {"OYUN_TERAPISI": "Oyun", "BIREYSEL_TERAPI": "Bireysel"}, "yas": {"COCUK": "Çocuk", "YETISKIN": "Yetişkin"}}
BUGUN = date(2026, 11, 26)


def rastgele_satirlar(rng, n):
    satirlar = []
    for i in range(n):
        durum = rng.choice(["PLANLANDI", "TAMAMLANDI", "GELMEDI", "IPTAL_EDILDI"])
        gun = BUGUN + timedelta(days=rng.randint(-60, 30))
        satirlar.append({
            "randevu_id": i, "danisan_kod_id": f"K-{rng.randint(1, 15)}", "psikolog_id": rng.choice([1, 2, 3, None]), "psikolog_adi": rng.choice(["Ayşe", "Fatma", None]),
            "oda_id": rng.randint(1, 3), "oda_adi": "Oda", "baslangic_zamani": datetime(gun.year, gun.month, gun.day, 10), "bitis_zamani": datetime(gun.year, gun.month, gun.day, 11),
            "durum": durum, "iptal_nedeni": rng.choice([None, "DANISAN_TALEBI", "DIGER"]) if durum == "IPTAL_EDILDI" else None,
            "gorusme_tipi": rng.choice(["YUZ_YUZE", "ONLINE", None]), "terapi_turu": rng.choice(["OYUN_TERAPISI", "BIREYSEL_TERAPI", None]),
            "yas_grubu": rng.choice(["COCUK", "YETISKIN", None]),
        })
    return satirlar


def grupla(satirlar):
    """SQL GROUP BY'ın taklidi: anahtar sütunlar + geçmiş mi -> adet; benzersiz danışan sayısı ayrı."""
    gruplar = {}
    for s in satirlar:
        k = (s["psikolog_id"], s["psikolog_adi"], s["durum"], s["iptal_nedeni"], s["gorusme_tipi"], s["terapi_turu"], s["yas_grubu"], s["baslangic_zamani"].date() < BUGUN)
        gruplar[k] = gruplar.get(k, 0) + 1
    liste = [{"psikolog_id": k[0], "psikolog_adi": k[1], "durum": k[2], "iptal_nedeni": k[3], "gorusme_tipi": k[4], "terapi_turu": k[5], "yas_grubu": k[6],
              "gecmis": k[7], "adet": adet} for k, adet in gruplar.items()]
    return liste, len({s["danisan_kod_id"] for s in satirlar})


@pytest.mark.parametrize("tohum", range(8))
def test_gruplu_hesap_satir_satir_hesapla_ayni(tohum):
    satirlar = rastgele_satirlar(random.Random(tohum), 400)
    beklenen = randevu_raporu_hesapla(satirlar, ETIKET, bugun=BUGUN)
    gruplar, danisan = grupla(satirlar)
    assert len(gruplar) < len(satirlar)                                                  # gerçekten gruplandı
    assert randevu_raporu_hesapla(gruplar, ETIKET, bugun=BUGUN, danisan_sayisi=danisan) == beklenen


def test_bos_veri_ve_tek_satir():
    assert randevu_raporu_hesapla([], ETIKET, bugun=BUGUN, danisan_sayisi=0) == randevu_raporu_hesapla([], ETIKET, bugun=BUGUN)
    satirlar = rastgele_satirlar(random.Random(99), 1)
    gruplar, danisan = grupla(satirlar)
    assert randevu_raporu_hesapla(gruplar, ETIKET, bugun=BUGUN, danisan_sayisi=danisan) == randevu_raporu_hesapla(satirlar, ETIKET, bugun=BUGUN)


def test_tek_tek_satirlar_eskisi_gibi_calisir_adet_yoksa_bir_sayilir():
    satirlar = rastgele_satirlar(random.Random(5), 50)
    assert randevu_raporu_hesapla(satirlar, ETIKET, bugun=BUGUN)["ozet"]["toplam"] == 50
