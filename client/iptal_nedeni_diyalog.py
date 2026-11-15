"""Randevu iptal penceresi: hazır listeden neden (zorunlu) + isteğe bağlı kısa not ("Diğer" için zorunlu).

Not alanı bilinçli olarak kısadır (100 karakter) ve kişisel bilgi yazılmaması için uyarı gösterir (FR-008).
Liste ve sınır, sunucudaki modeller.IPTAL_NEDENLERI / IPTAL_NOTU_MAX ile aynı olmalıdır (testle denetlenir).
"""
from PySide6.QtWidgets import (QComboBox, QDialog, QFormLayout, QFrame, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QVBoxLayout)

IPTAL_NEDENLERI = [
    ("DANISAN_TALEBI", "Danışan talebi"),
    ("PSIKOLOG_MAZERETI", "Psikolog mazereti"),
    ("ODA_EKIPMAN_SORUNU", "Oda / ekipman sorunu"),
    ("HATALI_KAYIT", "Hatalı kayıt"),
    ("DIGER", "Diğer"),
]
IPTAL_NOTU_MAX = 100


def iptal_girdisi_gecerli_mi(neden, notu):
    """(geçerli_mi, mesaj): neden seçilmeli; 'Diğer' için kısa açıklama zorunlu; not 100 karakteri aşamaz."""
    if not neden:
        return False, "Lütfen iptal nedenini seçin."
    notu = (notu or "").strip()
    if neden == "DIGER" and not notu:
        return False, "'Diğer' için kısa bir açıklama yazın."
    if len(notu) > IPTAL_NOTU_MAX:
        return False, f"Not en fazla {IPTAL_NOTU_MAX} karakter olabilir."
    return True, ""


class IptalNedeniDialog(QDialog):
    def __init__(self, ebeveyn=None, randevu_kodu=None):
        super().__init__(ebeveyn)
        self.setWindowTitle("Randevu İptali")
        self.setMinimumWidth(430)
        self.setStyleSheet("""
            QDialog { background-color: #F8F9FA; font-family: 'Segoe UI', Arial; }
            QLabel { font-weight: bold; color: #0F2552; font-size: 13px; }
            QLineEdit, QComboBox {
                padding: 9px; border-radius: 6px; border: 1px solid #CBD5E1;
                background-color: white; color: #0F2552; font-size: 13px; font-weight: bold;
            }
            QComboBox QAbstractItemView {
                background-color: white; color: #0F2552;
                selection-background-color: #2563EB; selection-color: white;
            }
            QLabel#uyari { color: #B45309; font-size: 11px; font-weight: bold; }
            QLabel#hata { color: #B42318; font-size: 12px; font-weight: bold; }
        """)
        ana = QVBoxLayout(self)
        ana.setContentsMargins(15, 15, 15, 15)
        ana.setSpacing(12)

        baslik = QFrame()
        baslik.setStyleSheet("background-color: #0A1F5C; border-radius: 8px;")
        bl = QHBoxLayout(baslik)
        bl.setContentsMargins(15, 12, 15, 12)
        yazi = QLabel(f"{randevu_kodu or 'Randevu'} randevusu iptal edilecek")
        yazi.setStyleSheet("color: white; font-size: 14px; font-weight: bold; background: transparent;")
        bl.addWidget(yazi)
        ana.addWidget(baslik)

        form = QFormLayout()
        form.setSpacing(10)
        self.cmb_neden = QComboBox()
        self.cmb_neden.addItem("--- Neden Seçiniz ---", None)
        for kod, etiket in IPTAL_NEDENLERI:
            self.cmb_neden.addItem(etiket, kod)
        form.addRow("İptal Nedeni:", self.cmb_neden)

        self.txt_not = QLineEdit()
        self.txt_not.setMaxLength(IPTAL_NOTU_MAX)
        self.txt_not.setPlaceholderText("Kısa not (isteğe bağlı)")
        form.addRow("Not:", self.txt_not)
        ana.addLayout(form)

        self.lbl_uyari = QLabel("Kişisel bilgi (ad, telefon, tanı vb.) yazmayın.")
        self.lbl_uyari.setObjectName("uyari")
        ana.addWidget(self.lbl_uyari)
        self.lbl_hata = QLabel("")
        self.lbl_hata.setObjectName("hata")
        self.lbl_hata.setWordWrap(True)
        ana.addWidget(self.lbl_hata)

        butonlar = QHBoxLayout()
        butonlar.addStretch()
        btn_vazgec = QPushButton("Vazgeç")
        btn_vazgec.setFixedWidth(90)
        btn_vazgec.setStyleSheet("background-color: #E2E8F0; color: #0F2552; border-radius: 6px; padding: 8px; font-weight: bold;")
        btn_vazgec.clicked.connect(self.reject)
        self.btn_iptal_et = QPushButton("Randevuyu İptal Et")
        self.btn_iptal_et.setFixedWidth(170)
        self.btn_iptal_et.setStyleSheet(
            "QPushButton { background-color: #2563EB; color: white; border-radius: 6px; padding: 8px; font-weight: bold; }"
            "QPushButton:disabled { background-color: #CBD5E1; color: #64748B; }")
        self.btn_iptal_et.clicked.connect(self.accept)
        butonlar.addWidget(btn_vazgec)
        butonlar.addWidget(self.btn_iptal_et)
        ana.addLayout(butonlar)

        self.cmb_neden.currentIndexChanged.connect(self._dogrula)
        self.txt_not.textChanged.connect(self._dogrula)
        self._dogrula()

    def _dogrula(self, *_):
        neden = self.cmb_neden.currentData()
        self.txt_not.setPlaceholderText("Kısa açıklama (zorunlu)" if neden == "DIGER" else "Kısa not (isteğe bağlı)")
        gecerli, mesaj = iptal_girdisi_gecerli_mi(neden, self.txt_not.text())
        self.btn_iptal_et.setEnabled(gecerli)
        # Neden henüz seçilmediyse hata göstermek yerine düğme kapalı kalır
        self.lbl_hata.setText(mesaj if (neden and not gecerli) else "")

    def sonuc(self):
        """(neden_kodu, not_ya_da_None)"""
        notu = self.txt_not.text().strip()
        return self.cmb_neden.currentData(), (notu or None)
