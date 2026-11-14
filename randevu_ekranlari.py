import requests
from api_yoneticisi import oturum_kontrollu_istek, oturum_hatasi_mi, api_hata_mesaji
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QFormLayout, QHBoxLayout,
                               QComboBox, QMessageBox, QDateTimeEdit, QDialog,
                               QLabel, QTableWidget, QTableWidgetItem, QHeaderView,
                               QAbstractItemView, QPushButton, QLineEdit,
                               QDateEdit)
from PySide6.QtCore import QDateTime, Signal, Qt, QDate, QTimer, QPoint
from PySide6.QtGui import QColor, QTextCharFormat, QPixmap, QPainter, QIcon
from PySide6.QtWidgets import QStyledItemDelegate, QMenu
from PySide6.QtWidgets import QCheckBox
from datetime import datetime, timedelta

from istemci_modelleri import IstemciRandevu
from siniflandirma import (GORUSME_TIPLERI, gorusme_etiketi, terapi_etiketi, terapi_kutusunu_doldur)
from iptal_nedeni_diyalog import IPTAL_NEDENLERI, IptalNedeniDialog
from ui_components import StandartButon

# ======================================================================
#  APT-002: YENİ RANDEVU OLUŞTURMA FORMU
# ======================================================================
SAAT_LISTESI = ["09:00", "10:00", "11:00", "12:00", "13:00", "14:00", "15:00"]
DOLU_ETIKETLERI = {"oda": "Oda dolu", "psikolog": "Psikolog dolu", "oda_ve_psikolog": "Dolu"}


def dolu_saatleri_hesapla(dolu_araliklar, tarih_str):
    """Sunucudan gelen dolu aralıklardan {saat: sebep} sözlüğü üretir (1 saatlik dilimler)."""
    dolu = {}
    for saat in SAAT_LISTESI:
        dilim_bas = datetime.fromisoformat(f"{tarih_str}T{saat}:00")
        dilim_bit = dilim_bas + timedelta(hours=1)
        oda = psikolog = False
        for aralik in dolu_araliklar:
            try:
                bas = datetime.fromisoformat(str(aralik["baslangic"]).split(".")[0])
                bit = datetime.fromisoformat(str(aralik["bitis"]).split(".")[0])
            except (KeyError, ValueError, TypeError):
                continue
            if bas < dilim_bit and bit > dilim_bas:
                sebep = aralik.get("sebep", "oda_ve_psikolog")
                oda = oda or sebep in ("oda", "oda_ve_psikolog")
                psikolog = psikolog or sebep in ("psikolog", "oda_ve_psikolog")
        if oda or psikolog:
            dolu[saat] = "oda_ve_psikolog" if (oda and psikolog) else ("oda" if oda else "psikolog")
    return dolu


HAFTA_SONU_MESAJI = "Hafta sonu randevu verilmez. Lütfen hafta içi bir gün seçin."


def hafta_sonu_mu(tarih):
    """QDate cumartesi ya da pazara denk geliyor mu (kurum hafta sonu kapalıdır)."""
    return tarih.dayOfWeek() >= 6


def siradaki_is_gunu(tarih):
    """Hafta sonuna denk gelen tarih için sonraki pazartesiyi, değilse aynı tarihi döndürür."""
    while hafta_sonu_mu(tarih):
        tarih = tarih.addDays(1)
    return tarih


def hafta_sonunu_soluklastir(dt_tarih):
    """Takvim açılırken cumartesi ve pazar günleri sönük gösterilir."""
    takvim = dt_tarih.calendarWidget()
    bicim = QTextCharFormat()
    bicim.setForeground(QColor("#94A3B8"))
    takvim.setWeekdayTextFormat(Qt.Saturday, bicim)
    takvim.setWeekdayTextFormat(Qt.Sunday, bicim)


class DolulukGosterimi:
    """Randevu oluşturma ve düzenleme formlarında ortak: dolu saatleri soluk ve seçilemez gösterir.

    Gösterim yalnızca kolaylıktır; son karar sunucudadır (409 + veritabanı kısıtı).
    Sunucuya ulaşılamazsa hiçbir saat kapatılmaz.
    """

    def doluluk_gosterimini_kur(self):
        # Stil tanımlı açılır liste varsayılan çiziciyle pasif/soluk rengi göstermez; standart çizici gerekir.
        self.cmb_saat.setItemDelegate(QStyledItemDelegate(self.cmb_saat))
        self._doluluk_dogrulandi = False
        self._form_hatalari = {}

        self.lbl_form_hatasi = QLabel(self)
        self.lbl_form_hatasi.setObjectName("randevuFormYuklemeHatasi")
        self.lbl_form_hatasi.setWordWrap(True)
        self.lbl_form_hatasi.setStyleSheet(
            "color: #B42318; padding: 6px; font-size: 12px;"
        )
        self.lbl_form_hatasi.hide()
        self.layout().addWidget(self.lbl_form_hatasi)
        self.lbl_doluluk_hatasi = QLabel(self)
        self.lbl_doluluk_hatasi.setObjectName("dolulukKontrolDurumu")
        self.lbl_doluluk_hatasi.setWordWrap(True)
        self.lbl_doluluk_hatasi.setStyleSheet(
            "color: #B42318; padding: 6px; font-size: 12px;"
        )
        self.layout().addWidget(self.lbl_doluluk_hatasi)
        self._doluluk_durumunu_ayarla(
            False, "Saat uygunluğu henüz doğrulanmadı."
        )
        self._doluluk_zamanlayici = QTimer(self)
        self._doluluk_zamanlayici.setSingleShot(True)
        self._doluluk_zamanlayici.timeout.connect(self.doluluk_yenile)
        self.dt_tarih.dateChanged.connect(self.doluluk_yenilemeyi_planla)
        self.cmb_odalar.currentIndexChanged.connect(self.doluluk_yenilemeyi_planla)
        self.cmb_psikologlar.currentIndexChanged.connect(self.doluluk_yenilemeyi_planla)
        hafta_sonunu_soluklastir(self.dt_tarih)
        self.doluluk_yenilemeyi_planla()

    def doluluk_yenilemeyi_planla(self, *_):
        # Art arda gelen değişiklikler (liste temizleme + doldurma) tek istekte birleşir.
        self._doluluk_durumunu_ayarla(
            False, "Saat uygunluğu kontrol ediliyor..."
        )
        self._doluluk_zamanlayici.start(0)

    def _doluluk_durumunu_ayarla(self, dogrulandi, mesaj=""):
        self._doluluk_dogrulandi = dogrulandi

        for ad in ("btn_kaydet", "btn_guncelle"):
            buton = getattr(self, ad, None)
            if buton is not None:
                buton.setEnabled(dogrulandi and not self._form_hatalari)

        self.lbl_doluluk_hatasi.setText(mesaj)
        self.lbl_doluluk_hatasi.setVisible(bool(mesaj))

    def _form_hata_durumu(self, kaynak, mesaj=None):
        if mesaj:
            self._form_hatalari[kaynak] = mesaj
        else:
            self._form_hatalari.pop(kaynak, None)

        metin = "\n".join(dict.fromkeys(self._form_hatalari.values()))
        self.lbl_form_hatasi.setText(metin)
        self.lbl_form_hatasi.setVisible(bool(metin))

        for ad in ("btn_kaydet", "btn_guncelle"):
            buton = getattr(self, ad, None)
            if buton is not None:
                buton.setEnabled(
                    self._doluluk_dogrulandi
                    and not self._form_hatalari
                )

    def _form_istegi(self, method, url, **kwargs):
        """Form listelerini getir; HTTP ve ağ hatalarını göster."""
        try:
            cevap = oturum_kontrollu_istek(
                method, url, **kwargs
            )

            if oturum_hatasi_mi(cevap):
                return None

            if cevap.status_code != 200:
                self._form_hata_durumu(
                    url,
                    api_hata_mesaji(cevap)
                    + " Gerekli bilgiler yüklenemedi."
                )
                return None

            try:
                veri = cevap.json()
                if not isinstance(veri, list):
                    raise ValueError("Liste bekleniyordu")
            except (ValueError, TypeError) as hata:
                self._form_hata_durumu(
                    url,
                    "Sunucudan beklenmeyen veri alındı. "
                    "Gerekli bilgiler yüklenemedi."
                )
                return None

            self._form_hata_durumu(url)
            return cevap

        except Exception as hata:
            self._form_hata_durumu(
                url,
                api_hata_mesaji(hata=hata)
                + " Gerekli bilgiler yüklenemedi."
            )
            return None

    def doluluk_yenile(self):
        oda_id = self.cmb_odalar.currentData()
        psikolog_id = self.cmb_psikologlar.currentData()
        tarih_str = self.dt_tarih.date().toString("yyyy-MM-dd")

        self._doluluk_durumunu_ayarla(
            False, "Saat uygunluğu kontrol ediliyor..."
        )

        if hafta_sonu_mu(self.dt_tarih.date()):
            self.saat_kutusunu_kapat()
            self._doluluk_durumunu_ayarla(False, HAFTA_SONU_MESAJI)
            return

        if oda_id is None and psikolog_id is None:
            self._doluluk_durumunu_ayarla(
                False, "Saat kontrolü için psikolog ve oda seçiniz."
            )
            return

        params = {"tarih": tarih_str}
        if oda_id is not None:
            params["oda_id"] = int(oda_id)
        if psikolog_id is not None:
            params["psikolog_id"] = int(psikolog_id)

        haric = getattr(self, "randevu_id", None)
        if haric:
            params["haric_randevu_id"] = int(haric)

        try:
            cevap = oturum_kontrollu_istek(
                "GET",
                f"{self.api_url}/api/randevular/doluluk",
                params=params,
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=5,
            )

            if oturum_hatasi_mi(cevap):
                return

            if cevap.status_code != 200:
                self._doluluk_durumunu_ayarla(
                    False,
                    api_hata_mesaji(cevap)
                    + " Saat uygunluğu doğrulanamadı; kayıt yapılamaz."
                )
                return

            veri = cevap.json()
            if (
                not isinstance(veri, dict)
                or not isinstance(veri.get("dolu_araliklar"), list)
            ):
                raise ValueError("Geçersiz doluluk yanıtı")

            dolu = dolu_saatleri_hesapla(
                veri["dolu_araliklar"], tarih_str
            )
            self.saat_kutusunu_guncelle(dolu)
            self._doluluk_durumunu_ayarla(True)

        except Exception as hata:
            self._doluluk_durumunu_ayarla(
                False,
                api_hata_mesaji(hata=hata)
                + " Saat uygunluğu doğrulanamadı; kayıt yapılamaz."
            )

    def saat_kutusunu_guncelle(self, dolu):
        model = self.cmb_saat.model()
        for i in range(self.cmb_saat.count()):
            saat = self.cmb_saat.itemData(i)
            sebep = dolu.get(saat)
            self.cmb_saat.setItemText(i, saat if sebep is None else f"{saat}  —  {DOLU_ETIKETLERI[sebep]}")
            model.item(i).setEnabled(sebep is None)
            # Dolu saat soluk (gri), boş saat normal renkte görünür.
            model.item(i).setForeground(QColor("#94A3B8" if sebep else "#0F2552"))
        if self.saat_secimi() is None:
            ilk_bos = next((i for i in range(self.cmb_saat.count()) if model.item(i).isEnabled()), -1)
            self.cmb_saat.setCurrentIndex(ilk_bos)

    def saat_kutusunu_kapat(self):
        """Seçilebilir saat bırakmaz (örn. hafta sonu)."""
        model = self.cmb_saat.model()
        for i in range(self.cmb_saat.count()):
            model.item(i).setEnabled(False)
            model.item(i).setForeground(QColor("#94A3B8"))
        self.cmb_saat.setCurrentIndex(-1)

    def saat_secimi(self):
        """Seçili saat ("HH:MM"); seçim yoksa ya da seçili saat doluysa None."""
        index = self.cmb_saat.currentIndex()
        if index < 0:
            return None
        oge = self.cmb_saat.model().item(index)
        if oge is not None and not oge.isEnabled():
            return None
        return self.cmb_saat.itemData(index)


