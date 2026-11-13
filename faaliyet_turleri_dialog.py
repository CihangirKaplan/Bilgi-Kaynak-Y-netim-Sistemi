from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QMessageBox,
    QLineEdit, QSpinBox, QDialogButtonBox
)

from api_yoneticisi import (
    oturum_kontrollu_istek,
    oturum_hatasi_mi
)


STIL = """
QDialog {
    background-color: #F0F5FF;
}

QLabel {
    color: #0A1F5C;
    font-size: 13px;
}

QTableWidget {
    background-color: white;
    color: #243653;
    border: 1px solid #D6E2F5;
    border-radius: 6px;
    gridline-color: #E3EAF5;
}

QHeaderView::section {
    background-color: #E5EFFD;
    color: #0A1F5C;
    font-weight: bold;
    padding: 10px;
    border: 1px solid #D6E2F5;
}

QLineEdit, QSpinBox {
    background-color: white;
    color: #243653;
    border: 1px solid #D1DDED;
    border-radius: 7px;
    padding: 7px;
    min-height: 25px;
}

QLineEdit:focus, QSpinBox:focus {
    border: 1px solid #285CE6;
}

QPushButton {
    background-color: #285CE6;
    color: white;
    border: none;
    border-radius: 7px;
    padding: 10px 16px;
    font-weight: bold;
}

QPushButton:hover {
    background-color: #1E4BC5;
}

QPushButton#ikincil {
    background-color: #E8F1FF;
    color: #0A4F9B;
    border: 1px solid #D1E2FB;
}

QPushButton#ikincil:hover {
    background-color: #D8E8FF;
}
"""


