import re
from datetime import datetime
from PySide6.QtWidgets import (QComboBox, QDialog, QFormLayout, QFrame, QHBoxLayout, QLabel,
                               QLineEdit, QMessageBox, QPushButton, QVBoxLayout)

from api_yoneticisi import oturum_kontrollu_istek, oturum_hatasi_mi
from siniflandirma import YAS_GRUPLARI

OKUNUR_STIL = "background-color: #F1F5F9; color: #64748B; font-weight: bold;"


class DanisanOlusturDialog(QDialog):
    """Yeni danışan kodu oluşturur ve dinamik ücret/istisna kurallarını uygular."""

    def __init__(self, api_url, token, ebeveyn=None, mevcut_psikolog_id=None, onceden_psikolog_id=None):
        super().__init__(ebeveyn)
        self.api_url = api_url.rstrip("/")
        self.token = token
        self.mevcut_psikolog_id = mevcut_psikolog_id
        self.onceden_psikolog_id = onceden_psikolog_id
        self.olusan_kod = None

        self.setWindowTitle("Yeni Danışan")
        self.setMinimumWidth(430)
        self.setStyleSheet("""
            QDialog { background-color: #F8F9FA; font-family: 'Segoe UI', Arial; }
            QLabel { font-weight: bold; color: #0F2552; font-size: 13px; }
            QLineEdit, QComboBox {
                padding: 9px; border-radius: 6px; border: 1px solid #CBD5E1;
                background-color: white; color: #0F2552; font-size: 13px; font-weight: bold;
            }
            QComboBox:disabled { background-color: #F1F5F9; color: #94A3B8; }
            QComboBox QAbstractItemView {
                background-color: white; color: #0F2552;
                selection-background-color: #2563EB; selection-color: white;
            }
        """)

        ana = QVBoxLayout(self)
        ana.setContentsMargins(15, 15, 15, 15)
        ana.setSpacing(15)

        # Lacivert üst başlık kartı
        baslik_frame = QFrame()
        baslik_frame.setStyleSheet("background-color: #0A1F5C; border-radius: 8px;")
        baslik_layout = QHBoxLayout(baslik_frame)
        baslik_layout.setContentsMargins(15, 12, 15, 12)
        lbl_ikon = QLabel("👤")
        lbl_ikon.setStyleSheet("font-size: 18px; background: transparent;")
        lbl_baslik = QLabel("Yeni Danışan")
        lbl_baslik.setStyleSheet(
            "color: white; font-size: 15px; font-weight: bold; background: transparent;"
        )
        baslik_layout.addWidget(lbl_ikon)
        baslik_layout.addWidget(lbl_baslik)
        baslik_layout.addStretch()
        ana.addWidget(baslik_frame)

        form = QFormLayout()
        form.setSpacing(12)

        # Sıradaki danışan kodunun gösterileceği alan
        self.txt_kod = QLineEdit("Yükleniyor...")
        self.txt_kod.setReadOnly(True)
        self.txt_kod.setStyleSheet(OKUNUR_STIL)
        form.addRow("Danışan Kodu:", self.txt_kod)

        # Psikolog: psikolog hesabında kendi adına kilitli; yetkili roller danışanın psikoloğunu seçer
        self.cmb_psikolog = QComboBox()
        form.addRow("Psikolog:", self.cmb_psikolog)

        # Yaş grubu: kapalı liste (terapi türü her randevuda seçilir, danışanda tutulmaz)
        self.cmb_yas = QComboBox()
        self.cmb_yas.addItem("--- Yaş Grubu Seçiniz ---", None)
        for kod, etiket in YAS_GRUPLARI:
            self.cmb_yas.addItem(etiket, kod)
        form.addRow("Yaş Grubu:", self.cmb_yas)

        # Ücret Durumu Seçimi
        self.cmb_ucret = QComboBox()
        self.cmb_ucret.addItem("Ücretli", True)
        self.cmb_ucret.addItem("Ücretsiz", False)
        form.addRow("Ücret Durumu:", self.cmb_ucret)

        # İstisna Türü Seçimi (Dinamik doldurulacak)
        self.cmb_istisna = QComboBox()
        form.addRow("İstisna Türü:", self.cmb_istisna)

        self.txt_durum = QLineEdit("Aktif")
        self.txt_durum.setReadOnly(True)
        self.txt_durum.setStyleSheet(OKUNUR_STIL)
        form.addRow("Durum:", self.txt_durum)

        ana.addLayout(form)

        # Alt Butonlar
        butonlar = QHBoxLayout()
        butonlar.addStretch()

        btn_iptal = QPushButton("İptal")
        btn_iptal.setFixedWidth(90)
        btn_iptal.setStyleSheet(
            "background-color: #E2E8F0; color: #0F2552; border-radius: 6px; "
            "padding: 8px; font-weight: bold;"
        )
        btn_iptal.clicked.connect(self.reject)

        self.btn_kaydet = QPushButton("Danışanı Oluştur")
        self.btn_kaydet.setFixedWidth(160)
        self.btn_kaydet.setStyleSheet(
            "background-color: #2563EB; color: white; border-radius: 6px; "
            "padding: 8px; font-weight: bold;"
        )
        self.btn_kaydet.clicked.connect(self.kaydet)

        butonlar.addWidget(btn_iptal)
        butonlar.addWidget(self.btn_kaydet)
        ana.addLayout(butonlar)

        # Event bağlantıları ve başlangıç yüklemeleri
        self.cmb_ucret.currentIndexChanged.connect(self.ucret_durumu_degisti)
        self.ucret_durumu_degisti()  # İlk açılışta kuralları uygula
        self.psikologlari_yukle()
        self.siradaki_kodu_yukle()   # Sıradaki danışan kodunu getir

    def psikologlari_yukle(self):
        """Psikolog listesini doldurur; giriş yapan psikologsa kendi adına kilitlenir."""
        self.cmb_psikolog.clear()
        self.cmb_psikolog.addItem("--- Psikolog Seçiniz ---", None)
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            cevap = oturum_kontrollu_istek("GET", f"{self.api_url}/api/psikologlar", headers=headers, timeout=5)
            if oturum_hatasi_mi(cevap) or cevap.status_code != 200:
                return
            for psikolog in cevap.json():
                self.cmb_psikolog.addItem(psikolog["ad_soyad"], psikolog["personel_id"])
        except Exception as e:
            print("Psikologlar çekilirken hata oluştu:", e)
            return

        kendisi = self.cmb_psikolog.findData(self.mevcut_psikolog_id)
        if self.mevcut_psikolog_id is not None and kendisi >= 0:
            self.cmb_psikolog.setCurrentIndex(kendisi)
            self.cmb_psikolog.setEnabled(False)
            return
        onceden = self.cmb_psikolog.findData(self.onceden_psikolog_id)
        if self.onceden_psikolog_id is not None and onceden >= 0:
            self.cmb_psikolog.setCurrentIndex(onceden)

    def ucret_durumu_degisti(self):
        """Ücret durumuna göre istisna türlerini dinamik günceller."""
        ucretli_mi = self.cmb_ucret.currentData()
        self.cmb_istisna.clear()

        if ucretli_mi:
            # Ücretli ise istisna Yok ve alan pasif
            self.cmb_istisna.addItem("Yok", "YOK")
            self.cmb_istisna.setEnabled(False)
        else:
            # Ücretsiz ise Kanser Hastası veya Şehit/Gazi Yakını seçilebilir
            self.cmb_istisna.addItem("Kanser Hastası", "KANSER")
            self.cmb_istisna.addItem("Şehit / Gazi Yakını", "SEHIT_GAZI")
            self.cmb_istisna.setEnabled(True)

    def siradaki_kodu_yukle(self):
        """Sistemdeki mevcut danışan kodlarına bakarak sıradaki kodu tahmin edip ekrana yazar."""
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            cevap = oturum_kontrollu_istek(
                "GET", f"{self.api_url}/api/danisan-kodlari", params={"pasifler_dahil": "true"},
                headers=headers, timeout=5
            )
            if cevap.status_code == 200:
                danisanlar = cevap.json()
                max_sira = 0
                yil = datetime.now().year

                for d in danisanlar:
                    kod = str(d.get("danisan_kod_id", ""))
                    match = re.search(r"DAN-\d+-(\d+)", kod)
                    if match:
                        max_sira = max(max_sira, int(match.group(1)))

                siradaki_no = max_sira + 1
                siradaki_kod = f"DAN-{yil}-{siradaki_no:04d}"
                self.txt_kod.setText(siradaki_kod)
            else:
                self.txt_kod.setText("Otomatik Atanacak")
        except Exception:
            self.txt_kod.setText("Otomatik Atanacak")

    @staticmethod
    def _detay(cevap):
        try:
            return str(cevap.json().get("detail", ""))
        except ValueError:
            return cevap.text[:200]

    def kaydet(self):
        # Sunucu bu değerleri sorgu parametresi olarak okur (JSON gövdesi yok sayılır; ücretsiz seçimi kaybolurdu).
        parametreler = {
            "ucretli_mi": "true" if self.cmb_ucret.currentData() else "false",
            "istisna_turu": self.cmb_istisna.currentData(),
        }
        if self.cmb_yas.currentData() is None:
            QMessageBox.warning(self, "Yaş Grubu Seçilmedi", "Lütfen danışanın yaş grubunu seçin.")
            return
        parametreler["yas_grubu"] = self.cmb_yas.currentData()
        psikolog_id = self.cmb_psikolog.currentData()
        if self.cmb_psikolog.isEnabled() and psikolog_id is None:
            QMessageBox.warning(self, "Psikolog Seçilmedi", "Lütfen danışanın psikoloğunu seçin.")
            return
        if psikolog_id is not None:
            parametreler["psikolog_id"] = int(psikolog_id)

        self.btn_kaydet.setEnabled(False)
        try:
            cevap = oturum_kontrollu_istek(
                "POST",
                f"{self.api_url}/api/danisan-kodlari",
                params=parametreler,
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=5,
            )
            if oturum_hatasi_mi(cevap):
                return

            if cevap.status_code == 201:
                kod = (cevap.json().get("veri") or {}).get("danisan_kod_id")
                self.olusan_kod = kod
                self.txt_kod.setText(kod or "")
                QMessageBox.information(
                    self, "Başarılı", f"Danışan kodu oluşturuldu:\n\n{kod}"
                )
                self.accept()
            else:
                QMessageBox.warning(
                    self, "Hata",
                    f"Danışan oluşturulamadı (Kod {cevap.status_code}).\n{self._detay(cevap)}",
                )
        except Exception as e:
            QMessageBox.critical(self, "Bağlantı Hatası", f"Sunucuya ulaşılamadı:\n{e}")
        finally:
            self.btn_kaydet.setEnabled(True)