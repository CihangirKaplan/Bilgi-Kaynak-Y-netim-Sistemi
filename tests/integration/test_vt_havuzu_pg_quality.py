"""Gerçek PostgreSQL: bağlantı havuzu (server/vt_baglanti.py) — yeniden kullanım, temizlik, istemci adresi, ölü bağlantı, eşzamanlılık."""
import os
import threading
import time

import psycopg2
import psycopg2.extensions
import pytest
from fastapi.testclient import TestClient

from server import giris_siniri, vt_baglanti
from server.sunucu import VT_AYARLARI, app

BOYUT = 5


@pytest.fixture
def havuz(monkeypatch):
    assert os.getenv("TKYS_PG_TEST_ONAY") == "EVET"
    assert VT_AYARLARI["dbname"] == "crkys_alembic_test"
    monkeypatch.setenv("TKYS_DB_HAVUZ_BOYUTU", str(BOYUT))
    vt_baglanti.havuzlari_bosalt()
    yield vt_baglanti._havuz_al(VT_AYARLARI, BOYUT)
    vt_baglanti.havuzlari_bosalt()


def _pid(conn):
    return conn.get_backend_pid()


def _ayar(conn):
    with conn.cursor() as c:
        c.execute("SELECT current_setting('tkys.istemci_adresi', true)")
        deger = c.fetchone()[0]
    conn.rollback()
    return deger


def test_kapatilan_baglanti_havuza_doner_ve_yeniden_kullanilir(havuz):
    a = vt_baglanti.vt_baglan(VT_AYARLARI)
    pid = _pid(a)
    a.close()
    assert not a.closed and len(havuz.bosta) == 1             # gerçekten kapanmadı, boşta bekliyor
    b = vt_baglanti.vt_baglan(VT_AYARLARI)
    assert _pid(b) == pid and len(havuz.bosta) == 0           # aynı veritabanı bağlantısı yeniden kullanıldı
    b.close()


def test_cift_kapatma_baglantiyi_havuza_iki_kez_koymaz(havuz):
    a = vt_baglanti.vt_baglan(VT_AYARLARI)
    a.close()
    a.close()
    assert len(havuz.bosta) == 1


def test_acik_islem_geri_alinir_ve_durum_bir_sonraki_istege_sizmaz(havuz):
    a = vt_baglanti.vt_baglan(VT_AYARLARI)
    pid = _pid(a)
    c = a.cursor()
    c.execute("CREATE TEMP TABLE sizinti_denemesi (x int)")        # bu işlem hiç commit edilmez
    c.execute("INSERT INTO sizinti_denemesi VALUES (1)")
    a.close()
    b = vt_baglanti.vt_baglan(VT_AYARLARI)
    assert _pid(b) == pid
    assert b.get_transaction_status() == psycopg2.extensions.TRANSACTION_STATUS_IDLE
    with b.cursor() as c2:
        c2.execute("SELECT to_regclass('pg_temp.sizinti_denemesi')")
        assert c2.fetchone()[0] is None                            # geri alındı: önceki isteğin yarım işi görünmez
    b.close()


def test_bozuk_islem_durumundaki_baglanti_temizlenir(havuz):
    a = vt_baglanti.vt_baglan(VT_AYARLARI)
    c = a.cursor()
    with pytest.raises(psycopg2.Error):
        c.execute("SELECT 1/0")                                    # işlem "aborted" durumuna girer
    assert a.get_transaction_status() == psycopg2.extensions.TRANSACTION_STATUS_INERROR
    a.close()
    b = vt_baglanti.vt_baglan(VT_AYARLARI)
    with b.cursor() as c2:
        c2.execute("SELECT 1")
        assert c2.fetchone()[0] == 1
    b.close()


def test_autocommit_havuza_donerken_sifirlanir(havuz):
    a = vt_baglanti.vt_baglan(VT_AYARLARI)
    a.autocommit = True
    a.close()
    b = vt_baglanti.vt_baglan(VT_AYARLARI)
    assert b.autocommit is False
    b.close()


