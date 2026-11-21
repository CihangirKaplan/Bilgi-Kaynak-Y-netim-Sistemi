"""Yönetim raporları: karşılaştırılan önceki dönem takvime göre seçilir (yöneticinin beklediği gibi)."""
from datetime import date

import pytest

from server.sunucu import _yonetim_onceki_donem


@pytest.mark.parametrize("baslangic, bitis, beklenen", [
    # Bu Ay (ayın 1'i - bugün): geçen ayın aynı günleri
    (date(2026, 11, 1), date(2026, 11, 21), (date(2026, 10, 1), date(2026, 10, 21))),
    # Geçen Ay (ayın tamamı): önceki ayın tamamı (31 günün karşılığı 30 gün)
    (date(2026, 10, 1), date(2026, 10, 31), (date(2026, 9, 1), date(2026, 9, 30))),
    (date(2026, 3, 1), date(2026, 3, 31), (date(2026, 2, 1), date(2026, 2, 28))),
    # Ayın 30'una kadar: kısa önceki ayda ay sonunda durur
    (date(2026, 3, 1), date(2026, 3, 30), (date(2026, 2, 1), date(2026, 2, 28))),
    # Ocak: önceki yılın aralığı
    (date(2027, 1, 1), date(2027, 1, 10), (date(2026, 12, 1), date(2026, 12, 10))),
    # Bu Hafta (pazartesi - cumartesi): geçen haftanın aynı günleri
    (date(2026, 11, 16), date(2026, 11, 21), (date(2026, 11, 9), date(2026, 11, 14))),
    # Bugün (pazar): geçen pazar
    (date(2026, 11, 22), date(2026, 11, 22), (date(2026, 11, 15), date(2026, 11, 15))),
    # Serbest aralık: hemen önceki aynı uzunluktaki aralık
    (date(2026, 11, 5), date(2026, 11, 14), (date(2026, 10, 26), date(2026, 11, 4))),
])
def test_onceki_donem_takvime_gore_secilir(baslangic, bitis, beklenen):
    assert _yonetim_onceki_donem(baslangic, bitis) == beklenen
