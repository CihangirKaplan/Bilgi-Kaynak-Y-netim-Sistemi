from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QHeaderView, QMessageBox, QDialog,
    QFormLayout, QComboBox, QDateEdit, QLineEdit, QTextEdit, QFrame
)
from PySide6.QtCore import Qt, QDate
import requests
from tablo_tasarimi import (FORM_STIL, tablo_olustur, metin_item, hap, islem_butonlari, sil_onayi,
                            sayi_cipi, tarih_goster, kalan_gun_hapi, sayfa_basligi,
                            yenile_butonu_olustur, bos_mesaj_olustur)

class YeniBakimFormu(QDialog):
    def __init__(self, api_url, token, parent=None):
        super().__init__(parent)
        self.api_url = api_url
        self.token = token

        self.setWindowTitle("Yeni Bakım Kaydı")
        self.setMinimumSize(450, 500)

        self.setStyleSheet(FORM_STIL)

        layout = QVBoxLayout(self)

        form_layout = QFormLayout()
        form_layout.setSpacing(15)

        self.cmb_cihaz = QComboBox()
        self.txt_kisi = QLineEdit()
        self.txt_islem = QTextEdit()
        self.txt_islem.setMaximumHeight(80)
        self.txt_maliyet = QLineEdit("0.0")

        # --- YENİ EKLENEN: BAŞLANGIÇ VE BİTİŞ TARİHLERİ ---
        self.dt_baslangic = QDateEdit(QDate.currentDate())
        self.dt_baslangic.setCalendarPopup(True)

        self.dt_bitis = QDateEdit(QDate.currentDate())
        self.dt_bitis.setCalendarPopup(True)

        self.dt_sonraki_bakim = QDateEdit(QDate.currentDate().addMonths(6))
        self.dt_sonraki_bakim.setCalendarPopup(True)

        form_layout.addRow("Cihaz (*):", self.cmb_cihaz)
        form_layout.addRow("Bakım Yapan Kişi (*):", self.txt_kisi)
        form_layout.addRow("Yapılan İşlem (*):", self.txt_islem)
        form_layout.addRow("Maliyet (₺):", self.txt_maliyet)
        form_layout.addRow("Başlangıç Tarihi (*):", self.dt_baslangic)
        form_layout.addRow("Bitiş Tarihi (*):", self.dt_bitis)
        form_layout.addRow("Sonraki Bakım Tarihi:", self.dt_sonraki_bakim)

        layout.addLayout(form_layout)

        btn_kaydet = QPushButton("Kaydet")
        btn_kaydet.setObjectName("kaydet")
        btn_kaydet.setCursor(Qt.PointingHandCursor)
        btn_kaydet.clicked.connect(self.kaydet)
        layout.addWidget(btn_kaydet)

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
        # TL Formatı Düzeltici: 10.000,50 veya 10000 veya 10,50'yi anlar
        metin = self.txt_maliyet.text().strip()
        if '.' in metin and ',' in metin:
            metin = metin.replace('.', '').replace(',', '.')
        elif '.' in metin and len(metin.split('.')[-1]) == 3:
            metin = metin.replace('.', '')
        else:
            metin = metin.replace(',', '.')

        try:
            maliyet = float(metin)
        except ValueError:
            maliyet = 0.0

        # GÜVENLİK YAMASI: Eski model "bakim_tarihi" bekliyorsa diye onu da pakete ekliyoruz
        veri = {
            "cihaz_id": self.cmb_cihaz.currentData(),
            "bakim_tarihi": self.dt_baslangic.date().toString("yyyy-MM-dd"), # EKLENDİ
            "bakim_yapan_kisi": self.txt_kisi.text().strip(),
            "yapilan_islem": self.txt_islem.toPlainText().strip(),
            "maliyet": maliyet,
            "bakim_baslangic_tarihi": self.dt_baslangic.date().toString("yyyy-MM-dd"),
            "bakim_bitis_tarihi": self.dt_bitis.date().toString("yyyy-MM-dd"),
            "sonraki_bakim_tarihi": self.dt_sonraki_bakim.date().toString("yyyy-MM-dd")
        }

        if not veri["bakim_yapan_kisi"] or not veri["yapilan_islem"]:
            QMessageBox.warning(self, "Uyarı", "Kişi ve Yapılan İşlem alanları zorunludur.")
            return

        try:
            res = requests.post(f"{self.api_url}/api/bakimlar", json=veri, headers={"Authorization": f"Bearer {self.token}"})
            if res.status_code == 201:
                QMessageBox.information(self, "Başarılı", "Bakım kaydı başarıyla eklendi.")
                self.accept()
            else:
                # ARTIK HATAYI GİZLEMİYORUZ, SUNUCUNUN CEVABINI EKRANA BASIYORUZ!
                hata_mesaji = res.json().get("detail", "Bilinmeyen Sunucu Hatası")
                QMessageBox.warning(self, "Hata", f"Kayıt yapılamadı!\n\nSebep: {hata_mesaji}")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Sunucu hatası: {str(e)}")

