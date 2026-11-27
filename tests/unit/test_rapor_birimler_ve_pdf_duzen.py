"""Raporlarda birimli sayılar (13 cihaz, 14.101,50 ₺, 6,1 gün), Excel yazdırma düzeni ve PDF yerleşimi (harf aralığı, yetim başlık)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from datetime import date, datetime
from pathlib import Path

import pytest
from openpyxl import Workbook, load_workbook
from PySide6.QtGui import QFont, QTextDocument, QTextTable
from PySide6.QtCore import QSizeF
from PySide6.QtWidgets import QApplication

import client.rapor_cikti as rapor_cikti
from client.rapor_excel import birim_bicimi, excel_dosyasi_olustur, ozet_bicimi
from client.rapor_excel_genel import excel_olustur


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    return QApplication.instance() or QApplication([])


def _satir(sayfa, etiket):
    for satir in sayfa.iter_rows(min_col=1, max_col=3):
        if satir[0].value == etiket:
            return satir
    raise AssertionError(f"'{etiket}' satırı yok")


# ---------------------------------------------------------------- PDF: Excel sayı biçimi (birim, binlik ayraç, ondalık)
@pytest.mark.parametrize("deger,bicim,beklenen", [
    (50796.95, '#,##0.00 "₺"', "50.796,95 ₺"),
    (14101.5, '#,##0.00 "₺"', "14.101,50 ₺"),
    (152, '0 "gün"', "152 gün"),
    (6.1176, '0.0 "gün"', "6,1 gün"),
    (13, '#,##0 "cihaz"', "13 cihaz"),
    (1250, '#,##0 "kayıt"', "1.250 kayıt"),
    (97.333, '0.00 "saat"', "97,33 saat"),
    (0.2557, "0.0%", "%25,6"),
    (0.5, "0%", "%50"),
    (3, "General", "3"),
    (2.5, "General", "2,5"),
    (1.2345, "General", "1,23"),
    (1200, '"₺" #,##0', "₺ 1.200"),
    (0, '#,##0 "cihaz"', "0 cihaz"),
    (-5.5, '0.0 "gün"', "-5,5 gün"),
    (12.5, "#,##0.0#", "12,5"),
    (12, "#,##0.0#", "12,0"),
    (True, "General", "Evet"),
])
def test_sayi_metni_excel_bicimini_turkce_uygular(deger, bicim, beklenen):
    assert rapor_cikti._sayi_metni(deger, bicim) == beklenen


def test_pdf_hucre_metni_birimli_sayiyi_ve_tarihi_yazar():
    ws = Workbook().active
    ws["A1"] = 3174.81; ws["A1"].number_format = '#,##0.00 "₺"'
    ws["A2"] = datetime(2026, 11, 27, 11, 43); ws["A2"].number_format = "dd.mm.yyyy hh:mm"
    ws["A3"] = date(2026, 1, 2)
    assert [rapor_cikti.hucre_metni(ws[f"A{i}"]) for i in (1, 2, 3)] == ["3.174,81 ₺", "27.11.2026 11:43", "02.01.2026"]


# ---------------------------------------------------------------- Excel: özet satırlarında birim
def test_birim_bicimi_ve_ozet_bicimi():
    assert birim_bicimi("cihaz", 13) == '#,##0 "cihaz"'
    assert birim_bicimi("saat", 2.5) == '#,##0.00 "saat"'
    assert birim_bicimi("saat", 2.0) == '#,##0 "saat"'                         # tam sayı değerli ondalık sayıda ondalık gösterilmez
    tablo = {"Rapordaki cihazlar": "cihaz"}
    assert ozet_bicimi(tablo, "Rapordaki cihazlar", 13) == '#,##0 "cihaz"'
    assert ozet_bicimi(tablo, "Rapordaki cihazlar", 13, "0.0%") == "0.0%"        # açıkça verilen biçim önceliklidir
    assert ozet_bicimi(tablo, "Rapordaki cihazlar", "metin") is None            # metin değerde biçim yok
    assert ozet_bicimi(tablo, "Rapordaki cihazlar", True) is None
    assert ozet_bicimi(tablo, "Bilinmeyen satır", 5) is None
    assert ozet_bicimi(None, "x", 5) is None


def test_cihaz_raporu_ozetinde_sayilar_birimli_ve_sayi_olarak_kalir(tmp_path):
    veri = {"ozet": {"bakim_sayisi": 2, "toplam_bakim_maliyeti": 14101.5, "kalibrasyon_sayisi": 0, "ariza_sayisi": 1},
            "cihazlar": [{"cihaz_id": 1, "envanter_kodu": "C-1", "cihaz_adi": "EEG", "marka_model": None, "durum": "Bakimda",
                          "sonraki_bakim_tarihi": None, "son_kalibrasyon": None}],
            "bakimlar": [], "kalibrasyonlar": [], "arizalar": []}
    yol = str(tmp_path / "c.xlsx")
    excel_dosyasi_olustur(veri, [("Dönem", "Tümü"), ("Cihaz", "Tüm Cihazlar")], yol, bugun=date(2026, 11, 27))
    ozet = load_workbook(yol)["Özet"]
    for etiket, birim in (("Rapordaki cihazlar", "cihaz"), ("Bakım kaydı (toplam)", "kayıt"), ("Devam eden bakım", "bakım"),
                          ("Kalibrasyon kaydı yok", "cihaz"), ("Arıza kaydı (toplam)", "kayıt"), ("Bakımda", "cihaz")):
        hucre = _satir(ozet, etiket)[1]
        assert isinstance(hucre.value, int) and f'"{birim}"' in hucre.number_format, (etiket, hucre.number_format)
    assert "₺" in _satir(ozet, "Toplam bakım maliyeti")[1].number_format          # para birimi korunur


def test_bos_liste_aciklamasinda_yok_yazilmaz_dolu_listede_kodlar_yazilir(tmp_path):
    veri = {"ozet": {}, "cihazlar": [{"cihaz_id": 1, "envanter_kodu": "C-1", "cihaz_adi": "EEG", "marka_model": None, "durum": "Bakimda",
                                      "sonraki_bakim_tarihi": None, "son_kalibrasyon": None}],
            "bakimlar": [{"cihaz_id": 1, "cihaz": "C-1 - EEG", "bakim_tarihi": "2026-11-26", "bakim_baslangic_tarihi": "2026-11-26",
                          "bakim_bitis_tarihi": "2026-11-30", "bakim_yapan_kisi": "Ali", "yapilan_islem": "Filtre", "maliyet": 100.0,
                          "sonraki_bakim_tarihi": None}],
            "kalibrasyonlar": [], "arizalar": []}
    yol = str(tmp_path / "c.xlsx")
    excel_dosyasi_olustur(veri, [], yol, bugun=date(2026, 11, 27))
    ozet = load_workbook(yol)["Özet"]
    assert _satir(ozet, "Planlanmış bakım")[2].value == "Başlangıç tarihi henüz gelmemiş bakımlar."     # 0 zaten değerde; 'Yok' tekrarı yok
    assert _satir(ozet, "Devam eden bakım")[2].value == "Şu an süren bakımlar: C-1 - EEG"
    assert "Yok" not in " ".join(str(h.value) for satir in ozet.iter_rows(min_col=3, max_col=3) for h in satir if h.value and "bakım" in str(h.value))
    assert _satir(ozet, "Rapor Tarihi")[2].value == "Raporun oluşturulduğu an."                         # Excel'e özgü ifade yok


def test_genel_rapor_ozetinde_birimler_baslik_ve_etikete_gore_gelir(tmp_path):
    yol = str(tmp_path / "g.xlsx")
    excel_olustur(yol, "CİHAZ REZERVASYON RAPORU", "açıklama", [("Dönem", "x")],
                  [("Rezervasyon sayısı", 15, "a"), ("Toplam kullanım", 30.5, "b"), ("Kullanılan cihaz", 9, "c"), ("Başka", 7, "d")],
                  [("Cihaz Bazlı", [("Cihaz", None)], [["C-1"]], "r")])
    ozet = load_workbook(yol)["Özet"]
    assert _satir(ozet, "Rezervasyon sayısı")[1].number_format == '#,##0 "rezervasyon"'
    assert _satir(ozet, "Toplam kullanım")[1].number_format == '#,##0.00 "saat"'
    assert _satir(ozet, "Kullanılan cihaz")[1].number_format == '#,##0 "cihaz"'
    assert _satir(ozet, "Başka")[1].number_format == "General"                                     # tabloda olmayan etiket: değişmez
    excel_olustur(yol, "BAŞKA BİR RAPOR", "a", [], [("Aktarılan Kayıt", 4, "x")], [("Liste", [("Ad", None)], [["a"]], "r")])
    assert _satir(load_workbook(yol)["Özet"], "Aktarılan Kayıt")[1].number_format == '#,##0 "kayıt"'  # liste sayfaları


# ---------------------------------------------------------------- Excel: yazdırma düzeni
def test_excel_yazdirma_duzeni_a4_yatay_basliklari_tekrarlar_sayfa_no_yazar(tmp_path):
    yol = str(tmp_path / "y.xlsx")
    excel_olustur(yol, "RAPOR", "a", [], [("Aktarılan Kayıt", 2, "x")], [("Liste", [("Ad", None), ("Puan", None)], [["a", 1], ["b", 2]], "r")])
    kitap = load_workbook(yol)
    for sayfa in kitap.worksheets:
        assert sayfa.page_setup.orientation == "landscape" and sayfa.page_setup.paperSize == 9
        assert sayfa.page_setup.fitToWidth == 1 and sayfa.page_setup.fitToHeight == 0 and sayfa.sheet_properties.pageSetUpPr.fitToPage
        assert "Sayfa &P / &N" in sayfa.oddFooter.right.text and sayfa.oddFooter.left.text == "TKYS"
    assert kitap["Liste"].print_title_rows == "$1:$1"                                  # tablo sayfasında sütun başlığı her sayfada tekrarlanır
    assert kitap["Özet"].print_title_rows is None


# ---------------------------------------------------------------- PDF: yerleşim
def test_pdf_yuksek_cozunurlukte_ve_hintingsiz_yazilir():
    assert rapor_cikti.PDF_COZUNURLUK >= 300                                          # düşük çözünürlükte harf aralıkları eşitsiz kalıyordu
    assert rapor_cikti._yazi_tipi(8).hintingPreference() == QFont.PreferNoHinting
    assert rapor_cikti._px(1) == 3 and rapor_cikti._px(0.1) == 1                      # piksel ölçüleri çözünürlükle ölçeklenir, en az 1


def test_pdf_font_boyutu_stil_sayfasiyla_ezilmez():
    """Stil sayfasındaki body/th font-size, Qt'de tablo hücrelerindeki satır içi boyutların önüne geçiyordu (başlık küçük çıkıyordu)."""
    assert "font-size" not in rapor_cikti._STIL


