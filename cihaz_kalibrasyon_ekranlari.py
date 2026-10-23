from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QHeaderView, QMessageBox, QDialog,
    QFormLayout, QComboBox, QDateEdit, QLineEdit, QFrame
)
from PySide6.QtCore import Qt, QDate
import requests
from tablo_tasarimi import (FORM_STIL, tablo_olustur, metin_item, hap, islem_butonlari, sil_onayi,
                            sayi_cipi, tarih_goster, kalan_gun_hapi, sayfa_basligi,
                            yenile_butonu_olustur, bos_mesaj_olustur)

class YeniKalibrasyonFormu(QDialog):
    def __init__(self, api_url, token, parent=None):
        super().__init__(parent)
        self.api_url = api_url
        self.token = token

        self.setWindowTitle("Yeni Kalibrasyon Kaydı")
        self.setMinimumSize(450, 420)

        self.setStyleSheet(FORM_STIL)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(15)

        self.cmb_cihaz = QComboBox()
        self.txt_kurum = QLineEdit()
        self.txt_kurum.setPlaceholderText("Örn: TSE, Kalibro A.Ş...")
        self.txt_sertifika = QLineEdit()
        self.txt_sertifika.setPlaceholderText("Sertifika veya Belge No...")
        self.dt_gecerlilik = QDateEdit(QDate.currentDate().addYears(1))
        self.dt_gecerlilik.setCalendarPopup(True)

        # --- YENİ EKLENEN TARİHLER ---
        self.dt_baslangic = QDateEdit(QDate.currentDate())
        self.dt_baslangic.setCalendarPopup(True)

        self.dt_bitis = QDateEdit(QDate.currentDate())
        self.dt_bitis.setCalendarPopup(True)

        form.addRow("Cihaz (*):", self.cmb_cihaz)
        form.addRow("Yapan Kurum (*):", self.txt_kurum)
        form.addRow("Sertifika No (*):", self.txt_sertifika)
        form.addRow("Başlangıç Tarihi (*):", self.dt_baslangic) # YENİ
        form.addRow("Bitiş Tarihi (*):", self.dt_bitis)         # YENİ
        form.addRow("Geçerlilik Tarihi (*):", self.dt_gecerlilik)
        layout.addLayout(form)

        self.btn_kaydet = QPushButton("Kaydet")
        self.btn_kaydet.setObjectName("kaydet")
        self.btn_kaydet.setCursor(Qt.PointingHandCursor)
        self.btn_kaydet.clicked.connect(self.kaydet)
        layout.addWidget(self.btn_kaydet)

        self.cihazlari_yukle()

    def cihazlari_yukle(self):
        try:
            res = requests.get(f"{self.api_url}/api/cihazlar", headers={"Authorization": f"Bearer {self.token}"})
            if res.status_code == 200:
                for c in res.json():
                    self.cmb_cihaz.addItem(f"{c['envanter_kodu']} - {c['cihaz_adi']}", c['cihaz_id'])
        except Exception:
            pass

    def kaydet(self):
        veri = {
            "cihaz_id": self.cmb_cihaz.currentData(),
            "kalibrasyon_yapan_kurum": self.txt_kurum.text().strip(),
            "sertifika_no": self.txt_sertifika.text().strip(),
            "gecerlilik_tarihi": self.dt_gecerlilik.date().toString("yyyy-MM-dd"),
            # YENİ EKLENEN VERİLER
            "kalibrasyon_baslangic_tarihi": self.dt_baslangic.date().toString("yyyy-MM-dd"),
            "kalibrasyon_bitis_tarihi": self.dt_bitis.date().toString("yyyy-MM-dd")
        }
        if not veri["kalibrasyon_yapan_kurum"] or not veri["sertifika_no"]:
            QMessageBox.warning(self, "Uyarı", "Kurum ve Sertifika No zorunludur.")
            return

        try:
            res = requests.post(f"{self.api_url}/api/kalibrasyonlar", json=veri, headers={"Authorization": f"Bearer {self.token}"})
            if res.status_code == 201:
                QMessageBox.information(self, "Başarılı", "Kalibrasyon kaydı başarıyla eklendi.")
                self.accept()
            else:
                # Hatayı gizlemiyoruz, ekrana basıyoruz!
                hata_mesaji = res.json().get("detail", "Kayıt yapılamadı.")
                QMessageBox.warning(self, "Hata", f"Sebep: {hata_mesaji}")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Sunucu hatası: {str(e)}")

