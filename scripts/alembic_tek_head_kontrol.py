"""TKYS - Alembic migration zincirinde TEK head olduğunu denetler (veritabanı gerekmez).

Neden: İki kişi aynı anda migration eklediğinde zincir ikiye ayrılır ("Multiple head revisions"); `alembic upgrade head`
ve CI'daki PostgreSQL testleri hata verir. Bu betik bunu saniyeler içinde, anlaşılır bir açıklamayla yakalar.
Yerelde de çalıştırılabilir (PR açmadan / merge etmeden önce):

    git fetch origin
    git merge origin/develop
    python scripts/alembic_tek_head_kontrol.py

Çıkış kodu: 0 = tek head (sorun yok), 1 = birden fazla head ya da zincir bozuk.
"""

import os
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]


def _ilk_satir(metin):
    for satir in (metin or "").splitlines():
        if satir.strip():
            return satir.strip()
    return ""


def kontrol_et(betik_dizini=None):
    """(çıkış_kodu, mesaj) döndürür. betik_dizini verilmezse projenin alembic.ini ayarı kullanılır."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    try:
        if betik_dizini is None:
            betikler = ScriptDirectory.from_config(Config(str(KOK / "alembic.ini")))
        else:
            betikler = ScriptDirectory(str(betik_dizini))
        headler = list(betikler.get_heads())
    except Exception as hata:    # bozuk zincirde Alembic türüne göre CommandError ya da KeyError verir
        return 1, (f"Migration zinciri okunamadı ({type(hata).__name__}: {hata}). Olmayan bir revizyona bağlanan "
                   "ya da aynı revizyon kimliğini kullanan bir migration dosyası olabilir.")

    if len(headler) == 1:
        return 0, f"Tek head var: {headler[0]}"

    satirlar = [f"Birden fazla migration head'i var ({len(headler)}): " + ", ".join(headler), ""]
    for rev_id in headler:
        rev = betikler.get_revision(rev_id)
        yol = Path(rev.path)
        try:
            yol = yol.relative_to(KOK)
        except ValueError:
            pass
        satirlar.append(f"  - {rev_id}  ({yol})  önceki: {rev.down_revision}  {_ilk_satir(rev.doc)}")
    satirlar += [
        "",
        "Nedeni: genellikle başka bir PR develop'a yeni bir migration eklemiştir ve sizin migration'ınız onun öncesine bağlıdır.",
        "Düzeltme:",
        "  1. git fetch origin && git merge origin/develop",
        "  2. Kendi migration dosyanızdaki 'down_revision' değerini, develop'taki güncel head'e bağlayın",
        "     (yukarıdaki listede sizin PR'ınıza ait olmayan head) ve dosyanın üstündeki 'Revises:' satırını da güncelleyin.",
        "  3. python -m alembic heads   ->   tek satır çıkmalı; sonra push edin.",
    ]
    return 1, "\n".join(satirlar)


def main():
    kod, mesaj = kontrol_et()
    print(mesaj)
    if kod != 0 and os.getenv("GITHUB_ACTIONS") == "true":
        # GitHub'da PR'ın kontrol ekranında görünen açıklama (satır sonları %0A ile kodlanır).
        kisa = mesaj.replace("%", "%25").replace("\r", "").replace("\n", "%0A")
        print(f"::error title=Alembic migration zinciri hatali::{kisa}")
    return kod


if __name__ == "__main__":
    sys.exit(main())
