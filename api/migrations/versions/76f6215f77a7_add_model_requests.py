"""add model requests

Revision ID: 76f6215f77a7
Revises: 9dfe09ba4419
Create Date: 2026-08-13 09:54:41.295025
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# ==========================================================
# REVISION IDENTIFIERS
# ==========================================================

revision: str = "76f6215f77a7"

down_revision: Union[
    str,
    Sequence[str],
    None,
] = "9dfe09ba4419"

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


# ==========================================================
# UPGRADE
# ==========================================================

def upgrade() -> None:
    """
    Add persistent model import requests.

    Important:
    This migration intentionally does NOT modify
    the existing audit_events table.
    """

    op.create_table(
        "model_requests",

        sa.Column(
            "id",
            sa.Integer(),
            autoincrement=True,
            nullable=False,
        ),

        sa.Column(
            "provider",
            sa.String(
                length=50
            ),
            nullable=False,
        ),

        sa.Column(
            "repository",
            sa.String(
                length=255
            ),
            nullable=False,
        ),

        sa.Column(
            "revision",
            sa.String(
                length=255
            ),
            nullable=False,
        ),

        sa.Column(
            "requested_profile",
            sa.String(
                length=100
            ),
            nullable=True,
        ),

        sa.Column(
            "purpose",
            sa.Text(),
            nullable=True,
        ),

        sa.Column(
            "status",
            sa.String(
                length=50
            ),
            nullable=False,
        ),

        sa.Column(
            "status_message",
            sa.Text(),
            nullable=True,
        ),

        sa.Column(
            "catalog_model_id",
            sa.String(
                length=150
            ),
            nullable=True,
        ),

        sa.Column(
            "artifact_reference",
            sa.String(
                length=1024
            ),
            nullable=True,
        ),

        sa.Column(
            "artifact_digest",
            sa.String(
                length=255
            ),
            nullable=True,
        ),

        sa.Column(
            "requested_by_user_id",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(
                timezone=True
            ),
            nullable=False,
        ),

        sa.Column(
            "updated_at",
            sa.DateTime(
                timezone=True
            ),
            nullable=False,
        ),

        sa.ForeignKeyConstraint(
            [
                "requested_by_user_id"
            ],
            [
                "users.id"
            ],
            ondelete="RESTRICT",
        ),

        sa.PrimaryKeyConstraint(
            "id"
        ),
    )

    # ======================================================
    # INDEXES
    # ======================================================

    op.create_index(
        op.f(
            "ix_model_requests_catalog_model_id"
        ),
        "model_requests",
        [
            "catalog_model_id"
        ],
        unique=False,
    )

    op.create_index(
        op.f(
            "ix_model_requests_repository"
        ),
        "model_requests",
        [
            "repository"
        ],
        unique=False,
    )

    op.create_index(
        op.f(
            "ix_model_requests_requested_by_user_id"
        ),
        "model_requests",
        [
            "requested_by_user_id"
        ],
        unique=False,
    )

    op.create_index(
        op.f(
            "ix_model_requests_status"
        ),
        "model_requests",
        [
            "status"
        ],
        unique=False,
    )


# ==========================================================
# DOWNGRADE
# ==========================================================

def downgrade() -> None:
    """
    Remove model request persistence.

    Existing application tables are left untouched.
    """

    op.drop_index(
        op.f(
            "ix_model_requests_status"
        ),
        table_name="model_requests",
    )

    op.drop_index(
        op.f(
            "ix_model_requests_requested_by_user_id"
        ),
        table_name="model_requests",
    )

    op.drop_index(
        op.f(
            "ix_model_requests_repository"
        ),
        table_name="model_requests",
    )

    op.drop_index(
        op.f(
            "ix_model_requests_catalog_model_id"
        ),
        table_name="model_requests",
    )

    op.drop_table(
        "model_requests"
    )
