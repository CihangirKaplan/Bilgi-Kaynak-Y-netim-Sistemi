"""Oda Etkinlikleri ekranının yeni tasarımı: anında süzme, tarih aralığı alanı, durum etiketi, sayaç, ipuçları, çift tıklama.

Liste ve düğme davranışları test_oda_etkinlikleri_arayuz.py'de; burada yalnızca görünüm/etkileşim katmanı sınanır.
"""
import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt

import client.oda_etkinlikleri_ekrani as modul
from client.sayfa_tema import DURUM_RENKLERI, DurumRozetiDelegate

ODALAR = [{"oda_id": 1, "oda_adi": "EEG Odası", "kapasite": 4}, {"oda_id": 2, "oda_adi": "Göz İzleme ve Sanal Gerçeklik Odası", "kapasite": 4}]
PERSONELLER = [{"personel_id": 1, "kullanici_adi": "memur", "personel_kodu": "P1"}]


def _yanit(veri):
    m = MagicMock()
    m.ok = True
    m.status_code = 200
    m.json.return_value = veri
    m.text = json.dumps(veri)
    m._tkys_oturum_reddedildi = False
    return m


def _etkinlik(no, ad, gun=1, iptal=False, oda=1):
    bas = datetime(2049, 6, 10, 13, 0) + timedelta(days=gun)
    bit = bas + timedelta(hours=1)
    return {
        "etkinlik_id": no, "oda_id": oda, "oda_adi": ODALAR[oda - 1]["oda_adi"], "organize_eden_personel_id": 1, "duzenleyen_adi": "memur",
        "etkinlik_adi": ad, "katilimci_sayisi": 5, "baslangic_zamani": bas.isoformat(), "bitis_zamani": bit.isoformat(),
        "iptal_edildi_mi": iptal, "gunler": [{"baslangic_zamani": bas.isoformat(), "bitis_zamani": bit.isoformat()}],
    }


def _ekran(tkys_qapplication, etkinlikler):
    veri = {"etkinlikler": etkinlikler, "toplam": len(etkinlikler), "kesildi": False}
    secenek = {"odalar": ODALAR, "personeller": PERSONELLER, "yonetebilir": True}

    def istek(metot, url, **kw):
        return _yanit(secenek if "secenekler" in url else veri)

    with patch.object(modul, "oturum_kontrollu_istek", side_effect=istek):
        return modul.OdaEtkinlikleriEkrani("http://x", "t")


def _adlar(ekran):
    return [ekran.tablo.item(s, 0).text() for s in range(ekran.tablo.rowCount())]


def test_arama_ve_durum_suzgeci_degisince_liste_kendiliginden_suzulur(tkys_qapplication):
    ekran = _ekran(tkys_qapplication, [_etkinlik(1, "Seminer"), _etkinlik(2, "Atölye"), _etkinlik(3, "Eski", iptal=True)])
    assert len(_adlar(ekran)) == 3 and ekran.sayac_rozeti.text() == "3 etkinlik"

    ekran.arama.setText("atö")                                           # Filtrele düğmesine basmadan
    assert _adlar(ekran) == ["Atölye"] and ekran.sayac_rozeti.text() == "1 etkinlik"

    ekran.arama.clear()
    ekran.durum_filtre.setCurrentText("İptal Edildi")
    assert _adlar(ekran) == ["Eski"]

    ekran.filtreleri_temizle()
    assert len(_adlar(ekran)) == 3 and ekran.arama.text() == "" and ekran.durum_filtre.currentText() == "Tümü"


