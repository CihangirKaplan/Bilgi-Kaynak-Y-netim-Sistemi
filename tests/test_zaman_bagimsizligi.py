"""Testler modül yüklenirken 'bugün/şimdi' değerini sabitlememeli.

`BUGUN = date.today()` gibi satırlar test oturumu gece yarısını geçerse (CI birkaç dakika sürer) yanlış gün
kullanır ve testi sebepsiz kırar. Tarihi her kullanıldığı yerde hesaplayın (ör. `gun(n)` yardımcısında).
"""
import re
from pathlib import Path

TEST_KLASORU = Path(__file__).resolve().parent
YASAK = re.compile(r"^[A-Za-z_]\w*\s*=\s*(?:datetime\.)?(?:date|datetime|D)\.(?:today|now)\(\)\s*(?:#.*)?$")


def modul_duzeyinde_bugun_atamalari(metin):
    return [(no, satir) for no, satir in enumerate(metin.splitlines(), 1) if YASAK.match(satir)]


def test_hicbir_test_dosyasi_bugunu_modul_duzeyinde_sabitlemez():
    sorunlar = []
    for dosya in sorted(TEST_KLASORU.glob("test_*.py")):
        for no, satir in modul_duzeyinde_bugun_atamalari(dosya.read_text(encoding="utf-8")):
            sorunlar.append(f"{dosya.name}:{no}: {satir.strip()}")
    assert not sorunlar, "Modül düzeyinde today()/now() atamaları:\n" + "\n".join(sorunlar)


def test_kalip_gercekten_yakalar_ve_icerideki_kullanima_dokunmaz():
    assert modul_duzeyinde_bugun_atamalari("BUGUN = date.today()")
    assert modul_duzeyinde_bugun_atamalari("BUGUN = D.today()")                      # D = datetime.date takma adı
    assert modul_duzeyinde_bugun_atamalari("ZAMAN = datetime.datetime.now()")
    assert modul_duzeyinde_bugun_atamalari("X = datetime.date.today()  # yorum")
    assert modul_duzeyinde_bugun_atamalari("    bugun = date.today()") == []          # fonksiyon içi, girintili: serbest
    assert modul_duzeyinde_bugun_atamalari("def gun(n):\n    return date.today()") == []
