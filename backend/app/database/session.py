from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
from backend.app.config import settings
from backend.app.database.models import Base

# Ensure SQLite path is formatted properly for aiosqlite (forward slashes)
db_path_str = str(settings.SQLITE_DB_PATH).replace("\\", "/")
DATABASE_URL = f"sqlite+aiosqlite:///{db_path_str}"

engine = create_async_engine(
    DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
    poolclass=NullPool,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

async def init_db() -> None:
    """Initialize database tables asynchronously on application startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for yielding an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

