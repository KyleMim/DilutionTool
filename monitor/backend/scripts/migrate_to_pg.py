"""
Migrate data from local SQLite to PostgreSQL.

Usage:
  python -m backend.scripts.migrate_to_pg "postgresql://user:pass@host:5432/dbname"
  or
  DATABASE_URL=postgresql://user:pass@host:5432/dbname python -m backend.scripts.migrate_to_pg
"""
import os
import sys
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker

from backend.models import (
    Base, Company, FundamentalsQuarterly, SecFiling,
    DilutionScore, Conversation, Message, Note,
)


def get_sqlite_engine():
    db_path = os.getenv("DB_PATH", "data/dilution_monitor.db")
    if not os.path.exists(db_path):
        print(f"ERROR: SQLite database not found at {db_path}")
        sys.exit(1)
    return create_engine(f"sqlite:///{db_path}", echo=False)


def get_pg_engine(database_url=None):
    # Accept database_url from argument or environment variable
    if not database_url:
        database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL not provided.")
        print("Usage: python -m backend.scripts.migrate_to_pg \"postgresql://user:pass@host:port/dbname\"")
        sys.exit(1)
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    return create_engine(database_url, echo=False)


# Tables in dependency order (parents before children)
TABLES = [
    Company,
    FundamentalsQuarterly,
    SecFiling,
    DilutionScore,
    Conversation,
    Message,
    Note,
]


def migrate(database_url=None):
    sqlite_engine = get_sqlite_engine()
    pg_engine = get_pg_engine(database_url)

    sqlite_session = sessionmaker(bind=sqlite_engine)()
    pg_session = sessionmaker(bind=pg_engine)()

    # Create all tables in PostgreSQL
    print("Creating tables in PostgreSQL...")
    Base.metadata.create_all(pg_engine)

    for model in TABLES:
        table_name = model.__tablename__
        print(f"\nMigrating {table_name}...")

        # Check if target already has data
        existing = pg_session.execute(
            text(f"SELECT COUNT(*) FROM {table_name}")
        ).scalar()
        if existing > 0:
            print(f"  Skipping {table_name}: already has {existing} rows")
            continue

        # Read all rows from SQLite
        rows = sqlite_session.query(model).all()
        print(f"  Found {len(rows)} rows in SQLite")

        if not rows:
            continue

        # Get column names (exclude relationships)
        mapper = inspect(model)
        columns = [c.key for c in mapper.column_attrs]

        # Batch insert into PostgreSQL
        batch_size = 500
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i + batch_size]
            row_dicts = []
            for row in batch:
                row_dicts.append({col: getattr(row, col) for col in columns})

            pg_session.bulk_insert_mappings(model, row_dicts)
            pg_session.commit()
            print(f"  Inserted {min(i + batch_size, len(rows))}/{len(rows)}")

        # Reset the auto-increment sequence for PostgreSQL
        max_id = pg_session.execute(
            text(f"SELECT COALESCE(MAX(id), 0) FROM {table_name}")
        ).scalar()
        if max_id > 0:
            seq_name = f"{table_name}_id_seq"
            try:
                pg_session.execute(
                    text(f"SELECT setval('{seq_name}', :val)")
                    , {"val": max_id}
                )
                pg_session.commit()
            except Exception:
                pg_session.rollback()

    sqlite_session.close()
    pg_session.close()

    print("\nMigration complete!")


if __name__ == "__main__":
    database_url = sys.argv[1] if len(sys.argv) > 1 else None
    migrate(database_url)
