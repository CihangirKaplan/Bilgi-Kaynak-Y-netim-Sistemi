"""Cihaz uygunluk takviminin saf mantığı: gün durumu, saat çizelgesi, aralık müsaitliği, filtre."""
from datetime import date, datetime, timedelta

import pytest

import cihaz_uygunluk_mantigi as m

D, DT = date, datetime
GUN = D(2026, 11, 4)                                   # Çarşamba


def donem(tur, bas, bit=None, kaynak="kayit"):
    return m.Donem(tur, bas, bit, kaynak)


def rez(saat1, saat2, gun=GUN):
    return donem(m.REZERVASYON, DT(gun.year, gun.month, gun.day, saat1), DT(gun.year, gun.month, gun.day, saat2))


def tum_gun(tur, gun=GUN, gun_sayisi=1):
    bas = DT(gun.year, gun.month, gun.day)
    return donem(tur, bas, bas + timedelta(days=gun_sayisi))


# ------------------------------------------------------------------ gün durumu
def test_donemsiz_gun_musait():
    d = m.gun_durumu([], GUN)
    assert d.kod == m.MUSAIT and not d.engelli


def test_kismi_rezervasyon_kismen_dolu_ve_dakika_hesabi():
    d = m.gun_durumu([rez(10, 12), rez(14, 15)], GUN)
    assert d.kod == m.KISMEN and d.dolu_dakika == 180 and len(d.rezervasyonlar) == 2


def test_ust_uste_binen_rezervasyonlar_dakikayi_iki_kez_saymaz():
    assert m.gun_durumu([rez(9, 12), rez(11, 13)], GUN).dolu_dakika == 240


def test_mesai_penceresini_tamamen_dolduran_rezervasyon_dolu():
    assert m.gun_durumu([rez(8, 13), rez(13, 18)], GUN).kod == m.DOLU
    assert m.gun_durumu([rez(7, 19)], GUN).kod == m.DOLU                   # pencereyi aşan rezervasyon da dolu sayılır


def test_mesai_disi_rezervasyon_gunu_kismen_dolu_yapar_ama_dolu_yapmaz():
    d = m.gun_durumu([rez(19, 21)], GUN)
    assert d.kod == m.KISMEN and d.dolu_dakika == 0


@pytest.mark.parametrize("tur", [m.BAKIM, m.KALIBRASYON, m.ARIZA, m.KULLANIM_DISI])
def test_engel_gunu_o_turle_isaretler(tur):
    d = m.gun_durumu([tum_gun(tur)], GUN)
    assert d.kod == tur and d.engelli and d.engeller[0].tur == tur


def test_engel_onceligi_kullanim_disi_ariza_bakim_kalibrasyon():
    donemler = [tum_gun(m.KALIBRASYON), tum_gun(m.BAKIM), tum_gun(m.ARIZA), tum_gun(m.KULLANIM_DISI)]
    d = m.gun_durumu(donemler, GUN)
    assert d.kod == m.KULLANIM_DISI
    assert [e.tur for e in d.engeller] == [m.KULLANIM_DISI, m.ARIZA, m.BAKIM, m.KALIBRASYON]
    assert m.gun_durumu(donemler[:3], GUN).kod == m.ARIZA
    assert m.gun_durumu(donemler[:2], GUN).kod == m.BAKIM


def test_engel_rezervasyondan_onceliklidir_ama_rezervasyon_bilgisi_korunur():
    d = m.gun_durumu([tum_gun(m.BAKIM), rez(9, 10)], GUN)
    assert d.kod == m.BAKIM and len(d.rezervasyonlar) == 1


def test_acik_ariza_bitissiz_sonraki_gunlere_uzanir_baslangictan_onceki_gune_degil():
    ariza = donem(m.ARIZA, DT(2026, 11, 4, 14, 0), None)
    assert m.gun_durumu([ariza], D(2026, 11, 3)).kod == m.MUSAIT
    assert m.gun_durumu([ariza], D(2026, 11, 4)).kod == m.ARIZA
    assert m.gun_durumu([ariza], D(2026, 12, 25)).kod == m.ARIZA


