import sys
import requests
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTableWidget, QTableWidgetItem, QHeaderView, QDialog, 
    QLineEdit, QComboBox, QMessageBox, QFormLayout
)
from PySide6.QtCore import Qt

TABLO_STIL = """
QTableWidget { background-color: white; color: #0A1F5C; border-radius: 8px; border: 1px solid #DCE7FF; }
QTableWidget::item { color: #0A1F5C; }
QHeaderView::section { background-color: #0A1F5C; color: white; padding: 8px; font-weight: bold; }
"""

class CihazIslemFormu(QDialog):
    """Cihaz Ekleme ve Düzenleme İşlemleri İçin Ortak Form"""
    def __init__(self, api_url, token, islem_turu="EKLE", cihaz_veri=None):
        super().__init__()
        self.api_url = api_url
        self.token = token
        self.islem_turu = islem_turu
        self.cihaz_veri = cihaz_veri
        
        baslik = "Yeni Cihaz Ekle" if islem_turu == "EKLE" else "Cihaz Durumunu Güncelle"
        self.setWindowTitle(f"TKYS — {baslik}")
        self.setMinimumWidth(400)
        self.setStyleSheet("* { font-family: 'Segoe UI', Arial; font-size: 13px; }")

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        
        self.txt_envanter = QLineEdit()
        self.txt_ad = QLineEdit()
        self.txt_marka = QLineEdit()
        self.txt_seri = QLineEdit()
        
        self.cmb_durum = QComboBox()
        durumlar = ["Kullanılabilir", "Rezerve", "Bakımda", "Arızalı", "Kalibrasyonda", "Kullanım Dışı"]
        self.cmb_durum.addItems(durumlar)

        self.cmb_oda = QComboBox()
        self.cmb_oda.addItem("Oda Seçiniz (Opsiyonel)", None)
        self.odalari_yukle()

        form_layout.addRow("Envanter Kodu (*):", self.txt_envanter)
        form_layout.addRow("Cihaz Adı (*):", self.txt_ad)
        form_layout.addRow("Marka / Model:", self.txt_marka)
        form_layout.addRow("Seri No:", self.txt_seri)
        form_layout.addRow("Zimmetli Oda:", self.cmb_oda)
        
        if islem_turu == "GUNCELLE":
            self.txt_envanter.setReadOnly(True)
            self.txt_envanter.setStyleSheet("background-color: #F0F0F0; color: #777;")
            form_layout.addRow("Durum (*):", self.cmb_durum)
            self.formu_doldur()
        
        layout.addLayout(form_layout)
        
        btn_layout = QHBoxLayout()
        self.btn_kaydet = QPushButton("💾 Kaydet")
        self.btn_kaydet.setStyleSheet("background-color: #27AE60; color: white; padding: 8px; border-radius: 4px; font-weight: bold;")
        self.btn_kaydet.clicked.connect(self.kaydet)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_kaydet)
        
        layout.addLayout(btn_layout)

    def odalari_yukle(self):
        try:
            cevap = requests.get(f"{self.api_url}/api/odalar", headers={"Authorization": f"Bearer {self.token}"})
            if cevap.status_code == 200:
                for oda in cevap.json():
                    if oda.get("aktif_mi"):
                        self.cmb_oda.addItem(oda["oda_adi"], oda["oda_id"])
        except:
            pass

    def formu_doldur(self):
        self.txt_envanter.setText(self.cihaz_veri.get("envanter_kodu", ""))
        self.txt_ad.setText(self.cihaz_veri.get("cihaz_adi", ""))
        self.txt_marka.setText(self.cihaz_veri.get("marka_model", ""))
        self.txt_seri.setText(self.cihaz_veri.get("seri_no", ""))
        self.cmb_durum.setCurrentText(self.cihaz_veri.get("durum", "Kullanılabilir"))

    def kaydet(self):
        if not self.txt_envanter.text().strip() or not self.txt_ad.text().strip():
            QMessageBox.warning(self, "Hata", "Envanter kodu ve cihaz adı zorunludur!")
            return

        veri = {
            "envanter_kodu": self.txt_envanter.text().strip(),
            "cihaz_adi": self.txt_ad.text().strip(),
            "marka_model": self.txt_marka.text().strip() or None,
            "seri_no": self.txt_seri.text().strip() or None,
            "durum": self.cmb_durum.currentText() if self.islem_turu == "GUNCELLE" else "Kullanılabilir"
        }
        
        secili_oda = self.cmb_oda.currentData()
        if secili_oda:
            veri["zimmetli_oda_id"] = secili_oda

        headers = {"Authorization": f"Bearer {self.token}"}
        
        try:
            if self.islem_turu == "EKLE":
                cevap = requests.post(f"{self.api_url}/api/cihazlar", json=veri, headers=headers)
            else:
                cevap = requests.patch(f"{self.api_url}/api/cihazlar/{self.cihaz_veri['cihaz_id']}", json=veri, headers=headers)
            
            if cevap.status_code in [200, 201]:
                QMessageBox.information(self, "Başarılı", "İşlem başarıyla kaydedildi.")
                self.accept()
            else:
                hata_detay = cevap.json().get('detail', 'Bilinmeyen bir hata oluştu.')
                QMessageBox.critical(self, "Hata", hata_detay)
        except Exception as e:
            QMessageBox.critical(self, "Bağlantı Hatası", f"Sunucuya ulaşılamadı: {str(e)}")

