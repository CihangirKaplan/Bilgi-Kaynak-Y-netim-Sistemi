"""Danışanın yaş grubunu ve terapi türünü düzenleme penceresi (ikisi de kapalı listedir; serbest metin yok)."""
from PySide6.QtWidgets import (QComboBox, QDialog, QFormLayout, QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton,
                               QVBoxLayout)

from api_yoneticisi import api_hata_mesaji, oturum_hatasi_mi, oturum_kontrollu_istek
from siniflandirma import YAS_GRUPLARI, terapi_kutusunu_doldur


class DanisanBilgiDialog(QDialog):
    """Seçili danışanın yaş grubu ve terapi türünü günceller (eski danışanlar "Belirtilmedi" ile başlar)."""

    def __init__(self, api_url, token, danisan, ebeveyn=None):
        super().__init__(ebeveyn)
        self.api_url = api_url.rstrip("/")
        self.token = token
        self.danisan_kodu = danisan.get("danisan_kod_id")
        self.setWindowTitle("Danışan Bilgilerini Düzenle")
        self.setMinimumWidth(420)
        self.setStyleSheet("""
            QDialog { background-color: #F8F9FA; font-family: 'Segoe UI', Arial; }
            QLabel { font-weight: bold; color: #0F2552; font-size: 13px; }
            QComboBox {
                padding: 9px; border-radius: 6px; border: 1px solid #CBD5E1;
                background-color: white; color: #0F2552; font-size: 13px; font-weight: bold;
            }
            QComboBox:disabled { background-color: #F1F5F9; color: #94A3B8; }
            QComboBox QAbstractItemView {
                background-color: white; color: #0F2552; selection-background-color: #2563EB; selection-color: white;
            }
        """)
        ana = QVBoxLayout(self)
        ana.setContentsMargins(15, 15, 15, 15)
        ana.setSpacing(12)

        baslik = QFrame()
        baslik.setStyleSheet("background-color: #0A1F5C; border-radius: 8px;")
        bl = QHBoxLayout(baslik)
        bl.setContentsMargins(15, 12, 15, 12)
        yazi = QLabel(f"{self.danisan_kodu} — bilgileri")
        yazi.setStyleSheet("color: white; font-size: 14px; font-weight: bold; background: transparent;")
        bl.addWidget(yazi)
        ana.addWidget(baslik)

        form = QFormLayout()
        form.setSpacing(10)
        self.cmb_yas = QComboBox()
        self.cmb_yas.addItem("--- Yaş Grubu Seçiniz ---", None)
        for kod, etiket in YAS_GRUPLARI:
            self.cmb_yas.addItem(etiket, kod)
        form.addRow("Yaş Grubu:", self.cmb_yas)
        self.cmb_terapi = QComboBox()
        form.addRow("Terapi Türü:", self.cmb_terapi)
        ana.addLayout(form)

        butonlar = QHBoxLayout()
        butonlar.addStretch()
        btn_vazgec = QPushButton("Vazgeç")
        btn_vazgec.setFixedWidth(90)
        btn_vazgec.setStyleSheet("background-color: #E2E8F0; color: #0F2552; border-radius: 6px; padding: 8px; font-weight: bold;")
        btn_vazgec.clicked.connect(self.reject)
        self.btn_kaydet = QPushButton("Kaydet")
        self.btn_kaydet.setFixedWidth(110)
        self.btn_kaydet.setStyleSheet("background-color: #2563EB; color: white; border-radius: 6px; padding: 8px; font-weight: bold;")
        self.btn_kaydet.clicked.connect(self.kaydet)
        butonlar.addWidget(btn_vazgec)
        butonlar.addWidget(self.btn_kaydet)
        ana.addLayout(butonlar)

        self.cmb_yas.currentIndexChanged.connect(lambda *_: terapi_kutusunu_doldur(self.cmb_terapi, self.cmb_yas.currentData()))
        yas = danisan.get("yas_grubu")
        self.cmb_yas.setCurrentIndex(max(self.cmb_yas.findData(yas), 0))
        terapi_kutusunu_doldur(self.cmb_terapi, self.cmb_yas.currentData(), secili=danisan.get("terapi_turu"))

    def kaydet(self):
        yas = self.cmb_yas.currentData()
        if yas is None:
            QMessageBox.warning(self, "Yaş Grubu Seçilmedi", "Lütfen danışanın yaş grubunu seçin.")
            return
        govde = {"yas_grubu": yas, "terapi_turu": self.cmb_terapi.currentData()}
        self.btn_kaydet.setEnabled(False)
        try:
            cevap = oturum_kontrollu_istek(
                "PATCH", f"{self.api_url}/api/danisan-kodlari/{self.danisan_kodu}/bilgiler",
                json=govde, headers={"Authorization": f"Bearer {self.token}"}, timeout=5,
            )
            if oturum_hatasi_mi(cevap):
                return
            if cevap.status_code == 200:
                self.accept()
                return
            try:
                detay = cevap.json().get("detail")
            except Exception:
                detay = None
            QMessageBox.warning(
                self, "Güncellenemedi", detay if isinstance(detay, str) and cevap.status_code in (403, 404) else api_hata_mesaji(cevap)
            )
        except Exception as hata:
            QMessageBox.warning(self, "Bağlantı Hatası", api_hata_mesaji(hata=hata))
        finally:
            self.btn_kaydet.setEnabled(True)
