"""Puan Raporu: sunucu ucu (sıralama, filtreler, yetki), Excel çıktısı, ekran ve menü bağlantısı.

Gerçek sunucu/PostgreSQL kullanılmaz; veritabanı ve ağ istekleri taklit edilir.
"""
import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication

import main_window
import puan_raporu_ekrani as ekran_modulu
import sunucu
import tkys_sidebar_refined
from puan_rapor_excel import excel_dosyasi_olustur
from sunucu import app, mevcut_kullanici_id

GUN = datetime.date


def ogr(id_, ad, no, tur, aktif, puan, adet, son=None):
    return (id_, ad, no, tur, aktif, puan, adet, son)


# DB'den puana göre azalan gelir: 412, 380, 380, 295, 0, 0
SATIRLAR = [
    ogr(1, "Ayşe", "1001", "GONULLU", True, 412, 20, GUN(2026, 11, 3)),
    ogr(2, "Burak", "1002", "DANISMA_MASASI", False, 380, 19, GUN(2026, 10, 1)),
    ogr(3, "Cem", "1003", "GONULLU", True, 380, 19, GUN(2026, 9, 9)),
    ogr(4, "Deniz", "1004", "GONULLU", True, 295, 14, GUN(2026, 8, 8)),
    ogr(5, "Elif", "1005", "GONULLU", True, 0, 0, None),
    ogr(6, "Fatma", "1006", "GONULLU", False, 0, 0, None),
]
DETAYLAR = [
    (1, GUN(2026, 11, 3), "Seminer", 2, "SAAT", 10, 20),
    (1, GUN(2026, 5, 1), "Rehberlik", 1, "KISI", 5, 5),
    (2, GUN(2026, 10, 1), "Seminer", 3, "SAAT", 10, 30),
]


@pytest.fixture(autouse=True)
def giris_yapmis_kullanici():
    app.dependency_overrides[mevcut_kullanici_id] = lambda: 5
    yield
    app.dependency_overrides.pop(mevcut_kullanici_id, None)


def rapor(sorgu="", satirlar=SATIRLAR, detaylar=None, izin=True):
    conn = MagicMock()
    c = conn.cursor.return_value
    c.fetchone.side_effect = [(1,)] if izin else [None]
    c.fetchall.side_effect = [list(satirlar)] + ([list(detaylar)] if detaylar is not None else [])
    with patch("sunucu.psycopg2.connect", return_value=conn):
        yanit = TestClient(app).get("/api/puan-raporu" + sorgu)
    return yanit, c


def rapor_sorgulari(c):
    return [x for x in c.execute.call_args_list if "ogrenci_faaliyet_takip" in x.args[0]]


# ================================================================ sunucu: sıralama
def test_siralama_esit_puanlilar_ayni_sirayi_alir_ve_sonraki_atlar():
    yanit, _ = rapor()
    assert yanit.status_code == 200, yanit.text
    assert [o["sira"] for o in yanit.json()["ogrenciler"]] == [1, 2, 2, 4, None, None]


def test_puani_olmayanin_sirasi_yoktur_ama_listede_kalir():
    ogrenciler = rapor()[0].json()["ogrenciler"]
    assert [o["ad_soyad"] for o in ogrenciler][-2:] == ["Elif", "Fatma"]
    assert all(o["sira"] is None and o["toplam_puan"] == 0 and o["faaliyet_sayisi"] == 0 for o in ogrenciler[-2:])


def test_pasif_ogrenciler_listede_kalir_ve_durumu_gorunur():
    durumlar = {o["ad_soyad"]: o["aktif_mi"] for o in rapor()[0].json()["ogrenciler"]}
    assert durumlar == {"Ayşe": True, "Burak": False, "Cem": True, "Deniz": True, "Elif": True, "Fatma": False}


def test_ogrenci_alanlari_tur_etiketi_ve_son_tarih():
    ilk, ikinci = rapor()[0].json()["ogrenciler"][:2]
    assert ilk["tur_etiketi"] == "Gönüllü Öğrenci" and ikinci["tur_etiketi"] == "Danışma Masası Öğrencisi"
    assert ilk["son_faaliyet_tarihi"] == "2026-11-03" and ilk["ogrenci_numarasi"] == "1001"


def test_ozet_toplam_ortalama_ve_en_yuksek():
    ozet = rapor()[0].json()["ozet"]
    assert ozet["ogrenci_sayisi"] == 6 and ozet["puanli_ogrenci_sayisi"] == 4
    assert ozet["toplam_puan"] == 412 + 380 + 380 + 295 and ozet["faaliyet_kaydi_sayisi"] == 72
    assert ozet["ortalama_puan"] == pytest.approx(1467 / 4)               # puansızlar ortalamayı düşürmez
    assert ozet["en_yuksek_puan"] == 412 and ozet["en_yuksek_ogrenciler"] == ["Ayşe"]


def test_en_yuksek_puan_esitse_hepsinin_adi_gelir():
    ozet = rapor(satirlar=[ogr(1, "A", "1", "GONULLU", True, 50, 1), ogr(2, "B", "2", "GONULLU", True, 50, 1)])[0].json()["ozet"]
    assert ozet["en_yuksek_ogrenciler"] == ["A", "B"]


def test_kimsenin_puani_yoksa_ozet_sifir_ve_hatasiz():
    yanit, _ = rapor(satirlar=[ogr(1, "A", "1", "GONULLU", True, 0, 0)])
    ozet = yanit.json()["ozet"]
    assert yanit.status_code == 200 and ozet["ortalama_puan"] == 0 and ozet["en_yuksek_ogrenciler"] == []


