"""TKYS - Danışma Masası Yönetimi (Memur / Admin)."""

from datetime import datetime

import requests
from client.api_yoneticisi import (
    hata_detayi_metni,
    oturum_kontrollu_istek,
    oturum_hatasi_mi,
    istek_hatasi_metni,
)

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QHeaderView,
)
from client.tablo_siralama import siralama_durumunu_al, siralamayi_geri_yukle, siralanabilir_yap
from client.tablo_tasarimi import bos_mesaj_olustur
from client.bildirim_toast import basari_bildirimi

# Sunucudaki sınırla aynı: bir görev en fazla mesai süresi (08:00-18:00) kadar olabilir.
GOREV_EN_UZUN_SAAT = 10
GOREV_COK_UZUN_MESAJI = (
    f"Bir görev en fazla {GOREV_EN_UZUN_SAAT} saat olabilir. "
    "Daha uzun çalışmayı ayrı görevler olarak girin."
)
UZUN_GOREV_IPUCU = (
    f"Görev {GOREV_EN_UZUN_SAAT} saatten uzun: öğrenci görevi bitirmeyi unutmuş olabilir. "
    "Onaylamadan önce saatleri kontrol edin, gerekirse Düzenle ile düzeltin."
)


def gorev_uzun_mu(oturum):
    """Görev mesai süresini aşıyor mu? Sunucu "uzun_gorev" gönderiyorsa o, göndermiyorsa (eski sunucu) süreden hesaplanır."""
    if not isinstance(oturum, dict):
        return False
    if "uzun_gorev" in oturum:
        return bool(oturum.get("uzun_gorev"))
    saniye = oturum.get("toplam_saniye")
    return saniye is not None and int(saniye) > GOREV_EN_UZUN_SAAT * 3600


def gorev_suresi_cok_uzun_mu(baslangic, bitis):
    return (bitis - baslangic).total_seconds() > GOREV_EN_UZUN_SAAT * 3600



def _gorev_formunu_stille(pencere, form, baslik, aciklama):
    from PySide6.QtWidgets import QFormLayout

    pencere.setObjectName("danismaGorevDialog")
    pencere.setMinimumWidth(570)

    pencere.setStyleSheet("""
        QDialog#danismaGorevDialog {
            background-color: #FFFFFF;
        }

        QDialog#danismaGorevDialog QLabel {
            color: #16294B;
            background: transparent;
            font-size: 13px;
        }

        QLabel#gorevDialogBaslik {
            color: #082B66;
            font-size: 20px;
            font-weight: 800;
        }

        QLabel#gorevDialogAciklama {
            color: #7184A2;
            font-size: 12px;
            padding-bottom: 8px;
        }

        QLabel#gorevOgrenci {
            background-color: #F1F6FF;
            color: #173B70;
            border: 1px solid #D7E5FA;
            border-radius: 8px;
            padding: 11px 12px;
            font-weight: 700;
        }

        QDialog#danismaGorevDialog QComboBox,
        QDialog#danismaGorevDialog QDateTimeEdit {
            background-color: #FFFFFF;
            color: #16294B;
            border: 1px solid #CCD9ED;
            border-radius: 8px;
            padding: 7px 12px;
            min-height: 28px;
            font-size: 13px;
        }

        QDialog#danismaGorevDialog QComboBox:focus,
        QDialog#danismaGorevDialog QDateTimeEdit:focus {
            border: 1px solid #1769EF;
            background-color: #F8FBFF;
        }

        QPushButton#danismaKaydet {
            background-color: #0966EF;
            color: white;
            border: none;
            border-radius: 8px;
            padding: 9px 20px;
            font-weight: 700;
        }

        QPushButton#danismaKaydet:hover {
            background-color: #0754C7;
        }

        QPushButton#danismaIptal {
            background-color: #EDF3FC;
            color: #234B80;
            border: 1px solid #D7E3F4;
            border-radius: 8px;
            padding: 9px 20px;
            font-weight: 700;
        }

        QPushButton#danismaIptal:hover {
            background-color: #DFEAF9;
        }
    """)

    form.setContentsMargins(28, 26, 28, 26)
    form.setHorizontalSpacing(18)
    form.setVerticalSpacing(15)
    form.setFieldGrowthPolicy(
        QFormLayout.AllNonFixedFieldsGrow
    )
    form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)

    ust_baslik = QLabel(baslik)
    ust_baslik.setObjectName("gorevDialogBaslik")
    form.addRow(ust_baslik)

    alt_yazi = QLabel(aciklama)
    alt_yazi.setObjectName("gorevDialogAciklama")
    alt_yazi.setWordWrap(True)
    form.addRow(alt_yazi)


