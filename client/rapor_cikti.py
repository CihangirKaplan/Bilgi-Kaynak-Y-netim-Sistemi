"""TKYS - Rapor/liste dışa aktarımında ortak "Excel mi, PDF mi?" katmanı.

Tüm "Dışa Aktar" düğmeleri aynı iki adımı izler: önce "Hangi türde kaydetmek istersiniz?" penceresi (Excel ya da PDF), sonra seçilen
türe göre dosya adı/konumu penceresi. Rapor her zaman önce Excel çalışma kitabı olarak üretilir; PDF seçildiyse aynı çalışma kitabı
(Özet + tablo sayfaları) A4 yatay PDF'e dönüştürülür. Böylece her rapor için ayrı bir PDF yazmaya gerek kalmadan iki çıktı da aynı
içeriği taşır. Ek bağımlılık yoktur (Qt'nin QPdfWriter'ı kullanılır).

Kullanım (bir dışa aktarım yolunda):

    yol, bicim = kayit_yolu_sec(self, "Raporu Kaydet", "cihaz_raporu_20260101_1200")
    if not yol: return
    with cikti_dosyasi(yol, bicim) as xlsx_yolu:
        excel_yazan_fonksiyon(xlsx_yolu)          # bicim "pdf" ise xlsx geçici dosyadır; çıkışta PDF'e çevrilir
"""
import html
import os
import tempfile
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path

from PySide6.QtCore import QMarginsF, QRectF, QSizeF, Qt
from PySide6.QtGui import QColor, QFont, QPageLayout, QPageSize, QPainter, QPdfWriter, QTextDocument
from PySide6.QtWidgets import QDialog, QFileDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

XLSX_FILTRESI = "Excel Çalışma Kitabı (*.xlsx)"
PDF_FILTRESI = "PDF Belgesi (*.pdf)"
PDF_EN_FAZLA_SATIR = 3000        # PDF'te her tablo sayfasından en çok bu kadar satır yazılır (devamı için Excel önerilir)
PDF_YAZI_TIPI = "Arial"

BICIM_ADLARI = {"xlsx": "Excel", "pdf": "PDF"}


def bicim_adi(bicim):
    return BICIM_ADLARI.get(bicim, "Excel")


class BicimSecimDiyalogu(QDialog):
    """"Hangi türde kaydetmek istersiniz?" penceresi: iki büyük seçenek (Excel / PDF) ve Vazgeç. secilen: "xlsx" | "pdf" | None."""

    SECENEKLER = (
        ("xlsx", "Excel (.xlsx)", "Düzenlemek ve hesaplamak için", "disaAktarExcel"),
        ("pdf", "PDF (.pdf)", "Yazdırmak ve paylaşmak için", "disaAktarPdf"),
    )

    def __init__(self, pencere=None, baslik="Dışa Aktar"):
        super().__init__(pencere)
        self.setWindowTitle(baslik)
        self.setModal(True)
        self.secilen = None
        ana = QVBoxLayout(self)
        ana.setContentsMargins(22, 20, 22, 18)
        ana.setSpacing(14)
        soru = QLabel("Hangi türde kaydetmek istersiniz?")
        soru.setObjectName("disaAktarSoru")
        soru.setStyleSheet("font-size: 15px; font-weight: 800; color: #0A1F5C;")
        ana.addWidget(soru)
        secenekler = QHBoxLayout()
        secenekler.setSpacing(12)
        self.dugmeler = {}
        for bicim, ad, aciklama, nesne_adi in self.SECENEKLER:
            dugme = QPushButton(f"{ad}\n{aciklama}")
            dugme.setObjectName(nesne_adi)
            dugme.setProperty("bicim", bicim)
            dugme.setCursor(Qt.PointingHandCursor)
            dugme.setMinimumSize(240, 80)
            dugme.setStyleSheet(
                "QPushButton { background: #F3F7FF; color: #0F2552; border: 1px solid #C7D6F2; border-radius: 12px; "
                "font-size: 13px; font-weight: 700; padding: 10px 14px; } "
                "QPushButton:hover { background: #E3EDFF; border-color: #1D4ED8; } "
                "QPushButton:focus { border: 2px solid #1D4ED8; }"
            )
            dugme.clicked.connect(self._secildi)
            secenekler.addWidget(dugme)
            self.dugmeler[bicim] = dugme
        ana.addLayout(secenekler)
        self.dugmeler["xlsx"].setDefault(True)
        self.dugmeler["xlsx"].setFocus()
        alt = QHBoxLayout()
        alt.addStretch(1)
        vazgec = QPushButton("Vazgeç")
        vazgec.setObjectName("disaAktarVazgec")
        vazgec.setCursor(Qt.PointingHandCursor)
        vazgec.clicked.connect(self.reject)
        alt.addWidget(vazgec)
        ana.addLayout(alt)

    def _secildi(self):
        dugme = self.sender()
        self.secilen = dugme.property("bicim") if dugme is not None else None
        self.accept()


