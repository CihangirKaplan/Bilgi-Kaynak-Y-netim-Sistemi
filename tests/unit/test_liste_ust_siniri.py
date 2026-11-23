"""Zamanla büyüyen listelerin (rezervasyon, arıza, bakım, kalibrasyon) üst sınırı ve ekranda gerçek toplamın gösterilmesi."""
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi import Response

import server.sunucu as sunucu
from client.liste_siniri import kisaltma_ipucu, liste_toplami, toplam_etiketi

TARIH = datetime(2026, 11, 20, 10, 0)

# Uç noktanın beklediği satır genişlikleri (sütun sayısı) ve çağrılacak fonksiyon.
UCLAR = [
    ("rezervasyonlar", "rezervasyonlari_listele", 15),
    ("arizalar", "arizalari_listele", 10),
    ("bakimlar", "bakimlari_listele", 13),
    ("kalibrasyonlar", "kalibrasyonlari_listele", 12),
]


def _satir(genislik, no):
    """Her sütuna zararsız bir değer: tarih gibi kullanılanlara datetime, kalanına metin/sayı."""
    satir = [f"v{no}-{i}" for i in range(genislik)]
    satir[0] = no
    if genislik > 5:
        satir[5] = 12.5                                       # bakımda maliyet, diğerlerinde bayrak olarak kullanılır
    for sira in (3, 4, 6, 7, 8, 9):
        if sira < genislik:
            satir[sira] = TARIH
    return tuple(satir)


def _calistir(fonksiyon_adi, genislik, satir_sayisi, toplam=None):
    baglanti = MagicMock()
    imlec = baglanti.cursor.return_value
    imlec.fetchall.return_value = [_satir(genislik, n) for n in range(1, satir_sayisi + 1)]
    imlec.fetchone.return_value = (toplam,)
    yanit = Response()
    with patch("server.sunucu.psycopg2.connect", return_value=baglanti):
        liste = getattr(sunucu, fonksiyon_adi)(response=yanit, kullanici_id=1)
    return liste, yanit, imlec


@pytest.mark.parametrize("ad, fonksiyon, genislik", UCLAR)
def test_sinira_ulasilmayinca_eskisi_gibi_basliksiz_ve_ek_sorgusuz(ad, fonksiyon, genislik):
    liste, yanit, imlec = _calistir(fonksiyon, genislik, 3)
    assert len(liste) == 3
    assert "X-Toplam-Kayit" not in yanit.headers
    assert imlec.execute.call_count == 1                                           # COUNT sorgusu çalışmaz
    assert sunucu.LISTE_UST_SINIRI in imlec.execute.call_args.args[1]              # LIMIT parametresi olarak gönderilir
    assert "LIMIT %s" in imlec.execute.call_args.args[0].replace("\n", " ")


@pytest.mark.parametrize("ad, fonksiyon, genislik", UCLAR)
def test_sinira_ulasilinca_gercek_toplam_baslikta_gelir(ad, fonksiyon, genislik):
    with patch("server.sunucu.LISTE_UST_SINIRI", 2):
        liste, yanit, imlec = _calistir(fonksiyon, genislik, 2, toplam=7312)
    assert len(liste) == 2
    assert yanit.headers["X-Toplam-Kayit"] == "7312"
    assert imlec.execute.call_count == 2
    assert imlec.execute.call_args.args[0].startswith("SELECT COUNT(*) FROM cihaz_")


@pytest.mark.parametrize("ad, fonksiyon, genislik", UCLAR)
def test_dogrudan_cagrida_response_verilmezse_sorun_cikmaz(ad, fonksiyon, genislik):
    """Eski çağıranlar (testler) response vermez; sınıra ulaşılsa bile hata çıkmaz."""
    baglanti = MagicMock()
    baglanti.cursor.return_value.fetchall.return_value = [_satir(genislik, 1), _satir(genislik, 2)]
    with patch("server.sunucu.psycopg2.connect", return_value=baglanti), patch("server.sunucu.LISTE_UST_SINIRI", 2):
        assert len(getattr(sunucu, fonksiyon)(kullanici_id=1)) == 2


def test_makul_bir_ust_sinir_secilmis():
    assert 1000 <= sunucu.LISTE_UST_SINIRI <= 20000


# ---------------- istemci yardımcıları ----------------
class _Yanit:
    def __init__(self, basliklar):
        self.headers = basliklar


def test_toplam_baslik_yoksa_gorunen_sayidir():
    assert liste_toplami(_Yanit({}), 40) == 40


def test_toplam_baslikta_ve_gorunenden_buyukse_o_kullanilir():
    assert liste_toplami(_Yanit({"X-Toplam-Kayit": "7312"}), 5000) == 7312


@pytest.mark.parametrize("baslik", ["abc", "", None, "-5", "10"])
def test_bozuk_ya_da_kucuk_baslik_gorunen_sayiyi_degistirmez(baslik):
    assert liste_toplami(_Yanit({"X-Toplam-Kayit": baslik}), 40) == 40


def test_sahte_yanit_nesnesi_toplami_bozmaz():
    assert liste_toplami(MagicMock(), 40) == 40                # sahte nesnenin başlığı sayıya çevrilse de görünenden büyük olmaz
    assert liste_toplami(object(), 40) == 40


def test_etiket_ve_ipucu_yalniz_kisaltildiginda_degisir():
    assert toplam_etiketi(12, 12) == "12 kayıt" and kisaltma_ipucu(12, 12) == ""
    assert toplam_etiketi(5000, 7312) == "en yeni 5000 / toplam 7312 kayıt"
    assert toplam_etiketi(5000, 7312, "rezervasyon") == "en yeni 5000 / toplam 7312 rezervasyon"
    assert "7312" in kisaltma_ipucu(5000, 7312)
