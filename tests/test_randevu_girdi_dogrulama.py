
import pytest
from pydantic import ValidationError

from modeller import RandevuOlusturModeli, RandevuGuncelleModeli


# Testlerde kullanılacak geçerli randevu bilgileri
def gecerli_randevu():
    return {
        "danisan_kod_id": "DAN-2026-0001",
        "psikolog_id": 1,
        "oda_id": 1,
        "baslangic_zamani": "2026-10-15T10:00:00",
        "bitis_zamani": "2026-10-15T11:00:00",
    }


# 1. Geçerli randevu verileri kabul edilmeli
def test_gecerli_randevu_kabul_edilir():
    randevu = RandevuOlusturModeli(**gecerli_randevu())

    assert randevu.psikolog_id == 1
    assert randevu.oda_id == 1


# 2. Boş danışan kodu reddedilmeli
@pytest.mark.parametrize("kod", ["", "   "])
def test_bos_danisan_kodu_reddedilir(kod):
    veriler = gecerli_randevu()
    veriler["danisan_kod_id"] = kod

    with pytest.raises(ValidationError):
        RandevuOlusturModeli(**veriler)


# 3. Sıfır veya negatif ID değerleri reddedilmeli
@pytest.mark.parametrize(
    "alan,deger",
    [
        ("psikolog_id", 0),
        ("psikolog_id", -5),
        ("oda_id", 0),
        ("oda_id", -2),
    ],
)
def test_gecersiz_id_reddedilir(alan, deger):
    veriler = gecerli_randevu()
    veriler[alan] = deger

    with pytest.raises(ValidationError):
        RandevuOlusturModeli(**veriler)


# 4. Eksik zorunlu alanlar reddedilmeli
@pytest.mark.parametrize(
    "alan",
    [
        "danisan_kod_id",
        "psikolog_id",
        "oda_id",
        "baslangic_zamani",
        "bitis_zamani",
    ],
)
def test_eksik_alan_reddedilir(alan):
    veriler = gecerli_randevu()
    del veriler[alan]

    with pytest.raises(ValidationError):
        RandevuOlusturModeli(**veriler)


# 5. Geçersiz tarih formatı reddedilmeli
def test_gecersiz_tarih_reddedilir():
    veriler = gecerli_randevu()
    veriler["baslangic_zamani"] = "gecersiz-tarih"

    with pytest.raises(ValidationError):
        RandevuOlusturModeli(**veriler)


# 6. Güncellemede geçersiz değerler reddedilmeli
@pytest.mark.parametrize(
    "alan,deger",
    [
        ("danisan_kod_id", ""),
        ("danisan_kod_id", "   "),
        ("psikolog_id", -1),
        ("oda_id", 0),
    ],
)
def test_gecersiz_guncelleme_reddedilir(alan, deger):
    with pytest.raises(ValidationError):
        RandevuGuncelleModeli(**{alan: deger})


# 7. Tek alanla geçerli güncelleme yapılabilmeli
def test_tek_alan_guncelleme_kabul_edilir():
    guncelleme = RandevuGuncelleModeli(oda_id=2)

    assert guncelleme.model_dump(exclude_unset=True) == {
        "oda_id": 2
    }


from datetime import datetime
from unittest.mock import patch
from fastapi import HTTPException

from sunucu import randevu_olustur


# 8. Başlangıç zamanı bitişten önce olmalı
def test_baslangic_bitisten_sonra_olamaz():
    veriler = gecerli_randevu()
    veriler["baslangic_zamani"] = "2026-10-15T12:00:00"
    veriler["bitis_zamani"] = "2026-10-15T11:00:00"

    randevu = RandevuOlusturModeli(**veriler)

    with patch("sunucu.psycopg2.connect") as mock_connect:
        with pytest.raises(HTTPException) as hata:
            randevu_olustur(randevu, kullanici_id=1)

        assert hata.value.status_code == 422

        # Hatalı istekte veritabanına bağlanılmamalı.
        mock_connect.assert_not_called()



