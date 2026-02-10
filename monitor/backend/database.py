import os
from pathlib import Path
from sqlalchemy import create_engine, text, inspect, event
from sqlalchemy.orm import sessionmaker
from backend.models import Base


def _get_engine():
    """Create engine from DATABASE_URL (PostgreSQL) or fall back to SQLite."""
    database_url = os.getenv("DATABASE_URL")

    if database_url:
        # Render provides postgres:// but SQLAlchemy needs postgresql://
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)
        return create_engine(database_url, echo=False, pool_pre_ping=True)

    # SQLite fallback for local dev
    db_path = os.getenv("DB_PATH", "data/dilution_monitor.db")
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        f"sqlite:///{db_path}",
        echo=False,
        connect_args={"timeout": 30},
    )

    # Enable WAL mode for better concurrent read/write (SQLite only)
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    return engine


engine = _get_engine()
SessionLocal = sessionmaker(bind=engine)

_is_sqlite = engine.dialect.name == "sqlite"


def _migrate(engine):
    """Add columns that don't exist yet (safe for repeated runs)."""
    insp = inspect(engine)
    tables = insp.get_table_names()

    if "dilution_scores" in tables:
        existing = {col["name"] for col in insp.get_columns("dilution_scores")}
        if "price_change_12m" not in existing:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE dilution_scores ADD COLUMN price_change_12m REAL"))

    if "companies" in tables:
        existing = {col["name"] for col in insp.get_columns("companies")}
        with engine.begin() as conn:
            if "is_spac" not in existing:
                conn.execute(text("ALTER TABLE companies ADD COLUMN is_spac BOOLEAN DEFAULT FALSE"))
            if "is_actively_trading" not in existing:
                conn.execute(text("ALTER TABLE companies ADD COLUMN is_actively_trading BOOLEAN DEFAULT TRUE"))


def _create_fts_index(engine):
    """Create FTS5 virtual table for full-text search on notes (SQLite only)."""
    if not _is_sqlite:
        return

    with engine.begin() as conn:
        conn.execute(text("""
            CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
                title, content, ticker, note_type,
                content_rowid=id,
                tokenize='porter unicode61'
            )
        """))

        conn.execute(text("""
            INSERT OR IGNORE INTO notes_fts(rowid, title, content, ticker, note_type)
            SELECT id, title, content, COALESCE(ticker, ''), note_type FROM notes
            WHERE id NOT IN (SELECT rowid FROM notes_fts)
        """))


def create_tables():
    Base.metadata.create_all(engine)
    _migrate(engine)
    _create_fts_index(engine)


def get_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def is_sqlite() -> bool:
    return _is_sqlite
