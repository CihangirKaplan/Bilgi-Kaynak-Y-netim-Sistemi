"""TKYS QA-001: Gercek PostgreSQL kullanici-personel butunlugu."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from threading import Barrier
from uuid import uuid4

import psycopg2
import pytest
from fastapi import HTTPException

from modeller import KullaniciOlusturModeli
from sunucu import VT_AYARLARI, kullanici_olustur


TEST_DB = "crkys_alembic_test"


@pytest.fixture
def qa_ortami():
    assert VT_AYARLARI["dbname"] == TEST_DB

    etiket = uuid4().hex[:10]
    yapan_adi = f"qa_atom_{etiket}_yapan"

    with closing(psycopg2.connect(**VT_AYARLARI)) as conn:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT current_database();")
                assert cur.fetchone()[0] == TEST_DB

                cur.execute("""
                    SELECT rol_adi, rol_id FROM roller
                    WHERE rol_adi IN ('PSIKOLOG', 'DANISMA_OGRENCISI');
                """)
                roller = dict(cur.fetchall())
                assert len(roller) == 2, "Test icin gerekli roller bulunamadi."

                gerekli = {
                    "KULLANICI_OLUSTUR",
                    "ROL_ATAMA_DEGISTIRME",
                    "PERSONEL_TANIMLA",
                }
                cur.execute(
                    "SELECT izin_adi, izin_id FROM izinler WHERE izin_adi = ANY(%s);",
                    (list(gerekli),),
                )
                izinler = dict(cur.fetchall())
                assert set(izinler) == gerekli, "Gerekli izinler eksik."

                cur.execute(
                    "INSERT INTO roller (rol_adi) VALUES (%s) RETURNING rol_id;",
                    (f"QA_ATOM_{etiket}",),
                )
                yapan_rol_id = cur.fetchone()[0]

                for izin_id in izinler.values():
                    cur.execute("""
                        INSERT INTO rol_izinleri (rol_id, izin_id, izin_var)
                        VALUES (%s, %s, 1);
                    """, (yapan_rol_id, izin_id))

                cur.execute("""
                    INSERT INTO kullanicilar (kullanici_adi, parola_hash, rol_id)
                    VALUES (%s, %s, %s)
                    RETURNING kullanici_id;
                """, (yapan_adi, "qa-gecici-hash", yapan_rol_id))
                yapan_id = cur.fetchone()[0]

                cur.execute("""
                    INSERT INTO personel (kullanici_id, personel_kodu)
                    VALUES (%s, %s);
                """, (yapan_id, f"QAAT-{etiket}"))

            conn.commit()
        except Exception:
            conn.rollback()
            raise

    ortam = {
        "etiket": etiket,
        "yapan_id": yapan_id,
        "yapan_rol_id": yapan_rol_id,
        "roller": roller,
        "kullanici_adlari": [yapan_adi],
    }

    try:
        yield ortam
    finally:
        # Yalnizca bu testin kayitlarini temizle.
        with closing(psycopg2.connect(**VT_AYARLARI)) as conn:
            try:
                with conn.cursor() as cur:
                    adlar = ortam["kullanici_adlari"]

                    cur.execute("""
                        DELETE FROM denetim_kayitlari
                        WHERE kullanici_id = %s;
                    """, (yapan_id,))

                    cur.execute("""
                        DELETE FROM ogrenciler
                        WHERE kullanici_id IN (
                            SELECT kullanici_id FROM kullanicilar
                            WHERE kullanici_adi = ANY(%s)
                        );
                    """, (adlar,))

                    cur.execute("""
                        DELETE FROM personel
                        WHERE kullanici_id IN (
                            SELECT kullanici_id FROM kullanicilar
                            WHERE kullanici_adi = ANY(%s)
                        );
                    """, (adlar,))

                    cur.execute(
                        "DELETE FROM kullanicilar WHERE kullanici_adi = ANY(%s);",
                        (adlar,),
                    )
                    cur.execute(
                        "DELETE FROM rol_izinleri WHERE rol_id = %s;",
                        (yapan_rol_id,),
                    )
                    cur.execute(
                        "DELETE FROM roller WHERE rol_id = %s;",
                        (yapan_rol_id,),
                    )

                conn.commit()
            except Exception:
                conn.rollback()
                raise


def test_postgresql_kullanici_personel_ve_audit_kaydedilir(qa_ortami):
    ortam = qa_ortami
    ad = f"qa_atom_{ortam['etiket']}_bir"
    ortam["kullanici_adlari"].append(ad)

    sonuc = kullanici_olustur(
        KullaniciOlusturModeli(
            kullanici_adi=ad,
            rol_id=ortam["roller"]["PSIKOLOG"],
        ),
        kullanici_id=ortam["yapan_id"],
    )

    with closing(psycopg2.connect(**VT_AYARLARI)) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT k.kullanici_id, p.personel_id, p.personel_kodu
                FROM kullanicilar k
                JOIN personel p ON p.kullanici_id = k.kullanici_id
                WHERE k.kullanici_adi = %s;
            """, (ad,))
            kayit = cur.fetchone()

            assert kayit is not None
            assert kayit[0] == sonuc["kullanici_id"]
            assert kayit[1] == sonuc["personel_id"]
            assert kayit[2] == sonuc["personel_kodu"]

            cur.execute("""
                SELECT hedef_tablo FROM denetim_kayitlari
                WHERE kullanici_id = %s
                  AND olay_turu = 'CREATE'
                  AND (
                    (hedef_tablo = 'kullanicilar' AND hedef_kayit_id = %s)
                    OR
                    (hedef_tablo = 'personel' AND hedef_kayit_id = %s)
                  );
            """, (
                ortam["yapan_id"],
                sonuc["kullanici_id"],
                sonuc["personel_id"],
            ))
            assert set(satir[0] for satir in cur.fetchall()) == {
                "kullanicilar", "personel"
            }