def bicim_sec(pencere, baslik="Dışa Aktar"):
    """Kullanıcıya Excel mi PDF mi sorar. "xlsx", "pdf" ya da (vazgeçildiyse) None döndürür."""
    diyalog = BicimSecimDiyalogu(pencere, baslik)
    if diyalog.exec() != QDialog.Accepted:
        return None
    return diyalog.secilen


def kayit_yolu_sec(pencere, baslik, varsayilan_ad):
    """Önce türü (Excel/PDF) sorar, sonra o türün dosya adı/konumunu seçtirir. (yol, bicim) döndürür; vazgeçilirse (None, None).

    varsayilan_ad uzantısız ya da .xlsx/.pdf uzantılı verilebilir. Seçilen türün uzantısı yoksa tamamlanır.
    """
    bicim = bicim_sec(pencere, baslik)
    if bicim is None:
        return None, None
    ad = Path(varsayilan_ad)
    if ad.suffix.lower() in (".xlsx", ".pdf"):
        ad = ad.with_suffix("")
    uzanti = f".{bicim}"
    yol, _ = QFileDialog.getSaveFileName(
        pencere, f"{baslik} - {bicim_adi(bicim)}", f"{ad}{uzanti}", XLSX_FILTRESI if bicim == "xlsx" else PDF_FILTRESI,
    )
    if not yol:
        return None, None
    if not yol.lower().endswith(uzanti):
        yol += uzanti
    return yol, bicim


@contextmanager
def cikti_dosyasi(yol, bicim, baslik=None):
    """Excel yazan kodun yazacağı .xlsx yolunu verir. bicim "xlsx" ise yolun kendisi; "pdf" ise geçici bir dosya.

    PDF'te blok hatasız biterse çalışma kitabı PDF'e çevrilip hedefe taşınır; geçici dosya her durumda silinir.
    """
    if bicim != "pdf":
        yield yol
        return
    klasor = Path(yol).parent
    fd, gecici_xlsx = tempfile.mkstemp(prefix=".tkys_rapor_", suffix=".xlsx", dir=str(klasor))
    os.close(fd)
    try:
        yield gecici_xlsx
        xlsx_pdfe_cevir(gecici_xlsx, yol, baslik)
    finally:
        try:
            os.remove(gecici_xlsx)
        except OSError:
            pass


# ------------------------------------------------------------------ xlsx → pdf
def _sayi_metni(deger, bicim):
    if isinstance(deger, bool):
        return "Evet" if deger else "Hayır"
    if isinstance(deger, int):
        return str(deger)
    if "%" in bicim:
        metin = f"{deger * 100:.1f}".rstrip("0").rstrip(".")
        return f"%{metin.replace('.', ',')}"
    ondalik = 2 if "0.00" in bicim or abs(deger - round(deger)) > 1e-9 else 0
    metin = f"{deger:.{ondalik}f}"
    if "." in metin:
        metin = metin.rstrip("0").rstrip(".")
    return metin.replace(".", ",")


def hucre_metni(hucre):
    """Hücrenin PDF'te görünecek yazısı (tarihler gg.aa.yyyy [ss:dd], sayılar Türkçe ondalık)."""
    deger = hucre.value
    if deger is None:
        return ""
    bicim = hucre.number_format or ""
    if isinstance(deger, datetime):
        return deger.strftime("%d.%m.%Y %H:%M") if "h" in bicim.lower() else deger.strftime("%d.%m.%Y")
    if isinstance(deger, date):
        return deger.strftime("%d.%m.%Y")
    if isinstance(deger, (int, float)):
        return _sayi_metni(deger, bicim)
    return str(deger)


