"""personel tablosunu kullanicilar ile birlestir (personel adi geriye uyumlu gorunum olarak kalir)

personel, kullanicilar'in birebir uzantisiydi (kullanici_id UNIQUE NOT NULL; ek bilgi yalniz personel_kodu) ve ikinci bir aktif_mi
tasiyordu; iki bayragin birbirinden kopmasi (ornegin personel pasif, kullanici aktif) ve "kullanici var, personel yok" ara durumu
hata kaynagiydi. Bu migration:

1. kullanicilar'a personel_id (ESKI personel kimligi aynen korunur), personel_kodu ve personel_kaydi_tarihi ekler ve doldurur.
   Hicbir randevu/danisan/rezervasyon/etkinlik/denetim kaydinin degeri degismez: yalnizca baglantilarin hedefi degisir.
2. personel_id'ye bagli 4 yabanci anahtari kullanicilar(personel_id)'ye yonlendirir.
3. Tek aktiflik bayragi: kullanicilar.aktif_mi. Eskiden personel.aktif_mi ile kullanici.aktif_mi farkliysa etkin durum (ikisi de aktif)
   korunur: ikisinden biri pasifse kullanici pasif olur ve denetim kaydina yazilir.
4. personel tablosunu kaldirir; yerine ayni adli, yazilabilir (INSTEAD OF tetikleyicili) gorunum koyar. Boylece mevcut sorgular, betikler
   ve testler degismeden calisir.

Geri alma (downgrade) tabloyu ayni kimliklerle yeniden kurar.

Revision ID: b9d4f7a2c613
Revises: e5a2c8d1f396
Create Date: 2026-11-19 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "b9d4f7a2c613"
down_revision: Union[str, Sequence[str], None] = "e5a2c8d1f396"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (tablo, sutun, kisit adi, ek kural)
BAGLANTILAR = [
    ("cihaz_rezervasyonlari", "rezervasyonu_yapan_personel_id", "cihaz_rezervasyonlari_rezervasyonu_yapan_personel_id_fkey", ""),
    ("danisan_kodlari", "olusturan_psikolog_id", "fk_danisankodlari_personel", " ON DELETE SET NULL ON UPDATE SET NULL"),
    ("oda_etkinlikleri", "organize_eden_personel_id", "oda_etkinlikleri_organize_eden_personel_id_fkey", ""),
    ("randevular", "psikolog_id", "randevular_psikolog_id_fkey", ""),
]


def upgrade():
    for tablo, sutun, kisit, _ in BAGLANTILAR:
        op.execute(f"ALTER TABLE {tablo} DROP CONSTRAINT {kisit};")

    op.execute("ALTER TABLE kullanicilar ADD COLUMN personel_id integer, ADD COLUMN personel_kodu varchar(50), ADD COLUMN personel_kaydi_tarihi timestamp;")
    op.execute(
        """
        UPDATE kullanicilar k
        SET personel_id = p.personel_id, personel_kodu = p.personel_kodu, personel_kaydi_tarihi = p.olusturulma_tarihi
        FROM personel p WHERE p.kullanici_id = k.kullanici_id;
        """
    )
    # Tek aktiflik bayragi: etkin durum (ikisi de aktif) korunur; degisen hesaplar denetim kaydina yazilir.
    op.execute(
        """
        INSERT INTO denetim_kayitlari (kullanici_id, olay_turu, hedef_tablo, hedef_kayit_id, ayrinti)
        SELECT NULL, 'UPDATE', 'kullanicilar', k.kullanici_id,
               jsonb_build_object('neden', 'personel ve kullanici aktiflik bayraklari birlestirildi',
                                  'onceki', jsonb_build_object('kullanici_aktif_mi', k.aktif_mi, 'personel_aktif_mi', p.aktif_mi),
                                  'yeni', jsonb_build_object('aktif_mi', FALSE))
        FROM kullanicilar k JOIN personel p ON p.kullanici_id = k.kullanici_id
        WHERE k.aktif_mi AND NOT p.aktif_mi;
        """
    )
    op.execute("UPDATE kullanicilar k SET aktif_mi = FALSE FROM personel p WHERE p.kullanici_id = k.kullanici_id AND NOT p.aktif_mi;")

    op.execute(
        """
        ALTER TABLE kullanicilar
            ADD CONSTRAINT kullanicilar_personel_id_key UNIQUE (personel_id),
            ADD CONSTRAINT kullanicilar_personel_kodu_key UNIQUE (personel_kodu),
            ADD CONSTRAINT kullanicilar_personel_alanlari_birlikte CHECK ((personel_id IS NULL) = (personel_kodu IS NULL));
        """
    )

    # Sayac korunur (yeni personel kimlikleri kaldigi yerden devam eder); tablo ile birlikte silinmesin.
    op.execute("ALTER SEQUENCE personel_personel_id_seq OWNED BY NONE;")
    op.execute("DROP TABLE personel;")

    op.execute(
        """
        CREATE VIEW personel AS
        SELECT personel_id, kullanici_id, personel_kodu, aktif_mi, personel_kaydi_tarihi AS olusturulma_tarihi
        FROM kullanicilar WHERE personel_id IS NOT NULL;
        """
    )
    op.execute(
        """
        CREATE FUNCTION personel_gorunumu_yaz() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                UPDATE kullanicilar
                SET personel_id = nextval('personel_personel_id_seq'),
                    personel_kodu = NEW.personel_kodu,
                    personel_kaydi_tarihi = COALESCE(NEW.olusturulma_tarihi, CURRENT_TIMESTAMP),
                    aktif_mi = COALESCE(NEW.aktif_mi, aktif_mi)
                WHERE kullanici_id = NEW.kullanici_id AND personel_id IS NULL
                RETURNING personel_id, personel_kaydi_tarihi, aktif_mi INTO NEW.personel_id, NEW.olusturulma_tarihi, NEW.aktif_mi;
                IF NOT FOUND THEN
                    IF EXISTS (SELECT 1 FROM kullanicilar WHERE kullanici_id = NEW.kullanici_id) THEN
                        RAISE EXCEPTION 'duplicate key value violates unique constraint "personel_kullanici_id_key"'
                            USING ERRCODE = 'unique_violation', CONSTRAINT = 'personel_kullanici_id_key';
                    END IF;
                    RAISE EXCEPTION 'insert or update on table "personel" violates foreign key constraint "personel_kullanici_id_fkey"'
                        USING ERRCODE = 'foreign_key_violation', CONSTRAINT = 'personel_kullanici_id_fkey';
                END IF;
                RETURN NEW;
            ELSIF TG_OP = 'UPDATE' THEN
                IF NEW.personel_id IS DISTINCT FROM OLD.personel_id OR NEW.kullanici_id IS DISTINCT FROM OLD.kullanici_id THEN
                    RAISE EXCEPTION 'personel_id ve kullanici_id degistirilemez';
                END IF;
                UPDATE kullanicilar SET personel_kodu = NEW.personel_kodu, aktif_mi = NEW.aktif_mi WHERE personel_id = OLD.personel_id;
                RETURN NEW;
            ELSE
                UPDATE kullanicilar SET personel_id = NULL, personel_kodu = NULL, personel_kaydi_tarihi = NULL WHERE personel_id = OLD.personel_id;
                RETURN OLD;
            END IF;
        END;
        $$;
        """
    )
    op.execute("CREATE TRIGGER personel_gorunumu_yaz INSTEAD OF INSERT OR UPDATE OR DELETE ON personel FOR EACH ROW EXECUTE FUNCTION personel_gorunumu_yaz();")

    for tablo, sutun, kisit, ek in BAGLANTILAR:
        op.execute(f"ALTER TABLE {tablo} ADD CONSTRAINT {kisit} FOREIGN KEY ({sutun}) REFERENCES kullanicilar(personel_id){ek};")


def downgrade():
    for tablo, sutun, kisit, _ in BAGLANTILAR:
        op.execute(f"ALTER TABLE {tablo} DROP CONSTRAINT {kisit};")
    op.execute("DROP TRIGGER personel_gorunumu_yaz ON personel;")
    op.execute("DROP FUNCTION personel_gorunumu_yaz();")
    op.execute("DROP VIEW personel;")
    op.execute(
        """
        CREATE TABLE personel (
            personel_id integer NOT NULL,
            kullanici_id integer NOT NULL,
            personel_kodu varchar(50) NOT NULL,
            aktif_mi boolean NOT NULL DEFAULT TRUE,
            olusturulma_tarihi timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT personel_pkey PRIMARY KEY (personel_id),
            CONSTRAINT personel_kullanici_id_key UNIQUE (kullanici_id),
            CONSTRAINT personel_personel_kodu_key UNIQUE (personel_kodu),
            CONSTRAINT personel_kullanici_id_fkey FOREIGN KEY (kullanici_id) REFERENCES kullanicilar(kullanici_id)
        );
        """
    )
    op.execute(
        """
        INSERT INTO personel (personel_id, kullanici_id, personel_kodu, aktif_mi, olusturulma_tarihi)
        SELECT personel_id, kullanici_id, personel_kodu, aktif_mi, COALESCE(personel_kaydi_tarihi, CURRENT_TIMESTAMP)
        FROM kullanicilar WHERE personel_id IS NOT NULL;
        """
    )
    op.execute("ALTER TABLE personel ALTER COLUMN personel_id SET DEFAULT nextval('personel_personel_id_seq');")
    op.execute("ALTER SEQUENCE personel_personel_id_seq OWNED BY personel.personel_id;")
    op.execute(
        """
        ALTER TABLE kullanicilar
            DROP CONSTRAINT kullanicilar_personel_alanlari_birlikte,
            DROP CONSTRAINT kullanicilar_personel_kodu_key,
            DROP CONSTRAINT kullanicilar_personel_id_key,
            DROP COLUMN personel_kaydi_tarihi, DROP COLUMN personel_kodu, DROP COLUMN personel_id;
        """
    )
    for tablo, sutun, kisit, ek in BAGLANTILAR:
        op.execute(f"ALTER TABLE {tablo} ADD CONSTRAINT {kisit} FOREIGN KEY ({sutun}) REFERENCES personel(personel_id){ek.replace(' ON UPDATE SET NULL', '')};")