def test_ogrenci_yoksa_bos_liste_doner():
    yanit, _ = rapor(satirlar=[])
    assert yanit.status_code == 200 and yanit.json()["ogrenciler"] == [] and yanit.json()["ozet"]["ogrenci_sayisi"] == 0


# ================================================================ sunucu: filtreler
def test_filtreler_parametreli_ve_sirasi_dogru():
    _, c = rapor("?baslangic=2026-01-01&bitis=2026-12-31&tur=GONULLU&durum=pasif")
    sorgu, parametreler = rapor_sorgulari(c)[0].args
    assert parametreler == [GUN(2026, 1, 1), GUN(2026, 12, 31), "GONULLU", False]
    assert "t.faaliyet_tarihi >= %s" in sorgu and "t.faaliyet_tarihi <= %s" in sorgu
    assert "o.tur::text = %s" in sorgu and "o.aktif_mi = %s" in sorgu
    assert "2026" not in sorgu and "GONULLU" not in sorgu                  # değerler sorguya yapıştırılmaz


def test_tarih_kosulu_birlesimde_olur_boylece_puansiz_ogrenciler_kaybolmaz():
    _, c = rapor("?baslangic=2026-01-01&bitis=2026-12-31")
    sorgu = rapor_sorgulari(c)[0].args[0]
    assert "LEFT JOIN ogrenci_faaliyet_takip t" in sorgu
    birlesim = sorgu.split("ON ", 1)[1].split("WHERE")[0].split("GROUP BY")[0]
    assert "faaliyet_tarihi" in birlesim


def test_filtre_yoksa_parametre_de_yoktur():
    _, c = rapor()
    sorgu, parametreler = rapor_sorgulari(c)[0].args
    assert parametreler == [] and "WHERE" not in sorgu and "HAVING" not in sorgu


def test_aktif_durumu_true_parametresi_gonderir():
    _, c = rapor("?durum=aktif")
    assert rapor_sorgulari(c)[0].args[1] == [True]


def test_puansizlari_gizle_having_ekler():
    _, c = rapor("?puansizlari_goster=false")
    assert "HAVING COUNT(t.takip_id) > 0" in rapor_sorgulari(c)[0].args[0]
    _, c = rapor("?puansizlari_goster=true")
    assert "HAVING" not in rapor_sorgulari(c)[0].args[0]


def test_filtre_bilgisi_yanitta_geri_doner():
    filtre = rapor("?baslangic=2026-01-01&bitis=2026-06-30&tur=DANISMA_MASASI&durum=aktif&puansizlari_goster=false")[0].json()["filtre"]
    assert filtre == {"baslangic": "2026-01-01", "bitis": "2026-06-30", "tur": "DANISMA_MASASI", "durum": "aktif",
                      "puansizlari_goster": False}


@pytest.mark.parametrize("sorgu", ["?baslangic=2026-12-31&bitis=2026-01-01", "?tur=YONETICI", "?durum=belki",
                                   "?tur=GONULLU'%3B%20DROP%20TABLE%20ogrenciler%3B--", "?baslangic=bugun"])
def test_gecersiz_filtreler_422_verir_ve_sorgu_calismaz(sorgu):
    yanit, c = rapor(sorgu)
    assert yanit.status_code == 422 and not rapor_sorgulari(c)


def test_ayni_gun_baslangic_ve_bitis_gecerlidir():
    assert rapor("?baslangic=2026-05-05&bitis=2026-05-05")[0].status_code == 200


# ================================================================ sunucu: detay
def test_detay_istenmezse_ikinci_sorgu_yoktur_ve_detaylar_donmez():
    yanit, c = rapor()
    assert "detaylar" not in yanit.json() and len(rapor_sorgulari(c)) == 1


def test_detay_istenirse_kayitlar_donar_ve_ayni_tarih_filtresi_uygulanir():
    yanit, c = rapor("?detay=true&baslangic=2026-01-01&bitis=2026-12-31", detaylar=DETAYLAR)
    detaylar = yanit.json()["detaylar"]
    assert [d["faaliyet"] for d in detaylar] == ["Seminer", "Rehberlik", "Seminer"]
    assert detaylar[0] == {"ogrenci_id": 1, "tarih": "2026-11-03", "faaliyet": "Seminer", "adet": 2, "birim": "SAAT",
                           "birim_puan": 10.0, "toplam_puan": 20.0}
    sorgu, parametreler = rapor_sorgulari(c)[1].args
    assert parametreler == [[1, 2, 3, 4, 5, 6], GUN(2026, 1, 1), GUN(2026, 12, 31)]
    assert "t.faaliyet_tarihi >= %s" in sorgu and "ANY(%s)" in sorgu


def test_detay_icin_liste_bossa_ikinci_sorgu_calismaz():
    yanit, c = rapor("?detay=true", satirlar=[])
    assert yanit.json()["detaylar"] == [] and len(rapor_sorgulari(c)) == 1


# ================================================================ sunucu: yetki ve hata
def test_yetkisiz_kullanici_403_alir_ve_hicbir_rapor_sorgusu_calismaz():
    yanit, c = rapor(izin=False)
    assert yanit.status_code == 403 and not rapor_sorgulari(c)


def test_yetki_faaliyet_kayitlari_duzenleme_iznine_baglidir():
    kaynak = Path(sunucu.__file__).read_text(encoding="utf-8")
    govde = kaynak[kaynak.index("def puan_raporu("):kaynak.index("def _ogrenci_on_yil_kontrol")]
    assert 'izin_kontrol("FAALIYET_KAYITLARI_DUZENLE")' in govde


