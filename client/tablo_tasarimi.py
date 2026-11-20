"""Bakım / kalibrasyon gibi liste ekranlarının ortak görünümü ve yardımcı bileşenleri."""
import datetime
import re
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QFrame,
                               QTableWidget, QTableWidgetItem, QHeaderView, QSizePolicy,
                               QMessageBox, QStyle, QStyledItemDelegate, QStyleOptionViewItem, QApplication)
from PySide6.QtCore import Qt, QRect, QSize
from PySide6.QtGui import QColor, QFont, QFontMetrics
from client.tablo_siralama import siralanabilir_yap

SATIR_YUKSEKLIK = 54

TABLO_STIL = """
    QTableWidget { background: white; border: none; font-size: 13px; color: #0F2552; }
    QTableWidget::item { padding: 6px 10px; border-bottom: 1px solid #EEF2FA; }
    QTableWidget::item:selected { background: #EEF4FF; color: #0F2552; }
    QHeaderView::section { background: #F3F7FF; color: #6B7FA8; padding: 12px 10px;
                           font-size: 11px; font-weight: 800; border: none; }
"""

def ortak_liste_stili_uygula(tablo):
    """Liste sayfalarının ortak tablo görünümü (açık başlıklı, ızgarasız; cihaz sayfalarındakiyle aynı). Satır numarası gizlenir:
    kayıt kimliği gerekiyorsa ayrı bir ID sütunu vardır."""
    tablo.setStyleSheet(TABLO_STIL)
    tablo.setShowGrid(False)
    tablo.verticalHeader().setVisible(False)