class RandevuOlusturFormu(DolulukGosterimi, QWidget):
    veriler_degisti = Signal()
    def __init__(self, api_url, token, mevcut_psikolog_id):
        super().__init__()
        self.api_url = api_url
        self.token = token
        self.mevcut_psikolog_id = mevcut_psikolog_id
        self.tum_odalar = []

        self.setWindowTitle("Yeni Randevu Oluştur (APT-002)")
        self.resize(480, 360)
        self.init_ui()

        self.odalari_yukle()
        self.psikologlari_yukle()
        self.danisan_kodlarini_yukle()

    def init_ui(self):
        self.setStyleSheet("""
            QWidget { background-color: #F8F9FA; font-family: 'Segoe UI', Arial; }
            QLabel { font-weight: bold; color: #0F2552; font-size: 13px; }
            QLineEdit, QComboBox, QDateTimeEdit {
                padding: 9px; border-radius: 6px; border: 1px solid #CBD5E1;
                background-color: white; color: #0F2552; font-size: 13px; font-weight: bold;
            }
            QLineEdit:focus, QComboBox:focus, QDateTimeEdit:focus { border: 2px solid #2563EB; }
            QComboBox QAbstractItemView { background-color: white; color: #0F2552; selection-background-color: #2563EB; selection-color: white; }
        """)

        ana_layout = QVBoxLayout(self)
        ana_layout.setContentsMargins(15, 15, 15, 15)
        ana_layout.setSpacing(15)

        from PySide6.QtWidgets import QFrame
        baslik_frame = QFrame()
        baslik_frame.setStyleSheet("background-color: #0A1F5C; border-radius: 8px;")
        baslik_layout = QHBoxLayout(baslik_frame)
        baslik_layout.setContentsMargins(15, 10, 15, 10)
        baslik_frame.setFixedHeight(46)

        lbl_ikon = QLabel("📅")
        lbl_ikon.setStyleSheet("font-size: 18px; background: transparent;")
        lbl_baslik = QLabel("Yeni Randevu Oluştur")
        lbl_baslik.setStyleSheet("color: white; font-size: 15px; font-weight: bold; background: transparent;")

        baslik_layout.addWidget(lbl_ikon)
        baslik_layout.addWidget(lbl_baslik)
        baslik_layout.addStretch()
        ana_layout.addWidget(baslik_frame)

        form_layout = QFormLayout()
        form_layout.setSpacing(12)

        danisan_layout = QHBoxLayout()
        self.cmb_danisan_kodu = QComboBox()
        danisan_layout.addWidget(self.cmb_danisan_kodu)
        form_layout.addRow("Danışan Kodu:", danisan_layout)

        self.cmb_psikologlar = QComboBox()
        form_layout.addRow("Psikolog Seçiniz:", self.cmb_psikologlar)

        self.cmb_odalar = QComboBox()
        form_layout.addRow("Görüşme Odası:", self.cmb_odalar)

        # Görüşme tipi (yüz yüze / online; online da oda ister) ve terapi türü (danışanın yaş grubuna göre)
        self.cmb_gorusme = QComboBox()
        for kod, etiket in GORUSME_TIPLERI:
            self.cmb_gorusme.addItem(etiket, kod)
        form_layout.addRow("Görüşme Tipi:", self.cmb_gorusme)
        self.cmb_terapi = QComboBox()
        form_layout.addRow("Terapi Türü:", self.cmb_terapi)
        self._danisan_siniflari = {}
        terapi_kutusunu_doldur(self.cmb_terapi, None, bos_metin="--- Önce danışan seçiniz ---")
        self.cmb_danisan_kodu.currentIndexChanged.connect(self._terapiyi_danisana_gore_ayarla)

        self.dt_tarih = QDateEdit(siradaki_is_gunu(QDate.currentDate()))
        self.dt_tarih.setDisplayFormat("dd.MM.yyyy")
        self.dt_tarih.setCalendarPopup(True)
        form_layout.addRow("Randevu Tarihi:", self.dt_tarih)

        self.cmb_saat = QComboBox()
        for _saat in SAAT_LISTESI:
            self.cmb_saat.addItem(_saat, _saat)
        form_layout.addRow("Randevu Saati:", self.cmb_saat)

        ana_layout.addLayout(form_layout)

        buton_layout = QHBoxLayout()
        buton_layout.addStretch()

        btn_iptal = QPushButton("İptal")
        btn_iptal.setFixedWidth(90)
        btn_iptal.setStyleSheet("background-color: #E2E8F0; color: #0F2552; border-radius: 6px; padding: 8px; font-weight: bold;")
        btn_iptal.clicked.connect(self.close)

        self.btn_kaydet = QPushButton("Randevuyu Kaydet")
        self.btn_kaydet.setFixedWidth(160)
        self.btn_kaydet.setStyleSheet("background-color: #2563EB; color: white; border-radius: 6px; padding: 8px; font-weight: bold;")
        self.btn_kaydet.clicked.connect(self.randevuyu_kaydet)
        self.doluluk_gosterimini_kur()

        buton_layout.addWidget(btn_iptal)
        buton_layout.addWidget(self.btn_kaydet)
        ana_layout.addLayout(buton_layout)

    def odalari_yukle(self):
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            cevap = self._form_istegi("GET", f"{self.api_url}/api/odalar", headers=headers, timeout=5)
            if cevap is None:
                return
            if cevap.status_code == 200:
                self.tum_odalar = cevap.json()
        except Exception as e:
            QMessageBox.warning(self, "Ağ Uyarısı", f"Odalar yüklenemedi: {str(e)}")

    def psikologlari_yukle(self):
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            cevap = self._form_istegi("GET", f"{self.api_url}/api/psikologlar", headers=headers, timeout=5)
            if cevap is None:
                return
            if cevap.status_code == 200:
                for psi in cevap.json():
                    self.cmb_psikologlar.addItem(psi["ad_soyad"], psi["personel_id"])

                self.cmb_psikologlar.currentIndexChanged.connect(self.odalari_filtrele)
                self.cmb_psikologlar.currentIndexChanged.connect(self.danisan_kodlarini_yukle)

                # mevcut_psikolog_id, giriş yapan kişinin PERSONEL kimliğidir (login_ekrani: personel_id or kullanici_id).
                # Psikolog listesinde bu kimlikte biri varsa (yani kendisi psikologsa) kendi adına kilitlenir;
                # admin ve danışma öğrencisi gibi roller listede olmadığı için psikolog seçebilir.
                if self.mevcut_psikolog_id is not None:
                    kendisi = next(
                        (p for p in cevap.json() if p.get("personel_id") == self.mevcut_psikolog_id),
                        None,
                    )
                    if kendisi is not None:
                        index = self.cmb_psikologlar.findData(kendisi["personel_id"])
                        if index >= 0:
                            self.cmb_psikologlar.setCurrentIndex(index)
                            self.cmb_psikologlar.setEnabled(False)

                self.odalari_filtrele()
        except Exception as e:
            QMessageBox.warning(self, "Ağ Uyarısı", f"Psikologlar yüklenemedi: {str(e)}")

    def odalari_filtrele(self):
        self.cmb_odalar.clear()

        secilen_psikolog_id = self.cmb_psikologlar.currentData()
        if secilen_psikolog_id is None:
            return

        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            # Artık tüm odaları değil, sadece bu psikoloğa atanmış odaları çekiyoruz
            istek_url = f"{self.api_url}/api/psikologlar/{secilen_psikolog_id}/odalar"
            cevap = self._form_istegi("GET", istek_url, headers=headers, timeout=5)

            if cevap is None:
                return

            if cevap.status_code == 200:
                atanmis_odalar = cevap.json()
                for oda in atanmis_odalar:
                    if oda.get("aktif_mi", True):
                        self.cmb_odalar.addItem(oda["oda_adi"], oda["oda_id"])
                if self.cmb_odalar.count() == 0:
                    self.cmb_odalar.addItem("Bu psikoloğa atanmış oda yok", None)
                    self.cmb_odalar.model().item(0).setEnabled(False)

        except Exception as e:
            QMessageBox.warning(self, "Ağ Uyarısı", f"Psikoloğun odaları yüklenemedi: {str(e)}")

    def danisan_kodlarini_yukle(self, *_):
        """Danışan listesi seçilen psikologun oluşturduğu danışanlarla sınırlanır.

        Psikolog hesabında sunucu zaten yalnızca kendi danışanlarını döndürür. Psikolog değişince liste yenilenir;
        seçili danışan yeni listede de varsa korunur.
        """
        onceki = self.cmb_danisan_kodu.currentData()
        self.cmb_danisan_kodu.clear()
        self.cmb_danisan_kodu.addItem("--- Danışan Seçiniz ---", "")

        params = {}
        psikolog_id = self.cmb_psikologlar.currentData()
        if psikolog_id is not None:
            params["psikolog_id"] = int(psikolog_id)

        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            cevap = self._form_istegi(
                "GET", f"{self.api_url}/api/danisan-kodlari", params=params, headers=headers, timeout=5
            )
            if cevap is None:
                return
            if cevap.status_code == 200:
                for danisan in cevap.json():
                    kod = danisan.get("danisan_kod_id")
                    self.cmb_danisan_kodu.addItem(kod, kod)
                    self._danisan_siniflari[kod] = danisan.get("yas_grubu")
        except Exception as e:
            QMessageBox.warning(self, "Ağ Uyarısı", f"Danışan kodları yüklenemedi: {str(e)}")

        if onceki:
            index = self.cmb_danisan_kodu.findData(onceki)
            if index >= 0:
                self.cmb_danisan_kodu.setCurrentIndex(index)

    def _terapiyi_danisana_gore_ayarla(self, *_):
        """Terapi seçenekleri danışanın yaş grubuna göre belirlenir: yetişkinde otomatik bireysel terapi, çocukta seçilir."""
        kod = self.cmb_danisan_kodu.currentData()
        yas = self._danisan_siniflari.get(kod)
        terapi_kutusunu_doldur(
            self.cmb_terapi, yas, yas_bilinmiyor_secenekli=bool(kod),
            bos_metin="--- Önce danışan seçiniz ---", cocukta_secim_zorunlu=True,
        )

    def randevuyu_kaydet(self):
        if (
            not getattr(self, "_doluluk_dogrulandi", False)
            or bool(getattr(self, "_form_hatalari", {}))
        ):
            QMessageBox.warning(
                self,
                "Saat Uygunluğu",
                "Saat uygunluğu doğrulanamadı. "
                "Lütfen kontrolü yenileyip tekrar deneyin."
            )
            return

        secilen_danisan_kodu = self.cmb_danisan_kodu.currentData()
        secilen_oda_id = self.cmb_odalar.currentData()
        secilen_psikolog_id = self.cmb_psikologlar.currentData()

        if not secilen_danisan_kodu:
            QMessageBox.warning(self, "Eksik Veri", "Lütfen bir danışan kodu seçiniz veya yeni oluşturunuz.")
            return
        if secilen_psikolog_id is None:
            QMessageBox.warning(self, "Eksik Veri", "Lütfen bir psikolog seçiniz.")
            return
        if secilen_oda_id is None:
            QMessageBox.warning(self, "Eksik Veri", "Lütfen geçerli bir görüşme odası seçiniz.")
            return

        tarih_str = self.dt_tarih.date().toString("yyyy-MM-dd")
        saat_str = self.saat_secimi()
        if saat_str is None:
            QMessageBox.warning(self, "Saat Seçilemedi", "Seçilen tarih için boş saat yok ya da seçili saat dolu. Lütfen başka bir saat, oda veya tarih seçiniz.")
            return
        if self._danisan_siniflari.get(secilen_danisan_kodu) == "COCUK" and self.cmb_terapi.currentData() is None:
            QMessageBox.warning(self, "Eksik Veri", "Lütfen terapi türünü seçiniz.")
            return
        saat_int = int(saat_str.split(":")[0])

        baslangic_str = f"{tarih_str}T{saat_str}:00"
        bitis_str = f"{tarih_str}T{saat_int + 1:02d}:00:00"

        payload = {
            "danisan_kod_id": secilen_danisan_kodu,
            "psikolog_id": int(secilen_psikolog_id),
            "oda_id": int(secilen_oda_id),
            "baslangic_zamani": baslangic_str,
            "bitis_zamani": bitis_str,
            "gorusme_tipi": self.cmb_gorusme.currentData(),
        }
        if self.cmb_terapi.currentData() is not None:
            payload["terapi_turu"] = self.cmb_terapi.currentData()

        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            cevap = oturum_kontrollu_istek("POST", f"{self.api_url}/api/randevular", json=payload, headers=headers, timeout=5)
            if oturum_hatasi_mi(cevap):
                return

            if cevap.status_code in (200, 201):
                QMessageBox.information(self, "Başarılı", "Randevu başarıyla oluşturuldu!")
                self.veriler_degisti.emit()
                self.close()
            elif cevap.status_code == 409:
                QMessageBox.warning(self, "Çakışma", "Seçilen psikolog veya oda bu saatlerde dolu!")
            else:
                hata_detay = cevap.json().get('detail', 'Bilinmeyen hata') if cevap.headers.get("content-type") == "application/json" else cevap.text
                QMessageBox.warning(self, "Hata", f"İşlem başarısız: {hata_detay}")
        except Exception as e:
            QMessageBox.critical(self, "Bağlantı Hatası", str(e))

