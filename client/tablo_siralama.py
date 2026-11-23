"""TKYS - Tablo başlığına tıklayınca sıralama.

Başlığa bir kez tıklayınca artan, ikinci kez azalan sıralanır; başlıktaki ok yönü gösterir. Sıralama doğru anlaşılır:
  * Türkçe harf sırası (a b c ç d e f g ğ h ı i j k l m n o ö p r s ş t u ü v y z),
  * sayılar sayı gibi (9, 10'dan önce gelir; "E-2", "E-10"dan önce gelir; "1.250,50" tutarı sayıdır),
  * tarihler tarih gibi (dd.mm.yyyy [hh:mm]),
  * boş değerler ("—", "-") her iki yönde de en sonda.
Durum rozeti gibi hücre bileşenleri ve düğmeler satırla birlikte taşınır. Düğme sütunları (İŞLEM) sıralanmaz.
Tablo yeniden doldurulunca (Yenile, arama...) sıra sunucunun sırasına döner ve ok kaybolur.

Qt'nin kendi sıralaması (sortItems) metni alfabetik karşılaştırdığı için, sıralamadan hemen önce her hücrenin görünen metni
geçici olarak bir sıra numarasıyla değiştirilir, sıralama yapılır, ardından asıl metinler geri yazılır. Böylece satırlar,
rozetleri ve kayıt kimlikleriyle birlikte Qt tarafından taşınır.
"""
import re

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QTableWidgetItem

BOS_DEGERLER = {"", "-", "—", "–"}
SIRALAMA_ROLU = Qt.UserRole + 77     # hücrenin görünen metninden farklı bir sıralama metni gerekiyorsa (örn. "KOD · Ad" hücresi ada göre)
SIRASIZ_BASLIKLAR = {"işlem", "islem", ""}

_ALFABE = "abcçdefgğhıijklmnoöprsştuüvyz"
_HARF_SIRASI = {harf: sira for sira, harf in enumerate(_ALFABE)}
_TARIH = re.compile(r"^\s*(\d{1,2})[./](\d{1,2})[./](\d{4})(?:\D+(\d{1,2}):(\d{2}))?")
_TUTAR = re.compile(r"^\s*[-+]?(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d+)?\s*(?:₺|TL|%)?\s*$")
_PARCA = re.compile(r"(\d+)")


def _turkce_kucult(metin):
    return metin.replace("İ", "i").replace("I", "ı").lower()


def siralama_anahtari(metin):
    """Bir hücre metninden sıralama anahtarı üretir. Boşlar (9, ()) ile en sona gider."""
    metin = (metin or "").strip()
    if metin in BOS_DEGERLER:
        return (9, ())
    tarih = _TARIH.match(metin)
    if tarih:
        gun, ay, yil, saat, dakika = tarih.groups()
        return (1, (int(yil), int(ay), int(gun), int(saat or 0), int(dakika or 0)))
    if _TUTAR.match(metin):
        sayi = re.sub(r"[^\d,.\-+]", "", metin)
        sayi = sayi.replace(".", "").replace(",", ".")
        try:
            return (0, (float(sayi),))
        except ValueError:
            pass
    parcalar = []
    for parca in _PARCA.split(_turkce_kucult(metin)):
        if not parca:
            continue
        if parca.isdigit():
            parcalar.append((0, int(parca), ()))
        else:
            parcalar.append((1, 0, tuple(_HARF_SIRASI.get(h, ord(h) - 100000) for h in parca)))
    return (2, tuple(parcalar))


def _hucre_metni(tablo, satir, sutun):
    """Hücrenin sıralanacak metni: önce öğe metni; yoksa hücre bileşenindeki (rozet) etiket metni."""
    oge = tablo.item(satir, sutun)
    if oge is not None:
        ozel = oge.data(SIRALAMA_ROLU)
        if ozel:
            return str(ozel)
    if oge is not None and oge.text().strip():
        return oge.text()
    bilesen = tablo.cellWidget(satir, sutun)
    if bilesen is not None:
        for etiket in ([bilesen] if isinstance(bilesen, QLabel) else []) + bilesen.findChildren(QLabel):
            metin = etiket.text().replace("▾", "").strip()          # tıklanabilir rozetin ok simgesi sıralamayı etkilemesin
            if metin:
                return metin
    return ""