def test_postgresql_ogrenci_hatasinda_kullanici_rollback(qa_ortami):
    ortam = qa_ortami
    birinci = f"qa_atom_{ortam['etiket']}_ogr1"
    ikinci = f"qa_atom_{ortam['etiket']}_ogr2"
    ortam["kullanici_adlari"].extend([birinci, ikinci])

    ogrenci_no = str(int(ortam["etiket"], 16)).zfill(12)

    def ogrenci_modeli(ad):
        return KullaniciOlusturModeli(
            kullanici_adi=ad,
            rol_id=ortam["roller"]["DANISMA_OGRENCISI"],
            ad_soyad="QA Test Ogrencisi",
            ogrenci_numarasi=ogrenci_no,
        )

    # İlk öğrenci başarıyla kaydedilir.
    kullanici_olustur(
        ogrenci_modeli(birinci),
        kullanici_id=ortam["yapan_id"],
    )

    # Aynı öğrenci numarasıyla ikinci kayıt başarısız olmalı.
    with pytest.raises(HTTPException) as hata:
        kullanici_olustur(
            ogrenci_modeli(ikinci),
            kullanici_id=ortam["yapan_id"],
        )

    assert hata.value.status_code == 409

    # İkinci kullanıcı ve personeli veritabanında kalmamalı.
    with closing(psycopg2.connect(**VT_AYARLARI)) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM kullanicilar WHERE kullanici_adi = %s;",
                (ikinci,),
            )
            assert cur.fetchone()[0] == 0

            cur.execute("""
                SELECT COUNT(*)
                FROM personel p
                JOIN kullanicilar k ON k.kullanici_id = p.kullanici_id
                WHERE k.kullanici_adi = %s;
            """, (ikinci,))
            assert cur.fetchone()[0] == 0


def test_postgresql_eszamanli_personel_kodlari_benzersiz(qa_ortami):
    ortam = qa_ortami
    adlar = [
        f"qa_atom_{ortam['etiket']}_es1",
        f"qa_atom_{ortam['etiket']}_es2",
    ]
    ortam["kullanici_adlari"].extend(adlar)

    bariyer = Barrier(2)

    def olustur(ad):
        bariyer.wait(timeout=10)
        return kullanici_olustur(
            KullaniciOlusturModeli(
                kullanici_adi=ad,
                rol_id=ortam["roller"]["PSIKOLOG"],
            ),
            kullanici_id=ortam["yapan_id"],
        )

    with ThreadPoolExecutor(max_workers=2) as havuz:
        sonuclar = list(havuz.map(olustur, adlar))

    kodlar = [sonuc["personel_kodu"] for sonuc in sonuclar]

    assert len(kodlar) == 2
    assert len(set(kodlar)) == 2
    assert all(kod.startswith("PER-PSK-") for kod in kodlar)



