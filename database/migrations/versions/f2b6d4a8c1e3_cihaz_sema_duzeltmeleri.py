"""Cihaz yaşam döngüsü şema düzeltmeleri

Revision ID: f2b6d4a8c1e3
Revises: e7c4b1d9a603
Create Date: 2026-11-17 15:00:00.000000

1. cihaz_arizalari: ariza_baslik ve aciliyet sütunları eklenir. Şimdiye kadar ikisi de
   "[Aciliyet] Başlık - Açıklama" biçiminde ariza_aciklamasi içine gömülüyordu ve '-' içeren
   başlıklar ("Wi-Fi") listede yanlış bölünüyordu. Mevcut kayıtlar eski ayrıştırma kuralıyla
   yeni sütunlara taşınır; ariza_aciklamasi artık yalnızca açıklamayı tutar.
2. cihaz_bakim_planlari: periyot/uyarı CHECK kısıtları ve "aynı cihaz + aynı tür tek aktif plan"
   kuralı veritabanı düzeyinde de uygulanır. Mevcut veride aynı türde birden fazla aktif plan
   varsa en eski plan aktif kalır, diğerleri pasife alınır.
3. cihaz_bakimlari / cihaz_kalibrasyonlari: bitiş >= başlangıç ve maliyet >= 0 kısıtları.
   Kısıtlar NOT VALID eklenir: yeni ve değiştirilen satırlar denetlenir, eski bozuk satırlar
   migrasyonu durdurmaz.
4. cihaz_takip_parametreleri: hiçbir yerde kullanılmadığı için kaldırılır.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "f2b6d4a8c1e3"
down_revision: Union[str, Sequence[str], None] = "e7c4b1d9a603"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ACILIYETLER = ("Düşük", "Orta", "Yüksek", "Kritik")


def _eski_metni_ayir(tam_metin):
    """Eski sunucu kuralı: '[Aciliyet] Başlık - Açıklama' -> (aciliyet, başlık, açıklama)."""
    tam_metin = tam_metin or ""
    aciliyet, baslik, aciklama = "Orta", tam_metin, tam_metin
    if tam_metin.startswith("[") and "]" in tam_metin:
        ham, kalan = tam_metin.split("]", 1)
        ham = ham.replace("[", "").strip()
        kalan = kalan.strip()
        aciliyet = ham if ham in ACILIYETLER else "Orta"
        if "-" in kalan:
            baslik, aciklama = (p.strip() for p in kalan.split("-", 1))
        else:
            baslik, aciklama = kalan, ""
    baslik = (baslik or "").strip()[:150] or "Başlıksız arıza"
    return aciliyet, baslik, aciklama


def upgrade():
    # 1. Arıza başlığı ve aciliyeti
    op.execute("ALTER TABLE cihaz_arizalari ADD COLUMN ariza_baslik VARCHAR(150)")
    op.execute("ALTER TABLE cihaz_arizalari ADD COLUMN aciliyet VARCHAR(20) NOT NULL DEFAULT 'Orta'")
    baglanti = op.get_bind()
    for ariza_id, metin in baglanti.exec_driver_sql(
        "SELECT ariza_id, ariza_aciklamasi FROM cihaz_arizalari"
    ).fetchall():
        aciliyet, baslik, aciklama = _eski_metni_ayir(metin)
        baglanti.exec_driver_sql(
            "UPDATE cihaz_arizalari SET aciliyet = %s, ariza_baslik = %s, ariza_aciklamasi = %s "
            "WHERE ariza_id = %s",
            (aciliyet, baslik, aciklama, ariza_id),
        )
    op.execute("ALTER TABLE cihaz_arizalari ALTER COLUMN ariza_baslik SET NOT NULL")
    op.execute(
        "ALTER TABLE cihaz_arizalari ADD CONSTRAINT ck_cihaz_arizalari_aciliyet "
        "CHECK (aciliyet IN ('Düşük', 'Orta', 'Yüksek', 'Kritik'))"
    )

    # 2. Bakım planları
    op.execute(
        "ALTER TABLE cihaz_bakim_planlari ADD CONSTRAINT ck_cihaz_bakim_planlari_periyot "
        "CHECK (periyot_gun BETWEEN 1 AND 3650) NOT VALID"
    )
    op.execute(
        "ALTER TABLE cihaz_bakim_planlari ADD CONSTRAINT ck_cihaz_bakim_planlari_uyari "
        "CHECK (uyari_suresi_gun IS NULL OR (uyari_suresi_gun >= 0 AND uyari_suresi_gun <= periyot_gun)) NOT VALID"
    )
    op.execute(
        """
        UPDATE cihaz_bakim_planlari p SET aktif_mi = FALSE
        WHERE p.aktif_mi IS NOT FALSE AND EXISTS (
            SELECT 1 FROM cihaz_bakim_planlari d
            WHERE d.cihaz_id = p.cihaz_id AND LOWER(d.gorev_turu) = LOWER(p.gorev_turu)
              AND d.aktif_mi IS NOT FALSE AND d.plan_id < p.plan_id)
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX ux_cihaz_bakim_planlari_aktif_tur "
        "ON cihaz_bakim_planlari (cihaz_id, LOWER(gorev_turu)) WHERE aktif_mi IS NOT FALSE"
    )

    # 3. Bakım ve kalibrasyon
    op.execute(
        "ALTER TABLE cihaz_bakimlari ADD CONSTRAINT ck_cihaz_bakimlari_tarih_sirasi "
        "CHECK (bakim_baslangic_tarihi IS NULL OR bakim_bitis_tarihi IS NULL "
        "OR bakim_bitis_tarihi >= bakim_baslangic_tarihi) NOT VALID"
    )
    op.execute(
        "ALTER TABLE cihaz_bakimlari ADD CONSTRAINT ck_cihaz_bakimlari_maliyet "
        "CHECK (maliyet IS NULL OR maliyet >= 0) NOT VALID"
    )
    op.execute(
        "ALTER TABLE cihaz_kalibrasyonlari ADD CONSTRAINT ck_cihaz_kalibrasyonlari_tarih_sirasi "
        "CHECK (kalibrasyon_baslangic_tarihi IS NULL OR kalibrasyon_bitis_tarihi IS NULL "
        "OR kalibrasyon_bitis_tarihi >= kalibrasyon_baslangic_tarihi) NOT VALID"
    )

    # 4. Kullanılmayan tablo
    op.execute("DROP TABLE IF EXISTS cihaz_takip_parametreleri")


