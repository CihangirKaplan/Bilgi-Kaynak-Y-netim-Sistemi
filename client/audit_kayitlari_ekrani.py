from datetime import datetime
import requests
from client.api_yoneticisi import istek_hatasi_metni, oturum_kontrollu_istek, oturum_hatasi_mi

from PySide6.QtCore import Qt, QDate, QRectF
from PySide6.QtGui import QColor, QPainter, QFontMetrics
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QLineEdit, QComboBox,
    QCheckBox, QDateEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QFrame, QDialog,
    QMenu, QWidgetAction, QApplication, QMessageBox,
    QStyledItemDelegate, QGraphicsDropShadowEffect, QStyle, QSizePolicy
)
from client.bilgi_rozeti import BilgiRozeti, ROZET_METNI
from client.liste_excel import aktarimi_denetime_yaz
from client.rapor_cikti import bicim_adi, cikti_dosyasi, kayit_yolu_sec
from client.sayfa_tema import (
    DurumRozetiDelegate, TABLO_STILI, VARSAYILAN_DURUM_RENGI, dialog_stili, kart_olustur, liste_sayfasi_stili, ozet_karti_olustur,
)



ROZET_ACIKLAMASI = (
    "Burada sistemde kimin, ne zaman, ne yaptığına bakarsınız; kayıtlar değiştirilemez ve silinemez.\n"
    "Ayrıntı için bir satıra çift tıklayın ya da Görüntüle düğmesine basın."
)


OLAY_ADLARI = {
    "PASSWORD_RESET": "Parola Sıfırlama",
    "PASSWORD_CHANGE": "Parola Değiştirme",
    "PASSWORD_CHANGE_FAILED": "Başarısız Parola Değiştirme",
    "LOGIN": "Giriş Başarılı",
    "LOGIN_FAILED": "Başarısız Giriş",
    "LOGOUT": "Çıkış",
    "VIEW": "Görüntüleme",
    "CREATE": "Oluşturma",
    "UPDATE": "Güncelleme",
    "CANCEL": "İptal",
    "DELETE": "Silme",
    "EXPORT": "Dışa Aktarım (Excel/PDF)",
    "ROLE_CHANGE": "Rol Değişikliği",
    "DEVICE_STATUS_CHANGE": "Cihaz Durum Değişikliği",
}

HEDEF_TABLO_ADLARI = {
    "kullanicilar": "Kullanıcı",
    "personel": "Personel",
    "ogrenciler": "Öğrenci",
    "roller": "Rol",
    "izinler": "İzin",
    "randevular": "Randevu",
    "odalar": "Oda",
    "cihazlar": "Cihaz",
    "cihaz_rezervasyonlari": "Cihaz Rezervasyonu",
    "cihaz_bakim": "Cihaz Bakımı",
    "cihaz_ariza": "Cihaz Arızası",
    "cihaz_kalibrasyon": "Cihaz Kalibrasyonu",
    "cihaz_bakimlari": "Cihaz Bakımı",
    "cihaz_arizalari": "Cihaz Arızası",
    "cihaz_kalibrasyonlari": "Cihaz Kalibrasyonu",
    "cihaz_bakim_planlari": "Cihaz Bakım Planı",
    "faaliyet_birimleri": "Faaliyet Birimi",
    "psikolog_odalar": "Psikolog Oda Yetkisi",
    "danisan_kodlari": "Danışan Kodu",
    "danisma_masasi_oturumlari": "Danışma Oturumu",
    "ogrenci_faaliyet_takip": "Öğrenci Faaliyeti",
    "projeler": "Proje",
    "deneyler": "Deney",
    "denetim_kayitlari": "Denetim Kayıtları",
    "oda_etkinlikleri": "Oda Etkinliği",
    "duyurular": "Duyuru",
    "faaliyetler": "Faaliyet Türü",
    "ogrenci_kayit_erteleme_gecmisi": "Öğrenci Kayıt Erteleme",
    "parola_sifirlama_talepleri": "Parola Sıfırlama Talebi",
}

# Excel aktarım kaydındaki "liste" değerlerinin okunur adları.
LISTE_ADLARI = {
    "CIHAZ": "Cihaz", "OGRENCI": "Öğrenci", "DANISAN": "Danışan", "REZERVASYON": "Cihaz Rezervasyonu", "BAKIM": "Bakım",
    "KALIBRASYON": "Kalibrasyon", "ARIZA": "Arıza", "BAKIM_PLANI": "Bakım Planı", "DENETIM": "Denetim Kayıtları",
}

OLAY_RENKLERI = {
    "PASSWORD_CHANGE": ("#17634F", "#E8F6EF"),
    "PASSWORD_CHANGE_FAILED": ("#9B3048", "#FCEBF0"),
    "LOGIN": ("#17634F", "#E8F6EF"),
    "LOGIN_FAILED": ("#9B3048", "#FCEBF0"),
    "LOGOUT": ("#4A5568", "#EEF1F5"),
    "VIEW": ("#285F88", "#E8F2FB"),
    "CREATE": ("#2457A2", "#E9F1FF"),
    "UPDATE": ("#96601B", "#FFF2DF"),
    "CANCEL": ("#9B3048", "#FCEBF0"),
    "DELETE": ("#8A1F2D", "#FBE3E6"),
    "EXPORT": ("#285F88", "#E8F2FB"),
    "ROLE_CHANGE": ("#62499E", "#F0EBFC"),
    "DEVICE_STATUS_CHANGE": ("#285F88", "#E8F2FB"),
}