def test_istemci_adresi_her_kullanimda_dogru_ayarlanir_ve_geri_almaya_dayanir(havuz):
    belirtec = vt_baglanti.adresi_ayarla("203.0.113.7")
    try:
        a = vt_baglanti.vt_baglan(VT_AYARLARI)
        pid = _pid(a)
        assert _ayar(a) == "203.0.113.7"
        a.close()
        vt_baglanti.adresi_sifirla(belirtec)

        belirtec = vt_baglanti.adresi_ayarla("198.51.100.4")      # aynı bağlantı, başka istemci
        b = vt_baglanti.vt_baglan(VT_AYARLARI)
        assert _pid(b) == pid and _ayar(b) == "198.51.100.4"
        b.rollback()
        assert _ayar(b) == "198.51.100.4"                          # ayar işlem geri almasıyla kaybolmaz
        b.close()
        vt_baglanti.adresi_sifirla(belirtec)

        belirtec = vt_baglanti.adresi_ayarla(None)                 # adressiz istek önceki adresi taşımaz
        c = vt_baglanti.vt_baglan(VT_AYARLARI)
        assert _pid(c) == pid and not _ayar(c)
        c.close()
    finally:
        vt_baglanti.adresi_sifirla(belirtec)


def test_denetim_kaydi_havuzlu_baglantida_dogru_istemci_adresini_yazar(havuz):
    """Aynı havuzlu bağlantılar üzerinden art arda gelen farklı istemcilerin denetim kayıtları kendi adreslerini taşır."""
    from uuid import uuid4

    from server.guvenlik import parola_hashle
    from server.personel_kaydi import personel_kaydi_ata

    temiz = psycopg2.connect(**VT_AYARLARI)
    temiz.autocommit = True
    t = temiz.cursor()
    ad = f"hv_{uuid4().hex[:8]}"
    t.execute("INSERT INTO kullanicilar (kullanici_adi, parola_hash, rol_id, ilk_giris_mi) VALUES (%s, %s, "
              "(SELECT rol_id FROM roller WHERE rol_adi = 'ADMIN'), FALSE) RETURNING kullanici_id", (ad, parola_hashle("Guzel-Parola-2026")))
    kimlik = t.fetchone()[0]
    personel_kaydi_ata(t, kimlik, f"HV-{uuid4().hex[:6]}")
    try:
        for adres in ("203.0.113.21", "203.0.113.22", "203.0.113.21"):
            yanit = TestClient(app, client=(adres, 1)).post("/api/login", json={"kullanici_adi": ad, "parola": "Guzel-Parola-2026"})
            assert yanit.status_code == 200, yanit.text
            TestClient(app, client=(adres, 1)).get("/api/audit-kayitlari",
                                                   headers={"Authorization": f"Bearer {yanit.json()['access_token']}"})
        t.execute("SELECT olay_turu::text, istemci_adresi FROM denetim_kayitlari WHERE kullanici_id = %s ORDER BY denetim_id", (kimlik,))
        satirlar = t.fetchall()
        giris_adresleri = [a for o, a in satirlar if o == "LOGIN"]
        assert giris_adresleri == ["203.0.113.21", "203.0.113.22", "203.0.113.21"]
        assert all(a is not None for _, a in satirlar)             # hiçbir kayıt adressiz kalmadı
        assert len(havuz.bosta) >= 1                               # istekler havuzlu bağlantı kullandı
    finally:
        t.execute("DELETE FROM denetim_kayitlari WHERE kullanici_id = %s OR (hedef_tablo = 'kullanicilar' AND hedef_kayit_id = %s)",
                  (kimlik, kimlik))
        t.execute("DELETE FROM kullanicilar WHERE kullanici_id = %s", (kimlik,))
        t.execute("DELETE FROM giris_istek_limitleri WHERE pencere_baslangici > NOW() - INTERVAL '5 minutes'")
        temiz.close()


