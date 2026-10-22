import requests
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QLabel, QAbstractItemView, QInputDialog, QLineEdit
)
from PySide6.QtCore import Qt

class BirimYonetimDialog(QDialog):
    def __init__(self, api_url, token, parent=None):
        super().__init__(parent)
        self.api_url = api_url
        self.token = token

        self.setWindowTitle("Faaliyet Birimleri Yönetimi")
        self.setMinimumSize(450, 450)

        # HAYALET BUTONLARI VE SİYAH KUTULARI ÇÖZEN YENİ STİL YAPISI
        self.setStyleSheet("""
            QDialog { background-color: #F8F9FA; }
            QLabel { color: #2C3E50; font-weight: bold; font-size: 13px; }

            /* Metin giriş kutularının siyah olmasını engeller, beyaz ve okunaklı yapar */
            QLineEdit {
                background-color: white; color: #2C3E50;
                border: 1px solid #BDC3C7; border-radius: 4px; padding: 6px;
            }

            QTableWidget {
                background-color: white; color: #2C3E50;
                border: 1px solid #D0D7E5; border-radius: 4px;
            }
            QTableWidget::item:selected { background-color: #3498DB; color: white; }
            QHeaderView::section {
                background-color: #0A1F5C; color: white; font-weight: bold;
                padding: 8px; border: none;
            }

            /* GÖRÜNMEZ BUTON ÇÖZÜMÜ: Tüm standart butonlar (OK/Cancel/Yes/No) açık gri ve koyu yazılı olacak */
            QPushButton {
                font-weight: bold; padding: 8px 15px; border-radius: 4px;
                background-color: #E2E8F0; color: #1E293B; border: 1px solid #CBD5E1;
            }
            QPushButton:hover { background-color: #CBD5E1; }

            /* BİZİM ANA EKRANDAKİ ÖZEL BUTONLARIMIZ (Ekle, Düzenle, Sil) */
            QPushButton#btnStandart { background-color: #2980B9; color: white; border: none; }
            QPushButton#btnStandart:hover { background-color: #3498DB; }
            QPushButton#btnSil { background-color: #E74C3C; color: white; border: none; }
            QPushButton#btnSil:hover { background-color: #C0392B; }
        """)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Sistemde Kayıtlı Birimler:"))

        # ORTA KISIM: SADECE TABLO
        self.tablo = QTableWidget()
        self.tablo.setColumnCount(2)
        self.tablo.setHorizontalHeaderLabels(["ID", "Birim Adı"])
        self.tablo.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tablo.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tablo.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tablo.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tablo.setSelectionMode(QAbstractItemView.SingleSelection)
        layout.addWidget(self.tablo)

        # ALT KISIM: WİNDOWS STANDART KONTROL BUTONLARI
        btn_layout = QHBoxLayout()

        self.btn_ekle = QPushButton("➕ Yeni Ekle")
        self.btn_ekle.setObjectName("btnStandart")
        self.btn_ekle.setCursor(Qt.PointingHandCursor)
        self.btn_ekle.clicked.connect(self.birim_ekle)

        self.btn_duzenle = QPushButton("✎ Düzenle")
        self.btn_duzenle.setObjectName("btnStandart")
        self.btn_duzenle.setCursor(Qt.PointingHandCursor)
        self.btn_duzenle.clicked.connect(self.birim_duzenle)

        self.btn_sil = QPushButton("🗑️ Sil")
        self.btn_sil.setObjectName("btnSil")
        self.btn_sil.setCursor(Qt.PointingHandCursor)
        self.btn_sil.clicked.connect(self.birim_sil)

        btn_layout.addWidget(self.btn_ekle)
        btn_layout.addWidget(self.btn_duzenle)
        btn_layout.addWidget(self.btn_sil)

        layout.addLayout(btn_layout)

        self.verileri_yukle()

    def verileri_yukle(self):
        self.tablo.setRowCount(0)
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            res = requests.get(f"{self.api_url}/api/faaliyet-birimleri", headers=headers)
            if res.status_code == 200:
                birimler = res.json()
                self.tablo.setRowCount(len(birimler))
                for i, b in enumerate(birimler):
                    item_id = QTableWidgetItem(str(b["id"]))
                    item_id.setTextAlignment(Qt.AlignCenter)
                    item_ad = QTableWidgetItem(b["ad"])
                    self.tablo.setItem(i, 0, item_id)
                    self.tablo.setItem(i, 1, item_ad)
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Veriler yüklenemedi: {str(e)}")

    def birim_ekle(self):
        yeni_ad, ok = QInputDialog.getText(self, "Yeni Birim Ekle", "Eklenecek birim adını girin (Örn: SAAT, KİŞİ):")

        if ok and yeni_ad.strip():
            headers = {"Authorization": f"Bearer {self.token}"}
            payload = {"birim_adi": yeni_ad.strip()}
            try:
                res = requests.post(f"{self.api_url}/api/faaliyet-birimleri", json=payload, headers=headers)
                if res.status_code == 200:
                    QMessageBox.information(self, "Başarılı", "Yeni birim başarıyla eklendi!")
                    self.verileri_yukle()
                else:
                    QMessageBox.warning(self, "Hata", res.json().get("detail", "Eklenemedi."))
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Bağlantı hatası: {str(e)}")

    def birim_duzenle(self):
        secili = self.tablo.selectionModel().selectedRows()

        if not secili:
            QMessageBox.warning(self, "Seçim Yapılmadı", "Lütfen güncellemek istediğiniz kutucuğu (birimi) tablodan seçin!")
            return

        satir = secili[0].row()
        birim_id = int(self.tablo.item(satir, 0).text())
        eski_ad = self.tablo.item(satir, 1).text()

        yeni_ad, ok = QInputDialog.getText(self, "Birim Güncelle", "Yeni birim adını girin:", QLineEdit.Normal, eski_ad)

        if ok and yeni_ad.strip() and yeni_ad.strip() != eski_ad:
            headers = {"Authorization": f"Bearer {self.token}"}
            payload = {"birim_adi": yeni_ad.strip()}
            try:
                res = requests.put(f"{self.api_url}/api/faaliyet-birimleri/{birim_id}", json=payload, headers=headers)
                if res.status_code == 200:
                    QMessageBox.information(self, "Başarılı", "Birim başarıyla güncellendi!")
                    self.verileri_yukle()
                else:
                    QMessageBox.warning(self, "Hata", res.json().get("detail", "Güncellenemedi."))
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Bağlantı hatası: {str(e)}")

    def birim_sil(self):
        secili = self.tablo.selectionModel().selectedRows()
        if not secili:
            QMessageBox.warning(self, "Seçim Yapılmadı", "Lütfen silmek istediğiniz birimi tablodan seçin!")
            return

        satir = secili[0].row()
        birim_id = int(self.tablo.item(satir, 0).text())
        birim_adi = self.tablo.item(satir, 1).text()

        # SİLME ONAY KUTUSU İÇİN ÖZEL KIRMIZI BUTON TASARIMI
        soru = QMessageBox(self)
        soru.setWindowTitle("Silme Onayı")
        soru.setText(f"'{birim_adi}' birimini silmek istediğinize emin misiniz?")
        soru.setIcon(QMessageBox.Question)
        soru.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        soru.setDefaultButton(QMessageBox.No)
        soru.setStyleSheet("""
            QMessageBox { background-color: #F8F9FA; }
            QLabel { color: #2C3E50; font-size: 13px; font-weight: bold; }
            QPushButton { background-color: #E2E8F0; color: #1E293B; padding: 6px 15px; border-radius: 4px; font-weight: bold; border: 1px solid #CBD5E1; }
            QPushButton:hover { background-color: #CBD5E1; }
            /* Yes butonunu kan kırmızı yapıyoruz */
            QPushButton[text="&Yes"] { background-color: #E74C3C; color: white; border: none; }
            QPushButton[text="&Yes"]:hover { background-color: #C0392B; }
        """)
        cevap = soru.exec()

        if cevap == QMessageBox.Yes:
            headers = {"Authorization": f"Bearer {self.token}"}
            try:
                res = requests.delete(f"{self.api_url}/api/faaliyet-birimleri/{birim_id}", headers=headers)
                if res.status_code == 200:
                    QMessageBox.information(self, "Başarılı", "Birim başarıyla silindi.")
                    self.verileri_yukle()
                else:
                    QMessageBox.warning(self, "Kritik Uyarı", res.json().get("detail", "Silinemedi."))
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Bağlantı hatası: {str(e)}")