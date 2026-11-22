"""TKYS - Cihaz Geçmişi: bir cihazın bakım, kalibrasyon, arıza ve rezervasyon kayıtları tek zaman çizgisinde (en yeni önce).

Cihaz Envanteri'nde satırın sonundaki "🕘" düğmesiyle açılır. Üstte cihaz bilgisi, bugünkü durumu ve özet sayılar; altta tür süzgeci
(Tümü / Bakım / Kalibrasyon / Arıza / Rezervasyon) ve kartlar halinde olaylar bulunur.
"""
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup, QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from client.api_yoneticisi import api_hata_mesaji, oturum_hatasi_mi, oturum_kontrollu_istek
from client.tablo_tasarimi import hap

# olay türü -> (simge, çubuk/yazı rengi, hap arka planı)
TUR_STILLERI = {
    "Bakım": ("🔧", "#B45309", "#FEF3C7"),
    "Kalibrasyon": ("🎯", "#6D28D9", "#EDE9FE"),
    "Arıza": ("⚠", "#B91C1C", "#FEE2E2"),
    "Rezervasyon": ("📌", "#1D4ED8", "#DBEAFE"),
}
SUZGECLER = ["Tümü"] + list(TUR_STILLERI)
DURUM_RENKLERI = {
    "Açık": ("#991B1B", "#FEE2E2"), "Çözüldü": ("#166534", "#DCFCE7"),
    "Aktif": ("#166534", "#DCFCE7"), "Tamamlandı": ("#475569", "#E2E8F0"), "İptal Edildi": ("#991B1B", "#FEE2E2"),
}
CIHAZ_DURUMLARI = {
    "Kullanima_Hazir": ("Kullanıma Hazır", "#166534", "#DCFCE7"), "Rezerve": ("Rezerve", "#1D4ED8", "#DBEAFE"),
    "Kullanimda": ("Kullanımda", "#0E7490", "#CFFAFE"), "Bakimda": ("Bakımda", "#854D0E", "#FEF3C7"),
    "Kalibrasyonda": ("Kalibrasyonda", "#6D28D9", "#EDE9FE"), "Arizali": ("Arızalı", "#991B1B", "#FEE2E2"),
    "Kullanim_Disi": ("Kullanım Dışı", "#475569", "#E2E8F0"),
}

STIL = """
QDialog { background: #F3F6FC; }
QLabel { background: transparent; color: #243653; }
QPushButton#suzgec { background: #E3ECFA; color: #4A5E80; border: none; border-radius: 14px; padding: 7px 16px; font-weight: 700; }
QPushButton#suzgec:checked { background: #285CE6; color: white; }
QPushButton#suzgec:hover:!checked { background: #D3E1F7; }
QPushButton#kapat { background: #E3ECFA; color: #16294B; border: none; border-radius: 8px; padding: 9px 22px; font-weight: 700; }
QScrollArea { border: none; background: transparent; }
"""


def tarih_metni(deger):
    """'2026-11-02T09:30:00' -> '02.11.2026 09:30'; gece yarısı (yalnızca gün bilgisi olan) kayıtlarda saat yazılmaz."""
    if not deger:
        return ""
    try:
        d = datetime.fromisoformat(str(deger))
    except ValueError:
        return str(deger)
    return d.strftime("%d.%m.%Y") if (d.hour, d.minute) == (0, 0) else d.strftime("%d.%m.%Y %H:%M")


def olay_zaman_metni(olay):
    """Başlangıç (varsa ' → bitiş'); aynı günde biten gün kayıtları tek tarih olarak yazılır."""
    bas, bit = tarih_metni(olay.get("baslangic")), tarih_metni(olay.get("bitis"))
    if not bit or bit == bas:
        return bas
    if bas[:10] == bit[:10]:                                                  # aynı gün, farklı saat: "02.11.2026 09:00 – 11:00"
        return f"{bas} – {bit[11:]}"
    return f"{bas}  →  {bit}"


def para_metni(deger):
    return f"{float(deger or 0):,.2f} ₺".replace(",", "X").replace(".", ",").replace("X", ".")


