"""Giriş ekranındaki 'Şifremi Unuttum' penceresi: kullanıcı yöneticiye parola sıfırlama talebi bildirir.

Giriş yapılmamış olduğundan istek kimliksiz gönderilir; yalnızca kullanıcı adı iletilir. Sunucu var olmayan
kullanıcı adını (404) ve pasif hesabı (403) açıkça bildirir; kullanıcı yazım hatasını hemen anlar. Pencere sonucu
sade bir dille gösterir; ağ ya da sunucu hatalarında kullanıcıya yöneticiye doğrudan ulaşmasını söyler.
"""
import requests
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout)

STIL = """
QDialog { background: #FFFFFF; }
QLabel#baslik { font-size: 20px; font-weight: 800; color: #0A1F5C; }
QLabel#alt { font-size: 13px; color: #5B6B8C; }
QLabel#adim { font-size: 13px; color: #1E2F57; padding: 2px 0; }
QLabel#etiket { font-size: 11px; font-weight: 800; color: #1554B7; }
QLineEdit { border: 1px solid #C9D6EE; border-radius: 10px; padding: 10px 12px; font-size: 14px; background: #F6F9FF; }
QLineEdit:focus { border: 1px solid #1554B7; background: white; }
QPushButton#birincil { background: #1554B7; color: white; border: none; border-radius: 10px;
                       padding: 11px 20px; font-size: 14px; font-weight: 700; }
QPushButton#birincil:hover { background: #0E408F; }
QPushButton#birincil:disabled { background: #9DB4DC; }
QPushButton#ikincil { background: #EEF3FC; color: #1554B7; border: none; border-radius: 10px;
                      padding: 11px 20px; font-size: 14px; font-weight: 700; }
QPushButton#ikincil:hover { background: #DFE9FA; }
QFrame#basari { background: #DCFCE7; border-radius: 12px; }
QLabel#basariYazi { color: #166534; font-size: 14px; font-weight: 700; }
QLabel#hata { background: #FEE2E2; color: #991B1B; border-radius: 10px; padding: 9px 12px;
              font-size: 13px; font-weight: 600; }
QLabel#not { font-size: 12px; color: #6B7FA8; }
"""

ZAMAN_ASIMI_SANIYE = 8


