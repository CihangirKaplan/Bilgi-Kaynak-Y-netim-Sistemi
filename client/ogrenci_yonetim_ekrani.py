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

from client.api_yoneticisi import (
    api_hata_mesaji,
    hata_detayi_metni,
    oturum_kontrollu_istek,
    oturum_hatasi_mi,
)

from client.gorunum_bicimleri import telefon_goster
from client.liste_excel import listeyi_excele_aktar
from client.ogrenci_dialog import OgrenciEkleDialog
from client.tablo_siralama import siralama_durumunu_al, siralamayi_geri_yukle, siralanabilir_yap
from client.tablo_tasarimi import bos_mesaj_olustur
from client.bildirim_toast import basari_bildirimi
from client.sayfa_tema import (
    DurumRozetiDelegate, TABLO_STILI, kart_olustur, liste_sayfasi_stili, ozet_karti_olustur,
)


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


# Ana sayfadaki "Süresi Dolan Kayıtlar" düğmesi için sarı uyarı görünümü (ortak temada yok).
UYARI_DUGMESI_STILI = """
QPushButton#uyari { background: #FFF2DF; color: #96601B; border: 1px solid #F2D6AC; }
QPushButton#uyari:hover { background: #FFE8C7; border: 1px solid #E6B877; }
QPushButton#uyari:disabled { background: #F4F6FA; color: #A3B1CE; border: 1px solid #E8EDF6; }
"""


class EtiketDelegate(DurumRozetiDelegate):
    """Durum hücresini renkli rozet olarak çizer (hücrenin metni değişmez; sıralama ve arama eskisi gibi çalışır)."""

    def __init__(self, parent=None):
        super().__init__({"Aktif": ("#17634F", "#E8F6EF"), "Pasif": ("#9B3048", "#FCEBF0")}, parent)


