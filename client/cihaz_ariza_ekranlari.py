"""Arıza kayıtları: liste ekranı ile 'Yeni arıza bildirimi' ve 'Arıza düzenle / çöz' pencereleri.

Görünüm, bakım/kalibrasyon ekranlarıyla aynı ortak bileşenleri (tablo_tasarimi) kullanır.
"""
import logging
from client.tablo_tasarimi import cihaz_hucresi_uygula, cihaz_ipucu, tarih_saat_goster
from client.tablo_siralama import SIRALAMA_ROLU
from client.api_yoneticisi import istek_hatasi_metni, hata_detayi_metni
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFormLayout, QFrame, QHeaderView, QLabel, QLineEdit,
    QMessageBox, QPushButton, QTextEdit, QVBoxLayout, QWidget,
)

from client.api_yoneticisi import oturum_kontrollu_istek, oturum_hatasi_mi
from client.tablo_tasarimi import hap_sutununu_sigdir, hizli_doldur, daha_fazla_dugmesi
from client.tablo_tasarimi import cift_tikla_ac, satira_kimlik_ata
from client.tablo_tasarimi import (FORM_STIL, bos_mesaj_olustur, hap, metin_item, sayfa_basligi,
                            sayi_cipi, tablo_olustur, tek_islem_butonu, yenile_butonu_olustur)
from client.bildirim_toast import basari_bildirimi
from client.liste_excel import excel_dugmesi_olustur, tablodan_excele_aktar
from client.liste_siniri import ListeSiniri, daha_fazla_guncelle, kisaltma_ipucu, liste_toplami, toplam_etiketi

logger = logging.getLogger(__name__)

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


# Arıza yalnızca kullanım dışı bırakılmış cihaza açılmaz. Bakımda/kalibrasyonda ya da zaten arızalı cihaza da arıza bildirilebilir:
# sunucu kaydı alır, cihazın bakım/kalibrasyon durumunu korur (arızalı olmayan hazır cihaz "Arızalı" olur).
ARIZA_ACILMAYAN_DURUMLAR = ("Kullanim_Disi",)
DURUM_ADLARI = {
    "Kullanima_Hazir": "Kullanıma Hazır", "Kullanılabilir": "Kullanıma Hazır", "Rezerve": "Rezerve", "Kullanimda": "Kullanımda",
    "Bakimda": "Bakımda", "Kalibrasyonda": "Kalibrasyonda", "Arizali": "Zaten arızalı", "Kullanim_Disi": "Kullanım Dışı",
}
HAZIR_DURUMLAR = ("Kullanima_Hazir", "Kullanılabilir", "Rezerve", "Kullanimda")


