"""Danışma masası raporu: Excel çıktısı, ekran düğmesi ve sunucunun öğrenci durumu alanı.

Gerçek sunucu/PostgreSQL kullanılmaz; veritabanı ve ağ istekleri taklit edilir.
"""
import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from PySide6.QtWidgets import QApplication

import danisma_masasi_raporlari as ekran_modulu
import sunucu
from danisma_rapor_excel import excel_dosyasi_olustur
from sunucu import app

VERI = {
    "ozet": {
        "toplam_gorev": 4, "devam_eden": 1, "tamamlanan": 3, "onay_bekleyen": 1, "onaylanan": 2,
        "toplam_calisma_saniye": 3 * 3600 + 1800, "onaylanan_calisma_saniye": 2 * 3600,
    },
    "ogrenci_ozetleri": [
        {"ogrenci_id": 1, "ad_soyad": "Ayşe Yılmaz", "ogrenci_numarasi": "1001", "aktif_mi": True,
         "toplam_gorev": 2, "devam_eden": 1, "onay_bekleyen": 0, "onaylanan": 1,
         "toplam_saniye": 3600, "onaylanan_saniye": 3600},
        {"ogrenci_id": 2, "ad_soyad": "Burak Demir", "ogrenci_numarasi": "1002", "aktif_mi": False,
         "toplam_gorev": 2, "devam_eden": 0, "onay_bekleyen": 1, "onaylanan": 1,
         "toplam_saniye": 9000, "onaylanan_saniye": 3600},
    ],
    "oturumlar": [
        {"oturum_id": 11, "ogrenci_id": 1, "ad_soyad": "Ayşe Yılmaz", "ogrenci_numarasi": "1001",
         "ogrenci_aktif_mi": True, "baslangic_zamani": "2026-11-10T09:00:00", "bitis_zamani": "2026-11-10T10:00:00",
         "toplam_saniye": 3600, "durum": "TAMAMLANDI", "onaylandi_mi": True},
        {"oturum_id": 12, "ogrenci_id": 1, "ad_soyad": "Ayşe Yılmaz", "ogrenci_numarasi": "1001",
         "ogrenci_aktif_mi": True, "baslangic_zamani": "2026-11-11T09:00:00", "bitis_zamani": None,
         "toplam_saniye": 0, "durum": "AKTIF", "onaylandi_mi": False},
        {"oturum_id": 13, "ogrenci_id": 2, "ad_soyad": "Burak Demir", "ogrenci_numarasi": "1002",
         "ogrenci_aktif_mi": False, "baslangic_zamani": "2026-11-09T09:00:00", "bitis_zamani": "2026-11-09T10:00:00",
         "toplam_saniye": 3600, "durum": "TAMAMLANDI", "onaylandi_mi": True},
        {"oturum_id": 14, "ogrenci_id": 2, "ad_soyad": "Burak Demir", "ogrenci_numarasi": "1002",
         "ogrenci_aktif_mi": False, "baslangic_zamani": "2026-11-08T09:00:00", "bitis_zamani": "2026-11-08T11:30:00",
         "toplam_saniye": 5400, "durum": "TAMAMLANDI", "onaylandi_mi": False},
    ],
}
FILTRE = [("Dönem", "Tümü"), ("Öğrenci", "Tüm Öğrenciler")]


def uret(tmp_path, veri=VERI, filtre=FILTRE):
    yol = tmp_path / "rapor.xlsx"
    excel_dosyasi_olustur(veri, filtre, str(yol))
    return load_workbook(yol)


def satirlar(sayfa):
    return [[h.value for h in satir] for satir in sayfa.iter_rows(min_row=2)]


def ozet_metni(sayfa):
    return {(r[0].value, r[1].value) for r in sayfa.iter_rows() if r[0].value}


# ================================================================ Excel içeriği
def test_uc_sayfa_beklenen_sirayla_olusur(tmp_path):
    assert uret(tmp_path).sheetnames == ["Özet", "Görev Kayıtları", "Öğrenci Bazlı"]


def test_gorev_kayitlari_sayfasi_basliklari_ve_satirlari(tmp_path):
    sayfa = uret(tmp_path)["Görev Kayıtları"]
    assert [h.value for h in sayfa[1]] == [
        "Öğrenci", "Öğrenci No", "Öğrenci Durumu", "Başlangıç", "Bitiş", "Çalışma Süresi", "Görev Durumu", "Onay Durumu"]
    satir = satirlar(sayfa)
    assert len(satir) == 4
    assert satir[0][:3] == ["Ayşe Yılmaz", "1001", "Aktif"]
    assert satir[0][3] == datetime.datetime(2026, 11, 10, 9, 0) and satir[0][4] == datetime.datetime(2026, 11, 10, 10, 0)
    assert satir[0][5] == 1.0 and satir[0][6:] == ["Tamamlandı", "Onaylandı"]