def _belge(html):
    belge = QTextDocument()
    belge.setDefaultFont(rapor_cikti._yazi_tipi(8.5))
    belge.setPageSize(QSizeF(3000, rapor_cikti._BUYUK_SAYFA))
    belge.setHtml(html)
    return belge


def _uzun_tablo_html(satir_sayisi, baslik="Bölüm"):
    satirlar = "".join(f"<tr><td>kayıt {i}</td><td>{'uzun açıklama metni ' * (1 + i % 5)}</td></tr>" for i in range(satir_sayisi))
    return (f"<html><body><p>giriş</p>{rapor_cikti._bolum_basligi(baslik)}<table width='100%' cellpadding='6'><thead><tr><th>Ad</th><th>Açıklama</th></tr></thead>"
            f"{satirlar}</table><p>son</p></body></html>")


def test_sayfa_plani_hicbir_tablo_satiri_ikiye_bolunmez_ve_baslik_tekrarlanir():
    belge = _belge(_uzun_tablo_html(80))
    yukseklik = 900
    plan = rapor_cikti._sayfa_plani(belge, yukseklik)
    parcalar, basliklar = rapor_cikti._parcalar(belge)
    assert len(plan) > 2
    for p in parcalar:                                                                  # her parça tek bir sayfaya tamamen sığar
        sayfalar = [k for k, (y0, y1, _t) in enumerate(plan) if y0 - 0.5 <= p.ust and p.alt <= y1 + 0.5]
        assert len(sayfalar) >= 1, (p.ust, p.alt)
    for k, (y0, y1, tekrar) in enumerate(plan):
        yuk = (y1 - y0) + ((tekrar[1] - tekrar[0]) if tekrar else 0)
        assert yuk <= yukseklik + 1                                                     # tekrarlanan başlık dahil sayfaya sığar
        if k:
            assert tekrar is not None                                                   # tablo gövdesinden başlayan her sayfada sütun başlığı yinelenir
    assert plan[0][2] is None


