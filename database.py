import aiosqlite
from typing import Optional, List, Tuple
from datetime import datetime, timedelta

DB_PATH = "forwardx.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT,
                daily_count INTEGER DEFAULT 0,
                premium_until TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS mappings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER NOT NULL,
                source_chat TEXT NOT NULL,
                target_chat TEXT NOT NULL,
                active INTEGER DEFAULT 1
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                txn_id TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()

async def ensure_user(user_id: int, username: Optional[str]):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (id, username, daily_count, premium_until) VALUES (?, ?, 0, NULL)",
            (user_id, username or "")
        )
        await db.execute("UPDATE users SET username = ? WHERE id = ?", (username or "", user_id))
        await db.commit()

async def get_user(user_id: int) -> Optional[tuple]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT id, username, daily_count, premium_until FROM users WHERE id = ?", (user_id,))
        return await cur.fetchone()

async def set_premium_days(user_id: int, days: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT premium_until FROM users WHERE id = ?", (user_id,))
        row = await cur.fetchone()
        now = datetime.utcnow()
        cur_until = now
        if row and row[0]:
            try:
                cur_until = datetime.fromisoformat(row[0])
            except Exception:
                cur_until = now
        base = max(now, cur_until)
        new_until = base + timedelta(days=days)
        await db.execute("UPDATE users SET premium_until = ? WHERE id = ?", (new_until.isoformat(), user_id))
        await db.commit()
        return new_until

async def revoke_premium(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET premium_until = NULL WHERE id = ?", (user_id,))
        await db.commit()

async def increment_daily(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET daily_count = daily_count + 1 WHERE id = ?", (user_id,))
        await db.commit()

async def reset_daily_counts():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET daily_count = 0")
        await db.commit()

async def create_mapping(owner_id: int, src: str, dst: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO mappings (owner_id, source_chat, target_chat, active) VALUES (?, ?, ?, 1)",
            (owner_id, str(src), str(dst))
        )
        await db.commit()
        return cur.lastrowid

async def list_mappings(owner_id: int) -> List[Tuple]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT id, source_chat, target_chat, active FROM mappings WHERE owner_id = ? ORDER BY id DESC",
            (owner_id,)
        )
        return await cur.fetchall()

async def toggle_mapping(owner_id: int, mapping_id: int, active: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "UPDATE mappings SET active = ? WHERE id = ? AND owner_id = ?",
            (active, mapping_id, owner_id)
        )
        await db.commit()
        return cur.rowcount > 0

async def delete_mapping(owner_id: int, mapping_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("DELETE FROM mappings WHERE id = ? AND owner_id = ?", (mapping_id, owner_id))
        await db.commit()
        return cur.rowcount > 0

async def targets_for_source(source_chat_id: int) -> List[Tuple[int, int, str]]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT owner_id, id, target_chat FROM mappings WHERE source_chat = ? AND active = 1",
            (str(source_chat_id),)
        )
        return await cur.fetchall()

async def create_payment(user_id: int, amount: int, txn_id: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO payments (user_id, amount, txn_id, status) VALUES (?, ?, ?, 'pending')",
            (user_id, amount, txn_id)
        )
        await db.commit()
        return cur.lastrowid

async def set_payment_status(payment_id: int, status: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE payments SET status = ? WHERE id = ?", (status, payment_id))
        await db.commit()