class KalibrasyonDuzenleFormu(QDialog):
    def __init__(self, api_url, token, veri, parent=None):
        super().__init__(parent)
        self.api_url = api_url
        self.token = token
        self.k_veri = veri

        self.setWindowTitle("Kalibrasyon Kaydını Düzenle")
        self.setMinimumSize(450, 420)

        self.setStyleSheet(FORM_STIL)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(15)

        self.txt_cihaz = QLineEdit(veri.get("cihaz_adi", ""))
        self.txt_cihaz.setReadOnly(True)
        self.txt_kurum = QLineEdit(veri.get("kalibrasyon_yapan_kurum", ""))
        self.txt_sertifika = QLineEdit(veri.get("sertifika_no", ""))
        self.dt_gecerlilik = QDateEdit(QDate.fromString(str(veri.get("gecerlilik_tarihi", QDate.currentDate().toString("yyyy-MM-dd")))[:10], "yyyy-MM-dd"))
        self.dt_gecerlilik.setCalendarPopup(True)

        # --- YENİ TARİHLERİ GÜVENLİ ÇEKME ---
        baslangic_str = veri.get("kalibrasyon_baslangic_tarihi") or QDate.currentDate().toString("yyyy-MM-dd")
        bitis_str = veri.get("kalibrasyon_bitis_tarihi") or baslangic_str

        self.dt_baslangic = QDateEdit(QDate.fromString(str(baslangic_str)[:10], "yyyy-MM-dd"))
        self.dt_baslangic.setCalendarPopup(True)

        self.dt_bitis = QDateEdit(QDate.fromString(str(bitis_str)[:10], "yyyy-MM-dd"))
        self.dt_bitis.setCalendarPopup(True)

        form.addRow("Cihaz:", self.txt_cihaz)
        form.addRow("Yapan Kurum (*):", self.txt_kurum)
        form.addRow("Sertifika No (*):", self.txt_sertifika)
        form.addRow("Başlangıç Tarihi (*):", self.dt_baslangic) # YENİ
        form.addRow("Bitiş Tarihi (*):", self.dt_bitis)         # YENİ
        form.addRow("Geçerlilik (*):", self.dt_gecerlilik)
        layout.addLayout(form)

        btn = QPushButton("Değişiklikleri Kaydet")
        btn.setObjectName("kaydet")
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(self.kaydet)
        layout.addWidget(btn)

    def kaydet(self):
        veri = {
            "kalibrasyon_yapan_kurum": self.txt_kurum.text().strip(),
            "sertifika_no": self.txt_sertifika.text().strip(),
            "gecerlilik_tarihi": self.dt_gecerlilik.date().toString("yyyy-MM-dd"),
            # YENİ EKLENEN VERİLER
            "kalibrasyon_baslangic_tarihi": self.dt_baslangic.date().toString("yyyy-MM-dd"),
            "kalibrasyon_bitis_tarihi": self.dt_bitis.date().toString("yyyy-MM-dd")
        }
        if not veri["kalibrasyon_yapan_kurum"] or not veri["sertifika_no"]:
            QMessageBox.warning(self, "Uyarı", "Kurum ve Sertifika No zorunludur.")
            return

        try:
            res = requests.put(f"{self.api_url}/api/kalibrasyonlar/{self.k_veri['kalibrasyon_id']}", json=veri, headers={"Authorization": f"Bearer {self.token}"})
            if res.status_code == 200:
                QMessageBox.information(self, "Başarılı", "Kalibrasyon kaydı başarıyla güncellendi.")
                self.accept()
            else:
                hata_mesaji = res.json().get("detail", "Güncelleme yapılamadı.")
                QMessageBox.warning(self, "Hata", f"Sebep: {hata_mesaji}")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Sunucu hatası: {str(e)}")

