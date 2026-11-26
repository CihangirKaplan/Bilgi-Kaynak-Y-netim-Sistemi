"""Gerçek PostgreSQL: randevu raporu ucu (sayılar, süzgeçler, psikolog yetkisi, detay).

CI'daki "PostgreSQL Entegrasyon Testleri" işinde (alembic upgrade head sonrası) çalışır; gerçek kayıt oluşturur, sonunda temizler.
"""
import os
from datetime import datetime, timedelta
from uuid import uuid4

import psycopg2
import pytest
from fastapi.testclient import TestClient

from server.sunucu import VT_AYARLARI, app, mevcut_kullanici_id


def _dogru_veritabani(cursor):
    assert os.getenv("TKYS_PG_TEST_ONAY") == "EVET"
    assert VT_AYARLARI["dbname"] == "crkys_alembic_test"
    cursor.execute("SELECT current_database()")
    assert cursor.fetchone()[0] == "crkys_alembic_test"


def _kullanici(cursor, ad, rol):
    cursor.execute("INSERT INTO kullanicilar (kullanici_adi, parola_hash, rol_id) VALUES (%s, 'x', (SELECT rol_id FROM roller WHERE rol_adi = %s)) RETURNING kullanici_id", (ad, rol))
    return cursor.fetchone()[0]


@pytest.fixture
def kayitlar():
    etiket = uuid4().hex[:10]
    conn = psycopg2.connect(**VT_AYARLARI)
    conn.autocommit = True
    c = conn.cursor()
    _dogru_veritabani(c)
    admin = _kullanici(c, f"ra_{etiket}", "ADMIN")
    psikologlar = []
    for ad in ("a", "b"):
        kullanici = _kullanici(c, f"rp{ad}_{etiket}", "PSIKOLOG")
        c.execute("INSERT INTO personel (kullanici_id, personel_kodu) VALUES (%s, %s) RETURNING personel_id", (kullanici, f"R-{ad}{etiket}"))
        pid = c.fetchone()[0]
        c.execute("INSERT INTO odalar (oda_adi, kapasite) VALUES (%s, 1) RETURNING oda_id", (f"r_oda_{ad}{etiket}",))
        oda = c.fetchone()[0]
        psikologlar.append((kullanici, pid, oda))
    kodlar = [f"R-{etiket}-{i}" for i in range(3)]
    for kod, yas in zip(kodlar, ("COCUK", "YETISKIN", None)):
        c.execute("INSERT INTO danisan_kodlari (danisan_kod_id, olusturan_psikolog_id, yas_grubu) VALUES (%s, %s, %s)", (kod, psikologlar[0][1], yas))
    try:
        yield c, admin, psikologlar, kodlar
    finally:
        app.dependency_overrides.pop(mevcut_kullanici_id, None)
        c.execute("DELETE FROM randevular WHERE danisan_kod_id = ANY(%s)", (kodlar,))
        c.execute("DELETE FROM denetim_kayitlari WHERE kullanici_id = ANY(%s)", ([admin] + [p[0] for p in psikologlar],))
        c.execute("DELETE FROM danisan_kodlari WHERE danisan_kod_id = ANY(%s)", (kodlar,))
        c.execute("DELETE FROM psikolog_odalar WHERE kullanici_id = ANY(%s)", ([p[0] for p in psikologlar],))
        for kullanici, pid, oda in psikologlar:
            c.execute("DELETE FROM odalar WHERE oda_id = %s", (oda,))
            c.execute("DELETE FROM personel WHERE personel_id = %s", (pid,))
        c.execute("DELETE FROM kullanicilar WHERE kullanici_id = ANY(%s)", ([admin] + [p[0] for p in psikologlar],))
        conn.close()


def _ekle(c, kod, psikolog, gun, durum, gorusme="YUZ_YUZE", terapi=None, neden=None):
    kullanici, pid, oda = psikolog
    bas = datetime(2031, 3, 3, 10, 0) + timedelta(days=gun)
    c.execute("INSERT INTO randevular (danisan_kod_id, psikolog_id, oda_id, baslangic_zamani, bitis_zamani, durum, gorusme_tipi, terapi_turu, iptal_nedeni) "
              "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)", (kod, pid, oda, bas, bas + timedelta(hours=1), durum, gorusme, terapi, neden))