class DanismaMasasiYonetimi(QWidget):
    NAVY = "#16294B"
    BLUE = "#285CE6"
    MUTED = "#697993"

    def __init__(self, api_url, token, parent=None):
        super().__init__(parent)

        self.api_url = api_url.rstrip("/")
        self.token = token
        self._arayuz_kur()
        self.yenile()

        self.yenile_timer = QTimer(self)
        self.yenile_timer.setInterval(30000)
        self.yenile_timer.timeout.connect(self._otomatik_yenile)
        self.yenile_timer.start()

    def _arayuz_kur(self):
        self.setStyleSheet("""
            QWidget#danismaYonetim {
                background: #F5F7FB;
            }
            QFrame#yonetimKart {
                background: white;
                border: 1px solid #E7ECF4;
                border-radius: 14px;
            }
            QPushButton {
                background: #285CE6;
                color: white;
                padding: 10px 18px;
                border-radius: 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #1E4BC5;
            }
            QPushButton:disabled {
                background: #DCE2EB;
                color: #8491A5;
            }
            QTableWidget {
                background: white;
                border: 1px solid #E7ECF4;
                gridline-color: #E7ECF4;
            }
        """)

        self.setObjectName("danismaYonetim")

        ana = QVBoxLayout(self)
        ana.setContentsMargins(20, 20, 20, 20)
        ana.setSpacing(16)

        # Görev özet kartları
        ozet_satiri = QHBoxLayout()
        ozet_satiri.setSpacing(12)

        self.ozet_kartlari = {}

        for anahtar, baslik, renk in [
            ("toplam", "Toplam Görev", "#16294B"),
            ("aktif", "Devam Eden Görevler", "#285CE6"),
            ("bekleyen", "Onay Bekleyen", "#B86B08"),
            ("onaylanan", "Onaylanan", "#16803C"),
        ]:
            kart = QFrame()
            kart.setStyleSheet("""
                QFrame {
                    background-color: #FFFFFF;
                    border: 1px solid #E3EAF5;
                    border-radius: 10px;
                }
                QLabel {
                    border: none;
                    background: transparent;
                }
            """)

            kart_icerik = QVBoxLayout(kart)
            kart_icerik.setContentsMargins(16, 12, 16, 12)
            kart_icerik.setSpacing(5)

            baslik_etiketi = QLabel(baslik)
            baslik_etiketi.setStyleSheet(
                "font-size: 12px; color: #697993;"
            )

            sayi_etiketi = QLabel("0")
            sayi_etiketi.setStyleSheet(
                f"font-size: 25px; font-weight: bold; color: {renk};"
            )

            kart_icerik.addWidget(baslik_etiketi)
            kart_icerik.addWidget(sayi_etiketi)

            self.ozet_kartlari[anahtar] = sayi_etiketi
            ozet_satiri.addWidget(kart, 1)

        ana.addLayout(ozet_satiri)

        ust = QHBoxLayout()

        # Liste kısaltıldığında nedenini söyler; aksi halde gizlidir (sayılar zaten kartlarda).
        self.ozet = QLabel("")
        self.ozet.setStyleSheet(f"font-size: 12px; color: {self.MUTED};")
        self.ozet.hide()
        ust.addWidget(self.ozet)
        ust.addStretch()

        self.ekle_btn = QPushButton("+ Yeni Görev Ekle")
        self.ekle_btn.clicked.connect(self.yeni_gorev_penceresi)
        ust.addWidget(self.ekle_btn)

        yenile_btn = QPushButton("↻ Yenile")
        yenile_btn.clicked.connect(self.yenile)
        ust.addWidget(yenile_btn)

        ana.addLayout(ust)

        kart = QFrame()
        kart.setObjectName("yonetimKart")
        kart_layout = QVBoxLayout(kart)
        kart_layout.setContentsMargins(14, 14, 14, 14)

        self.tablo = QTableWidget()
        siralanabilir_yap(self.tablo)
        self.tablo.setAlternatingRowColors(False)
        self.tablo.setStyleSheet("""
            QTableWidget {
                background-color: #FFFFFF;
                alternate-background-color: #FFFFFF;
                color: #243653;
                gridline-color: #E3EAF5;
                selection-background-color: #DCEAFF;
                selection-color: #16294B;
            }
            QHeaderView::section {
                background-color: #E8F0FF;
                color: #16294B;
                font-weight: bold;
                padding: 9px 5px;
                border: none;
                border-right: 1px solid #D6E2F3;
                border-bottom: 1px solid #D6E2F3;
            }
        """)
        self.tablo.verticalHeader().setDefaultSectionSize(39)
        self.tablo.setColumnCount(7)
        self.tablo.setHorizontalHeaderLabels([
            "Öğrenci",
            "Öğrenci No",
            "Başlangıç",
            "Bitiş",
            "Çalışma Süresi",
            "Görev Durumu",
            "Onay Durumu",
        ])

        self.tablo.setSelectionBehavior(
            QAbstractItemView.SelectRows
        )
        self.tablo.setSelectionMode(
            QAbstractItemView.SingleSelection
        )
        self.tablo.setEditTriggers(
            QAbstractItemView.NoEditTriggers
        )
        self.tablo.verticalHeader().hide()
        # Öğrenci adı kalan genişliği alır (dar pencerede iki satıra bölünmesin); diğer sütunlar içeriğine göre boyutlanır.
        baslik = self.tablo.horizontalHeader()
        baslik.setSectionResizeMode(QHeaderView.ResizeToContents)
        baslik.setSectionResizeMode(0, QHeaderView.Stretch)
        baslik.setMinimumSectionSize(110)

        kart_layout.addWidget(self.tablo)
        self.bos_mesaj = bos_mesaj_olustur("Henüz görev kaydı yok.")
        kart_layout.addWidget(self.bos_mesaj)
        ana.addWidget(kart, 1)

        alt = QHBoxLayout()
        alt.addStretch()

        self.duzenle_btn = QPushButton("✎ Seçilen Görevi Düzenle")
        self.duzenle_btn.clicked.connect(self.gorev_duzenle)
        self.duzenle_btn.setEnabled(False)
        alt.addWidget(self.duzenle_btn)

        self.geri_al_btn = QPushButton("↶ Onayı Geri Al")
        self.geri_al_btn.setToolTip("Onaylanmış görevi yeniden onay bekleyen duruma döndürür; görev düzenlenebilir olur.")
        self.geri_al_btn.setStyleSheet(
            "QPushButton { background: #B86B08; } QPushButton:hover { background: #945606; } "
            "QPushButton:disabled { background: #DCE2EB; color: #8491A5; }"
        )
        self.geri_al_btn.clicked.connect(self.onayi_geri_al)
        self.geri_al_btn.setEnabled(False)
        alt.addWidget(self.geri_al_btn)

        self.onay_btn = QPushButton("✓ Seçilen Görevi Onayla")
        self.onay_btn.clicked.connect(self.gorev_onayla)
        self.onay_btn.setEnabled(False)
        alt.addWidget(self.onay_btn)

        ana.addLayout(alt)

        self.tablo.itemSelectionChanged.connect(
            self._secim_degisti
        )

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.token}"
        }

    @staticmethod
    def _tarih_bicimlendir(deger):
        if not deger:
            return "—"
        try:
            return datetime.fromisoformat(deger).strftime(
                "%d.%m.%Y %H:%M:%S"
            )
        except (ValueError, TypeError):
            return str(deger)

    def _otomatik_yenile(self):
        if not self.isVisible():
            return

        if QApplication.activeModalWidget() is not None:
            return

        self.yenile(sessiz=True)

    def yenile(self, sessiz=False):
        secili_id = None
        satir = self.tablo.currentRow()

        if satir >= 0:
            hucre = self.tablo.item(satir, 0)
            if hucre is not None:
                kayit = hucre.data(Qt.UserRole)
                if isinstance(kayit, dict):
                    secili_id = kayit.get("oturum_id")

        # Kullanıcının seçtiği sıralama, otomatik yenilemede sunucu sırasına dönmesin.
        siralama = siralama_durumunu_al(self.tablo)

        try:
            yanit = oturum_kontrollu_istek("GET",
                f"{self.api_url}/api/danisma/yonetim/oturumlar",
                headers=self._headers(),
                timeout=10
            )
            yanit.raise_for_status()
            veri = yanit.json()

            oturumlar = veri.get("oturumlar", [])
            self.tablo.setRowCount(0)

            # Kart sayıları sunucunun tüm kayıtlardan hesapladığı özetten gelir (liste kısaltılmış olabilir).
            ozet = veri.get("ozet")
            if not isinstance(ozet, dict):
                ozet = {
                    "toplam": len(oturumlar),
                    "aktif": sum(1 for x in oturumlar if x.get("bitis_zamani") is None),
                    "bekleyen": sum(
                        1 for x in oturumlar
                        if x.get("bitis_zamani") is not None and not x.get("onaylandi_mi")
                    ),
                    "onaylanan": sum(1 for x in oturumlar if x.get("onaylandi_mi")),
                }

            for anahtar in ("toplam", "aktif", "bekleyen", "onaylanan"):
                self.ozet_kartlari[anahtar].setText(str(ozet.get(anahtar, 0)))

            self.tablo.setRowCount(len(oturumlar))

            for satir, oturum in enumerate(oturumlar):
                uzun = gorev_uzun_mu(oturum)
                degerler = [
                    oturum.get("ad_soyad", ""),
                    oturum.get("ogrenci_numarasi", ""),
                    self._tarih_bicimlendir(
                        oturum.get("baslangic_zamani")
                    ),
                    self._tarih_bicimlendir(
                        oturum.get("bitis_zamani")
                    ),
                    "",
                    oturum.get("durum", ""),
                    (
                        "Onaylandı"
                        if oturum.get("onaylandi_mi")
                        else "Onay Bekliyor"
                    ),
                ]

                for sutun, deger in enumerate(degerler):
                    if sutun == 4:
                        saniye = oturum.get("toplam_saniye")
                        if saniye is not None:
                            toplam_dakika = max(0, int(saniye)) // 60
                            deger = (
                                f"{toplam_dakika // 60} sa "
                                f"{toplam_dakika % 60:02d} dk"
                            )
                        if uzun:
                            deger = f"⚠ {deger}"

                    if sutun == 5:
                        deger = (
                            "Devam Ediyor"
                            if oturum.get("durum") == "AKTIF"
                            else "Tamamlandı"
                        )

                    hucre = QTableWidgetItem(str(deger))
                    hucre.setFlags(
                        hucre.flags() & ~Qt.ItemIsEditable
                    )

                    if sutun == 0:
                        font = hucre.font()
                        font.setBold(True)
                        hucre.setFont(font)
                        hucre.setForeground(QColor("#16294B"))

                    elif sutun == 1:
                        hucre.setForeground(QColor("#617493"))

                    elif sutun == 4 and uzun:
                        hucre.setForeground(QColor("#B45309"))
                        hucre.setToolTip(UZUN_GOREV_IPUCU)
                        font = hucre.font()
                        font.setBold(True)
                        hucre.setFont(font)

                    elif sutun == 5:
                        renk = (
                            "#2563EB"
                            if oturum.get("durum") == "AKTIF"
                            else "#16803C"
                        )
                        hucre.setForeground(QColor(renk))
                        font = hucre.font()
                        font.setBold(True)
                        hucre.setFont(font)

                    elif sutun == 6:
                        renk = (
                            "#16803C"
                            if oturum.get("onaylandi_mi")
                            else "#B86B08"
                        )
                        hucre.setForeground(QColor(renk))
                        font = hucre.font()
                        font.setBold(True)
                        hucre.setFont(font)

                    self.tablo.setItem(satir, sutun, hucre)

                self.tablo.item(satir, 0).setData(
                    Qt.UserRole, oturum
                )

            siralamayi_geri_yukle(self.tablo, siralama)

            if veri.get("kisaltildi"):
                self.ozet.setText(
                    f"Toplam {ozet.get('toplam', len(oturumlar))} görev kaydı var; devam eden ve onay bekleyen görevlerin tümü "
                    f"ile en yeni görevler gösteriliyor."
                )
                self.ozet.show()
            else:
                self.ozet.hide()

            bos = not oturumlar
            self.bos_mesaj.setVisible(bos)
            self.tablo.setVisible(not bos)

            # Seçim, sıralama sonrası satır sırasından bağımsız olarak görev kimliğiyle geri getirilir.
            if secili_id is not None:
                for satir in range(self.tablo.rowCount()):
                    hucre = self.tablo.item(satir, 0)
                    kayit = hucre.data(Qt.UserRole) if hucre is not None else None
                    if isinstance(kayit, dict) and kayit.get("oturum_id") == secili_id:
                        self.tablo.selectRow(satir)
                        break

            self._secim_degisti()

        except requests.RequestException as hata:
            if oturum_hatasi_mi(hata):
                return

            if not sessiz:
                QMessageBox.warning(
                    self,
                    "Bağlantı Hatası",
                    f"Görev kayıtları alınamadı:\n{istek_hatasi_metni(hata)}"
                )

    def _secim_degisti(self):
        satir = self.tablo.currentRow()

        hucre = self.tablo.item(satir, 0) if satir >= 0 else None
        oturum = hucre.data(Qt.UserRole) if hucre is not None else None

        uygun = (
            isinstance(oturum, dict)
            and oturum.get("bitis_zamani") is not None
            and not oturum.get("onaylandi_mi")
        )
        onayli = isinstance(oturum, dict) and bool(oturum.get("onaylandi_mi"))

        self.onay_btn.setEnabled(uygun)
        self.duzenle_btn.setEnabled(uygun)
        self.geri_al_btn.setEnabled(onayli)

    def gorev_onayla(self):
        satir = self.tablo.currentRow()
        if satir < 0:
            return

        hucre = self.tablo.item(satir, 0)
        if hucre is None:
            return

        oturum = hucre.data(Qt.UserRole)
        if not isinstance(oturum, dict):
            return

        if (
            oturum.get("bitis_zamani") is None
            or oturum.get("onaylandi_mi")
        ):
            return

        onay_penceresi = QMessageBox(self)
        onay_penceresi.setWindowTitle("Görev Onayı")
        onay_penceresi.setText(
            "Seçilen tamamlanmış görevi onaylamak istiyor musunuz?"
        )
        onay_penceresi.setIcon(QMessageBox.Question)
        if gorev_uzun_mu(oturum):
            onay_penceresi.setIcon(QMessageBox.Warning)
            onay_penceresi.setInformativeText(UZUN_GOREV_IPUCU)

        evet_btn = onay_penceresi.addButton(
            "Evet", QMessageBox.YesRole
        )
        onay_penceresi.addButton(
            "Hayır", QMessageBox.NoRole
        )

        onay_penceresi.exec()

        if onay_penceresi.clickedButton() != evet_btn:
            return

        try:
            yanit = oturum_kontrollu_istek("PATCH",
                f"{self.api_url}/api/danisma/yonetim/oturumlar/"
                f"{oturum['oturum_id']}/onayla",
                headers=self._headers(),
                timeout=10
            )
            yanit.raise_for_status()

            basari_bildirimi(self, "Görev başarıyla onaylandı.")
            self.yenile()

        except requests.RequestException as hata:
            if oturum_hatasi_mi(hata):
                return

            QMessageBox.warning(
                self,
                "Onay Hatası",
                f"Görev onaylanamadı:\n{istek_hatasi_metni(hata)}"
            )

    def onayi_geri_al(self):
        satir = self.tablo.currentRow()
        hucre = self.tablo.item(satir, 0) if satir >= 0 else None
        oturum = hucre.data(Qt.UserRole) if hucre is not None else None
        if not isinstance(oturum, dict) or not oturum.get("onaylandi_mi"):
            return

        soru = QMessageBox(self)
        soru.setWindowTitle("Onayı Geri Al")
        soru.setIcon(QMessageBox.Question)
        soru.setText("Seçilen görevin onayı kaldırılsın mı?")
        soru.setInformativeText(
            "Görev yeniden \"Onay Bekliyor\" durumuna döner ve düzenlenebilir. İşlem denetim kaydına yazılır."
        )
        evet_btn = soru.addButton("Evet", QMessageBox.YesRole)
        soru.addButton("Hayır", QMessageBox.NoRole)
        soru.exec()
        if soru.clickedButton() != evet_btn:
            return

        try:
            yanit = oturum_kontrollu_istek("PATCH",
                f"{self.api_url}/api/danisma/yonetim/oturumlar/"
                f"{oturum['oturum_id']}/onay-geri-al",
                headers=self._headers(),
                timeout=10
            )
            yanit.raise_for_status()

            basari_bildirimi(self, "Görevin onayı geri alındı.")
            self.yenile()

        except requests.HTTPError as hata:
            if oturum_hatasi_mi(hata):
                return
            QMessageBox.warning(
                self, "Onay Geri Alınamadı",
                hata_detayi_metni(hata.response, "Görevin onayı geri alınamadı.")
            )
            self.yenile(sessiz=True)

        except requests.RequestException as hata:
            if oturum_hatasi_mi(hata):
                return
            QMessageBox.warning(
                self, "Bağlantı Hatası",
                f"Görevin onayı geri alınamadı:\n{istek_hatasi_metni(hata)}"
            )

    def yeni_gorev_penceresi(self):
        from PySide6.QtCore import QDateTime, QTime
        from PySide6.QtWidgets import (
            QComboBox, QDateTimeEdit, QDialog,
            QDialogButtonBox, QFormLayout
        )

        try:
            yanit = oturum_kontrollu_istek("GET",
                f"{self.api_url}/api/danisma/yonetim/ogrenciler",
                headers=self._headers(),
                timeout=10
            )
            yanit.raise_for_status()
            ogrenciler = yanit.json().get("ogrenciler", [])
        except (requests.RequestException, ValueError) as hata:
            if oturum_hatasi_mi(hata):
                return

            QMessageBox.warning(
                self, "Bağlantı Hatası",
                f"Öğrenci listesi alınamadı:\n{istek_hatasi_metni(hata)}"
            )
            return

        if not ogrenciler:
            QMessageBox.information(
                self, "Öğrenci Bulunamadı",
                "Görev eklemek için aktif danışma masası öğrencisi bulunamadı."
            )
            return

        pencere = QDialog(self)
        pencere.setWindowTitle("Yeni Danışma Masası Görevi")
        pencere.setMinimumWidth(440)

        form = QFormLayout(pencere)
        _gorev_formunu_stille(
            pencere, form,
            "Yeni Danışma Masası Görevi",
            "Öğrenci için yeni görev kaydı oluşturun. "
            f"Bir görev en fazla {GOREV_EN_UZUN_SAAT} saat olabilir."
        )

        ogrenci_sec = QComboBox()
        for ogrenci in ogrenciler:
            metin = (
                f"{ogrenci['ad_soyad']} - "
                f"{ogrenci['ogrenci_numarasi']}"
            )
            if ogrenci.get("tur_etiketi"):
                metin += f" ({ogrenci['tur_etiketi']})"
            ogrenci_sec.addItem(metin, ogrenci["ogrenci_id"])

        def dakikaya_yuvarla(zaman):
            """Saat kutusu saniyeyi göstermediği için varsayılan zamanın saniyesi sıfırlanır (görünmeyen saniye kaydedilmesin)."""
            return QDateTime(zaman.date(), QTime(zaman.time().hour(), zaman.time().minute(), 0))

        baslangic = QDateTimeEdit()
        baslangic.setCalendarPopup(True)
        baslangic.setDisplayFormat("dd.MM.yyyy HH:mm")
        baslangic.setDateTime(
            dakikaya_yuvarla(QDateTime.currentDateTime().addSecs(-3600))
        )

        bitis = QDateTimeEdit()
        bitis.setCalendarPopup(True)
        bitis.setDisplayFormat("dd.MM.yyyy HH:mm")
        bitis.setDateTime(dakikaya_yuvarla(QDateTime.currentDateTime()))

        form.addRow("Öğrenci:", ogrenci_sec)
        form.addRow("Başlangıç:", baslangic)
        form.addRow("Bitiş:", bitis)

        butonlar = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        butonlar.button(QDialogButtonBox.Save).setText("Kaydet")
        butonlar.button(QDialogButtonBox.Cancel).setText("İptal")

        kaydet_btn = butonlar.button(QDialogButtonBox.Save)
        iptal_btn = butonlar.button(QDialogButtonBox.Cancel)

        kaydet_btn.setObjectName("danismaKaydet")
        iptal_btn.setObjectName("danismaIptal")

        for btn in (kaydet_btn, iptal_btn):
            btn.setMinimumSize(105, 38)
            btn.setCursor(Qt.PointingHandCursor)

        form.addRow(butonlar)

        def kaydet():
            bas = baslangic.dateTime().toPython()
            bit = bitis.dateTime().toPython()

            if bit <= bas:
                QMessageBox.warning(
                    pencere, "Geçersiz Zaman",
                    "Bitiş zamanı başlangıçtan sonra olmalıdır."
                )
                return

            if gorev_suresi_cok_uzun_mu(bas, bit):
                QMessageBox.warning(
                    pencere, "Görev Çok Uzun", GOREV_COK_UZUN_MESAJI
                )
                return

            if bit > datetime.now():
                QMessageBox.warning(
                    pencere, "Geçersiz Zaman",
                    "Gelecekte biten görev kaydı oluşturulamaz."
                )
                return

            veri = {
                "ogrenci_id": ogrenci_sec.currentData(),
                "baslangic_zamani": bas.isoformat(),
                "bitis_zamani": bit.isoformat()
            }

            try:
                yanit = oturum_kontrollu_istek("POST",
                    f"{self.api_url}/api/danisma/yonetim/oturumlar",
                    json=veri,
                    headers=self._headers(),
                    timeout=10
                )
                yanit.raise_for_status()
            except requests.HTTPError:
                if oturum_hatasi_mi(yanit):
                    return

                QMessageBox.warning(pencere, "Kayıt Hatası", hata_detayi_metni(yanit, "Kayıt oluşturulamadı."))
                return
            except requests.RequestException as hata:
                if oturum_hatasi_mi(hata):
                    return

                QMessageBox.warning(
                    pencere, "Bağlantı Hatası", istek_hatasi_metni(hata)
                )
                return

            pencere.accept()
            self.yenile()
            basari_bildirimi(self, "Yeni danışma masası görevi oluşturuldu.")

        butonlar.accepted.connect(kaydet)
        butonlar.rejected.connect(pencere.reject)

        pencere.exec()

    def gorev_duzenle(self):
        from PySide6.QtCore import QDateTime
        from PySide6.QtWidgets import (
            QDialog, QDateTimeEdit,
            QDialogButtonBox, QFormLayout
        )

        satir = self.tablo.currentRow()
        if satir < 0:
            return

        hucre = self.tablo.item(satir, 0)
        if hucre is None:
            return

        oturum = hucre.data(Qt.UserRole)

        if not isinstance(oturum, dict):
            return

        if oturum.get("onaylandi_mi") or not oturum.get("bitis_zamani"):
            QMessageBox.warning(
                self,
                "Düzenleme Yapılamaz",
                "Yalnızca tamamlanmış ve onay bekleyen görevler düzenlenebilir."
            )
            return

        pencere = QDialog(self)
        pencere.setWindowTitle("Danışma Masası Görev Düzenleme")
        pencere.setMinimumWidth(480)

        form = QFormLayout(pencere)
        _gorev_formunu_stille(
            pencere, form,
            "Danışma Masası Görevini Düzenle",
            "Seçilen görevin başlangıç ve bitiş zamanını güncelleyin. "
            f"Bir görev en fazla {GOREV_EN_UZUN_SAAT} saat olabilir."
        )

        ogrenci = QLabel(
            f"{oturum.get('ad_soyad', '')} - "
            f"{oturum.get('ogrenci_numarasi', '')}"
        )
        ogrenci.setObjectName("gorevOgrenci")
        ogrenci.setWordWrap(True)

        baslangic = QDateTimeEdit()
        baslangic.setCalendarPopup(True)
        baslangic.setDisplayFormat("dd.MM.yyyy HH:mm:ss")

        bitis = QDateTimeEdit()
        bitis.setCalendarPopup(True)
        bitis.setDisplayFormat("dd.MM.yyyy HH:mm:ss")

        baslangic.setDateTime(
            QDateTime.fromString(
                oturum["baslangic_zamani"][:19],
                "yyyy-MM-ddTHH:mm:ss"
            )
        )

        bitis.setDateTime(
            QDateTime.fromString(
                oturum["bitis_zamani"][:19],
                "yyyy-MM-ddTHH:mm:ss"
            )
        )

        form.addRow("Öğrenci:", ogrenci)
        form.addRow("Başlangıç:", baslangic)
        form.addRow("Bitiş:", bitis)

        butonlar = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )

        butonlar.button(QDialogButtonBox.Save).setText("Kaydet")
        butonlar.button(QDialogButtonBox.Cancel).setText("İptal")

        kaydet_btn = butonlar.button(QDialogButtonBox.Save)
        iptal_btn = butonlar.button(QDialogButtonBox.Cancel)

        kaydet_btn.setObjectName("danismaKaydet")
        iptal_btn.setObjectName("danismaIptal")

        for btn in (kaydet_btn, iptal_btn):
            btn.setMinimumSize(105, 38)
            btn.setCursor(Qt.PointingHandCursor)

        form.addRow(butonlar)

        def kaydet():
            bas = baslangic.dateTime().toPython()
            bit = bitis.dateTime().toPython()

            if bit <= bas:
                QMessageBox.warning(
                    pencere,
                    "Geçersiz Zaman",
                    "Bitiş zamanı başlangıçtan sonra olmalıdır."
                )
                return

            if gorev_suresi_cok_uzun_mu(bas, bit):
                QMessageBox.warning(
                    pencere,
                    "Görev Çok Uzun",
                    GOREV_COK_UZUN_MESAJI
                )
                return

            if bit > datetime.now():
                QMessageBox.warning(
                    pencere,
                    "Geçersiz Zaman",
                    "Gelecekte biten görev kaydı düzenlenemez."
                )
                return

            veri = {
                "baslangic_zamani": bas.isoformat(),
                "bitis_zamani": bit.isoformat()
            }

            try:
                yanit = oturum_kontrollu_istek("PATCH",
                    f"{self.api_url}/api/danisma/yonetim/oturumlar/"
                    f"{oturum['oturum_id']}",
                    json=veri,
                    headers=self._headers(),
                    timeout=10
                )
                yanit.raise_for_status()

            except requests.HTTPError:
                if oturum_hatasi_mi(yanit):
                    return

                QMessageBox.warning(
                    pencere, "Düzenleme Hatası", hata_detayi_metni(yanit, "Görev düzenlenemedi.")
                )
                return

            except requests.RequestException as hata:
                if oturum_hatasi_mi(hata):
                    return

                QMessageBox.warning(
                    pencere, "Bağlantı Hatası", istek_hatasi_metni(hata)
                )
                return

            pencere.accept()
            self.yenile()

            basari_bildirimi(self, "Görev başarıyla güncellendi.")

        butonlar.accepted.connect(kaydet)
        butonlar.rejected.connect(pencere.reject)

        pencere.exec()
