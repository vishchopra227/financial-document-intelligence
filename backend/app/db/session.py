"""Database session management with MySQL support and graceful SQLite fallback."""

import logging
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from backend.app.config import settings
from backend.app.db.models import Base

logger = logging.getLogger("finsight.db")

active_db_type = "unknown"
active_db_url = ""


def create_db_engine():
    global active_db_type, active_db_url

    mysql_url = settings.DATABASE_URL
    if mysql_url and mysql_url.startswith("mysql"):
        try:
            logger.info("Attempting connection to MySQL database: %s", mysql_url.split("@")[-1])
            engine = create_engine(
                mysql_url,
                pool_pre_ping=True,
                pool_recycle=3600,
                pool_size=5,
                max_overflow=10,
                connect_args={"connect_timeout": 3},
            )
            # Verify connectivity
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            active_db_type = "mysql"
            active_db_url = mysql_url.split("@")[-1]
            logger.info("Successfully connected to MySQL database: %s", active_db_url)
            return engine
        except Exception as e:
            logger.warning(
                "Could not connect to MySQL (%s). Falling back to local SQLite at %s for seamless local execution.",
                str(e),
                settings.SQLITE_DB_PATH,
            )

    # SQLite Fallback
    sqlite_url = f"sqlite:///{settings.SQLITE_DB_PATH}"
    active_db_type = "sqlite"
    active_db_url = settings.SQLITE_DB_PATH
    engine = create_engine(
        sqlite_url,
        connect_args={"check_same_thread": False},
    )
    logger.info("Using SQLite database engine at: %s", settings.SQLITE_DB_PATH)
    return engine


engine = create_db_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Create all tables in the active database engine."""
    Base.metadata.create_all(bind=engine)
    logger.info("Database schema initialized successfully on [%s].", active_db_type)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_status() -> dict:
    """Return database connection status and type."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {
            "status": "connected",
            "type": active_db_type,
            "target": active_db_url,
        }
    except Exception as e:
        return {
            "status": "error",
            "type": active_db_type,
            "error": str(e),
        }
