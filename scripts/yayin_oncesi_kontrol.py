"""TKYS - v1.0.0 yayın öncesi otomatik kontrol (veritabanı ve ağ gerekmez).

Yayın günü rehberindeki (docs/release/Yayin_Gunu_Rehberi_v1.0.0.md) kontrollerin makinece yapılabilen kısmı:

    python scripts/yayin_oncesi_kontrol.py                  # her gün çalıştırılabilir: eksikler UYARI olarak görünür
    python scripts/yayin_oncesi_kontrol.py --go             # yayın anı: UYARI da HATA sayılır (hiçbir eksik kalmamalı)
    python scripts/yayin_oncesi_kontrol.py --belgeleri-main-yap
                                                            # kurulum/güncelleme belgelerinde develop -> main (yalnızca GO'dan sonra)

Çıkış kodu: 0 = hata yok, 1 = en az bir HATA. Betik dosyaları yalnızca OKUR; tek istisna --belgeleri-main-yap'tır.
"""

import argparse
import re
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK))

# Kurulum ve güncelleme komutları geçen belgeler: yayından sonra develop değil main izlenir.
KURULUM_BELGELERI = (
    "docs/deployment/Sunucu_Kurulum_Kilavuzu.md",
    "docs/deployment/Personel_Kullanici_Gecis_Rehberi.md",
    "docs/deployment/windows-sunucu/KURULUM.md",
    "docs/deployment/windows-sunucu/KOMUTLAR.md",
    "user-manuals/administrative/Sistem_Yoneticisi_Kilavuzu.md",
)
# Yalnızca KOMUT biçimleri değiştirilir (açıklama metinlerindeki "develop" sözcüğüne dokunulmaz).
KOMUT_DEGISIMLERI = (
    (re.compile(r"\bgit checkout develop\b"), "git checkout main"),
    (re.compile(r"\bgit switch develop\b"), "git switch main"),
    (re.compile(r"\bgit pull( --ff-only)? origin develop\b"), r"git pull\1 origin main"),
)
YER_TUTUCULAR = {
    "CHANGELOG.md": "GO/NO-GO kararından sonra yazılacak",
    "RELEASE_NOTES.md": "________",
    "docs/test-reports/GO-NO-GO_Kontrol_Listesi.md": "________",
}

OK, UYARI, HATA = "OK", "UYARI", "HATA"


def _oku(yol, kok):
    return (Path(kok) / yol).read_text(encoding="utf-8")


def _surum(yol, kok):
    eslesme = re.search(r'^SURUM\s*=\s*"([^"]+)"', _oku(yol, kok), re.MULTILINE)
    return eslesme.group(1) if eslesme else None


