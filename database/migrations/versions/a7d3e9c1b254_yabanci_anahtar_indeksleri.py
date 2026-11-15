"""Yabancı anahtar sütunlarına indeks ekle

Bir tabloya başka bir tabloyu gösteren sütun (yabancı anahtar) varsa, PostgreSQL bu sütun için kendiliğinden
indeks oluşturmaz. Bu yüzden "bu cihazın tüm bakımları", "bu odanın etkinlikleri", "bu rolün kullanıcıları" gibi
sorgular ve bir kayıt silinirken ona bağlı kayıt var mı denetimi, tablo büyüdükçe tüm tabloyu taramak zorunda kalır.

Bu migrasyon, indeksi olmayan 24 yabancı anahtar sütununa indeks ekler. Veriye dokunmaz; yalnızca arama hızını
artırır. IF NOT EXISTS sayesinde tekrar çalıştırmak zararsızdır.

Revision ID: a7d3e9c1b254
Revises: b5e2c8d9a1f3
Create Date: 2026-11-13

"""
from typing import Sequence, Union

from alembic import op


revision: str = "a7d3e9c1b254"
down_revision: Union[str, Sequence[str], None] = "b5e2c8d9a1f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (tablo, sütun): bu sütunların hiçbirinin başında indeks yoktu.
INDEKSLER = [
    ("danisan_kodlari", "olusturan_psikolog_id"),
    ("rol_izinleri", "izin_id"),
    ("kullanicilar", "rol_id"),
    ("ogrenci_faaliyet_takip", "birim_id"),
    ("ogrenci_faaliyet_takip", "faaliyet_id"),
    ("ogrenci_faaliyet_takip", "ogrenci_id"),
    ("denetim_kayitlari", "kullanici_id"),
    ("cihazlar", "zimmetli_oda_id"),
    ("cihaz_rezervasyonlari", "bolum_id"),
    ("cihaz_rezervasyonlari", "kullanilacak_oda_id"),
    ("cihaz_rezervasyonlari", "rezervasyonu_yapan_personel_id"),
    ("cihaz_arizalari", "cihaz_id"),
    ("cihaz_bakimlari", "cihaz_id"),
    ("cihaz_kalibrasyonlari", "cihaz_id"),
    ("cihaz_bakim_planlari", "cihaz_id"),
    ("cihaz_takip_parametreleri", "cihaz_id"),
    ("randevular", "danisan_kod_id"),
    ("oda_etkinlikleri", "oda_id"),
    ("oda_etkinlikleri", "organize_eden_personel_id"),
    ("personel_faaliyet_kayitlari", "birim_id"),
    ("personel_faaliyet_kayitlari", "faaliyet_id"),
    ("parola_sifirlama_talepleri", "kapatan_kullanici_id"),
    ("ogrenci_kayit_erteleme_gecmisi", "erteleyen_kullanici_id"),
    ("psikolog_odalar", "oda_id"),
]


def indeks_adi(tablo: str, sutun: str) -> str:
    # PostgreSQL'de ad en fazla 63 karakter olabilir; en uzun ad bunun altındadır (test ile korunur).
    return f"ix_{tablo}_{sutun}"


def upgrade() -> None:
    for tablo, sutun in INDEKSLER:
        op.execute(f'CREATE INDEX IF NOT EXISTS "{indeks_adi(tablo, sutun)}" ON "{tablo}" ("{sutun}")')


def downgrade() -> None:
    for tablo, sutun in INDEKSLER:
        op.execute(f'DROP INDEX IF EXISTS "{indeks_adi(tablo, sutun)}"')