# 9. Geçersiz danışan koduyla randevu oluşturulamamalı
def test_gecersiz_danisan_kodu_reddedilir():
    randevu = RandevuOlusturModeli(**gecerli_randevu())

    with patch("sunucu.psycopg2.connect") as mock_connect:
        mock_cursor = mock_connect.return_value.cursor.return_value

        # İlk sorgu: Kullanıcı rolü ADMIN
        # İkinci sorgu: Danışan kodu bulunamadı
        mock_cursor.fetchone.side_effect = [
            ("ADMIN",),
            None,
        ]

        with pytest.raises(HTTPException) as hata:
            randevu_olustur(randevu, kullanici_id=1)

        assert hata.value.status_code == 422
        assert hata.value.detail == (
            "Danışan kodu bulunamadı veya aktif değil."
        )

        # Hatalı randevu veritabanına kaydedilmemeli.
        mock_connect.return_value.commit.assert_not_called()

        # INSERT sorgusu çalıştırılmamalı.
        sorgular = [
            cagri.args[0].strip().upper()
            for cagri in mock_cursor.execute.call_args_list
        ]
        assert not any(
            sorgu.startswith("INSERT") for sorgu in sorgular
        )


# 9. Geçersiz danışan koduyla randevu oluşturulamamalı
def test_gecersiz_danisan_kodu_reddedilir():
    randevu = RandevuOlusturModeli(**gecerli_randevu())

    with patch("sunucu.psycopg2.connect") as mock_connect:
        mock_cursor = mock_connect.return_value.cursor.return_value

        # Kullanıcı ADMIN, danışan kodu bulunamadı.
        mock_cursor.fetchone.side_effect = [
            ("ADMIN",),
            None,
        ]

        with pytest.raises(HTTPException) as hata:
            randevu_olustur(randevu, kullanici_id=1)

        assert hata.value.status_code == 422
        assert hata.value.detail == (
            "Danışan kodu bulunamadı veya aktif değil."
        )

        # Veritabanına kayıt yapılmamalı.
        mock_connect.return_value.commit.assert_not_called()

        sorgular = [
            cagri.args[0].strip().upper()
            for cagri in mock_cursor.execute.call_args_list
        ]
        assert not any(
            sorgu.startswith("INSERT") for sorgu in sorgular
        )


# 10. Geçersiz veya pasif psikologla randevu oluşturulamamalı
def test_gecersiz_psikolog_reddedilir():
    randevu = RandevuOlusturModeli(**gecerli_randevu())

    with patch("sunucu.psycopg2.connect") as mock_connect:
        mock_cursor = mock_connect.return_value.cursor.return_value

        # Kullanıcı ADMIN
        # Danışan kodu geçerli
        # Psikolog bulunamadı veya aktif değil
        mock_cursor.fetchone.side_effect = [
            ("ADMIN",),
            (1,),
            None,
        ]

        with pytest.raises(HTTPException) as hata:
            randevu_olustur(randevu, kullanici_id=1)

        assert hata.value.status_code == 422
        assert hata.value.detail == (
            "Geçerli ve aktif bir psikolog seçilmelidir."
        )

        # Hatalı veri kaydedilmemeli.
        mock_connect.return_value.commit.assert_not_called()

        sorgular = [
            cagri.args[0].strip().upper()
            for cagri in mock_cursor.execute.call_args_list
        ]
        assert not any(
            sorgu.startswith("INSERT") for sorgu in sorgular
        )


