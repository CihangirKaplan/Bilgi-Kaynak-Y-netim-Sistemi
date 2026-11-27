"""TKYS - API uç listesini (yöntem, yol, gereken izin) Markdown olarak üretir.

Kullanım (proje klasöründen):
    python scripts/api_uc_listesi_uret.py            # docs/API/Uc_Listesi.md dosyasını yeniden yazar
    python scripts/api_uc_listesi_uret.py --stdout   # ekrana yazar

Sunucu kodundaki gerçek yönlendirmelerden üretilir; elle yazılmış bir liste değildir. İzin adı, uçtaki `izin_kontrol('...')` bağımlılığından okunur.
"""
import argparse
import os
import sys
from collections import defaultdict
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK))
os.environ.setdefault("JWT_SECRET", "x" * 48)          # yalnızca uygulamayı içe aktarmak için; hiçbir şey çalıştırılmaz

from fastapi.routing import APIRoute  # noqa: E402

from server.sunucu import app  # noqa: E402


def izinleri_bul(bagimlilik):
    """Uçtaki izin_kontrol('...') / izin_kontrol_tumu(...) / izin_kontrol_biri(...) bağımlılıklarının izin adları."""
    bulunan = []
    for alt in bagimlilik.dependencies:
        cagri = alt.call
        ad = getattr(cagri, "__qualname__", "")
        if ad.startswith("izin_kontrol.") and cagri.__closure__:
            bulunan += [h.cell_contents for h in cagri.__closure__ if isinstance(h.cell_contents, str)]
        elif ad.startswith(("izin_kontrol_tumu.", "izin_kontrol_biri.")) and cagri.__closure__:     # birden çok izin (tümü ya da biri)
            for hucre in cagri.__closure__:
                if isinstance(hucre.cell_contents, (tuple, list)):
                    bulunan += [str(x) for x in hucre.cell_contents]
        bulunan += izinleri_bul(alt)
    return bulunan


def api_rotalari(rotalar):
    """`include_router` ile eklenen yönlendiricilerin içindeki uçlar dahil, bütün APIRoute'ları gezer."""
    for rota in rotalar:
        if isinstance(rota, APIRoute):
            yield rota
        elif getattr(rota, "original_router", None) is not None:
            yield from api_rotalari(rota.original_router.routes)
        else:
            yield from api_rotalari(getattr(rota, "routes", []))


def uclari_topla():
    satirlar = []
    for r in api_rotalari(app.routes):
        if True:
            if not isinstance(r, APIRoute) or not r.path.startswith("/api"):
                continue
            izinler = sorted(set(izinleri_bul(r.dependant)))
            ozet = (r.summary or (r.endpoint.__doc__ or "").strip().splitlines()[0] if (r.endpoint.__doc__ or "").strip() else r.endpoint.__name__)
            for yontem in sorted(r.methods - {"HEAD", "OPTIONS"}):
                satirlar.append((r.path, yontem, ", ".join(izinler) or "—", ozet))
    return sorted(satirlar)


def markdown_uret():
    satirlar = uclari_topla()
    gruplar = defaultdict(list)
    for yol, yontem, izin, ozet in satirlar:
        parcalar = yol.split("/")
        gruplar[parcalar[2] if len(parcalar) > 2 else "diğer"].append((yol, yontem, izin, ozet))
    cikti = [
        "# TKYS API Uç Listesi",
        "",
        "Bu dosya **sunucu kodundan otomatik üretilir** (`python scripts/api_uc_listesi_uret.py`); elle düzenlemeyin.",
        f"Toplam **{len(satirlar)}** uç. **İzin** sütunu, ucu çağırmak için rolün sahip olması gereken izindir (`—`: yalnızca giriş yapmış olmak yeterli ya da uç kendi kuralını uygular;",
        "gerekçeler `tests/security/test_uc_koruma_taramasi.py` içindedir).",
        "",
        "Etkileşimli API belgesi (`/docs`) **varsayılan olarak kapalıdır**; yalnızca teknik kişi gerektiğinde sunucunun `.env` dosyasına `TKYS_API_DOCS=1` yazarak açar.",
        "",
        "Kimlik doğrulama: `Authorization: Bearer <JWT>` başlığı (giriş: `POST /api/login`). Hatalar `{\"detail\": \"...\"}` biçimindedir; yetki yoksa **403**, oturum geçersizse **401**, doğrulama hatasında **422**.",
        "",
    ]
    for grup in sorted(gruplar):
        cikti += [f"## /api/{grup}", "", "| Yöntem | Yol | İzin | Açıklama |", "|---|---|---|---|"]
        for yol, yontem, izin, ozet in gruplar[grup]:
            ozet = ozet.replace("|", "\\|")[:110]
            cikti.append(f"| {yontem} | `{yol}` | {izin} | {ozet} |")
        cikti.append("")
    return "\n".join(cikti)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stdout", action="store_true")
    args = ap.parse_args()
    metin = markdown_uret()
    if args.stdout:
        print(metin)
        return
    hedef = KOK / "docs" / "API" / "Uc_Listesi.md"
    hedef.write_text(metin + "\n", encoding="utf-8")
    print(f"Yazıldı: {hedef} ({metin.count(chr(10)) + 1} satır)")


if __name__ == "__main__":
    main()
