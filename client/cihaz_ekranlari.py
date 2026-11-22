from client.api_yoneticisi import api_hata_mesaji
"""Cihaz envanteri: liste ekranı, 'Cihaz ekle / durum güncelle' formu ve düzenleme listesi.

Görünüm, bakım/kalibrasyon/arıza ekranlarıyla aynı ortak bileşenleri (tablo_tasarimi) kullanır.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFormLayout, QFrame, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from client.api_yoneticisi import oturum_kontrollu_istek, oturum_hatasi_mi
from client.liste_excel import excel_dugmesi_olustur, listeyi_excele_aktar
from client.rapor_excel import TARIH_BICIMI, _tarih_degeri
from client.tablo_tasarimi import hap_sutununu_sigdir
from client.tablo_tasarimi import cift_tikla_ac, satira_kimlik_ata, tehlike_dugmesi
from client.tablo_tasarimi import (FORM_STIL, bos_mesaj_olustur, hap, metin_item, sayfa_basligi,
                            sayi_cipi, tablo_olustur, tek_islem_butonu, yenile_butonu_olustur)
from client.bildirim_toast import basari_bildirimi

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


def etkin_durum(cihaz):
    """Listede gösterilen durum: sunucunun hesapladığı etkin durum (bugün bakım/kalibrasyon aralığındaki cihaz 'bakımda/kalibrasyonda').
    Eski sunucu bu alanı göndermezse kayıtlı durum kullanılır. Düzenleme formu kayıtlı (ham) durumu kullanmaya devam eder."""
    return cihaz.get("etkin_durum") or cihaz.get("durum")


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


        form_layout.addRow("Envanter Kodu (*):", self.txt_envanter)
        form_layout.addRow("Cihaz Adı (*):", self.txt_ad)
        form_layout.addRow("Marka / Model:", self.txt_marka)
        form_layout.addRow("Seri No:", self.txt_seri)
        
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

        # Cihazlar silinmez (bakım, kalibrasyon, arıza ve rezervasyon geçmişi bağlıdır); yerine "kullanım dışına al" vardır.
        self.btn_kullanim_disi = None
        if islem_turu == "GUNCELLE" and (cihaz_veri or {}).get("durum") != "Kullanim_Disi":
            self.btn_kullanim_disi = tehlike_dugmesi("Cihazı kullanım dışına al", self.kullanim_disi_yap)
            layout.addWidget(self.btn_kullanim_disi)

    def _kullanim_disi_onayi(self):
        kutu = QMessageBox(self)
        kutu.setIcon(QMessageBox.Warning)
        kutu.setWindowTitle("Kullanım Dışına Al")
        kutu.setText(f"“{(self.cihaz_veri or {}).get('cihaz_adi', '')}” cihazı kullanım dışına alınsın mı?")
        kutu.setInformativeText("Cihaz kullanıma ve rezervasyona kapanır. Geçmiş kayıtları silinmez; durumu istediğin zaman yeniden değiştirebilirsin.")
        evet = kutu.addButton("Evet, kullanım dışına al", QMessageBox.DestructiveRole)
        kutu.addButton("Vazgeç", QMessageBox.RejectRole)
        kutu.exec()
        return kutu.clickedButton() is evet

    def kullanim_disi_yap(self):
        if not self._kullanim_disi_onayi():
            return
        try:
            cevap = oturum_kontrollu_istek("PATCH", f"{self.api_url}/api/cihazlar/{self.cihaz_veri['cihaz_id']}",
                                           json={"durum": "Kullanim_Disi"}, headers={"Authorization": f"Bearer {self.token}"})
            if oturum_hatasi_mi(cevap):
                return
            if cevap.status_code == 200:
                basari_bildirimi(self, "Cihaz kullanım dışına alındı.")
                self.accept()
            else:
                QMessageBox.critical(self, "Hata", str(cevap.json().get("detail", "Bilinmeyen bir hata oluştu.")))
        except Exception as e:
            QMessageBox.critical(self, "Bağlantı Hatası", f"Sunucuya ulaşılamadı: {str(e)}")

    def formu_doldur(self):
        self.txt_envanter.setText(self.cihaz_veri.get("envanter_kodu", ""))
        self.txt_ad.setText(self.cihaz_veri.get("cihaz_adi", ""))
        self.txt_marka.setText(self.cihaz_veri.get("marka_model", ""))
        self.txt_seri.setText(self.cihaz_veri.get("seri_no", ""))
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
                basari_bildirimi(self, "İşlem başarıyla kaydedildi.")
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
        self.cihaz_detaylari = {}
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
            [self.cip_toplam, self.cip_hazir, self.cip_bakimda, self.cip_arizali],
            ek_butonlar=[excel_dugmesi_olustur(self.excele_aktar)]))

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

        self.tablo = tablo_olustur(["ENVANTER KODU", "CİHAZ ADI", "MARKA / MODEL", "SERİ NO", "DURUM", "GEÇMİŞ"], ortali=True)
        kb = self.tablo.horizontalHeader()
        # Uzun kod/marka/seri no sütunları şişirip diğerlerini ezmesin: sabit genişlik (sığmayan metin alt satıra sarar), ad sütunu esner.
        kb.setSectionResizeMode(0, QHeaderView.Fixed)
        self.tablo.setColumnWidth(0, 170)
        kb.setSectionResizeMode(1, QHeaderView.Stretch)
        kb.setSectionResizeMode(2, QHeaderView.Fixed)
        self.tablo.setColumnWidth(2, 190)
        kb.setSectionResizeMode(3, QHeaderView.Fixed)
        self.tablo.setColumnWidth(3, 150)
        kb.setSectionResizeMode(4, QHeaderView.Fixed)
        self.tablo.setColumnWidth(4, 170)
        kb.setSectionResizeMode(5, QHeaderView.Fixed)
        self.tablo.setColumnWidth(5, 90)
        self.tablo.setColumnHidden(5, not self.yetkili_mi)                     # geçmiş (maliyet, arıza notları) yalnızca cihaz yöneticilerine
        # Cihaz adı ekranda ilk sütun, envanter kodu ikinci olur (mantıksal sütun sırası ve kayıt kimliği değişmez; yalnızca görünüm).
        kb.moveSection(1, 0)

        cift_tikla_ac(self.tablo, self.cihaz_duzenle_ac)                       # satıra çift tıklayınca düzenleme açılır (yetkililer)
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
        self.cihaz_detaylari = {c.get("cihaz_id"): c for c in cihazlar}
        self.tablo.setRowCount(len(cihazlar))
        for satir, cihaz in enumerate(cihazlar):
            durum = etkin_durum(cihaz)                      # bugünkü bakım/kalibrasyon aralığı da hesaba katılır (ana panelle aynı)
            hazir += durum == "Kullanima_Hazir"
            bakimda += durum in ("Bakimda", "Kalibrasyonda")
            arizali += durum == "Arizali"

            kod_item = metin_item(str(cihaz.get("envanter_kodu") or ""), renk="#64748B")
            kod_item.setData(Qt.UserRole, cihaz.get("cihaz_id"))
            kod_item.setData(DURUM_ROLU, durum)
            self.tablo.setItem(satir, 0, kod_item)
            ad_item = metin_item(str(cihaz.get("cihaz_adi") or ""), kalin=True)
            ad_item.setToolTip(str(cihaz.get("cihaz_adi") or ""))
            self.tablo.setItem(satir, 1, ad_item)
            self.tablo.setItem(satir, 2, metin_item(cihaz.get("marka_model") or "-"))
            self.tablo.setItem(satir, 3, metin_item(cihaz.get("seri_no") or "-"))
            self.tablo.setCellWidget(satir, 4, durum_hapi(durum))
            if self.yetkili_mi:
                self.tablo.setCellWidget(satir, 5, tek_islem_butonu(
                    lambda _=False, c_id=cihaz.get("cihaz_id"): self.gecmis_ac(c_id), "🕘", "Cihaz geçmişi: bakım, kalibrasyon, arıza, rezervasyon",
                    renk="#1D4ED8", arka="#DBEAFE", hover="#BFDBFE"))
            satira_kimlik_ata(self.tablo, satir, cihaz.get("cihaz_id"))

        self.cip_toplam.setText(f"{len(cihazlar)} cihaz")
        self.cip_hazir.setText(f"{hazir} kullanıma hazır")
        self.cip_bakimda.setText(f"{bakimda} bakım/kalibrasyon")
        self.cip_arizali.setText(f"{arizali} arızalı")
        self.bos_mesaj.setText("Henüz cihaz kaydı yok.")
        hap_sutununu_sigdir(self.tablo, 4, en_az=120)            # "Kullanıma Hazır" rozeti kesilmesin
        self.bos_mesaj.setVisible(not cihazlar)
        self.tablo.setVisible(bool(cihazlar))
        self.filtrele(self.arama.text())

    def gecmis_ac(self, cihaz_id):
        """Cihazın bakım, kalibrasyon, arıza ve rezervasyon geçmişini tek zaman çizgisinde açar."""
        from client.cihaz_gecmisi_penceresi import CihazGecmisiPenceresi
        CihazGecmisiPenceresi(self.api_url, self.token, cihaz_id, self).exec()

    def gorunen_cihazlar(self):
        """Arama ve durum filtresine uyan (tabloda görünen) cihazlar, tablo sırasıyla."""
        sonuc = []
        for satir in range(self.tablo.rowCount()):
            kod_item = self.tablo.item(satir, 0)
            if kod_item is None or self.tablo.isRowHidden(satir):
                continue
            cihaz = self.cihaz_detaylari.get(kod_item.data(Qt.UserRole))
            if cihaz is not None:
                sonuc.append(cihaz)
        return sonuc

    def excele_aktar(self):
        """Ekranda görünen cihazları (demirbaş sayımı için) Excel'e aktarır."""
        cihazlar = self.gorunen_cihazlar()
        filtre = [("Arama", self.arama.text().strip() or "Yok")]
        filtre.append(("Durum filtresi", DURUMLAR.get(self.durum_filtresi, (self.durum_filtresi,))[0] if self.durum_filtresi else "Tümü"))
        listeyi_excele_aktar(
            self, "Cihaz Envanteri", "cihaz_envanteri",
            [("Envanter Kodu", None), ("Cihaz Adı", None), ("Marka / Model", None), ("Seri No", None),
             ("Durum", None), ("Kayıt Tarihi", TARIH_BICIMI)],
            [[c.get("envanter_kodu") or "", c.get("cihaz_adi") or "", c.get("marka_model") or "", c.get("seri_no") or "",
              DURUMLAR.get(etkin_durum(c), (etkin_durum(c) or "",))[0], _tarih_degeri(c.get("kayit_tarihi"))]
             for c in cihazlar],
            filtre, sayfa_adi="Cihazlar", aciklama="Kayıtlı cihazların envanter listesi (demirbaş sayımı için).",
            kayit={"api_url": self.api_url, "token": self.token, "liste": "CIHAZ"},
        )

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

    def cihaz_duzenle_ac(self, cihaz_id):
        cihaz = self.cihaz_detaylari.get(cihaz_id)
        if cihaz is None or not self.yetkili_mi:
            return
        if CihazIslemFormu(self.api_url, self.token, islem_turu="GUNCELLE", cihaz_veri=cihaz).exec():
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

        self.tablo = tablo_olustur(["ENVANTER KODU", "CİHAZ ADI", "DURUM", "İŞLEM"], ortali=True)
        kb = self.tablo.horizontalHeader()
        kb.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        kb.setSectionResizeMode(1, QHeaderView.Stretch)
        kb.setSectionResizeMode(2, QHeaderView.Fixed)
        kb.setSectionResizeMode(3, QHeaderView.Fixed)
        self.tablo.setColumnWidth(2, 160)
        self.tablo.setColumnWidth(3, 90)
        layout.addWidget(self.tablo, 1)

        self.lbl_yukleme_hatasi = QLabel()
        self.lbl_yukleme_hatasi.setObjectName("cihazDuzenlemeYuklemeDurumu")
        self.lbl_yukleme_hatasi.setWordWrap(True)
        self.lbl_yukleme_hatasi.setStyleSheet(
            "color: #B42318; padding: 8px; font-size: 12px;"
        )
        self.lbl_yukleme_hatasi.hide()
        layout.addWidget(self.lbl_yukleme_hatasi)

        self.verileri_yukle()

    def verileri_yukle(self):
        self.lbl_yukleme_hatasi.hide()
        self.tablo.setRowCount(0)

        try:
            cevap = oturum_kontrollu_istek(
                "GET",
                f"{self.api_url}/api/cihazlar",
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=5,
            )

            if oturum_hatasi_mi(cevap):
                return

            if cevap.status_code != 200:
                self.lbl_yukleme_hatasi.setText(api_hata_mesaji(cevap))
                self.lbl_yukleme_hatasi.show()
                return

            cihazlar = cevap.json()
            if not isinstance(cihazlar, list):
                raise ValueError("Geçersiz cihaz listesi")

        except Exception as hata:
            self.lbl_yukleme_hatasi.setText(
                api_hata_mesaji(hata=hata)
            )
            self.lbl_yukleme_hatasi.show()
            return

        if not cihazlar:
            self.lbl_yukleme_hatasi.setText("Henüz cihaz kaydı bulunmuyor.")
            self.lbl_yukleme_hatasi.show()
            return

        self.tablo.setRowCount(len(cihazlar))
        for satir, cihaz in enumerate(cihazlar):
            self.tablo.setItem(
                satir, 0,
                metin_item(str(cihaz.get("envanter_kodu") or ""), kalin=True)
            )
            self.tablo.setItem(
                satir, 1,
                metin_item(str(cihaz.get("cihaz_adi") or ""))
            )
            self.tablo.setCellWidget(
                satir, 2, durum_hapi(cihaz.get("durum"))
            )
            self.tablo.setCellWidget(
                satir, 3,
                tek_islem_butonu(
                    lambda _=False, c=cihaz: self.cihazi_duzenle(c),
                    "✎",
                    "Düzenle",
                )
            )

    def cihazi_duzenle(self, cihaz):
        form = CihazIslemFormu(self.api_url, self.token, islem_turu="GUNCELLE", cihaz_veri=cihaz)
        if form.exec():
            self.verileri_yukle()  # Pencere içindeki listeyi yenile