# 10. Geçersiz veya pasif psikologla randevu oluşturulamamalı
def test_gecersiz_psikolog_reddedilir():
    randevu = RandevuOlusturModeli(**gecerli_randevu())

    with patch("sunucu.psycopg2.connect") as mock_connect:
        mock_cursor = mock_connect.return_value.cursor.return_value

        # Kullanıcı ADMIN
        # Danışan kodu geçerli
        # Psikolog bulunamadı veya aktif değil
        mock_cursor.fetchone.side_effect = [
            ("ADMIN",),
            (1,),
            None,
        ]

        with pytest.raises(HTTPException) as hata:
            randevu_olustur(randevu, kullanici_id=1)

        assert hata.value.status_code == 422
        assert hata.value.detail == (
            "Geçerli ve aktif bir psikolog seçilmelidir."
        )

        # Hatalı veri kaydedilmemeli.
        mock_connect.return_value.commit.assert_not_called()

        sorgular = [
            cagri.args[0].strip().upper()
            for cagri in mock_cursor.execute.call_args_list
        ]
        assert not any(
            sorgu.startswith("INSERT") for sorgu in sorgular
        )



# 11. Geçersiz veya pasif odayla randevu oluşturulamamalı
def test_gecersiz_oda_reddedilir():
    randevu = RandevuOlusturModeli(**gecerli_randevu())

    with patch("sunucu.psycopg2.connect") as mock_connect:
        mock_cursor = mock_connect.return_value.cursor.return_value

        # Kullanıcı ADMIN
        # Danışan kodu geçerli
        # Psikolog geçerli
        # Oda bulunamadı veya aktif değil
        mock_cursor.fetchone.side_effect = [
            ("ADMIN",),
            (1,),
            (1,),
            None,
        ]

        with pytest.raises(HTTPException) as hata:
            randevu_olustur(randevu, kullanici_id=1)

        assert hata.value.status_code == 422
        assert hata.value.detail == (
            "Oda bulunamadı veya aktif değil."
        )

        # Hatalı randevu kaydedilmemeli.
        mock_connect.return_value.commit.assert_not_called()

        sorgular = [
            cagri.args[0].strip().upper()
            for cagri in mock_cursor.execute.call_args_list
        ]
        assert not any(
            sorgu.startswith("INSERT") for sorgu in sorgular
        )


from sunucu import randevu_guncelle


# 12. Boş güncelleme isteği reddedilmeli
def test_bos_guncelleme_reddedilir():
    guncelleme = RandevuGuncelleModeli()

    with patch("sunucu.psycopg2.connect") as mock_connect:
        mock_cursor = mock_connect.return_value.cursor.return_value

        # Randevu mevcut ve PLANLANDI durumunda
        # Kullanıcı ADMIN
        mock_cursor.fetchone.side_effect = [
            (
                "DAN-2026-0001",
                1,
                1,
                datetime(2026, 10, 15, 10, 0),
                datetime(2026, 10, 15, 11, 0),
                "PLANLANDI",
            ),
            ("ADMIN",),
        ]

        with pytest.raises(HTTPException) as hata:
            randevu_guncelle(
                randevu_id=1,
                guncelleme=guncelleme,
                kullanici_id=1,
            )

        assert hata.value.status_code == 422
        assert hata.value.detail == (
            "Geçerli güncelleme alanları gönderilmelidir."
        )

        # Güncelleme yapılmamalı.
        mock_connect.return_value.commit.assert_not_called()

        sorgular = [
            cagri.args[0].strip().upper()
            for cagri in mock_cursor.execute.call_args_list
        ]
        assert not any(
            sorgu.startswith("UPDATE") for sorgu in sorgular
        )


