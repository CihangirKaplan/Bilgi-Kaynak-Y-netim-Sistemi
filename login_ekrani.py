import sys
import requests
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QFrame, QPushButton, QCheckBox, QGraphicsDropShadowEffect
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from main_window import AnaPencere
from sifre_degistir_ekrani import SifreDegistirEkrani

# ======================================================================
#  TEMA VE SABİTLER
# ======================================================================
API_URL = "http://127.0.0.1:8000" # Sunucu adresimiz
MAX_DENEME = 5
KILIT_SANIYE = 30

STIL = """
* { font-family: 'Segoe UI', 'Inter', Arial; }
QWidget#kok { background: #EAF0FA; }
QFrame#loginKart { background: white; border-radius: 24px; }

QFrame#marka {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0A1F5C, stop:0.55 #1D4ED8, stop:1 #3B82F6);
    border-top-left-radius: 24px; border-bottom-left-radius: 24px;
    border-top-right-radius: 0px; border-bottom-right-radius: 0px;
}
QLabel#logoYazi { color: white; font-size: 34px; font-weight: 900; letter-spacing: 5px; background: transparent; }
QLabel#markaBaslik { color: white; font-size: 19px; font-weight: 700; background: transparent; }
QLabel#markaAlt { color: #CFE0FF; font-size: 13px; background: transparent; }
QLabel#ozellik { color: #E3EDFF; font-size: 13px; font-weight: 600; background: transparent; }
QLabel#markaAltBilgi { color: #9DB9F2; font-size: 11px; background: transparent; }

QFrame#form { background: white; border-top-right-radius: 24px; border-bottom-right-radius: 24px; }
QLabel#hosgeldin { color: #0A1F5C; font-size: 28px; font-weight: 800; background: transparent; }
QLabel#hosgeldinAlt { color: #6B7FA8; font-size: 13px; background: transparent; }
QLabel#etiket { color: #1E3A8A; font-size: 12px; font-weight: 700; background: transparent; }

QLineEdit {
    background: #F3F7FF; color: #0A1F5C; border: 1.5px solid #D5E2FB;
    border-radius: 12px; padding: 13px 14px; font-size: 14px;
    selection-background-color: #2563EB;
}
QLineEdit:hover { border: 1.5px solid #9DB9F2; }
QLineEdit:focus { border: 1.5px solid #2563EB; background: white; }

QCheckBox { color: #6B7FA8; font-size: 12px; spacing: 8px; background: transparent; }
QCheckBox::indicator { width: 16px; height: 16px; border-radius: 4px; border: 1.5px solid #9DB9F2; background: white; }
QCheckBox::indicator:checked { background: #2563EB; border: 1.5px solid #2563EB; }

QLabel#hata {
    color: #B91C1C; background: #FEE2E2; border-radius: 10px;
    padding: 10px 14px; font-size: 12px; font-weight: 600;
}
QPushButton#giris {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1D4ED8, stop:1 #3B82F6);
    color: white; border: none; border-radius: 12px; padding: 14px;
    font-size: 15px; font-weight: 800; letter-spacing: 1px;
}
QPushButton#giris:hover { background: #1E40AF; }
QPushButton#giris:pressed { background: #172554; }
QPushButton#giris:disabled { background: #B7C6E6; color: #EEF3FF; }
QLabel#guvenlik { color: #8A9BC0; font-size: 11px; background: transparent; }
"""