def test_veritabani_hatasinda_ic_hata_metni_sizmaz():
    conn = MagicMock()
    c = conn.cursor.return_value
    c.fetchone.side_effect = [(1,)]
    c.execute.side_effect = [None, RuntimeError("gizli_sema_adi baglanti parolasi")]
    with patch("sunucu.psycopg2.connect", return_value=conn):
        yanit = TestClient(app).get("/api/puan-raporu")
    assert yanit.status_code == 500 and yanit.json()["detail"] == "Puan raporu alınamadı."
    assert "gizli" not in yanit.text


def test_baglanti_her_durumda_kapatilir():
    conn = MagicMock()
    c = conn.cursor.return_value
    c.fetchone.side_effect = [(1,)]
    c.execute.side_effect = [None, RuntimeError("x")]
    with patch("sunucu.psycopg2.connect", return_value=conn):
        TestClient(app).get("/api/puan-raporu")
    assert conn.close.called


# ================================================================ Excel
def api_verisi(detay=True):
    veri = rapor("?detay=true", detaylar=DETAYLAR)[0].json() if detay else rapor()[0].json()
    return veri


FILTRE = [("Dönem", "Tümü"), ("Öğrenci Türü", "Tümü"), ("Öğrenci Durumu", "Tümü"), ("Puanı Olmayanlar", "Gösterilir")]


def uret(tmp_path, veri=None, filtre=FILTRE):
    yol = tmp_path / "puan.xlsx"
    excel_dosyasi_olustur(api_verisi() if veri is None else veri, filtre, str(yol))
    return load_workbook(yol)


def satirlar(sayfa):
    return [[h.value for h in satir] for satir in sayfa.iter_rows(min_row=2)]


def ozet_metni(sayfa):
    return {(r[0].value, r[1].value) for r in sayfa.iter_rows() if r[0].value}


def tum_metin(sayfa):
    return " ".join(str(c.value) for r in sayfa.iter_rows() for c in r if c.value is not None)


def test_dort_sayfa_beklenen_sirayla_olusur(tmp_path):
    assert uret(tmp_path).sheetnames == ["Özet", "Puan Sıralaması", "Faaliyet Dağılımı", "Faaliyet Detayı"]


def test_siralama_sayfasi_en_yuksek_puanli_en_ustte(tmp_path):
    sayfa = uret(tmp_path)["Puan Sıralaması"]
    assert [h.value for h in sayfa[1]] == ["Sıra", "Öğrenci", "Öğrenci No", "Öğrenci Türü", "Öğrenci Durumu", "Faaliyet Sayısı",
                                           "Toplam Puan", "Faaliyet Başına Ortalama Puan", "Son Faaliyet Tarihi"]
    satir = satirlar(sayfa)
    assert [r[1] for r in satir] == ["Ayşe", "Burak", "Cem", "Deniz", "Elif", "Fatma"]
    assert [r[6] for r in satir] == [412, 380, 380, 295, 0, 0]
    assert [r[0] for r in satir] == [1, 2, 2, 4, "—", "—"]


def test_pasif_ogrenci_durum_sutununda_pasif_ve_kirmizi(tmp_path):
    sayfa = uret(tmp_path)["Puan Sıralaması"]
    durumlar = {r[1]: r[4] for r in satirlar(sayfa)}
    assert durumlar["Burak"] == "Pasif" and durumlar["Ayşe"] == "Aktif"
    assert str(sayfa["E3"].font.color.rgb).endswith("C0392B")
    assert not (sayfa["E2"].font.color and str(sayfa["E2"].font.color.rgb).endswith("C0392B"))


def test_ilk_uc_sira_renklendirilir_digerleri_renksiz(tmp_path):
    sayfa = uret(tmp_path)["Puan Sıralaması"]
    renkler = [sayfa.cell(row=r, column=2).fill.fgColor.rgb[-6:] for r in range(2, 8)]
    assert renkler[0] == "FFF2B8" and renkler[1] == renkler[2] == "E9EDF3"
    assert renkler[3] == "000000" and renkler[4] == "000000"             # dolgu yok


def test_ortalama_ve_tarih_sutunlari(tmp_path):
    satir = satirlar(uret(tmp_path)["Puan Sıralaması"])
    assert satir[0][7] == 20.6 and satir[0][8] == datetime.datetime(2026, 11, 3)
    assert satir[4][7] is None and satir[4][8] is None                    # faaliyeti olmayan: boş


def test_faaliyet_dagilimi_puana_gore_azalan_ve_paylar_toplami_bir(tmp_path):
    sayfa = uret(tmp_path)["Faaliyet Dağılımı"]
    satir = satirlar(sayfa)
    assert [h.value for h in sayfa[1]] == ["Faaliyet", "Kayıt Sayısı", "Katılan Öğrenci", "Toplam Puan", "Toplam İçindeki Payı"]
    assert [r[:4] for r in satir] == [["Seminer", 2, 2, 50], ["Rehberlik", 1, 1, 5]]
    assert sum(r[4] for r in satir) == pytest.approx(1.0)
    assert sayfa["E2"].number_format == "0.0%"


def test_faaliyet_detayi_ogrenci_sirasina_gore_ve_tum_kayitlar(tmp_path):
    sayfa = uret(tmp_path)["Faaliyet Detayı"]
    satir = satirlar(sayfa)
    assert [h.value for h in sayfa[1]][:6] == ["Sıra", "Öğrenci", "Öğrenci No", "Öğrenci Durumu", "Tarih", "Faaliyet"]
    assert [(r[1], r[5], r[6], r[7], r[9]) for r in satir] == [
        ("Ayşe", "Seminer", 2, "SAAT", 20), ("Ayşe", "Rehberlik", 1, "KISI", 5), ("Burak", "Seminer", 3, "SAAT", 30)]
    assert satir[2][3] == "Pasif" and satir[0][0] == 1 and satir[2][0] == 2


