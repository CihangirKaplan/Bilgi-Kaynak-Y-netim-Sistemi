"""
Randevu Yönetimi ekranı (eski adı Randevu Takvimi).

- Ad değişikliği her yerde tutarlı (menü, kontrol paneli kartı, kenar çubuğu simgesi, yenileme listesi)
- Psikolog sütunu, okunur tarih/saat, durum rozetleri
- Arama (Türkçe karakter duyarsız), tarih aralığı, durum filtresi, iptalleri gizle
- Yaklaşan randevular önce; iptal ve geçmişler sonra
- Düzenleme/iptal kurallarını sütun sırasına değil kayda bağlı

Tarihler hep "şimdi"ye göre üretilir (sabit tarih zamanla testleri bozar).
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import QLabel, QMessageBox

import dashboard_ekrani
import main_window as mw
import randevu_ekranlari as modul
import tkys_sidebar_refined
from randevu_ekranlari import (
    RandevuAnaEkrani,
    ara_normalle,
    donem_araligi,
    randevu_zamani,
    randevulari_filtrele,
    siralama_anahtari,
    tarih_saat_metinleri,
)

SIMDI = datetime(2026, 11, 11, 12, 0)


def zaman(gun_farki=0, saat=10, dakika=0, simdi=None):
    taban = (simdi or datetime.now()).replace(hour=saat, minute=dakika, second=0, microsecond=0)
    return (taban + timedelta(days=gun_farki)).isoformat()


def randevu(no, durum="PLANLANDI", gun=1, saat=10, danisan=None, psikolog=3, oda=2):
    return {
        "randevu_id": no, "danisan_kod_id": danisan or f"DAN-2026-{no:04d}",
        "psikolog_id": psikolog, "oda_id": oda, "durum": durum,
        "baslangic_zamani": zaman(gun, saat), "bitis_zamani": zaman(gun, saat + 1),
        "olusturma_tarihi": zaman(-10),
    }


# ------------------------------------------------------------------ ad değişikliği
def test_ekran_adi_menude_ve_her_yerde_randevu_yonetimi():
    adlar = [oge["ad"] for _, ogeler in mw.MENU for oge in ogeler]
    assert "Randevu Yönetimi" in adlar and "Randevu Takvimi" not in adlar
    assert mw.AnaPencere.SAYFA_YENILEME["Randevu Yönetimi"] == ("randevu_ana_ekrani", "verileri_cek")
    assert tkys_sidebar_refined.PAGE_ICONS["Randevu Yönetimi"] == "calendar"
    assert "Randevu Takvimi" not in tkys_sidebar_refined.PAGE_ICONS


def test_kontrol_paneli_kartlari_var_olan_sayfalara_gider():
    """Kart hedefleri menüdeki sayfa adlarıyla eşleşmeli (ad değişince kopuk kart kalmasın)."""
    adlar = {oge["ad"] for _, ogeler in mw.MENU for oge in ogeler}
    for kart, (sayfa, *_) in dashboard_ekrani.KART_HEDEFLERI.items():
        assert sayfa in adlar, f"'{kart}' kartının hedefi menüde yok: {sayfa}"


def test_sayfa_acilinca_randevu_listesi_yenilenir():
    ana = MagicMock()
    ana.SAYFA_YENILEME = mw.AnaPencere.SAYFA_YENILEME
    ana.SAYFA_YENILEME_ARALIGI = mw.AnaPencere.SAYFA_YENILEME_ARALIGI
    ana._sayfa_son_yenileme = {}
    mw.AnaPencere._sayfayi_yenile(ana, "Randevu Yönetimi")
    ana.randevu_ana_ekrani.verileri_cek.assert_called_once()


# ------------------------------------------------------------------ saf yardımcılar
def test_tarih_ve_saat_okunur_bicimde_gosterilir():
    assert tarih_saat_metinleri("2026-10-15T11:47:08.123456", "2026-10-15T12:47:00") == ("15.10.2026", "11:47 – 12:47")
    assert tarih_saat_metinleri("2026-10-15T09:00:00", None) == ("15.10.2026", "09:00")
    assert tarih_saat_metinleri(None, None) == ("", "")
    assert randevu_zamani("bozuk") is None


@pytest.mark.parametrize("metin, aranan", [
    ("Görüşme Odası-1", "gorusme"), ("Görüşme Odası-1", "GÖRÜŞME"), ("ŞEHNAZ", "sehnaz"),
    ("Işık", "isik"), ("İpek", "ipek"), ("Çiğdem", "cigdem"),
])
def test_arama_turkce_karakter_ve_buyuk_kucuk_harf_duyarsiz(metin, aranan):
    assert ara_normalle(aranan) in ara_normalle(metin)


@pytest.mark.parametrize("anahtar, bugun, beklenen", [
    ("bugun", datetime(2026, 11, 11).date(), (datetime(2026, 11, 11).date(), datetime(2026, 11, 11).date())),
    ("hafta", datetime(2026, 11, 11).date(), (datetime(2026, 11, 9).date(), datetime(2026, 11, 15).date())),   # Çarşamba
    ("hafta", datetime(2026, 11, 15).date(), (datetime(2026, 11, 9).date(), datetime(2026, 11, 15).date())),   # Pazar
    ("ay", datetime(2026, 11, 11).date(), (datetime(2026, 11, 1).date(), datetime(2026, 11, 30).date())),
    ("ay", datetime(2026, 12, 31).date(), (datetime(2026, 12, 1).date(), datetime(2026, 12, 31).date())),
    ("ay", datetime(2028, 2, 10).date(), (datetime(2028, 2, 1).date(), datetime(2028, 2, 29).date())),         # artık yıl
    ("tumu", datetime(2026, 11, 11).date(), None),
    ("ozel", datetime(2026, 11, 11).date(), None),
])
def test_donem_araliklari(anahtar, bugun, beklenen):
    assert donem_araligi(anahtar, bugun) == beklenen


def test_siralama_yaklasanlar_once_sonra_gecmis_ve_iptaller_en_yeni_ustte():
    yaklasan_yakin = randevu(1, gun=1)
    yaklasan_uzak = randevu(2, gun=5)
    gecmis_yeni = randevu(3, gun=-1)
    gecmis_eski = randevu(4, gun=-9)
    iptal_gelecek = randevu(5, durum="IPTAL_EDILDI", gun=2)
    tamamlanan = randevu(6, durum="TAMAMLANDI", gun=-3)
    simdi = datetime.now()
    liste = [gecmis_eski, iptal_gelecek, yaklasan_uzak, tamamlanan, gecmis_yeni, yaklasan_yakin]
    liste.sort(key=lambda r: siralama_anahtari(r, simdi))
    assert [r["randevu_id"] for r in liste] == [1, 2, 5, 3, 6, 4]


def test_devam_eden_randevu_yaklasan_sayilir():
    simdi = datetime.now()
    suren = {"randevu_id": 1, "durum": "PLANLANDI",
             "baslangic_zamani": (simdi - timedelta(minutes=20)).isoformat(),
             "bitis_zamani": (simdi + timedelta(minutes=40)).isoformat()}
    assert siralama_anahtari(suren, simdi)[0] == 0


def test_bozuk_tarihli_kayit_en_sona_gider_cokmez():
    assert siralama_anahtari({"durum": "PLANLANDI", "baslangic_zamani": None}, datetime.now())[0] == 2


PSIKOLOGLAR = {3: "Ayşe Yılmaz", 7: "Reyhan Kaya"}
ODALAR = {2: "Görüşme Odası-1", 3: "Görüşme Odası-2"}


def filtre(liste, **kwargs):
    return [r["randevu_id"] for r in randevulari_filtrele(liste, PSIKOLOGLAR, ODALAR, **kwargs)]


def test_arama_danisan_kodu_psikolog_oda_ve_id_uzerinden_calisir():
    liste = [randevu(1, danisan="DAN-2026-0031", psikolog=3, oda=2),
             randevu(2, danisan="DAN-2026-0040", psikolog=7, oda=3)]
    assert filtre(liste, arama="0040") == [2]
    assert filtre(liste, arama="reyhan") == [2]
    assert filtre(liste, arama="AYSE") == [1]                # Türkçe karakter duyarsız
    assert filtre(liste, arama="gorusme odasi-2") == [2]
    assert filtre(liste, arama="  ") == [1, 2]                # boşluk = filtre yok
    assert filtre(liste, arama="yok boyle bir sey") == []


def test_tarih_araligi_baslangic_gunune_gore_ve_sinirlar_dahil():
    bugun = datetime.now().date()
    liste = [randevu(1, gun=-2), randevu(2, gun=0), randevu(3, gun=2), randevu(4, gun=10)]
    assert filtre(liste, aralik=(bugun, bugun)) == [2]
    assert filtre(liste, aralik=(bugun - timedelta(days=2), bugun + timedelta(days=2))) == [1, 2, 3]
    assert filtre(liste, aralik=None) == [1, 2, 3, 4]


def test_iptalleri_gizle_ama_durum_acikca_secilince_iptaller_gorunur():
    liste = [randevu(1), randevu(2, durum="IPTAL_EDILDI"), randevu(3, durum="TAMAMLANDI")]
    assert filtre(liste, iptalleri_gizle=True) == [1, 3]
    assert filtre(liste, iptalleri_gizle=False) == [1, 2, 3]
    assert filtre(liste, durum="IPTAL_EDILDI", iptalleri_gizle=True) == [2]   # açık seçim önceliklidir
    assert filtre(liste, durum="TAMAMLANDI") == [3]


def test_filtreler_birlikte_calisir():
    bugun = datetime.now().date()
    liste = [randevu(1, gun=0, psikolog=3), randevu(2, gun=0, psikolog=7), randevu(3, gun=5, psikolog=7),
             randevu(4, gun=0, psikolog=7, durum="IPTAL_EDILDI")]
    assert filtre(liste, arama="reyhan", aralik=(bugun, bugun), iptalleri_gizle=True) == [2]


# ------------------------------------------------------------------ ekran
def cevap(veri, durum=200):
    yanit = MagicMock()
    yanit.status_code = durum
    yanit.json.return_value = veri
    yanit._tkys_oturum_reddedildi = False
    return yanit


class Sunucu:
    def __init__(self, randevular, psikolog_durumu=200, iptal_cevabi=None):
        self.randevular = randevular
        self.psikolog_durumu = psikolog_durumu
        self.iptal_cevabi = iptal_cevabi or cevap({"durum": "basarili"})
        self.istekler = []

    def __call__(self, yontem, url, **kwargs):
        self.istekler.append((yontem, url))
        if yontem == "PATCH":
            return self.iptal_cevabi
        if url.endswith("/api/randevular"):
            return cevap(self.randevular)
        if url.endswith("/api/psikologlar"):
            if self.psikolog_durumu != 200:
                return cevap({"detail": "yetki yok"}, self.psikolog_durumu)
            return cevap([{"personel_id": k, "ad_soyad": v, "kullanici_id": 100 + k} for k, v in PSIKOLOGLAR.items()])
        if url.endswith("/api/odalar"):
            return cevap([{"oda_id": k, "oda_adi": v, "kapasite": 1, "aktif_mi": True} for k, v in ODALAR.items()])
        return cevap([])


def ekran_ac(sunucu):
    with patch.object(modul, "oturum_kontrollu_istek", side_effect=sunucu):
        return RandevuAnaEkrani("http://testserver", "TOKEN", 11, "admin")


def sutun(ekran, no):
    return [ekran.tablo.item(i, no).text() for i in range(ekran.tablo.rowCount())]


def ornek_liste():
    return [
        randevu(1, gun=-9),                                    # geçmiş, hâlâ planlı
        randevu(2, gun=3, psikolog=7, oda=3),                  # yaklaşan (uzak)
        randevu(3, gun=1),                                     # yaklaşan (yakın)
        randevu(4, durum="IPTAL_EDILDI", gun=2),               # iptal
        randevu(5, durum="TAMAMLANDI", gun=-3),
    ]


def test_basliklar_psikolog_sutunu_var_olusturulma_tarihi_yok():
    ekran = ekran_ac(Sunucu([]))
    basliklar = [ekran.tablo.horizontalHeaderItem(i).text() for i in range(ekran.tablo.columnCount())]
    assert basliklar == ["Randevu ID", "Danışan Kodu", "Psikolog", "Oda", "Tarih", "Saat", "Durum"]
    ekran.close()


def test_varsayilan_yaklasanlar_once_iptaller_gizli_psikolog_ve_oda_adlari_gorunur():
    ekran = ekran_ac(Sunucu(ornek_liste()))
    assert sutun(ekran, 0) == ["3", "2", "5", "1"]                 # iptal (4) gizli; yaklaşanlar, sonra yeniden eskiye
    assert sutun(ekran, 2)[:2] == ["Ayşe Yılmaz", "Reyhan Kaya"]
    assert sutun(ekran, 3)[:2] == ["Görüşme Odası-1", "Görüşme Odası-2"]
    assert ekran.lbl_sayac.text() == "4 / 5 randevu"
    ekran.close()


def test_iptalleri_gizle_kapatilinca_iptaller_gorunur():
    ekran = ekran_ac(Sunucu(ornek_liste()))
    ekran.chk_iptal_gizle.setChecked(False)
    assert "4" in sutun(ekran, 0) and ekran.tablo.rowCount() == 5
    ekran.close()


def test_arama_kutusu_listeyi_daraltir_ve_bos_durumda_bilgi_gosterir():
    ekran = ekran_ac(Sunucu(ornek_liste()))
    ekran.arama.setText("reyhan")
    assert sutun(ekran, 0) == ["2"] and ekran.lbl_bos.isHidden()
    ekran.arama.setText("hicbir sey bulunamaz")
    assert ekran.tablo.rowCount() == 0
    assert not ekran.lbl_bos.isHidden() and ekran.tablo.isHidden()
    ekran.arama.setText("")
    assert ekran.tablo.rowCount() == 4 and not ekran.tablo.isHidden()
    ekran.close()


def test_hazir_donem_ve_ozel_aralik_filtreleri():
    ekran = ekran_ac(Sunucu([randevu(1, gun=0, saat=10), randevu(2, gun=2), randevu(3, gun=-4)]))
    ekran.cmb_donem.setCurrentIndex(ekran.cmb_donem.findData("bugun"))
    assert sutun(ekran, 0) == ["1"]
    assert ekran.dt_bas.isHidden()                                  # özel aralık kutuları yalnızca "Özel aralık"ta görünür

    ekran.cmb_donem.setCurrentIndex(ekran.cmb_donem.findData("ozel"))
    assert not ekran.dt_bas.isHidden() and not ekran.dt_bit.isHidden()
    bugun = QDate.currentDate()
    ekran.dt_bas.setDate(bugun.addDays(-5))
    ekran.dt_bit.setDate(bugun.addDays(3))
    assert sorted(sutun(ekran, 0)) == ["1", "2", "3"]
    ekran.dt_bas.setDate(bugun.addDays(1))
    ekran.dt_bit.setDate(bugun.addDays(3))
    assert sutun(ekran, 0) == ["2"]
    ekran.dt_bas.setDate(bugun.addDays(3))                           # başlangıç > bitiş: kendiliğinden düzeltilir
    ekran.dt_bit.setDate(bugun.addDays(1))
    assert sutun(ekran, 0) == ["2"]
    ekran.close()


def test_durum_filtresi():
    ekran = ekran_ac(Sunucu(ornek_liste()))
    ekran.cmb_durum.setCurrentIndex(ekran.cmb_durum.findData("IPTAL_EDILDI"))
    assert sutun(ekran, 0) == ["4"]                                  # iptal gizle açık olsa da açık seçim görünür
    ekran.cmb_durum.setCurrentIndex(ekran.cmb_durum.findData("TAMAMLANDI"))
    assert sutun(ekran, 0) == ["5"]
    ekran.close()


def test_okunur_tarih_ve_saat_sutunlari():
    kayit = randevu(1, gun=1, saat=9)
    ekran = ekran_ac(Sunucu([kayit]))
    beklenen_tarih, beklenen_saat = tarih_saat_metinleri(kayit["baslangic_zamani"], kayit["bitis_zamani"])
    assert sutun(ekran, 4) == [beklenen_tarih] and sutun(ekran, 5) == ["09:00 – 10:00"] == [beklenen_saat]
    ekran.close()


def test_durum_rozetleri_yumusak_renkli_ve_iptal_kirmizi_degil():
    ekran = ekran_ac(Sunucu([randevu(1), randevu(2, durum="TAMAMLANDI", gun=-1),
                             randevu(3, durum="GELMEDI", gun=-2), randevu(4, durum="IPTAL_EDILDI", gun=-3)]))
    ekran.chk_iptal_gizle.setChecked(False)
    rozetler = {}
    for satir in range(ekran.tablo.rowCount()):
        etiket = ekran.tablo.cellWidget(satir, 6).findChild(QLabel)
        rozetler[etiket.text()] = etiket.styleSheet()
    assert set(rozetler) == {"Planlandı", "Tamamlandı", "Gelmedi", "İptal Edildi"}
    assert "#DBEAFE" in rozetler["Planlandı"] and "#1D4ED8" in rozetler["Planlandı"]       # mavi
    assert "#DCFCE7" in rozetler["Tamamlandı"]                                              # yeşil
    assert "#FCE7F3" in rozetler["Gelmedi"] and "#BE185D" in rozetler["Gelmedi"]            # pembe
    assert "#F1F5F9" in rozetler["İptal Edildi"] and "#64748B" in rozetler["İptal Edildi"]  # nötr gri
    for stil in rozetler.values():
        assert "border-radius" in stil
    ekran.close()


def gorunen_rozetler(ekran):
    # isHidden() yalnızca kendi durumuna bakar; kabı gizlenmiş rozet için isVisibleTo() yanlış-pozitifi önler.
    return [w for w in ekran.tablo.viewport().findChildren(QLabel) if w.isVisibleTo(ekran.tablo)]


def test_filtre_degisince_eski_rozetlerin_hayaleti_kalmaz():
    """Qt eski hücre bileşenlerini hemen silmez; gizlenmezse yeni satırların arkasında eski rozetler görünür."""
    ekran = ekran_ac(Sunucu(ornek_liste() + [randevu(6, durum="GELMEDI", gun=-5)]))
    ekran.chk_iptal_gizle.setChecked(False)
    assert len(gorunen_rozetler(ekran)) == ekran.tablo.rowCount() == 6
    ekran.cmb_durum.setCurrentIndex(ekran.cmb_durum.findData("TAMAMLANDI"))
    assert ekran.tablo.rowCount() == 1 and len(gorunen_rozetler(ekran)) == 1
    ekran.cmb_durum.setCurrentIndex(0)
    ekran.arama.setText("reyhan")
    assert len(gorunen_rozetler(ekran)) == ekran.tablo.rowCount() == 1
    ekran.close()


def test_psikolog_listesi_alinamazsa_kimlikle_gosterilir():
    ekran = ekran_ac(Sunucu([randevu(1, psikolog=3)], psikolog_durumu=403))
    assert sutun(ekran, 2) == ["Psikolog #3"]
    ekran.close()


# ------------------------------------------------------------------ düzenleme ve iptal
def sec(ekran, randevu_id):
    for satir in range(ekran.tablo.rowCount()):
        if ekran.tablo.item(satir, 0).text() == str(randevu_id):
            ekran.tablo.selectRow(satir)
            return
    raise AssertionError(randevu_id)


def test_secim_yoksa_duzenle_ve_iptal_uyarir():
    ekran = ekran_ac(Sunucu(ornek_liste()))
    with patch.object(modul.tmk, "uyari") as uyari, patch.object(modul, "RandevuDuzenleFormu") as form:
        ekran.duzenle_secilen()
        ekran.iptal_et_secilen()
    assert uyari.call_count == 2
    form.assert_not_called()
    ekran.close()


def test_planli_randevu_duzenleme_formunu_kayitla_acar_ve_cift_tik_da_acar():
    ekran = ekran_ac(Sunucu(ornek_liste()))
    sec(ekran, 3)
    with patch.object(modul, "RandevuDuzenleFormu") as form:
        ekran.duzenle_secilen()
        ekran.tablo.cellDoubleClicked.emit(0, 0)         # çift tık aynı işi yapar
    assert form.call_count == 2
    kwargs = form.call_args.kwargs
    assert kwargs["randevu_id"] == 3 and kwargs["eski_veriler"]["danisan_kod_id"] == "DAN-2026-0003"
    form.return_value.veriler_degisti.connect.assert_called_with(ekran.verileri_cek)
    ekran.close()


@pytest.mark.parametrize("durum", ["IPTAL_EDILDI", "TAMAMLANDI", "GELMEDI"])
def test_planli_olmayan_randevu_duzenlenemez(durum):
    ekran = ekran_ac(Sunucu([randevu(1, durum=durum)]))
    ekran.chk_iptal_gizle.setChecked(False)
    sec(ekran, 1)
    with patch.object(modul.tmk, "uyari") as uyari, patch.object(modul, "RandevuDuzenleFormu") as form:
        ekran.duzenle_secilen()
    uyari.assert_called_once()
    form.assert_not_called()
    ekran.close()


def test_planli_randevu_onayla_iptal_edilir_ve_liste_yenilenir():
    sunucu = Sunucu(ornek_liste())
    ekran = ekran_ac(sunucu)
    sec(ekran, 3)
    with patch.object(modul, "oturum_kontrollu_istek", side_effect=sunucu), \
            patch.object(modul.tmk, "soru", return_value=QMessageBox.Yes), \
            patch.object(modul.tmk, "bilgi") as bilgi:
        ekran.iptal_et_secilen()
    assert ("PATCH", "http://testserver/api/randevular/3/iptal") in sunucu.istekler
    bilgi.assert_called_once()
    assert sunucu.istekler[-1][1].endswith("/api/randevular")      # iptalden sonra liste yeniden çekildi
    ekran.close()


def test_iptal_onaylanmazsa_istek_atilmaz():
    sunucu = Sunucu(ornek_liste())
    ekran = ekran_ac(sunucu)
    sec(ekran, 3)
    with patch.object(modul, "oturum_kontrollu_istek", side_effect=sunucu), \
            patch.object(modul.tmk, "soru", return_value=QMessageBox.No):
        ekran.iptal_et_secilen()
    assert not any(y == "PATCH" for y, _ in sunucu.istekler)
    ekran.close()


def test_iptal_reddedilirse_sunucunun_mesaji_gosterilir():
    sunucu = Sunucu(ornek_liste(), iptal_cevabi=cevap({"detail": "Bu randevu iptal edilemez."}, 409))
    ekran = ekran_ac(sunucu)
    sec(ekran, 3)
    with patch.object(modul, "oturum_kontrollu_istek", side_effect=sunucu), \
            patch.object(modul.tmk, "soru", return_value=QMessageBox.Yes), \
            patch.object(modul.tmk, "uyari") as uyari:
        ekran.iptal_et_secilen()
    assert uyari.call_args.args[2] == "Bu randevu iptal edilemez."
    ekran.close()


@pytest.mark.parametrize("durum, parca", [("IPTAL_EDILDI", "zaten iptal"), ("TAMAMLANDI", "iptal edilemez"), ("GELMEDI", "iptal edilemez")])
def test_planli_olmayan_randevu_iptal_edilemez(durum, parca):
    sunucu = Sunucu([randevu(1, durum=durum)])
    ekran = ekran_ac(sunucu)
    ekran.chk_iptal_gizle.setChecked(False)
    sec(ekran, 1)
    with patch.object(modul, "oturum_kontrollu_istek", side_effect=sunucu), \
            patch.object(modul.tmk, "bilgi") as bilgi, patch.object(modul.tmk, "soru") as soru:
        ekran.iptal_et_secilen()
    bilgi.assert_called_once()
    assert parca in bilgi.call_args.args[2]
    soru.assert_not_called()
    ekran.close()


def test_yenile_dugmesi_listeyi_yeniden_ceker():
    sunucu = Sunucu(ornek_liste())
    ekran = ekran_ac(sunucu)
    onceki = sum(1 for _, u in sunucu.istekler if u.endswith("/api/randevular"))
    sunucu.randevular = [randevu(9)]
    with patch.object(modul, "oturum_kontrollu_istek", side_effect=sunucu):
        ekran.btn_yenile.click()
    assert sutun(ekran, 0) == ["9"]
    assert sum(1 for _, u in sunucu.istekler if u.endswith("/api/randevular")) == onceki + 1
    ekran.close()


def test_sunucu_hatasinda_mevcut_liste_korunur():
    sunucu = Sunucu(ornek_liste())
    ekran = ekran_ac(sunucu)
    sunucu.randevular = None
    def bozuk(yontem, url, **kwargs):
        if url.endswith("/api/randevular"):
            return cevap({"detail": "hata"}, 500)
        return sunucu(yontem, url, **kwargs)
    with patch.object(modul, "oturum_kontrollu_istek", side_effect=bozuk):
        ekran.verileri_cek()
    assert ekran.tablo.rowCount() == 4                               # eski liste silinmedi
    # Sunucu hatasında kullanıcıya açıklama gösterilmeli.
    assert not ekran.lbl_randevu_hatasi.isHidden()
    assert "güncel olmayabilir" in ekran.lbl_randevu_hatasi.text()

    # Başarılı yenileme sonrasında uyarı kaybolmalı.
    sunucu.randevular = ornek_liste()
    with patch.object(
        modul, "oturum_kontrollu_istek", side_effect=sunucu
    ):
        ekran.verileri_cek()

    assert ekran.tablo.rowCount() == 4
    assert ekran.lbl_randevu_hatasi.isHidden()
    ekran.close()
