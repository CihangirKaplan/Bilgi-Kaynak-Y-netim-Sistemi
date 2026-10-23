import requests
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QFrame
)
from PySide6.QtWidgets import (
    QDialog, QLineEdit, QComboBox, QHBoxLayout, QLabel, 
    QPushButton, QMessageBox
)
from PySide6.QtCore import Qt

class KullaniciPersonelEkrani(QWidget):
    def __init__(self, api_url, token):
        super().__init__()
        self.api_url = api_url
        self.token = token
        
        self.arayuzu_kur()
        self.verileri_cek()

    def arayuzu_kur(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 2. TABLO (Kart görünümü için çerçeve)
        ik = QFrame()
        ik.setStyleSheet("background: white; border-radius: 16px;")
        il = QVBoxLayout(ik)

        self.tablo = QTableWidget()
        self.tablo.setColumnCount(6)
        self.tablo.setHorizontalHeaderLabels([
            "Personel ID", "Kullanıcı Adı", "Personel Kodu", "Rolü", "Durum", "Kayıt Tarihi"
        ])
        
        self.tablo.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tablo.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tablo.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tablo.setStyleSheet("""
            QTableWidget {
                background-color: white;
                border: 1px solid #D0D7E5;
                border-radius: 8px;
                gridline-color: #E2E8F0;
            }
            QHeaderView::section {
                background-color: #0A1F5C;
                color: white;
                font-weight: bold;
                padding: 10px;
                border: none;
            }
        """)

        il.addWidget(self.tablo)
        layout.addWidget(ik)

    def verileri_cek(self):
        headers = {"Authorization": f"Bearer {self.token}"}
        url = f"{self.api_url}/api/personel"

        try:
            cevap = requests.get(url, headers=headers, timeout=5)
            if cevap.status_code == 200:
                personeller = cevap.json()
                self.tablo.setRowCount(len(personeller))

                for satir, p in enumerate(personeller):
                    durum = "🟢 Aktif" if p["aktif_mi"] else "🔴 Pasif"
                    tarih = str(p["olusturulma_tarihi"])[:10]

                    item_id = QTableWidgetItem(str(p["personel_id"]))
                    item_ad = QTableWidgetItem(p["kullanici_adi"])
                    item_ad.setData(Qt.UserRole, p["kullanici_id"])  # YENİ: ID'yi arka planda saklıyoruz
                    item_kod = QTableWidgetItem(p["personel_kodu"])
                    item_rol = QTableWidgetItem(p["rol_adi"])
                    item_durum = QTableWidgetItem(durum)
                    item_tarih = QTableWidgetItem(tarih)

                    for item in [item_id, item_ad, item_kod, item_rol, item_durum, item_tarih]:
                        item.setTextAlignment(Qt.AlignCenter)

                    self.tablo.setItem(satir, 0, item_id)
                    self.tablo.setItem(satir, 1, item_ad)
                    self.tablo.setItem(satir, 2, item_kod)
                    self.tablo.setItem(satir, 3, item_rol)
                    self.tablo.setItem(satir, 4, item_durum)
                    self.tablo.setItem(satir, 5, item_tarih)
            else:
                print(f"Veri çekilemedi. Hata Kodu: {cevap.status_code}")
        except Exception as e:
            print("Sunucuya bağlanılamadı:", e)

    def secili_kullanici_durum_degistir(self):
        secili_satirlar = self.tablo.selectionModel().selectedRows()
        
        if not secili_satirlar:
            QMessageBox.warning(self, "Uyarı", "Lütfen tablodan durumunu değiştirmek istediğiniz kullanıcıyı seçin.")
            return

        satir = secili_satirlar[0].row()
        kullanici_adi = self.tablo.item(satir, 1).text()
        kullanici_id = self.tablo.item(satir, 1).data(Qt.UserRole)
        mevcut_durum_metni = self.tablo.item(satir, 4).text()

        if not kullanici_id:
            QMessageBox.critical(self, "Hata", "Kullanıcı ID'si bulunamadı. Lütfen tabloyu yenileyin.")
            return

        # Dinamik soru sorma mantığı
        islem_sorusu = "aktife almak" if "Pasif" in mevcut_durum_metni else "pasife almak"
        
        cevap = QMessageBox.question(
            self, "Onay",
            f"'{kullanici_adi}' adlı kullanıcıyı {islem_sorusu} istediğinize emin misiniz?",
            QMessageBox.Yes | QMessageBox.No
        )

        if cevap == QMessageBox.Yes:
            headers = {"Authorization": f"Bearer {self.token}"}
            # YENİ ENDPOINT'E GİDİYORUZ
            url = f"{self.api_url}/api/kullanicilar/{kullanici_id}/durum-degistir"
            
            try:
                res = requests.patch(url, headers=headers, timeout=5)
                if res.status_code == 200:
                    yeni_durum_bilgisi = "Aktif" if res.json().get("yeni_durum") else "Pasif"
                    QMessageBox.information(self, "Başarılı", f"Kullanıcı başarıyla {yeni_durum_bilgisi} duruma getirildi.")
                    self.verileri_cek() 
                elif res.status_code == 403:
                    QMessageBox.warning(self, "Yetki Hatası", res.json().get("detail", "Bu işlem için yetkiniz yok."))
                else:
                    QMessageBox.critical(self, "Hata", f"Sunucu hatası: {res.status_code}")
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Bağlantı hatası:\n{str(e)}")
    def secili_kullanici_rol_degistir(self):
        secili_satirlar = self.tablo.selectionModel().selectedRows()
        
        if not secili_satirlar:
            QMessageBox.warning(self, "Uyarı", "Lütfen tablodan rolünü değiştirmek istediğiniz kullanıcıyı seçin.")
            return

        satir = secili_satirlar[0].row()
        kullanici_adi = self.tablo.item(satir, 1).text()
        kullanici_id = self.tablo.item(satir, 1).data(Qt.UserRole)
        mevcut_rol = self.tablo.item(satir, 3).text()
        
        # YENİ KONTROL: 4. sütundaki durumu (Aktif/Pasif) oku
        durum = self.tablo.item(satir, 4).text()
        if "Pasif" in durum:
            QMessageBox.warning(self, "İşlem Reddedildi", "Pasif durumdaki bir kullanıcının rolü değiştirilemez.")
            return

        if not kullanici_id:
            QMessageBox.critical(self, "Hata", "Kullanıcı ID'si bulunamadı. Lütfen tabloyu yenileyin.")
            return

        form = RolDegistirFormu(self.api_url, self.token, kullanici_id, kullanici_adi, mevcut_rol, self)
        if form.exec() == QDialog.Accepted:
            self.verileri_cek()

    def personel_tanimla_ac(self):
        form = PersonelTanimlaFormu(self.api_url, self.token, self)
        if form.exec() == QDialog.Accepted:
            self.verileri_cek()

    def kullanici_olustur_ac(self):
        form = KullaniciOlusturFormu(self.api_url, self.token, self)
        if form.exec() == QDialog.Accepted:
            self.verileri_cek()

class KullaniciOlusturFormu(QDialog):
    def __init__(self, api_url, token, ebeveyn=None):
        super().__init__(ebeveyn)
        self.api_url = api_url
        self.token = token
        self.setWindowTitle("👤 Yeni Sistem Kullanıcısı Oluştur")
        self.setFixedSize(400, 260) 
        
        # Modern CSS Tasarımı
        self.setStyleSheet("""
            QDialog { background-color: #F8FAFC; }
            QLabel { font-weight: bold; color: #1E293B; font-size: 13px; }
            QComboBox, QLineEdit {
                background-color: white;
                border: 1px solid #CBD5E1;
                border-radius: 8px;
                padding: 10px 12px;
                color: #0F172A;
                font-size: 13px;
            }
            QComboBox::drop-down { border: none; width: 24px; }
            QComboBox:focus, QLineEdit:focus { border: 1px solid #3B82F6; }
            QPushButton { border-radius: 8px; padding: 10px 15px; font-weight: bold; font-size: 13px; }
            QPushButton#btn_iptal { background-color: white; border: 1px solid #CBD5E1; color: #475569; }
            QPushButton#btn_iptal:hover { background-color: #F1F5F9; }
            QPushButton#btn_kaydet { background-color: #2563EB; color: white; border: none; }
            QPushButton#btn_kaydet:hover { background-color: #1D4ED8; }
        """)
        self.arayuzu_kur()

    def arayuzu_kur(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 25, 20, 20)

        # Kullanıcı Adı Girdisi
        layout.addWidget(QLabel("Kullanıcı Adı:"))
        self.input_kullanici_adi = QLineEdit()
        self.input_kullanici_adi.setPlaceholderText("Kullanıcı adını giriniz...")
        layout.addWidget(self.input_kullanici_adi)

        # Rol Seçimi
        layout.addWidget(QLabel("Sistem Rolü:"))
        self.combo_rol = QComboBox()
        self.combo_rol.addItem("— Rol seçiniz —", None)
        self.combo_rol.setCursor(Qt.PointingHandCursor)
        
        roller = [
            ("Psikolog", 1),
            ("Memur", 2),
            ("Müdür (Yönetici)", 3),
            ("Danışma Öğrencisi", 4),
            ("Proje Asistanı", 5),
            ("Sistem Admin", 6)
        ]
        for ad, rol_id in roller:
            self.combo_rol.addItem(ad, rol_id)
            
        self.combo_rol.setCurrentIndex(0)
        layout.addWidget(self.combo_rol)

        layout.addStretch()

        # Butonlar
        buton_layout = QHBoxLayout()
        buton_layout.setSpacing(10)
        
        self.btn_iptal = QPushButton("İptal")
        self.btn_iptal.setObjectName("btn_iptal")
        self.btn_iptal.setCursor(Qt.PointingHandCursor)
        self.btn_iptal.clicked.connect(self.reject)
        
        self.btn_kaydet = QPushButton("Kullanıcıyı Oluştur")
        self.btn_kaydet.setObjectName("btn_kaydet")
        self.btn_kaydet.setCursor(Qt.PointingHandCursor)
        self.btn_kaydet.clicked.connect(self.kaydet)

        buton_layout.addWidget(self.btn_iptal)
        buton_layout.addWidget(self.btn_kaydet)
        layout.addLayout(buton_layout)

    def kaydet(self):
        kullanici_adi = self.input_kullanici_adi.text().strip()
        rol_id = self.combo_rol.currentData()

        if not kullanici_adi:
            QMessageBox.warning(self, "Uyarı", "Kullanıcı adı boş bırakılamaz.")
            return

        if rol_id is None:
            QMessageBox.warning(self, "Uyarı", "Lütfen bir rol seçiniz.")
            return

        veri = {"kullanici_adi": kullanici_adi, "rol_id": rol_id}
        headers = {"Authorization": f"Bearer {self.token}"}

        try:
            cevap = requests.post(f"{self.api_url}/api/kullanicilar", json=veri, headers=headers, timeout=5)
            
            if cevap.status_code == 201:
                sonuc = cevap.json()
                gecici_parola = sonuc.get("gecici_parola", "HATA")
                
                mesaj = (f"Kullanıcı hesabı başarıyla oluşturuldu!\n\n"
                         f"👤 Kullanıcı Adı: {kullanici_adi}\n"
                         f"🔑 Geçici Parola: {gecici_parola}\n\n"
                         f"Lütfen bu parolayı kopyalayıp kullanıcıya iletin. "
                         f"Kullanıcı ilk girişinde şifresini değiştirmek zorunda kalacaktır.")
                
                QMessageBox.information(self, "Kayıt Başarılı", mesaj)
                self.accept()
            
            elif cevap.status_code == 409:
                QMessageBox.warning(self, "Hata", "Bu kullanıcı adı zaten kullanılıyor. Lütfen farklı bir isim seçin.")
            else:
                QMessageBox.critical(self, "Hata", f"Sunucu hatası: Kod {cevap.status_code}")
                
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Bağlantı hatası:\n{str(e)}")

class PersonelTanimlaFormu(QDialog):
    def __init__(self, api_url, token, ebeveyn=None):
        super().__init__(ebeveyn)
        self.api_url = api_url
        self.token = token
        self.setWindowTitle("🧑‍💼 Personel Tanımla")
        self.setFixedSize(400, 260)
        
        # Modern CSS Tasarımı
        self.setStyleSheet("""
            QDialog { background-color: #F8FAFC; }
            QLabel { font-weight: bold; color: #1E293B; font-size: 13px; }
            QComboBox, QLineEdit {
                background-color: white;
                border: 1px solid #CBD5E1;
                border-radius: 8px;
                padding: 10px 12px;
                color: #0F172A;
                font-size: 13px;
            }
            QComboBox::drop-down { border: none; width: 24px; }
            QComboBox:focus, QLineEdit:focus { border: 1px solid #3B82F6; }
            QLineEdit:read-only {
                background-color: #F1F5F9;
                color: #64748B;
                border: 1px dashed #94A3B8;
            }
            QPushButton { border-radius: 8px; padding: 10px 15px; font-weight: bold; font-size: 13px; }
            QPushButton#btn_iptal { background-color: white; border: 1px solid #CBD5E1; color: #475569; }
            QPushButton#btn_iptal:hover { background-color: #F1F5F9; }
            QPushButton#btn_kaydet { background-color: #2563EB; color: white; border: none; }
            QPushButton#btn_kaydet:hover { background-color: #1D4ED8; }
        """)
        
        self.arayuzu_kur()
        self.kullanicilari_yukle()

    def arayuzu_kur(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 25, 20, 20)

        layout.addWidget(QLabel("Personel Yapılacak Kullanıcı:"))
        self.combo_kullanici = QComboBox()
        self.combo_kullanici.addItem("— Bekleyen Kullanıcı Seçiniz —", None)
        self.combo_kullanici.setCursor(Qt.PointingHandCursor)
        
        # Seçim değiştiğinde otomatik kod üretme fonksiyonunu tetikler
        self.combo_kullanici.currentIndexChanged.connect(self.kodu_otomatik_olustur)
        layout.addWidget(self.combo_kullanici)

        layout.addWidget(QLabel("Personel Kodu (Sistem Tarafından Atanır):"))
        self.input_personel_kodu = QLineEdit()
        self.input_personel_kodu.setReadOnly(True)
        self.input_personel_kodu.setPlaceholderText("Kullanıcı seçildiğinde otomatik atanacak")
        layout.addWidget(self.input_personel_kodu)

        layout.addStretch()

        buton_layout = QHBoxLayout()
        buton_layout.setSpacing(10)
        
        self.btn_iptal = QPushButton("İptal")
        self.btn_iptal.setObjectName("btn_iptal")
        self.btn_iptal.setCursor(Qt.PointingHandCursor)
        self.btn_iptal.clicked.connect(self.reject)
        
        self.btn_kaydet = QPushButton("Personel Olarak Ata")
        self.btn_kaydet.setObjectName("btn_kaydet")
        self.btn_kaydet.setCursor(Qt.PointingHandCursor)
        self.btn_kaydet.clicked.connect(self.kaydet)

        buton_layout.addWidget(self.btn_iptal)
        buton_layout.addWidget(self.btn_kaydet)
        layout.addLayout(buton_layout)

    def kodu_otomatik_olustur(self):
        kullanici_id = self.combo_kullanici.currentData()
        metin = self.combo_kullanici.currentText().upper()
        
        if not kullanici_id:
            self.input_personel_kodu.clear()
            return
            
        # 1. Rol kodunu belirle
        rol_kodu = "SYS"
        if "PSİKOLOG" in metin or "PSIKOLOG" in metin: rol_kodu = "PSK"
        elif "MEMUR" in metin: rol_kodu = "MEM"
        elif "MÜDÜR" in metin or "MUDUR" in metin: rol_kodu = "MUD"
        elif "ASİSTAN" in metin or "ASISTAN" in metin: rol_kodu = "AST"
        elif "ÖĞRENCİ" in metin or "OGRENCI" in metin: rol_kodu = "OGR"
        elif "ADMIN" in metin: rol_kodu = "ADM"
        
        # 2. Sunucudan mevcut personelleri çekip son sayıyı bul
        siradaki_sayi = 1
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            cevap = requests.get(f"{self.api_url}/api/personel", headers=headers, timeout=5)
            if cevap.status_code == 200:
                personeller = cevap.json()
                # Bu role ait mevcut kodları bul
                mevcut_sayilar = []
                aranan_baslangic = f"PER-{rol_kodu}-"
                
                for p in personeller:
                    kod = p.get("personel_kodu", "")
                    if kod.startswith(aranan_baslangic):
                        try:
                            # PER-PSK-001 şeklindeki kodun son 3 hanesini sayıya çevir
                            num = int(kod.split("-")[-1])
                            mevcut_sayilar.append(num)
                        except:
                            pass
                
                if mevcut_sayilar:
                    siradaki_sayi = max(mevcut_sayilar) + 1
        except Exception as e:
            print("Otomatik numara hesaplanırken hata:", e)
            
        # 3. Yeni kodu 3 haneli (001, 002) formatında kutuya yazdır
        yeni_kod = f"PER-{rol_kodu}-{siradaki_sayi:03d}"
        self.input_personel_kodu.setText(yeni_kod)

    def kullanicilari_yukle(self):
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            cevap = requests.get(f"{self.api_url}/api/kullanicilar/personel-olmayanlar", headers=headers, timeout=5)
            if cevap.status_code == 200:
                kullanicilar = cevap.json()
                for k in kullanicilar:
                    metin = f"{k['kullanici_adi']} ({k['rol_adi']})"
                    self.combo_kullanici.addItem(metin, k["kullanici_id"])
        except Exception as e:
            print(f"Kullanıcılar yüklenemedi: {e}")

    def kaydet(self):
        kullanici_id = self.combo_kullanici.currentData()
        personel_kodu = self.input_personel_kodu.text().strip()

        if kullanici_id is None:
            QMessageBox.warning(self, "Uyarı", "Lütfen listeden bir kullanıcı seçiniz.")
            return
        if not personel_kodu:
            QMessageBox.warning(self, "Uyarı", "Personel kodu otomatik üretilemedi, lütfen tekrar deneyin.")
            return

        veri = {"kullanici_id": kullanici_id, "personel_kodu": personel_kodu}
        headers = {"Authorization": f"Bearer {self.token}"}

        try:
            cevap = requests.post(f"{self.api_url}/api/personel", json=veri, headers=headers, timeout=5)
            if cevap.status_code == 201:
                QMessageBox.information(self, "Başarılı", f"Kullanıcı başarıyla personel olarak atandı.\n\nSistem Kodu: {personel_kodu}")
                self.accept()
            elif cevap.status_code == 409:
                QMessageBox.warning(self, "Hata", "Bu personel kodu zaten kullanılıyor.")
            else:
                QMessageBox.critical(self, "Hata", f"Sunucu hatası: {cevap.text}")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Bağlantı hatası:\n{str(e)}")

class RolDegistirFormu(QDialog):
    def __init__(self, api_url, token, kullanici_id, kullanici_adi, mevcut_rol, ebeveyn=None):
        super().__init__(ebeveyn)
        self.api_url = api_url
        self.token = token
        self.kullanici_id = kullanici_id
        self.kullanici_adi = kullanici_adi
        self.mevcut_rol = mevcut_rol
        
        self.setWindowTitle("🔁 Rol Ata / Değiştir")
        self.setFixedSize(400, 260) 
        
        self.setStyleSheet("""
            QDialog { background-color: #F8FAFC; }
            QLabel { font-weight: bold; color: #1E293B; font-size: 13px; }
            QComboBox, QLineEdit {
                background-color: white;
                border: 1px solid #CBD5E1;
                border-radius: 8px;
                padding: 10px 12px;
                color: #0F172A;
                font-size: 13px;
            }
            QComboBox::drop-down { border: none; width: 24px; }
            QComboBox:focus, QLineEdit:focus { border: 1px solid #3B82F6; }
            QLineEdit:read-only { background-color: #F1F5F9; color: #64748B; border: 1px dashed #94A3B8; }
            QPushButton { border-radius: 8px; padding: 10px 15px; font-weight: bold; font-size: 13px; }
            QPushButton#btn_iptal { background-color: white; border: 1px solid #CBD5E1; color: #475569; }
            QPushButton#btn_iptal:hover { background-color: #F1F5F9; }
            QPushButton#btn_kaydet { background-color: #2563EB; color: white; border: none; }
            QPushButton#btn_kaydet:hover { background-color: #1D4ED8; }
        """)
        self.arayuzu_kur()

    def arayuzu_kur(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 25, 20, 20)

        # Seçilen Kullanıcı (Kilitli)
        layout.addWidget(QLabel("İşlem Yapılan Kullanıcı:"))
        self.input_kullanici = QLineEdit()
        self.input_kullanici.setText(f"{self.kullanici_adi} (Mevcut: {self.mevcut_rol})")
        self.input_kullanici.setReadOnly(True)
        layout.addWidget(self.input_kullanici)

        # Yeni Rol Seçimi
        layout.addWidget(QLabel("Yeni Sistem Rolü:"))
        self.combo_rol = QComboBox()
        self.combo_rol.addItem("— Yeni Rolü Seçiniz —", None)
        self.combo_rol.setCursor(Qt.PointingHandCursor)
        
        roller = [
            ("Psikolog", 1), ("Memur", 2), ("Müdür (Yönetici)", 3),
            ("Danışma Öğrencisi", 4), ("Proje Asistanı", 5), ("Sistem Admin", 6)
        ]
        for ad, rol_id in roller:
            self.combo_rol.addItem(ad, rol_id)
            
        layout.addWidget(self.combo_rol)
        layout.addStretch()

        # Butonlar
        buton_layout = QHBoxLayout()
        buton_layout.setSpacing(10)
        
        self.btn_iptal = QPushButton("İptal")
        self.btn_iptal.setObjectName("btn_iptal")
        self.btn_iptal.setCursor(Qt.PointingHandCursor)
        self.btn_iptal.clicked.connect(self.reject)
        
        self.btn_kaydet = QPushButton("Rolü Güncelle")
        self.btn_kaydet.setObjectName("btn_kaydet")
        self.btn_kaydet.setCursor(Qt.PointingHandCursor)
        self.btn_kaydet.clicked.connect(self.kaydet)

        buton_layout.addWidget(self.btn_iptal)
        buton_layout.addWidget(self.btn_kaydet)
        layout.addLayout(buton_layout)

    def kaydet(self):
        yeni_rol_id = self.combo_rol.currentData()

        if yeni_rol_id is None:
            QMessageBox.warning(self, "Uyarı", "Lütfen listeden yeni bir rol seçiniz.")
            return

        # Sunucuna gönderilecek JSON verisi ve URL
        veri = {"rol_id": yeni_rol_id}
        headers = {"Authorization": f"Bearer {self.token}"}
        url = f"{self.api_url}/api/kullanicilar/{self.kullanici_id}/rol"

        try:
            cevap = requests.patch(url, json=veri, headers=headers, timeout=5)
            if cevap.status_code == 200:
                QMessageBox.information(self, "Başarılı", "Kullanıcının rolü başarıyla güncellendi.")
                self.accept()
            elif cevap.status_code == 403:
                QMessageBox.warning(self, "Yetki Hatası", "Bu işlem için yetkiniz yok.")
            else:
                QMessageBox.critical(self, "Hata", f"Sunucu hatası: {cevap.text}")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Bağlantı hatası:\n{str(e)}")