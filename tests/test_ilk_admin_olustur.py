"""İlk yönetici betiği: sahte imleçle, gerçek veritabanına dokunmaz."""
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_yol = Path(__file__).resolve().parents[1] / "scripts" / "ilk_admin_olustur.py"
_spec = importlib.util.spec_from_file_location("ilk_admin_olustur", _yol)
betik = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(betik)


def imlec(*sonuclar):
    """fetchone sırayla verilen sonuçları döndürür."""
    c = MagicMock()
    c.fetchone.side_effect = list(sonuclar)
    return c


def calisan_sorgular(c):
    return [cagri.args[0] for cagri in c.execute.call_args_list]


def test_admin_yoksa_olusturur_ve_ilk_giris_zorunlu_kilar():
    c = imlec((7,), None, None, (42,), (0,))
    ad, parola, kod = betik.admin_olustur(c, "yonetici")
    assert (ad, kod) == ("yonetici", "PER-ADM-001") and len(parola) >= 12
    ekle = next(q for q in c.execute.call_args_list if "INSERT INTO kullanicilar" in q.args[0])
    assert "TRUE, TRUE" in ekle.args[0]                     # aktif_mi, ilk_giris_mi
    assert ekle.args[1][0] == "yonetici" and ekle.args[1][1] != parola   # parola düz yazı saklanmaz
    assert ekle.args[1][2] == 7
    assert any("INSERT INTO personel" in q for q in calisan_sorgular(c))


def test_zaten_admin_varsa_hicbir_sey_eklemez():
    c = imlec((7,), (1,))
    with pytest.raises(betik.IlkAdminHatasi, match="zaten bir ADMIN"):
        betik.admin_olustur(c, "yonetici")
    assert not any("INSERT" in q for q in calisan_sorgular(c))


def test_admin_rolu_yoksa_migration_hatirlatir():
    with pytest.raises(betik.IlkAdminHatasi, match="alembic upgrade head"):
        betik.admin_olustur(imlec(None), "yonetici")


def test_kullanici_adi_baska_hesapta_kullaniliyorsa_reddeder():
    c = imlec((7,), None, (9,))
    with pytest.raises(betik.IlkAdminHatasi, match="zaten kullanılıyor"):
        betik.admin_olustur(c, "yonetici")
    assert not any("INSERT" in q for q in calisan_sorgular(c))


@pytest.mark.parametrize("ad", ["", "ab", "bosluk var", "a;drop", "x" * 51, None])
def test_gecersiz_kullanici_adi_veritabanina_gitmeden_reddedilir(ad):
    c = imlec()
    with pytest.raises(betik.IlkAdminHatasi):
        betik.admin_olustur(c, ad)
    c.execute.assert_not_called()


def test_her_calistirmada_farkli_gecici_parola_uretilir():
    parolalar = {betik.admin_olustur(imlec((7,), None, None, (1,), (0,)), "yonetici")[1] for _ in range(5)}
    assert len(parolalar) == 5


# ------------------------------------------------------------------ ek yönetici (--ek-yonetici)
def test_ek_yonetici_zaten_admin_olsa_da_olusturur_ve_denetim_kaydi_yazar():
    c = imlec((7,), None, (42,), (1,))            # rol, ad boş, yeni kullanıcı id, mevcut PER-ADM sayısı
    ad, parola, kod = betik.admin_olustur(c, "yonetici2", ek_yonetici=True)
    assert (ad, kod) == ("yonetici2", "PER-ADM-002") and len(parola) >= 12
    sorgular = calisan_sorgular(c)
    assert not any("WHERE rol_id = %s LIMIT 1" in q for q in sorgular)         # "zaten admin var" engeli atlanır
    ekle = next(q for q in c.execute.call_args_list if "INSERT INTO kullanicilar" in q.args[0])
    assert "TRUE, TRUE" in ekle.args[0] and ekle.args[1][0] == "yonetici2" and ekle.args[1][1] != parola
    denetim = next(q for q in c.execute.call_args_list if "INSERT INTO denetim_kayitlari" in q.args[0])
    assert denetim.args[1] == (42, "CREATE", "kullanicilar", 42)


def test_ek_yonetici_olmadan_ilk_admin_davranisi_ayni_kalir_ve_ipucu_verir():
    c = imlec((7,), (1,))
    with pytest.raises(betik.IlkAdminHatasi, match="--ek-yonetici"):
        betik.admin_olustur(c, "yonetici2")
    assert not any("INSERT" in q for q in calisan_sorgular(c))


def test_ilk_admin_olusturulurken_denetim_kaydi_yazilmaz_davranis_degismedi():
    c = imlec((7,), None, None, (1,), (0,))
    betik.admin_olustur(c, "yonetici")
    assert not any("denetim_kayitlari" in q for q in calisan_sorgular(c))


