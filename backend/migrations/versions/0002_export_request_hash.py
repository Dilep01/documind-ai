"""Bind idempotency keys to the requested export selection and format."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"


def upgrade():
    op.add_column(
        "export_batches",
        sa.Column("request_hash", sa.String(64), nullable=False, server_default=""),
    )


def downgrade():
    raise RuntimeError("Restore a verified backup instead of a destructive downgrade.")
