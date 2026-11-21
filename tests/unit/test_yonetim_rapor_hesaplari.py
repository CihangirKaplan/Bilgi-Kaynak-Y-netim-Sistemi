"""Yönetim raporları: iptaller hariç sayım, oranlar ve önceki döneme göre değişim rozeti."""
import pytest

import client.yonetim_rapor_hesaplari as h

OZET = {"toplam": 98, "planlandi": 32, "tamamlandi": 49, "gelmedi": 5, "iptal_edildi": 12, "sonucu_girilmemis": 4}


def test_gerceklesen_randevu_iptalleri_saymaz():
    assert h.gerceklesen_randevu(OZET) == 86
    assert h.ileri_tarihli_planli(OZET) == 28                     # 32 planlı - 4 sonucu girilmemiş


def test_oranlar_sonuclanan_randevulara_gore_hesaplanir():
    assert h.gelmeme_orani(OZET) == pytest.approx(5 / 54)
    assert h.tamamlanma_orani(OZET) == pytest.approx(49 / 54)
    assert h.iptal_orani(OZET) == pytest.approx(12 / 98)


def test_sonuclanan_randevu_yoksa_oran_hesaplanmaz():
    bos = {"toplam": 0, "planlandi": 0, "tamamlandi": 0, "gelmedi": 0, "iptal_edildi": 0}
    assert h.gelmeme_orani(bos) is None and h.iptal_orani(bos) is None


@pytest.mark.parametrize("simdi, once, oran, beklenen", [
    (86, 71, False, "▲ %21"),
    (3, 5, False, "▼ %40"),
    (10, 10, False, "= değişmedi"),
    (5, 0, False, "▲ önceki dönemde yok"),
    (0, 0, False, "—"),
    (0.093, 0.105, True, "▼ 1,2 puan"),
    (None, 0.1, True, "—"),
])
def test_degisim_metni(simdi, once, oran, beklenen):
    assert h.degisim_metni(simdi, once, oran) == beklenen


@pytest.mark.parametrize("ok, yon, beklenen", [
    (h.YUKARI, 1, "iyi"), (h.ASAGI, 1, "kotu"),        # artış iyi (ör. faaliyet puanı)
    (h.YUKARI, -1, "kotu"), (h.ASAGI, -1, "iyi"),      # artış kötü (ör. gelmeme oranı, arıza)
    (h.YUKARI, 0, "notr"), (h.AYNI, 1, "notr"), (None, -1, "notr"),
])
def test_rozet_rengi_gostergenin_yonune_gore_secilir(ok, yon, beklenen):
    assert h.rozet_turu(ok, yon) == beklenen