@pytest.mark.parametrize("eksik_izin", [
    "KULLANICI_OLUSTUR",
    "ROL_ATAMA_DEGISTIRME",
    "PERSONEL_TANIMLA",
])
def test_http_eksik_yetki_kullanici_olusturmayi_engeller(
    qa_ortami, eksik_izin
):
    """Eksik izinle HTTP isteği reddedilmeli ve kullanıcı oluşmamalı."""
    from fastapi.testclient import TestClient
    from sunucu import app, mevcut_kullanici_id

    ortam = qa_ortami
    ad = f"qa_atom_{ortam['etiket']}_yetki"
    ortam["kullanici_adlari"].append(ad)

    # Test kullanıcısının yalnızca ilgili iznini kaldır.
    with closing(psycopg2.connect(**VT_AYARLARI)) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE rol_izinleri
                SET izin_var = 0
                WHERE rol_id = %s
                  AND izin_id = (
                      SELECT izin_id FROM izinler
                      WHERE izin_adi = %s
                  );
            """, (ortam["yapan_rol_id"], eksik_izin))

            assert cur.rowcount == 1
        conn.commit()

    app.dependency_overrides[mevcut_kullanici_id] = (
        lambda: ortam["yapan_id"]
    )

    try:
        with TestClient(app) as client:
            yanit = client.post(
                "/api/kullanicilar",
                json={
                    "kullanici_adi": ad,
                    "rol_id": ortam["roller"]["PSIKOLOG"],
                },
            )

        assert yanit.status_code == 403

        # Reddedilen işlem hiçbir kullanıcı kaydı bırakmamalı.
        with closing(psycopg2.connect(**VT_AYARLARI)) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM kullanicilar
                    WHERE kullanici_adi = %s;
                    """,
                    (ad,),
                )
                assert cur.fetchone()[0] == 0

    finally:
        app.dependency_overrides.pop(mevcut_kullanici_id, None)



def test_postgresql_audit_hatasinda_tum_kayitlar_rollback(qa_ortami):
    """Ilk Audit yazildiktan sonra hata olursa tum kayitlar geri alinmali."""
    from unittest.mock import patch

    ortam = qa_ortami
    ad = f"qa_atom_{ortam['etiket']}_audit"
    ortam["kullanici_adlari"].append(ad)

    gercek_connect = psycopg2.connect
    durum = {"audit_yazildi": 0}

    class KontrolluCursor:
        def __init__(self, cursor):
            self._cursor = cursor

        def execute(self, sorgu, parametreler=None):
            duz_sorgu = " ".join(sorgu.lower().split())
            audit = "insert into denetim_kayitlari" in duz_sorgu

            if audit and durum["audit_yazildi"] == 1:
                raise RuntimeError("QA001_KONTROLLU_AUDIT_HATASI")

            sonuc = self._cursor.execute(sorgu, parametreler)

            if audit:
                durum["audit_yazildi"] += 1

            return sonuc

        def __getattr__(self, isim):
            return getattr(self._cursor, isim)

    class KontrolluBaglanti:
        def __init__(self, baglanti):
            self._baglanti = baglanti

        def cursor(self, *args, **kwargs):
            return KontrolluCursor(
                self._baglanti.cursor(*args, **kwargs)
            )

        def __getattr__(self, isim):
            return getattr(self._baglanti, isim)

    def baglanti_olustur(**kwargs):
        return KontrolluBaglanti(gercek_connect(**kwargs))

    with patch(
        "sunucu.psycopg2.connect",
        side_effect=baglanti_olustur,
    ):
        with pytest.raises(HTTPException) as hata:
            kullanici_olustur(
                KullaniciOlusturModeli(
                    kullanici_adi=ad,
                    rol_id=ortam["roller"]["PSIKOLOG"],
                ),
                kullanici_id=ortam["yapan_id"],
            )

    assert hata.value.status_code == 500
    assert "QA001_KONTROLLU_AUDIT_HATASI" not in str(
        hata.value.detail
    )

    # En az bir Audit kaydi gercek PostgreSQL'e yazilmis olmali.
    assert durum["audit_yazildi"] == 1

    # Rollback sonrasinda ayri baglantidan kontrol et.
    with closing(psycopg2.connect(**VT_AYARLARI)) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT current_database();"
            )
            assert cur.fetchone()[0] == TEST_DB

            cur.execute(
                """
                SELECT COUNT(*) FROM kullanicilar
                WHERE kullanici_adi = %s;
                """,
                (ad,),
            )
            assert cur.fetchone()[0] == 0

            cur.execute(
                """
                SELECT COUNT(*) FROM denetim_kayitlari
                WHERE kullanici_id = %s
                  AND olay_turu = 'CREATE'
                  AND hedef_tablo IN ('kullanicilar', 'personel');
                """,
                (ortam["yapan_id"],),
            )
            assert cur.fetchone()[0] == 0


