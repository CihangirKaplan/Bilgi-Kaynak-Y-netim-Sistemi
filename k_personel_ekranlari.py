import requests
from gecici_parola_dialog import GeciciParolaDialog
from datetime import datetime
from api_yoneticisi import (
    oturum_kontrollu_istek,
    oturum_hatasi_mi,
)
from PySide6.QtWidgets import (
    QWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView
)

from PySide6.QtCore import Qt, QRegularExpression, QTimer
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QHBoxLayout,
                               QLineEdit, QComboBox, QPushButton, QMessageBox,
                               QListWidget, QListWidgetItem, QLabel, QFrame,QScrollArea)


def kayit_tarihi_bicimle(deger):
    """Kayıt tarihini GG.AA.YYYY biçiminde göster."""
    if not deger:
        return "—"
    try:
        tarih = datetime.fromisoformat(
            str(deger).replace("Z", "+00:00")
        )
        return tarih.strftime("%d.%m.%Y")
    except (ValueError, TypeError):
        return str(deger)


class KullaniciPersonelEkrani(QWidget):
    def __init__(self, api_url, token):
        super().__init__()
        self.api_url = api_url
        self.token = token
        
        self.arayuzu_kur()
        self.verileri_cek()

    def arayuzu_kur(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 1. PAROLA SIFIRLAMA TALEPLERİ: yalnızca bekleyen talep varsa ve kullanıcının yetkisi varsa görünür.
        self.talep_paneli = QFrame()
        self.talep_paneli.setObjectName("talepPaneli")
        self.talep_paneli.setStyleSheet(
            "QFrame#talepPaneli { background: #EFF6FF; border: 1px solid #BFDBFE; border-radius: 14px; }")
        self.talep_lay = QVBoxLayout(self.talep_paneli)
        self.talep_lay.setContentsMargins(18, 14, 18, 14)
        self.talep_lay.setSpacing(8)
        self.talep_paneli.hide()
        layout.addWidget(self.talep_paneli)

        # 2. TABLO (Kart görünümü için çerçeve)
        ik = QFrame()
        ik.setStyleSheet("background: white; border-radius: 16px;")
        il = QVBoxLayout(ik)

        self.tablo = QTableWidget()
        self.tablo.setColumnCount(6)
        self.tablo.setHorizontalHeaderLabels([
            "Personel ID", "Kullanıcı Adı", "Personel Kodu", "Rolü", "Durum", "Kayıt Tarihi"
        ])
        
        self.tablo.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tablo.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tablo.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tablo.setStyleSheet("""
            QTableWidget {
                background-color: white;
                border: 1px solid #D0D7E5;
                border-radius: 8px;
                gridline-color: #E2E8F0;
            }
            QHeaderView::section {
                background-color: #0A1F5C;
                color: white;
                font-weight: bold;
                padding: 10px;
                border: none;
            }
        """)

        il.addWidget(self.tablo)
        layout.addWidget(ik)

    def verileri_cek(self):
        self.talepleri_yukle()
        headers = {"Authorization": f"Bearer {self.token}"}
        url = f"{self.api_url}/api/personel"

        try:
            cevap = oturum_kontrollu_istek("GET", url, headers=headers, timeout=5)
            if oturum_hatasi_mi(cevap):
                return
            if cevap.status_code == 200:
                personeller = cevap.json()
                self.tablo.setRowCount(len(personeller))

                for satir, p in enumerate(personeller):
                    durum = "🟢 Aktif" if p["aktif_mi"] else "🔴 Pasif"
                    tarih = kayit_tarihi_bicimle(p.get("olusturulma_tarihi"))

                    item_id = QTableWidgetItem(str(p["personel_id"]))
                    item_ad = QTableWidgetItem(p["kullanici_adi"])
                    item_ad.setData(Qt.UserRole, p["kullanici_id"])  # YENİ: ID'yi arka planda saklıyoruz
                    item_kod = QTableWidgetItem(p["personel_kodu"])
                    item_rol = QTableWidgetItem(p.get("gorunen_ad") or p["rol_adi"])
                    item_rol.setData(Qt.UserRole, p["rol_adi"])  # karşılaştırmalar kodla yapılır, ekranda görünen ad gösterilir
                    item_durum = QTableWidgetItem(durum)
                    item_tarih = QTableWidgetItem(tarih)

                    for item in [item_id, item_ad, item_kod, item_rol, item_durum, item_tarih]:
                        item.setTextAlignment(Qt.AlignCenter)

                    self.tablo.setItem(satir, 0, item_id)
                    self.tablo.setItem(satir, 1, item_ad)
                    self.tablo.setItem(satir, 2, item_kod)
                    self.tablo.setItem(satir, 3, item_rol)
                    self.tablo.setItem(satir, 4, item_durum)
                    self.tablo.setItem(satir, 5, item_tarih)
            else:
                print(f"Veri çekilemedi. Hata Kodu: {cevap.status_code}")
        except Exception as e:
            print("Sunucuya bağlanılamadı:", e)

    def secili_kullanici_durum_degistir(self):
        secili_satirlar = self.tablo.selectionModel().selectedRows()
        
        if not secili_satirlar:
            QMessageBox.warning(self, "Uyarı", "Lütfen tablodan durumunu değiştirmek istediğiniz kullanıcıyı seçin.")
            return

        satir = secili_satirlar[0].row()
        kullanici_adi = self.tablo.item(satir, 1).text()
        kullanici_id = self.tablo.item(satir, 1).data(Qt.UserRole)
        mevcut_durum_metni = self.tablo.item(satir, 4).text()
        rol_item = self.tablo.item(satir, 3)
        rol_kodu = str(
            rol_item.data(Qt.UserRole) or rol_item.text()
        ).strip().upper()

        if rol_kodu == "ADMIN":
            QMessageBox.warning(
                self,
                "İşlem Engellendi",
                "ADMIN kullanıcısının aktiflik durumu değiştirilemez."
            )
            return

        if not kullanici_id:
            QMessageBox.critical(self, "Hata", "Kullanıcı ID'si bulunamadı. Lütfen tabloyu yenileyin.")
            return

        # Dinamik soru sorma mantığı
        islem_sorusu = "aktife almak" if "Pasif" in mevcut_durum_metni else "pasife almak"
        
        cevap = QMessageBox.question(
            self, "Onay",
            f"'{kullanici_adi}' adlı kullanıcıyı {islem_sorusu} istediğinize emin misiniz?",
            QMessageBox.Yes | QMessageBox.No
        )

        if cevap == QMessageBox.Yes:
            headers = {"Authorization": f"Bearer {self.token}"}
            # YENİ ENDPOINT'E GİDİYORUZ
            url = f"{self.api_url}/api/kullanicilar/{kullanici_id}/durum-degistir"
            
            try:
                res = oturum_kontrollu_istek("PATCH", url, headers=headers, timeout=5)
                if oturum_hatasi_mi(res):
                    return
                if res.status_code == 200:
                    yeni_durum_bilgisi = "Aktif" if res.json().get("yeni_durum") else "Pasif"
                    QMessageBox.information(self, "Başarılı", f"Kullanıcı başarıyla {yeni_durum_bilgisi} duruma getirildi.")
                    self.verileri_cek() 
                elif res.status_code == 403:
                    QMessageBox.warning(self, "Yetki Hatası", res.json().get("detail", "Bu işlem için yetkiniz yok."))
                else:
                    QMessageBox.critical(self, "Hata", f"Sunucu hatası: {res.status_code}")
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Bağlantı hatası:\n{str(e)}")
    def secili_kullanici_rol_degistir(self):
        secili_satirlar = self.tablo.selectionModel().selectedRows()
        
        if not secili_satirlar:
            QMessageBox.warning(self, "Uyarı", "Lütfen tablodan rolünü değiştirmek istediğiniz kullanıcıyı seçin.")
            return

        satir = secili_satirlar[0].row()
        kullanici_adi = self.tablo.item(satir, 1).text()
        kullanici_id = self.tablo.item(satir, 1).data(Qt.UserRole)
        mevcut_rol = self.tablo.item(satir, 3).data(Qt.UserRole) or self.tablo.item(satir, 3).text()

        if str(mevcut_rol).strip().upper() == "ADMIN":
            QMessageBox.warning(
                self,
                "İşlem Engellendi",
                "ADMIN kullanıcısının rolü değiştirilemez."
            )
            return

        
        # YENİ KONTROL: 4. sütundaki durumu (Aktif/Pasif) oku
        durum = self.tablo.item(satir, 4).text()
        if "Pasif" in durum:
            QMessageBox.warning(self, "İşlem Reddedildi", "Pasif durumdaki bir kullanıcının rolü değiştirilemez.")
            return

        if not kullanici_id:
            QMessageBox.critical(self, "Hata", "Kullanıcı ID'si bulunamadı. Lütfen tabloyu yenileyin.")
            return

        form = RolDegistirFormu(
            self.api_url, self.token, kullanici_id, kullanici_adi, mevcut_rol, self,
            mevcut_rol_gorunen=self.tablo.item(satir, 3).text(),
        )
        if form.exec() == QDialog.Accepted:
            self.verileri_cek()

    def secili_kullanici_oda_yetkileri(self):
        """Seçili psikologun görüşme odalarını düzenleme penceresini açar."""
        secim = self.tablo.selectionModel().selectedRows()
        if not secim:
            QMessageBox.warning(self, "Kullanıcı Seçilmedi", "Lütfen oda yetkilerini düzenlemek istediğiniz psikoloğu tablodan seçin.")
            return

        satir = secim[0].row()
        ad_item = self.tablo.item(satir, 1)
        rol_item = self.tablo.item(satir, 3)
        kullanici_id = ad_item.data(Qt.UserRole) if ad_item is not None else None
        rol_kodu = str((rol_item.data(Qt.UserRole) or rol_item.text()) if rol_item is not None else "")

        if rol_kodu.upper() != "PSIKOLOG":
            QMessageBox.information(self, "Oda Yetkisi", "Oda yetkisi yalnızca psikolog rolündeki kullanıcılar için tanımlanır.")
            return
        if not kullanici_id:
            QMessageBox.critical(self, "Hata", "Kullanıcı ID'si bulunamadı. Lütfen tabloyu yenileyin.")
            return

        OdaYetkileriFormu(self.api_url, self.token, kullanici_id, ad_item.text(), self).exec()

    # ------------------------------------------------------------ parola sıfırlama talepleri
    @staticmethod
    def bekleme_metni(dakika):
        """'az önce', '5 dk önce', '2 saat önce', '3 gün önce'."""
        dakika = max(int(dakika or 0), 0)
        if dakika < 1:
            return "az önce"
        if dakika < 60:
            return f"{dakika} dk önce"
        if dakika < 1440:
            return f"{dakika // 60} saat önce"
        return f"{dakika // 1440} gün önce"

    def talepleri_yukle(self):
        """Bekleyen parola sıfırlama taleplerini getirir; yetki yoksa (403) ya da hata olursa panel gizli kalır."""
        talepler = []
        try:
            cevap = oturum_kontrollu_istek(
                "GET", f"{self.api_url}/api/parola-sifirlama-talepleri",
                headers={"Authorization": f"Bearer {self.token}"}, timeout=5)
            if oturum_hatasi_mi(cevap):
                return
            if cevap.status_code == 200:
                talepler = cevap.json()
        except Exception:
            talepler = []
        self.talepleri_goster(talepler if isinstance(talepler, list) else [])

    TALEP_ALANLARI = ("talep_id", "kullanici_id", "kullanici_adi")

    def talepleri_goster(self, talepler):
        # Beklenmeyen biçimde gelen kayıtlar (eksik alan) panelde sessizce atlanır; ekran çökmez.
        talepler = [t for t in talepler if isinstance(t, dict) and all(t.get(a) is not None for a in self.TALEP_ALANLARI)]
        while self.talep_lay.count():
            w = self.talep_lay.takeAt(0).widget()
            if w:
                w.hide()
                w.setParent(None)
                w.deleteLater()
        if not talepler:
            self.talep_paneli.hide()
            return
        baslik = QLabel(f"🔐  Parola sıfırlama talepleri  ({len(talepler)})")
        baslik.setStyleSheet("font-size: 15px; font-weight: 800; color: #1E3A8A; background: transparent;")
        self.talep_lay.addWidget(baslik)
        for t in talepler:
            self.talep_lay.addWidget(self._talep_satiri(t))
        self.talep_paneli.show()

    def _talep_satiri(self, talep):
        satir = QFrame()
        satir.setStyleSheet("QFrame { background: white; border-radius: 10px; }")
        lay = QHBoxLayout(satir)
        lay.setContentsMargins(14, 8, 10, 8)
        rol = talep.get("rol_adi") or "-"
        yazi = QLabel(f"<b>{talep['kullanici_adi']}</b>  ·  {rol}  ·  "
                      f"<span style='color:#6B7FA8'>{self.bekleme_metni(talep.get('bekleme_dakika'))}</span>")
        yazi.setTextFormat(Qt.RichText)
        yazi.setStyleSheet("font-size: 13px; color: #0A1F5C; background: transparent;")
        lay.addWidget(yazi, 1)
        for ad, nesne, renk, zemin, yuva in (
            ("🔑  Parola Sıfırla", "talepSifirla", "white", "#1554B7", self.talep_parola_sifirla),
            ("Talebi Kapat", "talepKapat", "#1554B7", "#EEF3FC", self.talep_kapat),
        ):
            dugme = QPushButton(ad)
            dugme.setObjectName(nesne)
            dugme.setCursor(Qt.PointingHandCursor)
            dugme.setProperty("talep_id", talep["talep_id"])
            dugme.setProperty("kullanici_id", talep["kullanici_id"])
            dugme.setProperty("kullanici_adi", talep["kullanici_adi"])
            dugme.setStyleSheet(
                f"QPushButton {{ background: {zemin}; color: {renk}; border: none; border-radius: 8px; "
                f"padding: 7px 14px; font-size: 12px; font-weight: 700; }} QPushButton:hover {{ opacity: 0.9; }}")
            dugme.clicked.connect(yuva)
            lay.addWidget(dugme)
        return satir

    def talep_parola_sifirla(self):
        """Talep satırındaki 'Parola Sıfırla': aynı sıfırlama akışı, kullanıcı seçmeye gerek kalmadan."""
        d = self.sender()
        if d is None:
            return
        self.parola_sifirla(d.property("kullanici_id"), d.property("kullanici_adi"))

    def talep_kapat(self):
        """Talebi parolayı sıfırlamadan kapatır (örn. kullanıcı parolasını hatırladı)."""
        d = self.sender()
        if d is None:
            return
        kullanici_adi, talep_id = d.property("kullanici_adi"), d.property("talep_id")
        onay = QMessageBox.question(
            self, "Talebi Kapat",
            f"'{kullanici_adi}' kullanıcısının parola sıfırlama talebi, parolası sıfırlanmadan kapatılsın mı?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if onay != QMessageBox.Yes:
            return
        try:
            cevap = oturum_kontrollu_istek(
                "PATCH", f"{self.api_url}/api/parola-sifirlama-talepleri/{talep_id}/kapat",
                headers={"Authorization": f"Bearer {self.token}"}, timeout=10)
            if oturum_hatasi_mi(cevap):
                return
            if cevap.status_code != 200:
                try:
                    mesaj = cevap.json().get("detail", "Talep kapatılamadı.")
                except ValueError:
                    mesaj = "Talep kapatılamadı."
                QMessageBox.warning(self, "İşlem Başarısız", str(mesaj))
        except requests.RequestException:
            QMessageBox.critical(self, "Bağlantı Hatası", "Sunucudan yanıt alınamadı. Lütfen tekrar deneyin.")
        self.talepleri_yukle()

    def secili_kullanici_parola_sifirla(self):
        """Seçili kullanıcının parolasını ADMIN aracılığıyla sıfırla."""

        secim = self.tablo.selectionModel().selectedRows()

        if not secim:
            QMessageBox.warning(
    self,
    "Kullanıcı Seçilmedi",
    "Lütfen parolasını sıfırlamak istediğiniz kullanıcıyı seçin."
)
            return

        satir = secim[0].row()
        kullanici_item = self.tablo.item(satir, 1)

        if kullanici_item is None:
            QMessageBox.warning(
                self, "Hata", "Kullanıcı bilgisi bulunamadı."
            )
            return

        kullanici_id = kullanici_item.data(Qt.UserRole)
        kullanici_adi = kullanici_item.text()

        if not kullanici_id:
            QMessageBox.warning(
                self,
                "Hata",
                "Kullanıcı ID'si bulunamadı."
            )
            return

        self.parola_sifirla(kullanici_id, kullanici_adi)

    def parola_sifirla(self, kullanici_id, kullanici_adi):
        """Verilen kullanıcının parolasını ADMIN aracılığıyla sıfırlar (onay ister, geçici parolayı gösterir)."""
        onay = QMessageBox.question(
    self,
    "Parola Sıfırlama Onayı",
    f"'{kullanici_adi}' kullanıcısının parolası sıfırlansın mı?\n\n"
    "Mevcut parola geçersiz olacak.\n"
    "Kullanıcı ilk girişte yeni parola belirlemek zorunda kalacak.\n\n"
    "Parolayı vermeden önce kullanıcının kimliğini yüz yüze ya da telefonla doğrulayın.",
    QMessageBox.Yes | QMessageBox.No,
    QMessageBox.No
)

        if onay != QMessageBox.Yes:
            return

        headers = {
            "Authorization": f"Bearer {self.token}"
        }

        url = (
            f"{self.api_url}/api/kullanicilar/"
            f"{kullanici_id}/parola-sifirla"
        )

        try:
            cevap = oturum_kontrollu_istek(
                "POST",
                url,
                headers=headers,
                timeout=10
            )

            if oturum_hatasi_mi(cevap):
                return

            if cevap.status_code != 200:
                try:
                    mesaj = cevap.json().get(
                        "detail",
                        "Parola sıfırlanamadı."
                    )
                except ValueError:
                    mesaj = "Parola sıfırlanamadı."

                QMessageBox.warning(
                    self,
                    "İşlem Başarısız",
                    str(mesaj)
                )
                return

            sonuc = cevap.json()
            gecici_parola = sonuc.get("gecici_parola")

            if not gecici_parola:
                QMessageBox.warning(
                    self,
                    "Hata",
                    "İşlem sonucunda geçici parola alınamadı. "
                    "Sistem yöneticisiyle iletişime geçin."
                )
                return

            # Parola kopyalanabilir pencerede gösterilir; kapandıktan sonra tekrar gösterilemez.
            GeciciParolaDialog(kullanici_adi, gecici_parola, self).exec()
            # Sıfırlanan kullanıcının bekleyen talebi sunucuda tamamlandı; paneli tazele.
            self.talepleri_yukle()

        except requests.RequestException:
            QMessageBox.critical(
                self,
                "Bağlantı Hatası",
                "Sunucudan yanıt alınamadı.\\n\\n"
                "İşlem gerçekleşmiş olabilir. "
                "Durumu kontrol etmeden tekrar denemeyin."
            )

    def kullanici_olustur_ac(self):
        form = KullaniciOlusturFormu(self.api_url, self.token, self)
        form.exec()
        if form.olusturulan_kullanici is not None:
            self.verileri_cek()

# ======================================================================
#  ORTAK YARDIMCILAR (kullanıcı oluşturma + personel atama)
# ======================================================================
DANISMA_OGRENCISI = "DANISMA_OGRENCISI"

# Kullanıcı oluştur formundaki rol listesiyle aynı numaralar (roller tablosu).
ROL_ID_ADLARI = {
    1: "PSIKOLOG", 2: "MEMUR", 3: "MUDUR",
    4: DANISMA_OGRENCISI, 5: "PROJE_ASISTANI", 6: "ADMIN",
}

# "Bu rol neler yapabilir?" özetinde izinler, kullanıcının tanıdığı başlıklar altında gösterilir.
# (başlık, simge, izin adı önekleri). Eşleşmeyen izinler "Diğer" altında toplanır.
IZIN_GRUPLARI = (
    ("Randevu ve Takvim", "📅", ("RANDEVU_", "TAKVIM_")),
    ("Odalar", "🚪", ("ODA_",)),
    ("Cihazlar", "🔬", ("CIHAZ_", "BAKIM_", "KALIBRASYON_", "ARIZA_")),
    ("Faaliyetler", "📋", ("FAALIYET_",)),
    ("Danışma Masası", "🛎️", ("DANISMA_",)),
    ("Kullanıcı ve Personel", "👥", ("KULLANICI_", "PERSONEL_")),
    ("Rol ve Yetki Yönetimi", "🔐", ("ROL_", "IZIN_")),
    ("Denetim", "🔎", ("AUDIT_",)),
)
GENIS_YETKILI_ROLLER = ("ADMIN", "MUDUR")


def izinleri_grupla(izinler):
    """[{'izin_adi', 'gorunen_ad'}] -> [(başlık, simge, [görünen adlar])]; boş gruplar atlanır."""
    gruplar = {baslik: [] for baslik, _, _ in IZIN_GRUPLARI}
    diger = []
    for izin in izinler:
        ad = izin.get("izin_adi", "")
        gorunen = izin.get("gorunen_ad") or ad
        for baslik, _, onekler in IZIN_GRUPLARI:
            if ad.startswith(onekler):
                gruplar[baslik].append(gorunen)
                break
        else:
            diger.append(gorunen)
    sonuc = [(b, simge, gruplar[b]) for b, simge, _ in IZIN_GRUPLARI if gruplar[b]]
    if diger:
        sonuc.append(("Diğer", "•", diger))
    return sonuc


def yetki_ozeti_getir(api_url, token, rol_id):
    """Rolün yetki özetini sunucudan alır. Başarılıysa (veri, None), değilse (None, mesaj)."""
    headers = {"Authorization": f"Bearer {token}"}
    try:
        cevap = oturum_kontrollu_istek(
            "GET", f"{api_url}/api/roller/{rol_id}/yetki-ozeti", headers=headers, timeout=5
        )
        if oturum_hatasi_mi(cevap):
            return None, "Oturum süreniz doldu."
        if cevap.status_code == 200:
            return cevap.json(), None
        if cevap.status_code == 403:
            return None, "Rol yetkilerini görmek için yetkiniz yok."
        if cevap.status_code == 404:
            return None, ("Sunucu bu özelliği tanımıyor (404). Sunucuyu güncelleyip "
                          "yeniden başlatın, sonra tekrar deneyin.")
        return None, f"Rol yetkileri şu an alınamadı (sunucu yanıtı: {cevap.status_code})."
    except Exception:
        return None, "Sunucuya ulaşılamadı; rol yetkileri gösterilemiyor."

FORM_STIL = """
    QDialog { background-color: #F8FAFC; }
    QLabel { font-weight: bold; color: #1E293B; font-size: 13px; }
    QLabel#sonuc_metni { font-weight: normal; color: #0F172A; }
    QLabel#ulke_kodu {
        background-color: #E2E8F0; color: #334155; border: 1px solid #CBD5E1;
        border-radius: 8px; padding: 10px 12px; font-size: 13px; font-weight: bold;
    }
    QFrame#sonuc_kutusu { background-color: #ECFDF5; border: 1px solid #A7F3D0; border-radius: 10px; }
    QComboBox, QLineEdit {
        background-color: white;
        border: 1px solid #CBD5E1;
        border-radius: 8px;
        padding: 10px 12px;
        color: #0F172A;
        font-size: 13px;
    }
    QComboBox::drop-down { border: none; width: 24px; }
    QComboBox:focus, QLineEdit:focus { border: 1px solid #3B82F6; }
    QLineEdit:read-only {
        background-color: #F1F5F9;
        color: #64748B;
        border: 1px dashed #94A3B8;
    }
    QPushButton { border-radius: 8px; padding: 10px 15px; font-weight: bold; font-size: 13px; }
    QPushButton#btn_iptal { background-color: white; border: 1px solid #CBD5E1; color: #475569; }
    QPushButton#btn_iptal:hover { background-color: #F1F5F9; }
    QPushButton#btn_kaydet { background-color: #2563EB; color: white; border: none; }
    QPushButton#btn_kaydet:hover { background-color: #1D4ED8; }
    QPushButton#btn_kaydet:disabled { background-color: #CBD5E1; color: #64748B; }
    QPushButton#btn_ata { background-color: #059669; color: white; border: none; }
    QPushButton#btn_ata:hover { background-color: #047857; }
    QFrame#yetki_karti { background-color: white; border: 1px solid #E2E8F0; border-radius: 12px; }
    QLabel#yetki_baslik { font-size: 14px; color: #0F172A; background: transparent; }
    QLabel#yetki_rozet {
        background-color: #DBEAFE; color: #1D4ED8; border-radius: 9px;
        padding: 2px 10px; font-size: 11px;
    }
    QLabel#yetki_grup { color: #475569; font-size: 11px; padding-top: 6px; background: transparent; }
    QLabel#yetki_liste { font-weight: normal; color: #334155; font-size: 12px; background: transparent; }
    QLabel#yetki_bilgi { font-weight: normal; color: #64748B; font-size: 12px; background: transparent; }
    QLabel#yetki_uyari {
        background-color: #FEF3C7; color: #92400E; border-radius: 8px;
        padding: 6px 10px; font-weight: normal; font-size: 12px;
    }
    QScrollArea#yetki_kaydirma { background: transparent; border: none; }
    QWidget#yetki_icerik { background: transparent; }
"""




def sunucu_hata_mesaji(cevap, varsayilan):
    try:
        detay = cevap.json().get("detail")
        if isinstance(detay, str) and detay:
            return detay
        if isinstance(detay, list):
            # Doğrulama hataları (422): her birinin "msg" alanını okunur biçimde birleştir.
            mesajlar = [
                str(h.get("msg", "")).replace("Value error, ", "")
                for h in detay if isinstance(h, dict) and h.get("msg")
            ]
            if mesajlar:
                return "\n".join(mesajlar)
    except Exception:
        pass
    return varsayilan




def ogrenci_alanlari_olustur():
    """Danışma öğrencisi için ad soyad, öğrenci numarası ve telefon alanları."""
    kutu = QWidget()
    lay = QVBoxLayout(kutu)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(8)

    lay.addWidget(QLabel("Ad Soyad:"))
    ad_soyad = QLineEdit()
    ad_soyad.setMaxLength(100)
    ad_soyad.setPlaceholderText("Öğrencinin adı ve soyadı")
    lay.addWidget(ad_soyad)

    lay.addWidget(QLabel("Öğrenci Numarası:"))
    numara = QLineEdit()
    numara.setMaxLength(15)  # 'Öğrenci Ekle' formuyla aynı
    numara.setValidator(QRegularExpressionValidator(QRegularExpression(r"[0-9]*")))
    numara.setPlaceholderText("Öğrenci numarasını giriniz")
    lay.addWidget(numara)

    lay.addWidget(QLabel("Telefon (isteğe bağlı):"))
    telefon_satiri = QHBoxLayout()
    telefon_satiri.setSpacing(8)
    ulke_kodu = QLabel("+90")
    ulke_kodu.setObjectName("ulke_kodu")
    ulke_kodu.setAlignment(Qt.AlignCenter)
    telefon_satiri.addWidget(ulke_kodu)
    telefon = QLineEdit()
    telefon.setMaxLength(15)  # "(555) 123 45 67" en uzun biçimdir
    telefon.setValidator(QRegularExpressionValidator(QRegularExpression(r"[0-9 ()]*")))
    telefon.setPlaceholderText("(555) 123 45 67")
    # Yazarken biçimlendirir: 5551234567 -> (555) 123 45 67
    telefon.textEdited.connect(lambda metin, alan=telefon: telefonu_bicimle_alanda(alan, metin))
    telefon_satiri.addWidget(telefon, 1)
    lay.addLayout(telefon_satiri)

    kutu.setVisible(False)
    return kutu, ad_soyad, numara, telefon


def telefon_rakamlari(metin):
    return "".join(c for c in metin if c.isascii() and c.isdigit())


def telefon_bicimle(metin):
    """Yazılan rakamları telefon biçimine sokar: '5551234567' -> '(555) 123 45 67'.

    Başa 0 yazmak gerekmez; yazılırsa yok sayılır. Kapanış parantezi ve boşluklar yalnızca
    sonraki rakam yazılınca eklenir; böylece geri silerken imleç biçime takılmaz.
    """
    rakamlar = telefon_rakamlari(metin)
    if rakamlar.startswith("0"):
        rakamlar = rakamlar[1:]
    rakamlar = rakamlar[:10]
    if not rakamlar:
        return ""
    sonuc = "(" + rakamlar[:3]
    if len(rakamlar) > 3:
        sonuc += ") " + rakamlar[3:6]
    if len(rakamlar) > 6:
        sonuc += " " + rakamlar[6:8]
    if len(rakamlar) > 8:
        sonuc += " " + rakamlar[8:10]
    return sonuc


def telefon_normalle(metin):
    """Sunucuya gidecek biçim: 10 haneli numaranın başına 0 eklenir ('05551234567')."""
    rakamlar = telefon_rakamlari(metin)
    if len(rakamlar) == 10 and not rakamlar.startswith("0"):
        return "0" + rakamlar
    return rakamlar


def telefonu_bicimle_alanda(alan, metin):
    alan.setText(telefon_bicimle(metin))


def ogrenci_bilgisi_dogrula(ogrenci):
    """Öğrenci alanlarını denetler (kurallar 'Öğrenci Ekle' formuyla aynıdır).

    Dönüş: hata mesajı ya da None (geçerliyse).
    """
    if not ogrenci["ad_soyad"] or not ogrenci["ogrenci_numarasi"]:
        return "Danışma öğrencisi için ad soyad ve öğrenci numarası zorunludur."
    numara = ogrenci["ogrenci_numarasi"]
    if not (numara.isascii() and numara.isdigit()):
        return "Öğrenci numarası sadece rakamlardan oluşmalıdır."
    if len(numara) > 15:
        return "Öğrenci numarası en fazla 15 haneli olabilir."
    telefon = ogrenci["telefon"]  # ogrenci_bilgisi_oku() zaten normalleştirir
    if telefon and not (len(telefon) == 11 and telefon.startswith("0")):
        return "Telefon numarası 10 haneli olmalıdır, başına 0 yazmanız gerekmez.\n(Örn: 555 123 45 67)"
    return None


_TR_HARITA = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")


def kullanici_adi_oner(ad_soyad):
    """Ad soyaddan kullanıcı adı önerir: 'Veli Kaya' -> 'veli.kaya'."""
    metin = ad_soyad.translate(_TR_HARITA).lower()
    metin = "".join(c if (c.isascii() and c.isalnum()) else " " for c in metin)
    return ".".join(metin.split())


def musait_kullanici_adi(api_url, token, temel):
    """Sunucudan ilk boş kullanıcı adını ister ('ali.veli' doluysa 'ali.veli2').

    Sunucuya ulaşılamazsa verilen adı olduğu gibi döndürür.
    """
    if not temel:
        return temel
    try:
        cevap = oturum_kontrollu_istek(
            "GET", f"{api_url}/api/kullanicilar/musait-kullanici-adi",
            params={"temel": temel},
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )
        if cevap.status_code == 200 and not oturum_hatasi_mi(cevap):
            return cevap.json().get("kullanici_adi") or temel
    except Exception as e:
        print("Kullanıcı adı önerisi alınamadı:", e)
    return temel


def ogrenci_bilgisi_oku(ad_soyad, numara, telefon):
    return {
        "ad_soyad": ad_soyad.text().strip(),
        "ogrenci_numarasi": numara.text().strip(),
        "telefon": telefon_normalle(telefon.text()),
    }


class YetkiOzetiKarti(QFrame):
    """Seçilen rolün neler yapabildiğini başlıklara ayrılmış, okunaklı bir kartta gösterir."""

    BOS_METIN = "Bir rol seçtiğinizde, o rolün sistemde neler yapabileceği burada görünür."

    def __init__(self, ebeveyn=None):
        super().__init__(ebeveyn)
        self.setObjectName("yetki_karti")
        dis = QVBoxLayout(self)
        dis.setContentsMargins(14, 12, 14, 12)
        dis.setSpacing(8)

        ust = QHBoxLayout()
        self.lbl_baslik = QLabel()
        self.lbl_baslik.setObjectName("yetki_baslik")
        self.lbl_rozet = QLabel()
        self.lbl_rozet.setObjectName("yetki_rozet")
        ust.addWidget(self.lbl_baslik)
        ust.addStretch()
        ust.addWidget(self.lbl_rozet)
        dis.addLayout(ust)

        self.lbl_bilgi = QLabel()
        self.lbl_bilgi.setObjectName("yetki_bilgi")
        self.lbl_bilgi.setWordWrap(True)
        dis.addWidget(self.lbl_bilgi)

        self.lbl_uyari = QLabel("⚠ Geniş yetkili bir rol: yalnızca güvendiğiniz kişilere verin.")
        self.lbl_uyari.setObjectName("yetki_uyari")
        self.lbl_uyari.setWordWrap(True)
        dis.addWidget(self.lbl_uyari)

        self.kaydirma = QScrollArea()
        self.kaydirma.setObjectName("yetki_kaydirma")
        self.kaydirma.setWidgetResizable(True)
        self.kaydirma.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.kaydirma.setMaximumHeight(230)
        self.icerik = QWidget()
        self.icerik.setObjectName("yetki_icerik")
        self.icerik_lay = QVBoxLayout(self.icerik)
        self.icerik_lay.setContentsMargins(0, 0, 4, 0)
        self.icerik_lay.setSpacing(2)
        self.kaydirma.setWidget(self.icerik)
        dis.addWidget(self.kaydirma)
        self.bos_goster()

    def _icerigi_temizle(self):
        while self.icerik_lay.count():
            oge = self.icerik_lay.takeAt(0)
            parca = oge.widget()
            if parca is not None:
                # Ebeveynsiz bırakılmaz: sahipsiz Qt nesnesini Python çöp toplayıcısı başka bir
                # iş parçacığında silerse uygulama çöker. Gizle, Qt kendi ebeveyniyle silsin.
                parca.hide()
                parca.deleteLater()

    def _durum(self, baslik="", rozet="", bilgi="", uyari=False, liste=False):
        self.lbl_baslik.setText(baslik)
        self.lbl_baslik.setVisible(bool(baslik))
        self.lbl_rozet.setText(rozet)
        self.lbl_rozet.setVisible(bool(rozet))
        self.lbl_bilgi.setText(bilgi)
        self.lbl_bilgi.setVisible(bool(bilgi))
        self.lbl_uyari.setVisible(uyari)
        self.kaydirma.setVisible(liste)
        self._icerigi_temizle()

    def bos_goster(self):
        self._durum(bilgi=self.BOS_METIN)

    def yukleniyor_goster(self):
        self._durum(bilgi="Rol yetkileri yükleniyor...")

    def hata_goster(self, mesaj):
        self._durum(bilgi=f"ℹ {mesaj}")

    def ozet_goster(self, veri):
        izinler = veri.get("izinler", [])
        rol_adi = veri.get("gorunen_ad") or veri.get("rol_adi") or "Rol"
        if not izinler:
            self._durum(baslik=rol_adi, rozet="0 yetki", bilgi="Bu rolün henüz açık bir yetkisi yok.")
            return
        self._durum(
            baslik=rol_adi,
            rozet=f"{len(izinler)} yetki",
            bilgi="Bu rolle açılan hesap şunları yapabilir:",
            uyari=veri.get("rol_adi") in GENIS_YETKILI_ROLLER,
            liste=True,
        )
        parcalar = []
        for baslik, simge, adlar in izinleri_grupla(izinler):
            grup = QLabel(f"{simge}  {baslik.upper()}")
            grup.setObjectName("yetki_grup")
            liste = QLabel("<br>".join(f"<span style='color:#059669'>✓</span>&nbsp; {a}" for a in adlar))
            liste.setObjectName("yetki_liste")
            liste.setTextFormat(Qt.RichText)
            # Satır sonu zaten <br> ile verilir; kelime kaydırma kapalı olunca etiketin yüksekliği
            # kesin hesaplanır (kaydırmalı etiketlerde sizeHint güvenilmez, liste kesilirdi).
            liste.setWordWrap(False)
            self.icerik_lay.addWidget(grup)
            self.icerik_lay.addWidget(liste)
            parcalar += [grup, liste]
        self.icerik_lay.addStretch()
        # Kısa listede boşluk kalmasın; uzunsa 230 pikselde kaydırılır. Yükseklik, her etiketin
        # kendi ölçüsünden hesaplanır (yerleşim henüz yapılmadan sizeHint 0'a yakın çıkabilir).
        self.kaydirma.setFixedHeight(self._liste_yuksekligi(parcalar))

    def _liste_yuksekligi(self, parcalar):
        toplam = 0
        for parca in parcalar:
            parca.ensurePolished()
            toplam += parca.sizeHint().height()
        toplam += self.icerik_lay.spacing() * max(len(parcalar) - 1, 0)
        return max(min(toplam + 8, 230), 60)



def atanabilir_rolleri_yukle(api_url, token, combo, islem):
    """Aktif atanabilir rolleri sunucudan al; hata durumunda boş bırak."""
    adres = (
        "/api/roller/atanabilir/olusturma"
        if islem == "olusturma"
        else "/api/roller/atanabilir/degistirme"
    )
    try:
        cevap = oturum_kontrollu_istek(
            "GET",
            f"{api_url}{adres}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )
        if oturum_hatasi_mi(cevap):
            return

        if cevap.status_code != 200:
            raise ValueError(
                f"Rol listesi alınamadı (HTTP {cevap.status_code})."
            )

        roller = cevap.json()
        if not isinstance(roller, list):
            raise ValueError("Sunucudan geçersiz rol listesi geldi.")

        for rol in roller:
            rol_id = int(rol["rol_id"])
            rol_adi = str(rol["gorunen_ad"]).strip()
            if not rol_adi:
                raise ValueError("Rolün görünen adı boş.")
            combo.addItem(rol_adi, rol_id)

    except (ValueError, TypeError, KeyError, OSError) as hata:
        QMessageBox.warning(
            combo.window(),
            "Roller Yüklenemedi",
            str(hata),
        )


class KullaniciOlusturFormu(QDialog):
    """Kullanıcı, personel ve gerekirse öğrenci kaydını tek işlemde oluşturur."""

    def __init__(self, api_url, token, ebeveyn=None):
        super().__init__(ebeveyn)
        self.api_url = api_url
        self.token = token
        self.olusturulan_kullanici = None
        self.setWindowTitle("👤 Yeni Sistem Kullanıcısı Oluştur")
        self.setMinimumWidth(460)
        
        # SİZİN ORİJİNAL STİLİNİZ GERİ GELDİ!
        if 'FORM_STIL' in globals():
            self.setStyleSheet(FORM_STIL) 
            
        self._yetki_onbellek = {}
        self.arayuzu_kur()
        self.odalari_yukle() # EKLENDİ
        self.rol_degisti()

    def arayuzu_kur(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 25, 20, 20)

        layout.addWidget(QLabel("Sistem Rolü:"))
        self.combo_rol = QComboBox()
        self.combo_rol.addItem("— Rol seçiniz —", None)
        self.combo_rol.setCursor(Qt.PointingHandCursor)
        atanabilir_rolleri_yukle(
            self.api_url, self.token, self.combo_rol, "olusturma"
        )
        self.combo_rol.setCurrentIndex(0)
        self.combo_rol.currentIndexChanged.connect(self.rol_degisti)
        layout.addWidget(self.combo_rol)

        # Seçilen rolün neler yapabildiğini gösterir.
        self.yetki_karti = YetkiOzetiKarti()
        self.yetki_karti.setMinimumWidth(420)   # SetFixedSize, pencere genişliğini içerikten alır
        layout.addWidget(self.yetki_karti)

        # Yalnızca "Danışma Öğrencisi" seçilince görünür. (Sizin kodunuz)
        try:
             (self.ogrenci_kutusu, self.input_ad_soyad,
              self.input_ogrenci_no, self.input_telefon) = ogrenci_alanlari_olustur()
             layout.addWidget(self.ogrenci_kutusu)
        except NameError:
             pass # Eğer fonksiyon yoksa geç

        # =======================================================
        # EKLENEN KISIM: ODA SEÇİM KUTUSU (PSİKOLOG İÇİN)
        # =======================================================
        self.lbl_oda = QLabel("Kullanacağı Odaları Seçiniz:")
        self.lbl_oda.setObjectName("lbl_oda") # Stil eklenebilir diye isim verdik
        self.lbl_oda.hide()
        layout.addWidget(self.lbl_oda)

        self.liste_odalar = QListWidget()
        self.liste_odalar.setObjectName("liste_odalar")
        # ListWidget'ı sizin diğer inputlarınıza benzer bir görünüme sokalım
        self.liste_odalar.setStyleSheet("""
            QListWidget {
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                padding: 5px;
                background-color: white;
            }
        """)
        self.liste_odalar.hide()
        # Çok fazla yer kaplamasın diye sabit bir yükseklik verelim
        self.liste_odalar.setMaximumHeight(90) 
        layout.addWidget(self.liste_odalar)
        # =======================================================

        # Kullanıcı adı (Sizin kodunuz)
        layout.addWidget(QLabel("Kullanıcı Adı:"))
        self.input_kullanici_adi = QLineEdit()
        self.input_kullanici_adi.setPlaceholderText("Kullanıcı adını giriniz...")
        layout.addWidget(self.input_kullanici_adi)
        
        self.kullanici_adi_elle_degisti = False
        self._son_kontrol_edilen_ad = None
        # Pencere boyutunu, içerik yerleştikten sonra bir kez daha içeriğe göre ayarlar.
        self._boyut_zamanlayici = QTimer(self)
        self._boyut_zamanlayici.setSingleShot(True)
        self._boyut_zamanlayici.timeout.connect(self.adjustSize)
        # Ad soyad yazılırken kısa bir bekleme sonrası sunucuya "bu ad boş mu?" diye sorulur.
        self._netlestirme_zamanlayici = QTimer(self)
        self._netlestirme_zamanlayici.setSingleShot(True)
        self._netlestirme_zamanlayici.setInterval(400)
        
        try:
            self._netlestirme_zamanlayici.timeout.connect(self._kullanici_adini_netlestir)
            self.input_ad_soyad.textChanged.connect(self._kullanici_adi_oner)
            self.input_ad_soyad.editingFinished.connect(self._kullanici_adini_netlestir)
        except AttributeError:
             pass
        self.input_kullanici_adi.textEdited.connect(self._kullanici_adi_elle_yazildi)

        buton_layout = QHBoxLayout()
        buton_layout.setSpacing(10)
        self.btn_iptal = QPushButton("İptal")
        self.btn_iptal.setObjectName("btn_iptal")
        self.btn_iptal.setCursor(Qt.PointingHandCursor)
        self.btn_iptal.clicked.connect(self.reject)
        
        self.btn_kaydet = QPushButton("Kullanıcıyı Oluştur")
        self.btn_kaydet.setObjectName("btn_kaydet")
        self.btn_kaydet.setCursor(Qt.PointingHandCursor)
        self.btn_kaydet.clicked.connect(self.kaydet)
        
        buton_layout.addWidget(self.btn_iptal)
        buton_layout.addWidget(self.btn_kaydet)
        layout.addLayout(buton_layout)

        # Hesap oluşturulduktan sonra görünür. (Sizin kodunuz)
        self.sonuc_kutusu = QFrame()
        self.sonuc_kutusu.setObjectName("sonuc_kutusu")
        sonuc_lay = QVBoxLayout(self.sonuc_kutusu)
        sonuc_lay.setContentsMargins(14, 12, 14, 12)
        sonuc_lay.setSpacing(10)
        self.lbl_sonuc = QLabel()
        self.lbl_sonuc.setObjectName("sonuc_metni")
        self.lbl_sonuc.setWordWrap(True)
        self.lbl_sonuc.setTextInteractionFlags(Qt.TextSelectableByMouse)
        sonuc_lay.addWidget(self.lbl_sonuc)
        self.sonuc_kutusu.setVisible(False)
        layout.addWidget(self.sonuc_kutusu)

    def odalari_yukle(self):
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            # oturum_kontrollu_istek fonksiyonunuzu kullanın
            import requests 
            cevap = requests.get(f"{self.api_url}/api/odalar", headers=headers, timeout=5)
            if cevap.status_code == 200:
                for oda in cevap.json():
                    if oda.get("aktif_mi", True):
                        item = QListWidgetItem(oda["oda_adi"])
                        item.setData(Qt.UserRole, oda["oda_id"])
                        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                        item.setCheckState(Qt.Unchecked)
                        self.liste_odalar.addItem(item)
        except Exception as e:
            print("Odalar yüklenirken hata:", e)

    def secili_rol_adi(self):
        return self.combo_rol.currentText()

    def _kullanici_adi_elle_yazildi(self, _metin):
        self.kullanici_adi_elle_degisti = True

    # SİZİN METOTLARINIZI KORUYORUM
    def _kullanici_adi_oner(self, ad_soyad):
        if self.kullanici_adi_elle_degisti or self.combo_rol.currentData() != 4:
            return
        self._son_kontrol_edilen_ad = None
        self.input_kullanici_adi.clear()
        try:
            if kullanici_adi_oner(ad_soyad):
                self.input_kullanici_adi.setPlaceholderText("Kullanıcı adı kontrol ediliyor...")
                self._netlestirme_zamanlayici.start()
            else:
                self._netlestirme_zamanlayici.stop()
                self.input_kullanici_adi.setPlaceholderText("Kullanıcı adını giriniz...")
        except NameError:
             pass

    def _kullanici_adini_netlestir(self):
        self._netlestirme_zamanlayici.stop()
        if self.kullanici_adi_elle_degisti or self.combo_rol.currentData() != 4:
            return
        try:
            temel = kullanici_adi_oner(self.input_ad_soyad.text())
            if temel and temel != self._son_kontrol_edilen_ad:
                self._son_kontrol_edilen_ad = temel
                self.input_kullanici_adi.setText(musait_kullanici_adi(self.api_url, self.token, temel))
        except NameError:
             pass
        self.input_kullanici_adi.setPlaceholderText("Kullanıcı adını giriniz...")

    def yetki_ozetini_guncelle(self):
        rol_id = self.combo_rol.currentData()
        if not hasattr(self, 'yetki_karti'): return
        
        if rol_id is None:
            self.yetki_karti.bos_goster()
            return
        if rol_id not in self._yetki_onbellek:
            self.yetki_karti.yukleniyor_goster()
            try:
                veri, hata = yetki_ozeti_getir(self.api_url, self.token, rol_id)
                if veri is None:
                    self.yetki_karti.hata_goster(hata)
                    return
                self._yetki_onbellek[rol_id] = veri
            except NameError:
                pass
        self.yetki_karti.ozet_goster(self._yetki_onbellek.get(rol_id, []))

    def rol_degisti(self, *_):
        self.yetki_ozetini_guncelle()
        rol_adi = self.secili_rol_adi()
        
        if self.combo_rol.currentData() != 4:
            self._netlestirme_zamanlayici.stop()
            self.input_kullanici_adi.setPlaceholderText("Kullanıcı adını giriniz...")
            
        goster = self.olusturulan_kullanici is None and self.combo_rol.currentData() == 4
        if hasattr(self, 'ogrenci_kutusu'):
            self.ogrenci_kutusu.setVisible(goster)

        # =======================================================
        # EKLENEN KISIM: PSİKOLOG SEÇİLİRSE ODALARI GÖSTER
        # =======================================================
        if self.combo_rol.currentData() == 1:
            if hasattr(self, 'yetki_karti'):
                 self.yetki_karti.hide() # Odalar çok yer kaplamasın diye kartı gizleyebiliriz
            self.lbl_oda.setVisible(True)
            self.liste_odalar.setVisible(True)
        else:
            if hasattr(self, 'yetki_karti'):
                 self.yetki_karti.show()
            self.lbl_oda.setVisible(False)
            self.liste_odalar.setVisible(False)
            for i in range(self.liste_odalar.count()):
                self.liste_odalar.item(i).setCheckState(Qt.Unchecked)
        # =======================================================
        
        self.adjustSize()
        # Yetki kartının içeriği yeni eklendi; yerleşim olay döngüsünde tamamlanınca pencere,
        # ekran ölçeğinden bağımsız olarak son boyuna getirilir (liste kesilmesin).
        # Zamanlayıcı pencerenin çocuğudur: pencere kapanıp silinirse bekleyen çağrı da iptal olur
        # (QTimer.singleShot ile silinmiş pencerenin yöntemi çağrılıp hata penceresi çıkabiliyordu).
        self._boyut_zamanlayici.start(0)

    def kaydet(self):
        rol_id = self.combo_rol.currentData()
        if rol_id is None:
            QMessageBox.warning(self, "Uyarı", "Lütfen bir rol seçiniz.")
            return

        rol_adi = self.secili_rol_adi()
        danisma_ogrencisi = (self.combo_rol.currentData() == 4)
        otomatik_ad = danisma_ogrencisi and not self.kullanici_adi_elle_degisti
        
        if danisma_ogrencisi:
            try:
                ogrenci = ogrenci_bilgisi_oku(self.input_ad_soyad, self.input_ogrenci_no, self.input_telefon)
                hata = ogrenci_bilgisi_dogrula(ogrenci)
                if hata:
                    QMessageBox.warning(self, "Uyarı", hata)
                    return
            except NameError:
                pass

        # =======================================================
        # EKLENEN KISIM: PSİKOLOG ODA KONTROLÜ
        # =======================================================
        secilen_oda_idleri = []
        if self.combo_rol.currentData() == 1:
            for i in range(self.liste_odalar.count()):
                item = self.liste_odalar.item(i)
                if item.checkState() == Qt.Checked:
                    secilen_oda_idleri.append(item.data(Qt.UserRole))
            
            if not secilen_oda_idleri:
                QMessageBox.warning(self, "Eksik Seçim", "Psikolog rolü için lütfen en az bir adet görüşme odası seçiniz!")
                return
        # =======================================================

        if otomatik_ad:
            self._netlestirme_zamanlayici.stop()
            try:
                kullanici_adi = musait_kullanici_adi(
                    self.api_url, self.token, kullanici_adi_oner(self.input_ad_soyad.text())
                )
                self.input_kullanici_adi.setText(kullanici_adi)
            except NameError:
                kullanici_adi = self.input_kullanici_adi.text().strip()
        else:
            kullanici_adi = self.input_kullanici_adi.text().strip()
            
        if not kullanici_adi:
            QMessageBox.warning(self, "Uyarı", "Kullanıcı adı boş bırakılamaz.")
            return

        headers = {"Authorization": f"Bearer {self.token}"}

        istek_verisi = {
            "kullanici_adi": kullanici_adi,
            "rol_id": rol_id,
        }
        if danisma_ogrencisi:
            istek_verisi.update(ogrenci)
        if secilen_oda_idleri:
            istek_verisi["oda_idleri"] = secilen_oda_idleri

        try:
            cevap = oturum_kontrollu_istek(
                "POST", f"{self.api_url}/api/kullanicilar",
                json=istek_verisi, headers=headers, timeout=5,
            )
            if oturum_hatasi_mi(cevap):
                return
            if (
                cevap.status_code == 409
                and otomatik_ad
                and sunucu_hata_mesaji(cevap, "") == "Bu kullanıcı adı zaten kullanılıyor."
            ):
                # Aynı anda başka biri aynı adı aldıysa bir sonraki boş ad ile yeniden dene.
                kullanici_adi = musait_kullanici_adi(self.api_url, self.token, kullanici_adi)
                self.input_kullanici_adi.setText(kullanici_adi)
                istek_verisi["kullanici_adi"] = kullanici_adi
                cevap = oturum_kontrollu_istek(
                    "POST", f"{self.api_url}/api/kullanicilar",
                    json=istek_verisi, headers=headers, timeout=5,
                )
                if oturum_hatasi_mi(cevap):
                    return

            if cevap.status_code == 201:
                sonuc = cevap.json()
                personel_kodu = sonuc.get("personel_kodu")

                if not personel_kodu:
                    QMessageBox.critical(
                        self,
                        "Eksik Sunucu Yanıtı",
                        "Sunucu personel kodu döndürmedi. "
                        "Kayıt durumunu kontrol edin.",
                    )
                    return
                gecici_parola = sonuc.get("gecici_parola", "HATA")
                self.olusturulan_kullanici = {
                    "kullanici_id": sonuc.get("kullanici_id"),
                    "kullanici_adi": kullanici_adi,
                    "rol_id": rol_id,
                }
                self.btn_iptal.setText("Kapat")
                self.btn_kaydet.hide()
                self.lbl_sonuc.setText(
                    "✔ Kullanıcı ve personel başarıyla oluşturuldu.\n\n"
                    f"👤 Kullanıcı Adı: {kullanici_adi}\n"
                    f"🔑 Geçici Parola: {gecici_parola}\n"
                    f"🏷 Personel Kodu: {personel_kodu}\n\n"
                    "Parolayı kullanıcıya iletin; ilk girişte "
                    "değiştirmesi gerekir."
                )
                kullanilabilir = max(self.width() - 40, 300)
                self.lbl_sonuc.setMinimumHeight(self.lbl_sonuc.heightForWidth(kullanilabilir))
                
                # Inputları kitle
                for parca in (self.input_kullanici_adi, self.combo_rol, self.btn_kaydet):
                    parca.setEnabled(False)
                if hasattr(self, 'input_ad_soyad'):
                    self.input_ad_soyad.setEnabled(False)
                    self.input_ogrenci_no.setEnabled(False)
                    self.input_telefon.setEnabled(False)
                
                self.liste_odalar.setEnabled(False) # Odaları kitle
                
                if hasattr(self, 'yetki_karti'):
                     self.yetki_karti.setVisible(False)
                self.sonuc_kutusu.setVisible(True)
                self.adjustSize()
                
            elif cevap.status_code == 409:
                QMessageBox.warning(
                    self,
                    "Hata",
                    sunucu_hata_mesaji(
                        cevap,
                        "Bu kayıt zaten mevcut. Bilgileri kontrol edin.",
                    ),
                )
            else:
                 QMessageBox.critical(self, "Hata", f"Sunucu hatası: Kod {cevap.status_code}")

        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Bağlantı hatası:\n{str(e)}")


class OdaYetkileriFormu(QDialog):
    """Seçili psikologun görüşme odalarını düzenler. Her psikologun en az bir odası olmalıdır."""

    def __init__(self, api_url, token, kullanici_id, kullanici_adi, ebeveyn=None):
        super().__init__(ebeveyn)
        self.api_url = api_url
        self.token = token
        self.kullanici_id = kullanici_id
        self.kullanici_adi = kullanici_adi

        self.setWindowTitle("Oda Yetkileri")
        self.setMinimumWidth(420)
        self.setStyleSheet(
            "QDialog { background-color: #F8FAFC; }"
            "QLabel { color: #1E293B; font-size: 13px; }"
            "QListWidget { background: white; border: 1px solid #CBD5E1; border-radius: 8px; padding: 6px; color: #0F172A; }"
            "QPushButton { border-radius: 8px; padding: 10px 15px; font-weight: bold; font-size: 13px; }"
            "QPushButton#btn_iptal { background-color: white; border: 1px solid #CBD5E1; color: #475569; }"
            "QPushButton#btn_kaydet { background-color: #2563EB; color: white; border: none; }"
            "QPushButton#btn_kaydet:disabled { background-color: #94A3B8; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        baslik = QLabel(f"<b>{kullanici_adi}</b> kullanıcısının görüşme odaları")
        baslik.setTextFormat(Qt.RichText)
        layout.addWidget(baslik)
        layout.addWidget(QLabel("Her psikologun en az bir odası olmalıdır."))

        self.liste_odalar = QListWidget()
        self.liste_odalar.setObjectName("liste_odalar")
        layout.addWidget(self.liste_odalar)

        butonlar = QHBoxLayout()
        butonlar.addStretch()
        self.btn_iptal = QPushButton("İptal")
        self.btn_iptal.setObjectName("btn_iptal")
        self.btn_iptal.clicked.connect(self.reject)
        self.btn_kaydet = QPushButton("Kaydet")
        self.btn_kaydet.setObjectName("btn_kaydet")
        self.btn_kaydet.clicked.connect(self.kaydet)
        butonlar.addWidget(self.btn_iptal)
        butonlar.addWidget(self.btn_kaydet)
        layout.addLayout(butonlar)

        self.odalari_yukle()

    def _headers(self):
        return {"Authorization": f"Bearer {self.token}"}

    def odalari_yukle(self):
        """Aktif odaları listeler; psikologun mevcut odalarını işaretli getirir."""
        self.btn_kaydet.setEnabled(False)
        try:
            oda_cevabi = oturum_kontrollu_istek("GET", f"{self.api_url}/api/odalar", headers=self._headers(), timeout=5)
            if oturum_hatasi_mi(oda_cevabi):
                return
            mevcut_cevabi = oturum_kontrollu_istek(
                "GET", f"{self.api_url}/api/kullanicilar/{self.kullanici_id}/odalar",
                headers=self._headers(), timeout=5,
            )
            if oturum_hatasi_mi(mevcut_cevabi):
                return
            if oda_cevabi.status_code != 200 or mevcut_cevabi.status_code != 200:
                QMessageBox.warning(
                    self, "Odalar Yüklenemedi",
                    sunucu_hata_mesaji(mevcut_cevabi if mevcut_cevabi.status_code != 200 else oda_cevabi,
                                       "Odalar yüklenemedi."),
                )
                return
            mevcut = set(mevcut_cevabi.json().get("oda_idleri", []))
            for oda in oda_cevabi.json():
                if not oda.get("aktif_mi", True):
                    continue
                oge = QListWidgetItem(oda["oda_adi"])
                oge.setData(Qt.UserRole, oda["oda_id"])
                oge.setFlags(oge.flags() | Qt.ItemIsUserCheckable)
                oge.setCheckState(Qt.Checked if oda["oda_id"] in mevcut else Qt.Unchecked)
                self.liste_odalar.addItem(oge)
            self.btn_kaydet.setEnabled(True)
        except Exception as e:
            QMessageBox.warning(self, "Ağ Uyarısı", f"Odalar yüklenemedi: {str(e)}")

    def secilen_oda_idleri(self):
        return [
            self.liste_odalar.item(i).data(Qt.UserRole)
            for i in range(self.liste_odalar.count())
            if self.liste_odalar.item(i).checkState() == Qt.Checked
        ]

    def kaydet(self):
        secilen = self.secilen_oda_idleri()
        if not secilen:
            QMessageBox.warning(self, "Eksik Seçim", "Psikolog için en az bir görüşme odası seçilmelidir.")
            return
        try:
            cevap = oturum_kontrollu_istek(
                "PUT", f"{self.api_url}/api/kullanicilar/{self.kullanici_id}/odalar",
                json={"oda_idleri": secilen}, headers=self._headers(), timeout=5,
            )
            if oturum_hatasi_mi(cevap):
                return
            if cevap.status_code == 200:
                QMessageBox.information(self, "Başarılı", "Oda yetkileri güncellendi.")
                self.accept()
            else:
                QMessageBox.warning(self, "Hata", sunucu_hata_mesaji(cevap, f"Güncellenemedi: Kod {cevap.status_code}"))
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Bağlantı hatası:\n{str(e)}")


class RolDegistirFormu(QDialog):
    def __init__(self, api_url, token, kullanici_id, kullanici_adi, mevcut_rol, ebeveyn=None, mevcut_rol_gorunen=None):
        super().__init__(ebeveyn)
        self.api_url = api_url
        self.token = token
        self.kullanici_id = kullanici_id
        self.kullanici_adi = kullanici_adi
        self.mevcut_rol = mevcut_rol
        self.mevcut_rol_gorunen = mevcut_rol_gorunen or mevcut_rol
        
        self.setWindowTitle("🔁 Rol Ata / Değiştir")
        self.setMinimumWidth(460)
        self.resize(460, 290)
        
        self.setStyleSheet("""
            QDialog { background-color: #F8FAFC; }
            QLabel { font-weight: bold; color: #1E293B; font-size: 13px; }
            QComboBox, QLineEdit {
                background-color: white;
                border: 1px solid #CBD5E1;
                border-radius: 8px;
                padding: 10px 12px;
                color: #0F172A;
                font-size: 13px;
            }
            QComboBox::drop-down { border: none; width: 24px; }
            QComboBox:focus, QLineEdit:focus { border: 1px solid #3B82F6; }
            QLineEdit:read-only { background-color: #F1F5F9; color: #64748B; border: 1px dashed #94A3B8; }
            QPushButton { border-radius: 8px; padding: 10px 15px; font-weight: bold; font-size: 13px; }
            QPushButton#btn_iptal { background-color: white; border: 1px solid #CBD5E1; color: #475569; }
            QPushButton#btn_iptal:hover { background-color: #F1F5F9; }
            QPushButton#btn_kaydet { background-color: #2563EB; color: white; border: none; }
            QPushButton#btn_kaydet:hover { background-color: #1D4ED8; }
        """)
        self.ogrenci_kaydi_var = None
        self.arayuzu_kur()
        self.rol_degisti()

    def arayuzu_kur(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 25, 20, 20)

        # Seçilen Kullanıcı (Kilitli)
        layout.addWidget(QLabel("İşlem Yapılan Kullanıcı:"))
        self.input_kullanici = QLineEdit()
        self.input_kullanici.setText(f"{self.kullanici_adi} (Mevcut: {self.mevcut_rol_gorunen})")
        self.input_kullanici.setReadOnly(True)
        layout.addWidget(self.input_kullanici)

        # Yeni Rol Seçimi
        layout.addWidget(QLabel("Yeni Sistem Rolü:"))
        self.combo_rol = QComboBox()
        self.combo_rol.addItem("— Yeni Rolü Seçiniz —", None)
        self.combo_rol.setCursor(Qt.PointingHandCursor)
        
        atanabilir_rolleri_yukle(
            self.api_url, self.token, self.combo_rol, "degistirme"
        )
            
        layout.addWidget(self.combo_rol)

        self.ogrenci_bilgi = QLabel()
        self.ogrenci_bilgi.setWordWrap(True)
        layout.addWidget(self.ogrenci_bilgi)

        (
            self.ogrenci_kutusu,
            self.input_ad_soyad,
            self.input_ogrenci_no,
            self.input_telefon,
        ) = ogrenci_alanlari_olustur()

        layout.addWidget(self.ogrenci_kutusu)

        # Psikolog seçilirse en az bir görüşme odası zorunludur (her psikologun odası olmalı).
        self.oda_bilgi = QLabel("Psikolog için en az bir görüşme odası seçin.")
        self.oda_bilgi.setWordWrap(True)
        self.oda_bilgi.setVisible(False)
        layout.addWidget(self.oda_bilgi)
        self.liste_odalar = QListWidget()
        self.liste_odalar.setObjectName("liste_odalar")
        self.liste_odalar.setMaximumHeight(130)
        self.liste_odalar.setVisible(False)
        layout.addWidget(self.liste_odalar)
        self._odalar_yuklendi = False

        self.combo_rol.currentIndexChanged.connect(self.rol_degisti)

        layout.addStretch()

        # Butonlar
        buton_layout = QHBoxLayout()
        buton_layout.setSpacing(10)
        
        self.btn_iptal = QPushButton("İptal")
        self.btn_iptal.setObjectName("btn_iptal")
        self.btn_iptal.setCursor(Qt.PointingHandCursor)
        self.btn_iptal.clicked.connect(self.reject)
        
        self.btn_kaydet = QPushButton("Rolü Güncelle")
        self.btn_kaydet.setObjectName("btn_kaydet")
        self.btn_kaydet.setCursor(Qt.PointingHandCursor)
        self.btn_kaydet.clicked.connect(self.kaydet)

        # ADMIN kullanıcıların rolleri değiştirilemez.
        if str(self.mevcut_rol).strip().upper() in (
            "ADMIN", "SISTEM ADMIN", "SİSTEM ADMİN"
        ):
            self.btn_kaydet.setEnabled(False)
            self.combo_rol.setEnabled(False)

        buton_layout.addWidget(self.btn_iptal)
        buton_layout.addWidget(self.btn_kaydet)
        layout.addLayout(buton_layout)

    def rol_degisti(self, *_):
        # ADMIN kullanıcısının rolü değiştirilemez.
        if str(self.mevcut_rol).strip().upper() in (
            "ADMIN", "SISTEM ADMIN", "SİSTEM ADMİN"
        ):
            self.combo_rol.setEnabled(False)
            self.btn_kaydet.setEnabled(False)
            return

        self.oda_alanini_guncelle()

        danisma = (
            ROL_ID_ADLARI.get(self.combo_rol.currentData())
            == "DANISMA_OGRENCISI"
        )
        self.ogrenci_bilgi.setVisible(danisma)
        self.ogrenci_kutusu.setVisible(False)
        self.ogrenci_kaydi_var = None

        if not danisma:
            self.btn_kaydet.setEnabled(True)
            self.adjustSize()
            return

        self.btn_kaydet.setEnabled(False)
        self.ogrenci_bilgi.setText("Öğrenci kaydı kontrol ediliyor...")

        try:
            cevap = oturum_kontrollu_istek(
                "GET",
                f"{self.api_url}/api/kullanicilar/"
                f"{self.kullanici_id}/ogrenci-kayit-durumu",
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=5,
            )

            if oturum_hatasi_mi(cevap):
                self.ogrenci_bilgi.setText(
                    "Oturum süresi doldu. Yeniden giriş yapın."
                )
                return

            if cevap.status_code != 200:
                self.ogrenci_bilgi.setText(
                    "Öğrenci kaydı kontrol edilemedi."
                )
                return

            self.ogrenci_kaydi_var = bool(
                cevap.json()["ogrenci_kaydi_var"]
            )

            if self.ogrenci_kaydi_var:
                self.ogrenci_bilgi.setText(
                    "Öğrenci kaydı mevcut. Mevcut bilgiler korunacak."
                )
            else:
                self.ogrenci_bilgi.setText(
                    "Öğrenci bilgilerini girin."
                )
                self.ogrenci_kutusu.setVisible(True)

            self.btn_kaydet.setEnabled(True)

        except Exception:
            self.ogrenci_bilgi.setText(
                "Sunucuya bağlanılamadı."
            )
        finally:
            self.adjustSize()

    def oda_alanini_guncelle(self):
        """Psikolog seçilince oda listesini gösterir (odalar ilk gösterişte yüklenir)."""
        psikolog = ROL_ID_ADLARI.get(self.combo_rol.currentData()) == "PSIKOLOG"
        self.oda_bilgi.setVisible(psikolog)
        self.liste_odalar.setVisible(psikolog)
        if psikolog and not self._odalar_yuklendi:
            self.odalari_yukle()
        self.adjustSize()

    def odalari_yukle(self):
        try:
            cevap = oturum_kontrollu_istek(
                "GET", f"{self.api_url}/api/odalar",
                headers={"Authorization": f"Bearer {self.token}"}, timeout=5,
            )
            if oturum_hatasi_mi(cevap):
                return
            if cevap.status_code != 200:
                self.oda_bilgi.setText("Odalar yüklenemedi: " + sunucu_hata_mesaji(cevap, f"Kod {cevap.status_code}"))
                return
            for oda in cevap.json():
                if not oda.get("aktif_mi", True):
                    continue
                oge = QListWidgetItem(oda["oda_adi"])
                oge.setData(Qt.UserRole, oda["oda_id"])
                oge.setFlags(oge.flags() | Qt.ItemIsUserCheckable)
                oge.setCheckState(Qt.Unchecked)
                self.liste_odalar.addItem(oge)
            self._odalar_yuklendi = True
        except Exception:
            self.oda_bilgi.setText("Sunucuya bağlanılamadı; odalar yüklenemedi.")

    def secilen_oda_idleri(self):
        return [
            self.liste_odalar.item(i).data(Qt.UserRole)
            for i in range(self.liste_odalar.count())
            if self.liste_odalar.item(i).checkState() == Qt.Checked
        ]

    def kaydet(self):
        yeni_rol_id = self.combo_rol.currentData()

        mevcut_admin = str(self.mevcut_rol).strip().upper() in (
            "ADMIN", "SISTEM ADMIN", "SİSTEM ADMİN"
        )
        hedef_admin = ROL_ID_ADLARI.get(yeni_rol_id) == "ADMIN"

        if mevcut_admin or hedef_admin:
            QMessageBox.warning(
                self,
                "İşlem Engellendi",
                "ADMIN rolü atanamaz veya başka bir role dönüştürülemez."
            )
            return

        if yeni_rol_id is None:
            QMessageBox.warning(self, "Uyarı", "Lütfen listeden yeni bir rol seçiniz.")
            return

        if ROL_ID_ADLARI.get(yeni_rol_id) == str(self.mevcut_rol).upper():
            QMessageBox.information(
                self,
                "Rol Zaten Atanmış",
                f"Bu kullanıcı zaten {self.combo_rol.currentText()} rolüne sahip.\n"
                "Herhangi bir değişiklik yapılmadı."
            )
            return

        # Sunucuna gönderilecek JSON verisi ve URL
        veri = {"rol_id": yeni_rol_id}

        if ROL_ID_ADLARI.get(yeni_rol_id) == "PSIKOLOG":
            secilen_odalar = self.secilen_oda_idleri()
            if not secilen_odalar:
                QMessageBox.warning(self, "Eksik Seçim", "Psikolog rolü için en az bir görüşme odası seçilmelidir.")
                return
            veri["oda_idleri"] = secilen_odalar

        if ROL_ID_ADLARI.get(yeni_rol_id) == DANISMA_OGRENCISI:
            if self.ogrenci_kaydi_var is None:
                QMessageBox.warning(
                    self, "Uyarı",
                    "Öğrenci kaydı doğrulanamadı."
                )
                return

            if not self.ogrenci_kaydi_var:
                ogrenci = ogrenci_bilgisi_oku(
                    self.input_ad_soyad,
                    self.input_ogrenci_no,
                    self.input_telefon,
                )
                hata = ogrenci_bilgisi_dogrula(ogrenci)
                if hata:
                    QMessageBox.warning(self, "Uyarı", hata)
                    return
                veri.update(ogrenci)
        headers = {"Authorization": f"Bearer {self.token}"}
        url = f"{self.api_url}/api/kullanicilar/{self.kullanici_id}/rol"

        try:
            cevap = oturum_kontrollu_istek("PATCH", url, json=veri, headers=headers, timeout=5)
            if oturum_hatasi_mi(cevap):
                return
            if cevap.status_code == 200:
                QMessageBox.information(self, "Başarılı", "Kullanıcının rolü ve personel kodu başarıyla güncellendi.")
                self.accept()
            elif cevap.status_code == 422:
                QMessageBox.warning(
                    self,
                    "Eksik veya Hatalı Bilgi",
                    sunucu_hata_mesaji(cevap, "Öğrenci bilgilerini kontrol edin.")
                )
            elif cevap.status_code == 409:
                hata = sunucu_hata_mesaji(
                    cevap, "Rol güncellemesi tamamlanamadı."
                )
                if "zaten seçilen role sahip" in hata:
                    QMessageBox.information(
                        self,
                        "Rol Zaten Atanmış",
                        f"Bu kullanıcı zaten {self.combo_rol.currentText()} rolüne sahip.\n"
                        "Herhangi bir değişiklik yapılmadı."
                    )
                else:
                    QMessageBox.warning(
                        self, "İşlem Tamamlanamadı", hata
                    )
            elif cevap.status_code == 403:
                QMessageBox.warning(
                    self, "Yetki Hatası",
                    "Bu işlem için yetkiniz yok."
                )
            else:
                QMessageBox.critical(
                    self, "Hata",
                    f"Sunucu hatası: {cevap.text}"
                )
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Bağlantı hatası:\n{str(e)}")