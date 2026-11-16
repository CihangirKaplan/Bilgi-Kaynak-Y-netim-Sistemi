"""Gerçek PostgreSQL: geçici parola süresi ve yönetici parolası koruması (uçtan uca).

CI'daki "PostgreSQL Entegrasyon Testleri" işinde (alembic upgrade head sonrası) çalışır; gerçek kayıt oluşturur, sonunda temizler.
"""
import os
from uuid import uuid4

import psycopg2
import pytest
from fastapi.testclient import TestClient

from server.guvenlik import parola_hashle
from server.sunucu import VT_AYARLARI, app


def test_gecici_parola_suresi_ve_yonetici_korumasi_gercek_veritabaninda():
    assert os.getenv("TKYS_PG_TEST_ONAY") == "EVET"
    assert VT_AYARLARI["dbname"] == "crkys_alembic_test"
    kod = uuid4().hex[:10]
    parola = f"Test!{kod}Aa"
    conn = psycopg2.connect(**VT_AYARLARI)
    conn.autocommit = True
    c = conn.cursor()
    idler = []
    try:
        c.execute("SELECT current_database()")
        assert c.fetchone()[0] == "crkys_alembic_test"
        c.execute("SELECT 1 FROM information_schema.columns WHERE table_name = 'kullanicilar' AND column_name = 'gecici_parola_bitis'")
        assert c.fetchone() is not None
        c.execute("SELECT rol_adi, rol_id FROM roller WHERE rol_adi IN ('ADMIN', 'MEMUR')")
        roller = dict(c.fetchall())

        hesaplar = {}
        for ad, rol in (("yonetici", "ADMIN"), ("yonetici2", "ADMIN"), ("memur", "MEMUR")):
            c.execute(
                "INSERT INTO kullanicilar (kullanici_adi, parola_hash, rol_id, aktif_mi, ilk_giris_mi) VALUES (%s, %s, %s, TRUE, FALSE) RETURNING kullanici_id",
                (f"gp_{ad}_{kod}", parola_hashle(parola), roller[rol]),
            )
            kid = c.fetchone()[0]
            idler.append(kid)
            c.execute("INSERT INTO personel (kullanici_id, personel_kodu, aktif_mi) VALUES (%s, %s, TRUE)", (kid, f"GP{kod}{ad[:3]}{ad[-1]}"))
            hesaplar[ad] = {"id": kid, "ad": f"gp_{ad}_{kod}"}

        istemci = TestClient(app)

        def giris(hesap, p):
            return istemci.post("/api/login", json={"kullanici_adi": hesap["ad"], "parola": p})

        yonetici_token = giris(hesaplar["yonetici"], parola).json()["access_token"]
        baslik = {"Authorization": f"Bearer {yonetici_token}"}

        # 1) Yönetici başka yöneticinin parolasını sıfırlayamaz; hiçbir şey değişmez.
        engel = istemci.post(f"/api/kullanicilar/{hesaplar['yonetici2']['id']}/parola-sifirla", headers=baslik)
        assert engel.status_code == 403 and "kurtarma aracı" in engel.json()["detail"]
        c.execute("SELECT ilk_giris_mi, gecici_parola_bitis FROM kullanicilar WHERE kullanici_id = %s", (hesaplar["yonetici2"]["id"],))
        assert c.fetchone() == (False, None)

        # 2) Yönetici dışındaki hesap sıfırlanır; geçerlilik süresi yazılır (≈ şimdi + süre).
        sifirlama = istemci.post(f"/api/kullanicilar/{hesaplar['memur']['id']}/parola-sifirla", headers=baslik)
        assert sifirlama.status_code == 200, sifirlama.text
        gecici = sifirlama.json()["gecici_parola"]
        saat = sifirlama.json()["gecici_parola_gecerlilik_saat"]
        c.execute("SELECT gecici_parola_bitis - CURRENT_TIMESTAMP > (%s - 1) * INTERVAL '1 hour' FROM kullanicilar WHERE kullanici_id = %s",
                  (saat, hesaplar["memur"]["id"]))
        assert c.fetchone()[0] is True

        # 3) Süre içinde giriş olur; süre dolunca (geçici parola doğru olsa da) 403.
        assert giris(hesaplar["memur"], gecici).status_code == 200
        c.execute("UPDATE kullanicilar SET gecici_parola_bitis = CURRENT_TIMESTAMP - INTERVAL '1 minute' WHERE kullanici_id = %s", (hesaplar["memur"]["id"],))
        dolmus = giris(hesaplar["memur"], gecici)
        assert dolmus.status_code == 403 and "süresi doldu" in dolmus.json()["detail"]
        assert giris(hesaplar["memur"], "Yanlis-Parola-1").status_code == 401                  # yanlış parolada süre bilgisi verilmez

        # 4) Yeniden sıfırlama süreyi yeniler; parola değiştirilince süre bilgisi temizlenir.
        yeni = istemci.post(f"/api/kullanicilar/{hesaplar['memur']['id']}/parola-sifirla", headers=baslik).json()["gecici_parola"]
        gecici_giris = giris(hesaplar["memur"], yeni)
        assert gecici_giris.status_code == 200 and gecici_giris.json()["sifre_degistirme_gerekli"] is True
        kalici = f"Yeni!{kod}Bb"
        degistirme = istemci.post(
            "/api/sifre-degistir", headers={"Authorization": f"Bearer {gecici_giris.json()['access_token']}"},
            json={"eski_parola": yeni, "yeni_parola": kalici, "yeni_parola_tekrar": kalici},
        )
        assert degistirme.status_code == 200, degistirme.text
        c.execute("SELECT ilk_giris_mi, gecici_parola_bitis FROM kullanicilar WHERE kullanici_id = %s", (hesaplar["memur"]["id"],))
        assert c.fetchone() == (False, None)

        # 5) Yönetici hesabı için talep açılamaz; yönetici talepleri listede görünmez. Diğer hesaplar için talep açılır.
        yonetici_talebi = istemci.post("/api/parola-sifirlama-talebi", json={"kullanici_adi": hesaplar["yonetici2"]["ad"]})
        assert yonetici_talebi.status_code == 403 and yonetici_talebi.json()["detail"]["kod"] == "HESAP_YONETICI"
        c.execute("SELECT COUNT(*) FROM parola_sifirlama_talepleri WHERE kullanici_id = %s", (hesaplar["yonetici2"]["id"],))
        assert c.fetchone()[0] == 0
        c.execute("INSERT INTO parola_sifirlama_talepleri (kullanici_id) VALUES (%s)", (hesaplar["yonetici2"]["id"],))   # eski kayıt (araç öncesi)
        memur_talebi = istemci.post("/api/parola-sifirlama-talebi", json={"kullanici_adi": hesaplar["memur"]["ad"]})
        assert memur_talebi.status_code == 200
        kullanicilar = {t["kullanici_id"] for t in istemci.get("/api/parola-sifirlama-talepleri", headers=baslik).json()}
        assert hesaplar["memur"]["id"] in kullanicilar and hesaplar["yonetici2"]["id"] not in kullanicilar
    finally:
        c.execute("DELETE FROM parola_sifirlama_talepleri WHERE kullanici_id = ANY(%s)", (idler,))
        c.execute("DELETE FROM denetim_kayitlari WHERE kullanici_id = ANY(%s) OR hedef_kayit_id = ANY(%s)", (idler, idler))
        c.execute("DELETE FROM personel WHERE kullanici_id = ANY(%s)", (idler,))
        c.execute("DELETE FROM kullanicilar WHERE kullanici_id = ANY(%s)", (idler,))
        conn.close()