def downgrade():
    op.execute(
        """
        CREATE TABLE cihaz_takip_parametreleri (
            parametre_id SERIAL PRIMARY KEY,
            cihaz_id INT REFERENCES cihazlar(cihaz_id),
            parametre_adi VARCHAR(100) NOT NULL,
            parametre_degeri VARCHAR(100) NOT NULL,
            birim VARCHAR(50),
            son_guncelleme TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute("CREATE INDEX ix_cihaz_takip_parametreleri_cihaz_id ON cihaz_takip_parametreleri (cihaz_id)")

    op.execute("ALTER TABLE cihaz_kalibrasyonlari DROP CONSTRAINT IF EXISTS ck_cihaz_kalibrasyonlari_tarih_sirasi")
    op.execute("ALTER TABLE cihaz_bakimlari DROP CONSTRAINT IF EXISTS ck_cihaz_bakimlari_maliyet")
    op.execute("ALTER TABLE cihaz_bakimlari DROP CONSTRAINT IF EXISTS ck_cihaz_bakimlari_tarih_sirasi")

    op.execute("DROP INDEX IF EXISTS ux_cihaz_bakim_planlari_aktif_tur")
    op.execute("ALTER TABLE cihaz_bakim_planlari DROP CONSTRAINT IF EXISTS ck_cihaz_bakim_planlari_uyari")
    op.execute("ALTER TABLE cihaz_bakim_planlari DROP CONSTRAINT IF EXISTS ck_cihaz_bakim_planlari_periyot")

    # Arıza: başlık ve aciliyet tekrar "[Aciliyet] Başlık - Açıklama" biçimine gömülür.
    op.execute(
        "UPDATE cihaz_arizalari SET ariza_aciklamasi = "
        "'[' || aciliyet || '] ' || ariza_baslik || ' - ' || ariza_aciklamasi"
    )
    op.execute("ALTER TABLE cihaz_arizalari DROP CONSTRAINT IF EXISTS ck_cihaz_arizalari_aciliyet")
    op.execute("ALTER TABLE cihaz_arizalari DROP COLUMN aciliyet")
    op.execute("ALTER TABLE cihaz_arizalari DROP COLUMN ariza_baslik")