def test_ozet_sayfasi_degerleri_ilk_uc_ve_pasif_listesi(tmp_path):
    sayfa = uret(tmp_path)["Özet"]
    ozet = ozet_metni(sayfa)
    for beklenen in [("Listelenen öğrenci", 6), ("Puanı olan öğrenci", 4), ("Faaliyet kaydı", 72), ("Toplam puan", 1467),
                     ("Ortalama puan", 366.75), ("En yüksek puan", 412), ("1. sıra", 412), ("2. sıra", 380),
                     ("Aktif öğrenci", 4), ("Pasif öğrenci", 2)]:
        assert beklenen in ozet, beklenen
    metin = tum_metin(sayfa)
    assert "Ayşe (1001)" in metin and "Burak (1002) — pasif öğrenci" in metin and "Fatma (1006)" in metin
    assert not any(a == "3. sıra" for a, _ in ozet) and ("2. sıra", 380) in ozet      # 2. sıra iki kişi; 3. sıra yok


def test_ozet_sayfasi_filtreleri_hesap_notu_ve_rapor_tarihi(tmp_path):
    filtre = [("Dönem", "01.01.2026 - 31.12.2026"), ("Öğrenci Türü", "Gönüllü Öğrenci"), ("Öğrenci Durumu", "Pasif"),
              ("Puanı Olmayanlar", "Gizlenir")]
    sayfa = uret(tmp_path, filtre=filtre)["Özet"]
    ozet = ozet_metni(sayfa)
    for beklenen in filtre:
        assert beklenen in ozet
    assert any(a == "Rapor Tarihi" and isinstance(d, datetime.datetime) for a, d in ozet)
    assert "Miktar × Faaliyet puanı" in tum_metin(sayfa) and sayfa["A1"].value.startswith("PUAN RAPORU")


def test_detay_verisi_yoksa_sayfalar_bos_ama_rapor_uretilir(tmp_path):
    kitap = uret(tmp_path, api_verisi(detay=False))
    assert satirlar(kitap["Faaliyet Dağılımı"]) == [] and satirlar(kitap["Faaliyet Detayı"]) == []
    assert len(satirlar(kitap["Puan Sıralaması"])) == 6


def test_bos_rapor_hatasiz_uretilir(tmp_path):
    bos = {"ozet": {}, "ogrenciler": [], "detaylar": []}
    kitap = uret(tmp_path, bos)
    assert all(satirlar(kitap[ad]) == [] for ad in kitap.sheetnames[1:])
    assert ("Listelenen öğrenci", 0) in ozet_metni(kitap["Özet"]) and "puanı olan öğrenci yok" in tum_metin(kitap["Özet"])


def test_kuruslu_puan_tam_sayiya_cevrilmez(tmp_path):
    veri = {"ozet": {"toplam_puan": 10.5}, "ogrenciler": [
        {"sira": 1, "ogrenci_id": 1, "ad_soyad": "A", "ogrenci_numarasi": "1", "tur": "GONULLU", "aktif_mi": True,
         "toplam_puan": 10.5, "faaliyet_sayisi": 2, "son_faaliyet_tarihi": None}]}
    assert satirlar(uret(tmp_path, veri)["Puan Sıralaması"])[0][6] == 10.5


@pytest.mark.parametrize("tehlikeli", ["=1+1", "+SUM(A1)", "-2+3", "@HYPERLINK(\"x\")"])
def test_ogrenci_adi_formul_olarak_calismaz(tmp_path, tehlikeli):
    veri = {"ozet": {}, "ogrenciler": [{"sira": 1, "ogrenci_id": 1, "ad_soyad": tehlikeli, "ogrenci_numarasi": "1",
                                        "tur": "GONULLU", "aktif_mi": True, "toplam_puan": 5, "faaliyet_sayisi": 1,
                                        "son_faaliyet_tarihi": None}],
            "detaylar": [{"ogrenci_id": 1, "tarih": "2026-01-01", "faaliyet": tehlikeli, "adet": 1, "birim": "", "birim_puan": 5,
                          "toplam_puan": 5}]}
    kitap = uret(tmp_path, veri)
    for ad, sutun in (("Puan Sıralaması", "B2"), ("Faaliyet Detayı", "B2"), ("Faaliyet Detayı", "F2"), ("Faaliyet Dağılımı", "A2")):
        hucre = kitap[ad][sutun]
        assert hucre.data_type == "s" and hucre.value == tehlikeli, (ad, sutun)


def test_cihaz_ve_danisma_raporlariyla_ayni_gorunum(tmp_path):
    import rapor_excel
    kitap = uret(tmp_path)
    assert kitap["Puan Sıralaması"]["A1"].fill.fgColor.rgb.endswith("E8F0FF") and rapor_excel.BASLIK_DOLGU.fgColor.rgb.endswith("E8F0FF")
    assert kitap["Puan Sıralaması"].freeze_panes == "A2" and kitap["Puan Sıralaması"].auto_filter.ref


def test_kaydedilemezse_oserror_yukselir(tmp_path):
    with pytest.raises(OSError):
        excel_dosyasi_olustur(api_verisi(), FILTRE, str(tmp_path / "yok_klasor" / "r.xlsx"))


# ================================================================ ekran
@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def api_yaniti():
    return rapor()[0].json()


def yanit(veri, durum=200):
    r = MagicMock()
    r.status_code = durum
    r.json.return_value = veri
    return r


