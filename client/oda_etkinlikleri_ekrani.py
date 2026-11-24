"""TKYS Oda Etkinlikleri yönetim ekranı."""

import calendar
from datetime import datetime, time as saat_tipi, timedelta

import requests
from PySide6.QtCore import QDate, QTime, Qt
from PySide6.QtGui import QColor, QIntValidator
from PySide6.QtWidgets import (
    QWidget, QDialog, QVBoxLayout, QHBoxLayout,
    QFormLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QComboBox, QLineEdit, QLabel,
    QPushButton, QMessageBox, QDialogButtonBox, QAbstractItemView,
    QDateEdit, QTimeEdit, QScrollArea, QFrame, QGridLayout, QCheckBox,
)

from client.api_yoneticisi import (
    hata_detayi_metni,
    istek_hatasi_metni,
    oturum_kontrollu_istek,
    oturum_hatasi_mi,
)
from client.tablo_siralama import siralama_durumunu_al, siralamayi_geri_yukle, siralanabilir_yap
from client.sayfa_tema import (
    DurumRozetiDelegate, TABLO_STILI, dialog_stili, kart_olustur, liste_sayfasi_stili, ozet_karti_olustur,
)
from client.tablo_tasarimi import bos_mesaj_olustur


def tarih_yaz(deger):
    if not deger:
        return "—"
    try:
        return datetime.fromisoformat(str(deger)).strftime("%d.%m.%Y %H:%M")
    except ValueError:
        return str(deger)


GUN_ADLARI = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]
EN_FAZLA_OTURUM = 366


def tekrar_tarihleri(baslangic, bitis, hafta_gunleri):
    """baslangic..bitis (ikisi dahil) arasında, haftanın seçili günlerine (0=Pazartesi ... 6=Pazar) denk gelen tarihler."""
    gunler = set(hafta_gunleri)
    if bitis < baslangic or not gunler:
        return []
    sonuc = []
    gun = baslangic
    while gun <= bitis:
        if gun.weekday() in gunler:
            sonuc.append(gun)
        gun += timedelta(days=1)
    return sonuc


