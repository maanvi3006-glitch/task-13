"""
create_database.py
Initializes the SQLite database for the PlaceMux Offer->Acceptance project
by executing sql/create_tables.sql against database/placemux.db.

Run:
    python create_database.py
"""

import sqlite3
import logging
import os

import config

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.FileHandler(config.LOG_FILE),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("create_database")


def create_database():
    if not os.path.exists(config.CREATE_TABLES_SQL):
        raise FileNotFoundError(
            f"Schema file not found at {config.CREATE_TABLES_SQL}"
        )

    with open(config.CREATE_TABLES_SQL, "r") as f:
        schema_sql = f.read()

    logger.info("Connecting to database at %s", config.DB_PATH)
    conn = sqlite3.connect(config.DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.executescript(schema_sql)
        conn.commit()
        logger.info("Schema applied successfully.")

        # Sanity: confirm expected tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        expected = {"candidates", "offers", "interviews", "events"}
        missing = expected - set(tables)
        if missing:
            raise RuntimeError(f"Tables missing after schema creation: {missing}")
        logger.info("Tables present: %s", sorted(tables))
    finally:
        conn.close()
        logger.info("Database connection closed.")


if __name__ == "__main__":
    create_database()
    print(f"Database initialized at {config.DB_PATH}")
