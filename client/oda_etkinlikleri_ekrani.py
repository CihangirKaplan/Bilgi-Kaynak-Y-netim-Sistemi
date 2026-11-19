"""TKYS Oda Etkinlikleri yönetim ekranı."""

from datetime import datetime

import requests
from PySide6.QtCore import QDateTime, Qt
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QWidget, QDialog, QVBoxLayout, QHBoxLayout,
    QFormLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QComboBox, QLineEdit, QSpinBox,
    QDateTimeEdit, QLabel, QPushButton, QMessageBox,
    QDialogButtonBox, QAbstractItemView, QPlainTextEdit,
)

from client.api_yoneticisi import (
    oturum_kontrollu_istek,
    oturum_hatasi_mi,
)


def tarih_yaz(deger):
    if not deger:
        return "—"
    try:
        return datetime.fromisoformat(str(deger)).strftime("%d.%m.%Y %H:%M")
    except ValueError:
        return str(deger)


from PySide6.QtCore import QDate, QTime
from PySide6.QtWidgets import QDateEdit, QTimeEdit, QScrollArea, QFrame

class OdaEtkinlikFormu(QDialog):
    """Tek etkinliğe birden fazla bağımsız oturum ekleme formu."""

    def __init__(self, odalar, personeller, kayit=None, parent=None):
        super().__init__(parent)

        self.setWindowTitle(
            "Etkinlik Düzenle" if kayit else "Yeni Oda Etkinliği"
        )
        self.resize(720, 600)
        self.setMinimumWidth(640)

        self.setStyleSheet("""
            QDialog {
                background: #F8FAFF;
                color: #243653;
            }
            QLabel {
                color: #243653;
                font-size: 12px;
            }
            QLineEdit, QComboBox, QSpinBox,
            QDateEdit, QTimeEdit {
                background: white;
                color: #243653;
                border: 1px solid #CBD7E8;
                border-radius: 7px;
                padding: 6px;
                min-height: 24px;
            }
            QPushButton {
                background: #EFF4FD;
                color: #243653;
                border: 1px solid #D1DDF0;
                border-radius: 7px;
                padding: 8px 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #DFEAFE;
            }
        """)

        ana = QVBoxLayout(self)
        ana.setSpacing(12)

        form = QFormLayout()

        self.oda = QComboBox()
        for o in odalar:
            ad = o["oda_adi"]
            self.oda.addItem(ad, o["oda_id"])

        self.personel = QComboBox()
        for p in personeller:
            ad = p["kullanici_adi"]
            kod = p.get("personel_kodu")
            self.personel.addItem(
                f"{ad} ({kod})" if kod else ad,
                p["personel_id"],
            )

        self.ad = QLineEdit()
        self.ad.setMaxLength(150)
        self.ad.setPlaceholderText("Örn. Eğitim Semineri")

        self.katilimci = QLineEdit()
        self.katilimci.setPlaceholderText("Örn. 12")
        self.katilimci.setValidator(
            QIntValidator(1, 100000, self.katilimci)
        )
        self.katilimci.setMaximumWidth(260)

        form.addRow("Oda:", self.oda)
        form.addRow("Düzenleyen personel:", self.personel)
        form.addRow("Etkinlik adı:", self.ad)
        form.addRow("Katılımcı sayısı (isteğe bağlı):", self.katilimci)
        ana.addLayout(form)

        baslik = QLabel("Etkinlik Günleri ve Saatleri")
        baslik.setStyleSheet(
            "font-size: 15px; font-weight: 700; color: #203657;"
        )
        ana.addWidget(baslik)

        bilgi = QLabel(
            "Her oturum için tarih ve saat seçiniz. "
            "Oda yalnızca eklenen günlerde ve saatlerde ayrılır. "
            "Çalışma saatleri: 08.00–18.00."
        )
        bilgi.setWordWrap(True)
        ana.addWidget(bilgi)

        self.kaydirma = QScrollArea()
        self.kaydirma.setWidgetResizable(True)
        self.kaydirma.setMinimumHeight(180)
        self.kaydirma.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
        )

        self.oturum_alani = QWidget()
        self.oturum_duzeni = QVBoxLayout(self.oturum_alani)
        self.oturum_duzeni.setSpacing(8)
        self.oturum_duzeni.setContentsMargins(2, 2, 2, 2)
        self.oturum_duzeni.addStretch()

        self.kaydirma.setWidget(self.oturum_alani)
        ana.addWidget(self.kaydirma, 1)

        self.oturum_satirlari = []

        ekle_btn = QPushButton("+ Gün / Saat Ekle")
        ekle_btn.clicked.connect(self.oturum_ekle)
        ana.addWidget(ekle_btn)

        if kayit:
            self.oda.setCurrentIndex(
                self.oda.findData(kayit["oda_id"])
            )
            self.personel.setCurrentIndex(
                self.personel.findData(
                    kayit["organize_eden_personel_id"]
                )
            )
            self.ad.setText(kayit["etkinlik_adi"])
            self.katilimci.setText(
                str(kayit["katilimci_sayisi"])
                if kayit.get("katilimci_sayisi") is not None
                else ""
            )

            gunler = kayit.get("gunler") or []

            if not gunler:
                # Eski API yanıtları için geriye dönük uyumluluk.
                from datetime import timedelta

                bas = datetime.fromisoformat(
                    str(kayit["baslangic_zamani"])
                )
                bit = datetime.fromisoformat(
                    str(kayit["bitis_zamani"])
                )

                gun_sayisi = (bit.date() - bas.date()).days + 1
                if not 1 <= gun_sayisi <= 366:
                    raise ValueError(
                        "Etkinliğin gün bilgileri geçersiz."
                    )

                for i in range(gun_sayisi):
                    gun = bas.date() + timedelta(days=i)
                    gunler.append({
                        "baslangic_zamani": datetime.combine(
                            gun, bas.time()
                        ).isoformat(),
                        "bitis_zamani": datetime.combine(
                            gun, bit.time()
                        ).isoformat(),
                    })

            for gun in gunler:
                self.oturum_ekle(
                    gun["baslangic_zamani"],
                    gun["bitis_zamani"],
                )
        else:
            self.oturum_ekle()

        dugmeler = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        dugmeler.button(QDialogButtonBox.Save).setText("Kaydet")
        dugmeler.button(QDialogButtonBox.Cancel).setText("Vazgeç")
        dugmeler.accepted.connect(self.kaydet)
        dugmeler.rejected.connect(self.reject)
        ana.addWidget(dugmeler)

    def oturum_ekle(self, baslangic=None, bitis=None):
        if len(self.oturum_satirlari) >= 366:
            QMessageBox.warning(
                self, "Oturum Sınırı",
                "En fazla 366 oturum eklenebilir."
            )
            return

        cerceve = QFrame()
        cerceve.setStyleSheet("""
            QFrame {
                background: white;
                border: 1px solid #E3EAF5;
                border-radius: 8px;
            }
            QFrame QLabel {
                border: none;
            }
        """)

        duzen = QHBoxLayout(cerceve)

        tarih = QDateEdit()
        tarih.setCalendarPopup(True)
        tarih.setDisplayFormat("dd.MM.yyyy")
        tarih.setDate(QDate.currentDate())

        saat_bas = QTimeEdit()
        saat_bas.setDisplayFormat("HH:mm")
        saat_bas.setTime(QTime(13, 0))

        saat_bit = QTimeEdit()
        saat_bit.setDisplayFormat("HH:mm")
        saat_bit.setTime(QTime(14, 0))

        if baslangic is not None and bitis is not None:
            bas = datetime.fromisoformat(str(baslangic))
            bit = datetime.fromisoformat(str(bitis))

            tarih.setDate(
                QDate(bas.year, bas.month, bas.day)
            )
            saat_bas.setTime(
                QTime(bas.hour, bas.minute)
            )
            saat_bit.setTime(
                QTime(bit.hour, bit.minute)
            )

        kaldir = QPushButton("Kaldır")
        kaldir.setToolTip("Bu etkinlik oturumunu kaldır")

        duzen.addWidget(tarih, 3)
        duzen.addWidget(QLabel("Başlangıç:"))
        duzen.addWidget(saat_bas, 2)
        duzen.addWidget(QLabel("Bitiş:"))
        duzen.addWidget(saat_bit, 2)
        duzen.addWidget(kaldir)

        satir = (cerceve, tarih, saat_bas, saat_bit)
        self.oturum_satirlari.append(satir)

        kaldir.clicked.connect(
            lambda checked=False, s=satir: self.oturum_kaldir(s)
        )

        self.oturum_duzeni.insertWidget(
            self.oturum_duzeni.count() - 1, cerceve
        )

    def oturum_kaldir(self, satir):
        if len(self.oturum_satirlari) <= 1:
            QMessageBox.warning(
                self, "Oturum Gerekli",
                "Etkinlikte en az bir oturum bulunmalıdır."
            )
            return

        self.oturum_satirlari.remove(satir)
        cerceve = satir[0]
        self.oturum_duzeni.removeWidget(cerceve)
        cerceve.deleteLater()

    def oturum_verileri(self):
        gunler = []

        for _, tarih, saat_bas, saat_bit in self.oturum_satirlari:
            gun = tarih.date().toString("yyyy-MM-dd")
            bas = saat_bas.time().toString("HH:mm")
            bit = saat_bit.time().toString("HH:mm")

            gunler.append({
                "baslangic_zamani": f"{gun}T{bas}:00",
                "bitis_zamani": f"{gun}T{bit}:00",
            })

        return gunler

    def kaydet(self):
        if self.oda.currentData() is None:
            QMessageBox.warning(
                self, "Eksik Bilgi", "Oda seçiniz."
            )
            return

        if self.personel.currentData() is None:
            QMessageBox.warning(
                self, "Eksik Bilgi", "Personel seçiniz."
            )
            return

        if not self.ad.text().strip():
            QMessageBox.warning(
                self, "Eksik Bilgi", "Etkinlik adını giriniz."
            )
            return

        if (self.katilimci.text().strip()
                and not self.katilimci.hasAcceptableInput()):
            QMessageBox.warning(
                self, "Geçersiz Katılımcı Sayısı",
                "1 ile 100000 arasında tam sayı giriniz."
            )
            return

        from datetime import time as _time

        araliklar = []

        for gun in self.oturum_verileri():
            bas = datetime.fromisoformat(
                gun["baslangic_zamani"]
            )
            bit = datetime.fromisoformat(
                gun["bitis_zamani"]
            )

            if not (
                bas.date() == bit.date()
                and _time(8, 0) <= bas.time()
                < bit.time() <= _time(18, 0)
            ):
                QMessageBox.warning(
                    self, "Geçersiz Oturum",
                    "Her oturum aynı gün içinde ve "
                    "08.00–18.00 arasında olmalıdır. "
                    "Bitiş saati başlangıçtan sonra gelmelidir."
                )
                return

            araliklar.append((bas, bit))

        araliklar.sort()

        if (
            araliklar[-1][1].date()
            - araliklar[0][0].date()
        ).days >= 366:
            QMessageBox.warning(
                self, "Geçersiz Süre",
                "İlk ve son oturum arasında en fazla "
                "366 gün olabilir."
            )
            return

        for onceki, sonraki in zip(araliklar, araliklar[1:]):
            if onceki[1] > sonraki[0]:
                QMessageBox.warning(
                    self, "Çakışan Oturumlar",
                    "Aynı etkinliğin oturumları "
                    "birbiriyle çakışamaz."
                )
                return

        self.accept()

    def veri(self):
        return {
            "oda_id": self.oda.currentData(),
            "organize_eden_personel_id": self.personel.currentData(),
            "etkinlik_adi": self.ad.text().strip(),
            "katilimci_sayisi": (
                int(self.katilimci.text().strip())
                if self.katilimci.text().strip() else None
            ),
            "gunler": self.oturum_verileri(),
        }





