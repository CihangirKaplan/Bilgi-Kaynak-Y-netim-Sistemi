"""b9d4f7a2c613: personel ve kullanicilar birlesimi migrasyonunun veritabanı gerektirmeyen denetimleri.

Gerçek veritabanı karşılıkları (görünümün yazma davranışı, yabancı anahtarlar, hata sınıfları) test_kisisel_veri_ayrimi_pg_quality.py'dedir.
"""
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

SURUMLER = Path(__file__).resolve().parents[2] / "database" / "migrations" / "versions"
MIGRASYON = SURUMLER / "b9d4f7a2c613_personel_kullanicilar_birlestir.py"


def _yukle():
    spec = importlib.util.spec_from_file_location("personel_birlestir", MIGRASYON)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def _sorgular(islev):
    modul = _yukle()
    with patch.object(modul, "op", MagicMock()) as op:
        getattr(modul, islev)()
    return [" ".join(c.args[0].split()) for c in op.execute.call_args_list]


def test_zincire_baglanir():
    modul = _yukle()
    assert modul.revision == "b9d4f7a2c613"
    assert isinstance(modul.down_revision, str) and any(d.name.startswith(modul.down_revision) for d in SURUMLER.glob("*.py"))


def test_yukseltme_sirasi_baglantilar_once_kopar_veri_tasinir_sonra_tablo_gider():
    s = _sorgular("upgrade")
    sira = lambda parca: next(i for i, q in enumerate(s) if parca in q)
    assert sira("DROP CONSTRAINT randevular_psikolog_id_fkey") < sira("ADD COLUMN personel_id")      # önce yabancı anahtarlar kalkar
    assert sira("ADD COLUMN personel_id") < sira("SET personel_id = p.personel_id")                  # sonra veri taşınır (eski kimlikler aynen)
    assert sira("SET personel_id = p.personel_id") < sira("DROP TABLE personel;") < sira("CREATE VIEW personel")
    assert sira("CREATE VIEW personel") < sira("ADD CONSTRAINT randevular_psikolog_id_fkey")         # bağlantılar en son yeni hedefe kurulur
    assert sira("OWNED BY NONE") < sira("DROP TABLE personel;")                                      # sayaç tabloyla birlikte silinmez


def test_yukseltme_hicbir_randevu_danisan_rezervasyon_ya_da_denetim_verisini_silmez_degistirmez():
    s = " ".join(_sorgular("upgrade")).upper()
    for yasak in ("DELETE FROM", "TRUNCATE", "UPDATE RANDEVULAR", "UPDATE DANISAN_KODLARI", "UPDATE CIHAZ_REZERVASYONLARI", "UPDATE ODA_ETKINLIKLERI", "UPDATE DENETIM_KAYITLARI"):
        assert yasak not in s


def test_dort_baglanti_kullanicilar_personel_id_ye_yonlendirilir_danisan_baglantisi_bos_birakma_kuralini_korur():
    s = _sorgular("upgrade")
    for tablo in ("cihaz_rezervasyonlari", "danisan_kodlari", "oda_etkinlikleri", "randevular"):
        assert any(q.startswith(f"ALTER TABLE {tablo} ADD CONSTRAINT") and "REFERENCES kullanicilar(personel_id)" in q for q in s)
    danisan = next(q for q in s if q.startswith("ALTER TABLE danisan_kodlari ADD CONSTRAINT"))
    assert "ON DELETE SET NULL" in danisan and "ON UPDATE SET NULL" in danisan                       # eski "personel silinince boşalır" davranışı


def test_farkli_aktiflikler_guvenli_yonde_uzlastirilir_ve_denetime_yazilir():
    s = _sorgular("upgrade")
    denetim = next(q for q in s if q.startswith("INSERT INTO denetim_kayitlari"))
    assert "k.aktif_mi AND NOT p.aktif_mi" in denetim and "aktiflik bayraklari birlestirildi" in denetim
    guncelle = next(q for q in s if q.startswith("UPDATE kullanicilar k SET aktif_mi = FALSE"))
    assert "NOT p.aktif_mi" in guncelle                                                              # ikisinden biri pasifse hesap pasif
    assert s.index(denetim) < s.index(guncelle)                                                      # önce kayıt, sonra değişiklik (önceki değer okunabilsin)


def test_geri_alma_tabloyu_ayni_kimliklerle_kurar_ve_sayaci_geri_baglar():
    s = _sorgular("downgrade")
    sira = lambda parca: next(i for i, q in enumerate(s) if parca in q)
    assert sira("DROP VIEW personel") < sira("CREATE TABLE personel") < sira("INSERT INTO personel") < sira("DROP COLUMN personel_kaydi_tarihi")
    assert "SELECT personel_id, kullanici_id, personel_kodu, aktif_mi" in next(q for q in s if q.startswith("INSERT INTO personel"))   # eski kimlikler korunur
    assert any("OWNED BY personel.personel_id" in q for q in s)
    for tablo in ("cihaz_rezervasyonlari", "danisan_kodlari", "oda_etkinlikleri", "randevular"):
        assert any(q.startswith(f"ALTER TABLE {tablo} ADD CONSTRAINT") and "REFERENCES personel(personel_id)" in q for q in s)
    assert not any("ON UPDATE SET NULL" in q for q in s)                                              # eski şemada bu kural yoktu
