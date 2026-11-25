"""Oda Etkinlikleri - gerçek PostgreSQL RBAC entegrasyon testleri."""

import pytest
import psycopg2
from fastapi.testclient import TestClient

from server.sunucu import (
    app,
    mevcut_kullanici_id,
    VT_AYARLARI,
)


def gecici_izinsiz_kullanici():
    """Hiçbir Oda Etkinlikleri izni olmayan geçici bir rol ve kullanıcı açar (varsayılan rollerin hepsi bu izinlerden en az birine sahiptir;
    bu yüzden 'izinsiz' testi gerçek bir kullanıcı bulamayıp sessizce atlanıyordu). Döndürür: (kullanici_id, rol_adi, temizle)."""
    assert VT_AYARLARI["dbname"] == "crkys_alembic_test"
    conn = psycopg2.connect(**VT_AYARLARI)
    with conn.cursor() as cursor:
        cursor.execute("INSERT INTO roller (rol_adi) VALUES ('TEST_IZINSIZ_ROL') ON CONFLICT (rol_adi) DO UPDATE SET rol_adi = EXCLUDED.rol_adi RETURNING rol_id")
        rol_id = cursor.fetchone()[0]
        cursor.execute("DELETE FROM rol_izinleri WHERE rol_id = %s", (rol_id,))
        cursor.execute("INSERT INTO kullanicilar (kullanici_adi, parola_hash, rol_id) VALUES ('oe_test_izinsiz', 'x', %s) "
                       "ON CONFLICT (kullanici_adi) DO UPDATE SET rol_id = EXCLUDED.rol_id RETURNING kullanici_id", (rol_id,))
        kullanici_id = cursor.fetchone()[0]
    conn.commit()

    def temizle():
        with conn.cursor() as imlec:
            imlec.execute("DELETE FROM kullanicilar WHERE kullanici_id = %s", (kullanici_id,))
            imlec.execute("DELETE FROM roller WHERE rol_id = %s", (rol_id,))
        conn.commit()
        conn.close()

    return kullanici_id, "TEST_IZINSIZ_ROL", temizle


def kullanici_bul(goruntule, yonet):
    assert VT_AYARLARI["dbname"] == "crkys_alembic_test"

    conn = psycopg2.connect(**VT_AYARLARI)
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT current_database()")
            assert cursor.fetchone()[0] == "crkys_alembic_test"

            cursor.execute("""
                SELECT k.kullanici_id, r.rol_adi
                FROM kullanicilar k
                JOIN roller r ON r.rol_id = k.rol_id
                WHERE k.aktif_mi = TRUE
                  AND COALESCE((
                    SELECT ri.izin_var
                    FROM rol_izinleri ri
                    JOIN izinler i ON i.izin_id = ri.izin_id
                    WHERE ri.rol_id = k.rol_id
                      AND i.izin_adi = 'ODA_ETKINLIK_GORUNTULE'
                  ), 0) = %s
                  AND COALESCE((
                    SELECT ri.izin_var
                    FROM rol_izinleri ri
                    JOIN izinler i ON i.izin_id = ri.izin_id
                    WHERE ri.rol_id = k.rol_id
                      AND i.izin_adi = 'ODA_ETKINLIK_YONET'
                  ), 0) = %s
                ORDER BY k.kullanici_id
                LIMIT 1
            """, (int(goruntule), int(yonet)))
            return cursor.fetchone()
    finally:
        conn.rollback()
        conn.close()


def istek_yap(kullanici_id, yontem, yol, **kwargs):
    app.dependency_overrides[mevcut_kullanici_id] = (
        lambda: kullanici_id
    )
    try:
        with TestClient(app) as client:
            return client.request(yontem, yol, **kwargs)
    finally:
        app.dependency_overrides.pop(mevcut_kullanici_id, None)


