"""Database engine, session factory and dependency helpers."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from .config import Settings
from .models import Base


class Database:
    def __init__(self, settings: Settings) -> None:
        kwargs: dict[str, object] = {"pool_pre_ping": True, "future": True}
        if settings.database_url.startswith("sqlite"):
            self._ensure_sqlite_parent(settings.database_url)
            kwargs.update({"connect_args": {"check_same_thread": False}, "poolclass": StaticPool})
        else:
            kwargs.update(
                {"pool_size": 5, "max_overflow": 10, "pool_timeout": 10, "pool_recycle": 1800}
            )
        self.engine: Engine = create_engine(settings.database_url, **kwargs)
        self.SessionLocal = sessionmaker(
            bind=self.engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
            class_=Session,
        )

    @staticmethod
    def _ensure_sqlite_parent(url: str) -> None:
        prefix = "sqlite+pysqlite:///" if url.startswith("sqlite+pysqlite:///") else "sqlite:///"
        if not url.startswith(prefix) or ":memory:" in url:
            return
        raw_path = url[len(prefix) :]
        path = Path(raw_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        path.parent.mkdir(parents=True, exist_ok=True)

    def create_schema(self) -> None:
        Base.metadata.create_all(self.engine)

    def check(self) -> bool:
        with self.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True

    def session(self) -> Iterator[Session]:
        session = self.SessionLocal()
        try:
            yield session
        finally:
            session.close()

    def dispose(self) -> None:
        self.engine.dispose()
