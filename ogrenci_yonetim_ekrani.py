
"""TKYS - Öğrenci Yönetimi."""

from datetime import date

from PySide6.QtCore import Qt, QDate, QRectF
from PySide6.QtGui import QColor, QPainter, QFontMetrics

from PySide6.QtWidgets import (
    QWidget,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QFrame,
    QLabel,
    QPushButton,
    QLineEdit,
    QComboBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
    QDateEdit,
    QMessageBox,
    QStyledItemDelegate,
    QGraphicsDropShadowEffect,
    QStyle,
)

from api_yoneticisi import (
    oturum_kontrollu_istek,
    oturum_hatasi_mi,
)

from ogrenci_dialog import OgrenciEkleDialog


STIL = """
QWidget#ogrenciYonetimi {
    background: transparent;
    color: #243653;
}

QDialog#ogrenciDialog {
    background: #F3F6FC;
    color: #243653;
}

QFrame#ozetKart,
QFrame#tabloKart {
    background: #FFFFFF;
    border: 1px solid #E3EAF5;
    border-radius: 11px;
}

QLabel#ozetBaslik {
    color: #697993;
    font-size: 12px;
    background: transparent;
    border: none;
}

QLabel#ozetDeger {
    color: #16294B;
    font-size: 25px;
    font-weight: bold;
    background: transparent;
    border: none;
}

QLabel#tabloBaslik {
    color: #0A1F5C;
    font-size: 17px;
    font-weight: bold;
    background: transparent;
    border: none;
}

QLabel#aciklama {
    color: #71829D;
    font-size: 12px;
    background: transparent;
    border: none;
}

QLineEdit,
QComboBox,
QDateEdit {
    background: #FFFFFF;
    color: #243653;
    border: 1px solid #D1DDED;
    border-radius: 8px;
    padding: 7px 10px;
    min-height: 28px;
    font-size: 13px;
}

QLineEdit:focus,
QComboBox:focus,
QDateEdit:focus {
    border: 1px solid #3778D8;
}

/* Audit ekranıyla uyumlu tarih seçicileri */
QDateEdit#auditTarih {
    background: #FFFFFF;
    color: #183461;
    border: 1px solid #D1DDED;
    border-radius: 8px;
    padding: 4px 9px;
    min-height: 25px;
    font-size: 13px;
}
QDateEdit#auditTarih:focus {
    border: 1px solid #3778D8;
    background: #FFFFFF;
}
QPushButton:disabled {
    background: #DCE6F5;
    color: #8192AD;
    border-color: #DCE6F5;
}
QLabel#puanKart {
    background: #E9F1FF;
    color: #0A1F5C;
    border: 1px solid #D6E2F5;
    border-radius: 9px;
    padding: 10px 14px;
    font-size: 15px;
    font-weight: bold;
}

QPushButton {
    background: #285CE6;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 8px 13px;
    min-height: 28px;
    font-size: 12px;
    font-weight: bold;
}

QPushButton:hover {
    background: #1E4BC5;
}

QPushButton#ikincil {
    background: #E9F1FF;
    color: #2457A2;
    border: 1px solid #D5E3F7;
}

QPushButton#ikincil:hover {
    background: #D9E8FD;
}

QPushButton#uyari {
    background: #FFF2DF;
    color: #96601B;
    border: 1px solid #F2D6AC;
}

QPushButton#uyari:hover:enabled {
    background: #FFE8C7;
}

QPushButton#uyari:disabled {
    background: #DCE6F5;
    color: #8192AD;
    border: 1px solid #DCE6F5;
}

QTableWidget {
    background: #FFFFFF;
    color: #243653;
    alternate-background-color: #F7F9FD;
    border: 1px solid #E3EAF5;
    border-radius: 7px;
    gridline-color: #E3EAF5;
    selection-background-color: #E6EEFC;
    selection-color: #173263;
    font-size: 12px;
}

QTableWidget::item {
    padding: 4px 6px;
    border-bottom: 1px solid #EDF1F7;
}

QTableWidget::item:selected {
    background: #E6EEFC;
    color: #173263;
}

QHeaderView::section {
    background: #E8F0FF;
    color: #16294B;
    border: none;
    border-right: 1px solid #D6E2F3;
    border-bottom: 1px solid #D6E2F3;
    padding: 9px 5px;
    font-size: 12px;
    font-weight: bold;
}
"""


