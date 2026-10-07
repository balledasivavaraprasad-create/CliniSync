from contextlib import contextmanager
from typing import Generator

import structlog
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.config import settings

logger = structlog.get_logger(__name__)

_is_sqlite = settings.DATABASE_URL.startswith("sqlite")

# `check_same_thread=False` is required because FastAPI serves sync endpoints on
# a thread pool. `timeout` is SQLite's busy-wait: without it a concurrent writer
# (the document pipeline, a recompute) raises `database is locked` immediately
# instead of waiting for the write lock. 30 s comfortably covers a recompute.
connect_args: dict = (
    {"check_same_thread": False, "timeout": 30} if _is_sqlite else {}
)

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=(settings.LOG_LEVEL == "DEBUG"),
    pool_pre_ping=True,
)

if _is_sqlite:
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        # NORMAL is the right durability trade-off under WAL: still crash-safe,
        # without an fsync per commit. Matters because the document pipeline
        # commits on every stage transition.
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """Session context for background work.

    Adds rollback-on-exception, so a failed recompute or pipeline run cannot
    leave a half-applied transaction for the next reader.

    Deliberately does **not** commit on exit. Callers commit explicitly, and a
    commit here would expire every loaded instance — code that holds an ORM
    object across the boundary (e.g. `pipeline_orchestrator.run` reading
    `job.id` after its first block) would then hit `DetachedInstanceError`.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def ensure_default_users(session: Session) -> None:
    from app.models.user import User
    from app.utils.hashing import hash_password

    try:
        if session.query(User.id).first() is None:
            demo_users = [
                User(
                    id="usr_doctor_001",
                    email="doctor@clinsync.health",
                    full_name="Dr. Willie Carter, MD",
                    role="doctor",
                    specialty="General Medicine",
                    hashed_password=hash_password("demo1234"),
                    is_active=True,
                ),
                User(
                    id="usr_doctor_002",
                    email="sarah.jenkins@clinsync.health",
                    full_name="Dr. Sarah Jenkins, MD",
                    role="doctor",
                    specialty="Cardiology",
                    hashed_password=hash_password("demo1234"),
                    is_active=True,
                ),
                User(
                    id="usr_doctor_003",
                    email="demo@clinsync.health",
                    full_name="Dr. Alex Mercer, MD",
                    role="doctor",
                    specialty="Internal Medicine",
                    hashed_password=hash_password("demo1234"),
                    is_active=True,
                ),
            ]
            session.add_all(demo_users)
            session.commit()
    except Exception as exc:
        session.rollback()
        logger.warning("ensure_default_users_skipped", error=str(exc))


def ensure_schema() -> bool:
    """Create any missing tables. Additive only — never drops or alters.

    There is no migration tool in this project, so a fresh clone has no tables
    at all and every endpoint 500s on `no such table`. Importing the model
    modules registers them on `Base.metadata`, and `create_all(checkfirst=True)`
    only issues `CREATE TABLE` for what is absent. Returns True when the schema
    is complete afterwards.
    """
    from app import models  # noqa: F401  — registers every table on Base

    try:
        Base.metadata.create_all(bind=engine, checkfirst=True)
        with SessionLocal() as session:
            ensure_default_users(session)
    except Exception as exc:  # pragma: no cover - surfaced via /health/deep
        logger.error("ensure_schema_failed", error=str(exc))
        return False
    return schema_is_complete()


def schema_is_complete() -> bool:
    """True when every declared table exists.

    `create_all` succeeding is not proof on its own: a table can exist with the
    wrong shape if the file predates a column. This checks names only, which is
    what the API can detect cheaply on every boot.
    """
    expected = set(Base.metadata.tables)
    try:
        present = set(inspect(engine).get_table_names())
    except Exception as exc:  # pragma: no cover - surfaced via /health/deep
        logger.error("schema_inspect_failed", error=str(exc))
        return False
    missing = sorted(expected - present)
    if missing:
        logger.error("schema_incomplete", missing=missing)
        return False
    return True


def db_health() -> dict:
    """Connectivity plus schema state, for `GET /health/deep`."""
    report = {"connected": False, "schema_complete": False, "missing_tables": []}
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            report["connected"] = True
    except Exception as exc:
        report["error"] = str(exc)
        return report

    try:
        from app import models  # noqa: F401

        present = set(inspect(engine).get_table_names())
        report["missing_tables"] = sorted(set(Base.metadata.tables) - present)
        report["schema_complete"] = not report["missing_tables"]
    except Exception as exc:
        report["error"] = str(exc)
    return report