def test_postgresql_rol_degisiminde_personel_kodu_da_degisisir(qa_ortami):
    """Rol, personel kodu ve Audit gerçek PostgreSQL üzerinde doğrulanır."""
    from modeller import RolDegistirModeli
    from sunucu import kullanici_rol_degistir

    ortam = qa_ortami
    ad = f"qa_atom_{ortam['etiket']}_rol"
    ortam["kullanici_adlari"].append(ad)

    with closing(psycopg2.connect(**VT_AYARLARI)) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT rol_id FROM roller WHERE rol_adi = 'MEMUR';"
            )
            satir = cur.fetchone()
            assert satir is not None
            memur_rol_id = satir[0]

    olusturulan = kullanici_olustur(
        KullaniciOlusturModeli(
            kullanici_adi=ad,
            rol_id=ortam["roller"]["PSIKOLOG"],
        ),
        kullanici_id=ortam["yapan_id"],
    )

    kullanici_id = olusturulan["kullanici_id"]
    personel_id = olusturulan["personel_id"]
    eski_kod = olusturulan["personel_kodu"]

    assert eski_kod.startswith("PER-PSK-")

    sonuc = kullanici_rol_degistir(
        kullanici_id=kullanici_id,
        veri=RolDegistirModeli(rol_id=memur_rol_id),
        islem_yapan_id=ortam["yapan_id"],
    )

    assert sonuc["yeni_rol_adi"] == "MEMUR"
    assert sonuc["yeni_personel_kodu"].startswith("PER-MEM-")
    assert sonuc["yeni_personel_kodu"] != eski_kod

    with closing(psycopg2.connect(**VT_AYARLARI)) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT k.rol_id, p.personel_id, p.personel_kodu
                FROM kullanicilar k
                JOIN personel p ON p.kullanici_id = k.kullanici_id
                WHERE k.kullanici_id = %s;
            """, (kullanici_id,))

            kayit = cur.fetchone()

            assert kayit == (
                memur_rol_id,
                personel_id,
                sonuc["yeni_personel_kodu"],
            )

            cur.execute("""
                SELECT olay_turu::text, hedef_tablo
                FROM denetim_kayitlari
                WHERE kullanici_id = %s
                  AND (
                    (hedef_tablo = 'kullanicilar'
                     AND hedef_kayit_id = %s
                     AND olay_turu = 'ROLE_CHANGE')
                    OR
                    (hedef_tablo = 'personel'
                     AND hedef_kayit_id = %s
                     AND olay_turu = 'UPDATE')
                  );
            """, (
                ortam["yapan_id"],
                kullanici_id,
                personel_id,
            ))

            audit_kayitlari = cur.fetchall()

    assert sorted(audit_kayitlari) == sorted([
        ("ROLE_CHANGE", "kullanicilar"),
        ("UPDATE", "personel"),
    ])

    # Aynı rol yeniden seçilirse veriler değişmemeli.
    with pytest.raises(HTTPException) as hata:
        kullanici_rol_degistir(
            kullanici_id=kullanici_id,
            veri=RolDegistirModeli(rol_id=memur_rol_id),
            islem_yapan_id=ortam["yapan_id"],
        )

    assert hata.value.status_code == 409

    with closing(psycopg2.connect(**VT_AYARLARI)) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT p.personel_id, p.personel_kodu
                FROM personel p
                WHERE p.kullanici_id = %s;
            """, (kullanici_id,))
            assert cur.fetchone() == (
                personel_id,
                sonuc["yeni_personel_kodu"],
            )

            cur.execute("""
                SELECT olay_turu::text, hedef_tablo
                FROM denetim_kayitlari
                WHERE kullanici_id = %s
                  AND (
                    (hedef_tablo = 'kullanicilar'
                     AND hedef_kayit_id = %s
                     AND olay_turu = 'ROLE_CHANGE')
                    OR
                    (hedef_tablo = 'personel'
                     AND hedef_kayit_id = %s
                     AND olay_turu = 'UPDATE')
                  );
            """, (
                ortam["yapan_id"],
                kullanici_id,
                personel_id,
            ))

            assert len(cur.fetchall()) == 2


