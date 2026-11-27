"""Dışa aktarma: Excel ya da PDF seçimi (kayit_yolu_sec), Excel'den PDF'e dönüşüm ve ekranların PDF yolu."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from openpyxl import Workbook
from PySide6.QtWidgets import QApplication, QDialog, QFileDialog, QLabel, QPushButton, QWidget

import client.rapor_cikti as rapor_cikti
from client.liste_excel import listeyi_excele_aktar
from client.rapor_excel import TARIH_BICIMI, TARIH_SAAT_BICIMI
from client.rapor_excel_genel import excel_olustur


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    return QApplication.instance() or QApplication([])


def _pdf_metni(yol):
    """PDF'in içindeki yazıyı döndürür (QtPdf yok: pdftotext varsa onunla, yoksa yalnızca geçerli PDF başlığı denetlenir)."""
    import shutil, subprocess
    assert Path(yol).read_bytes()[:5] == b"%PDF-"
    if shutil.which("pdftotext"):
        return subprocess.run(["pdftotext", "-layout", str(yol), "-"], capture_output=True, text=True, check=True).stdout
    return None


def _ornek_excel(yol, satir_sayisi=5):
    satirlar = [[f"Öğrenci Şğüİ {i}", datetime(2026, 11, 26, 9, 30), date(2026, 1, 2), 12.5, i] for i in range(satir_sayisi)]
    excel_olustur(yol, "Cihaz Raporu", "Açıklama", [("Dönem", "01.01.2026 - 31.01.2026")],
                  [("Toplam", satir_sayisi, "Toplam kayıt"), ("Oran", 0.256, "Yüzde", "0.0%")],
                  [("Liste", [("Ad", None), ("Zaman", TARIH_SAAT_BICIMI), ("Tarih", TARIH_BICIMI), ("Puan", "0.00"), ("Adet", None)],
                    satirlar, "Ayrıntı")])


# ---------------------------------------------------------------- tür sorusu + kayit_yolu_sec
def _secim(bicim):
    """bicim_sec'i, kullanıcı o türü seçmiş gibi yamar."""
    return patch.object(rapor_cikti, "bicim_sec", return_value=bicim)


@pytest.mark.parametrize("bicim,yol,beklenen", [
    ("pdf", "/tmp/a", ("/tmp/a.pdf", "pdf")),
    ("pdf", "/tmp/a.pdf", ("/tmp/a.pdf", "pdf")),
    ("pdf", "/tmp/a.PDF", ("/tmp/a.PDF", "pdf")),
    ("xlsx", "/tmp/a", ("/tmp/a.xlsx", "xlsx")),
    ("xlsx", "/tmp/a.xlsx", ("/tmp/a.xlsx", "xlsx")),
])
def test_dosya_penceresi_secilen_turun_uzantisini_tamamlar(bicim, yol, beklenen):
    with _secim(bicim), patch.object(QFileDialog, "getSaveFileName", return_value=(yol, "")):
        assert rapor_cikti.kayit_yolu_sec(QWidget(), "Kaydet", "rapor") == beklenen


def test_tur_sorusundan_vazgecilirse_dosya_penceresi_hic_acilmaz():
    with _secim(None), patch.object(QFileDialog, "getSaveFileName") as pencere:
        assert rapor_cikti.kayit_yolu_sec(QWidget(), "Kaydet", "rapor") == (None, None)
    assert not pencere.called


def test_dosya_penceresi_yalniz_secilen_turu_sunar_ve_varsayilan_ad_o_uzantiyla_gelir():
    for bicim, filtre, ad in (("xlsx", "(*.xlsx)", "rapor_1.xlsx"), ("pdf", "(*.pdf)", "rapor_1.pdf")):
        with _secim(bicim), patch.object(QFileDialog, "getSaveFileName", return_value=("", "")) as pencere:
            assert rapor_cikti.kayit_yolu_sec(QWidget(), "Kaydet", "rapor_1.xlsx") == (None, None)
        assert pencere.call_args.args[3].endswith(filtre) and ";;" not in pencere.call_args.args[3]     # tek tür: karışıklık yok
        assert pencere.call_args.args[2].endswith(ad)
        assert bicim_adi_beklenen(bicim) in pencere.call_args.args[1]


def bicim_adi_beklenen(bicim):
    return {"xlsx": "Excel", "pdf": "PDF"}[bicim]


