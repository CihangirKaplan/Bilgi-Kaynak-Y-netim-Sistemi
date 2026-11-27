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
import re
import tempfile
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path

from PySide6.QtCore import QMarginsF, QRectF, QSizeF, Qt
from PySide6.QtGui import QColor, QFont, QPageLayout, QPageSize, QPainter, QPdfWriter, QTextDocument, QTextTable
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
# PDF yüksek çözünürlükte (300 dpi) yazılır ve yazı tipinde "hinting" kapatılır: düşük çözünürlükte (96 dpi) Windows harf aralıklarını tam piksele yuvarlayıp
# "D e v a m  e d e n" gibi eşitsiz boşluklar üretiyordu. Yerleşimdeki piksel ölçüleri (dolgu, kenarlık) bu yüzden _px() ile ölçeklenir.
PDF_COZUNURLUK = 300
_OLCEK = PDF_COZUNURLUK / 96
LACIVERT = "#16294B"
MAVI = "#24559B"
ACIK_MAVI = "#E8F0FF"
GRI_YAZI = "#5B6B82"
CIZGI = "#D5DCE8"


def _px(n):
    return max(1, round(n * _OLCEK))


def _tr_sayi(metin):
    """Python biçimli sayının (1,234.50) ayraçlarını Türkçeye çevirir (1.234,50)."""
    return metin.replace(",", "\x01").replace(".", ",").replace("\x01", ".")


def _sayi_metni(deger, bicim=""):
    """Excel sayı biçimini (ondalık, binlik ayraç, yüzde, tırnaklı birim eki/öneki: '#,##0.00 "₺"', '0 "gün"') Türkçe metne çevirir."""
    if isinstance(deger, bool):
        return "Evet" if deger else "Hayır"
    ilk = (bicim or "").split(";")[0]
    literaller = re.findall(r'"([^"]*)"', ilk)
    kalan = re.sub(r'"[^"]*"', "\x00", ilk)
    kalan = re.sub(r"\\(.)", r"\1", kalan)                            # \x ile kaçırılmış karakter olduğu gibi yazılır
    kalan = re.sub(r"_.|\*.", "", kalan)
    eslesme = re.search(r"[#0?,.]+%?", kalan)
    if eslesme is None:                                                     # General / sayı deseni yok
        if isinstance(deger, int):
            return str(deger)
        return _tr_sayi(f"{deger:.2f}".rstrip("0").rstrip("."))
    desen = eslesme.group(0)
    yuzde = desen.endswith("%")
    desen = desen.rstrip("%")
    tam, _, ondalik = desen.partition(".")
    zorunlu, istege_bagli = ondalik.count("0"), ondalik.count("#") + ondalik.count("?")
    deger_ = deger * 100 if yuzde else deger
    binlik = "," in tam
    metin = f"{deger_:,.{zorunlu + istege_bagli}f}" if binlik else f"{deger_:.{zorunlu + istege_bagli}f}"
    if istege_bagli and "." in metin:                                       # '#' ile istenen fazla ondalık sıfırlar atılır
        govde, _, kesir = metin.partition(".")
        kesir = kesir.rstrip("0").ljust(zorunlu, "0")
        metin = govde + ("." + kesir if kesir else "")
    metin = _tr_sayi(metin)
    if yuzde:
        metin = "%" + metin
    sonuc = kalan[:eslesme.start()] + metin + kalan[eslesme.end():]
    for lit in literaller:
        sonuc = sonuc.replace("\x00", lit, 1)
    return sonuc.strip()


def hucre_metni(hucre):
    """Hücrenin PDF'te görünecek yazısı: tarihler gg.aa.yyyy [ss:dd], sayılar Excel biçimiyle (birim eki, binlik ayraç, Türkçe ondalık)."""
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


def _renk(renk):
    """openpyxl rengini (ARGB metni) #RRGGBB'ye çevirir; tema/indeks renkleri ve 'dolgusuz' (00000000) için None."""
    deger = getattr(renk, "rgb", None)
    if isinstance(deger, str) and len(deger) == 8 and deger != "00000000":
        return "#" + deger[2:]
    return None


def _satir_verileri(sayfa, en_fazla=None):
    """Boş olmayan satırlar: [(metin, sayisal_mi, kalin_mi, dolgu_rengi, yazi_rengi)] listesi; en_fazla verilirse ilk satır + en_fazla veri satırı."""
    satirlar = []
    for satir in sayfa.iter_rows():
        if all(h.value is None for h in satir):
            continue
        satirlar.append([
            (hucre_metni(h), isinstance(h.value, (int, float)) and not isinstance(h.value, bool),
             bool(h.font and h.font.b), _renk(h.fill.fgColor) if (h.fill and h.fill.fill_type == "solid") else None,
             _renk(h.font.color) if (h.font and h.font.color) else None)
            for h in satir
        ])
    toplam = len(satirlar)
    if en_fazla is not None and toplam - 1 > en_fazla:
        satirlar = satirlar[: en_fazla + 1]
    return satirlar, toplam