def test_rapor_gercek_veritabaninda(kayitlar):
    c, admin, (psi_a, psi_b), (cocuk, yetiskin, eski) = kayitlar
    _ekle(c, cocuk, psi_a, 0, "TAMAMLANDI", terapi="OYUN_TERAPISI")
    _ekle(c, yetiskin, psi_a, 1, "TAMAMLANDI", gorusme="ONLINE", terapi="BIREYSEL_TERAPI")
    _ekle(c, yetiskin, psi_a, 2, "GELMEDI", terapi="BIREYSEL_TERAPI")
    _ekle(c, eski, psi_a, 3, "PLANLANDI")
    _ekle(c, cocuk, psi_a, 4, "IPTAL_EDILDI", neden="DANISAN_TALEBI")
    _ekle(c, cocuk, psi_b, 5, "TAMAMLANDI", terapi="BIREYSEL_TERAPI")
    istemci = TestClient(app)
    app.dependency_overrides[mevcut_kullanici_id] = lambda: admin
    dar = f"baslangic=2031-03-01&bitis=2031-03-31"

    yanit = istemci.get(f"/api/randevu-raporu?{dar}&psikolog_id={psi_a[1]}&detay=true")
    assert yanit.status_code == 200, yanit.text
    veri = yanit.json()
    assert (veri["ozet"]["toplam"], veri["ozet"]["tamamlandi"], veri["ozet"]["gelmedi"], veri["ozet"]["iptal_edildi"], veri["ozet"]["planlandi"]) == (5, 2, 1, 1, 1)
    assert veri["ozet"]["tamamlanma_orani"] == round(2 / 3, 4) and veri["ozet"]["danisan_sayisi"] == 3
    assert [p["psikolog_id"] for p in veri["psikologlar"]] == [psi_a[1]]
    assert veri["iptal_nedenleri"][0]["kod"] == "DANISAN_TALEBI" and veri["iptal_nedenleri"][0]["etiket"] == "Danışan talebi"
    gorusme = {o["kod"]: o["sayi"] for o in veri["dagilimlar"]["gorusme_tipi"]}
    assert gorusme == {"YUZ_YUZE": 3, "ONLINE": 1}                                         # iptal hariç
    assert {o["kod"] for o in veri["dagilimlar"]["yas_grubu"]} == {"COCUK", "YETISKIN", "BELIRTILMEDI"}
    assert len(veri["randevular"]) == 5 and all(r["psikolog"].startswith("rpa_") for r in veri["randevular"])

    tum = istemci.get(f"/api/randevu-raporu?{dar}").json()                                  # süzgeçsiz: iki psikolog
    assert tum["ozet"]["toplam"] == 6 and len(tum["psikologlar"]) == 2
    oda = istemci.get(f"/api/randevu-raporu?{dar}&oda_id={psi_b[2]}").json()
    assert oda["ozet"]["toplam"] == 1
    bos = istemci.get("/api/randevu-raporu?baslangic=2040-01-01&bitis=2040-01-31").json()   # randevu olmayan dönem
    assert bos["ozet"]["toplam"] == 0 and bos["ozet"]["tamamlanma_orani"] is None
    ilk_gun = istemci.get("/api/randevu-raporu?baslangic=2031-03-03&bitis=2031-03-03").json()  # bitiş günü dahil
    assert ilk_gun["ozet"]["toplam"] == 1


def test_psikolog_yalnizca_kendi_randevularini_gorur(kayitlar):
    c, admin, (psi_a, psi_b), (cocuk, yetiskin, eski) = kayitlar
    _ekle(c, cocuk, psi_a, 0, "TAMAMLANDI", terapi="OYUN_TERAPISI")
    _ekle(c, cocuk, psi_b, 1, "TAMAMLANDI", terapi="BIREYSEL_TERAPI")
    _ekle(c, cocuk, psi_b, 2, "GELMEDI", terapi="BIREYSEL_TERAPI")
    istemci = TestClient(app)
    app.dependency_overrides[mevcut_kullanici_id] = lambda: psi_b[0]
    veri = istemci.get(f"/api/randevu-raporu?baslangic=2031-03-01&bitis=2031-03-31&psikolog_id={psi_a[1]}").json()   # başkasını istese de
    assert veri["ozet"]["toplam"] == 2 and [p["psikolog_id"] for p in veri["psikologlar"]] == [psi_b[1]]


