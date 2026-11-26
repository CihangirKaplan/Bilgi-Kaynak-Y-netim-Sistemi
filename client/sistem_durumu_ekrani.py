"""TKYS - Sistem Durumu (yönetici): sürüm, veritabanı şeması, son yedek, son girişler.

Daha önce bu bilgiler komut satırından bakılıyordu. Sunucudaki /api/sistem-durumu özetini gösterir; kişisel veri, parola ya da
dosya yolu içermez.
"""
from datetime import datetime

import requests
from client.bilgi_rozeti import BilgiRozeti, ROZET_METNI
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel, QMessageBox, QVBoxLayout, QWidget

from client.api_yoneticisi import istek_hatasi_metni, api_hata_mesaji, oturum_hatasi_mi, oturum_kontrollu_istek
from client.tablo_tasarimi import bos_mesaj_olustur, metin_item, tablo_olustur, yenile_butonu_olustur
from client.surum import SURUM

IYI, UYARI, KOTU = ("#166534", "#DCFCE7"), ("#854D0E", "#FEF3C7"), ("#991B1B", "#FEE2E2")
ALT_BASLIK = "Sürüm, veritabanı şeması, son yedek ve son girişler"
ROZET_ACIKLAMASI = (
    "Burada sunucu sürümüne, veritabanı şemasına, son yedeğe ve son girişlere bakarsınız; değişiklik yapılmaz.\n"
    "Bir sorun görürseniz sistem sorumlusuna bildirin."
)


def zaman_metni(deger):
    try:
        return datetime.fromisoformat(str(deger)).strftime("%d.%m.%Y %H:%M")
    except (TypeError, ValueError):
        return "—"


def gecen_metni(saat):
    if saat is None:
        return ""
    if saat < 1:
        return "1 saatten kısa süre önce"
    if saat < 48:
        return f"{int(saat)} saat önce"
    return f"{int(saat // 24)} gün önce"


def yedek_ozeti(yedek):
    """(başlık, açıklama, renk) — son yedeğin durumu. Yedek yoksa ya da eskiyse uyarı rengi."""
    if not yedek or not yedek.get("var"):
        return "Yedek bulunamadı", "Yedek klasöründe bu veritabanına ait yedek yok. Yedekleme görevini kontrol edin.", KOTU
    metin = f"{zaman_metni(yedek.get('tarih'))} ({gecen_metni(yedek.get('gecen_saat'))})"
    ayrinti = f"Toplam {yedek.get('adet', 0)} yedek · son yedek {yedek.get('boyut_mb', 0)} MB"
    if yedek.get("eski"):
        return metin, f"{ayrinti}. Son yedek eski; yedekleme görevi çalışmıyor olabilir.", UYARI
    return metin, ayrinti, IYI


