"""Ana panel duyurusu yayınlama penceresi (yalnızca DUYURU_YONET izni olanlara açılır)."""

from client.diyalog_tabani import KaydirmaliDiyalog
from PySide6.QtCore import QDate
from PySide6.QtWidgets import (QCheckBox, QDateEdit, QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QMessageBox,
                               QPlainTextEdit, QVBoxLayout)

from client.api_yoneticisi import istek_hatasi_metni, oturum_hatasi_mi, oturum_kontrollu_istek

BASLIK_UZUNLUGU = 120
METIN_UZUNLUGU = 1000


class DuyuruDiyalogu(KaydirmaliDiyalog):
    """Başlık, metin ve (isteğe bağlı) son geçerlilik tarihi alıp sunucuya gönderir."""

    def __init__(self, api_url, token, parent=None):
        super().__init__(parent)
        self.api_url = api_url
        self.basliklar = {"Authorization": f"Bearer {token}"}
        self.setWindowTitle("Yeni Duyuru")
        self.setMinimumWidth(460)

        lay, alt_yerlesim = self.kaydirmali_kur()      # alanlar kaydırılır; düğmeler altta sabit kalır
        uyari = QLabel("Duyuru, giriş yapan herkesin ana panelinde görünür. Kişisel bilgi (danışan adı, telefon vb.) yazmayın.")
        uyari.setWordWrap(True)
        uyari.setStyleSheet("color: #854D0E; background: #FEF3C7; border-radius: 8px; padding: 8px 10px; font-size: 12px;")
        lay.addWidget(uyari)

        form = QFormLayout()
        self.txt_baslik = QLineEdit()
        self.txt_baslik.setMaxLength(BASLIK_UZUNLUGU)
        self.txt_baslik.setPlaceholderText("Örn. Yarın sistem bakımı")
        self.txt_metin = QPlainTextEdit()
        self.txt_metin.setPlaceholderText("Duyuru metni")
        self.txt_metin.setFixedHeight(110)
        self.chk_bitis = QCheckBox("Son geçerlilik tarihi olsun (sonra otomatik kalkar)")
        self.tarih_bitis = QDateEdit(QDate.currentDate().addDays(7))
        self.tarih_bitis.setCalendarPopup(True)
        self.tarih_bitis.setDisplayFormat("dd.MM.yyyy")
        self.tarih_bitis.setMinimumDate(QDate.currentDate())
        self.tarih_bitis.setEnabled(False)
        self.chk_bitis.toggled.connect(self.tarih_bitis.setEnabled)
        form.addRow("Başlık", self.txt_baslik)
        form.addRow("Metin", self.txt_metin)
        form.addRow(self.chk_bitis, self.tarih_bitis)
        lay.addLayout(form)

        self.kutu = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.kutu.button(QDialogButtonBox.Ok).setText("Yayınla")
        self.kutu.button(QDialogButtonBox.Cancel).setText("Vazgeç")
        self.kutu.accepted.connect(self.yayinla)
        self.kutu.rejected.connect(self.reject)
        alt_yerlesim.addWidget(self.kutu)

    def yayinla(self):
        baslik = self.txt_baslik.text().strip()
        metin = self.txt_metin.toPlainText().strip()
        if not baslik or not metin:
            QMessageBox.warning(self, "Eksik bilgi", "Başlık ve metin boş bırakılamaz.")
            return
        if len(metin) > METIN_UZUNLUGU:
            QMessageBox.warning(self, "Metin çok uzun", f"Metin en fazla {METIN_UZUNLUGU} karakter olabilir (şu an {len(metin)}).")
            return
        govde = {"baslik": baslik, "metin": metin, "son_gecerlilik_tarihi": None}
        if self.chk_bitis.isChecked():
            govde["son_gecerlilik_tarihi"] = self.tarih_bitis.date().toPython().isoformat()
        try:
            yanit = oturum_kontrollu_istek("POST", f"{self.api_url}/api/duyurular", json=govde, headers=self.basliklar, timeout=10)
            if oturum_hatasi_mi(yanit):
                return
            yanit.raise_for_status()
        except Exception as hata:
            QMessageBox.warning(self, "Duyuru yayınlanamadı", istek_hatasi_metni(hata, "Duyuru yayınlanamadı."))
            return
        self.accept()


def duyuru_kaldir(api_url, token, duyuru_id, parent=None):
    """Onay alıp duyuruyu kaldırır; kaldırıldıysa True."""
    cevap = QMessageBox.question(parent, "Duyuruyu kaldır", "Bu duyuru herkesin ana panelinden kaldırılsın mı?",
                                 QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
    if cevap != QMessageBox.Yes:
        return False
    try:
        yanit = oturum_kontrollu_istek("DELETE", f"{api_url}/api/duyurular/{int(duyuru_id)}",
                                       headers={"Authorization": f"Bearer {token}"}, timeout=10)
        if oturum_hatasi_mi(yanit):
            return False
        yanit.raise_for_status()
    except Exception as hata:
        QMessageBox.warning(parent, "Duyuru kaldırılamadı", istek_hatasi_metni(hata, "Duyuru kaldırılamadı."))
        return False
    return True
