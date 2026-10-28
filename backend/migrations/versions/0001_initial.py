"""Initial local-release schema. Snapshot of the v0.1 schema is locked by this release."""

from pathlib import Path

from alembic import op

revision = "0001"
down_revision = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    # Frozen DDL: future ORM changes require a new migration.
    ddl = Path(__file__).with_name("0001_schema.sql").read_text(encoding="utf-8")
    for statement in ddl.split(";"):
        if statement.strip():
            op.execute(statement)


def downgrade():
    raise RuntimeError("Destructive downgrade is disabled. Restore a verified backup instead.")