def test_secenekler_yalnizca_psikologlara_atanmis_aktif_odalari_getirir(kayitlar):
    c, admin, (psi_a, psi_b), _ = kayitlar
    etiket = uuid4().hex[:8]
    c.execute("INSERT INTO odalar (oda_adi, kapasite) VALUES (%s, 1) RETURNING oda_id", (f"r_atanmamis_{etiket}",))
    atanmamis = c.fetchone()[0]                                                              # hiçbir psikolog atanmamış oda
    c.execute("INSERT INTO odalar (oda_adi, kapasite, aktif_mi) VALUES (%s, 1, FALSE) RETURNING oda_id", (f"r_pasif_{etiket}",))
    pasif = c.fetchone()[0]                                                                  # atanmış ama pasif oda
    c.execute("INSERT INTO psikolog_odalar (kullanici_id, oda_id) VALUES (%s, %s), (%s, %s), (%s, %s)",
              (psi_a[0], psi_a[2], psi_a[0], pasif, psi_b[0], psi_b[2]))
    try:
        istemci = TestClient(app)
        app.dependency_overrides[mevcut_kullanici_id] = lambda: admin
        veri = istemci.get("/api/randevu-raporu/secenekler").json()
        odalar = {o["oda_id"] for o in veri["odalar"]}
        assert {psi_a[2], psi_b[2]} <= odalar and atanmamis not in odalar and pasif not in odalar
        assert {p["personel_id"] for p in veri["psikologlar"]} >= {psi_a[1], psi_b[1]}
        dar = istemci.get(f"/api/randevu-raporu/secenekler?psikolog_id={psi_a[1]}").json()
        assert [o["oda_id"] for o in dar["odalar"]] == [psi_a[2]]                            # seçilen psikologun odalarına daralır
        app.dependency_overrides[mevcut_kullanici_id] = lambda: psi_b[0]
        kendi = istemci.get(f"/api/randevu-raporu/secenekler?psikolog_id={psi_a[1]}").json()   # başkasını istese de
        assert [o["oda_id"] for o in kendi["odalar"]] == [psi_b[2]] and [p["personel_id"] for p in kendi["psikologlar"]] == [psi_b[1]]
    finally:
        c.execute("DELETE FROM psikolog_odalar WHERE oda_id = ANY(%s)", ([atanmamis, pasif],))
        c.execute("DELETE FROM odalar WHERE oda_id = ANY(%s)", ([atanmamis, pasif],))


def test_secenekler_pasif_psikologun_ve_odasinin_randevu_gecmisi_suzulebilir(kayitlar):
    c, admin, (psi_a, psi_b), (cocuk, yetiskin, eski) = kayitlar
    _ekle(c, cocuk, psi_b, 0, "TAMAMLANDI")                                                 # yalnızca psi_b'nin randevu geçmişi var
    c.execute("UPDATE personel SET aktif_mi = FALSE WHERE personel_id = ANY(%s)", ([psi_a[1], psi_b[1]],))
    c.execute("UPDATE odalar SET aktif_mi = FALSE WHERE oda_id = %s", (psi_b[2],))
    istemci = TestClient(app)
    app.dependency_overrides[mevcut_kullanici_id] = lambda: admin
    veri = istemci.get("/api/randevu-raporu/secenekler").json()
    psikologlar = {p["personel_id"]: p for p in veri["psikologlar"]}
    assert psikologlar[psi_b[1]]["aktif_mi"] is False and psikologlar[psi_b[1]]["ad_soyad"].endswith("(pasif)")
    assert psi_a[1] not in psikologlar                                                      # pasif ve randevusu yok: listede yok
    odalar = {o["oda_id"]: o for o in veri["odalar"]}
    assert odalar[psi_b[2]]["aktif_mi"] is False and odalar[psi_b[2]]["oda_adi"].endswith("(pasif)")
    dar = istemci.get(f"/api/randevu-raporu/secenekler?psikolog_id={psi_b[1]}").json()
    assert [o["oda_id"] for o in dar["odalar"]] == [psi_b[2]]                              # odalar seçilen psikologa daralır


def test_planli_randevusu_olan_oda_pasife_alinamaz_gercek_veritabani(kayitlar):
    c, admin, (psi_a, psi_b), (cocuk, yetiskin, eski) = kayitlar
    _ekle(c, cocuk, psi_a, 0, "PLANLANDI")                                                  # 2031: bugün ve sonrası
    istemci = TestClient(app)
    app.dependency_overrides[mevcut_kullanici_id] = lambda: admin
    yanit = istemci.patch(f"/api/odalar/{psi_a[2]}", json={"aktif_mi": False})
    assert yanit.status_code == 409 and "1 planlı randevu" in yanit.json()["detail"] and "Tamamlandı / Gelmedi" in yanit.json()["detail"]
    c.execute("SELECT aktif_mi FROM odalar WHERE oda_id = %s", (psi_a[2],))
    assert c.fetchone()[0] is True                                                          # değişmedi
    c.execute("UPDATE randevular SET durum = 'TAMAMLANDI' WHERE danisan_kod_id = %s", (cocuk,))    # sonuç girilince pasife alınabilir
    assert istemci.patch(f"/api/odalar/{psi_a[2]}", json={"aktif_mi": False}).status_code == 200


