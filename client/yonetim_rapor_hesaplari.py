"""Yönetim raporlarında ekranın gösterdiği türetilmiş göstergeler (oranlar, önceki döneme göre değişim).

Ortak kural: "yapılan iş" sayılarında İPTAL EDİLENLER HARİÇ tutulur, iptaller ayrıca gösterilir. Böylece aynı sayfadaki
randevu, cihaz rezervasyonu ve oda etkinliği sayıları aynı kuralla okunur.
"""

YUKARI, ASAGI, AYNI = "▲", "▼", "="


def gerceklesen_randevu(ozet):
    """İptal edilenler hariç randevu sayısı (planlanan + tamamlanan + gelmeyen)."""
    return max(0, int(ozet.get("toplam", 0)) - int(ozet.get("iptal_edildi", 0)))


def ileri_tarihli_planli(ozet):
    """Henüz zamanı gelmemiş "Planlandı" randevular (sonucu girilmemiş geçmiş randevular hariç)."""
    return max(0, int(ozet.get("planlandi", 0)) - int(ozet.get("sonucu_girilmemis", 0)))


def _oran(pay, payda):
    return None if not payda else pay / payda


def gelmeme_orani(ozet):
    """Sonuçlanan randevular (tamamlanan + gelmeyen) içinde danışanın gelmediklerinin payı."""
    return _oran(ozet.get("gelmedi", 0), ozet.get("tamamlandi", 0) + ozet.get("gelmedi", 0))


def tamamlanma_orani(ozet):
    return _oran(ozet.get("tamamlandi", 0), ozet.get("tamamlandi", 0) + ozet.get("gelmedi", 0))


def iptal_orani(ozet):
    return _oran(ozet.get("iptal_edildi", 0), ozet.get("toplam", 0))


def _sayi(deger):
    deger = float(deger)
    return f"{int(deger)}" if deger.is_integer() else f"{deger:.1f}".replace(".", ",")


def degisim(simdi, once, oran=False):
    """Önceki döneme göre değişim: (ok, metin). Sayılarda yüzde, oranlarda yüzde puanı.

    Önceki dönemde hiç yoksa yüzde hesaplanamaz: "önceki dönemde yok" denir."""
    if simdi is None or once is None:
        return None, "—"
    if oran:
        fark = round((simdi - once) * 100, 1)
        if fark == 0:
            return AYNI, "değişmedi"
        return (YUKARI if fark > 0 else ASAGI), f"{_sayi(abs(fark))} puan"
    if once == 0:
        return (None, "—") if simdi == 0 else (YUKARI, "önceki dönemde yok")
    yuzde = round((simdi - once) / once * 100)
    if yuzde == 0:
        return AYNI, "değişmedi"
    return (YUKARI if yuzde > 0 else ASAGI), f"%{abs(yuzde)}"


def degisim_metni(simdi, once, oran=False):
    """Tablo hücresi için: "▲ %12", "▼ 2,1 puan", "= değişmedi", "—"."""
    ok, metin = degisim(simdi, once, oran)
    return metin if ok is None else f"{ok} {metin}"


# Rozet renkleri: artışın iyi mi kötü mü olduğu göstergeye göre değişir (gelmeme oranında artış kötüdür).
# Renk tek başına bilgi taşımaz: ok ve yazı her zaman vardır.
ROZET_RENKLERI = {
    "iyi": ("#166534", "#DCFCE7"),
    "kotu": ("#B91C1C", "#FEE2E2"),
    "notr": ("#1E3A8A", "#E6EEF9"),
}


def rozet_turu(ok, yon):
    """yon: +1 artış iyi, -1 artış kötü, 0 yorum yok (yalnızca değişim gösterilir)."""
    if ok in (None, AYNI) or not yon:
        return "notr"
    iyi = (ok == YUKARI) == (yon > 0)
    return "iyi" if iyi else "kotu"