class FaaliyetTurleriDialog(QDialog):

    def __init__(self, api_url, token, parent=None):
        super().__init__(parent)

        self.api_url = api_url
        self.token = token

        self.setWindowTitle("Faaliyet Türleri Yönetimi")
        self.setMinimumSize(720, 560)
        self.setStyleSheet(STIL)

        ana = QVBoxLayout(self)
        ana.setSpacing(14)

        baslik = QLabel("Faaliyet Türleri ve Puanları")
        baslik.setStyleSheet(
            "font-size: 19px; font-weight: bold;"
        )
        ana.addWidget(baslik)

        aciklama = QLabel(
            "Yeni faaliyet türü ekleyebilir ve "
            "mevcut faaliyetlerin puanlarını görüntüleyebilirsiniz."
        )
        ana.addWidget(aciklama)

        self.tablo = QTableWidget()
        self.tablo.setColumnCount(3)
        self.tablo.setHorizontalHeaderLabels(
            ["ID", "Faaliyet Türü", "Puan"]
        )

        self.tablo.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeToContents
        )
        self.tablo.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.Stretch
        )
        self.tablo.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeToContents
        )

        self.tablo.setEditTriggers(
            QAbstractItemView.NoEditTriggers
        )

        self.tablo.setSelectionBehavior(
            QAbstractItemView.SelectRows
        )

        ana.addWidget(self.tablo, 1)

        form_baslik = QLabel("Yeni Faaliyet Türü Ekle")
        form_baslik.setStyleSheet(
            "font-size: 15px; font-weight: bold;"
        )
        ana.addWidget(form_baslik)

        form = QFormLayout()

        self.ad = QLineEdit()
        self.ad.setMaxLength(100)
        self.ad.setPlaceholderText(
            "Faaliyet türünün adını girin"
        )

        self.puan = QSpinBox()
        self.puan.setRange(0, 1000000)
        self.puan.setValue(0)

        form.addRow("Faaliyet Adı:", self.ad)
        form.addRow("Puan:", self.puan)

        ana.addLayout(form)

        butonlar = QHBoxLayout()

        self.ekle_btn = QPushButton(
            "+ Yeni Faaliyet Türü Ekle"
        )
        self.ekle_btn.setCursor(Qt.PointingHandCursor)
        self.ekle_btn.clicked.connect(self.faaliyet_ekle)

        self.duzenle_btn = QPushButton(
            "✎ Seçili Faaliyeti Düzenle"
        )
        self.duzenle_btn.setObjectName("ikincil")
        self.duzenle_btn.setCursor(Qt.PointingHandCursor)
        self.duzenle_btn.clicked.connect(self.faaliyet_duzenle)

        kapat_btn = QPushButton("Kapat")
        kapat_btn.setObjectName("ikincil")
        kapat_btn.clicked.connect(self.accept)

        butonlar.addWidget(self.ekle_btn)
        butonlar.addWidget(self.duzenle_btn)
        butonlar.addStretch()
        butonlar.addWidget(kapat_btn)

        ana.addLayout(butonlar)

        self.verileri_yukle()

    def _istek(self, metot, yol, **kwargs):
        headers = {
            "Authorization": f"Bearer {self.token}"
        }

        try:
            cevap = oturum_kontrollu_istek(
                metot,
                f"{self.api_url}{yol}",
                headers=headers,
                timeout=10,
                **kwargs
            )

            if oturum_hatasi_mi(cevap):
                return None

            return cevap

        except Exception:
            QMessageBox.warning(
                self,
                "Bağlantı Hatası",
                "Sunucuya bağlanılamadı."
            )
            return None

    def verileri_yukle(self):
        cevap = self._istek(
            "GET",
            "/api/faaliyetler"
        )

        if cevap is None:
            return

        if cevap.status_code != 200:
            QMessageBox.warning(
                self,
                "Hata",
                "Faaliyet türleri yüklenemedi."
            )
            return

        faaliyetler = cevap.json()

        self.tablo.setRowCount(len(faaliyetler))

        for satir, faaliyet in enumerate(faaliyetler):
            alanlar = [
                str(faaliyet["id"]),
                faaliyet["ad"],
                str(faaliyet["puan"])
            ]

            for sutun, deger in enumerate(alanlar):
                item = QTableWidgetItem(deger)

                if sutun != 1:
                    item.setTextAlignment(Qt.AlignCenter)

                self.tablo.setItem(
                    satir, sutun, item
                )

    def faaliyet_ekle(self):
        ad = self.ad.text().strip()
        puan = self.puan.value()

        if not ad:
            QMessageBox.warning(
                self,
                "Eksik Bilgi",
                "Faaliyet adı boş olamaz."
            )
            return

        self.ekle_btn.setEnabled(False)

        try:
            cevap = self._istek(
                "POST",
                "/api/faaliyetler",
                json={
                    "faaliyet_adi": ad,
                    "puan": puan
                }
            )

            if cevap is None:
                return

            if cevap.status_code == 201:
                QMessageBox.information(
                    self,
                    "Başarılı",
                    "Yeni faaliyet türü eklendi."
                )

                self.ad.clear()
                self.puan.setValue(0)
                self.verileri_yukle()

            else:
                try:
                    mesaj = cevap.json().get(
                        "detail",
                        "Faaliyet türü eklenemedi."
                    )
                except ValueError:
                    mesaj = "Faaliyet türü eklenemedi."

                QMessageBox.warning(
                    self,
                    "Hata",
                    str(mesaj)
                )

        finally:
            self.ekle_btn.setEnabled(True)


    def faaliyet_duzenle(self):
        secili = self.tablo.selectionModel().selectedRows()

        if not secili:
            QMessageBox.warning(
                self,
                "Faaliyet Seç",
                "Lütfen düzenlemek istediğiniz faaliyet türünü seçin."
            )
            return

        satir = secili[0].row()

        faaliyet_id = int(self.tablo.item(satir, 0).text())
        eski_ad = self.tablo.item(satir, 1).text()
        eski_puan = int(self.tablo.item(satir, 2).text())

        pencere = QDialog(self)
        pencere.setWindowTitle("Faaliyet Türünü Düzenle")
        pencere.setMinimumWidth(420)
        pencere.setStyleSheet(STIL)

        ana = QVBoxLayout(pencere)

        baslik = QLabel("Seçili Faaliyet Türünü Düzenle")
        baslik.setStyleSheet(
            "font-size: 16px; font-weight: bold;"
        )
        ana.addWidget(baslik)

        form = QFormLayout()

        ad_alani = QLineEdit(eski_ad)
        ad_alani.setMaxLength(100)

        puan_alani = QSpinBox()
        puan_alani.setRange(0, 1000000)
        puan_alani.setValue(eski_puan)

        form.addRow("Faaliyet Adı:", ad_alani)
        form.addRow("Puan:", puan_alani)

        ana.addLayout(form)

        butonlar = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )

        butonlar.button(
            QDialogButtonBox.Save
        ).setText("Kaydet")

        butonlar.button(
            QDialogButtonBox.Cancel
        ).setText("Vazgeç")

        ana.addWidget(butonlar)

        def kaydet():
            yeni_ad = ad_alani.text().strip()
            yeni_puan = puan_alani.value()

            if not yeni_ad:
                QMessageBox.warning(
                    pencere,
                    "Eksik Bilgi",
                    "Faaliyet adı boş olamaz."
                )
                return

            if yeni_ad == eski_ad and yeni_puan == eski_puan:
                pencere.reject()
                return

            gecmisi_guncelle = False

            if yeni_puan != eski_puan:
                soru = QMessageBox(pencere)
                soru.setWindowTitle(
                    "Geçmiş Faaliyet Puanları"
                )
                soru.setIcon(QMessageBox.Question)
                soru.setText(
                    f"{eski_ad} faaliyetinin puanı "
                    f"{eski_puan} → {yeni_puan} "
                    "olarak değiştirilecek."
                )
                soru.setInformativeText(
                    "Bu değişiklik geçmiş öğrenci "
                    "faaliyet kayıtlarını da etkilesin mi?\n\n"
                    "Geçmiş Puanları Güncelle: "
                    "Eski kayıtların puanları da "
                    "yeni değere çevrilir.\n\n"
                    "Geçmiş Puanları Koru: "
                    "Eski kayıtlar aynı kalır, "
                    "yeni kayıtlar yeni puanı kullanır."
                )

                guncelle_btn = soru.addButton(
                    "Geçmiş Puanları Güncelle",
                    QMessageBox.ActionRole
                )

                koru_btn = soru.addButton(
                    "Geçmiş Puanları Koru",
                    QMessageBox.ActionRole
                )

                vazgec_btn = soru.addButton(
                    "Vazgeç",
                    QMessageBox.RejectRole
                )

                soru.setDefaultButton(vazgec_btn)
                soru.exec()

                secim = soru.clickedButton()

                if secim == guncelle_btn:
                    gecmisi_guncelle = True
                elif secim == koru_btn:
                    gecmisi_guncelle = False
                else:
                    return

            kaydet_btn = butonlar.button(
                QDialogButtonBox.Save
            )
            kaydet_btn.setEnabled(False)

            try:
                cevap = self._istek(
                    "PUT",
                    f"/api/faaliyetler/{faaliyet_id}",
                    json={
                        "faaliyet_adi": yeni_ad,
                        "puan": yeni_puan,
                        "gecmis_puanlari_guncelle": gecmisi_guncelle
                    }
                )

                if cevap is None:
                    return

                if cevap.status_code == 200:
                    pencere.accept()
                    self.verileri_yukle()

                    QMessageBox.information(
                        self,
                        "Başarılı",
                        "Faaliyet türü başarıyla güncellendi."
                    )
                else:
                    try:
                        mesaj = cevap.json().get(
                            "detail",
                            "Faaliyet türü güncellenemedi."
                        )
                    except ValueError:
                        mesaj = "Faaliyet türü güncellenemedi."

                    QMessageBox.warning(
                        pencere,
                        "Hata",
                        str(mesaj)
                    )

            finally:
                kaydet_btn.setEnabled(True)

        butonlar.accepted.connect(kaydet)
        butonlar.rejected.connect(pencere.reject)

        pencere.exec()