AYRINTI_ETIKETLERI = {
    "onceki": "Önceki değer", "yeni": "Yeni değer", "neden": "Neden", "izin": "İzin", "rol": "Rol",
    "eklenen_roller": "Rolü eklenenler", "kaldirilan_roller": "Rolü kaldırılanlar", "verilen_roller": "Verilen roller",
    "gorunen_ad": "Görünen ad", "aktif_mi": "Aktif mi", "personel_kodu": "Personel kodu", "yas_grubu": "Yaş grubu",
    "danisan_kod_id": "Danışan kodu", "iptal_nedeni": "İptal nedeni", "etkilenen_danisan": "Etkilenen danışan",
    "pasife_alinan_danisan": "Pasife alınan danışan", "aktif_edilen_danisan": "Aktif edilen danışan",
    "girisi_engellenen_kullanici": "Girişi engellenen kullanıcı", "psikolog_kullanici_id": "Psikolog (kullanıcı no)",
    "izin_adi": "İzin adı", "rol_adi": "Rol adı", "kullanici_adi": "Kullanıcı adı",
    "faaliyet_adi": "Faaliyet adı", "puan": "Puan", "faaliyet_puani": "Faaliyet puanı", "kayit_puani": "Kayıt puanı",
    "gecmis_kayitlara_uygulandi": "Geçmiş kayıtlara uygulandı", "guncellenen_gecmis_kayit": "Güncellenen geçmiş kayıt",
    "etkilenen_kayit": "Etkilenen kayıt", "faaliyet_id": "Faaliyet türü no", "ogrenci_id": "Öğrenci no",
    "birim_id": "Birim no", "adet": "Miktar", "baslangic_zamani": "Başlangıç", "bitis_zamani": "Bitiş",
    "degisen_alanlar": "Değişen alanlar", "gun_sayisi": "Gün sayısı", "tur": "Tür", "onaylandi_mi": "Onaylandı mı",
    "oda_id": "Oda no", "organize_eden_personel_id": "Düzenleyen personel no", "katilimci_sayisi": "Katılımcı sayısı",
    "etkinlik_adi": "Etkinlik adı", "gunler": "Günler", "silinen_faaliyet_kaydi_sayisi": "Silinen faaliyet kaydı",
    "silinen_erteleme_kaydi_sayisi": "Silinen erteleme kaydı", "liste": "Liste", "satir_sayisi": "Satır sayısı",
    "ne": "Ne", "yeni_uyari_tarihi": "Yeni uyarı tarihi",
}


def alan_adi(anahtar):
    return AYRINTI_ETIKETLERI.get(anahtar) or str(anahtar).replace("_", " ").capitalize()


def biçimle(deger):
    if deger is None:
        return "—"
    if isinstance(deger, bool):
        return "Evet" if deger else "Hayır"
    if isinstance(deger, (list, tuple)):
        return ", ".join(biçimle(d) for d in deger) if deger else "—"
    if isinstance(deger, dict):                                         # önceki/yeni gibi iç içe değerler: "Alan: değer, Alan: değer"
        return ", ".join(f"{alan_adi(a)}: {biçimle(d)}" for a, d in deger.items()) if deger else "—"
    return str(deger)


def hedef_metni(kayit):
    """İşlemin hangi kayda yapıldığını okunur yazar: "Kullanıcı: ayse", "Randevu (no 12)" ya da "—"."""
    tablo = kayit.get("hedef_tablo")
    kayit_no = kayit.get("hedef_kayit_id")
    ad = HEDEF_TABLO_ADLARI.get(tablo, tablo)
    if not ad:
        return "—"
    if tablo == "kullanicilar" and kayit_no is not None:
        return f"{ad}: {kayit.get('hedef_kullanici_adi') or 'bulunamadı (kayıt silinmiş olabilir)'}"
    return f"{ad} (no {kayit_no})" if kayit_no is not None else ad


def olay_cumlesi(kayit):
    """Denetim kaydını tek cümleyle anlatır: kim, neyi, nasıl yaptı. Ayrıntı penceresinin başında gösterilir."""
    kim = kayit.get("kullanici_adi") or "Bilinmeyen kullanıcı"
    olay = kayit.get("olay_turu")
    ayrinti = kayit.get("ayrinti") if isinstance(kayit.get("ayrinti"), dict) else {}
    tablo = kayit.get("hedef_tablo")
    etiket = HEDEF_TABLO_ADLARI.get(tablo, tablo or "kayıt")
    hedef_kullanici = kayit.get("hedef_kullanici_adi")

    if olay == "LOGIN":
        return f"{kim} sisteme giriş yaptı."
    if olay == "LOGIN_FAILED":
        denenen = ayrinti.get("kullanici_adi") or kim
        return f"“{denenen}” adıyla başarısız bir giriş denemesi yapıldı."
    if olay == "LOGOUT":
        return f"{kim} oturumu kapattı."
    if olay == "PASSWORD_CHANGE":
        return f"{kim} parolasını değiştirdi."
    if olay == "PASSWORD_CHANGE_FAILED":
        return f"{kim} parolasını değiştirmeyi denedi; işlem başarısız oldu."
    if olay == "PASSWORD_RESET":
        return (f"{kim}, {hedef_kullanici} kullanıcısının parolasını sıfırladı." if hedef_kullanici
                else f"{kim} bir parola sıfırlama işlemi yaptı.")
    if olay == "VIEW":
        return (f"{kim} denetim kayıtlarını görüntüledi." if tablo == "denetim_kayitlari"
                else f"{kim}, “{etiket}” kaydını görüntüledi.")
    if olay == "CREATE":
        return f"{kim}, yeni bir “{etiket}” kaydı oluşturdu."
    if olay == "UPDATE":
        return f"{kim}, “{etiket}” kaydını güncelledi."
    if olay == "CANCEL":
        return f"{kim}, “{etiket}” kaydını iptal etti."
    if olay == "DELETE":
        return f"{kim}, “{etiket}” kaydını sildi."
    if olay == "EXPORT":
        liste = LISTE_ADLARI.get(ayrinti.get("liste"), ayrinti.get("liste"))
        pdf = ayrinti.get("bicim") == "PDF"
        if liste:
            return f"{kim}, “{liste}” listesini PDF olarak kaydetti." if pdf else f"{kim}, “{liste}” listesini Excel'e aktardı."
        return f"{kim} bir listeyi PDF olarak kaydetti." if pdf else f"{kim} bir listeyi Excel'e aktardı."
    if olay == "ROLE_CHANGE":
        return (f"{kim}, {hedef_kullanici} kullanıcısının rollerini değiştirdi." if hedef_kullanici
                else f"{kim} bir rol değişikliği yaptı.")
    if olay == "DEVICE_STATUS_CHANGE":
        return f"{kim} bir cihazın durumunu değiştirdi."
    return f"{kim}: {OLAY_ADLARI.get(olay, olay)}"


