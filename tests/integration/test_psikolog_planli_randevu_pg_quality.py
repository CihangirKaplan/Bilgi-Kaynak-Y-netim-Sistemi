"""Gerçek PostgreSQL: planlı randevusu olan psikologun odası boşalacak işlemler engellenir.

- Rol değiştirme (psikologluktan çıkma): bugünden sonra planlı randevu varsa 409; iptal edilince / yalnızca geçmiş kayıt varsa geçer
- Oda yetkisi güncelleme: planlı randevusu olan oda kaldırılamaz (409); kalan odalar ya da randevusuz odalar için engel yok

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
def ortam():
    etiket = uuid4().hex[:10]
    conn = psycopg2.connect(**VT_AYARLARI)
    conn.autocommit = True
    c = conn.cursor()
    _dogru_veritabani(c)
    admin = _kullanici(c, f"pa_{etiket}", "ADMIN")
    psikolog = _kullanici(c, f"pp_{etiket}", "PSIKOLOG")
    c.execute("INSERT INTO personel (kullanici_id, personel_kodu) VALUES (%s, %s) RETURNING personel_id", (psikolog, f"PL-{etiket}"))
    personel = c.fetchone()[0]
    odalar = []
    for ad in ("a", "b"):
        c.execute("INSERT INTO odalar (oda_adi, kapasite) VALUES (%s, 1) RETURNING oda_id", (f"pl_oda_{ad}_{etiket}",))
        odalar.append(c.fetchone()[0])
        c.execute("INSERT INTO psikolog_odalar (kullanici_id, oda_id) VALUES (%s, %s)", (psikolog, odalar[-1]))
    kod = f"PL-{etiket}-1"
    c.execute("INSERT INTO danisan_kodlari (danisan_kod_id, olusturan_psikolog_id) VALUES (%s, %s)", (kod, personel))
    try:
        yield c, admin, psikolog, personel, odalar, kod, etiket
    finally:
        app.dependency_overrides.pop(mevcut_kullanici_id, None)
        c.execute("DELETE FROM randevular WHERE danisan_kod_id = %s", (kod,))
        c.execute("DELETE FROM danisan_kodlari WHERE danisan_kod_id = %s", (kod,))
        c.execute("DELETE FROM psikolog_odalar WHERE kullanici_id = %s", (psikolog,))
        c.execute("DELETE FROM denetim_kayitlari WHERE kullanici_id = ANY(%s)", ([admin, psikolog],))
        c.execute("DELETE FROM odalar WHERE oda_id = ANY(%s)", (odalar,))
        c.execute("DELETE FROM personel WHERE personel_id = %s", (personel,))
        c.execute("DELETE FROM kullanicilar WHERE kullanici_id = ANY(%s)", ([admin, psikolog],))
        conn.close()


def _randevu(c, kod, personel, oda, baslangic, durum="PLANLANDI"):
    c.execute("INSERT INTO randevular (danisan_kod_id, psikolog_id, oda_id, baslangic_zamani, bitis_zamani, durum, gorusme_tipi, terapi_turu) "
              "VALUES (%s, %s, %s, %s, %s, %s, 'YUZ_YUZE', 'BIREYSEL_TERAPI') RETURNING randevu_id",
              (kod, personel, oda, baslangic, baslangic + timedelta(hours=1), durum))
    return c.fetchone()[0]


def _atanmis(c, psikolog):
    c.execute("SELECT oda_id FROM psikolog_odalar WHERE kullanici_id = %s ORDER BY oda_id", (psikolog,))
    return [k[0] for k in c.fetchall()]


def test_planli_randevusu_olan_odayi_kaldirma_ve_rol_degistirme_engellenir_gercek_veritabaninda(ortam):
    c, admin, psikolog, personel, (oda_a, oda_b), kod, etiket = ortam
    istemci = TestClient(app)
    app.dependency_overrides[mevcut_kullanici_id] = lambda: admin
    odalar_guncelle = lambda *idler: istemci.put(f"/api/kullanicilar/{psikolog}/odalar", json={"oda_idleri": list(idler)})
    c.execute("SELECT rol_id FROM roller WHERE rol_adi = 'MEMUR'")
    memur = c.fetchone()[0]
    rol_degistir = lambda: istemci.patch(f"/api/kullanicilar/{psikolog}/rol", json={"rol_id": memur})
    gelecek = datetime.now() + timedelta(days=3)

    planli = _randevu(c, kod, personel, oda_a, gelecek)                                     # oda_a'da bugünden sonra planlı randevu
    yanit = odalar_guncelle(oda_b)                                                          # oda_a kaldırılmak isteniyor
    assert yanit.status_code == 409
    assert f"pl_oda_a_{etiket} (1 randevu)" in yanit.json()["detail"] and "iptal edin" in yanit.json()["detail"]
    assert _atanmis(c, psikolog) == [oda_a, oda_b]                                          # atama değişmedi
    assert odalar_guncelle(oda_a, oda_b).status_code == 200                                 # hiçbir şey kaldırılmıyor: engel yok
    assert odalar_guncelle(oda_a).status_code == 200 and _atanmis(c, psikolog) == [oda_a]   # randevusuz oda_b kaldırılabilir

    yanit = rol_degistir()                                                                  # psikologluktan çıkmak: odaları kalkacak
    assert yanit.status_code == 409 and "1 planlı randevusu var" in yanit.json()["detail"]
    c.execute("SELECT r.rol_adi FROM kullanicilar k JOIN roller r ON r.rol_id = k.rol_id WHERE k.kullanici_id = %s", (psikolog,))
    assert c.fetchone()[0] == "PSIKOLOG" and _atanmis(c, psikolog) == [oda_a]               # rol ve odalar değişmedi

    c.execute("UPDATE randevular SET durum = 'IPTAL_EDILDI' WHERE randevu_id = %s", (planli,))
    eski_planli = _randevu(c, kod, personel, oda_a, datetime.now() - timedelta(days=5))     # geçmişte kalan "Planlandı" engel olmaz
    assert odalar_guncelle(oda_b).status_code == 200 and _atanmis(c, psikolog) == [oda_b]   # iptal sonrası oda_a kaldırılabilir
    assert rol_degistir().status_code == 200
    c.execute("SELECT r.rol_adi FROM kullanicilar k JOIN roller r ON r.rol_id = k.rol_id WHERE k.kullanici_id = %s", (psikolog,))
    assert c.fetchone()[0] == "MEMUR" and _atanmis(c, psikolog) == []                       # rol değişti, odalar kalktı
    c.execute("SELECT randevu_id, oda_id FROM randevular WHERE danisan_kod_id = %s ORDER BY randevu_id", (kod,))
    assert c.fetchall() == [(planli, oda_a), (eski_planli, oda_a)]                          # randevular ve oda bilgileri aynen


def test_gelecek_etkinligi_olan_oda_psikologa_atanamaz(ortam):
    """Gelecek etkinliği olan oda 409; iptalden sonra atama serbest."""
    c, admin, psikolog, personel, odalar, kod, etiket = ortam

    # Testin var olan oda/psikolog kayıtlarını kullan, yeni oda aç.
    c.execute(
        "INSERT INTO odalar (oda_adi, kapasite) "
        "VALUES (%s, 10) RETURNING oda_id",
        (f"etkinlik_atama_{etiket}",),
    )
    yeni_oda = c.fetchone()[0]
    odalar.append(yeni_oda)  # Mevcut fixture bu odayı da temizleyecek.

    etkinlik_id = None
    try:
        bas = (
            datetime.now() + timedelta(days=10)
        ).replace(hour=10, minute=0, second=0, microsecond=0)
        bit = bas + timedelta(hours=1)

        c.execute(
            """
            INSERT INTO oda_etkinlikleri
                (oda_id, organize_eden_personel_id,
                 etkinlik_adi, katilimci_sayisi,
                 baslangic_zamani, bitis_zamani)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING etkinlik_id
            """,
            (
                yeni_oda, personel,
                f"Atama testi {etiket}", 1, bas, bit,
            ),
        )
        etkinlik_id = c.fetchone()[0]

        c.execute(
            """
            INSERT INTO oda_etkinlik_gunleri
                (etkinlik_id, baslangic_zamani, bitis_zamani)
            VALUES (%s, %s, %s)
            """,
            (etkinlik_id, bas, bit),
        )

        app.dependency_overrides[mevcut_kullanici_id] = lambda: admin

        def atanmis_odalar():
            c.execute(
                "SELECT oda_id FROM psikolog_odalar "
                "WHERE kullanici_id = %s ORDER BY oda_id",
                (psikolog,),
            )
            return [satir[0] for satir in c.fetchall()]

        ilk = atanmis_odalar()
        istenen = sorted(set(ilk + [yeni_oda]))

        with TestClient(app) as istemci:
            url = f"/api/kullanicilar/{psikolog}/odalar"

            yanit = istemci.put(
                url, json={"oda_idleri": istenen}
            )
            assert yanit.status_code == 409, yanit.text
            assert "etkinli" in yanit.json()["detail"].lower()
            assert atanmis_odalar() == ilk
            print("PASS | Etkinlikli oda atanamadı: 409")
            print("PASS | Eski oda atamaları korundu")

            c.execute(
                "UPDATE oda_etkinlikleri "
                "SET iptal_edildi_mi = TRUE "
                "WHERE etkinlik_id = %s",
                (etkinlik_id,),
            )

            yanit = istemci.put(
                url, json={"oda_idleri": istenen}
            )
            assert yanit.status_code == 200, yanit.text
            assert atanmis_odalar() == istenen
            print("PASS | Etkinlik iptal edilince atama: 200")

            yanit = istemci.put(
                url, json={"oda_idleri": ilk}
            )
            assert yanit.status_code == 200, yanit.text
            assert atanmis_odalar() == ilk
            print("PASS | Geçici oda ataması geri alındı")

    finally:
        # Önce testin oluşturduğu etkinlik, ardından fixture odaları temizler.
        if etkinlik_id is not None:
            c.execute(
                "DELETE FROM denetim_kayitlari "
                "WHERE hedef_tablo = 'oda_etkinlikleri' "
                "AND hedef_kayit_id = %s",
                (etkinlik_id,),
            )
            c.execute(
                "DELETE FROM oda_etkinlik_gunleri "
                "WHERE etkinlik_id = %s",
                (etkinlik_id,),
            )
            c.execute(
                "DELETE FROM oda_etkinlikleri "
                "WHERE etkinlik_id = %s",
                (etkinlik_id,),
            )


def test_es_zamanli_etkinlik_ve_psikolog_oda_atamasi(ortam):
    """Aynı odada eşzamanlı POST ve PUT birlikte başarılı olamaz."""
    import time
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    c, admin, psikolog, personel, odalar, kod, etiket = ortam
    _dogru_veritabani(c)

    c.execute(
        "INSERT INTO odalar (oda_adi, kapasite) "
        "VALUES (%s, 10) RETURNING oda_id",
        (f"es_zamanli_oda_{etiket}",),
    )
    yeni_oda = c.fetchone()[0]
    odalar.append(yeni_oda)

    c.execute(
        "SELECT oda_id FROM psikolog_odalar "
        "WHERE kullanici_id = %s ORDER BY oda_id",
        (psikolog,),
    )
    eski_odalar = [r[0] for r in c.fetchall()]
    istenen_odalar = sorted(set(eski_odalar + [yeni_oda]))

    bas = (
        datetime.now() + timedelta(days=10)
    ).replace(hour=10, minute=0, second=0, microsecond=0)
    bit = bas + timedelta(hours=1)

    payload = {
        "oda_id": yeni_oda,
        "organize_eden_personel_id": personel,
        "etkinlik_adi": f"Es zamanli test {etiket}",
        "katilimci_sayisi": 1,
        "gunler": [{
            "baslangic_zamani": bas.isoformat(),
            "bitis_zamani": bit.isoformat(),
        }],
    }

    app.dependency_overrides[mevcut_kullanici_id] = lambda: admin

    # İlk bağlantı aynı oda kilidini geçici olarak tutar.
    # İki API isteği de aynı kilit için yarışacaktır.
    kilit_conn = psycopg2.connect(**VT_AYARLARI)
    etkinlik_id = None

    try:
        with kilit_conn.cursor() as kc:
            kc.execute("SELECT current_database()")
            assert kc.fetchone()[0] == "crkys_alembic_test"

            kc.execute(
                "SELECT pg_advisory_xact_lock(%s, %s)",
                (391284, yeni_oda),
            )

        baslama = Barrier(3)

        def etkinlik_olustur():
            with TestClient(app) as istemci:
                baslama.wait(timeout=10)
                return istemci.post(
                    "/api/oda-etkinlikleri",
                    json=payload,
                )

        def psikologa_oda_ata():
            with TestClient(app) as istemci:
                baslama.wait(timeout=10)
                return istemci.put(
                    f"/api/kullanicilar/{psikolog}/odalar",
                    json={"oda_idleri": istenen_odalar},
                )

        try:
            with ThreadPoolExecutor(max_workers=2) as havuz:
                gelecek_etkinlik = havuz.submit(etkinlik_olustur)
                gelecek_atama = havuz.submit(psikologa_oda_ata)

                baslama.wait(timeout=10)
                time.sleep(0.3)

                # Kilidi serbest bırak: iki gerçek API isteği yarışsın.
                kilit_conn.rollback()

                etkinlik_yanit = gelecek_etkinlik.result(timeout=20)
                atama_yanit = gelecek_atama.result(timeout=20)
        finally:
            kilit_conn.rollback()

        print("Etkinlik POST:", etkinlik_yanit.status_code)
        print("Psikolog PUT:", atama_yanit.status_code)

        if etkinlik_yanit.status_code == 201:
            etkinlik_id = etkinlik_yanit.json()["etkinlik_id"]

        assert sorted([
            etkinlik_yanit.status_code,
            atama_yanit.status_code,
        ]) in ([200, 409], [201, 409]), (
            etkinlik_yanit.text,
            atama_yanit.text,
        )

        c.execute(
            "SELECT COUNT(*) FROM psikolog_odalar "
            "WHERE kullanici_id = %s AND oda_id = %s",
            (psikolog, yeni_oda),
        )
        atama_var = c.fetchone()[0] == 1

        c.execute(
            "SELECT COUNT(*) FROM oda_etkinlikleri "
            "WHERE oda_id = %s "
            "AND COALESCE(iptal_edildi_mi, FALSE) = FALSE",
            (yeni_oda,),
        )
        etkinlik_var = c.fetchone()[0] > 0

        assert atama_var != etkinlik_var, (
            "Oda ataması ve etkinlik birlikte oluştu "
            "veya ikisi de oluşmadı."
        )

        print("PASS | İşlemlerden yalnızca biri başarılı.")
        print("PASS | Oda ataması ve etkinlik çakışmadı.")
        print("PASS | Beklenmeyen HTTP 500 oluşmadı.")

    finally:
        kilit_conn.rollback()
        kilit_conn.close()

        # Teste ait olası kayıtları temizle.
        c.execute(
            "DELETE FROM psikolog_odalar "
            "WHERE kullanici_id = %s AND oda_id = %s",
            (psikolog, yeni_oda),
        )

        c.execute(
            "SELECT etkinlik_id FROM oda_etkinlikleri "
            "WHERE oda_id = %s",
            (yeni_oda,),
        )
        test_etkinlikleri = [r[0] for r in c.fetchall()]

        for eid in test_etkinlikleri:
            c.execute(
                "DELETE FROM denetim_kayitlari "
                "WHERE hedef_tablo = 'oda_etkinlikleri' "
                "AND hedef_kayit_id = %s",
                (eid,),
            )
            c.execute(
                "DELETE FROM oda_etkinlik_gunleri "
                "WHERE etkinlik_id = %s",
                (eid,),
            )
            c.execute(
                "DELETE FROM oda_etkinlikleri "
                "WHERE etkinlik_id = %s",
                (eid,),
            )


def test_bugunku_planli_randevu_pasife_almayi_engeller_gercek_veritabaninda(ortam):
    """Bugün (saati geçmiş olsa bile) planlı randevusu olan psikolog pasife alınamaz; durumu güncellenince ya da iptalde alınır."""
    c, admin, psikolog, personel, (oda_a, oda_b), kod, etiket = ortam
    istemci = TestClient(app)
    app.dependency_overrides[mevcut_kullanici_id] = lambda: admin
    pasife_al = lambda: istemci.patch(f"/api/kullanicilar/{psikolog}/durum-degistir")
    aktif = lambda: c.execute("SELECT aktif_mi FROM kullanicilar WHERE kullanici_id = %s", (psikolog,)) or c.fetchone()[0]

    dun = _randevu(c, kod, personel, oda_a, (datetime.now() - timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0))   # dünkü "Planlandı" engel olmaz
    bugun = _randevu(c, kod, personel, oda_a, datetime.now().replace(hour=0, minute=30, second=0, microsecond=0))                    # bugün, saati geçmiş
    yanit = pasife_al()
    assert yanit.status_code == 409 and "bugün ve sonrası için 1 planlı randevusu var" in yanit.json()["detail"]
    assert aktif() is True and _atanmis(c, psikolog) == [oda_a, oda_b]                          # hiçbir şey değişmedi

    c.execute("UPDATE randevular SET durum = 'TAMAMLANDI' WHERE randevu_id = %s", (bugun,))      # durumu güncellenince engel kalkar
    yanit = pasife_al()
    assert yanit.status_code == 200 and yanit.json()["yeni_durum"] is False
    assert aktif() is False and _atanmis(c, psikolog) == []                                     # oda atamaları kalktı
    c.execute("SELECT randevu_id, oda_id FROM randevular WHERE danisan_kod_id = %s ORDER BY randevu_id", (kod,))
    assert c.fetchall() == [(dun, oda_a), (bugun, oda_a)]                                       # randevular ve oda bilgileri aynen


def test_oda_yonetimi_sutunu_ve_cihaz_odasi_yalnizca_psikolog_rolune_bakar_gercek_veritabaninda(ortam):
    """Psikolog olup sonradan başka role geçen kullanıcının (eski atama kaydı kalmış olsa bile) adı Oda Yönetimi'nde görünmez, odayı tutmaz."""
    c, admin, psikolog, personel, (oda_a, oda_b), kod, etiket = ortam
    eski = _kullanici(c, f"eskipsi_{etiket}", "MEMUR")                                          # artık psikolog değil, ama oda_c kaydı kalmış
    c.execute("INSERT INTO odalar (oda_adi, kapasite) VALUES (%s, 1) RETURNING oda_id", (f"pl_oda_c_{etiket}",))
    oda_c = c.fetchone()[0]                                                                     # yalnızca eski kayıt bu odayı tutuyor
    c.execute("INSERT INTO psikolog_odalar (kullanici_id, oda_id) VALUES (%s, %s)", (eski, oda_c))
    try:
        istemci = TestClient(app)
        app.dependency_overrides[mevcut_kullanici_id] = lambda: admin
        atamalar = {a["oda_id"]: a["psikologlar"] for a in istemci.get("/api/oda-psikolog-atamalari").json()}
        assert atamalar[oda_a] == [f"pp_{etiket}"]                                              # gerçek psikolog görünür
        assert oda_c not in atamalar                                                            # eski psikologun adı görünmez
        cihaz_odalari = {o["oda_id"] for o in istemci.get("/api/cihaz-odalari").json()}
        assert oda_a not in cihaz_odalari and oda_c in cihaz_odalari                           # eski kayıt odayı tutmaz: cihaz rezervasyonuna açık
    finally:
        c.execute("DELETE FROM psikolog_odalar WHERE kullanici_id = %s", (eski,))
        c.execute("DELETE FROM odalar WHERE oda_id = %s", (oda_c,))
        c.execute("DELETE FROM kullanicilar WHERE kullanici_id = %s", (eski,))
