"""
Danışanlar sayfası: psikoloğa göre danışanlar, bilgileri, randevu özeti ve geçmişi.

Danışanlar projede bilerek yalnızca bir kodla tutulur (kişisel veri yoktur, FR-008). Bu sayfa yalnızca kod,
ücret, istisna türü, aktiflik, oluşturan psikolog ve randevu bilgilerini gösterir.

Görünürlük sunucuda uygulanır: psikolog yalnızca kendi oluşturduğu danışanları görür; diğer roller psikolog seçerek
o psikologun danışanlarını ya da tümünü görür.
"""

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QButtonGroup, QComboBox, QFormLayout, QFrame, QGridLayout, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton, QSplitter, QStackedWidget,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from api_yoneticisi import oturum_hatasi_mi, oturum_kontrollu_istek
from api_yoneticisi import api_hata_mesaji
from randevu_ekranlari import (
    DURUM_ETIKETLERI, DURUM_RENKLERI, RandevuAnaEkrani, RandevuOlusturFormu,
    ara_normalle, randevu_zamani, tarih_saat_metinleri,
)
import turkce_mesaj_kutusu as tmk

ISTISNA_ETIKETLERI = {"YOK": "Yok", "KANSER": "Kanser hastası", "SEHIT_GAZI": "Şehit / gazi yakını"}
DANISAN_TABLO_BASLIKLARI = ["Danışan Kodu", "Psikolog", "Ücret", "İstisna", "Randevu", "Durum"]
GECMIS_TABLO_BASLIKLARI = ["Tarih", "Saat", "Oda", "Durum"]
BOLUMLER = [("Bilgiler", 0), ("Özet", 1), ("Geçmiş", 2)]


# ------------------------------------------------------------------ saf yardımcılar
def istisna_etiketi(kod):
    if not kod:
        return "Yok"
    return ISTISNA_ETIKETLERI.get(kod, str(kod).replace("_", " ").capitalize())


def tarih_metni(deger):
    zaman = randevu_zamani(deger)
    return zaman.strftime("%d.%m.%Y") if zaman else "-"


def randevulari_danisana_gore(randevular):
    gruplar = {}
    for r in randevular:
        gruplar.setdefault(r.get("danisan_kod_id"), []).append(r)
    return gruplar


def danisan_ozeti(randevular, simdi):
    """Durum sayıları, ilk randevu, son (geçmişteki en yakın) randevu ve sıradaki planlı randevu."""
    sayilar = {durum: 0 for durum in DURUM_ETIKETLERI}
    for r in randevular:
        if r.get("durum") in sayilar:
            sayilar[r["durum"]] += 1
    gecerli = [(randevu_zamani(r.get("baslangic_zamani")), r) for r in randevular if r.get("durum") != "IPTAL_EDILDI"]
    zamanlar = sorted(z for z, _ in gecerli if z is not None)
    gecmis = [z for z in zamanlar if z < simdi]
    gelecek = sorted(z for z, r in gecerli if z is not None and z >= simdi and r.get("durum") == "PLANLANDI")
    return {
        "sayilar": sayilar,
        "toplam": len(randevular),
        "ilk": zamanlar[0] if zamanlar else None,
        "son": gecmis[-1] if gecmis else None,
        "siradaki": gelecek[0] if gelecek else None,
    }


def danisanlari_filtrele(danisanlar, psikolog_adlari, arama=""):
    """Arama: danışan kodu ve oluşturan psikolog (Türkçe karakter ve büyük/küçük harf duyarsız)."""
    aranan = ara_normalle(arama).strip()
    if not aranan:
        return list(danisanlar)
    sonuc = []
    for danisan in danisanlar:
        metin = f"{danisan.get('danisan_kod_id', '')} {psikolog_adlari.get(danisan.get('olusturan_psikolog_id'), '')}"
        if aranan in ara_normalle(metin):
            sonuc.append(danisan)
    return sonuc


