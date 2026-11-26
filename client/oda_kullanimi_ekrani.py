"""TKYS - Oda Kullanımı: odaların günlük ve haftalık doluluğu.

İki görünüm vardır: Gün (seçili günde tüm odalar yan yana) ve Hafta (seçili odanın haftası). Randevular renkli bloklar olarak
gösterilir (renkler Randevu Yönetimi'ndeki durum renkleriyle aynıdır); iptal edilenler gösterilmez. Psikolog, başkalarının
randevularında yalnızca "Dolu" bilgisini görür (sunucu uygular). Cihaz rezervasyonu odayı o saatlerde tamamen doldurur: yetkili
roller cihaz adını ve bölümü görür, yetkisi olmayanlar odanın cihaz kullanımı nedeniyle dolu olduğunu görür. Takvim her zaman
08:00-18:00 mesai saatlerini gösterir; mesai dışı saatler gösterilmez ve ızgarayı genişletmez. Çok günlü cihaz rezervasyonu tek kayıttır,
her gün yalnızca mesai kısmıyla çizilir. Sayfa yalnızca görüntülemedir.
"""

import textwrap
from datetime import date, datetime, timedelta

import requests
from client.api_yoneticisi import istek_hatasi_metni, oturum_hatasi_mi, oturum_kontrollu_istek
from client.randevu_ekranlari import DURUM_ETIKETLERI, DURUM_RENKLERI
from client.bilgi_rozeti import BilgiRozeti, ROZET_METNI, TiklaninceAciklayanKutu
from client.siniflandirma import gorusme_etiketi

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QButtonGroup, QComboBox, QFrame, QHBoxLayout, QHeaderView, QLabel, QMessageBox, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

GUN_KISA = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]
GUN_UZUN = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
AY_UZUN = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
AY_KISA = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]
CALISMA_GUNU_SAYISI = 5            # Pazartesi-Cuma; hafta sonu randevu verilmez
GIZLI_RENK = ("#F1F5F9", "#64748B")
CIHAZ_RENK = ("#F3E8FF", "#7E22CE")          # cihaz rezervasyonu (odanın cihaz kullanımı nedeniyle dolu olduğu saatler)
ODA_TAKVIMI_SAATLERI = list(range(8, 18))     # mesai 08:00-18:00; her satır bir saat dilimi (son satır 17:00-18:00)


# ------------------------------------------------------------------ saf işlevler (arayüzden bağımsız, testlenebilir)
ETKINLIK_RENK = ("#FFF3CD", "#9A6700")


def hafta_basi(gun):
    return gun - timedelta(days=gun.weekday())


def hafta_basligi(pazartesi):
    """'10 – 16 Kasım 2026'; ay ya da yıl değişirse '28 Eki – 3 Kas 2026' / '29 Ara 2026 – 4 Oca 2027'."""
    pazar = pazartesi + timedelta(days=6)
    if pazartesi.year != pazar.year:
        return f"{pazartesi.day} {AY_KISA[pazartesi.month - 1]} {pazartesi.year} – {pazar.day} {AY_KISA[pazar.month - 1]} {pazar.year}"
    if pazartesi.month != pazar.month:
        return f"{pazartesi.day} {AY_KISA[pazartesi.month - 1]} – {pazar.day} {AY_KISA[pazar.month - 1]} {pazar.year}"
    return f"{pazartesi.day} – {pazar.day} {AY_UZUN[pazar.month - 1]} {pazar.year}"


def zaman(metin):
    if not metin:
        return None
    try:
        return datetime.fromisoformat(str(metin).split(".")[0])
    except ValueError:
        return None


def saat_dilimleri(kayitlar=None):
    """Satır saatleri: her zaman 08:00-18:00 mesai saatleri. Mesai dışındaki kayıtlar ızgarayı genişletmez, gösterilmez.

    (kayitlar parametresi eski çağrılarla uyum içindir; saat aralığı kayıtlara bağlı değildir.)"""
    return list(ODA_TAKVIMI_SAATLERI)