class LoginEkrani(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("kok")
        self.setWindowTitle("TKYS — Güvenli Giriş")
        self.setFixedSize(980, 620)
        self.setStyleSheet(STIL)
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

        # -------------------- SOL: MARKA PANELİ --------------------
        marka = QFrame()
        marka.setObjectName("marka")
        marka.setFixedWidth(400)
        ml = QVBoxLayout(marka)
        ml.setContentsMargins(44, 48, 44, 36)
        ml.setSpacing(6)

        logo = QLabel("TKYS")
        logo.setObjectName("logoYazi")
        baslik = QLabel("Travma Kalite\nYönetim Sistemi")
        baslik.setObjectName("markaBaslik")
        alt = QLabel("Klinik operasyon, cihaz yaşam döngüsü ve\nyönetim süreçleri tek platformda.")
        alt.setObjectName("markaAlt")
        ml.addWidget(logo)
        ml.addSpacing(6)
        ml.addWidget(baslik)
        ml.addSpacing(4)
        ml.addWidget(alt)
        ml.addSpacing(34)
        for metin in ("✔  Role dayalı erişim kontrolü",
                      "✔  Denetim izi (audit) kaydı",
                      "✔  Cihaz yaşam döngüsü takibi",
                      "✔  Randevu ve oda yönetimi"):
            o = QLabel(metin)
            o.setObjectName("ozellik")
            ml.addWidget(o)
            ml.addSpacing(6)
        ml.addStretch()
        mab = QLabel("BKYS v1.0  ·  Kurumsal Sürüm")
        mab.setObjectName("markaAltBilgi")
        ml.addWidget(mab)
        kl.addWidget(marka)

        # -------------------- SAĞ: FORM --------------------
        form = QFrame()
        form.setObjectName("form")
        fl = QVBoxLayout(form)
        fl.setContentsMargins(54, 48, 54, 36)
        fl.setSpacing(6)

        h1 = QLabel("Hoş Geldiniz")
        h1.setObjectName("hosgeldin")
        h2 = QLabel("Devam etmek için hesabınızla oturum açınız.")
        h2.setObjectName("hosgeldinAlt")
        fl.addWidget(h1)
        fl.addWidget(h2)
        fl.addSpacing(22)

        e1 = QLabel("KULLANICI ADI")
        e1.setObjectName("etiket")
        self.kullanici_input = QLineEdit()
        self.kullanici_input.setPlaceholderText("Kullanıcı adınızı giriniz:")
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

        # Enter tuşu ile giriş
        self.kullanici_input.returnPressed.connect(self.sifre_input.setFocus)
        self.sifre_input.returnPressed.connect(self.giris_yap)
        self.kullanici_input.setFocus()

    def hata_goster(self, metin):
        self.hata_lbl.setText("⚠  " + metin)
        self.hata_lbl.show()

    def rol_adindan_koda(self, rol_id):
        # API'den gelen Rol ID'sini arayüzün anladığı kelimelere (slug) çevirir.
        roller = {1: "psikolog", 2: "memur", 3: "mudur", 4: "ogrenci", 9: "asistan", 6: "admin"}
        return roller.get(rol_id, None)

    def giris_yap(self):
        if self.kalan > 0:
            return

        kullanici = self.kullanici_input.text().strip()
        sifre = self.sifre_input.text()

        if not kullanici or not sifre:
            self.hata_goster("Kullanıcı adı ve şifre boş bırakılamaz.")
            return

        # ==========================================
        # GERÇEK API'YE (SUNUCUYA) BAĞLANTI KATMANI
        # ==========================================
        try:
            cevap = requests.post(
                f"{API_URL}/api/login",
                json={"kullanici_adi": kullanici, "parola": sifre},
                timeout=5
            )
            
            # Gelen cevabı önce ekrana düz metin (text) olarak basalım ki sunucu ne diyor görelim!
            print(f"Sunucudan Gelen Ham Cevap (Text): {cevap.text}")
            print(f"Sunucudan Gelen HTTP Kodu: {cevap.status_code}")
            
            # Eğer sunucu tamamen boş döndüyse (char 0 hatası buradan çıkar)
            if not cevap.text.strip():
                 self.hata_goster(f"Sunucu {cevap.status_code} kodu döndürdü ama içeriği bomboş!")
                 return
                 
            veri = cevap.json()

            if cevap.status_code == 200 and veri.get("durum") == "basarili":

                # Yetki ve Rol Kontrolü
                r_id = veri.get("rol_id")
                aktif_rol = self.rol_adindan_koda(r_id)

                if aktif_rol is None:
                    self.hata_goster("Sisteme erişim yetkiniz veya tanımlı bir rolünüz bulunmamaktadır.")
                    return

                # Güvenli Giriş Onayı
                self.hatali_deneme = 0
                self.hata_lbl.hide()

                gercek_token = veri.get("access_token")
                k_adi = veri.get("kullanici_adi")
                k_id = veri.get("kullanici_id")
                p_id = veri.get("personel_id")
                aktif_personel_id = p_id if p_id else k_id

                # İlk girişte zorunlu şifre değiştirme
                if veri.get("sifre_degistirme_gerekli") is True:
                    self.sifre_penceresi = SifreDegistirEkrani(gercek_token)
                    self.sifre_penceresi.sifre_degistirildi.connect(
                        self.ilk_giris_sifresi_degisti
                    )
                    self.sifre_penceresi.iptal_edildi.connect(
                        self.ilk_giris_iptal
                    )
                    self.sifre_penceresi.show()
                    self.hide()
                    return

                # 1. Ana Pencereyi var olan yapısına uygun yaratıyoruz (Çökmeyi engeller)
# Token'ı ve ID'yi pencere yaratılırken doğrudan içeri yolluyoruz
                # ki Cihaz ekranı çizilirken token'ı kapabilsin!
                self.ana_pencere = AnaPencere(
                    aktif_rol=aktif_rol,
                    kullanici_adi=k_adi,
                    token=gercek_token,
                    kullanici_id=aktif_personel_id
                )

                self.ana_pencere.oturum_kapatildi.connect(self.oturum_kapandi)
                self.ana_pencere.showMaximized()

                self.kullanici_input.clear()
                self.sifre_input.clear()
                self.goster.setChecked(False)
                self.hide()

            elif cevap.status_code == 429: # Çok fazla hatalı giriş (Kilitlenme)
                self.kilitle()

            else: # 401 veya 403 (Hatalı şifre / Pasif hesap)
                self.hata_goster(veri.get("detail", "Giriş başarısız."))
                self.hatali_deneme += 1
                self.sifre_input.clear()
                self.sifre_input.setFocus()

        except requests.exceptions.ConnectionError:
            self.hata_goster("Sunucuya bağlanılamadı. API'nin açık olduğundan emin olun.")
        except Exception as e:
            self.hata_goster(f"Beklenmeyen bir hata oluştu: {str(e)}")

    def ilk_giris_sifresi_degisti(self):
        """Şifre değişince yeni şifreyle tekrar giriş yapılmasını sağlar."""
        self.sifre_penceresi.close()
        self.kullanici_input.clear()
        self.sifre_input.clear()
        self.goster.setChecked(False)
        self.hata_lbl.hide()
        self.show()
        self.kullanici_input.setFocus()

    def ilk_giris_iptal(self):
        """Şifre değiştirme ekranı kapatılırsa giriş ekranına döner."""
        self.sifre_input.clear()
        self.show()
        self.sifre_input.setFocus()

    def oturum_kapandi(self):
        """Ana pencerede 'Oturumu Kapat'a basılınca giriş ekranı geri gelir."""
        self.kullanici_input.setFocus()
        self.show()

    def kilitle(self):
        self.kalan = KILIT_SANIYE
        self.hatali_deneme = 0
        self.giris_btn.setEnabled(False)
        self.kullanici_input.setEnabled(False)
        self.sifre_input.setEnabled(False)
        self.kilit_guncelle()
        self.zamanlayici = QTimer(self)
        self.zamanlayici.timeout.connect(self.kilit_guncelle)
        self.zamanlayici.start(1000)

    def kilit_guncelle(self):
        if self.kalan <= 0:
            self.zamanlayici.stop()
            self.giris_btn.setEnabled(True)
            self.kullanici_input.setEnabled(True)
            self.sifre_input.setEnabled(True)
            self.hata_lbl.hide()
            self.kullanici_input.setFocus()
            return
        self.hata_goster(f"Çok fazla hatalı deneme. {self.kalan} saniye kilitlendiniz.")
        self.kalan -= 1


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    pencere = LoginEkrani()
    pencere.show()
    sys.exit(app.exec())