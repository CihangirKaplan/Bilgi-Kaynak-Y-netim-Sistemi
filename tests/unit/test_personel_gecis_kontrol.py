"""scripts/personel_gecis_kontrol.py: geçiş öncesi/sonrası karar mantığı (veritabanı gerektirmez)."""
from scripts import personel_gecis_kontrol as k


def _g(adet=3, ozet="a"):
    return {"adet": adet, "ozet": ozet}


ONCEKI = {"goruntu": {"personel": _g(), "randevular": _g(5, "r")}, "uyumsuz_aktiflik": 0}
YAPI_TAMAM = {"tetikleyici_var": True, "dort_baglanti_kullanicilara": True, "baglanti_adlari_korundu": True, "sayac_eski_kimlikleri_asiyor": True}


# ------------------------------------------------------------------ geçiş öncesi
def test_temiz_veritabani_geciise_hazir():
    sorun, uyari, bilgi = k.on_karar("r", ["e5a2c8d1f396"], [])
    assert sorun == [] and uyari == [] and any("aynı" in b for b in bilgi)


def test_aktifligi_farkli_kayitlar_engel_degil_uyaridir_ve_ornek_gosterir():
    uyumsuz = [{"kullanici_adi": "ayse", "kullanici_aktif": True, "personel_aktif": False}]
    sorun, uyari, _ = k.on_karar("r", ["x"], uyumsuz)
    assert sorun == [] and len(uyari) == 1 and "ayse" in uyari[0] and "PASİF" in uyari[0]


def test_zaten_gecilmis_ya_da_bozuk_sema_engeldir():
    assert k.on_karar("v", ["x"], [])[0]                                       # personel zaten görünüm
    assert k.on_karar(None, ["x"], [])[0]                                      # personel yok
    assert k.on_karar("r", [], [])[0]                                          # alembic sürümü yok
    assert k.on_karar("r", [k.MIGRASYON], [])[0]                               # migration zaten uygulanmış


# ------------------------------------------------------------------ geçiş sonrası
def test_her_sey_ayniysa_dogrulanir():
    simdi = {"personel": _g(), "randevular": _g(5, "r")}
    sorun, bilgi = k.son_karar(ONCEKI, simdi, "v", YAPI_TAMAM, (True, "tamam"))
    assert sorun == [] and sum("aynı" in b for b in bilgi) == 2


def test_satir_sayisi_ya_da_icerik_degisirse_yakalanir():
    sorun, _ = k.son_karar(ONCEKI, {"personel": _g(2), "randevular": _g(5, "r")}, "v", YAPI_TAMAM, (True, "x"))
    assert any("satır sayısı değişti" in s for s in sorun)
    sorun, _ = k.son_karar(ONCEKI, {"personel": _g(3, "degisti"), "randevular": _g(5, "r")}, "v", YAPI_TAMAM, (True, "x"))
    assert any("sağlama özeti farklı" in s for s in sorun)


def test_eksik_yapi_ya_da_basarisiz_yazma_denemesi_yakalanir():
    simdi = {"personel": _g(), "randevular": _g(5, "r")}
    sorun, _ = k.son_karar(ONCEKI, simdi, "v", {**YAPI_TAMAM, "tetikleyici_var": False}, (True, "x"))
    assert any("tetikleyici_var" in s for s in sorun)
    sorun, _ = k.son_karar(ONCEKI, simdi, "v", YAPI_TAMAM, (False, "hata"))
    assert any("yazma denemesi" in s for s in sorun)


def test_oncesi_sagama_dosyasi_yoksa_dogrulanamaz():
    sorun, _ = k.son_karar(None, {"personel": _g()}, "v", YAPI_TAMAM, (True, "x"))
    assert any("sağlama dosyası bulunamadı" in s for s in sorun)


def test_gecis_uygulanmamissa_tek_net_mesaj_verilir():
    sorun, _ = k.son_karar(ONCEKI, {}, "r", {}, (False, "atlandı"))
    assert len(sorun) == 1 and "geçiş uygulanmamış" in sorun[0]


def test_gecis_oncesi_aktiflik_uzlastirmasi_bilgi_olarak_yazilir():
    onceki = {**ONCEKI, "uyumsuz_aktiflik": 2}
    _, bilgi = k.son_karar(onceki, {"personel": _g(), "randevular": _g(5, "r")}, "v", YAPI_TAMAM, (True, "x"))
    assert any("2 kayıt" in b and "uzlaştırıldı" in b for b in bilgi)


# ------------------------------------------------------------------ eski (artakalan) sütunlardaki dolu değerler: yalnızca bilgi
def _ekstra():
    return [{"sutun": "varsayilan_oda_id", "personel_id": 7, "kullanici_adi": "psikolog1", "deger": "2", "oda_adi": "Görüşme Odası-1"}]


def test_eski_sutundaki_dolu_deger_uyari_olarak_gosterilir_ama_gecisi_engellemez():
    sorun, uyari, _ = k.on_karar("r", ["x"], [], _ekstra())
    assert sorun == []                                                                       # kalıntı veri: engel değil
    assert len(uyari) == 1 and "psikolog1" in uyari[0] and "varsayilan_oda_id = 2" in uyari[0] and "Görüşme Odası-1" in uyari[0] and "silinecek" in uyari[0]


def test_eski_sutun_yoksa_cikti_degismez():
    assert k.on_karar("r", ["x"], [], []) == k.on_karar("r", ["x"], [])
