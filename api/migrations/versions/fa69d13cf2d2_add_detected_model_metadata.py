"""add detected model metadata

Revision ID: fa69d13cf2d2
Revises: a62494827c3f
Create Date: 2026-08-16 11:50:36.891410

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fa69d13cf2d2'
down_revision: Union[str, Sequence[str], None] = 'a62494827c3f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "model_requests",
        sa.Column(
            "artifact_format",
            sa.String(length=50),
            nullable=True,
        ),
    )

    op.add_column(
        "model_requests",
        sa.Column(
            "architecture",
            sa.String(length=100),
            nullable=True,
        ),
    )

    op.add_column(
        "model_requests",
        sa.Column(
            "quantization",
            sa.String(length=100),
            nullable=True,
        ),
    )

    op.create_index(
        op.f(
            "ix_model_requests_artifact_format"
        ),
        "model_requests",
        ["artifact_format"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f(
            "ix_model_requests_artifact_format"
        ),
        table_name="model_requests",
    )

    op.drop_column(
        "model_requests",
        "quantization",
    )

    op.drop_column(
        "model_requests",
        "architecture",
    )

    op.drop_column(
        "model_requests",
        "artifact_format",
    )
