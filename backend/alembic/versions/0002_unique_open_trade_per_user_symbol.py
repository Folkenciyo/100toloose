"""Unique open trade per user+symbol

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Partial unique index: only one OPEN trade allowed per (user_id, symbol)
    op.create_index(
        "uq_trades_user_symbol_open",
        "trades",
        ["user_id", "symbol"],
        unique=True,
        postgresql_where=sa.text("status = 'open'"),
    )


def downgrade() -> None:
    op.drop_index("uq_trades_user_symbol_open", table_name="trades")
