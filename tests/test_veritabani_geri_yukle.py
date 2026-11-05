"""Geri yükleme aracı: yalnızca YENİ veritabanına yükler, mevcut hiçbir veritabanının üzerine yazmaz."""
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from scripts import veritabani_geri_yukle as gy


@pytest.fixture(autouse=True)
def ortam(monkeypatch, tmp_path):
    for ad, deger in (("DB_NAME", "crkys"), ("DB_USER", "u"), ("DB_PASSWORD", "p"), ("DB_HOST", "h"), ("DB_PORT", "5432")):
        monkeypatch.setenv(ad, deger)
    monkeypatch.setenv("PG_RESTORE_PATH", "/usr/bin/pg_restore")
    monkeypatch.setattr(gy, "YEDEK_KLASORU", tmp_path / "backups")
    (tmp_path / "backups").mkdir()
    return tmp_path


def dump_olustur(klasor, ad="crkys_20261104_090000_000000.dump", icerik="x"):
    dosya = klasor / "backups" / ad
    dosya.write_text(icerik)
    return dosya


def yonetim_baglantisi(var_mi=False):
    baglanti = MagicMock()
    imlec = baglanti.cursor.return_value
    imlec.fetchone.return_value = (1,) if var_mi else None
    return baglanti, imlec


def calistirilan_sql(imlec):
    return [str(c.args[0]) for c in imlec.execute.call_args_list]


# ----------------------------------------------------------------------- güvenlik kuralları
@pytest.mark.parametrize("hedef", ["crkys", "postgres", "template0", "template1"])
def test_canli_veritabani_ve_sistem_veritabanlari_hedef_olamaz(ortam, hedef):
    dump = dump_olustur(ortam)
    with patch.object(gy, "_baglan") as baglan, patch.object(gy.subprocess, "run") as calistir:
        with pytest.raises(gy.GeriYuklemeHatasi, match="hedef olarak kullanilamaz"):
            gy.geri_yukle(dump, hedef, "crkys")
    baglan.assert_not_called()
    calistir.assert_not_called()


def test_kaynak_veritabaniyla_ayni_ad_hedef_olamaz(ortam):
    dump = dump_olustur(ortam, "crkys_alembic_test_20261104_090000_000000.dump")
    with pytest.raises(gy.GeriYuklemeHatasi, match="hedef olarak kullanilamaz"):
        gy.geri_yukle(dump, "crkys_alembic_test", "crkys_alembic_test")


@pytest.mark.parametrize("ad", ["a-b", "x; DROP DATABASE crkys", "../x", "", "x" * 64])
def test_gecersiz_hedef_adi_reddedilir(ortam, ad):
    with pytest.raises(gy.GeriYuklemeHatasi):
        gy.geri_yukle(dump_olustur(ortam), ad, "crkys")


def test_yedek_dosyasi_yok_ya_da_bos_ise_reddedilir(ortam):
    with pytest.raises(gy.GeriYuklemeHatasi, match="bulunamadi veya bos"):
        gy.geri_yukle(ortam / "backups" / "yok.dump", "crkys_deneme", "crkys")
    bos = dump_olustur(ortam, "crkys_20261104_090001_000000.dump", icerik="")
    with pytest.raises(gy.GeriYuklemeHatasi, match="bulunamadi veya bos"):
        gy.geri_yukle(bos, "crkys_deneme", "crkys")


def test_hedef_veritabani_zaten_varsa_uzerine_yazilmaz(ortam):
    dump = dump_olustur(ortam)
    baglanti, imlec = yonetim_baglantisi(var_mi=True)
    with patch.object(gy, "_baglan", return_value=baglanti), patch.object(gy.subprocess, "run") as calistir:
        with pytest.raises(gy.GeriYuklemeHatasi, match="zaten var"):
            gy.geri_yukle(dump, "crkys_deneme", "crkys")
    assert not any("CREATE DATABASE" in s for s in calistirilan_sql(imlec))
    assert not any("DROP" in s for s in calistirilan_sql(imlec))
    calistir.assert_not_called()