def ariza_cihaz_notu(durum):
    """Seçilen cihazın durumuna göre arıza bildirimi sonucunu anlatan not."""
    if durum in HAZIR_DURUMLAR or durum is None:
        return "Bu cihaz otomatik olarak 'Arızalı' durumuna geçecektir."
    if durum == "Arizali":
        return "Bu cihaz zaten arızalı; yeni arıza ayrı bir kayıt olarak eklenir, cihaz durumu değişmez."
    return f"Cihaz şu anda '{DURUM_ADLARI.get(durum, durum)}' durumunda: arıza kaydedilir, cihazın durumu değişmez."


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

        self.lbl_bilgi = QLabel("Arızalanan cihazı ve sorunun detaylarını giriniz.\n" + ariza_cihaz_notu(None))
        self.lbl_bilgi.setStyleSheet(UYARI_KUTUSU_STILI)
        self.lbl_bilgi.setWordWrap(True)
        layout.addWidget(self.lbl_bilgi)

        form_layout = QFormLayout()
        form_layout.setSpacing(15)

        self.cmb_cihaz = QComboBox()
        self.cmb_cihaz.currentIndexChanged.connect(self._cihaz_notunu_guncelle)
        self.cmb_aciliyet = QComboBox()
        self.cmb_aciliyet.addItems(ACILIYETLER)
        self.txt_baslik = QLineEdit()
        self.txt_baslik.setMaxLength(150)
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

    def _cihaz_notunu_guncelle(self, *_):
        """Seçilen cihazın durumu hazır değilse (bakımda, arızalı...) arıza bildiriminin ne yapacağını söyler."""
        durum = self.cmb_cihaz.currentData(Qt.UserRole + 1)
        self.lbl_bilgi.setText("Arızalanan cihazı ve sorunun detaylarını giriniz.\n" + ariza_cihaz_notu(durum))

    def cihazlari_yukle(self):
        """Kullanım dışı olmayan tüm cihazları listeler; hazır olmayanların yanına durumu yazılır."""
        self.cmb_cihaz.clear()
        try:
            cevap = oturum_kontrollu_istek("GET", f"{self.api_url}/api/cihazlar", headers={"Authorization": f"Bearer {self.token}"})
            if oturum_hatasi_mi(cevap):
                return
            if cevap.status_code == 200:
                aktif_cihaz_var_mi = False
                for cihaz in cevap.json():
                    if cihaz["durum"] in ARIZA_ACILMAYAN_DURUMLAR:
                        continue
                    etiket = f"{cihaz['envanter_kodu']} - {cihaz['cihaz_adi']}"
                    if cihaz["durum"] not in HAZIR_DURUMLAR:
                        etiket += f"  ({DURUM_ADLARI.get(cihaz['durum'], cihaz['durum'])})"
                    self.cmb_cihaz.addItem(etiket, cihaz["cihaz_id"])
                    self.cmb_cihaz.setItemData(self.cmb_cihaz.count() - 1, cihaz["durum"], Qt.UserRole + 1)
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
            QMessageBox.warning(self, "Hata", "Lütfen geçerli bir cihaz seçin.")
            return
        if not baslik or not aciklama:
            QMessageBox.warning(self, "Hata", "Lütfen arıza başlığı ve açıklama alanlarını doldurun.")
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
                basari_bildirimi(self, "Arıza bildirimi oluşturuldu. Cihaz durumu otomatik olarak güncellendi.")
                self.accept()
            else:
                hata = str(hata_detayi_metni(cevap, 'Bilinmeyen bir hata oluştu.'))
                QMessageBox.critical(self, "Hata", hata)
        except Exception:
            QMessageBox.critical(self, "Bağlantı Hatası", "Sunucuya ulaşılamadı. Bağlantınızı kontrol edip tekrar deneyin.")