def test_goruntuleme_izni_olan_yonetemez():
    kullanici = kullanici_bul(True, False)
    if kullanici is None:
        pytest.skip("Görüntüleme yetkili test kullanıcısı yok.")

    kullanici_id, rol = kullanici
    print("Görüntüleme rolü:", rol)

    cevap = istek_yap(
        kullanici_id, "GET", "/api/oda-etkinlikleri"
    )
    assert cevap.status_code == 200, cevap.text

    cevap = istek_yap(
        kullanici_id, "GET", "/api/oda-etkinlikleri/secenekler"
    )
    assert cevap.status_code == 200, cevap.text
    assert cevap.json()["yonetebilir"] is False

    veri = {
        "oda_id": 1,
        "organize_eden_personel_id": 1,
        "etkinlik_adi": "Yetkisiz test",
        "katilimci_sayisi": 1,
        "baslangic_zamani": "2048-06-15T10:00:00",
        "bitis_zamani": "2048-06-15T11:00:00",
    }

    for yontem, yol, ek in (
        ("POST", "/api/oda-etkinlikleri", {"json": veri}),
        ("PATCH", "/api/oda-etkinlikleri/1", {
            "json": {"etkinlik_adi": "Yetkisiz değişiklik"}
        }),
        ("PATCH", "/api/oda-etkinlikleri/1/iptal", {}),
    ):
        cevap = istek_yap(kullanici_id, yontem, yol, **ek)
        assert cevap.status_code == 403, (
            yontem, yol, cevap.status_code, cevap.text
        )


def test_yonetim_izni_olan_secenekleri_gorur():
    kullanici = kullanici_bul(True, True)
    if kullanici is None:
        pytest.skip("Yönetim yetkili test kullanıcısı yok.")

    kullanici_id, rol = kullanici
    print("Yönetim rolü:", rol)

    cevap = istek_yap(
        kullanici_id, "GET", "/api/oda-etkinlikleri/secenekler"
    )
    assert cevap.status_code == 200, cevap.text
    assert cevap.json()["yonetebilir"] is True


def test_goruntuleme_izni_olmayan_listeyi_goremez():
    kullanici_id, rol, temizle = gecici_izinsiz_kullanici()
    try:
        print("Yetkisiz rol:", rol)

        for yol in (
            "/api/oda-etkinlikleri",
            "/api/oda-etkinlikleri/secenekler",
            "/api/dashboard/bugunku-rezervasyonlar",                      # cihaz izni de yok: ana panel rezervasyon listesi de 403
        ):
            cevap = istek_yap(kullanici_id, "GET", yol)
            assert cevap.status_code == 403, (
                yol, cevap.status_code, cevap.text
            )

        # Ana paneldeki bugünkü etkinlikler ise giriş yapmış herkese açıktır (salt okunur bilgi): izni olmayan da görür.
        cevap = istek_yap(kullanici_id, "GET", "/api/dashboard/bugunku-etkinlikler")
        assert cevap.status_code == 200, (cevap.status_code, cevap.text)
    finally:
        temizle()


@pytest.mark.parametrize("izin_sonucu", [None, (0,)])
def test_goruntuleme_izni_reddedilince_403(izin_sonucu):
    from unittest.mock import patch

    # Sadece yetki sorgusunun sonucunu taklit ediyoruz.
    # Gerçek kullanıcı, rol veya izin kayıtları değişmiyor.
    with patch("server.sunucu.psycopg2.connect") as baglan:
        baglan.return_value.cursor.return_value.fetchone.return_value = (
            izin_sonucu
        )

        cevap = istek_yap(
            1, "GET", "/api/oda-etkinlikleri"
        )

        assert cevap.status_code == 403, cevap.text

    print("PASS | Yetkisiz görüntüleme HTTP 403.")


VARSAYILAN_ODA_ETKINLIK_IZINLERI = {
    # rol: (ODA_ETKINLIK_GORUNTULE, ODA_ETKINLIK_YONET)
    "ADMIN": (1, 1), "MUDUR": (1, 1), "MEMUR": (1, 1), "PROJE_ASISTANI": (1, 1),
    "PSIKOLOG": (1, 0), "DANISMA_OGRENCISI": (1, 0),
}