from PySide6.QtCore import QDate
from PySide6.QtWidgets import QFrame, QDateEdit, QGridLayout


class OdaEtkinlikleriEkrani(QWidget):
    # AUDIT_TARZI_ODA_ETKINLIKLERI_V1

    def __init__(self, api_url, token, parent=None):
        super().__init__(parent)

        self.api_url = api_url.rstrip("/")
        self.token = token
        self.etkinlikler = []
        self.gorunen = []
        self.odalar = []
        self.personeller = []
        self.yonetebilir = False

        self.setStyleSheet("""
            QWidget {
                font-family: Arial;
                color: #243653;
                font-size: 12px;
            }
            QFrame#kart {
                background: white;
                border: 1px solid #E3EAF5;
                border-radius: 11px;
            }
            QLineEdit, QComboBox {
                background: white;
                border: 1px solid #D0DDF0;
                border-radius: 8px;
                padding: 8px;
                min-height: 20px;
            }
            QLineEdit:focus, QComboBox:focus,
            QComboBox:focus {
                border: 1px solid #1763E9;
            }
            QPushButton {
                background: #F1F5FD;
                border: 1px solid #D1DFF3;
                border-radius: 8px;
                padding: 9px 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #E3EDFF;
            }
            QPushButton:disabled {
                background: #F4F6FA;
                color: #9BAAC0;
            }
            QPushButton#birincil {
                background: #0B5BF0;
                border: 1px solid #0B5BF0;
                color: white;
            }
            QPushButton#birincil:hover {
                background: #0048D4;
            }
            QTableWidget {
                background: white;
                border: 1px solid #E3EAF5;
                border-radius: 8px;
                gridline-color: #E3EAF5;
                selection-background-color: #DFEBFF;
                selection-color: #243653;
                alternate-background-color: #F8FAFE;
            }
            QHeaderView::section {
                background: #E7F0FF;
                color: #15315A;
                border: none;
                border-bottom: 1px solid #D1DFF0;
                padding: 11px 7px;
                font-weight: 700;
            }
        """)

        ana = QVBoxLayout(self)
        ana.setContentsMargins(18, 16, 18, 16)
        ana.setSpacing(15)

        # Başlık
        baslik = QLabel("Oda Etkinlikleri")
        baslik.setStyleSheet(
            "font-size: 23px; font-weight: 700; color: #203657;"
        )
        ana.addWidget(baslik)

        aciklama = QLabel(
            "Odalardaki etkinlikleri görüntüleyin ve yetkiniz varsa yönetin."
        )
        aciklama.setStyleSheet("color: #647895;")
        ana.addWidget(aciklama)

        # Arama ve filtreler
        filtreler = QHBoxLayout()
        filtreler.setSpacing(9)

        self.arama = QLineEdit()
        self.arama.setPlaceholderText(
            "Etkinlik adı, oda veya düzenleyen ara..."
        )
        self.arama.setClearButtonEnabled(True)
        filtreler.addWidget(self.arama, 3)

        filtreler.addWidget(QLabel("Durum:"))

        self.durum_filtre = QComboBox()
        self.durum_filtre.addItems([
            "Tümü",
            "Planlandı",
            "Devam Ediyor",
            "Tamamlandı",
            "İptal Edildi",
        ])
        filtreler.addWidget(self.durum_filtre, 1)

        filtreler.addWidget(QLabel("Dönem:"))

        self.donem = QComboBox()
        self.donem.addItems([
            "Tümü",
            "Bugün",
            "Bu Hafta",
            "Bu Ay",
            "Tarih Aralığı",
        ])
        filtreler.addWidget(self.donem, 1)

        self.filtre_btn = QPushButton("Filtrele")
        self.filtre_btn.setObjectName("birincil")

        self.temizle_btn = QPushButton("Filtreleri Temizle")
        self.ust_yenile_btn = QPushButton("Yenile")

        filtreler.addWidget(self.filtre_btn)
        filtreler.addWidget(self.temizle_btn)
        filtreler.addWidget(self.ust_yenile_btn)

        ana.addLayout(filtreler)

        # Tarih aralığı
        tarih_satiri = QHBoxLayout()
        tarih_satiri.addWidget(QLabel("Başlangıç:"))

        self.tarih_bas = QDateEdit()
        self.tarih_bas.setCalendarPopup(True)
        self.tarih_bas.setDisplayFormat("dd.MM.yyyy")
        self.tarih_bas.setFixedWidth(150)
        self.tarih_bas.setDate(QDate.currentDate().addDays(-7))
        self.tarih_bas.setEnabled(False)
        tarih_satiri.addWidget(self.tarih_bas)

        tarih_satiri.addWidget(QLabel("Bitiş:"))

        self.tarih_bit = QDateEdit()
        self.tarih_bit.setCalendarPopup(True)
        self.tarih_bit.setDisplayFormat("dd.MM.yyyy")
        self.tarih_bit.setFixedWidth(150)
        self.tarih_bit.setDate(QDate.currentDate())
        self.tarih_bit.setEnabled(False)
        tarih_satiri.addWidget(self.tarih_bit)


        tarih_satiri.addStretch()
        # DONEM_TARIHLERIN_SOLUNDA
        # Dönem seçimini mevcut satırından çıkar.
        for duzen in (filtreler, tarih_satiri):
            for indeks in reversed(range(duzen.count())):
                widget = duzen.itemAt(indeks).widget()

                if widget is self.donem:
                    duzen.removeWidget(widget)

                elif (
                    isinstance(widget, QLabel)
                    and widget.text().strip() == "Dönem:"
                ):
                    duzen.removeWidget(widget)
                    widget.deleteLater()

        # Dönem, Başlangıç ve Bitiş aynı satırda.
        self.donem.setFixedWidth(185)
        tarih_satiri.insertWidget(0, self.donem)
        tarih_satiri.insertWidget(0, QLabel("Dönem:"))

        ana.addLayout(tarih_satiri)

        # Dört özet kartı
        kartlar = QGridLayout()
        kartlar.setSpacing(12)

        self.ozet_degerleri = {}

        ozetler = [
            ("toplam", "Toplam Etkinlik", "#203657"),
            ("planlanan", "Planlanan", "#078346"),
            ("bugun", "Bugünkü Etkinlikler", "#075DE3"),
            ("iptal", "İptal Edilen", "#CB3347"),
        ]

        for sutun, (anahtar, yazi, renk) in enumerate(ozetler):
            kart = QFrame()
            kart.setObjectName("kart")

            dikey = QVBoxLayout(kart)
            dikey.setContentsMargins(16, 12, 16, 12)

            etiket = QLabel(yazi)
            etiket.setStyleSheet(
                "color: #6C809C; font-size: 12px;"
            )

            deger = QLabel("0")
            deger.setStyleSheet(
                f"color: {renk}; font-size: 25px; font-weight: bold;"
            )

            dikey.addWidget(etiket)
            dikey.addWidget(deger)

            kartlar.addWidget(kart, 0, sutun)
            self.ozet_degerleri[anahtar] = deger

        ana.addLayout(kartlar)

        # Ana liste kartı
        liste_karti = QFrame()
        liste_karti.setObjectName("kart")

        liste_duzen = QVBoxLayout(liste_karti)
        liste_duzen.setContentsMargins(15, 13, 15, 14)
        liste_duzen.setSpacing(12)

        liste_ust = QHBoxLayout()

        liste_baslik = QLabel("Etkinlik Listesi")
        liste_baslik.setStyleSheet(
            "font-size: 17px; font-weight: bold; color: #173257;"
        )
        liste_ust.addWidget(liste_baslik)
        liste_ust.addStretch()

        self.ekle_btn = QPushButton("＋ Yeni Etkinlik")
        self.ekle_btn.setObjectName("birincil")

        self.duzenle_btn = QPushButton("Düzenle")
        self.iptal_btn = QPushButton("İptal Et")

        for buton in (
            self.ekle_btn,
            self.duzenle_btn,
            self.iptal_btn,
        ):
            liste_ust.addWidget(buton)

        self.oturum_gor_btn = QPushButton("Oturumları Gör")
        liste_ust.addWidget(self.oturum_gor_btn)
        liste_duzen.addLayout(liste_ust)

        self.tablo = QTableWidget()
        self.tablo.setColumnCount(7)
        self.tablo.setHorizontalHeaderLabels([
            "Etkinlik",
            "Oda",
            "Düzenleyen",
            "Katılımcı",
            "Başlangıç",
            "Bitiş",
            "Durum",
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

        self.tablo.setAlternatingRowColors(True)
        self.tablo.verticalHeader().setVisible(False)
        self.tablo.verticalHeader().setDefaultSectionSize(43)

        basliklar = self.tablo.horizontalHeader()
        basliklar.setSectionResizeMode(
            QHeaderView.Stretch
        )
        basliklar.setStretchLastSection(True)
        self.tablo.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff
        )

        liste_duzen.addWidget(self.tablo, 1)

        ana.addWidget(liste_karti, 1)

        self.durum = QLabel("Toplam 0 etkinlik kaydı")
        self.durum.setStyleSheet("color: #647895;")
        ana.addWidget(self.durum)

        # Sinyaller
        self.ekle_btn.clicked.connect(self.ekle)
        self.duzenle_btn.clicked.connect(self.duzenle)
        self.iptal_btn.clicked.connect(self.iptal)
        self.oturum_gor_btn.clicked.connect(self.oturumlari_goster)

        self.ust_yenile_btn.clicked.connect(self.yenile)

        self.filtre_btn.clicked.connect(self.filtrele)
        self.temizle_btn.clicked.connect(self.filtreleri_temizle)
        self.arama.returnPressed.connect(self.filtrele)

        self.donem.currentTextChanged.connect(
            self.tarih_alanlarini_guncelle
        )
        self.tablo.itemSelectionChanged.connect(
            self.butonlari_guncelle
        )

        self.yenile()

    def istek(self, metot, yol, **kwargs):
        cevap = oturum_kontrollu_istek(
            metot,
            f"{self.api_url}{yol}",
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=15,
            **kwargs,
        )
        if oturum_hatasi_mi(cevap):
            return None
        if not cevap.ok:
            try:
                detay = cevap.json().get("detail")
            except ValueError:
                detay = None
            if isinstance(detay, (dict, list)):
                detay = str(detay)
            raise ValueError(
                detay or f"İşlem başarısız (HTTP {cevap.status_code})"
            )
        return cevap.json()


    def yenile(self):
        try:
            secenek = self.istek(
                "GET", "/api/oda-etkinlikleri/secenekler"
            )
            if secenek is None:
                return

            sonuc = self.istek(
                "GET", "/api/oda-etkinlikleri"
            )
            if sonuc is None:
                return

        except (requests.RequestException, ValueError) as hata:
            QMessageBox.warning(
                self, "Oda Etkinlikleri", str(hata)
            )
            return

        self.odalar = secenek.get("odalar", [])
        self.personeller = secenek.get("personeller", [])
        self.yonetebilir = bool(
            secenek.get("yonetebilir", False)
        )
        self.etkinlikler = sonuc.get("etkinlikler", [])

        self.ozet_guncelle()
        self.filtrele()

    def etkinlik_durumu(self, etkinlik, simdi=None):
        """Gerçek etkinlik oturumlarına göre durum hesapla."""
        if etkinlik.get("iptal_edildi_mi"):
            return "İptal Edildi"

        if simdi is None:
            simdi = datetime.now()
        simdi = simdi.replace(tzinfo=None)

        try:
            bas = datetime.fromisoformat(
                str(etkinlik["baslangic_zamani"])
            ).replace(tzinfo=None)
            bit = datetime.fromisoformat(
                str(etkinlik["bitis_zamani"])
            ).replace(tzinfo=None)
        except (ValueError, TypeError, KeyError):
            return "Planlandı"

        gunler = etkinlik.get("gunler")

        if gunler is not None:
            araliklar = []
            try:
                for gun in gunler:
                    ilk = datetime.fromisoformat(
                        str(gun["baslangic_zamani"])
                    ).replace(tzinfo=None)
                    son = datetime.fromisoformat(
                        str(gun["bitis_zamani"])
                    ).replace(tzinfo=None)

                    if ilk >= son:
                        return "Planlandı"

                    araliklar.append((ilk, son))
            except (ValueError, TypeError, KeyError):
                return "Planlandı"

            if not araliklar:
                return "Planlandı"

            if any(ilk <= simdi < son for ilk, son in araliklar):
                return "Devam Ediyor"

            if simdi >= max(son for _, son in araliklar):
                return "Tamamlandı"

            return "Planlandı"

        # Eski API yanıtlarında günlük kayıt listesi bulunmayabilir.
        if simdi < bas:
            return "Planlandı"
        if simdi >= bit:
            return "Tamamlandı"

        gunluk_bas = datetime.combine(simdi.date(), bas.time())
        gunluk_bit = datetime.combine(simdi.date(), bit.time())

        if gunluk_bas <= simdi < gunluk_bit:
            return "Devam Ediyor"

        return "Planlandı"



    def tarih_alanlarini_guncelle(self, *_):
        aktif = self.donem.currentText() == "Tarih Aralığı"
        self.tarih_bas.setEnabled(aktif)
        self.tarih_bit.setEnabled(aktif)

    def filtreleri_temizle(self):
        self.arama.clear()
        self.durum_filtre.setCurrentText("Tümü")
        self.donem.setCurrentText("Tümü")
        self.filtrele()

    def tarih_uygun(self, etkinlik):
        donem = self.donem.currentText()
        if donem == "Tümü":
            return True

        try:
            bas = datetime.fromisoformat(
                str(etkinlik["baslangic_zamani"])
            ).date()
            bit = datetime.fromisoformat(
                str(etkinlik["bitis_zamani"])
            ).date()
        except (ValueError, TypeError, KeyError):
            return False

        bugun = datetime.now().date()

        if donem == "Bugün":
            aralik_bas = bugun
            aralik_bit = bugun

        elif donem == "Bu Hafta":
            from datetime import timedelta
            aralik_bas = bugun - timedelta(
                days=bugun.weekday()
            )
            aralik_bit = aralik_bas + timedelta(days=6)

        elif donem == "Bu Ay":
            import calendar
            aralik_bas = bugun.replace(day=1)
            aralik_bit = bugun.replace(
                day=calendar.monthrange(
                    bugun.year, bugun.month
                )[1]
            )

        else:
            aralik_bas = self.tarih_bas.date().toPython()
            aralik_bit = self.tarih_bit.date().toPython()

            if aralik_bas > aralik_bit:
                return False

        # Artık etkinliğin tüm tarih aralığını değil,
        # gerçekten kaydedilen oturum günlerini dikkate al.
        gunler = etkinlik.get("gunler")

        if gunler is not None:
            for gun in gunler:
                try:
                    oturum_bas = datetime.fromisoformat(
                        str(gun["baslangic_zamani"])
                    ).date()
                    oturum_bit = datetime.fromisoformat(
                        str(gun["bitis_zamani"])
                    ).date()
                except (ValueError, TypeError, KeyError):
                    continue

                if (
                    oturum_bas <= aralik_bit
                    and oturum_bit >= aralik_bas
                ):
                    return True

            return False

        # Eski API yanıtları için geriye dönük uyumluluk.
        return bas <= aralik_bit and bit >= aralik_bas

    def ozet_guncelle(self):
        bugun = datetime.now().date()

        toplam = len(self.etkinlikler)
        planlanan = 0
        bugunku = 0
        iptal = 0

        for etkinlik in self.etkinlikler:
            durum = self.etkinlik_durumu(etkinlik)

            if durum == "Planlandı":
                planlanan += 1

            if durum == "İptal Edildi":
                iptal += 1
                continue

            try:
                bas = datetime.fromisoformat(
                    str(etkinlik["baslangic_zamani"])
                ).date()
                bit = datetime.fromisoformat(
                    str(etkinlik["bitis_zamani"])
                ).date()

                gunler = etkinlik.get("gunler")

                if gunler is not None:
                    if any(
                        datetime.fromisoformat(
                            str(g["baslangic_zamani"])
                        ).date() == bugun
                        for g in gunler
                    ):
                        bugunku += 1
                elif bas <= bugun <= bit:
                    bugunku += 1

            except (ValueError, TypeError, KeyError):
                pass

        self.ozet_degerleri["toplam"].setText(str(toplam))
        self.ozet_degerleri["planlanan"].setText(
            str(planlanan)
        )
        self.ozet_degerleri["bugun"].setText(
            str(bugunku)
        )
        self.ozet_degerleri["iptal"].setText(str(iptal))

    def filtrele(self):
        aranan = self.arama.text().strip().casefold()
        durum_filtre = self.durum_filtre.currentText()

        oda_adlari = {
            o["oda_id"]: o["oda_adi"]
            for o in self.odalar
        }
        personel_adlari = {
            p["personel_id"]: p["kullanici_adi"]
            for p in self.personeller
        }

        self.gorunen = []

        for e in self.etkinlikler:
            oda = (
                e.get("oda_adi")
                or oda_adlari.get(e["oda_id"], "")
            )
            personel = personel_adlari.get(
                e["organize_eden_personel_id"], ""
            )

            aranabilir = " ".join([
                str(e.get("etkinlik_adi") or ""),
                str(oda),
                str(personel),
            ]).casefold()

            if aranan and aranan not in aranabilir:
                continue

            durum = self.etkinlik_durumu(e)

            if (
                durum_filtre != "Tümü"
                and durum_filtre != durum
            ):
                continue

            if not self.tarih_uygun(e):
                continue

            self.gorunen.append(e)

        self.tablo.setRowCount(0)
        self.tablo.setRowCount(len(self.gorunen))

        for satir, e in enumerate(self.gorunen):
            oda = (
                e.get("oda_adi")
                or oda_adlari.get(e["oda_id"], "—")
            )
            personel = personel_adlari.get(
                e["organize_eden_personel_id"], "—"
            )
            durum = self.etkinlik_durumu(e)

            degerler = [
                e["etkinlik_adi"],
                oda,
                personel,
                (
                    str(e["katilimci_sayisi"])
                    if e.get("katilimci_sayisi") is not None
                    else "—"
                ),
                tarih_yaz(e["baslangic_zamani"]),
                tarih_yaz(e["bitis_zamani"]),
                durum,
            ]

            for sutun, deger in enumerate(degerler):
                oge = QTableWidgetItem(str(deger))
                oge.setData(
                    Qt.UserRole,
                    e["etkinlik_id"]
                )

                if sutun == 6:
                    from PySide6.QtGui import QColor

                    renkler = {
                        "Planlandı": "#078346",
                        "Devam Ediyor": "#075DE3",
                        "Tamamlandı": "#64748B",
                        "İptal Edildi": "#CB3347",
                    }
                    oge.setForeground(
                        QColor(renkler.get(durum, "#243653"))
                    )

                self.tablo.setItem(satir, sutun, oge)

        self.durum.setText(
            f"{len(self.etkinlikler)} kayıttan "
            f"{len(self.gorunen)} tanesi gösteriliyor."
        )
        self.butonlari_guncelle()

    @staticmethod
    def oturum_detay_metni(etkinlik):
        """Etkinliğe ait oturumları kronolojik sırada göster."""
        gunler = etkinlik.get("gunler") or []

        if not gunler:
            return (
                "Bu etkinlik için ayrı oturum bilgisi bulunamadı."
            )

        araliklar = []
        for gun in gunler:
            try:
                bas = datetime.fromisoformat(
                    str(gun["baslangic_zamani"])
                )
                bit = datetime.fromisoformat(
                    str(gun["bitis_zamani"])
                )
                araliklar.append((bas, bit))
            except (ValueError, TypeError, KeyError):
                continue

        if not araliklar:
            return "Geçerli oturum bilgisi bulunamadı."

        araliklar.sort(key=lambda aralik: aralik[0])

        satirlar = [
            f"Toplam {len(araliklar)} oturum"
        ]
        for sira, (bas, bit) in enumerate(araliklar, 1):
            satirlar.append(
                f"{sira}.  {bas:%d.%m.%Y}  "
                f"{bas:%H:%M}–{bit:%H:%M}"
            )

        return "\n".join(satirlar)


    def oturumlari_goster(self):
        etkinlik = self.secili()

        if not etkinlik:
            QMessageBox.warning(
                self,
                "Etkinlik Seçilmedi",
                "Önce tablodan bir etkinlik seçiniz."
            )
            return

        araliklar = []

        for gun in etkinlik.get("gunler") or []:
            try:
                bas = datetime.fromisoformat(
                    str(gun["baslangic_zamani"])
                )
                bit = datetime.fromisoformat(
                    str(gun["bitis_zamani"])
                )
            except (ValueError, TypeError, KeyError):
                continue

            if bas < bit:
                araliklar.append((bas, bit))

        araliklar.sort(key=lambda x: (x[0], x[1]))

        pencere = QDialog(self)
        pencere.setWindowTitle("Etkinlik Oturumları")
        pencere.resize(680, 440)
        pencere.setMinimumSize(520, 310)

        pencere.setStyleSheet("""
            QDialog {
                background: #F8FAFF;
                color: #243653;
            }
            QLabel#oturumBaslik {
                color: #203657;
                font-size: 19px;
                font-weight: 700;
            }
            QLabel#oturumOzet {
                color: #647895;
                font-size: 12px;
            }
            QTableWidget {
                background: white;
                color: #243653;
                alternate-background-color: #F5F8FE;
                gridline-color: #E3EAF5;
                border: 1px solid #D7E3F4;
                border-radius: 8px;
                font-size: 12px;
            }
            QHeaderView::section {
                background: #E7F0FF;
                color: #15315A;
                border: none;
                border-bottom: 1px solid #D1DFF0;
                padding: 10px 6px;
                font-weight: 700;
            }
            QPushButton {
                background: #EFF4FD;
                color: #243653;
                border: 1px solid #D1DDF0;
                border-radius: 8px;
                padding: 9px 22px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #DFEAFE;
            }
        """)

        duzen = QVBoxLayout(pencere)
        duzen.setContentsMargins(20, 18, 20, 18)
        duzen.setSpacing(12)

        baslik = QLabel(
            str(etkinlik.get("etkinlik_adi") or "Etkinlik")
        )
        baslik.setObjectName("oturumBaslik")
        duzen.addWidget(baslik)

        ozet = QLabel(f"Etkinlik Oturumları  |  {len(araliklar)} oturum")
        ozet.setObjectName("oturumOzet")
        duzen.addWidget(ozet)

        tablo = QTableWidget()
        tablo.setColumnCount(4)
        tablo.setHorizontalHeaderLabels([
            "No", "Tarih", "Başlangıç", "Bitiş"
        ])
        tablo.setRowCount(len(araliklar))

        tablo.setEditTriggers(
            QAbstractItemView.NoEditTriggers
        )
        tablo.setSelectionMode(
            QAbstractItemView.NoSelection
        )
        tablo.setAlternatingRowColors(True)
        tablo.verticalHeader().setVisible(False)
        tablo.verticalHeader().setDefaultSectionSize(42)
        tablo.setShowGrid(False)

        basliklar = tablo.horizontalHeader()
        basliklar.setSectionResizeMode(
            0, QHeaderView.ResizeToContents
        )

        for sutun in (1, 2, 3):
            basliklar.setSectionResizeMode(
                sutun, QHeaderView.Stretch
            )

        for i, (bas, bit) in enumerate(araliklar):
            degerler = (
                str(i + 1),
                bas.strftime("%d.%m.%Y"),
                bas.strftime("%H:%M"),
                bit.strftime("%H:%M"),
            )

            for sutun, deger in enumerate(degerler):
                oge = QTableWidgetItem(deger)
                oge.setTextAlignment(Qt.AlignCenter)
                tablo.setItem(i, sutun, oge)

        duzen.addWidget(tablo, 1)

        alt = QHBoxLayout()
        alt.addStretch()

        kapat = QPushButton("Kapat")
        kapat.setMinimumWidth(110)
        kapat.clicked.connect(pencere.accept)
        alt.addWidget(kapat)

        duzen.addLayout(alt)
        pencere.exec()


    def secili(self):
        satir = self.tablo.currentRow()

        if 0 <= satir < len(self.gorunen):
            return self.gorunen[satir]

        return None

    def butonlari_guncelle(self):
        secili = self.secili()
        aktif = bool(
            secili and not secili["iptal_edildi_mi"]
        )

        self.ekle_btn.setVisible(self.yonetebilir)
        self.duzenle_btn.setVisible(self.yonetebilir)
        self.iptal_btn.setVisible(self.yonetebilir)

        # Seçim olmasa da butonlar tıklanabilir.
        # Yetkisiz kullanıcılar için butonlar gizli kalır.
        self.duzenle_btn.setEnabled(self.yonetebilir)
        self.iptal_btn.setEnabled(self.yonetebilir)

    def ekle(self):
        dialog = OdaEtkinlikFormu(
            self.odalar, self.personeller, parent=self
        )
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            sonuc = self.istek(
                "POST", "/api/oda-etkinlikleri",
                json=dialog.veri(),
            )
            if sonuc is not None:
                self.yenile()
        except (requests.RequestException, ValueError) as hata:
            QMessageBox.warning(self, "Etkinlik Eklenemedi", str(hata))

    def duzenle(self):
        kayit = self.secili()
        if not kayit:
            QMessageBox.warning(
                self,
                "Etkinlik Seçilmedi",
                "Lütfen düzenlemek istediğiniz etkinliği seçin."
            )
            return

        if kayit["iptal_edildi_mi"]:
            QMessageBox.warning(
                self,
                "İşlem Yapılamaz",
                "İptal edilmiş etkinlik düzenlenemez."
            )
            return
        dialog = OdaEtkinlikFormu(
            self.odalar, self.personeller, kayit, self
        )
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            sonuc = self.istek(
                "PATCH",
                f"/api/oda-etkinlikleri/{kayit['etkinlik_id']}",
                json=dialog.veri(),
            )
            if sonuc is not None:
                self.yenile()
        except (requests.RequestException, ValueError) as hata:
            QMessageBox.warning(
                self, "Etkinlik Güncellenemedi", str(hata)
            )

    def iptal(self):
        kayit = self.secili()
        if not kayit:
            QMessageBox.warning(
                self,
                "Etkinlik Seçilmedi",
                "Lütfen iptal etmek istediğiniz etkinliği seçin."
            )
            return

        if kayit["iptal_edildi_mi"]:
            QMessageBox.warning(
                self,
                "İşlem Yapılamaz",
                "Bu etkinlik zaten iptal edilmiş."
            )
            return
        cevap = QMessageBox.question(
            self, "Etkinliği İptal Et",
            f"{kayit['etkinlik_adi']} etkinliği iptal edilsin mi?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if cevap != QMessageBox.Yes:
            return
        try:
            sonuc = self.istek(
                "PATCH",
                f"/api/oda-etkinlikleri/{kayit['etkinlik_id']}/iptal",
            )
            if sonuc is not None:
                self.yenile()
        except (requests.RequestException, ValueError) as hata:
            QMessageBox.warning(
                self, "Etkinlik İptal Edilemedi", str(hata)
            )
