"""cihazlar.durum sütununu cihaz_durumu enum tipine geri getir (onarım)

Revision ID: c5a2e8f1d739
Revises: b3e8f1a5d472
Create Date: 2026-11-18 11:00:00.000000

Bazı veritabanlarında cihazlar.durum sütunu elle VARCHAR(50)'ye çevrilmiş ve varsayılanı 'Kullanılabilir' yapılmıştı;
migrasyonların kurduğu şema ise cihaz_durumu enum tipidir (varsayılan 'Kullanima_Hazir'). Bu fark, durum yazmadan eklenen
cihazların uygulamanın tanımadığı 'Kullanılabilir' değerini almasına ve yanlış yazılmış durumların kabul edilmesine yol açar.

Bu migrasyon yalnızca sütun hâlâ metin tipindeyse çalışır; zaten enum olan veritabanlarında (CI dahil) hiçbir şey yapmaz.
Eski yazımlar ('Kullanılabilir', 'Kullanıma Hazır', 'kullanima_hazir' gibi) tanınan değerlere çevrilir. Tanınmayan bir değer
varsa hiçbir değişiklik yapılmadan açık bir hatayla durulur (değer listelenir, düzeltilip komut yeniden çalıştırılır).
"""
import unicodedata
from typing import Sequence, Union

from alembic import op

revision: str = "c5a2e8f1d739"
down_revision: Union[str, Sequence[str], None] = "b3e8f1a5d472"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

GECERLI_DURUMLAR = (
    "Kullanima_Hazir", "Rezerve", "Kullanimda", "Arizali", "Bakimda", "Kalibrasyonda", "Kullanim_Disi",
)


def _anahtar(deger):
    """Büyük/küçük harf, Türkçe karakter, boşluk ve alt çizgi farklarını yok sayan karşılaştırma anahtarı."""
    metin = unicodedata.normalize("NFKD", str(deger)).replace("ı", "i")
    metin = "".join(k for k in metin if not unicodedata.combining(k))
    return "".join(k for k in metin.lower() if k.isalnum())


ESLEME = {_anahtar(d): d for d in GECERLI_DURUMLAR}
ESLEME[_anahtar("Kullanılabilir")] = "Kullanima_Hazir"      # elle verilen eski varsayılan


def durumu_coz(deger):
    """Eski metin değerini enum değerine çevirir; tanınmıyorsa None."""
    return ESLEME.get(_anahtar(deger))


def upgrade():
    baglanti = op.get_bind()
    tip = baglanti.exec_driver_sql(
        "SELECT data_type FROM information_schema.columns "
        "WHERE table_schema = current_schema() AND table_name = 'cihazlar' AND column_name = 'durum'"
    ).scalar()
    if tip != "character varying" and tip != "text":
        return                                              # zaten enum: yapılacak bir şey yok

    mevcutlar = [s[0] for s in baglanti.exec_driver_sql(
        "SELECT DISTINCT durum FROM cihazlar WHERE durum IS NOT NULL").fetchall()]
    tanimsiz = sorted(d for d in mevcutlar if durumu_coz(d) is None)
    if tanimsiz:
        raise RuntimeError(
            "cihazlar.durum içinde tanınmayan değerler var: " + ", ".join(repr(d) for d in tanimsiz)
            + ". Bu cihazların durumunu elle Kullanima_Hazir, Rezerve, Kullanimda, Arizali, Bakimda, Kalibrasyonda "
              "ya da Kullanim_Disi olarak düzeltip migrasyonu yeniden çalıştırın."
        )
    for eski in mevcutlar:
        yeni = durumu_coz(eski)
        if yeni != eski:
            baglanti.exec_driver_sql("UPDATE cihazlar SET durum = %s WHERE durum = %s", (yeni, eski))

    op.execute("ALTER TABLE cihazlar ALTER COLUMN durum DROP DEFAULT")
    op.execute("ALTER TABLE cihazlar ALTER COLUMN durum TYPE cihaz_durumu USING durum::cihaz_durumu")
    op.execute("ALTER TABLE cihazlar ALTER COLUMN durum SET DEFAULT 'Kullanima_Hazir'")


def downgrade():
    # Bir onarım migrasyonudur: şemayı bilerek bozuk eski hâline döndürmez (değerler de geri çevrilemez).
    pass
