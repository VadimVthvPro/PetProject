# app/db.py
import os
import asyncio
import asyncpg
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    'user': os.getenv('POSTGRES_USER', 'petuser'),
    'password': os.getenv('POSTGRES_PASSWORD', 'petpass'),
    'database': os.getenv('POSTGRES_DB', 'pet_hotel'),
    'host': os.getenv('POSTGRES_HOST', 'db'),
    'port': int(os.getenv('POSTGRES_PORT', 5432)),
}

_pool: asyncpg.pool.Pool | None = None

async def get_pool():
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(**DB_CONFIG, min_size=1, max_size=10)
    return _pool

async def fetch(query: str, *args):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(query, *args)

async def fetchrow(query: str, *args):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(query, *args)

async def execute(query: str, *args):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.execute(query, *args)

# helper to run a transaction function
async def with_transaction(func):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            return await func(conn)