# ======================================================================
#  APT-003 & APT-004: MEVCUT RANDEVUYU DÜZENLEME VE İPTAL FORMU
# ======================================================================
class RandevuDuzenleFormu(DolulukGosterimi, QWidget):
    veriler_degisti = Signal()

    def __init__(self, api_url, token, mevcut_psikolog_id, randevu_id, eski_veriler):
        super().__init__()
        self.api_url = api_url
        self.token = token
        self.mevcut_psikolog_id = mevcut_psikolog_id
        self.randevu_id = randevu_id
        self.eski_veriler = eski_veriler
        self.tum_odalar = []

        self.setWindowTitle("Randevu Düzenle")
        self.resize(450, 420)

        self.init_ui()
        self.odalari_yukle()
        self.psikologlari_yukle()
        self.eski_verileri_arayuze_bas()
        self._siniflari_doldur()

    def init_ui(self):
        self.setStyleSheet("""
            QWidget { background-color: #F8F9FA; font-family: 'Segoe UI', Arial; }
            QLabel { font-weight: bold; color: #0F2552; font-size: 13px; }
            QLineEdit, QComboBox, QDateEdit, QDateTimeEdit {
                padding: 10px; border-radius: 6px; border: 1px solid #CBD5E1;
                background-color: white; color: #0F2552; font-size: 13px; font-weight: bold;
            }
            QLineEdit:focus, QComboBox:focus, QDateEdit:focus { border: 2px solid #2563EB; }
            QComboBox QAbstractItemView {
                background-color: white; color: #0F2552; selection-background-color: #2563EB; selection-color: white;
            }
            QPushButton#btnGuncelle {
                background-color: #2563EB; color: white; border-radius: 6px; padding: 10px 20px;
                font-weight: bold; font-size: 14px; border: none;
            }
            QPushButton#btnGuncelle:hover { background-color: #1D4ED8; }
        """)

        ana_layout = QVBoxLayout(self)
        ana_layout.setContentsMargins(15, 15, 15, 15)
        ana_layout.setSpacing(12)

        from PySide6.QtWidgets import QFrame
        baslik_frame = QFrame()
        baslik_frame.setStyleSheet("background-color: #0A1F5C; border-radius: 8px;")
        baslik_layout = QHBoxLayout(baslik_frame)
        baslik_layout.setContentsMargins(15, 15, 15, 15)

        lbl_ikon = QLabel("✏️")
        lbl_ikon.setStyleSheet("font-size: 18px; color: white; background: transparent;")
        lbl_baslik = QLabel("Randevu Düzenle")
        lbl_baslik.setStyleSheet("color: white; font-size: 15px; font-weight: bold; background: transparent;")

        baslik_layout.addWidget(lbl_ikon)
        baslik_layout.addWidget(lbl_baslik)
        baslik_layout.addStretch()
        ana_layout.addWidget(baslik_frame)

        form_layout = QFormLayout()
        form_layout.setSpacing(12)

        self.txt_danisan_kodu = QLineEdit()
        self.txt_danisan_kodu.setReadOnly(True)
        self.txt_danisan_kodu.setStyleSheet("background-color: #E2E8F0; color: #1E3A8A; font-weight: bold; padding: 9px; border-radius: 6px; border: none;")
        form_layout.addRow("Danışan Kodu:", self.txt_danisan_kodu)

        self.cmb_psikologlar = QComboBox()
        form_layout.addRow("Psikolog:", self.cmb_psikologlar)
        self.cmb_psikologlar.currentIndexChanged.connect(self.odalari_filtrele)

        self.cmb_odalar = QComboBox()
        form_layout.addRow("Görüşme Odası:", self.cmb_odalar)

        self.cmb_gorusme = QComboBox()
        for kod, etiket in GORUSME_TIPLERI:
            self.cmb_gorusme.addItem(etiket, kod)
        form_layout.addRow("Görüşme Tipi:", self.cmb_gorusme)
        self.cmb_terapi = QComboBox()
        form_layout.addRow("Terapi Türü:", self.cmb_terapi)

        self.dt_tarih = QDateEdit()
        self.dt_tarih.setDisplayFormat("dd.MM.yyyy")
        self.dt_tarih.setCalendarPopup(True)
        form_layout.addRow("Randevu Tarihi:", self.dt_tarih)

        self.cmb_saat = QComboBox()
        for _saat in SAAT_LISTESI:
            self.cmb_saat.addItem(_saat, _saat)
        form_layout.addRow("Randevu Saati:", self.cmb_saat)

        ana_layout.addLayout(form_layout)

        buton_layout = QHBoxLayout()
        self.btn_guncelle = QPushButton("Değişiklikleri Kaydet")
        self.btn_guncelle.setObjectName("btnGuncelle")
        self.btn_guncelle.clicked.connect(self.randevuyu_guncelle)
        self.doluluk_gosterimini_kur()

        buton_layout.addStretch()
        buton_layout.addWidget(self.btn_guncelle)
        buton_layout.addStretch()

        ana_layout.addLayout(buton_layout)

    def odalari_yukle(self):
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            cevap = self._form_istegi("GET", f"{self.api_url}/api/odalar", headers=headers, timeout=5)
            if cevap is None: return
            if cevap.status_code == 200:
                self.tum_odalar = cevap.json()
        except Exception as e:
            QMessageBox.warning(self, "Ağ Uyarısı", f"Odalar yüklenemedi: {str(e)}")

    def psikologlari_yukle(self):
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            cevap = self._form_istegi("GET", f"{self.api_url}/api/psikologlar", headers=headers, timeout=5)
            if cevap is None: return
            if cevap.status_code == 200:
                for psi in cevap.json():
                    self.cmb_psikologlar.addItem(psi["ad_soyad"], psi["personel_id"])

                index = self.cmb_psikologlar.findData(self.eski_veriler["psikolog_id"])
                if index >= 0:
                    self.cmb_psikologlar.setCurrentIndex(index)

                self.odalari_filtrele()
        except Exception as e:
            QMessageBox.warning(self, "Ağ Uyarısı", f"Psikologlar yüklenemedi: {str(e)}")

    def odalari_filtrele(self):
        self.cmb_odalar.clear()

        secilen_psikolog_id = self.cmb_psikologlar.currentData()
        if secilen_psikolog_id is None:
            return

        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            # Artık tüm odaları değil, sadece bu psikoloğa atanmış odaları çekiyoruz
            istek_url = f"{self.api_url}/api/psikologlar/{secilen_psikolog_id}/odalar"
            cevap = self._form_istegi("GET", istek_url, headers=headers, timeout=5)

            if cevap is None:
                return

            if cevap.status_code == 200:
                atanmis_odalar = cevap.json()
                for oda in atanmis_odalar:
                    if oda.get("aktif_mi", True):
                        self.cmb_odalar.addItem(oda["oda_adi"], oda["oda_id"])
                if self.cmb_odalar.count() == 0:
                    self.cmb_odalar.addItem("Bu psikoloğa atanmış oda yok", None)
                    self.cmb_odalar.model().item(0).setEnabled(False)

        except Exception as e:
            QMessageBox.warning(self, "Ağ Uyarısı", f"Psikoloğun odaları yüklenemedi: {str(e)}")

    def eski_verileri_arayuze_bas(self):
        self.txt_danisan_kodu.setText(self.eski_veriler["danisan_kod_id"])

        oda_index = self.cmb_odalar.findData(self.eski_veriler["oda_id"])
        if oda_index >= 0:
            self.cmb_odalar.setCurrentIndex(oda_index)

        baslangic = self.eski_veriler["baslangic_zamani"].split('.')[0]
        tarih_kismi, saat_kismi = baslangic.split("T")

        self.dt_tarih.setDate(QDate.fromString(tarih_kismi, "yyyy-MM-dd"))

        saat_kisa = saat_kismi[:5]
        index = self.cmb_saat.findData(saat_kisa)
        if index >= 0:
            self.cmb_saat.setCurrentIndex(index)

    def _siniflari_doldur(self):
        """Görüşme tipi ve terapi türünü mevcut randevudan doldurur (yaş grubuna uygunluğu sunucu denetler)."""
        gorusme = self.cmb_gorusme.findData(self.eski_veriler.get("gorusme_tipi") or "YUZ_YUZE")
        if gorusme >= 0:
            self.cmb_gorusme.setCurrentIndex(gorusme)
        terapi_kutusunu_doldur(
            self.cmb_terapi, None, secili=self.eski_veriler.get("terapi_turu"), yas_bilinmiyor_secenekli=True
        )

    def randevuyu_guncelle(self):
        if (
            not getattr(self, "_doluluk_dogrulandi", False)
            or bool(getattr(self, "_form_hatalari", {}))
        ):
            QMessageBox.warning(
                self,
                "Saat Uygunluğu",
                "Saat uygunluğu doğrulanamadı. "
                "Lütfen kontrolü yenileyip tekrar deneyin."
            )
            return

        secilen_oda_id = self.cmb_odalar.currentData()
        if secilen_oda_id is None:
            QMessageBox.warning(self, "Eksik Veri", "Lütfen bir görüşme odası seçiniz.")
            return

        tarih_str = self.dt_tarih.date().toString("yyyy-MM-dd")
        saat_str = self.saat_secimi()
        if saat_str is None:
            QMessageBox.warning(self, "Saat Seçilemedi", "Seçilen tarihte boş saat yok ya da seçili saat dolu. Randevu güncellenemedi; başka bir saat, oda veya tarih seçiniz.")
            return
        saat_int = int(saat_str.split(":")[0])

        guncel_veriler = {
            "danisan_kod_id": self.txt_danisan_kodu.text(),
            "psikolog_id": self.cmb_psikologlar.currentData(),
            "oda_id": secilen_oda_id,
            "baslangic_zamani": f"{tarih_str}T{saat_str}:00",
            "bitis_zamani": f"{tarih_str}T{saat_int + 1:02d}:00:00",
            "gorusme_tipi": self.cmb_gorusme.currentData(),
        }
        if self.cmb_terapi.currentData() is not None:
            guncel_veriler["terapi_turu"] = self.cmb_terapi.currentData()

        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            cevap = oturum_kontrollu_istek("PATCH", f"{self.api_url}/api/randevular/{self.randevu_id}",
                                          json=guncel_veriler, headers=headers, timeout=5)
            if oturum_hatasi_mi(cevap): return

            if cevap.status_code == 200:
                QMessageBox.information(self, "Başarılı", "Randevu başarıyla güncellendi!")
                self.veriler_degisti.emit()
                self.close()
            elif cevap.status_code == 409:
                QMessageBox.warning(self, "Çakışma", "Seçilen saatte oda veya psikolog dolu!")
            else:
                QMessageBox.warning(self, "Hata", f"Güncellenemedi: {cevap.json().get('detail')}")
        except Exception as e:
            QMessageBox.critical(self, "Hata", str(e))


