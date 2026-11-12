"""Cihaz bakım / kalibrasyon planları ekranı (müdür konfigürasyonu).

Her cihaz için tekrarlayan plan tanımlanır: tür, tekrar aralığı (gün), uyarı süresi (gün) ve
sonraki görev tarihi. Plan durumu: Planlı, Yaklaşıyor (uyarı süresi içinde), Gecikmiş, Pasif.
"""
import datetime

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDateEdit, QDialog, QFormLayout, QFrame, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMessageBox, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from api_yoneticisi import api_hata_mesaji
from api_yoneticisi import oturum_hatasi_mi, oturum_kontrollu_istek
from tablo_tasarimi import (
    FORM_STIL, bos_mesaj_olustur, hap, islem_butonlari, metin_item, sayfa_basligi, sayi_cipi,
    sil_onayi, tablo_olustur, tarih_goster, yenile_butonu_olustur,
)

# Sık kullanılan tekrar aralıkları: (görünen ad, gün). "Özel" her zaman en sonda durur.
HAZIR_PERIYOTLAR = (
    ("Haftalık (7 gün)", 7),
    ("Aylık (30 gün)", 30),
    ("3 aylık (90 gün)", 90),
    ("6 aylık (180 gün)", 180),
    ("Yıllık (365 gün)", 365),
)
OZEL_PERIYOT = "Özel"
TUR_ONERILERI = ("Periyodik bakım", "Yıllık bakım", "6 aylık bakım", "Kalibrasyon", "Temizlik ve kontrol")

PLAN_FORM_STIL = FORM_STIL + """
    QSpinBox { background: white; color: #0F2552; border: 1px solid #C7D9FB; border-radius: 10px;
               padding: 9px 12px; font-size: 13px; }
    QSpinBox:focus { border: 2px solid #3B82F6; }
    QCheckBox { color: #1E3A8A; font-size: 13px; font-weight: 700; }
    QLabel#ozet { background: #EEF4FF; color: #1E3A8A; border-radius: 10px; padding: 10px 12px;
                  font-weight: 600; font-size: 12px; }
    QPushButton#vazgec { background: white; color: #475569; border: 1px solid #CBD5E1;
                         border-radius: 10px; padding: 12px; font-size: 14px; font-weight: 700; }
    QPushButton#vazgec:hover { background: #F1F5F9; }
"""

DURUM_RENKLERI = {
    "Planlı": ("#166534", "#DCFCE7"),
    "Yaklaşıyor": ("#854D0E", "#FEF3C7"),
    "Gecikmiş": ("#991B1B", "#FEE2E2"),
    "Pasif": ("#6B7280", "#F3F4F6"),
}


def hata_metni(cevap, varsayilan):
    """Sunucu yanıtından kullanıcıya gösterilecek kısa hata metni (ayrıntı/dizi içermez)."""
    try:
        detay = cevap.json().get("detail")
    except Exception:
        return varsayilan
    if isinstance(detay, str):
        return detay
    if isinstance(detay, list) and detay:
        mesaj = str(detay[0].get("msg", "")) if isinstance(detay[0], dict) else ""
        mesaj = mesaj.replace("Value error, ", "")
        return mesaj or varsayilan
    return varsayilan


def kalan_gun_metni(kalan_gun, durum):
    if durum == "Pasif":
        return "Pasif"
    if kalan_gun < 0:
        return f"{-kalan_gun} gün gecikti"
    if kalan_gun == 0:
        return "bugün"
    return f"{kalan_gun} gün kaldı"


def periyot_metni(gun):
    for ad, deger in HAZIR_PERIYOTLAR:
        if deger == gun:
            return ad.split(" (")[0]
    return f"{gun} günde bir"


