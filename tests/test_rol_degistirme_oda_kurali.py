"""
Rol Ata / Değiştir ile psikolog yapma: her psikologun en az bir (aktif) odası olmalı.

- Sunucu: psikolog yapılırken oda zorunlu; psikolog olmayan role oda verilemez;
  psikologluktan çıkarken oda yetkileri silinir.
- Arayüz: Psikolog seçilince oda listesi çıkar, oda seçmeden kaydedilmez.
- Temizlik: oda_yonetimi.py'deki sınıf dışı kopya `odayi_kaydet` kaldırıldı.
"""

import ast
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QMessageBox

import k_personel_ekranlari as modul
import oda_yonetimi
from modeller import RolDegistirModeli
from sunucu import kullanici_rol_degistir

ROL_ID = {"PSIKOLOG": 1, "MEMUR": 2, "MUDUR": 3}


# ------------------------------------------------------------------ sunucu
def rol_degistir(hedef_rol, yeni_rol, oda_idleri=None, aktif_odalar=(), personel_kodlari=()):
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchone.side_effect = [("ADMIN",), (hedef_rol,), (yeni_rol,), (20, "PER-X-001")]
    fetchall = []
    if yeni_rol == "PSIKOLOG":
        fetchall.append([(o,) for o in aktif_odalar])   # oda doğrulama sorgusu
    fetchall.append(list(personel_kodlari))             # personel kodu sorgusu
    cursor.fetchall.side_effect = fetchall

    veri = RolDegistirModeli(rol_id=ROL_ID[yeni_rol], oda_idleri=oda_idleri)
    with patch("sunucu.psycopg2.connect", return_value=conn):
        try:
            sonuc = kullanici_rol_degistir(kullanici_id=5, veri=veri, islem_yapan_id=10)
            hata = None
        except HTTPException as h:
            sonuc, hata = None, h
    return conn, cursor, sonuc, hata


def sorgular(cursor):
    return [c.args[0] for c in cursor.execute.call_args_list]


def rol_guncellendi_mi(cursor):
    return any(s.strip().upper().startswith("UPDATE KULLANICILAR") for s in sorgular(cursor))


@pytest.mark.parametrize("oda_idleri", [None, []])
def test_psikolog_yapilirken_oda_zorunlu(oda_idleri):
    conn, cursor, _, hata = rol_degistir("MEMUR", "PSIKOLOG", oda_idleri)
    assert hata.status_code == 422
    assert "en az bir" in hata.detail
    assert not rol_guncellendi_mi(cursor)
    conn.commit.assert_not_called()
    conn.rollback.assert_called_once()


def test_pasif_ya_da_olmayan_odayla_psikolog_olunamaz():
    conn, cursor, _, hata = rol_degistir("MEMUR", "PSIKOLOG", [2, 9], aktif_odalar=(2,))
    assert hata.status_code == 422
    assert "aktif" in hata.detail
    assert not rol_guncellendi_mi(cursor)
    conn.commit.assert_not_called()


def test_psikolog_olunurken_odalar_yazilir():
    conn, cursor, sonuc, hata = rol_degistir("MEMUR", "PSIKOLOG", [3, 2, 3], aktif_odalar=(2, 3))
    assert hata is None and sonuc["yeni_rol_adi"] == "PSIKOLOG"

    tum = cursor.execute.call_args_list
    dogrulama = next(c for c in tum if "FROM odalar WHERE oda_id = ANY" in c.args[0])
    assert dogrulama.args[1] == ([2, 3],)  # tekrarlar atılmış, sıralı

    metinler = [c.args[0].strip().upper() for c in tum]
    silme = next(i for i, s in enumerate(metinler) if s.startswith("DELETE FROM PSIKOLOG_ODALAR"))
    eklemeler = [(i, c.args[1]) for i, (c, s) in enumerate(zip(tum, metinler)) if s.startswith("INSERT INTO PSIKOLOG_ODALAR")]
    assert [e[1] for e in eklemeler] == [(5, 2), (5, 3)]
    assert all(e[0] > silme for e in eklemeler)  # önce eski kayıtlar silinir, sonra yenileri eklenir

    denetim = [c.args[1] for c in tum if "INSERT INTO denetim_kayitlari" in c.args[0]]
    assert (10, "UPDATE", "psikolog_odalar", 5) in denetim
    assert (10, "ROLE_CHANGE", "kullanicilar", 5) in denetim
    conn.commit.assert_called_once()


def test_psikolog_olmayan_role_oda_verilemez():
    conn, cursor, _, hata = rol_degistir("MEMUR", "MUDUR", [2])
    assert hata.status_code == 422
    assert "psikolog" in hata.detail
    assert not rol_guncellendi_mi(cursor)
    conn.commit.assert_not_called()


