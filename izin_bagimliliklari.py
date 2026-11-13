"""Rol & İzin Yönetimi: bir izin tek başına sekme açmıyorsa yöneticiye açıklayıcı not gösterir.

Bazı izinler yeni bir menü sekmesi değil, bir sayfanın İÇİNDEKİ düğmeleri açar (örn. "Rol atama" düğmesi
"Kullanıcı & Personel" sayfasındadır). Bu izni tek başına veren yönetici sekmenin görünmesini bekler ama görünmez.
Notlar menü tanımından (MENU) otomatik üretilir; menü değişirse notlar kendiliğinden güncel kalır.
"""

# Menüden çıkarılamayan, elle yazılan notlar (izin kodu -> not).
SABIT_NOTLAR = {
    "PERSONEL_TANIMLA": (
        "Bu izin, 'Kullanıcı & Personel' sayfasındaki personel listesini ve personel işlemlerini açar. "
        "Sayfanın kendisi 'Kullanıcı oluşturma' izniyle görünür; bu yüzden iki izin birlikte verilmelidir."
    ),
    "IZIN_TANIMLA": (
        "Şu an sistemde bu izni kullanan bir sayfa, düğme ya da işlem yok; açıp kapatmak hiçbir şeyi değiştirmez."
    ),
    "CIHAZ_TAKIP_KONTROL_LISTESI": (
        "Şu an sistemde bu izni kullanan bir sayfa, düğme ya da işlem yok; açıp kapatmak hiçbir şeyi değiştirmez."
    ),
}


def _kod_adlari(izin_kodlari):
    """Tek kodlu izin adlarından 'kod -> görünen izin adı' sözlüğü (not metinlerinde kullanılır)."""
    return {kodlar[0]: ad for ad, kodlar in izin_kodlari.items() if len(kodlar) == 1}


def _liste(adlar):
    adlar = [f"'{ad}'" for ad in adlar]
    return adlar[0] if len(adlar) == 1 else ", ".join(adlar[:-1]) + " ve " + adlar[-1]


def bagimlilik_notlari(menu, izin_kodlari, etiketler=None):
    """Her izin kodu için, o izin tek başına sekme açmıyorsa nedenini anlatan not üretir.

    menu: main_window.MENU ([(bölüm, [sayfa sözlüğü])]); izin_kodlari: main_window.IZIN_KODLARI.
    etiketler: {izin kodu: matriste görünen ad}; verilirse notlardaki izin adları matristekiyle aynı olur.
    Dönüş: {izin kodu: not metni}. Kendi başına bir sayfayı açan izinler için not yoktur.
    """
    adlar = {**_kod_adlari(izin_kodlari), **(etiketler or {})}
    sayfa_gerektirenler = {}      # kod -> [(sayfa, gereken izin adı)]  (düğme izinleri)
    birlikte_gerekenler = {}      # kod -> [(sayfa, diğer izin adları)]  (sayfa birden çok izin ister)
    tek_basina_acanlar = set()

    for _, ogeler in menu:
        for oge in ogeler:
            sayfa_izni = oge.get("izin")
            sayfa_kodlari = izin_kodlari.get(sayfa_izni)
            if not sayfa_kodlari:
                continue                                  # izinsiz (ana panel) ya da birleşik izinli sayfa
            if len(sayfa_kodlari) == 1:
                tek_basina_acanlar.add(sayfa_kodlari[0])
            else:
                for kod in sayfa_kodlari:
                    digerleri = [adlar.get(k, k) for k in sayfa_kodlari if k != kod]
                    birlikte_gerekenler.setdefault(kod, []).append((oge["ad"], digerleri))

            for _, aksiyon_izni in oge.get("aksiyon", []):
                for kod in izin_kodlari.get(aksiyon_izni, ()):
                    if kod not in sayfa_kodlari:
                        gereken = " ve ".join(adlar.get(k, k) for k in sayfa_kodlari)
                        sayfa_gerektirenler.setdefault(kod, []).append((oge["ad"], gereken))

    notlar = {}
    for kod, sayfalar in sayfa_gerektirenler.items():
        if kod in tek_basina_acanlar:
            continue                                      # bu izin zaten başka bir sayfayı tek başına açıyor
        benzersiz = list(dict.fromkeys(sayfalar))
        sayfa_adlari = _liste([s for s, _ in benzersiz])
        gerekenler = _liste(list(dict.fromkeys(i for _, i in benzersiz)))
        notlar[kod] = (
            f"Bu izin tek başına yeni bir sekme açmaz; {sayfa_adlari} sayfasının içindeki düğmeleri açar. "
            f"Kişinin o sayfayı görebilmesi için {gerekenler} izni de verilmelidir."
        )
    for kod, sayfalar in birlikte_gerekenler.items():
        for sayfa, digerleri in sayfalar:
            notlar.setdefault(
                kod,
                f"'{sayfa}' sayfası, bu izin ile birlikte {_liste(digerleri)} izni de verildiğinde görünür. "
                f"Tek başına sekme açmaz.",
            )
    for kod, metin in SABIT_NOTLAR.items():
        notlar.setdefault(kod, metin)
    return notlar


def etiketler_matristen(matris_verisi):
    """Matris yanıtındaki izin listesinden {izin kodu: görünen ad} çıkarır."""
    return {
        izin["izin_adi"]: izin.get("gorunen_ad") or izin["izin_adi"]
        for izin in (matris_verisi or {}).get("izinler", [])
        if izin.get("izin_adi")
    }


def izin_notlari(matris_verisi=None):
    """Uygulamanın gerçek menüsünden üretilmiş notlar; izin adları matristekiyle aynıdır."""
    import main_window                                    # tembel içe aktarma: dairesel bağımlılığı önler
    return bagimlilik_notlari(main_window.MENU, main_window.IZIN_KODLARI, etiketler_matristen(matris_verisi))


def not_getir(izin_kodu, matris_verisi=None):
    """Verilen izin kodu için not metni; not gerekmiyorsa None."""
    return izin_notlari(matris_verisi).get(izin_kodu)