def test_bitis_gunu_dahil_bakim_sonraki_gun_musait():
    bakim = donem(m.BAKIM, DT(2026, 11, 3), DT(2026, 11, 5))                # 3-4 Kasım (bitiş 5'in 00:00'ı, hariç)
    assert [m.gun_durumu([bakim], D(2026, 11, g)).kod for g in (2, 3, 4, 5)] == [m.MUSAIT, m.BAKIM, m.BAKIM, m.MUSAIT]


# --------------------------------------------------------------- saat çizelgesi
def test_saat_cizelgesi_rezervasyon_ve_engel_saatlerini_gosterir():
    cizelge = dict(m.saat_cizelgesi([rez(10, 12)], GUN))
    assert cizelge[9] == m.MUSAIT and cizelge[10] == m.REZERVASYON and cizelge[11] == m.REZERVASYON and cizelge[12] == m.MUSAIT
    assert list(cizelge) == list(range(8, 18))
    ariza = donem(m.ARIZA, DT(2026, 11, 4, 14, 30), None)
    cizelge = dict(m.saat_cizelgesi([ariza, rez(14, 16)], GUN))
    assert cizelge[13] == m.MUSAIT and cizelge[14] == m.ARIZA and cizelge[17] == m.ARIZA   # engel rezervasyonun önüne geçer


# ------------------------------------------------------------- aralık müsaitliği
def test_musait_mi_bos_cihaz_musait():
    assert m.musait_mi([], DT(2026, 11, 4, 9), DT(2026, 11, 4, 10)) == (True, [])


def test_musait_mi_sinir_temasi_cakisma_sayilmaz():
    donemler = [rez(10, 12)]
    assert m.musait_mi(donemler, DT(2026, 11, 4, 12), DT(2026, 11, 4, 13))[0] is True      # 12:00'de başlayan serbest
    assert m.musait_mi(donemler, DT(2026, 11, 4, 9), DT(2026, 11, 4, 10))[0] is True       # 10:00'da biten serbest
    assert m.musait_mi(donemler, DT(2026, 11, 4, 11), DT(2026, 11, 4, 13)) == (False, [m.REZERVASYON])


def test_musait_mi_nedenleri_onem_sirasiyla_ve_benzersiz():
    donemler = [tum_gun(m.KALIBRASYON), tum_gun(m.ARIZA), rez(9, 10), rez(9, 11)]
    musait, nedenler = m.musait_mi(donemler, DT(2026, 11, 4, 9), DT(2026, 11, 4, 12))
    assert not musait and nedenler == [m.ARIZA, m.KALIBRASYON, m.REZERVASYON]


def test_musait_mi_gecersiz_aralik_hata():
    with pytest.raises(ValueError):
        m.musait_mi([], DT(2026, 11, 4, 10), DT(2026, 11, 4, 10))


def test_su_anki_durum():
    donemler = [rez(10, 12), donem(m.BAKIM, DT(2026, 11, 4, 11), DT(2026, 11, 4, 12))]
    assert m.su_anki_durum(donemler, DT(2026, 11, 4, 9)) == m.MUSAIT
    assert m.su_anki_durum(donemler, DT(2026, 11, 4, 10, 30)) == m.REZERVASYON
    assert m.su_anki_durum(donemler, DT(2026, 11, 4, 11, 30)) == m.BAKIM


# ---------------------------------------------------------------- yanıt ayrıştırma
def test_donemleri_coz_bozuk_kayitlari_atlar():
    cihaz = {"donemler": [
        {"tur": "BAKIM", "baslangic": "2026-11-03T00:00:00", "bitis": "2026-11-05T00:00:00", "kaynak": "kayit"},
        {"tur": "ARIZA", "baslangic": "2026-11-04T10:00:00", "bitis": None},
        {"tur": "BAKIM", "baslangic": "bozuk", "bitis": None},
        {"tur": "BAKIM", "baslangic": "2026-11-04T10:00:00", "bitis": "2026-11-04T09:00:00"},   # bitiş başlangıçtan önce
        {"tur": "BAKIM"},
    ]}
    cozulen = m.donemleri_coz(cihaz)
    assert [(d.tur, d.bitis) for d in cozulen] == [("BAKIM", DT(2026, 11, 5)), ("ARIZA", None)]
    assert m.donemleri_coz({}) == []


