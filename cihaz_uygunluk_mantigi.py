"""Cihaz Uygunluğu takviminin saf (arayüzsüz) mantığı.

`/api/cihaz-uygunluk` yanıtındaki dönemlerden bir gün için durum, saat çizelgesi, belirli bir
aralıkta müsaitlik, bugün sayacı ve filtreleme üretir. Qt'ye bağlı değildir; ayrıca test edilir.

Kurallar (sunucudaki rezervasyon kurallarıyla uyumlu):
  * Bakım, kalibrasyon, arıza ve kullanım dışı dönemleri cihazı o aralıkta KULLANILAMAZ yapar.
  * Rezervasyon cihazı yalnızca o saatlerde meşgul eder (gün kısmen dolu olur).
  * Bir günde birden çok engel varsa en öncelikli olan gösterilir:
    kullanım dışı > arıza > bakım > kalibrasyon.
"""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Optional

# Gün hücresi / durum kodları
MUSAIT, KISMEN, DOLU = "MUSAIT", "KISMEN", "DOLU"
BAKIM, KALIBRASYON, ARIZA, KULLANIM_DISI = "BAKIM", "KALIBRASYON", "ARIZA", "KULLANIM_DISI"
REZERVASYON = "REZERVASYON"

# Büyük sayı = daha öncelikli engel
ENGEL_ONCELIGI = {KULLANIM_DISI: 4, ARIZA: 3, BAKIM: 2, KALIBRASYON: 1}

KOD_ADLARI = {
    MUSAIT: "Müsait", KISMEN: "Kısmen dolu", DOLU: "Dolu", BAKIM: "Bakımda",
    KALIBRASYON: "Kalibrasyonda", ARIZA: "Arızalı", KULLANIM_DISI: "Kullanım dışı",
}
CALISMA_BASLANGIC_SAATI = 8      # takvimdeki mesai penceresi (haftalik_takvim.py ile aynı: 08:00-18:00)
CALISMA_BITIS_SAATI = 18


@dataclass(frozen=True)
class Donem:
    tur: str
    baslangic: datetime
    bitis: Optional[datetime]            # None = bitişi belli değil (örn. açık arıza)
    kaynak: str = "kayit"

    def kesisir(self, bas, bit):
        """[bas, bit) aralığıyla kesişiyor mu?"""
        return self.baslangic < bit and (self.bitis is None or self.bitis > bas)


@dataclass(frozen=True)
class GunDurumu:
    kod: str
    engeller: tuple = ()                 # o günle kesişen engeller (öncelik sırasıyla)
    rezervasyonlar: tuple = ()           # o güne kırpılmış (başlangıç, bitiş) çiftleri
    dolu_dakika: int = 0                 # mesai penceresinde rezervasyonla dolu dakika

    @property
    def engelli(self):
        return self.kod in ENGEL_ONCELIGI


def _zaman(deger):
    return deger if isinstance(deger, datetime) else datetime.fromisoformat(str(deger))


def donemleri_coz(cihaz):
    """Sunucu yanıtındaki cihaz sözlüğünden Donem listesi üretir (bozuk kayıtlar atlanır)."""
    sonuc = []
    for d in cihaz.get("donemler", []):
        try:
            bas = _zaman(d["baslangic"])
            bit = None if d.get("bitis") in (None, "") else _zaman(d["bitis"])
        except (KeyError, ValueError, TypeError):
            continue
        if bit is not None and bit <= bas:
            continue
        sonuc.append(Donem(d.get("tur", ""), bas, bit, d.get("kaynak", "kayit")))
    return sonuc


def _gun_siniri(gun):
    bas = datetime.combine(gun, time.min)
    return bas, bas + timedelta(days=1)


def _engeller(donemler, bas, bit):
    liste = [d for d in donemler if d.tur in ENGEL_ONCELIGI and d.kesisir(bas, bit)]
    return sorted(liste, key=lambda d: (-ENGEL_ONCELIGI[d.tur], d.baslangic))


def _birlestir(araliklar):
    sonuc = []
    for bas, bit in sorted(araliklar):
        if sonuc and bas <= sonuc[-1][1]:
            sonuc[-1] = (sonuc[-1][0], max(sonuc[-1][1], bit))
        else:
            sonuc.append((bas, bit))
    return sonuc