def test_tur_penceresi_iki_secenek_ve_vazgec_sunar_excel_varsayilandir():
    ebeveyn = QWidget()
    pencere = rapor_cikti.BicimSecimDiyalogu(ebeveyn)
    adlar = {d.objectName(): d.text() for d in pencere.findChildren(QPushButton)}
    assert set(adlar) == {"disaAktarExcel", "disaAktarPdf", "disaAktarVazgec"}
    assert "Excel (.xlsx)" in adlar["disaAktarExcel"] and "PDF (.pdf)" in adlar["disaAktarPdf"]
    assert pencere.dugmeler["xlsx"].isDefault() and not pencere.dugmeler["pdf"].isDefault()
    assert "Hangi türde kaydetmek istersiniz?" in [e.text() for e in pencere.findChildren(QLabel)]
    pencere.close()


@pytest.mark.parametrize("dugme,beklenen", [("pdf", "pdf"), ("xlsx", "xlsx")])
def test_tur_penceresinde_tiklanan_dugme_secimi_belirler(dugme, beklenen):
    ebeveyn = QWidget()
    pencere = rapor_cikti.BicimSecimDiyalogu(ebeveyn)
    pencere.dugmeler[dugme].click()
    assert pencere.secilen == beklenen and pencere.result() == QDialog.Accepted
    pencere.close()


def test_tur_penceresi_vazgecilince_none_doner():
    ebeveyn = QWidget()
    pencere = rapor_cikti.BicimSecimDiyalogu(ebeveyn)
    pencere.findChild(QPushButton, "disaAktarVazgec").click()
    assert pencere.secilen is None and pencere.result() == QDialog.Rejected
    with patch.object(rapor_cikti.BicimSecimDiyalogu, "exec", return_value=QDialog.Rejected):
        assert rapor_cikti.bicim_sec(ebeveyn) is None
    with patch.object(rapor_cikti.BicimSecimDiyalogu, "exec", return_value=QDialog.Accepted):
        assert rapor_cikti.bicim_sec(ebeveyn) is None             # seçim yapılmadan kapanırsa da yok sayılır


# ---------------------------------------------------------------- xlsx -> pdf
def test_excel_pdfe_cevrilir_turkce_tarih_yuzde_ve_sayfa_numarasi_dogru(tmp_path):
    xlsx, pdf = str(tmp_path / "r.xlsx"), str(tmp_path / "r.pdf")
    _ornek_excel(xlsx)
    rapor_cikti.xlsx_pdfe_cevir(xlsx, pdf)
    metin = _pdf_metni(pdf)
    if metin is not None:
        for parca in ("Cihaz Raporu", "RAPOR BİLGİLERİ", "Öğrenci Şğüİ 0", "26.11.2026 09:30", "02.01.2026", "12,5", "%25,6", "Sayfa 1 / 1"):
            assert parca in metin, parca
        assert "Excel'e aktarıldığı" not in metin                           # PDF'te "Excel'e" denmez
    assert [p.name for p in tmp_path.iterdir() if p.name.startswith(".tkys_")] == []      # geçici dosya kalmaz


def test_uzun_rapor_cok_sayfali_olur_ve_satir_siniri_notu_yazilir(tmp_path):
    xlsx, pdf = str(tmp_path / "r.xlsx"), str(tmp_path / "r.pdf")
    with patch.object(rapor_cikti, "PDF_EN_FAZLA_SATIR", 40):
        _ornek_excel(xlsx, satir_sayisi=120)
        rapor_cikti.xlsx_pdfe_cevir(xlsx, pdf)
    metin = _pdf_metni(pdf)
    if metin is not None:
        assert "ilk 40 kayıt gösterilir" in metin and "Öğrenci Şğüİ 39" in metin and "Öğrenci Şğüİ 40" not in metin
        assert "Sayfa 2 /" in metin                                         # birden çok sayfa, numaralı


def test_hucre_bicimleri():
    wb = Workbook(); ws = wb.active
    ws["A1"] = 0.5; ws["A1"].number_format = "0.0%"
    ws["A2"] = 3; ws["A3"] = 2.0; ws["A4"] = 1.2345
    ws["A5"] = datetime(2026, 1, 2, 0, 0); ws["A5"].number_format = "dd.mm.yyyy"
    ws["A6"] = True; ws["A7"] = None; ws["A8"] = "=A1"
    cikti = [rapor_cikti.hucre_metni(ws[f"A{i}"]) for i in range(1, 9)]
    assert cikti == ["%50", "3", "2", "1,23", "02.01.2026", "Evet", "", "=A1"]       # metin ham yazılır (formül çalıştırılmaz)