def test_devam_eden_gorevin_bitisi_ve_suresi_bostur_onayi_tire(tmp_path):
    devam = satirlar(uret(tmp_path)["Görev Kayıtları"])[1]
    assert devam[4] is None and devam[5] is None and devam[6] == "Devam ediyor" and devam[7] == "—"


def test_onay_bekleyen_gorev_ve_sure_saat_olarak_yazilir(tmp_path):
    bekleyen = satirlar(uret(tmp_path)["Görev Kayıtları"])[3]
    assert bekleyen[5] == 1.5 and bekleyen[7] == "Onay bekliyor"


def test_pasif_ogrenci_her_iki_sayfada_pasif_olarak_gorunur(tmp_path):
    kitap = uret(tmp_path)
    gorevler = [r for r in satirlar(kitap["Görev Kayıtları"]) if r[0] == "Burak Demir"]
    assert gorevler and all(r[2] == "Pasif" for r in gorevler)
    bazli = {r[0]: r for r in satirlar(kitap["Öğrenci Bazlı"])}
    assert bazli["Burak Demir"][2] == "Pasif" and bazli["Ayşe Yılmaz"][2] == "Aktif"


def test_ogrenci_bazli_sayfa_sayilari_ve_sureleri(tmp_path):
    sayfa = uret(tmp_path)["Öğrenci Bazlı"]
    assert [h.value for h in sayfa[1]] == [
        "Öğrenci", "Öğrenci No", "Öğrenci Durumu", "Toplam Görev", "Devam Eden", "Onay Bekleyen", "Onaylanan",
        "Toplam Süre", "Onaylı Süre"]
    ayse, burak = satirlar(sayfa)
    assert ayse == ["Ayşe Yılmaz", "1001", "Aktif", 2, 1, 0, 1, 1.0, 1.0]
    assert burak == ["Burak Demir", "1002", "Pasif", 2, 0, 1, 1, 2.5, 1.0]


def test_ozet_sayfasi_toplamlari_ve_pasif_ogrenci_listesi(tmp_path):
    ozet = ozet_metni(uret(tmp_path)["Özet"])
    for beklenen in [("Toplam görev", 4), ("Devam eden", 1), ("Tamamlanan", 3), ("Onay bekleyen", 1), ("Onaylanan", 2),
                     ("Toplam çalışma süresi", 3.5), ("Onaylı çalışma süresi", 2.0), ("Onay bekleyen süre", 1.5),
                     ("Ortalama görev süresi", 1.17), ("Rapordaki öğrenciler", 2),
                     ("Aktif öğrenci", 1), ("Pasif öğrenci", 1)]:
        assert beklenen in ozet, beklenen
    metin = " ".join(str(c.value) for r in uret(tmp_path)["Özet"].iter_rows() for c in r if c.value)
    assert "Burak Demir (1002)" in metin


def test_ozet_sayfasi_filtreleri_ve_rapor_tarihini_gosterir(tmp_path):
    kitap = uret(tmp_path, filtre=[("Dönem", "01.11.2026 - 30.11.2026"), ("Öğrenci", "Ayşe Yılmaz - 1001")])
    ozet = ozet_metni(kitap["Özet"])
    assert ("Dönem", "01.11.2026 - 30.11.2026") in ozet and ("Öğrenci", "Ayşe Yılmaz - 1001") in ozet
    assert any(ad == "Rapor Tarihi" and isinstance(d, datetime.datetime) for ad, d in ozet)


def test_ozet_ve_gorev_sayfalari_cihaz_raporuyla_ayni_basliklari_kullanir(tmp_path):
    import rapor_excel
    kitap = uret(tmp_path)
    assert kitap["Görev Kayıtları"]["A1"].fill.fgColor.rgb.endswith("E8F0FF")
    assert kitap["Görev Kayıtları"]["A1"].font.bold and rapor_excel.BASLIK_DOLGU.fgColor.rgb.endswith("E8F0FF")
    assert kitap["Özet"]["A1"].value.startswith("DANIŞMA MASASI RAPORU")


def test_bos_rapor_hatasiz_uretilir(tmp_path):
    bos = {"ozet": {}, "ogrenci_ozetleri": [], "oturumlar": []}
    kitap = uret(tmp_path, bos)
    assert satirlar(kitap["Görev Kayıtları"]) == [] and satirlar(kitap["Öğrenci Bazlı"]) == []
    ozet = ozet_metni(kitap["Özet"])
    assert ("Toplam görev", 0) in ozet and ("Pasif öğrenci", 0) in ozet