# ======================================================================
#  RANDEVU ANA EKRANI (TABLO GÖRÜNÜMÜ VE DOĞRUDAN DÜZENLEME MANTIĞI)
# ======================================================================
# ======================================================================
#  RANDEVU YÖNETİMİ EKRANI (LİSTE, ARAMA, FİLTRE, DÜZENLEME VE İPTAL)
# ======================================================================
DURUM_ETIKETLERI = {
    "PLANLANDI": "Planlandı",
    "TAMAMLANDI": "Tamamlandı",
    "GELMEDI": "Gelmedi",
    "IPTAL_EDILDI": "İptal Edildi",
}
# (arka plan, yazı) - yumuşak rozet renkleri. İptal bir hata değil; kırmızı yerine nötr gri.
DURUM_RENKLERI = {
    "PLANLANDI": ("#DBEAFE", "#1D4ED8"),
    "TAMAMLANDI": ("#DCFCE7", "#15803D"),
    "GELMEDI": ("#FCE7F3", "#BE185D"),
    "IPTAL_EDILDI": ("#F1F5F9", "#64748B"),
}
DONEM_SECENEKLERI = [
    ("tumu", "Tüm tarihler"), ("bugun", "Bugün"), ("hafta", "Bu hafta"),
    ("ay", "Bu ay"), ("ozel", "Özel aralık"),
]
DURUM_SECENEKLERI = [
    (None, "Tüm durumlar"), ("PLANLANDI", "Planlandı"), ("TAMAMLANDI", "Tamamlandı"),
    ("GELMEDI", "Gelmedi"), ("IPTAL_EDILDI", "İptal Edildi"),
]
RANDEVU_TABLO_BASLIKLARI = ["Randevu ID", "Danışan Kodu", "Psikolog", "Oda", "Tarih", "Saat", "Görüşme", "Terapi", "Durum"]
DURUM_SUTUNU = RANDEVU_TABLO_BASLIKLARI.index("Durum")