def _satir_verileri(sayfa, en_fazla=None):
    """Boş olmayan satırlar: [(metin, sayisal_mi, kalin_mi, dolgulu_mu)] listesi; en_fazla verilirse ilk satır + en_fazla veri satırı."""
    satirlar = []
    for numara, satir in enumerate(sayfa.iter_rows(), start=1):
        if all(h.value is None for h in satir):
            continue
        satirlar.append([
            (hucre_metni(h), isinstance(h.value, (int, float)) and not isinstance(h.value, bool),
             bool(h.font and h.font.b), bool(h.fill and h.fill.fill_type == "solid"))
            for h in satir
        ])
    toplam = len(satirlar)
    if en_fazla is not None and toplam - 1 > en_fazla:
        satirlar = satirlar[: en_fazla + 1]
    return satirlar, toplam


def _ozet_html(sayfa):
    """Özet sayfası: başlık, alt başlık, bölüm başlıkları ve (ad, değer, açıklama) satırları."""
    satirlar, _ = _satir_verileri(sayfa)
    govde = []
    ilk_satir = True
    for satir in satirlar:
        metinler = [m[0] for m in satir]
        dolu = [m for m in metinler if m != ""]
        if ilk_satir:
            govde.append(f"<h1>{html.escape(metinler[0])}</h1>")
            ilk_satir = False
            continue
        if len(dolu) == 1 and satir[0][3]:                      # tek hücreli, dolgulu satır = bölüm başlığı
            govde.append(f"<h2>{html.escape(dolu[0])}</h2>")
        elif len(dolu) == 1 and not satir[0][2]:                # tek hücreli düz satır = açıklama
            govde.append(f"<p class='alt'>{html.escape(dolu[0])}</p>")
        else:
            ad, deger, aciklama = (metinler + ["", "", ""])[:3]
            aciklama = aciklama.replace("Excel'e aktarıldığı", "dışa aktarıldığı")
            govde.append(
                "<table width='100%' cellspacing='0' cellpadding='3'><tr>"
                f"<td width='24%'><b>{html.escape(ad)}</b></td><td width='26%'>{html.escape(deger)}</td>"
                f"<td width='50%' class='alt'>{html.escape(aciklama)}</td></tr></table>"
            )
    return "\n".join(govde)


def _tablo_html(ad, sayfa):
    satirlar, toplam = _satir_verileri(sayfa, PDF_EN_FAZLA_SATIR)
    if not satirlar:
        return f"<h2>{html.escape(ad)}</h2><p class='alt'>Bu sayfada kayıt yok.</p>"
    sutun_sayisi = max(len(s) for s in satirlar)
    agirlik = [1.0] * sutun_sayisi
    for satir in satirlar[:200]:
        for i, (metin, *_r) in enumerate(satir):
            agirlik[i] = max(agirlik[i], min(len(metin), 40) ** 0.8)
    toplam_agirlik = sum(agirlik)
    govde = [f"<h2>{html.escape(ad)}</h2>"]
    if toplam - 1 > PDF_EN_FAZLA_SATIR:
        govde.append(f"<p class='alt'>Bu sayfada {toplam - 1} kayıt var; PDF'te ilk {PDF_EN_FAZLA_SATIR} kayıt gösterilir. "
                     "Tamamı için Excel olarak kaydedin.</p>")
    govde.append("<table width='100%' cellspacing='0' cellpadding='3' border='1' style='border-color:#C7D0DD;'>")
    baslik, *veriler = satirlar
    govde.append("<thead><tr>" + "".join(
        f"<th width='{100 * agirlik[i] / toplam_agirlik:.1f}%' bgcolor='#24559B'><font color='#FFFFFF'>"
        f"{html.escape(m[0])}</font></th>" for i, m in enumerate(baslik)
    ) + "</tr></thead>")
    for numara, satir in enumerate(veriler):
        zemin = "#F3F6FB" if numara % 2 else "#FFFFFF"
        govde.append(f"<tr bgcolor='{zemin}'>" + "".join(
            f"<td align='{'right' if sayisal else 'left'}'>{html.escape(metin)}</td>" for metin, sayisal, *_r in satir
        ) + "</tr>")
    govde.append("</table>")
    return "\n".join(govde)


