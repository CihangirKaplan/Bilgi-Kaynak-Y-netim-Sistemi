"""Ayrıntılı rapor sayfaları (cihaz rezervasyon, oda kullanım, yetki) ve denetim Excel çıktısı: ekran, süzgeç ve Excel içeriği."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from unittest.mock import MagicMock, patch

import openpyxl
import pytest
from PySide6.QtWidgets import QMessageBox

import client.main_window as ana
from client.audit_excel import audit_excel_olustur, ayrinti_metni
from client.cihaz_rezervasyon_raporu_ekrani import CihazRezervasyonRaporuEkrani
from client.oda_kullanim_raporu_ekrani import OdaKullanimRaporuEkrani
from client.yetki_raporu_ekrani import YetkiRaporuEkrani

CIHAZ = {
    "ozet": {"rezervasyon_sayisi": 2, "iptal_edilen_rezervasyon": 1, "toplam_saat": 5.0, "ortalama_sure_saat": 2.5,
             "kullanilan_cihaz_sayisi": 1, "kullanilmayan_cihaz_sayisi": 1},
    "cihazlar": [
        {"cihaz_id": 1, "envanter_kodu": "EEG-01", "cihaz_adi": "EEG", "rezervasyon_sayisi": 2, "rezervasyon_saati": 5.0,
         "iptal_edilen_rezervasyon": 1, "son_kullanim": "2026-11-04T15:00:00"},
        {"cihaz_id": 2, "envanter_kodu": "TMS-02", "cihaz_adi": "TMS", "rezervasyon_sayisi": 0, "rezervasyon_saati": 0.0,
         "iptal_edilen_rezervasyon": 0, "son_kullanim": None},
    ],
    "proje_turleri": [{"ad": "TÜBİTAK", "rezervasyon_sayisi": 1, "saat": 3.0}],
    "bolumler": [{"ad": "=HYPERLINK(\"x\")", "rezervasyon_sayisi": 2, "saat": 5.0}],
    "rezervasyonlar": [
        {"rezervasyon_id": 1, "envanter_kodu": "EEG-01", "cihaz_adi": "EEG", "bolum": "Lab", "oda": "—", "yapan": "dr_ayse",
         "baslangic_zamani": "2026-11-02T09:00:00", "bitis_zamani": "2026-11-02T12:00:00", "sure_saat": 3.0, "proje_turu": "TÜBİTAK",
         "proje_adi": "Uyku", "durum": "Aktif"},
    ],
    "aciklama": "Saatler planlanan süreyi gösterir.",
}
ODA = {
    "ozet": {"toplam_saat": 12.0, "randevu_saati": 5.0, "cihaz_rezervasyon_saati": 5.0, "etkinlik_saati": 2.0, "kullanilan_oda_sayisi": 3,
             "kullanilmayan_oda_sayisi": 0, "mesai_doluluk_orani": 0.024},
    "varsayim": {"is_gunu_sayisi": 21, "gunluk_mesai_saati": 8},
    "odalar": [{"oda_id": 1, "oda_adi": "Oda A", "aktif_mi": True, "randevu_sayisi": 4, "randevu_saati": 4.0, "cihaz_rezervasyon_sayisi": 0,
                "cihaz_rezervasyon_saati": 0.0, "etkinlik_sayisi": 1, "etkinlik_saati": 2.0, "toplam_saat": 6.0, "mesai_doluluk_orani": 0.036},
               {"oda_id": 2, "oda_adi": "Oda B", "aktif_mi": False, "randevu_sayisi": 1, "randevu_saati": 1.0, "cihaz_rezervasyon_sayisi": 0,
                "cihaz_rezervasyon_saati": 0.0, "etkinlik_sayisi": 0, "etkinlik_saati": 0.0, "toplam_saat": 1.0, "mesai_doluluk_orani": 0.006}],
    "gun_dagilimi": [{"gun": g, "kayit_sayisi": 1, "saat": 1.0} for g in ("Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar")],
    "oda_secenekleri": [{"oda_id": 1, "oda_adi": "Oda A"}],
    "kayitlar": [{"tur": "Randevu", "oda_id": 1, "oda_adi": "Oda A", "baslangic_zamani": "2026-11-02T10:00:00",
                  "bitis_zamani": "2026-11-02T11:00:00", "sure_saat": 1.0, "aciklama": "dr_ayse · TAMAMLANDI"}],
    "aciklama": "Saatler planlanan süreyi gösterir.",
}
YETKI = {
    "ozet": {"kullanici_sayisi": 2, "aktif_kullanici": 1, "pasif_kullanici": 1, "kilitli_kullanici": 1, "hic_giris_yapmamis": 1,
             "gecici_parolali": 0, "rol_sayisi": 2, "izin_sayisi": 3, "son_30_gun_basarisiz_giris": 4},
    "kullanicilar": [
        {"kullanici_id": 1, "kullanici_adi": "ali", "rol_adi": "ADMIN", "aktif_mi": True, "personel_kodu": "P1", "son_giris": None,
         "basarisiz_giris_sayisi": 5, "kilitli_mi": True, "gecici_parola_mi": False},
        {"kullanici_id": 2, "kullanici_adi": "veli", "rol_adi": "MEMUR", "aktif_mi": False, "personel_kodu": None,
         "son_giris": "2026-11-01T09:00:00", "basarisiz_giris_sayisi": 0, "kilitli_mi": False, "gecici_parola_mi": False},
    ],
    "roller": [{"rol_id": 1, "rol_adi": "ADMIN", "kullanici_sayisi": 1, "aktif_kullanici_sayisi": 1, "izin_sayisi": 3},
               {"rol_id": 2, "rol_adi": "MEMUR", "kullanici_sayisi": 1, "aktif_kullanici_sayisi": 0, "izin_sayisi": 1}],
    "matris": {"roller": ["ADMIN", "MEMUR"], "izinler": [{"izin_adi": "A_IZNI", "aciklama": "a", "roller": {"ADMIN": True, "MEMUR": False}}]},
}


def sahte_istek(veri, kayit):
    def istek(yontem, url, headers=None, params=None, timeout=None):
        kayit.append((url, dict(params or {})))
        yanit = MagicMock(status_code=200)
        yanit.json.return_value = veri if url.endswith(("rezervasyon-raporu", "kullanim-raporu", "yetki-raporu", "ogrenci-raporu", "faaliyet-raporu", "bakim-plani-raporu")) else []
        return yanit
    return istek


def ekran_ac(sinif, veri):
    kayit = []
    with patch("client.rapor_sayfasi_taban.oturum_kontrollu_istek", sahte_istek(veri, kayit)), \
         patch("client.cihaz_rezervasyon_raporu_ekrani.oturum_kontrollu_istek", sahte_istek(veri, kayit)), \
         patch("client.rapor_sayfasi_taban.oturum_hatasi_mi", return_value=False), \
         patch("client.cihaz_rezervasyon_raporu_ekrani.oturum_hatasi_mi", return_value=False):
        ekran = sinif("http://sunucu", "belirtec")
    return ekran, kayit


def yaz_ve_oku(ekran, veri, tmp_path):
    yol = str(tmp_path / "rapor.xlsx")
    ekran.excel_yaz(veri, ekran._son_filtre, yol)
    return openpyxl.load_workbook(yol)


def test_cihaz_rezervasyon_sayfasi_kartlar_tablolar_ve_istek(tmp_path):
    ekran, kayit = ekran_ac(CihazRezervasyonRaporuEkrani, CIHAZ)
    istekler = [k for k in kayit if k[0].endswith("/api/cihaz-rezervasyon-raporu")]
    assert istekler and {"baslangic", "bitis"} <= set(istekler[0][1])
    assert ekran.kartlar["rezervasyon"][0].text() == "2" and ekran.kartlar["saat"][0].text() == "5"
    assert ekran.kartlar["kullanilmayan"][0].text() == "1"
    assert ekran.tablolar["cihaz"].rowCount() == 2 and ekran.tablolar["cihaz"].item(0, 4).text() == "04.11.2026 15:00"
    assert ekran.tablolar["cihaz"].item(1, 4).text() == "—"
    kitap = yaz_ve_oku(ekran, CIHAZ, tmp_path)
    assert kitap.sheetnames == ["Özet", "Cihaz Bazlı", "Proje Türü", "Bölüm", "Rezervasyon Detayı"]
    hucre = kitap["Bölüm"]["A2"]
    assert hucre.data_type == "s" and hucre.quotePrefix is True             # formül gibi görünen metin formül olmaz


def test_oda_kullanim_sayfasi_oda_listesi_bir_kez_dolar_ve_excel_sayfalari(tmp_path):
    ekran, _ = ekran_ac(OdaKullanimRaporuEkrani, ODA)
    assert ekran.oda_sec.count() == 2 and ekran.oda_sec.itemText(1) == "Oda A"
    assert ekran.kartlar["toplam"][0].text() == "12" and ekran.kartlar["doluluk"][0].text() == "%2,4"
    assert ekran.tablolar["oda"].item(1, 0).text() == "Oda B (pasif)" and ekran.tablolar["gun"].rowCount() == 7
    ekran.goster(ODA)                                                          # ikinci yanıt listeyi çoğaltmaz
    assert ekran.oda_sec.count() == 2
    kitap = yaz_ve_oku(ekran, ODA, tmp_path)
    assert kitap.sheetnames == ["Özet", "Oda Bazlı", "Gün Dağılımı", "Kullanım Kayıtları"]
    assert kitap["Oda Bazlı"]["J2"].value == pytest.approx(0.036)


def test_oda_secilince_istege_oda_id_eklenir():
    ekran, kayit = ekran_ac(OdaKullanimRaporuEkrani, ODA)
    kayit.clear()
    with patch("client.rapor_sayfasi_taban.oturum_kontrollu_istek", sahte_istek(ODA, kayit)), \
         patch("client.rapor_sayfasi_taban.oturum_hatasi_mi", return_value=False):
        ekran.oda_sec.setCurrentIndex(1)
    assert kayit and kayit[-1][1].get("oda_id") == 1


def test_yetki_sayfasi_donem_yok_uyarilar_ve_matris(tmp_path):
    ekran, kayit = ekran_ac(YetkiRaporuEkrani, YETKI)
    assert "baslangic" not in kayit[0][1]                                       # yetki raporu dönemsizdir
    assert ekran.rol_sec.count() == 3 and ekran.kartlar["kilitli"][0].text() == "1"
    assert ekran.tablolar["kullanici"].item(0, 4).text() == "Kilitli, Hiç giriş yok"
    assert ekran.tablolar["kullanici"].item(1, 2).text() == "Pasif" and ekran.tablolar["kullanici"].item(1, 3).text() == "01.11.2026 09:00"
    assert ekran.tablolar["rol"].item(1, 1).text() == "0 / 1"
    kitap = yaz_ve_oku(ekran, YETKI, tmp_path)
    assert kitap.sheetnames == ["Özet", "Kullanıcılar", "Roller", "Rol-İzin Matrisi"]
    matris = kitap["Rol-İzin Matrisi"]
    assert [h.value for h in matris[1]] == ["İzin", "Açıklama", "ADMIN", "MEMUR"] and [h.value for h in matris[2]] == ["A_IZNI", "a", "Evet", "—"]
    metin = str([[c.value for c in satir] for satir in kitap["Kullanıcılar"].iter_rows()]).lower()
    assert "parola_hash" not in metin and "$2" not in metin                       # parola özeti Excel'e sızmaz


def test_gecersiz_tarih_araligi_istek_atmaz():
    ekran, kayit = ekran_ac(CihazRezervasyonRaporuEkrani, CIHAZ)
    with patch.object(QMessageBox, "warning") as uyari, \
         patch("client.rapor_sayfasi_taban.oturum_kontrollu_istek", sahte_istek(CIHAZ, kayit)), \
         patch("client.rapor_sayfasi_taban.oturum_hatasi_mi", return_value=False):
        ekran.donem.setCurrentText("Tarih Aralığı")                               # geçerli aralıkla yenilenir
        kayit.clear()
        ekran.bitis.blockSignals(True)
        ekran.bitis.setDate(ekran.baslangic.date().addDays(-1))                   # ters aralık
        ekran.bitis.blockSignals(False)
        ekran.yenile()
        ekran.bitis.blockSignals(True)
        ekran.bitis.setDate(ekran.baslangic.date().addDays(400))                  # 366 günü aşan aralık
        ekran.bitis.blockSignals(False)
        ekran.yenile()
    assert uyari.call_count == 2 and not kayit


def test_yeni_sayfalar_menude_ve_izinleri_tanimli():
    adlar = {o["ad"]: o for _, grup in ana.MENU for o in grup}
    beklenen = {"Cihaz Rezervasyon Raporu": "Cihaz raporlarını görüntüleme", "Oda Kullanım Raporu": "Yönetim raporlarını görüntüleme",
                "Yetki Raporu": "Audit kayıtlarını inceleme"}
    for ad, izin in beklenen.items():
        assert adlar[ad]["izin"] == izin and izin in ana.IZIN_KODLARI
        assert ad in ana.AnaPencere.SAYFA_YENILEME


def test_audit_excel_silinen_veriyi_yazar_ve_formul_enjeksiyonunu_onler(tmp_path):
    kayitlar = [
        {"denetim_id": 2, "olusturulma_tarihi": "2026-11-18T10:00:00", "kullanici_adi": "=CMD()", "olay_turu": "DELETE",
         "hedef_tablo": "cihaz_bakimlari", "hedef_kayit_id": 7, "hedef_kullanici_adi": None,
         "ayrinti": {"silinen": {"yapilan_islem": "Filtre", "maliyet": 150.5}}},
        {"denetim_id": 1, "olusturulma_tarihi": "2026-11-18T09:00:00", "kullanici_adi": "ali", "olay_turu": "LOGIN",
         "hedef_tablo": "kullanicilar", "hedef_kayit_id": 1, "hedef_kullanici_adi": "ali", "ayrinti": None},
    ]
    yol = str(tmp_path / "audit.xlsx")
    audit_excel_olustur(yol, kayitlar, {"toplam_kayit": 2}, [("Dönem", "Tümü")], kesildi=True)
    kitap = openpyxl.load_workbook(yol)
    assert kitap.sheetnames == ["Özet", "Denetim Kayıtları", "Silmeler"]
    satir = [h.value for h in kitap["Denetim Kayıtları"][2]]
    assert satir[3] == "Silme" and satir[4] == "Cihaz Bakımı" and "Yapilan islem: Filtre" in satir[7] and "Maliyet: 150.5" in satir[7]
    assert kitap["Denetim Kayıtları"]["C2"].quotePrefix is True
    assert kitap["Silmeler"].max_row == 2                                       # başlık + yalnızca silme kaydı
    assert ayrinti_metni(None) is None
    assert "sınırlandırılmıştır" in kitap["Özet"]["A2"].value


# ------------------------------------------------------------------ yönetim paneli yeni görünümleri
from client.yonetim_raporlari_panel import (
    EK_KAYNAKLAR, RAPOR_TURLERI, YonetimRaporlariEkrani, cihaz_gorunumu, oda_gorunumu, yetki_gorunumu,
)


@pytest.mark.parametrize("gorunum,veri", [(oda_gorunumu, ODA), (cihaz_gorunumu, CIHAZ), (yetki_gorunumu, YETKI)])
def test_panel_gorunumleri_4_kart_5_tablo_uretir(gorunum, veri):
    kartlar, tablolar = gorunum(veri)
    assert len(kartlar) == 4 and len(tablolar) == 5
    for ad, sutunlar, satirlar in tablolar:
        assert all(len(satir) == len(sutunlar) for satir in satirlar), ad               # her satır sütun sayısıyla uyumlu
    yok_kartlar, yok_tablolar = gorunum(None)                                           # veri alınamadı: yine 4 kart + 5 tablo
    assert len(yok_kartlar) == 4 and len(yok_tablolar) == 5 and "alınamadı" in yok_tablolar[0][2][0][0]


def test_panel_oda_gorunumu_sayilari_ayrintili_sayfayla_ayni():
    kartlar, tablolar = oda_gorunumu(ODA)
    assert kartlar[0][1] == "12" and kartlar[3][1] == "%2,4"
    assert tablolar[0][2][0][:1] == ("Oda A",) and tablolar[0][2][1][0] == "Oda B (pasif)"
    assert [satir[0] for satir in tablolar[2][2]] == ["Randevu", "Cihaz rezervasyonu", "Oda etkinliği"]


def test_panel_yetki_gorunumu_uyarili_hesaplari_listeler_parola_icermez():
    kartlar, tablolar = yetki_gorunumu(YETKI)
    assert tablolar[2][2] == [("ali", "ADMIN", "Kilitli, Hiç giriş yok")]
    assert "parola_hash" not in str(tablolar) and "$2" not in str(tablolar)


def test_panel_yeni_secenekler_ve_ek_kaynaklar():
    assert {"Oda Kullanımı", "Cihaz Kullanımı", "Yetkiler"} <= set(RAPOR_TURLERI)
    assert EK_KAYNAKLAR["yetki"][1] is False and EK_KAYNAKLAR["oda"][1] is True       # yetki raporu dönemsizdir


def test_panel_bir_ek_rapor_alinamazsa_digerleri_gosterilir():
    """Örn. kullanıcının yetki raporu izni yok (403): panel yine açılır, yalnızca o görünümde 'alınamadı' yazar."""
    def istek(yontem, url, headers=None, params=None, timeout=None):
        yanit = MagicMock(status_code=403 if url.endswith("yetki-raporu") else 200)
        yanit.json.return_value = ODA if url.endswith("oda-kullanim-raporu") else (CIHAZ if url.endswith("cihaz-rezervasyon-raporu") else {})
        return yanit
    with patch("client.yonetim_raporlari_panel.oturum_kontrollu_istek", istek):
        panel = YonetimRaporlariEkrani("http://x", "t")
        sonuc = panel.verileri_getir({"baslangic": "2026-11-01", "bitis": "2026-11-30"})
    assert sonuc["yetki"] is None and sonuc["oda"] == ODA and sonuc["cihaz_rez"] == CIHAZ
