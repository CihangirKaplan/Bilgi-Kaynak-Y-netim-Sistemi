"""Yöneticinin sıfırladığı geçici parolayı gösteren pencere.

Parola okunaklı, seçilebilir ve tek tıkla kopyalanabilir. Kopyalanan parola, panoda hâlâ aynı metin duruyorsa
belirli süre sonra panodan silinir (pencere kapansa da). Pencere kapandıktan sonra parola tekrar gösterilemez.
"""
from PySide6.QtCore import QObject, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QApplication, QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout)

PANO_TEMIZLEME_SANIYE = 60

STIL = """
QDialog { background: #FFFFFF; }
QLabel#baslik { font-size: 19px; font-weight: 800; color: #0A1F5C; }
QLabel#alt { font-size: 13px; color: #5B6B8C; }
QLabel#etiket { font-size: 11px; font-weight: 800; color: #1554B7; }
QLineEdit#parola { border: 2px solid #1554B7; border-radius: 10px; padding: 12px; font-size: 22px;
                   font-weight: 700; color: #0A1F5C; background: #F6F9FF; letter-spacing: 2px; }
QLabel#durum { font-size: 12px; color: #166534; font-weight: 700; }
QLabel#not { font-size: 12px; color: #6B7FA8; }
QPushButton#birincil { background: #1554B7; color: white; border: none; border-radius: 10px;
                       padding: 11px 20px; font-size: 14px; font-weight: 700; }
QPushButton#birincil:hover { background: #0E408F; }
QPushButton#ikincil { background: #EEF3FC; color: #1554B7; border: none; border-radius: 10px;
                      padding: 11px 20px; font-size: 14px; font-weight: 700; }
QPushButton#ikincil:hover { background: #DFE9FA; }
"""


class PanoTemizleyici(QObject):
    """Kopyalanan parolayı süre dolunca, yalnızca pano hâlâ aynı metni tutuyorsa siler."""

    def __init__(self, parola, saniye, parent=None):
        super().__init__(parent)
        self.parola = parola
        self.zamanlayici = QTimer(self)
        self.zamanlayici.setSingleShot(True)
        self.zamanlayici.setInterval(int(saniye * 1000))
        self.zamanlayici.timeout.connect(self.temizle)

    def baslat(self):
        self.zamanlayici.start()

    def temizle(self):
        pano = QApplication.clipboard()
        if pano.text() == self.parola:
            pano.clear()
        self.parola = ""
        self.deleteLater()


_aktif_temizleyici = None


def panoya_kopyala_ve_zamanla(parola, saniye=PANO_TEMIZLEME_SANIYE):
    """Parolayı panoya koyar ve temizlemeyi zamanlar. Önceki zamanlayıcı varsa onu iptal eder."""
    global _aktif_temizleyici
    if _aktif_temizleyici is not None:
        try:
            _aktif_temizleyici.zamanlayici.stop()
            _aktif_temizleyici.deleteLater()
        except RuntimeError:
            pass
    QApplication.clipboard().setText(parola)
    _aktif_temizleyici = PanoTemizleyici(parola, saniye, QApplication.instance())
    _aktif_temizleyici.baslat()
    return _aktif_temizleyici


class GeciciParolaDialog(QDialog):
    def __init__(self, kullanici_adi, parola, parent=None, pano_saniye=PANO_TEMIZLEME_SANIYE):
        super().__init__(parent)
        self.parola = parola
        self.pano_saniye = pano_saniye
        self.kopyalandi = False
        self.setWindowTitle("Parola Sıfırlandı")
        self.setMinimumWidth(460)
        self.setStyleSheet(STIL)

        ana = QVBoxLayout(self)
        ana.setContentsMargins(28, 26, 28, 24)
        ana.setSpacing(12)

        baslik = QLabel("✔ Parola sıfırlandı")
        baslik.setObjectName("baslik")
        self.lbl_alt = QLabel(f"<b>{kullanici_adi}</b> kullanıcısının yeni geçici parolası aşağıdadır.")
        self.lbl_alt.setObjectName("alt")
        self.lbl_alt.setWordWrap(True)
        ana.addWidget(baslik)
        ana.addWidget(self.lbl_alt)

        etiket = QLabel("GEÇİCİ PAROLA")
        etiket.setObjectName("etiket")
        ana.addWidget(etiket)

        self.parola_kutusu = QLineEdit(parola)
        self.parola_kutusu.setObjectName("parola")
        self.parola_kutusu.setReadOnly(True)
        yazi = QFont("Consolas")
        yazi.setStyleHint(QFont.Monospace)
        self.parola_kutusu.setFont(yazi)
        ana.addWidget(self.parola_kutusu)

        self.lbl_durum = QLabel("")
        self.lbl_durum.setObjectName("durum")
        self.lbl_durum.setWordWrap(True)
        ana.addWidget(self.lbl_durum)

        self.lbl_not = QLabel(
            "Parolayı kullanıcıya güvenli şekilde iletin. Pencere kapandıktan sonra parola tekrar gösterilemez. "
            "Kullanıcı ilk girişinde yeni parola belirlemek zorundadır."
        )
        self.lbl_not.setObjectName("not")
        self.lbl_not.setWordWrap(True)
        ana.addWidget(self.lbl_not)

        satir = QHBoxLayout()
        satir.addStretch()
        self.btn_kopyala = QPushButton("Kopyala")
        self.btn_kopyala.setObjectName("birincil")
        self.btn_kopyala.clicked.connect(self.kopyala)
        self.btn_kapat = QPushButton("Kapat")
        self.btn_kapat.setObjectName("ikincil")
        self.btn_kapat.clicked.connect(self.accept)
        satir.addWidget(self.btn_kopyala)
        satir.addWidget(self.btn_kapat)
        ana.addLayout(satir)

    def kopyala(self):
        panoya_kopyala_ve_zamanla(self.parola, self.pano_saniye)
        self.kopyalandi = True
        self.lbl_durum.setText(f"✔ Kopyalandı. Pano {self.pano_saniye} saniye sonra otomatik temizlenecek.")
        self.adjustSize()
