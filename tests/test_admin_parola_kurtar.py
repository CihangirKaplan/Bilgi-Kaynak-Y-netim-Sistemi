"""Yönetici parola kurtarma aracı: sahte imleçle, gerçek veritabanına dokunmaz."""
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from guvenlik import parola_dogrula

_yol = Path(__file__).resolve().parents[1] / "scripts" / "admin_parola_kurtar.py"
_spec = importlib.util.spec_from_file_location("admin_parola_kurtar", _yol)
betik = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(betik)


def imlec(*sonuclar, liste=None):
    c = MagicMock()
    c.fetchone.side_effect = list(sonuclar)
    if liste is not None:
        c.fetchall.return_value = liste
    return c


def sorgular(c):
    return [(" ".join(k.args[0].split()), k.args[1] if len(k.args) > 1 else None) for k in c.execute.call_args_list]


# ------------------------------------------------------------------ sıfırlama
def test_admin_parolasi_sifirlanir_ilk_giris_zorunlu_kilit_kalkar_hash_saklanir():
    c = imlec((5, True))
    ad, parola = betik.admin_parolasini_sifirla(c, "admin")
    assert ad == "admin" and len(parola) >= 12
    guncelleme = next(s for s in sorgular(c) if s[0].startswith("UPDATE kullanicilar"))
    assert "ilk_giris_mi = TRUE" in guncelleme[0]
    assert "basarisiz_giris_sayisi = 0" in guncelleme[0] and "kilit_bitis_zamani = NULL" in guncelleme[0]
    yeni_hash, kullanici_id = guncelleme[1]
    assert kullanici_id == 5 and yeni_hash != parola and parola_dogrula(parola, yeni_hash)   # düz yazı saklanmaz


def test_bekleyen_talep_kapanir_ve_denetim_kaydi_yazilir():
    c = imlec((5, True))
    betik.admin_parolasini_sifirla(c, "admin")
    s = sorgular(c)
    talep = next(x for x in s if "parola_sifirlama_talepleri" in x[0])
    assert "durum = 'TAMAMLANDI'" in talep[0] and "durum = 'ACIK'" in talep[0] and talep[1] == (5,)
    denetim = next(x for x in s if "INSERT INTO denetim_kayitlari" in x[0])
    assert denetim[1] == (5, "PASSWORD_RESET", "kullanicilar", 5)


def test_her_seferinde_farkli_parola_uretilir():
    parolalar = {betik.admin_parolasini_sifirla(imlec((5, True)), "admin")[1] for _ in range(5)}
    assert len(parolalar) == 5


def test_admin_olmayan_veya_olmayan_hesap_reddedilir_hicbir_sey_yazilmaz():
    c = imlec(None)
    with pytest.raises(betik.KurtarmaHatasi, match="yönetici \\(ADMIN\\) hesabı bulunamadı"):
        betik.admin_parolasini_sifirla(c, "memur1")
    assert not any(s[0].startswith(("UPDATE", "INSERT")) for s in sorgular(c))


def test_sorgu_rol_adini_admin_ile_sinirlar_ve_kullanici_adi_parametredir():
    c = imlec((5, True))
    betik.admin_parolasini_sifirla(c, "x'; DROP TABLE kullanicilar;--")
    ilk = sorgular(c)[0]
    assert "r.rol_adi = 'ADMIN'" in ilk[0] and ilk[1] == ("x'; DROP TABLE kullanicilar;--",)
    assert "DROP" not in ilk[0]


def test_pasif_hesap_acilmaz():
    c = imlec((5, False))
    with pytest.raises(betik.KurtarmaHatasi, match="pasif"):
        betik.admin_parolasini_sifirla(c, "admin")
    assert not any(s[0].startswith(("UPDATE", "INSERT")) for s in sorgular(c))


# ------------------------------------------------------------------ hesap seçimi
def test_tek_yonetici_varsa_otomatik_secilir_birden_cok_ise_listeden_secilir():
    assert betik.hesap_sec(["admin"], None, girdi=lambda _: "") == "admin"
    assert betik.hesap_sec(["a", "b"], None, girdi=lambda _: "2") == "b"
    assert betik.hesap_sec(["a", "b"], "b", girdi=lambda _: "1") == "b"          # --kullanici-adi öncelikli


