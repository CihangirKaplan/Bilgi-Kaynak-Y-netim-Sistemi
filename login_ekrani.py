import os
import sys
import requests
import base64
import re
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QFrame, QPushButton, QCheckBox, QGraphicsDropShadowEffect, QMessageBox
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPixmap
from main_window import AnaPencere
from sifre_degistir_ekrani import SifreDegistirEkrani
import faulthandler, traceback
faulthandler.enable()

def hata_yakala(tip, deger, tb):
    metin = "".join(traceback.format_exception(tip, deger, tb))
    print(metin)
    QMessageBox.critical(None, "Beklenmeyen Hata", metin)

sys.excepthook = hata_yakala

# ======================================================================
#  TEMA VE SABİTLER
# ======================================================================
API_URL = os.getenv("TKYS_API_URL", "http://127.0.0.1:8000") # Sunucu adresimiz
MAX_DENEME = 5

STIL = """
QWidget#kok {
    background: #E8F0FB;
    font-family: Arial;
}

QFrame#loginKart {
    background: #FFFFFF;
    border-radius: 22px;
}

QFrame#marka {
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0 #082856,
        stop:0.50 #0B428E,
        stop:1 #086DE2
    );
    border-top-left-radius: 22px;
    border-bottom-left-radius: 22px;
}

QLabel#neuLogo {
    background: transparent;
}

QLabel#logoYazi {
    color: white;
    background: transparent;
    font-size: 33px;
    font-weight: 800;
    letter-spacing: 3px;
}

QLabel#markaBaslik {
    color: #E7F1FF;
    background: transparent;
    font-size: 17px;
    font-weight: 600;
}

QLabel#markaAltBilgi {
    color: #BAD6FC;
    background: transparent;
    font-size: 11px;
}

QFrame#form {
    background: white;
    border-top-right-radius: 22px;
    border-bottom-right-radius: 22px;
}

QLabel#hosgeldin {
    color: #102A56;
    font-size: 27px;
    font-weight: 800;
    background: transparent;
}

QLabel#hosgeldinAlt {
    color: #7187A7;
    font-size: 13px;
    background: transparent;
}

QLabel#etiket {
    color: #325381;
    font-size: 11px;
    font-weight: 700;
    background: transparent;
}

QLineEdit {
    background: #F8FAFF;
    color: #102A56;
    border: 1px solid #CCDDF2;
    border-radius: 10px;
    padding: 12px 14px;
    font-size: 14px;
}

QLineEdit:hover {
    border: 1px solid #98B9E7;
}

QLineEdit:focus {
    background: white;
    border: 2px solid #2776DD;
}

QCheckBox {
    color: #6B7FA8;
    font-size: 12px;
    background: transparent;
}


/* TKYS_LOGIN_CHECKBOX_V1 */
QCheckBox {
    color: #516B91;
    font-size: 12px;
    spacing: 9px;
    background: transparent;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 1px solid #96B0D1;
    border-radius: 5px;
    background: #FFFFFF;
}

QCheckBox::indicator:hover {
    border: 1px solid #3578D4;
    background: #F0F6FF;
}

QCheckBox::indicator:checked {
    background: #1554B7;
    border: 1px solid #1554B7;
    image: url("__TKYS_CHECK_ICON__");
}

QCheckBox::indicator:disabled {
    background: #E5EAF2;
    border: 1px solid #C5D1E0;
}

QLabel#hata {
    color: #A92828;
    background: #FEEBEC;
    border-radius: 8px;
    padding: 9px 12px;
    font-size: 12px;
    font-weight: 600;
}

QPushButton#giris {
    background: #1554B7;
    color: white;
    border: none;
    border-radius: 10px;
    padding: 13px;
    font-size: 14px;
    font-weight: 700;
}

QPushButton#giris:hover {
    background: #2068D3;
}

QPushButton#giris:pressed {
    background: #0E408F;
}

QPushButton#giris:disabled {
    background: #9CB5D8;
    color: #F8FAFF;
}

QLabel#guvenlik {
    color: #899BB4;
    font-size: 11px;
    background: transparent;
}
"""

