"""scripts/canli_guvenlik_denemesi.py (SEC-001 canlı ortam denemeleri): PASS/FAIL mantığı, onay kapısı ve kanıt dosyasının sızıntısızlığı."""
import importlib.util
import json
import pathlib
from unittest.mock import MagicMock

import pytest

YOL = pathlib.Path(__file__).resolve().parents[2] / "scripts" / "canli_guvenlik_denemesi.py"
ozellik = importlib.util.spec_from_file_location("canli_guvenlik_denemesi", YOL)
betik = importlib.util.module_from_spec(ozellik)
ozellik.loader.exec_module(betik)

GIZLI_TOKEN = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.GizliImza"
GIZLI_PAROLA = "Cok-Gizli-Parola-2026!"


def _yanit(kod, veri=None, basliklar=None):
    y = MagicMock(status_code=kod, headers=basliklar or {})
    y.json.return_value = veri if veri is not None else {}
    return y


class SahteSunucu:
    """Güvenli bir sunucu gibi davranır; `bozuk` verilen yollar tokensiz bile 200 döner (güvenlik açığı simülasyonu)."""

    def __init__(self, bozuk=()):
        self.bozuk = set(bozuk)
        self.cagrilar = []

    def __call__(self, yontem, url, headers=None, json=None, timeout=None, **_):
        yol = url.split("://", 1)[1].split("/", 1)[1]
        yol = "/" + yol
        token = (headers or {}).get("Authorization", "")
        self.cagrilar.append((yontem, yol, bool(token), json))
        if yol == "/api/saglik":
            return _yanit(200, {"durum": "calisiyor"})
        if yol == "/api/login":
            return _yanit(200, {"access_token": GIZLI_TOKEN, "kullanici_id": 7}) if json["parola"] == GIZLI_PAROLA else _yanit(401, {"detail": "Kullanıcı adı veya parola hatalı."})
        if yol in self.bozuk:
            return _yanit(200, [])
        if not token:
            return _yanit(401, {"detail": "Not authenticated"})
        if token.endswith("abc.def.ghi") or not token.endswith(GIZLI_TOKEN):
            return _yanit(401, {"detail": "Geçersiz token."})
        if yol == "/api/yetkilerim":
            return _yanit(200, {"izinler": []})
        return _yanit(403, {"detail": "Bu işlem için yetkiniz bulunmuyor."})


@pytest.fixture
def calistir(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SEC_PAROLA_PSIKOLOGA", GIZLI_PAROLA)

    def _calistir(sunucu, *argv):
        monkeypatch.setattr(betik.requests.Session, "request", lambda self, *a, **k: sunucu(*a, **k))
        kanit = tmp_path / "kanit.txt"
        kod = betik.main(["--adres", "http://sunucu:8000", "--kanit", str(kanit), *argv])
        return kod, capsys.readouterr().out, kanit.read_text(encoding="utf-8")
    return _calistir


def test_guvenli_sunucuda_t01_t02_t08_gecer_ve_cikis_kodu_sifir(calistir):
    kod, cikti, _ = calistir(SahteSunucu(), "--adimlar", "T01,T02,T08", "--yetkisiz", "psikologA")
    assert kod == 0 and "FAIL" not in cikti.replace("0 FAIL", "") and "ÖZET: 13 PASS, 0 FAIL, 1 ATLANDI" in cikti


def test_korumasiz_uc_fail_verir_ve_cikis_kodu_bir(calistir):
    kod, cikti, _ = calistir(SahteSunucu(bozuk={"/api/cihazlar"}), "--adimlar", "T01")
    assert kod == 1 and "[FAIL] T01.2 GET /api/cihazlar tokensiz" in cikti


def test_yetkisiz_hesap_yonetim_ucuna_girebiliyorsa_t02_fail(calistir):
    guvenli = SahteSunucu()

    def acik(yontem, url, **k):                     # yetkisiz hesabın denetim kayıtlarını okuyabildiği (yetki açığı) sunucu
        if url.endswith("/api/audit-kayitlari") and (k.get("headers") or {}).get("Authorization", "").endswith(GIZLI_TOKEN):
            return _yanit(200, [])
        return guvenli(yontem, url, **k)
    kod, cikti, _ = calistir(acik, "--adimlar", "T02", "--yetkisiz", "psikologA")
    assert kod == 1 and "[FAIL] T02.1 GET /api/audit-kayitlari (psikologA)" in cikti


def test_veri_degistiren_adimlar_onay_olmadan_atlanir_ve_istek_gitmez(calistir):
    sunucu = SahteSunucu()
    kod, cikti, _ = calistir(sunucu, "--adimlar", "T03,T07", "--psikolog-a", "psikologA", "--psikolog-b", "psikologB", "--kilit-hesabi", "psikologA")
    assert kod == 0 and cikti.count("[ATLANDI]") == 2 and "--onay verilmedi" in cikti
    assert sunucu.cagrilar == []                                                        # onay yokken sunucuya hiç istek atılmaz (giriş dahil)


def test_kanit_dosyasi_ve_cikti_token_ya_da_parola_icermez(calistir):
    _, cikti, kanit = calistir(SahteSunucu(), "--adimlar", "T01,T02,T08", "--yetkisiz", "psikologA")
    for metin in (cikti, kanit):
        assert GIZLI_TOKEN not in metin and GIZLI_PAROLA not in metin and "Bearer" not in metin
    assert "GizliImza" not in kanit


def test_ayni_hesabin_parolasi_bir_kez_sorulur(monkeypatch):
    sorulan = []
    monkeypatch.delenv("SEC_PAROLA_TEKRARLI", raising=False)
    monkeypatch.setattr(betik, "_PAROLALAR", {})
    monkeypatch.setattr(betik.getpass, "getpass", lambda istem: sorulan.append(istem) or "gizli")
    assert betik.parola_al("tekrarli") == "gizli" and betik.parola_al("tekrarli") == "gizli"
    assert len(sorulan) == 1


def test_gecersiz_adim_adi_kullanim_hatasi_verir():
    with pytest.raises(SystemExit) as hata:
        betik.main(["--adres", "http://x", "--adimlar", "T99"])
    assert hata.value.code == 2


def test_bozuk_token_uretecleri():
    ana = "uc.yuk.imza"
    sahte = betik._sahte_imza(ana)
    assert sahte != ana and sahte.rpartition(".")[0] == "uc.yuk" and len(sahte) == len(ana)
    imzasiz = betik._alg_none("a." + "eyJzdWIiOiIxIn0" + ".c")
    ust, yuk, imza = imzasiz.split(".")
    assert imza == "" and yuk == "eyJzdWIiOiIxIn0" and json.loads(__import__("base64").urlsafe_b64decode(ust + "==")) == {"alg": "none", "typ": "JWT"}
