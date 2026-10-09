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

engine_kwargs: dict = {
    "connect_args": connect_args,
    "echo": (settings.LOG_LEVEL == "DEBUG"),
    "pool_pre_ping": True,
}
if not _is_sqlite:
    engine_kwargs.update({
        "pool_size": getattr(settings, "DB_POOL_SIZE", 10),
        "max_overflow": getattr(settings, "DB_MAX_OVERFLOW", 20),
        "pool_timeout": getattr(settings, "DB_POOL_TIMEOUT", 30),
    })

engine = create_engine(settings.DATABASE_URL, **engine_kwargs)

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

    if settings.APP_ENV != "development":
        logger.info("ensure_default_users_skipped_in_non_dev_environment")
        return

    try:
        presets = [
            ("usr_doctor_001", "doctor@clinsync.health", "Dr. Willie Carter, MD", "doctor", "General Medicine", "Doc@ClinSync2026!"),
            ("usr_doctor_002", "sarah.jenkins@clinsync.health", "Dr. Sarah Jenkins, MD", "doctor", "Cardiology", "Cardio@Sync2026!"),
            ("usr_doctor_003", "demo@clinsync.health", "Dr. Alex Mercer, MD", "doctor", "Internal Medicine", "Internal@Med2026!"),
            ("usr_patient_001", "patient@clinsync.health", "Willie Baker", "patient", "General", "Patient@Sync2026!"),
            ("usr_patient_002", "jane.doe@clinsync.health", "Jane Doe", "patient", "Cardiac Care", "Healthy@Life2026!"),
        ]
        for uid, email, name, role, spec, pwd in presets:
            existing = session.query(User).filter(User.email == email).first()
            if not existing:
                session.add(
                    User(
                        id=uid,
                        email=email,
                        full_name=name,
                        role=role,
                        specialty=spec,
                        hashed_password=hash_password(pwd),
                        is_active=True,
                    )
                )
        session.commit()
    except Exception as exc:
        session.rollback()
        logger.warning("ensure_default_users_skipped", error=str(exc))


def run_alembic_migrations() -> bool:
    """Run Alembic migrations programmatically to head, stamping baseline if legacy db."""
    try:
        from pathlib import Path
        from alembic.config import Config
        from alembic import command

        backend_dir = Path(__file__).resolve().parent.parent.parent
        ini_candidates = [
            backend_dir / "alembic.ini",
            backend_dir.parent / "alembic.ini",
        ]
        ini_path = next((p for p in ini_candidates if p.exists()), None)
        if not ini_path:
            return False

        alembic_cfg = Config(str(ini_path))
        alembic_cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()

        # If existing database has data tables but no alembic_version, stamp baseline first
        if "alembic_version" not in existing_tables and "patients" in existing_tables:
            logger.info("stamping_baseline_alembic_version_for_existing_database")
            command.stamp(alembic_cfg, "4c1d44f6a4e8")

        command.upgrade(alembic_cfg, "head")
        return True
    except Exception as exc:
        logger.warning("alembic_migration_attempt_fallback", error=str(exc))
        return False


def ensure_schema() -> bool:
    """Ensure database schema is complete and migrated to head. Additive only.

    Applies Alembic migrations to head. If migrations cannot run or tables are missing,
    safely falls back to Base.metadata.create_all(checkfirst=True). Returns True when
    schema is complete.
    """
    from app import models  # noqa: F401  — registers every table on Base

    try:
        run_alembic_migrations()
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