def golge_ekle(widget):
    efekt = QGraphicsDropShadowEffect(widget)
    efekt.setBlurRadius(20)
    efekt.setOffset(0, 3)
    efekt.setColor(QColor(13, 37, 87, 18))
    widget.setGraphicsEffect(efekt)


def buton_olustur(yazi, fonksiyon, tur=None):
    btn = QPushButton(yazi)

    if tur:
        btn.setObjectName(tur)

    btn.setCursor(Qt.PointingHandCursor)
    btn.clicked.connect(fonksiyon)

    return btn


def tarih_goster(deger):
    if not deger:
        return "—"

    try:
        return date.fromisoformat(
            str(deger)[:10]
        ).strftime("%d.%m.%Y")
    except ValueError:
        return str(deger)


def tablo_hazirla(tablo, basliklar):
    tablo.setColumnCount(len(basliklar))
    tablo.setHorizontalHeaderLabels(basliklar)

    tablo.setEditTriggers(
        QAbstractItemView.NoEditTriggers
    )

    tablo.setSelectionBehavior(
        QAbstractItemView.SelectRows
    )

    tablo.setSelectionMode(
        QAbstractItemView.SingleSelection
    )

    tablo.setAlternatingRowColors(True)
    tablo.setShowGrid(False)

    tablo.verticalHeader().setVisible(False)
    tablo.verticalHeader().setDefaultSectionSize(43)

    tablo.horizontalHeader().setFixedHeight(44)

    tablo.horizontalHeader().setSectionResizeMode(
        QHeaderView.Stretch
    )


class EtiketDelegate(QStyledItemDelegate):
    """Audit ekranındaki gibi renkli durum rozeti."""

    RENKLER = {
        "active": ("#17634F", "#E8F6EF"),
        "passive": ("#9B3048", "#FCEBF0"),
        "expired": ("#96601B", "#FFF2DF"),
        "deferred": ("#285F88", "#E8F2FB"),
        "normal": ("#55708E", "#EDF3FA"),
    }

    def paint(self, painter, option, index):
        metin = str(
            index.data(Qt.DisplayRole) or ""
        )

        durum = index.data(Qt.UserRole)

        yazi_rengi, arka_plan = self.RENKLER.get(
            durum,
            self.RENKLER["normal"]
        )

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        secili = bool(
            option.state & QStyle.State_Selected
        )

        satir_rengi = (
            "#E6EEFC" if secili
            else "#FFFFFF" if index.row() % 2 == 0
            else "#F7F9FD"
        )

        painter.fillRect(
            option.rect,
            QColor(satir_rengi)
        )

        font = option.font
        font.setBold(True)
        painter.setFont(font)

        olcu = QFontMetrics(font)

        genislik = min(
            olcu.horizontalAdvance(metin) + 25,
            max(20, option.rect.width() - 12)
        )

        rozet = QRectF(
            option.rect.x()
            + (option.rect.width() - genislik) / 2,
            option.rect.y()
            + (option.rect.height() - 29) / 2,
            genislik,
            29
        )

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(arka_plan))
        painter.drawRoundedRect(rozet, 9, 9)

        painter.setPen(QColor(yazi_rengi))
        painter.drawText(
            rozet,
            Qt.AlignCenter,
            metin
        )

        painter.restore()