# -------------------------------------------------------------------------- başarılı yükleme
def test_basarili_yukleme_yeni_veritabani_olusturur_ve_pg_restore_calistirir(ortam):
    dump = dump_olustur(ortam)
    baglanti, imlec = yonetim_baglantisi(var_mi=False)
    with patch.object(gy, "_baglan", return_value=baglanti), \
         patch.object(gy.subprocess, "run") as calistir, \
         patch.object(gy, "kayit_sayilari", return_value={"kullanicilar": 7}):
        sonuc = gy.geri_yukle(dump, "crkys_deneme", "crkys")

    assert sonuc == {"kullanicilar": 7}
    assert any("CREATE DATABASE" in s for s in calistirilan_sql(imlec))
    assert not any("DROP" in s for s in calistirilan_sql(imlec))
    komut = calistir.call_args.args[0]
    assert komut[0] == "/usr/bin/pg_restore" and "--no-owner" in komut and "--exit-on-error" in komut
    assert komut[komut.index("--dbname") + 1] == "crkys_deneme" and komut[-1] == str(dump)
    assert calistir.call_args.kwargs["env"]["PGPASSWORD"] == "p"
    assert "p" not in [a for a in komut if a == "p"]            # parola komut satırında görünmez


def test_pg_restore_basarisizsa_olusturulan_yarim_veritabani_silinir(ortam):
    dump = dump_olustur(ortam)
    baglanti, imlec = yonetim_baglantisi(var_mi=False)
    hata = subprocess.CalledProcessError(1, ["pg_restore"], stderr="bozuk yedek")
    with patch.object(gy, "_baglan", return_value=baglanti), patch.object(gy.subprocess, "run", side_effect=hata):
        with pytest.raises(gy.GeriYuklemeHatasi, match="basarisiz.*silindi"):
            gy.geri_yukle(dump, "crkys_deneme", "crkys")
    sorgular = calistirilan_sql(imlec)
    assert any("CREATE DATABASE" in s for s in sorgular)
    assert any("DROP DATABASE" in s and "crkys_deneme" in s for s in sorgular)
    assert not any("DROP" in s and '"crkys"' in s for s in sorgular)   # canlı veritabanına dokunulmaz


# ---------------------------------------------------------------- en yeni yedek ve komut satırı
def test_en_yeni_yedek_yalnizca_o_veritabaninin_yedeklerinden_secilir(ortam):
    dump_olustur(ortam, "crkys_20261101_090000_000000.dump")
    yeni = dump_olustur(ortam, "crkys_20261104_090000_000000.dump")
    dump_olustur(ortam, "crkys_alembic_test_20261105_090000_000000.dump")   # daha yeni ama başka DB
    dump_olustur(ortam, "crkys_elle_alinan.dump")
    assert gy.en_yeni_yedek("crkys") == yeni


def test_yedek_yoksa_anlasilir_hata(ortam):
    with pytest.raises(gy.GeriYuklemeHatasi, match="yedek bulunamadi"):
        gy.en_yeni_yedek("crkys")


def test_main_hata_olursa_cikis_kodu_1_ve_mesaj(ortam, capsys):
    with pytest.raises(SystemExit) as cikis:
        gy.main(["--hedef", "crkys"])                           # canlı veritabanı hedef -> reddedilir
    assert cikis.value.code == 1
    assert "HATA" in capsys.readouterr().err


def test_main_basarida_kayit_sayilarini_karsilastirir(ortam, capsys):
    dump_olustur(ortam)
    with patch.object(gy, "geri_yukle", return_value={"kullanicilar": 7, "alembic": "abc"}), \
         patch.object(gy, "kayit_sayilari", return_value={"kullanicilar": 9, "alembic": "abc"}):
        gy.main(["--hedef", "crkys_deneme"])
    cikti = capsys.readouterr().out
    assert "Geri yuklendi: crkys_deneme" in cikti and "kullanicilar" in cikti and "7" in cikti and "9" in cikti
    assert "hedef veritabanini kendiniz silin" in cikti          # araç hedefi silmez