def test_varsayilan_oda_etkinligi_izin_matrisi_alembic_sonrasi_dogru():
    """Alembic ile kurulan veritabanında her rolün Oda Etkinlikleri varsayılanı (Proje Asistanı dahil görüntüler ve yönetir)."""
    assert VT_AYARLARI["dbname"] == "crkys_alembic_test"
    conn = psycopg2.connect(**VT_AYARLARI)
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT UPPER(r.rol_adi), i.izin_adi, ri.izin_var
                FROM rol_izinleri ri
                JOIN roller r ON r.rol_id = ri.rol_id
                JOIN izinler i ON i.izin_id = ri.izin_id
                WHERE i.izin_adi IN ('ODA_ETKINLIK_GORUNTULE', 'ODA_ETKINLIK_YONET')
                  AND UPPER(r.rol_adi) = ANY(%s)
            """, (list(VARSAYILAN_ODA_ETKINLIK_IZINLERI),))
            bulunan = {}
            for rol, izin, deger in cursor.fetchall():
                bulunan.setdefault(rol, {})[izin] = deger
    finally:
        conn.rollback()
        conn.close()
    gercek = {rol: (d.get("ODA_ETKINLIK_GORUNTULE"), d.get("ODA_ETKINLIK_YONET")) for rol, d in bulunan.items()}
    assert gercek == VARSAYILAN_ODA_ETKINLIK_IZINLERI


# ---------------------------------------------------------------- Ana panel: duyurular, "Benim günüm", gün seçici (gerçek SQL)
def _mevcut_kullanici(rol_adi):
    """Veritabanında bu rolde etkin, kayıtlı bir kullanıcı (CI tohumunda Admin vardır). Yeni kullanıcı AÇILMAZ: denetim kaydı bağlanan
    kullanıcı silinemez ve diğer PG testlerinin kullanıcı sayımlarını bozardı. Döndürür: (kullanici_id, kullanici_adi, temizle)."""
    assert VT_AYARLARI["dbname"] == "crkys_alembic_test"
    conn = psycopg2.connect(**VT_AYARLARI)
    with conn.cursor() as cursor:
        cursor.execute("SELECT k.kullanici_id, k.kullanici_adi FROM kullanicilar k JOIN roller r ON r.rol_id = k.rol_id "
                       "WHERE UPPER(r.rol_adi) = %s AND k.aktif_mi = TRUE ORDER BY k.kullanici_id LIMIT 1", (rol_adi,))
        satir = cursor.fetchone()
    assert satir is not None, f"{rol_adi} rolünde etkin kullanıcı yok (CI tohumu çalışmadı mı?)"
    kullanici_id, kullanici_adi = satir

    def temizle():
        with conn.cursor() as imlec:
            imlec.execute("DELETE FROM duyurular WHERE olusturan_kullanici_id = %s", (kullanici_id,))
        conn.commit()
        conn.close()

    return kullanici_id, kullanici_adi, temizle


def test_varsayilan_duyuru_izni_yalniz_yonetim_rollerinde_alembic_sonrasi():
    conn = psycopg2.connect(**VT_AYARLARI)
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT UPPER(r.rol_adi), ri.izin_var FROM rol_izinleri ri
                JOIN roller r ON r.rol_id = ri.rol_id JOIN izinler i ON i.izin_id = ri.izin_id
                WHERE i.izin_adi = 'DUYURU_YONET' AND UPPER(r.rol_adi) IN ('ADMIN','MUDUR','MEMUR','PSIKOLOG','PROJE_ASISTANI','DANISMA_OGRENCISI')
            """)
            bulunan = dict(cursor.fetchall())
    finally:
        conn.rollback()
        conn.close()
    assert bulunan == {"ADMIN": 1, "MUDUR": 1, "MEMUR": 1, "PSIKOLOG": 0, "PROJE_ASISTANI": 0, "DANISMA_OGRENCISI": 0}