def _sirala(tablo, sutun, yon):
    satir_sayisi = tablo.rowCount()
    metinler = [_hucre_metni(tablo, s, sutun) for s in range(satir_sayisi)]
    if satir_sayisi < 2 or all(m.strip() in BOS_DEGERLER for m in metinler):
        return False

    anahtarlar = [siralama_anahtari(m) for m in metinler]
    dolu = sorted({a for a in anahtarlar if a[0] != 9})
    sira = {a: i for i, a in enumerate(dolu)}
    en_son = len(dolu)
    azalan = yon == Qt.DescendingOrder
    haneler = len(str(en_son + 1))

    def sira_numarasi(anahtar):
        if anahtar[0] == 9:
            return en_son                              # boşlar her iki yönde de sonda
        n = sira[anahtar]
        return en_son - 1 - n if azalan else n

    # Satırın görünürlüğü ve yüksekliği satır numarasına bağlıdır; sıralamadan sonra satırla birlikte taşınması için saklanır.
    ogeler = []
    for s in range(satir_sayisi):
        ogeler.append(next((o for o in (tablo.item(s, k) for k in range(tablo.columnCount())) if o is not None), None))
    durum = {id(o): (tablo.isRowHidden(s), tablo.rowHeight(s)) for s, o in enumerate(ogeler) if o is not None}

    gecici = []                                        # bu sırada oluşturulan geçici öğeler (sütunda metin öğesi yoksa)
    orijinal = []
    tablo.blockSignals(True)
    try:
        for s, anahtar in enumerate(anahtarlar):
            oge = tablo.item(s, sutun)
            if oge is None:
                oge = QTableWidgetItem("")
                tablo.setItem(s, sutun, oge)
                gecici.append(oge)
            orijinal.append((oge, oge.data(Qt.DisplayRole)))
            oge.setData(Qt.DisplayRole, str(sira_numarasi(anahtar)).zfill(haneler))
        tablo.sortItems(sutun, Qt.AscendingOrder)
    finally:
        for oge, deger in orijinal:
            oge.setData(Qt.DisplayRole, deger)
        for oge in gecici:
            tablo.takeItem(tablo.row(oge), sutun)
        for s in range(tablo.rowCount()):
            oge = next((o for o in (tablo.item(s, k) for k in range(tablo.columnCount())) if o is not None), None)
            if oge is not None and id(oge) in durum:
                gizli, yukseklik = durum[id(oge)]
                tablo.setRowHidden(s, gizli)
                tablo.setRowHeight(s, yukseklik)
        tablo.blockSignals(False)
    return True


def siralanabilir_yap(tablo, sirasiz_sutunlar=()):
    """Tablonun başlığına tıklayınca sıralamayı açar (bir kez artan, ikinci kez azalan)."""
    baslik = tablo.horizontalHeader()
    baslik.setSectionsClickable(True)
    baslik.setCursor(Qt.PointingHandCursor)
    baslik.setSortIndicatorShown(False)
    durum = {"sutun": None, "yon": Qt.AscendingOrder, "siraliyor": False}
    yasak = set(sirasiz_sutunlar)

    def tiklandi(sutun):
        etiket = tablo.horizontalHeaderItem(sutun)
        if sutun in yasak or (etiket is not None and _turkce_kucult(etiket.text()).strip() in SIRASIZ_BASLIKLAR):
            return
        yon = Qt.DescendingOrder if (durum["sutun"] == sutun and durum["yon"] == Qt.AscendingOrder) else Qt.AscendingOrder
        durum["siraliyor"] = True
        try:
            sirali = _sirala(tablo, sutun, yon)
        finally:
            durum["siraliyor"] = False
        if sirali:
            durum["sutun"], durum["yon"] = sutun, yon
            baslik.setSortIndicator(sutun, yon)
            baslik.setSortIndicatorShown(True)

    def sirayi_sifirla(*_):
        """Tablo yeniden dolduruluyor ya da hücreler değişiyor: sıra sunucu sırasına döner, ok kaybolur."""
        if durum["siraliyor"] or durum["sutun"] is None:
            return
        durum["sutun"], durum["yon"] = None, Qt.AscendingOrder
        baslik.setSortIndicatorShown(False)

    baslik.sectionClicked.connect(tiklandi)
    model = tablo.model()
    model.rowsRemoved.connect(sirayi_sifirla)
    model.dataChanged.connect(sirayi_sifirla)
    tablo._tiklandi_siralama = tiklandi               # testler ve kod aynı yolu kullanabilsin
    tablo._siralama_durumu = durum                    # yeniden doldurulmadan önce okunup sonra geri yüklenebilsin
    return tablo


def siralama_durumunu_al(tablo):
    """Kullanıcının seçtiği sıralamayı (sütun, yön) döndürür; sıralama yoksa None. Tablo yeniden doldurulmadan ÖNCE çağrılır."""
    durum = getattr(tablo, "_siralama_durumu", None)
    if not durum or durum["sutun"] is None:
        return None
    return durum["sutun"], durum["yon"]


def siralamayi_geri_yukle(tablo, durum):
    """Tablo yeniden dolduruldu: daha önce alınan sıralamayı (siralama_durumunu_al) yeniden uygular, başlıktaki ok geri gelir."""
    if not durum or not hasattr(tablo, "_tiklandi_siralama"):
        return
    sutun, yon = durum
    tablo._tiklandi_siralama(sutun)                   # ilk tıklama: artan
    if yon == Qt.DescendingOrder:
        tablo._tiklandi_siralama(sutun)               # ikinci tıklama: azalan
