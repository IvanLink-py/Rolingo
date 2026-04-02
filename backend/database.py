import asyncpg
import asyncio
from typing import Optional
from backend.config import settings


class DatabasePool:
    _pool: Optional[asyncpg.Pool] = None

    @classmethod
    async def create_pool(cls):
        if cls._pool is None:
            cls._pool = await asyncpg.create_pool(
                settings.database_url,
                min_size=5,
                max_size=20
            )
        return cls._pool

    @classmethod
    async def close_pool(cls):
        if cls._pool:
            await cls._pool.close()
            cls._pool = None

    @classmethod
    async def get_connection(cls):
        pool = await cls.create_pool()
        return pool


async def get_db():
    """Dependency для получения соединения с БД"""
    pool = await DatabasePool.get_connection()
    async with pool.acquire() as conn:
        yield conn