def test_eski_sunucu_aktiflik_alani_gondermezse_bilinmiyor_yazilir(tmp_path):
    eski = {"ozet": {}, "ogrenci_ozetleri": [{"ad_soyad": "A", "ogrenci_numarasi": "1", "toplam_gorev": 1}],
            "oturumlar": [{"ad_soyad": "A", "ogrenci_numarasi": "1", "baslangic_zamani": "2026-11-01T09:00:00",
                           "bitis_zamani": None, "toplam_saniye": 0}]}
    kitap = uret(tmp_path, eski)
    assert satirlar(kitap["Öğrenci Bazlı"])[0][2] == "Bilinmiyor" and satirlar(kitap["Görev Kayıtları"])[0][2] == "Bilinmiyor"
    assert ("Pasif öğrenci", 0) in ozet_metni(kitap["Özet"])        # bilinmeyen, pasif sayılmaz


@pytest.mark.parametrize("tehlikeli", ["=1+1", "+SUM(A1)", "-2+3", "@HYPERLINK(\"x\")"])
def test_ogrenci_adi_formul_olarak_calismaz(tmp_path, tehlikeli):
    veri = {"ozet": {}, "ogrenci_ozetleri": [{"ad_soyad": tehlikeli, "ogrenci_numarasi": "1", "aktif_mi": True}],
            "oturumlar": [{"ad_soyad": tehlikeli, "ogrenci_numarasi": "1", "baslangic_zamani": "2026-11-01T09:00:00",
                           "bitis_zamani": None}]}
    kitap = uret(tmp_path, veri)
    for ad in ("Görev Kayıtları", "Öğrenci Bazlı"):
        hucre = kitap[ad]["A2"]
        assert hucre.data_type == "s" and hucre.value == tehlikeli


def test_kaydedilemezse_oserror_yukselir(tmp_path):
    with pytest.raises(OSError):
        excel_dosyasi_olustur(VERI, FILTRE, str(tmp_path / "yok_klasor" / "r.xlsx"))


# ================================================================ ekran
@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def yanit(veri):
    r = MagicMock()
    r.status_code = 200
    r.json.return_value = veri
    return r


def ekran_ac(qt_app, veri=VERI, yanit_yok=False):
    hata = ekran_modulu.requests.RequestException("ag yok")
    istek = MagicMock(side_effect=hata) if yanit_yok else MagicMock(return_value=yanit(veri))
    with patch.object(ekran_modulu, "oturum_kontrollu_istek", istek), \
            patch.object(ekran_modulu, "oturum_hatasi_mi", return_value=False), \
            patch.object(ekran_modulu.QMessageBox, "warning"):
        return ekran_modulu.DanismaMasasiRaporlari("http://s", "t")


def test_excel_dugmesi_rapor_gelince_acilir_gelmezse_kapali_kalir(qt_app):
    acik = ekran_ac(qt_app)
    kapali = ekran_ac(qt_app, yanit_yok=True)
    assert acik.excel_btn.isEnabled() and acik.excel_btn.text() == "⬇ Excel'e Aktar"
    assert not kapali.excel_btn.isEnabled() and kapali._son_veri is None


def test_ogrenci_bazli_tabloda_durum_sutunu_pasifi_gosterir(qt_app):
    e = ekran_ac(qt_app)
    basliklar = [e.ogrenci_tablo.horizontalHeaderItem(i).text() for i in range(e.ogrenci_tablo.columnCount())]
    assert basliklar[:3] == ["Öğrenci", "Öğrenci No", "Durum"]
    assert [e.ogrenci_tablo.item(s, 2).text() for s in range(2)] == ["Aktif", "Pasif"]


def test_eski_sunucuda_durum_sutunu_tire_gosterir(qt_app):
    eski = {"ozet": {}, "ogrenci_ozetleri": [{"ogrenci_id": 1, "ad_soyad": "A", "ogrenci_numarasi": "1", "toplam_gorev": 0,
                                                "devam_eden": 0, "onay_bekleyen": 0, "onaylanan": 0,
                                                "toplam_saniye": 0, "onaylanan_saniye": 0}], "oturumlar": []}
    assert ekran_ac(qt_app, eski).ogrenci_tablo.item(0, 2).text() == "—"


def test_excel_aktar_son_veriyle_dosyayi_yazar_ve_uzantiyi_tamamlar(qt_app, tmp_path):
    e = ekran_ac(qt_app)
    hedef = str(tmp_path / "rapor")                                   # uzantısız verildi
    with patch.object(ekran_modulu.QFileDialog, "getSaveFileName", return_value=(hedef, "")), \
            patch.object(ekran_modulu.QMessageBox, "information") as bilgi:
        e.excel_aktar()
    dosya = Path(hedef + ".xlsx")
    assert dosya.exists() and bilgi.called
    assert load_workbook(dosya).sheetnames == ["Özet", "Görev Kayıtları", "Öğrenci Bazlı"]


