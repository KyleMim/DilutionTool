import os
from pathlib import Path
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from backend.models import Base


def get_db_path() -> str:
    db_path = os.getenv("DB_PATH", "data/dilution_monitor.db")
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    return db_path


engine = create_engine(f"sqlite:///{get_db_path()}", echo=False)
SessionLocal = sessionmaker(bind=engine)


def _migrate(engine):
    """Add columns that don't exist yet (safe for repeated runs)."""
    insp = inspect(engine)
    if "dilution_scores" in insp.get_table_names():
        existing = {col["name"] for col in insp.get_columns("dilution_scores")}
        if "price_change_12m" not in existing:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE dilution_scores ADD COLUMN price_change_12m REAL"))


def _create_fts_index(engine):
    """Create FTS5 virtual table for full-text search on notes (idempotent)."""
    with engine.begin() as conn:
        # Create FTS5 virtual table if it doesn't exist
        conn.execute(text("""
            CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
                title, content, ticker, note_type,
                content_rowid=id,
                tokenize='porter unicode61'
            )
        """))

        # Backfill any existing notes that aren't in the FTS index
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
