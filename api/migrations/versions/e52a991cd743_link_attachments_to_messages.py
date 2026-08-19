"""link attachments to conversation messages

Revision ID: e52a991cd743
Revises: d91e7c2a4b10
"""

from alembic import op
import sqlalchemy as sa


revision = "e52a991cd743"
down_revision = "d91e7c2a4b10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "conversation_attachments",
        sa.Column(
            "message_id",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.create_foreign_key(
        "fk_conversation_attachments_message_id",
        "conversation_attachments",
        "conversation_messages",
        ["message_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_index(
        "ix_conversation_attachments_message_id",
        "conversation_attachments",
        ["message_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_conversation_attachments_message_id",
        table_name="conversation_attachments",
    )

    op.drop_constraint(
        "fk_conversation_attachments_message_id",
        "conversation_attachments",
        type_="foreignkey",
    )

    op.drop_column(
        "conversation_attachments",
        "message_id",
    )