# 13. Null değerle güncelleme yapılamamalı
def test_null_guncelleme_reddedilir():
    guncelleme = RandevuGuncelleModeli(oda_id=None)

    with patch("sunucu.psycopg2.connect") as mock_connect:
        mock_cursor = mock_connect.return_value.cursor.return_value

        # Randevu mevcut ve planlandı, kullanıcı ADMIN
        mock_cursor.fetchone.side_effect = [
            (
                "DAN-2026-0001",
                1,
                1,
                datetime(2026, 10, 15, 10, 0),
                datetime(2026, 10, 15, 11, 0),
                "PLANLANDI",
            ),
            ("ADMIN",),
        ]

        with pytest.raises(HTTPException) as hata:
            randevu_guncelle(
                randevu_id=1,
                guncelleme=guncelleme,
                kullanici_id=1,
            )

        assert hata.value.status_code == 422
        assert hata.value.detail == (
            "Geçerli güncelleme alanları gönderilmelidir."
        )

        # Hatalı güncelleme kaydedilmemeli.
        mock_connect.return_value.commit.assert_not_called()

        sorgular = [
            cagri.args[0].strip().upper()
            for cagri in mock_cursor.execute.call_args_list
        ]
        assert not any(
            sorgu.startswith("UPDATE") for sorgu in sorgular
        )



# 14. Güncellemede başlangıç zamanı bitişten sonra olamaz
def test_guncellemede_gecersiz_tarih_reddedilir():
    guncelleme = RandevuGuncelleModeli(
        baslangic_zamani=datetime(2026, 10, 15, 12, 0)
    )

    with patch("sunucu.psycopg2.connect") as mock_connect:
        mock_cursor = mock_connect.return_value.cursor.return_value

        # Mevcut randevu 10.00 - 11.00 arasında
        # Kullanıcı ADMIN
        mock_cursor.fetchone.side_effect = [
            (
                "DAN-2026-0001",
                1,
                1,
                datetime(2026, 10, 15, 10, 0),
                datetime(2026, 10, 15, 11, 0),
                "PLANLANDI",
            ),
            ("ADMIN",),
        ]

        with pytest.raises(HTTPException) as hata:
            randevu_guncelle(
                randevu_id=1,
                guncelleme=guncelleme,
                kullanici_id=1,
            )

        assert hata.value.status_code == 422
        assert hata.value.detail == (
            "Başlangıç zamanı bitiş zamanından önce olmalıdır."
        )

        # Hatalı güncelleme kaydedilmemeli.
        mock_connect.return_value.commit.assert_not_called()

        sorgular = [
            cagri.args[0].strip().upper()
            for cagri in mock_cursor.execute.call_args_list
        ]
        assert not any(
            sorgu.startswith("UPDATE") for sorgu in sorgular
        )


# 15. Geçerli randevu güncellemesi başarılı olmalı
def test_gecerli_randevu_guncellenir():
    guncelleme = RandevuGuncelleModeli(oda_id=2)

    with patch("sunucu.psycopg2.connect") as mock_connect:
        mock_conn = mock_connect.return_value
        mock_cursor = mock_conn.cursor.return_value

        mock_cursor.fetchone.side_effect = [
            # Mevcut randevu
            (
                "DAN-2026-0001",
                1,
                1,
                datetime(2026, 10, 15, 10, 0),
                datetime(2026, 10, 15, 11, 0),
                "PLANLANDI",
            ),
            ("ADMIN",),  # Kullanıcı rolü
            (1,),        # Danışan kodu geçerli
            (1,),        # Psikolog geçerli
            (1,),        # Yeni oda geçerli
            None,        # Saat çakışması yok
        ]

        sonuc = randevu_guncelle(
            randevu_id=1,
            guncelleme=guncelleme,
            kullanici_id=1,
        )

        assert sonuc["durum"] == "basarili"
        assert sonuc["randevu_id"] == 1

        # Güncelleme sorgusu çalıştırılmış olmalı.
        update_cagrilari = [
            cagri
            for cagri in mock_cursor.execute.call_args_list
            if cagri.args[0].strip().upper().startswith("UPDATE")
        ]

        assert len(update_cagrilari) == 1

        # Yeni oda ID'si sorguya aktarılmış olmalı.
        assert update_cagrilari[0].args[1][2] == 2

        # İşlem kaydedilmiş olmalı.
        mock_conn.commit.assert_called_once()