def gun_durumu(donemler, gun, simdi=None):
    """Bir gün için durum: en öncelikli engel varsa o, yoksa rezervasyon yoğunluğuna göre müsait/kısmen/dolu.

    `simdi` verilirse ve gün bugünse, yalnızca şimdiden sonra süren engeller günün durumunu belirler:
    sabah açılıp öğleden önce çözülen bir arıza bugünü "Arızalı" yapmaz (cihaz artık kullanılabilir).
    Geçmiş ve gelecek günlerde tüm gün esas alınır.
    """
    gun_bas, gun_bit = _gun_siniri(gun)
    engel_bas = max(gun_bas, simdi) if simdi is not None and simdi.date() == gun else gun_bas
    engeller = _engeller(donemler, engel_bas, gun_bit)
    rezervasyonlar = tuple(sorted(
        (max(d.baslangic, gun_bas), min(d.bitis, gun_bit))
        for d in donemler if d.tur == REZERVASYON and d.bitis is not None and d.kesisir(gun_bas, gun_bit)))
    mesai_bas = datetime.combine(gun, time(CALISMA_BASLANGIC_SAATI))
    mesai_bit = datetime.combine(gun, time(CALISMA_BITIS_SAATI))
    kirpilmis = [(max(b, mesai_bas), min(s, mesai_bit)) for b, s in rezervasyonlar if b < mesai_bit and s > mesai_bas]
    dolu = sum(int((s - b).total_seconds() // 60) for b, s in _birlestir(kirpilmis))
    if engeller:
        return GunDurumu(engeller[0].tur, tuple(engeller), rezervasyonlar, dolu)
    toplam = (CALISMA_BITIS_SAATI - CALISMA_BASLANGIC_SAATI) * 60
    if not rezervasyonlar:
        return GunDurumu(MUSAIT)
    return GunDurumu(DOLU if dolu >= toplam else KISMEN, (), rezervasyonlar, dolu)


def saat_cizelgesi(donemler, gun, baslangic_saati=CALISMA_BASLANGIC_SAATI, bitis_saati=CALISMA_BITIS_SAATI):
    """Her saatlik dilim için (saat, durum): MUSAIT / REZERVASYON / engel türü."""
    sonuc = []
    for saat in range(baslangic_saati, bitis_saati):
        bas = datetime.combine(gun, time(saat))
        bit = bas + timedelta(hours=1)
        engel = _engeller(donemler, bas, bit)
        if engel:
            sonuc.append((saat, engel[0].tur))
        elif any(d.tur == REZERVASYON and d.kesisir(bas, bit) for d in donemler):
            sonuc.append((saat, REZERVASYON))
        else:
            sonuc.append((saat, MUSAIT))
    return sonuc


def musait_mi(donemler, baslangic, bitis):
    """[baslangic, bitis) aralığında cihaz müsait mi? (müsait_mi, engelleyen türler önem sırasıyla)"""
    if bitis <= baslangic:
        raise ValueError("Bitiş zamanı başlangıçtan sonra olmalıdır.")
    engeller = [d.tur for d in _engeller(donemler, baslangic, bitis)]
    if any(d.tur == REZERVASYON and d.kesisir(baslangic, bitis) for d in donemler):
        engeller.append(REZERVASYON)
    benzersiz = list(dict.fromkeys(engeller))
    return (not benzersiz), benzersiz


def su_anki_durum(donemler, simdi):
    """'Şu an' sütunu: engel türü, o an rezervasyonlu ise REZERVASYON, değilse MUSAIT."""
    engel = _engeller(donemler, simdi, simdi + timedelta(microseconds=1))
    if engel:
        return engel[0].tur
    if any(d.tur == REZERVASYON and d.kesisir(simdi, simdi + timedelta(microseconds=1)) for d in donemler):
        return REZERVASYON
    return MUSAIT


def bugun_ozeti(cihazlar, bugun, simdi=None):
    """Bugün için sayaçlar: musait (müsait + kısmen dolu), dolu, bakim, kalibrasyon, ariza, kullanim_disi."""
    sayac = {"musait": 0, "dolu": 0, "bakim": 0, "kalibrasyon": 0, "ariza": 0, "kullanim_disi": 0}
    esle = {MUSAIT: "musait", KISMEN: "musait", DOLU: "dolu", BAKIM: "bakim", KALIBRASYON: "kalibrasyon",
            ARIZA: "ariza", KULLANIM_DISI: "kullanim_disi"}
    for cihaz in cihazlar:
        sayac[esle[gun_durumu(donemleri_coz(cihaz), bugun, simdi).kod]] += 1
    return sayac


def hafta_basi(gun):
    """Verilen günün haftasının Pazartesi'si."""
    return gun - timedelta(days=gun.weekday())


def hafta_gunleri(gun):
    basi = hafta_basi(gun)
    return [basi + timedelta(days=i) for i in range(7)]


_TR_KUCUK = str.maketrans({"İ": "i", "I": "ı"})


def tr_kucult(metin):
    return str(metin or "").translate(_TR_KUCUK).lower()


def sorunlu_mu(cihaz, gunler, simdi=None):
    """Haftada engeli olan ya da kalibrasyon/bakım uyarısı taşıyan cihaz."""
    donemler = donemleri_coz(cihaz)
    if any(gun_durumu(donemler, g, simdi).engelli for g in gunler):
        return True
    return bool(cihaz.get("kalibrasyon_uyari") or cihaz.get("bakim_uyari"))


def filtrele(cihazlar, arama="", mod="TUMU", gunler=None, bugun=None, musait_idler=None, simdi=None):
    """Arama (kod/ad), mod (TUMU | BUGUN_MUSAIT | SORUNLU) ve 'müsait cihaz bul' sonucuna göre süz."""
    aranan = tr_kucult(arama).strip()
    sonuc = []
    for cihaz in cihazlar:
        if aranan and aranan not in tr_kucult(f"{cihaz.get('envanter_kodu', '')} {cihaz.get('cihaz_adi', '')}"):
            continue
        if musait_idler is not None and cihaz.get("cihaz_id") not in musait_idler:
            continue
        if mod == "BUGUN_MUSAIT" and gun_durumu(donemleri_coz(cihaz), bugun or date.today(), simdi).kod not in (MUSAIT, KISMEN):
            continue
        if mod == "SORUNLU" and not sorunlu_mu(cihaz, gunler or hafta_gunleri(bugun or date.today()), simdi):
            continue
        sonuc.append(cihaz)
    return sonuc


def musait_cihazlar(cihazlar, baslangic, bitis):
    """Aralıkta müsait olan cihazların kimlik kümesi."""
    return {c["cihaz_id"] for c in cihazlar if musait_mi(donemleri_coz(c), baslangic, bitis)[0]}


# ----------------------------------------------------------------------------------------------
# Metin üreticiler (ekranda gösterilen Türkçe açıklamalar)
# ----------------------------------------------------------------------------------------------
AYLAR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
GUN_ADLARI = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
GUN_KISA = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]

ENGEL_ACIKLAMA = {
    BAKIM: "Bakım süresince rezerve edilemez.",
    KALIBRASYON: "Kalibrasyon süresince rezerve edilemez.",
    ARIZA: "Arıza çözülene kadar rezerve edilemez.",
    KULLANIM_DISI: "Cihaz kullanım dışı olduğu için rezerve edilemez.",
}


def tarih_yazi(gun, yil=True):
    """4 Kasım 2026 (yil=False ise 4 Kasım)."""
    return f"{gun.day} {AYLAR[gun.month - 1]}" + (f" {gun.year}" if yil else "")


def uzun_tarih(gun):
    return f"{tarih_yazi(gun)} {GUN_ADLARI[gun.weekday()]}"


def hafta_etiketi(gunler):
    """2 – 8 Kasım 2026  /  28 Ekim – 3 Kasım 2026."""
    ilk, son = gunler[0], gunler[-1]
    if ilk.month == son.month and ilk.year == son.year:
        return f"{ilk.day} – {son.day} {AYLAR[son.month - 1]} {son.year}"
    return f"{tarih_yazi(ilk, yil=ilk.year != son.year)} – {tarih_yazi(son)}"


def _an(zaman):
    return f"{tarih_yazi(zaman.date(), yil=False)} {zaman:%H:%M}"


def donem_aciklamasi(donem):
    """Bir engel döneminin kısa, kişisel veri içermeyen açıklaması."""
    ad = {BAKIM: "Bakım", KALIBRASYON: "Kalibrasyon", ARIZA: "Arıza", KULLANIM_DISI: "Kullanım dışı"}.get(donem.tur, donem.tur)
    if donem.kaynak == "durum":
        return f"{ad}: cihazın durumu bu şekilde işaretli (bitiş tarihi belirsiz)"
    if donem.tur in (BAKIM, KALIBRASYON):                                 # gün aralığı; bitiş ertesi gün 00:00
        son_gun = (donem.bitis - timedelta(seconds=1)).date() if donem.bitis else None
        ilk_gun = donem.baslangic.date()
        aralik = tarih_yazi(ilk_gun, yil=False) if son_gun in (None, ilk_gun) else \
            f"{tarih_yazi(ilk_gun, yil=False)} – {tarih_yazi(son_gun, yil=False)}"
        return f"{ad}: {aralik}"
    if donem.bitis is None:
        return f"{ad}: {_an(donem.baslangic)}'den beri açık"
    return f"{ad}: {_an(donem.baslangic)} – {_an(donem.bitis)}"


def uyari_satirlari(cihaz, bugun):
    """Cihazın kalibrasyon/bakım uyarıları: [(metin, ciddiyet)], ciddiyet 'kritik' | 'uyari'."""
    satirlar = []
    gecerlilik = cihaz.get("kalibrasyon_gecerlilik")
    if gecerlilik and cihaz.get("kalibrasyon_uyari"):
        g = date.fromisoformat(str(gecerlilik)[:10])
        if cihaz["kalibrasyon_uyari"] == "SURESI_DOLDU":
            satirlar.append((f"Kalibrasyon süresi doldu ({tarih_yazi(g)}, {(bugun - g).days} gün önce)", "kritik"))
        else:
            satirlar.append((f"Kalibrasyon süresi yaklaşıyor ({tarih_yazi(g)}, {(g - bugun).days} gün kaldı)", "uyari"))
    sonraki = cihaz.get("sonraki_bakim")
    if sonraki and cihaz.get("bakim_uyari"):
        s = date.fromisoformat(str(sonraki)[:10])
        if cihaz["bakim_uyari"] == "GECIKTI":
            satirlar.append((f"Bakım gecikti ({tarih_yazi(s)}, {(bugun - s).days} gün önce)", "kritik"))
        else:
            satirlar.append((f"Bakım zamanı yaklaşıyor ({tarih_yazi(s)}, {(s - bugun).days} gün kaldı)", "uyari"))
    return satirlar


def gun_ipucu(gun, durum):
    """Gün hücresinin üzerine gelince görünen açıklama."""
    satirlar = [f"{uzun_tarih(gun)} — {KOD_ADLARI[durum.kod]}"]
    satirlar += [donem_aciklamasi(e) for e in durum.engeller]
    for bas, bit in durum.rezervasyonlar:
        satirlar.append(f"Rezervasyon: {bas:%H:%M} – {'24:00' if bit.hour == 0 and bit.minute == 0 else bit.strftime('%H:%M')}")
    if durum.engelli:
        satirlar.append(ENGEL_ACIKLAMA[durum.kod])
    return "\n".join(satirlar)


def rezervasyon_onerisi(durum, cizelge, gun, bugun, simdi):
    """Gün detayındaki 'Rezervasyon yap' için ilk uygun saat: ('HH:00', 'HH+1:00', None) ya da (None, None, neden)."""
    if gun < bugun:
        return None, None, "Geçmiş günlere rezervasyon yapılamaz."
    if durum.engelli:
        return None, None, ENGEL_ACIKLAMA[durum.kod]
    en_erken = 0
    if gun == bugun:                                                       # bugünse bir sonraki tam saatten başla
        dakika = simdi.hour * 60 + simdi.minute
        en_erken = (dakika // 30 + 1) * 30
    for saat, kod in cizelge:
        if kod == MUSAIT and saat * 60 >= en_erken:
            return f"{saat:02d}:00", f"{saat + 1:02d}:00", None
    return None, None, "Bu gün mesai saatlerinde boş saat kalmadı."
