from sqlmodel import SQLModel, Session, create_engine, text
from config import settings

engine = create_engine(settings.database_url, echo=False)


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)
    with engine.connect() as conn:
        conn.execute(text("PRAGMA journal_mode=WAL"))
    _migrate()


def _migrate() -> None:
    """
    Safe, additive schema migrations for SQLite.
    Runs on every startup — each step is idempotent.
    """
    with engine.connect() as conn:
        existing_cols = {
            row[1]
            for row in conn.execute(text("PRAGMA table_info(clausefinding)")).fetchall()
        }
        if "talking_points" not in existing_cols:
            conn.execute(
                text("ALTER TABLE clausefinding ADD COLUMN talking_points TEXT DEFAULT ''")
            )
            conn.commit()


def get_session():
    with Session(engine) as session:
        yield session
