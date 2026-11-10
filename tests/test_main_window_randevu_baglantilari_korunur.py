"""#258'de eklenen randevu/danışan bağlantıları main_window.py'de korunur (başka bir değişiklik bunları silmemeli)."""
import inspect

import main_window as mw

KAYNAK = open("main_window.py", encoding="utf-8").read()


def test_yeni_danisan_butonu_ve_islevi_var():
    assert '("＋  Yeni Danışan", "Randevu oluşturma")' in KAYNAK
    assert hasattr(mw.AnaPencere, "hizli_danisan_kod_olustur")
    assert 'elif "Yeni Danışan" in etiket:' in KAYNAK
    assert "btn.clicked.connect(self.hizli_danisan_kod_olustur)" in KAYNAK


def test_randevu_ana_ekrani_rol_bilgisini_alir():
    assert "rol=self.kullanici_adi" in KAYNAK
    from randevu_ekranlari import RandevuAnaEkrani
    assert "rol" in inspect.signature(RandevuAnaEkrani.__init__).parameters


def test_randevu_formu_kaydedilince_tablo_yenilenir():
    assert "self.randevu_formu.veriler_degisti.connect(self.randevu_ana_ekrani.verileri_cek)" in KAYNAK