class ParolaTalebiDialog(QDialog):
    def __init__(self, api_url, kullanici_adi="", parent=None):
        super().__init__(parent)
        self.api_url = api_url
        self.talep_gonderildi = False
        self.setWindowTitle("Şifremi Unuttum")
        self.setMinimumWidth(460)
        self.setStyleSheet(STIL)

        ana = QVBoxLayout(self)
        ana.setContentsMargins(28, 26, 28, 24)
        ana.setSpacing(12)

        self.lbl_baslik = QLabel("Şifrenizi mi unuttunuz?")
        self.lbl_baslik.setObjectName("baslik")
        self.lbl_alt = QLabel("Sorun değil. Yöneticinize bildirin, size geçici bir şifre versin.")
        self.lbl_alt.setObjectName("alt")
        self.lbl_alt.setWordWrap(True)
        ana.addWidget(self.lbl_baslik)
        ana.addWidget(self.lbl_alt)

        self.adimlar = QLabel(
            "①  Kullanıcı adınızı yazıp <b>Yöneticiye Bildir</b>'e basın.<br><br>"
            "②  Yönetici size geçici şifrenizi iletir.<br><br>"
            "③  O şifreyle girin, yeni şifrenizi kendiniz belirleyin.")
        self.adimlar.setObjectName("adim")
        self.adimlar.setTextFormat(Qt.RichText)
        ana.addSpacing(4)
        ana.addWidget(self.adimlar)

        self.lbl_kullanici = QLabel("KULLANICI ADINIZ")
        self.lbl_kullanici.setObjectName("etiket")
        self.txt_kullanici = QLineEdit(kullanici_adi)
        self.txt_kullanici.setPlaceholderText("Kullanıcı adınızı girin")
        self.txt_kullanici.setMaxLength(100)
        self.txt_kullanici.returnPressed.connect(self.talep_gonder)
        ana.addSpacing(6)
        ana.addWidget(self.lbl_kullanici)
        ana.addWidget(self.txt_kullanici)

        self.lbl_hata = QLabel("")
        self.lbl_hata.setObjectName("hata")
        self.lbl_hata.setWordWrap(True)
        self.lbl_hata.hide()
        ana.addWidget(self.lbl_hata)

        self.kutu_basari = QFrame()
        self.kutu_basari.setObjectName("basari")
        basari_lay = QVBoxLayout(self.kutu_basari)
        basari_lay.setContentsMargins(16, 12, 16, 12)
        self.lbl_basari = QLabel("")
        self.lbl_basari.setObjectName("basariYazi")
        self.lbl_basari.setWordWrap(True)
        basari_lay.addWidget(self.lbl_basari)
        self.kutu_basari.hide()
        ana.addWidget(self.kutu_basari)

        self.lbl_not = QLabel("Yöneticinize yüz yüze ya da telefonla da bildirebilirsiniz.\n"
                              "Yönetici hesabının şifresini unuttuysanız ve başka yönetici yoksa, sunucu bilgisayarından "
                              "sistem sorumlusuna başvurun.")
        self.lbl_not.setObjectName("not")
        self.lbl_not.setWordWrap(True)
        ana.addWidget(self.lbl_not)

        dugmeler = QHBoxLayout()
        dugmeler.setSpacing(10)
        dugmeler.addStretch()
        self.btn_vazgec = QPushButton("Vazgeç")
        self.btn_vazgec.setObjectName("ikincil")
        self.btn_vazgec.setCursor(Qt.PointingHandCursor)
        self.btn_vazgec.clicked.connect(self.reject)
        self.btn_gonder = QPushButton("Yöneticiye Bildir")
        self.btn_gonder.setObjectName("birincil")
        self.btn_gonder.setCursor(Qt.PointingHandCursor)
        self.btn_gonder.setDefault(True)
        self.btn_gonder.clicked.connect(self.talep_gonder)
        dugmeler.addWidget(self.btn_vazgec)
        dugmeler.addWidget(self.btn_gonder)
        ana.addSpacing(6)
        ana.addLayout(dugmeler)

        self.txt_kullanici.setFocus(Qt.MouseFocusReason)        # yazı seçili gelmesin, imleç sonda dursun

    # ------------------------------------------------------------------ durumlar
    def hata_goster(self, metin):
        self.lbl_hata.setText("⚠  " + metin)
        self.lbl_hata.show()

    def basari_goster(self, mesaj):
        """Talep alındı: bilgi kutusunu gösterir, formu kapatıp 'Kapat' düğmesi bırakır."""
        self.talep_gonderildi = True
        self.lbl_hata.hide()
        self.lbl_basari.setText("✓  " + mesaj)
        self.kutu_basari.show()
        for parca in (self.adimlar, self.lbl_kullanici, self.txt_kullanici, self.lbl_not, self.btn_gonder):
            parca.hide()
        self.lbl_baslik.setText("Talebiniz iletildi")
        self.lbl_alt.setText("Yöneticiniz talebi gördüğünde geçici şifrenizi size verecek.")
        self.btn_vazgec.setText("Kapat")
        self.btn_vazgec.setDefault(True)
        self.adjustSize()                 # gizlenen alanların boşluğu kalmasın

    # ------------------------------------------------------------------- istek
    def talep_gonder(self):
        if self.talep_gonderildi:
            return
        kullanici = self.txt_kullanici.text().strip()
        if not kullanici:
            self.hata_goster("Lütfen kullanıcı adınızı yazın.")
            self.txt_kullanici.setFocus()
            return

        self.lbl_hata.hide()
        self.btn_gonder.setEnabled(False)
        self.btn_gonder.setText("Gönderiliyor…")
        try:
            yanit = requests.post(
                f"{self.api_url}/api/parola-sifirlama-talebi",
                json={"kullanici_adi": kullanici}, timeout=ZAMAN_ASIMI_SANIYE)
            self._yaniti_isle(yanit)
        except requests.exceptions.Timeout:
            self.hata_goster("Sunucu yanıt vermedi. Lütfen yöneticinize doğrudan ulaşın.")
        except requests.exceptions.RequestException:
            self.hata_goster("Sunucuya bağlanılamadı. Lütfen yöneticinize doğrudan ulaşın.")
        finally:
            if not self.talep_gonderildi:
                self.btn_gonder.setEnabled(True)
                self.btn_gonder.setText("Yöneticiye Bildir")

    BILINEN_HATA_KODLARI = ("KULLANICI_BULUNAMADI", "HESAP_PASIF")

    @classmethod
    def _bilinen_hata_mesaji(cls, yanit):
        """Sunucunun bu uca özgü 404/403 yanıtındaki mesaj; başka bir 404/403 (örn. eski sunucu) için None."""
        try:
            detay = yanit.json().get("detail")
        except (ValueError, AttributeError):
            return None
        if isinstance(detay, dict) and detay.get("kod") in cls.BILINEN_HATA_KODLARI and isinstance(detay.get("mesaj"), str):
            return detay["mesaj"]
        return None

    def _yaniti_isle(self, yanit):
        if yanit.status_code == 200:
            try:
                mesaj = yanit.json().get("mesaj")
            except ValueError:
                mesaj = None
            self.basari_goster(mesaj or "Talebiniz yöneticinize iletildi.")
        elif yanit.status_code == 429:
            self.hata_goster("Şu anda çok fazla bekleyen talep var. Lütfen yöneticinize doğrudan ulaşın.")
        elif yanit.status_code == 422:
            self.hata_goster("Kullanıcı adı geçersiz görünüyor. Lütfen kontrol edip tekrar deneyin.")
        elif yanit.status_code in (403, 404) and self._bilinen_hata_mesaji(yanit):
            self.hata_goster(self._bilinen_hata_mesaji(yanit))       # kullanıcı adı yok / hesap pasif
        else:
            self.hata_goster("Talep şu anda gönderilemedi. Lütfen daha sonra tekrar deneyin ya da yöneticinize ulaşın.")
