"""Add due dates and completion timestamps.

Revision ID: f4e31d9ab271
Revises: 8c4b752aa9ef
Create Date: 2026-10-05
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f4e31d9ab271"
down_revision: Union[str, None] = "8c4b752aa9ef"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    existing_columns = {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("todos")
    }
    if "completed_at" not in existing_columns:
        op.add_column("todos", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
    if "due_date" not in existing_columns:
        op.add_column("todos", sa.Column("due_date", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("todos", "due_date")
    op.drop_column("todos", "completed_at")