# ----------------------------------------------------------------------- sayaçlar
def cihaz(cid, kod="E", ad="Cihaz", donemler=(), **ek):
    ham = [{"tur": d.tur, "baslangic": d.baslangic.isoformat(), "bitis": d.bitis.isoformat() if d.bitis else None,
            "kaynak": d.kaynak} for d in donemler]
    return {"cihaz_id": cid, "envanter_kodu": kod, "cihaz_adi": ad, "donemler": ham, **ek}


def test_bugun_ozeti_sayar():
    cihazlar = [cihaz(1), cihaz(2, donemler=[rez(9, 10)]), cihaz(3, donemler=[rez(8, 18)]),
                cihaz(4, donemler=[tum_gun(m.BAKIM)]), cihaz(5, donemler=[tum_gun(m.KALIBRASYON)]),
                cihaz(6, donemler=[tum_gun(m.ARIZA)]), cihaz(7, donemler=[tum_gun(m.KULLANIM_DISI)])]
    assert m.bugun_ozeti(cihazlar, GUN) == {"musait": 2, "dolu": 1, "bakim": 1, "kalibrasyon": 1, "ariza": 1, "kullanim_disi": 1}


# ------------------------------------------------------------------------ hafta
def test_hafta_pazartesi_baslar():
    assert m.hafta_basi(D(2026, 11, 4)) == D(2026, 11, 2) and m.hafta_basi(D(2026, 11, 8)) == D(2026, 11, 2)
    assert m.hafta_basi(D(2026, 11, 9)) == D(2026, 11, 9)
    assert m.hafta_gunleri(D(2026, 11, 4))[0] == D(2026, 11, 2) and m.hafta_gunleri(D(2026, 11, 4))[-1] == D(2026, 11, 8)


# ------------------------------------------------------------------------ filtre
def test_turkce_buyuk_kucuk_harf_aramasi():
    assert m.tr_kucult("İSTANBUL IŞIK") == "istanbul ışık"
    cihazlar = [cihaz(1, "E-1", "Işık Terapi Cihazı"), cihaz(2, "E-2", "EEG")]
    assert [c["cihaz_id"] for c in m.filtrele(cihazlar, arama="IŞIK")] == [1]
    assert [c["cihaz_id"] for c in m.filtrele(cihazlar, arama="e-2")] == [2]
    assert [c["cihaz_id"] for c in m.filtrele(cihazlar, arama="  ")] == [1, 2]


def test_filtre_bugun_musait_ve_sorunlu_ve_musait_idler():
    hafta = m.hafta_gunleri(GUN)
    cihazlar = [cihaz(1), cihaz(2, donemler=[tum_gun(m.ARIZA)]), cihaz(3, kalibrasyon_uyari="SURESI_DOLDU"),
                cihaz(4, donemler=[tum_gun(m.BAKIM, D(2026, 11, 6))]), cihaz(5, donemler=[rez(9, 10)])]
    kimlikler = lambda s: [c["cihaz_id"] for c in s]
    assert kimlikler(m.filtrele(cihazlar, mod="BUGUN_MUSAIT", bugun=GUN)) == [1, 3, 4, 5]
    assert kimlikler(m.filtrele(cihazlar, mod="SORUNLU", gunler=hafta, bugun=GUN)) == [2, 3, 4]
    assert kimlikler(m.filtrele(cihazlar, musait_idler={1, 5})) == [1, 5]
    assert kimlikler(m.filtrele(cihazlar, arama="", mod="TUMU")) == [1, 2, 3, 4, 5]


def test_musait_cihazlar_kumesi():
    cihazlar = [cihaz(1), cihaz(2, donemler=[rez(9, 11)]), cihaz(3, donemler=[tum_gun(m.ARIZA)])]
    assert m.musait_cihazlar(cihazlar, DT(2026, 11, 4, 10), DT(2026, 11, 4, 11)) == {1}
    assert m.musait_cihazlar(cihazlar, DT(2026, 11, 4, 11), DT(2026, 11, 4, 12)) == {1, 2}


