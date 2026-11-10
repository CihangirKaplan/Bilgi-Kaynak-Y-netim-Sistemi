"""Cihaz envanteri: liste ekranı, 'Cihaz ekle / durum güncelle' formu ve düzenleme listesi.

Görünüm, bakım/kalibrasyon/arıza ekranlarıyla aynı ortak bileşenleri (tablo_tasarimi) kullanır.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFormLayout, QFrame, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from api_yoneticisi import oturum_kontrollu_istek, oturum_hatasi_mi
from tablo_tasarimi import (FORM_STIL, bos_mesaj_olustur, hap, metin_item, sayfa_basligi,
                            sayi_cipi, tablo_olustur, tek_islem_butonu, yenile_butonu_olustur)

# Sunucu cihaz durumunu veritabanı değeriyle verir; ekranda okunaklı Türkçe adı gösterilir.
# veritabanı değeri -> (görünen ad, yazı rengi, arka plan)
DURUMLAR = {
    "Kullanima_Hazir": ("Kullanıma Hazır", "#166534", "#DCFCE7"),
    "Rezerve": ("Rezerve", "#1D4ED8", "#DBEAFE"),
    "Kullanimda": ("Kullanımda", "#0E7490", "#CFFAFE"),
    "Bakimda": ("Bakımda", "#854D0E", "#FEF3C7"),
    "Kalibrasyonda": ("Kalibrasyonda", "#6D28D9", "#EDE9FE"),
    "Arizali": ("Arızalı", "#991B1B", "#FEE2E2"),
    "Kullanim_Disi": ("Kullanım Dışı", "#475569", "#E2E8F0"),
}
BILGI_KUTUSU_STILI = ("background: #FEF3C7; color: #854D0E; border: 1px solid #FDE68A; border-radius: 10px; "
                      "padding: 10px 12px; font-size: 12px; font-weight: 700;")


def durum_hapi(durum):
    ad, renk, arka = DURUMLAR.get(durum, (str(durum or "-"), "#6B7280", "#F3F4F6"))
    return hap(ad, renk, arka)


class CihazIslemFormu(QDialog):
    """Cihaz Ekleme ve Düzenleme İşlemleri İçin Ortak Form"""
    def __init__(self, api_url, token, islem_turu="EKLE", cihaz_veri=None):
        super().__init__()
        self.api_url = api_url
        self.token = token
        self.islem_turu = islem_turu
        self.cihaz_veri = cihaz_veri
        
        baslik = "Yeni Cihaz Ekle" if islem_turu == "EKLE" else "Cihaz Durumunu Güncelle"
        self.setWindowTitle(f"TKYS — {baslik}")
        self.setMinimumWidth(440)
        self.setStyleSheet(FORM_STIL)

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        form_layout.setSpacing(15)
        
        self.txt_envanter = QLineEdit()
        self.txt_ad = QLineEdit()
        self.txt_marka = QLineEdit()
        self.txt_seri = QLineEdit()
        
        self.cmb_durum = QComboBox()
        for db_degeri, (ad, _renk, _arka) in DURUMLAR.items():
            self.cmb_durum.addItem(ad, db_degeri)         # gösterilen ad + sunucunun anladığı değer

        self.cmb_oda = QComboBox()
        self.cmb_oda.addItem("Oda Seçiniz (Opsiyonel)", None)
        self.odalari_yukle()

        form_layout.addRow("Envanter Kodu (*):", self.txt_envanter)
        form_layout.addRow("Cihaz Adı (*):", self.txt_ad)
        form_layout.addRow("Marka / Model:", self.txt_marka)
        form_layout.addRow("Seri No:", self.txt_seri)
        form_layout.addRow("Zimmetli Oda:", self.cmb_oda)
        
        if islem_turu == "GUNCELLE":
            self.txt_envanter.setReadOnly(True)                  # gri görünüm FORM_STIL'den gelir
            form_layout.addRow("Durum (*):", self.cmb_durum)
            self.formu_doldur()
        
        layout.addLayout(form_layout)
        
        self.btn_kaydet = QPushButton("Kaydet")
        self.btn_kaydet.setObjectName("kaydet")
        self.btn_kaydet.setCursor(Qt.PointingHandCursor)
        self.btn_kaydet.clicked.connect(self.kaydet)
        layout.addWidget(self.btn_kaydet)

    def odalari_yukle(self):
        try:
            cevap = oturum_kontrollu_istek("GET", f"{self.api_url}/api/odalar", headers={"Authorization": f"Bearer {self.token}"})
            if oturum_hatasi_mi(cevap):
                return
            if cevap.status_code == 200:
                for oda in cevap.json():
                    if oda.get("aktif_mi"):
                        self.cmb_oda.addItem(oda["oda_adi"], oda["oda_id"])
        except:
            pass

    def formu_doldur(self):
        self.txt_envanter.setText(self.cihaz_veri.get("envanter_kodu", ""))
        self.txt_ad.setText(self.cihaz_veri.get("cihaz_adi", ""))
        self.txt_marka.setText(self.cihaz_veri.get("marka_model", ""))
        self.txt_seri.setText(self.cihaz_veri.get("seri_no", ""))
        oda_indeks = self.cmb_oda.findData(self.cihaz_veri.get("zimmetli_oda_id"))
        if oda_indeks >= 0:
            self.cmb_oda.setCurrentIndex(oda_indeks)
        indeks = self.cmb_durum.findData(self.cihaz_veri.get("durum"))
        if indeks >= 0:                                    # bilinmeyen değerde ilk seçeneğe sessizce düşme
            self.cmb_durum.setCurrentIndex(indeks)

    def kaydet(self):
        if not self.txt_envanter.text().strip() or not self.txt_ad.text().strip():
            QMessageBox.warning(self, "Hata", "Envanter kodu ve cihaz adı zorunludur!")
            return

        db_durumu = self.cmb_durum.currentData() or "Kullanima_Hazir"

        veri = {
            "envanter_kodu": self.txt_envanter.text().strip(),
            "cihaz_adi": self.txt_ad.text().strip(),
            "marka_model": self.txt_marka.text().strip() or None,
            "seri_no": self.txt_seri.text().strip() or None,
            "durum": db_durumu if self.islem_turu == "GUNCELLE" else "Kullanima_Hazir"
        }
        
        secili_oda = self.cmb_oda.currentData()
        if secili_oda:
            veri["zimmetli_oda_id"] = secili_oda

        headers = {"Authorization": f"Bearer {self.token}"}
        
        try:
            if self.islem_turu == "EKLE":
                cevap = oturum_kontrollu_istek("POST", f"{self.api_url}/api/cihazlar", json=veri, headers=headers)
                if oturum_hatasi_mi(cevap):
                    return
            else:
                cevap = oturum_kontrollu_istek("PATCH", f"{self.api_url}/api/cihazlar/{self.cihaz_veri['cihaz_id']}", json=veri, headers=headers)
                if oturum_hatasi_mi(cevap):
                    return
            
            if cevap.status_code in [200, 201]:
                QMessageBox.information(self, "Başarılı", "İşlem başarıyla kaydedildi.")
                self.accept()
            else:
                # Gelen hatayı ne olursa olsun zorla düz metne (str) çeviriyoruz ki PySide6 çökmesin!
                hata_detay = str(cevap.json().get('detail', 'Bilinmeyen bir hata oluştu.'))
                QMessageBox.critical(self, "Hata", hata_detay)
        except Exception as e:
            QMessageBox.critical(self, "Bağlantı Hatası", f"Sunucuya ulaşılamadı: {str(e)}")

DURUM_ROLU = Qt.UserRole + 1      # tablo satırında cihazın veritabanı durumu (filtre için)


class CihazYonetimEkrani(QWidget):
    """Ana Cihaz Listesi Ekranı"""
    def __init__(self, api_url, token, yetkili_mi=False):
        super().__init__()
        self.api_url = api_url
        self.token = token
        self.yetkili_mi = yetkili_mi
        self.durum_filtresi = None          # None = hepsi; aksi halde yalnızca bu veritabanı durumundaki cihazlar
        self.arayuzu_olustur()

    def arayuzu_olustur(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        self.arama = QLineEdit()
        self.arama.setPlaceholderText("🔍  Envanter kodu, cihaz veya marka ara...")
        self.arama.textChanged.connect(self.filtrele)

        self.cip_toplam = sayi_cipi("0 cihaz")
        self.cip_hazir = sayi_cipi("0 kullanıma hazır", "#166534", "#DCFCE7")
        self.cip_bakimda = sayi_cipi("0 bakım/kalibrasyon", "#854D0E", "#FEF3C7")
        self.cip_arizali = sayi_cipi("0 arızalı", "#991B1B", "#FEE2E2")

        layout.addWidget(sayfa_basligi(
            "Cihaz Envanteri", "Kayıtlı cihazlar ve anlık durumları",
            self.arama, yenile_butonu_olustur(self.verileri_yukle),
            [self.cip_toplam, self.cip_hazir, self.cip_bakimda, self.cip_arizali]))

        # Ana paneldeki durum kartından gelindiğinde görünür; filtreyi tek tıkla kaldırır.
        self.filtre_seridi = QFrame()
        self.filtre_seridi.setObjectName("filtreSeridi")
        self.filtre_seridi.setStyleSheet("QFrame#filtreSeridi { background: #EFF6FF; border: 1px solid #BFDBFE; "
                                         "border-radius: 12px; }")
        fs = QHBoxLayout(self.filtre_seridi)
        fs.setContentsMargins(16, 8, 10, 8)
        self.lbl_filtre = QLabel("")
        self.lbl_filtre.setStyleSheet("color: #1E3A8A; font-size: 13px; font-weight: 800; background: transparent;")
        self.btn_filtre_kaldir = QPushButton("✕  Filtreyi kaldır, tümünü göster")
        self.btn_filtre_kaldir.setCursor(Qt.PointingHandCursor)
        self.btn_filtre_kaldir.setStyleSheet(
            "QPushButton { background: #DBEAFE; color: #1D4ED8; border: none; border-radius: 10px; padding: 6px 14px; "
            "font-size: 12px; font-weight: 800; } QPushButton:hover { background: #BFDBFE; }")
        self.btn_filtre_kaldir.clicked.connect(self.durum_filtresini_temizle)
        fs.addWidget(self.lbl_filtre)
        fs.addStretch()
        fs.addWidget(self.btn_filtre_kaldir)
        self.filtre_seridi.hide()
        layout.addWidget(self.filtre_seridi)

        self.tablo = tablo_olustur(["ENVANTER KODU", "CİHAZ ADI", "MARKA / MODEL", "SERİ NO", "DURUM"])
        kb = self.tablo.horizontalHeader()
        kb.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        kb.setSectionResizeMode(1, QHeaderView.Stretch)
        kb.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        kb.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        kb.setSectionResizeMode(4, QHeaderView.Fixed)
        self.tablo.setColumnWidth(4, 160)

        self.bos_mesaj = bos_mesaj_olustur("Henüz cihaz kaydı yok.")

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
        try:
            cevap = oturum_kontrollu_istek("GET", f"{self.api_url}/api/cihazlar", headers={"Authorization": f"Bearer {self.token}"})
            if oturum_hatasi_mi(cevap):
                return
            cevap.raise_for_status()
            cihazlar = cevap.json()
        except Exception as e:
            print(f"Cihaz listesi yükleme hatası: {e}")
            self.bos_mesaj.setText("Cihazlar yüklenemedi. Sunucu bağlantısını kontrol edin.")
            self.bos_mesaj.show()
            self.tablo.hide()
            return

        hazir = bakimda = arizali = 0
        self.tablo.setRowCount(len(cihazlar))
        for satir, cihaz in enumerate(cihazlar):
            durum = cihaz.get("durum")
            hazir += durum == "Kullanima_Hazir"
            bakimda += durum in ("Bakimda", "Kalibrasyonda")
            arizali += durum == "Arizali"

            kod_item = metin_item(str(cihaz.get("envanter_kodu") or ""), kalin=True)
            kod_item.setData(Qt.UserRole, cihaz.get("cihaz_id"))
            kod_item.setData(DURUM_ROLU, durum)
            self.tablo.setItem(satir, 0, kod_item)
            self.tablo.setItem(satir, 1, metin_item(str(cihaz.get("cihaz_adi") or "")))
            self.tablo.setItem(satir, 2, metin_item(cihaz.get("marka_model") or "-"))
            self.tablo.setItem(satir, 3, metin_item(cihaz.get("seri_no") or "-"))
            self.tablo.setCellWidget(satir, 4, durum_hapi(durum))

        self.cip_toplam.setText(f"{len(cihazlar)} cihaz")
        self.cip_hazir.setText(f"{hazir} kullanıma hazır")
        self.cip_bakimda.setText(f"{bakimda} bakım/kalibrasyon")
        self.cip_arizali.setText(f"{arizali} arızalı")
        self.bos_mesaj.setText("Henüz cihaz kaydı yok.")
        self.bos_mesaj.setVisible(not cihazlar)
        self.tablo.setVisible(bool(cihazlar))
        self.filtrele(self.arama.text())

    def durum_filtrele(self, durum):
        """Yalnızca bu durumdaki cihazları gösterir (ana paneldeki durum kartlarından gelinir)."""
        self.durum_filtresi = durum
        if durum:
            ad = DURUMLAR.get(durum, (durum,))[0]
            self.lbl_filtre.setText(f"🔎  Filtre: yalnızca “{ad}” cihazlar gösteriliyor")
        self.filtre_seridi.setVisible(bool(durum))
        self.filtrele(self.arama.text())

    def durum_filtresini_temizle(self):
        self.durum_filtrele(None)

    def filtrele(self, metin):
        """Envanter kodu, cihaz adı, marka ve seri no sütunlarında arama yapar; varsa durum filtresini de uygular."""
        aranan = metin.strip().lower()
        gorunen = 0
        for satir in range(self.tablo.rowCount()):
            icerik = " ".join(
                (self.tablo.item(satir, k).text() if self.tablo.item(satir, k) else "")
                for k in (0, 1, 2, 3)).lower()
            kod_item = self.tablo.item(satir, 0)
            durum = kod_item.data(DURUM_ROLU) if kod_item is not None else None
            gizle = aranan not in icerik or (self.durum_filtresi is not None and durum != self.durum_filtresi)
            self.tablo.setRowHidden(satir, gizle)
            gorunen += not gizle
        if self.tablo.rowCount():
            # Filtre/arama hiçbir cihaza uymuyorsa boş tablo yerine açıklayıcı mesaj göster.
            self.bos_mesaj.setText("Bu filtreye uyan cihaz yok." if gorunen == 0 else "Henüz cihaz kaydı yok.")
            self.bos_mesaj.setVisible(gorunen == 0)
            self.tablo.setVisible(gorunen > 0)

    def yeni_cihaz_ekle(self):
        form = CihazIslemFormu(self.api_url, self.token, islem_turu="EKLE")
        if form.exec():
            self.verileri_yukle()

    def envanter_duzenle_liste_ac(self):
        liste_formu = CihazDuzenlemeListesi(self.api_url, self.token)
        liste_formu.exec()
        # Kullanıcı düzenleme penceresini kapattığında, ana ekrandaki tabloyu da yenile:
        self.verileri_yukle()


class CihazDuzenlemeListesi(QDialog):
    """Kullanıcının cihazları listeden görüp ✎ butonuyla düzenlediği pencere"""
    def __init__(self, api_url, token, parent=None):
        super().__init__(parent)
        self.api_url = api_url
        self.token = token
        self.setWindowTitle("TKYS — Envanter Düzenleme")
        self.setMinimumSize(720, 480)
        self.setStyleSheet(FORM_STIL)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        lbl = QLabel("Düzenlemek istediğiniz cihazın sağındaki ✎ butonuna tıklayın.")
        lbl.setStyleSheet(BILGI_KUTUSU_STILI)
        lbl.setWordWrap(True)
        layout.addWidget(lbl)

        self.tablo = tablo_olustur(["ENVANTER KODU", "CİHAZ ADI", "DURUM", "İŞLEM"])
        kb = self.tablo.horizontalHeader()
        kb.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        kb.setSectionResizeMode(1, QHeaderView.Stretch)
        kb.setSectionResizeMode(2, QHeaderView.Fixed)
        kb.setSectionResizeMode(3, QHeaderView.Fixed)
        self.tablo.setColumnWidth(2, 160)
        self.tablo.setColumnWidth(3, 90)
        layout.addWidget(self.tablo, 1)

        self.verileri_yukle()

    def verileri_yukle(self):
        self.tablo.setRowCount(0)
        try:
            cevap = oturum_kontrollu_istek("GET", f"{self.api_url}/api/cihazlar", headers={"Authorization": f"Bearer {self.token}"})
            if oturum_hatasi_mi(cevap):
                return
            cevap.raise_for_status()
            cihazlar = cevap.json()
        except Exception as e:
            print(f"Düzenleme listesi yükleme hatası: {e}")
            return

        self.tablo.setRowCount(len(cihazlar))
        for satir, cihaz in enumerate(cihazlar):
            self.tablo.setItem(satir, 0, metin_item(str(cihaz.get("envanter_kodu") or ""), kalin=True))
            self.tablo.setItem(satir, 1, metin_item(str(cihaz.get("cihaz_adi") or "")))
            self.tablo.setCellWidget(satir, 2, durum_hapi(cihaz.get("durum")))
            self.tablo.setCellWidget(satir, 3, tek_islem_butonu(
                lambda _=False, c=cihaz: self.cihazi_duzenle(c), "✎", "Düzenle"))

    def cihazi_duzenle(self, cihaz):
        form = CihazIslemFormu(self.api_url, self.token, islem_turu="GUNCELLE", cihaz_veri=cihaz)
        if form.exec():
            self.verileri_yukle()  # Pencere içindeki listeyi yenile