def test_excel_aktar_kaydetme_penceresi_iptal_edilirse_dosya_yazilmaz(qt_app):
    e = ekran_ac(qt_app)
    with patch.object(ekran_modulu.QFileDialog, "getSaveFileName", return_value=("", "")), \
            patch.object(ekran_modulu, "excel_dosyasi_olustur") as uretici:
        e.excel_aktar()
    assert not uretici.called


def test_excel_aktar_rapor_yokken_uyari_verir_ve_yazmaz(qt_app):
    e = ekran_ac(qt_app, yanit_yok=True)
    with patch.object(ekran_modulu.QMessageBox, "information") as bilgi, \
            patch.object(ekran_modulu, "excel_dosyasi_olustur") as uretici:
        e.excel_aktar()
    assert bilgi.called and not uretici.called


def test_excel_aktar_yazma_hatasinda_kullaniciya_anlasilir_uyari_verir(qt_app, tmp_path):
    e = ekran_ac(qt_app)
    with patch.object(ekran_modulu.QFileDialog, "getSaveFileName", return_value=(str(tmp_path / "r.xlsx"), "")), \
            patch.object(ekran_modulu, "excel_dosyasi_olustur", side_effect=OSError("kilitli")), \
            patch.object(ekran_modulu.QMessageBox, "warning") as uyari, \
            patch.object(ekran_modulu.QMessageBox, "information") as bilgi:
        e.excel_aktar()
    assert uyari.called and "Excel'de açık" in uyari.call_args.args[2] and not bilgi.called


def test_filtre_ozeti_donemi_ve_ogrenciyi_yazar(qt_app):
    e = ekran_ac(qt_app)
    assert e._filtre_ozeti({}) == [("Dönem", "Tümü"), ("Öğrenci", "Tüm Öğrenciler")]
    ozet = e._filtre_ozeti({"baslangic_tarihi": "2026-11-01", "bitis_tarihi": "2026-11-30"})
    assert ozet[0] == ("Dönem", "01.11.2026 - 30.11.2026")


def test_excel_ekranda_gorulen_son_veriyle_uretilir_yeni_filtre_getirilmeden_degismez(qt_app):
    e = ekran_ac(qt_app)
    ilk = e._son_veri
    e.donem.setCurrentText("Bugün")                                   # filtre değişti ama rapor yeniden getirilmedi
    assert e._son_veri is ilk and e._son_filtre[0] == ("Dönem", "Tümü")


# ================================================================ sunucu: öğrenci durumu
@pytest.fixture
def istemci():
    # izin kontrolü yalnızca bu test için atlanır
    from sunucu import mevcut_kullanici_id
    app.dependency_overrides[mevcut_kullanici_id] = lambda: 5
    yield TestClient(app)
    app.dependency_overrides.pop(mevcut_kullanici_id, None)


def test_sunucu_ogrenci_aktiflik_bilgisini_ozet_ve_gorevlerde_dondurur(istemci):
    bas = datetime.datetime(2026, 11, 10, 9, 0)
    db = [(1, 7, "Ayşe", "1001", bas, bas + datetime.timedelta(hours=1), True, True),
          (2, 8, "Burak", "1002", bas, None, False, False)]
    conn = MagicMock()
    c = conn.cursor.return_value
    c.fetchone.side_effect = [(1,)]                                   # izin kontrolü
    c.fetchall.return_value = db
    with patch("sunucu.psycopg2.connect", return_value=conn):
        yanit = istemci.get("/api/danisma/raporlar")
    assert yanit.status_code == 200, yanit.text
    veri = yanit.json()
    assert {o["ad_soyad"]: o["aktif_mi"] for o in veri["ogrenci_ozetleri"]} == {"Ayşe": True, "Burak": False}
    assert {o["ad_soyad"]: o["ogrenci_aktif_mi"] for o in veri["oturumlar"]} == {"Ayşe": True, "Burak": False}
    assert all(isinstance(o["aktif_mi"], bool) for o in veri["ogrenci_ozetleri"])


def test_sunucu_sorgusu_ogrenci_aktiflik_sutununu_okur_ve_pasifleri_elemez():
    kaynak = Path(sunucu.__file__).read_text(encoding="utf-8")
    govde = kaynak[kaynak.index("def danisma_raporlari("):kaynak.index("@app.post(\"/api/faaliyet-birimleri\")")]
    assert "o.aktif_mi" in govde
    assert "aktif_mi = TRUE" not in govde and "aktif_mi = true" not in govde.lower().replace("o.aktif_mi,", "")


def test_pasif_ogrenci_ekranda_kirmizi_aktif_ogrenci_normal_renkte_gorunur(qt_app):
    e = ekran_ac(qt_app)
    aktif, pasif = e.ogrenci_tablo.item(0, 2), e.ogrenci_tablo.item(1, 2)
    assert pasif.foreground().color().name().upper() == "#C0392B"
    assert aktif.foreground().color().name().upper() != "#C0392B"
