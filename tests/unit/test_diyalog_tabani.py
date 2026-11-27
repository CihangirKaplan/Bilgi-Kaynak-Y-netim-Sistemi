"""Ortak form diyaloğu tabanı (KaydirmaliDiyalog): uzun formda düğmeler ekran dışında kalmaz, alanlar kaydırılır; sığan formlar eskisi gibi açılır."""
import ast
import re
from pathlib import Path
from unittest.mock import patch

import pytest
from PySide6.QtCore import QRect, QTimer
from PySide6.QtWidgets import QApplication, QLabel, QLineEdit, QPushButton

from client.diyalog_tabani import CERCEVE_PAYI, EN_COK_EKRAN_ORANI, KaydirmaliDiyalog

KOK = Path(__file__).resolve().parents[2]
ISTEMCI = KOK / "client"


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


class _Form(KaydirmaliDiyalog):
    def __init__(self, alan_sayisi):
        super().__init__()
        self.setMinimumWidth(420)
        yerlesim, alt = self.kaydirmali_kur()
        self.alanlar = []
        for i in range(alan_sayisi):
            yerlesim.addWidget(QLabel(f"Alan {i}"))
            kutu = QLineEdit()
            kutu.setMinimumHeight(36)
            self.alanlar.append(kutu)
            yerlesim.addWidget(kutu)
        self.btn_kaydet = QPushButton("Kaydet")
        alt.addWidget(self.btn_kaydet)


def _ac(alan_sayisi, ekran_yuksekligi):
    ekran = QRect(0, 0, 1366, ekran_yuksekligi)
    with patch.object(KaydirmaliDiyalog, "_ekran_alani", lambda self: ekran):
        form = _Form(alan_sayisi)
        form.show()
        QApplication.processEvents()
        QApplication.processEvents()
    return form


def _dugme_gorunur(form):
    alt = form.btn_kaydet.mapTo(form, form.btn_kaydet.rect().bottomLeft()).y()
    return form.btn_kaydet.isVisible() and alt <= form.height()


def test_uzun_form_ekrandan_uzun_olmaz_dugme_gorunur_ve_kaydirma_var(qt_app):
    form = _ac(alan_sayisi=20, ekran_yuksekligi=728)
    sinir = int(728 * EN_COK_EKRAN_ORANI) - CERCEVE_PAYI
    assert form.height() <= sinir
    assert form.kaydirma.verticalScrollBar().maximum() > 0
    assert _dugme_gorunur(form)
    form.close()


def test_kisa_form_eskisi_gibi_icerigi_kadar_acilir_kaydirma_yok(qt_app):
    form = _ac(alan_sayisi=2, ekran_yuksekligi=728)
    assert form.kaydirma.verticalScrollBar().maximum() == 0
    assert form.height() < 400
    assert _dugme_gorunur(form)
    form.close()


def test_ayni_form_kucuk_ekranda_kaydirir_buyuk_ekranda_kaydirmaz(qt_app):
    kucuk, buyuk = _ac(10, 546), _ac(10, 1000)
    assert kucuk.kaydirma.verticalScrollBar().maximum() > 0 and buyuk.kaydirma.verticalScrollBar().maximum() == 0
    assert _dugme_gorunur(kucuk) and _dugme_gorunur(buyuk)
    assert kucuk.height() < buyuk.height()
    kucuk.close(); buyuk.close()


def test_kaydirinca_dugme_yerinde_kalir_alanlar_kayar(qt_app):
    form = _ac(20, 600)
    onceki = form.btn_kaydet.mapTo(form, form.btn_kaydet.rect().topLeft()).y()
    ilk_alan = form.alanlar[0].mapTo(form, form.alanlar[0].rect().topLeft()).y()
    form.kaydirma.verticalScrollBar().setValue(form.kaydirma.verticalScrollBar().maximum())
    QApplication.processEvents()
    assert form.btn_kaydet.mapTo(form, form.btn_kaydet.rect().topLeft()).y() == onceki
    assert form.alanlar[0].mapTo(form, form.alanlar[0].rect().topLeft()).y() < ilk_alan
    form.close()


