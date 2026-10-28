"""Prove the frozen migrations create the current schema in a fresh disposable database."""

import json
import os
import uuid
from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from documind_ai.config import settings
from documind_ai.database import Base
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url


def verify():
    original = settings().database_url
    database_name = "documind_migration_check_" + uuid.uuid4().hex[:12]
    control = create_engine(original, isolation_level="AUTOCOMMIT")
    created = False
    target = None
    try:
        with control.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{database_name}"'))
        created = True
        url = make_url(original).set(database=database_name).render_as_string(hide_password=False)
        os.environ["DOCUMIND_DATABASE_URL"] = url
        command.upgrade(Config("alembic.ini"), "head")
        command.upgrade(Config("alembic.ini"), "head")
        target = create_engine(url)
        with target.connect() as connection:
            differences = compare_metadata(MigrationContext.configure(connection), Base.metadata)
            version = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
        if differences:
            raise RuntimeError(
                "Fresh migration schema differs from current metadata: " + repr(differences)
            )
        report = {
            "status": "passed",
            "revision": version,
            "tables": len(inspect(target).get_table_names()),
            "schema_differences": 0,
            "idempotent_second_upgrade": True,
            "scope": "new, separately named database; application records untouched",
        }
        Path("evaluation/reports/fresh-migrations.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(report))
    finally:
        os.environ["DOCUMIND_DATABASE_URL"] = original
        if target is not None:
            target.dispose()
        if created:
            with control.connect() as connection:
                connection.execute(text(f'DROP DATABASE "{database_name}" WITH (FORCE)'))
        control.dispose()


if __name__ == "__main__":
    verify()