class OgrenciYonetimEkrani(QWidget):

    def __init__(self, api_url, token, parent=None):
        super().__init__(parent)

        self.api_url = api_url.rstrip("/")
        self.token = token
        self.kayitlar = []
        self._on_yil_uyarisi_gosterildi = False

        self.setObjectName("ogrenciYonetimi")
        self.setStyleSheet(STIL)

        ana = QVBoxLayout(self)
        ana.setContentsMargins(4, 8, 4, 8)
        ana.setSpacing(14)

        # FİLTRE ALANI
        filtreler = QHBoxLayout()
        filtreler.setSpacing(9)

        self.arama = QLineEdit()
        self.arama.setPlaceholderText(
            "Ad, öğrenci numarası veya telefon ara..."
        )
        self.arama.setClearButtonEnabled(True)
        self.arama.textChanged.connect(self.filtrele)

        self.grup = QComboBox()

        self.grup.addItem(
            "Tüm Öğrenciler", None
        )
        self.grup.addItem(
            "Gönüllü Öğrenci", "GONULLU"
        )
        self.grup.addItem(
            "Danışma Masası Öğrencisi",
            "DANISMA_MASASI"
        )

        self.grup.setCursor(Qt.PointingHandCursor)

        self.grup.currentIndexChanged.connect(
            self.filtrele
        )

        self.durum_filtresi = QComboBox()
        self.durum_filtresi.addItems([
            "Her Durum",
            "Aktif",
            "Pasif",
        ])

        self.durum_filtresi.setCursor(
            Qt.PointingHandCursor
        )

        self.durum_filtresi.currentIndexChanged.connect(
            self.filtrele
        )

        temizle = buton_olustur(
            "Filtreleri Temizle",
            self.filtreleri_temizle,
            "ikincil"
        )

        yenile = buton_olustur(
            "Yenile",
            self.yenile,
            "ikincil"
        )

        filtreler.addWidget(self.arama, 4)
        filtreler.addWidget(self.grup, 2)
        filtreler.addWidget(self.durum_filtresi, 1)
        filtreler.addWidget(temizle)
        filtreler.addWidget(yenile)

        ana.addLayout(filtreler)

        # ÖZET KARTLARI
        kartlar = QGridLayout()
        kartlar.setSpacing(12)

        self.degerler = {}

        bilgiler = [
            (
                "total",
                "Toplam Öğrenci",
                "#16294B"
            ),
            (
                "active",
                "Aktif Öğrenci",
                "#17634F"
            ),
            (
                "passive",
                "Pasif Öğrenci",
                "#9B3048"
            ),
            (
                "expired",
                "Süresi Dolan Öğrenciler",
                "#96601B"
            ),
        ]

        for sira, (anahtar, ad, renk) in enumerate(
            bilgiler
        ):
            kart = QFrame()
            kart.setObjectName("ozetKart")

            icerik = QVBoxLayout(kart)
            icerik.setContentsMargins(16, 12, 16, 12)
            icerik.setSpacing(5)

            baslik = QLabel(ad)
            baslik.setObjectName("ozetBaslik")

            deger = QLabel("0")
            deger.setObjectName("ozetDeger")
            deger.setStyleSheet(
                f"color: {renk};"
            )

            icerik.addWidget(baslik)
            icerik.addWidget(deger)

            golge_ekle(kart)

            kartlar.addWidget(kart, 0, sira)
            self.degerler[anahtar] = deger

        ana.addLayout(kartlar)

        # TABLO KARTI
        kart = QFrame()
        kart.setObjectName("tabloKart")
        golge_ekle(kart)

        yer = QVBoxLayout(kart)
        yer.setContentsMargins(16, 14, 16, 13)
        yer.setSpacing(12)

        ust = QHBoxLayout()
        ust.setSpacing(9)

        baslik_alani = QVBoxLayout()
        baslik_alani.setSpacing(4)

        baslik = QLabel("Öğrenci Listesi")
        baslik.setObjectName("tabloBaslik")

        aciklama = QLabel(
            "Öğrenci bilgileri, faaliyet puanları "
            "ve kayıt süreleri"
        )
        aciklama.setObjectName("aciklama")

        baslik_alani.addWidget(baslik)
        baslik_alani.addWidget(aciklama)

        ust.addLayout(baslik_alani)
        ust.addStretch()

        self.ekle_btn = buton_olustur(
            "＋ Öğrenci Ekle",
            self.yeni_ogrenci_ekle
        )

        self.aktiflik_btn = buton_olustur(
            "Aktiflik Düzenle",
            self.aktiflik_duzenle
        )

        self.detay_btn = buton_olustur(
            "Detay / Puanlar",
            self.detay_ac,
            "ikincil"
        )

        self.sure_btn = buton_olustur(
            "Süresi Dolan Kayıtlar",
            self.suresi_dolan_ac,
            "uyari"
        )

        ust.addWidget(self.ekle_btn)
        ust.addWidget(self.aktiflik_btn)
        ust.addWidget(self.detay_btn)
        ust.addWidget(self.sure_btn)

        yer.addLayout(ust)

        # ÖĞRENCİ TABLOSU
        self.tablo = QTableWidget()

        tablo_hazirla(self.tablo, [
            "Ad Soyad",
            "Öğrenci No",
            "Telefon",
            "Öğrenci Grubu",
            "Bağlı Hesap",
            "Kayıt Tarihi",
            "Durum",
        ])

        header = self.tablo.horizontalHeader()

        sutunlar = {
            1: 145,
            2: 130,
            5: 115,
            6: 105,
        }

        for sutun, genislik in sutunlar.items():
            header.setSectionResizeMode(
                sutun,
                QHeaderView.Fixed
            )

            self.tablo.setColumnWidth(
                sutun,
                genislik
            )

        self.tablo.setItemDelegateForColumn(
            6,
            EtiketDelegate(self.tablo)
        )

        self.tablo.cellDoubleClicked.connect(
            lambda *_: self.detay_ac()
        )

        yer.addWidget(self.tablo, 1)

        self.ozet = QLabel(
            "Öğrenciler yükleniyor..."
        )
        self.ozet.setObjectName("aciklama")

        yer.addWidget(self.ozet)
        ana.addWidget(kart, 1)

    def _istek(self, method, path, **kwargs):
        try:
            cevap = oturum_kontrollu_istek(
                method,
                f"{self.api_url}{path}",
                headers={
                    "Authorization": f"Bearer {self.token}"
                },
                timeout=15,
                **kwargs
            )

            if oturum_hatasi_mi(cevap):
                return None

            return cevap

        except Exception as hata:
            QMessageBox.warning(
                self,
                "Bağlantı Hatası",
                str(hata)
            )
            return None

    @staticmethod
    def hata(cevap):
        try:
            return str(
                cevap.json().get(
                    "detail",
                    "İşlem tamamlanamadı."
                )
            )
        except (ValueError, AttributeError):
            return (
                f"Sunucu hatası: HTTP "
                f"{cevap.status_code}"
            )

    def yenile(self):
        cevap = self._istek(
            "GET",
            "/api/ogrenciler-yonetim"
        )

        if cevap is None:
            return

        if cevap.status_code != 200:
            QMessageBox.warning(
                self,
                "Öğrenci Listesi",
                self.hata(cevap)
            )
            return

        self.kayitlar = cevap.json()
        self.filtrele()

        bekleyen = sum(
            o.get("tur") == "GONULLU"
            and o.get("kayit_suresi_doldu")
            and not o.get("ertelendi_mi")
            for o in self.kayitlar
        )

        if (
            bekleyen > 0
            and not self._on_yil_uyarisi_gosterildi
        ):
            self._on_yil_uyarisi_gosterildi = True

            QMessageBox.information(
                self,
                "10 Yıllık Kayıt Uyarısı",
                f"{bekleyen} gönüllü öğrencinin "
                "10 yıllık kayıt süresi dolmuş.\n\n"
                "İncelemek için "
                "'Süresi Dolan Kayıtlar' "
                "butonunu kullanın."
            )

    def filtreleri_temizle(self):
        self.arama.clear()
        self.grup.setCurrentIndex(0)
        self.durum_filtresi.setCurrentIndex(0)
        self.filtrele()

    def filtrele(self, *_):
        aranan = self.arama.text().strip().casefold()
        grup = self.grup.currentData()
        durum = self.durum_filtresi.currentIndex()

        kayitlar = []

        for ogrenci in self.kayitlar:
            arama_metni = " ".join(
                str(ogrenci.get(alan) or "")
                for alan in (
                    "ad_soyad",
                    "ogrenci_numarasi",
                    "telefon",
                    "kullanici_adi"
                )
            ).casefold()

            if aranan not in arama_metni:
                continue

            if grup and ogrenci["tur"] != grup:
                continue

            if durum == 1 and not ogrenci["aktif_mi"]:
                continue

            if durum == 2 and ogrenci["aktif_mi"]:
                continue

            kayitlar.append(ogrenci)

        self.tablo.setRowCount(0)
        self.tablo.setRowCount(len(kayitlar))

        for satir, ogrenci in enumerate(kayitlar):
            alanlar = [
                ogrenci.get("ad_soyad") or "—",
                ogrenci.get("ogrenci_numarasi") or "—",
                ogrenci.get("telefon") or "—",
                ogrenci.get("tur_etiketi") or "—",
                ogrenci.get("kullanici_adi") or "—",
                tarih_goster(
                    ogrenci.get("olusturulma_tarihi")
                ),
                "Aktif" if ogrenci["aktif_mi"]
                else "Pasif",
            ]

            for sutun, deger in enumerate(alanlar):
                item = QTableWidgetItem(str(deger))

                if sutun == 6:
                    item.setData(
                        Qt.UserRole,
                        "active" if ogrenci["aktif_mi"]
                        else "passive"
                    )

                else:
                    item.setData(
                        Qt.UserRole,
                        ogrenci["ogrenci_id"]
                    )

                item.setToolTip(str(deger))

                if sutun in (5, 6):
                    item.setTextAlignment(
                        Qt.AlignCenter
                    )

                self.tablo.setItem(
                    satir,
                    sutun,
                    item
                )

        toplam = len(self.kayitlar)

        aktif = sum(
            bool(o["aktif_mi"])
            for o in self.kayitlar
        )

        bekleyen = sum(
            o["tur"] == "GONULLU"
            and o.get("kayit_suresi_doldu")
            and not o.get("ertelendi_mi")
            for o in self.kayitlar
        )

        self.degerler["total"].setText(
            str(toplam)
        )

        self.degerler["active"].setText(
            str(aktif)
        )

        self.degerler["passive"].setText(
            str(toplam - aktif)
        )

        self.degerler["expired"].setText(
            str(bekleyen)
        )

        self.sure_btn.setText(
            f"Süresi Dolan Kayıtlar ({bekleyen})"
        )

        self.ozet.setText(
            f"Toplam {toplam} öğrenci • "
            f"Görüntülenen {len(kayitlar)}"
        )

    def secili_ogrenci(self):
        satir = self.tablo.currentRow()

        if satir < 0:
            QMessageBox.information(
                self,
                "Öğrenci Seç",
                "Önce listeden bir öğrenci seçin."
            )
            return None

        item = self.tablo.item(satir, 0)

        if item is None:
            return None

        ogrenci_id = item.data(Qt.UserRole)

        return next(
            (
                o for o in self.kayitlar
                if o["ogrenci_id"] == ogrenci_id
            ),
            None
        )

    def yeni_ogrenci_ekle(self):
        dialog = OgrenciEkleDialog(
            self.api_url,
            self.token,
            self
        )

        # Danışma Öğrencisi burada oluşturulmayacak.
        dialog.cb_tur.clear()

        dialog.cb_tur.addItem(
            "Gönüllü Öğrenci",
            "GONULLU"
        )


        dialog.cb_tur.setCurrentIndex(0)
        dialog.cb_tur.setCursor(
            Qt.PointingHandCursor
        )

        dialog.btn_kaydet.setCursor(
            Qt.PointingHandCursor
        )

        if dialog.exec():
            self.yenile()

    def aktiflik_duzenle(self):
        ogrenci = self.secili_ogrenci()

        if ogrenci is None:
            return

        yeni_durum = not ogrenci["aktif_mi"]

        if (
            ogrenci["tur"] == "DANISMA_MASASI"
            and not yeni_durum
        ):
            QMessageBox.information(
                self,
                "Aktiflik Düzenle",
                "Danışma Masası Öğrencileri "
                "bu ekrandan pasife alınamaz."
            )
            return

        islem = (
            "aktifleştirmek"
            if yeni_durum
            else "pasife almak"
        )

        onay = QMessageBox.question(
            self,
            "Öğrenci Aktiflik Düzenle",
            f"{ogrenci['ad_soyad']} adlı öğrenciyi "
            f"{islem} istiyor musunuz?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if onay != QMessageBox.Yes:
            return

        cevap = self._istek(
            "PATCH",
            f"/api/ogrenciler/"
            f"{ogrenci['ogrenci_id']}/aktiflik",
            json={
                "aktif_mi": yeni_durum
            }
        )

        if cevap is None:
            return

        if cevap.status_code != 200:
            QMessageBox.warning(
                self,
                "Aktiflik Düzenlenemedi",
                self.hata(cevap)
            )
            return

        self.yenile()

    def detay_ac(self):
        ogrenci = self.secili_ogrenci()

        if ogrenci is None:
            return

        pencere = QDialog(self)
        pencere.setObjectName("ogrenciDialog")
        pencere.setStyleSheet(STIL)

        pencere.setWindowTitle(
            "Öğrenci Detayı ve Faaliyet Puanları"
        )
        pencere.resize(920, 620)

        ana = QVBoxLayout(pencere)
        ana.setSpacing(13)

        baslik = QLabel(
            f"{ogrenci['ad_soyad']} • "
            f"{ogrenci['ogrenci_numarasi']}"
        )
        baslik.setObjectName("tabloBaslik")

        ana.addWidget(baslik)

        bilgi = QLabel(
            f"{ogrenci.get('tur_etiketi') or '—'}"
            f"   |   Telefon: "
            f"{ogrenci.get('telefon') or '—'}"
            f"   |   Kayıt: "
            f"{tarih_goster(ogrenci.get('olusturulma_tarihi'))}"
        )
        bilgi.setObjectName("aciklama")
        ana.addWidget(bilgi)

        tarih_satiri = QHBoxLayout()

        baslangic = QDateEdit()
        baslangic.setCalendarPopup(True)
        baslangic.setDisplayFormat("dd.MM.yyyy")
        baslangic.setObjectName("auditTarih")
        baslangic.setFixedWidth(155)
        baslangic.setDate(
            QDate.currentDate()
        )

        bitis = QDateEdit()
        bitis.setCalendarPopup(True)
        bitis.setDisplayFormat("dd.MM.yyyy")
        bitis.setObjectName("auditTarih")
        bitis.setFixedWidth(155)
        bitis.setDate(
            QDate.currentDate()
        )

        # Tarih seçimi serbesttir.
        # Geçersiz aralık, hesaplama sırasında kontrol edilir.

        toplam = QLabel("Toplam Puan: —")
        toplam.setObjectName("puanKart")

        tarih_satiri.addWidget(
            QLabel("Başlangıç:")
        )
        tarih_satiri.addWidget(baslangic)

        tarih_satiri.addWidget(
            QLabel("Bitiş:")
        )
        tarih_satiri.addWidget(bitis)

        tarih_satiri.addStretch()
        tarih_satiri.addWidget(toplam)

        ana.addLayout(tarih_satiri)

        tablo = QTableWidget()

        tablo_hazirla(tablo, [
            "Tarih",
            "Faaliyet",
            "Adet",
            "Birim",
            "Birim Puan",
            "Toplam Puan",
        ])

        ana.addWidget(tablo, 1)

        bos_faaliyet = QLabel(
            "Seçilen tarih aralığında faaliyet kaydı bulunamadı."
        )
        bos_faaliyet.setObjectName("aciklama")
        bos_faaliyet.setAlignment(Qt.AlignCenter)
        bos_faaliyet.setVisible(False)
        ana.addWidget(bos_faaliyet)

        def tarih_degisti(*_):
            toplam.setText("Toplam Puan: —")
            tablo.setRowCount(0)
            bos_faaliyet.setVisible(False)

        baslangic.dateChanged.connect(tarih_degisti)
        bitis.dateChanged.connect(tarih_degisti)

        def puanlari_hesapla():
            if baslangic.date() > bitis.date():
                QMessageBox.warning(
                    pencere,
                    "Tarih Aralığı",
                    "Bitiş tarihi başlangıç tarihinden önce olamaz. "
                    "Lütfen tarih aralığını düzeltin."
                )
                return

            cevap = self._istek(
                "GET",
                f"/api/ogrenciler/"
                f"{ogrenci['ogrenci_id']}/puanlar",
                params={
                    "baslangic":
                        baslangic.date().toString(
                            "yyyy-MM-dd"
                        ),
                    "bitis":
                        bitis.date().toString(
                            "yyyy-MM-dd"
                        ),
                }
            )

            if cevap is None:
                return

            if cevap.status_code != 200:
                QMessageBox.warning(
                    pencere,
                    "Puanlar",
                    self.hata(cevap)
                )
                return

            veri = cevap.json()

            toplam.setText(
                f"Toplam Puan: "
                f"{veri['toplam_puan']:g}"
            )

            faaliyetler = veri["faaliyetler"]

            tablo.setRowCount(len(faaliyetler))
            bos_faaliyet.setVisible(not faaliyetler)

            for satir, faaliyet in enumerate(
                faaliyetler
            ):
                alanlar = [
                    tarih_goster(faaliyet["tarih"]),
                    faaliyet["faaliyet"],
                    str(faaliyet["adet"]),
                    faaliyet["birim"],
                    str(faaliyet["birim_puan"]),
                    str(faaliyet["toplam_puan"]),
                ]

                for sutun, deger in enumerate(alanlar):
                    tablo.setItem(
                        satir,
                        sutun,
                        QTableWidgetItem(deger)
                    )

        alt = QHBoxLayout()

        alt.addWidget(
            buton_olustur(
                "Puanları Hesapla",
                puanlari_hesapla
            )
        )

        alt.addStretch()

        alt.addWidget(
            buton_olustur(
                "Kapat",
                pencere.accept,
                "ikincil"
            )
        )

        ana.addLayout(alt)

        puanlari_hesapla()
        pencere.exec()

    def suresi_dolan_ac(self):
        pencere = QDialog(self)
        pencere.setObjectName("ogrenciDialog")
        pencere.setStyleSheet(STIL)

        pencere.setWindowTitle(
            "10 Yılını Dolduran Gönüllü Öğrenciler"
        )
        pencere.resize(850, 530)

        ana = QVBoxLayout(pencere)
        ana.setSpacing(12)

        baslik = QLabel(
            "Süresi Dolan Gönüllü Öğrenci Kayıtları"
        )
        baslik.setObjectName("tabloBaslik")
        ana.addWidget(baslik)

        aciklama = QLabel(
            "Yalnızca Gönüllü Öğrenciler listelenir. "
            "Erteleme tarihi gelmeden kayıt silinemez."
        )
        aciklama.setWordWrap(True)
        aciklama.setObjectName("aciklama")

        ana.addWidget(aciklama)

        tablo = QTableWidget()

        tablo_hazirla(tablo, [
            "Ad Soyad",
            "Öğrenci No",
            "Kayıt Tarihi",
            "Erteleme Tarihi",
            "Durum",
        ])

        ana.addWidget(tablo, 1)

        bos_kayit = QLabel(
            "10 yıllık kayıt süresi dolan gönüllü öğrenci bulunmuyor."
        )
        bos_kayit.setObjectName("aciklama")
        bos_kayit.setAlignment(Qt.AlignCenter)
        bos_kayit.setVisible(False)
        ana.addWidget(bos_kayit)

        kayitlar = []

        def listeyi_yenile():
            nonlocal kayitlar

            self.yenile()

            kayitlar = [
                o for o in self.kayitlar
                if (
                    o["tur"] == "GONULLU"
                    and o.get("kayit_suresi_doldu")
                )
            ]

            tablo.clearSelection()
            tablo.setCurrentCell(-1, -1)
            tablo.setRowCount(len(kayitlar))
            bos_kayit.setVisible(not kayitlar)
            ertele_btn.setEnabled(False)
            sil_btn.setEnabled(False)

            for satir, ogrenci in enumerate(kayitlar):
                alanlar = [
                    ogrenci["ad_soyad"],
                    ogrenci["ogrenci_numarasi"],
                    tarih_goster(
                        ogrenci.get("olusturulma_tarihi")
                    ),
                    tarih_goster(
                        ogrenci.get("ertelemeye_kadar")
                    ),
                    (
                        "Ertelendi"
                        if ogrenci.get("ertelendi_mi")
                        else "İşlem Bekliyor"
                    ),
                ]

                for sutun, deger in enumerate(alanlar):
                    tablo.setItem(
                        satir,
                        sutun,
                        QTableWidgetItem(
                            str(deger)
                        )
                    )

        def secili_kayit():
            satir = tablo.currentRow()

            if satir < 0 or satir >= len(kayitlar):
                QMessageBox.information(
                    pencere,
                    "Öğrenci Seç",
                    "Önce öğrenci seçin."
                )
                return None

            return kayitlar[satir]

        def ertele():
            ogrenci = secili_kayit()

            if ogrenci is None:
                return

            secim = QDialog(pencere)
            secim.setObjectName("ogrenciDialog")
            secim.setStyleSheet(STIL)

            secim.setWindowTitle(
                "Kayıt Uyarısını Ertele"
            )

            alan = QVBoxLayout(secim)

            alan.addWidget(
                QLabel(
                    f"{ogrenci['ad_soyad']} için "
                    "yeni uyarı tarihini seçin:"
                )
            )

            tarih = QDateEdit()
            tarih.setCalendarPopup(True)
            tarih.setDisplayFormat("dd.MM.yyyy")

            tarih.setMinimumDate(
                QDate.currentDate().addDays(1)
            )

            tarih.setDate(
                QDate.currentDate().addMonths(1)
            )

            alan.addWidget(tarih)

            alan.addWidget(
                buton_olustur(
                    "Ertelemeyi Kaydet",
                    secim.accept
                )
            )

            if not secim.exec():
                return

            cevap = self._istek(
                "PATCH",
                f"/api/ogrenciler/"
                f"{ogrenci['ogrenci_id']}/silme-ertele",
                json={
                    "yeni_uyari_tarihi":
                        tarih.date().toString(
                            "yyyy-MM-dd"
                        )
                }
            )

            if cevap is None:
                return

            if cevap.status_code != 200:
                QMessageBox.warning(
                    pencere,
                    "Erteleme",
                    self.hata(cevap)
                )
                return

            listeyi_yenile()

        def sil():
            ogrenci = secili_kayit()

            if ogrenci is None:
                return

            if ogrenci.get("ertelendi_mi"):
                QMessageBox.information(
                    pencere,
                    "Kayıt Ertelendi",
                    "Erteleme tarihi gelmeden "
                    "bu kayıt silinemez."
                )
                return

            cevap = QMessageBox.warning(
                pencere,
                "Kalıcı Silme Onayı",
                f"{ogrenci['ad_soyad']} adlı "
                "gönüllü öğrencinin kaydı "
                "kalıcı olarak silinecek.\n\n"
                "Öğrencinin tüm faaliyet ve puan "
                "kayıtları da kalıcı olarak silinecek.\n\n"
                "Bu işlem geri alınamaz.\n\n"
                "Emin misiniz?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if cevap != QMessageBox.Yes:
                return

            yanit = self._istek(
                "DELETE",
                f"/api/ogrenciler/"
                f"{ogrenci['ogrenci_id']}/on-yil-sil",
                json={
                    "onayla": True
                }
            )

            if yanit is None:
                return

            if yanit.status_code != 200:
                QMessageBox.warning(
                    pencere,
                    "Kayıt Silinemedi",
                    self.hata(yanit)
                )
                return

            QMessageBox.information(
                pencere,
                "Başarılı",
                "Öğrenci kaydı silindi."
            )

            listeyi_yenile()

        alt = QHBoxLayout()

        ertele_btn = buton_olustur(
            "Seçili Öğrenciyi Ertele", ertele
        )
        sil_btn = buton_olustur(
            "Seçili Kaydı Sil", sil, "uyari"
        )

        ertele_btn.setEnabled(False)
        sil_btn.setEnabled(False)

        alt.addWidget(ertele_btn)
        alt.addWidget(sil_btn)

        def secim_degisti():
            satir = tablo.currentRow()
            gecerli = (
                0 <= satir < len(kayitlar)
                and bool(tablo.selectedItems())
            )

            if not gecerli:
                ertele_btn.setEnabled(False)
                sil_btn.setEnabled(False)
                return

            ertele_btn.setEnabled(True)

            sil_btn.setEnabled(
                not kayitlar[satir].get("ertelendi_mi")
            )

        tablo.itemSelectionChanged.connect(secim_degisti)

        alt.addStretch()

        alt.addWidget(
            buton_olustur(
                "Kapat",
                pencere.accept,
                "ikincil"
            )
        )

        ana.addLayout(alt)

        listeyi_yenile()
        pencere.exec()
