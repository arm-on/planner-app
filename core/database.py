from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


from core.database import engine
from sqlalchemy import text

def migrate_reminders_table_if_needed():
    with engine.begin() as conn:
        rows = conn.execute(text("PRAGMA table_info(reminders)")).fetchall()
        if not rows:
            return
        cols = {r[1]: r for r in rows}
        has_is_timeless = "is_timeless" in cols
        when_notnull = bool(cols.get("when", (None, None, None, 1))[3])

        if has_is_timeless and not when_notnull:
            return

        if not has_is_timeless:
            conn.execute(text("ALTER TABLE reminders ADD COLUMN is_timeless INTEGER NOT NULL DEFAULT 0"))
            rows = conn.execute(text("PRAGMA table_info(reminders)")).fetchall()
            cols = {r[1]: r for r in rows}
            when_notnull = bool(cols.get("when", (None, None, None, 1))[3])

        if when_notnull:
            conn.execute(text("PRAGMA foreign_keys=OFF"))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS reminders_new (
                    id INTEGER PRIMARY KEY,
                    owner_id INTEGER NOT NULL,
                    "when" DATETIME NULL,
                    is_timeless INTEGER NOT NULL DEFAULT 0,
                    note VARCHAR NOT NULL,
                    FOREIGN KEY(owner_id) REFERENCES users(id)
                )
            """))
            conn.execute(text("""
                INSERT INTO reminders_new (id, owner_id, "when", is_timeless, note)
                SELECT id, owner_id, "when", COALESCE(is_timeless, 0), note
                FROM reminders
            """))
            conn.execute(text("DROP TABLE reminders"))
            conn.execute(text("ALTER TABLE reminders_new RENAME TO reminders"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_reminders_id ON reminders (id)"))
            conn.execute(text("PRAGMA foreign_keys=ON"))