class PlanFormu(QDialog):
    """Yeni plan ekleme / mevcut planı düzenleme penceresi."""

    def __init__(self, api_url, token, plan=None, ebeveyn=None):
        super().__init__(ebeveyn)
        self.api_url = api_url
        self.token = token
        self.plan = plan                         # None -> yeni plan
        self._tarih_elle_degisti = False
        self.setWindowTitle("Planı Düzenle" if plan else "Yeni Bakım / Kalibrasyon Planı")
        self.setMinimumWidth(460)
        self.setStyleSheet(PLAN_FORM_STIL)
        self.arayuzu_kur()
        if plan:
            self.plan_bilgisini_yukle()
        else:
            self.cihazlari_yukle()
        self.ozeti_guncelle()

    # ------------------------------------------------------------------ arayüz
    def arayuzu_kur(self):
        ana = QVBoxLayout(self)
        ana.setContentsMargins(22, 20, 22, 18)
        ana.setSpacing(14)

        form = QFormLayout()
        form.setSpacing(14)
        form.setLabelAlignment(Qt.AlignLeft)

        if self.plan:
            self.lbl_cihaz = QLineEdit(f"{self.plan.get('envanter_kodu', '')} - {self.plan.get('cihaz_adi', '')}")
            self.lbl_cihaz.setReadOnly(True)
            form.addRow("Cihaz:", self.lbl_cihaz)
            self.cmb_cihaz = None
        else:
            self.cmb_cihaz = QComboBox()
            self.cmb_cihaz.addItem("— Cihaz seçiniz —", None)
            form.addRow("Cihaz (*):", self.cmb_cihaz)

        self.cmb_tur = QComboBox()
        self.cmb_tur.setEditable(True)
        self.cmb_tur.addItems(TUR_ONERILERI)
        self.cmb_tur.setCurrentIndex(-1)
        self.cmb_tur.lineEdit().setPlaceholderText("Örn. Yıllık bakım, Kalibrasyon")
        self.cmb_tur.lineEdit().setMaxLength(100)
        self.cmb_tur.currentTextChanged.connect(self.ozeti_guncelle)
        form.addRow("Plan türü (*):", self.cmb_tur)

        tekrar = QHBoxLayout()
        tekrar.setSpacing(10)
        self.cmb_hazir = QComboBox()
        for ad, _ in HAZIR_PERIYOTLAR:
            self.cmb_hazir.addItem(ad)
        self.cmb_hazir.addItem(OZEL_PERIYOT)
        self.spin_periyot = QSpinBox()
        self.spin_periyot.setRange(1, 3650)
        self.spin_periyot.setSuffix(" gün")
        self.spin_periyot.setValue(365)
        tekrar.addWidget(self.cmb_hazir, 1)
        tekrar.addWidget(self.spin_periyot, 1)
        form.addRow("Tekrar aralığı (*):", tekrar)
        self.cmb_hazir.setCurrentIndex(len(HAZIR_PERIYOTLAR) - 1)      # Yıllık
        self.cmb_hazir.activated.connect(self.hazir_secildi)
        self.spin_periyot.valueChanged.connect(self.periyot_degisti)

        self.spin_uyari = QSpinBox()
        self.spin_uyari.setRange(0, 365)
        self.spin_uyari.setSuffix(" gün önce")
        self.spin_uyari.setValue(7)
        self.spin_uyari.valueChanged.connect(self.ozeti_guncelle)
        form.addRow("Uyarı süresi:", self.spin_uyari)

        self.dt_sonraki = QDateEdit()
        self.dt_sonraki.setCalendarPopup(True)
        self.dt_sonraki.setDisplayFormat("dd.MM.yyyy")
        self.dt_sonraki.setDate(QDate.currentDate().addDays(self.spin_periyot.value()))
        self.dt_sonraki.userDateChanged.connect(self.tarih_elle_degistirildi)
        form.addRow("Sonraki tarih:", self.dt_sonraki)

        self.chk_aktif = QCheckBox("Plan aktif (dashboard'da ve uyarılarda görünür)")
        self.chk_aktif.setChecked(True)
        self.chk_aktif.setVisible(self.plan is not None)
        form.addRow("", self.chk_aktif)
        ana.addLayout(form)

        self.lbl_ozet = QLabel()
        self.lbl_ozet.setObjectName("ozet")
        self.lbl_ozet.setWordWrap(True)
        ana.addWidget(self.lbl_ozet)

        self.lbl_cihaz_hatasi = QLabel()
        self.lbl_cihaz_hatasi.setWordWrap(True)
        self.lbl_cihaz_hatasi.setStyleSheet("color: #B42318;")
        self.lbl_cihaz_hatasi.hide()
        ana.addWidget(self.lbl_cihaz_hatasi)

        butonlar = QHBoxLayout()
        butonlar.setSpacing(10)
        self.btn_vazgec = QPushButton("Vazgeç")
        self.btn_vazgec.setObjectName("vazgec")
        self.btn_vazgec.setCursor(Qt.PointingHandCursor)
        self.btn_vazgec.clicked.connect(self.reject)
        self.btn_kaydet = QPushButton("Kaydet")
        self.btn_kaydet.setObjectName("kaydet")
        self.btn_kaydet.setCursor(Qt.PointingHandCursor)
        self.btn_kaydet.clicked.connect(self.kaydet)
        butonlar.addWidget(self.btn_vazgec)
        butonlar.addWidget(self.btn_kaydet, 1)
        ana.addLayout(butonlar)

    # ----------------------------------------------------------------- etkileşim
    def hazir_secildi(self, indeks):
        if indeks < len(HAZIR_PERIYOTLAR):
            self.spin_periyot.setValue(HAZIR_PERIYOTLAR[indeks][1])

    def periyot_degisti(self, gun):
        # Seçili hazır aralık ile gün sayısı tutarlı kalsın.
        indeks = len(HAZIR_PERIYOTLAR)                                   # "Özel"
        for i, (_, deger) in enumerate(HAZIR_PERIYOTLAR):
            if deger == gun:
                indeks = i
        self.cmb_hazir.setCurrentIndex(indeks)
        # Uyarı süresi periyottan uzun olamaz.
        self.spin_uyari.setMaximum(min(365, gun))
        if not self._tarih_elle_degisti:
            self.dt_sonraki.blockSignals(True)
            self.dt_sonraki.setDate(QDate.currentDate().addDays(gun))
            self.dt_sonraki.blockSignals(False)
        self.ozeti_guncelle()

    def tarih_elle_degistirildi(self, _tarih):
        self._tarih_elle_degisti = True
        self.ozeti_guncelle()

    def ozeti_guncelle(self, *_):
        if not hasattr(self, "lbl_ozet"):          # arayüz kurulurken sinyaller erken tetiklenebilir
            return
        gun = self.spin_periyot.value()
        uyari = self.spin_uyari.value()
        sonraki = self.dt_sonraki.date().toPython()
        uyari_baslangic = sonraki - datetime.timedelta(days=uyari)
        tur = self.cmb_tur.currentText().strip() or "Plan"
        self.lbl_ozet.setText(
            f"{tur}: her {gun} günde bir tekrarlanır. Sonraki tarih {sonraki:%d.%m.%Y}; "
            + (f"{uyari} gün kala ({uyari_baslangic:%d.%m.%Y} itibarıyla) uyarı verilir."
               if uyari else "uyarı verilmez (yalnızca tarih gelince görünür).")
        )

    # ---------------------------------------------------------------- veri alma
    def cihazlari_yukle(self):
        if self.cmb_cihaz is None:
            return

        self.btn_kaydet.setEnabled(False)
        self.cmb_cihaz.clear()
        self.cmb_cihaz.addItem("— Cihaz seçiniz —", None)
        self.lbl_cihaz_hatasi.hide()

        try:
            cevap = oturum_kontrollu_istek(
                "GET",
                f"{self.api_url}/api/cihazlar",
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=10,
            )

            if oturum_hatasi_mi(cevap):
                return

            if cevap.status_code != 200:
                self.lbl_cihaz_hatasi.setText(api_hata_mesaji(cevap))
                self.lbl_cihaz_hatasi.show()
                return

            cihazlar = cevap.json()

            if not isinstance(cihazlar, list):
                raise ValueError("Geçersiz cihaz listesi")

            if not cihazlar:
                self.lbl_cihaz_hatasi.setText(
                    "Sistemde kayıtlı cihaz bulunmamaktadır."
                )
                self.lbl_cihaz_hatasi.show()
                return

            for cihaz in cihazlar:
                self.cmb_cihaz.addItem(
                    f"{cihaz['envanter_kodu']} - {cihaz['cihaz_adi']}",
                    cihaz["cihaz_id"]
                )

            self.btn_kaydet.setEnabled(True)

        except Exception as hata:
            self.cmb_cihaz.clear()
            self.btn_kaydet.setEnabled(False)
            self.lbl_cihaz_hatasi.setText(api_hata_mesaji(hata=hata))
            self.lbl_cihaz_hatasi.show()

    def plan_bilgisini_yukle(self):
        p = self.plan
        self.cmb_tur.setEditText(p.get("gorev_turu", ""))
        self.spin_periyot.setValue(int(p.get("periyot_gun", 365)))
        self.spin_uyari.setValue(int(p.get("uyari_suresi_gun", 7)))
        tarih = QDate.fromString(str(p.get("sonraki_gorev_tarihi", ""))[:10], "yyyy-MM-dd")
        if tarih.isValid():
            self.dt_sonraki.setDate(tarih)
        self._tarih_elle_degisti = True                      # mevcut tarih kendiliğinden kaymasın
        self.chk_aktif.setChecked(bool(p.get("aktif_mi", True)))

    # ------------------------------------------------------------------ kaydetme
    def veri_olustur(self):
        veri = {
            "gorev_turu": self.cmb_tur.currentText().strip(),
            "periyot_gun": self.spin_periyot.value(),
            "uyari_suresi_gun": self.spin_uyari.value(),
            "sonraki_gorev_tarihi": self.dt_sonraki.date().toString("yyyy-MM-dd"),
        }
        if self.plan:
            veri["aktif_mi"] = self.chk_aktif.isChecked()
        else:
            veri["cihaz_id"] = self.cmb_cihaz.currentData()
        return veri

    def dogrula(self, veri):
        if not self.plan and veri["cihaz_id"] is None:
            return "Lütfen bir cihaz seçiniz."
        if len(veri["gorev_turu"]) < 2:
            return "Plan türü en az 2 karakter olmalıdır."
        if veri["uyari_suresi_gun"] > veri["periyot_gun"]:
            return "Uyarı süresi tekrar aralığından uzun olamaz."
        return None

    def kaydet(self):
        veri = self.veri_olustur()
        hata = self.dogrula(veri)
        if hata:
            QMessageBox.warning(self, "Uyarı", hata)
            return
        yontem = "PUT" if self.plan else "POST"
        adres = f"{self.api_url}/api/bakim-planlari" + (f"/{self.plan['plan_id']}" if self.plan else "")
        try:
            cevap = oturum_kontrollu_istek(yontem, adres, json=veri,
                                           headers={"Authorization": f"Bearer {self.token}"}, timeout=10)
            if oturum_hatasi_mi(cevap):
                return
            if cevap.status_code in (200, 201):
                self.accept()
            else:
                QMessageBox.warning(self, "Plan kaydedilemedi", hata_metni(cevap, "Plan kaydedilemedi."))
        except Exception:
            QMessageBox.critical(self, "Bağlantı hatası", "Sunucuya ulaşılamadı. Lütfen tekrar deneyin.")