class TekrarliOturumDialog(QDialog):
    """Düzenli etkinlik için tarih aralığı + haftanın günleri + saat seçerek birçok oturumu tek seferde üretir."""

    def __init__(self, parent=None, baslangic=None):
        super().__init__(parent)
        self.setWindowTitle("Tekrarlı Oturum Ekle")
        self.setMinimumWidth(560)
        self.setStyleSheet(dialog_stili())

        ana = QVBoxLayout(self)
        ana.setContentsMargins(22, 20, 22, 18)
        ana.setSpacing(12)

        baslik = QLabel("Düzenli oturumları tek seferde ekleyin")
        baslik.setObjectName("formBaslik")
        bilgi = QLabel(
            "Tarih aralığını, haftanın hangi günlerinde yapılacağını ve saati seçin. Oturumlar listeye eklenir; "
            "istediğinizi sonra tek tek değiştirebilir ya da kaldırabilirsiniz."
        )
        bilgi.setObjectName("ipucu")
        bilgi.setWordWrap(True)
        ana.addWidget(baslik)
        ana.addWidget(bilgi)

        ilk = baslangic or QDate.currentDate()
        self.bas_tarih = QDateEdit(ilk)
        self.bas_tarih.setCalendarPopup(True)
        self.bas_tarih.setDisplayFormat("dd.MM.yyyy")
        self.bit_tarih = QDateEdit(ilk.addDays(27))                       # varsayılan: 4 hafta
        self.bit_tarih.setCalendarPopup(True)
        self.bit_tarih.setDisplayFormat("dd.MM.yyyy")

        tarih_satiri = QHBoxLayout()
        tarih_satiri.setSpacing(10)
        tarih_satiri.addWidget(QLabel("İlk gün"))
        tarih_satiri.addWidget(self.bas_tarih, 1)
        tarih_satiri.addSpacing(8)
        tarih_satiri.addWidget(QLabel("Son gün"))
        tarih_satiri.addWidget(self.bit_tarih, 1)
        ana.addLayout(tarih_satiri)

        gun_satiri = QHBoxLayout()
        gun_satiri.setSpacing(8)
        gun_satiri.addWidget(QLabel("Günler"))
        self.gun_kutulari = []
        for sira, ad in enumerate(GUN_ADLARI):
            kutu = QCheckBox(ad)
            kutu.setChecked(sira == ilk.dayOfWeek() - 1)                    # Qt: Pazartesi=1 ... Pazar=7
            kutu.toggled.connect(self.guncelle)
            self.gun_kutulari.append(kutu)
            gun_satiri.addWidget(kutu)
        gun_satiri.addStretch()
        self.hafta_ici_btn = QPushButton("Hafta içi")
        self.hafta_ici_btn.setToolTip("Pazartesi–Cuma günlerini seç")
        self.hafta_ici_btn.clicked.connect(lambda _=False: self.hafta_ici_sec())
        gun_satiri.addWidget(self.hafta_ici_btn)
        ana.addLayout(gun_satiri)

        self.saat_bas = QTimeEdit(QTime(13, 0))
        self.saat_bas.setDisplayFormat("HH:mm")
        self.saat_bit = QTimeEdit(QTime(14, 0))
        self.saat_bit.setDisplayFormat("HH:mm")
        saat_satiri = QHBoxLayout()
        saat_satiri.setSpacing(10)
        saat_satiri.addWidget(QLabel("Saat"))
        saat_satiri.addWidget(self.saat_bas, 1)
        saat_satiri.addWidget(QLabel("–"))
        saat_satiri.addWidget(self.saat_bit, 1)
        saat_satiri.addStretch(2)
        ana.addLayout(saat_satiri)

        self.onizleme = QLabel("")
        self.onizleme.setObjectName("onizleme")
        self.hata = QLabel("")
        self.hata.setObjectName("hata")
        self.hata.setWordWrap(True)
        ana.addWidget(self.onizleme)
        ana.addWidget(self.hata)

        dugmeler = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.ekle_btn = dugmeler.button(QDialogButtonBox.Ok)
        self.ekle_btn.setText("Oturumları Ekle")
        self.ekle_btn.setObjectName("birincil")
        dugmeler.button(QDialogButtonBox.Cancel).setText("Vazgeç")
        dugmeler.accepted.connect(self.accept)
        dugmeler.rejected.connect(self.reject)
        ana.addWidget(dugmeler)

        for alan in (self.bas_tarih, self.bit_tarih):
            alan.dateChanged.connect(self.guncelle)
        for alan in (self.saat_bas, self.saat_bit):
            alan.timeChanged.connect(self.guncelle)
        self.guncelle()

    def hafta_ici_sec(self):
        for sira, kutu in enumerate(self.gun_kutulari):
            kutu.setChecked(sira < 5)

    def secili_gunler(self):
        return [sira for sira, kutu in enumerate(self.gun_kutulari) if kutu.isChecked()]

    def tarihler(self):
        return tekrar_tarihleri(self.bas_tarih.date().toPython(), self.bit_tarih.date().toPython(), self.secili_gunler())

    def denetle(self):
        """(uygun_mu, hata_metni, tarihler)."""
        bas, bit = self.bas_tarih.date().toPython(), self.bit_tarih.date().toPython()
        if bit < bas:
            return False, "Son gün, ilk günden önce olamaz.", []
        if (bit - bas).days >= EN_FAZLA_OTURUM:
            return False, f"İlk ve son gün arasında en fazla {EN_FAZLA_OTURUM} gün olabilir.", []
        if not self.secili_gunler():
            return False, "En az bir gün seçin.", []
        if not (saat_tipi(8, 0) <= self.saat_bas.time().toPython() < self.saat_bit.time().toPython() <= saat_tipi(18, 0)):
            return False, "Saatler 08.00–18.00 arasında olmalı ve bitiş başlangıçtan sonra gelmelidir.", []
        tarihler = self.tarihler()
        if not tarihler:
            return False, "Seçtiğiniz aralıkta, seçtiğiniz günlere denk gelen tarih yok.", []
        return True, "", tarihler

    def guncelle(self, *_):
        uygun, hata, tarihler = self.denetle()
        self.hata.setText(hata)
        self.hata.setVisible(bool(hata))
        if uygun:
            self.onizleme.setText(
                f"{len(tarihler)} oturum eklenecek  ·  ilk: {tarihler[0].strftime('%d.%m.%Y')}  ·  son: {tarihler[-1].strftime('%d.%m.%Y')}"
            )
        else:
            self.onizleme.setText("Eklenecek oturum yok")
        self.ekle_btn.setEnabled(uygun)

    def sonuc(self):
        """(tarihler, başlangıç saati, bitiş saati)."""
        return self.tarihler(), self.saat_bas.time(), self.saat_bit.time()


