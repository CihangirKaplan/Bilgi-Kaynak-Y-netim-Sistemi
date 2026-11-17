"""Cihaz Rezervasyonu sayfası: rezervasyon listesi, yeni rezervasyon formu ve iptal onayı.

Görünüm diğer cihaz sayfalarıyla (Arıza, Bakım, Kalibrasyon) aynı ortak bileşenleri kullanır (client/tablo_tasarimi.py).
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QHeaderView, QMessageBox, QDialog,
    QFormLayout, QComboBox, QDateEdit, QLineEdit, QTextEdit, QFrame
)
from PySide6.QtCore import Qt, QDate, QDateTime
from client.rezervasyon_cakisma_uyarisi import cakisma_cozumlu_istek
from client.api_yoneticisi import (
    oturum_kontrollu_istek,
    oturum_hatasi_mi,
    api_hata_mesaji,
)
from client.tablo_tasarimi import (
    FORM_STIL, bos_mesaj_olustur, hap, metin_item, sayfa_basligi, sayi_cipi, tablo_olustur,
    tek_islem_butonu, yenile_butonu_olustur,
)

REZERVASYON_CAKISMA_METINLERI = (
    "Bu saat dolu",
    "Cihaz seçtiğiniz saat aralığında başka bir iş için ayrılmış. İsterseniz çakışan "
    "rezervasyonu iptal edip devam edebilirsiniz.",
    "Rezervasyonu yeniden dene",
)


def varsayilan_rezervasyon_zamanlari(simdi=None):
    simdi = simdi if simdi is not None else QDateTime.currentDateTime()

    dakika = simdi.time().hour() * 60 + simdi.time().minute()
    sonraki = max(8 * 60, (dakika // 30 + 1) * 30)

    # Son uygun baslangic 17:30; bitis 18:30 olabilir.
    if sonraki > 17 * 60 + 30:
        return simdi.date().addDays(1), "08:00", "09:00"

    baslangic = f"{sonraki // 60:02d}:{sonraki % 60:02d}"
    bitis_dakika = sonraki + 60
    bitis = f"{bitis_dakika // 60:02d}:{bitis_dakika % 60:02d}"

    return simdi.date(), baslangic, bitis


class YeniRezervasyonFormu(QDialog):
    """Yeni Cihaz Rezervasyonu formu (diğer cihaz formlarıyla aynı görünüm)."""
    def __init__(self, api_url, token, parent=None, cihaz_id=None, tarih=None,
                 baslangic_saati=None, bitis_saati=None):
        super().__init__(parent)
        self.api_url = api_url
        self.token = token

        self.setWindowTitle("Yeni Cihaz Rezervasyonu")
        self.setMinimumSize(560, 620)
        self.setObjectName("RezervasyonKutusu")
        self.setStyleSheet(FORM_STIL + KISAYOL_STIL)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(14)

        baslik = QLabel("📌  Yeni Cihaz Rezervasyonu")
        baslik.setStyleSheet("font-size: 18px; font-weight: 800; color: #0A1F5C;")
        alt = QLabel("Cihazı, odayı ve saat aralığını seçin. Mesai saatleri 08:00 – 18:00'dir.")
        alt.setStyleSheet("font-size: 12px; font-weight: 500; color: #6B7FA8;")
        alt.setWordWrap(True)
        layout.addWidget(baslik)
        layout.addWidget(alt)

        # Bölüm / proje türü / oda listeleri alınamazsa nedeni burada görünür (örn. migrasyon çalıştırılmamış).
        self._liste_hatalari = {}
        self.lbl_uyari = QLabel()
        self.lbl_uyari.setWordWrap(True)
        self.lbl_uyari.setStyleSheet("background: #FEE2E2; color: #991B1B; border-radius: 10px; font-size: 12px; "
                                     "font-weight: 700; padding: 10px 14px;")
        self.lbl_uyari.hide()
        layout.addWidget(self.lbl_uyari)

        form_layout = QFormLayout()
        form_layout.setSpacing(14)
        form_layout.setLabelAlignment(Qt.AlignLeft)

        # Not: Buradaki değişkenler, yapıcıya dışarıdan verilen baslangic_saati/bitis_saati parametrelerinin
        # üzerine yazmasın diye "varsayilan_" önekiyle adlandırılır.
        varsayilan_tarih, varsayilan_baslangic, varsayilan_bitis = (
            varsayilan_rezervasyon_zamanlari()
        )

        self.cmb_cihaz = QComboBox()
        self.cmb_oda = QComboBox()

        saatler = [f"{h:02d}:{m:02d}" for h in range(8, 19) for m in (0, 30)]

        layout_baslangic = QHBoxLayout()
        self.dt_baslangic_tarih = QDateEdit(varsayilan_tarih)
        self.dt_baslangic_tarih.setMinimumDate(QDate.currentDate())
        self.dt_baslangic_tarih.setCalendarPopup(True)
        self.cmb_baslangic_saat = QComboBox()
        self.cmb_baslangic_saat.addItems(saatler)
        self.cmb_baslangic_saat.setCurrentText(varsayilan_baslangic)
        layout_baslangic.addWidget(self.dt_baslangic_tarih, stretch=2)
        layout_baslangic.addWidget(self.cmb_baslangic_saat, stretch=1)

        layout_bitis = QHBoxLayout()
        self.dt_bitis_tarih = QDateEdit(varsayilan_tarih)
        self.dt_bitis_tarih.setMinimumDate(QDate.currentDate())
        self.dt_bitis_tarih.setCalendarPopup(True)
        self.cmb_bitis_saat = QComboBox()
        self.cmb_bitis_saat.addItems(saatler)
        self.cmb_bitis_saat.setCurrentText(varsayilan_bitis)
        layout_bitis.addWidget(self.dt_bitis_tarih, stretch=2)
        layout_bitis.addWidget(self.cmb_bitis_saat, stretch=1)

        # Bölüm ve proje türü veritabanındaki listelerden seçilir; listede yoksa yandaki düğmeyle eklenir.
        self.cmb_bolum = QComboBox()
        self.cmb_bolum.addItem("Bölüm seçin", None)
        self.btn_yeni_bolum = self._kisayol_dugmesi("＋ Yeni bölüm", "Listede olmayan bir bölümü ekleyin", self.yeni_bolum_ekle)
        self.cmb_proje_turu = QComboBox()
        self.cmb_proje_turu.addItem("Seçilmedi", None)
        self.btn_yeni_proje_turu = self._kisayol_dugmesi("＋ Yeni tür", "Listede olmayan bir proje türünü ekleyin", self.yeni_proje_turu_ekle)

        self.txt_proje_aciklama = QTextEdit()
        self.txt_proje_aciklama.setMaximumHeight(90)
        self.txt_proje_aciklama.setPlaceholderText("Rezervasyon amacını kısaca belirtin...")

        form_layout.addRow("Cihaz *", self.cmb_cihaz)
        form_layout.addRow("Bölüm *", self._yan_yana(self.cmb_bolum, self.btn_yeni_bolum))
        form_layout.addRow("Kullanılacak oda *", self.cmb_oda)
        form_layout.addRow("Başlangıç *", layout_baslangic)
        form_layout.addRow("Bitiş *", layout_bitis)
        form_layout.addRow("Proje türü", self._yan_yana(self.cmb_proje_turu, self.btn_yeni_proje_turu))
        form_layout.addRow("Açıklama", self.txt_proje_aciklama)
        layout.addLayout(form_layout)
        layout.addStretch()

        self.btn_kaydet = QPushButton("Rezervasyonu Onayla")
        self.btn_kaydet.setObjectName("kaydet")
        self.btn_kaydet.setCursor(Qt.PointingHandCursor)
        self.btn_kaydet.clicked.connect(self.kaydet)
        layout.addWidget(self.btn_kaydet)

        self.verileri_yukle()
        self.on_degerleri_uygula(cihaz_id, tarih, baslangic_saati, bitis_saati)

    @staticmethod
    def _kisayol_dugmesi(yazi, ipucu, tikla):
        d = QPushButton(yazi)
        d.setObjectName("kisayol")
        d.setToolTip(ipucu)
        d.setCursor(Qt.PointingHandCursor)
        d.clicked.connect(tikla)
        return d

    @staticmethod
    def _yan_yana(kutu, dugme):
        kap = QWidget()
        lay = QHBoxLayout(kap)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        lay.addWidget(kutu, 1)
        lay.addWidget(dugme)
        return kap

    def on_degerleri_uygula(self, cihaz_id=None, tarih=None, baslangic_saati=None, bitis_saati=None):
        """Cihaz Uygunluğu takviminden gelindiğinde cihaz, gün ve saati önceden seçer (verilmeyenler değişmez)."""
        if cihaz_id is not None:
            indeks = self.cmb_cihaz.findData(cihaz_id)
            if indeks >= 0:
                self.cmb_cihaz.setCurrentIndex(indeks)
        if tarih is not None:
            if not isinstance(tarih, QDate):
                tarih = QDate(tarih.year, tarih.month, tarih.day)
            self.dt_baslangic_tarih.setDate(tarih)
            self.dt_bitis_tarih.setDate(tarih)
        for kutu, saat in ((self.cmb_baslangic_saat, baslangic_saati), (self.cmb_bitis_saat, bitis_saati)):
            if saat and kutu.findText(saat) >= 0:
                kutu.setCurrentText(saat)

    def verileri_yukle(self):
        try:
            headers = {"Authorization": f"Bearer {self.token}"}
            
            # CİHAZLARI ÇEK
            res_cihaz = oturum_kontrollu_istek("GET", f"{self.api_url}/api/cihazlar", headers=headers)
            if oturum_hatasi_mi(res_cihaz):
                return
            if res_cihaz.status_code == 200:
                cihazlar = res_cihaz.json()
                
                # Filtreyi esnettik: Küçük/Büyük harf ve boşluk hatalarına karşı korumalı
                uygun_cihazlar = [c for c in cihazlar if str(c.get("durum", "")).strip().lower() in ["kullanima_hazir", "kullanıma hazır", "kullanılabilir"]]
                
                if uygun_cihazlar:
                    for c in uygun_cihazlar:
                        self.cmb_cihaz.addItem(f"{c['envanter_kodu']} - {c['cihaz_adi']}", c['cihaz_id'])
                else:
                    # Neden boş olduğunu kullanıcıya dürüstçe söylüyoruz
                    self.cmb_cihaz.addItem("Müsait Cihaz Yok (Hepsi dolu/arızalı)", None)
            else:
                self.cmb_cihaz.addItem("Sunucudan cihazlar alınamadı", None)

            # ODALARI ÇEK: psikologlara atanmamış aktif odalar (psikologlara atanan görüşme odaları gelmez)
            res_oda = oturum_kontrollu_istek("GET", f"{self.api_url}/api/cihaz-odalari", headers=headers)
            if oturum_hatasi_mi(res_oda):
                return
            if res_oda.status_code == 200:
                odalar = res_oda.json()
                uygun_odalar = [o for o in odalar if o.get("aktif_mi")]
                if uygun_odalar:
                    for o in uygun_odalar:
                        self.cmb_oda.addItem(o["oda_adi"], o["oda_id"])
                else:
                    self.cmb_oda.addItem("Uygun oda yok", None)
                    self.cmb_oda.setToolTip("Psikologlara atanmamış aktif oda bulunamadı. Oda Yönetimi'ni kontrol edin.")
                self._liste_uyarisi("Odalar", None)
            else:
                self.cmb_oda.addItem("Odalar alınamadı", None)
                self._liste_uyarisi("Odalar", api_hata_mesaji(res_oda))

            self.bolumleri_yukle()
            self.proje_turlerini_yukle()

        except Exception as e:
            QMessageBox.warning(self, "Bağlantı Hatası", "Sunucuya bağlanırken bir sorun oluştu.")

    def _liste_uyarisi(self, ad, metin):
        """Formun üstündeki uyarıyı günceller: metin verilirse "<ad> alınamadı: ..." satırı eklenir, None ise o satır kalkar."""
        if metin:
            self._liste_hatalari[ad] = metin
        else:
            self._liste_hatalari.pop(ad, None)
        self.lbl_uyari.setText("\n".join(f"⚠ {k} alınamadı: {m}" for k, m in self._liste_hatalari.items()))
        self.lbl_uyari.setVisible(bool(self._liste_hatalari))

    def _liste_getir(self, yol, ad):
        """Sunucudan liste getirir. Alınamazsa (sunucu/şema/bağlantı hatası) boş liste döner, form yine açılır ve neden uyarıda yazar."""
        try:
            cevap = oturum_kontrollu_istek("GET", f"{self.api_url}{yol}", headers={"Authorization": f"Bearer {self.token}"})
            if oturum_hatasi_mi(cevap):
                return []                                                              # oturum süresi doldu: giriş ekranı ele alır
            if cevap.status_code != 200:
                self._liste_uyarisi(ad, api_hata_mesaji(cevap))
                return []
            veri = cevap.json()
        except Exception as e:
            self._liste_uyarisi(ad, api_hata_mesaji(hata=e))
            return []
        self._liste_uyarisi(ad, None)
        return [k for k in veri if isinstance(k, dict)] if isinstance(veri, list) else []

    def _kutuyu_doldur(self, kutu, kayitlar, kimlik_alani, ad_alani, secilecek_ad=None, secilecek_kimlik=None):
        """Kutunun ilk (yer tutucu) öğesi dışındakileri yeniler; önceki seçimi (ya da verilen yeni kaydı) korur."""
        onceki_kimlik, onceki_ad = kutu.currentData(), kutu.currentText()
        while kutu.count() > 1:
            kutu.removeItem(1)
        for k in kayitlar:
            if k.get(ad_alani):
                kutu.addItem(str(k[ad_alani]), k.get(kimlik_alani))
        hedef = None
        if secilecek_ad is not None:
            hedef = next((i for i in range(1, kutu.count()) if kutu.itemText(i).strip().lower() == secilecek_ad.strip().lower()), None)
        elif secilecek_kimlik is not None:
            hedef = next((i for i in range(1, kutu.count()) if kutu.itemData(i) == secilecek_kimlik), None)
        elif onceki_kimlik is not None or kutu.findText(onceki_ad) > 0:
            hedef = kutu.findData(onceki_kimlik) if onceki_kimlik is not None else kutu.findText(onceki_ad)
        if hedef is not None and hedef > 0:
            kutu.setCurrentIndex(hedef)

    def bolumleri_yukle(self, secilecek_kimlik=None):
        self._kutuyu_doldur(self.cmb_bolum, self._liste_getir("/api/bolumler", "Bölümler"), "bolum_id", "bolum_adi",
                            secilecek_kimlik=secilecek_kimlik)

    def proje_turlerini_yukle(self, secilecek_ad=None):
        self._kutuyu_doldur(self.cmb_proje_turu, self._liste_getir("/api/proje-turleri", "Proje türleri"), "proje_turu_id", "ad",
                            secilecek_ad=secilecek_ad)

    def _yeni_kayit_gonder(self, yol, veri, baslik):
        """Yeni bölüm / proje türü kaydını sunucuya gönderir. Başarılıysa yanıt sözlüğünü, değilse None döner."""
        try:
            cevap = oturum_kontrollu_istek("POST", f"{self.api_url}{yol}", json=veri, headers={"Authorization": f"Bearer {self.token}"})
            if oturum_hatasi_mi(cevap):
                return None
            if cevap.status_code == 201:
                return cevap.json()
            QMessageBox.warning(self, baslik, self._hata_metni(cevap))
        except Exception as e:
            QMessageBox.warning(self, baslik, api_hata_mesaji(hata=e))
        return None

    @staticmethod
    def _hata_metni(cevap):
        """Çakışma (409) ve doğrulama (422) yanıtlarında sunucunun açıklamasını ("Bu proje türü zaten mevcut.") gösterir."""
        if cevap.status_code in (409, 422):
            try:
                detay = cevap.json().get("detail")
            except Exception:
                detay = None
            if isinstance(detay, str) and detay.strip():
                return detay
        return api_hata_mesaji(cevap)

    def yeni_bolum_ekle(self):
        pencere = YeniBolumPenceresi(self)
        if not pencere.exec():
            return
        sonuc = self._yeni_kayit_gonder("/api/bolumler", pencere.veri(), "Yeni Bölüm")
        if sonuc:
            self.bolumleri_yukle(secilecek_kimlik=sonuc.get("bolum_id"))                       # listeye düşer ve seçili gelir

    def yeni_proje_turu_ekle(self):
        pencere = YeniProjeTuruPenceresi(self)
        if not pencere.exec():
            return
        ad = pencere.veri()["ad"]
        sonuc = self._yeni_kayit_gonder("/api/proje-turleri", {"ad": ad}, "Yeni Proje Türü")
        if sonuc:
            self.proje_turlerini_yukle(secilecek_ad=sonuc.get("ad") or ad)

    def kaydet(self):
        cihaz_id = self.cmb_cihaz.currentData()
        oda_id = self.cmb_oda.currentData()

        bolum_id = self.cmb_bolum.currentData()

        if not cihaz_id or not oda_id:
            QMessageBox.warning(self, "Uyarı", "Geçerli bir cihaz veya oda seçilemedi. Envanteri kontrol edin.")
            return

        if not bolum_id:
            QMessageBox.warning(self, "Uyarı", "Rezervasyonu yapan bölümü seçin. Listede yoksa \"＋ Yeni bölüm\" ile ekleyebilirsiniz.")
            return

        # Kullanıcının şık UI'dan seçtiği tarih ve saatleri birleştirip Backend'in anladığı formata (ISO 8601) çeviriyoruz
        bas_tarih = self.dt_baslangic_tarih.date().toString("yyyy-MM-dd")
        bas_saat = self.cmb_baslangic_saat.currentText()
        bas_iso = f"{bas_tarih}T{bas_saat}:00"

        bit_tarih = self.dt_bitis_tarih.date().toString("yyyy-MM-dd")
        bit_saat = self.cmb_bitis_saat.currentText()
        bit_iso = f"{bit_tarih}T{bit_saat}:00"

        bas_dt = QDateTime.fromString(
            f"{bas_tarih} {bas_saat}", "yyyy-MM-dd HH:mm"
        )
        bit_dt = QDateTime.fromString(
            f"{bit_tarih} {bit_saat}", "yyyy-MM-dd HH:mm"
        )

        if bas_dt <= QDateTime.currentDateTime():
            QMessageBox.warning(
                self, "Geçersiz Tarih",
                "Rezervasyon başlangıç zamanı geçmişte olamaz."
            )
            return

        if bit_dt <= bas_dt:
            QMessageBox.warning(
                self, "Geçersiz Tarih",
                "Bitiş zamanı başlangıçtan sonra olmalıdır."
            )
            return

        veri = {
            "cihaz_id": cihaz_id,
            "bolum_id": bolum_id,
            "kullanilacak_oda_id": oda_id,
            "baslangic_zamani": bas_iso,
            "bitis_zamani": bit_iso,
            "proje_turu": self.cmb_proje_turu.currentText() if self.cmb_proje_turu.currentIndex() > 0 else "",
            "proje_adi_aciklamasi": self.txt_proje_aciklama.toPlainText().strip()
        }

        try:
            res = cakisma_cozumlu_istek(self, "POST", f"{self.api_url}/api/rezervasyonlar", veri, {"Authorization": f"Bearer {self.token}"}, *REZERVASYON_CAKISMA_METINLERI)
            if res is None or oturum_hatasi_mi(res):
                return
            if res.status_code == 201:
                basari = QMessageBox(self)
                basari.setWindowTitle("Başarılı")
                basari.setText("✅ Rezervasyon başarıyla oluşturuldu!")
                basari.setStyleSheet("QMessageBox { background-color: #FFFFFF; } QLabel { color: #27AE60; font-size: 13px; font-weight: bold; } QPushButton { background-color: #27AE60; color: white; padding: 6px 15px; border-radius: 4px; font-weight: bold; }")
                basari.setStandardButtons(QMessageBox.Ok)
                basari.exec()
                self.accept()
            else:
                hata_detay = res.json().get("detail", "Bilinmeyen bir hata oluştu.")
                QMessageBox.warning(self, "İşlem Başarısız", hata_detay)
        except Exception as e:
            QMessageBox.critical(self, "Bağlantı Hatası", f"Sunucuya ulaşılamadı: {str(e)}")


KISAYOL_STIL = """
    QPushButton#kisayol { background: #EEF4FF; color: #1D4ED8; border: 1px solid #C7D9FB; border-radius: 10px;
                          padding: 9px 12px; font-size: 12px; font-weight: 700; }
    QPushButton#kisayol:hover { background: #DBEAFE; }
