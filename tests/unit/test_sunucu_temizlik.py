"""server/sunucu.py temizliği: hata yolunun çökmemesi ve kalıntı bırakılmaması."""
import ast
import logging
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import server.sunucu as sunucu

KAYNAK = Path(sunucu.__file__).read_text(encoding="utf-8")
AGAC = ast.parse(KAYNAK)


def test_sistem_durumu_alinamazsa_planlanan_mesajla_500_doner_ve_neden_gunluge_yazilir(caplog):
    """Eskiden hata yolunda `logging` tanımsızdı: NameError asıl hatayı gizleyip beklenmeyen bir çökmeye yol açıyordu."""
    rota = next(r for r in sunucu.app.routes if getattr(r, "path", None) == "/api/sistem-durumu")
    izin_bagimliligi = rota.dependant.dependencies[0].call                              # izin_kontrol(...) (kendi veritabanı sorgusunu yapar)
    sunucu.app.dependency_overrides[izin_bagimliligi] = lambda: 1

    def baglanti_hatasi(*args, **kwargs):
        raise RuntimeError("veritabani yok (deneme)")

    try:
        with patch.object(sunucu.psycopg2, "connect", baglanti_hatasi), caplog.at_level(logging.ERROR):
            yanit = TestClient(sunucu.app, raise_server_exceptions=False).get("/api/sistem-durumu")
    finally:
        sunucu.app.dependency_overrides.pop(izin_bagimliligi, None)

    assert yanit.status_code == 500
    assert yanit.json() == {"detail": "Sistem durumu alınırken bir hata oluştu."}        # NameError olsaydı JSON değil düz metin 500 dönerdi
    assert any("Sistem durumu alınamadı" in k.getMessage() for k in caplog.records)     # neden günlükte


def test_logging_modul_duzeyinde_iceri_aktarilmistir():
    iceri = {a.name for n in AGAC.body if isinstance(n, ast.Import) for a in n.names}
    assert "logging" in iceri


def test_uretim_kodunda_print_yok():
    cagrilar = [n.lineno for n in ast.walk(AGAC) if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "print"]
    assert cagrilar == []          # hatalar merkezi günlüğe (logs/sunucu.log) yazılır; print kullanılmaz


def test_ayni_modeller_iki_kez_iceri_aktarilmamis():
    adlar = []
    for n in AGAC.body:
        if isinstance(n, ast.ImportFrom) and n.module == "server.modeller":
            adlar += [a.asname or a.name for a in n.names]
    tekrar = sorted({a for a in adlar if adlar.count(a) > 1})
    assert tekrar == []


def test_kullanilmayan_rol_kodu_sozlugu_kalmamis():
    """Personel kodu önekleri yalnızca _siradaki_personel_kodu içinde tanımlıdır (kullanici_olustur'da ölü bir kopyası vardı)."""
    kullanici_olustur = next(n for n in AGAC.body if isinstance(n, ast.FunctionDef) and n.name == "kullanici_olustur")
    atamalar = [t.id for n in ast.walk(kullanici_olustur) if isinstance(n, ast.Assign) for t in n.targets if isinstance(t, ast.Name)]
    assert "rol_kodlari" not in atamalar
