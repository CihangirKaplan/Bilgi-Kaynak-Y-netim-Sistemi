"""Rol adlarını normalleştir

rol_adi, kodun beklediği BÜYÜK HARFLİ koddur (PSIKOLOG, ADMIN ...); ekranda görünen ad gorunen_ad'dadır.
Bazı eski kurulumlarda ilk altı rol 'Psikolog', 'Admin' gibi yazılmıştı. Kodda büyük harfle yapılan
karşılaştırmalar (psikolog yalnızca kendi randevusunu düzenler, ADMIN korumaları, danışma öğrencisi
kaydı ...) bu veritabanlarında tutmuyordu.

Bu migrasyon yalnızca bilinen eski yazımları koda çevirir; zaten doğru olan veritabanlarında
(örn. migrasyonlardan sıfırdan kurulanlar, CI) hiçbir şey yapmaz. rol_id'ler ve izinler değişmez.

Revision ID: d41c7e0a95b3
Revises: b3f7a1c92d84
Create Date: 2026-11-11

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "d41c7e0a95b3"
down_revision: Union[str, Sequence[str], None] = "b3f7a1c92d84"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (eski yazım, kod)
ESLESMELER = (
    ("Psikolog", "PSIKOLOG"),
    ("Memur", "MEMUR"),
    ("Müdür", "MUDUR"),
    ("Danışma Öğrencisi", "DANISMA_OGRENCISI"),
    ("Proje Asistanı", "PROJE_ASISTANI"),
    ("Admin", "ADMIN"),
)

# 1) Görünen ad boşsa okunur eski adı sakla.
GORUNEN_AD_SORGUSU = (
    "UPDATE roller SET gorunen_ad = rol_adi "
    "WHERE rol_adi <> :yeni AND (rol_adi = :eski OR UPPER(rol_adi) = :yeni) "
    "AND (gorunen_ad IS NULL OR gorunen_ad = '')"
)

# 2) Kodu düzelt. Aynı kod zaten varsa (UNIQUE çakışması) dokunma.
KOD_SORGUSU = (
    "UPDATE roller SET rol_adi = :yeni "
    "WHERE rol_adi <> :yeni AND (rol_adi = :eski OR UPPER(rol_adi) = :yeni) "
    "AND NOT EXISTS (SELECT 1 FROM roller r2 WHERE r2.rol_adi = :yeni)"
)


def upgrade() -> None:
    for eski, yeni in ESLESMELER:
        op.execute(sa.text(GORUNEN_AD_SORGUSU).bindparams(eski=eski, yeni=yeni))
        op.execute(sa.text(KOD_SORGUSU).bindparams(eski=eski, yeni=yeni))


def downgrade() -> None:
    # Bilerek geri alınmaz: eski, tutarsız yazıma dönmenin bir faydası yok.
    pass