def test_duyuru_herkes_okur_yalniz_izinli_yazar_ve_kaldirir_gercek_sql():
    yonetici_id, yonetici_adi, yonetici_temizle = _mevcut_kullanici("ADMIN")
    izinsiz_id, _rol, izinsiz_temizle = gecici_izinsiz_kullanici()
    try:
        yanit = istek_yap(yonetici_id, "POST", "/api/duyurular", json={"baslik": "Test duyurusu", "metin": "Yarın bakım var."})
        assert yanit.status_code == 201, yanit.text
        duyuru_id = yanit.json()["duyuru_id"]

        # izni olmayan, giriş yapmış kullanıcı okur ama yazan adını görmez; yazamaz ve kaldıramaz
        okunan = [d for d in istek_yap(izinsiz_id, "GET", "/api/duyurular").json() if d["duyuru_id"] == duyuru_id]
        assert okunan and okunan[0]["yazan"] is None and okunan[0]["yonetebilir"] is False and okunan[0]["yeni"] is True
        assert istek_yap(izinsiz_id, "POST", "/api/duyurular", json={"baslik": "a", "metin": "b"}).status_code == 403
        assert istek_yap(izinsiz_id, "DELETE", f"/api/duyurular/{duyuru_id}").status_code == 403

        yonetici_gorur = [d for d in istek_yap(yonetici_id, "GET", "/api/duyurular").json() if d["duyuru_id"] == duyuru_id][0]
        assert yonetici_gorur["yazan"] == yonetici_adi and yonetici_gorur["yonetebilir"] is True

        # süresi geçmiş duyuru listede çıkmaz
        conn = psycopg2.connect(**VT_AYARLARI)
        with conn.cursor() as cursor:
            cursor.execute("UPDATE duyurular SET son_gecerlilik_tarihi = CURRENT_DATE - 1 WHERE duyuru_id = %s", (duyuru_id,))
        conn.commit()
        conn.close()
        assert duyuru_id not in [d["duyuru_id"] for d in istek_yap(izinsiz_id, "GET", "/api/duyurular").json()]

        assert istek_yap(yonetici_id, "DELETE", f"/api/duyurular/{duyuru_id}").status_code == 200
        assert istek_yap(yonetici_id, "DELETE", f"/api/duyurular/{duyuru_id}").status_code == 404
        assert istek_yap(yonetici_id, "POST", "/api/duyurular", json={"baslik": " ", "metin": "x"}).status_code == 422

        conn = psycopg2.connect(**VT_AYARLARI)
        with conn.cursor() as cursor:
            cursor.execute("SELECT olay_turu::text FROM denetim_kayitlari WHERE hedef_tablo = 'duyurular' AND hedef_kayit_id = %s ORDER BY 1", (duyuru_id,))
            assert [s[0] for s in cursor.fetchall()] == ["CREATE", "DELETE"]
        conn.close()
    finally:
        yonetici_temizle()
        izinsiz_temizle()


@pytest.mark.parametrize("aralik", ["bugun", "yarin", "hafta"])
def test_ana_panel_uclari_her_aralikta_gercek_sql_ile_calisir(aralik):
    yonetici_id, _ad, yonetici_temizle = _mevcut_kullanici("ADMIN")
    try:
        for yol in ("bugunku-randevular", "bugunku-rezervasyonlar", "bugunku-etkinlikler"):
            yanit = istek_yap(yonetici_id, "GET", f"/api/dashboard/{yol}?aralik={aralik}")
            assert yanit.status_code == 200, (yol, yanit.text)
            assert isinstance(yanit.json(), list)
        gunum = istek_yap(yonetici_id, "GET", "/api/dashboard/benim-gunum")
        assert gunum.status_code == 200 and gunum.json() == {"randevular": [], "rezervasyonlar": []}        # personel kaydı olmayan kullanıcıda boş
    finally:
        yonetici_temizle()
