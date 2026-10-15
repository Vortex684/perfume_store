from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.core.config import get_settings
from collections.abc import AsyncGenerator

settings = get_settings()

# create_async_engine builds the connection pool to PostgreSQL.
# echo=True logs every SQL query to the console. INVALUABLE for learning.
# pool_pre_ping=True checks if a connection is alive before using it.
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=True,
    future=True,
    pool_pre_ping=True,
)

# async_sessionmaker is a factory that creates new AsyncSession objects.
# expire_on_commit=False keeps objects usable after the session commits.
# Without this, accessing attributes after commit triggers a lazy load,
# which fails in async mode because the session is closed.
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

# Base class for all our SQLAlchemy models.
Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession,None]:
    """
    Dependency Injection function.
    FastAPI calls this for every request that needs a database session.
    'yield' gives the session to the route, then continues here to close it.
    This ensures sessions are never leaked, even if the route crashes.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()