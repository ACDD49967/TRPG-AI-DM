"""异步 SQLAlchemy 数据库引擎与会话工厂。"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from backend.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    """所有 ORM 模型的基类。"""
    pass


async def get_db() -> AsyncSession:
    """FastAPI 依赖注入：生成一个异步数据库会话。"""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """应用启动时创建所有表。"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
