"""TKYS - Danışma Masası Öğrencisi Görev Takip Ekranı."""

import time
from datetime import datetime

import requests

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QHeaderView,
)


class DanismaMasasiEkrani(QWidget):
    BG = "#F5F7FB"
    NAVY = "#16294B"
    BLUE = "#285CE6"
    MUTED = "#697993"
    GREEN = "#15865D"
    RED = "#CE4352"

    def __init__(self, api_url, token, parent=None):
        super().__init__(parent)

        self.api_url = api_url.rstrip("/")
        self.token = token

        self._aktif = False
        self._gecen_saniye = 0
        self._referans_zamani = time.monotonic()

        self._arayuz_kur()

        # Canlı çalışma süresi
        self.saat = QTimer(self)
        self.saat.timeout.connect(self._sayaci_guncelle)
        self.saat.start(1000)

        # Sunucuyla her 30 saniyede bir senkronizasyon
        self.sunucu_yenileme = QTimer(self)
        self.sunucu_yenileme.timeout.connect(self.durum_yenile)
        self.sunucu_yenileme.start(30000)

        self.yenile()

    def _golge(self, widget):
        golge = QGraphicsDropShadowEffect(widget)
        golge.setBlurRadius(20)
        golge.setOffset(0, 5)
        golge.setColor(QColor(24, 42, 75, 15))
        widget.setGraphicsEffect(golge)

    def _kart(self):
        kart = QFrame()
        kart.setObjectName("kart")
        kart.setStyleSheet("""
            QFrame#kart {
                background: white;
                border: 1px solid #E7ECF4;
                border-radius: 16px;
            }
        """)
        self._golge(kart)
        return kart

    def _metin(self, yazi, boyut=12, renk=None, kalin=False):
        etiket = QLabel(yazi)

        etiket.setStyleSheet(
            f"color: {renk or self.NAVY}; "
            f"font-size: {boyut}px;"
            + ("font-weight: 700;" if kalin else "")
        )

        return etiket

    def _arayuz_kur(self):
        self.setObjectName("danismaSayfa")

        self.setStyleSheet("""
            QWidget#danismaSayfa {
                background: #F5F7FB;
            }
        """)

        ana = QVBoxLayout(self)
        ana.setContentsMargins(0, 0, 0, 0)

        kaydir = QScrollArea()
        kaydir.setWidgetResizable(True)
        kaydir.setFrameShape(QFrame.NoFrame)

        kaydir.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
        """)

        ana.addWidget(kaydir)

        icerik = QWidget()
        icerik.setObjectName("danismaIcerik")

        icerik.setStyleSheet("""
            QWidget#danismaIcerik {
                background: #F5F7FB;
            }
        """)

        kaydir.setWidget(icerik)

        govde = QVBoxLayout(icerik)
        govde.setContentsMargins(28, 26, 28, 28)
        govde.setSpacing(18)

        # -------------------------------------
        # SAYFA BAŞLIĞI
        # -------------------------------------

        ust = QHBoxLayout()

        baslik = QVBoxLayout()
        baslik.setSpacing(5)

        baslik.addWidget(
            self._metin(
                "Danışma Masası",
                27,
                self.NAVY,
                True
            )
        )

        ust.addLayout(baslik)
        ust.addStretch()

        self.lbl_etiket = self._metin(
            "ÖĞRENCİ PANELİ",
            10,
            self.BLUE,
            True
        )

        self.lbl_etiket.setStyleSheet("""
            QLabel {
                background: #EAF0FF;
                color: #285CE6;
                border-radius: 11px;
                padding: 9px 14px;
                font-size: 10px;
                font-weight: 700;
            }
        """)

        ust.addWidget(self.lbl_etiket)
        govde.addLayout(ust)

        # -------------------------------------
        # GÖREV DURUMU VE ÇALIŞMA SÜRESİ
        # -------------------------------------

        kartlar = QHBoxLayout()
        kartlar.setSpacing(16)

        # Görev durumu kartı
        durum_karti = self._kart()

        durum_icerik = QVBoxLayout(durum_karti)
        durum_icerik.setContentsMargins(22, 20, 22, 22)
        durum_icerik.setSpacing(12)

        durum_icerik.addWidget(
            self._metin(
                "GÖREV DURUMU",
                10,
                self.MUTED,
                True
            )
        )

        self.lbl_durum = self._metin(
            "Görev bilgisi yükleniyor...",
            17,
            self.NAVY,
            True
        )

        self.lbl_durum.setWordWrap(True)
        durum_icerik.addWidget(self.lbl_durum)

        self.lbl_alt_durum = self._metin(
            "Bağlantı kontrol ediliyor",
            11,
            self.MUTED
        )

        self.lbl_alt_durum.setWordWrap(True)
        durum_icerik.addWidget(self.lbl_alt_durum)

        durum_icerik.addStretch()
        kartlar.addWidget(durum_karti, 1)

        # Çalışma süresi kartı
        sure_karti = self._kart()

        sure_icerik = QVBoxLayout(sure_karti)
        sure_icerik.setContentsMargins(22, 20, 22, 22)
        sure_icerik.setSpacing(9)

        sure_icerik.addWidget(
            self._metin(
                "ÇALIŞMA SÜRESİ",
                10,
                self.MUTED,
                True
            )
        )

        self.lbl_sure = self._metin(
            "00:00:00",
            34,
            self.NAVY,
            True
        )

        self.lbl_sure.setStyleSheet("""
            color: #16294B;
            font-size: 34px;
            font-weight: 800;
        """)

        sure_icerik.addWidget(self.lbl_sure)

        sure_icerik.addWidget(
            self._metin(
                "Saat : Dakika : Saniye",
                11,
                self.MUTED
            )
        )

        sure_icerik.addStretch()
        kartlar.addWidget(sure_karti, 1)

        govde.addLayout(kartlar)

        # -------------------------------------
        # GÖREV İŞLEMLERİ
        # -------------------------------------

        islemler = self._kart()

        islemler_icerik = QVBoxLayout(islemler)
        islemler_icerik.setContentsMargins(22, 20, 22, 22)
        islemler_icerik.setSpacing(13)

        islemler_icerik.addWidget(
            self._metin(
                "Görev İşlemleri",
                16,
                self.NAVY,
                True
            )
        )

        islemler_icerik.addWidget(
            self._metin(
                "Görev süren, başlatma ve bitirme işlemlerine göre kaydedilir.",
                11,
                self.MUTED
            )
        )

        butonlar = QHBoxLayout()
        butonlar.setSpacing(12)

        self.btn_baslat = QPushButton(
            "▶   Görevi Başlat"
        )

        self.btn_bitir = QPushButton(
            "■   Görevi Bitir"
        )


        for buton in (
            self.btn_baslat,
            self.btn_bitir
        ):
            buton.setMinimumHeight(44)
            buton.setCursor(Qt.PointingHandCursor)

        self.btn_baslat.setStyleSheet("""
            QPushButton {
                background: #285CE6;
                color: white;
                border: none;
                border-radius: 10px;
                font-size: 13px;
                font-weight: 700;
            }

            QPushButton:hover {
                background: #1E49BD;
            }

            QPushButton:disabled {
                background: #DCE4F3;
                color: #96A3B9;
            }
        """)

        self.btn_bitir.setStyleSheet("""
            QPushButton {
                background: #CE4352;
                color: white;
                border: none;
                border-radius: 10px;
                font-size: 13px;
                font-weight: 700;
            }

            QPushButton:hover {
                background: #B52F40;
            }

            QPushButton:disabled {
                background: #F2E4E7;
                color: #CDAEB6;
            }
        """)


        self.btn_baslat.clicked.connect(
            self.gorev_baslat
        )

        self.btn_bitir.clicked.connect(
            self.gorev_bitir
        )


        butonlar.addWidget(self.btn_baslat, 2)
        butonlar.addWidget(self.btn_bitir, 2)

        islemler_icerik.addLayout(butonlar)


        govde.addWidget(islemler)

        # -------------------------------------
        # GEÇMİŞ GÖREVLER
        # -------------------------------------

        gecmis = self._kart()

        gecmis_icerik = QVBoxLayout(gecmis)
        gecmis_icerik.setContentsMargins(22, 20, 22, 22)
        gecmis_icerik.setSpacing(14)

        satir = QHBoxLayout()

        satir.addWidget(
            self._metin(
                "Geçmiş Görevler",
                16,
                self.NAVY,
                True
            )
        )

        satir.addStretch()

        self.lbl_gecmis_sayi = self._metin(
            "0 kayıt",
            11,
            self.MUTED
        )

        satir.addWidget(self.lbl_gecmis_sayi)

        gecmis_icerik.addLayout(satir)

        self.tablo = QTableWidget(0, 5)

        self.tablo.setHorizontalHeaderLabels([
            "Tarih",
            "Başlangıç",
            "Bitiş",
            "Çalışma Süresi",
            "Onay Durumu"
        ])

        self.tablo.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )

        self.tablo.horizontalHeader().setFixedHeight(42)

        self.tablo.verticalHeader().hide()

        self.tablo.setSelectionBehavior(
            QAbstractItemView.SelectRows
        )

        self.tablo.setEditTriggers(
            QAbstractItemView.NoEditTriggers
        )

        self.tablo.setAlternatingRowColors(True)
        self.tablo.setShowGrid(False)
        self.tablo.setMinimumHeight(210)

        self.tablo.setStyleSheet("""
            QTableWidget {
                background: white;
                alternate-background-color: #F9FBFF;
                color: #263A5C;
                border: 1px solid #E7ECF4;
                border-radius: 9px;
                font-size: 12px;
            }

            QHeaderView::section {
                background: #F2F5FA;
                color: #66758E;
                font-weight: 700;
                border: none;
                border-bottom: 1px solid #E7ECF4;
                padding-left: 8px;
            }

            QTableWidget::item {
                padding: 8px;
                border: none;
            }

            QTableWidget::item:selected {
                background: #EAF0FF;
                color: #16294B;
            }
        """)

        gecmis_icerik.addWidget(self.tablo)

        self.lbl_gecmis = self._metin(
            "Görev geçmişi yükleniyor...",
            11,
            self.MUTED
        )

        self.lbl_gecmis.setAlignment(Qt.AlignCenter)
        self.lbl_gecmis.setMinimumHeight(28)

        gecmis_icerik.addWidget(
            self.lbl_gecmis
        )

        govde.addWidget(gecmis)
        govde.addStretch()

        self._butonlari_ayarla(
            False,
            baglanti_var=False
        )

    # -------------------------------------
    # API İSTEKLERİ
    # -------------------------------------

    def _butonlari_ayarla(
        self,
        aktif,
        baglanti_var=True
    ):
        self.btn_baslat.setEnabled(
            baglanti_var and not aktif
        )

        self.btn_bitir.setEnabled(
            baglanti_var and aktif
        )

    def _istek(self, method, yol):
        cevap = requests.request(
            method,
            f"{self.api_url}{yol}",
            headers={
                "Authorization": f"Bearer {self.token}"
            },
            timeout=6,
        )

        if not cevap.ok:
            try:
                detay = cevap.json().get(
                    "detail",
                    "İşlem başarısız."
                )
            except (ValueError, AttributeError):
                detay = "İşlem başarısız."

            raise RuntimeError(
                f"{cevap.status_code}: {detay}"
            )

        return cevap.json()

    # -------------------------------------
    # SÜRE HESAPLAMA
    # -------------------------------------

    @staticmethod
    def _saniye_hesapla(veri):
        if veri.get("toplam_saniye") is not None:
            return max(
                0,
                int(veri["toplam_saniye"])
            )

        if veri.get("toplam_dakika") is not None:
            return max(
                0,
                int(veri["toplam_dakika"]) * 60
            )

        baslangic = veri.get("baslangic_zamani")

        if baslangic:
            try:
                tarih = datetime.fromisoformat(
                    baslangic.replace(
                        "Z",
                        "+00:00"
                    )
                )

                simdi = (
                    datetime.now(tarih.tzinfo)
                    if tarih.tzinfo
                    else datetime.now()
                )

                return max(
                    0,
                    int(
                        (simdi - tarih).total_seconds()
                    )
                )

            except (
                ValueError,
                TypeError,
                OverflowError
            ):
                pass

        return 0

    @staticmethod
    def _saat_bicimi(saniye):
        saat, kalan = divmod(
            max(0, int(saniye)),
            3600
        )

        dakika, saniye = divmod(
            kalan,
            60
        )

        return (
            f"{saat:02d}:"
            f"{dakika:02d}:"
            f"{saniye:02d}"
        )

    @staticmethod
    def _insan_suresi(saniye):
        dakika = max(
            0,
            int(saniye)
        ) // 60

        return (
            f"{dakika // 60} saat "
            f"{dakika % 60} dakika"
        )

    def _sayaci_guncelle(self):
        if self._aktif:
            anlik = (
                self._gecen_saniye
                + (
                    time.monotonic()
                    - self._referans_zamani
                )
            )

            self.lbl_sure.setText(
                self._saat_bicimi(anlik)
            )

    # -------------------------------------
    # AKTİF GÖREV DURUMU
    # -------------------------------------

    def durum_yenile(self):
        try:
            veri = self._istek(
                "GET",
                "/api/danisma/oturum/aktif"
            )

            self._aktif = (
                veri.get("durum") == "AKTIF"
            )

            self._gecen_saniye = (
                self._saniye_hesapla(veri)
                if self._aktif
                else 0
            )

            self._referans_zamani = (
                time.monotonic()
            )

            self.lbl_sure.setText(
                self._saat_bicimi(
                    self._gecen_saniye
                )
            )

            if self._aktif:
                self.lbl_durum.setText(
                    "●  Görev Devam Ediyor"
                )

                self.lbl_durum.setStyleSheet(
                    f"color: {self.GREEN}; "
                    "font-size: 17px; "
                    "font-weight: 700;"
                )

                self.lbl_alt_durum.setText(
                    "Çalışma süreniz kaydediliyor."
                )

            else:
                self.lbl_durum.setText(
                    "○  Aktif Görev Yok"
                )

                self.lbl_durum.setStyleSheet(
                    f"color: {self.NAVY}; "
                    "font-size: 17px; "
                    "font-weight: 700;"
                )

                self.lbl_alt_durum.setText(
                    "Başlamak için 'Görevi Başlat' "
                    "düğmesini kullanın."
                )

            self._butonlari_ayarla(
                self._aktif
            )

            return True

        except (
            requests.RequestException,
            RuntimeError,
            ValueError,
            KeyError,
            TypeError
        ) as hata:

            self._aktif = False

            self.lbl_sure.setText(
                "--:--:--"
            )

            self.lbl_durum.setText(
                "Bağlantı / Yetkilendirme Hatası"
            )

            self.lbl_durum.setStyleSheet(
                f"color: {self.RED}; "
                "font-size: 15px; "
                "font-weight: 700;"
            )

            self.lbl_alt_durum.setText(
                str(hata)
            )

            self._butonlari_ayarla(
                False,
                baglanti_var=False
            )

            return False

    # -------------------------------------
    # GEÇMİŞ GÖREVLER
    # -------------------------------------

    def gecmis_yenile(self):
        try:
            veri = self._istek(
                "GET",
                "/api/danisma/oturum/gecmis"
            )

            oturumlar = veri.get(
                "oturumlar",
                []
            )

            self.tablo.setRowCount(
                len(oturumlar)
            )

            for satir, oturum in enumerate(
                oturumlar
            ):
                baslangic = str(
                    oturum.get(
                        "baslangic_zamani"
                    ) or ""
                )

                bitis = str(
                    oturum.get(
                        "bitis_zamani"
                    ) or ""
                )

                tarih = (
                    oturum.get("tarih")
                    or baslangic[:10]
                )

                try:
                    bas = datetime.fromisoformat(
                        baslangic.replace("Z", "+00:00")
                    )
                    son = datetime.fromisoformat(
                        bitis.replace("Z", "+00:00")
                    )
                    toplam = max(
                        0, int((son - bas).total_seconds())
                    )

                    saat, kalan = divmod(toplam, 3600)
                    dakika, saniye = divmod(kalan, 60)

                    if saat:
                        sure = f"{saat} saat {dakika} dakika {saniye} saniye"
                    elif dakika:
                        sure = f"{dakika} dakika {saniye} saniye"
                    else:
                        sure = f"{saniye} saniye"

                except (ValueError, TypeError):
                    sure = oturum.get("calisilan_sure") or "—"

                degerler = [
                    tarih,
                    (
                        baslangic[11:16]
                        if len(baslangic) >= 16
                        else "—"
                    ),
                    (
                        bitis[11:16]
                        if len(bitis) >= 16
                        else "—"
                    ),
                    sure,
                    (
                        "Onaylandı"
                        if oturum.get(
                            "onaylandi_mi"
                        )
                        else "Onay bekliyor"
                    )
                ]

                self.tablo.setRowHeight(
                    satir,
                    42
                )

                for sutun, deger in enumerate(
                    degerler
                ):
                    hucre = QTableWidgetItem(
                        str(deger)
                    )

                    hucre.setTextAlignment(
                        Qt.AlignCenter
                    )

                    if sutun == 4:
                        renk = (
                            self.GREEN
                            if oturum.get(
                                "onaylandi_mi"
                            )
                            else "#B47D23"
                        )

                        hucre.setForeground(
                            QColor(renk)
                        )

                    self.tablo.setItem(
                        satir,
                        sutun,
                        hucre
                    )

            self.lbl_gecmis_sayi.setText(
                f"{len(oturumlar)} kayıt"
            )

            if not oturumlar:
                self.lbl_gecmis.setText(
                    "Henüz tamamlanmış "
                    "göreviniz bulunmuyor."
                )
            else:
                self.lbl_gecmis.setText(
                    "Son 50 tamamlanan görev listelenir."
                )

            return True

        except (
            requests.RequestException,
            RuntimeError,
            ValueError,
            KeyError,
            TypeError
        ) as hata:

            self.lbl_gecmis.setText(
                "Görev geçmişi alınamadı: "
                f"{hata}"
            )

            self.lbl_gecmis_sayi.setText(
                "—"
            )
            return False

    def yenile(self, bildirim=False):
        durum_ok = self.durum_yenile()
        gecmis_ok = self.gecmis_yenile()

        if bildirim:
            if durum_ok and gecmis_ok:
                saat = datetime.now().strftime("%H:%M:%S")
                self.lbl_yenileme.setText(
                    f"✓ Bilgiler güncellendi • {saat}"
                )
            else:
                self.lbl_yenileme.setText(
                    "Güncelleme tamamlanamadı. Hata mesajını kontrol edin."
                )

    # -------------------------------------
    # GÖREV BAŞLATMA
    # -------------------------------------

    def gorev_baslat(self):
        pencere = QMessageBox(self)
        pencere.setWindowTitle("Görevi Başlat")
        pencere.setIcon(QMessageBox.Question)
        pencere.setText(
            "Danışma masası görevinizi başlatmak "
            "istediğinize emin misiniz?\n\n"
            "Onayladığınızda çalışma süreniz "
            "kaydedilmeye başlanacaktır."
        )

        vazgec = pencere.addButton(
            "Vazgeç",
            QMessageBox.RejectRole
        )

        evet = pencere.addButton(
            "Evet, Görevi Başlat",
            QMessageBox.AcceptRole
        )

        pencere.setDefaultButton(vazgec)
        pencere.exec()

        # Vazgeçilirse API çağrılmaz, süre başlamaz.
        if pencere.clickedButton() != evet:
            return

        self._butonlari_ayarla(
            False,
            baglanti_var=False
        )

        try:
            self._istek(
                "POST",
                "/api/danisma/oturum/baslat"
            )

            self.yenile()

        except (
            requests.RequestException,
            RuntimeError,
            ValueError
        ) as hata:
            QMessageBox.warning(
                self,
                "Görev Başlatılamadı",
                str(hata)
            )

            self.yenile()

    # -------------------------------------
    # GÖREV BİTİRME VE ONAY PENCERESİ
    # -------------------------------------

    def gorev_bitir(self):
        try:
            aktif = self._istek(
                "GET",
                "/api/danisma/oturum/aktif"
            )

            if aktif.get("durum") != "AKTIF":
                QMessageBox.warning(
                    self,
                    "Uyarı",
                    "Devam eden bir göreviniz "
                    "bulunmuyor."
                )

                self.yenile()
                return

            saniye = self._saniye_hesapla(
                aktif
            )

            sure = self._insan_suresi(
                saniye
            )

            onay_kutusu = QMessageBox(self)

            onay_kutusu.setWindowTitle(
                "Görevi Bitir"
            )

            onay_kutusu.setIcon(
                QMessageBox.Question
            )

            onay_kutusu.setText(
                f"{sure} çalıştınız.\n\n"
                "Görevinizi bitirmek "
                "istediğinize emin misiniz?"
            )

            onay_kutusu.addButton(
                "Vazgeç",
                QMessageBox.RejectRole
            )

            evet = onay_kutusu.addButton(
                "Evet, Görevi Bitir",
                QMessageBox.AcceptRole
            )

            onay_kutusu.exec()

            # Vazgeç seçilirse görev devam eder.
            if (
                onay_kutusu.clickedButton()
                != evet
            ):
                return

            self._butonlari_ayarla(
                False,
                baglanti_var=False
            )

            sonuc = self._istek(
                "PATCH",
                "/api/danisma/oturum/bitir"
            )

            self.yenile()

            QMessageBox.information(
                self,
                "Görev Tamamlandı",
                "Göreviniz başarıyla bitirildi."
                "\n\n"
                "Toplam çalışma süreniz: "
                f"{sonuc.get('calisilan_sure', sure)}"
            )

        except (
            requests.RequestException,
            RuntimeError,
            ValueError,
            KeyError
        ) as hata:

            QMessageBox.warning(
                self,
                "Görev Bitirilemedi",
                str(hata)
            )

            self.yenile()
