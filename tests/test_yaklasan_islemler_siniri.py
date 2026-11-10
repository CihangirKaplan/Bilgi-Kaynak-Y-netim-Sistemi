"""Yaklaşan/geciken bakım ve kalibrasyon listesi: sınır 50'dir; fazla kayıt sessizce kesilmez, en acil olanlar önce gelir."""
import datetime
from unittest.mock import MagicMock, patch

import sunucu

BUGUN = datetime.date.today()


def gun(n):
    return BUGUN + datetime.timedelta(days=n)


def liste(n_bakim, n_kalibrasyon=0):
    """Hepsi uyarı süresi içinde (kayıt başına 30 gün): kalan günler -n..0 arasında."""
    bakimlar = [(f"B{i}", f"Cihaz B{i}", gun(-i), 30) for i in range(n_bakim)]
    kalibrasyonlar = [(f"K{i}", f"Cihaz K{i}", gun(-i - 1), 30) for i in range(n_kalibrasyon)]
    conn = MagicMock()
    conn.cursor.return_value.fetchall.side_effect = [bakimlar, kalibrasyonlar, []]
    with patch("sunucu.psycopg2.connect", return_value=conn):
        return sunucu.yaklasan_islemler_getir(kullanici_id=1)


def test_sinir_50dir():
    assert sunucu.YAKLASAN_ISLEM_UST_SINIR == 50


def test_10dan_fazla_geciken_kayit_artik_kesilmez():
    sonuc = liste(15)
    assert len(sonuc) == 15                                        # eskiden 10'da kesilirdi


def test_sinirin_tam_altinda_ve_tam_sinirda_hepsi_gelir():
    assert len(liste(49)) == 49 and len(liste(50)) == 50


def test_sinir_asilirsa_en_acil_50_kayit_doner_geri_kalan_kesilir():
    sonuc = liste(40, 30)                                          # 70 kayıt
    assert len(sonuc) == 50
    assert sonuc[0]["kalan_gun"] == min(i["kalan_gun"] for i in sonuc)           # en çok geciken en üstte
    assert [i["kalan_gun"] for i in sonuc] == sorted(i["kalan_gun"] for i in sonuc)
    # kesilenler en az acil olanlardır: dönen en büyük kalan gün, dışarıda kalanlardan büyük değildir
    tum = sorted([-i for i in range(40)] + [-i - 1 for i in range(30)])
    assert sorted(i["kalan_gun"] for i in sonuc) == tum[:50]


def test_az_kayitta_hepsi_gelir():
    assert len(liste(3, 2)) == 5 and liste(0) == []