def ayrinti_satirlari(ayrinti):
    """Denetim kaydındaki ayrıntıyı (silinen veri, önceki/yeni değer) ekranda gösterilecek (başlık, değer) satırlarına çevirir."""
    if not isinstance(ayrinti, dict):
        return []

    satirlar = []
    for anahtar, deger in ayrinti.items():
        if anahtar == "liste" and isinstance(deger, str):
            satirlar.append((alan_adi(anahtar), LISTE_ADLARI.get(deger, deger)))
        elif anahtar == "degisen_alanlar" and isinstance(deger, (list, tuple)):
            satirlar.append((alan_adi(anahtar), biçimle([alan_adi(a) for a in deger])))
        elif anahtar == "silinen" and isinstance(deger, dict):
            satirlar.extend((alan_adi(a), biçimle(d)) for a, d in deger.items())
        elif anahtar == "maskelenen_alanlar":
            satirlar.append(("Kişisel veri olduğu için kaydedilmeyen alanlar", biçimle(deger)))
        else:
            satirlar.append((alan_adi(anahtar), biçimle(deger)))
    return satirlar


def kart_golgesi(widget):
    efekt = QGraphicsDropShadowEffect(widget)
    efekt.setBlurRadius(20)
    efekt.setOffset(0, 3)
    efekt.setColor(QColor(13, 37, 87, 18))
    widget.setGraphicsEffect(efekt)


class IslemEtiketiDelegate(DurumRozetiDelegate):
    """İşlem türünü, satır seçilse bile rengini koruyan rozet olarak çizer (rengi, görünen ada değil işlem koduna göre bulunur)."""

    def renk_bul(self, index, metin):
        return OLAY_RENKLERI.get(index.data(Qt.UserRole), VARSAYILAN_DURUM_RENGI)