class KalibrasyonYonetimEkrani(QWidget):
    """Kalibrasyon kayıtlarının listelendiği, aranabilir ve silinebilir tablo ekranı."""
    def __init__(self, api_url, token):
        super().__init__()
        self.api_url = api_url
        self.token = token
        self.basliklar = {"Authorization": f"Bearer {token}"}
        self.detaylar = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        self.arama = QLineEdit()
        self.arama.setPlaceholderText("🔍  Cihaz, kurum veya sertifika ara...")
        self.arama.textChanged.connect(self.filtrele)

        self.cip_toplam = sayi_cipi("0 kayıt")
        self.cip_yaklasan = sayi_cipi("0 süresi yaklaşan", "#854D0E", "#FEF3C7")
        self.cip_gecmis = sayi_cipi("0 süresi dolmuş", "#991B1B", "#FEE2E2")

        layout.addWidget(sayfa_basligi(
            "Cihaz Kalibrasyon Kayıtları", "Kalibrasyon sertifikaları ve geçerlilik süreleri",
            self.arama, yenile_butonu_olustur(self.yukle),
            [self.cip_toplam, self.cip_yaklasan, self.cip_gecmis]))

        self.tablo = tablo_olustur(["CİHAZ", "KURUM", "SERTİFİKA NO", "KALİBRASYON TARİHİ",
                                    "GEÇERLİLİK", "İŞLEM"])
        kb = self.tablo.horizontalHeader()
        kb.setSectionResizeMode(0, QHeaderView.Stretch)
        kb.setSectionResizeMode(1, QHeaderView.Stretch)
        kb.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        kb.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        kb.setSectionResizeMode(4, QHeaderView.Fixed)
        kb.setSectionResizeMode(5, QHeaderView.Fixed)
        self.tablo.setColumnWidth(4, 230)
        self.tablo.setColumnWidth(5, 110)

        self.bos_mesaj = bos_mesaj_olustur("Henüz kalibrasyon kaydı yok.")

        kart = QFrame()
        kart.setObjectName("kart")
        kl = QVBoxLayout(kart)
        kl.setContentsMargins(8, 8, 8, 8)
        kl.addWidget(self.tablo)
        kl.addWidget(self.bos_mesaj)
        layout.addWidget(kart, 1)

        self.yukle()

    def yukle(self):
        self.tablo.setRowCount(0)
        self.detaylar.clear()
        yaklasan = gecmis = 0
        try:
            res = requests.get(f"{self.api_url}/api/kalibrasyonlar", headers=self.basliklar, timeout=10)
            res.raise_for_status()
            kayitlar = res.json()
        except Exception as e:
            print("Kalibrasyon listesi yükleme hatası:", e)
            self.bos_mesaj.setText("Kalibrasyon kayıtları yüklenemedi. Sunucu bağlantısını kontrol edin.")
            self.bos_mesaj.show()
            self.tablo.hide()
            return

        self.tablo.setRowCount(len(kayitlar))
        for i, k in enumerate(kayitlar):
            self.detaylar[k["kalibrasyon_id"]] = k

            bas = tarih_goster(k.get("kalibrasyon_baslangic_tarihi") or k.get("islem_tarihi"))
            bit = tarih_goster(k.get("kalibrasyon_bitis_tarihi"))
            tarih_metni = bas if bas == bit else f"{bas} – {bit}"

            self.tablo.setItem(i, 0, metin_item(k.get("cihaz_adi", ""), kalin=True))
            self.tablo.setItem(i, 1, metin_item(k.get("kalibrasyon_yapan_kurum", "")))
            self.tablo.setItem(i, 2, metin_item(k.get("sertifika_no", ""), ortala=True))
            self.tablo.setItem(i, 3, metin_item(tarih_metni, ortala=True))

            widget, durum = kalan_gun_hapi(k.get("gecerlilik_tarihi"))
            yaklasan += durum == "yaklasiyor"
            gecmis += durum == "gecmis"
            self.tablo.setCellWidget(i, 4, widget)

            self.tablo.setCellWidget(i, 5, islem_butonlari(
                lambda _=False, kid=k["kalibrasyon_id"]: self.duzenle(kid),
                lambda _=False, kid=k["kalibrasyon_id"]: self.sil(kid)))

        self.cip_toplam.setText(f"{len(kayitlar)} kayıt")
        self.cip_yaklasan.setText(f"{yaklasan} süresi yaklaşan")
        self.cip_gecmis.setText(f"{gecmis} süresi dolmuş")
        self.bos_mesaj.setText("Henüz kalibrasyon kaydı yok. Üstteki “Kalibrasyon Kaydı” butonuyla ekleyebilirsiniz.")
        self.bos_mesaj.setVisible(not kayitlar)
        self.tablo.setVisible(bool(kayitlar))
        self.filtrele(self.arama.text())

    def filtrele(self, metin):
        """Cihaz, kurum ve sertifika sütunlarında arama yapar."""
        aranan = metin.strip().lower()
        for satir in range(self.tablo.rowCount()):
            icerik = " ".join(
                (self.tablo.item(satir, k).text() if self.tablo.item(satir, k) else "")
                for k in (0, 1, 2)).lower()
            self.tablo.setRowHidden(satir, aranan not in icerik)

    def yeni_ekle(self):
        if YeniKalibrasyonFormu(self.api_url, self.token, self).exec():
            self.yukle()

    def duzenle(self, kid):
        if KalibrasyonDuzenleFormu(self.api_url, self.token, self.detaylar[kid], self).exec():
            self.yukle()

    def sil(self, kid):
        kayit = self.detaylar.get(kid)
        if not kayit:
            return
        if not sil_onayi(self, "Kalibrasyon Kaydını Sil",
                         f"“{kayit.get('cihaz_adi', '')}” cihazının bu kalibrasyon kaydı silinsin mi?"):
            return
        try:
            res = requests.delete(f"{self.api_url}/api/kalibrasyonlar/{kid}", headers=self.basliklar, timeout=10)
            if res.status_code == 200:
                self.yukle()
            else:
                hata = res.json().get("detail", "Bilinmeyen hata")
                QMessageBox.warning(self, "Silinemedi", hata)
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Sunucuya ulaşılamadı: {e}")