def test_olmus_baglanti_yoklamada_atilir_ve_yenisi_acilir(havuz, monkeypatch):
    monkeypatch.setattr(vt_baglanti, "YOKLAMA_ESIGI_SN", 0.0)     # her kullanımda yokla
    a = vt_baglanti.vt_baglan(VT_AYARLARI)
    pid = _pid(a)
    a.close()
    yonetim = psycopg2.connect(**VT_AYARLARI)
    yonetim.autocommit = True
    with yonetim.cursor() as c:
        c.execute("SELECT pg_terminate_backend(%s)", (pid,))        # sunucu bağlantıyı öldürdü (yeniden başlatma, ağ kopması...)
    yonetim.close()
    time.sleep(0.3)
    b = vt_baglanti.vt_baglan(VT_AYARLARI)
    assert _pid(b) != pid
    with b.cursor() as c2:
        c2.execute("SELECT 1")
        assert c2.fetchone()[0] == 1
    b.close()


def test_cok_eski_baglanti_yenilenir(havuz, monkeypatch):
    a = vt_baglanti.vt_baglan(VT_AYARLARI)
    pid = _pid(a)
    a.close()
    monkeypatch.setattr(vt_baglanti, "BAGLANTI_OMRU_SN", 0.0)
    b = vt_baglanti.vt_baglan(VT_AYARLARI)
    assert _pid(b) != pid
    b.close()


def test_havuz_eszamanli_baglanti_sayisini_sinirlamaz_fazlasi_donuste_kapanir(havuz):
    eszamanli = BOYUT * 3
    hepsi_acik = threading.Barrier(eszamanli)
    hatalar, baglantilar = [], []

    def isle():
        try:
            c = vt_baglanti.vt_baglan(VT_AYARLARI)
            with c.cursor() as i:
                i.execute("SELECT 1")
            baglantilar.append(c)
            hepsi_acik.wait(timeout=20)                            # hepsi aynı anda açık
        except Exception as hata:                                  # pragma: no cover - hata ayıklama için
            hatalar.append(hata)

    iplikler = [threading.Thread(target=isle) for _ in range(eszamanli)]
    for i in iplikler:
        i.start()
    for i in iplikler:
        i.join(30)
    assert hatalar == [] and len(baglantilar) == eszamanli
    for c in baglantilar:
        c.close()
    assert len(havuz.bosta) == BOYUT                               # fazlası gerçekten kapandı
    assert sum(1 for c in baglantilar if c.closed) == eszamanli - BOYUT


def test_cok_iplikli_yogun_kullanim_baglantilari_karistirmaz(havuz):
    hatalar = []

    def isle(sayi):
        try:
            for _ in range(30):
                c = vt_baglanti.vt_baglan(VT_AYARLARI)
                with c.cursor() as i:
                    i.execute("SELECT %s", (sayi,))
                    assert i.fetchone()[0] == sayi
                c.commit()
                c.close()
        except Exception as hata:
            hatalar.append(hata)

    iplikler = [threading.Thread(target=isle, args=(n,)) for n in range(12)]
    for i in iplikler:
        i.start()
    for i in iplikler:
        i.join(60)
    assert hatalar == []
    assert len(havuz.bosta) <= BOYUT
    assert len({id(c) for c, _ in havuz.bosta}) == len(havuz.bosta)    # aynı bağlantı havuzda iki kez yok


def test_havuz_kapaliyken_baglanti_eskisi_gibi_gercekten_kapanir(monkeypatch):
    monkeypatch.setenv("TKYS_DB_HAVUZ_BOYUTU", "0")
    c = vt_baglanti.vt_baglan(VT_AYARLARI)
    assert not isinstance(c, vt_baglanti.HavuzluBaglanti)
    c.close()
    assert c.closed


def test_giris_sinirlayici_havuzlu_baglanti_kullanir(havuz):
    anahtar = "hv_" + os.urandom(8).hex()
    assert giris_siniri.engel_suresi(VT_AYARLARI, anahtar) == 0
    giris_siniri.basarisiz_girisi_kaydet(VT_AYARLARI, anahtar)
    assert len(havuz.bosta) >= 1                                   # bağlantılar kapatılmadı, havuza döndü
    temiz = psycopg2.connect(**VT_AYARLARI)
    temiz.autocommit = True
    with temiz.cursor() as c:
        c.execute("DELETE FROM giris_istek_limitleri WHERE anahtar = %s", (anahtar,))
    temiz.close()
