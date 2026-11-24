"""Oda Etkinlikleri ekranı: düzenleyen adı, sıralama ve seçimin korunması, düğme durumları, boş/kısaltma mesajları, form seçenekleri."""
import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import client.oda_etkinlikleri_ekrani as modul

ODALAR = [{"oda_id": 1, "oda_adi": "EEG Odası", "kapasite": 4}, {"oda_id": 2, "oda_adi": "Göz İzleme Odası", "kapasite": 4}]
PERSONELLER = [{"personel_id": 1, "kullanici_adi": "memur", "personel_kodu": "P1"}]


def _yanit(veri):
    m = MagicMock()
    m.ok = True
    m.status_code = 200
    m.json.return_value = veri
    m.text = json.dumps(veri)
    m._tkys_oturum_reddedildi = False
    return m


def _etkinlik(no, ad, gun=1, iptal=False, duzenleyen="memur", personel=1, oda=1):
    bas = datetime(2049, 6, 10, 13, 0) + timedelta(days=gun)
    bit = bas + timedelta(hours=1)
    return {
        "etkinlik_id": no, "oda_id": oda, "oda_adi": "EEG Odası" if oda == 1 else "Göz İzleme Odası", "organize_eden_personel_id": personel,
        "duzenleyen_adi": duzenleyen, "etkinlik_adi": ad, "katilimci_sayisi": 5, "baslangic_zamani": bas.isoformat(),
        "bitis_zamani": bit.isoformat(), "iptal_edildi_mi": iptal,
        "gunler": [{"baslangic_zamani": bas.isoformat(), "bitis_zamani": bit.isoformat()}],
    }


def _ekran(tkys_qapplication, etkinlikler, yonetebilir=True, **ek):
    veri = {"etkinlikler": etkinlikler, "toplam": ek.get("toplam", len(etkinlikler)), "kesildi": ek.get("kesildi", False)}
    secenek = {"odalar": ODALAR, "personeller": PERSONELLER, "yonetebilir": yonetebilir}

    def istek(metot, url, **kw):
        return _yanit(secenek if "secenekler" in url else veri)

    with patch.object(modul, "oturum_kontrollu_istek", side_effect=istek):
        ekran = modul.OdaEtkinlikleriEkrani("http://x", "t")
    return ekran, istek


def _adlar(ekran):
    return [ekran.tablo.item(s, 0).text() for s in range(ekran.tablo.rowCount())]


def test_duzenleyen_adi_sunucudan_gelir_secenekte_olmayan_admin_de_gorunur(tkys_qapplication):
    ekran, _ = _ekran(tkys_qapplication, [_etkinlik(1, "A", duzenleyen="memur"), _etkinlik(2, "B", duzenleyen="admin", personel=9)])
    assert [ekran.tablo.item(s, 2).text() for s in range(2)] == ["memur", "admin"]
    ekran.arama.setText("admin")                                         # aramada da düzenleyen adıyla bulunur
    ekran.filtrele()
    assert _adlar(ekran) == ["B"]


def test_siralama_ve_secim_yenilemede_korunur_secili_etkinlik_kimlikle_bulunur(tkys_qapplication):
    ekran, istek = _ekran(tkys_qapplication, [_etkinlik(1, "Zeynep", gun=3), _etkinlik(2, "Ali", gun=2), _etkinlik(3, "Can", gun=1)])
    ekran.tablo._tiklandi_siralama(0)                                    # Etkinlik adına göre artan
    assert _adlar(ekran) == ["Ali", "Can", "Zeynep"]
    ekran.tablo.selectRow(1)                                             # "Can"
    assert ekran.secili()["etkinlik_adi"] == "Can"                       # satır 1, listedeki 2. sıra değil; kimlikle bulunur
    with patch.object(modul, "oturum_kontrollu_istek", side_effect=istek):
        ekran.yenile()
    assert _adlar(ekran) == ["Ali", "Can", "Zeynep"]
    assert ekran.secili()["etkinlik_adi"] == "Can"


def test_dugmeler_secime_ve_iptal_durumuna_gore_acilir(tkys_qapplication):
    ekran, _ = _ekran(tkys_qapplication, [_etkinlik(1, "Açık"), _etkinlik(2, "İptal", iptal=True)])
    assert not ekran.duzenle_btn.isEnabled() and not ekran.iptal_btn.isEnabled() and not ekran.oturum_gor_btn.isEnabled()
    ekran.tablo.selectRow(0)
    assert ekran.duzenle_btn.isEnabled() and ekran.iptal_btn.isEnabled() and ekran.oturum_gor_btn.isEnabled()
    ekran.tablo.selectRow(1)
    assert not ekran.duzenle_btn.isEnabled() and not ekran.iptal_btn.isEnabled() and ekran.oturum_gor_btn.isEnabled()


def test_yetkisiz_kullanicida_yonetim_dugmeleri_gizli(tkys_qapplication):
    ekran, _ = _ekran(tkys_qapplication, [_etkinlik(1, "Açık")], yonetebilir=False)
    ekran.tablo.selectRow(0)
    assert ekran.ekle_btn.isHidden() and ekran.duzenle_btn.isHidden() and ekran.iptal_btn.isHidden()


def test_bos_liste_ve_sonuc_yok_mesajlari(tkys_qapplication):
    ekran, _ = _ekran(tkys_qapplication, [])
    assert not ekran.bos_mesaj.isHidden() and ekran.tablo.isHidden() and "Henüz" in ekran.bos_mesaj.text()
    ekran, _ = _ekran(tkys_qapplication, [_etkinlik(1, "Açık")])
    ekran.arama.setText("bulunmayan")
    ekran.filtrele()
    assert not ekran.bos_mesaj.isHidden() and "uyan etkinlik yok" in ekran.bos_mesaj.text()
    ekran.arama.setText("")
    ekran.filtrele()
    assert ekran.bos_mesaj.isHidden() and not ekran.tablo.isHidden()


def test_liste_kisaltildiysa_durum_satiri_toplami_soyler(tkys_qapplication):
    ekran, _ = _ekran(tkys_qapplication, [_etkinlik(1, "A")], toplam=2500, kesildi=True)
    assert "Toplam 2500 etkinlik var" in ekran.durum.text()
    ekran, _ = _ekran(tkys_qapplication, [_etkinlik(1, "A")])
    assert "Toplam" not in ekran.durum.text()


def test_form_secenekte_olmayan_oda_ve_duzenleyeni_listeye_ekleyip_secili_acar(tkys_qapplication):
    kayit = _etkinlik(5, "Eski", duzenleyen="admin", personel=9, oda=2)
    form = modul.OdaEtkinlikFormu([ODALAR[0]], PERSONELLER, kayit=kayit)
    assert form.oda.currentData() == 2 and form.oda.currentText() == "Göz İzleme Odası"
    assert form.personel.currentData() == 9 and form.personel.currentText() == "admin"
    assert form.veri()["organize_eden_personel_id"] == 9                 # kaydedilince düzenleyen değişmez