def ozet_metinleri(ozet):
    """Üstteki özet çipleri: [(metin, yazı rengi, arka plan)]."""
    cipler = [
        (f"{ozet.get('bakim_sayisi', 0)} bakım · {para_metni(ozet.get('toplam_bakim_maliyeti'))}", "#B45309", "#FEF3C7"),
        (f"{ozet.get('kalibrasyon_sayisi', 0)} kalibrasyon"
         + (f" · geçerlilik {tarih_metni(ozet.get('kalibrasyon_gecerlilik'))}" if ozet.get("kalibrasyon_gecerlilik") else ""), "#6D28D9", "#EDE9FE"),
        (f"{ozet.get('ariza_sayisi', 0)} arıza" + (f" · {ozet['acik_ariza_sayisi']} açık" if ozet.get("acik_ariza_sayisi") else ""),
         "#B91C1C" if ozet.get("acik_ariza_sayisi") else "#475569", "#FEE2E2" if ozet.get("acik_ariza_sayisi") else "#E2E8F0"),
        (f"{ozet.get('rezervasyon_sayisi', 0)} rezervasyon · {str(ozet.get('rezervasyon_saati', 0)).replace('.', ',')} saat", "#1D4ED8", "#DBEAFE"),
    ]
    return cipler


class OlayKarti(QFrame):
    """Zaman çizgisindeki tek olay: solda tür renginde çubuk; tür, zaman, başlık, ayrıntı ve (varsa) durum rozeti."""

    def __init__(self, olay, parent=None):
        super().__init__(parent)
        self.olay = olay
        simge, renk, arka = TUR_STILLERI.get(olay.get("tur"), ("•", "#475569", "#E2E8F0"))
        self.setObjectName("olayKarti")
        self.setStyleSheet(f"QFrame#olayKarti {{ background: white; border: 1px solid #E3EAF5; border-left: 5px solid {renk}; border-radius: 10px; }} "
                           "QLabel { background: transparent; border: none; }")
        yatay = QHBoxLayout(self)
        yatay.setContentsMargins(16, 12, 16, 12)
        yatay.setSpacing(14)

        sol = QVBoxLayout()
        sol.setSpacing(4)
        ust = QHBoxLayout()
        ust.setSpacing(10)
        self.lbl_tur = QLabel(f"{simge}  {olay.get('tur', '')}")
        self.lbl_tur.setStyleSheet(f"background: {arka}; color: {renk}; border-radius: 10px; font-size: 11px; font-weight: 800; padding: 3px 10px;")
        self.lbl_zaman = QLabel(olay_zaman_metni(olay))
        self.lbl_zaman.setStyleSheet("color: #64748B; font-size: 12px; font-weight: 700;")
        ust.addWidget(self.lbl_tur)
        ust.addWidget(self.lbl_zaman)
        ust.addStretch()
        sol.addLayout(ust)
        self.lbl_baslik = QLabel(str(olay.get("baslik") or ""))
        self.lbl_baslik.setWordWrap(True)
        self.lbl_baslik.setStyleSheet("color: #0A1F5C; font-size: 14px; font-weight: 800;")
        sol.addWidget(self.lbl_baslik)
        if olay.get("ayrinti"):
            self.lbl_ayrinti = QLabel(str(olay["ayrinti"]))
            self.lbl_ayrinti.setWordWrap(True)
            self.lbl_ayrinti.setStyleSheet("color: #5B6B88; font-size: 12px;")
            sol.addWidget(self.lbl_ayrinti)
        yatay.addLayout(sol, 1)

        self.durum_hapi = None
        if olay.get("durum"):
            d_renk, d_arka = DURUM_RENKLERI.get(olay["durum"], ("#475569", "#E2E8F0"))
            self.durum_hapi = hap(olay["durum"], d_renk, d_arka)
            yatay.addWidget(self.durum_hapi, alignment=Qt.AlignTop)