# ----------------------------------------------------------------- metin üreticiler
def test_tarih_ve_hafta_etiketleri():
    assert m.tarih_yazi(D(2026, 11, 4)) == "4 Kasım 2026" and m.tarih_yazi(D(2026, 11, 4), yil=False) == "4 Kasım"
    assert m.uzun_tarih(D(2026, 11, 4)) == "4 Kasım 2026 Çarşamba"
    assert m.hafta_etiketi(m.hafta_gunleri(D(2026, 11, 4))) == "2 – 8 Kasım 2026"
    assert m.hafta_etiketi(m.hafta_gunleri(D(2026, 10, 30))) == "26 Ekim – 1 Kasım 2026"
    assert m.hafta_etiketi(m.hafta_gunleri(D(2026, 12, 31))) == "28 Aralık 2026 – 3 Ocak 2027"


def test_donem_aciklamalari_kisisel_veri_icermez():
    bakim = donem(m.BAKIM, DT(2026, 11, 3), DT(2026, 11, 5))
    assert m.donem_aciklamasi(bakim) == "Bakım: 3 Kasım – 4 Kasım"
    assert m.donem_aciklamasi(donem(m.KALIBRASYON, DT(2026, 11, 3), DT(2026, 11, 4))) == "Kalibrasyon: 3 Kasım"
    assert m.donem_aciklamasi(donem(m.ARIZA, DT(2026, 11, 3, 14, 5), None)) == "Arıza: 3 Kasım 14:05'den beri açık"
    assert m.donem_aciklamasi(donem(m.ARIZA, DT(2026, 11, 2, 9), DT(2026, 11, 3, 9))) == "Arıza: 2 Kasım 09:00 – 3 Kasım 09:00"
    assert "bitiş tarihi belirsiz" in m.donem_aciklamasi(donem(m.BAKIM, DT(2026, 11, 4), None, kaynak="durum"))


def test_uyari_satirlari_ciddiyet_ve_gun_sayilari():
    cihaz_ = {"kalibrasyon_gecerlilik": "2026-11-01", "kalibrasyon_uyari": "SURESI_DOLDU",
              "sonraki_bakim": "2026-11-10", "bakim_uyari": "YAKLASIYOR"}
    satirlar = m.uyari_satirlari(cihaz_, GUN)
    assert satirlar == [("Kalibrasyon süresi doldu (1 Kasım 2026, 3 gün önce)", "kritik"),
                        ("Bakım zamanı yaklaşıyor (10 Kasım 2026, 6 gün kaldı)", "uyari")]
    assert m.uyari_satirlari({}, GUN) == []
    assert m.uyari_satirlari({"kalibrasyon_gecerlilik": "2026-12-01", "kalibrasyon_uyari": None}, GUN) == []


def test_gun_ipucu_engel_rezervasyon_ve_aciklama():
    d = m.gun_durumu([tum_gun(m.BAKIM), rez(9, 10)], GUN)
    ipucu = m.gun_ipucu(GUN, d)
    assert ipucu.splitlines()[0] == "4 Kasım 2026 Çarşamba — Bakımda"
    assert "Bakım: 4 Kasım" in ipucu and "Rezervasyon: 09:00 – 10:00" in ipucu and "Bakım süresince rezerve edilemez." in ipucu
    assert m.gun_ipucu(GUN, m.gun_durumu([], GUN)) == "4 Kasım 2026 Çarşamba — Müsait"
    gece = m.gun_ipucu(GUN, m.gun_durumu([rez(22, 23), donem(m.REZERVASYON, DT(2026, 11, 4, 23), DT(2026, 11, 5))], GUN))
    assert "Rezervasyon: 22:00 – 23:00" in gece and "Rezervasyon: 23:00 – 24:00" in gece     # gece yarısı '24:00' yazılır


