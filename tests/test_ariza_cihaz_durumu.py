"""Arıza açılıp çözülünce cihaz durumu: yalnızca doğru durumlarda ve doğru zamanda değişir.

Eskiden herhangi bir arıza çözülünce cihaz kayıtsız şartsız "Kullanıma Hazır" oluyordu; başka açık
arıza ya da bakım/kalibrasyon durumu olsa bile. Gerçek PostgreSQL kullanılmaz.
"""
from unittest.mock import MagicMock, patch

import pytest

from modeller import ArizaBildirimModeli, ArizaGuncelleModeli
from sunucu import ariza_bildir, ariza_guncelle, arizadan_sonra_cihaz_durumu


# ---------------------------------------------------------------- karar fonksiyonu
@pytest.mark.parametrize("eski, cozuldu, baska_acik, beklenen", [
    # Çözüldü
    ("Arizali", True, False, "Kullanima_Hazir"),      # tek/son arıza çözüldü
    ("Arizali", True, True, "Arizali"),               # başka açık arıza var: arızalı kalır
    ("Bakimda", True, False, "Bakimda"),              # bakımdaki cihaz arıza çözülünce hazır olmaz
    ("Kalibrasyonda", True, False, "Kalibrasyonda"),
    ("Kullanim_Disi", True, False, "Kullanim_Disi"),
    ("Kullanima_Hazir", True, False, "Kullanima_Hazir"),
    ("Rezerve", True, False, "Rezerve"),
    # Açık (yeni arıza ya da çözülmüş arızanın yeniden açılması)
    ("Kullanima_Hazir", False, False, "Arizali"),
    ("Rezerve", False, False, "Arizali"),
    ("Kullanimda", False, False, "Arizali"),
    ("Arizali", False, True, "Arizali"),
    ("Bakimda", False, False, "Bakimda"),             # bakımdaki cihaz arıza kaydıyla ezilmez
    ("Kalibrasyonda", False, False, "Kalibrasyonda"),
    ("Kullanim_Disi", False, False, "Kullanim_Disi"),
])
def test_cihaz_durumu_karari(eski, cozuldu, baska_acik, beklenen):
    assert arizadan_sonra_cihaz_durumu(eski, cozuldu, baska_acik) == beklenen


# ------------------------------------------------------------------ ariza_guncelle
def guncelle(eski_durum, baska_acik, cozuldu):
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchone.side_effect = [(10,), (eski_durum, baska_acik)]
    model = ArizaGuncelleModeli(
        aciliyet="Orta", ariza_baslik="Test arızası", ariza_aciklama="Test açıklaması", cozuldu_mu=cozuldu
    )
    with patch("sunucu.psycopg2.connect", return_value=conn):
        ariza_guncelle(ariza_id=5, ariza=model, kullanici_id=1)
    cihaz_guncellemeleri = [
        c.args[1][0] for c in cursor.execute.call_args_list if c.args[0].startswith("UPDATE cihazlar")
    ]
    olaylar = [
        c.args[1][1] for c in cursor.execute.call_args_list if "INSERT INTO denetim_kayitlari" in c.args[0]
    ]
    return cihaz_guncellemeleri, olaylar, cursor, conn


def test_son_acik_ariza_cozulunce_cihaz_hazir_olur_ve_durum_degisimi_kaydedilir():
    guncellemeler, olaylar, _, conn = guncelle("Arizali", False, True)
    assert guncellemeler == ["Kullanima_Hazir"]
    assert olaylar == ["UPDATE", "DEVICE_STATUS_CHANGE"]
    conn.commit.assert_called_once()


def test_baska_acik_ariza_varken_cihaz_hazir_olmaz():
    guncellemeler, olaylar, _, _ = guncelle("Arizali", True, True)
    assert guncellemeler == []
    assert olaylar == ["UPDATE"]                      # durum değişmediği için DEVICE_STATUS_CHANGE yok


@pytest.mark.parametrize("durum", ["Bakimda", "Kalibrasyonda", "Kullanim_Disi"])
def test_bakimdaki_kalibrasyondaki_veya_kullanim_disi_cihaz_arizayla_degismez(durum):
    for cozuldu in (True, False):
        guncellemeler, olaylar, _, _ = guncelle(durum, False, cozuldu)
        assert guncellemeler == [] and olaylar == ["UPDATE"]


def test_cozulmus_ariza_yeniden_acilinca_hazir_cihaz_arizali_olur():
    guncellemeler, olaylar, _, _ = guncelle("Kullanima_Hazir", False, False)
    assert guncellemeler == ["Arizali"]
    assert olaylar == ["UPDATE", "DEVICE_STATUS_CHANGE"]


def test_baska_acik_ariza_sorgusu_ayni_arizayi_saymaz_ve_cihaz_satirini_kilitler():
    _, _, cursor, _ = guncelle("Arizali", False, True)
    sorgu = [c for c in cursor.execute.call_args_list if "FROM cihazlar" in c.args[0]][0]
    assert "ariza_id <> %s" in sorgu.args[0] and "cozuldu_mu = FALSE" in sorgu.args[0]
    assert "FOR UPDATE" in sorgu.args[0]
    assert sorgu.args[1] == (10, 5, 10)               # (cihaz, bu arıza hariç, cihaz)


# -------------------------------------------------------------------- ariza_bildir
def bildir(eski_durum):
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchone.side_effect = [(eski_durum,), ("kullanici",), (5,)]
    model = ArizaBildirimModeli(
        cihaz_id=10, aciliyet="Orta", ariza_baslik="Test arızası", ariza_aciklama="Test açıklaması"
    )
    with patch("sunucu.psycopg2.connect", return_value=conn):
        sonuc = ariza_bildir(ariza=model, kullanici_id=1)
    guncellemeler = [c.args[1][0] for c in cursor.execute.call_args_list if c.args[0].startswith("UPDATE cihazlar")]
    olaylar = [c.args[1][1] for c in cursor.execute.call_args_list if "INSERT INTO denetim_kayitlari" in c.args[0]]
    ariza_eklendi = any("INSERT INTO cihaz_arizalari" in c.args[0] for c in cursor.execute.call_args_list)
    return sonuc, guncellemeler, olaylar, ariza_eklendi


@pytest.mark.parametrize("durum", ["Kullanima_Hazir", "Rezerve", "Kullanimda"])
def test_calisan_cihaza_ariza_bildirilince_cihaz_arizali_olur(durum):
    sonuc, guncellemeler, olaylar, _ = bildir(durum)
    assert guncellemeler == ["Arizali"]
    assert olaylar == ["CREATE", "DEVICE_STATUS_CHANGE"]
    assert "arızalı konuma çekildi" in sonuc["mesaj"]


@pytest.mark.parametrize("durum", ["Bakimda", "Kalibrasyonda", "Kullanim_Disi"])
def test_bakimdaki_cihaza_ariza_bildirilince_kayit_tutulur_ama_durum_degismez(durum):
    sonuc, guncellemeler, olaylar, ariza_eklendi = bildir(durum)
    assert ariza_eklendi and sonuc["ariza_id"] == 5   # arıza kaydı kaybolmaz
    assert guncellemeler == []
    assert olaylar == ["CREATE"]
    assert durum in sonuc["mesaj"] and "değiştirilmedi" in sonuc["mesaj"]


def test_zaten_arizali_cihaza_ikinci_ariza_durum_degisimi_yazmaz():
    sonuc, guncellemeler, olaylar, _ = bildir("Arizali")
    assert guncellemeler == [] and olaylar == ["CREATE"]