class OdaEtkinlikFormu(QDialog):
    """Tek etkinliğe birden fazla bağımsız oturum ekleme formu."""

    def __init__(self, odalar, personeller, kayit=None, parent=None):
        super().__init__(parent)
        self.kayit_modu = bool(kayit)

        self.setWindowTitle(
            "Etkinlik Düzenle" if kayit else "Yeni Oda Etkinliği"
        )
        self.resize(720, 600)
        self.setMinimumWidth(640)

        self.setStyleSheet(dialog_stili())

        ana = QVBoxLayout(self)
        ana.setContentsMargins(22, 20, 22, 18)
        ana.setSpacing(12)

        form = QFormLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)

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
        baslik.setObjectName("formBaslik")
        ana.addWidget(baslik)

        bilgi = QLabel(
            "Her oturum için tarih ve saat seçiniz. "
            "Oda yalnızca eklenen günlerde ve saatlerde ayrılır. "
            "Çalışma saatleri: 08.00–18.00."
        )
        bilgi.setWordWrap(True)
        bilgi.setObjectName("ipucu")
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

        ekle_satiri = QHBoxLayout()
        ekle_satiri.setSpacing(10)
        self.gun_ekle_btn = QPushButton("＋  Gün / Saat Ekle")
        self.gun_ekle_btn.setToolTip("Tek bir oturum satırı ekle")
        self.gun_ekle_btn.clicked.connect(lambda _=False: self.oturum_ekle())
        self.tekrarli_btn = QPushButton("⟳  Tekrarlı Ekle…")
        self.tekrarli_btn.setToolTip("Tarih aralığı, haftanın günleri ve saati seçerek düzenli oturumları tek seferde ekle")
        self.tekrarli_btn.clicked.connect(lambda _=False: self.tekrarli_ekle())
        ekle_satiri.addWidget(self.gun_ekle_btn, 1)
        ekle_satiri.addWidget(self.tekrarli_btn, 1)
        ana.addLayout(ekle_satiri)

        if kayit:
            # Etkinliğin odası ya da düzenleyeni seçeneklerde yoksa (Admin düzenleyen, sonradan psikoloğa atanan oda)
            # kutu boş kalmasın; mevcut değer listeye eklenir ve seçili gelir.
            if self.oda.findData(kayit["oda_id"]) < 0:
                self.oda.addItem(str(kayit.get("oda_adi") or "—"), kayit["oda_id"])
            if self.personel.findData(kayit["organize_eden_personel_id"]) < 0:
                self.personel.addItem(
                    str(kayit.get("duzenleyen_adi") or "—"), kayit["organize_eden_personel_id"]
                )
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

            for gun in kayit.get("gunler") or [{}]:                 # günü olmayan kayıtta bir boş oturum satırı açılır
                self.oturum_ekle(
                    gun.get("baslangic_zamani"),
                    gun.get("bitis_zamani"),
                )
        else:
            self.oturum_ekle()

        dugmeler = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        dugmeler.button(QDialogButtonBox.Save).setText("Kaydet")
        dugmeler.button(QDialogButtonBox.Save).setObjectName("birincil")
        dugmeler.button(QDialogButtonBox.Cancel).setText("Vazgeç")
        dugmeler.accepted.connect(self.kaydet)
        dugmeler.rejected.connect(self.reject)
        ana.addWidget(dugmeler)

    def oturum_ekle(self, baslangic=None, bitis=None):
        if len(self.oturum_satirlari) >= EN_FAZLA_OTURUM:
            QMessageBox.warning(
                self, "Oturum Sınırı",
                f"En fazla {EN_FAZLA_OTURUM} oturum eklenebilir."
            )
            return

        cerceve = QFrame()
        cerceve.setObjectName("oturumSatiri")

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
        kaldir.setObjectName("tehlike")
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

    def _varsayilan_satir_mi(self, satir):
        """Yeni etkinlik formunun kendiliğinden açtığı, hiç değiştirilmemiş ilk satır mı (bugün 13:00–14:00)."""
        _, tarih, saat_bas, saat_bit = satir
        return (tarih.date() == QDate.currentDate() and saat_bas.time() == QTime(13, 0) and saat_bit.time() == QTime(14, 0))

    def tekrarli_ekle(self):
        pencere = TekrarliOturumDialog(self)
        if pencere.exec() == QDialog.Accepted:
            self.tekrarli_oturumlari_ekle(*pencere.sonuc())

    def tekrarli_oturumlari_ekle(self, tarihler, saat_bas, saat_bit):
        """Verilen günlerin her birine aynı saatlerde oturum ekler; aynı gün ve saatte zaten var olan oturum tekrar eklenmez.

        Yeni formun kendiliğinden açtığı, değiştirilmemiş ilk satır (bugün 13:00–14:00) üretilen oturumlarla değiştirilir.
        Döner: eklenen oturum sayısı."""
        bas_metin = saat_bas.toString("HH:mm")
        bit_metin = saat_bit.toString("HH:mm")
        mevcut = {
            (t.date().toPython(), sb.time().toString("HH:mm"), sbit.time().toString("HH:mm"))
            for _, t, sb, sbit in self.oturum_satirlari
        }
        yeni = [gun for gun in tarihler if (gun, bas_metin, bit_metin) not in mevcut]
        if not yeni:
            QMessageBox.information(self, "Tekrarlı Oturum", "Seçilen oturumların hepsi listede zaten var.")
            return 0

        silinecek = None
        if not self.kayit_modu and len(self.oturum_satirlari) == 1 and self._varsayilan_satir_mi(self.oturum_satirlari[0]):
            silinecek = self.oturum_satirlari[0]
        if len(self.oturum_satirlari) - (1 if silinecek else 0) + len(yeni) > EN_FAZLA_OTURUM:
            QMessageBox.warning(
                self, "Oturum Sınırı",
                f"En fazla {EN_FAZLA_OTURUM} oturum eklenebilir; seçiminiz bu sınırı aşıyor."
            )
            return 0

        if silinecek is not None:
            self.oturum_satirlari.remove(silinecek)
            self.oturum_duzeni.removeWidget(silinecek[0])
            silinecek[0].deleteLater()
        for gun in yeni:
            self.oturum_ekle(f"{gun.isoformat()}T{bas_metin}:00", f"{gun.isoformat()}T{bit_metin}:00")
        return len(yeni)

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
                and saat_tipi(8, 0) <= bas.time()
                < bit.time() <= saat_tipi(18, 0)
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
        self.toplam_kayit = 0                 # sunucudaki toplam etkinlik (liste kısaltıldıysa yüklenenden büyük olur)

        self.setStyleSheet(liste_sayfasi_stili())

        ana = QVBoxLayout(self)
        ana.setContentsMargins(24, 20, 24, 18)
        ana.setSpacing(16)

        # Başlık ve ana işlem
        ust = QHBoxLayout()
        ust.setSpacing(16)
        basliklar = QVBoxLayout()
        basliklar.setSpacing(3)
        baslik = QLabel("Oda Etkinlikleri")
        baslik.setObjectName("baslik")
        aciklama = QLabel("Odalardaki etkinlikleri görüntüleyin ve yetkiniz varsa yönetin.")
        aciklama.setObjectName("altBaslik")
        basliklar.addWidget(baslik)
        basliklar.addWidget(aciklama)
        ust.addLayout(basliklar, 1)

        self.ekle_btn = QPushButton("＋  Yeni Etkinlik")
        self.ekle_btn.setObjectName("birincil")
        self.ekle_btn.setCursor(Qt.PointingHandCursor)
        self.ekle_btn.setMinimumHeight(40)
        ust.addWidget(self.ekle_btn, 0, Qt.AlignTop)
        ana.addLayout(ust)

        # Arama ve süzgeçler (değiştikçe liste kendiliğinden süzülür)
        filtre_karti = kart_olustur()
        filtre_duzen = QVBoxLayout(filtre_karti)
        filtre_duzen.setContentsMargins(16, 12, 16, 12)
        filtre_duzen.setSpacing(10)
        filtreler = QHBoxLayout()
        filtreler.setSpacing(10)
        filtre_duzen.addLayout(filtreler)

        self.arama = QLineEdit()
        self.arama.setPlaceholderText("Etkinlik, oda veya kişi ara...")
        self.arama.setClearButtonEnabled(True)
        self.arama.setMinimumWidth(220)
        filtreler.addWidget(self.arama, 3)

        self.durum_filtre = QComboBox()
        self.durum_filtre.addItems(["Tümü", "Planlandı", "Devam Ediyor", "Tamamlandı", "İptal Edildi"])
        self.donem = QComboBox()
        self.donem.addItems(["Tümü", "Bugün", "Bu Hafta", "Bu Ay", "Tarih Aralığı"])

        durum_etiketi = QLabel("Durum")
        durum_etiketi.setObjectName("etiket")
        donem_etiketi = QLabel("Dönem")
        donem_etiketi.setObjectName("etiket")
        filtreler.addWidget(durum_etiketi)
        filtreler.addWidget(self.durum_filtre, 1)
        filtreler.addWidget(donem_etiketi)
        filtreler.addWidget(self.donem, 1)

        # Başlangıç/bitiş yalnızca "Tarih Aralığı" seçilince, kartın ikinci satırında görünür (üst satır sıkışmasın)
        self.tarih_alani = QWidget()
        tarih_satiri = QHBoxLayout(self.tarih_alani)
        tarih_satiri.setContentsMargins(0, 0, 0, 0)
        tarih_satiri.setSpacing(10)
        self.tarih_bas = QDateEdit()
        self.tarih_bas.setCalendarPopup(True)
        self.tarih_bas.setDisplayFormat("dd.MM.yyyy")
        self.tarih_bas.setMinimumWidth(160)
        self.tarih_bas.setDate(QDate.currentDate().addDays(-7))
        self.tarih_bit = QDateEdit()
        self.tarih_bit.setCalendarPopup(True)
        self.tarih_bit.setDisplayFormat("dd.MM.yyyy")
        self.tarih_bit.setMinimumWidth(160)
        self.tarih_bit.setDate(QDate.currentDate())
        bas_etiketi = QLabel("Başlangıç")
        bas_etiketi.setObjectName("etiket")
        bit_etiketi = QLabel("Bitiş")
        bit_etiketi.setObjectName("etiket")
        tarih_satiri.addWidget(bas_etiketi)
        tarih_satiri.addWidget(self.tarih_bas)
        tarih_satiri.addSpacing(8)
        tarih_satiri.addWidget(bit_etiketi)
        tarih_satiri.addWidget(self.tarih_bit)
        tarih_satiri.addStretch()
        self.tarih_alani.setVisible(False)

        self.temizle_btn = QPushButton("Temizle")
        self.temizle_btn.setObjectName("hayalet")
        self.temizle_btn.setToolTip("Arama ve süzgeçleri sıfırla")
        self.ust_yenile_btn = QPushButton("⟳  Yenile")
        self.ust_yenile_btn.setObjectName("hayalet")
        self.ust_yenile_btn.setToolTip("Etkinlikleri sunucudan yeniden yükle")
        filtreler.addWidget(self.temizle_btn)
        filtreler.addWidget(self.ust_yenile_btn)
        filtre_duzen.addWidget(self.tarih_alani)
        ana.addWidget(filtre_karti)

        # Dört özet kartı
        kartlar = QGridLayout()
        kartlar.setSpacing(16)
        self.ozet_degerleri = {}
        ozetler = [
            ("toplam", "Toplam Etkinlik", "#1D4ED8"),
            ("planlanan", "Planlanan", "#0E9F6E"),
            ("bugun", "Bugünkü Etkinlikler", "#D97706"),
            ("iptal", "İptal Edilen", "#DC2626"),
        ]
        for sutun, (anahtar, yazi, renk) in enumerate(ozetler):
            kart, deger = ozet_karti_olustur(yazi, renk)
            kartlar.addWidget(kart, 0, sutun)
            kartlar.setColumnStretch(sutun, 1)
            self.ozet_degerleri[anahtar] = deger
        ana.addLayout(kartlar)

        # Ana liste kartı
        liste_karti = kart_olustur()
        liste_duzen = QVBoxLayout(liste_karti)
        liste_duzen.setContentsMargins(20, 18, 20, 14)
        liste_duzen.setSpacing(14)

        liste_ust = QHBoxLayout()
        liste_ust.setSpacing(10)
        liste_baslik = QLabel("Etkinlik Listesi")
        liste_baslik.setObjectName("kartBaslik")
        liste_ust.addWidget(liste_baslik)
        self.sayac_rozeti = QLabel("0 etkinlik")
        self.sayac_rozeti.setObjectName("rozet")
        liste_ust.addWidget(self.sayac_rozeti)
        liste_ust.addStretch()

        self.duzenle_btn = QPushButton("Düzenle")
        self.duzenle_btn.setObjectName("hayalet")
        self.iptal_btn = QPushButton("İptal Et")
        self.iptal_btn.setObjectName("tehlike")
        self.oturum_gor_btn = QPushButton("Oturumları Gör")
        self.oturum_gor_btn.setObjectName("hayalet")
        for buton in (self.duzenle_btn, self.iptal_btn, self.oturum_gor_btn):
            buton.setCursor(Qt.PointingHandCursor)
            liste_ust.addWidget(buton)
        liste_duzen.addLayout(liste_ust)

        self.tablo = QTableWidget()
        self.tablo.setColumnCount(7)
        self.tablo.setHorizontalHeaderLabels(["ETKİNLİK", "ODA", "DÜZENLEYEN", "KATILIMCI", "BAŞLANGIÇ", "BİTİŞ", "DURUM"])
        self.tablo.setStyleSheet(TABLO_STILI)
        self.tablo.setShowGrid(False)
        self.tablo.setFrameShape(QFrame.NoFrame)
        self.tablo.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tablo.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tablo.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tablo.setFocusPolicy(Qt.NoFocus)
        self.tablo.setWordWrap(False)                                     # uzun ad tek satırda "…" ile kısalır; tam metin ipucunda
        self.tablo.setMouseTracking(True)
        self.tablo.verticalHeader().setVisible(False)
        self.tablo.verticalHeader().setDefaultSectionSize(52)
        self.tablo.setItemDelegateForColumn(6, DurumRozetiDelegate(parent=self.tablo))

        # Etkinlik adı ve oda adı kalan genişliği paylaşır (uzun oda adı iki satıra bölünmesin); diğerleri içeriğine göre boyutlanır.
        sutun_basliklari = self.tablo.horizontalHeader()
        sutun_basliklari.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        sutun_basliklari.setSectionResizeMode(QHeaderView.ResizeToContents)
        sutun_basliklari.setSectionResizeMode(0, QHeaderView.Stretch)
        sutun_basliklari.setSectionResizeMode(1, QHeaderView.Stretch)
        sutun_basliklari.setMinimumSectionSize(110)
        self.tablo.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        siralanabilir_yap(self.tablo)

        liste_duzen.addWidget(self.tablo, 1)
        self.bos_mesaj = bos_mesaj_olustur("Henüz oda etkinliği yok.")
        self.bos_mesaj.setObjectName("bosMesaj")
        self.bos_mesaj.setStyleSheet("")                                  # ortak tema (liste_sayfasi_stili) belirler
        liste_duzen.addWidget(self.bos_mesaj, 1)

        self.durum = QLabel("Toplam 0 etkinlik kaydı")
        self.durum.setObjectName("altBilgi")
        liste_duzen.addWidget(self.durum)
        ana.addWidget(liste_karti, 1)

        # Sinyaller
        self.ekle_btn.clicked.connect(self.ekle)
        self.duzenle_btn.clicked.connect(self.duzenle)
        self.iptal_btn.clicked.connect(self.iptal)
        self.oturum_gor_btn.clicked.connect(self.oturumlari_goster)
        self.ust_yenile_btn.clicked.connect(self.yenile)
        self.temizle_btn.clicked.connect(self.filtreleri_temizle)

        # Arama ve süzgeçler değiştikçe liste anında süzülür (veri zaten yüklü olduğu için sunucuya gidilmez).
        self.arama.textChanged.connect(self.filtrele)
        self.durum_filtre.currentTextChanged.connect(self.filtrele)
        self.donem.currentTextChanged.connect(self.tarih_alanlarini_guncelle)
        self.donem.currentTextChanged.connect(self.filtrele)
        self.tarih_bas.dateChanged.connect(self.filtrele)
        self.tarih_bit.dateChanged.connect(self.filtrele)
        self.tablo.itemSelectionChanged.connect(self.butonlari_guncelle)
        self.tablo.itemDoubleClicked.connect(lambda _oge: self.oturumlari_goster())

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
            # Sunucunun Türkçe açıklaması gösterilir (liste/sözlük biçimindeki ayrıntılar da okunur metne çevrilir).
            raise ValueError(
                hata_detayi_metni(cevap, f"İşlem tamamlanamadı (HTTP {cevap.status_code}).")
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
                self, "Oda Etkinlikleri", istek_hatasi_metni(hata)
            )
            return

        self.odalar = secenek.get("odalar", [])
        self.personeller = secenek.get("personeller", [])
        self.yonetebilir = bool(
            secenek.get("yonetebilir", False)
        )
        self.etkinlikler = sonuc.get("etkinlikler", [])
        self.toplam_kayit = sonuc.get("toplam", len(self.etkinlikler)) if sonuc.get("kesildi") else len(self.etkinlikler)

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
        self.tarih_alani.setVisible(self.donem.currentText() == "Tarih Aralığı")

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
            aralik_bas = bugun - timedelta(
                days=bugun.weekday()
            )
            aralik_bit = aralik_bas + timedelta(days=6)

        elif donem == "Bu Ay":
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

        # Yenileme/süzme sonrası kullanıcının sıralaması ve seçili etkinliği korunur.
        secili_kayit = self.secili()
        secili_id = secili_kayit["etkinlik_id"] if secili_kayit else None
        siralama = siralama_durumunu_al(self.tablo)

        self.gorunen = []

        for e in self.etkinlikler:
            oda = (
                e.get("oda_adi")
                or oda_adlari.get(e["oda_id"], "")
            )
            personel = (
                e.get("duzenleyen_adi")
                or personel_adlari.get(e["organize_eden_personel_id"], "")
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
            personel = (
                e.get("duzenleyen_adi")
                or personel_adlari.get(e["organize_eden_personel_id"], "—")
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

                if sutun in (0, 1, 2):
                    oge.setToolTip(str(deger))
                if sutun == 0:
                    yazi_tipi = oge.font()
                    yazi_tipi.setBold(True)
                    oge.setFont(yazi_tipi)                      # etkinlik adı satırın ana bilgisi
                if sutun == 3:
                    oge.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                if durum == "İptal Edildi" and sutun < 6:
                    oge.setForeground(QColor("#8A9BC0"))        # iptal edilen etkinliğin satırı soluk görünür (durum etiketi kırmızı kalır)
                elif sutun in (1, 2, 4, 5):
                    oge.setForeground(QColor("#3B4C6B"))

                self.tablo.setItem(satir, sutun, oge)

        siralamayi_geri_yukle(self.tablo, siralama)
        if secili_id is not None:
            # Sıralamadan sonra satır sırası değişir; seçim etkinlik kimliğiyle geri getirilir.
            for satir in range(self.tablo.rowCount()):
                hucre = self.tablo.item(satir, 0)
                if hucre is not None and hucre.data(Qt.UserRole) == secili_id:
                    self.tablo.selectRow(satir)
                    break

        bos = not self.gorunen
        self.tablo.setVisible(not bos)
        self.bos_mesaj.setVisible(bos)
        self.bos_mesaj.setText(
            "Henüz oda etkinliği yok." if not self.etkinlikler else "Aramaya ve süzgeçlere uyan etkinlik yok."
        )

        self.sayac_rozeti.setText(f"{len(self.gorunen)} etkinlik")
        metin = f"{len(self.etkinlikler)} kayıttan {len(self.gorunen)} tanesi gösteriliyor."
        if self.toplam_kayit > len(self.etkinlikler):
            metin += (
                f" Toplam {self.toplam_kayit} etkinlik var; yalnızca en yeni {len(self.etkinlikler)} tanesi yüklendi."
            )
        self.durum.setText(metin)
        self.butonlari_guncelle()

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
        # Tablo başlıktan sıralanabildiği için satır sırası liste sırasıyla aynı olmayabilir; etkinlik kimliğiyle bulunur.
        hucre = self.tablo.item(self.tablo.currentRow(), 0)
        if hucre is None:
            return None
        kimlik = hucre.data(Qt.UserRole)
        return next((e for e in self.gorunen if e["etkinlik_id"] == kimlik), None)

    def butonlari_guncelle(self):
        self.ekle_btn.setVisible(self.yonetebilir)
        self.duzenle_btn.setVisible(self.yonetebilir)
        self.iptal_btn.setVisible(self.yonetebilir)

        # Yetkisiz kullanıcılar için düğmeler gizli kalır; yetkili kullanıcıda seçime ve etkinliğin durumuna göre açılır.
        kayit = self.secili()
        islenebilir = bool(kayit) and not kayit.get("iptal_edildi_mi")
        self.duzenle_btn.setEnabled(self.yonetebilir and islenebilir)
        self.iptal_btn.setEnabled(self.yonetebilir and islenebilir)
        self.oturum_gor_btn.setEnabled(bool(kayit))

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
            QMessageBox.warning(self, "Etkinlik Eklenemedi", istek_hatasi_metni(hata))

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
                self, "Etkinlik Güncellenemedi", istek_hatasi_metni(hata)
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
                self, "Etkinlik İptal Edilemedi", istek_hatasi_metni(hata)
            )
