"""Rezervasyon çakışması: çakışan rezervasyonlar tek tek gösterilir, kullanıcı isterse iptal eder.

Sunucu, yeni rezervasyon ya da bakım/kalibrasyon kaydı mevcut bir rezervasyonla çakışırsa işlemi
yapmadan 409 + çakışan rezervasyonların listesini döner. Bu pencere o listeyi gösterir; her satırın
yanındaki "Rezervasyonu iptal et" ile kullanıcı yalnızca istediği rezervasyonu iptal eder (iptal ucu
denetim kaydı yazar). Çakışma kalmayınca "Devam et" ile asıl işlem yeniden denenir. Hiçbir
rezervasyon kullanıcı seçmeden iptal edilmez.
"""
import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton, QScrollArea,
    QVBoxLayout, QWidget,
)

from api_yoneticisi import oturum_kontrollu_istek, oturum_hatasi_mi
import turkce_mesaj_kutusu as tmk

CAKISMA_KODU = "REZERVASYON_CAKISMASI"
EN_FAZLA_DENEME = 5

STIL = """
    QDialog { background-color: #F8FAFC; }
    QLabel { color: #1E293B; font-size: 13px; }
    QLabel#baslik { font-size: 16px; font-weight: bold; color: #0F172A; }
    QLabel#alt_metin { color: #64748B; }
    QLabel#ipucu { color: #92400E; background-color: #FEF3C7; border-radius: 8px; padding: 8px 10px; }
    QLabel#ipucu_hazir { color: #065F46; background-color: #D1FAE5; border-radius: 8px; padding: 8px 10px; }
    QScrollArea#liste_kaydirma, QWidget#liste_kap { background: transparent; border: none; }
    QFrame#satir { background-color: white; border: 1px solid #E2E8F0; border-radius: 10px; }
    QFrame#satir QLabel { background: transparent; }
    QLabel#zaman { font-weight: bold; color: #0F172A; }
    QLabel#kisi { color: #64748B; }
    QPushButton { border-radius: 8px; padding: 8px 14px; font-weight: bold; font-size: 13px; }
    QPushButton#iptal_et { background-color: white; color: #B91C1C; border: 1px solid #FCA5A5; }
    QPushButton#iptal_et:hover { background-color: #FEF2F2; }
    QPushButton#vazgec { background-color: white; color: #475569; border: 1px solid #CBD5E1; }
    QPushButton#vazgec:hover { background-color: #F1F5F9; }
    QPushButton#devam { background-color: #2563EB; color: white; border: none; }
    QPushButton#devam:hover { background-color: #1D4ED8; }
    QPushButton#devam:disabled { background-color: #CBD5E1; color: #64748B; }
"""


def cakisan_rezervasyonlar(cevap):
    """409 yanıtı rezervasyon çakışmasıysa rezervasyon listesini, değilse None döndürür."""
    if getattr(cevap, "status_code", None) != 409:
        return None
    try:
        detay = cevap.json().get("detail")
    except Exception:
        return None
    if isinstance(detay, dict) and detay.get("kod") == CAKISMA_KODU:
        return detay.get("rezervasyonlar") or []
    return None


def zaman_araligi(baslangic_iso, bitis_iso):
    """'10.11.2026 10:00 – 11:00' (aynı gün) ya da '10.11.2026 22:00 – 11.11.2026 02:00'."""
    bas = datetime.datetime.fromisoformat(baslangic_iso)
    bit = datetime.datetime.fromisoformat(bitis_iso)
    if bas.date() == bit.date():
        return f"{bas:%d.%m.%Y %H:%M} – {bit:%H:%M}"
    return f"{bas:%d.%m.%Y %H:%M} – {bit:%d.%m.%Y %H:%M}"


def rezervasyonu_iptal_et(api_url, token, rezervasyon_id):
    """Rezervasyonu iptal eder. Döndürür: (başarılı_mı, kullanıcıya_gösterilecek_hata | None)."""
    try:
        cevap = oturum_kontrollu_istek(
            "PATCH", f"{api_url}/api/rezervasyonlar/{rezervasyon_id}/iptal",
            headers={"Authorization": f"Bearer {token}"}, timeout=10,
        )
    except Exception:
        return False, "Sunucuya ulaşılamadı. Rezervasyon iptal edilemedi."
    if oturum_hatasi_mi(cevap):
        return False, "Oturum süreniz doldu."
    if cevap.status_code == 200:
        return True, None
    if cevap.status_code == 404:
        return True, None            # başka biri zaten iptal etmiş: çakışma kalmadı
    if cevap.status_code == 403:
        return False, "Bu rezervasyonu iptal etme yetkiniz yok. Yetkili bir personelle iletişime geçin."
    return False, "Rezervasyon iptal edilemedi."


