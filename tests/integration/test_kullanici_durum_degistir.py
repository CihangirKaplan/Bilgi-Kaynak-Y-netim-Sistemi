from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from server.sunucu import (
    DurumDegistirModeli,
    app,
    kullanici_durum_degistir,
    mevcut_kullanici_id,
)


def sahte_db(islem_rolu="MUDUR", hedef_rol="PSIKOLOG", aktif=True, planli=0, aktif_odalar=(3,), rezervasyonlu=()):
    """planli: bugünden sonraki planlı randevu sayısı (psikolog pasife alınırken sorulur).
    aktif_odalar / rezervasyonlu: psikolog aktifleştirilirken oda doğrulama ve cihaz rezervasyonlu oda sorguları."""
    conn = MagicMock()
    cursor = conn.cursor.return_value
    fetchone = [(islem_rolu,), (hedef_rol, aktif)]
    if hedef_rol == "PSIKOLOG" and aktif:
        fetchone.append((planli,))
    cursor.fetchone.side_effect = fetchone
    cursor.fetchall.side_effect = [[(o,) for o in aktif_odalar], list(rezervasyonlu)]
    return conn, cursor


def calistir(conn, veri=None, **kwargs):
    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        return kullanici_durum_degistir(kullanici_id=5, veri=veri, islem_yapan_id=10, **kwargs)


def sorgular(cursor):
    return [c.args for c in cursor.execute.call_args_list]


def yazan_sorgu_var_mi(cursor, baslangic):
    return any(args[0].strip().upper().startswith(baslangic) for args in sorgular(cursor))


@pytest.mark.parametrize(
    "mevcut,beklenen",
    [(True, False), (False, True)],
)
def test_aktif_pasif_durum_degistirme(mevcut, beklenen):
    conn, cursor = sahte_db(aktif=mevcut)

    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        sonuc = kullanici_durum_degistir(
            kullanici_id=5,
            veri=None if mevcut else DurumDegistirModeli(oda_idleri=[3]),   # psikolog aktifleştirilirken oda seçilir
            islem_yapan_id=10,
        )

    assert sonuc["yeni_durum"] is beklenen

    sorgular = [
        c.args for c in cursor.execute.call_args_list
    ]

    for tablo in ("kullanicilar", "personel"):
        assert any(
            f"UPDATE {tablo} SET aktif_mi" in args[0]
            and args[1] == (beklenen, 5)
            for args in sorgular
        )

    assert any(
        "INSERT INTO denetim_kayitlari" in args[0]
        for args in sorgular
    )

    conn.commit.assert_called_once()


def test_mudur_admin_durumunu_degistiremez():
    conn, _ = sahte_db(hedef_rol="ADMIN")

    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            kullanici_durum_degistir(
                kullanici_id=5,
                islem_yapan_id=10,
            )

    assert hata.value.status_code == 403
    conn.commit.assert_not_called()


def test_kendi_hesabini_degistiremez():
    conn = MagicMock()

    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            kullanici_durum_degistir(
                kullanici_id=10,
                islem_yapan_id=10,
            )

    assert hata.value.status_code == 403
    conn.commit.assert_not_called()


def test_olmayan_kullanici_reddedilir():
    conn, _ = sahte_db()
    conn.cursor.return_value.fetchone.side_effect = [
        ("MUDUR",),
        None,
    ]

    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            kullanici_durum_degistir(
                kullanici_id=999,
                islem_yapan_id=10,
            )

    assert hata.value.status_code == 404
    conn.commit.assert_not_called()


def test_yetkisiz_http_erisim_reddedilir():
    conn = MagicMock()
    conn.cursor.return_value.fetchone.return_value = (0,)

    app.dependency_overrides[mevcut_kullanici_id] = lambda: 10

    try:
        with patch("server.sunucu.psycopg2.connect", return_value=conn):
            with TestClient(app) as client:
                yanit = client.patch(
                    "/api/kullanicilar/5/durum-degistir"
                )

        assert yanit.status_code == 403
        conn.commit.assert_not_called()
    finally:
        app.dependency_overrides.pop(mevcut_kullanici_id, None)


def test_veritabani_hatasi_hassas_bilgi_sizdirmaz():
    conn = MagicMock()
    cursor = conn.cursor.return_value

    gizli_hata = (
        "password=GIZLI_TEST_SIFRESI "
        "SELECT * FROM kullanicilar "
        "/Users/test/proje/.env"
    )

    cursor.execute.side_effect = RuntimeError(gizli_hata)

    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            kullanici_durum_degistir(
                kullanici_id=5,
                islem_yapan_id=10,
            )

    assert hata.value.status_code == 500

    mesaj = str(hata.value.detail)

    assert "GIZLI_TEST_SIFRESI" not in mesaj
    assert "SELECT * FROM" not in mesaj
    assert ".env" not in mesaj

    conn.rollback.assert_called_once()
    conn.commit.assert_not_called()