class BakimDuzenleFormu(QDialog):
    def __init__(self, api_url, token, bakim_verisi, parent=None):
        super().__init__(parent)
        self.api_url = api_url
        self.token = token
        self.bakim_verisi = bakim_verisi

        self.setWindowTitle("Bakım Kaydını Düzenle")
        self.setMinimumSize(450, 520)

        self.setStyleSheet(FORM_STIL)

        layout = QVBoxLayout(self)

        form_layout = QFormLayout()
        form_layout.setSpacing(15)

        self.txt_cihaz = QLineEdit(bakim_verisi.get("cihaz_adi", ""))
        self.txt_cihaz.setReadOnly(True)
        self.txt_kisi = QLineEdit(bakim_verisi.get("bakim_yapan_kisi", ""))

        maliyet_str = str(bakim_verisi.get("maliyet", "0.0"))
        self.txt_maliyet = QLineEdit(maliyet_str)

        self.txt_islem = QTextEdit(bakim_verisi.get("yapilan_islem", ""))
        self.txt_islem.setMaximumHeight(80)

        # --- TARİHLERİ GÜVENLİ ÇEKME (Hiçbir şekilde patlamaz) ---
        baslangic_str = bakim_verisi.get("bakim_baslangic_tarihi") or bakim_verisi.get("bakim_tarihi") or QDate.currentDate().toString("yyyy-MM-dd")
        bitis_str = bakim_verisi.get("bakim_bitis_tarihi") or baslangic_str
        sonraki_str = bakim_verisi.get("sonraki_bakim_tarihi") or QDate.currentDate().addMonths(6).toString("yyyy-MM-dd")

        self.dt_baslangic = QDateEdit(QDate.fromString(str(baslangic_str)[:10], "yyyy-MM-dd"))
        self.dt_baslangic.setCalendarPopup(True)

        self.dt_bitis = QDateEdit(QDate.fromString(str(bitis_str)[:10], "yyyy-MM-dd"))
        self.dt_bitis.setCalendarPopup(True)

        self.dt_sonraki_bakim = QDateEdit(QDate.fromString(str(sonraki_str)[:10], "yyyy-MM-dd"))
        self.dt_sonraki_bakim.setCalendarPopup(True)

        form_layout.addRow("Cihaz (Değiştirilemez):", self.txt_cihaz)
        form_layout.addRow("Bakımı Yapan Kişi (*):", self.txt_kisi)
        form_layout.addRow("Maliyet (₺):", self.txt_maliyet)
        form_layout.addRow("Yapılan İşlem (*):", self.txt_islem)
        form_layout.addRow("Başlangıç Tarihi (*):", self.dt_baslangic)
        form_layout.addRow("Bitiş Tarihi (*):", self.dt_bitis)
        form_layout.addRow("Sonraki Bakım Tarihi:", self.dt_sonraki_bakim)

        layout.addLayout(form_layout)

        btn_kaydet = QPushButton("Değişiklikleri Kaydet")
        btn_kaydet.setObjectName("kaydet")
        btn_kaydet.setCursor(Qt.PointingHandCursor)
        btn_kaydet.clicked.connect(self.kaydet)
        layout.addWidget(btn_kaydet)

    def kaydet(self):
        # TL Formatı Düzeltici
        metin = self.txt_maliyet.text().strip()
        if '.' in metin and ',' in metin:
            metin = metin.replace('.', '').replace(',', '.')
        elif '.' in metin and len(metin.split('.')[-1]) == 3:
            metin = metin.replace('.', '')
        else:
            metin = metin.replace(',', '.')

        try:
            maliyet = float(metin)
        except ValueError:
            maliyet = 0.0

        veri = {
            "bakim_tarihi": self.dt_baslangic.date().toString("yyyy-MM-dd"),
            "bakim_yapan_kisi": self.txt_kisi.text().strip(),
            "yapilan_islem": self.txt_islem.toPlainText().strip(),
            "maliyet": maliyet,
            "bakim_baslangic_tarihi": self.dt_baslangic.date().toString("yyyy-MM-dd"),
            "bakim_bitis_tarihi": self.dt_bitis.date().toString("yyyy-MM-dd"),
            "sonraki_bakim_tarihi": self.dt_sonraki_bakim.date().toString("yyyy-MM-dd")
        }

        if not veri["bakim_yapan_kisi"] or not veri["yapilan_islem"]:
            QMessageBox.warning(self, "Uyarı", "Kişi ve Yapılan İşlem alanları zorunludur.")
            return

        try:
            res = requests.put(f"{self.api_url}/api/bakimlar/{self.bakim_verisi['bakim_id']}", json=veri, headers={"Authorization": f"Bearer {self.token}"})
            if res.status_code == 200:
                QMessageBox.information(self, "Başarılı", "Bakım kaydı başarıyla güncellendi.")
                self.accept()
            else:
                hata_mesaji = res.json().get("detail", "Bilinmeyen Sunucu Hatası")
                QMessageBox.warning(self, "Hata", f"Güncelleme yapılamadı!\n\nSebep: {hata_mesaji}")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Sunucu hatası: {str(e)}")