def test_sayfa_plani_bolum_basligi_altindaki_icerikten_ayrilmaz():
    """Beklenen zincir uygulamanın kendi işaretlerinden değil, belgenin yapısından (başlık tablosu, thead) çıkarılır."""
    yukseklik = 700
    for dolgu in range(1, 70):                                                          # başlığı sayfanın farklı yerlerine düşüren dolgular
        html = ("<html><body>" + "".join(f"<p>satır {i}</p>" for i in range(dolgu)) + rapor_cikti._bolum_basligi("Bölüm A")
                + "<table width='100%' cellpadding='6'><thead><tr><th>Ad</th></tr></thead>"
                + "".join(f"<tr><td>kayıt {i}</td></tr>" for i in range(25)) + "</table></body></html>")
        belge = _belge(html)
        plan = rapor_cikti._sayfa_plani(belge, yukseklik)
        parcalar, _b = rapor_cikti._parcalar(belge)
        tablolar = [t for t in belge.rootFrame().childFrames() if isinstance(t, QTextTable)]
        baslik_tablolari = {i for i, t in enumerate(tablolar) if t.format().cellPadding() == rapor_cikti.BASLIK_DOLGUSU}
        gorev_gruplari = {i: t.format().headerRowCount() for i, t in enumerate(tablolar)}
        for k, parca in enumerate(parcalar[:-1]):
            zincir = parca.tablo in baslik_tablolari or (parca.tablo is not None and parca.satir < gorev_gruplari[parca.tablo])
            if zincir:                                                                  # bölüm başlığı ve sütun başlığı, sonraki parçayla aynı sayfada
                ayni = any(y0 - 0.5 <= parca.ust and parcalar[k + 1].alt <= y1 + 0.5 for y0, y1, _t in plan)
                assert ayni, (dolgu, k)