class BakimPlanlariEkrani(QWidget):
    """Bakım ve kalibrasyon planlarının listelendiği, aranabilir ve düzenlenebilir ekran."""

    FILTRELER = (("Aktif planlar", True), ("Tüm planlar", None), ("Pasif planlar", False))

    def __init__(self, api_url, token):
        super().__init__()
        self.api_url = api_url
        self.token = token
        self.basliklar = {"Authorization": f"Bearer {token}"}
        self.planlar = {}
        self.arayuzu_olustur()

    def arayuzu_olustur(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        self.arama = QLineEdit()
        self.arama.setPlaceholderText("🔍  Cihaz veya plan türü ara...")
        self.arama.textChanged.connect(self.filtrele)

        self.cip_toplam = sayi_cipi("0 plan")
        self.cip_yaklasan = sayi_cipi("0 yaklaşan", "#854D0E", "#FEF3C7")
        self.cip_gecmis = sayi_cipi("0 gecikmiş", "#991B1B", "#FEE2E2")

        layout.addWidget(sayfa_basligi(
            "Bakım ve Kalibrasyon Planları",
            "Cihazların tekrar aralığı, uyarı süresi ve sonraki bakım/kalibrasyon tarihi",
            self.arama, yenile_butonu_olustur(self.verileri_yukle),
            [self.cip_toplam, self.cip_yaklasan, self.cip_gecmis]))

        self.tablo = tablo_olustur(["CİHAZ", "PLAN", "TEKRAR", "UYARI", "SONRAKİ TARİH", "DURUM", "İŞLEM"])
        baslik = self.tablo.horizontalHeader()
        baslik.setSectionResizeMode(0, QHeaderView.Stretch)
        baslik.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        baslik.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        baslik.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        baslik.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        baslik.setSectionResizeMode(5, QHeaderView.Fixed)
        baslik.setSectionResizeMode(6, QHeaderView.Fixed)
        self.tablo.setColumnWidth(5, 190)
        self.tablo.setColumnWidth(6, 110)

        self.bos_mesaj = bos_mesaj_olustur("")
        kart = QFrame()
        kart.setObjectName("kart")
        kl = QVBoxLayout(kart)
        kl.setContentsMargins(8, 8, 8, 8)

        filtre_satiri = QHBoxLayout()
        filtre_satiri.setContentsMargins(10, 4, 10, 4)
        etiket = QLabel("Göster:")
        etiket.setStyleSheet("color: #6B7FA8; font-size: 12px; font-weight: 700;")
        self.cmb_filtre = QComboBox()
        for ad, _ in self.FILTRELER:
            self.cmb_filtre.addItem(ad)
        self.cmb_filtre.setStyleSheet("QComboBox { background: #F3F7FF; border: 1px solid #DCE6FA; "
                                      "border-radius: 10px; padding: 6px 12px; color: #0F2552; font-size: 12px; }")
        self.cmb_filtre.currentIndexChanged.connect(self.verileri_yukle)
        filtre_satiri.addWidget(etiket)
        filtre_satiri.addWidget(self.cmb_filtre)
        filtre_satiri.addStretch()
        kl.addLayout(filtre_satiri)
        kl.addWidget(self.tablo)
        kl.addWidget(self.bos_mesaj)
        layout.addWidget(kart, 1)

        self.verileri_yukle()

    # --------------------------------------------------------------------- veri
    def secili_aktiflik_filtresi(self):
        return self.FILTRELER[self.cmb_filtre.currentIndex()][1]

    def verileri_yukle(self, *_):
        self.tablo.setRowCount(0)
        self.planlar.clear()
        adres = f"{self.api_url}/api/bakim-planlari"
        aktiflik = self.secili_aktiflik_filtresi()
        if aktiflik is not None:
            adres += f"?aktif_mi={'true' if aktiflik else 'false'}"
        try:
            cevap = oturum_kontrollu_istek("GET", adres, headers=self.basliklar, timeout=10)
            if oturum_hatasi_mi(cevap):
                return
            cevap.raise_for_status()
            kayitlar = cevap.json()
        except Exception:
            self.bos_mesaj.setText("Planlar yüklenemedi. Sunucu bağlantısını kontrol edin.")
            self.bos_mesaj.show()
            self.tablo.hide()
            return

        yaklasan = gecmis = 0
        self.tablo.setRowCount(len(kayitlar))
        for i, p in enumerate(kayitlar):
            self.planlar[p["plan_id"]] = p
            cihaz = metin_item(f"{p['envanter_kodu']} - {p['cihaz_adi']}", kalin=True)
            cihaz.setData(Qt.UserRole, p["plan_id"])
            self.tablo.setItem(i, 0, cihaz)
            self.tablo.setItem(i, 1, metin_item(p["gorev_turu"]))
            self.tablo.setItem(i, 2, metin_item(periyot_metni(p["periyot_gun"]), ortala=True))
            self.tablo.setItem(i, 3, metin_item(f"{p['uyari_suresi_gun']} gün önce", ortala=True))
            self.tablo.setItem(i, 4, metin_item(tarih_goster(p["sonraki_gorev_tarihi"]), ortala=True))

            durum = p["durum"]
            renk, arka = DURUM_RENKLERI.get(durum, DURUM_RENKLERI["Planlı"])
            self.tablo.setCellWidget(i, 5, hap(f"{durum}  ·  {kalan_gun_metni(p['kalan_gun'], durum)}"
                                               if durum != "Pasif" else "Pasif", renk, arka))
            self.tablo.setCellWidget(i, 6, islem_butonlari(
                lambda _=False, pid=p["plan_id"]: self.plan_duzenle(pid),
                lambda _=False, pid=p["plan_id"]: self.plan_sil(pid)))
            yaklasan += durum == "Yaklaşıyor"
            gecmis += durum == "Gecikmiş"

        self.cip_toplam.setText(f"{len(kayitlar)} plan")
        self.cip_yaklasan.setText(f"{yaklasan} yaklaşan")
        self.cip_gecmis.setText(f"{gecmis} gecikmiş")
        self.bos_mesaj.setText(
            "Henüz bakım/kalibrasyon planı yok. Üstteki “Yeni Plan” butonuyla ekleyebilirsiniz."
            if aktiflik is not False else "Pasif plan yok.")
        self.bos_mesaj.setVisible(not kayitlar)
        self.tablo.setVisible(bool(kayitlar))
        self.filtrele(self.arama.text())

    def filtrele(self, metin):
        aranan = metin.strip().lower()
        for satir in range(self.tablo.rowCount()):
            icerik = " ".join(
                (self.tablo.item(satir, k).text() if self.tablo.item(satir, k) else "")
                for k in (0, 1)).lower()
            self.tablo.setRowHidden(satir, aranan not in icerik)

    # ----------------------------------------------------------------- eylemler
    def yeni_plan_ekle(self):
        form = PlanFormu(self.api_url, self.token, None, self)
        if form.exec():
            self.verileri_yukle()

    def plan_duzenle(self, plan_id):
        plan = self.planlar.get(plan_id)
        if plan:
            form = PlanFormu(self.api_url, self.token, plan, self)
            if form.exec():
                self.verileri_yukle()

    def plan_sil(self, plan_id):
        plan = self.planlar.get(plan_id)
        if not plan:
            return
        if not sil_onayi(self, "Planı Sil",
                         f"“{plan['cihaz_adi']}” cihazının “{plan['gorev_turu']}” planı silinsin mi?"):
            return
        try:
            cevap = oturum_kontrollu_istek("DELETE", f"{self.api_url}/api/bakim-planlari/{plan_id}",
                                           headers=self.basliklar, timeout=10)
            if oturum_hatasi_mi(cevap):
                return
            if cevap.status_code == 200:
                self.verileri_yukle()
            else:
                QMessageBox.warning(self, "Silinemedi", hata_metni(cevap, "Plan silinemedi."))
        except Exception:
            QMessageBox.critical(self, "Bağlantı hatası", "Sunucuya ulaşılamadı. Lütfen tekrar deneyin.")