class CihazYonetimEkrani(QWidget):
    """Ana Cihaz Listesi Ekranı"""
    def __init__(self, api_url, token, yetkili_mi=False):
        super().__init__()
        self.api_url = api_url
        self.token = token
        self.yetkili_mi = yetkili_mi
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.tablo = QTableWidget()
        self.tablo.setColumnCount(6)
        self.tablo.setHorizontalHeaderLabels(["ID", "Envanter Kodu", "Cihaz Adı", "Marka/Model", "Seri No", "Durum"])
        self.tablo.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tablo.setStyleSheet(TABLO_STIL)
        self.tablo.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tablo.setSelectionBehavior(QTableWidget.SelectRows)
                    
        layout.addWidget(self.tablo)
        
        # (Eskiden burada olan alt bilgi yazısını tamamen sildik çünkü artık yukarıda harika bir kutumuz var)
        
        self.verileri_yukle()

    def verileri_yukle(self):
        self.tablo.setRowCount(0)
        try:
            cevap = requests.get(f"{self.api_url}/api/cihazlar", headers={"Authorization": f"Bearer {self.token}"})
            if cevap.status_code == 200:
                cihazlar = cevap.json()
                self.tablo.setRowCount(len(cihazlar))
                for satir, cihaz in enumerate(cihazlar):
                    self.tablo.setItem(satir, 0, QTableWidgetItem(str(cihaz["cihaz_id"])))
                    self.tablo.setItem(satir, 1, QTableWidgetItem(cihaz["envanter_kodu"]))
                    self.tablo.setItem(satir, 2, QTableWidgetItem(cihaz["cihaz_adi"]))
                    self.tablo.setItem(satir, 3, QTableWidgetItem(cihaz.get("marka_model") or "-"))
                    self.tablo.setItem(satir, 4, QTableWidgetItem(cihaz.get("seri_no") or "-"))
                    
                    durum_hucre = QTableWidgetItem(cihaz["durum"])
                    if cihaz["durum"] == "Arızalı":
                        durum_hucre.setForeground(Qt.red)
                    elif cihaz["durum"] == "Kullanılabilir":
                        durum_hucre.setForeground(Qt.darkGreen)
                    elif cihaz["durum"] == "Bakımda":
                        durum_hucre.setForeground(Qt.darkYellow)
                    durum_hucre.setFont(durum_hucre.font())
                    
                    self.tablo.setItem(satir, 5, durum_hucre)
        except Exception as e:
            pass

    def yeni_cihaz_ekle(self):
        form = CihazIslemFormu(self.api_url, self.token, islem_turu="EKLE")
        if form.exec():
            self.verileri_yukle()

    def envanter_duzenle_liste_ac(self):
        liste_formu = CihazDuzenlemeListesi(self.api_url, self.token)
        liste_formu.exec()
        # Kullanıcı düzenleme penceresini kapattığında, ana ekrandaki tabloyu da yenile:
        self.verileri_yukle()