@pytest.mark.parametrize("secim", ["", "0", "3", "x", "-1"])
def test_gecersiz_secim_reddedilir(secim):
    with pytest.raises(betik.KurtarmaHatasi, match="Geçersiz seçim"):
        betik.hesap_sec(["a", "b"], None, girdi=lambda _: secim)


def test_aktif_yonetici_yoksa_ilk_admin_betigi_hatirlatilir():
    with pytest.raises(betik.KurtarmaHatasi, match="ilk_admin_olustur"):
        betik.hesap_sec([], None, girdi=lambda _: "")


# ------------------------------------------------------------------ main akışı
def baglanti_taklidi(yoneticiler, hesap=(5, True)):
    conn = MagicMock()
    c = conn.cursor.return_value.__enter__.return_value
    c.fetchall.return_value = [(a,) for a in yoneticiler]
    c.fetchone.side_effect = [hesap]
    return conn, c


def calistir(argv, yanitlar=(), yoneticiler=("admin",), hesap=(5, True)):
    conn, c = baglanti_taklidi(yoneticiler, hesap)
    yanit = iter(yanitlar)
    with patch.object(betik.psycopg2, "connect", return_value=conn):
        kod = betik.main(argv, girdi=lambda _: next(yanit))
    return kod, conn, c


def test_onaysiz_vazgecince_hicbir_sey_degismez(capsys):
    kod, conn, c = calistir([], yanitlar=["hayir"])
    assert kod == 0 and "Vazgeçildi" in capsys.readouterr().out
    conn.commit.assert_not_called()
    assert not any(s[0].startswith("UPDATE") for s in sorgular(c))


@pytest.mark.parametrize("yanit", ["evet", "e", "EVE", "yes", ""])
def test_yalniz_EVET_onay_sayilir(yanit, capsys):
    kod, conn, _ = calistir([], yanitlar=[yanit])
    assert kod == 0 and "Parola sıfırlandı" not in capsys.readouterr().out
    conn.commit.assert_not_called()


def test_EVET_ile_sifirlanir_parola_bir_kez_yazilir_ve_commit_edilir(capsys):
    kod, conn, _ = calistir([], yanitlar=["EVET"])
    cikti = capsys.readouterr().out
    assert kod == 0 and "Parola sıfırlandı" in cikti and "Geçici parola" in cikti and "bir daha gösterilmez" in cikti
    conn.commit.assert_called_once()


def test_evet_bayragi_onay_sormaz(capsys):
    kod, conn, _ = calistir(["--evet", "--kullanici-adi", "admin"])
    assert kod == 0 and "Parola sıfırlandı" in capsys.readouterr().out
    conn.commit.assert_called_once()


def test_hata_olursa_geri_alinir_ve_parola_yazilmaz(capsys):
    kod, conn, _ = calistir(["--evet", "--kullanici-adi", "memur1"], hesap=None)
    cikti = capsys.readouterr().out
    assert kod == 1 and "HATA" in cikti and "Geçici parola" not in cikti
    conn.rollback.assert_called_once()
    conn.commit.assert_not_called()


def test_veritabani_hatasinda_anlasilir_mesaj_ve_sifre_sizmaz(capsys):
    with patch.object(betik.psycopg2, "connect", side_effect=betik.psycopg2.OperationalError("parola: gizli123")):
        kod = betik.main(["--evet"], girdi=lambda _: "")
    cikti = capsys.readouterr().out
    assert kod == 1 and ".env" in cikti and "gizli123" not in cikti


# ------------------------------------------------------------------ kullanıcıyı yönlendiren yerler
def test_windows_baslaticisi_betigi_proje_kokunden_calistirir_ve_pencereyi_acik_tutar():
    bat = (Path(__file__).resolve().parents[1] / "scripts" / "windows" / "admin_parola_kurtar.bat").read_text()
    assert "scripts\\admin_parola_kurtar.py" in bat and "cd /d" in bat and "pause" in bat.lower()


def test_kilavuz_kurtarma_adimlarini_ve_iki_yonetici_onerisini_icerir():
    kilavuz = (Path(__file__).resolve().parents[1] / "docs" / "Sunucu_Kurulum_Kilavuzu.md").read_text(encoding="utf-8")
    assert "Yönetici parolasını unuttuysanız" in kilavuz and "admin_parola_kurtar" in kilavuz
    assert "en az **iki** yönetici" in kilavuz