def test_html_ozel_karakterler_kacirilir(tmp_path):
    xlsx, pdf = str(tmp_path / "r.xlsx"), str(tmp_path / "r.pdf")
    excel_olustur(xlsx, "<b>Başlık</b>", "x", [], [("a", "<script>alert(1)</script>", "")], [("S", [("K", None)], [["<i>kalın</i>"]], "")])
    rapor_cikti.xlsx_pdfe_cevir(xlsx, pdf)
    metin = _pdf_metni(pdf)
    if metin is not None:
        assert "<b>Başlık</b>" in metin and "<i>kalın</i>" in metin           # etiket olarak yorumlanmaz, düz yazı görünür


# ---------------------------------------------------------------- cikti_dosyasi
def test_cikti_dosyasi_excelde_yolu_oldugu_gibi_verir(tmp_path):
    yol = str(tmp_path / "r.xlsx")
    with rapor_cikti.cikti_dosyasi(yol, "xlsx") as hedef:
        assert hedef == yol


def test_cikti_dosyasi_pdfte_gecici_xlsx_verir_cikista_pdf_yazar_ve_gecici_siler(tmp_path):
    pdf = str(tmp_path / "r.pdf")
    with rapor_cikti.cikti_dosyasi(pdf, "pdf", "Başlık") as gecici:
        assert gecici.endswith(".xlsx") and gecici != pdf
        _ornek_excel(gecici)
    assert Path(pdf).read_bytes()[:5] == b"%PDF-"
    assert [p.name for p in tmp_path.iterdir()] == ["r.pdf"]


def test_pdf_yazilamazsa_hedef_bozulmaz_gecici_dosyalar_silinir(tmp_path):
    pdf = tmp_path / "r.pdf"
    pdf.write_bytes(b"ESKI")
    with patch.object(rapor_cikti, "_belgeyi_ciz", side_effect=RuntimeError("yazılamadı")):
        with pytest.raises(RuntimeError):
            with rapor_cikti.cikti_dosyasi(str(pdf), "pdf") as gecici:
                _ornek_excel(gecici)
    assert pdf.read_bytes() == b"ESKI" and [p.name for p in tmp_path.iterdir()] == ["r.pdf"]


# ---------------------------------------------------------------- liste dışa aktarımı
def test_liste_pdf_olarak_kaydedilir_ve_denetime_pdf_yazilir(tmp_path):
    hedef = str(tmp_path / "liste.pdf")
    gonderilen = []

    def istek(yontem, url, **kw):
        gonderilen.append(kw["json"])
        yanit = MagicMock(); yanit.status_code = 200
        return yanit
    with _secim("pdf"), patch.object(QFileDialog, "getSaveFileName", return_value=(hedef, "")), \
            patch("client.liste_excel.QMessageBox.information") as bilgi, \
            patch("client.liste_excel.oturum_kontrollu_istek", istek), patch("client.liste_excel.oturum_hatasi_mi", return_value=False):
        yol = listeyi_excele_aktar(QWidget(), "Öğrenciler", "ogrenciler", [("Ad", None)], [["Ayşe"], ["Çağrı"]],
                                   kayit={"api_url": "http://x", "token": "T", "liste": "OGRENCI"})
    assert yol == hedef and Path(hedef).read_bytes()[:5] == b"%PDF-"
    assert gonderilen == [{"liste": "OGRENCI", "satir_sayisi": 2, "bicim": "PDF"}]
    assert "PDF olarak kaydedildi" in bilgi.call_args.args[2]
    metin = _pdf_metni(hedef)
    if metin is not None:
        assert "Ayşe" in metin and "Çağrı" in metin


def test_liste_excel_denetim_istegi_eski_bicimde_kalir(tmp_path):
    hedef = str(tmp_path / "liste.xlsx")
    gonderilen = []

    def istek(yontem, url, **kw):
        gonderilen.append(kw["json"])
        yanit = MagicMock(); yanit.status_code = 200
        return yanit
    with _secim("xlsx"), patch.object(QFileDialog, "getSaveFileName", return_value=(hedef, "")), patch("client.liste_excel.QMessageBox.information"), \
            patch("client.liste_excel.oturum_kontrollu_istek", istek), patch("client.liste_excel.oturum_hatasi_mi", return_value=False):
        listeyi_excele_aktar(QWidget(), "Öğrenciler", "ogrenciler", [("Ad", None)], [["Ayşe"]],
                             kayit={"api_url": "http://x", "token": "T", "liste": "OGRENCI"})
    assert gonderilen == [{"liste": "OGRENCI", "satir_sayisi": 1}]            # Excel'de istek değişmez (eski sunucuyla uyumlu)


