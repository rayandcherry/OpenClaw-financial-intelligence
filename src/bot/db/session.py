import os
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://openclaw:localdev@localhost:5432/openclaw")

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session


async def init_db():
    """For testing or first-run. Production uses Alembic."""
    from src.bot.db.models import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