def test_acildiktan_sonra_alan_eklenince_pencere_buyur_ama_ekrani_asmaz(qt_app):
    ekran = QRect(0, 0, 1366, 728)
    with patch.object(KaydirmaliDiyalog, "_ekran_alani", lambda self: ekran):
        form = _Form(2)
        form.show()
        QApplication.processEvents()
        boy = form.height()
        for i in range(30):                                       # ör. rol seçilince açılan alanlar
            form.icerik.layout().addWidget(QLabel(f"Yeni {i}"))
        QApplication.processEvents()
        QApplication.processEvents()
        QTimer.singleShot(0, lambda: None)
        QApplication.processEvents()
    assert form.height() > boy
    assert form.height() <= int(728 * EN_COK_EKRAN_ORANI) - CERCEVE_PAYI
    assert _dugme_gorunur(form)
    form.close()


def test_icerik_degisince_pencere_kullanicinin_buyuttugu_boyuttan_kuculmez(qt_app):
    ekran = QRect(0, 0, 1366, 728)
    with patch.object(KaydirmaliDiyalog, "_ekran_alani", lambda self: ekran):
        form = _Form(2)
        form.show()
        QApplication.processEvents()
        form.resize(form.width() + 80, 560)                       # kullanıcı pencereyi büyüttü
        QApplication.processEvents()
        form.icerik.layout().addWidget(QLabel("yeni alan"))
        QApplication.processEvents()
        QApplication.processEvents()
    assert form.height() >= 560 and form.width() >= 500
    form.close()


def test_eski_adjustsize_cagrilari_kaydirmali_boyutu_kullanir(qt_app):
    form = _ac(20, 728)
    with patch.object(KaydirmaliDiyalog, "_ekran_alani", lambda self: QRect(0, 0, 1366, 728)):
        form.resize(form.width(), 300)
        form.adjustSize()
    assert form.height() <= int(728 * EN_COK_EKRAN_ORANI) - CERCEVE_PAYI
    form.close()


def test_tercih_edilen_boyut_ekrana_sigmazsa_kisilir(qt_app):
    ekran = QRect(0, 0, 1366, 546)

    class Sabit(KaydirmaliDiyalog):
        def __init__(self):
            super().__init__()
            yerlesim, alt = self.kaydirmali_kur(tercih_boyut=(480, 700))
            yerlesim.addWidget(QLabel("x"))
            self.btn = QPushButton("Tamam")
            alt.addWidget(self.btn)

    with patch.object(KaydirmaliDiyalog, "_ekran_alani", lambda self: ekran):
        form = Sabit()
        form.show()
        QApplication.processEvents()
    assert form.width() >= 480 and form.height() <= int(546 * EN_COK_EKRAN_ORANI) - CERCEVE_PAYI
    form.close()


# ---------------------------------------------------------------- gerçek diyaloglar
GECEN = {
    "k_personel_ekranlari": ["KullaniciOlusturFormu", "OdaYetkileriFormu", "RolDegistirFormu"],
    "cihaz_bakim_ekranlari": ["YeniBakimFormu", "BakimDuzenleFormu"],
    "cihaz_kalibrasyon_ekranlari": ["YeniKalibrasyonFormu", "KalibrasyonDuzenleFormu"],
    "cihaz_rezervasyon_ekranlari": ["YeniRezervasyonFormu"],
    "cihaz_ariza_ekranlari": ["ArizaBildirimFormu", "ArizaDuzenleFormu"],
    "cihaz_ekranlari": ["CihazIslemFormu"],
    "rol_izin_diyaloglari": ["RolDuzenleDialog", "IzinDuzenleDialog"],
    "bakim_plani_ekranlari": ["PlanFormu"],
    "parola_talebi_dialog": ["ParolaTalebiDialog"],
    "danisan_diyalog": ["DanisanOlusturDialog"],
    "ogrenci_dialog": ["OgrenciEkleDialog"],
    "faaliyet_dialog": ["FaaliyetEkleDialog"],
    "duyuru_diyaloglari": ["DuyuruDiyalogu"],
    "iptal_nedeni_diyalog": ["IptalNedeniDialog"],
    "oda_etkinlikleri_ekrani": ["TekrarliOturumDialog", "OdaEtkinlikFormu"],
}
SINIFLAR = [(m, s) for m, adlar in GECEN.items() for s in adlar]


