"""
TKYS - Quality Assurance (QA-001)
GitHub Issue: #186
Test Alani: Randevu Transaction ve Veri Butunlugu

Amac:
PostgreSQL EXCLUDE kisitlarinin gercek veritabani
uzerinde randevu cakismalarini engelledigini dogrulamak.
"""

from contextlib import closing
from datetime import datetime, timedelta
from uuid import uuid4

import psycopg2
import pytest
from psycopg2.errors import ExclusionViolation

from server.sunucu import VT_AYARLARI


def test_quality_randevu_cakisma_kisitlari_postgresql():
    assert VT_AYARLARI["dbname"] == "crkys_alembic_test"

    etiket = uuid4().hex[:12]

    with closing(psycopg2.connect(**VT_AYARLARI)) as conn:
        try:
            with conn.cursor() as cursor:

                cursor.execute("SELECT current_database();")
                assert cursor.fetchone()[0] == "crkys_alembic_test"

                cursor.execute("SET LOCAL lock_timeout = '3s';")
                cursor.execute("SET LOCAL statement_timeout = '10s';")

                # Psikolog rolunu bul veya transaction icinde olustur.
                cursor.execute(
                    "SELECT rol_id FROM roller WHERE rol_adi = %s;",
                    ("PSIKOLOG",),
                )
                kayit = cursor.fetchone()

                if kayit:
                    rol_id = kayit[0]
                else:
                    cursor.execute(
                        """
                        INSERT INTO roller (rol_adi)
                        VALUES (%s)
                        RETURNING rol_id;
                        """,
                        ("PSIKOLOG",),
                    )
                    rol_id = cursor.fetchone()[0]

                # Iki gecici oda olustur.
                oda_ids = []

                for i in (1, 2):
                    cursor.execute(
                        """
                        INSERT INTO odalar (oda_adi, kapasite)
                        VALUES (%s, %s)
                        RETURNING oda_id;
                        """,
                        (f"QA001-{etiket}-ODA-{i}", 2),
                    )
                    oda_ids.append(cursor.fetchone()[0])

                # Iki gecici psikolog/personel olustur.
                psikolog_ids = []

                for i in (1, 2):
                    cursor.execute(
                        """
                        INSERT INTO kullanicilar
                            (kullanici_adi, parola_hash, rol_id)
                        VALUES (%s, %s, %s)
                        RETURNING kullanici_id;
                        """,
                        (
                            f"qa001_{etiket}_p{i}",
                            "qa001-test-kaydi",
                            rol_id,
                        ),
                    )
                    kullanici_id = cursor.fetchone()[0]

                    cursor.execute(
                        """
                        INSERT INTO personel
                            (kullanici_id, personel_kodu)
                        VALUES (%s, %s)
                        RETURNING personel_id;
                        """,
                        (
                            kullanici_id,
                            f"QA001-{etiket}-{i}",
                        ),
                    )
                    psikolog_ids.append(cursor.fetchone()[0])

                # Gecici danisan kodu olustur.
                danisan_kodu = f"QA001-{etiket}"

                cursor.execute(
                    """
                    INSERT INTO danisan_kodlari
                        (danisan_kod_id, ucretli_mi)
                    VALUES (%s, TRUE);
                    """,
                    (danisan_kodu,),
                )

                oda1, oda2 = oda_ids
                psikolog1, psikolog2 = psikolog_ids

                baslangic = (
                    datetime.now().replace(microsecond=0)
                    + timedelta(days=60)
                )
                bitis = baslangic + timedelta(hours=1)

                def randevu_ekle(psikolog, oda, ilk, son):
                    cursor.execute(
                        """
                        INSERT INTO randevular
                            (
                                danisan_kod_id,
                                psikolog_id,
                                oda_id,
                                baslangic_zamani,
                                bitis_zamani,
                                durum
                            )
                        VALUES (%s, %s, %s, %s, %s, 'PLANLANDI');
                        """,
                        (
                            danisan_kodu,
                            psikolog,
                            oda,
                            ilk,
                            son,
                        ),
                    )

                # 1. Ilk randevu basarili olmali.
                randevu_ekle(
                    psikolog1,
                    oda1,
                    baslangic,
                    bitis,
                )

                cakis_baslangic = baslangic + timedelta(minutes=30)
                cakis_bitis = bitis + timedelta(minutes=30)

                # 2 ve 3. Iki farkli cakisma senaryosu.
                senaryolar = [
                    (
                        psikolog2,
                        oda1,
                        "oda_randevu_cakisma",
                    ),
                    (
                        psikolog1,
                        oda2,
                        "psikolog_randevu_cakisma",
                    ),
                ]

                for psikolog, oda, beklenen_kisit in senaryolar:
                    cursor.execute("SAVEPOINT qa001_cakisma;")

                    try:
                        with pytest.raises(ExclusionViolation) as hata:
                            randevu_ekle(
                                psikolog,
                                oda,
                                cakis_baslangic,
                                cakis_bitis,
                            )

                        assert (
                            hata.value.diag.constraint_name
                            == beklenen_kisit
                        )

                    finally:
                        cursor.execute(
                            "ROLLBACK TO SAVEPOINT qa001_cakisma;"
                        )
                        cursor.execute(
                            "RELEASE SAVEPOINT qa001_cakisma;"
                        )

                # 4. Bitisik saatlerde randevu olusturulabilmeli.
                randevu_ekle(
                    psikolog1,
                    oda1,
                    bitis,
                    bitis + timedelta(hours=1),
                )

                # Sadece iki basarili randevu bulunmali.
                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM randevular
                    WHERE danisan_kod_id = %s;
                    """,
                    (danisan_kodu,),
                )

                assert cursor.fetchone()[0] == 2

        finally:
            # Basarili veya basarisiz her durumda
            # gecici verileri geri al.
            conn.rollback()


# ======================================================================================================================
# scripts/randevu_cakisma_onar.py: eksik çakışma kurallarının tespiti ve onarımı (gerçek PostgreSQL; her test geri alınır)
# ======================================================================================================================
from datetime import datetime as _dt  # noqa: E402

from scripts import randevu_cakisma_onar as onar  # noqa: E402


def _onarim_ortami(cursor, etiket):
    """İşlemde: iki oda, bir psikolog (personel görünümü üzerinden) ve bir danışan; çakışma kurallarını KALDIRIR (eksik kurulumu taklit)."""
    cursor.execute("SET LOCAL lock_timeout = '3s'")
    cursor.execute("ALTER TABLE randevular DROP CONSTRAINT IF EXISTS psikolog_randevu_cakisma")
    cursor.execute("ALTER TABLE randevular DROP CONSTRAINT IF EXISTS oda_randevu_cakisma")
    odalar = []
    for i in (1, 2):
        cursor.execute("INSERT INTO odalar (oda_adi) VALUES (%s) RETURNING oda_id", (f"onar_oda_{i}_{etiket}",))
        odalar.append(cursor.fetchone()[0])
    cursor.execute("INSERT INTO kullanicilar (kullanici_adi, parola_hash, rol_id) VALUES (%s, 'x', (SELECT rol_id FROM roller WHERE rol_adi = 'PSIKOLOG')) RETURNING kullanici_id",
                   (f"onar_k_{etiket}",))
    kullanici = cursor.fetchone()[0]
    cursor.execute("INSERT INTO personel (kullanici_id, personel_kodu) VALUES (%s, %s) RETURNING personel_id", (kullanici, f"ONR-{etiket}"))
    psikolog = cursor.fetchone()[0]
    cursor.execute("INSERT INTO danisan_kodlari (danisan_kod_id) VALUES (%s)", (f"ONR-D-{etiket}",))
    return odalar, psikolog, f"ONR-D-{etiket}"


def _randevu(cursor, kod, psikolog, oda, saat, dakika=60, durum="PLANLANDI"):
    bas = _dt(2038, 3, 3, saat, 0)
    cursor.execute(
        "INSERT INTO randevular (danisan_kod_id, psikolog_id, oda_id, baslangic_zamani, bitis_zamani, durum) "
        "VALUES (%s, %s, %s, %s, %s + make_interval(mins => %s), %s) RETURNING randevu_id", (kod, psikolog, oda, bas, bas, dakika, durum))
    return cursor.fetchone()[0]


def _savepointli(cursor, sql, parametre=()):
    cursor.execute("SAVEPOINT s")
    try:
        cursor.execute(sql, parametre or None)
    except psycopg2.Error as hata:
        cursor.execute("ROLLBACK TO SAVEPOINT s")
        return hata
    cursor.execute("RELEASE SAVEPOINT s")
    return None


def _onarim_testi(test):
    def sarmal():
        assert VT_AYARLARI["dbname"] == "crkys_alembic_test"
        conn = psycopg2.connect(**VT_AYARLARI)
        try:
            with conn.cursor() as cursor:
                test(cursor, uuid4().hex[:8])
        finally:
            conn.rollback()
            conn.close()
    sarmal.__name__ = test.__name__
    return sarmal


@_onarim_testi
def test_onarim_eksik_kurallari_bulur_cakisma_yokken_ekler_ve_kurallar_calisir(cursor, etiket):
    (oda1, oda2), psikolog, kod = _onarim_ortami(cursor, etiket)
    assert sorted(a for a, _, _ in onar.eksik_kurallar(cursor)) == ["oda_randevu_cakisma", "psikolog_randevu_cakisma"]
    _randevu(cursor, kod, psikolog, oda1, 10)
    _randevu(cursor, kod, psikolog, oda2, 11)                                                # ardışık (10-11, 11-12): çakışma DEĞİL
    assert onar.cakismalar(cursor, "psikolog_id") == [] and onar.cakismalar(cursor, "oda_id") == []
    sorun, _, uygulanabilir = onar.karar(onar.eksik_kurallar(cursor), {"psikolog_id": 0, "oda_id": 0})
    assert uygulanabilir and sorun
    onar.uygula(cursor, onar.eksik_kurallar(cursor))
    assert onar.eksik_kurallar(cursor) == []
    assert isinstance(_savepointli(cursor, "INSERT INTO randevular (danisan_kod_id, psikolog_id, oda_id, baslangic_zamani, bitis_zamani, durum) "
                                           "VALUES (%s, %s, %s, '2038-03-03 10:30', '2038-03-03 11:30', 'PLANLANDI')", (kod, psikolog, oda2)),
                      ExclusionViolation)                                                    # kural artık çakışmayı engeller (aynı psikolog)


@_onarim_testi
def test_onarim_cakisan_randevular_varken_kurali_eklemez_cakismalari_listeler(cursor, etiket):
    (oda1, oda2), psikolog, kod = _onarim_ortami(cursor, etiket)
    a = _randevu(cursor, kod, psikolog, oda1, 10)
    b = _randevu(cursor, kod, psikolog, oda2, 10, dakika=30)                                  # aynı psikolog, aynı saat, farklı oda
    liste = onar.cakismalar(cursor, "psikolog_id")
    assert [(c["a"], c["b"]) for c in liste] == [(a, b)] and liste[0]["a_kod"] == kod
    assert onar.cakismalar(cursor, "oda_id") == []                                           # odalar farklı
    sorun, _, uygulanabilir = onar.karar(onar.eksik_kurallar(cursor), {"psikolog_id": 1, "oda_id": 0})
    assert uygulanabilir is False and any("psikolog_id: 1 çakışan" in s for s in sorun)
    assert isinstance(_savepointli(cursor, onar.kural_sql("psikolog_randevu_cakisma", "psikolog_id")), ExclusionViolation)      # veritabanı da reddeder


@_onarim_testi
def test_onarim_iptal_edilen_randevular_cakisma_sayilmaz(cursor, etiket):
    (oda1, _), psikolog, kod = _onarim_ortami(cursor, etiket)
    _randevu(cursor, kod, psikolog, oda1, 10)
    _randevu(cursor, kod, psikolog, oda1, 10, durum="IPTAL_EDILDI")                          # aynı psikolog, aynı oda, aynı saat ama iptal
    assert onar.cakismalar(cursor, "psikolog_id") == [] and onar.cakismalar(cursor, "oda_id") == []
    onar.uygula(cursor, onar.eksik_kurallar(cursor))
    assert onar.eksik_kurallar(cursor) == []


@_onarim_testi
def test_onarim_yalniz_eksik_olan_kurali_ekler(cursor, etiket):
    _onarim_ortami(cursor, etiket)
    cursor.execute(onar.kural_sql("oda_randevu_cakisma", "oda_id"))                           # oda kuralı var, psikolog kuralı eksik
    assert [a for a, _, _ in onar.eksik_kurallar(cursor)] == ["psikolog_randevu_cakisma"]
    onar.uygula(cursor, onar.eksik_kurallar(cursor))
    assert onar.eksik_kurallar(cursor) == []