class CihazHucresiDelegate(QStyledItemDelegate):
    """"KOD · Ad" biçimindeki hücreyi iki satırda çizer: üstte cihaz adı (kalın), altında envanter kodu (küçük, gri).

    Hücrenin metni değişmez (arama, sıralama ve testler eskisi gibi çalışır); yalnızca çizim değişir. Uzun ad ya da kod hücreye
    sığmazsa sonu "…" ile kısaltılır; tam metin hücrenin ipucunda (üzerine gelince) görünür. Ayırıcı yoksa hücre normal çizilir.
    """
    AYIRICI = re.compile(r"\s+[·\-]\s+")
    KOD_RENGI = QColor("#64748B")

    @classmethod
    def parcala(cls, metin):
        """(ad, kod). Ayırıcı yoksa (metin, "")."""
        parca = cls.AYIRICI.split(str(metin or ""), maxsplit=1)
        return (parca[1].strip(), parca[0].strip()) if len(parca) == 2 and parca[0] and parca[1] else (str(metin or ""), "")

    @staticmethod
    def _yazilar(temel):
        ad = QFont(temel)
        ad.setBold(True)
        ad.setPixelSize(13)
        kod = QFont(temel)
        kod.setBold(False)
        kod.setPixelSize(11)
        return ad, kod

    def sizeHint(self, option, index):
        ad, kod = self.parcala(index.data(Qt.DisplayRole))
        if not kod:
            return super().sizeHint(option, index)
        f_ad, f_kod = self._yazilar(option.font)
        genislik = max(QFontMetrics(f_ad).horizontalAdvance(ad), QFontMetrics(f_kod).horizontalAdvance(kod)) + 28
        return QSize(genislik, QFontMetrics(f_ad).height() + QFontMetrics(f_kod).height() + 14)

    def paint(self, painter, option, index):
        ad, kod = self.parcala(index.data(Qt.DisplayRole))
        if not kod:
            super().paint(painter, option, index)
            return
        secenek = QStyleOptionViewItem(option)
        self.initStyleOption(secenek, index)
        secenek.text = ""                                                    # arka plan ve seçim rengi stile çizdirilir, metni biz çizeriz
        stil = secenek.widget.style() if secenek.widget else QApplication.style()
        stil.drawControl(QStyle.CE_ItemViewItem, secenek, painter, secenek.widget)

        secili = bool(option.state & QStyle.State_Selected)
        f_ad, f_kod = self._yazilar(option.font)
        olcu_ad, olcu_kod = QFontMetrics(f_ad), QFontMetrics(f_kod)
        alan = option.rect.adjusted(12, 0, -12, 0)
        toplam = olcu_ad.height() + olcu_kod.height()
        ust = option.rect.top() + max((option.rect.height() - toplam) // 2, 0)
        hiza = index.data(Qt.TextAlignmentRole)
        hiza = Qt.AlignCenter if hiza is not None and int(hiza) & int(Qt.AlignHCenter) else Qt.AlignLeft | Qt.AlignVCenter

        fircalar = index.data(Qt.ForegroundRole)
        ad_rengi = option.palette.highlightedText().color() if secili else (
            fircalar.color() if fircalar is not None and hasattr(fircalar, "color") else QColor("#0F2552"))
        kod_rengi = option.palette.highlightedText().color() if secili else self.KOD_RENGI

        painter.save()
        painter.setFont(f_ad)
        painter.setPen(ad_rengi)
        painter.drawText(QRect(alan.left(), ust, alan.width(), olcu_ad.height()), hiza,
                         olcu_ad.elidedText(ad, Qt.ElideRight, alan.width()))
        painter.setFont(f_kod)
        painter.setPen(kod_rengi)
        painter.drawText(QRect(alan.left(), ust + olcu_ad.height(), alan.width(), olcu_kod.height()), hiza,
                         olcu_kod.elidedText(kod, Qt.ElideRight, alan.width()))
        painter.restore()


def _yatay_dolgu(tablo):
    """Tablonun `::item { padding: ... }` kuralındaki sağ+sol dolgu toplamı (px). Hücre bileşenleri bu kadar daraltılmış alana yerleşir."""
    eslesme = re.search(r"::item\s*\{[^}]*?padding:\s*\d+px\s+(\d+)px", tablo.styleSheet() or "")
    return 2 * int(eslesme.group(1)) if eslesme else 0


def hap_sutununu_sigdir(tablo, sutun, en_az=96):
    """Durum rozetleri (hap) taşıyan sütunun genişliğini, en geniş rozet + hücre dolgusu kadar yapar.

    Qt, tablo stilindeki `padding` kadar daralttığı alana hücre bileşenini koyar; sütun yalnızca rozet kadar geniş olursa rozet iki
    yandan kesiliyordu ("Tamamlandı" -> "amamlanc"). Genişlik açıkça verilince bileşenler de yeniden yerleştirilir.
    Satırlar doldurulduktan sonra çağrılır; sütun Fixed kipte olmalıdır.
    """
    genislikler = [tablo.cellWidget(s, sutun).sizeHint().width() for s in range(tablo.rowCount()) if tablo.cellWidget(s, sutun)]
    tablo.setColumnWidth(sutun, max(genislikler + [en_az]) + _yatay_dolgu(tablo) + 6)


def cihaz_hucresi_uygula(tablo, sutun=0):
    """Tablonun bu sütununda "KOD · Ad" hücrelerini iki satırlı (ad üstte, kod altta) çizer."""
    tablo.setItemDelegateForColumn(sutun, CihazHucresiDelegate(tablo))


# Cihaz yaşam döngüsü tabloları: hücre metni ortalı, sütunlar arası daha geniş boşluk
ORTALI_TABLO_STIL = (TABLO_STIL.replace("padding: 6px 10px", "padding: 6px 22px")
                               .replace("padding: 12px 10px", "padding: 12px 22px"))


class OrtaliTablo(QTableWidget):
    """Tabloya konan her metin hücresini otomatik ortalar (hücre widget'ları kendi hizasını yönetir)."""

    def setItem(self, satir, sutun, item):
        if item is not None:
            item.setTextAlignment(Qt.AlignCenter)
        super().setItem(satir, sutun, item)


# Form pencerelerinin (Yeni / Düzenle) ortak görünümü
FORM_STIL = """
    QDialog { background: #F4F7FC; }
    QLabel { color: #1E3A8A; font-size: 13px; font-weight: 700; background: transparent; }
    QLineEdit, QComboBox, QDateEdit, QTextEdit {
        background: white; color: #0F2552; border: 1px solid #C7D9FB;
        border-radius: 10px; padding: 9px 12px; font-size: 13px;
    }
    QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QTextEdit:focus { border: 2px solid #3B82F6; }
    QLineEdit:read-only { background: #EAF0FA; color: #6B7FA8; }
    QComboBox QAbstractItemView { background: white; color: #0F2552;
        selection-background-color: #2563EB; selection-color: white; }
    QCalendarWidget QWidget { alternate-background-color: #EAF0FA; color: #0F2552; }
    QPushButton#kaydet { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #1D4ED8, stop:1 #3B82F6);
        color: white; border: none; border-radius: 10px; padding: 12px; font-size: 14px; font-weight: 800; }
    QPushButton#kaydet:hover { background: #1E40AF; }
"""

ARAMA_STIL = """
    QLineEdit { background: #F3F7FF; border: 1px solid #DCE6FA; border-radius: 12px;
                padding: 10px 14px; font-size: 13px; color: #0F2552; min-width: 260px; }
    QLineEdit:focus { border: 1px solid #3B82F6; background: white; }
"""


def tablo_olustur(kolonlar, ortali=False, siralanabilir=True):
    """ortali=True: metinler hücrede ortalanır ve sütunlar arası boşluk artar (cihaz yaşam döngüsü ekranları)."""
    tablo = OrtaliTablo(0, len(kolonlar)) if ortali else QTableWidget(0, len(kolonlar))
    tablo.setHorizontalHeaderLabels(kolonlar)
    tablo.horizontalHeader().setHighlightSections(False)
    tablo.verticalHeader().setVisible(False)
    tablo.verticalHeader().setDefaultSectionSize(SATIR_YUKSEKLIK)
    tablo.setEditTriggers(QTableWidget.NoEditTriggers)
    tablo.setSelectionBehavior(QTableWidget.SelectRows)
    tablo.setSelectionMode(QTableWidget.SingleSelection)
    tablo.setFocusPolicy(Qt.NoFocus)
    tablo.setShowGrid(False)
    tablo.setWordWrap(True)
    tablo.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    tablo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    tablo.setStyleSheet(ORTALI_TABLO_STIL if ortali else TABLO_STIL)
    if siralanabilir:
        siralanabilir_yap(tablo)          # başlığa tıklayınca sıralama (İŞLEM sütunu hariç)
    return tablo


def metin_item(metin, ortala=False, kalin=False, renk=None):
    item = QTableWidgetItem(metin)
    if ortala:
        item.setTextAlignment(Qt.AlignCenter)
    if kalin:
        f = item.font()
        f.setBold(True)
        item.setFont(f)
    if renk:
        item.setForeground(QColor(renk))
    return item


def hap(metin, renk, arka, ipucu=None):
    """Tabloya konacak renkli durum 'hapı' (hücre widget'ı)."""
    lbl = QLabel(metin)
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setStyleSheet(f"background: {arka}; color: {renk}; border-radius: 12px; "
                      f"font-size: 11px; font-weight: 800; padding: 5px 12px;")
    # Qt, etiketin boyutunu yazı tipi stil sayfasından uygulanmadan hesaplayabildiği için bazı bilgisayarlarda metin kenarlardan
    # kırpılıyordu ("Tamamlandı" -> "amamlanc"). Gerçek (kalın, 11 px) yazı tipiyle ölçülen genişlik en az genişlik olarak verilir.
    yazi = QFont(lbl.font())
    yazi.setPixelSize(11)
    yazi.setWeight(QFont.ExtraBold)
    lbl.setMinimumWidth(QFontMetrics(yazi).horizontalAdvance(metin) + 24 + 10)
    if ipucu:
        lbl.setToolTip(ipucu)
    kap = QWidget()
    lay = QHBoxLayout(kap)
    lay.setContentsMargins(6, 4, 6, 4)
    lay.addStretch()
    lay.addWidget(lbl)
    lay.addStretch()
    return kap


def _ikon_buton(simge, ipucu, renk, arka, arka_hover, tikla):
    b = QPushButton(simge)
    b.setToolTip(ipucu)
    b.setCursor(Qt.PointingHandCursor)
    b.setFixedSize(34, 34)
    b.setStyleSheet(
        f"QPushButton {{ background: {arka}; color: {renk}; border: none; border-radius: 10px; "
        f"font-size: 15px; }} QPushButton:hover {{ background: {arka_hover}; }}")
    b.clicked.connect(tikla)
    return b


def islem_butonlari(duzenle_fn, sil_fn):
    """Satır sonu için ✎ (düzenle) ve 🗑 (sil) ikon butonları."""
    kap = QWidget()
    lay = QHBoxLayout(kap)
    lay.setContentsMargins(6, 4, 6, 4)
    lay.setSpacing(8)
    lay.addStretch()
    lay.addWidget(_ikon_buton("✎", "Düzenle", "#B45309", "#FEF3C7", "#FDE68A", duzenle_fn))
    lay.addWidget(_ikon_buton("🗑", "Sil", "#B91C1C", "#FEE2E2", "#FECACA", sil_fn))
    lay.addStretch()
    return kap


def tek_islem_butonu(fn, simge="✎", ipucu="Düzenle", renk="#B45309", arka="#FEF3C7", hover="#FDE68A"):
    """Satır sonu için tek ikon butonu (ör. sadece düzenle)."""
    kap = QWidget()
    lay = QHBoxLayout(kap)
    lay.setContentsMargins(6, 4, 6, 4)
    lay.addStretch()
    lay.addWidget(_ikon_buton(simge, ipucu, renk, arka, hover, fn))
    lay.addStretch()
    return kap


def sil_onayi(parent, baslik, mesaj):
    """Silmeden önce onay ister. Evet denirse True döner."""
    kutu = QMessageBox(parent)
    kutu.setIcon(QMessageBox.Warning)
    kutu.setWindowTitle(baslik)
    kutu.setText(mesaj)
    kutu.setInformativeText("Bu işlem geri alınamaz.")
    evet = kutu.addButton("Evet, sil", QMessageBox.DestructiveRole)
    kutu.addButton("Vazgeç", QMessageBox.RejectRole)
    kutu.setDefaultButton(kutu.buttons()[-1])
    kutu.setStyleSheet("QLabel { color: #0F2552; font-size: 13px; } QPushButton { padding: 8px 18px; }")
    kutu.exec()
    return kutu.clickedButton() is evet


KIMLIK_ROLU = Qt.UserRole + 7           # satırın kayıt kimliği (ilk sütundaki öğede saklanır)


def satira_kimlik_ata(tablo, satir, kimlik):
    """Satırın kayıt kimliğini saklar; çift tıklamada hangi kaydın açılacağı buradan bulunur."""
    item = tablo.item(satir, 0)
    if item is None:
        item = QTableWidgetItem("")
        tablo.setItem(satir, 0, item)
    item.setData(KIMLIK_ROLU, kimlik)


def satir_kimligi(tablo, satir):
    item = tablo.item(satir, 0)
    return item.data(KIMLIK_ROLU) if item is not None else None


def cift_tikla_ac(tablo, islev):
    """Satıra çift tıklanınca islev(kayit_kimligi) çağrılır (kimliği atanmamış satırlar yok sayılır).

    Satır sonundaki simge düğmeleri kendi tıklamasını yakalar; çift tıklama yalnızca satırın geri kalanında çalışır."""
    def tiklandi(satir, _sutun):
        kimlik = satir_kimligi(tablo, satir)
        if kimlik is not None:
            islev(kimlik)
    tablo.cellDoubleClicked.connect(tiklandi)


def tehlike_dugmesi(yazi, tikla):
    """Düzenleme pencerelerinin altındaki silme / iptal düğmesi (kırmızı çerçeveli)."""
    d = QPushButton(yazi)
    d.setObjectName("tehlike")
    d.setCursor(Qt.PointingHandCursor)
    d.setStyleSheet("QPushButton#tehlike { background: #FEF2F2; color: #B91C1C; border: 1px solid #FECACA; border-radius: 10px; "
                    "padding: 11px; font-size: 13px; font-weight: 800; } QPushButton#tehlike:hover { background: #FEE2E2; }")
    d.clicked.connect(tikla)
    return d


def sayi_cipi(yazi, renk="#1D4ED8", arka="#DBEAFE"):
    c = QLabel(yazi)
    c.setStyleSheet(f"background: {arka}; color: {renk}; border-radius: 12px; "
                    f"font-size: 12px; font-weight: 800; padding: 6px 14px;")
    return c


def tarih_goster(deger):
    """'2026-11-10T00:00:00' / '2026-11-10' -> '10.11.2026'. Boşsa '—'."""
    if not deger or str(deger) == "Belirtilmedi":
        return "—"
    metin = str(deger)[:10]
    try:
        return datetime.date.fromisoformat(metin).strftime("%d.%m.%Y")
    except ValueError:
        return metin


def kalan_gun_hapi(deger, uyari_gun=30):
    """Bir bitiş/son tarih için renkli hap döner: gecikmiş kırmızı, uyarı süresi (varsayılan 30 gün) içinde
    sarı, ötesi yeşil. Kayıt kendi uyarı süresini taşıyorsa o verilmelidir (zil ve dashboard ile aynı kural).

    Dönen değer: (widget, durum) — durum 'gecmis' | 'yaklasiyor' | 'iyi' | 'yok'
    """
    try:
        hedef = datetime.date.fromisoformat(str(deger)[:10])
    except (ValueError, TypeError):
        return hap("Belirtilmedi", "#6B7280", "#F3F4F6"), "yok"
    kalan = (hedef - datetime.date.today()).days
    tarih = hedef.strftime("%d.%m.%Y")
    if kalan < 0:
        return hap(f"{tarih}  ·  {-kalan} gün gecikti", "#991B1B", "#FEE2E2"), "gecmis"
    if kalan <= uyari_gun:
        yazi = "bugün" if kalan == 0 else f"{kalan} gün kaldı"
        return hap(f"{tarih}  ·  {yazi}", "#854D0E", "#FEF3C7"), "yaklasiyor"
    return hap(f"{tarih}  ·  {kalan} gün", "#166534", "#DCFCE7"), "iyi"


def hatirlatma_metni(gun):
    """Kayıttaki uyarı süresini listede okunur yazıya çevirir: bildirim tarihe kaç gün kala düşer."""
    try:
        gun = int(gun)
    except (TypeError, ValueError):
        return "-"
    return "Geldiği gün" if gun == 0 else f"{gun} gün kala"


def sayfa_basligi(baslik, alt_baslik, arama_kutusu, yenile_butonu, cipler, ek_butonlar=()):
    """Ekranın üstündeki beyaz araç çubuğu kartı."""
    kart = QFrame()
    kart.setObjectName("kart")
    ana = QVBoxLayout(kart)
    ana.setContentsMargins(22, 18, 22, 16)
    ana.setSpacing(12)

    ust = QHBoxLayout()
    metinler = QVBoxLayout()
    metinler.setSpacing(0)
    b = QLabel(baslik)
    b.setStyleSheet("font-size: 18px; font-weight: 800; color: #0A1F5C;")
    a = QLabel(alt_baslik)
    a.setStyleSheet("font-size: 12px; color: #6B7FA8;")
    metinler.addWidget(b)
    metinler.addWidget(a)
    ust.addLayout(metinler)
    ust.addStretch()
    arama_kutusu.setStyleSheet(ARAMA_STIL)
    ust.addWidget(arama_kutusu)
    for ek in ek_butonlar:          # Yenile'den önce (örn. Excel'e Aktar)
        ust.addWidget(ek)
    ust.addWidget(yenile_butonu)
    ana.addLayout(ust)

    alt = QHBoxLayout()
    alt.setSpacing(10)
    for c in cipler:
        alt.addWidget(c)
    alt.addStretch()
    ana.addLayout(alt)
    return kart


def yenile_butonu_olustur(tikla):
    b = QPushButton("⟳  Yenile")
    b.setCursor(Qt.PointingHandCursor)
    b.setStyleSheet("QPushButton { background: #EEF4FF; color: #1D4ED8; border: 1px solid #C7D9FB; "
                    "border-radius: 12px; padding: 10px 18px; font-size: 13px; font-weight: 700; } "
                    "QPushButton:hover { background: #DBEAFE; }")
    b.clicked.connect(tikla)
    return b


def bos_mesaj_olustur(metin):
    lbl = QLabel(metin)
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setStyleSheet("font-size: 14px; color: #8A9BC0; padding: 60px;")
    lbl.hide()
    return lbl