def test_rezervasyon_onerisi():
    simdi = DT(2026, 11, 4, 11, 10)
    bos = m.gun_durumu([], GUN)
    assert m.rezervasyon_onerisi(bos, m.saat_cizelgesi([], GUN), GUN, GUN, simdi) == ("12:00", "13:00", None)   # bugün: sonraki tam saat
    ileri = D(2026, 11, 5)
    assert m.rezervasyon_onerisi(m.gun_durumu([], ileri), m.saat_cizelgesi([], ileri), ileri, GUN, simdi) == ("08:00", "09:00", None)
    dolu_donemler = [rez(8, 10, ileri)]
    assert m.rezervasyon_onerisi(m.gun_durumu(dolu_donemler, ileri), m.saat_cizelgesi(dolu_donemler, ileri), ileri, GUN, simdi)[:2] == ("10:00", "11:00")
    gec = DT(2026, 11, 4, 17, 40)
    assert m.rezervasyon_onerisi(bos, m.saat_cizelgesi([], GUN), GUN, GUN, gec)[2] == "Bu gün mesai saatlerinde boş saat kalmadı."


def test_rezervasyon_onerisi_gecmis_ve_engelli_gunlerde_yok():
    simdi = DT(2026, 11, 4, 9)
    dun = D(2026, 11, 3)
    assert m.rezervasyon_onerisi(m.gun_durumu([], dun), m.saat_cizelgesi([], dun), dun, GUN, simdi) == (None, None, "Geçmiş günlere rezervasyon yapılamaz.")
    ariza = [tum_gun(m.ARIZA)]
    sonuc = m.rezervasyon_onerisi(m.gun_durumu(ariza, GUN), m.saat_cizelgesi(ariza, GUN), GUN, GUN, simdi)
    assert sonuc == (None, None, "Arıza çözülene kadar rezerve edilemez.")


# ------------------------------------------------- bugün için "şimdiden sonrası" kuralı
def test_bugun_sabah_cozulen_ariza_bugunu_arizali_yapmaz():
    cozulmus = donem(m.ARIZA, DT(2026, 11, 4, 8, 0), DT(2026, 11, 4, 11, 0))
    assert m.gun_durumu([cozulmus], GUN).kod == m.ARIZA                                   # simdi verilmezse tüm gün
    assert m.gun_durumu([cozulmus], GUN, DT(2026, 11, 4, 12, 0)).kod == m.MUSAIT          # çözüldükten sonra bugün müsait
    assert m.gun_durumu([cozulmus], GUN, DT(2026, 11, 4, 9, 0)).kod == m.ARIZA            # henüz çözülmediyse arızalı


def test_simdi_kurali_gecmis_ve_gelecek_gunleri_degistirmez():
    ariza = donem(m.ARIZA, DT(2026, 11, 3, 8), DT(2026, 11, 3, 11))
    simdi = DT(2026, 11, 4, 12)
    assert m.gun_durumu([ariza], D(2026, 11, 3), simdi).kod == m.ARIZA                  # dün: geçmişte yaşandı, işaretli kalır
    bakim = donem(m.BAKIM, DT(2026, 11, 5), DT(2026, 11, 6))
    assert m.gun_durumu([bakim], D(2026, 11, 5), simdi).kod == m.BAKIM                  # yarın: tüm gün


def test_bugun_devam_eden_engel_simdi_kuralindan_etkilenmez():
    acik_ariza = donem(m.ARIZA, DT(2026, 11, 2, 9), None)
    assert m.gun_durumu([acik_ariza], GUN, DT(2026, 11, 4, 23, 59)).kod == m.ARIZA
    gun_boyu_bakim = tum_gun(m.BAKIM)
    assert m.gun_durumu([gun_boyu_bakim], GUN, DT(2026, 11, 4, 17, 50)).kod == m.BAKIM


def test_simdi_kuralinin_filtre_ve_sayaca_yansimasi():
    cozulmus = donem(m.ARIZA, DT(2026, 11, 4, 8), DT(2026, 11, 4, 11))
    c = cihaz(1, donemler=[cozulmus])
    simdi = DT(2026, 11, 4, 12)
    assert m.bugun_ozeti([c], GUN, simdi)["musait"] == 1 and m.bugun_ozeti([c], GUN)["ariza"] == 1
    assert [x["cihaz_id"] for x in m.filtrele([c], mod="BUGUN_MUSAIT", bugun=GUN, simdi=simdi)] == [1]
    assert m.sorunlu_mu(c, [GUN], simdi) is False and m.sorunlu_mu(c, [GUN]) is True