_TR_KATLA = str.maketrans("çğıöşü", "cgiosu")


def ara_normalle(metin):
    """Aramada Türkçe karakter ve büyük/küçük harf farkı önemsenmez ('gorusme' -> 'Görüşme')."""
    return str(metin or "").replace("İ", "i").replace("I", "ı").lower().translate(_TR_KATLA)


def randevu_zamani(metin):
    if not metin:
        return None
    try:
        return datetime.fromisoformat(str(metin).split(".")[0])
    except ValueError:
        return None


def tarih_saat_metinleri(baslangic, bitis):
    """('15.10.2026', '11:47 – 12:47')"""
    bas, bit = randevu_zamani(baslangic), randevu_zamani(bitis)
    if bas is None:
        return "", ""
    saat = bas.strftime("%H:%M") + (" – " + bit.strftime("%H:%M") if bit else "")
    return bas.strftime("%d.%m.%Y"), saat


def donem_araligi(anahtar, bugun):
    """Hazır dönemler için (ilk gün, son gün); 'tumu' ve 'ozel' için None."""
    if anahtar == "bugun":
        return bugun, bugun
    if anahtar == "hafta":
        ilk = bugun - timedelta(days=bugun.weekday())
        return ilk, ilk + timedelta(days=6)
    if anahtar == "ay":
        ilk = bugun.replace(day=1)
        return ilk, (ilk + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    return None


def siralama_anahtari(randevu, simdi):
    """Yaklaşan planlı randevular önce (en yakını en üstte); sonra geçmiş ve diğerleri (en yenisi önce)."""
    bas = randevu_zamani(randevu.get("baslangic_zamani"))
    bit = randevu_zamani(randevu.get("bitis_zamani")) or bas
    if bas is None:
        return (2, 0.0)
    if randevu.get("durum") == "PLANLANDI" and bit >= simdi:
        return (0, bas.timestamp())
    return (1, -bas.timestamp())


def randevulari_filtrele(randevular, psikolog_adlari, oda_adlari, arama="", aralik=None,
                         durum=None, iptalleri_gizle=False):
    """Arama (ID, danışan kodu, psikolog, oda), tarih aralığı (başlangıç günü) ve durum filtresi.

    Durum açıkça seçilmişse iptal gizleme dikkate alınmaz (İptal Edildi seçilince iptaller görünür).
    """
    aranan = ara_normalle(arama).strip()
    sonuc = []
    for r in randevular:
        d = r.get("durum")
        if durum is not None:
            if d != durum:
                continue
        elif iptalleri_gizle and d == "IPTAL_EDILDI":
            continue
        if aralik is not None:
            bas = randevu_zamani(r.get("baslangic_zamani"))
            if bas is None or not (aralik[0] <= bas.date() <= aralik[1]):
                continue
        if aranan:
            metin = " ".join(str(x) for x in (
                r.get("randevu_id"), r.get("danisan_kod_id"),
                psikolog_adlari.get(r.get("psikolog_id"), ""), oda_adlari.get(r.get("oda_id"), ""),
            ))
            if aranan not in ara_normalle(metin):
                continue
        sonuc.append(r)
    return sonuc


FILTRE_STILI = """
    QLineEdit, QComboBox, QDateEdit {
        background-color: white; border: 1px solid #CBD5E1; border-radius: 8px;
        padding: 7px 10px; color: #0F172A; font-size: 13px;
    }
    QLineEdit:focus, QComboBox:focus, QDateEdit:focus { border: 1px solid #3B82F6; }
    /* Ana pencerenin genel stili her açılır kutuya min-width: 170px verir; filtre çubuğunda geçersiz kılınır. */
    QComboBox { min-width: 120px; }
    QCheckBox { color: #1E293B; font-size: 13px; font-weight: bold; }
    QPushButton#btn_yenile {
        background-color: white; border: 1px solid #CBD5E1; border-radius: 8px;
        padding: 7px 14px; color: #1E293B; font-weight: bold;
    }
    QPushButton#btn_yenile:hover { background-color: #F1F5F9; }
    QLabel#lbl_sayac { color: #64748B; font-size: 12px; font-weight: bold; }
"""


def iptal_bilgisi_metni(randevu):
    """İptal edilmiş randevu için 'İptal nedeni: ...' metni; iptal edilmemişse boş metin."""
    if not randevu or randevu.get("durum") != "IPTAL_EDILDI":
        return ""
    kod = randevu.get("iptal_nedeni")
    if not kod:
        return "İptal nedeni:  kaydedilmemiş (neden zorunlu olmadan önce iptal edilmiş)"
    metin = dict(IPTAL_NEDENLERI).get(kod, str(kod))
    notu = randevu.get("iptal_notu")
    return f"İptal nedeni:  {metin}" + (f" — {notu}" if notu else "")


def durum_isaretlenebilir(randevu, simdi):
    """Başlangıcı geçmiş ve iptal edilmemiş randevu Tamamlandı / Gelmedi olarak işaretlenebilir (ya da düzeltilebilir)."""
    if not randevu or randevu.get("durum") not in ("PLANLANDI", "TAMAMLANDI", "GELMEDI"):
        return False
    zaman = randevu_zamani(randevu.get("baslangic_zamani"))
    return zaman is not None and zaman <= simdi


def menu_konumu(rozet_sol_alt, rozet_genislik, menu_genislik, ekran_sag):
    """Liste rozetin hemen altında, sol kenarları hizalı açılır; ekranın sağına sığmıyorsa sağ kenarlar hizalanır."""
    x, y = rozet_sol_alt.x(), rozet_sol_alt.y()
    if x + menu_genislik > ekran_sag:
        x = x + rozet_genislik - menu_genislik
    return QPoint(x, y)


def _renkli_nokta(renk):
    """Liste satırlarının başında görünen küçük renkli daire."""
    resim = QPixmap(12, 12)
    resim.fill(Qt.transparent)
    cizici = QPainter(resim)
    cizici.setRenderHint(QPainter.Antialiasing)
    cizici.setBrush(QColor(renk))
    cizici.setPen(Qt.NoPen)
    cizici.drawEllipse(1, 1, 10, 10)
    cizici.end()
    return QIcon(resim)


class DurumRozeti(QLabel):
    """Durum rozeti; tiklanabilir ise sol tıkta `tiklandi` sinyalini gönderir."""
    tiklandi = Signal()

    def __init__(self, metin, tiklanabilir=False):
        super().__init__(metin)
        self.tiklanabilir = tiklanabilir

    def mousePressEvent(self, olay):
        if self.tiklanabilir and olay.button() == Qt.LeftButton:
            self.tiklandi.emit()
            olay.accept()
            return
        super().mousePressEvent(olay)


class RandevuAnaEkrani(QWidget):
    """Randevu Yönetimi: randevuları listeler; arama, tarih aralığı ve durum filtresi; düzenleme ve iptal."""

    def __init__(self, api_url, token, mevcut_psikolog_id, rol="", duzenleme_yetkisi=True):
        super().__init__()
        self.duzenleme_yetkisi = duzenleme_yetkisi      # yoksa durum rozeti tıklanmaz (sunucu da reddeder)
        self.api_url = api_url
        self.token = token
        self.mevcut_psikolog_id = mevcut_psikolog_id
        self.rol = rol
        self.randevular = []
        self.psikolog_adlari = {}
        self.oda_adlari = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addLayout(self._filtre_cubugu())

        self.lbl_randevu_hatasi = QLabel()
        self.lbl_randevu_hatasi.setObjectName("randevuYuklemeHatasi")
        self.lbl_randevu_hatasi.setWordWrap(True)
        self.lbl_randevu_hatasi.setStyleSheet(
            "color: #B42318; padding: 8px; font-size: 12px;"
        )
        self.lbl_randevu_hatasi.hide()
        layout.addWidget(self.lbl_randevu_hatasi)

        self.lbl_bos = QLabel("Filtreye uyan randevu yok.")
        self.lbl_bos.setAlignment(Qt.AlignCenter)
        self.lbl_bos.setStyleSheet("color: #64748B; font-size: 14px; font-weight: bold; padding: 40px;")
        self.lbl_bos.setVisible(False)
        layout.addWidget(self.lbl_bos)

        self.tablo = QTableWidget()
        self.tablo.setColumnCount(len(RANDEVU_TABLO_BASLIKLARI))
        self.tablo.setHorizontalHeaderLabels(RANDEVU_TABLO_BASLIKLARI)
        self.tablo.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        # Durum rozeti (▾ ile) kırpılmasın: sabit genişlik; kimlik sütunu içeriğe göre
        self.tablo.horizontalHeader().setSectionResizeMode(DURUM_SUTUNU, QHeaderView.Fixed)
        self.tablo.setColumnWidth(DURUM_SUTUNU, 150)
        self.tablo.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tablo.verticalHeader().setVisible(False)
        self.tablo.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tablo.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tablo.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tablo.setStyleSheet("""
            QTableWidget { background-color: white; border: 1px solid #D0D7E5; border-radius: 8px; gridline-color: #E2E8F0; }
            QHeaderView::section { background-color: #0A1F5C; color: white; font-weight: bold; padding: 10px; border: none; }
        """)
        self.tablo.cellDoubleClicked.connect(lambda *_: self.duzenle_secilen())
        layout.addWidget(self.tablo, 1)

        # Seçili iptal edilmiş randevunun nedeni tablonun altında ince bir satırda gösterilir
        self.lbl_iptal_bilgisi = QLabel()
        self.lbl_iptal_bilgisi.setObjectName("iptalBilgisi")
        self.lbl_iptal_bilgisi.setWordWrap(True)
        self.lbl_iptal_bilgisi.setStyleSheet(
            "background-color: #F1F5F9; color: #334155; border: 1px solid #D0D7E5; border-radius: 8px; "
            "padding: 8px 12px; font-size: 12px; font-weight: 600;"
        )
        self.lbl_iptal_bilgisi.hide()
        layout.addWidget(self.lbl_iptal_bilgisi)
        self.tablo.itemSelectionChanged.connect(self._iptal_bilgisini_guncelle)

        self.verileri_cek()

    # ------------------------------------------------------------------ arayüz
    def _filtre_cubugu(self):
        """İki satır: üstte arama, sayaç ve Yenile; altta dönem, tarih, durum ve iptal filtreleri.

        Tek satıra sığmaz: ana pencerenin genel stili her açılır kutuya min-width: 170px verir ve
        pencere genişliği sabittir; kutular birbirinin üstüne biner.
        """
        kok = QVBoxLayout()
        kok.setSpacing(8)
        ust = QHBoxLayout()
        ust.setSpacing(8)
        alt = QHBoxLayout()
        alt.setSpacing(8)

        self.arama = QLineEdit()
        self.arama.setPlaceholderText("Ara: danışan kodu, psikolog, oda...")
        self.arama.setClearButtonEnabled(True)
        self.arama.setMinimumWidth(200)
        self.arama.textChanged.connect(self.tabloyu_guncelle)

        self.cmb_donem = QComboBox()
        for anahtar, etiket in DONEM_SECENEKLERI:
            self.cmb_donem.addItem(etiket, anahtar)
        self.cmb_donem.currentIndexChanged.connect(self._donem_degisti)

        bugun = QDate.currentDate()
        self.dt_bas = QDateEdit(bugun.addDays(-30))
        self.dt_bit = QDateEdit(bugun)
        for kutu in (self.dt_bas, self.dt_bit):
            kutu.setDisplayFormat("dd.MM.yyyy")
            kutu.setCalendarPopup(True)
            kutu.setMinimumWidth(125)
            kutu.setVisible(False)
            kutu.dateChanged.connect(self.tabloyu_guncelle)
        self.lbl_tire = QLabel("–")
        self.lbl_tire.setVisible(False)

        self.cmb_durum = QComboBox()
        for anahtar, etiket in DURUM_SECENEKLERI:
            self.cmb_durum.addItem(etiket, anahtar)
        self.cmb_durum.currentIndexChanged.connect(self.tabloyu_guncelle)

        self.chk_iptal_gizle = QCheckBox("İptalleri gizle")
        self.chk_iptal_gizle.setChecked(True)
        self.chk_iptal_gizle.toggled.connect(self.tabloyu_guncelle)

        self.btn_yenile = QPushButton("⟳  Yenile")
        self.btn_yenile.setObjectName("btn_yenile")
        self.btn_yenile.setCursor(Qt.PointingHandCursor)
        self.btn_yenile.clicked.connect(self.verileri_cek)

        self.lbl_sayac = QLabel("")
        self.lbl_sayac.setObjectName("lbl_sayac")

        ust.addWidget(self.arama, 1)
        ust.addWidget(self.lbl_sayac)
        ust.addWidget(self.btn_yenile)
        for parca in (self.cmb_donem, self.dt_bas, self.lbl_tire, self.dt_bit,
                      self.cmb_durum, self.chk_iptal_gizle):
            alt.addWidget(parca)
        alt.addStretch()
        kok.addLayout(ust)
        kok.addLayout(alt)
        self.setStyleSheet(FILTRE_STILI)
        return kok

    def _donem_degisti(self, *_):
        ozel = self.cmb_donem.currentData() == "ozel"
        for parca in (self.dt_bas, self.lbl_tire, self.dt_bit):
            parca.setVisible(ozel)
        self.tabloyu_guncelle()

    def _aralik(self):
        anahtar = self.cmb_donem.currentData()
        if anahtar == "ozel":
            bas, bit = self.dt_bas.date().toPython(), self.dt_bit.date().toPython()
            return min(bas, bit), max(bas, bit)
        return donem_araligi(anahtar, datetime.now().date())

    # ------------------------------------------------------------------ veri
    def _sozluk_cek(self, yol, anahtar, deger, onceki):
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            cevap = oturum_kontrollu_istek("GET", f"{self.api_url}{yol}", headers=headers, timeout=5)
            if oturum_hatasi_mi(cevap):
                return onceki
            if cevap.status_code == 200:
                return {k[anahtar]: k[deger] for k in cevap.json()}
        except Exception as e:
            print(f"{yol} çekilirken hata oluştu:", e)
        return onceki

    def verileri_cek(self, *_):
        self.lbl_randevu_hatasi.hide()

        self.oda_adlari = self._sozluk_cek(
            "/api/odalar", "oda_id", "oda_adi", self.oda_adlari
        )
        self.psikolog_adlari = self._sozluk_cek(
            "/api/psikologlar", "personel_id", "ad_soyad",
            self.psikolog_adlari
        )

        headers = {"Authorization": f"Bearer {self.token}"}

        try:
            cevap = oturum_kontrollu_istek(
                "GET",
                f"{self.api_url}/api/randevular",
                headers=headers,
                timeout=5
            )

            if oturum_hatasi_mi(cevap):
                return

            if cevap.status_code != 200:
                self._randevu_yukleme_hatasi(api_hata_mesaji(cevap))
                return

            randevular = cevap.json()
            if not isinstance(randevular, list):
                raise ValueError("Geçersiz randevu listesi")

            self.randevular = randevular
            self.tabloyu_guncelle()

        except Exception as hata:
            self._randevu_yukleme_hatasi(
                api_hata_mesaji(hata=hata)
            )

    def _randevu_yukleme_hatasi(self, mesaj):
        """Hata durumunda mevcut listeyi koru ve güncellik uyarısı göster."""
        self.lbl_randevu_hatasi.setText(
            (mesaj or "Randevu listesi yüklenemedi.")
            + " Liste yenilenemedi; gösterilen kayıtlar güncel olmayabilir."
        )
        self.lbl_randevu_hatasi.show()


    # ------------------------------------------------------------------ tablo
    @staticmethod
    def _hucre(metin):
        oge = QTableWidgetItem(metin)
        oge.setTextAlignment(Qt.AlignCenter)
        return oge

    @staticmethod
    def _durum_rozeti(durum, tiklanabilir=False):
        etiket = DURUM_ETIKETLERI.get(durum, str(durum or "").capitalize())
        arka, yazi = DURUM_RENKLERI.get(durum, ("#E2E8F0", "#334155"))
        rozet = DurumRozeti(etiket + ("  ▾" if tiklanabilir else ""), tiklanabilir)
        rozet.setAlignment(Qt.AlignCenter)
        rozet.setStyleSheet(
            f"QLabel {{ background-color: {arka}; color: {yazi}; border-radius: 10px; "
            "padding: 3px 14px; font-weight: bold; font-size: 12px; border: 1px solid transparent; }"
            f"QLabel:hover {{ border: 1px solid {yazi if tiklanabilir else 'transparent'}; }}"
        )
        if tiklanabilir:
            rozet.setCursor(Qt.PointingHandCursor)
        kap = QWidget()
        kap.setStyleSheet("background: transparent;")
        yerlesim = QHBoxLayout(kap)
        yerlesim.setContentsMargins(6, 4, 6, 4)
        yerlesim.addStretch()
        yerlesim.addWidget(rozet)
        yerlesim.addStretch()
        return kap, rozet

    def tabloyu_guncelle(self, *_):
        liste = randevulari_filtrele(
            self.randevular, self.psikolog_adlari, self.oda_adlari,
            arama=self.arama.text(), aralik=self._aralik(),
            durum=self.cmb_durum.currentData(), iptalleri_gizle=self.chk_iptal_gizle.isChecked(),
        )
        simdi = datetime.now()
        liste.sort(key=lambda r: siralama_anahtari(r, simdi))

        # Qt eski hücre bileşenlerini hemen silmez; gizlemezsek yeni satırların arkasında eski rozetlerin hayaleti kalır.
        for satir in range(self.tablo.rowCount()):
            eski = self.tablo.cellWidget(satir, DURUM_SUTUNU)
            if eski is not None:
                eski.hide()
        self.tablo.setRowCount(0)
        self.tablo.setRowCount(len(liste))
        for satir, r in enumerate(liste):
            tarih, saat = tarih_saat_metinleri(r.get("baslangic_zamani"), r.get("bitis_zamani"))
            kimlik = self._hucre(str(r.get("randevu_id", "")))
            kimlik.setData(Qt.UserRole, r)  # düzenleme ve iptal bu kayıttan okur, sütun sırasına bağlı değildir
            psikolog = self.psikolog_adlari.get(r.get("psikolog_id"), f"Psikolog #{r.get('psikolog_id')}")
            oda = self.oda_adlari.get(r.get("oda_id"), f"Oda #{r.get('oda_id')}")
            durum_hucresi = self._hucre("")

            for sutun, oge in enumerate((kimlik, self._hucre(str(r.get("danisan_kod_id") or "")),
                                         self._hucre(psikolog), self._hucre(oda),
                                         self._hucre(tarih), self._hucre(saat),
                                         self._hucre(gorusme_etiketi(r.get("gorusme_tipi"))),
                                         self._hucre(terapi_etiketi(r.get("terapi_turu"), "-")), durum_hucresi)):
                self.tablo.setItem(satir, sutun, oge)
            tiklanabilir = self.duzenleme_yetkisi and durum_isaretlenebilir(r, simdi)
            kap, rozet = self._durum_rozeti(r.get("durum"), tiklanabilir)
            if tiklanabilir:
                rozet.tiklandi.connect(lambda r=r, rozet=rozet: self._durum_menusu_ac(r, rozet))
            self.tablo.setCellWidget(satir, DURUM_SUTUNU, kap)
            self.tablo.setRowHeight(satir, 40)

        self.lbl_sayac.setText(f"{len(liste)} / {len(self.randevular)} randevu")
        self.lbl_bos.setVisible(len(liste) == 0)
        self.tablo.setVisible(len(liste) > 0)
        self._iptal_bilgisini_guncelle()

    def _iptal_bilgisini_guncelle(self, *_):
        metin = iptal_bilgisi_metni(self.secili_randevu())
        self.lbl_iptal_bilgisi.setText(metin)
        self.lbl_iptal_bilgisi.setVisible(bool(metin))

    def secili_randevu(self):
        secili = self.tablo.selectionModel().selectedRows()
        if not secili:
            return None
        oge = self.tablo.item(secili[0].row(), 0)
        return oge.data(Qt.UserRole) if oge is not None else None

    # ------------------------------------------------------------------ işlemler
    def duzenle_secilen(self):
        randevu = self.secili_randevu()
        if randevu is None:
            QMessageBox.warning(self, "Seçim Yapılmadı", "Lütfen düzenlemek istediğiniz randevuyu tablodan seçin.")
            return

        durum = randevu.get("durum")
        if durum != "PLANLANDI":
            ek = ("\n\nLütfen bu danışan için yeni bir randevu oluşturun."
                  if durum == "IPTAL_EDILDI" else "")
            QMessageBox.warning(
                self, "İşlem Engellendi",
                f"'{DURUM_ETIKETLERI.get(durum, durum)}' durumundaki randevular düzenlenemez. "
                f"Yalnızca planlanmış randevular düzenlenebilir.{ek}",
            )
            return

        self.duzenle_formu = RandevuDuzenleFormu(
            api_url=self.api_url, token=self.token,
            mevcut_psikolog_id=self.mevcut_psikolog_id,
            randevu_id=randevu["randevu_id"], eski_veriler=randevu,
        )
        self.duzenle_formu.veriler_degisti.connect(self.verileri_cek)
        self.duzenle_formu.show()

    def _menuyu_goster(self, liste, konum):
        """Listeyi konumda açar ve seçilen eylemi döndürür (etkileşimli; testlerde değiştirilir)."""
        return liste.exec(konum)

    def _durum_menusu_ac(self, randevu, rozet):
        """Rozetin hemen altında Tamamlandı / Gelmedi listesini açar; seçim doğrudan sunucuya gider."""
        liste = QMenu(self)
        liste.setStyleSheet(
            "QMenu { background: white; border: 1px solid #CBD5E1; border-radius: 8px; padding: 6px; } "
            "QMenu::item { padding: 8px 22px 8px 12px; border-radius: 6px; font-weight: 700; font-size: 12px; color: #0F172A; } "
            "QMenu::item:selected { background: #F1F5F9; } QMenu::item:disabled { color: #94A3B8; }"
        )
        for kod in ("TAMAMLANDI", "GELMEDI"):
            eylem = liste.addAction(_renkli_nokta(DURUM_RENKLERI[kod][1]), DURUM_ETIKETLERI[kod])
            eylem.setData(kod)
            eylem.setEnabled(randevu.get("durum") != kod)          # mevcut durum seçilemez
        liste.setMinimumWidth(rozet.width())                       # en az rozet kadar geniş: yazının hemen altında durur
        sol_alt = rozet.mapToGlobal(QPoint(0, rozet.height() + 2))
        ekran = rozet.screen()
        ekran_sag = ekran.availableGeometry().right() if ekran is not None else sol_alt.x() + 100000
        konum = menu_konumu(sol_alt, rozet.width(), max(liste.sizeHint().width(), rozet.width()), ekran_sag)
        secim = self._menuyu_goster(liste, konum)
        if secim is not None:
            self.durum_isaretle(secim.data(), randevu=randevu)

    def durum_isaretle(self, yeni_durum, randevu=None):
        """Randevuyu (verilmezse seçili randevuyu) Tamamlandı ya da Gelmedi olarak işaretler; yalnızca başlangıcı geçmiş randevular."""
        if randevu is None:
            randevu = self.secili_randevu()
        if randevu is None:
            QMessageBox.warning(self, "Seçim Yapılmadı", "Lütfen durumunu işaretlemek istediğiniz randevuyu tablodan seçin.")
            return

        durum = randevu.get("durum")
        if durum == "IPTAL_EDILDI":
            QMessageBox.information(self, "Bilgi", "İptal edilmiş randevu Tamamlandı ya da Gelmedi olarak işaretlenemez.")
            return
        zaman = randevu_zamani(randevu.get("baslangic_zamani"))
        if zaman is not None and zaman > datetime.now():
            QMessageBox.information(
                self, "Bilgi", "Henüz başlamamış randevu işaretlenemez. Randevu saatinden sonra tekrar deneyin."
            )
            return
        if durum == yeni_durum:
            QMessageBox.information(self, "Bilgi", f"Bu randevu zaten '{DURUM_ETIKETLERI[yeni_durum]}' olarak işaretli.")
            return

        # Tamamlandı ⇄ Gelmedi geçişi kolay yapıldığı için her işaretleme onay ister (varsayılan düğme "Hayır")
        mevcut = f"\n\nŞu an '{DURUM_ETIKETLERI[durum]}' olarak işaretli." if durum in ("TAMAMLANDI", "GELMEDI") else ""
        onay = QMessageBox.question(
            self, "Onay",
            f"{randevu.get('danisan_kod_id')} randevusu '{DURUM_ETIKETLERI[yeni_durum]}' olarak işaretlensin mi?{mevcut}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if onay != QMessageBox.Yes:
            return

        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            cevap = oturum_kontrollu_istek(
                "PATCH", f"{self.api_url}/api/randevular/{randevu['randevu_id']}/durum",
                json={"durum": yeni_durum}, headers=headers, timeout=5,
            )
            if oturum_hatasi_mi(cevap):
                return
            if cevap.status_code == 200:
                self.verileri_cek()
            else:
                try:
                    mesaj = cevap.json().get("detail")
                except Exception:
                    mesaj = None
                QMessageBox.warning(self, "Hata", mesaj if isinstance(mesaj, str) and mesaj else "İşlem başarısız oldu.")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Bağlantı hatası: {str(e)}")

    def iptal_et_secilen(self):
        randevu = self.secili_randevu()
        if randevu is None:
            QMessageBox.warning(self, "Seçim Yapılmadı", "Lütfen iptal etmek istediğiniz randevuyu tablodan seçin.")
            return

        durum = randevu.get("durum")
        if durum == "IPTAL_EDILDI":
            QMessageBox.information(self, "Bilgi", "Bu randevu zaten iptal edilmiş.")
            return
        if durum != "PLANLANDI":
            QMessageBox.information(
                self, "Bilgi",
                f"'{DURUM_ETIKETLERI.get(durum, durum)}' durumundaki bir randevu iptal edilemez.",
            )
            return

        pencere = IptalNedeniDialog(self, randevu_kodu=randevu.get("danisan_kod_id"))
        if pencere.exec() != QDialog.Accepted:
            return
        nedeni, notu = pencere.sonuc()

        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            cevap = oturum_kontrollu_istek(
                "PATCH", f"{self.api_url}/api/randevular/{randevu['randevu_id']}/iptal",
                json={"iptal_nedeni": nedeni, "iptal_notu": notu}, headers=headers, timeout=5,
            )
            if oturum_hatasi_mi(cevap):
                return
            if cevap.status_code == 200:
                QMessageBox.information(self, "Başarılı", "Randevu iptal edildi.")
                self.verileri_cek()
            else:
                try:
                    mesaj = cevap.json().get("detail")
                except Exception:
                    mesaj = None
                QMessageBox.warning(self, "Hata", mesaj if isinstance(mesaj, str) and mesaj else "İşlem başarısız oldu.")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Bağlantı hatası: {str(e)}")