def ekran_ac(qt_app, veri=None, hata=False):
    veri = api_yaniti() if veri is None else veri
    istek = MagicMock(side_effect=ekran_modulu.requests.RequestException("ag yok")) if hata else MagicMock(return_value=yanit(veri))
    with patch.object(ekran_modulu, "oturum_kontrollu_istek", istek), \
            patch.object(ekran_modulu, "oturum_hatasi_mi", return_value=False), \
            patch.object(ekran_modulu.QMessageBox, "warning"):
        e = ekran_modulu.PuanRaporuEkrani("http://s", "t")
    e._veri = veri
    return e


def hucre(e, satir, sutun):
    return e.tablo.item(satir, sutun).text()


def istek_degistir(e, *, veri=None, hata=False, ayar):
    """Filtre kutusunu değiştirir ve gönderilen isteği (varsa uyarıyı) döndürür."""
    istek = MagicMock(side_effect=ekran_modulu.requests.RequestException("x")) if hata else MagicMock(return_value=yanit(veri or e._veri))
    with patch.object(ekran_modulu, "oturum_kontrollu_istek", istek), \
            patch.object(ekran_modulu, "oturum_hatasi_mi", return_value=False), \
            patch.object(ekran_modulu.QMessageBox, "warning") as uyari:
        ayar()
    return istek, uyari


def test_acilista_en_yuksek_puanli_ogrenci_en_ustte(qt_app):
    e = ekran_ac(qt_app)
    assert e.tablo.rowCount() == 6
    assert [hucre(e, s, ekran_modulu.SUTUN_OGRENCI) for s in range(6)] == ["Ayşe", "Burak", "Cem", "Deniz", "Elif", "Fatma"]
    assert [hucre(e, s, ekran_modulu.SUTUN_PUAN) for s in range(6)] == ["412", "380", "380", "295", "0", "0"]


def test_sira_sutunu_madalya_esit_sira_ve_tire(qt_app):
    e = ekran_ac(qt_app)
    assert [hucre(e, s, 0) for s in range(6)] == ["🥇 1", "🥈 2", "🥈 2", "4", "—", "—"]


def test_pasif_ogrenci_durumu_kirmizi_gorunur(qt_app):
    e = ekran_ac(qt_app)
    assert [hucre(e, s, ekran_modulu.SUTUN_DURUM) for s in range(6)] == ["Aktif", "Pasif", "Aktif", "Aktif", "Aktif", "Pasif"]
    pasif, aktif = e.tablo.item(1, ekran_modulu.SUTUN_DURUM), e.tablo.item(0, ekran_modulu.SUTUN_DURUM)
    assert pasif.foreground().color().name().upper() == ekran_modulu.PASIF_RENK and aktif.foreground().color().name().upper() != ekran_modulu.PASIF_RENK


def test_ilk_uc_satir_arka_plani_renklidir(qt_app):
    e = ekran_ac(qt_app)
    assert e.tablo.item(0, 1).background().color().name().upper() == "#FFF8DC"
    assert e.tablo.item(3, 1).background().color().name().upper() != "#FFF8DC"


def test_puan_cubugu_en_yuksege_oranlidir_pasif_gri(qt_app):
    e = ekran_ac(qt_app)
    degerler = [e.tablo.cellWidget(s, ekran_modulu.SUTUN_CUBUK).findChild(ekran_modulu.QProgressBar).value() for s in range(6)]
    assert degerler == [100, 92, 92, 72, 0, 0]
    pasif_cubuk = e.tablo.cellWidget(1, ekran_modulu.SUTUN_CUBUK).findChild(ekran_modulu.QProgressBar)
    assert "#C9D3E6" in pasif_cubuk.styleSheet()


def test_ozet_kartlari_ve_ilk_uc_kutulari(qt_app):
    e = ekran_ac(qt_app)
    assert e.kartlar["ogrenci"][0].text() == "6" and "4 öğrencinin" in e.kartlar["ogrenci"][1].text()
    assert e.kartlar["toplam_puan"][0].text() == "1.467" and e.kartlar["en_yuksek"][0].text() == "412"
    assert e.kartlar["en_yuksek"][1].text() == "Ayşe" and e.kartlar["ortalama_puan"][0].text() == "366,75"
    assert not e.podyum_kutusu.isHidden()
    assert "Ayşe" in e.podyum[0][1].text() and "412 puan" in e.podyum[0][1].text() and "Burak" in e.podyum[1][1].text()


def test_kimsenin_puani_yoksa_ilk_uc_kutusu_gizlenir(qt_app):
    veri = rapor(satirlar=[ogr(1, "A", "1", "GONULLU", True, 0, 0)])[0].json()
    e = ekran_ac(qt_app, veri)
    assert e.podyum_kutusu.isHidden() and hucre(e, 0, 0) == "—"


def test_puan_metni_binlik_ayrac_ve_kurus():
    assert ekran_modulu.puan_metni(1250) == "1.250" and ekran_modulu.puan_metni(260.5) == "260,50"
    assert ekran_modulu.puan_metni(0) == "0" and ekran_modulu.puan_metni(None) == "0" and ekran_modulu.puan_metni(1234567.5) == "1.234.567,50"


# ---- arama
def test_arama_satirlari_gizler_ama_sira_numaralari_degismez(qt_app):
    e = ekran_ac(qt_app)
    e.arama.setText("deniz")
    gorunen = [s for s in range(6) if not e.tablo.isRowHidden(s)]
    assert gorunen == [3] and hucre(e, 3, 0) == "4"                      # 4. sıra olarak kalır
    assert "1 / 6" in e.durum_etiketi.text()