class BakimYonetimEkrani(QWidget):
    """Bakım kayıtlarının listelendiği, aranabilir ve silinebilir tablo ekranı."""
    def __init__(self, api_url, token):
        super().__init__()
        self.api_url = api_url
        self.token = token
        self.basliklar = {"Authorization": f"Bearer {token}"}
        self.bakim_detaylari = {}
        self.arayuzu_olustur()

    def arayuzu_olustur(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        self.arama = QLineEdit()
        self.arama.setPlaceholderText("🔍  Cihaz, kişi veya işlem ara...")
        self.arama.textChanged.connect(self.filtrele)

        self.cip_toplam = sayi_cipi("0 kayıt")
        self.cip_yaklasan = sayi_cipi("0 yaklaşan", "#854D0E", "#FEF3C7")
        self.cip_gecmis = sayi_cipi("0 gecikmiş", "#991B1B", "#FEE2E2")

        layout.addWidget(sayfa_basligi(
            "Cihaz Bakım Geçmişi", "Yapılan bakımlar ve planlanan sonraki bakım tarihleri",
            self.arama, yenile_butonu_olustur(self.verileri_yukle),
            [self.cip_toplam, self.cip_yaklasan, self.cip_gecmis]))

        self.tablo = tablo_olustur(["CİHAZ", "YAPAN KİŞİ", "YAPILAN İŞLEM", "MALİYET",
                                    "BAKIM TARİHİ", "SONRAKİ BAKIM", "İŞLEM"])
        kb = self.tablo.horizontalHeader()
        kb.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        kb.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        kb.setSectionResizeMode(2, QHeaderView.Stretch)
        kb.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        kb.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        kb.setSectionResizeMode(5, QHeaderView.Fixed)
        kb.setSectionResizeMode(6, QHeaderView.Fixed)
        self.tablo.setColumnWidth(5, 230)
        self.tablo.setColumnWidth(6, 110)

        self.bos_mesaj = bos_mesaj_olustur("Henüz bakım kaydı yok. Üstteki “Bakım Kaydı” butonuyla ekleyebilirsiniz.")

        kart = QFrame()
        kart.setObjectName("kart")
        kl = QVBoxLayout(kart)
        kl.setContentsMargins(8, 8, 8, 8)
        kl.addWidget(self.tablo)
        kl.addWidget(self.bos_mesaj)
        layout.addWidget(kart, 1)

        self.verileri_yukle()

    def verileri_yukle(self):
        self.tablo.setRowCount(0)
        self.bakim_detaylari.clear()
        yaklasan = gecmis = 0
        try:
            res = requests.get(f"{self.api_url}/api/bakimlar", headers=self.basliklar, timeout=10)
            res.raise_for_status()
            bakimlar = res.json()
        except Exception as e:
            print("Bakım listesi yükleme hatası:", e)
            self.bos_mesaj.setText("Bakım kayıtları yüklenemedi. Sunucu bağlantısını kontrol edin.")
            self.bos_mesaj.show()
            self.tablo.hide()
            return

        self.tablo.setRowCount(len(bakimlar))
        for i, b in enumerate(bakimlar):
            self.bakim_detaylari[b["bakim_id"]] = b

            maliyet = float(b.get("maliyet") or 0.0)
            maliyet_metni = f"{maliyet:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " ₺"

            bas = tarih_goster(b.get("bakim_baslangic_tarihi") or b.get("bakim_tarihi"))
            bit = tarih_goster(b.get("bakim_bitis_tarihi"))
            tarih_metni = bas if bas == bit else f"{bas} – {bit}"

            cihaz_item = metin_item(b.get("cihaz_adi", ""), kalin=True)
            cihaz_item.setData(Qt.UserRole, b["bakim_id"])
            self.tablo.setItem(i, 0, cihaz_item)
            self.tablo.setItem(i, 1, metin_item(b.get("bakim_yapan_kisi", "")))
            self.tablo.setItem(i, 2, metin_item(b.get("yapilan_islem", "")))
            self.tablo.setItem(i, 3, metin_item(maliyet_metni, ortala=True))
            self.tablo.setItem(i, 4, metin_item(tarih_metni, ortala=True))

            sonraki = b.get("sonraki_bakim_tarihi")
            if sonraki and sonraki != "Belirtilmedi":
                widget, durum = kalan_gun_hapi(sonraki)
                yaklasan += durum == "yaklasiyor"
                gecmis += durum == "gecmis"
            else:
                widget, durum = hap("Planlanmadı", "#6B7280", "#F3F4F6"), "yok"
            self.tablo.setCellWidget(i, 5, widget)

            self.tablo.setCellWidget(i, 6, islem_butonlari(
                lambda _=False, b_id=b["bakim_id"]: self.bakim_duzenle_ac(b_id),
                lambda _=False, b_id=b["bakim_id"]: self.bakim_sil(b_id)))

        self.cip_toplam.setText(f"{len(bakimlar)} kayıt")
        self.cip_yaklasan.setText(f"{yaklasan} yaklaşan")
        self.cip_gecmis.setText(f"{gecmis} gecikmiş")
        self.bos_mesaj.setText("Henüz bakım kaydı yok. Üstteki “Bakım Kaydı” butonuyla ekleyebilirsiniz.")
        self.bos_mesaj.setVisible(not bakimlar)
        self.tablo.setVisible(bool(bakimlar))
        self.filtrele(self.arama.text())

    def filtrele(self, metin):
        """Cihaz, kişi ve işlem sütunlarında arama yapar."""
        aranan = metin.strip().lower()
        for satir in range(self.tablo.rowCount()):
            icerik = " ".join(
                (self.tablo.item(satir, k).text() if self.tablo.item(satir, k) else "")
                for k in (0, 1, 2)).lower()
            self.tablo.setRowHidden(satir, aranan not in icerik)

    def yeni_bakim_ekle(self):
        form = YeniBakimFormu(self.api_url, self.token, self)
        if form.exec():
            self.verileri_yukle()

    def bakim_duzenle_ac(self, bakim_id):
        secili_bakim = self.bakim_detaylari.get(bakim_id)
        if secili_bakim:
            form = BakimDuzenleFormu(self.api_url, self.token, secili_bakim, self)
            if form.exec():
                self.verileri_yukle()

    def bakim_sil(self, bakim_id):
        kayit = self.bakim_detaylari.get(bakim_id)
        if not kayit:
            return
        if not sil_onayi(self, "Bakım Kaydını Sil",
                         f"“{kayit.get('cihaz_adi', '')}” cihazının bu bakım kaydı silinsin mi?"):
            return
        try:
            res = requests.delete(f"{self.api_url}/api/bakimlar/{bakim_id}", headers=self.basliklar, timeout=10)
            if res.status_code == 200:
                self.verileri_yukle()
            else:
                hata = res.json().get("detail", "Bilinmeyen hata")
                QMessageBox.warning(self, "Silinemedi", hata)
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Sunucuya ulaşılamadı: {e}")