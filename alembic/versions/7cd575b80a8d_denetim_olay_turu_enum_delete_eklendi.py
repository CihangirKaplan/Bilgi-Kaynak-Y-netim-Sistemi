"""denetim_olay_turu_enum_delete_eklendi

Revision ID: 7cd575b80a8d
Revises: 5fff9a787871
Create Date: 2026-10-22 10:37:28.281613

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7cd575b80a8d'
down_revision: Union[str, Sequence[str], None] = '5fff9a787871'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # PostgreSQL, ENUM'a değer eklemeyi transaction içinde reddeder.
    # Bu yüzden önce aktif işlemi bitiriyor (COMMIT), sonra kelimeyi ekliyoruz.
    # IF NOT EXISTS ekledik ki senin veritabanında zaten var olduğu için sende çalışırken hata vermesin!
    op.execute("COMMIT")
    op.execute("ALTER TYPE denetim_olay_turu ADD VALUE IF NOT EXISTS 'DELETE'")


def downgrade():
    # PostgreSQL'de bir ENUM tipinden tek bir değeri (DROP VALUE ile) silmek desteklenmez.
    # Tüm tipi silip baştan yaratmak çok riskli olacağı için, 
    # downgrade işlemi bilerek boş bırakılır.
    pass