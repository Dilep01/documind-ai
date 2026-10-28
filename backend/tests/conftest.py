import os
import uuid

import pytest
from documind_ai.samples import generate_samples
from sqlalchemy import create_engine, text


@pytest.fixture(scope="session")
def samples(tmp_path_factory):
    directory = tmp_path_factory.mktemp("samples")
    generate_samples(directory)
    return directory


@pytest.fixture
def database(monkeypatch, tmp_path):
    url = os.environ.get("DOCUMIND_TEST_DATABASE_URL") or os.environ.get("DOCUMIND_DATABASE_URL")
    if not url:
        pytest.skip(
            "PostgreSQL integration requires DOCUMIND_TEST_DATABASE_URL or the Docker app environment"
        )
    from documind_ai import database as module

    schema = "test_" + uuid.uuid4().hex
    control = create_engine(url)
    with control.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema},public"})
    # checkfirst=False prevents an existing public table from hiding a new isolated test table.
    module.Base.metadata.create_all(engine, checkfirst=False)
    monkeypatch.setattr(module, "engine", lambda: engine)
    monkeypatch.setenv("DOCUMIND_STORAGE", str(tmp_path / "storage"))
    monkeypatch.setenv("DOCUMIND_CLASSIFIER", str(tmp_path / "no-model.joblib"))
    import documind_ai.processing as processing
    import httpx

    def no_model(*args, **kwargs):
        raise httpx.ConnectError("Offline integration test")

    monkeypatch.setattr(processing, "embed", no_model)
    yield module
    engine.dispose()
    with control.begin() as connection:
        connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
    control.dispose()


@pytest.fixture
def client(database):
    from documind_ai.api import app, login_attempts
    from documind_ai.auth import hash_password
    from fastapi.testclient import TestClient

    login_attempts.clear()
    with database.session_factory()() as db:
        db.add(
            database.User(
                username="admin",
                password_hash=hash_password("test-only-password-123"),
                role="admin",
            )
        )
        db.commit()
    with TestClient(app) as client:
        result = client.post(
            "/api/v1/auth/login", json={"username": "admin", "password": "test-only-password-123"}
        )
        assert result.status_code == 200
        client.headers["x-documind-csrf"] = result.json()["csrf_token"]
        yield client
