"""Arıza kayıtları: liste ekranı ile 'Yeni arıza bildirimi' ve 'Arıza düzenle / çöz' pencereleri.

Görünüm, bakım/kalibrasyon ekranlarıyla aynı ortak bileşenleri (tablo_tasarimi) kullanır.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFormLayout, QFrame, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMessageBox, QPushButton, QTextEdit, QVBoxLayout, QWidget,
)

from api_yoneticisi import oturum_kontrollu_istek, oturum_hatasi_mi
from tablo_tasarimi import (FORM_STIL, bos_mesaj_olustur, hap, metin_item, sayfa_basligi,
                            sayi_cipi, tablo_olustur, tek_islem_butonu, yenile_butonu_olustur)
import turkce_mesaj_kutusu as tmk

# Ortak form stiline ek: kırmızı "bildir" butonu ve uyarı kutusu
ARIZA_FORM_STIL = FORM_STIL + """
    QPushButton#tehlike { background: #DC2626; color: white; border: none; border-radius: 10px;
        padding: 12px; font-size: 14px; font-weight: 800; }
    QPushButton#tehlike:hover { background: #B91C1C; }
    QPushButton:disabled { background: #CBD5E1; color: #64748B; }
"""
UYARI_KUTUSU_STILI = ("background: #FEE2E2; color: #991B1B; border: 1px solid #FECACA; border-radius: 10px; "
                      "padding: 10px 12px; font-size: 12px; font-weight: 700;")

ACILIYETLER = ["Düşük", "Orta", "Yüksek", "Kritik"]
# aciliyet -> (yazı rengi, arka plan)
ACILIYET_RENKLERI = {
    "Kritik": ("#991B1B", "#FEE2E2"),
    "Yüksek": ("#9A3412", "#FFEDD5"),
    "Orta": ("#854D0E", "#FEF3C7"),
    "Düşük": ("#166534", "#DCFCE7"),
}


class ArizaBildirimFormu(QDialog):
    """Yeni Cihaz Arıza Bildirimi Oluşturma Ekranı (FAIL-002)"""
    def __init__(self, api_url, token, parent=None):
        super().__init__(parent)
        self.api_url = api_url
        self.token = token

        self.setWindowTitle("Yeni Arıza Bildirimi")
        self.setMinimumWidth(460)
        self.setStyleSheet(ARIZA_FORM_STIL)
        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        bilgi = QLabel("Arızalanan cihazı ve sorunun detaylarını giriniz.\n"
                       "Bu cihaz otomatik olarak 'Arızalı' durumuna geçecektir.")
        bilgi.setStyleSheet(UYARI_KUTUSU_STILI)
        bilgi.setWordWrap(True)
        layout.addWidget(bilgi)

        form_layout = QFormLayout()
        form_layout.setSpacing(15)

        self.cmb_cihaz = QComboBox()
        self.cmb_aciliyet = QComboBox()
        self.cmb_aciliyet.addItems(ACILIYETLER)
        self.txt_baslik = QLineEdit()
        self.txt_baslik.setPlaceholderText("Örn: Güç kablosu temassızlığı")
        self.txt_aciklama = QTextEdit()
        self.txt_aciklama.setPlaceholderText("Arızanın detaylarını, ne zaman fark edildiğini vb. belirtiniz...")
        self.txt_aciklama.setMaximumHeight(100)

        form_layout.addRow("Arızalı Cihaz (*):", self.cmb_cihaz)
        form_layout.addRow("Aciliyet Seviyesi (*):", self.cmb_aciliyet)
        form_layout.addRow("Sorun Başlığı (*):", self.txt_baslik)
        form_layout.addRow("Açıklama (*):", self.txt_aciklama)
        layout.addLayout(form_layout)

        self.btn_kaydet = QPushButton("Arızayı Bildir")
        self.btn_kaydet.setObjectName("tehlike")
        self.btn_kaydet.setCursor(Qt.PointingHandCursor)
        self.btn_kaydet.clicked.connect(self.kaydet)
        layout.addWidget(self.btn_kaydet)

        self.cihazlari_yukle()

    def cihazlari_yukle(self):
        """Sadece 'Kullanılabilir' ve 'Rezerve' durumdaki cihazları listeler."""
        self.cmb_cihaz.clear()
        try:
            cevap = oturum_kontrollu_istek("GET", f"{self.api_url}/api/cihazlar", headers={"Authorization": f"Bearer {self.token}"})
            if oturum_hatasi_mi(cevap):
                return
            if cevap.status_code == 200:
                aktif_cihaz_var_mi = False
                for cihaz in cevap.json():
                    # Zaten arızalı veya bakımda olan cihaza yeni arıza kaydı açılamaz
                    if cihaz["durum"] in ["Kullanima_Hazir", "Kullanılabilir", "Rezerve"]:
                        self.cmb_cihaz.addItem(f"{cihaz['envanter_kodu']} - {cihaz['cihaz_adi']}", cihaz["cihaz_id"])
                        aktif_cihaz_var_mi = True

                if not aktif_cihaz_var_mi:
                    self.cmb_cihaz.addItem("Arıza bildirilebilecek cihaz bulunamadı!", None)
                    self.btn_kaydet.setEnabled(False)
        except Exception:
            self.cmb_cihaz.addItem("Cihazlar Yüklenemedi!", None)
            self.btn_kaydet.setEnabled(False)

    def kaydet(self):
        cihaz_id = self.cmb_cihaz.currentData()
        baslik = self.txt_baslik.text().strip()
        aciklama = self.txt_aciklama.toPlainText().strip()
        aciliyet = self.cmb_aciliyet.currentText()

        if not cihaz_id:
            tmk.uyari(self, "Hata", "Lütfen geçerli bir cihaz seçin.")
            return
        if not baslik or not aciklama:
            tmk.uyari(self, "Hata", "Lütfen arıza başlığı ve açıklama alanlarını doldurun.")
            return

        veri = {
            "cihaz_id": cihaz_id,
            "ariza_baslik": baslik,
            "ariza_aciklama": aciklama,
            "aciliyet": aciliyet
        }

        try:
            cevap = oturum_kontrollu_istek("POST", f"{self.api_url}/api/arizalar", json=veri, headers={"Authorization": f"Bearer {self.token}"})
            if oturum_hatasi_mi(cevap):
                return
            if cevap.status_code in [200, 201]:
                tmk.bilgi(self, "Başarılı", "Arıza bildirimi oluşturuldu. Cihaz durumu otomatik olarak güncellendi.")
                self.accept()
            else:
                hata = str(cevap.json().get('detail', 'Bilinmeyen bir hata oluştu.'))
                tmk.hata(self, "Hata", hata)
        except Exception:
            tmk.hata(self, "Bağlantı Hatası", "Sunucuya ulaşılamadı. Bağlantınızı kontrol edip tekrar deneyin.")


class ArizaYonetimEkrani(QWidget):
    """Ana Arıza Kayıtları Listesi Ekranı"""
    def __init__(self, api_url, token, yetkili_mi=False):
        super().__init__()
        self.api_url = api_url
        self.token = token
        self.yetkili_mi = yetkili_mi
        self.ariza_detaylari = {}
        self.arayuzu_olustur()

    def arayuzu_olustur(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        self.arama = QLineEdit()
        self.arama.setPlaceholderText("🔍  Cihaz veya sorun ara...")
        self.arama.textChanged.connect(self.filtrele)

        self.cip_toplam = sayi_cipi("0 kayıt")
        self.cip_acik = sayi_cipi("0 açık", "#991B1B", "#FEE2E2")
        self.cip_cozulen = sayi_cipi("0 çözüldü", "#166534", "#DCFCE7")

        layout.addWidget(sayfa_basligi(
            "Arıza Kayıtları", "Arıza bildirimi ve takibi",
            self.arama, yenile_butonu_olustur(self.verileri_yukle),
            [self.cip_toplam, self.cip_acik, self.cip_cozulen]))

        self.tablo = tablo_olustur(["NO", "CİHAZ", "SORUN BAŞLIĞI", "ACİLİYET", "DURUM",
                                    "BİLDİRİM TARİHİ", "İŞLEM"])
        kb = self.tablo.horizontalHeader()
        kb.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        kb.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        kb.setSectionResizeMode(2, QHeaderView.Stretch)
        kb.setSectionResizeMode(3, QHeaderView.Fixed)           # etiket (hap) sütunları: içerikten
        kb.setSectionResizeMode(4, QHeaderView.Fixed)           # ölçülemediği için sabit genişlik
        kb.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        kb.setSectionResizeMode(6, QHeaderView.Fixed)
        self.tablo.setColumnWidth(3, 130)
        self.tablo.setColumnWidth(4, 110)
        self.tablo.setColumnWidth(6, 90)

        self.bos_mesaj = bos_mesaj_olustur("Henüz arıza kaydı yok.")

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
        self.ariza_detaylari = {}
        try:
            cevap = oturum_kontrollu_istek("GET", f"{self.api_url}/api/arizalar", headers={"Authorization": f"Bearer {self.token}"})
            if oturum_hatasi_mi(cevap):
                return
            cevap.raise_for_status()
            arizalar = cevap.json()
        except Exception as e:
            print(f"Arıza listesi yükleme hatası: {e}")
            self.bos_mesaj.setText("Arıza kayıtları yüklenemedi. Sunucu bağlantısını kontrol edin.")
            self.bos_mesaj.show()
            self.tablo.hide()
            return

        acik = cozulen = 0
        self.tablo.setRowCount(len(arizalar))
        for satir, ar in enumerate(arizalar):
            ariza_id = ar.get("ariza_id")
            self.ariza_detaylari[ariza_id] = ar
            cozuldu = ar.get("durum") == "Çözüldü"
            cozulen += cozuldu
            acik += not cozuldu

            self.tablo.setItem(satir, 0, metin_item(str(ariza_id if ariza_id is not None else ""), ortala=True))
            self.tablo.setItem(satir, 1, metin_item(str(ar.get("cihaz_adi") or "Bilinmeyen"), kalin=True))
            self.tablo.setItem(satir, 2, metin_item(ar.get("ariza_baslik") or ""))

            aciliyet = ar.get("aciliyet") or "Belirtilmedi"
            renk, arka = ACILIYET_RENKLERI.get(aciliyet, ("#6B7280", "#F3F4F6"))
            self.tablo.setCellWidget(satir, 3, hap(aciliyet, renk, arka))

            if cozuldu:
                self.tablo.setCellWidget(satir, 4, hap("Çözüldü", "#166534", "#DCFCE7"))
            else:
                self.tablo.setCellWidget(satir, 4, hap("Açık", "#991B1B", "#FEE2E2"))

            tarih = str(ar.get("bildirim_tarihi") or "")[:16].replace("T", " ")
            self.tablo.setItem(satir, 5, metin_item(tarih, ortala=True))

            if self.yetkili_mi and not cozuldu:
                self.tablo.setCellWidget(satir, 6, tek_islem_butonu(
                    lambda _=False, a_id=ariza_id: self.ariza_duzenle_form_ac(a_id),
                    "✎", "Düzenle / Çöz"))

        self.cip_toplam.setText(f"{len(arizalar)} kayıt")
        self.cip_acik.setText(f"{acik} açık")
        self.cip_cozulen.setText(f"{cozulen} çözüldü")
        self.bos_mesaj.setText("Henüz arıza kaydı yok.")
        self.bos_mesaj.setVisible(not arizalar)
        self.tablo.setVisible(bool(arizalar))
        self.filtrele(self.arama.text())

    def filtrele(self, metin):
        """Cihaz adı ve sorun başlığında arama yapar."""
        aranan = metin.strip().lower()
        for satir in range(self.tablo.rowCount()):
            icerik = " ".join(
                (self.tablo.item(satir, k).text() if self.tablo.item(satir, k) else "")
                for k in (1, 2)).lower()
            self.tablo.setRowHidden(satir, aranan not in icerik)

    def ariza_duzenle_form_ac(self, ariza_id):
        secili_ariza = self.ariza_detaylari.get(ariza_id)
        if secili_ariza:
            form = ArizaDuzenleFormu(self.api_url, self.token, secili_ariza, self)
            if form.exec():
                self.verileri_yukle()

    def yeni_ariza_bildirimi(self):
        form = ArizaBildirimFormu(self.api_url, self.token, self)
        if form.exec():
            self.verileri_yukle()


class ArizaDuzenleFormu(QDialog):
    """Mevcut Arızayı Düzenleme ve Çözme Ekranı"""
    def __init__(self, api_url, token, ariza_verisi, parent=None):
        super().__init__(parent)
        self.api_url = api_url
        self.token = token
        self.ariza_verisi = ariza_verisi

        self.setWindowTitle(f"Arıza Düzenle - {ariza_verisi['cihaz_adi']}")
        self.setMinimumWidth(460)
        self.setStyleSheet(ARIZA_FORM_STIL)

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        form_layout.setSpacing(15)

        self.lbl_cihaz = QLineEdit(self.ariza_verisi["cihaz_adi"])
        self.lbl_cihaz.setReadOnly(True)

        self.cmb_aciliyet = QComboBox()
        self.cmb_aciliyet.addItems(ACILIYETLER)
        self.cmb_aciliyet.setCurrentText(self.ariza_verisi.get("aciliyet", "Orta"))

        self.txt_baslik = QLineEdit(self.ariza_verisi.get("ariza_baslik", ""))

        self.txt_aciklama = QTextEdit(self.ariza_verisi.get("ariza_aciklama", ""))
        self.txt_aciklama.setMaximumHeight(100)

        self.cmb_durum = QComboBox()
        self.cmb_durum.addItems(["Açık (devam ediyor)", "Çözüldü (cihaz kullanıma açılır)"])
        if self.ariza_verisi.get("durum") == "Çözüldü":
            self.cmb_durum.setCurrentIndex(1)

        form_layout.addRow("Cihaz:", self.lbl_cihaz)
        form_layout.addRow("Aciliyet Seviyesi:", self.cmb_aciliyet)
        form_layout.addRow("Sorun Başlığı:", self.txt_baslik)
        form_layout.addRow("Açıklama:", self.txt_aciklama)
        form_layout.addRow("Mevcut Durum:", self.cmb_durum)
        layout.addLayout(form_layout)

        self.btn_kaydet = QPushButton("Güncelle")
        self.btn_kaydet.setObjectName("kaydet")
        self.btn_kaydet.setCursor(Qt.PointingHandCursor)
        self.btn_kaydet.clicked.connect(self.kaydet)
        layout.addWidget(self.btn_kaydet)

    def kaydet(self):
        baslik = self.txt_baslik.text().strip()
        aciklama = self.txt_aciklama.toPlainText().strip()

        if not baslik or not aciklama:
            tmk.uyari(self, "Hata", "Başlık ve açıklama boş bırakılamaz.")
            return

        veri = {
            "ariza_baslik": baslik,
            "ariza_aciklama": aciklama,
            "aciliyet": self.cmb_aciliyet.currentText(),
            "cozuldu_mu": "Çözüldü" in self.cmb_durum.currentText()
        }

        try:
            cevap = oturum_kontrollu_istek("PUT",
                f"{self.api_url}/api/arizalar/{self.ariza_verisi['ariza_id']}",
                json=veri,
                headers={"Authorization": f"Bearer {self.token}"}
            )
            if oturum_hatasi_mi(cevap):
                return
            if cevap.status_code == 200:
                tmk.bilgi(self, "Başarılı", "Arıza kaydı başarıyla güncellendi.")
                self.accept()
            else:
                tmk.uyari(self, "Hata", f"İşlem reddedildi. Kod: {cevap.status_code}")
        except Exception as e:
            tmk.hata(self, "Hata", f"Sunucuya bağlanılamadı: {str(e)}")