def test_tarih_alani_yalniz_tarih_araligi_secilince_gorunur_ve_degisince_suzer(tkys_qapplication):
    ekran = _ekran(tkys_qapplication, [_etkinlik(1, "Haziran", gun=1)])
    assert ekran.tarih_alani.isHidden()

    ekran.donem.setCurrentText("Bu Hafta")
    assert ekran.tarih_alani.isHidden()

    ekran.donem.setCurrentText("Tarih Aralığı")
    assert not ekran.tarih_alani.isHidden()
    ekran.tarih_bas.setDate(datetime(2049, 6, 1).date())
    ekran.tarih_bit.setDate(datetime(2049, 6, 30).date())
    assert _adlar(ekran) == ["Haziran"]                                  # tarih değişince liste anında süzülür
    ekran.tarih_bit.setDate(datetime(2049, 6, 5).date())
    assert _adlar(ekran) == []

    ekran.donem.setCurrentText("Tümü")
    assert ekran.tarih_alani.isHidden() and _adlar(ekran) == ["Haziran"]


def test_durum_etiketi_hucre_metnini_degistirmez_ve_butun_durumlarin_rengi_vardir(tkys_qapplication):
    ekran = _ekran(tkys_qapplication, [_etkinlik(1, "A"), _etkinlik(2, "B", iptal=True)])
    assert isinstance(ekran.tablo.itemDelegateForColumn(6), DurumRozetiDelegate)
    assert [ekran.tablo.item(s, 6).text() for s in range(2)] == ["Planlandı", "İptal Edildi"]   # sıralama/arama metne bağlı kalır
    assert set(DURUM_RENKLERI) == {"Planlandı", "Devam Ediyor", "Tamamlandı", "İptal Edildi"}

    ekran.resize(1100, 700)
    ekran.show()
    tkys_qapplication.processEvents()
    assert not ekran.tablo.viewport().grab().isNull()                    # etiket çizimi hata vermez
    ekran.close()


def test_iptal_satiri_soluk_uzun_adlar_ipucunda_tam_gorunur(tkys_qapplication):
    ekran = _ekran(tkys_qapplication, [_etkinlik(1, "Normal"), _etkinlik(2, "Silinen", iptal=True, oda=2)])
    assert ekran.tablo.item(0, 0).foreground().color().name().lower() != ekran.tablo.item(1, 0).foreground().color().name().lower()
    assert ekran.tablo.item(1, 1).toolTip() == "Göz İzleme ve Sanal Gerçeklik Odası"
    assert ekran.tablo.item(1, 0).font().bold()
    assert not ekran.tablo.wordWrap()                                    # uzun ad iki satıra bölünmez, "…" ile kısalır


def test_satira_cift_tiklayinca_oturumlar_acilir(tkys_qapplication):
    ekran = _ekran(tkys_qapplication, [_etkinlik(1, "A")])
    with patch.object(ekran, "oturumlari_goster") as goster:
        ekran.tablo.itemDoubleClicked.emit(ekran.tablo.item(0, 0))
    goster.assert_called_once()


def test_bos_sonuc_mesaji_ve_alt_bilgi_korunur(tkys_qapplication):
    ekran = _ekran(tkys_qapplication, [_etkinlik(1, "A")])
    ekran.arama.setText("yok böyle bir şey")
    assert not ekran.bos_mesaj.isHidden() and ekran.bos_mesaj.text() == "Aramaya ve süzgeçlere uyan etkinlik yok."
    assert ekran.durum.text().startswith("1 kayıttan 0 tanesi gösteriliyor")
    assert ekran.sayac_rozeti.text() == "0 etkinlik"


def test_tarih_alani_dar_pencerede_ikinci_satirda_acilir_ust_satir_sikismaz(tkys_qapplication):
    ekran = _ekran(tkys_qapplication, [_etkinlik(1, "A")])
    ekran.resize(980, 700)
    ekran.show()
    ekran.donem.setCurrentText("Tarih Aralığı")
    tkys_qapplication.processEvents()
    assert ekran.tarih_alani.geometry().top() > ekran.arama.geometry().bottom()          # alt satırda, aramayla yan yana değil
    assert ekran.tarih_bas.geometry().right() < ekran.tarih_bit.geometry().left()        # iki tarih kutusu üst üste binmez
    assert ekran.arama.width() >= 220                                                    # arama kutusu sıkışıp daralmaz
    ekran.close()