class CihazDuzenlemeListesi(QDialog):
    """Kullanıcının cihazları listeden görüp 'Düzenle' butonuna basarak düzenlediği özel pencere"""
    def __init__(self, api_url, token, parent=None):
        super().__init__(parent)
        self.api_url = api_url
        self.token = token
        self.setWindowTitle("TKYS — Envanter Düzenleme Listesi")
        self.setMinimumSize(700, 450)
        self.setStyleSheet("* { font-family: 'Segoe UI', Arial; font-size: 13px; }")

        layout = QVBoxLayout(self)

        lbl = QLabel("✏️ <b>Düzenlemek istediğiniz cihazın sağ tarafındaki 'Düzenle' butonuna tıklayın.</b>")
        lbl.setStyleSheet("background-color: #FFF3CD; color: #856404; padding: 10px; border-radius: 5px; border: 1px solid #FFEEBA;")
        layout.addWidget(lbl)

        self.tablo = QTableWidget()
        self.tablo.setColumnCount(5)
        self.tablo.setHorizontalHeaderLabels(["ID", "Envanter Kodu", "Cihaz Adı", "Durum", "İşlem"])
        self.tablo.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tablo.setStyleSheet(TABLO_STIL)
        self.tablo.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tablo.setSelectionBehavior(QTableWidget.SelectRows)

        layout.addWidget(self.tablo)
        self.verileri_yukle()

    def verileri_yukle(self):
        self.tablo.setRowCount(0)
        try:
            cevap = requests.get(f"{self.api_url}/api/cihazlar", headers={"Authorization": f"Bearer {self.token}"})
            if cevap.status_code == 200:
                cihazlar = cevap.json()
                self.tablo.setRowCount(len(cihazlar))
                for satir, cihaz in enumerate(cihazlar):
                    self.tablo.setItem(satir, 0, QTableWidgetItem(str(cihaz["cihaz_id"])))
                    self.tablo.setItem(satir, 1, QTableWidgetItem(cihaz["envanter_kodu"]))
                    self.tablo.setItem(satir, 2, QTableWidgetItem(cihaz["cihaz_adi"]))
                    self.tablo.setItem(satir, 3, QTableWidgetItem(cihaz["durum"]))

                    # Her satırın sonuna Özel "Düzenle" Butonu Ekleme
                    btn_duzenle = QPushButton("✎ Düzenle")
                    btn_duzenle.setStyleSheet("background-color: #F39C12; color: white; border-radius: 4px; padding: 5px; font-weight: bold;")
                    btn_duzenle.setCursor(Qt.PointingHandCursor)
                    
                    # Tıklanınca formu açacak bağlantı
                    btn_duzenle.clicked.connect(lambda checked=False, c=cihaz: self.cihazi_duzenle(c))

                    hucre_widget = QWidget()
                    hucre_layout = QHBoxLayout(hucre_widget)
                    hucre_layout.setContentsMargins(4, 4, 4, 4)
                    hucre_layout.addWidget(btn_duzenle)
                    hucre_layout.setAlignment(Qt.AlignCenter)
                    
                    self.tablo.setCellWidget(satir, 4, hucre_widget)
        except Exception as e:
            pass

    def cihazi_duzenle(self, cihaz):
        form = CihazIslemFormu(self.api_url, self.token, islem_turu="GUNCELLE", cihaz_veri=cihaz)
        if form.exec():
            self.verileri_yukle() # Pencere içindeki listeyi yenile