def test_sayfa_plani_sayfadan_yuksek_tek_parca_dilimlenir_ve_icerik_kaybolmaz():
    belge = _belge("<html><body><table width='100%'><tr><td>" + "<br>".join(f"satır {i}" for i in range(200)) + "</td></tr></table></body></html>")
    plan = rapor_cikti._sayfa_plani(belge, 500)
    assert len(plan) >= 3
    assert plan[0][0] <= 10 and plan[-1][1] >= belge.size().height() - 30                # baştan sona tüm içerik dilimlerde


def test_tablo_basligi_sayisal_sutunda_sagda_metin_sutununda_solda():
    wb = Workbook(); ws = wb.active; ws.title = "Liste"
    ws.append(["Ad", "Puan"])
    for i in range(5):
        ws.append([f"k{i}", i * 10])
    kod = rapor_cikti._tablo_html("Liste", ws)
    assert "<th width=" in kod and "align='left'" in kod.split("</th>")[0] and "align='right'" in kod.split("</th>")[1]


def test_pdf_ozeti_birimleri_ve_temiz_basliklari_gosterir(tmp_path):
    import shutil, subprocess
    xlsx, pdf = str(tmp_path / "r.xlsx"), str(tmp_path / "r.pdf")
    excel_olustur(xlsx, "CİHAZ REZERVASYON RAPORU", "açıklama", [("Dönem", "Tümü")],
                  [("Rezervasyon sayısı", 15, "Dönemle kesişen rezervasyonlar."), ("Toplam kullanım", 30.5, "Toplam süre.")],
                  [("Cihaz Bazlı", [("Cihaz", None), ("Maliyet", '#,##0.00 "₺"')], [["C-1", 1234.5]], "rehber"),
                   ("Detay", [("Cihaz", None)], [["C-1"]], "ikinci sayfa")])
    rapor_cikti.xlsx_pdfe_cevir(xlsx, pdf)
    assert Path(pdf).read_bytes()[:5] == b"%PDF-"
    if shutil.which("pdftotext"):
        metin = subprocess.run(["pdftotext", "-layout", pdf, "-"], capture_output=True, text=True, check=True).stdout
        for parca in ("15 rezervasyon", "30,50 saat", "1.234,50 ₺", "RAPOR İÇERİĞİ", "Raporun oluşturulduğu an."):
            assert parca in metin, parca
        assert "SAYFA REHBERİ" not in metin and "Excel'e" not in metin


