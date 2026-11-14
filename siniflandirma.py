"""Danışan ve randevu sınıflandırmaları (yaş grubu, terapi türü, görüşme tipi): KAPALI listeler, serbest metin yok (FR-008).

Yaş grubu danışana, görüşme tipi ve terapi türü RANDEVUYA aittir (terapi her randevuda değişebilir). Listeler sunucudaki
modeller.YAS_GRUPLARI / TERAPI_TURLERI / GORUSME_TIPLERI ile aynı olmalıdır (testle denetlenir).
Kural: yetişkinde terapi türü yalnızca bireysel terapidir (otomatik); çocukta oyun terapisi ya da bireysel terapi seçilir.
"""

YAS_GRUPLARI = [("COCUK", "Çocuk"), ("YETISKIN", "Yetişkin")]
TERAPI_TURLERI = [("OYUN_TERAPISI", "Oyun terapisi"), ("BIREYSEL_TERAPI", "Bireysel terapi")]
GORUSME_TIPLERI = [("YUZ_YUZE", "Yüz yüze"), ("ONLINE", "Online")]

YAS_ETIKETLERI = dict(YAS_GRUPLARI)
TERAPI_ETIKETLERI = dict(TERAPI_TURLERI)
GORUSME_ETIKETLERI = dict(GORUSME_TIPLERI)
BELIRTILMEDI = "Belirtilmedi"


def yas_etiketi(kod):
    return YAS_ETIKETLERI.get(kod, BELIRTILMEDI)


def terapi_etiketi(kod, bos=BELIRTILMEDI):
    return TERAPI_ETIKETLERI.get(kod, bos)


def gorusme_etiketi(kod):
    return GORUSME_ETIKETLERI.get(kod, GORUSME_ETIKETLERI["YUZ_YUZE"])


def terapi_secenekleri(yas_grubu):
    """Yaş grubuna göre seçilebilir terapi türleri (kod listesi). Yaş grubu bilinmiyorsa boş liste."""
    if yas_grubu == "COCUK":
        return ["OYUN_TERAPISI", "BIREYSEL_TERAPI"]
    if yas_grubu == "YETISKIN":
        return ["BIREYSEL_TERAPI"]
    return []


def terapi_kutusunu_doldur(kutu, yas_grubu, secili=None, yas_bilinmiyor_secenekli=False,
                           bos_metin="--- Önce yaş grubunu seçin ---", cocukta_secim_zorunlu=False):
    """Terapi türü açılır kutusunu yaş grubuna göre doldurur.

    Yetişkin: tek seçenek, kutu kapalı. Çocuk: iki seçenek (cocukta_secim_zorunlu=True ise önce "Seçiniz" satırı gelir ve seçim
    yapılmalıdır). Yaş grubu bilinmiyorsa: boş metin ve kapalı kutu; ya da (eski danışanlar için) "Belirtilmedi" + iki seçenek
    (yas_bilinmiyor_secenekli=True).
    """
    kutu.blockSignals(True)
    kutu.clear()
    secenekler = terapi_secenekleri(yas_grubu)
    if not secenekler:
        if yas_bilinmiyor_secenekli:
            kutu.addItem("--- " + BELIRTILMEDI + " ---", None)
            for kod, etiket in TERAPI_TURLERI:
                kutu.addItem(etiket, kod)
            kutu.setEnabled(True)
        else:
            kutu.addItem(bos_metin, None)
            kutu.setEnabled(False)
    else:
        if cocukta_secim_zorunlu and len(secenekler) > 1:
            kutu.addItem("--- Terapi Türü Seçiniz ---", None)
        for kod in secenekler:
            kutu.addItem(TERAPI_ETIKETLERI[kod], kod)
        kutu.setEnabled(len(secenekler) > 1)
    if secili is not None:
        indeks = kutu.findData(secili)
        if indeks >= 0:
            kutu.setCurrentIndex(indeks)
    kutu.blockSignals(False)