class CakisanRezervasyonlarDialog(QDialog):
    """Çakışan rezervasyonları satır satır listeler; her satırda 'Rezervasyonu iptal et' düğmesi var."""

    def __init__(self, ebeveyn, rezervasyonlar, api_url, token, baslik, aciklama, devam_metni):
        super().__init__(ebeveyn)
        self.api_url = api_url
        self.token = token
        self.satirlar = {}                       # rezervasyon_id -> satır widget'ı
        self.setWindowTitle(baslik)
        self.setMinimumWidth(480)
        self.setStyleSheet(STIL)

        ana = QVBoxLayout(self)
        ana.setContentsMargins(22, 20, 22, 18)
        ana.setSpacing(12)

        lbl_baslik = QLabel(f"⚠  {baslik}")
        lbl_baslik.setObjectName("baslik")
        ana.addWidget(lbl_baslik)
        lbl_alt = QLabel(aciklama)
        lbl_alt.setObjectName("alt_metin")
        lbl_alt.setWordWrap(True)
        ana.addWidget(lbl_alt)

        self.liste = QVBoxLayout()
        self.liste.setSpacing(8)
        kap = QWidget()
        kap.setLayout(self.liste)
        kaydirma = QScrollArea()
        kaydirma.setWidgetResizable(True)
        kaydirma.setFrameShape(QFrame.NoFrame)
        kaydirma.setMaximumHeight(260)
        kap.setObjectName("liste_kap")
        kaydirma.setObjectName("liste_kaydirma")
        kaydirma.viewport().setAutoFillBackground(False)
        kaydirma.setWidget(kap)
        self.kaydirma = kaydirma
        ana.addWidget(kaydirma)
        for r in rezervasyonlar:
            self._satir_ekle(r)

        self.lbl_ipucu = QLabel()
        self.lbl_ipucu.setWordWrap(True)
        ana.addWidget(self.lbl_ipucu)

        alt = QHBoxLayout()
        alt.addStretch()
        self.btn_vazgec = QPushButton("Vazgeç")
        self.btn_vazgec.setObjectName("vazgec")
        self.btn_vazgec.setCursor(Qt.PointingHandCursor)
        self.btn_vazgec.clicked.connect(self.reject)
        self.btn_devam = QPushButton(devam_metni)
        self.btn_devam.setObjectName("devam")
        self.btn_devam.setCursor(Qt.PointingHandCursor)
        self.btn_devam.clicked.connect(self.accept)
        alt.addWidget(self.btn_vazgec)
        alt.addWidget(self.btn_devam)
        ana.addLayout(alt)
        self._durumu_guncelle()

    def _satir_ekle(self, r):
        satir = QFrame()
        satir.setObjectName("satir")
        lay = QHBoxLayout(satir)
        lay.setContentsMargins(14, 10, 12, 10)
        metin = QVBoxLayout()
        metin.setSpacing(2)
        zaman = QLabel(zaman_araligi(r["baslangic"], r["bitis"]))
        zaman.setObjectName("zaman")
        kisi = QLabel(f"Rezerve eden: {r.get('rezerve_eden', '-')}")
        kisi.setObjectName("kisi")
        metin.addWidget(zaman)
        metin.addWidget(kisi)
        lay.addLayout(metin)
        lay.addStretch()
        btn = QPushButton("Rezervasyonu iptal et")
        btn.setObjectName("iptal_et")
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(lambda _=False, rez=r: self._iptal_tikla(rez))
        lay.addWidget(btn)
        self.liste.addWidget(satir)
        self.satirlar[r["rezervasyon_id"]] = satir

    def _iptal_tikla(self, r):
        soru = (
            f"{r.get('rezerve_eden', '-')} kullanıcısının\n"
            f"{zaman_araligi(r['baslangic'], r['bitis'])} rezervasyonu iptal edilsin mi?\n\n"
            "Bu işlem denetim kayıtlarına yazılır."
        )
        if tmk.soru(self, "Rezervasyonu iptal et", soru,
                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        basarili, hata = rezervasyonu_iptal_et(self.api_url, self.token, r["rezervasyon_id"])
        if not basarili:
            tmk.uyari(self, "İptal edilemedi", hata)
            return
        satir = self.satirlar.pop(r["rezervasyon_id"], None)
        if satir is not None:
            satir.setParent(None)         # hemen kaybolsun
            satir.deleteLater()
        self._durumu_guncelle()

    def kalan(self):
        return len(self.satirlar)

    def _durumu_guncelle(self):
        kalan = self.kalan()
        hazir = kalan == 0
        self.btn_devam.setEnabled(hazir)
        self.kaydirma.setVisible(not hazir)      # liste boşalınca boş alan kalmasın
        self.lbl_ipucu.setObjectName("ipucu_hazir" if hazir else "ipucu")
        self.lbl_ipucu.setText(
            "Çakışan rezervasyon kalmadı, devam edebilirsiniz." if hazir
            else f"Devam etmek için çakışan {kalan} rezervasyonu iptal edin ya da Vazgeç'e basın."
        )
        self.lbl_ipucu.setStyle(self.lbl_ipucu.style())     # stil, nesne adı değişince yenilensin


def cakisma_cozumlu_istek(ebeveyn, yontem, url, veri, headers, baslik, aciklama, devam_metni):
    """İsteği gönderir; rezervasyon çakışırsa kullanıcıya gösterir, çakışma çözülünce yeniden dener.

    Döndürür: sunucunun son yanıtı, ya da kullanıcı vazgeçtiyse None.
    """
    api_url = url.split("/api/")[0]
    token = headers.get("Authorization", "").replace("Bearer ", "", 1)
    for _ in range(EN_FAZLA_DENEME):
        cevap = oturum_kontrollu_istek(yontem, url, json=veri, headers=headers)
        if oturum_hatasi_mi(cevap):
            return cevap
        rezervasyonlar = cakisan_rezervasyonlar(cevap)
        if rezervasyonlar is None:
            return cevap
        pencere = CakisanRezervasyonlarDialog(
            ebeveyn, rezervasyonlar, api_url, token, baslik, aciklama, devam_metni
        )
        if pencere.exec() != QDialog.Accepted:
            return None
    return cevap
