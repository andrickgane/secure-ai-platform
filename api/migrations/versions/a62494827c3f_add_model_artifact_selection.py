"""add model artifact selection

Revision ID: a62494827c3f
Revises: 76f6215f77a7
Create Date: 2026-08-16 02:24:01.884303

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a62494827c3f'
down_revision: Union[str, Sequence[str], None] = '76f6215f77a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "model_requests",
        sa.Column(
            "artifact_patterns",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
    )

    op.add_column(
        "model_requests",
        sa.Column(
            "download_complete_repository",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column(
        "model_requests",
        "download_complete_repository",
    )

    op.drop_column(
        "model_requests",
        "artifact_patterns",
    )
