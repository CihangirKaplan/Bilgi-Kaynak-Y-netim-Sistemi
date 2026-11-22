"""TKYS - Liste sayfalarından Excel (.xlsx) aktarımı.

Cihaz Envanteri, Öğrenciler ve Danışanlar gibi liste sayfaları ekranda o an görünen (aramaya/süzgeçlere uyan) satırları
tek tıkla Excel'e aktarır. Dosya, raporlarla aynı biçimdedir: 'Özet' sayfası (aktarım zamanı, süzgeçler, satır sayısı)
ve tablonun kendisi. Metin hücreleri formül olarak yorumlanmaz (formül enjeksiyonuna karşı).
"""
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QLabel, QMessageBox, QPushButton

from client.api_yoneticisi import oturum_hatasi_mi, oturum_kontrollu_istek
from client.rapor_excel_genel import excel_olustur

EXCEL_DUGME_STILI = (
    "QPushButton { background: #ECFDF3; color: #166534; border: 1px solid #BBF7D0; border-radius: 12px; "
    "padding: 10px 18px; font-size: 13px; font-weight: 700; } "
    "QPushButton:hover { background: #DCFCE7; } "
    "QPushButton:disabled { background: #F1F5F9; color: #94A3B8; border-color: #E2E8F0; }"
)


def excel_dugmesi_olustur(tikla):
    """Yenile düğmesinin yanına konan, yeşil 'Excel'e Aktar' düğmesi."""
    dugme = QPushButton("⬇  Excel'e Aktar")
    dugme.setCursor(Qt.PointingHandCursor)
    dugme.setStyleSheet(EXCEL_DUGME_STILI)
    dugme.clicked.connect(lambda *_: tikla())
    return dugme


def dosya_adi_olustur(onek, simdi=None):
    return f"{onek}_{(simdi or datetime.now()).strftime('%Y%m%d_%H%M')}.xlsx"


def listeyi_excele_aktar(pencere, baslik, onek, kolonlar, satirlar, filtre_ozeti=(), sayfa_adi="Liste", aciklama="", kayit=None):
    """Görünen satırları kullanıcının seçtiği .xlsx dosyasına yazar. Başarılıysa dosya yolunu, aksi halde None döndürür.

    kolonlar: [(başlık, sayı/tarih biçimi veya None)]; satirlar: değer listeleri; filtre_ozeti: [(ad, değer)].
    kayit: {"api_url", "token", "liste"}; verilirse aktarım denetim kaydına yazılır (kim, ne zaman, hangi liste, kaç satır).
    """
    satirlar = [list(s) for s in satirlar]
    if not satirlar:
        QMessageBox.information(pencere, "Excel'e Aktar", "Aktarılacak kayıt yok. Arama ya da süzgeçleri kontrol edin.")
        return None

    dosya_yolu, _ = QFileDialog.getSaveFileName(pencere, "Listeyi Kaydet", dosya_adi_olustur(onek), "Excel Dosyası (*.xlsx)")
    if not dosya_yolu:
        return None
    if not dosya_yolu.lower().endswith(".xlsx"):
        dosya_yolu += ".xlsx"

    try:
        excel_olustur(
            dosya_yolu,
            baslik,
            aciklama or f"{baslik} sayfasında ekranda görünen kayıtlar.",
            list(filtre_ozeti),
            [("Aktarılan Kayıt", len(satirlar), "Ekranda görünen ve Excel'e yazılan satır sayısı.")],
            [(sayfa_adi, list(kolonlar), satirlar, f"{baslik} - ekrandaki sütunlar ve kayıtlar.")],
        )
    except OSError as hata:
        QMessageBox.warning(
            pencere, "Kaydedilemedi",
            f"Dosya kaydedilemedi. Aynı adlı dosya Excel'de açık olabilir ya da klasöre yazma izniniz olmayabilir.\n{hata}",
        )
        return None
    if kayit is not None:
        _aktarimi_denetime_yaz(pencere, kayit, len(satirlar))
    QMessageBox.information(pencere, "Excel'e Aktar", f"{len(satirlar)} kayıt kaydedildi:\n{dosya_yolu}")
    return dosya_yolu


def hucre_metni(tablo, satir, sutun):
    """Tablo hücresinin gösterdiği metin: normal hücrede öğenin metni, rozet/etiket gibi hücre bileşeninde içindeki yazı."""
    oge = tablo.item(satir, sutun)
    if oge is not None:
        return oge.text()
    bilesen = tablo.cellWidget(satir, sutun)
    if bilesen is None:
        return ""
    if isinstance(bilesen, QLabel):
        return bilesen.text()
    etiketler = bilesen.findChildren(QLabel)
    return " ".join(e.text() for e in etiketler if e.text()).strip()


def tablodan_excele_aktar(pencere, tablo, baslik, onek, sutunlar, liste, api_url, token, filtre_ozeti=(), sayfa_adi="Liste",
                          aciklama="", ek_sutunlar=()):
    """Ekranda GÖRÜNEN (aramaya uyan, gizlenmemiş) satırları, tablodaki yazılarıyla Excel'e aktarır.

    sutunlar: [(Excel başlığı, tablo sütun numarası, tür)]; tür "metin" | "cihaz_kodu" | "cihaz_adi"
              ("KOD · Ad" biçimindeki cihaz hücresi iki Excel sütununa ayrılır).
    ek_sutunlar: [(Excel başlığı, fonksiyon(satir_no) -> değer)]; tabloda görünmeyen ama kayıtta olan bilgiler için.
    """
    from client.tablo_tasarimi import CihazHucresiDelegate
    satirlar = []
    for satir in range(tablo.rowCount()):
        if tablo.isRowHidden(satir):
            continue
        deger = []
        for _, sutun, tur in sutunlar:
            metin = hucre_metni(tablo, satir, sutun).strip()
            if tur in ("cihaz_kodu", "cihaz_adi"):
                ad, kod = CihazHucresiDelegate.parcala(metin)
                metin = kod if tur == "cihaz_kodu" else ad
            deger.append(metin)
        for _, fonksiyon in ek_sutunlar:
            deger.append(fonksiyon(satir))
        satirlar.append(deger)
    kolonlar = [(b, None) for b, _, _ in sutunlar] + [(b, None) for b, _ in ek_sutunlar]
    return listeyi_excele_aktar(
        pencere, baslik, onek, kolonlar, satirlar, filtre_ozeti, sayfa_adi=sayfa_adi, aciklama=aciklama,
        kayit={"api_url": api_url, "token": token, "liste": liste},
    )


def _aktarimi_denetime_yaz(pencere, kayit, satir_sayisi):
    """Aktarımı denetim kaydına yazar. Yazılamazsa kullanıcıya açıkça söylenir (aktarım gizlice kayıtsız kalmaz)."""
    uyari = None
    try:
        cevap = oturum_kontrollu_istek(
            "POST", f"{kayit['api_url'].rstrip('/')}/api/liste-aktarim-kaydi",
            headers={"Authorization": f"Bearer {kayit['token']}"},
            json={"liste": kayit["liste"], "satir_sayisi": satir_sayisi}, timeout=10,
        )
        if oturum_hatasi_mi(cevap):
            return
        if cevap.status_code != 200:
            uyari = f"Sunucu kaydı kabul etmedi ({cevap.status_code})."
    except Exception as hata:
        uyari = f"Sunucuya ulaşılamadı: {hata}"
    if uyari:
        QMessageBox.warning(
            pencere, "Denetim kaydı yazılamadı",
            f"Dosya kaydedildi ancak aktarım denetim kaydına yazılamadı.\n{uyari}\nBu durumu yöneticiye bildirin.",
        )