def test_psikologluktan_cikarken_oda_yetkileri_silinir():
    conn, cursor, sonuc, hata = rol_degistir("PSIKOLOG", "MEMUR")
    assert hata is None and sonuc["yeni_rol_adi"] == "MEMUR"
    metinler = [s.strip().upper() for s in sorgular(cursor)]
    assert any(s.startswith("DELETE FROM PSIKOLOG_ODALAR") for s in metinler)
    assert not any(s.startswith("INSERT INTO PSIKOLOG_ODALAR") for s in metinler)
    denetim = [c.args[1] for c in cursor.execute.call_args_list if "INSERT INTO denetim_kayitlari" in c.args[0]]
    assert (10, "UPDATE", "psikolog_odalar", 5) in denetim


def test_psikologla_ilgisiz_rol_degisiminde_oda_islemi_yapilmaz():
    _, cursor, sonuc, hata = rol_degistir("MEMUR", "MUDUR")
    assert hata is None and sonuc["yeni_rol_adi"] == "MUDUR"
    assert not any("psikolog_odalar" in s for s in sorgular(cursor))


def test_zaten_psikolog_olana_psikolog_atamasi_409_verir():
    conn, cursor, _, hata = rol_degistir("PSIKOLOG", "PSIKOLOG", [2], aktif_odalar=(2,))
    assert hata.status_code == 409
    assert not rol_guncellendi_mi(cursor)


def test_model_oda_idlerini_kabul_eder_ama_baska_alani_reddeder():
    assert RolDegistirModeli(rol_id=1, oda_idleri=[2, 3]).oda_idleri == [2, 3]
    assert RolDegistirModeli(rol_id=2).oda_idleri is None
    with pytest.raises(ValidationError):
        RolDegistirModeli(rol_id=1, oda="2")


# ------------------------------------------------------------------ arayüz
def cevap(veri, durum=200):
    yanit = MagicMock()
    yanit.status_code = durum
    yanit.json.return_value = veri
    yanit._tkys_oturum_reddedildi = False
    return yanit


ODALAR = [
    {"oda_id": 1, "oda_adi": "EEG Odası", "aktif_mi": True},
    {"oda_id": 2, "oda_adi": "Görüşme Odası-1", "aktif_mi": True},
    {"oda_id": 3, "oda_adi": "Görüşme Odası-2", "aktif_mi": True},
    {"oda_id": 9, "oda_adi": "Eski Oda", "aktif_mi": False},
]


class Sunucu:
    def __init__(self, oda_durumu=200, patch_cevabi=None):
        self.oda_durumu = oda_durumu
        self.patch_cevabi = patch_cevabi or cevap({"mesaj": "ok"})
        self.oda_istekleri = 0
        self.patch_istekleri = []

    def __call__(self, yontem, url, **kwargs):
        if yontem == "PATCH":
            self.patch_istekleri.append((url, kwargs.get("json")))
            return self.patch_cevabi
        if url.endswith("/api/odalar"):
            self.oda_istekleri += 1
            if self.oda_durumu != 200:
                return cevap({"detail": "yetki yok"}, self.oda_durumu)
            return cevap(ODALAR)
        return cevap({})


def form_ac(mevcut_rol="MEMUR"):
    return modul.RolDegistirFormu("http://testserver", "TOKEN", 5, "kisi", mevcut_rol)


def rol_sec(form, sunucu, rol_id):
    with patch.object(modul, "oturum_kontrollu_istek", side_effect=sunucu):
        form.combo_rol.setCurrentIndex(form.combo_rol.findData(rol_id))


def isaretle(form, *oda_idleri):
    for i in range(form.liste_odalar.count()):
        oge = form.liste_odalar.item(i)
        oge.setCheckState(Qt.Checked if oge.data(Qt.UserRole) in oda_idleri else Qt.Unchecked)


def test_oda_listesi_yalnizca_psikolog_secilince_gorunur_odalar_bir_kez_yuklenir():
    sunucu, form = Sunucu(), form_ac()
    assert form.liste_odalar.isHidden() and form.oda_bilgi.isHidden()

    rol_sec(form, sunucu, 1)  # Psikolog
    assert not form.liste_odalar.isHidden() and not form.oda_bilgi.isHidden()
    adlar = [form.liste_odalar.item(i).text() for i in range(form.liste_odalar.count())]
    assert adlar == ["EEG Odası", "Görüşme Odası-1", "Görüşme Odası-2"]  # pasif oda yok

    rol_sec(form, sunucu, 3)  # Müdür
    assert form.liste_odalar.isHidden()
    rol_sec(form, sunucu, 1)  # yeniden Psikolog
    assert form.liste_odalar.count() == 3
    assert sunucu.oda_istekleri == 1
    form.close()