def ariza_ipucu(ar):
    """Arıza satırının ipucu: açıklama; çözüldüyse çözüm tarihi ve çözüm notu da."""
    satirlar = [str(ar.get("ariza_aciklama") or "").strip()]
    if ar.get("durum") == "Çözüldü":
        tarih = tarih_saat_goster(ar.get("cozum_tarihi"))
        if tarih:
            satirlar.append(f"Çözüm tarihi: {tarih}")
        satirlar.append(f"Çözüm: {ar.get('cozum_notu') or 'not girilmemiş'}")
    return "\n".join(s for s in satirlar if s)


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
        self.liste_siniri = ListeSiniri()
        self.dahafazla_btn = daha_fazla_dugmesi(self.daha_fazla_yukle)

        layout.addWidget(sayfa_basligi(
            "Arıza Kayıtları", "Arıza bildirimi ve takibi",
            self.arama, yenile_butonu_olustur(self.verileri_yukle),
            [self.cip_toplam, self.cip_acik, self.cip_cozulen, self.dahafazla_btn],
            ek_butonlar=[excel_dugmesi_olustur(self.excele_aktar)]))

        self.tablo = tablo_olustur(["NO", "CİHAZ", "SORUN BAŞLIĞI", "ACİLİYET", "DURUM",
                                    "BİLDİRİM TARİHİ", "İŞLEM"], ortali=True)
        kb = self.tablo.horizontalHeader()
        kb.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        kb.setSectionResizeMode(1, QHeaderView.Fixed)                          # uzun cihaz adı sütunu şişirmesin ("…" ile kısalır, ipucunda tam)
        self.tablo.setColumnWidth(1, 230)
        cihaz_hucresi_uygula(self.tablo, 1)                                    # ad üstte (kalın), envanter kodu altta (gri)
        kb.setSectionResizeMode(2, QHeaderView.Stretch)
        kb.setSectionResizeMode(3, QHeaderView.Fixed)           # etiket (hap) sütunları: içerikten
        kb.setSectionResizeMode(4, QHeaderView.Fixed)           # ölçülemediği için sabit genişlik
        kb.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        kb.setSectionResizeMode(6, QHeaderView.Fixed)
        self.tablo.setColumnWidth(3, 130)
        self.tablo.setColumnWidth(4, 110)
        self.tablo.setColumnWidth(6, 90)

        cift_tikla_ac(self.tablo, self.ariza_duzenle_form_ac)                  # satıra çift tıklayınca düzenleme açılır
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
            cevap = oturum_kontrollu_istek("GET", f"{self.api_url}/api/arizalar", headers={"Authorization": f"Bearer {self.token}"}, params=self.liste_siniri.parametreler())
            if oturum_hatasi_mi(cevap):
                return
            cevap.raise_for_status()
            arizalar = cevap.json()
            toplam = liste_toplami(cevap, len(arizalar))
        except Exception as e:
            logger.warning("Arıza listesi yüklenemedi: %s", e)
            self.bos_mesaj.setText("Arıza kayıtları yüklenemedi. Sunucu bağlantısını kontrol edin.")
            self.bos_mesaj.show()
            self.tablo.hide()
            return

        acik = cozulen = 0
        with hizli_doldur(self.tablo):
            self.tablo.setRowCount(len(arizalar))
            for satir, ar in enumerate(arizalar):
                ariza_id = ar.get("ariza_id")
                self.ariza_detaylari[ariza_id] = ar
                cozuldu = ar.get("durum") == "Çözüldü"
                cozulen += cozuldu
                acik += not cozuldu

                self.tablo.setItem(satir, 0, metin_item(str(ariza_id if ariza_id is not None else ""), ortala=True))
                cihaz_adi = str(ar.get("cihaz_adi") or "Bilinmeyen")
                kod = ar.get("envanter_kodu")
                cihaz_item = metin_item(f"{kod}  ·  {cihaz_adi}" if kod else cihaz_adi, kalin=True)      # ad üstte, envanter kodu altta (çizici)
                cihaz_item.setToolTip(cihaz_ipucu(cihaz_item.text()))
                cihaz_item.setData(SIRALAMA_ROLU, cihaz_adi)                                              # sıralama cihaz adına göre
                self.tablo.setItem(satir, 1, cihaz_item)
                baslik_item = metin_item(ar.get("ariza_baslik") or "")
                baslik_item.setToolTip(ariza_ipucu(ar))                                                   # açıklama, çözüldüyse çözüm notu
                self.tablo.setItem(satir, 2, baslik_item)

                aciliyet = ar.get("aciliyet") or "Belirtilmedi"
                renk, arka = ACILIYET_RENKLERI.get(aciliyet, ("#6B7280", "#F3F4F6"))
                self.tablo.setCellWidget(satir, 3, hap(aciliyet, renk, arka))

                if cozuldu:
                    self.tablo.setCellWidget(satir, 4, hap("Çözüldü", "#166534", "#DCFCE7"))
                else:
                    self.tablo.setCellWidget(satir, 4, hap("Açık", "#991B1B", "#FEE2E2"))

                self.tablo.setItem(satir, 5, metin_item(tarih_saat_goster(ar.get("bildirim_tarihi")), ortala=True))

                if self.yetkili_mi:
                    # Açık arıza düzenlenir/çözülür; çözülmüş arıza yanlışlıkla çözüldü işaretlendiyse yeniden açılabilir.
                    if cozuldu:
                        dugme = tek_islem_butonu(lambda _=False, a_id=ariza_id: self.ariza_duzenle_form_ac(a_id), "↺", "Düzenle / yeniden aç",
                                                 renk="#1D4ED8", arka="#DBEAFE", hover="#BFDBFE")
                    else:
                        dugme = tek_islem_butonu(lambda _=False, a_id=ariza_id: self.ariza_duzenle_form_ac(a_id), "✎", "Düzenle / Çöz")
                    self.tablo.setCellWidget(satir, 6, dugme)
                    satira_kimlik_ata(self.tablo, satir, ariza_id)      # yetkili kullanıcı için her satır (açık ya da çözülmüş) çift tıkla açılır

        self.cip_toplam.setText(toplam_etiketi(len(arizalar), toplam))
        self.cip_toplam.setToolTip(kisaltma_ipucu(len(arizalar), toplam))
        daha_fazla_guncelle(self.dahafazla_btn, self.liste_siniri, len(arizalar), toplam)
        self.cip_acik.setText(f"{acik} açık")
        self.cip_cozulen.setText(f"{cozulen} çözüldü")
        self.bos_mesaj.setText("Henüz arıza kaydı yok.")
        hap_sutununu_sigdir(self.tablo, 3)                       # Aciliyet rozeti
        hap_sutununu_sigdir(self.tablo, 4)                       # Durum rozeti ("Çözüldü" / "Açık"): kesilmesin
        hap_sutununu_sigdir(self.tablo, 6, en_az=60)             # işlem düğmeleri sağdan kırpılmasın
        self.bos_mesaj.setVisible(not arizalar)
        self.tablo.setVisible(bool(arizalar))
        self.filtrele(self.arama.text())

    def daha_fazla_yukle(self):
        """Listeyi, en yeni kayıtlardan başlayarak ADIM kadar daha uzatır (en çok sunucunun üst sınırına kadar)."""
        self.liste_siniri.artir()
        self.verileri_yukle()

    def filtrele(self, metin):
        """Cihaz adı ve sorun başlığında arama yapar."""
        aranan = metin.strip().lower()
        for satir in range(self.tablo.rowCount()):
            icerik = " ".join(
                (self.tablo.item(satir, k).text() if self.tablo.item(satir, k) else "")
                for k in (1, 2)).lower()
            self.tablo.setRowHidden(satir, aranan not in icerik)

    def excele_aktar(self):
        """Ekranda görünen arızaları Excel'e aktarır; çözüm tarihi ve çözüm notu da eklenir."""
        def kayit(satir, alan):
            oge = self.tablo.item(satir, 0)
            ar = self.ariza_detaylari.get(int(oge.text())) if oge is not None and oge.text().isdigit() else None
            return (ar or {}).get(alan) or ""
        tablodan_excele_aktar(
            self, self.tablo, "Cihaz Arıza Kayıtları", "cihaz_arizalari",
            [("No", 0, "metin"), ("Envanter Kodu", 1, "cihaz_kodu"), ("Cihaz Adı", 1, "cihaz_adi"), ("Sorun Başlığı", 2, "metin"),
             ("Aciliyet", 3, "metin"), ("Durum", 4, "metin"), ("Bildirim Tarihi", 5, "metin")],
            "ARIZA", self.api_url, self.token,
            filtre_ozeti=[("Arama", self.arama.text().strip() or "Yok")], sayfa_adi="Arızalar",
            aciklama="Cihaz arıza kayıtları (ekranda görünen kayıtlar).",
            ek_sutunlar=[("Açıklama", lambda s: kayit(s, "ariza_aciklama")),
                         ("Çözüm Tarihi", lambda s: tarih_saat_goster(kayit(s, "cozum_tarihi"))),
                         ("Çözüm Notu", lambda s: kayit(s, "cozum_notu"))],
        )

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
        self.txt_baslik.setMaxLength(150)

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

        # Çözüm notu yalnızca "Çözüldü" seçilince görünür ve zorunludur: ne yapıldığı sonradan da bilinsin.
        self.txt_cozum_notu = QTextEdit(self.ariza_verisi.get("cozum_notu") or "")
        self.txt_cozum_notu.setPlaceholderText("Ne yapılarak çözüldü? (örn. kablo değiştirildi, yazılım güncellendi)")
        self.txt_cozum_notu.setMaximumHeight(80)
        self.etiket_cozum_notu = QLabel("Çözüm Notu (*):")
        form_layout.addRow(self.etiket_cozum_notu, self.txt_cozum_notu)
        self.cmb_durum.currentIndexChanged.connect(self._cozum_notu_gorunurlugu)
        self._cozum_notu_gorunurlugu()
        layout.addLayout(form_layout)

        # Çözülmüş bir arıza yeniden açılırken sonucu önceden söyler.
        self.lbl_yeniden_ac = QLabel("Arıza yeniden açılırsa çözüm notu ve çözüm tarihi silinir; cihaz tekrar 'Arızalı' olur "
                                     "(bakımda ya da kalibrasyondaysa cihazın durumu değişmez).")
        self.lbl_yeniden_ac.setStyleSheet(UYARI_KUTUSU_STILI)
        self.lbl_yeniden_ac.setWordWrap(True)
        layout.addWidget(self.lbl_yeniden_ac)
        self.zaten_cozulmustu = self.ariza_verisi.get("durum") == "Çözüldü"
        self.cmb_durum.currentIndexChanged.connect(self._yeniden_ac_notu)
        self._yeniden_ac_notu()

        self.btn_kaydet = QPushButton("Güncelle")
        self.btn_kaydet.setObjectName("kaydet")
        self.btn_kaydet.setCursor(Qt.PointingHandCursor)
        self.btn_kaydet.clicked.connect(self.kaydet)
        layout.addWidget(self.btn_kaydet)

    def _yeniden_ac_notu(self, *_):
        self.lbl_yeniden_ac.setVisible(self.zaten_cozulmustu and "Çözüldü" not in self.cmb_durum.currentText())

    def _cozum_notu_gorunurlugu(self, *_):
        gorunur = "Çözüldü" in self.cmb_durum.currentText()
        self.etiket_cozum_notu.setVisible(gorunur)
        self.txt_cozum_notu.setVisible(gorunur)

    def kaydet(self):
        baslik = self.txt_baslik.text().strip()
        aciklama = self.txt_aciklama.toPlainText().strip()

        if not baslik or not aciklama:
            QMessageBox.warning(self, "Hata", "Başlık ve açıklama boş bırakılamaz.")
            return

        cozuldu = "Çözüldü" in self.cmb_durum.currentText()
        cozum_notu = self.txt_cozum_notu.toPlainText().strip()
        if cozuldu and len(cozum_notu) < 3:
            QMessageBox.warning(self, "Çözüm Notu", "Arızayı çözüldü olarak işaretlerken ne yapıldığını kısaca yazın.")
            self.txt_cozum_notu.setFocus()
            return

        veri = {
            "ariza_baslik": baslik,
            "ariza_aciklama": aciklama,
            "aciliyet": self.cmb_aciliyet.currentText(),
            "cozuldu_mu": cozuldu,
            "cozum_notu": cozum_notu if cozuldu else None,
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
                basari_bildirimi(self, "Arıza kaydı başarıyla güncellendi.")
                self.accept()
            else:
                QMessageBox.warning(self, "Hata", f"İşlem reddedildi. Kod: {cevap.status_code}")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Sunucuya bağlanılamadı: {istek_hatasi_metni(e)}")