SAYFA_STILI = """
    QLineEdit, QComboBox {
        background-color: white; border: 1px solid #CBD5E1; border-radius: 8px;
        padding: 7px 10px; color: #0F172A; font-size: 13px;
    }
    QLineEdit:focus, QComboBox:focus { border: 1px solid #3B82F6; }
    /* Ana pencerenin genel stili her açılır kutuya min-width: 170px verir; bu sayfada geçersiz kılınır. */
    QComboBox { min-width: 120px; }
    QPushButton#btn_yenile {
        background-color: white; border: 1px solid #CBD5E1; border-radius: 8px;
        padding: 7px 14px; color: #1E293B; font-weight: bold;
    }
    QPushButton#btn_yenile:hover { background-color: #F1F5F9; }
    QPushButton#segment {
        background-color: white; border: 1px solid #CBD5E1; border-radius: 8px;
        padding: 7px 16px; color: #475569; font-weight: bold;
    }
    QPushButton#segment:checked { background-color: #0A1F5C; border: 1px solid #0A1F5C; color: white; }
    QPushButton#btn_yeni_randevu {
        background-color: #2563EB; border: none; border-radius: 8px; padding: 8px 14px; color: white; font-weight: bold;
    }
    QPushButton#btn_yeni_randevu:hover { background-color: #1D4ED8; }
    QLabel#lbl_sayac { color: #64748B; font-size: 12px; font-weight: bold; }
    QLabel#lbl_danisan_kodu { color: #0A1F5C; font-size: 18px; font-weight: bold; }
    QLabel#lbl_alt_baslik { color: #64748B; font-size: 12px; }
    QLabel#lbl_secim_yok { color: #64748B; font-size: 14px; font-weight: bold; }
    QFrame#detay_kutusu { background-color: white; border: 1px solid #D0D7E5; border-radius: 8px; }
    QLabel#alan_adi { color: #64748B; font-weight: bold; }
    QLabel#alan_degeri { color: #0F172A; }
"""