@pytest.mark.parametrize("mevcut_ogrenci", [False, True])
def test_postgresql_danisma_ogrencisi_rol_gecisi(
    qa_ortami, mevcut_ogrenci
):
    """Rol, personel kodu ve öğrenci kaydı birlikte güncellenir."""
    from modeller import RolDegistirModeli
    from sunucu import kullanici_rol_degistir

    ortam = qa_ortami
    ad = f"qa_atom_{ortam['etiket']}_danisma"
    ogrenci_no = str(int(ortam["etiket"], 16)).zfill(12)

    ortam["kullanici_adlari"].append(ad)

    olusturulan = kullanici_olustur(
        KullaniciOlusturModeli(
            kullanici_adi=ad,
            rol_id=ortam["roller"]["PSIKOLOG"],
        ),
        kullanici_id=ortam["yapan_id"],
    )

    kullanici_id = olusturulan["kullanici_id"]
    personel_id = olusturulan["personel_id"]
    eski_ogrenci_id = None

    if mevcut_ogrenci:
        with closing(psycopg2.connect(**VT_AYARLARI)) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO ogrenciler
                        (kullanici_id, ad_soyad,
                         ogrenci_numarasi, tur)
                    VALUES (%s, %s, %s, 'GONULLU')
                    RETURNING ogrenci_id;
                """, (
                    kullanici_id,
                    "QA Test Ogrencisi",
                    ogrenci_no,
                ))
                eski_ogrenci_id = cur.fetchone()[0]
            conn.commit()

    model_verisi = {
        "rol_id": ortam["roller"]["DANISMA_OGRENCISI"]
    }

    if not mevcut_ogrenci:
        model_verisi.update({
            "ad_soyad": "QA Test Ogrencisi",
            "ogrenci_numarasi": ogrenci_no,
        })

    sonuc = kullanici_rol_degistir(
        kullanici_id=kullanici_id,
        veri=RolDegistirModeli(**model_verisi),
        islem_yapan_id=ortam["yapan_id"],
    )

    assert sonuc["yeni_rol_adi"] == "DANISMA_OGRENCISI"
    assert sonuc["yeni_personel_kodu"].startswith("PER-OGR-")

    with closing(psycopg2.connect(**VT_AYARLARI)) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    r.rol_adi,
                    p.personel_id,
                    p.personel_kodu
                FROM kullanicilar k
                JOIN roller r ON r.rol_id = k.rol_id
                JOIN personel p ON p.kullanici_id = k.kullanici_id
                WHERE k.kullanici_id = %s;
            """, (kullanici_id,))

            assert cur.fetchone() == (
                "DANISMA_OGRENCISI",
                personel_id,
                sonuc["yeni_personel_kodu"],
            )

            cur.execute("""
                SELECT ogrenci_id, tur::text,
                       ad_soyad, ogrenci_numarasi
                FROM ogrenciler
                WHERE kullanici_id = %s;
            """, (kullanici_id,))

            ogrenciler = cur.fetchall()

            assert len(ogrenciler) == 1

            ogrenci_id, tur, ad_soyad, numara = ogrenciler[0]

            assert tur == "DANISMA_MASASI"
            assert ad_soyad == "QA Test Ogrencisi"
            assert numara == ogrenci_no

            if mevcut_ogrenci:
                assert ogrenci_id == eski_ogrenci_id

            cur.execute("""
                SELECT olay_turu::text
                FROM denetim_kayitlari
                WHERE kullanici_id = %s
                  AND hedef_tablo = 'ogrenciler'
                  AND hedef_kayit_id = %s;
            """, (ortam["yapan_id"], ogrenci_id))

            olaylar = [satir[0] for satir in cur.fetchall()]

            assert olaylar == [
                "UPDATE" if mevcut_ogrenci else "CREATE"
            ]


