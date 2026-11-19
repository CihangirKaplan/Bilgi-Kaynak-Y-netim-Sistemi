"""Cihaz rezervasyonunda oda kilidi ve uygunluk kontrolü sırası."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from server.modeller import RezervasyonOlusturModeli
from server.sunucu import cihaz_rezervasyonu_yap


def test_oda_kilidi_uygunluk_sorgusundan_once_alinir():
    baslangic = (
        datetime.now() + timedelta(days=30)
    ).replace(hour=10, minute=0, second=0, microsecond=0)

    conn = MagicMock()
    cursor = conn.cursor.return_value

    def sorgu_calistir(sql, params=None):
        sql_normal = " ".join(sql.split()).upper()

        if "FROM CIHAZLAR WHERE CIHAZ_ID" in sql_normal:
            cursor.fetchone.return_value = ("Kullanima_Hazir",)

        elif "FROM (" in sql_normal and "ODA_ID" in sql_normal:
            cursor.fetchone.return_value = (1,)

        elif "RETURNING REZERVASYON_ID" in sql_normal:
            cursor.fetchone.return_value = (77,)

        elif "FROM PERSONEL WHERE KULLANICI_ID" in sql_normal:
            cursor.fetchone.return_value = (1,)

        else:
            cursor.fetchone.return_value = None

    cursor.execute.side_effect = sorgu_calistir
    cursor.fetchall.return_value = []

    rezervasyon = RezervasyonOlusturModeli(
        cihaz_id=1,
        kullanilacak_oda_id=2,
        baslangic_zamani=baslangic,
        bitis_zamani=baslangic + timedelta(hours=1),
        proje_turu="Test",
        proje_adi_aciklamasi="Oda kilidi sıra testi",
    )

    with patch(
        "server.sunucu.psycopg2.connect",
        return_value=conn,
    ):
        sonuc = cihaz_rezervasyonu_yap(
            rez=rezervasyon,
            kullanici_id=1,
        )

    sorgular = [
        c.args[0]
        for c in cursor.execute.call_args_list
    ]

    kilit_indeksleri = [
        i for i, sql in enumerate(sorgular)
        if "pg_advisory_xact_lock" in sql
    ]

    uygunluk_indeksleri = [
        i for i, sql in enumerate(sorgular)
        if "CIHAZ_ODALARI_SORGUSU" in sql
        or ("SELECT 1 FROM (" in sql and ") d WHERE d.oda_id" in sql)
    ]

    assert len(kilit_indeksleri) == 1
    assert len(uygunluk_indeksleri) == 1
    assert kilit_indeksleri[0] < uygunluk_indeksleri[0]

    kilit_cagrisi = cursor.execute.call_args_list[
        kilit_indeksleri[0]
    ]
    assert kilit_cagrisi.args[1] == (391284, 2)

    assert sonuc["rezervasyon_id"] == 77
    conn.commit.assert_called_once()
