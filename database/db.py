# database/db.py
# AdaptLab — SQLite engine, session factory, and table initialisation.
# Imports from: database/models.py, utils/logger.py
# All other modules obtain a DB session via get_db() or SessionLocal().

import os
from contextlib import contextmanager
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from database.models import Base
from utils.logger import get_logger

load_dotenv()

log = get_logger("database.db")

# ─────────────────────────────────────────────
# Engine configuration
# ─────────────────────────────────────────────

DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./adaptlab.db")

# check_same_thread=False is required for SQLite when used with FastAPI
# (multiple threads share the same connection pool).
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,        # set True for SQL query debugging
)


# ─────────────────────────────────────────────
# Enable WAL mode + foreign keys for every new SQLite connection.
# WAL = Write-Ahead Logging — allows concurrent reads during writes.
# Foreign key enforcement is OFF by default in SQLite; must be set per-connection.
# ─────────────────────────────────────────────

@event.listens_for(engine, "connect")
def _on_connect(dbapi_connection, connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA foreign_keys=ON;")
    cursor.close()


# ─────────────────────────────────────────────
# Session factory
# ─────────────────────────────────────────────

SessionLocal: sessionmaker[Session] = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,   # objects stay usable after commit (important for async routes)
)


# ─────────────────────────────────────────────
# Dependency-injection helper for FastAPI routes
# Usage in a route:
#   def my_route(db: Session = Depends(get_db)): ...
# ─────────────────────────────────────────────

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ─────────────────────────────────────────────
# Context-manager variant for non-route usage
# (capability_engine, escalation, anti_gaming, etc.)
# Usage:
#   with db_session() as db:
#       db.query(Student).all()
# ─────────────────────────────────────────────

@contextmanager
def db_session() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ─────────────────────────────────────────────
# Table initialisation — called once on startup
# ─────────────────────────────────────────────

def init_db() -> None:
    """
    Creates all tables that do not yet exist.
    Safe to call on every startup — SQLAlchemy uses CREATE TABLE IF NOT EXISTS.
    After table creation, runs the seeder if the problems table is empty.
    """
    log.info("db_init_start", database_url=DATABASE_URL)
    try:
        Base.metadata.create_all(bind=engine)
        log.info("db_tables_created")
        _maybe_seed()
    except Exception as exc:
        log.exception("db_init_failed", error=str(exc))
        raise


def _maybe_seed() -> None:
    """
    Imports and runs the seeder only if the problems table is empty.
    Deferred import avoids a circular dependency at module load time.
    """
    with db_session() as db:
        count = db.execute(text("SELECT COUNT(*) FROM problems")).scalar()
        if count == 0:
            log.info("db_seed_start", reason="problems_table_empty")
            from database.seed import seed_problems
            seed_problems(db)
            log.info("db_seed_complete")
        else:
            log.info("db_seed_skipped", existing_problems=count)


# ─────────────────────────────────────────────
# Health-check utility — used by main.py startup event
# ─────────────────────────────────────────────

def check_db_health() -> bool:
    """Returns True if the DB is reachable and tables exist."""
    try:
        with db_session() as db:
            db.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        log.error("db_health_check_failed", error=str(exc))
        return False
