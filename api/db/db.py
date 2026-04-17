from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession


from api.db.models import Base
from config import settings

# Создание асинхронного движка и асинхронной фабрики сессий
async_engine = create_async_engine(url=settings.DB_URL, echo=True)

async_session = async_sessionmaker(
    bind=async_engine,
    expire_on_commit=False,
    class_=AsyncSession
)


async def create_db():
    try:
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as e:
        print(e)


async def get_session():
    try:
        async with async_session() as session:
            yield session
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()

