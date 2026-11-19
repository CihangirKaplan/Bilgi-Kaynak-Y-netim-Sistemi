"""Migration zincirini tek uca bağla (#407 ve #409 paralel birleştirildi)

Revision ID: a4c9e2d7b315
Revises: d7a2c5e8f193, d1e6a3b9c847
Create Date: 2026-11-19 10:00:00.000000

#409 (d7a2c5e8f193, performans indeksleri) ve #407 (d1e6a3b9c847, pasif psikolog danışanları) aynı revizyondan (c2e5a9d4b681)
dallandığı için "Multiple head revisions" oluştu. Bu revizyon yalnızca iki ucu birleştirir; şemada değişiklik yapmaz.
"""
from typing import Sequence, Union

revision: str = "a4c9e2d7b315"
down_revision: Union[str, Sequence[str], None] = ("d7a2c5e8f193", "d1e6a3b9c847")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    pass


def downgrade():
    pass