def _bosluk(pt=7):
    return f"<p style='margin:0; font-size:{pt}pt;'>&nbsp;</p>"


BASLIK_DOLGUSU = _px(3.5)               # bölüm başlığı tablolarını belgede tanımak için ayrı dolgu değeri


def _bolum_basligi(metin, sag=""):
    """Açık mavi şeritli bölüm başlığı; sağ tarafta isteğe bağlı kısa bilgi (örn. kayıt sayısı)."""
    sag_hucre = f"<td align='right' bgcolor='{ACIK_MAVI}'><span style='font-size:8pt; color:{GRI_YAZI};'>{html.escape(sag)}</span></td>" if sag else ""
    return (f"{_bosluk(8)}<table width='100%' cellspacing='0' cellpadding='{BASLIK_DOLGUSU}'><tr>"
            f"<td bgcolor='{ACIK_MAVI}'><b><span style='font-size:10pt; color:{LACIVERT};'>{html.escape(metin)}</span></b></td>{sag_hucre}</tr></table>")


def _ozet_satiri(ad, deger, aciklama, kalin, ilk):
    kenar = "" if ilk else f" style='border-top:2px solid {CIZGI};'"
    etiket = f"<b>{html.escape(ad)}</b>" if kalin else html.escape(ad)
    return (f"<tr><td width='25%' valign='top'{kenar}><span style='color:{LACIVERT};'>{etiket}</span></td>"
            f"<td width='22%' valign='top'{kenar}><b>{html.escape(deger)}</b></td>"
            f"<td width='53%' valign='top'{kenar}><span style='color:{GRI_YAZI};'>{html.escape(aciklama)}</span></td></tr>")


# PDF'te "sayfa" kavramı yok (bölümler art arda gelir): Excel'deki sayfa rehberi burada içindekiler olarak anılır.
_PDF_BASLIK_DEGISIMLERI = {"SAYFA REHBERİ": "RAPOR İÇERİĞİ"}
_PDF_METIN_DEGISIMLERI = (("Excel'e aktarıldığı", "oluşturulduğu"), ("dışa aktarıldığı", "oluşturulduğu"), ("Bu Excel dosyasına", "Bu dosyaya"))


def _ozet_html(sayfa):
    """Özet sayfası: koyu başlık şeridi, açık mavi bölüm başlıkları ve (ad, değer, açıklama) tabloları."""
    satirlar, _ = _satir_verileri(sayfa)
    bolumler = []                                   # [(başlık, [html parçaları], satır sayısı)]
    baslik = alt = None

    def acik():
        if not bolumler:
            bolumler.append((None, [], 0))
        return bolumler[-1]

    for sira, satir in enumerate(satirlar):
        metinler = [m[0] for m in satir]
        dolu = [m for m in metinler if m != ""]
        for eski, yeni in _PDF_METIN_DEGISIMLERI:
            metinler = [m.replace(eski, yeni) for m in metinler]
        if sira == 0:
            baslik = metinler[0]
            continue
        if sira == 1 and len(dolu) == 1 and not satir[0][3]:
            alt = metinler[0]
            continue
        if len(dolu) == 1 and satir[0][3] is not None:           # tek hücreli, dolgulu satır = bölüm başlığı
            bolumler.append((dolu[0], [], 0))
        elif len(dolu) == 1 and not satir[0][2]:                  # tek hücreli düz satır = açıklama
            acik()[1].append(f"<p style='color:{GRI_YAZI};'>{html.escape(metinler[0])}</p>")
        else:
            ad, deger, aciklama = (metinler + ["", "", ""])[:3]
            b_ad, parcalar, sayi = acik()
            parcalar.append(_ozet_satiri(ad, deger, aciklama, satir[0][2], sayi == 0))
            bolumler[-1] = (b_ad, parcalar, sayi + 1)

    govde = []
    for b_ad, parcalar, sayi in bolumler:
        if b_ad in _PDF_BASLIK_DEGISIMLERI and sayi <= 1:         # tek sayfalık (liste) raporlarda tek maddelik içindekiler gereksiz
            continue
        if b_ad:
            govde.append(_bolum_basligi(_PDF_BASLIK_DEGISIMLERI.get(b_ad, b_ad)))
        satir_html = "".join(p for p in parcalar if p.startswith("<tr>"))
        for p in parcalar:
            if not p.startswith("<tr>"):
                govde.append(p)
        if satir_html:
            govde.append(f"<table width='100%' cellspacing='0' cellpadding='{_px(2.2)}'>{satir_html}</table>")
    ust = (f"<table width='100%' cellspacing='0' cellpadding='{_px(8)}'><tr><td bgcolor='{LACIVERT}'>"
           f"<span style='font-size:17pt; color:#FFFFFF;'><b>{html.escape(baslik or '')}</b></span>"
           + (f"<p style='margin-top:{_px(3)}px; margin-bottom:0;'><span style='font-size:8pt; color:#C9D6EE;'>{html.escape(alt)}</span></p>" if alt else "")
           + "</td></tr></table>")
    return ust + "\n" + "\n".join(govde)