class SistemDurumuEkrani(QWidget):
    def __init__(self, api_url, token):
        super().__init__()
        self.api_url = api_url.rstrip("/")
        self.token = token
        self.kartlar = {}
        self._arayuzu_olustur()
        self.yenile()

    # ------------------------------------------------------------------ arayüz
    def _arayuzu_olustur(self):
        kok = QVBoxLayout(self)
        kok.setContentsMargins(0, 0, 0, 0)
        kok.setSpacing(16)

        baslik_karti = QFrame()
        baslik_karti.setObjectName("kart")
        ust = QHBoxLayout(baslik_karti)
        ust.setContentsMargins(22, 18, 22, 16)
        metinler = QVBoxLayout()
        metinler.setSpacing(0)
        baslik = QLabel("Sistem Durumu")
        baslik.setStyleSheet("font-size: 18px; font-weight: 800; color: #0A1F5C;")
        self.alt_baslik = QLabel(ALT_BASLIK)
        self.alt_baslik.setStyleSheet("font-size: 12px; color: #6B7FA8;")
        baslik_satiri = QHBoxLayout()
        baslik_satiri.setSpacing(10)
        baslik_satiri.addWidget(baslik)
        self.rozet = BilgiRozeti(ROZET_METNI, ROZET_ACIKLAMASI)
        baslik_satiri.addWidget(self.rozet)
        baslik_satiri.addStretch()
        metinler.addLayout(baslik_satiri)
        metinler.addWidget(self.alt_baslik)
        ust.addLayout(metinler)
        ust.addStretch()
        ust.addWidget(yenile_butonu_olustur(self.yenile))
        kok.addWidget(baslik_karti)

        izgara = QGridLayout()
        izgara.setSpacing(12)
        for sutun, (anahtar, ad) in enumerate([("surum", "Uygulama Sürümü"), ("sema", "Veritabanı Şeması"),
                                               ("boyut", "Veritabanı Boyutu"), ("yedek", "Son Yedek")]):
            kart = QFrame()
            kart.setObjectName("kart")
            duzen = QVBoxLayout(kart)
            duzen.setContentsMargins(18, 14, 18, 14)
            duzen.setSpacing(4)
            etiket = QLabel(ad)
            etiket.setStyleSheet("font-size: 12px; font-weight: 700; color: #6B7FA8;")
            deger = QLabel("—")
            deger.setStyleSheet("font-size: 18px; font-weight: 800; color: #0A1F5C;")
            deger.setWordWrap(True)
            alt = QLabel("")
            alt.setWordWrap(True)
            alt.setStyleSheet("font-size: 11px; color: #6B7FA8;")
            duzen.addWidget(etiket)
            duzen.addWidget(deger)
            duzen.addWidget(alt)
            izgara.addWidget(kart, 0, sutun)
            self.kartlar[anahtar] = (kart, deger, alt)
        kok.addLayout(izgara)

        self.giris_basligi = QLabel("Son girişler")
        self.giris_basligi.setStyleSheet("font-size: 15px; font-weight: 800; color: #0A1F5C;")
        kok.addWidget(self.giris_basligi)
        self.tablo = tablo_olustur(["KULLANICI", "ROL", "SON GİRİŞ"], ortali=True)
        # Üç sütun tüm genişliği doldurur (önceden dar kalıp yazılar kesiliyor, yanda boş alan kalıyordu).
        baslik_cubugu = self.tablo.horizontalHeader()
        baslik_cubugu.setStretchLastSection(False)
        baslik_cubugu.setSectionResizeMode(0, QHeaderView.Stretch)
        baslik_cubugu.setSectionResizeMode(1, QHeaderView.Stretch)
        baslik_cubugu.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        baslik_cubugu.setMinimumSectionSize(150)
        self.bos_mesaj = bos_mesaj_olustur("Bu süre içinde giriş yapan kullanıcı yok.")
        kart = QFrame()
        kart.setObjectName("kart")
        kl = QVBoxLayout(kart)
        kl.setContentsMargins(8, 8, 8, 8)
        kl.addWidget(self.tablo)
        kl.addWidget(self.bos_mesaj)
        kok.addWidget(kart, 1)

        self.ozet = QLabel("")
        self.ozet.setWordWrap(True)
        self.ozet.setStyleSheet("font-size: 12px; color: #6B7FA8;")
        kok.addWidget(self.ozet)

    def _kart_yaz(self, anahtar, deger, alt="", renk=None):
        kart, deger_etiketi, alt_etiketi = self.kartlar[anahtar]
        deger_etiketi.setText(str(deger))
        alt_etiketi.setText(alt)
        if renk:
            kart.setStyleSheet(f"QFrame#kart {{ background: {renk[1]}; border-radius: 14px; }}")
            deger_etiketi.setStyleSheet(f"font-size: 18px; font-weight: 800; color: {renk[0]};")
        else:
            kart.setStyleSheet("")
            deger_etiketi.setStyleSheet("font-size: 18px; font-weight: 800; color: #0A1F5C;")

    # ------------------------------------------------------------------ veri
    def yenile(self):
        try:
            cevap = oturum_kontrollu_istek("GET", f"{self.api_url}/api/sistem-durumu",
                                           headers={"Authorization": f"Bearer {self.token}"}, timeout=15)
        except requests.RequestException as hata:
            self.alt_baslik.setText(f"Sunucuya ulaşılamadı: {istek_hatasi_metni(hata)}")
            return
        if oturum_hatasi_mi(cevap):
            return
        if cevap.status_code != 200:
            QMessageBox.warning(self, "Sistem Durumu", api_hata_mesaji(cevap))
            return
        self.goster(cevap.json())

    def goster(self, veri):
        self.alt_baslik.setText(ALT_BASLIK)          # önceki bir bağlantı hatası mesajı kalmasın
        sunucu_surumu = veri.get("surum", "—")
        uyumlu = sunucu_surumu == SURUM
        self._kart_yaz("surum", sunucu_surumu,
                       f"İstemci sürümü {SURUM}" + ("" if uyumlu else " — sunucudan farklı, istemciyi güncelleyin"),
                       None if uyumlu else UYARI)
        self._kart_yaz("sema", veri.get("sema_surumu") or "—", "Alembic migration sürümü")
        self._kart_yaz("boyut", f"{veri.get('veritabani_boyutu_mb', 0)} MB", "PostgreSQL veritabanı")
        baslik, aciklama, renk = yedek_ozeti(veri.get("yedek"))
        self._kart_yaz("yedek", baslik, aciklama, renk)

        girisler = veri.get("son_girisler", [])
        self.giris_basligi.setText(f"Son girişler (son {veri.get('oturum_suresi_dk', 45)} dakika; oturumu hâlâ açık olabilecekler)")
        self.tablo.setRowCount(0)
        self.tablo.setRowCount(len(girisler))
        for satir, g in enumerate(girisler):
            self.tablo.setItem(satir, 0, metin_item(g.get("kullanici_adi") or "—", ortala=True, kalin=True))
            self.tablo.setItem(satir, 1, metin_item(g.get("rol") or "—", ortala=True))
            self.tablo.setItem(satir, 2, metin_item(zaman_metni(g.get("zaman")), ortala=True))
        self.bos_mesaj.setVisible(not girisler)
        self.tablo.setVisible(bool(girisler))

        sayilar = veri.get("sayilar", {})
        self.ozet.setText(
            f"Son 24 saatte {veri.get('basarisiz_giris_24s', 0)} başarısız giriş denemesi · "
            f"{sayilar.get('aktif_kullanici', 0)} aktif kullanıcı · {sayilar.get('randevu', 0)} randevu · "
            f"{sayilar.get('danisan_kodu', 0)} danışan kodu"
        )