class OgrenciYonetimEkrani(QWidget):

    def __init__(self, api_url, token, parent=None, sayfaya_git=None, kullanici_sayfasi_izinli=False, silebilir=False):
        super().__init__(parent)

        self.api_url = api_url.rstrip("/")
        self.token = token
        self._sayfaya_git = sayfaya_git                              # ana pencerenin sayfa açma işlevi
        self._kullanici_sayfasi_izinli = kullanici_sayfasi_izinli    # "Kullanıcı & Personel" sayfasına yetkisi var mı
        self.silebilir = silebilir                                   # 10 yıl sonu kalıcı silme izni (Admin, Müdür)
        self.kayitlar = []
        self.gorunen_kayitlar = []                                   # arama ve süzgeçlere uyanlar (Excel'e bunlar aktarılır)
        self._on_yil_uyarisi_gosterildi = False

        self.setObjectName("ogrenciYonetimi")
        self.setStyleSheet(liste_sayfasi_stili() + UYARI_DUGMESI_STILI)

        ana = QVBoxLayout(self)
        ana.setContentsMargins(24, 20, 24, 18)
        ana.setSpacing(16)

        # Başlık ve ana işlem
        ust = QHBoxLayout()
        ust.setSpacing(16)
        basliklar = QVBoxLayout()
        basliklar.setSpacing(3)
        sayfa_baslik = QLabel("Öğrenciler")
        sayfa_baslik.setObjectName("baslik")
        sayfa_alt = QLabel("Öğrenci bilgileri, faaliyet puanları ve kayıt süreleri.")
        sayfa_alt.setObjectName("altBaslik")
        basliklar.addWidget(sayfa_baslik)
        basliklar.addWidget(sayfa_alt)
        ust.addLayout(basliklar, 1)

        self.ekle_btn = buton_olustur("＋  Öğrenci Ekle", self.yeni_ogrenci_ekle, "birincil")
        self.ekle_btn.setMinimumHeight(40)
        ust.addWidget(self.ekle_btn, 0, Qt.AlignTop)
        ana.addLayout(ust)

        # Arama ve süzgeçler (değiştikçe liste anında süzülür)
        filtre_karti = kart_olustur()
        filtreler = QHBoxLayout(filtre_karti)
        filtreler.setContentsMargins(16, 12, 16, 12)
        filtreler.setSpacing(10)

        self.arama = QLineEdit()
        self.arama.setPlaceholderText("Ad, numara veya telefon ara...")
        self.arama.setClearButtonEnabled(True)
        self.arama.setMinimumWidth(200)
        self.arama.textChanged.connect(self.filtrele)

        self.grup = QComboBox()
        self.grup.addItem("Tüm Öğrenciler", None)
        self.grup.addItem("Gönüllü Öğrenci", "GONULLU")
        self.grup.addItem("Danışma Masası Öğrencisi", "DANISMA_MASASI")
        self.grup.addItem("Asistan Öğrenci", "ASISTAN")
        self.grup.setCursor(Qt.PointingHandCursor)
        self.grup.currentIndexChanged.connect(self.filtrele)

        self.durum_filtresi = QComboBox()
        self.durum_filtresi.addItems(["Her Durum", "Aktif", "Pasif"])
        self.durum_filtresi.setCursor(Qt.PointingHandCursor)
        self.durum_filtresi.currentIndexChanged.connect(self.filtrele)

        temizle = buton_olustur("Temizle", self.filtreleri_temizle, "hayalet")
        temizle.setToolTip("Arama ve süzgeçleri sıfırla")
        yenile = buton_olustur("⟳  Yenile", self.yenile, "hayalet")
        yenile.setToolTip("Öğrencileri sunucudan yeniden yükle")

        filtreler.addWidget(self.arama, 4)
        filtreler.addWidget(self.grup, 2)
        filtreler.addWidget(self.durum_filtresi, 1)
        filtreler.addWidget(temizle)
        filtreler.addWidget(yenile)
        ana.addWidget(filtre_karti)

        # Özet kartları
        kartlar = QGridLayout()
        kartlar.setSpacing(16)
        self.degerler = {}
        bilgiler = [
            ("total", "Toplam Öğrenci", "#1D4ED8"),
            ("active", "Aktif Öğrenci", "#0E9F6E"),
            ("passive", "Pasif Öğrenci", "#DC2626"),
            ("expired", "Süresi Dolan (İşlem Bekleyen)", "#D97706"),
        ]
        for sira, (anahtar, ad, renk) in enumerate(bilgiler):
            kart, deger = ozet_karti_olustur(ad, renk)
            kartlar.addWidget(kart, 0, sira)
            kartlar.setColumnStretch(sira, 1)
            self.degerler[anahtar] = deger
        ana.addLayout(kartlar)

        # Tablo kartı
        kart = kart_olustur()
        yer = QVBoxLayout(kart)
        yer.setContentsMargins(20, 18, 20, 14)
        yer.setSpacing(14)

        liste_ust = QHBoxLayout()
        liste_ust.setSpacing(10)
        liste_baslik = QLabel("Öğrenci Listesi")
        liste_baslik.setObjectName("kartBaslik")
        liste_ust.addWidget(liste_baslik)
        self.sayac_rozeti = QLabel("0 öğrenci")
        self.sayac_rozeti.setObjectName("rozet")
        liste_ust.addWidget(self.sayac_rozeti)
        liste_ust.addStretch()

        self.excel_btn = buton_olustur("⬇  Excel'e Aktar", self.excele_aktar, "hayalet")
        self.aktiflik_btn = buton_olustur("Aktiflik Düzenle", self.aktiflik_duzenle, "hayalet")
        self.detay_btn = buton_olustur("Detay / Puanlar", self.detay_ac, "hayalet")
        self.sure_btn = buton_olustur("Süresi Dolan Kayıtlar", self.suresi_dolan_ac, "uyari")
        for buton in (self.excel_btn, self.aktiflik_btn, self.detay_btn, self.sure_btn):
            liste_ust.addWidget(buton)
        yer.addLayout(liste_ust)

        # Öğrenci tablosu
        self.tablo = QTableWidget()
        siralanabilir_yap(self.tablo)

        tablo_hazirla(self.tablo, [
            "AD SOYAD",
            "ÖĞRENCİ NO",
            "TELEFON",
            "ÖĞRENCİ GRUBU",
            "BAĞLI HESAP",
            "KAYIT TARİHİ",
            "DURUM",
        ])
        self.tablo.setStyleSheet(TABLO_STILI)
        self.tablo.setFrameShape(QFrame.NoFrame)
        self.tablo.setAlternatingRowColors(False)
        self.tablo.setFocusPolicy(Qt.NoFocus)
        self.tablo.setWordWrap(False)
        self.tablo.setMouseTracking(True)
        self.tablo.verticalHeader().setDefaultSectionSize(52)

        header = self.tablo.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        sutunlar = {1: 130, 2: 125, 5: 118, 6: 105}
        for sutun, genislik in sutunlar.items():
            header.setSectionResizeMode(sutun, QHeaderView.Fixed)
            self.tablo.setColumnWidth(sutun, genislik)

        self.tablo.setItemDelegateForColumn(6, EtiketDelegate(self.tablo))
        self.tablo.cellDoubleClicked.connect(self.satir_cift_tiklandi)

        yer.addWidget(self.tablo, 1)
        self.bos_mesaj = bos_mesaj_olustur("Henüz öğrenci kaydı yok.")
        self.bos_mesaj.setObjectName("bosMesaj")
        self.bos_mesaj.setStyleSheet("")                                  # ortak tema (liste_sayfasi_stili) belirler
        yer.addWidget(self.bos_mesaj, 1)

        self.ozet = QLabel("Öğrenciler yükleniyor...")
        self.ozet.setObjectName("altBilgi")
        yer.addWidget(self.ozet)
        ana.addWidget(kart, 1)

    def satir_cift_tiklandi(self, *_):
        """Satıra çift tıklayınca detay açılır. (Lambda ile bağlanmaz: sayfayı tutan lambda çöp toplayıcının göremediği bir
        döngü kurar ve süreç kapanırken Qt'yi çökertir.)"""
        self.detay_ac()

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
                api_hata_mesaji(hata=hata)
            )
            return None

    @staticmethod
    def hata(cevap):
        """Sunucunun Türkçe açıklaması; liste biçimli (422) ayrıntılar da okunur metne çevrilir."""
        return hata_detayi_metni(cevap, f"İşlem tamamlanamadı (HTTP {cevap.status_code}).")

    def _bekleyen_sayisi(self):
        """10 yıllık süresi dolmuş, ertelenmemiş (işlem bekleyen) gönüllü öğrenci sayısı."""
        return sum(
            o.get("tur") == "GONULLU"
            and bool(o.get("kayit_suresi_doldu"))
            and not o.get("ertelendi_mi")
            for o in self.kayitlar
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
                api_hata_mesaji(cevap)
            )
            return

        self.kayitlar = cevap.json()
        self.filtrele()

        bekleyen = self._bekleyen_sayisi()

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

    def excele_aktar(self):
        """Ekranda görünen öğrencileri (arama ve süzgeçlere uyanları) Excel'e aktarır."""
        kayitlar = self.gorunen_kayitlar
        filtre = [
            ("Arama", self.arama.text().strip() or "Yok"),
            ("Öğrenci grubu", self.grup.currentText()),
            ("Durum", self.durum_filtresi.currentText()),
        ]
        listeyi_excele_aktar(
            self, "Öğrenci Listesi", "ogrenci_listesi",
            [("Ad Soyad", None), ("Öğrenci No", None), ("Telefon", None), ("Öğrenci Grubu", None),
             ("Bağlı Hesap", None), ("Kayıt Tarihi", None), ("Durum", None)],
            [[o.get("ad_soyad") or "", str(o.get("ogrenci_numarasi") or ""), telefon_goster(o.get("telefon"), ""),
              o.get("tur_etiketi") or "", o.get("kullanici_adi") or "", tarih_goster(o.get("olusturulma_tarihi")),
              "Aktif" if o.get("aktif_mi") else "Pasif"]
             for o in kayitlar],
            filtre, sayfa_adi="Öğrenciler", aciklama="Öğrenci Yönetimi sayfasında ekranda görünen öğrenciler.",
            kayit={"api_url": self.api_url, "token": self.token, "liste": "OGRENCI"},
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

        # Arama/süzgeç/yenileme tabloyu yeniden doldurur; kullanıcının sıralaması ve seçili öğrencisi korunur.
        siralama = siralama_durumunu_al(self.tablo)
        onceki_satir = self.tablo.item(self.tablo.currentRow(), 0)
        secili_id = onceki_satir.data(Qt.UserRole) if onceki_satir is not None else None

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
            ).casefold() + " " + telefon_goster(ogrenci.get("telefon"), "")

            if aranan not in arama_metni:
                continue

            if grup and ogrenci["tur"] != grup:
                continue

            if durum == 1 and not ogrenci["aktif_mi"]:
                continue

            if durum == 2 and ogrenci["aktif_mi"]:
                continue

            kayitlar.append(ogrenci)

        self.gorunen_kayitlar = list(kayitlar)   # Excel'e aktarılan, ekranda görünen öğrenciler

        self.tablo.setRowCount(0)
        self.tablo.setRowCount(len(kayitlar))

        for satir, ogrenci in enumerate(kayitlar):
            alanlar = [
                ogrenci.get("ad_soyad") or "—",
                ogrenci.get("ogrenci_numarasi") or "—",
                telefon_goster(ogrenci.get("telefon")),
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

                if sutun == 0:
                    yazi_tipi = item.font()
                    yazi_tipi.setBold(True)
                    item.setFont(yazi_tipi)                      # ad satırın ana bilgisi
                elif sutun != 6:
                    item.setForeground(QColor("#3B4C6B"))

                self.tablo.setItem(
                    satir,
                    sutun,
                    item
                )

        siralamayi_geri_yukle(self.tablo, siralama)
        if secili_id is not None:
            for satir in range(self.tablo.rowCount()):
                hucre = self.tablo.item(satir, 0)
                if hucre is not None and hucre.data(Qt.UserRole) == secili_id:
                    self.tablo.selectRow(satir)
                    break

        bos = not kayitlar
        self.tablo.setVisible(not bos)
        self.bos_mesaj.setVisible(bos)
        self.bos_mesaj.setText(
            "Henüz öğrenci kaydı yok." if not self.kayitlar else "Aramaya ve süzgeçlere uyan öğrenci yok."
        )

        toplam = len(self.kayitlar)

        aktif = sum(
            bool(o["aktif_mi"])
            for o in self.kayitlar
        )

        bekleyen = self._bekleyen_sayisi()

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
        self.sayac_rozeti.setText(f"{len(kayitlar)} öğrenci")

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
            self,
            kullanici_sayfasi_acilabilir=bool(self._sayfaya_git and self._kullanici_sayfasi_izinli),
        )

        # Gönüllü ve Asistan buradan eklenir; Danışma Masası öğrencisi "Kullanıcı & Personel" sayfasından oluşturulur.
        dialog.cb_tur.setCurrentIndex(0)

        if dialog.exec():
            self.yenile()
        elif dialog.sayfa_istendi and self._sayfaya_git:
            self._sayfaya_git("Kullanıcı & Personel")

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
            f"{telefon_goster(ogrenci.get('telefon'))}"
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
            QDate.currentDate().addDays(1 - QDate.currentDate().day())      # ayın ilk günü
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
            """Tarih değişince sonuç kendiliğinden yenilenir; aralık henüz geçersizse (yazarken) yalnızca temizlenir."""
            if baslangic.date() > bitis.date():
                toplam.setText("Toplam Puan: —")
                tablo.setRowCount(0)
                bos_faaliyet.setVisible(False)
                return
            puanlari_hesapla()

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

        baslangic.dateChanged.connect(tarih_degisti)
        bitis.dateChanged.connect(tarih_degisti)

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

        ozet_etiketi = QLabel("")
        ozet_etiketi.setObjectName("aciklama")
        ana.addWidget(ozet_etiketi)

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
            bekleyen = sum(1 for o in kayitlar if not o.get("ertelendi_mi"))
            ozet_etiketi.setText(
                f"{bekleyen} kayıt işlem bekliyor, {len(kayitlar) - bekleyen} kayıt ertelenmiş." if kayitlar else ""
            )
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

            basari_bildirimi(pencere, "Öğrenci kaydı silindi.")

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
        sil_btn.setVisible(self.silebilir)              # kalıcı silme ayrı bir izne bağlıdır (Admin, Müdür)

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
                self.silebilir and not kayitlar[satir].get("ertelendi_mi")
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