def _sutun_agirliklari(satirlar, sutun_sayisi):
    """Sütun genişlik oranları: kısa sütunlar (No, tarih, durum) içeriği sığacak kadar, uzun metin sütunları orantılı daralarak pay alır."""
    en_uzun = [1] * sutun_sayisi
    for satir in satirlar[:200]:
        for i, hucre in enumerate(satir):
            en_uzun[i] = max(en_uzun[i], len(hucre[0]))
    return [u * 2.0 + 4 if u <= 16 else 36 + 2.5 * (u - 16) ** 0.55 for u in en_uzun]


def _kucult(icerik):
    return f"<span style='font-size:7pt'>{icerik}</span>"


def _hucre_html(hucre, etiket, zemin, kucuk=False):
    metin, sayisal, kalin, dolgu, yazi = hucre
    renk = yazi if yazi and yazi.upper() != "#000000" else None
    icerik = html.escape(metin)
    if kucuk:
        icerik = _kucult(icerik)
    if kalin:
        icerik = f"<b>{icerik}</b>"
    if renk:
        icerik = f"<font color='{renk}'>{icerik}</font>"
    cizgi = f" style='border-bottom:2px solid {CIZGI};'" if etiket == "td" else ""
    return f"<{etiket} align='{'right' if sayisal else 'left'}' valign='top' bgcolor='{dolgu or zemin}'{cizgi}>{icerik}</{etiket}>"


def _tablo_html(ad, sayfa):
    satirlar, toplam = _satir_verileri(sayfa, PDF_EN_FAZLA_SATIR)
    if not satirlar:
        return _bolum_basligi(ad) + f"<p style='color:{GRI_YAZI};'>Bu bölümde kayıt yok.</p>"
    sutun_sayisi = max(len(s) for s in satirlar)
    agirlik = _sutun_agirliklari(satirlar, sutun_sayisi)
    toplam_agirlik = sum(agirlik)
    genislik = [f"{100 * a / toplam_agirlik:.2f}%" for a in agirlik]
    ilk = satirlar[0]
    kucuk = sutun_sayisi > 10                                                   # çok sütunlu tabloda yazı bir punto küçülür
    basliklu = len(ilk) == sutun_sayisi and all(h[0] != "" for h in ilk)        # düzenli tablo: ilk satır sütun başlığıdır
    kayit = f"{toplam - 1} kayıt" if basliklu else ""
    govde = [_bolum_basligi(ad, kayit) + _bosluk(3)]
    if toplam - 1 > PDF_EN_FAZLA_SATIR:
        govde.append(f"<p style='color:{GRI_YAZI};'>Bu bölümde {toplam - 1} kayıt var; PDF'te ilk {PDF_EN_FAZLA_SATIR} kayıt gösterilir. "
                     "Tamamı için Excel olarak kaydedin.</p>")
    govde.append(f"<table width='100%' cellspacing='0' cellpadding='{_px(2.2)}'>")
    veriler = satirlar
    if basliklu:
        veriler = satirlar[1:]
        sayisal = [sum(1 for v in veriler[:30] if i < len(v) and v[i][1]) > len(veriler[:30]) / 2 for i in range(sutun_sayisi)]   # çoğu hücresi sayı olan sütun
        govde.append("<thead><tr>" + "".join(
            f"<th width='{genislik[i]}' align='{'right' if sayisal[i] else 'left'}' bgcolor='{MAVI}'><font color='#FFFFFF'>"
            f"{_kucult(html.escape(m[0])) if kucuk else html.escape(m[0])}</font></th>" for i, m in enumerate(ilk)
        ) + "</tr></thead>")
    if not basliklu:                                                              # serbest düzenli sayfa: sütun genişlikleri görünmez bir ilk satırla verilir
        govde.append("<tr>" + "".join(f"<td width='{g}' style='font-size:1pt;'></td>" for g in genislik) + "</tr>")
    for numara, satir in enumerate(veriler):
        zemin = "#F5F8FC" if numara % 2 else "#FFFFFF"
        dolu = [i for i, h in enumerate(satir) if h[0] != ""]
        if not basliklu and len(dolu) == 1 and dolu[0] == 0 and sutun_sayisi > 1:   # tek hücreli satır (ara başlık, açıklama): tüm genişliğe yayılır
            hucreler = _hucre_html(satir[0], "td", zemin, kucuk).replace("<td ", f"<td colspan='{sutun_sayisi}' ", 1)
        else:
            hucreler = "".join(_hucre_html(h, "td", zemin, kucuk) for h in satir)
        govde.append(f"<tr>{hucreler}</tr>")
    govde.append("</table>")
    return "\n".join(govde)