def test_durum_degistirme_audit_parametreleri_dogru():
    conn, cursor = sahte_db(
        islem_rolu="MUDUR",
        hedef_rol="PSIKOLOG",
        aktif=True,
    )

    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        kullanici_durum_degistir(
            kullanici_id=5,
            islem_yapan_id=10,
        )

    audit_cagrilari = [
        c for c in cursor.execute.call_args_list
        if "INSERT INTO denetim_kayitlari" in c.args[0]
    ]

    # Psikolog pasife alınınca oda atamalarının kaldırılması da denetim kaydına yazılır.
    assert [c.args[1] for c in audit_cagrilari] == [
        (10, "UPDATE", "psikolog_odalar", 5),
        (10, "UPDATE", "kullanicilar", 5),
    ]

    conn.commit.assert_called_once()


def test_mudur_http_uzerinden_kullanici_durumunu_degistirebilir():
    endpoint = next(
        route for route in app.routes
        if getattr(route, "path", None)
        == "/api/kullanicilar/{kullanici_id}/durum-degistir"
        and "PATCH" in getattr(route, "methods", set())
    )

    yetki_bagimliligi = endpoint.dependant.dependencies[0].call

    conn, cursor = sahte_db(
        islem_rolu="MUDUR",
        hedef_rol="PSIKOLOG",
        aktif=True,
    )

    app.dependency_overrides[yetki_bagimliligi] = lambda: 10

    try:
        with patch("server.sunucu.psycopg2.connect", return_value=conn):
            with TestClient(app) as client:
                yanit = client.patch(
                    "/api/kullanicilar/5/durum-degistir"
                )

        assert yanit.status_code == 200
        assert yanit.json()["kullanici_id"] == 5
        assert yanit.json()["yeni_durum"] is False

        conn.commit.assert_called_once()

    finally:
        app.dependency_overrides.pop(yetki_bagimliligi, None)


# ------------------------------------------------------------------ psikolog pasife alınırken / aktifleştirilirken odalar
def test_planli_randevusu_olan_psikolog_pasife_alinamaz():
    conn, cursor = sahte_db(planli=2)
    with pytest.raises(HTTPException) as hata:
        calistir(conn)
    assert hata.value.status_code == 409
    assert "2 planlı randevusu var" in hata.value.detail and "iptal edin" in hata.value.detail
    assert not yazan_sorgu_var_mi(cursor, "UPDATE")                       # durum değişmez
    assert not yazan_sorgu_var_mi(cursor, "DELETE")                       # oda atamaları da kalkmaz
    conn.commit.assert_not_called()
    conn.rollback.assert_called_once()


def test_planli_randevu_denetimi_yalnizca_bugunden_sonrasini_ve_planlilari_sayar():
    conn, cursor = sahte_db()
    calistir(conn)
    sql, parametreler = next(a for a in sorgular(cursor) if "FROM randevular r" in a[0])
    assert "r.durum = 'PLANLANDI'" in sql and "r.baslangic_zamani > NOW()" in sql      # geçmişte kalan "Planlandı" kayıtlar engellemez
    assert "p.personel_id = r.psikolog_id" in sql and parametreler == (5,)


def test_psikolog_pasife_alininca_oda_atamalari_kaldirilir_ve_yenisi_yazilmaz():
    conn, cursor = sahte_db()
    sonuc = calistir(conn)
    assert sonuc["yeni_durum"] is False
    silme = [a for a in sorgular(cursor) if a[0].strip().upper().startswith("DELETE FROM PSIKOLOG_ODALAR")]
    assert [a[1] for a in silme] == [(5,)]
    assert not yazan_sorgu_var_mi(cursor, "INSERT INTO PSIKOLOG_ODALAR")
    assert not yazan_sorgu_var_mi(cursor, "DELETE FROM RANDEVULAR") and not yazan_sorgu_var_mi(cursor, "UPDATE RANDEVULAR")   # geçmiş randevular etkilenmez
    conn.commit.assert_called_once()


def test_psikolog_aktiflestirilirken_oda_zorunlu():
    conn, cursor = sahte_db(aktif=False)
    with pytest.raises(HTTPException) as hata:
        calistir(conn)
    assert hata.value.status_code == 422 and "en az bir görüşme odası" in hata.value.detail
    assert not yazan_sorgu_var_mi(cursor, "UPDATE")
    conn.commit.assert_not_called()
    with pytest.raises(HTTPException) as hata:
        calistir(sahte_db(aktif=False)[0], DurumDegistirModeli(oda_idleri=[]))
    assert hata.value.status_code == 422