def test_ek_yonetici_kullanici_adi_zaten_varsa_reddedilir():
    c = imlec((7,), (9,))
    with pytest.raises(betik.IlkAdminHatasi, match="zaten kullanılıyor"):
        betik.admin_olustur(c, "memur1", ek_yonetici=True)
    assert not any("INSERT" in q for q in calisan_sorgular(c))


@pytest.mark.parametrize("ad", ["", "ab", "bosluk var", "a;drop", None])
def test_ek_yonetici_gecersiz_ad_veritabanina_gitmeden_reddedilir(ad):
    c = imlec()
    with pytest.raises(betik.IlkAdminHatasi):
        betik.admin_olustur(c, ad, ek_yonetici=True)
    c.execute.assert_not_called()


# ---- main akışı
def baglanti(yoneticiler, fetchone):
    from unittest.mock import patch
    conn = MagicMock()
    c = conn.cursor.return_value.__enter__.return_value
    c.fetchall.return_value = [(a,) for a in yoneticiler]
    c.fetchone.side_effect = list(fetchone)
    return conn, c


def calistir(argv, yanitlar=(), yoneticiler=("admin",), fetchone=((7,), None, (42,), (1,))):
    from unittest.mock import patch
    conn, c = baglanti(yoneticiler, fetchone)
    yanit = iter(yanitlar)
    with patch.object(betik.psycopg2, "connect", return_value=conn):
        kod = betik.main(argv, girdi=lambda _: next(yanit))
    return kod, conn, c


def test_main_ek_yonetici_mevcutlari_gosterir_ad_sorar_EVET_isteyip_olusturur(capsys):
    kod, conn, _ = calistir(["--ek-yonetici"], yanitlar=["yonetici2", "EVET"])
    cikti = capsys.readouterr().out
    assert kod == 0 and "Mevcut yöneticiler: admin" in cikti and "Yönetici hesabı oluşturuldu" in cikti
    assert "yonetici2" in cikti and "Geçici parola" in cikti and "bir daha gösterilmez" in cikti
    conn.commit.assert_called_once()


@pytest.mark.parametrize("yanit", ["evet", "e", "EVE", "hayir", ""])
def test_main_yalniz_EVET_onay_sayilir_digerlerinde_hicbir_sey_degismez(yanit, capsys):
    kod, conn, c = calistir(["--ek-yonetici", "--kullanici-adi", "yonetici2"], yanitlar=[yanit])
    assert kod == 0 and "Vazgeçildi" in capsys.readouterr().out
    conn.commit.assert_not_called()
    assert not any("INSERT" in " ".join(k.args[0].split()).upper() for k in c.execute.call_args_list)


def test_main_evet_bayragi_onay_sormaz(capsys):
    kod, conn, _ = calistir(["--ek-yonetici", "--kullanici-adi", "yonetici2", "--evet"])
    assert kod == 0 and "Yönetici hesabı oluşturuldu" in capsys.readouterr().out
    conn.commit.assert_called_once()


def test_main_ek_yonetici_bos_ad_girilirse_admin_olarak_olusturmaz(capsys):
    kod, conn, c = calistir(["--ek-yonetici"], yanitlar=["   "])
    assert kod == 1 and "boş bırakılamaz" in capsys.readouterr().out
    conn.rollback.assert_called_once()
    conn.commit.assert_not_called()
    assert not any("INSERT" in " ".join(k.args[0].split()).upper() for k in c.execute.call_args_list)


def test_main_hata_olursa_geri_alinir_ve_parola_yazilmaz(capsys):
    kod, conn, _ = calistir(["--ek-yonetici", "--kullanici-adi", "memur1", "--evet"], fetchone=[(7,), (9,)])
    cikti = capsys.readouterr().out
    assert kod == 1 and "zaten kullanılıyor" in cikti and "Geçici parola" not in cikti
    conn.rollback.assert_called_once()
    conn.commit.assert_not_called()


def test_main_ek_yonetici_olmadan_eskisi_gibi_admin_adini_varsayar(capsys):
    kod, conn, c = calistir([], fetchone=[(7,), None, None, (1,), (0,)])
    assert kod == 0 and "admin" in capsys.readouterr().out
    conn.commit.assert_called_once()


def test_kilavuz_ek_yonetici_adimini_ve_uygulamadan_acilamayacagini_anlatir():
    kilavuz = (Path(__file__).resolve().parents[1] / "docs" / "Sunucu_Kurulum_Kilavuzu.md").read_text(encoding="utf-8")
    assert kilavuz.count("ilk_admin_olustur.py --ek-yonetici") >= 2      # ilk yönetici bölümü + acil durum listesi
    assert "Uygulamadan yönetici (ADMIN) hesabı açılamaz" in kilavuz
