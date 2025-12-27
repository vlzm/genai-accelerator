"""
Database connection management.

Provides SQLModel engine and session factory with hybrid authentication support.
Uses connection pooling for production performance.
"""

from contextlib import contextmanager
from typing import Generator

from sqlmodel import Session, SQLModel, create_engine

from app.services.secret_manager import get_settings, get_database_password


def get_database_url() -> str:
    """
    Constructs database URL with appropriate credentials.
    
    Security Note:
        - LOCAL: Uses password from .env
        - CLOUD: Fetches password from Key Vault via Managed Identity
    """
    settings = get_settings()
    password = get_database_password()
    
    return (
        f"postgresql://{settings.database_user}:{password}"
        f"@{settings.database_host}:{settings.database_port}/{settings.database_name}"
    )


def create_db_engine():
    """
    Creates SQLAlchemy engine with connection pooling.
    
    Pool settings are optimized for container environments
    where connections should be recycled frequently.
    """
    database_url = get_database_url()
    
    engine = create_engine(
        database_url,
        echo=False,  # Set to True for SQL debugging
        pool_size=5,
        max_overflow=10,
        pool_timeout=30,
        pool_recycle=1800,  # Recycle connections after 30 minutes
        pool_pre_ping=True,  # Verify connection health before use
    )
    
    return engine


# Global engine instance (lazy initialization)
_engine = None


def get_engine():
    """Returns the global database engine, creating it if needed."""
    global _engine
    if _engine is None:
        _engine = create_db_engine()
    return _engine


def init_db() -> None:
    """
    Initializes database schema.
    
    Creates all tables defined in SQLModel metadata.
    Safe to call multiple times (uses CREATE IF NOT EXISTS).
    
    If RAG_ENABLED=true, also activates pgvector extension for similarity search.
    """
    from sqlalchemy import text
    from app.models import Transaction, RiskReport  # noqa: F401 - Import for side effects
    from app.services.secret_manager import get_settings
    
    engine = get_engine()
    settings = get_settings()
    
    # Enable pgvector extension if RAG is enabled
    if settings.rag_enabled:
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            conn.commit()
    
    SQLModel.metadata.create_all(engine)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """
    Context manager for database sessions.
    
    Usage:
        with get_session() as session:
            session.add(transaction)
            session.commit()
    
    Automatically handles commit/rollback and session cleanup.
    
    Note: expire_on_commit=False allows using objects after session closes,
    which is needed for Streamlit's rendering flow.
    """
    engine = get_engine()
    session = Session(engine, expire_on_commit=False)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session_dependency() -> Generator[Session, None, None]:
    """
    FastAPI/Streamlit dependency for database sessions.
    
    Can be used with FastAPI's Depends() or directly in Streamlit.
    """
    with get_session() as session:
        yield session

