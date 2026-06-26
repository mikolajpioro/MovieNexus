from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase


SQLALCHEMY_DATABSE_URL = "sqlite+aiosqlite:///./reviews.db"

engine = create_async_engine(
    SQLALCHEMY_DATABSE_URL,
    connect_args={"check_same_thread": False}
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

class Base(DeclarativeBase):
    pass

# changed db to session--------
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session