"""Windows'ta sunucunun kendiliğinden başlaması: başlatıcı betik ve Görev Zamanlayıcı kurulumu.

Gerçek sunucu, veritabanı ya da Windows görevi kullanılmaz; subprocess, soket ve zaman taklit edilir.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.windows import sunucu_baslat as baslat
from scripts.windows import sunucu_kurulum as kurulum


# --------------------------------------------------------------------- ayarlar
@pytest.fixture
def temiz_ortam(monkeypatch):
    for ad in ("TKYS_HOST", "TKYS_PORT", "DB_HOST", "DB_PORT"):
        monkeypatch.delenv(ad, raising=False)
    return monkeypatch


def test_varsayilan_ayarlar_tum_arayuzlerde_8000(temiz_ortam):
    assert baslat.ayarlar() == ("0.0.0.0", 8000, "localhost", 5432)


def test_ayarlar_ortam_degiskenlerinden_okunur(temiz_ortam):
    temiz_ortam.setenv("TKYS_HOST", "127.0.0.1")
    temiz_ortam.setenv("TKYS_PORT", "9000")
    temiz_ortam.setenv("DB_HOST", "10.0.0.5")
    temiz_ortam.setenv("DB_PORT", "5433")
    assert baslat.ayarlar() == ("127.0.0.1", 9000, "10.0.0.5", 5433)


@pytest.mark.parametrize("ad,deger", [("TKYS_PORT", "abc"), ("TKYS_PORT", "0"), ("TKYS_PORT", "70000"), ("DB_PORT", "x")])
def test_gecersiz_port_anlasilir_hatayla_reddedilir(temiz_ortam, ad, deger):
    temiz_ortam.setenv(ad, deger)
    with pytest.raises(SystemExit):
        baslat.ayarlar()


def test_sunucu_komutu_uvicorn_ile_dogru_adres_ve_port():
    assert baslat.sunucu_komutu("0.0.0.0", 8000) == [
        sys.executable, "-m", "uvicorn", "sunucu:app", "--host", "0.0.0.0", "--port", "8000"]


# ---------------------------------------------------------------- veritabanı bekleme
def test_veritabani_hazir_mi_baglanti_acilirsa_true_acilmazsa_false():
    with patch.object(baslat.socket, "create_connection") as baglan:
        assert baslat.veritabani_hazir_mi("localhost", 5432) is True
        baglan.assert_called_once()
    with patch.object(baslat.socket, "create_connection", side_effect=OSError):
        assert baslat.veritabani_hazir_mi("localhost", 5432) is False


def test_veritabani_hazirsa_hic_beklenmez():
    bekle = MagicMock()
    with patch.object(baslat, "veritabani_hazir_mi", return_value=True):
        assert baslat.veritabanini_bekle("h", 1, bekle=bekle) is True
    bekle.assert_not_called()


def test_veritabani_birkac_denemeden_sonra_hazir_olursa_beklemeyi_birakir():
    yanitlar = iter([False, False, True])
    bekle = MagicMock()
    with patch.object(baslat, "veritabani_hazir_mi", side_effect=lambda *a, **k: next(yanitlar)):
        assert baslat.veritabanini_bekle("h", 1, en_fazla=100, bekle=bekle, simdi=lambda: 0) is True
    assert bekle.call_count == 2


def test_veritabani_hic_hazir_olmazsa_sure_dolunca_false_doner():
    saat = iter(range(0, 1000, 5))
    with patch.object(baslat, "veritabani_hazir_mi", return_value=False):
        assert baslat.veritabanini_bekle("h", 1, en_fazla=20, bekle=lambda s: None, simdi=lambda: next(saat)) is False


# ------------------------------------------------------------------------- günlük dosyası
@pytest.fixture
def log_klasoru(tmp_path):
    with patch.object(baslat, "LOG_KLASORU", tmp_path / "logs"), \
         patch.object(baslat, "LOG_DOSYASI", tmp_path / "logs" / "sunucu.log"):
        yield tmp_path / "logs"


def test_log_klasoru_yoksa_olusturulur(log_klasoru):
    baslat.log_dosyasini_hazirla()
    assert log_klasoru.is_dir()


def test_buyuk_log_dosyasi_kenara_alinir_kucuk_olan_yerinde_kalir(log_klasoru):
    log_klasoru.mkdir()
    dosya = log_klasoru / "sunucu.log"
    dosya.write_text("kucuk")
    baslat.log_dosyasini_hazirla()
    assert dosya.read_text() == "kucuk"
    with patch.object(baslat, "LOG_ENIYI_BOYUT", 3):
        baslat.log_dosyasini_hazirla()
    assert not dosya.exists() and (log_klasoru / "sunucu.log.1").read_text() == "kucuk"


def test_eski_log_yedegi_uzerine_yazilir(log_klasoru):
    log_klasoru.mkdir()
    (log_klasoru / "sunucu.log.1").write_text("cok eski")
    (log_klasoru / "sunucu.log").write_text("yeni buyuk")
    with patch.object(baslat, "LOG_ENIYI_BOYUT", 3):
        baslat.log_dosyasini_hazirla()
    assert (log_klasoru / "sunucu.log.1").read_text() == "yeni buyuk"


# ---------------------------------------------------------------------------- çalıştırma döngüsü
def calistir_kosulu(log_klasoru, temiz_ortam, cikis_kodlari, db_hazir=True):
    kodlar = iter(cikis_kodlari)
    bekle = MagicMock()
    with patch.object(baslat.os, "chdir"), patch.object(baslat, "load_dotenv"), \
         patch.object(baslat, "veritabanini_bekle", return_value=db_hazir), \
         patch.object(baslat.subprocess, "run", side_effect=lambda *a, **k: MagicMock(returncode=next(kodlar))) as calistir:
        baslat.calistir(maks_tur=len(cikis_kodlari), bekle=bekle)
    return calistir, bekle


def test_sunucu_kapaninca_yeniden_baslatilir(log_klasoru, temiz_ortam):
    calistir, bekle = calistir_kosulu(log_klasoru, temiz_ortam, [1, 1, 0])
    assert calistir.call_count == 3
    assert calistir.call_args.args[0] == baslat.sunucu_komutu("0.0.0.0", 8000)
    assert [c.args[0] for c in bekle.call_args_list] == [baslat.YENIDEN_BASLATMA_BEKLEME_SANIYE] * 3   # her kapanıştan sonra bekler


def test_baslatma_ve_kapanma_gunluge_yazilir(log_klasoru, temiz_ortam):
    calistir_kosulu(log_klasoru, temiz_ortam, [3])
    metin = (log_klasoru / "sunucu.log").read_text(encoding="utf-8")
    assert "Sunucu başlatılıyor: http://0.0.0.0:8000" in metin and "çıkış kodu 3" in metin


def test_sunucu_ciktisi_gunluk_dosyasina_yonlendirilir(log_klasoru, temiz_ortam):
    calistir, _ = calistir_kosulu(log_klasoru, temiz_ortam, [0])
    kw = calistir.call_args.kwargs
    assert kw["stdout"].name.endswith("sunucu.log") and kw["stderr"] == baslat.subprocess.STDOUT
    assert kw["cwd"] == baslat.PROJE


def test_veritabani_hazir_olmasa_da_sunucu_baslatilir_ve_uyari_yazilir(log_klasoru, temiz_ortam):
    calistir, _ = calistir_kosulu(log_klasoru, temiz_ortam, [0], db_hazir=False)
    assert calistir.call_count == 1
    assert "hazır olmadı" in (log_klasoru / "sunucu.log").read_text(encoding="utf-8")


def test_calistirma_proje_klasorune_gecer_ve_env_yukler(log_klasoru, temiz_ortam):
    kodlar = iter([0])
    with patch.object(baslat.os, "chdir") as gec, patch.object(baslat, "load_dotenv") as yukle, \
         patch.object(baslat, "veritabanini_bekle", return_value=True), \
         patch.object(baslat.subprocess, "run", side_effect=lambda *a, **k: MagicMock(returncode=next(kodlar))):
        baslat.calistir(maks_tur=1, bekle=lambda s: None)
    gec.assert_called_once_with(baslat.PROJE)
    yukle.assert_called_once_with(baslat.PROJE / ".env")


# --------------------------------------------------------------- Görev Zamanlayıcı kurulumu
def kur(argv=None, env_var=True):
    with patch.object(kurulum, "windows_mu", return_value=True), \
         patch.object(Path, "is_file", return_value=env_var), \
         patch.object(kurulum.subprocess, "run") as calistir:
        kurulum.main(argv)
    return calistir


def test_varsayilan_kurulum_acilista_system_hesabiyla_30_sn_gecikmeyle_calisir():
    c = kur([])
    komut = c.call_args.args[0]
    assert komut[:4] == ["schtasks", "/Create", "/TN", "TKYS_Sunucu"]
    assert komut[komut.index("/SC") + 1] == "ONSTART"
    assert komut[komut.index("/DELAY") + 1] == "0000:30"
    assert komut[komut.index("/RU") + 1] == "SYSTEM"
    assert "/RL" in komut and "/F" in komut and c.call_args.kwargs["check"] is True


def test_gorev_python_ve_baslatici_betigi_calistirir():
    komut = kur([]).call_args.args[0]
    calisan = komut[komut.index("/TR") + 1]
    assert sys.executable in calisan and "sunucu_baslat.py" in calisan


def test_oturum_secenegi_kullanici_giris_yapinca_calistirir_ve_system_kullanmaz():
    komut = kur(["--oturum"]).call_args.args[0]
    assert komut[komut.index("/SC") + 1] == "ONLOGON"
    assert "/RU" not in komut and "/DELAY" not in komut


def test_kaldir_secenegi_gorevi_siler_ve_olusturmaz():
    komut = kur(["--kaldir"]).call_args.args[0]
    assert komut == ["schtasks", "/Delete", "/TN", "TKYS_Sunucu", "/F"]


def test_windows_disinda_calismaz():
    with patch.object(kurulum, "windows_mu", return_value=False), patch.object(kurulum.subprocess, "run") as c:
        with pytest.raises(SystemExit, match="Windows"):
            kurulum.main([])
    c.assert_not_called()


def test_env_dosyasi_yoksa_gorev_olusturulmaz():
    with patch.object(kurulum, "windows_mu", return_value=True), patch.object(kurulum.subprocess, "run") as c:
        orijinal = Path.is_file
        with patch.object(Path, "is_file", lambda self: False if self.name == ".env" else orijinal(self)):
            with pytest.raises(SystemExit, match=".env"):
                kurulum.main([])
    c.assert_not_called()


def test_oturum_ve_kaldir_birlikte_verilemez():
    with pytest.raises(SystemExit):
        kur(["--oturum", "--kaldir"])
