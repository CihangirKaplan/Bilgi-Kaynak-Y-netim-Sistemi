"""asistan rolunu proje_asistani ile birlestir

Revision ID: fc6f9347b3b7
Revises: ee12c8c2b5fb
Create Date: 2026-10-22 14:45:38.045067

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fc6f9347b3b7'
down_revision: Union[str, Sequence[str], None] = 'ee12c8c2b5fb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    hedef = conn.execute(
        sa.text("SELECT rol_id FROM roller WHERE rol_adi = 'PROJE_ASISTANI'")
    ).scalar()
    if hedef is None:
        raise RuntimeError("PROJE_ASISTANI rolü bulunamadı, migration durduruldu.")

    kaynak = conn.execute(
        sa.text("SELECT rol_id FROM roller WHERE rol_adi = 'ASISTAN'")
    ).scalar()
    if kaynak is None:
        return  # ASISTAN rolü zaten yok, yapılacak bir şey yok

    conn.execute(
        sa.text("UPDATE kullanicilar SET rol_id = :hedef WHERE rol_id = :kaynak"),
        {"hedef": hedef, "kaynak": kaynak},
    )
    conn.execute(sa.text("DELETE FROM rol_izinleri WHERE rol_id = :kaynak"), {"kaynak": kaynak})
    conn.execute(sa.text("DELETE FROM roller WHERE rol_id = :kaynak"), {"kaynak": kaynak})


def downgrade() -> None:
    # Tek yönlü veri düzeltmesi: ASISTAN rolü boş olarak yeniden açılır,
    # kullanıcılar otomatik geri taşınamaz ve rol_id eskisiyle aynı olmayabilir.
    op.execute("INSERT INTO roller (rol_adi) VALUES ('ASISTAN')")
