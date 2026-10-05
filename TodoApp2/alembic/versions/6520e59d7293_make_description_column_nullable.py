"""Create the base schema when it is not already present.

Revision ID: 6520e59d7293
Revises:
Create Date: 2024-04-02 19:31:50.524407
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "6520e59d7293"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    existing_tables = set(sa.inspect(op.get_bind()).get_table_names())

    if "users" not in existing_tables:
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("email", sa.String(), nullable=True),
            sa.Column("username", sa.String(), nullable=True),
            sa.Column("first_name", sa.String(), nullable=True),
            sa.Column("last_name", sa.String(), nullable=True),
            sa.Column("hashed_password", sa.String(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_users_id", "users", ["id"], unique=False)
        op.create_index("ix_users_email", "users", ["email"], unique=True)
        op.create_index("ix_users_username", "users", ["username"], unique=True)

    if "todos" not in existing_tables:
        op.create_table(
            "todos",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(), nullable=True),
            sa.Column("description", sa.String(), nullable=True),
            sa.Column("priority", sa.Integer(), nullable=True),
            sa.Column("complete", sa.Boolean(), nullable=True),
            sa.Column("owner_id", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_todos_id", "todos", ["id"], unique=False)


def downgrade() -> None:
    pass