# ---------------------------------------------------------------- sunucu / denetim metni
def test_aktarim_modeli_bicimi_kabul_eder_eskisiz_excel_sayar():
    import server.sunucu as sunucu
    from pydantic import ValidationError
    assert sunucu.ListeAktarimModeli(liste="OGRENCI", satir_sayisi=1).bicim == "EXCEL"
    assert sunucu.ListeAktarimModeli(liste="OGRENCI", satir_sayisi=1, bicim="PDF").bicim == "PDF"
    with pytest.raises(ValidationError):
        sunucu.ListeAktarimModeli(liste="OGRENCI", satir_sayisi=1, bicim="DOCX")


# ---------------------------------------------------------------- görsel doğrulamada bulunan kusurlar
def test_kisa_sutunlar_icerigi_sigacak_kadar_genis_kalir():
    """Görsel doğrulamada 'No' ve 'Öğrenci No' sütunları dar kalıp rakamları satır ortasından bölüyordu."""
    satirlar = [[("No", False, True, None, None), ("Açıklama", False, True, None, None)],
                [("12", True, False, None, None), ("Çok uzun bir açıklama metni " * 6, False, False, None, None)],
                [("202100001", False, False, None, None), ("Kısa", False, False, None, None)]]
    no, aciklama = rapor_cikti._sutun_agirliklari(satirlar, 2)
    assert no >= len("202100001") * 2                                          # en uzun değer (9 hane) sığacak pay
    assert aciklama > no                                                       # uzun metin sütunu yine de daha fazla pay alır
    uzun_1 = rapor_cikti._sutun_agirliklari([[("x" * 60, False, False, None, None)]], 1)[0]
    uzun_2 = rapor_cikti._sutun_agirliklari([[("x" * 120, False, False, None, None)]], 1)[0]
    assert uzun_1 < uzun_2 < uzun_1 * 2                                       # uzun metinde pay orantısız büyümez


def test_serbest_duzenli_sayfa_baslik_satiri_gibi_boyanmaz_hucre_bicimleri_korunur():
    """Cihaz Raporu'nun 'Durum Raporu' sayfası gibi serbest düzenli sayfalarda ilk satır başlık değildir; Excel'deki dolgu/kalın korunur."""
    from openpyxl.styles import Font, PatternFill
    wb = Workbook(); ws = wb.active; ws.title = "Durum Raporu"
    ws["A1"] = "DURUM RAPORU — Kategorilere göre kayıt"                           # tek hücreli ilk satır: başlık değil
    ws["A2"] = "BAKIM — Devam eden"; ws["A2"].fill = PatternFill("solid", fgColor="FF16294B"); ws["A2"].font = Font(bold=True, color="FFFFFFFF")
    ws["B2"] = "x"; ws["A3"] = "Cihaz"; ws["B3"] = "Tarih"; ws["A4"] = "EEG"; ws["B4"] = "26.11.2026"
    kod = rapor_cikti._tablo_html("Durum Raporu", ws)
    assert "<thead>" not in kod                                                # sahte mavi başlık satırı yok
    assert "bgcolor='#16294B'" in kod and "<b>BAKIM — Devam eden</b>" in kod and "<font color='#FFFFFF'>" in kod


def test_duzenli_tablo_ilk_satiri_basliktir_ve_cok_sutunda_yazi_kuculur():
    wb = Workbook(); ws = wb.active; ws.title = "Liste"
    for s in range(1, 13):
        ws.cell(row=1, column=s, value=f"Sütun {s}")
        ws.cell(row=2, column=s, value=s)
    kod = rapor_cikti._tablo_html("Liste", ws)
    assert kod.count("<th ") == 12 and "<thead>" in kod and "font-size:7pt" in kod         # >10 sütun: bir punto küçük
    ws2 = Workbook().active
    for s in range(1, 4):
        ws2.cell(row=1, column=s, value=f"S{s}"); ws2.cell(row=2, column=s, value=s)
    assert "font-size:7pt" not in rapor_cikti._tablo_html("Az", ws2)


def test_denetim_ayrintisinda_bicim_alani_turkce_etiketle_gorunur():
    import client.audit_kayitlari_ekrani as modul
    assert modul.alan_adi("bicim") == "Biçim"
