"""add custom profiles

Revision ID: c8d4f6a1b203
Revises: fa69d13cf2d2
Create Date: 2026-08-17
"""

from typing import (
    Sequence,
    Union,
)

from alembic import op
import sqlalchemy as sa


revision: str = (
    "c8d4f6a1b203"
)

down_revision: Union[
    str,
    Sequence[str],
    None,
] = "fa69d13cf2d2"

branch_labels: Union[
    str,
    Sequence[str],
    None,
] = None

depends_on: Union[
    str,
    Sequence[str],
    None,
] = None


def upgrade() -> None:
    op.create_table(
        "profiles",

        sa.Column(
            "id",
            sa.Integer(),
            autoincrement=True,
            nullable=False,
        ),

        sa.Column(
            "name",
            sa.String(
                length=63
            ),
            nullable=False,
        ),

        sa.Column(
            "display_name",
            sa.String(
                length=120
            ),
            nullable=False,
        ),

        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
        ),

        sa.Column(
            "category",
            sa.String(
                length=64
            ),
            nullable=False,
        ),

        sa.Column(
            "base_profile",
            sa.String(
                length=63
            ),
            nullable=False,
        ),

        sa.Column(
            "overrides",
            sa.JSON(),
            nullable=False,
        ),

        sa.Column(
            "owner_id",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(
                timezone=True
            ),
            server_default=(
                sa.text(
                    "now()"
                )
            ),
            nullable=False,
        ),

        sa.Column(
            "updated_at",
            sa.DateTime(
                timezone=True
            ),
            server_default=(
                sa.text(
                    "now()"
                )
            ),
            nullable=False,
        ),

        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),

        sa.PrimaryKeyConstraint(
            "id"
        ),

        sa.UniqueConstraint(
            "name"
        ),
    )

    op.create_index(
        op.f(
            "ix_profiles_name"
        ),
        "profiles",
        ["name"],
        unique=True,
    )

    op.create_index(
        op.f(
            "ix_profiles_base_profile"
        ),
        "profiles",
        ["base_profile"],
        unique=False,
    )

    op.create_index(
        op.f(
            "ix_profiles_owner_id"
        ),
        "profiles",
        ["owner_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f(
            "ix_profiles_owner_id"
        ),
        table_name="profiles",
    )

    op.drop_index(
        op.f(
            "ix_profiles_base_profile"
        ),
        table_name="profiles",
    )

    op.drop_index(
        op.f(
            "ix_profiles_name"
        ),
        table_name="profiles",
    )

    op.drop_table(
        "profiles"
    )