class CokluIslemSecici(QPushButton):
    def __init__(self, parent=None):
        super().__init__("Tüm İşlemler", parent)

        self.kutular = {}

        self.setMinimumHeight(40)
        self.setStyleSheet("""
            QPushButton {
                background: white;
                color: #0F2552;
                border: 1px solid #C7D9FB;
                border-radius: 10px;
                text-align: left;
                padding: 8px 14px;
                font-size: 13px;
                font-weight: 700;
            }
            QPushButton:hover {
                background: #F7FAFF;
                border: 1px solid #93B4F5;
            }
        """)

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background: white;
                border: 1px solid #C7D9FB;
                border-radius: 10px;
                padding: 6px;
            }
        """)

        for kod, ad in OLAY_ADLARI.items():
            kutu = QCheckBox(ad)
            kutu.setMinimumHeight(32)

            kapsayici = QWidget(menu)
            duzen = QHBoxLayout(kapsayici)
            duzen.setContentsMargins(12, 2, 14, 2)
            duzen.addWidget(kutu)

            eylem = QWidgetAction(menu)
            eylem.setDefaultWidget(kapsayici)
            menu.addAction(eylem)

            self.kutular[kod] = kutu
            kutu.toggled.connect(self.yaziyi_guncelle)

        self.setMenu(menu)

    def secilenler(self):
        return [
            kod for kod, kutu in self.kutular.items()
            if kutu.isChecked()
        ]

    def yaziyi_guncelle(self, *_):
        secilen = self.secilenler()

        if not secilen:
            self.setText("Tüm İşlemler")
        elif len(secilen) == 1:
            self.setText(
                OLAY_ADLARI[secilen[0]]
            )
        else:
            self.setText(
                f"{len(secilen)} işlem seçildi"
            )

    def temizle(self):
        for kutu in self.kutular.values():
            kutu.setChecked(False)
        self.yaziyi_guncelle()


class AuditKayitlariEkrani(QWidget):
    def __init__(self, api_url, token, parent=None):
        super().__init__(parent)

        self.api_url = api_url.rstrip("/")
        self.token = token
        self.limit = 50
        self.offset = 0
        self.toplam = 0

        self.arayuzu_olustur()
        self.kayitlari_getir()

    def arayuzu_olustur(self):
        self.setStyleSheet(liste_sayfasi_stili())

        # Sayfa tek parça: yalnızca tablo kendi içinde kayar (önceden sayfa da ayrıca kayıyordu, iki kaydırma iç içe geçiyordu).
        ana = QVBoxLayout(self)
        ana.setContentsMargins(24, 20, 24, 18)
        ana.setSpacing(16)

        # Başlık ve ana işlem
        ust = QHBoxLayout()
        ust.setSpacing(16)
        basliklar = QVBoxLayout()
        basliklar.setSpacing(3)
        sayfa_baslik = QLabel("Denetim Kayıtları")
        sayfa_baslik.setObjectName("baslik")
        sayfa_alt = QLabel("Sistemde yapılan giriş, değişiklik ve silme işlemlerinin geçmişi.")
        sayfa_alt.setObjectName("altBaslik")
        baslik_satiri = QHBoxLayout()
        baslik_satiri.setSpacing(10)
        baslik_satiri.addWidget(sayfa_baslik)
        self.rozet = BilgiRozeti(ROZET_METNI, ROZET_ACIKLAMASI)
        baslik_satiri.addWidget(self.rozet, 0, Qt.AlignBottom)
        baslik_satiri.addStretch()
        basliklar.addLayout(baslik_satiri)
        basliklar.addWidget(sayfa_alt)
        ust.addLayout(basliklar, 1)

        self.excel_btn = QPushButton("⬇  Dışa Aktar")
        self.excel_btn.setObjectName("yesil")
        self.excel_btn.setMinimumHeight(40)
        self.excel_btn.setToolTip("Süzgece uyan kayıtları (silinen verinin içeriğiyle birlikte) Excel ya da PDF dosyasına yaz")
        self.excel_btn.clicked.connect(self.excel_aktar)
        ust.addWidget(self.excel_btn, 0, Qt.AlignTop)
        ana.addLayout(ust)

        # Süzgeçler
        filtre_karti = kart_olustur()
        filtre_duzen = QVBoxLayout(filtre_karti)
        filtre_duzen.setContentsMargins(16, 12, 16, 12)
        filtre_duzen.setSpacing(10)
        arama_satiri = QHBoxLayout()
        arama_satiri.setSpacing(10)
        filtre_duzen.addLayout(arama_satiri)

        self.kullanici_arama = QLineEdit()
        self.kullanici_arama.setPlaceholderText("Kullanıcı adı ara...")
        self.kullanici_arama.setClearButtonEnabled(True)
        self.kullanici_arama.setMinimumWidth(180)
        self.kullanici_arama.returnPressed.connect(self.filtrele)
        arama_satiri.addWidget(self.kullanici_arama, 3)

        self.olay_secimi = CokluIslemSecici()
        self.olay_secimi.setCursor(Qt.CursorShape.PointingHandCursor)
        self.olay_secimi.setMinimumWidth(170)
        arama_satiri.addWidget(self.olay_secimi, 2)

        donem_etiketi = QLabel("Dönem")
        donem_etiketi.setObjectName("etiket")
        arama_satiri.addWidget(donem_etiketi)
        self.donem_secimi = QComboBox()
        self.donem_secimi.addItems(["Tümü", "Bugün", "Son 7 Gün", "Son 30 Gün", "Tarih Aralığı"])
        self.donem_secimi.setCursor(Qt.CursorShape.PointingHandCursor)
        arama_satiri.addWidget(self.donem_secimi, 1)

        self.filtre_btn = QPushButton("Filtrele")
        self.filtre_btn.setObjectName("birincil")
        self.filtre_btn.clicked.connect(self.filtrele)
        self.temizle_btn = QPushButton("Temizle")
        self.temizle_btn.setObjectName("hayalet")
        self.temizle_btn.setToolTip("Arama ve süzgeçleri sıfırla")
        self.temizle_btn.clicked.connect(self.filtreleri_temizle)
        self.yenile_btn = QPushButton("⟳  Yenile")
        self.yenile_btn.setObjectName("hayalet")
        self.yenile_btn.setToolTip("Kayıtları sunucudan yeniden yükle")
        self.yenile_btn.clicked.connect(self.kayitlari_getir)
        for buton in (self.filtre_btn, self.temizle_btn, self.yenile_btn, self.excel_btn):
            buton.setCursor(Qt.CursorShape.PointingHandCursor)
            if buton is not self.excel_btn:
                arama_satiri.addWidget(buton)

        # Başlangıç/bitiş yalnızca "Tarih Aralığı" seçilince, kartın ikinci satırında görünür (üst satır sıkışmasın)
        self.tarih_alani = QWidget()
        tarih_satiri = QHBoxLayout(self.tarih_alani)
        tarih_satiri.setContentsMargins(0, 0, 0, 0)
        tarih_satiri.setSpacing(10)
        self.baslangic = QDateEdit()
        self.baslangic.setMinimumWidth(160)
        self.baslangic.setCalendarPopup(True)
        self.baslangic.setDisplayFormat("dd.MM.yyyy")
        self.baslangic.setDate(QDate.currentDate().addDays(-7))
        self.bitis = QDateEdit()
        self.bitis.setMinimumWidth(160)
        self.bitis.setCalendarPopup(True)
        self.bitis.setDisplayFormat("dd.MM.yyyy")
        self.bitis.setDate(QDate.currentDate())
        bas_etiketi = QLabel("Başlangıç")
        bas_etiketi.setObjectName("etiket")
        bit_etiketi = QLabel("Bitiş")
        bit_etiketi.setObjectName("etiket")
        tarih_satiri.addWidget(bas_etiketi)
        tarih_satiri.addWidget(self.baslangic)
        tarih_satiri.addSpacing(8)
        tarih_satiri.addWidget(bit_etiketi)
        tarih_satiri.addWidget(self.bitis)
        tarih_satiri.addStretch()
        self.tarih_alani.setVisible(False)
        filtre_duzen.addWidget(self.tarih_alani)
        self.donem_secimi.currentIndexChanged.connect(self._donem_degisti)
        ana.addWidget(filtre_karti)

        # Özet kartları
        kartlar = QGridLayout()
        kartlar.setSpacing(16)
        self.ozet_degerleri = {}
        ozetler = [
            ("toplam_kayit", "Toplam Kayıt", "#1D4ED8"),
            ("basarisiz_giris", "Başarısız Giriş", "#DC2626"),
            ("kullanici_islemleri", "Değişiklik İşlemleri", "#D97706"),
            ("bugunku_islemler", "Bugünkü Kayıtlar", "#0E9F6E"),
        ]
        for sutun, (anahtar, baslik, renk) in enumerate(ozetler):
            kart, deger = ozet_karti_olustur(baslik, renk)
            deger.setText("—")
            kartlar.addWidget(kart, 0, sutun)
            kartlar.setColumnStretch(sutun, 1)
            self.ozet_degerleri[anahtar] = deger
        ana.addLayout(kartlar)

        # Salt okunur kayıt tablosu
        # Sunucu sayfalıdır ve kayıtları zamana göre (en yeni önce) verir; başlıktan sıralama yalnızca ekrandaki sayfayı sıralayıp
        # yanıltacağı için bu tabloda yoktur.
        self.tablo = QTableWidget()
        self.tablo.setMinimumHeight(260)
        self.tablo.setColumnCount(5)
        self.tablo.setHorizontalHeaderLabels(["TARİH / SAAT", "İŞLEMİ YAPAN", "İŞLEM TÜRÜ", "İLGİLİ KAYIT TÜRÜ", "DETAY"])
        self.tablo.setStyleSheet(TABLO_STILI)
        self.tablo.setShowGrid(False)
        self.tablo.setFrameShape(QFrame.NoFrame)
        self.tablo.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tablo.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tablo.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tablo.setAlternatingRowColors(False)
        self.tablo.setFocusPolicy(Qt.NoFocus)
        self.tablo.setWordWrap(False)
        self.tablo.setMouseTracking(True)
        self.tablo.verticalHeader().setVisible(False)
        self.tablo.verticalHeader().setDefaultSectionSize(52)

        sutun_basliklari = self.tablo.horizontalHeader()
        sutun_basliklari.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        sutun_basliklari.setSectionResizeMode(0, QHeaderView.Fixed)
        sutun_basliklari.setSectionResizeMode(1, QHeaderView.Stretch)
        sutun_basliklari.setSectionResizeMode(2, QHeaderView.Stretch)
        sutun_basliklari.setSectionResizeMode(3, QHeaderView.Stretch)
        sutun_basliklari.setSectionResizeMode(4, QHeaderView.Fixed)
        self.tablo.setColumnWidth(0, 190)
        self.tablo.setColumnWidth(4, 130)
        self.tablo.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.tablo.horizontalHeaderItem(4).setTextAlignment(Qt.AlignCenter)      # düğmeyle aynı hizada
        self.tablo.setItemDelegateForColumn(2, IslemEtiketiDelegate(parent=self.tablo))
        self.tablo.itemDoubleClicked.connect(self.satir_cift_tiklandi)
        self._satir_kayitlari = []              # görünen her satırın (kayıt, tarih) bilgisi; "Görüntüle" düğmesi sırasını property olarak taşır

        tablo_kart = kart_olustur()
        tablo_duzen = QVBoxLayout(tablo_kart)
        tablo_duzen.setContentsMargins(20, 18, 20, 14)
        tablo_duzen.setSpacing(14)

        tablo_ust = QHBoxLayout()
        tablo_ust.setSpacing(10)
        tablo_baslik = QLabel("Denetim Geçmişi")
        tablo_baslik.setObjectName("kartBaslik")
        tablo_ust.addWidget(tablo_baslik)
        self.sayac_rozeti = QLabel("0 kayıt")
        self.sayac_rozeti.setObjectName("rozet")
        tablo_ust.addWidget(self.sayac_rozeti)
        tablo_ust.addStretch()
        tablo_aciklama = QLabel("İşlem geçmişi · ayrıntı için satıra çift tıklayın")
        tablo_aciklama.setObjectName("altBilgi")
        tablo_ust.addWidget(tablo_aciklama)
        tablo_duzen.addLayout(tablo_ust)
        tablo_duzen.addWidget(self.tablo, 1)

        # Sayfalama ve durum bilgisi (kartın altında)
        alt = QHBoxLayout()
        alt.setSpacing(10)
        self.durum = QLabel("Kayıtlar yükleniyor...")
        self.durum.setObjectName("altBilgi")
        self.durum.setTextFormat(Qt.PlainText)
        alt.addWidget(self.durum, 1)
        self.onceki_btn = QPushButton("←  Önceki")
        self.onceki_btn.setObjectName("hayalet")
        self.onceki_btn.clicked.connect(self.onceki_sayfa)
        self.sonraki_btn = QPushButton("Sonraki  →")
        self.sonraki_btn.setObjectName("hayalet")
        self.sonraki_btn.clicked.connect(self.sonraki_sayfa)
        for buton in (self.onceki_btn, self.sonraki_btn):
            buton.setCursor(Qt.CursorShape.PointingHandCursor)
            buton.setMinimumWidth(110)
            alt.addWidget(buton)
        tablo_duzen.addLayout(alt)
        ana.addWidget(tablo_kart, 1)

        self.sayfalama_guncelle()

    def _audit_detayini_goster(self, kayit, tarih):
        pencere = QDialog(self)
        pencere.setWindowTitle("Denetim Kaydı Detayları")
        pencere.setObjectName("auditDetayPenceresi")
        pencere.setStyleSheet(dialog_stili())
        pencere.setMinimumWidth(580)

        duzen = QVBoxLayout(pencere)
        duzen.setContentsMargins(24, 22, 24, 20)
        duzen.setSpacing(14)

        baslik = QLabel("Denetim Kaydı Detayları")
        baslik.setObjectName("formBaslik")
        duzen.addWidget(baslik)

        # Özet kartı: ne olduğunu tek cümleyle anlatır (renkli işlem rozeti + kim, neyi yaptı; tarih aşağıdaki satırlardadır).
        olay = kayit.get("olay_turu")
        renk, zemin = OLAY_RENKLERI.get(olay, VARSAYILAN_DURUM_RENGI)
        ozet = QFrame()
        ozet.setObjectName("oturumSatiri")
        ozet_duzen = QVBoxLayout(ozet)
        ozet_duzen.setContentsMargins(18, 14, 18, 14)
        ozet_duzen.setSpacing(8)
        rozet = QLabel(OLAY_ADLARI.get(olay, olay or "İşlem"))
        rozet.setObjectName("islemRozeti")
        rozet.setStyleSheet(
            f"QLabel#islemRozeti {{ color: {renk}; background: {zemin}; border-radius: 10px; padding: 3px 12px;"
            " font-size: 12px; font-weight: 800; }"
        )
        rozet.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        ozet_duzen.addWidget(rozet)
        cumle = QLabel(olay_cumlesi(kayit))
        cumle.setObjectName("olayCumlesi")
        cumle.setTextFormat(Qt.PlainText)
        cumle.setWordWrap(True)
        cumle.setStyleSheet("QLabel#olayCumlesi { font-size: 15px; font-weight: 700; color: #0F2552; }")
        ozet_duzen.addWidget(cumle)
        duzen.addWidget(ozet)

        kullanici_no = kayit.get("kullanici_id")
        yapan = kayit.get("kullanici_adi") or "Bilinmeyen kullanıcı"
        bilgiler = [
            ("Tarih / Saat", tarih),
            ("İşlemi Yapan", f"{yapan} (kullanıcı no {kullanici_no})" if kullanici_no is not None else yapan),
            ("İşlem Türü", OLAY_ADLARI.get(olay, olay)),
            ("İşlem Yapılan", hedef_metni(kayit)),
            ("İstemci Adresi", kayit.get("istemci_adresi")),
            ("Kayıt No", kayit.get("denetim_id")),
        ]
        duzen.addLayout(self._alan_izgarasi(bilgiler, 12))

        ayrinti = kayit.get("ayrinti")
        onceki_yeni = (
            isinstance(ayrinti, dict) and isinstance(ayrinti.get("onceki"), dict) and isinstance(ayrinti.get("yeni"), dict)
        )
        kalan = ayrinti_satirlari(
            {k: v for k, v in ayrinti.items() if k not in ("onceki", "yeni")} if onceki_yeni else ayrinti
        )
        if onceki_yeni or kalan:
            alt_baslik = QLabel(
                {"DELETE": "Silinen Veri", "EXPORT": "Aktarım Ayrıntısı"}.get(olay, "Değişiklik Ayrıntısı")
            )
            alt_baslik.setObjectName("formBaslik")
            duzen.addWidget(alt_baslik)
            if onceki_yeni:
                duzen.addWidget(self._degisiklik_tablosu(ayrinti["onceki"], ayrinti["yeni"]))
            if kalan:
                duzen.addLayout(self._alan_izgarasi(kalan, 8))

        kapat = QPushButton("Kapat")
        kapat.setObjectName("birincil")
        kapat.setCursor(Qt.PointingHandCursor)
        kapat.setMinimumWidth(110)
        kapat.clicked.connect(pencere.accept)

        duzen.addWidget(kapat, alignment=Qt.AlignRight)
        pencere.exec()
        pencere.deleteLater()

    @staticmethod
    def _alan_izgarasi(satirlar, dikey_bosluk):
        """(alan adı, değer) çiftlerini iki sütunlu, üstten hizalı ve seçilip kopyalanabilir bir ızgaraya dizer."""
        izgara = QGridLayout()
        izgara.setHorizontalSpacing(20)
        izgara.setVerticalSpacing(dikey_bosluk)
        for sira, (alan, deger) in enumerate(satirlar):
            ad = QLabel(alan)
            ad.setObjectName("alanAdi")
            ad.setAlignment(Qt.AlignTop | Qt.AlignLeft)
            ad.setWordWrap(True)
            deger_yazisi = QLabel("—" if deger is None or deger == "" else str(deger))
            deger_yazisi.setAlignment(Qt.AlignTop | Qt.AlignLeft)
            deger_yazisi.setTextFormat(Qt.PlainText)
            deger_yazisi.setWordWrap(True)
            deger_yazisi.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            izgara.addWidget(ad, sira, 0)
            izgara.addWidget(deger_yazisi, sira, 1)
        izgara.setColumnStretch(1, 1)
        izgara.setColumnMinimumWidth(0, 150)
        return izgara

    @staticmethod
    def _degisiklik_tablosu(onceki, yeni):
        """Değişen alanlar için Alan / Önceki / Yeni karşılaştırma tablosu; değişen yeni değer vurgulanır."""
        kart = QFrame()
        kart.setObjectName("oturumSatiri")
        izgara = QGridLayout(kart)
        izgara.setContentsMargins(16, 12, 16, 12)
        izgara.setHorizontalSpacing(18)
        izgara.setVerticalSpacing(8)
        for sutun, metin in enumerate(("ALAN", "ÖNCEKİ", "YENİ")):
            etiket = QLabel(metin)
            etiket.setObjectName("ipucu")
            etiket.setStyleSheet("font-size: 11px; font-weight: 800; color: #6B7FA8;")
            izgara.addWidget(etiket, 0, sutun)
        anahtarlar = list(onceki) + [a for a in yeni if a not in onceki]
        for sira, anahtar in enumerate(anahtarlar, start=1):
            eski_deger, yeni_deger = biçimle(onceki.get(anahtar)), biçimle(yeni.get(anahtar))
            degisti = eski_deger != yeni_deger
            for sutun, (metin, adi) in enumerate(((alan_adi(anahtar), "alanAdi"), (eski_deger, ""), (yeni_deger, ""))):
                etiket = QLabel(metin)
                if adi:
                    etiket.setObjectName(adi)
                etiket.setTextFormat(Qt.PlainText)
                etiket.setWordWrap(True)
                etiket.setAlignment(Qt.AlignTop | Qt.AlignLeft)
                etiket.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                if sutun == 2 and degisti:
                    etiket.setStyleSheet("font-weight: 800; color: #1D4ED8;")
                izgara.addWidget(etiket, sira, sutun)
        izgara.setColumnMinimumWidth(0, 130)
        izgara.setColumnStretch(1, 1)
        izgara.setColumnStretch(2, 1)
        return kart

    def detay_dugmesine_basildi(self, *_):
        """"Görüntüle" düğmesi: hangi satırın olduğu düğmenin özelliğinden bulunur (düğmeyi lambda ile bağlamak pencereyi çöp
        toplayıcının göremediği bir döngüde tutar ve süreç kapanırken Qt'yi çökertir)."""
        dugme = self.sender()
        sira = dugme.property("kayit_sirasi") if dugme is not None else None
        if sira is not None:
            self._ayrintiyi_ac(int(sira))

    def satir_cift_tiklandi(self, oge=None, *_):
        if oge is not None:
            self._ayrintiyi_ac(oge.row())

    def _ayrintiyi_ac(self, sira):
        if 0 <= sira < len(self._satir_kayitlari):
            kayit, tarih = self._satir_kayitlari[sira]
            self._audit_detayini_goster(kayit, tarih)

    def _donem_degisti(self, *_):
        secim = self.donem_secimi.currentText()
        bugun = QDate.currentDate()

        if secim == "Bugün":
            self.baslangic.setDate(bugun)
            self.bitis.setDate(bugun)

        elif secim == "Son 7 Gün":
            self.baslangic.setDate(bugun.addDays(-6))
            self.bitis.setDate(bugun)

        elif secim == "Son 30 Gün":
            self.baslangic.setDate(bugun.addDays(-29))
            self.bitis.setDate(bugun)

        self.tarih_alani.setVisible(secim == "Tarih Aralığı")

    def filtrele(self):
        self.offset = 0
        self.kayitlari_getir()

    def filtreleri_temizle(self):
        self.kullanici_arama.clear()
        self.olay_secimi.temizle()
        self.donem_secimi.setCurrentIndex(0)
        self.baslangic.setDate(QDate.currentDate().addDays(-7))
        self.bitis.setDate(QDate.currentDate())
        self.offset = 0
        self.kayitlari_getir()

    def onceki_sayfa(self):
        if self.offset >= self.limit:
            self.offset -= self.limit
            self.kayitlari_getir()

    def sonraki_sayfa(self):
        if self.offset + self.limit < self.toplam:
            self.offset += self.limit
            self.kayitlari_getir()

    def sayfalama_guncelle(self):
        self.onceki_btn.setEnabled(self.offset > 0)
        self.sonraki_btn.setEnabled(
            self.offset + self.limit < self.toplam
        )

    def _suzgec_parametreleri(self):
        """Ekrandaki süzgeçlerden API parametreleri (sayfalama olmadan); tarih aralığı geçersizse ValueError."""
        self._donem_degisti()
        parametreler = {}
        kullanici = self.kullanici_arama.text().strip()
        if kullanici:
            parametreler["kullanici"] = kullanici
        olay = self.olay_secimi.secilenler()
        if olay:
            parametreler["olay_turu"] = olay
        if self.donem_secimi.currentIndex() != 0:
            if self.baslangic.date() > self.bitis.date():
                raise ValueError("Başlangıç tarihi bitiş tarihinden sonra olamaz.")
            parametreler["baslangic_tarihi"] = self.baslangic.date().toString("yyyy-MM-dd")
            parametreler["bitis_tarihi"] = self.bitis.date().toString("yyyy-MM-dd")
        return parametreler

    def _excel_icin_kayitlari_getir(self, parametreler, en_fazla):
        """Süzgece uyan kayıtları 200'lük sayfalarla toplar; (kayıtlar, özet, kesildi) döner."""
        kayitlar, ozet, offset = [], {}, 0
        while len(kayitlar) < en_fazla:
            yanit = oturum_kontrollu_istek(
                "GET", f"{self.api_url}/api/audit-kayitlari", headers={"Authorization": f"Bearer {self.token}"},
                params={**parametreler, "limit": 200, "offset": offset, **({"ozet": "false"} if offset else {})}, timeout=30,
            )
            if oturum_hatasi_mi(yanit):
                return None
            yanit.raise_for_status()
            veri = yanit.json()
            ozet = veri.get("ozet") or ozet
            sayfa = veri.get("kayitlar", [])
            kayitlar.extend(sayfa)
            offset += 200
            if len(sayfa) < 200 or offset >= int(ozet.get("toplam_kayit", 0)):
                break
        kesildi = int(ozet.get("toplam_kayit", 0)) > en_fazla
        return kayitlar[:en_fazla], ozet, kesildi

    def excel_aktar(self):
        """Süzgece uyan denetim kayıtlarını (silinen verinin içeriğiyle birlikte) Excel dosyasına yazar."""
        from client.audit_excel import EN_FAZLA_KAYIT, audit_excel_olustur      # audit_excel bu modülden içe aktarır; döngüyü önlemek için burada

        try:
            parametreler = self._suzgec_parametreleri()
        except ValueError as hata:
            QMessageBox.warning(self, "Geçersiz Tarih", str(hata))
            return
        dosya_yolu, bicim = kayit_yolu_sec(self, "Raporu Kaydet", f"denetim_kayitlari_{datetime.now().strftime('%Y%m%d_%H%M')}")
        if not dosya_yolu:
            return

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            sonuc = self._excel_icin_kayitlari_getir(parametreler, EN_FAZLA_KAYIT)
        except (requests.RequestException, ValueError) as hata:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, "Rapor Hatası", f"Denetim kayıtları alınamadı:\n{istek_hatasi_metni(hata)}")
            return
        QApplication.restoreOverrideCursor()
        if sonuc is None:
            return
        kayitlar, ozet, kesildi = sonuc

        gun = lambda metin: QDate.fromString(metin, "yyyy-MM-dd").toString("dd.MM.yyyy")
        donem = (f"{gun(parametreler['baslangic_tarihi'])} - {gun(parametreler['bitis_tarihi'])}"
                 if "baslangic_tarihi" in parametreler else "Tümü")
        filtre = [
            ("Dönem", donem),
            ("Kullanıcı", parametreler.get("kullanici", "Tümü")),
            ("İşlem türü", ", ".join(OLAY_ADLARI.get(o, o) for o in parametreler.get("olay_turu", [])) or "Tümü"),
        ]
        try:
            with cikti_dosyasi(dosya_yolu, bicim) as xlsx_yolu:
                audit_excel_olustur(xlsx_yolu, kayitlar, ozet, filtre, kesildi)
        except (OSError, RuntimeError) as hata:
            QMessageBox.warning(self, "Kaydedilemedi", f"Dosya kaydedilemedi. Aynı adlı dosya başka bir programda (Excel, PDF okuyucu) açık olabilir ya da klasöre yazma izniniz olmayabilir.\n{hata}")
            return
        # Denetim kayıtları en hassas listedir (silinen veri ayrıntıları, istemci adresleri): kimin aldığı da denetime yazılır.
        aktarimi_denetime_yaz(self, {"api_url": self.api_url, "token": self.token, "liste": "DENETIM", "bicim": bicim}, len(kayitlar))
        uyari = f"\n\nNot: Dosya en yeni {EN_FAZLA_KAYIT} kayıtla sınırlandırıldı; süzgeçle daraltabilirsiniz." if kesildi else ""
        QMessageBox.information(self, "Dışa Aktar", f"{len(kayitlar)} kayıt {bicim_adi(bicim)} olarak kaydedildi:\n{dosya_yolu}{uyari}")

    def kayitlari_getir(self):
        try:
            parametreler = self._suzgec_parametreleri()
        except ValueError as hata:
            self.durum.setText(str(hata))
            return

        parametreler["limit"] = self.limit
        parametreler["offset"] = self.offset
        if self.offset > 0:
            parametreler["ozet"] = "false"      # kayıt sayımı yalnızca ilk sayfada yapılır; sonraki sayfalarda sunucu yeniden saymaz

        try:
            yanit = oturum_kontrollu_istek(
                "GET",
                f"{self.api_url}/api/audit-kayitlari",
                headers={
                    "Authorization": f"Bearer {self.token}"
                },
                params=parametreler,
                timeout=15
            )
            if oturum_hatasi_mi(yanit):
                return
            yanit.raise_for_status()
            veri = yanit.json()

        except requests.RequestException as hata:
            self.tablo.setRowCount(0)
            self._satir_kayitlari = []
            self.toplam = 0
            self.sayac_rozeti.setText("0 kayıt")
            self.sayfalama_guncelle()
            self.durum.setText(
                f"Denetim kayıtları yüklenemedi: {istek_hatasi_metni(hata)}"
            )
            return

        ozet = veri.get("ozet")
        if ozet:                                # ilk sayfa: kartlar ve toplam yenilenir; sonraki sayfalarda ilk sayfanınki korunur
            for anahtar, etiket in self.ozet_degerleri.items():
                etiket.setText(str(ozet.get(anahtar, 0)))
            self.toplam = int(ozet.get("toplam_kayit", 0))

        kayitlar = veri.get("kayitlar", [])

        self.tablo.setRowCount(len(kayitlar))
        self._satir_kayitlari = []

        for satir_no, kayit in enumerate(kayitlar):
            tarih = (kayit.get("olusturulma_tarihi") or "")
            if tarih:
                try:
                    tarih = datetime.fromisoformat(tarih).strftime(
                        "%d.%m.%Y %H:%M:%S"
                    )
                except ValueError:
                    tarih = tarih.replace("T", " ")[:19]

            hedef = kayit.get("hedef_tablo")

            alanlar = [
                tarih,
                kayit.get("kullanici_adi"),
                OLAY_ADLARI.get(
                    kayit.get("olay_turu"),
                    kayit.get("olay_turu")
                ),
                HEDEF_TABLO_ADLARI.get(hedef, hedef),
            ]

            for sutun_no, deger in enumerate(alanlar):
                metin = "—" if deger is None else str(deger)
                hucre = QTableWidgetItem(metin)

                if sutun_no == 2:
                    hucre.setData(
                        Qt.UserRole, kayit.get("olay_turu")
                    )

                hucre.setForeground(QColor("#0F2552" if sutun_no in (0, 1) else "#3B4C6B"))
                if sutun_no == 0:
                    yazi_tipi = hucre.font()
                    yazi_tipi.setBold(True)
                    hucre.setFont(yazi_tipi)                   # tarih satırın ana bilgisi
                hucre.setToolTip(metin)
                self.tablo.setItem(satir_no, sutun_no, hucre)

            self._satir_kayitlari.append((dict(kayit), tarih))

            hucre_alani = QWidget()
            hucre_duzen = QHBoxLayout(hucre_alani)
            hucre_duzen.setContentsMargins(4, 0, 4, 0)

            detay_btn = QPushButton("Görüntüle")
            detay_btn.setObjectName("kucuk")
            detay_btn.setFixedSize(92, 32)
            detay_btn.setCursor(Qt.PointingHandCursor)
            detay_btn.setProperty("kayit_sirasi", satir_no)
            detay_btn.clicked.connect(self.detay_dugmesine_basildi)

            hucre_duzen.addStretch()
            hucre_duzen.addWidget(detay_btn)
            hucre_duzen.addStretch()

            self.tablo.setCellWidget(
                satir_no, 4, hucre_alani
            )

        self.sayac_rozeti.setText(f"{self.toplam} kayıt")
        ilk = self.offset + 1 if kayitlar else 0
        son = self.offset + len(kayitlar)

        self.durum.setText(
            f"{self.toplam} kayıttan {ilk}-{son} arası gösteriliyor."
        )

        self.sayfalama_guncelle()