_STIL = """
body { font-family: '%s'; font-size: 8pt; color: #1F2D3D; }
h1 { font-size: 16pt; color: #16294B; margin-bottom: 2px; }
h2 { font-size: 11pt; color: #24559B; margin-top: 12px; margin-bottom: 4px; }
p.alt, td.alt { color: #5B6B82; }
th { font-size: 8pt; }
""" % PDF_YAZI_TIPI


def xlsx_pdfe_cevir(xlsx_yolu, pdf_yolu, baslik=None):
    """Raporun .xlsx dosyasını (Özet + tablo sayfaları) A4 yatay PDF'e çevirir. Önce geçici dosyaya yazar, başarılıysa hedefe taşır."""
    from openpyxl import load_workbook
    kitap = load_workbook(xlsx_yolu, data_only=True)
    try:
        sayfalar = list(kitap.worksheets)
        ilk = sayfalar[0]
        belge_basligi = baslik or str(ilk["A1"].value or "TKYS Raporu")
        govde = [_ozet_html(ilk)] if ilk.title == "Özet" else []
        for sayfa in (sayfalar[1:] if ilk.title == "Özet" else sayfalar):
            govde.append(_tablo_html(sayfa.title, sayfa))
        html_metni = f"<html><head><style>{_STIL}</style></head><body>{''.join(govde)}</body></html>"
    finally:
        kitap.close()

    hedef = Path(pdf_yolu)
    fd, gecici = tempfile.mkstemp(prefix=".tkys_rapor_", suffix=".pdf", dir=str(hedef.parent))
    os.close(fd)
    try:
        yazici = QPdfWriter(gecici)
        yazici.setPageSize(QPageSize(QPageSize.A4))
        yazici.setPageOrientation(QPageLayout.Landscape)
        yazici.setResolution(96)
        yazici.setPageMargins(QMarginsF(10, 10, 10, 10), QPageLayout.Millimeter)
        yazici.setTitle(belge_basligi)
        yazici.setCreator("TKYS")
        _belgeyi_ciz(yazici, html_metni, belge_basligi)
        os.replace(gecici, pdf_yolu)
    except Exception:
        try:
            os.remove(gecici)
        except OSError:
            pass
        raise


def _belgeyi_ciz(yazici, html_metni, belge_basligi):
    genislik, yukseklik = yazici.width(), yazici.height()
    altlik = 22
    govde_yuksekligi = yukseklik - altlik
    belge = QTextDocument()
    belge.setDefaultFont(QFont(PDF_YAZI_TIPI, 8))
    belge.documentLayout().setPaintDevice(yazici)
    belge.setPageSize(QSizeF(genislik, govde_yuksekligi))
    belge.setHtml(html_metni)
    sayfa_sayisi = max(1, belge.pageCount())

    ressam = QPainter()
    if not ressam.begin(yazici):
        raise RuntimeError("PDF yazıcısı başlatılamadı.")
    try:
        yazi = QFont(PDF_YAZI_TIPI, 7)
        zaman = datetime.now().strftime("%d.%m.%Y %H:%M")
        for i in range(sayfa_sayisi):
            if i:
                if not yazici.newPage():
                    raise RuntimeError("PDF'de yeni sayfa oluşturulamadı.")
            ressam.save()
            ressam.setClipRect(QRectF(0, 0, genislik, govde_yuksekligi))
            ressam.translate(0, -i * govde_yuksekligi)
            belge.drawContents(ressam, QRectF(0, i * govde_yuksekligi, genislik, govde_yuksekligi))
            ressam.restore()
            ressam.setFont(yazi)
            ressam.setPen(QColor("#5B6B82"))
            alan = QRectF(0, govde_yuksekligi + 4, genislik, altlik - 4)
            ressam.drawText(alan, Qt.AlignLeft | Qt.AlignVCenter, f"TKYS  ·  {belge_basligi}  ·  {zaman}")
            ressam.drawText(alan, Qt.AlignRight | Qt.AlignVCenter, f"Sayfa {i + 1} / {sayfa_sayisi}")
    finally:
        ressam.end()