def test_postgresql_danisma_ogrencisi_aktiflik_dongusu(qa_ortami):
    """Öğrenci kaydı rol geçişlerinde korunur, aktifliği değişir."""
    from modeller import RolDegistirModeli
    from sunucu import kullanici_rol_degistir

    ortam = qa_ortami
    kullanici_adi = f"qa_atom_{ortam['etiket']}_aktiflik"
    ogrenci_no = str(int(ortam["etiket"], 16)).zfill(12)

    ortam["kullanici_adlari"].append(kullanici_adi)

    olusturulan = kullanici_olustur(
        KullaniciOlusturModeli(
            kullanici_adi=kullanici_adi,
            rol_id=ortam["roller"]["PSIKOLOG"],
        ),
        kullanici_id=ortam["yapan_id"],
    )

    kullanici_id = olusturulan["kullanici_id"]
    personel_id = olusturulan["personel_id"]

    def durum():
        with closing(psycopg2.connect(**VT_AYARLARI)) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        o.ogrenci_id,
                        o.aktif_mi,
                        o.tur::text,
                        p.personel_id,
                        p.personel_kodu,
                        r.rol_adi
                    FROM ogrenciler o
                    JOIN kullanicilar k
                        ON k.kullanici_id = o.kullanici_id
                    JOIN roller r ON r.rol_id = k.rol_id
                    JOIN personel p
                        ON p.kullanici_id = k.kullanici_id
                    WHERE o.kullanici_id = %s;
                """, (kullanici_id,))
                return cur.fetchone()

    # 1. Psikolog -> Danışma Öğrencisi
    kullanici_rol_degistir(
        kullanici_id=kullanici_id,
        veri=RolDegistirModeli(
            rol_id=ortam["roller"]["DANISMA_OGRENCISI"],
            ad_soyad="QA Aktiflik Test",
            ogrenci_numarasi=ogrenci_no,
        ),
        islem_yapan_id=ortam["yapan_id"],
    )

    ilk = durum()
    assert ilk is not None
    ogrenci_id = ilk[0]
    assert ilk[1] is True
    assert ilk[2] == "DANISMA_MASASI"
    assert ilk[3] == personel_id
    assert ilk[4].startswith("PER-OGR-")
    assert ilk[5] == "DANISMA_OGRENCISI"

    # 2. Danışma Öğrencisi -> Psikolog
    kullanici_rol_degistir(
        kullanici_id=kullanici_id,
        veri=RolDegistirModeli(
            rol_id=ortam["roller"]["PSIKOLOG"],
        ),
        islem_yapan_id=ortam["yapan_id"],
    )

    ikinci = durum()
    assert ikinci[0] == ogrenci_id
    assert ikinci[1] is False
    assert ikinci[3] == personel_id
    assert ikinci[4].startswith("PER-PSK-")
    assert ikinci[5] == "PSIKOLOG"

    # 3. Psikolog -> Tekrar Danışma Öğrencisi
    kullanici_rol_degistir(
        kullanici_id=kullanici_id,
        veri=RolDegistirModeli(
            rol_id=ortam["roller"]["DANISMA_OGRENCISI"],
        ),
        islem_yapan_id=ortam["yapan_id"],
    )

    son = durum()
    assert son[0] == ogrenci_id
    assert son[1] is True
    assert son[2] == "DANISMA_MASASI"
    assert son[3] == personel_id
    assert son[4].startswith("PER-OGR-")
    assert son[5] == "DANISMA_OGRENCISI"

    # Aynı kullanıcıya ikinci öğrenci kaydı açılmamalı.
    with closing(psycopg2.connect(**VT_AYARLARI)) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM ogrenciler WHERE kullanici_id = %s;",
                (kullanici_id,),
            )
            assert cur.fetchone()[0] == 1


def test_postgresql_acik_gorev_varken_ogrenci_rolu_degistirilemez(qa_ortami):
    """Açık danışma görevi varsa rol değişikliği engellenmeli."""
    from modeller import RolDegistirModeli
    from sunucu import kullanici_rol_degistir

    ortam = qa_ortami
    ad = f"qa_atom_{ortam['etiket']}_acik_gorev"
    ogrenci_no = str(int(ortam["etiket"], 16)).zfill(12)

    ortam["kullanici_adlari"].append(ad)

    olusturulan = kullanici_olustur(
        KullaniciOlusturModeli(
            kullanici_adi=ad,
            rol_id=ortam["roller"]["DANISMA_OGRENCISI"],
            ad_soyad="QA Acik Gorev Test",
            ogrenci_numarasi=ogrenci_no,
        ),
        kullanici_id=ortam["yapan_id"],
    )

    kullanici_id = olusturulan["kullanici_id"]
    ogrenci_id = olusturulan["ogrenci_id"]
    eski_personel_kodu = olusturulan["personel_kodu"]

    oturum_id = None

    try:
        # Test öğrencisine açık danışma görevi oluştur.
        with closing(psycopg2.connect(**VT_AYARLARI)) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO danisma_masasi_oturumlari
                        (ogrenci_id, baslangic_zamani)
                    VALUES (%s, CURRENT_TIMESTAMP)
                    RETURNING oturum_id;
                """, (ogrenci_id,))

                oturum_id = cur.fetchone()[0]

            conn.commit()

        # Açık görev varken Psikolog rolüne geçiş reddedilmeli.
        with pytest.raises(HTTPException) as hata:
            kullanici_rol_degistir(
                kullanici_id=kullanici_id,
                veri=RolDegistirModeli(
                    rol_id=ortam["roller"]["PSIKOLOG"],
                ),
                islem_yapan_id=ortam["yapan_id"],
            )

        assert hata.value.status_code == 409
        assert "görevi" in str(hata.value.detail)

        # Rol, personel kodu ve öğrenci aktifliği korunmalı.
        with closing(psycopg2.connect(**VT_AYARLARI)) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT r.rol_adi, p.personel_kodu, o.aktif_mi
                    FROM kullanicilar k
                    JOIN roller r ON r.rol_id = k.rol_id
                    JOIN personel p ON p.kullanici_id = k.kullanici_id
                    JOIN ogrenciler o ON o.kullanici_id = k.kullanici_id
                    WHERE k.kullanici_id = %s;
                """, (kullanici_id,))

                assert cur.fetchone() == (
                    "DANISMA_OGRENCISI",
                    eski_personel_kodu,
                    True,
                )

                cur.execute("""
                    SELECT COUNT(*)
                    FROM danisma_masasi_oturumlari
                    WHERE oturum_id = %s
                      AND bitis_zamani IS NULL;
                """, (oturum_id,))

                assert cur.fetchone()[0] == 1

                # Reddedilen işlem Audit'e ROLE_CHANGE yazmamalı.
                cur.execute("""
                    SELECT COUNT(*)
                    FROM denetim_kayitlari
                    WHERE kullanici_id = %s
                      AND olay_turu = 'ROLE_CHANGE'
                      AND hedef_tablo = 'kullanicilar'
                      AND hedef_kayit_id = %s;
                """, (ortam["yapan_id"], kullanici_id))

                assert cur.fetchone()[0] == 0

    finally:
        # Geçici açık görevi mutlaka temizle.
        # Diğer test kayıtlarını qa_ortami fixture'ı temizleyecek.
        if oturum_id is not None:
            with closing(psycopg2.connect(**VT_AYARLARI)) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        DELETE FROM danisma_masasi_oturumlari
                        WHERE oturum_id = %s
                          AND ogrenci_id = %s;
                    """, (oturum_id, ogrenci_id))

                conn.commit()