def test_arama_numaraya_gore_ve_buyuk_kucuk_harf_duyarsiz(qt_app):
    e = ekran_ac(qt_app)
    e.arama.setText("1002")
    assert [s for s in range(6) if not e.tablo.isRowHidden(s)] == [1]
    e.arama.setText("AYŞE")
    assert [s for s in range(6) if not e.tablo.isRowHidden(s)] == [0]


def test_arama_temizlenince_hepsi_geri_gelir_ve_eslesme_yoksa_mesaj_cikar(qt_app):
    e = ekran_ac(qt_app)
    e.arama.setText("yokboyleogrenci")
    assert all(e.tablo.isRowHidden(s) for s in range(6)) and not e.bos_mesaj.isHidden() and "uyan öğrenci yok" in e.bos_mesaj.text()
    e.arama.setText("")
    assert not any(e.tablo.isRowHidden(s) for s in range(6)) and e.bos_mesaj.isHidden()


def test_hic_ogrenci_yoksa_bos_durum_mesaji(qt_app):
    veri = rapor(satirlar=[])[0].json()
    e = ekran_ac(qt_app, veri)
    assert e.tablo.rowCount() == 0 and not e.bos_mesaj.isHidden() and "bulunamadı" in e.bos_mesaj.text()


# ---- filtreler ve istekler
def test_acilista_bu_yil_secili_ve_istek_tum_yili_kapsar(qt_app):
    istek = MagicMock(return_value=yanit(api_yaniti()))
    with patch.object(ekran_modulu, "oturum_kontrollu_istek", istek), patch.object(ekran_modulu, "oturum_hatasi_mi", return_value=False):
        e = ekran_modulu.PuanRaporuEkrani("http://s", "t")
    yil = QDate.currentDate().year()
    params = istek.call_args.kwargs["params"]
    assert e.donem.currentText() == "Bu Yıl" and istek.call_args.args[:2] == ("GET", "http://s/api/puan-raporu")
    assert params == {"puansizlari_goster": "true", "baslangic": f"{yil}-01-01", "bitis": f"{yil}-12-31"}
    assert istek.call_args.kwargs["headers"] == {"Authorization": "Bearer t"}


def test_donem_secenekleri_dogru_tarih_araligini_uretir(qt_app):
    e = ekran_ac(qt_app)
    bugun = QDate.currentDate()
    beklenen = {
        "Geçen Yıl": (QDate(bugun.year() - 1, 1, 1), QDate(bugun.year() - 1, 12, 31)),
        "Son 6 Ay": (bugun.addMonths(-6), bugun),
        "Bu Ay": (QDate(bugun.year(), bugun.month(), 1), QDate(bugun.year(), bugun.month(), 1).addMonths(1).addDays(-1)),
        "Tümü": (None, None),
    }
    for ad, aralik in beklenen.items():
        e.donem.blockSignals(True)
        e.donem.setCurrentText(ad)
        e.donem.blockSignals(False)
        assert e._donem_araligi() == aralik, ad


def test_donem_degisince_tarih_kutulari_dolar_ve_yalnizca_ozelde_acilir(qt_app):
    e = ekran_ac(qt_app)
    istek_degistir(e, ayar=lambda: e.donem.setCurrentText("Geçen Yıl"))
    assert e.baslangic.date().year() == QDate.currentDate().year() - 1 and not e.baslangic.isEnabled() and not e.bitis.isEnabled()
    istek_degistir(e, ayar=lambda: e.donem.setCurrentText("Tarih Aralığı"))
    assert e.baslangic.isEnabled() and e.bitis.isEnabled()


def test_donem_tumu_istege_tarih_eklemez(qt_app):
    e = ekran_ac(qt_app)
    istek, _ = istek_degistir(e, ayar=lambda: e.donem.setCurrentText("Tümü"))
    assert "baslangic" not in istek.call_args.kwargs["params"] and "bitis" not in istek.call_args.kwargs["params"]
    assert e._son_filtre[0] == ("Dönem", "Tümü")


def test_ozel_aralikta_tarih_degisince_rapor_yenilenir_baska_donemde_yenilenmez(qt_app):
    e = ekran_ac(qt_app)
    istek_degistir(e, ayar=lambda: e.donem.setCurrentText("Tarih Aralığı"))
    istek, _ = istek_degistir(e, ayar=lambda: e.baslangic.setDate(QDate(2025, 3, 1)))
    assert istek.call_args.kwargs["params"]["baslangic"] == "2025-03-01"
    istek_degistir(e, ayar=lambda: e.donem.setCurrentText("Bu Yıl"))
    istek, _ = istek_degistir(e, ayar=lambda: e.baslangic.setDate(QDate(2025, 3, 2)))     # kutu kapalı: kullanıcı değiştiremez
    assert not istek.called


def test_bitis_baslangictan_once_ise_uyarilir_ve_istek_atilmaz(qt_app):
    e = ekran_ac(qt_app)
    istek_degistir(e, ayar=lambda: e.donem.setCurrentText("Tarih Aralığı"))
    e.baslangic.blockSignals(True)
    e.baslangic.setDate(QDate(2026, 6, 1))
    e.baslangic.blockSignals(False)
    istek, uyari = istek_degistir(e, ayar=lambda: e.bitis.setDate(QDate(2026, 5, 1)))
    assert uyari.called and "Bitiş tarihi" in uyari.call_args.args[2] and not istek.called


def test_tur_ve_durum_secimi_istege_eklenir_ve_filtre_ozetine_yazilir(qt_app):
    e = ekran_ac(qt_app)
    istek, _ = istek_degistir(e, ayar=lambda: e.tur_sec.setCurrentIndex(2))
    assert istek.call_args.kwargs["params"]["tur"] == "DANISMA_MASASI"
    istek, _ = istek_degistir(e, ayar=lambda: e.durum_sec.setCurrentIndex(2))
    assert istek.call_args.kwargs["params"]["durum"] == "pasif"
    assert dict(e._son_filtre)["Öğrenci Türü"] == "Danışma Masası Öğrencisi" and dict(e._son_filtre)["Öğrenci Durumu"] == "Pasif"