def test_bugunku_sonucsuz_randevusu_olan_danisan_pasife_alinamaz_sonuc_girilince_alinir(kayitlar):
    """Planlı randevu = durumu PLANLANDI ve günü bugün ya da sonrası: saati geçmiş ama sonucu girilmemiş bugünkü randevu da engeller."""
    c, admin, (psi_a, psi_b), (cocuk, yetiskin, eski) = kayitlar
    bugun = datetime.now().replace(hour=0, minute=5, second=0, microsecond=0)                # bugünün erken (geçmiş) saati
    c.execute("INSERT INTO randevular (danisan_kod_id, psikolog_id, oda_id, baslangic_zamani, bitis_zamani, durum) VALUES (%s, %s, %s, %s, %s, 'PLANLANDI')",
              (cocuk, psi_a[1], psi_a[2], bugun, bugun + timedelta(minutes=30)))
    istemci = TestClient(app)
    app.dependency_overrides[mevcut_kullanici_id] = lambda: admin
    yanit = istemci.patch(f"/api/danisan-kodlari/{cocuk}/durum", params={"aktif_mi": "false"})
    assert yanit.status_code == 409 and "Tamamlandı / Gelmedi" in yanit.json()["detail"]
    c.execute("UPDATE randevular SET durum = 'TAMAMLANDI' WHERE danisan_kod_id = %s", (cocuk,))
    assert istemci.patch(f"/api/danisan-kodlari/{cocuk}/durum", params={"aktif_mi": "false"}).status_code == 200


def test_ozet_rapor_sql_gruplamasi_satir_satir_hesapla_ayni_sonucu_verir(kayitlar):
    """Özet rapor (detay=false) SQL'de gruplanır, detay=true ise satır satır hesaplanır: ikisi gerçek veritabanında birebir aynı olmalı."""
    c, admin, (psi_a, psi_b), (cocuk, yetiskin, eski) = kayitlar
    _ekle(c, cocuk, psi_a, 0, "TAMAMLANDI", terapi="OYUN_TERAPISI")
    _ekle(c, yetiskin, psi_a, 1, "TAMAMLANDI", gorusme="ONLINE", terapi="BIREYSEL_TERAPI")
    _ekle(c, yetiskin, psi_a, 2, "GELMEDI", terapi="BIREYSEL_TERAPI")
    _ekle(c, eski, psi_a, 3, "PLANLANDI")
    _ekle(c, cocuk, psi_a, 4, "IPTAL_EDILDI", neden="DANISAN_TALEBI")
    _ekle(c, cocuk, psi_a, 5, "IPTAL_EDILDI")                                              # nedeni kaydedilmemiş iptal
    _ekle(c, cocuk, psi_b, 6, "TAMAMLANDI", terapi="BIREYSEL_TERAPI")
    istemci = TestClient(app)
    app.dependency_overrides[mevcut_kullanici_id] = lambda: admin
    for sorgu in ("baslangic=2031-03-01&bitis=2031-03-31", f"baslangic=2031-03-01&bitis=2031-03-31&psikolog_id={psi_a[1]}", f"baslangic=2031-03-01&bitis=2031-03-31&oda_id={psi_b[2]}"):
        ozet = istemci.get(f"/api/randevu-raporu?{sorgu}").json()
        detayli = istemci.get(f"/api/randevu-raporu?{sorgu}&detay=true").json()
        detayli.pop("randevular")
        assert ozet == detayli, sorgu
    # 2031 geleceğe düşer: "sonucu girilmemiş geçmiş" 0; geçmiş tarihli planlı randevu için de aynı sonuç (gruplama 'gecmis' bayrağı)
    _ekle(c, eski, psi_a, -4000, "PLANLANDI")                                              # ~2020: geçmişte hâlâ planlı
    a = istemci.get("/api/randevu-raporu?baslangic=2010-01-01&bitis=2031-12-31").json()
    b = istemci.get("/api/randevu-raporu?baslangic=2010-01-01&bitis=2031-12-31&detay=true").json()
    b.pop("randevular")
    assert a == b and a["ozet"]["sonucsuz_gecmis"] >= 1
