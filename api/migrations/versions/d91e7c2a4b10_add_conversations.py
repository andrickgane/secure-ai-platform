"""add conversations messages and attachments

Revision ID: d91e7c2a4b10
Revises: c8d4f6a1b203
"""

from alembic import op
import sqlalchemy as sa


revision = "d91e7c2a4b10"
down_revision = "c8d4f6a1b203"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conversations",

        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            autoincrement=True,
        ),

        sa.Column(
            "owner_id",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "title",
            sa.String(length=200),
            nullable=False,
        ),

        sa.Column(
            "deployment_name",
            sa.String(length=63),
            nullable=True,
        ),

        sa.Column(
            "model",
            sa.String(length=255),
            nullable=True,
        ),

        sa.Column(
            "profile",
            sa.String(length=255),
            nullable=True,
        ),

        sa.Column(
            "runtime",
            sa.String(length=255),
            nullable=True,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text(
                "CURRENT_TIMESTAMP"
            ),
        ),

        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text(
                "CURRENT_TIMESTAMP"
            ),
        ),

        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
    )

    op.create_index(
        "ix_conversations_owner_id",
        "conversations",
        ["owner_id"],
    )

    op.create_index(
        "ix_conversations_deployment_name",
        "conversations",
        ["deployment_name"],
    )

    op.create_index(
        "ix_conversations_updated_at",
        "conversations",
        ["updated_at"],
    )


    op.create_table(
        "conversation_messages",

        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            autoincrement=True,
        ),

        sa.Column(
            "conversation_id",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "role",
            sa.String(length=16),
            nullable=False,
        ),

        sa.Column(
            "content",
            sa.Text(),
            nullable=False,
        ),

        sa.Column(
            "model",
            sa.String(length=255),
            nullable=True,
        ),

        sa.Column(
            "profile",
            sa.String(length=255),
            nullable=True,
        ),

        sa.Column(
            "runtime",
            sa.String(length=255),
            nullable=True,
        ),

        sa.Column(
            "parameters",
            sa.JSON(),
            nullable=True,
        ),

        sa.Column(
            "prompt_tokens",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "completion_tokens",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "total_tokens",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "latency_ms",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "first_token_latency_ms",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "generation_duration_ms",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "generation_tokens_per_second",
            sa.Float(),
            nullable=True,
        ),

        sa.Column(
            "output_tokens_per_second",
            sa.Float(),
            nullable=True,
        ),

        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text(
                "CURRENT_TIMESTAMP"
            ),
        ),

        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            ondelete="CASCADE",
        ),
    )

    op.create_index(
        "ix_conversation_messages_conversation_id",
        "conversation_messages",
        ["conversation_id"],
    )


    op.create_table(
        "conversation_attachments",

        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            autoincrement=True,
        ),

        sa.Column(
            "conversation_id",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "filename",
            sa.String(length=255),
            nullable=False,
        ),

        sa.Column(
            "media_type",
            sa.String(length=255),
            nullable=False,
        ),

        sa.Column(
            "size_bytes",
            sa.BigInteger(),
            nullable=False,
        ),

        sa.Column(
            "sha256",
            sa.String(length=64),
            nullable=False,
        ),

        sa.Column(
            "content",
            sa.LargeBinary(),
            nullable=False,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text(
                "CURRENT_TIMESTAMP"
            ),
        ),

        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            ondelete="CASCADE",
        ),
    )

    op.create_index(
        "ix_conversation_attachments_conversation_id",
        "conversation_attachments",
        ["conversation_id"],
    )

    op.create_index(
        "ix_conversation_attachments_sha256",
        "conversation_attachments",
        ["sha256"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_conversation_attachments_sha256",
        table_name="conversation_attachments",
    )

    op.drop_index(
        "ix_conversation_attachments_conversation_id",
        table_name="conversation_attachments",
    )

    op.drop_table(
        "conversation_attachments"
    )

    op.drop_index(
        "ix_conversation_messages_conversation_id",
        table_name="conversation_messages",
    )

    op.drop_table(
        "conversation_messages"
    )

    op.drop_index(
        "ix_conversations_updated_at",
        table_name="conversations",
    )

    op.drop_index(
        "ix_conversations_deployment_name",
        table_name="conversations",
    )

    op.drop_index(
        "ix_conversations_owner_id",
        table_name="conversations",
    )

    op.drop_table(
        "conversations"
    )
