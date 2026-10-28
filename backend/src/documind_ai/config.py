import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    database_url: str
    storage: Path
    ollama_url: str
    embedding_model: str
    chat_model: str
    origins: tuple[str, ...]
    cookie_secure: bool
    allow_self_approval: bool


def settings() -> Settings:
    return Settings(
        database_url=os.environ.get(
            "DOCUMIND_DATABASE_URL", "postgresql+psycopg://localhost/documind"
        ),
        storage=Path(os.environ.get("DOCUMIND_STORAGE", "storage")).resolve(),
        ollama_url=os.environ.get("DOCUMIND_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/"),
        embedding_model=os.environ.get("DOCUMIND_EMBEDDING_MODEL", "nomic-embed-text:latest"),
        chat_model=os.environ.get("DOCUMIND_CHAT_MODEL", "qwen3:1.7b"),
        origins=tuple(
            os.environ.get(
                "DOCUMIND_ORIGINS",
                "http://localhost:8765,http://127.0.0.1:8765,http://localhost:5173,http://127.0.0.1:5173",
            ).split(",")
        ),
        cookie_secure=os.environ.get("DOCUMIND_COOKIE_SECURE", "false").lower() == "true",
        allow_self_approval=os.environ.get("DOCUMIND_ALLOW_SELF_APPROVAL", "true").lower()
        == "true",
    )