class CihazGecmisiPenceresi(QDialog):
    def __init__(self, api_url, token, cihaz_id, parent=None):
        super().__init__(parent)
        self.api_url = api_url.rstrip("/")
        self.token = token
        self.cihaz_id = cihaz_id
        self.veri = None
        self.kartlar = []
        self.setWindowTitle("Cihaz Geçmişi")
        self.setMinimumSize(780, 660)
        self.setStyleSheet(STIL)

        kok = QVBoxLayout(self)
        kok.setContentsMargins(20, 18, 20, 16)
        kok.setSpacing(12)

        self.baslik_karti = QFrame()
        self.baslik_karti.setObjectName("baslikKarti")
        self.baslik_karti.setStyleSheet("QFrame#baslikKarti { background: white; border: 1px solid #E3EAF5; border-radius: 12px; }")
        self.baslik_duzeni = QVBoxLayout(self.baslik_karti)
        self.baslik_duzeni.setContentsMargins(20, 16, 20, 16)
        self.baslik_duzeni.setSpacing(8)
        self.lbl_ad = QLabel("Cihaz geçmişi yükleniyor…")
        self.lbl_ad.setStyleSheet("color: #0A1F5C; font-size: 20px; font-weight: 800;")
        self.lbl_alt = QLabel("")
        self.lbl_alt.setStyleSheet("color: #64748B; font-size: 12px; font-weight: 600;")
        self.baslik_duzeni.addWidget(self.lbl_ad)
        self.baslik_duzeni.addWidget(self.lbl_alt)
        self.cip_satiri = QVBoxLayout()                  # çipler dar pencerede kesilmesin diye iki satıra bölünür
        self.cip_satiri.setSpacing(6)
        self.baslik_duzeni.addLayout(self.cip_satiri)
        kok.addWidget(self.baslik_karti)

        suzgec_satiri = QHBoxLayout()
        suzgec_satiri.setSpacing(8)
        self.suzgec_grubu = QButtonGroup(self)
        self.suzgec_grubu.setExclusive(True)
        self.suzgec_dugmeleri = {}
        for ad in SUZGECLER:
            d = QPushButton(ad)
            d.setObjectName("suzgec")
            d.setCheckable(True)
            d.setCursor(Qt.PointingHandCursor)
            d.clicked.connect(lambda _=False, a=ad: self.suzgec_uygula(a))
            self.suzgec_grubu.addButton(d)
            self.suzgec_dugmeleri[ad] = d
            suzgec_satiri.addWidget(d)
        self.suzgec_dugmeleri["Tümü"].setChecked(True)
        suzgec_satiri.addStretch()
        self.lbl_sayac = QLabel("")
        self.lbl_sayac.setStyleSheet("color: #64748B; font-size: 12px; font-weight: 600;")
        suzgec_satiri.addWidget(self.lbl_sayac)
        kok.addLayout(suzgec_satiri)

        self.kaydirma = QScrollArea()
        self.kaydirma.setWidgetResizable(True)
        self.icerik = QWidget()
        self.icerik.setStyleSheet("background: transparent;")
        self.kart_duzeni = QVBoxLayout(self.icerik)
        self.kart_duzeni.setContentsMargins(0, 0, 6, 0)
        self.kart_duzeni.setSpacing(10)
        self.kart_duzeni.addStretch()
        self.kaydirma.setWidget(self.icerik)
        kok.addWidget(self.kaydirma, 1)

        self.lbl_bos = QLabel("")
        self.lbl_bos.setAlignment(Qt.AlignCenter)
        self.lbl_bos.setStyleSheet("color: #8A98B0; font-size: 13px; padding: 30px;")
        self.lbl_bos.hide()
        kok.addWidget(self.lbl_bos)

        alt = QHBoxLayout()
        self.lbl_sinir = QLabel("")
        self.lbl_sinir.setStyleSheet("color: #8A98B0; font-size: 11px;")
        alt.addWidget(self.lbl_sinir, 1)
        kapat = QPushButton("Kapat")
        kapat.setObjectName("kapat")
        kapat.setCursor(Qt.PointingHandCursor)
        kapat.clicked.connect(self.accept)
        alt.addWidget(kapat)
        kok.addLayout(alt)

        self.yukle()

    # ------------------------------------------------------------------ veri
    def yukle(self):
        try:
            cevap = oturum_kontrollu_istek("GET", f"{self.api_url}/api/cihazlar/{self.cihaz_id}/gecmis",
                                           headers={"Authorization": f"Bearer {self.token}"}, timeout=15)
            if oturum_hatasi_mi(cevap):
                return
            if cevap.status_code != 200:
                self._hata(api_hata_mesaji(cevap))
                return
            self.veri = cevap.json()
        except Exception as hata:
            self._hata(api_hata_mesaji(hata=hata))
            return
        self._doldur()

    def _hata(self, mesaj):
        self.lbl_ad.setText("Cihaz geçmişi alınamadı")
        self.lbl_alt.setText(str(mesaj))

    def _cip(self, metin, renk, arka):
        e = QLabel(metin)
        e.setStyleSheet(f"background: {arka}; color: {renk}; border-radius: 12px; font-size: 12px; font-weight: 800; padding: 5px 12px;")
        return e

    def _doldur(self):
        cihaz, ozet = self.veri["cihaz"], self.veri["ozet"]
        self.setWindowTitle(f"Cihaz Geçmişi — {cihaz.get('cihaz_adi', '')}")
        self.lbl_ad.setText(str(cihaz.get("cihaz_adi") or ""))
        parcalar = [str(cihaz.get("envanter_kodu") or "")]
        if cihaz.get("marka_model"):
            parcalar.append(str(cihaz["marka_model"]))
        if cihaz.get("seri_no"):
            parcalar.append(f"Seri no: {cihaz['seri_no']}")
        if cihaz.get("kayit_tarihi"):
            parcalar.append(f"Kayıt: {tarih_metni(cihaz['kayit_tarihi'])}")
        self.lbl_alt.setText("  ·  ".join(p for p in parcalar if p))
        while self.cip_satiri.count():
            oge = self.cip_satiri.takeAt(0)
            if oge.layout() is not None:
                while oge.layout().count():
                    alt = oge.layout().takeAt(0)
                    if alt.widget() is not None:
                        alt.widget().deleteLater()
            elif oge.widget() is not None:
                oge.widget().deleteLater()
        ad, renk, arka = CIHAZ_DURUMLARI.get(cihaz.get("etkin_durum") or cihaz.get("durum"), (str(cihaz.get("durum") or "—"), "#475569", "#E2E8F0"))
        self.durum_cipi = self._cip(f"Bugün: {ad}", renk, arka)
        cipler = [self.durum_cipi] + [self._cip(m, r, a) for m, r, a in ozet_metinleri(ozet)]
        for grup in (cipler[:3], cipler[3:]):                                       # ilk satır: durum, bakım, kalibrasyon; ikinci: arıza, rezervasyon
            satir = QHBoxLayout()
            satir.setSpacing(8)
            for cip in grup:
                satir.addWidget(cip)
            satir.addStretch()
            self.cip_satiri.addLayout(satir)

        for kart in self.kartlar:
            kart.deleteLater()
        self.kartlar = []
        for olay in self.veri["olaylar"]:
            kart = OlayKarti(olay)
            self.kartlar.append(kart)
            self.kart_duzeni.insertWidget(self.kart_duzeni.count() - 1, kart)
        sinir = self.veri.get("sinir")
        self.lbl_sinir.setText(f"Her türden en yeni {sinir} kayıt gösterilir; özet sayılar tüm kayıtları kapsar." if sinir else "")
        self.suzgec_uygula(self._secili_suzgec())

    # ------------------------------------------------------------------ süzgeç
    def _secili_suzgec(self):
        return next((ad for ad, d in self.suzgec_dugmeleri.items() if d.isChecked()), "Tümü")

    def suzgec_uygula(self, tur):
        gorunen = 0
        for kart in self.kartlar:
            goster = tur == "Tümü" or kart.olay.get("tur") == tur
            kart.setVisible(goster)
            gorunen += goster
        self.lbl_sayac.setText(f"{gorunen} kayıt")
        bos = gorunen == 0
        self.lbl_bos.setVisible(bos and self.veri is not None)
        if bos:
            self.lbl_bos.setText("Bu cihaz için henüz kayıt yok." if tur == "Tümü" else f"Bu cihaz için {tur.lower()} kaydı yok.")
        self.kaydirma.setVisible(not bos)
