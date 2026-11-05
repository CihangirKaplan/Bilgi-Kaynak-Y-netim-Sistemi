from unittest.mock import patch
import os
from uuid import uuid4

import psycopg2
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient

from guvenlik import parola_hashle, parola_dogrula
from sunucu import app, VT_AYARLARI, token_kullanici_id


def test_parola_sifirlama_gercek_postgresql():
    # Yanlış veritabanında çalışmayı kesinlikle engelle.
    assert os.getenv("TKYS_PG_TEST_ONAY") == "EVET"
    assert VT_AYARLARI["dbname"] == "crkys_alembic_test"

    conn = psycopg2.connect(**VT_AYARLARI)
    kullanici_idleri = []
    kod = uuid4().hex[:12]

    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT current_database()")
            assert cursor.fetchone()[0] == "crkys_alembic_test"

            cursor.execute("SELECT version_num FROM alembic_version")
            assert cursor.fetchall() == [("d82c4a71f06b",)]

            cursor.execute("""
                SELECT rol_adi, rol_id
                FROM roller
                WHERE rol_adi IN ('ADMIN', 'MEMUR')
            """)
            roller = dict(cursor.fetchall())
            assert set(roller) == {"ADMIN", "MEMUR"}

            hesaplar = {}

            for ad, rol in (
                ("yonetici", "ADMIN"),
                ("hedef", "MEMUR"),
            ):
                kullanici_adi = f"qa_reset_{ad}_{kod}"
                parola = f"Test!{kod}Aa"

                cursor.execute("""
                    INSERT INTO kullanicilar
                        (kullanici_adi, parola_hash,
                         rol_id, aktif_mi, ilk_giris_mi)
                    VALUES (%s, %s, %s, TRUE, FALSE)
                    RETURNING kullanici_id
                """, (
                    kullanici_adi,
                    parola_hashle(parola),
                    roller[rol],
                ))

                kullanici_id = cursor.fetchone()[0]
                kullanici_idleri.append(kullanici_id)

                cursor.execute("""
                    INSERT INTO personel
                        (kullanici_id, personel_kodu, aktif_mi)
                    VALUES (%s, %s, TRUE)
                """, (
                    kullanici_id,
                    f"QA{kod}{'A' if ad == 'yonetici' else 'M'}",
                ))

                hesaplar[ad] = {
                    "id": kullanici_id,
                    "ad": kullanici_adi,
                    "parola": parola,
                }

        conn.commit()

        with TestClient(app) as client:

            def giris(hesap, parola):
                # Test için bilinen bir CAPTCHA oluştur.
                # Gerçek CAPTCHA doğrulaması korunur.
                def test_rakam(ust_sinir):
                    return 7 if ust_sinir == 10 else 0

                with patch(
                    "captcha_servisi.secrets.randbelow",
                    side_effect=test_rakam,
                ):
                    captcha_cevap = client.get("/api/captcha")

                assert captcha_cevap.status_code == 200, captcha_cevap.text

                captcha = captcha_cevap.json()

                assert len(captcha["captcha_id"]) == 32
                assert captcha["gorsel_base64"]

                giris_verisi = {
                    "kullanici_adi": hesap["ad"],
                    "parola": parola,
                    "captcha_id": captcha["captcha_id"],
                    "guvenlik_kodu": "77777",
                }

                cevap = client.post(
                    "/api/login",
                    json=giris_verisi,
                )

                assert cevap.status_code == 200, cevap.text

                # Aynı CAPTCHA ikinci kez kullanılamamalı.
                tekrar = client.post(
                    "/api/login",
                    json=giris_verisi,
                )

                assert tekrar.status_code == 400

                return cevap.json()

            def baslik(token):
                return {"Authorization": f"Bearer {token}"}

            yonetici = hesaplar["yonetici"]
            hedef = hesaplar["hedef"]

            admin_token = giris(
                yonetici, yonetici["parola"]
            )["access_token"]

            eski_token = giris(
                hedef, hedef["parola"]
            )["access_token"]

            url = (
                f"/api/kullanicilar/{hedef['id']}/parola-sifirla"
            )

            # MEMUR, başkasının parolasını sıfırlayamaz.
            yetkisiz = client.post(
                url,
                headers=baslik(eski_token),
            )
            assert yetkisiz.status_code == 403

            # ADMIN parola sıfırlayabilir.
            sifirlama = client.post(
                url,
                headers=baslik(admin_token),
            )
            assert sifirlama.status_code == 200, sifirlama.text
            assert sifirlama.headers.get("cache-control") == "no-store"

            gecici_parola = sifirlama.json()["gecici_parola"]
            assert gecici_parola != hedef["parola"]

            # Yeni parola hashlenmiş ve ilk giriş zorunlu olmalı.
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT parola_hash, ilk_giris_mi
                    FROM kullanicilar
                    WHERE kullanici_id = %s
                """, (hedef["id"],))
                yeni_hash, ilk_giris = cursor.fetchone()

                assert parola_dogrula(gecici_parola, yeni_hash)
                assert ilk_giris is True

                cursor.execute("""
                    SELECT COUNT(*)
                    FROM denetim_kayitlari
                    WHERE kullanici_id = %s
                      AND hedef_tablo = 'kullanicilar'
                      AND hedef_kayit_id = %s
                      AND olay_turu = 'PASSWORD_RESET'
                """, (yonetici["id"], hedef["id"]))

                assert cursor.fetchone()[0] == 1

            # Eski JWT artık geçerli olmamalı.
            with pytest.raises(HTTPException) as hata:
                token_kullanici_id(
                    credentials=HTTPAuthorizationCredentials(
                        scheme="Bearer",
                        credentials=eski_token,
                    )
                )
            assert hata.value.status_code == 401

            # Geçici parolayla giriş yapılabilmeli.
            gecici_giris = giris(hedef, gecici_parola)
            assert gecici_giris["sifre_degistirme_gerekli"] is True

            # Kullanıcı kendine yeni parola belirlemeli.
            yeni_parola = f"Yeni!{kod}Bb"

            degistirme = client.post(
                "/api/sifre-degistir",
                headers=baslik(
                    gecici_giris["access_token"]
                ),
                json={
                    "eski_parola": gecici_parola,
                    "yeni_parola": yeni_parola,
                    "yeni_parola_tekrar": yeni_parola,
                },
            )
            assert degistirme.status_code == 200, degistirme.text

            # Son girişte parola değiştirme zorunluluğu kalkmalı.
            son_giris = giris(hedef, yeni_parola)
            assert son_giris["sifre_degistirme_gerekli"] is False

    finally:
        # Yalnızca bu testin oluşturduğu kullanıcıları temizle.
        try:
            conn.rollback()

            if kullanici_idleri:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        DELETE FROM denetim_kayitlari
                        WHERE kullanici_id = ANY(%s)
                           OR (
                               hedef_tablo = 'kullanicilar'
                               AND hedef_kayit_id = ANY(%s)
                           )
                    """, (
                        kullanici_idleri,
                        kullanici_idleri,
                    ))

                    cursor.execute("""
                        DELETE FROM personel
                        WHERE kullanici_id = ANY(%s)
                    """, (kullanici_idleri,))

                    cursor.execute("""
                        DELETE FROM kullanicilar
                        WHERE kullanici_id = ANY(%s)
                    """, (kullanici_idleri,))

                conn.commit()
        finally:
            conn.close()
