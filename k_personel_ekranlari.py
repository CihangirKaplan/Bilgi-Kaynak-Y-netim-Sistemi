import requests
from api_yoneticisi import (
    oturum_kontrollu_istek,
    oturum_hatasi_mi,
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QFrame
)
from PySide6.QtWidgets import (
    QDialog, QLineEdit, QComboBox, QHBoxLayout, QLabel,
    QPushButton, QMessageBox, QScrollArea
)
from PySide6.QtCore import Qt, QRegularExpression, QTimer
from PySide6.QtGui import QRegularExpressionValidator

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
                    tarih = str(p["olusturulma_tarihi"])[:10]

                    item_id = QTableWidgetItem(str(p["personel_id"]))
                    item_ad = QTableWidgetItem(p["kullanici_adi"])
                    item_ad.setData(Qt.UserRole, p["kullanici_id"])  # YENİ: ID'yi arka planda saklıyoruz
                    item_kod = QTableWidgetItem(p["personel_kodu"])
                    item_rol = QTableWidgetItem(p["rol_adi"])
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
        mevcut_rol = self.tablo.item(satir, 3).text()
        
        # YENİ KONTROL: 4. sütundaki durumu (Aktif/Pasif) oku
        durum = self.tablo.item(satir, 4).text()
        if "Pasif" in durum:
            QMessageBox.warning(self, "İşlem Reddedildi", "Pasif durumdaki bir kullanıcının rolü değiştirilemez.")
            return

        if not kullanici_id:
            QMessageBox.critical(self, "Hata", "Kullanıcı ID'si bulunamadı. Lütfen tabloyu yenileyin.")
            return

        form = RolDegistirFormu(self.api_url, self.token, kullanici_id, kullanici_adi, mevcut_rol, self)
        if form.exec() == QDialog.Accepted:
            self.verileri_cek()

    def secili_kullanici_parola_sifirla(self):
        """Seçili kullanıcının parolasını ADMIN aracılığıyla sıfırla."""

        secim = self.tablo.selectionModel().selectedRows()

        if not secim:
            QMessageBox.warning(
                self,
                "Kullanıcı Seçilmedi",
                "Lütfen parolasını sıfırlamak istediğiniz "
                "kullanıcıyı seçin."
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

        onay = QMessageBox.question(
            self,
            "Parola Sıfırlama Onayı",
            f"'{kullanici_adi}' adlı kullanıcının parolasını "
            "sıfırlamak istiyor musunuz?\\n\\n"
            "Mevcut parola geçersiz olacak ve kullanıcı "
            "ilk girişte yeni parola belirlemek zorunda kalacaktır.",
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

            QMessageBox.information(
                self,
                "Geçici Parola Oluşturuldu",
                f"Kullanıcı: {kullanici_adi}\\n\\n"
                f"Geçici Parola: {gecici_parola}\\n\\n"
                "Bu parolayı güvenli şekilde kullanıcıya iletin.\\n"
                "Pencere kapatıldığında parola tekrar "
                "görüntülenemeyecektir.\\n\\n"
                "Kullanıcı ilk girişte yeni parola belirlemelidir."
            )

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


class KullaniciOlusturFormu(QDialog):
    """Kullanıcı, personel ve gerekirse öğrenci kaydını tek işlemde oluşturur."""

    def __init__(self, api_url, token, ebeveyn=None):
        super().__init__(ebeveyn)
        self.api_url = api_url
        self.token = token
        self.olusturulan_kullanici = None
        self.setWindowTitle("👤 Yeni Sistem Kullanıcısı Oluştur")
        self.setMinimumWidth(460)
        self.setStyleSheet(FORM_STIL)
        self._yetki_onbellek = {}
        self.arayuzu_kur()
        self.rol_degisti()

    def arayuzu_kur(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 25, 20, 20)

        layout.addWidget(QLabel("Sistem Rolü:"))
        self.combo_rol = QComboBox()
        self.combo_rol.addItem("— Rol seçiniz —", None)
        self.combo_rol.setCursor(Qt.PointingHandCursor)
        roller = [
            ("Psikolog", 1),
            ("Memur", 2),
            ("Müdür (Yönetici)", 3),
            ("Danışma Öğrencisi", 4),
            ("Proje Asistanı", 5),
            ("Sistem Admin", 6),
        ]
        for ad, rol_id in roller:
            self.combo_rol.addItem(ad, rol_id)
        self.combo_rol.setCurrentIndex(0)
        self.combo_rol.currentIndexChanged.connect(self.rol_degisti)
        layout.addWidget(self.combo_rol)

        # Seçilen rolün neler yapabildiğini gösterir.
        self.yetki_karti = YetkiOzetiKarti()
        self.yetki_karti.setMinimumWidth(420)   # SetFixedSize, pencere genişliğini içerikten alır
        layout.addWidget(self.yetki_karti)

        # Yalnızca "Danışma Öğrencisi" seçilince görünür.
        (self.ogrenci_kutusu, self.input_ad_soyad,
         self.input_ogrenci_no, self.input_telefon) = ogrenci_alanlari_olustur()
        layout.addWidget(self.ogrenci_kutusu)

        # Kullanıcı adı en altta: danışma öğrencisinde ad soyaddan otomatik önerilir
        # (elle değiştirilebilir); böylece aynı isim iki kez yazılmaz.
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
        self._netlestirme_zamanlayici.timeout.connect(self._kullanici_adini_netlestir)
        self.input_kullanici_adi.textEdited.connect(self._kullanici_adi_elle_yazildi)
        self.input_ad_soyad.textChanged.connect(self._kullanici_adi_oner)
        self.input_ad_soyad.editingFinished.connect(self._kullanici_adini_netlestir)

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

        # Hesap oluşturulduktan sonra görünür.
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

    def secili_rol_adi(self):
        return ROL_ID_ADLARI.get(self.combo_rol.currentData())

    def _kullanici_adi_elle_yazildi(self, _metin):
        self.kullanici_adi_elle_degisti = True

    def _kullanici_adi_oner(self, ad_soyad):
        """Ad soyad değişince kullanıcı adı alanını boşaltır ve sunucu kontrolünü başlatır.

        Dolu bir ad hiç gösterilmez: alan, sunucu "bu ad boş" diyene kadar boş bekler.
        """
        if self.kullanici_adi_elle_degisti or self.secili_rol_adi() != DANISMA_OGRENCISI:
            return
        self._son_kontrol_edilen_ad = None
        self.input_kullanici_adi.clear()
        if kullanici_adi_oner(ad_soyad):
            self.input_kullanici_adi.setPlaceholderText("Kullanıcı adı kontrol ediliyor...")
            self._netlestirme_zamanlayici.start()
        else:
            self._netlestirme_zamanlayici.stop()
            self.input_kullanici_adi.setPlaceholderText("Kullanıcı adını giriniz...")

    def _kullanici_adini_netlestir(self):
        """Önerilen kullanıcı adının boş olduğunu sunucudan doğrulayıp alana yazar."""
        self._netlestirme_zamanlayici.stop()
        if self.kullanici_adi_elle_degisti or self.secili_rol_adi() != DANISMA_OGRENCISI:
            return
        temel = kullanici_adi_oner(self.input_ad_soyad.text())
        if temel and temel != self._son_kontrol_edilen_ad:
            self._son_kontrol_edilen_ad = temel
            self.input_kullanici_adi.setText(musait_kullanici_adi(self.api_url, self.token, temel))
        self.input_kullanici_adi.setPlaceholderText("Kullanıcı adını giriniz...")

    def yetki_ozetini_guncelle(self):
        rol_id = self.combo_rol.currentData()
        if rol_id is None:
            self.yetki_karti.bos_goster()
            return
        if rol_id not in self._yetki_onbellek:
            self.yetki_karti.yukleniyor_goster()
            veri, hata = yetki_ozeti_getir(self.api_url, self.token, rol_id)
            if veri is None:
                # Hata önbelleğe alınmaz: rol yeniden seçilince tekrar denenir.
                self.yetki_karti.hata_goster(hata)
                return
            self._yetki_onbellek[rol_id] = veri
        self.yetki_karti.ozet_goster(self._yetki_onbellek[rol_id])

    def rol_degisti(self, *_):
        self.yetki_ozetini_guncelle()
        if self.secili_rol_adi() != DANISMA_OGRENCISI:
            self._netlestirme_zamanlayici.stop()
            self.input_kullanici_adi.setPlaceholderText("Kullanıcı adını giriniz...")
        goster = self.olusturulan_kullanici is None and self.secili_rol_adi() == DANISMA_OGRENCISI
        self.ogrenci_kutusu.setVisible(goster)
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

        danisma_ogrencisi = self.secili_rol_adi() == DANISMA_OGRENCISI
        otomatik_ad = danisma_ogrencisi and not self.kullanici_adi_elle_degisti
        if danisma_ogrencisi:
            ogrenci = ogrenci_bilgisi_oku(self.input_ad_soyad, self.input_ogrenci_no, self.input_telefon)
            hata = ogrenci_bilgisi_dogrula(ogrenci)
            if hata:
                QMessageBox.warning(self, "Uyarı", hata)
                return

        if otomatik_ad:
            # Ad soyaddan türetilir ve oluşturmadan hemen önce son kez sunucuda doğrulanır
            # (araya giren kayıt olmasın, dolu ad gönderilmesin).
            self._netlestirme_zamanlayici.stop()
            kullanici_adi = musait_kullanici_adi(
                self.api_url, self.token, kullanici_adi_oner(self.input_ad_soyad.text())
            )
            self.input_kullanici_adi.setText(kullanici_adi)
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
                # Kaydırmalı metin kesilmesin: yüksekliği mevcut genişliğe göre ayır.
                kullanilabilir = max(self.width() - 40 - 28, 300)
                self.lbl_sonuc.setMinimumHeight(self.lbl_sonuc.heightForWidth(kullanilabilir))
                for parca in (self.input_kullanici_adi, self.combo_rol, self.input_ad_soyad,
                              self.input_ogrenci_no, self.input_telefon, self.btn_kaydet):
                    parca.setEnabled(False)
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
                QMessageBox.critical(self, "Hata", sunucu_hata_mesaji(cevap, f"Sunucu hatası: Kod {cevap.status_code}"))

        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Bağlantı hatası:\n{str(e)}")


class RolDegistirFormu(QDialog):
    def __init__(self, api_url, token, kullanici_id, kullanici_adi, mevcut_rol, ebeveyn=None):
        super().__init__(ebeveyn)
        self.api_url = api_url
        self.token = token
        self.kullanici_id = kullanici_id
        self.kullanici_adi = kullanici_adi
        self.mevcut_rol = mevcut_rol
        
        self.setWindowTitle("🔁 Rol Ata / Değiştir")
        self.setFixedSize(400, 260) 
        
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
        self.arayuzu_kur()

    def arayuzu_kur(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 25, 20, 20)

        # Seçilen Kullanıcı (Kilitli)
        layout.addWidget(QLabel("İşlem Yapılan Kullanıcı:"))
        self.input_kullanici = QLineEdit()
        self.input_kullanici.setText(f"{self.kullanici_adi} (Mevcut: {self.mevcut_rol})")
        self.input_kullanici.setReadOnly(True)
        layout.addWidget(self.input_kullanici)

        # Yeni Rol Seçimi
        layout.addWidget(QLabel("Yeni Sistem Rolü:"))
        self.combo_rol = QComboBox()
        self.combo_rol.addItem("— Yeni Rolü Seçiniz —", None)
        self.combo_rol.setCursor(Qt.PointingHandCursor)
        
        roller = [
            ("Psikolog", 1), ("Memur", 2), ("Müdür (Yönetici)", 3),
            ("Danışma Öğrencisi", 4), ("Proje Asistanı", 5), ("Sistem Admin", 6)
        ]
        for ad, rol_id in roller:
            self.combo_rol.addItem(ad, rol_id)
            
        layout.addWidget(self.combo_rol)
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

        buton_layout.addWidget(self.btn_iptal)
        buton_layout.addWidget(self.btn_kaydet)
        layout.addLayout(buton_layout)

    def kaydet(self):
        yeni_rol_id = self.combo_rol.currentData()

        if yeni_rol_id is None:
            QMessageBox.warning(self, "Uyarı", "Lütfen listeden yeni bir rol seçiniz.")
            return

        # Sunucuna gönderilecek JSON verisi ve URL
        veri = {"rol_id": yeni_rol_id}
        headers = {"Authorization": f"Bearer {self.token}"}
        url = f"{self.api_url}/api/kullanicilar/{self.kullanici_id}/rol"

        try:
            cevap = oturum_kontrollu_istek("PATCH", url, json=veri, headers=headers, timeout=5)
            if oturum_hatasi_mi(cevap):
                return
            if cevap.status_code == 200:
                QMessageBox.information(self, "Başarılı", "Kullanıcının rolü başarıyla güncellendi.")
                self.accept()
            elif cevap.status_code == 403:
                QMessageBox.warning(self, "Yetki Hatası", "Bu işlem için yetkiniz yok.")
            else:
                QMessageBox.critical(self, "Hata", f"Sunucu hatası: {cevap.text}")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Bağlantı hatası:\n{str(e)}")