def kontroller(kok=KOK):
    """[(durum, ad, ayrıntı)] döndürür. UYARI = yayın anına kadar giderilmesi gereken eksik; HATA = tutarsızlık/bozukluk."""
    sonuc = []

    istemci, sunucu = _surum("client/surum.py", kok), _surum("server/surum.py", kok)
    if istemci and istemci == sunucu:
        sonuc.append((OK, "Sürüm numarası", f"istemci ve sunucu aynı: {sunucu}"))
    else:
        sonuc.append((HATA, "Sürüm numarası", f"istemci={istemci!r}, sunucu={sunucu!r}: aynı olmalı (Hakkında penceresi uyarı verir)"))
    surum = sunucu or istemci or "?"

    if f"## [{surum}]" in _oku("CHANGELOG.md", kok):
        sonuc.append((OK, "CHANGELOG", f"[{surum}] başlığı var"))
    else:
        sonuc.append((HATA, "CHANGELOG", f"[{surum}] başlığı yok"))
    ilk_satir = _oku("RELEASE_NOTES.md", kok).splitlines()[0]
    sonuc.append((OK, "RELEASE_NOTES", f"başlık: {ilk_satir}") if surum in ilk_satir
                 else (HATA, "RELEASE_NOTES", f"başlıkta {surum} yok: {ilk_satir!r}"))

    try:
        from scripts.alembic_tek_head_kontrol import kontrol_et
        kod, mesaj = kontrol_et(Path(kok) / "database" / "migrations") if (Path(kok) / "database" / "migrations" / "versions").exists() else kontrol_et()
        sonuc.append((OK if kod == 0 else HATA, "Alembic zinciri", mesaj.splitlines()[0]))
    except Exception as hata:
        sonuc.append((HATA, "Alembic zinciri", f"denetlenemedi: {type(hata).__name__}: {hata}"))

    for yol, isaret in YER_TUTUCULAR.items():
        metin = _oku(yol, kok)
        if isaret in metin:
            sonuc.append((UYARI, f"Yayın tarihi/alanı: {yol}", "henüz doldurulmamış (yayın günü doldurulacak)"))
        else:
            sonuc.append((OK, f"Yayın tarihi/alanı: {yol}", "dolu"))

    acik = re.findall(r"^\|\s*(\d+)\s*\|[^\n]*☐\s*\|\s*$", _oku("docs/test-reports/GO-NO-GO_Kontrol_Listesi.md", kok), re.MULTILINE)
    if acik:
        sonuc.append((UYARI, "GO/NO-GO maddeleri", f"{len(acik)} madde açık: " + ", ".join(acik)))
    else:
        sonuc.append((OK, "GO/NO-GO maddeleri", "tüm maddeler işaretli"))

    kalan = [yol for yol in KURULUM_BELGELERI
             if any(desen.search(_oku(yol, kok)) for desen, _ in KOMUT_DEGISIMLERI)]
    if kalan:
        sonuc.append((UYARI, "Kurulum belgeleri hâlâ develop'u izliyor", ", ".join(kalan) + "  (GO'dan sonra: --belgeleri-main-yap)"))
    else:
        sonuc.append((OK, "Kurulum belgeleri", "main dalını izliyor"))
    return sonuc


def belgeleri_main_yap(kok=KOK):
    """Kurulum/güncelleme belgelerindeki git komutlarını develop -> main çevirir. Değişen dosyaların listesini döndürür."""
    degisen = []
    for yol in KURULUM_BELGELERI:
        hedef = Path(kok) / yol
        ham = hedef.read_bytes().decode("utf-8")
        yeni = ham
        for desen, yerine in KOMUT_DEGISIMLERI:
            yeni = desen.sub(yerine, yeni)
        if yeni != ham:
            hedef.write_bytes(yeni.encode("utf-8"))            # satır sonları (CRLF/LF) olduğu gibi korunur
            degisen.append(yol)
    return degisen


def ana(argumanlar=None, kok=KOK):
    ayri = argparse.ArgumentParser(description="TKYS yayın öncesi kontrol")
    ayri.add_argument("--go", action="store_true", help="yayın anı: UYARI'lar da HATA sayılır")
    ayri.add_argument("--belgeleri-main-yap", action="store_true", help="kurulum belgelerinde develop -> main (yalnızca GO'dan sonra)")
    sec = ayri.parse_args(argumanlar)

    if sec.belgeleri_main_yap:
        degisen = belgeleri_main_yap(kok)
        print("Değişen belgeler:" if degisen else "Değişecek bir şey yok (belgeler zaten main'i izliyor).")
        for yol in degisen:
            print("  -", yol)
        return 0

    hatali = False
    for durum, ad, ayrinti in kontroller(kok):
        if sec.go and durum == UYARI:
            durum = HATA
        hatali = hatali or durum == HATA
        print(f"[{durum:6}] {ad}: {ayrinti}")
    print("\nSONUÇ:", "HAZIR DEĞİL — yukarıdaki HATA satırlarını giderin." if hatali else
          ("Hata yok." + ("" if sec.go else " (UYARI satırları yayın gününe kadar giderilmeli.)")))
    return 1 if hatali else 0


if __name__ == "__main__":
    sys.exit(ana())