"""


class _KucukFormPenceresi(QDialog):
    """Yeni bölüm / proje türü pencerelerinin ortak iskeleti: başlık, alanlar ve Kaydet/Vazgeç düğmeleri."""
    BASLIK = ""
    ALT_BASLIK = ""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.BASLIK)
        self.setMinimumWidth(420)
        self.setStyleSheet(FORM_STIL + """
            QPushButton#vazgec { background: white; color: #1D4ED8; border: 1px solid #C7D9FB; border-radius: 10px;
                                 padding: 11px 18px; font-size: 13px; font-weight: 700; }
            QPushButton#vazgec:hover { background: #EEF4FF; }
        """)
        self.duzen = QVBoxLayout(self)
        self.duzen.setContentsMargins(24, 22, 24, 20)
        self.duzen.setSpacing(12)
        baslik = QLabel(self.BASLIK)
        baslik.setStyleSheet("font-size: 17px; font-weight: 800; color: #0A1F5C;")
        alt = QLabel(self.ALT_BASLIK)
        alt.setStyleSheet("font-size: 12px; font-weight: 500; color: #6B7FA8;")
        alt.setWordWrap(True)
        self.duzen.addWidget(baslik)
        self.duzen.addWidget(alt)
        self.form = QFormLayout()
        self.form.setSpacing(12)
        self.duzen.addLayout(self.form)

    def dugmeleri_ekle(self):
        butonlar = QHBoxLayout()
        butonlar.setSpacing(10)
        self.btn_vazgec = QPushButton("Vazgeç")
        self.btn_vazgec.setObjectName("vazgec")
        self.btn_vazgec.setCursor(Qt.PointingHandCursor)
        self.btn_vazgec.clicked.connect(self.reject)
        self.btn_kaydet = QPushButton("Ekle")
        self.btn_kaydet.setObjectName("kaydet")
        self.btn_kaydet.setCursor(Qt.PointingHandCursor)
        self.btn_kaydet.clicked.connect(self.onayla)
        butonlar.addStretch()
        butonlar.addWidget(self.btn_vazgec)
        butonlar.addWidget(self.btn_kaydet, 1)
        self.duzen.addLayout(butonlar)

    def onayla(self):
        eksik = self.eksik_alan()
        if eksik:
            QMessageBox.warning(self, "Eksik bilgi", eksik)
            return
        self.accept()


class YeniBolumPenceresi(_KucukFormPenceresi):
    BASLIK = "Yeni Bölüm"
    ALT_BASLIK = "Bölüm kaydı rezervasyonu yapan birimi göstermek için kullanılır."

    def __init__(self, parent=None):
        super().__init__(parent)
        self.txt_ad = QLineEdit()
        self.txt_ad.setPlaceholderText("Örn: Psikoloji Bölümü")
        self.txt_ad.setMaxLength(150)
        self.txt_sorumlu = QLineEdit()
        self.txt_sorumlu.setPlaceholderText("Bölüm sorumlusunun adı soyadı")
        self.txt_sorumlu.setMaxLength(100)
        self.txt_iletisim = QLineEdit()
        self.txt_iletisim.setPlaceholderText("Telefon veya iç hat (isteğe bağlı)")
        self.txt_iletisim.setMaxLength(100)
        self.form.addRow("Bölüm adı *", self.txt_ad)
        self.form.addRow("Sorumlu kişi *", self.txt_sorumlu)
        self.form.addRow("İletişim", self.txt_iletisim)
        self.dugmeleri_ekle()

    def eksik_alan(self):
        if not self.txt_ad.text().strip():
            return "Bölüm adı boş olamaz."
        if not self.txt_sorumlu.text().strip():
            return "Sorumlu kişinin adı soyadı boş olamaz."
        return None

    def veri(self):
        return {"bolum_adi": self.txt_ad.text().strip(), "sorumlu_ad_soyad": self.txt_sorumlu.text().strip(),
                "iletisim_bilgisi": self.txt_iletisim.text().strip() or None}


class YeniProjeTuruPenceresi(_KucukFormPenceresi):
    BASLIK = "Yeni Proje Türü"
    ALT_BASLIK = "Eklenen tür kaydedilir ve herkesin listesinde görünür."

    def __init__(self, parent=None):
        super().__init__(parent)
        self.txt_ad = QLineEdit()
        self.txt_ad.setPlaceholderText("Örn: Staj, Yüksek lisans tezi...")
        self.txt_ad.setMaxLength(50)
        self.form.addRow("Proje türü *", self.txt_ad)
        self.dugmeleri_ekle()

    def eksik_alan(self):
        return None if self.txt_ad.text().strip() else "Proje türü boş olamaz."

    def veri(self):
        return {"ad": self.txt_ad.text().strip()}


class IptalOnayKutusu(QDialog):
    """Rezervasyon iptali için onay penceresi (btn_evet / btn_vazgec adları korunur)."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("İptal Onayı")
        self.setFixedSize(440, 190)
        self.setStyleSheet(FORM_STIL + """
            QPushButton#vazgec { background: white; color: #1D4ED8; border: 1px solid #C7D9FB; border-radius: 10px;
                                 padding: 10px 18px; font-size: 13px; font-weight: 700; }
            QPushButton#vazgec:hover { background: #EEF4FF; }
            QPushButton#tehlike { background: #DC2626; color: white; border: none; border-radius: 10px;
                                  padding: 10px 18px; font-size: 13px; font-weight: 800; }
            QPushButton#tehlike:hover { background: #B91C1C; }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(8)

        lbl_mesaj = QLabel("Bu cihaz rezervasyonu iptal edilsin mi?")
        lbl_mesaj.setStyleSheet("font-size: 16px; font-weight: 800; color: #0A1F5C;")
        lbl_alt = QLabel("Bu işlem geri alınamaz ve denetim kayıtlarına işlenir.")
        lbl_alt.setStyleSheet("font-size: 12px; font-weight: 500; color: #6B7FA8;")
        layout.addWidget(lbl_mesaj)
        layout.addWidget(lbl_alt)
        layout.addStretch()

        butonlar = QHBoxLayout()
        butonlar.setSpacing(10)
        self.btn_vazgec = QPushButton("Vazgeç")
        self.btn_vazgec.setObjectName("vazgec")
        self.btn_vazgec.setCursor(Qt.PointingHandCursor)
        self.btn_vazgec.clicked.connect(self.reject)
        self.btn_evet = QPushButton("Evet, iptal et")
        self.btn_evet.setObjectName("tehlike")
        self.btn_evet.setCursor(Qt.PointingHandCursor)
        self.btn_evet.clicked.connect(self.accept)
        butonlar.addStretch()
        butonlar.addWidget(self.btn_vazgec)
        butonlar.addWidget(self.btn_evet)
        layout.addLayout(butonlar)



# Durum -> (yazı rengi, arka plan)
DURUM_RENKLERI = {
    "Aktif": ("#166534", "#DCFCE7"),
    "Tamamlandı": ("#475569", "#E2E8F0"),
    "İptal Edildi": ("#991B1B", "#FEE2E2"),
}
SUTUN_DURUM, SUTUN_ISLEM = 5, 6


def zaman_araligi(baslangic, bitis):
    """'2026-11-16T10:00:00', '2026-11-16T12:00:00' -> '16.11.2026  10:00 – 12:00' (farklı günse iki tarih)."""
    def parcala(deger):
        metin = str(deger or "").replace("T", " ")
        tarih, _, saat = metin.partition(" ")
        gun = ".".join(reversed(tarih.split("-"))) if tarih.count("-") == 2 else tarih
        return gun, saat[:5]
    g1, s1 = parcala(baslangic)
    g2, s2 = parcala(bitis)
    if not (g1 or s1 or g2 or s2):
        return "—"
    if g1 == g2:
        return f"{g1}  {s1} – {s2}"
    return f"{g1} {s1}  →  {g2} {s2}"


class RezervasyonYonetimEkrani(QWidget):
    """Ana Rezervasyon Listesi Ekranı"""
    def __init__(self, api_url, token, yetkili_mi=False):
        super().__init__()
        self.api_url = api_url
        self.token = token
        self.yetkili_mi = yetkili_mi
        self.rezervasyonlar = []
        self.arayuzu_olustur()

    def arayuzu_olustur(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        self.arama = QLineEdit()
        self.arama.setPlaceholderText("🔍  Cihaz, bölüm, oda veya proje ara...")
        self.arama.textChanged.connect(self.filtrele)

        self.cip_toplam = sayi_cipi("0 rezervasyon")
        self.cip_aktif = sayi_cipi("0 aktif", "#166534", "#DCFCE7")
        self.cip_tamam = sayi_cipi("0 tamamlandı", "#475569", "#E2E8F0")
        self.cip_iptal = sayi_cipi("0 iptal", "#991B1B", "#FEE2E2")

        layout.addWidget(sayfa_basligi(
            "Cihaz Rezervasyonu", "Cihaz rezervasyonlarını görüntüleyin ve iptal edin",
            self.arama, yenile_butonu_olustur(self.verileri_yukle),
            [self.cip_toplam, self.cip_aktif, self.cip_tamam, self.cip_iptal]))

        self.tablo = tablo_olustur(["CİHAZ", "BÖLÜM", "ODA", "PROJE", "TARİH VE SAAT", "DURUM", "İŞLEM"])
        kb = self.tablo.horizontalHeader()
        kb.setSectionResizeMode(0, QHeaderView.Stretch)
        kb.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        kb.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        kb.setSectionResizeMode(3, QHeaderView.Stretch)
        kb.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        kb.setSectionResizeMode(SUTUN_DURUM, QHeaderView.Fixed)       # etiket (hap) sütunları sabit genişlik
        kb.setSectionResizeMode(SUTUN_ISLEM, QHeaderView.Fixed)
        self.tablo.setColumnWidth(SUTUN_DURUM, 130)
        self.tablo.setColumnWidth(SUTUN_ISLEM, 90)

        self.bos_mesaj = bos_mesaj_olustur("Henüz rezervasyon yok.")

        kart = QFrame()
        kart.setObjectName("kart")
        kl = QVBoxLayout(kart)
        kl.setContentsMargins(8, 8, 8, 8)
        kl.addWidget(self.tablo)
        kl.addWidget(self.bos_mesaj)
        layout.addWidget(kart, 1)

        self.verileri_yukle()

    def verileri_yukle(self):
        try:
            cevap = oturum_kontrollu_istek("GET", f"{self.api_url}/api/rezervasyonlar", headers={"Authorization": f"Bearer {self.token}"})
            if oturum_hatasi_mi(cevap):
                return
            if cevap.status_code != 200:
                QMessageBox.warning(self, "Rezervasyon Listesi", api_hata_mesaji(cevap))
                return
            rezervasyonlar = cevap.json()
            if not isinstance(rezervasyonlar, list):
                raise ValueError("Geçersiz rezervasyon listesi")
        except Exception as e:
            QMessageBox.warning(self, "Rezervasyon Listesi", api_hata_mesaji(hata=e))
            return
        # Liste başarıyla alındıktan sonra eski satırlar yenisiyle değişir (hata olursa mevcut liste korunur).
        self.rezervasyonlar = rezervasyonlar
        self._sayaclari_guncelle()
        self.filtrele()

    def _sayaclari_guncelle(self):
        durumlar = [r.get("durum") for r in self.rezervasyonlar]
        self.cip_toplam.setText(f"{len(durumlar)} rezervasyon")
        self.cip_aktif.setText(f"{durumlar.count('Aktif')} aktif")
        self.cip_tamam.setText(f"{durumlar.count('Tamamlandı')} tamamlandı")
        self.cip_iptal.setText(f"{durumlar.count('İptal Edildi')} iptal")

    @staticmethod
    def _cihaz_metni(rez):
        kod, ad = rez.get("envanter_kodu"), rez.get("cihaz_adi")
        if kod or ad:
            return f"{kod} · {ad}" if kod and ad else str(kod or ad)
        return str(rez.get("cihaz_id", "Bilinmeyen Cihaz"))                    # eski sunucu: "KOD - Ad"

    def filtrele(self, *_):
        aranan = self.arama.text().strip().lower()
        gorunen = [r for r in self.rezervasyonlar if not aranan or aranan in " ".join(
            str(r.get(k) or "") for k in ("cihaz_id", "envanter_kodu", "cihaz_adi", "bolum_adi", "oda_adi", "proje_turu",
                                          "proje_adi_aciklamasi")).lower()]
        self.tablo.setRowCount(0)
        self.tablo.setRowCount(len(gorunen))
        for satir, rez in enumerate(gorunen):
            self.tablo.setItem(satir, 0, metin_item(self._cihaz_metni(rez), kalin=True))
            self.tablo.setItem(satir, 1, metin_item(str(rez.get("bolum_adi") or "—")))
            self.tablo.setItem(satir, 2, metin_item(str(rez.get("oda_adi") or "—")))
            proje = " – ".join(m for m in (rez.get("proje_turu"), rez.get("proje_adi_aciklamasi")) if m)
            proje_item = metin_item(proje or "—")
            proje_item.setToolTip(proje)
            self.tablo.setItem(satir, 3, proje_item)
            self.tablo.setItem(satir, 4, metin_item(zaman_araligi(rez.get("baslangic_zamani"), rez.get("bitis_zamani"))))

            durum = rez.get("durum", "Aktif")
            renk, arka = DURUM_RENKLERI.get(durum, ("#6B7280", "#F3F4F6"))
            self.tablo.setItem(satir, SUTUN_DURUM, metin_item(durum, renk="transparent"))   # metin hap'ın altında kalır; aramada/testte okunur
            self.tablo.setCellWidget(satir, SUTUN_DURUM, hap(durum, renk, arka))

            if durum == "Aktif" and self.yetkili_mi:
                r_id = rez.get("rezervasyon_id")
                self.tablo.setCellWidget(satir, SUTUN_ISLEM, tek_islem_butonu(
                    lambda r_id=r_id: self.rezervasyon_iptal_et(r_id), "✕", "Rezervasyonu iptal et",
                    "#B91C1C", "#FEE2E2", "#FECACA"))

        bos = not gorunen
        self.bos_mesaj.setText("Aramaya uyan rezervasyon yok." if self.rezervasyonlar else "Henüz rezervasyon yok.")
        self.bos_mesaj.setVisible(bos)
        self.tablo.setVisible(not bos)

    def yeni_rezervasyon_olustur(self, **on_degerler):
        form = YeniRezervasyonFormu(self.api_url, self.token, **on_degerler)
        if form.exec():
            self.verileri_yukle()  # Form başarıyla kapanırsa tabloyu yenile

    def rezervasyon_iptal_et(self, rezervasyon_id):
        onay_kutusu = IptalOnayKutusu(self)
        if not onay_kutusu.exec():
            return
        try:
            res = oturum_kontrollu_istek("PATCH", f"{self.api_url}/api/rezervasyonlar/{rezervasyon_id}/iptal", headers={"Authorization": f"Bearer {self.token}"})
            if oturum_hatasi_mi(res):
                return
            if res.status_code == 200:
                self.verileri_yukle()
                QMessageBox.information(self, "Rezervasyon", "Rezervasyon iptal edildi.")
            else:
                QMessageBox.warning(self, "Rezervasyon", api_hata_mesaji(res))
        except Exception as e:
            QMessageBox.warning(self, "Rezervasyon", api_hata_mesaji(hata=e))