class LoginEkrani(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("kok")
        self.setWindowTitle("TKYS — Güvenli Giriş")
        self.setFixedSize(980, 720)
        self.setStyleSheet(
            STIL.replace(
                "__TKYS_CHECK_ICON__",
                os.path.join(
                    os.path.dirname(os.path.abspath(__file__)),
                    "assets",
                    "tkys_checkbox_check.svg"
                )
            )
        )
        self.ana_pencere = None
        self.hatali_deneme = 0
        self.kalan = 0

        kok = QVBoxLayout(self)
        kok.setContentsMargins(40, 40, 40, 40)

        kart = QFrame()
        kart.setObjectName("loginKart")
        golge = QGraphicsDropShadowEffect(kart)
        golge.setBlurRadius(50)
        golge.setOffset(0, 14)
        golge.setColor(QColor(10, 31, 92, 70))
        kart.setGraphicsEffect(golge)
        kl = QHBoxLayout(kart)
        kl.setContentsMargins(0, 0, 0, 0)
        kl.setSpacing(0)

        # SOL: MARKA PANELİ — TKYS_LOGIN_TASARIM_V1
        marka = QFrame()
        marka.setObjectName("marka")
        marka.setFixedWidth(380)

        ml = QVBoxLayout(marka)
        ml.setContentsMargins(32, 34, 32, 30)
        ml.setSpacing(0)

        logo_dosyasi = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "assets",
            "tkys_travma_logo.png"
        )

        pix = QPixmap(logo_dosyasi)

        if pix.isNull():
            raise FileNotFoundError(
                f"Giriş logosu yüklenemedi: {logo_dosyasi}"
            )

        ml.addStretch(2)

        logo = QLabel()
        logo.setObjectName("neuLogo")
        logo.setAlignment(Qt.AlignCenter)

        logo.setPixmap(
            pix.scaled(
                152,
                152,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
        )

        ml.addWidget(logo)
        ml.addSpacing(19)

        sistem = QLabel("TKYS")
        sistem.setObjectName("logoYazi")
        sistem.setAlignment(Qt.AlignCenter)

        ml.addWidget(sistem)
        ml.addSpacing(8)

        baslik = QLabel("Travma Kaynak\nYönetim Sistemi")
        baslik.setObjectName("markaBaslik")
        baslik.setAlignment(Qt.AlignCenter)

        ml.addWidget(baslik)
        ml.addStretch(3)

        alt_bilgi = QLabel(
            "NEÜ TRAUM  •  Kurumsal Yönetim Sistemi"
        )
        alt_bilgi.setObjectName("markaAltBilgi")
        alt_bilgi.setAlignment(Qt.AlignCenter)

        ml.addWidget(alt_bilgi)
        kl.addWidget(marka)

        # SAĞ: FORM
        form = QFrame()
        form.setObjectName("form")
        fl = QVBoxLayout(form)
        fl.setContentsMargins(54, 48, 54, 36)
        fl.setSpacing(6)

        h1 = QLabel("Hoş Geldiniz")
        h1.setObjectName("hosgeldin")
        h2 = QLabel("Yetkili hesabınızla devam edin.")
        h2.setObjectName("hosgeldinAlt")
        fl.addWidget(h1)
        fl.addWidget(h2)
        fl.addSpacing(22)

        e1 = QLabel("KULLANICI ADI")
        e1.setObjectName("etiket")
        self.kullanici_input = QLineEdit()
        self.kullanici_input.setPlaceholderText("Kullanıcı adınızı girin")
        fl.addWidget(e1)
        fl.addWidget(self.kullanici_input)
        fl.addSpacing(10)

        e2 = QLabel("ŞİFRE")
        e2.setObjectName("etiket")
        self.sifre_input = QLineEdit()
        self.sifre_input.setEchoMode(QLineEdit.Password)
        self.sifre_input.setPlaceholderText("••••••••")
        fl.addWidget(e2)
        fl.addWidget(self.sifre_input)

        self.goster = QCheckBox("Şifreyi göster")
        self.goster.toggled.connect(
            lambda v: self.sifre_input.setEchoMode(QLineEdit.Normal if v else QLineEdit.Password))
        fl.addSpacing(4)
        fl.addWidget(self.goster)

        # CAPTCHA GÜVENLİK KODU
        fl.addSpacing(10)

        captcha_etiket = QLabel("GÜVENLİK KODU")
        captcha_etiket.setObjectName("etiket")
        fl.addWidget(captcha_etiket)

        captcha_satiri = QHBoxLayout()
        captcha_satiri.setSpacing(10)

        self.captcha_resim = QLabel()
        self.captcha_resim.setFixedSize(180, 54)
        self.captcha_resim.setAlignment(Qt.AlignCenter)
        self.captcha_resim.setStyleSheet(
            "background: #EDF4FF;"
            "border: 1px solid #D6E4F5;"
            "border-radius: 8px;"
        )
        captcha_satiri.addWidget(self.captcha_resim)

        self.captcha_yenile_btn = QPushButton("↻")
        self.captcha_yenile_btn.setToolTip("Yeni güvenlik kodu al")
        self.captcha_yenile_btn.setFixedSize(36, 36)
        self.captcha_yenile_btn.setCursor(Qt.PointingHandCursor)
        self.captcha_yenile_btn.setStyleSheet("""
            QPushButton {
                background: #E8F0FB;
                color: #1554B7;
                border: 1px solid #C8D9F0;
                border-radius: 9px;
                font-size: 25px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #D8E8FF;
            }
        """)
        self.captcha_yenile_btn.clicked.connect(self.captcha_yenile)

        captcha_satiri.addWidget(self.captcha_yenile_btn)
        captcha_satiri.addStretch()

        fl.addLayout(captcha_satiri)

        self.captcha_input = QLineEdit()
        self.captcha_input.setPlaceholderText(
            "Görseldeki 5 haneli güvenlik kodunu girin"
        )
        self.captcha_input.setMaxLength(5)
        self.captcha_input.setMaximumWidth(300)
        self.captcha_input.setEnabled(False)
        fl.addWidget(self.captcha_input)

        self.captcha_id = None

        self.captcha_sure_timer = QTimer(self)
        self.captcha_sure_timer.setSingleShot(True)
        self.captcha_sure_timer.timeout.connect(
            self.captcha_yenile
        )

        self.hata_lbl = QLabel("")
        self.hata_lbl.setObjectName("hata")
        self.hata_lbl.setWordWrap(True)
        self.hata_lbl.hide()
        fl.addSpacing(6)
        fl.addWidget(self.hata_lbl)

        fl.addSpacing(10)
        self.giris_btn = QPushButton("GÜVENLİ OTURUM AÇ")
        self.giris_btn.setObjectName("giris")
        self.giris_btn.setCursor(Qt.PointingHandCursor)
        self.giris_btn.clicked.connect(self.giris_yap)
        fl.addWidget(self.giris_btn)

        fl.addStretch()
        g = QLabel("🔒  Yetkisiz erişim denemeleri kayıt altına alınır.")
        g.setObjectName("guvenlik")
        g.setAlignment(Qt.AlignCenter)
        fl.addWidget(g)
        kl.addWidget(form, 1)

        kok.addWidget(kart)

        self.kullanici_input.returnPressed.connect(self.sifre_input.setFocus)
        self.sifre_input.returnPressed.connect(
            self.captcha_input.setFocus
        )
        self.captcha_input.returnPressed.connect(self.giris_yap)

        self.giris_btn.setEnabled(False)
        QTimer.singleShot(0, self.captcha_yenile)
        self.kullanici_input.setFocus()

    def hata_goster(self, metin):
        self.hata_lbl.setText("⚠  " + metin)
        self.hata_lbl.show()

    def rol_adindan_koda(self, rol_id):
        roller = {1: "psikolog", 2: "memur", 3: "mudur", 4: "ogrenci", 5: "asistan", 6: "admin"}
        return roller.get(rol_id, None)

    def captcha_yenile(self):
        """Sunucudan yeni CAPTCHA görseli al."""
        self.captcha_sure_timer.stop()
        self.captcha_id = None
        self.captcha_input.clear()
        self.captcha_input.setEnabled(False)
        self.captcha_resim.clear()
        self.giris_btn.setEnabled(False)
        self.captcha_yenile_btn.setEnabled(False)

        try:
            cevap = requests.get(
                f"{API_URL}/api/captcha",
                timeout=5,
            )
            cevap.raise_for_status()
            veri = cevap.json()

            captcha_id = veri["captcha_id"]
            if not (
                isinstance(captcha_id, str)
                and re.fullmatch(r"[0-9a-f]{32}", captcha_id)
            ):
                raise ValueError("Geçersiz CAPTCHA kimliği")

            resim_verisi = base64.b64decode(
                veri["gorsel_base64"],
                validate=True,
            )

            pixmap = QPixmap()
            if not pixmap.loadFromData(resim_verisi, "PNG"):
                raise ValueError("CAPTCHA görseli yüklenemedi")

            sure = int(veri["gecerlilik_saniye"])

            if not 15 <= sure <= 600:
                raise ValueError("Geçersiz CAPTCHA süresi")

            self.captcha_id = captcha_id

            # Sunucudaki süreden 10 saniye önce yenile.
            self.captcha_sure_timer.start(
                max(1000, (sure - 10) * 1000)
            )

            self.captcha_resim.setPixmap(
                pixmap.scaled(
                    self.captcha_resim.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
            )

        except requests.HTTPError as hata:
            yanit = hata.response

            if yanit is not None and yanit.status_code == 429:
                sure = yanit.headers.get("Retry-After", "")
                saniye = int(sure) if sure.isdigit() else 60

                self.hata_goster(
                    "Çok fazla güvenlik kodu istendi. "
                    f"Lütfen {saniye} saniye sonra tekrar deneyin."
                )
            else:
                self.hata_goster(
                    "Güvenlik kodu yüklenemedi. "
                    "Lütfen yenile butonuna basın."
                )

        except (
            requests.RequestException,
            ValueError,
            KeyError,
            TypeError,
        ):
            self.hata_goster(
                "Güvenlik kodu yüklenemedi. "
                "Lütfen yenile butonuna basın."
            )

        finally:
            self.captcha_yenile_btn.setEnabled(True)
            self.captcha_input.setEnabled(
                self.captcha_id is not None
            )
            self.giris_btn.setEnabled(
                self.captcha_id is not None
                and self.kalan == 0
            )

    def giris_yap(self):
        if self.kalan > 0:
            return

        captcha_yenilensin = True

        kullanici = self.kullanici_input.text().strip()
        sifre = self.sifre_input.text()
        guvenlik_kodu = self.captcha_input.text().strip()

        if self.captcha_id is None:
            self.hata_goster(
                "Güvenlik kodu yüklenemedi. Lütfen kodu yenileyin."
            )
            return

        if not kullanici or not sifre:
            self.hata_goster("Kullanıcı adı ve şifre boş bırakılamaz.")
            return

        if not re.fullmatch(r"[0-9]{5}", guvenlik_kodu):
            self.hata_goster(
                "Lütfen 5 haneli güvenlik kodunu girin."
            )
            self.captcha_input.setFocus()
            return

        try:
            cevap = requests.post(
                f"{API_URL}/api/login",
                json={
                    "kullanici_adi": kullanici,
                    "parola": sifre,
                    "captcha_id": self.captcha_id,
                    "guvenlik_kodu": guvenlik_kodu,
                },
                timeout=5
            )
            
            if not cevap.text.strip():
                 self.hata_goster(f"Sunucu {cevap.status_code} kodu döndürdü ama içeriği bomboş!")
                 return
                 
            veri = cevap.json()

            if cevap.status_code == 200 and veri.get("durum") == "basarili":

                self.captcha_sure_timer.stop()
                
                # 1. İlk giriş şifre değiştirme kontrolü
                if veri.get("sifre_degistirme_gerekli") is True:
                    self.sifre_penceresi = SifreDegistirEkrani(veri.get("access_token"))
                    self.sifre_penceresi.sifre_degistirildi.connect(self.ilk_giris_sifresi_degisti)
                    self.sifre_penceresi.iptal_edildi.connect(self.ilk_giris_iptal)
                    self.sifre_penceresi.show()
                    self.hide()
                    return

                # 2. Rol kontrolü
                r_id = veri.get("rol_id")
                aktif_rol = self.rol_adindan_koda(r_id)

                if not aktif_rol:
                    QMessageBox.warning(self, "Yetki Hatası", "Sisteme erişim yetkiniz veya tanımlı bir rolünüz bulunmamaktadır.")
                    return

                # 3. Hataları sıfırla ve ana pencereyi aç
                self.hatali_deneme = 0
                self.hata_lbl.hide()

                print("DEBUG: AnaPencere oluşturulmaya çalışılıyor...")
                print(f"DEBUG Parametreler -> Rol: {aktif_rol}, Kullanıcı: {veri.get('kullanici_adi')}, ID: {veri.get('personel_id') or veri.get('kullanici_id')}")

                self.ana_pencere = AnaPencere(
                    aktif_rol=aktif_rol,
                    kullanici_adi=veri.get("kullanici_adi"),
                    token=veri.get("access_token"),
                    kullanici_id=veri.get("personel_id") or veri.get("kullanici_id")
                )
                print("DEBUG: AnaPencere başarıyla oluşturuldu!")
                
                self.ana_pencere.oturum_kapatildi.connect(self.oturum_kapandi)
                self.ana_pencere.showMaximized()

                self.kullanici_input.clear()
                self.sifre_input.clear()
                self.goster.setChecked(False)
                self.hide()

            elif cevap.status_code == 400:
                self.hata_goster(
                    veri.get(
                        "detail",
                        "Güvenlik kodu hatalı veya süresi dolmuş.",
                    )
                )
            elif cevap.status_code == 429:
                sure = cevap.headers.get("Retry-After", "")
                saniye = int(sure) if sure.isdigit() else 60

                if cevap.headers.get("X-TKYS-RateLimit") == "1":
                    captcha_yenilensin = False

                    self.hata_goster(
                        "Çok fazla giriş isteği gönderildi. "
                        f"Lütfen {saniye} saniye sonra tekrar deneyin."
                    )
                else:
                    # Mevcut hesap kilitleme davranışını koru.
                    self.kilitle(saniye)
            elif cevap.status_code == 403:
                hata_mesaji = veri.get("detail", "Erişim reddedildi.")
                QMessageBox.warning(self, "Giriş Engellendi", hata_mesaji)
                self.sifre_input.clear()
                self.sifre_input.setFocus()
                return
            else:
                self.hata_goster(veri.get("detail", "Giriş başarısız."))
                self.hatali_deneme += 1
                self.sifre_input.clear()
                self.sifre_input.setFocus()

        except requests.exceptions.ConnectionError:
            self.hata_goster("Sunucuya bağlanılamadı. API'nin açık olduğundan emin olun.")
        except requests.exceptions.Timeout:
            self.hata_goster(
                "Sunucu yanıt vermedi. Lütfen tekrar deneyin."
            )
        except Exception:
            self.hata_goster(
                "Giriş işlemi tamamlanamadı. Lütfen tekrar deneyin."
            )

        finally:
            if self.isVisible() and captcha_yenilensin:
                self.captcha_yenile()

    def ilk_giris_sifresi_degisti(self):
        self.sifre_penceresi.close()
        self.kullanici_input.clear()
        self.sifre_input.clear()
        self.goster.setChecked(False)
        self.hata_lbl.hide()
        self.show()
        self.captcha_yenile()
        self.kullanici_input.setFocus()

    def ilk_giris_iptal(self):
        self.sifre_input.clear()
        self.show()
        self.captcha_yenile()
        self.sifre_input.setFocus()

    def oturum_kapandi(self):
        self.kullanici_input.setFocus()
        self.show()
        self.captcha_yenile()

    def kilitle(self, saniye):
        import time

        if hasattr(self, "zamanlayici"):
            self.zamanlayici.stop()

        self.kilit_bitis_monotonik = time.monotonic() + max(1, saniye)
        self.hatali_deneme = 0

        self.giris_btn.setEnabled(False)
        self.kullanici_input.setEnabled(False)
        self.sifre_input.setEnabled(False)

        self.zamanlayici = QTimer(self)
        self.zamanlayici.timeout.connect(self.kilit_guncelle)
        self.kilit_guncelle()
        self.zamanlayici.start(1000)

    def kilit_guncelle(self):
        import time
        import math

        kalan = max(
            0,
            math.ceil(self.kilit_bitis_monotonik - time.monotonic())
        )

        if kalan == 0:
            self.zamanlayici.stop()
            self.giris_btn.setEnabled(True)
            self.kullanici_input.setEnabled(True)
            self.sifre_input.setEnabled(True)
            self.hata_lbl.hide()
            self.kullanici_input.setFocus()
            return

        dakika, saniye = divmod(kalan, 60)

        self.hata_goster(
            f"Çok fazla hatalı deneme. "
            f"{dakika:02d}:{saniye:02d} sonra tekrar deneyebilirsiniz."
        )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    pencere = LoginEkrani()
    pencere.show()
    sys.exit(app.exec())