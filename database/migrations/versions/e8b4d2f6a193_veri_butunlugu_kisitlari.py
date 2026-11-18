"""Veri bütünlüğü: cihaz_id zorunlu, randevu durumu CHECK, büyük/küçük harf duyarsız benzersiz adlar

Revision ID: e8b4d2f6a193
Revises: d6c3a9e1f407
Create Date: 2026-11-18 14:00:00.000000

1. cihaz_arizalari / cihaz_bakimlari / cihaz_kalibrasyonlari / cihaz_bakim_planlari: cihaz_id NOT NULL. Kod her zaman doldurur
   ama veritabanı korumuyordu; cihazsız (yetim) kayıt oluşabilirdi. (Erteleme geçmişi gibi bilerek ON DELETE SET NULL olan
   sütunlara dokunulmaz.)
2. randevular.durum: yalnızca PLANLANDI, TAMAMLANDI, GELMEDI, IPTAL_EDILDI kabul edilir (CHECK) ve boş olamaz. Çakışma
   kısıtları yalnızca durum='PLANLANDI' satırlarına baktığı için yazım hatalı bir durum randevuyu sessizce kısıt dışı bırakırdı.
3. kullanicilar.kullanici_adi, odalar.oda_adi, bolumler.bolum_adi: büyük/küçük harf farkı yok sayılarak benzersiz
   ("Ali" ile "ali", "Oda A" ile "oda a" aynı sayılır). Türkçe için İ, I, ı, i aynı harf kabul edilir.

Mevcut veri kuralları bozuyorsa hiçbir değişiklik yapılmadan açık bir hatayla durulur (sorunlu kayıtlar listelenir; düzeltilip
komut yeniden çalıştırılır). Durum CHECK'i için eski bozuk satırlar varsa kısıt NOT VALID eklenir: yeni ve değişen satırlar
denetlenir, eskiler migrasyonu durdurmaz.
"""
import warnings
from typing import Sequence, Union

from alembic import op

revision: str = "e8b4d2f6a193"
down_revision: Union[str, Sequence[str], None] = "d6c3a9e1f407"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CIHAZ_TABLOLARI = ("cihaz_arizalari", "cihaz_bakimlari", "cihaz_kalibrasyonlari", "cihaz_bakim_planlari")
RANDEVU_DURUMLARI = ("PLANLANDI", "TAMAMLANDI", "GELMEDI", "IPTAL_EDILDI")
# (tablo, sütun, indeks adı)
AD_INDEKSLERI = (
    ("kullanicilar", "kullanici_adi", "ux_kullanicilar_kullanici_adi_ci"),
    ("odalar", "oda_adi", "ux_odalar_oda_adi_ci"),
    ("bolumler", "bolum_adi", "ux_bolumler_bolum_adi_ci"),
)


def ad_anahtari_sql(sutun):
    """Karşılaştırma anahtarı: küçük harf + Türkçe İ/I/ı -> i (uygulamadaki proje türü kontrolüyle aynı mantık)."""
    return f"lower(translate({sutun}, 'İIı', 'iii'))"


def _tek_deger(baglanti, sorgu):
    return baglanti.exec_driver_sql(sorgu).scalar()


def upgrade():
    baglanti = op.get_bind()

    # --- 1) cihaz_id zorunlu
    for tablo in CIHAZ_TABLOLARI:
        bos = _tek_deger(baglanti, f"SELECT count(*) FROM {tablo} WHERE cihaz_id IS NULL")
        if bos:
            raise RuntimeError(
                f"{tablo} tablosunda cihaz_id boş olan {bos} kayıt var. Bu kayıtlar hangi cihaza ait olduğu bilinmeyen "
                f"yetim kayıtlardır; silin ya da bir cihaza bağlayın, sonra migrasyonu yeniden çalıştırın."
            )
    for tablo in CIHAZ_TABLOLARI:
        op.execute(f"ALTER TABLE {tablo} ALTER COLUMN cihaz_id SET NOT NULL")

    # --- 2) randevu durumu
    bos_durum = _tek_deger(baglanti, "SELECT count(*) FROM randevular WHERE durum IS NULL")
    if bos_durum:
        raise RuntimeError(f"randevular tablosunda durumu boş olan {bos_durum} kayıt var; durumlarını düzeltip yeniden çalıştırın.")
    op.execute("ALTER TABLE randevular ALTER COLUMN durum SET NOT NULL")
    liste = ", ".join(f"'{d}'" for d in RANDEVU_DURUMLARI)
    bozuk = baglanti.exec_driver_sql(
        f"SELECT DISTINCT durum FROM randevular WHERE durum NOT IN ({liste})").fetchall()
    kisit = f"ALTER TABLE randevular ADD CONSTRAINT ck_randevular_durum CHECK (durum IN ({liste}))"
    if bozuk:
        warnings.warn(
            "randevular.durum içinde tanınmayan değerler var: " + ", ".join(repr(b[0]) for b in bozuk)
            + ". Kısıt NOT VALID eklendi (yeni/değişen satırlar denetlenir); eski satırları düzeltip "
              "'ALTER TABLE randevular VALIDATE CONSTRAINT ck_randevular_durum' çalıştırabilirsiniz.")
        kisit += " NOT VALID"
    op.execute(kisit)

    # --- 3) büyük/küçük harf duyarsız benzersiz adlar
    for tablo, sutun, _indeks in AD_INDEKSLERI:
        anahtar = ad_anahtari_sql(sutun)
        tekrarlar = baglanti.exec_driver_sql(
            f"SELECT {anahtar}, array_agg({sutun} ORDER BY {sutun}) FROM {tablo} "
            f"GROUP BY 1 HAVING count(*) > 1").fetchall()
        if tekrarlar:
            ayrinti = "; ".join(" / ".join(repr(a) for a in satir[1]) for satir in tekrarlar)
            raise RuntimeError(
                f"{tablo}.{sutun} içinde yalnızca büyük/küçük harf (ya da İ/ı) farkıyla ayrılan kayıtlar var: {ayrinti}. "
                f"Birini yeniden adlandırın (ya da kullanılmıyorsa silin), sonra migrasyonu yeniden çalıştırın."
            )
    for tablo, sutun, indeks in AD_INDEKSLERI:
        op.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS {indeks} ON {tablo} ({ad_anahtari_sql(sutun)})")


def downgrade():
    for _tablo, _sutun, indeks in AD_INDEKSLERI:
        op.execute(f"DROP INDEX IF EXISTS {indeks}")
    op.execute("ALTER TABLE randevular DROP CONSTRAINT IF EXISTS ck_randevular_durum")
    op.execute("ALTER TABLE randevular ALTER COLUMN durum DROP NOT NULL")
    for tablo in CIHAZ_TABLOLARI:
        op.execute(f"ALTER TABLE {tablo} ALTER COLUMN cihaz_id DROP NOT NULL")