def test_psikolog_icin_oda_secmeden_kaydedilmez():
    sunucu, form = Sunucu(), form_ac()
    rol_sec(form, sunucu, 1)
    with patch.object(modul, "oturum_kontrollu_istek", side_effect=sunucu), \
            patch.object(QMessageBox, "warning") as uyari:
        form.kaydet()
    uyari.assert_called_once()
    assert "en az bir" in uyari.call_args.args[2]
    assert sunucu.patch_istekleri == []
    form.close()


def test_psikolog_icin_secilen_odalar_sunucuya_gider():
    sunucu, form = Sunucu(), form_ac()
    rol_sec(form, sunucu, 1)
    isaretle(form, 2, 3)
    with patch.object(modul, "oturum_kontrollu_istek", side_effect=sunucu), \
            patch.object(QMessageBox, "information"):
        form.kaydet()
    (url, govde), = sunucu.patch_istekleri
    assert url.endswith("/api/kullanicilar/5/rol")
    assert govde == {"rol_id": 1, "oda_idleri": [2, 3]}
    assert form.result() == QDialog.Accepted
    form.close()


def test_psikolog_olmayan_rol_oda_gondermez():
    sunucu, form = Sunucu(), form_ac()
    rol_sec(form, sunucu, 1)
    isaretle(form, 2)             # psikolog seçilip odası işaretlendi...
    rol_sec(form, sunucu, 3)      # ...sonra Müdür'e dönüldü: oda gitmemeli
    with patch.object(modul, "oturum_kontrollu_istek", side_effect=sunucu), \
            patch.object(QMessageBox, "information"):
        form.kaydet()
    assert sunucu.patch_istekleri[0][1] == {"rol_id": 3}
    form.close()


def test_odalar_yuklenemezse_bilgi_gosterilir_ve_kaydedilmez():
    sunucu, form = Sunucu(oda_durumu=403), form_ac()
    rol_sec(form, sunucu, 1)
    assert "yüklenemedi" in form.oda_bilgi.text()
    with patch.object(modul, "oturum_kontrollu_istek", side_effect=sunucu), \
            patch.object(QMessageBox, "warning") as uyari:
        form.kaydet()
    uyari.assert_called_once()
    assert sunucu.patch_istekleri == []
    form.close()


def test_pencere_mevcut_rolu_gorunen_adla_yazar_kodla_karsilastirir():
    form = modul.RolDegistirFormu("http://testserver", "TOKEN", 5, "kisi", "MEMUR", mevcut_rol_gorunen="Memur")
    assert form.input_kullanici.text() == "kisi (Mevcut: Memur)"
    assert form.mevcut_rol == "MEMUR"   # "zaten bu rolde" kontrolü kodla çalışmaya devam eder
    form.close()


def test_gorunen_ad_verilmezse_kod_yazilir():
    form = modul.RolDegistirFormu("http://testserver", "TOKEN", 5, "kisi", "MEMUR")
    assert form.input_kullanici.text() == "kisi (Mevcut: MEMUR)"
    form.close()


def test_personel_ekrani_pencereye_gorunen_adi_da_gecirir():
    def sahte(yontem, url, **kwargs):
        if url.endswith("/api/personel"):
            return cevap([{"personel_id": 12, "kullanici_id": 14, "kullanici_adi": "memur", "personel_kodu": "PER-MEM-001",
                           "rol_adi": "MEMUR", "gorunen_ad": "Memur", "aktif_mi": True, "olusturulma_tarihi": None}])
        return cevap([])
    with patch.object(modul, "oturum_kontrollu_istek", side_effect=sahte):
        ekran = modul.KullaniciPersonelEkrani("http://testserver", "TOKEN")
    ekran.tablo.selectRow(0)
    with patch.object(modul, "RolDegistirFormu") as form_sinifi:
        form_sinifi.return_value.exec.return_value = QDialog.Rejected
        ekran.secili_kullanici_rol_degistir()
    assert form_sinifi.call_args.args[4] == "MEMUR"
    assert form_sinifi.call_args.kwargs["mevcut_rol_gorunen"] == "Memur"
    ekran.close()


# ------------------------------------------------------------------ temizlik
def test_oda_yonetimi_kopya_fonksiyon_temizlendi_ama_calistirma_blogu_duruyor():
    kaynak = Path(oda_yonetimi.__file__).read_text(encoding="utf8")
    modul_fonksiyonlari = [n.name for n in ast.parse(kaynak).body if isinstance(n, ast.FunctionDef)]
    assert "odayi_kaydet" not in modul_fonksiyonlari      # sınıf dışındaki ölü kopya yok
    assert hasattr(oda_yonetimi.OdaFormu, "odayi_kaydet")  # asıl yöntem duruyor
    assert 'if __name__ == "__main__":' in kaynak