def test_tek_sayfalik_raporda_tek_maddelik_icindekiler_yazilmaz(tmp_path):
    import shutil, subprocess
    xlsx, pdf = str(tmp_path / "l.xlsx"), str(tmp_path / "l.pdf")
    excel_olustur(xlsx, "Cihaz Rezervasyonları", "liste", [("Arama", "Yok")], [("Aktarılan Kayıt", 1, "x")], [("Liste", [("Ad", None)], [["a"]], "r")])
    rapor_cikti.xlsx_pdfe_cevir(xlsx, pdf)
    if shutil.which("pdftotext"):
        metin = subprocess.run(["pdftotext", "-layout", pdf, "-"], capture_output=True, text=True, check=True).stdout
        assert "RAPOR İÇERİĞİ" not in metin and "1 kayıt" in metin


def test_serbest_duzenli_sayfada_tek_hucreli_satir_tum_genislige_yayilir():
    wb = Workbook(); ws = wb.active; ws.title = "Durum Raporu"
    ws["A1"] = "DURUM RAPORU"
    ws["A2"] = "Cihaz"; ws["B2"] = "Tarih"; ws["C2"] = "Süre"
    ws["A3"] = "EEG"; ws["B3"] = "26.11.2026"; ws["C3"] = 4
    ws["A4"] = "Uzun bir açıklama satırı yalnızca ilk hücrede"
    kod = rapor_cikti._tablo_html("Durum Raporu", ws)
    assert kod.count("colspan='3'") == 2 and "<thead>" not in kod                      # başlık satırı ve açıklama satırı yayılır
    assert "font-size:1pt" in kod                                                       # sütun genişliklerini veren görünmez ilk satır


def test_sayfa_plani_serbest_duzenli_sayfada_bant_satiri_altindaki_satirdan_ayrilmaz():
    """Cihaz raporunun 'Durum Raporu' sayfasındaki koyu bant satırı (örn. 'ARIZA — Çözümü süren') sayfa dibinde tek kalmaz."""
    yukseklik = 700
    for dolgu in range(1, 40):
        satirlar = "".join(f"<tr><td>kayıt {i}</td><td>x</td></tr>" for i in range(12))
        html = ("<html><body><table width='100%' cellpadding='6'>"
                + "".join(f"<tr><td>satır {i}</td><td>y</td></tr>" for i in range(dolgu))
                + f"<tr><td colspan='2' bgcolor='{rapor_cikti.LACIVERT}'>BANT</td></tr>{satirlar}</table></body></html>")
        belge = _belge(html)
        plan = rapor_cikti._sayfa_plani(belge, yukseklik)
        parcalar, _b = rapor_cikti._parcalar(belge)
        bant = [k for k, p in enumerate(parcalar) if k == dolgu]                          # bant satırı tablodaki (dolgu)'ncu satırdır
        assert bant, dolgu
        k = bant[0]
        assert any(y0 - 0.5 <= parcalar[k].ust and parcalar[k + 1].alt <= y1 + 0.5 for y0, y1, _t in plan), dolgu


def test_liste_aramasi_bos_ise_yok_degil_uygulanmadi_yazilir(tmp_path):
    yol = str(tmp_path / "a.xlsx")
    excel_olustur(yol, "Liste", "a", [("Arama", "Yok")], [("Aktarılan Kayıt", 1, "x")], [("Liste", [("Ad", None)], [["a"]], "r")])
    satir = _satir(load_workbook(yol)["Özet"], "Arama")
    assert satir[1].value == "Uygulanmadı" and "tüm kayıtlar listelendi" in satir[2].value
    excel_olustur(yol, "Liste", "a", [("Arama", "eeg")], [("Aktarılan Kayıt", 1, "x")], [("Liste", [("Ad", None)], [["a"]], "r")])
    satir = _satir(load_workbook(yol)["Özet"], "Arama")
    assert satir[1].value == "eeg" and "bu aramaya uyan" in satir[2].value