# Dikkat: stil sayfasında body/th için font-size verilmez; Qt bunu tablo hücrelerinde satır içi (span) boyutların önüne geçirir. Boyut setDefaultFont ile verilir.
_STIL = """
body { font-family: '%s'; color: #1F2D3D; }
p { margin-top: 2px; margin-bottom: 2px; }
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
        yazici.setResolution(PDF_COZUNURLUK)
        yazici.setPageMargins(QMarginsF(12, 11, 12, 10), QPageLayout.Millimeter)
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


def _yazi_tipi(punto, kalin=False):
    yazi = QFont(PDF_YAZI_TIPI, punto)
    yazi.setHintingPreference(QFont.PreferNoHinting)                      # harf konumları tam piksele yuvarlanmaz (eşit harf aralığı)
    yazi.setBold(kalin)
    return yazi


_ARA_BASLIK_RENKLERI = {LACIVERT.lower(), ACIK_MAVI.lower()}         # serbest düzenli sayfalardaki bant / ara başlık satırları altındaki satırla kalır
_ISARET_BOSLUK = "\xa0"                                              # _bosluk() paragrafının metni (başlıkla birlikte tutulur)
_BUYUK_SAYFA = 2_000_000                                            # belge önce tek parça yerleştirilir, sayfalara biz böleriz


class _Parca:
    """Sayfa sonunda bölünemeyen yerleşim parçası: tablo satırı ya da paragraf. sonraki_ile: sayfa sonunda bir sonraki parçadan ayrılmaz."""
    __slots__ = ("ust", "alt", "tablo", "satir", "sonraki_ile")

    def __init__(self, ust, alt, tablo=None, satir=0, sonraki_ile=False):
        self.ust, self.alt, self.tablo, self.satir, self.sonraki_ile = ust, alt, tablo, satir, sonraki_ile


def _parcalar(belge):
    """Belgenin üst düzey içeriğini yerleşim sırasıyla bölünemez parçalara ayırır; tablo başlık aralıklarını da döndürür ({tablo_no: (ust, alt)})."""
    yer = belge.documentLayout()
    kutu = lambda blok: yer.blockBoundingRect(blok)
    parcalar, basliklar = [], {}
    sira = belge.rootFrame().begin()
    tablo_no = 0
    while not sira.atEnd():
        cerceve, blok = sira.currentFrame(), sira.currentBlock()
        if isinstance(cerceve, QTextTable):
            dolgu = cerceve.format().cellPadding()
            baslik_sayisi = cerceve.format().headerRowCount()
            bolum_basligi = dolgu == BASLIK_DOLGUSU
            araliklar = []
            for r in range(cerceve.rows()):
                ustler, altlar = [], []
                for c in range(cerceve.columns()):
                    hucre = cerceve.cellAt(r, c)
                    if hucre.row() != r:
                        continue
                    ustler.append(kutu(hucre.firstCursorPosition().block()).top())
                    altlar.append(kutu(hucre.lastCursorPosition().block()).bottom())
                araliklar.append((min(ustler) - dolgu, max(altlar) + dolgu))
            if baslik_sayisi:
                basliklar[tablo_no] = (araliklar[0][0], araliklar[baslik_sayisi - 1][1], baslik_sayisi)
            for r, (ust, alt) in enumerate(araliklar):
                ilk_hucre = cerceve.cellAt(r, 0)
                bant = ilk_hucre.columnSpan() > 1 or ilk_hucre.format().background().color().name().lower() in _ARA_BASLIK_RENKLERI
                parcalar.append(_Parca(ust, alt, tablo_no, r, sonraki_ile=bolum_basligi or r < baslik_sayisi or bant))
            tablo_no += 1
        elif blok.isValid() and blok.text().strip():
            dikdortgen = kutu(blok)
            parcalar.append(_Parca(dikdortgen.top(), dikdortgen.bottom(), sonraki_ile=blok.text() == _ISARET_BOSLUK))
        sira += 1
    return parcalar, basliklar


def _sayfa_plani(belge, sayfa_yuksekligi):
    """Sayfa bölünmeleri: [(y_baslangic, y_bitis, tekrar_basligi)]. Tablo satırı ve paragraf ikiye bölünmez; bölüm başlığı altındaki içerikle
    (sütun başlığı + ilk satır) birlikte kalır; tablo gövdesinden başlayan sayfanın üstünde sütun başlığı yinelenir."""
    parcalar, basliklar = _parcalar(belge)
    sayfalar = []
    i, n = 0, len(parcalar)
    while i < n:
        ilk = parcalar[i]
        tekrar = None
        if ilk.tablo in basliklar and ilk.satir >= basliklar[ilk.tablo][2]:      # tablonun gövdesinden başlayan sayfa
            tekrar = basliklar[ilk.tablo][:2]
        kapasite = sayfa_yuksekligi - ((tekrar[1] - tekrar[0]) if tekrar else 0)
        j = i
        while j < n and parcalar[j].alt - ilk.ust <= kapasite:
            j += 1
        if j == i:                                                               # tek parça sayfadan yüksek: dilimlenir
            y = ilk.ust
            while ilk.alt - y > kapasite:
                sayfalar.append((y, y + kapasite, tekrar))
                y += kapasite
            sayfalar.append((y, ilk.alt, tekrar))
            i += 1
            continue
        k = j
        if k < n:
            while k > i and parcalar[k - 1].sonraki_ile:                         # başlık/bant altındaki içerikten ayrılmaz
                k -= 1
            if k == i:                                                           # zincir sayfanın tamamını kaplıyorsa kaçınılmaz: sığdığı yerden böl
                k = j
        sayfalar.append((ilk.ust, parcalar[k - 1].alt, tekrar))
        i = k
    return sayfalar or [(0.0, float(belge.size().height()), None)]


def _belgeyi_ciz(yazici, html_metni, belge_basligi):
    genislik, yukseklik = yazici.width(), yazici.height()
    altlik = _px(24)
    govde_yuksekligi = yukseklik - altlik
    belge = QTextDocument()
    belge.setDefaultFont(_yazi_tipi(8.5))
    belge.documentLayout().setPaintDevice(yazici)
    belge.setPageSize(QSizeF(genislik, _BUYUK_SAYFA))
    belge.setHtml(html_metni)
    plan = _sayfa_plani(belge, govde_yuksekligi)
    sayfa_sayisi = len(plan)

    ressam = QPainter()
    if not ressam.begin(yazici):
        raise RuntimeError("PDF yazıcısı başlatılamadı.")
    try:
        zaman = datetime.now().strftime("%d.%m.%Y %H:%M")
        for i, (y0, y1, tekrar) in enumerate(plan):
            if i:
                if not yazici.newPage():
                    raise RuntimeError("PDF'de yeni sayfa oluşturulamadı.")
            ressam.save()
            ressam.setClipRect(QRectF(0, 0, genislik, govde_yuksekligi))
            kayma = 0.0
            if tekrar:                                                          # tablo başlığı bu sayfanın üstünde yinelenir
                ressam.save()
                ressam.translate(0, -tekrar[0])
                belge.drawContents(ressam, QRectF(0, tekrar[0], genislik, tekrar[1] - tekrar[0]))
                ressam.restore()
                kayma = tekrar[1] - tekrar[0]
            ressam.translate(0, kayma - y0)
            belge.drawContents(ressam, QRectF(0, y0, genislik, y1 - y0))
            ressam.restore()
            ressam.setPen(QColor(CIZGI))
            ressam.drawLine(0, int(govde_yuksekligi + _px(2)), int(genislik), int(govde_yuksekligi + _px(2)))
            ressam.setFont(_yazi_tipi(7))
            ressam.setPen(QColor(GRI_YAZI))
            alan = QRectF(0, govde_yuksekligi + _px(3), genislik, altlik - _px(3))
            ressam.drawText(alan, Qt.AlignLeft | Qt.AlignVCenter, f"TKYS  ·  {belge_basligi}  ·  {zaman}")
            ressam.drawText(alan, Qt.AlignRight | Qt.AlignVCenter, f"Sayfa {i + 1} / {sayfa_sayisi}")
    finally:
        ressam.end()
