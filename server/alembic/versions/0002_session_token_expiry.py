"""track token expiry for safe session refresh"""

import sqlalchemy as sa
from alembic import op

revision = "0002_session_token_expiry"
down_revision = "0001_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("bff_sessions", sa.Column("access_token_expires_at", sa.DateTime(timezone=True)))
    op.add_column("bff_sessions", sa.Column("refresh_token_expires_at", sa.DateTime(timezone=True)))
    op.add_column(
        "bff_sessions",
        sa.Column("token_updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(sa.text("UPDATE bff_sessions SET token_updated_at = created_at WHERE token_updated_at IS NULL"))
    op.alter_column("bff_sessions", "token_updated_at", nullable=False)


def downgrade() -> None:
    op.drop_column("bff_sessions", "token_updated_at")
    op.drop_column("bff_sessions", "refresh_token_expires_at")
    op.drop_column("bff_sessions", "access_token_expires_at")