@pytest.mark.parametrize("modul, sinif", SINIFLAR)
def test_uzun_form_diyaloglari_ortak_tabani_kullanir_ve_dugmeleri_alt_cubukta(modul, sinif):
    agac = ast.parse((ISTEMCI / f"{modul}.py").read_text(encoding="utf-8"))
    dugum = next(n for n in agac.body if isinstance(n, ast.ClassDef) and n.name == sinif)
    assert [ast.unparse(b) for b in dugum.bases] == ["KaydirmaliDiyalog"], "ortak taban kullanılmalı"
    kaynak = ast.get_source_segment((ISTEMCI / f"{modul}.py").read_text(encoding="utf-8"), dugum)
    assert "self.kaydirmali_kur(" in kaynak, "kaydırmalı yerleşim kurulmalı"
    assert not re.search(r"=\s*QVBoxLayout\(self\)", kaynak), "yerleşim doğrudan pencereye bağlanmamalı (düğmeler kaydırma alanına girer)"
    assert "alt_yerlesim." in kaynak, "düğme/eylem satırı altta sabit çubuğa eklenmeli"


def test_ortak_taban_disinda_kalan_diyaloglar_bilincli_olarak_kucuk_ya_da_liste_penceresidir():
    """Yeni bir form diyaloğu QDialog'tan türetilirse bu liste güncellenmeli: ya KaydirmaliDiyalog kullanır ya da gerekçesi burada yazılır."""
    ISTISNA = {
        "RolOlusturDialog": "sabit 400x260, tek alan",
        "GeciciParolaDialog": "tek metin + iki düğme, sabit boyutlu küçük pencere",
        "HakkindaDialog": "kendi kaydırma alanı var, düğme çubuğu yok",
        "CihazGecmisiPenceresi": "kendi kaydırma alanı var, salt okunur",
        "GunDetayDialog": "salt okunur",
        "BicimSecimDiyalogu": "iki seçenek",
        "CakisanRezervasyonlarDialog": "kendi kaydırma alanı var",
        "DanisanBilgiDialog": "küçük, tek alan",
        "IptalOnayKutusu": "sabit 440x190 onay kutusu",
        "_KucukFormPenceresi": "tek alanlı küçük form",
        "RezervasyonDetayPenceresi": "salt okunur özet + 2 düğme",
        "CihazDuzenlemeListesi": "liste penceresi (tablo kendi kaydırmasında)",
        "FaaliyetTurleriDialog": "liste yönetimi (tablo kendi kaydırmasında)",
        "BirimYonetimDialog": "liste yönetimi (tablo kendi kaydırmasında)",
        "AktiflestirmeOdaFormu": "OdaYetkileriFormu'ndan türer (taban oradan gelir)",
        "YeniBolumPenceresi": "tek alanlı küçük form", "YeniProjeTuruPenceresi": "tek alanlı küçük form",
    }
    gecen = {s for _, s in SINIFLAR}
    bilinmeyen = []
    for dosya in sorted(ISTEMCI.glob("*.py")):
        if dosya.name == "diyalog_tabani.py":
            continue
        agac = ast.parse(dosya.read_text(encoding="utf-8"))
        for n in agac.body:
            if isinstance(n, ast.ClassDef) and any(ast.unparse(b) == "QDialog" for b in n.bases):
                if n.name not in gecen and n.name not in ISTISNA:
                    bilinmeyen.append(f"{dosya.name}:{n.name}")
    assert bilinmeyen == [], f"QDialog'tan doğrudan türeyen ve listede olmayan diyaloglar: {bilinmeyen}"
