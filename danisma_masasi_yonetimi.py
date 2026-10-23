"""TKYS - Danışma Masası Yönetimi (Memur / Admin)."""

from datetime import datetime

import requests

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QHeaderView,
)


class DanismaMasasiYonetimi(QWidget):
    NAVY = "#16294B"
    BLUE = "#285CE6"
    MUTED = "#697993"

    def __init__(self, api_url, token, parent=None):
        super().__init__(parent)

        self.api_url = api_url.rstrip("/")
        self.token = token
        self._arayuz_kur()
        self.yenile()

        self.yenile_timer = QTimer(self)
        self.yenile_timer.setInterval(30000)
        self.yenile_timer.timeout.connect(self._otomatik_yenile)
        self.yenile_timer.start()

    def _arayuz_kur(self):
        self.setStyleSheet("""
            QWidget#danismaYonetim {
                background: #F5F7FB;
            }
            QFrame#yonetimKart {
                background: white;
                border: 1px solid #E7ECF4;
                border-radius: 14px;
            }
            QPushButton {
                background: #285CE6;
                color: white;
                padding: 10px 18px;
                border-radius: 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #1E4BC5;
            }
            QPushButton:disabled {
                background: #DCE2EB;
                color: #8491A5;
            }
            QTableWidget {
                background: white;
                border: 1px solid #E7ECF4;
                gridline-color: #E7ECF4;
            }
        """)

        self.setObjectName("danismaYonetim")

        ana = QVBoxLayout(self)
        ana.setContentsMargins(20, 20, 20, 20)
        ana.setSpacing(16)

        # Görev özet kartları
        ozet_satiri = QHBoxLayout()
        ozet_satiri.setSpacing(12)

        self.ozet_kartlari = {}

        for anahtar, baslik, renk in [
            ("toplam", "Toplam Görev", "#16294B"),
            ("aktif", "Devam Eden Görevler", "#285CE6"),
            ("bekleyen", "Onay Bekleyen", "#B86B08"),
            ("onaylanan", "Onaylanan", "#16803C"),
        ]:
            kart = QFrame()
            kart.setStyleSheet("""
                QFrame {
                    background-color: #FFFFFF;
                    border: 1px solid #E3EAF5;
                    border-radius: 10px;
                }
                QLabel {
                    border: none;
                    background: transparent;
                }
            """)

            kart_icerik = QVBoxLayout(kart)
            kart_icerik.setContentsMargins(16, 12, 16, 12)
            kart_icerik.setSpacing(5)

            baslik_etiketi = QLabel(baslik)
            baslik_etiketi.setStyleSheet(
                "font-size: 12px; color: #697993;"
            )

            sayi_etiketi = QLabel("0")
            sayi_etiketi.setStyleSheet(
                f"font-size: 25px; font-weight: bold; color: {renk};"
            )

            kart_icerik.addWidget(baslik_etiketi)
            kart_icerik.addWidget(sayi_etiketi)

            self.ozet_kartlari[anahtar] = sayi_etiketi
            ozet_satiri.addWidget(kart, 1)

        ana.addLayout(ozet_satiri)

        ust = QHBoxLayout()

        self.ozet = QLabel("Görev kayıtları yükleniyor...")
        self.ozet.setStyleSheet(
            f"font-size: 13px; font-weight: bold; color: {self.NAVY};"
        )
        ust.addWidget(self.ozet)
        ust.addStretch()

        self.ekle_btn = QPushButton("+ Yeni Görev Ekle")
        self.ekle_btn.clicked.connect(self.yeni_gorev_penceresi)
        ust.addWidget(self.ekle_btn)

        yenile_btn = QPushButton("↻ Yenile")
        yenile_btn.clicked.connect(self.yenile)
        ust.addWidget(yenile_btn)

        ana.addLayout(ust)

        kart = QFrame()
        kart.setObjectName("yonetimKart")
        kart_layout = QVBoxLayout(kart)
        kart_layout.setContentsMargins(14, 14, 14, 14)

        self.tablo = QTableWidget()
        self.tablo.setAlternatingRowColors(False)
        self.tablo.setStyleSheet("""
            QTableWidget {
                background-color: #FFFFFF;
                alternate-background-color: #FFFFFF;
                color: #243653;
                gridline-color: #E3EAF5;
                selection-background-color: #DCEAFF;
                selection-color: #16294B;
            }
            QHeaderView::section {
                background-color: #E8F0FF;
                color: #16294B;
                font-weight: bold;
                padding: 9px 5px;
                border: none;
                border-right: 1px solid #D6E2F3;
                border-bottom: 1px solid #D6E2F3;
            }
        """)
        self.tablo.verticalHeader().setDefaultSectionSize(39)
        self.tablo.setColumnCount(7)
        self.tablo.setHorizontalHeaderLabels([
            "Öğrenci",
            "Öğrenci No",
            "Başlangıç",
            "Bitiş",
            "Çalışma Süresi",
            "Görev Durumu",
            "Onay Durumu",
        ])

        self.tablo.setSelectionBehavior(
            QAbstractItemView.SelectRows
        )
        self.tablo.setSelectionMode(
            QAbstractItemView.SingleSelection
        )
        self.tablo.setEditTriggers(
            QAbstractItemView.NoEditTriggers
        )
        self.tablo.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )

        kart_layout.addWidget(self.tablo)
        ana.addWidget(kart, 1)

        alt = QHBoxLayout()
        alt.addStretch()

        self.duzenle_btn = QPushButton("✎ Seçilen Görevi Düzenle")
        self.duzenle_btn.clicked.connect(self.gorev_duzenle)
        self.duzenle_btn.setEnabled(False)
        alt.addWidget(self.duzenle_btn)

        self.onay_btn = QPushButton("✓ Seçilen Görevi Onayla")
        self.onay_btn.clicked.connect(self.gorev_onayla)
        self.onay_btn.setEnabled(False)
        alt.addWidget(self.onay_btn)

        ana.addLayout(alt)

        self.tablo.itemSelectionChanged.connect(
            self._secim_degisti
        )

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.token}"
        }

    @staticmethod
    def _tarih_bicimlendir(deger):
        if not deger:
            return "—"
        try:
            return datetime.fromisoformat(deger).strftime(
                "%d.%m.%Y %H:%M:%S"
            )
        except (ValueError, TypeError):
            return str(deger)

    def _otomatik_yenile(self):
        if not self.isVisible():
            return

        if QApplication.activeModalWidget() is not None:
            return

        self.yenile(sessiz=True)

    def yenile(self, sessiz=False):
        secili_id = None
        satir = self.tablo.currentRow()

        if satir >= 0:
            hucre = self.tablo.item(satir, 0)
            if hucre is not None:
                kayit = hucre.data(Qt.UserRole)
                if isinstance(kayit, dict):
                    secili_id = kayit.get("oturum_id")

        try:
            yanit = requests.get(
                f"{self.api_url}/api/danisma/yonetim/oturumlar",
                headers=self._headers(),
                timeout=10
            )
            yanit.raise_for_status()
            veri = yanit.json()

            oturumlar = veri.get("oturumlar", [])
            self.tablo.setRowCount(0)
            secili_satir = None

            aktif = sum(
                1 for x in oturumlar
                if x.get("bitis_zamani") is None
            )
            bekleyen = sum(
                1 for x in oturumlar
                if x.get("bitis_zamani") is not None
                and not x.get("onaylandi_mi")
            )
            onaylanan = sum(
                1 for x in oturumlar
                if x.get("onaylandi_mi")
            )

            self.ozet_kartlari["toplam"].setText(str(len(oturumlar)))
            self.ozet_kartlari["aktif"].setText(str(aktif))
            self.ozet_kartlari["bekleyen"].setText(str(bekleyen))
            self.ozet_kartlari["onaylanan"].setText(str(onaylanan))

            self.tablo.setRowCount(len(oturumlar))

            for satir, oturum in enumerate(oturumlar):
                degerler = [
                    oturum.get("ad_soyad", ""),
                    oturum.get("ogrenci_numarasi", ""),
                    self._tarih_bicimlendir(
                        oturum.get("baslangic_zamani")
                    ),
                    self._tarih_bicimlendir(
                        oturum.get("bitis_zamani")
                    ),
                    oturum.get("calisilan_sure", ""),
                    oturum.get("durum", ""),
                    (
                        "Onaylandı"
                        if oturum.get("onaylandi_mi")
                        else "Onay Bekliyor"
                    ),
                ]

                for sutun, deger in enumerate(degerler):
                    if sutun == 4:
                        saniye = oturum.get("toplam_saniye")
                        if saniye is not None:
                            toplam_dakika = max(0, int(saniye)) // 60
                            deger = (
                                f"{toplam_dakika // 60} sa "
                                f"{toplam_dakika % 60:02d} dk"
                            )

                    if sutun == 5:
                        deger = (
                            "Devam Ediyor"
                            if oturum.get("durum") == "AKTIF"
                            else "Tamamlandı"
                        )

                    hucre = QTableWidgetItem(str(deger))
                    hucre.setFlags(
                        hucre.flags() & ~Qt.ItemIsEditable
                    )

                    if sutun == 0:
                        font = hucre.font()
                        font.setBold(True)
                        hucre.setFont(font)
                        hucre.setForeground(QColor("#16294B"))

                    elif sutun == 1:
                        hucre.setForeground(QColor("#617493"))

                    elif sutun == 5:
                        renk = (
                            "#2563EB"
                            if oturum.get("durum") == "AKTIF"
                            else "#16803C"
                        )
                        hucre.setForeground(QColor(renk))
                        font = hucre.font()
                        font.setBold(True)
                        hucre.setFont(font)

                    elif sutun == 6:
                        renk = (
                            "#16803C"
                            if oturum.get("onaylandi_mi")
                            else "#B86B08"
                        )
                        hucre.setForeground(QColor(renk))
                        font = hucre.font()
                        font.setBold(True)
                        hucre.setFont(font)

                    self.tablo.setItem(satir, sutun, hucre)

                self.tablo.item(satir, 0).setData(
                    Qt.UserRole, oturum
                )

                if oturum.get("oturum_id") == secili_id:
                    secili_satir = satir

            self.ozet.setText(
                f"Toplam {len(oturumlar)} görev kaydı"
            )

            if secili_satir is not None:
                self.tablo.selectRow(secili_satir)

            self._secim_degisti()

        except requests.RequestException as hata:
            if not sessiz:
                QMessageBox.warning(
                    self,
                    "Bağlantı Hatası",
                    f"Görev kayıtları alınamadı:\n{hata}"
                )

    def _secim_degisti(self):
        satir = self.tablo.currentRow()

        if satir < 0:
            self.onay_btn.setEnabled(False)
            self.duzenle_btn.setEnabled(False)
            return

        hucre = self.tablo.item(satir, 0)
        if hucre is None:
            self.onay_btn.setEnabled(False)
            self.duzenle_btn.setEnabled(False)
            return

        oturum = hucre.data(Qt.UserRole)

        uygun = (
            isinstance(oturum, dict)
            and oturum.get("bitis_zamani") is not None
            and not oturum.get("onaylandi_mi")
        )

        self.onay_btn.setEnabled(uygun)
        self.duzenle_btn.setEnabled(uygun)

    def gorev_onayla(self):
        satir = self.tablo.currentRow()
        if satir < 0:
            return

        hucre = self.tablo.item(satir, 0)
        if hucre is None:
            return

        oturum = hucre.data(Qt.UserRole)
        if not isinstance(oturum, dict):
            return

        if (
            oturum.get("bitis_zamani") is None
            or oturum.get("onaylandi_mi")
        ):
            return

        onay_penceresi = QMessageBox(self)
        onay_penceresi.setWindowTitle("Görev Onayı")
        onay_penceresi.setText(
            "Seçilen tamamlanmış görevi onaylamak istiyor musunuz?"
        )
        onay_penceresi.setIcon(QMessageBox.Question)

        evet_btn = onay_penceresi.addButton(
            "Evet", QMessageBox.YesRole
        )
        onay_penceresi.addButton(
            "Hayır", QMessageBox.NoRole
        )

        onay_penceresi.exec()

        if onay_penceresi.clickedButton() != evet_btn:
            return

        try:
            yanit = requests.patch(
                f"{self.api_url}/api/danisma/yonetim/oturumlar/"
                f"{oturum['oturum_id']}/onayla",
                headers=self._headers(),
                timeout=10
            )
            yanit.raise_for_status()

            QMessageBox.information(
                self,
                "Başarılı",
                "Görev başarıyla onaylandı."
            )
            self.yenile()

        except requests.RequestException as hata:
            QMessageBox.warning(
                self,
                "Onay Hatası",
                f"Görev onaylanamadı:\n{hata}"
            )
    def yeni_gorev_penceresi(self):
        from PySide6.QtCore import QDateTime
        from PySide6.QtWidgets import (
            QComboBox, QDateTimeEdit, QDialog,
            QDialogButtonBox, QFormLayout
        )

        try:
            yanit = requests.get(
                f"{self.api_url}/api/danisma/yonetim/ogrenciler",
                headers=self._headers(),
                timeout=10
            )
            yanit.raise_for_status()
            ogrenciler = yanit.json().get("ogrenciler", [])
        except (requests.RequestException, ValueError) as hata:
            QMessageBox.warning(
                self, "Bağlantı Hatası",
                f"Öğrenci listesi alınamadı:\n{hata}"
            )
            return

        if not ogrenciler:
            QMessageBox.information(
                self, "Öğrenci Bulunamadı",
                "Görev eklemek için aktif öğrenci bulunamadı."
            )
            return

        pencere = QDialog(self)
        pencere.setWindowTitle("Yeni Danışma Masası Görevi")
        pencere.setMinimumWidth(440)

        form = QFormLayout(pencere)

        ogrenci_sec = QComboBox()
        for ogrenci in ogrenciler:
            ogrenci_sec.addItem(
                f"{ogrenci['ad_soyad']} - "
                f"{ogrenci['ogrenci_numarasi']}",
                ogrenci["ogrenci_id"]
            )

        baslangic = QDateTimeEdit()
        baslangic.setCalendarPopup(True)
        baslangic.setDisplayFormat("dd.MM.yyyy HH:mm")
        baslangic.setDateTime(
            QDateTime.currentDateTime().addSecs(-3600)
        )

        bitis = QDateTimeEdit()
        bitis.setCalendarPopup(True)
        bitis.setDisplayFormat("dd.MM.yyyy HH:mm")
        bitis.setDateTime(QDateTime.currentDateTime())

        form.addRow("Öğrenci:", ogrenci_sec)
        form.addRow("Başlangıç:", baslangic)
        form.addRow("Bitiş:", bitis)

        butonlar = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        butonlar.button(QDialogButtonBox.Save).setText("Kaydet")
        butonlar.button(QDialogButtonBox.Cancel).setText("İptal")

        form.addRow(butonlar)

        def kaydet():
            bas = baslangic.dateTime().toPython()
            bit = bitis.dateTime().toPython()

            if bit <= bas:
                QMessageBox.warning(
                    pencere, "Geçersiz Zaman",
                    "Bitiş zamanı başlangıçtan sonra olmalıdır."
                )
                return

            if bit > datetime.now():
                QMessageBox.warning(
                    pencere, "Geçersiz Zaman",
                    "Gelecekte biten görev kaydı oluşturulamaz."
                )
                return

            veri = {
                "ogrenci_id": ogrenci_sec.currentData(),
                "baslangic_zamani": bas.isoformat(),
                "bitis_zamani": bit.isoformat()
            }

            try:
                yanit = requests.post(
                    f"{self.api_url}/api/danisma/yonetim/oturumlar",
                    json=veri,
                    headers=self._headers(),
                    timeout=10
                )
                yanit.raise_for_status()
            except requests.HTTPError:
                try:
                    mesaj = yanit.json().get("detail", "Kayıt oluşturulamadı.")
                except ValueError:
                    mesaj = "Kayıt oluşturulamadı."
                QMessageBox.warning(pencere, "Kayıt Hatası", str(mesaj))
                return
            except requests.RequestException as hata:
                QMessageBox.warning(
                    pencere, "Bağlantı Hatası", str(hata)
                )
                return

            pencere.accept()
            self.yenile()
            QMessageBox.information(
                self, "Başarılı",
                "Yeni danışma masası görevi oluşturuldu."
            )

        butonlar.accepted.connect(kaydet)
        butonlar.rejected.connect(pencere.reject)

        pencere.exec()

    def gorev_duzenle(self):
        from PySide6.QtCore import QDateTime
        from PySide6.QtWidgets import (
            QDialog, QDateTimeEdit,
            QDialogButtonBox, QFormLayout
        )

        satir = self.tablo.currentRow()
        if satir < 0:
            return

        hucre = self.tablo.item(satir, 0)
        if hucre is None:
            return

        oturum = hucre.data(Qt.UserRole)

        if not isinstance(oturum, dict):
            return

        if oturum.get("onaylandi_mi") or not oturum.get("bitis_zamani"):
            QMessageBox.warning(
                self,
                "Düzenleme Yapılamaz",
                "Yalnızca tamamlanmış ve onay bekleyen görevler düzenlenebilir."
            )
            return

        pencere = QDialog(self)
        pencere.setWindowTitle("Danışma Masası Görev Düzenleme")
        pencere.setMinimumWidth(480)

        form = QFormLayout(pencere)

        ogrenci = QLabel(
            f"{oturum.get('ad_soyad', '')} - "
            f"{oturum.get('ogrenci_numarasi', '')}"
        )
        ogrenci.setStyleSheet(
            "font-weight: bold; color: #16294B;"
        )

        baslangic = QDateTimeEdit()
        baslangic.setCalendarPopup(True)
        baslangic.setDisplayFormat("dd.MM.yyyy HH:mm:ss")

        bitis = QDateTimeEdit()
        bitis.setCalendarPopup(True)
        bitis.setDisplayFormat("dd.MM.yyyy HH:mm:ss")

        baslangic.setDateTime(
            QDateTime.fromString(
                oturum["baslangic_zamani"][:19],
                "yyyy-MM-ddTHH:mm:ss"
            )
        )

        bitis.setDateTime(
            QDateTime.fromString(
                oturum["bitis_zamani"][:19],
                "yyyy-MM-ddTHH:mm:ss"
            )
        )

        form.addRow("Öğrenci:", ogrenci)
        form.addRow("Başlangıç:", baslangic)
        form.addRow("Bitiş:", bitis)

        butonlar = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )

        butonlar.button(QDialogButtonBox.Save).setText("Kaydet")
        butonlar.button(QDialogButtonBox.Cancel).setText("İptal")

        form.addRow(butonlar)

        def kaydet():
            bas = baslangic.dateTime().toPython()
            bit = bitis.dateTime().toPython()

            if bit <= bas:
                QMessageBox.warning(
                    pencere,
                    "Geçersiz Zaman",
                    "Bitiş zamanı başlangıçtan sonra olmalıdır."
                )
                return

            if bit > datetime.now():
                QMessageBox.warning(
                    pencere,
                    "Geçersiz Zaman",
                    "Gelecekte biten görev kaydı düzenlenemez."
                )
                return

            veri = {
                "baslangic_zamani": bas.isoformat(),
                "bitis_zamani": bit.isoformat()
            }

            try:
                yanit = requests.patch(
                    f"{self.api_url}/api/danisma/yonetim/oturumlar/"
                    f"{oturum['oturum_id']}",
                    json=veri,
                    headers=self._headers(),
                    timeout=10
                )
                yanit.raise_for_status()

            except requests.HTTPError:
                try:
                    mesaj = yanit.json().get(
                        "detail", "Görev düzenlenemedi."
                    )
                except ValueError:
                    mesaj = "Görev düzenlenemedi."

                QMessageBox.warning(
                    pencere, "Düzenleme Hatası", str(mesaj)
                )
                return

            except requests.RequestException as hata:
                QMessageBox.warning(
                    pencere, "Bağlantı Hatası", str(hata)
                )
                return

            pencere.accept()
            self.yenile()

            QMessageBox.information(
                self,
                "Başarılı",
                "Görev başarıyla güncellendi."
            )

        butonlar.accepted.connect(kaydet)
        butonlar.rejected.connect(pencere.reject)

        pencere.exec()
