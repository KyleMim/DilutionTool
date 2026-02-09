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


def create_tables():
    Base.metadata.create_all(engine)
    _migrate(engine)


def get_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