def test_tumu_secilince_tur_ve_durum_istekten_cikar(qt_app):
    e = ekran_ac(qt_app)
    istek_degistir(e, ayar=lambda: e.tur_sec.setCurrentIndex(1))
    istek, _ = istek_degistir(e, ayar=lambda: e.tur_sec.setCurrentIndex(0))
    assert "tur" not in istek.call_args.kwargs["params"] and "durum" not in istek.call_args.kwargs["params"]


def test_puansizlari_gizleme_kutusu_istege_ve_filtre_ozetine_yansir(qt_app):
    e = ekran_ac(qt_app)
    istek, _ = istek_degistir(e, ayar=lambda: e.puansiz_kutusu.setChecked(False))
    assert istek.call_args.kwargs["params"]["puansizlari_goster"] == "false" and dict(e._son_filtre)["Puanı Olmayanlar"] == "Gizlenir"


def test_sunucuya_ulasilamazsa_uyari_verilir_eski_liste_ve_dugme_korunur(qt_app):
    e = ekran_ac(qt_app)
    istek, uyari = istek_degistir(e, hata=True, ayar=lambda: e.tur_sec.setCurrentIndex(1))
    assert uyari.called and "alınamadı" in uyari.call_args.args[2]
    assert e.tablo.rowCount() == 6 and e.excel_btn.isEnabled()


def test_ilk_acilista_ulasilamazsa_excel_dugmesi_kapali(qt_app):
    e = ekran_ac(qt_app, hata=True)
    assert not e.excel_btn.isEnabled() and e._son_params is None and e.tablo.rowCount() == 0


def test_yenile_dugmesi_raporu_yeniden_getirir(qt_app):
    e = ekran_ac(qt_app)
    istek = MagicMock(return_value=yanit(e._veri))
    with patch.object(ekran_modulu, "oturum_kontrollu_istek", istek), patch.object(ekran_modulu, "oturum_hatasi_mi", return_value=False):
        e.yenile_btn.click()
    assert istek.call_count == 1


def test_oturum_hatasinda_ekran_degismez(qt_app):
    e = ekran_ac(qt_app)
    with patch.object(ekran_modulu, "oturum_kontrollu_istek", return_value=yanit({}, 401)), \
            patch.object(ekran_modulu, "oturum_hatasi_mi", return_value=True):
        e.yenile()
    assert e.tablo.rowCount() == 6


# ---- Excel düğmesi
def test_excel_dugmesi_rapor_gelince_acilir(qt_app):
    assert ekran_ac(qt_app).excel_btn.isEnabled() and ekran_ac(qt_app).excel_btn.text() == "⬇ Excel'e Aktar"


def test_excel_aktar_ayrintili_veriyi_ayni_filtrelerle_ister_ve_dosyayi_yazar(qt_app, tmp_path):
    e = ekran_ac(qt_app)
    istek_degistir(e, ayar=lambda: e.tur_sec.setCurrentIndex(1))
    hedef = str(tmp_path / "rapor")                                    # uzantısız verildi
    tam = rapor("?detay=true", detaylar=DETAYLAR)[0].json()
    istek = MagicMock(return_value=yanit(tam))
    with patch.object(ekran_modulu, "oturum_kontrollu_istek", istek), patch.object(ekran_modulu, "oturum_hatasi_mi", return_value=False), \
            patch.object(ekran_modulu.QFileDialog, "getSaveFileName", return_value=(hedef, "")), \
            patch.object(ekran_modulu.QMessageBox, "information") as bilgi:
        e.excel_aktar()
    assert istek.call_args.kwargs["params"] == {**e._son_params, "detay": "true"} and e._son_params["tur"] == "GONULLU"
    assert bilgi.called and load_workbook(hedef + ".xlsx").sheetnames == ["Özet", "Puan Sıralaması", "Faaliyet Dağılımı", "Faaliyet Detayı"]


def test_excel_aramadan_etkilenmez_raporun_tamamini_icerir(qt_app, tmp_path):
    e = ekran_ac(qt_app)
    e.arama.setText("deniz")
    hedef = str(tmp_path / "r.xlsx")
    tam = rapor("?detay=true", detaylar=DETAYLAR)[0].json()
    with patch.object(ekran_modulu, "oturum_kontrollu_istek", return_value=yanit(tam)), patch.object(ekran_modulu, "oturum_hatasi_mi", return_value=False), \
            patch.object(ekran_modulu.QFileDialog, "getSaveFileName", return_value=(hedef, "")), patch.object(ekran_modulu.QMessageBox, "information"):
        e.excel_aktar()
    assert len(satirlar(load_workbook(hedef)["Puan Sıralaması"])) == 6


def test_excel_kaydetme_penceresi_iptalinde_sunucuya_gidilmez(qt_app):
    e = ekran_ac(qt_app)
    istek = MagicMock()
    with patch.object(ekran_modulu, "oturum_kontrollu_istek", istek), patch.object(ekran_modulu.QFileDialog, "getSaveFileName", return_value=("", "")):
        e.excel_aktar()
    assert not istek.called


def test_excel_rapor_yokken_uyari_verir(qt_app):
    e = ekran_ac(qt_app, hata=True)
    with patch.object(ekran_modulu.QMessageBox, "information") as bilgi, patch.object(ekran_modulu, "excel_dosyasi_olustur") as uretici:
        e.excel_aktar()
    assert bilgi.called and not uretici.called


