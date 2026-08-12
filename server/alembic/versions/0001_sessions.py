"""create BFF sessions"""

import sqlalchemy as sa
from alembic import op

revision = "0001_sessions"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bff_sessions",
        sa.Column("id_hash", sa.String(length=64), primary_key=True),
        sa.Column("subject", sa.String(length=256), nullable=False),
        sa.Column("encrypted_access_token", sa.Text(), nullable=False),
        sa.Column("encrypted_refresh_token", sa.Text(), nullable=True),
        sa.Column("encrypted_id_token", sa.Text(), nullable=True),
        sa.Column("claims", sa.JSON(), nullable=False),
        sa.Column("csrf_hash", sa.String(length=64), nullable=False),
        sa.Column("encrypted_csrf_token", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Index("ix_bff_sessions_subject", "subject"),
        sa.Index("ix_bff_sessions_expires_at", "expires_at"),
    )


def downgrade() -> None:
    op.drop_table("bff_sessions")
