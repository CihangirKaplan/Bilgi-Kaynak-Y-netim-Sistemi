"""scripts/randevu_cakisma_onar.py: karar mantığı ve kural tanımları (veritabanı gerektirmez)."""
from scripts import randevu_cakisma_onar as k

IKISI = [("psikolog_randevu_cakisma", "psikolog_id", "aynı psikoloğa"), ("oda_randevu_cakisma", "oda_id", "aynı odaya")]


def test_kurallar_yerindeyse_yapilacak_bir_sey_yok():
    sorun, bilgi, uygulanabilir = k.karar([], {})
    assert sorun == [] and uygulanabilir is False and any("yapılacak bir şey yok" in b for b in bilgi)


def test_cakisma_yoksa_eksik_kurallar_eklenebilir():
    sorun, bilgi, uygulanabilir = k.karar(IKISI, {"psikolog_id": 0, "oda_id": 0})
    assert uygulanabilir is True
    assert sum("kural eksik" in s for s in sorun) == 2                                       # eksiklik bildirilir
    assert sum("kural eklenebilir" in b for b in bilgi) == 2


def test_tek_bir_cakisma_bile_eklemeyi_engeller_ve_nedeni_soyler():
    sorun, _, uygulanabilir = k.karar(IKISI, {"psikolog_id": 0, "oda_id": 2})
    assert uygulanabilir is False and any("oda_id: 2 çakışan randevu çifti" in s for s in sorun)


def test_yalniz_biri_eksikse_yalniz_onun_cakismasi_dikkate_alinir():
    eksik = [IKISI[1]]                                                                      # yalnız oda kuralı eksik
    assert k.karar(eksik, {"psikolog_id": 5, "oda_id": 0})[2] is True                        # psikolog çakışması eksik olmayan kuralı ilgilendirmez
    assert k.karar(eksik, {"oda_id": 1})[2] is False


def test_kural_tanimi_migration_ile_ayni():
    sql = k.kural_sql("oda_randevu_cakisma", "oda_id")
    assert sql == ("ALTER TABLE randevular ADD CONSTRAINT oda_randevu_cakisma EXCLUDE USING gist (oda_id WITH =, "
                   "tsrange(baslangic_zamani, bitis_zamani, '[)') WITH &&) WHERE (durum = 'PLANLANDI')")
    assert "'[)'" in sql and "durum = 'PLANLANDI'" in sql                                    # bitiş=başlangıç çakışma sayılmaz, iptaller sayılmaz
    assert [a for a, _, _ in k.KURALLAR] == ["psikolog_randevu_cakisma", "oda_randevu_cakisma"]


def test_cakismalar_beklenmeyen_sutunu_reddeder():
    import pytest

    with pytest.raises(ValueError):
        k.cakismalar(None, "durum; DROP TABLE randevular")