def test_excel_icin_veri_alinamazsa_dosya_yazilmaz_ve_uyari_verilir(qt_app, tmp_path):
    e = ekran_ac(qt_app)
    with patch.object(ekran_modulu, "oturum_kontrollu_istek", side_effect=ekran_modulu.requests.RequestException("kesildi")), \
            patch.object(ekran_modulu.QFileDialog, "getSaveFileName", return_value=(str(tmp_path / "r.xlsx"), "")), \
            patch.object(ekran_modulu, "excel_dosyasi_olustur") as uretici, patch.object(ekran_modulu.QMessageBox, "warning") as uyari:
        e.excel_aktar()
    assert uyari.called and "Excel için rapor verisi" in uyari.call_args.args[2] and not uretici.called


def test_excel_yazma_hatasinda_anlasilir_uyari(qt_app, tmp_path):
    e = ekran_ac(qt_app)
    with patch.object(ekran_modulu, "oturum_kontrollu_istek", return_value=yanit(api_yaniti())), patch.object(ekran_modulu, "oturum_hatasi_mi", return_value=False), \
            patch.object(ekran_modulu.QFileDialog, "getSaveFileName", return_value=(str(tmp_path / "r.xlsx"), "")), \
            patch.object(ekran_modulu, "excel_dosyasi_olustur", side_effect=OSError("kilitli")), \
            patch.object(ekran_modulu.QMessageBox, "warning") as uyari, patch.object(ekran_modulu.QMessageBox, "information") as bilgi:
        e.excel_aktar()
    assert uyari.called and "Excel'de açık" in uyari.call_args.args[2] and not bilgi.called


# ================================================================ menü ve ana pencere bağlantısı
def test_menude_puan_raporu_sayfasi_var_ve_mevcut_izne_baglidir():
    sayfalar = {oge["ad"]: oge for _, ogeler in main_window.MENU for oge in ogeler}
    oge = sayfalar["Puan Raporu"]
    assert oge["izin"] == "Faaliyet kayıtlarını düzenleme" and oge["aksiyon"] == []
    assert oge["izin"] in main_window.IZIN_KODLARI and main_window.IZIN_KODLARI[oge["izin"]] == ("FAALIYET_KAYITLARI_DUZENLE",)


def test_puan_raporu_ogrenciler_sayfasiyla_ayni_yetkiyle_acilir():
    sayfalar = {oge["ad"]: oge for _, ogeler in main_window.MENU for oge in ogeler}
    assert sayfalar["Puan Raporu"]["izin"] == sayfalar["Öğrenciler"]["izin"]


def test_sayfa_acilinca_yenilenir_ve_kenar_cubugunda_ikonu_vardir():
    assert main_window.AnaPencere.SAYFA_YENILEME["Puan Raporu"] == ("puan_raporu_ekrani", "yenile")
    assert tkys_sidebar_refined.PAGE_ICONS["Puan Raporu"] in tkys_sidebar_refined.PATHS
    assert callable(ekran_modulu.PuanRaporuEkrani.yenile)


def test_ana_pencere_puan_raporu_ekranini_olusturur():
    kaynak = Path(main_window.__file__).read_text(encoding="utf-8")
    assert 'elif oge["ad"] == "Puan Raporu":' in kaynak and "PuanRaporuEkrani(" in kaynak and "self.puan_raporu_ekrani" in kaynak


# ================================================================ kaçan mutantları kapatan testler
def test_sql_puana_gore_azalan_sonra_ada_gore_siralar():
    _, c = rapor()
    sorgu = rapor_sorgulari(c)[0].args[0]
    assert "ORDER BY toplam_puan DESC, o.ad_soyad, o.ogrenci_id" in sorgu


def test_excel_detay_satirlari_ogrenci_id_sirasina_degil_puan_sirasina_gore_dizilir(tmp_path):
    veri = {"ozet": {}, "ogrenciler": [
        {"sira": 1, "ogrenci_id": 9, "ad_soyad": "Yüksek", "ogrenci_numarasi": "9", "tur": "GONULLU", "aktif_mi": True,
         "toplam_puan": 50, "faaliyet_sayisi": 1, "son_faaliyet_tarihi": None},
        {"sira": 2, "ogrenci_id": 1, "ad_soyad": "Düşük", "ogrenci_numarasi": "1", "tur": "GONULLU", "aktif_mi": True,
         "toplam_puan": 10, "faaliyet_sayisi": 1, "son_faaliyet_tarihi": None}],
        "detaylar": [   # sunucu öğrenci kimliğine göre verir: 1 önce, 9 sonra
            {"ogrenci_id": 1, "tarih": "2026-01-01", "faaliyet": "A", "adet": 1, "birim": "", "birim_puan": 10, "toplam_puan": 10},
            {"ogrenci_id": 9, "tarih": "2026-01-02", "faaliyet": "B", "adet": 1, "birim": "", "birim_puan": 50, "toplam_puan": 50}]}
    satir = satirlar(uret(tmp_path, veri)["Faaliyet Detayı"])
    assert [r[1] for r in satir] == ["Yüksek", "Düşük"] and [r[0] for r in satir] == [1, 2]


def test_arama_yalnizca_numarada_gecen_metni_de_bulur_ve_adda_gecmeyeni_eler(qt_app):
    e = ekran_ac(qt_app)
    e.arama.setText("1003")                                            # yalnızca numarada geçiyor
    assert [s for s in range(6) if not e.tablo.isRowHidden(s)] == [2]
    e.arama.setText("Cem")                                             # yalnızca adda geçiyor
    assert [s for s in range(6) if not e.tablo.isRowHidden(s)] == [2]