class DanisanlarEkrani(QWidget):
    """Psikolog seçilince onun danışanları listelenir; danışan seçilince bilgileri, özeti ve geçmişi düğmelerle görülür."""

    def __init__(self, api_url, token, mevcut_psikolog_id):
        super().__init__()
        self.api_url = api_url
        self.token = token
        self.mevcut_psikolog_id = mevcut_psikolog_id
        self.danisanlar = []
        self._son_danisan_filtre_id = None
        self.randevular = []
        self.psikolog_adlari = {}
        self.oda_adlari = {}
        self.randevu_gruplari = {}

        kok = QVBoxLayout(self)
        kok.setContentsMargins(0, 0, 0, 0)
        kok.setSpacing(10)
        kok.addLayout(self._ust_cubuk())

        self._yukleme_hatalari = {}
        self.lbl_yukleme_hatasi = QLabel()
        self.lbl_yukleme_hatasi.setObjectName("danisanYuklemeHatasi")
        self.lbl_yukleme_hatasi.setWordWrap(True)
        self.lbl_yukleme_hatasi.setStyleSheet(
            "color: #B42318; padding: 8px; font-size: 12px;"
        )
        self.lbl_yukleme_hatasi.hide()
        kok.addWidget(self.lbl_yukleme_hatasi)

        self.bolucu = QSplitter(Qt.Horizontal)
        self.bolucu.setChildrenCollapsible(False)
        self.bolucu.addWidget(self._liste_paneli())
        self.bolucu.addWidget(self._detay_paneli())
        self.bolucu.setStretchFactor(0, 3)
        self.bolucu.setStretchFactor(1, 2)
        kok.addWidget(self.bolucu, 1)

        self.setStyleSheet(SAYFA_STILI)
        self._detay_goster(None)
        self.verileri_cek()

    # ------------------------------------------------------------------ arayüz
    def _ust_cubuk(self):
        cubuk = QHBoxLayout()
        cubuk.setSpacing(8)

        self.cmb_psikolog = QComboBox()
        self.cmb_psikolog.addItem("Tüm psikologlar", None)
        self.cmb_psikolog.currentIndexChanged.connect(self._psikolog_degisti)

        self.arama = QLineEdit()
        self.arama.setPlaceholderText("Ara: danışan kodu, psikolog...")
        self.arama.setClearButtonEnabled(True)
        self.arama.setMinimumWidth(160)
        self.arama.textChanged.connect(self.tabloyu_guncelle)

        self.lbl_sayac = QLabel("")
        self.lbl_sayac.setObjectName("lbl_sayac")

        self.btn_yenile = QPushButton("⟳  Yenile")
        self.btn_yenile.setObjectName("btn_yenile")
        self.btn_yenile.setCursor(Qt.PointingHandCursor)
        self.btn_yenile.clicked.connect(self.verileri_cek)

        cubuk.addWidget(self.cmb_psikolog)
        cubuk.addWidget(self.arama, 1)
        cubuk.addWidget(self.lbl_sayac)
        cubuk.addWidget(self.btn_yenile)
        return cubuk

    def _liste_paneli(self):
        self.tablo = QTableWidget()
        self.tablo.setColumnCount(len(DANISAN_TABLO_BASLIKLARI))
        self.tablo.setHorizontalHeaderLabels(DANISAN_TABLO_BASLIKLARI)
        self.tablo.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tablo.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)  # kod kırpılmasın
        self.tablo.verticalHeader().setVisible(False)
        self.tablo.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tablo.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tablo.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tablo.setStyleSheet("""
            QTableWidget { background-color: white; border: 1px solid #D0D7E5; border-radius: 8px; gridline-color: #E2E8F0; }
            QHeaderView::section { background-color: #0A1F5C; color: white; font-weight: bold; padding: 10px; border: none; }
        """)
        self.tablo.itemSelectionChanged.connect(self._secim_degisti)
        self.tablo.setMinimumWidth(360)
        return self.tablo

    def _detay_paneli(self):
        kutu = QFrame()
        kutu.setObjectName("detay_kutusu")
        kutu.setMinimumWidth(400)
        yerlesim = QVBoxLayout(kutu)
        yerlesim.setContentsMargins(14, 14, 14, 14)
        yerlesim.setSpacing(10)

        self.lbl_secim_yok = QLabel("Ayrıntıları görmek için bir danışan seçin.")
        self.lbl_secim_yok.setObjectName("lbl_secim_yok")
        self.lbl_secim_yok.setAlignment(Qt.AlignCenter)
        self.lbl_secim_yok.setWordWrap(True)
        yerlesim.addWidget(self.lbl_secim_yok, 1)

        self.detay_icerik = QWidget()
        icerik = QVBoxLayout(self.detay_icerik)
        icerik.setContentsMargins(0, 0, 0, 0)
        icerik.setSpacing(10)

        baslik = QHBoxLayout()
        basliklar = QVBoxLayout()
        self.lbl_kod = QLabel("")
        self.lbl_kod.setObjectName("lbl_danisan_kodu")
        self.lbl_alt = QLabel("")
        self.lbl_alt.setObjectName("lbl_alt_baslik")
        basliklar.addWidget(self.lbl_kod)
        basliklar.addWidget(self.lbl_alt)
        self.btn_yeni_randevu = QPushButton("＋  Randevu")
        self.btn_yeni_randevu.setObjectName("btn_yeni_randevu")
        self.btn_yeni_randevu.setCursor(Qt.PointingHandCursor)
        self.btn_yeni_randevu.clicked.connect(self.yeni_randevu_ac)
        baslik.addLayout(basliklar, 1)
        baslik.addWidget(self.btn_yeni_randevu)
        icerik.addLayout(baslik)

        dugmeler = QHBoxLayout()
        dugmeler.setSpacing(6)
        self.bolum_dugmeleri = QButtonGroup(self)
        self.bolum_dugmeleri.setExclusive(True)
        self.btn_bolumler = {}
        for etiket, sira in BOLUMLER:
            dugme = QPushButton(etiket)
            dugme.setObjectName("segment")
            dugme.setCheckable(True)
            dugme.setCursor(Qt.PointingHandCursor)
            self.bolum_dugmeleri.addButton(dugme, sira)
            dugmeler.addWidget(dugme)
            self.btn_bolumler[etiket] = dugme
        dugmeler.addStretch()
        self.btn_bolumler["Bilgiler"].setChecked(True)
        self.bolum_dugmeleri.idClicked.connect(lambda sira: self.bolumler.setCurrentIndex(sira))
        icerik.addLayout(dugmeler)

        self.bolumler = QStackedWidget()
        self.bolumler.addWidget(self._bilgiler_sayfasi())
        self.bolumler.addWidget(self._ozet_sayfasi())
        self.bolumler.addWidget(self._gecmis_sayfasi())
        icerik.addWidget(self.bolumler, 1)
        yerlesim.addWidget(self.detay_icerik, 1)
        return kutu

    @staticmethod
    def _alan_etiketi(metin, adi):
        etiket = QLabel(metin)
        etiket.setObjectName(adi)
        return etiket

    def _bilgiler_sayfasi(self):
        sayfa = QWidget()
        form = QFormLayout(sayfa)
        form.setContentsMargins(0, 8, 0, 0)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)
        self.bilgi_alanlari = {}
        for anahtar, ad in (("kod", "Danışan kodu"), ("ucret", "Ücret durumu"), ("istisna", "İstisna türü"),
                            ("durum", "Durum"), ("psikolog", "Oluşturan psikolog"), ("tarih", "Oluşturulma tarihi")):
            deger = self._alan_etiketi("", "alan_degeri")
            deger.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self.bilgi_alanlari[anahtar] = deger
            form.addRow(self._alan_etiketi(ad, "alan_adi"), deger)
        return sayfa

    def _ozet_sayfasi(self):
        sayfa = QWidget()
        yerlesim = QVBoxLayout(sayfa)
        yerlesim.setContentsMargins(0, 8, 0, 0)
        yerlesim.setSpacing(12)
        kartlar = QGridLayout()
        kartlar.setSpacing(8)
        self.ozet_sayilari = {}
        for sira, durum in enumerate(("PLANLANDI", "TAMAMLANDI", "GELMEDI", "IPTAL_EDILDI")):
            arka, yazi = DURUM_RENKLERI[durum]
            kart = QFrame()
            kart.setStyleSheet(f"QFrame {{ background-color: {arka}; border-radius: 10px; }}")
            k_yerlesim = QVBoxLayout(kart)
            k_yerlesim.setContentsMargins(12, 8, 12, 8)
            sayi = QLabel("0")
            sayi.setAlignment(Qt.AlignCenter)
            sayi.setStyleSheet(f"color: {yazi}; font-size: 22px; font-weight: bold; background: transparent;")
            ad = QLabel(DURUM_ETIKETLERI[durum])
            ad.setAlignment(Qt.AlignCenter)
            ad.setStyleSheet(f"color: {yazi}; font-size: 12px; font-weight: bold; background: transparent;")
            k_yerlesim.addWidget(sayi)
            k_yerlesim.addWidget(ad)
            kartlar.addWidget(kart, sira // 2, sira % 2)
            self.ozet_sayilari[durum] = sayi
        yerlesim.addLayout(kartlar)

        form = QFormLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(8)
        self.ozet_alanlari = {}
        for anahtar, ad in (("toplam", "Toplam randevu"), ("ilk", "İlk randevu"),
                            ("son", "Son randevu"), ("siradaki", "Sıradaki randevu")):
            deger = self._alan_etiketi("-", "alan_degeri")
            self.ozet_alanlari[anahtar] = deger
            form.addRow(self._alan_etiketi(ad, "alan_adi"), deger)
        yerlesim.addLayout(form)
        yerlesim.addStretch()
        return sayfa

    def _gecmis_sayfasi(self):
        self.gecmis_tablosu = QTableWidget()
        self.gecmis_tablosu.setColumnCount(len(GECMIS_TABLO_BASLIKLARI))
        self.gecmis_tablosu.setHorizontalHeaderLabels(GECMIS_TABLO_BASLIKLARI)
        baslik = self.gecmis_tablosu.horizontalHeader()
        baslik.setSectionResizeMode(QHeaderView.ResizeToContents)
        baslik.setSectionResizeMode(2, QHeaderView.Stretch)   # oda adı kalan yeri alır; rozet ve tarih kırpılmaz
        self.gecmis_tablosu.verticalHeader().setVisible(False)
        self.gecmis_tablosu.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.gecmis_tablosu.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.gecmis_tablosu.setStyleSheet("""
            QTableWidget { background-color: white; border: 1px solid #D0D7E5; border-radius: 6px; gridline-color: #E2E8F0; }
            QHeaderView::section { background-color: #0A1F5C; color: white; font-weight: bold; padding: 6px; border: none; }
        """)
        return self.gecmis_tablosu

    # ------------------------------------------------------------------ veri
    def _yukleme_durumu(self, yol, mesaj=None):
        if mesaj:
            self._yukleme_hatalari[yol] = mesaj
        else:
            self._yukleme_hatalari.pop(yol, None)

        metin = "\\n".join(self._yukleme_hatalari.values())
        if metin:
            metin += (
                "\\nListe yenilenemedi; gösterilen bilgiler "
                "güncel olmayabilir."
            )

        self.lbl_yukleme_hatasi.setText(metin)
        self.lbl_yukleme_hatasi.setVisible(bool(metin))

    def _api_liste_getir(self, yol, params=None):
        try:
            cevap = oturum_kontrollu_istek(
                "GET",
                f"{self.api_url}{yol}",
                params=params,
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=5,
            )

            if oturum_hatasi_mi(cevap):
                return None

            if cevap.status_code != 200:
                self._yukleme_durumu(
                    yol, f"{yol}: {api_hata_mesaji(cevap)}"
                )
                return None

            veri = cevap.json()
            if (
                not isinstance(veri, list)
                or not all(isinstance(k, dict) for k in veri)
            ):
                raise ValueError("Geçersiz liste yanıtı")

            self._yukleme_durumu(yol)
            return veri

        except Exception as hata:
            self._yukleme_durumu(
                yol, f"{yol}: {api_hata_mesaji(hata=hata)}"
            )
            return None

    def _sozluk_cek(self, yol, anahtar, deger, onceki):
        liste = self._api_liste_getir(yol)
        if liste is None:
            return onceki
        try:
            return {k[anahtar]: k[deger] for k in liste}
        except (KeyError, TypeError):
            self._yukleme_durumu(
                yol, f"{yol}: Sunucudan beklenmeyen veri alındı."
            )
            return onceki


    def _psikologlari_yukle(self):
        """Psikolog kutusunu doldurur; giriş yapan kişi psikologsa kendi adına kilitlenir."""
        self.psikolog_adlari = self._sozluk_cek("/api/psikologlar", "personel_id", "ad_soyad", self.psikolog_adlari)
        secili = self.cmb_psikolog.currentData()
        self.cmb_psikolog.blockSignals(True)
        self.cmb_psikolog.clear()
        self.cmb_psikolog.addItem("Tüm psikologlar", None)
        for personel_id, ad in self.psikolog_adlari.items():
            self.cmb_psikolog.addItem(ad, personel_id)
        kendisi = self.cmb_psikolog.findData(self.mevcut_psikolog_id)
        if self.mevcut_psikolog_id is not None and kendisi >= 0:
            self.cmb_psikolog.setCurrentIndex(kendisi)
            self.cmb_psikolog.setEnabled(False)
        else:
            self.cmb_psikolog.setEnabled(True)
            self.cmb_psikolog.setCurrentIndex(max(self.cmb_psikolog.findData(secili), 0))
        self.cmb_psikolog.blockSignals(False)

    def _randevulari_yukle(self):
        liste = self._api_liste_getir("/api/randevular")
        if liste is not None:
            self.randevular = liste
        self.randevu_gruplari = randevulari_danisana_gore(
            self.randevular
        )


    def _danisanlari_yukle(self):
        params = {}
        psikolog_id = self.cmb_psikolog.currentData()
        if psikolog_id is not None:
            params["psikolog_id"] = int(psikolog_id)

        liste = self._api_liste_getir(
            "/api/danisan-kodlari", params=params
        )

        if liste is not None:
            self.danisanlar = liste
            self._son_danisan_filtre_id = psikolog_id
        elif psikolog_id != self._son_danisan_filtre_id:
            # Farklı psikoloğa geçildiğinde eski psikoloğun
            # danışanlarını yeni seçimin altında gösterme.
            self.danisanlar = []

        self.tabloyu_guncelle()


    def verileri_cek(self, *_):
        self.oda_adlari = self._sozluk_cek("/api/odalar", "oda_id", "oda_adi", self.oda_adlari)
        self._psikologlari_yukle()
        self._randevulari_yukle()
        self._danisanlari_yukle()

    def _psikolog_degisti(self, *_):
        self._danisanlari_yukle()

    # ------------------------------------------------------------------ liste
    @staticmethod
    def _hucre(metin):
        oge = QTableWidgetItem(metin)
        oge.setTextAlignment(Qt.AlignCenter)
        return oge

    def _psikolog_adi(self, psikolog_id):
        return self.psikolog_adlari.get(psikolog_id, f"Psikolog #{psikolog_id}" if psikolog_id is not None else "-")

    def secili_danisan(self):
        secili = self.tablo.selectionModel().selectedRows()
        if not secili:
            return None
        oge = self.tablo.item(secili[0].row(), 0)
        return oge.data(Qt.UserRole) if oge is not None else None

    def tabloyu_guncelle(self, *_):
        onceki = (self.secili_danisan() or {}).get("danisan_kod_id")
        liste = danisanlari_filtrele(self.danisanlar, self.psikolog_adlari, self.arama.text())

        self.tablo.blockSignals(True)
        self.tablo.setRowCount(0)
        self.tablo.setRowCount(len(liste))
        for satir, danisan in enumerate(liste):
            kod = danisan.get("danisan_kod_id")
            kod_hucresi = self._hucre(str(kod))
            kod_hucresi.setData(Qt.UserRole, danisan)
            randevu_sayisi = len(self.randevu_gruplari.get(kod, []))
            hucreler = (
                kod_hucresi,
                self._hucre(self._psikolog_adi(danisan.get("olusturan_psikolog_id"))),
                self._hucre("Ücretli" if danisan.get("ucretli_mi") else "Ücretsiz"),
                self._hucre(istisna_etiketi(danisan.get("istisna_turu"))),
                self._hucre(str(randevu_sayisi)),
                self._hucre("Aktif" if danisan.get("aktif_mi", True) else "Pasif"),
            )
            for sutun, oge in enumerate(hucreler):
                self.tablo.setItem(satir, sutun, oge)
            self.tablo.setRowHeight(satir, 38)
            if kod == onceki:
                self.tablo.selectRow(satir)
        self.tablo.blockSignals(False)

        self.lbl_sayac.setText(f"{len(liste)} danışan")
        self._secim_degisti()

    def _secim_degisti(self):
        self._detay_goster(self.secili_danisan())

    # ------------------------------------------------------------------ ayrıntı
    def _detay_goster(self, danisan):
        secili_var = danisan is not None
        self.lbl_secim_yok.setVisible(not secili_var)
        self.detay_icerik.setVisible(secili_var)
        if not secili_var:
            return

        kod = danisan.get("danisan_kod_id")
        psikolog = self._psikolog_adi(danisan.get("olusturan_psikolog_id"))
        self.lbl_kod.setText(str(kod))
        self.lbl_alt.setText(f"Oluşturan psikolog: {psikolog}")

        self.bilgi_alanlari["kod"].setText(str(kod))
        self.bilgi_alanlari["ucret"].setText("Ücretli" if danisan.get("ucretli_mi") else "Ücretsiz")
        self.bilgi_alanlari["istisna"].setText(istisna_etiketi(danisan.get("istisna_turu")))
        self.bilgi_alanlari["durum"].setText("Aktif" if danisan.get("aktif_mi", True) else "Pasif")
        self.bilgi_alanlari["psikolog"].setText(psikolog)
        self.bilgi_alanlari["tarih"].setText(tarih_metni(danisan.get("olusturulma_tarihi")))

        randevular = self.randevu_gruplari.get(kod, [])
        ozet = danisan_ozeti(randevular, datetime.now())
        for durum, sayi in self.ozet_sayilari.items():
            sayi.setText(str(ozet["sayilar"][durum]))
        self.ozet_alanlari["toplam"].setText(str(ozet["toplam"]))
        for anahtar in ("ilk", "son", "siradaki"):
            zaman = ozet[anahtar]
            self.ozet_alanlari[anahtar].setText(zaman.strftime("%d.%m.%Y %H:%M") if zaman else "-")

        self._gecmisi_doldur(randevular)

    def _gecmisi_doldur(self, randevular):
        # Qt eski hücre bileşenlerini hemen silmez; gizlemezsek eski rozetlerin hayaleti kalır.
        for satir in range(self.gecmis_tablosu.rowCount()):
            eski = self.gecmis_tablosu.cellWidget(satir, 3)
            if eski is not None:
                eski.hide()
        self.gecmis_tablosu.setRowCount(0)
        sirali = sorted(randevular, key=lambda r: randevu_zamani(r.get("baslangic_zamani")) or datetime.min, reverse=True)
        self.gecmis_tablosu.setRowCount(len(sirali))
        for satir, r in enumerate(sirali):
            tarih, saat = tarih_saat_metinleri(r.get("baslangic_zamani"), r.get("bitis_zamani"))
            oda = self.oda_adlari.get(r.get("oda_id"), f"Oda #{r.get('oda_id')}")
            durum_hucresi = self._hucre("")
            durum_hucresi.setToolTip(DURUM_ETIKETLERI.get(r.get("durum"), str(r.get("durum") or "")))
            for sutun, oge in enumerate((self._hucre(tarih), self._hucre(saat), self._hucre(oda), durum_hucresi)):
                self.gecmis_tablosu.setItem(satir, sutun, oge)
            kap, _ = RandevuAnaEkrani._durum_rozeti(r.get("durum"))
            self.gecmis_tablosu.setCellWidget(satir, 3, kap)
            self.gecmis_tablosu.setRowHeight(satir, 36)

    # ------------------------------------------------------------------ işlemler
    def yeni_randevu_ac(self):
        """Seçili danışan ve onu oluşturan psikologla yeni randevu formunu açar."""
        danisan = self.secili_danisan()
        if danisan is None:
            tmk.uyari(self, "Seçim Yapılmadı", "Lütfen randevu oluşturmak istediğiniz danışanı seçin.")
            return
        self.randevu_formu = RandevuOlusturFormu(
            self.api_url, self.token, self.mevcut_psikolog_id,
            onceden_danisan=danisan.get("danisan_kod_id"),
            onceden_psikolog_id=danisan.get("olusturan_psikolog_id"),
        )
        self.randevu_formu.veriler_degisti.connect(self.verileri_cek)
        self.randevu_formu.show()