def test_psikolog_aktiflestirilirken_pasif_ya_da_olmayan_oda_reddedilir():
    conn, cursor = sahte_db(aktif=False, aktif_odalar=(3,))
    with pytest.raises(HTTPException) as hata:
        calistir(conn, DurumDegistirModeli(oda_idleri=[3, 9]))
    assert hata.value.status_code == 422 and "aktif değil" in hata.value.detail
    assert not yazan_sorgu_var_mi(cursor, "UPDATE")
    conn.commit.assert_not_called()


def test_psikolog_cihaz_rezervasyonlu_odayla_aktiflestirilemez_ve_uyari_doner():
    conn, cursor = sahte_db(aktif=False, aktif_odalar=(3, 4), rezervasyonlu=[("EEG Odası", 1)])
    with pytest.raises(HTTPException) as hata:
        calistir(conn, DurumDegistirModeli(oda_idleri=[3, 4]))
    assert hata.value.status_code == 409
    assert "EEG Odası (1 rezervasyon)" in hata.value.detail and "psikologa atanamaz" in hata.value.detail
    assert not yazan_sorgu_var_mi(cursor, "UPDATE") and not yazan_sorgu_var_mi(cursor, "INSERT INTO PSIKOLOG_ODALAR")
    conn.commit.assert_not_called()
    conn.rollback.assert_called_once()


def test_psikolog_aktiflestirilirken_secilen_odalar_yazilir_eski_artik_kayitlar_degisir():
    conn, cursor = sahte_db(aktif=False, aktif_odalar=(2, 3))
    sonuc = calistir(conn, DurumDegistirModeli(oda_idleri=[3, 2, 3]))
    assert sonuc["yeni_durum"] is True
    metinler = [a[0].strip().upper() for a in sorgular(cursor)]
    silme = next(i for i, m in enumerate(metinler) if m.startswith("DELETE FROM PSIKOLOG_ODALAR"))
    eklemeler = [(i, a[1]) for i, (a, m) in enumerate(zip(sorgular(cursor), metinler)) if m.startswith("INSERT INTO PSIKOLOG_ODALAR")]
    assert [e[1] for e in eklemeler] == [(5, 2), (5, 3)] and all(e[0] > silme for e in eklemeler)      # tekrarsız, sıralı; önce eskiler silinir
    audit = [a[1] for a in sorgular(cursor) if "INSERT INTO denetim_kayitlari" in a[0]]
    assert audit == [(10, "UPDATE", "psikolog_odalar", 5), (10, "UPDATE", "kullanicilar", 5)]
    conn.commit.assert_called_once()


def test_psikolog_olmayan_icin_davranis_eskisi_gibi_oda_sorgusu_yok():
    for aktif in (True, False):
        conn = MagicMock()
        cursor = conn.cursor.return_value
        cursor.fetchone.side_effect = [("MUDUR",), ("MEMUR", aktif)]
        sonuc = calistir(conn)
        assert sonuc["yeni_durum"] is (not aktif)
        assert not any("psikolog_odalar" in a[0].lower() or "FROM randevular" in a[0] for a in sorgular(cursor))
        conn.commit.assert_called_once()


def test_psikolog_olmayana_ya_da_pasife_alinirken_oda_secimi_reddedilir():
    conn = MagicMock()
    conn.cursor.return_value.fetchone.side_effect = [("MUDUR",), ("MEMUR", False)]
    with pytest.raises(HTTPException) as hata:
        calistir(conn, DurumDegistirModeli(oda_idleri=[3]))
    assert hata.value.status_code == 422 and "yalnızca psikolog aktifleştirilirken" in hata.value.detail
    conn.commit.assert_not_called()
    conn, _ = sahte_db(aktif=True)                                         # aktif psikolog pasife alınırken oda gönderilemez
    with pytest.raises(HTTPException) as hata:
        calistir(conn, DurumDegistirModeli(oda_idleri=[3]))
    assert hata.value.status_code == 422


@pytest.mark.parametrize("govde, beklenen", [(None, 422), ({}, 422), ({"oda_idleri": [3]}, 200)])
def test_http_psikolog_aktiflestirme_govdesi(govde, beklenen):
    endpoint = next(r for r in app.routes if getattr(r, "path", None) == "/api/kullanicilar/{kullanici_id}/durum-degistir" and "PATCH" in getattr(r, "methods", set()))
    yetki = endpoint.dependant.dependencies[0].call
    conn, _ = sahte_db(aktif=False, aktif_odalar=(3,))
    app.dependency_overrides[yetki] = lambda: 10
    try:
        with patch("server.sunucu.psycopg2.connect", return_value=conn):
            with TestClient(app) as client:
                yanit = client.patch("/api/kullanicilar/5/durum-degistir", **({} if govde is None else {"json": govde}))
        assert yanit.status_code == beklenen
        assert (conn.commit.call_count == 1) is (beklenen == 200)
    finally:
        app.dependency_overrides.pop(yetki, None)