def _kapsanan_saat(bas, bit):
    """Başlangıç ve bitişle kesişen saat dilimlerinin sayısı."""
    if bas is None or bit is None or bit <= bas:
        return 1

    ilk_saat = bas.replace(minute=0, second=0, microsecond=0)
    son_saat = (bit - timedelta(microseconds=1)).replace(
        minute=0, second=0, microsecond=0
    )

    return max(
        1,
        int((son_saat - ilk_saat).total_seconds() // 3600) + 1
    )


def rezervasyon_kayitlari(rezervasyonlar):
    """Sunucudaki cihaz rezervasyonlarını randevu kayıtlarıyla aynı biçime çevirir (blok haritası ve doluluk aynı kodla çalışsın).

    Çok günlü rezervasyon (örn. 18.11 09:00 - 20.11 09:00) tek kayıttır; ekranda her gün için yalnızca mesai (08:00-18:00) kısmı
    çizilir: ilk gün 09:00-18:00, aradaki gün 08:00-18:00, son gün 08:00-09:00. Mesai dışına düşen kısım hiç gösterilmez.
    Gerçek aralık gercek_baslangic / gercek_bitis alanlarında kalır (blokta okunur). cihaz_adi boşsa (yetkisi olmayan kullanıcı)
    blok yalnızca cihaz kullanımı nedeniyle dolu olarak görünür."""
    kayitlar = []
    mesai_bas, mesai_bit = ODA_TAKVIMI_SAATLERI[0], ODA_TAKVIMI_SAATLERI[-1] + 1
    for r in rezervasyonlar:
        bas, bit = zaman(r.get("baslangic_zamani")), zaman(r.get("bitis_zamani"))
        if bas is None or bit is None or bit <= bas:
            continue
        gun = bas.date()
        while gun <= (bit - timedelta(microseconds=1)).date():
            gun_bas = datetime.combine(gun, datetime.min.time())
            parca_bas = max(bas, gun_bas + timedelta(hours=mesai_bas))
            parca_bit = min(bit, gun_bas + timedelta(hours=mesai_bit))
            if parca_bas < parca_bit:
                kayitlar.append({
                    "rezervasyon_id": r.get("rezervasyon_id"), "oda_id": r.get("oda_id"), "cihaz": True, "durum": "CIHAZ",
                    "baslangic_zamani": parca_bas.isoformat(), "bitis_zamani": parca_bit.isoformat(),
                    "gercek_baslangic": bas.isoformat(), "gercek_bitis": bit.isoformat(),
                    "cihaz_adi": r.get("cihaz_adi"), "bolum_adi": r.get("bolum_adi"), "psikolog": None, "danisan_kod_id": None,
                })
            gun += timedelta(days=1)
    return kayitlar



def etkinlik_durumu_hesapla(etkinlik, simdi=None):
    """Oda etkinliğinin ekranda gösterilecek durumu."""
    if etkinlik.get("iptal_edildi_mi"):
        return "İptal Edildi"

    bas = zaman(etkinlik.get("baslangic_zamani"))
    bit = zaman(etkinlik.get("bitis_zamani"))

    if bas is None or bit is None:
        return "Planlandı"

    if simdi is None:
        simdi = datetime.now(bas.tzinfo)

    if simdi < bas:
        return "Planlandı"
    if simdi < bit:
        return "Devam Ediyor"
    return "Tamamlandı"


def etkinlik_kayitlari(etkinlikler):
    """Etkinlikleri takvimin günlük blok biçimine dönüştürür."""
    sonuc = []
    for e in etkinlikler:
        bas = zaman(e.get("baslangic_zamani"))
        bit = zaman(e.get("bitis_zamani"))
        if bas is None or bit is None or bit <= bas:
            continue

        durum_etiketi = etkinlik_durumu_hesapla(e)
        iptal = bool(e.get("iptal_edildi_mi"))

        gun = bas.date()
        while gun <= (bit - timedelta(microseconds=1)).date():
            gun_bas = datetime.combine(gun, datetime.min.time())
            parca_bas = max(bas, gun_bas)
            parca_bit = min(bit, gun_bas + timedelta(days=1))

            sonuc.append({
                "etkinlik_id": e.get("etkinlik_id"),
                "oda_id": e.get("oda_id"),
                "etkinlik": True,
                "durum": "ETKINLIK",
                "etkinlik_durumu": durum_etiketi,
                "iptal_edildi_mi": iptal,
                "etkinlik_adi": e.get("etkinlik_adi"),
                "katilimci_sayisi": e.get("katilimci_sayisi"),
                "baslangic_zamani": parca_bas.isoformat(),
                "bitis_zamani": parca_bit.isoformat(),
            })
            gun += timedelta(days=1)
    return sonuc


def takvim_kayit_onceligi(kayit):
    """İptal edilmiş etkinlikleri aktif kayıtların arkasına koyar."""
    return 1 if (
        kayit.get("etkinlik")
        and kayit.get("iptal_edildi_mi", False)
    ) else 0


def blok_haritasi(randevular):
    """{(oda_id, gün, saat): [randevu, ...]} – randevunun BAŞLADIĞI saat dilimine konur (süre _kapsanan_saat ile alınır)."""
    harita = {}
    for r in randevular:
        bas = zaman(r.get("baslangic_zamani"))
        if bas is None:
            continue
        harita.setdefault((r.get("oda_id"), bas.date(), bas.hour), []).append(r)
    return harita


def doluluk_hesapla(randevular, odalar, gunler, saatler):
    """Aktif odalar x çalışma günleri x saat dilimleri üzerinden doluluk.

    Döndürür: {"toplam": n, "dolu": n, "oran": 0..1 | None, "odalar": {oda_id: {"dolu", "toplam", "oran"}}, "en_yogun": oda ya da None}.
    Yalnızca aktif odalar ve Pazartesi-Cuma günleri sayılır; her randevu kapladığı saat dilimi kadar dolu sayar."""
    aktif = [o for o in odalar if o.get("aktif_mi", True)]
    calisma_gunleri = [g for g in gunler if g.weekday() < CALISMA_GUNU_SAYISI]
    saat_kumesi = set(saatler)
    toplam_oda = len(calisma_gunleri) * len(saatler)
    dolu_slotlar = {o["oda_id"]: set() for o in aktif}
    for r in randevular:
        bas, bit = zaman(r.get("baslangic_zamani")), zaman(r.get("bitis_zamani"))
        oda = r.get("oda_id")
        if bas is None or oda not in dolu_slotlar or bas.date() not in calisma_gunleri:
            continue
        for sira in range(_kapsanan_saat(bas, bit)):
            if bas.hour + sira in saat_kumesi:
                dolu_slotlar[oda].add((bas.date(), bas.hour + sira))
    odalar_ozet = {
        oda: {"dolu": len(slotlar), "toplam": toplam_oda, "oran": (len(slotlar) / toplam_oda) if toplam_oda else None}
        for oda, slotlar in dolu_slotlar.items()
    }
    toplam = toplam_oda * len(aktif)
    dolu = sum(len(s) for s in dolu_slotlar.values())
    en_yogun = None
    if dolu:
        en_yogun_id = max(odalar_ozet, key=lambda k: (odalar_ozet[k]["dolu"], -k))
        en_yogun = next(o for o in aktif if o["oda_id"] == en_yogun_id)
    return {"toplam": toplam, "dolu": dolu, "oran": (dolu / toplam) if toplam else None, "odalar": odalar_ozet, "en_yogun": en_yogun}


def yuzde(oran):
    return "—" if oran is None else f"%{round(oran * 100)}"


def oda_basligi(ad, doluluk_metni, genislik=16):
    """Sütun başlığı: oda adı en çok üç satıra bölünür (uzun adlar kırpılmasın), altında doluluk yüzdesi."""
    satirlar = textwrap.wrap(str(ad), width=genislik, break_long_words=False) or [""]
    if len(satirlar) > 3:
        satirlar = satirlar[:2] + [" ".join(satirlar[2:])]
    return "\n".join(satirlar + [f"{doluluk_metni} dolu"])


def baslik_yuksekligi(basliklar):
    """Başlık satırı yüksekliği: en uzun başlığın satır sayısına göre (11 px yazıda satır ~13 px)."""
    return 13 * max((b.count("\n") + 1 for b in basliklar), default=1) + 14


# ------------------------------------------------------------------ arayüz
TAKIP_ACIKLAMASI = (
    "Burada oda doluluğuna, randevulara, cihaz rezervasyonlarına ve oda etkinliklerine bakabilirsiniz; kayıt eklenmez ya da değiştirilmez.\n"
    "İşlem yapmak için Randevu Yönetimi, Cihaz Rezervasyonu ya da Oda Etkinlikleri sayfasına gidin."
)

BLOK_ACIKLAMALARI = {
    "randevu": "Randevuyu düzenlemek için Randevu Yönetimi sayfasına gidin.",
    "cihaz": "Rezervasyonu düzenlemek için Cihaz Rezervasyonu sayfasına gidin.",
    "etkinlik": "Etkinliği düzenlemek için Oda Etkinlikleri sayfasına gidin.",
}


class OdaKullanimiEkrani(QWidget):
    NAVY = "#16294B"
    SATIR_YUKSEKLIGI = 44

    def __init__(self, api_url, token, parent=None):
        super().__init__(parent)
        self.api_url = api_url.rstrip("/")
        self.token = token
        self.bugun = date.today()
        self.pazartesi = hafta_basi(self.bugun)
        self.secili_gun = self.bugun
        self.gorunum = "gun"                     # "gun" | "hafta"
        self.odalar = []
        self.randevular = []
        self.rezervasyonlar = []          # cihaz rezervasyonları (randevu biçiminde); randevu sayaçlarına girmez, doluluğa girer
        self.etkinlikler = []
        self._yukleniyor = False

        self._arayuz_kur()
        self.yenile()

    def _headers(self):
        return {"Authorization": f"Bearer {self.token}"}

    # ------------------------------------------------------------------ arayüz kurulumu
    def _kart(self, baslik, renk):
        kart = QFrame()
        kart.setStyleSheet("QFrame { background: white; border: 1px solid #E3EAF5; border-radius: 10px; } QLabel { border: none; }")
        icerik = QVBoxLayout(kart)
        icerik.setContentsMargins(14, 4, 14, 4)
        icerik.setSpacing(1)
        etiket = QLabel(baslik)
        etiket.setStyleSheet("color: #697993; font-size: 11px;")
        deger = QLabel("—")
        deger.setStyleSheet(f"color: {renk}; font-size: 19px; font-weight: bold;")
        alt = QLabel("")
        alt.setStyleSheet("color: #8A98B0; font-size: 10px;")
        alt.setWordWrap(True)
        icerik.addWidget(etiket)
        icerik.addWidget(deger)
        icerik.addWidget(alt)
        return kart, etiket, deger, alt

    def _arayuz_kur(self):
        self.setObjectName("odaKullanimi")
        self.setStyleSheet("""
            QWidget#odaKullanimi { background: #EAF0FA; }
            QLabel { color: #243653; }
            QPushButton#gezinme { background: white; color: #243653; border: 1px solid #C9D6EA; border-radius: 8px;
                padding: 5px 14px; font-weight: bold; }
            QPushButton#gezinme:hover { background: #F2F6FD; }
            QPushButton#segment { background: white; color: #243653; border: 1px solid #C9D6EA; padding: 5px 18px; font-weight: bold; }
            QPushButton#segment:checked { background: #16294B; color: white; border-color: #16294B; }
            QComboBox { background: white; color: #243653; border: 1px solid #C9D6EA; border-radius: 8px; padding: 6px 10px; min-width: 150px; }
        """)
        ana = QVBoxLayout(self)
        ana.setContentsMargins(0, 0, 0, 0)               # çevre boşluğunu ana pencere verir (kompakt sayfa: KOMPAKT_SAYFALAR)
        ana.setSpacing(8)

        # ---- gezinme satırı
        ust = QHBoxLayout()
        ust.setSpacing(8)
        self.btn_bugun = QPushButton("Bugün")
        self.btn_geri = QPushButton("‹")
        self.btn_ileri = QPushButton("›")
        for dugme in (self.btn_bugun, self.btn_geri, self.btn_ileri):
            dugme.setObjectName("gezinme")
            dugme.setCursor(Qt.PointingHandCursor)
        self.btn_geri.setFixedWidth(40)
        self.btn_ileri.setFixedWidth(40)
        self.lbl_baslik = QLabel("")
        self.lbl_baslik.setStyleSheet("color: #16294B; font-size: 19px; font-weight: bold; padding-left: 8px;")
        ust.addWidget(self.btn_bugun)
        ust.addWidget(self.btn_geri)
        ust.addWidget(self.btn_ileri)
        ust.addWidget(self.lbl_baslik)
        # Bu sayfadan kayıt eklenmez/değiştirilmez: küçük bir rozetle belirtilir, ayrıntı ipucundadır (sayfa kalabalıklaşmasın).
        self.takip_rozeti = BilgiRozeti(ROZET_METNI, TAKIP_ACIKLAMASI)
        ust.addWidget(self.takip_rozeti)
        ust.addStretch(1)
        self.etiket_oda = QLabel("Oda:")
        self.oda_sec = QComboBox()
        ust.addWidget(self.etiket_oda)
        ust.addWidget(self.oda_sec)
        ust.addSpacing(10)
        self.btn_gun = QPushButton("Gün")
        self.btn_hafta = QPushButton("Hafta")
        for dugme in (self.btn_gun, self.btn_hafta):
            dugme.setObjectName("segment")
            dugme.setCheckable(True)
            dugme.setCursor(Qt.PointingHandCursor)
        self.btn_gun.setStyleSheet("QPushButton { border-top-left-radius: 8px; border-bottom-left-radius: 8px; }")
        self.btn_hafta.setStyleSheet("QPushButton { border-top-right-radius: 8px; border-bottom-right-radius: 8px; border-left: none; }")
        self.gorunum_grubu = QButtonGroup(self)
        self.gorunum_grubu.setExclusive(True)
        self.gorunum_grubu.addButton(self.btn_gun)
        self.gorunum_grubu.addButton(self.btn_hafta)
        self.btn_gun.setChecked(True)
        ust.addWidget(self.btn_gun)
        ust.addWidget(self.btn_hafta)
        ana.addLayout(ust)

        # ---- gün şeridi
        serit = QHBoxLayout()
        serit.setSpacing(8)
        self.gun_dugmeleri = []
        self.gun_grubu = QButtonGroup(self)
        self.gun_grubu.setExclusive(True)
        for i in range(7):
            dugme = QPushButton("")
            dugme.setCheckable(True)
            dugme.setCursor(Qt.PointingHandCursor)
            dugme.setMinimumHeight(32)
            self.gun_grubu.addButton(dugme, i)
            self.gun_dugmeleri.append(dugme)
            serit.addWidget(dugme, 1)
        ana.addLayout(serit)

        # ---- özet kartları
        kartlar = QHBoxLayout()
        kartlar.setSpacing(12)
        self.kartlar = {}
        for anahtar, baslik, renk in [
            ("oda", "Aktif Oda", self.NAVY), ("gun", "Bugün", "#285CE6"),
            ("doluluk", "Haftalık Doluluk", "#16803C"), ("yogun", "En Yoğun Oda", "#B86B08"),
        ]:
            kart, etiket, deger, alt = self._kart(baslik, renk)
            self.kartlar[anahtar] = (etiket, deger, alt)
            kartlar.addWidget(kart, 1)
        ana.addLayout(kartlar)

        # ---- ızgara
        self.cerceve = QFrame()
        self.cerceve.setStyleSheet("QFrame#izgaraCercevesi { background: white; border: 1px solid #E3EAF5; border-radius: 12px; }")
        self.cerceve.setObjectName("izgaraCercevesi")
        cerceve_yerlesim = QVBoxLayout(self.cerceve)
        cerceve_yerlesim.setContentsMargins(6, 6, 6, 6)
        self.tablo = QTableWidget()
        self.tablo.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tablo.setSelectionMode(QAbstractItemView.NoSelection)
        self.tablo.setShowGrid(True)
        self.tablo.setFocusPolicy(Qt.NoFocus)
        # Satırlar mevcut yüksekliği eşit paylaşır (sığıyorsa kaydırma çubuğu çıkmaz); en az SATIR_YUKSEKLIGI yüksekliğinde kalır.
        self.tablo.verticalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tablo.verticalHeader().setMinimumSectionSize(self.SATIR_YUKSEKLIGI)
        self.tablo.verticalHeader().setFixedWidth(62)
        self.tablo.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tablo.horizontalHeader().setFixedHeight(42)
        self.tablo.horizontalHeader().setMinimumSectionSize(110)     # çok oda olursa sütunlar daralıp kırpılmasın; sığmazsa yatay kaydırma
        self.tablo.setStyleSheet("""
            QTableWidget { background: white; border: none; gridline-color: #EEF2F8; color: #243653; }
            QTableCornerButton::section { background: white; border: none; border-bottom: 1px solid #E3EAF5; border-right: 1px solid #E3EAF5; }
            QHeaderView::section { background: white; color: #16294B; font-weight: bold; font-size: 11px; padding: 3px;
                border: none; border-bottom: 1px solid #E3EAF5; border-right: 1px solid #EEF2F8; }
            QHeaderView::section:vertical { color: #8A98B0; font-weight: normal; border-bottom: 1px solid #EEF2F8; border-right: 1px solid #E3EAF5;
                padding-right: 8px; }
        """)
        cerceve_yerlesim.addWidget(self.tablo)
        self.bos_mesaj = QLabel("")
        self.bos_mesaj.setAlignment(Qt.AlignCenter)
        self.bos_mesaj.setStyleSheet("color: #697993; font-size: 14px; padding: 40px;")
        self.bos_mesaj.hide()
        cerceve_yerlesim.addWidget(self.bos_mesaj)
        ana.addWidget(self.cerceve, 1)

        # ---- gösterge ve durum
        alt = QHBoxLayout()
        alt.setSpacing(16)
        for kod in ("PLANLANDI", "TAMAMLANDI", "GELMEDI"):
            bg, fg = DURUM_RENKLERI[kod]
            nokta = QLabel(f"<span style='color:{fg}; font-size:15px;'>■</span>  {DURUM_ETIKETLERI[kod]}")
            nokta.setStyleSheet("color: #243653; font-size: 12px;")
            alt.addWidget(nokta)
        gizli = QLabel(f"<span style='color:{GIZLI_RENK[1]}; font-size:15px;'>■</span>  Dolu (başka psikolog)")
        gizli.setStyleSheet("color: #243653; font-size: 12px;")
        alt.addWidget(gizli)
        cihaz = QLabel(f"<span style='color:{CIHAZ_RENK[1]}; font-size:15px;'>■</span>  Cihaz rezervasyonu")
        cihaz.setStyleSheet("color: #243653; font-size: 12px;")
        alt.addWidget(cihaz)

        etkinlik_gosterge = QLabel(
            f"<span style='color:{ETKINLIK_RENK[1]}; "
            "font-size:15px;'>■</span>  Oda etkinliği"
        )
        etkinlik_gosterge.setStyleSheet(
            "color: #243653; font-size: 12px;"
        )
        alt.addWidget(etkinlik_gosterge)

        iptal = QLabel("İptal edilen randevu ve rezervasyonlar gösterilmez")
        iptal.setStyleSheet("color: #8A98B0; font-size: 12px;")
        alt.addWidget(iptal)
        alt.addStretch(1)
        self.durum_etiketi = QLabel("")
        self.durum_etiketi.setStyleSheet("color: #8A98B0; font-size: 12px;")
        alt.addWidget(self.durum_etiketi)
        ana.addLayout(alt)

        self.btn_bugun.clicked.connect(self.bugune_git)
        self.btn_geri.clicked.connect(self.onceki_hafta)
        self.btn_ileri.clicked.connect(self.sonraki_hafta)
        self.btn_gun.clicked.connect(self._gun_gorunumu)
        self.btn_hafta.clicked.connect(self._hafta_gorunumu)
        self.gun_grubu.idClicked.connect(self._gun_secildi)
        self.oda_sec.currentIndexChanged.connect(self._oda_degisti)

    # ------------------------------------------------------------------ gezinme
    def bugune_git(self):
        self.bugun = date.today()
        self.secili_gun = self.bugun
        self._haftayi_ac(hafta_basi(self.bugun))

    def onceki_hafta(self):
        self._haftayi_ac(self.pazartesi - timedelta(days=7), korunan_gun_farki=True)

    def sonraki_hafta(self):
        self._haftayi_ac(self.pazartesi + timedelta(days=7), korunan_gun_farki=True)

    def _haftayi_ac(self, pazartesi, korunan_gun_farki=False):
        if korunan_gun_farki:
            self.secili_gun = pazartesi + timedelta(days=(self.secili_gun - self.pazartesi).days)
        self.pazartesi = pazartesi
        self.yenile()

    def _gun_gorunumu(self):
        self.gorunum = "gun"
        self._goster()

    def _hafta_gorunumu(self):
        self.gorunum = "hafta"
        self._goster()

    def _gun_secildi(self, sira):
        self.secili_gun = self.pazartesi + timedelta(days=sira)
        self.gorunum = "gun"
        self.btn_gun.setChecked(True)
        self._goster()

    def _oda_degisti(self, *_):
        if self.gorunum == "hafta":
            self._goster()

    # ------------------------------------------------------------------ veri
    def yenile(self):
        if self._yukleniyor:
            return
        self._yukleniyor = True
        try:
            try:
                yanit = oturum_kontrollu_istek(
                    "GET", f"{self.api_url}/api/oda-kullanimi", headers=self._headers(), timeout=10,
                    params={"baslangic": self.pazartesi.isoformat(), "bitis": (self.pazartesi + timedelta(days=6)).isoformat()},
                )
                if oturum_hatasi_mi(yanit):
                    return
                yanit.raise_for_status()
                veri = yanit.json()
            except (requests.RequestException, ValueError) as hata:
                QMessageBox.warning(self, "Oda Kullanımı", f"Oda kullanım bilgisi alınamadı:\n{istek_hatasi_metni(hata)}")
                return
        finally:
            self._yukleniyor = False
        self.odalar = veri.get("odalar", [])
        self.randevular = veri.get("randevular", [])
        self.rezervasyonlar = rezervasyon_kayitlari(veri.get("rezervasyonlar", []))
        self.etkinlikler = etkinlik_kayitlari(veri.get("etkinlikler", []))
        self._oda_listesini_doldur()
        self._goster()
        self.durum_etiketi.setText(f"Son güncelleme: {datetime.now().strftime('%H:%M')}")

    def _tum_kayitlar(self):
        """Takvimde gösterilecek bütün kayıtlar."""
        return self.randevular + self.rezervasyonlar + self.etkinlikler

    def _doluluk_kayitlari(self):
        """İptal edilen etkinlikleri doluluk hesabından çıkar."""
        aktif_etkinlikler = [
            e for e in self.etkinlikler
            if not e.get("iptal_edildi_mi", False)
        ]
        return self.randevular + self.rezervasyonlar + aktif_etkinlikler

    def _aktif_odalar(self):
        return [o for o in self.odalar if o.get("aktif_mi", True)]

    def _oda_listesini_doldur(self):
        onceki = self.oda_sec.currentData()
        self.oda_sec.blockSignals(True)
        self.oda_sec.clear()
        for oda in self._aktif_odalar():
            self.oda_sec.addItem(str(oda.get("oda_adi")), oda.get("oda_id"))
        indeks = self.oda_sec.findData(onceki) if onceki is not None else -1
        self.oda_sec.setCurrentIndex(max(indeks, 0))
        self.oda_sec.blockSignals(False)

    # ------------------------------------------------------------------ görünüm
    def _gunler(self):
        return [self.pazartesi + timedelta(days=i) for i in range(7)]

    def _goster(self):
        saatler = saat_dilimleri(self._tum_kayitlar())
        gunler = self._gunler()
        self.lbl_baslik.setText(hafta_basligi(self.pazartesi))
        hafta_modu = self.gorunum == "hafta"
        self.etiket_oda.setVisible(hafta_modu)
        self.oda_sec.setVisible(hafta_modu)
        self.btn_gun.setChecked(not hafta_modu)
        self.btn_hafta.setChecked(hafta_modu)
        self._serit_doldur(gunler)
        self._kartlari_doldur(gunler, saatler)
        self._izgara_doldur(gunler, saatler)

    def _serit_doldur(self, gunler):
        sayilar = {}
        for r in self.randevular:
            bas = zaman(r.get("baslangic_zamani"))
            if bas is not None:
                sayilar[bas.date()] = sayilar.get(bas.date(), 0) + 1
        for i, (dugme, gun) in enumerate(zip(self.gun_dugmeleri, gunler)):
            sayi = sayilar.get(gun, 0)
            dugme.setText(f"{GUN_KISA[i]} {gun.day}  ·  {sayi} randevu" if sayi else f"{GUN_KISA[i]} {gun.day}")
            bugun, secili, hafta_sonu = gun == self.bugun, gun == self.secili_gun and self.gorunum == "gun", i >= CALISMA_GUNU_SAYISI
            dugme.setChecked(secili)
            kenar = "#285CE6" if bugun else "#D5DFEF"
            yazi = "#8A98B0" if hafta_sonu else "#243653"
            dugme.setStyleSheet(
                f"QPushButton {{ background: white; color: {yazi}; border: 2px solid {kenar}; border-radius: 10px; font-weight: bold; padding: 4px; }}"
                "QPushButton:hover { background: #F2F6FD; }"
                "QPushButton:checked { background: #16294B; color: white; border-color: #16294B; }"
            )

    def _kartlari_doldur(self, gunler, saatler):
        aktif = self._aktif_odalar()
        etiket, deger, alt = self.kartlar["oda"]
        deger.setText(str(len(aktif)))
        pasif = len(self.odalar) - len(aktif)
        alt.setText(f"{pasif} pasif oda" if pasif else f"toplam {len(self.odalar)} oda")

        gun_randevulari = [r for r in self.randevular if (zaman(r.get("baslangic_zamani")) or datetime.min).date() == self.secili_gun]
        etiket, deger, alt = self.kartlar["gun"]
        etiket.setText("Bugün" if self.secili_gun == self.bugun else f"{self.secili_gun.day} {AY_UZUN[self.secili_gun.month - 1]}")
        deger.setText(str(len(gun_randevulari)))
        parcalar = []
        for kod, ad in (("TAMAMLANDI", "tamamlandı"), ("PLANLANDI", "planlı"), ("GELMEDI", "gelmedi")):
            sayi = sum(1 for r in gun_randevulari if r.get("durum") == kod)
            if sayi:
                parcalar.append(f"{sayi} {ad}")
        alt.setText(" · ".join(parcalar) or "randevu yok")

        ozet = doluluk_hesapla(self._doluluk_kayitlari(), self.odalar, gunler, saatler)
        etiket, deger, alt = self.kartlar["doluluk"]
        deger.setText(yuzde(ozet["oran"]))
        alt.setText(f"{ozet['dolu']} / {ozet['toplam']} saat dilimi dolu" if ozet["toplam"] else "aktif oda yok")
        etiket, deger, alt = self.kartlar["yogun"]
        if ozet["en_yogun"] is None:
            deger.setText("—")
            alt.setText("bu hafta kullanım yok")
        else:
            deger.setText(str(ozet["en_yogun"].get("oda_adi")))
            alt.setText(f"{yuzde(ozet['odalar'][ozet['en_yogun']['oda_id']]['oran'])} doluluk")

    # ------------------------------------------------------------------ ızgara
    def _blok(self, r):
        """Bir randevuyu ya da cihaz rezervasyonunu renkli blok olarak çizer; başkasının randevusunda (kimlik gelmediyse) yalnızca
        'Dolu' görünür. Cihaz rezervasyonunda cihaz adı gelmediyse (yetkisiz kullanıcı) 'Dolu · Cihaz kullanımı' görünür."""
        cihaz = bool(r.get("cihaz"))
        etkinlik = bool(r.get("etkinlik"))
        gizli = r.get("cihaz_adi") is None if cihaz else (r.get("psikolog") is None and r.get("danisan_kod_id") is None)
        bg, fg = CIHAZ_RENK if cihaz else (GIZLI_RENK if gizli else DURUM_RENKLERI.get(r.get("durum"), DURUM_RENKLERI["PLANLANDI"]))
        if etkinlik:
            bg, fg = ETKINLIK_RENK
        kutu = TiklaninceAciklayanKutu(BLOK_ACIKLAMALARI["etkinlik" if etkinlik else "cihaz" if cihaz else "randevu"])
        kutu.setObjectName("blok")
        kutu.setStyleSheet(f"QFrame#blok {{ background: {bg}; border-left: 4px solid {fg}; border-radius: 6px; }} QLabel {{ background: transparent; border: none; }}")
        yerlesim = QVBoxLayout(kutu)
        yerlesim.setContentsMargins(9, 2, 6, 2)
        yerlesim.setSpacing(0)
        bas, bit = zaman(r.get("baslangic_zamani")), zaman(r.get("bitis_zamani"))
        saat = f"{bas:%H:%M} – {bit:%H:%M}" if bas and bit else ""
        if cihaz:
            # Blok yalnızca mesai kısmını çizer; yazıdaki aralık rezervasyonun gerçek aralığıdır (çok günlüyse tarihli).
            gb, gt = zaman(r.get("gercek_baslangic")), zaman(r.get("gercek_bitis"))
            if gb and gt:
                saat = f"{gb:%H:%M} – {gt:%H:%M}" if gb.date() == gt.date() else f"{gb:%d.%m %H:%M} – {gt:%d.%m %H:%M}"
        if etkinlik:
            satirlar = [
                (
                    str(r.get("etkinlik_adi") or "Oda Etkinliği"),
                    f"color: {fg}; font-weight: bold; font-size: 12px;"
                ),
                (
                    "Oda etkinliği · " +
                    str(r.get("etkinlik_durumu") or "Planlandı"),
                    f"color: {fg}; font-size: 10px;"
                ),
                (saat, f"color: {fg}; font-size: 9px;"),
            ]
        elif cihaz and gizli:
            satirlar = [
                ("Dolu", f"color: {fg}; font-weight: bold; font-size: 12px;"),
                ("Cihaz kullanımı", f"color: {fg}; font-size: 10px;"),
                (saat, f"color: {fg}; font-size: 9px;"),
            ]
        elif cihaz:
            satirlar = [
                (str(r.get("cihaz_adi")), f"color: {fg}; font-weight: bold; font-size: 12px;"),
                (str(r.get("bolum_adi") or "—"), f"color: {fg}; font-size: 10px;"),
                (saat, f"color: {fg}; font-size: 9px;"),
            ]
        elif gizli:
            satirlar = [("Dolu", f"color: {fg}; font-weight: bold; font-size: 12px;"), (saat, f"color: {fg}; font-size: 10px;")]
        else:
            ek = " · " + gorusme_etiketi(r.get("gorusme_tipi")) if r.get("gorusme_tipi") == "ONLINE" else ""
            satirlar = [
                (str(r.get("psikolog") or "—"), f"color: {fg}; font-weight: bold; font-size: 12px;"),
                (str(r.get("danisan_kod_id") or "—"), f"color: {fg}; font-size: 10px;"),
                (f"{saat}{ek}", f"color: {fg}; font-size: 9px;"),
            ]
        for metin, stil in satirlar:
            etiket = QLabel(metin)
            etiket.setStyleSheet(stil)
            yerlesim.addWidget(etiket)
        yerlesim.addStretch(1)
        return kutu

    def _izgara_doldur(self, gunler, saatler):
        aktif = self._aktif_odalar()
        self.tablo.clearSpans()
        self.tablo.clearContents()
        if not aktif:
            self.tablo.setVisible(False)
            self.bos_mesaj.setText("Tanımlı aktif oda yok.")
            self.bos_mesaj.setVisible(True)
            return
        self.tablo.setVisible(True)
        self.bos_mesaj.setVisible(False)

        harita = blok_haritasi(self._tum_kayitlar())
        ozet = doluluk_hesapla(self._doluluk_kayitlari(), self.odalar, [self.secili_gun] if self.gorunum == "gun" else gunler, saatler)
        if self.gorunum == "gun":
            sutunlar = [(o["oda_id"], oda_basligi(o.get("oda_adi"), yuzde(ozet["odalar"][o["oda_id"]]["oran"]))) for o in aktif]
            anahtar = lambda sutun, saat: (sutun[0], self.secili_gun, saat)
        else:
            oda_id = self.oda_sec.currentData()
            sutunlar = [(g, f"{GUN_KISA[i]} {g.day}") for i, g in enumerate(gunler)]
            anahtar = lambda sutun, saat: (oda_id, sutun[0], saat)

        self.tablo.setColumnCount(len(sutunlar))
        self.tablo.setRowCount(len(saatler))
        self.tablo.horizontalHeader().setFixedHeight(baslik_yuksekligi([etiket for _, etiket in sutunlar]))   # başlık satırı uzun adlara göre
        self.tablo.setHorizontalHeaderLabels([etiket for _, etiket in sutunlar])
        self.tablo.setVerticalHeaderLabels([f"{s:02d}:00" for s in saatler])

        yerlesenler = set()
        for sutun_no, sutun in enumerate(sutunlar):
            hafta_sonu = self.gorunum == "hafta" and sutun[0].weekday() >= CALISMA_GUNU_SAYISI
            for satir_no, saat in enumerate(saatler):
                if hafta_sonu:                                   # hafta sonu sütunu soluk görünür
                    oge = QTableWidgetItem("")
                    oge.setBackground(self._renk("#F8FAFC"))
                    self.tablo.setItem(satir_no, sutun_no, oge)
                if (satir_no, sutun_no) in yerlesenler:
                    continue
                kayitlar = harita.get(anahtar(sutun, saat), [])
                if not kayitlar:
                    continue

                # Aktif kayıtlar iptal edilmiş etkinliklerden önce görünür.
                kayitlar = sorted(
                    kayitlar,
                    key=takvim_kayit_onceligi
                )
                r = kayitlar[0]
                kapsam = min(_kapsanan_saat(zaman(r.get("baslangic_zamani")), zaman(r.get("bitis_zamani"))), len(saatler) - satir_no)
                self.tablo.setCellWidget(satir_no, sutun_no, self._blok_kapsayici(r, len(kayitlar)))
                if kapsam > 1:
                    self.tablo.setSpan(satir_no, sutun_no, kapsam, 1)
                    yerlesenler.update((satir_no + k, sutun_no) for k in range(1, kapsam))
        self._simdiki_saate_kaydir(saatler)

    def _blok_kapsayici(self, r, adet):
        """Blok + (aynı hücrede birden fazla randevu varsa) '+N' bilgisi."""
        blok = self._blok(r)
        if adet > 1:
            ek = QLabel(f"+{adet - 1}")
            ek.setStyleSheet("color: #64748B; font-size: 10px; font-weight: bold; background: transparent; border: none;")
            blok.layout().addWidget(ek)
        return blok

    @staticmethod
    def _renk(kod):
        from PySide6.QtGui import QColor
        return QColor(kod)

    def _simdiki_saate_kaydir(self, saatler):
        """Bugünün görünümünde şimdiki saat satırı görünür olsun (satır sayısı fazlaysa)."""
        simdi = datetime.now().hour
        if simdi in saatler and self.secili_gun == self.bugun:
            self.tablo.scrollTo(self.tablo.model().index(saatler.index(simdi), 0), QAbstractItemView.PositionAtCenter)
