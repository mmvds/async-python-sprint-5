from asyncpg import InvalidCatalogNameError
from sqlalchemy.util import greenlet_spawn
from sqlalchemy_utils import database_exists, create_database
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

from src.core.config import app_settings
from src.models.base import Base

engine = create_async_engine(app_settings.database_dsn, echo=app_settings.database_logging, future=True)
async_session = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session


async def db_init():
    try:
        await greenlet_spawn(database_exists, engine.url)
    except InvalidCatalogNameError:
        await greenlet_spawn(create_database, engine.url)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)



