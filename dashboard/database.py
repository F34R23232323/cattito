# Dashboard database operations

import json
import time
from typing import Optional

import asyncpg

pool = None


async def connect():
    global pool
    pool = await asyncpg.create_pool(
        user="cat_bot",
        password="meow",
        database="cat_bot",
        host="127.0.0.1",
        port=5432
    )


async def close():
    if pool:
        await pool.close()


async def init_tables():
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS dashboard_sessions (
                session_id TEXT PRIMARY KEY,
                user_id BIGINT NOT NULL,
                username TEXT NOT NULL DEFAULT '',
                avatar TEXT,
                global_name TEXT,
                access_token TEXT NOT NULL,
                refresh_token TEXT NOT NULL DEFAULT '',
                created_at DOUBLE PRECISION NOT NULL,
                expires_at DOUBLE PRECISION NOT NULL,
                guilds_json TEXT NOT NULL DEFAULT '[]'
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON dashboard_sessions(user_id)
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS dashboard_oauth_state (
                state TEXT PRIMARY KEY,
                expires_at DOUBLE PRECISION NOT NULL
            )
        """)


async def get_session(session_id: str) -> Optional[dict]:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM dashboard_sessions WHERE session_id = $1 AND expires_at > $2",
            session_id, time.time()
        )
        if row:
            return dict(row)
    return None


async def save_session(
    session_id: str,
    user_id: int,
    username: str,
    avatar: Optional[str],
    global_name: Optional[str],
    access_token: str,
    refresh_token: str,
    guilds: list
):
    now = time.time()
    expires_at = now + 86400 * 30
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO dashboard_sessions 
            (session_id, user_id, username, avatar, global_name, access_token, refresh_token, created_at, expires_at, guilds_json)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            ON CONFLICT (session_id) DO UPDATE SET
                username = $3, avatar = $4, global_name = $5, access_token = $6, refresh_token = $7, 
                expires_at = $9, guilds_json = $10
        """, session_id, user_id, username, avatar, global_name, access_token, refresh_token, now, expires_at, json.dumps(guilds))


async def delete_session(session_id: str):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM dashboard_sessions WHERE session_id = $1", session_id)


async def save_oauth_state(state: str):
    expires_at = time.time() + 600
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO dashboard_oauth_state (state, expires_at) VALUES ($1, $2) ON CONFLICT (state) DO UPDATE SET expires_at = $2",
            state, expires_at
        )


async def get_oauth_state(state: str) -> bool:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT 1 FROM dashboard_oauth_state WHERE state = $1 AND expires_at > $2",
            state, time.time()
        )
        return row is not None


async def delete_oauth_state(state: str):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM dashboard_oauth_state WHERE state = $1", state)