"""
Ma'lumotlar bazasi.
- DATABASE_URL berilgan bo'lsa -> PostgreSQL (asyncpg) — Render free uchun shu kerak.
- Aks holda -> lokal SQLite fayl (monita.db) — kompyuterda sinash uchun.
"""
import os
from datetime import date

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
DB_PATH = os.getenv("SQLITE_PATH", "monita.db")
USE_PG = DATABASE_URL.startswith(("postgres://", "postgresql://"))

_pool = None  # asyncpg pool

SCHEMA_PG = """
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY, full_name TEXT, username TEXT,
    sectors TEXT DEFAULT '', notify INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS updates (
    id BIGSERIAL PRIMARY KEY, title TEXT NOT NULL, sectors TEXT NOT NULL,
    summary TEXT NOT NULL, effective TEXT, source_url TEXT, details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS deadlines (
    id BIGSERIAL PRIMARY KEY, title TEXT NOT NULL, sectors TEXT NOT NULL,
    due_date TEXT NOT NULL, description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS reminders_sent (
    deadline_id BIGINT, days_before INTEGER, PRIMARY KEY (deadline_id, days_before));
CREATE TABLE IF NOT EXISTS feedback (
    id BIGSERIAL PRIMARY KEY, user_id BIGINT, text TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
"""

SCHEMA_SQLITE = (SCHEMA_PG.replace("BIGSERIAL PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT")
                 .replace("BIGINT PRIMARY KEY", "INTEGER PRIMARY KEY"))


# ---------------- past darajadagi yordamchilar ----------------
def _pg(sql: str) -> str:
    """'?' belgilarini Postgres uslubidagi $1, $2 ... ga almashtiradi."""
    out, n = [], 0
    for ch in sql:
        if ch == "?":
            n += 1
            out.append(f"${n}")
        else:
            out.append(ch)
    return "".join(out)


async def _fetch(sql: str, *args) -> list[dict]:
    if USE_PG:
        async with _pool.acquire() as c:
            return [dict(r) for r in await c.fetch(_pg(sql), *args)]
    import aiosqlite
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(sql, args)
        return [dict(r) for r in await cur.fetchall()]


async def _fetchone(sql: str, *args) -> dict | None:
    rows = await _fetch(sql, *args)
    return rows[0] if rows else None


async def _execute(sql: str, *args) -> int:
    """Bajaradi va ta'sirlangan qatorlar sonini qaytaradi."""
    if USE_PG:
        async with _pool.acquire() as c:
            status = await c.execute(_pg(sql), *args)
            try:
                return int(status.split()[-1])
            except ValueError:
                return 0
    import aiosqlite
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(sql, args)
        await db.commit()
        return cur.rowcount


async def _insert_returning_id(sql: str, *args) -> int:
    sql += " RETURNING id"
    if USE_PG:
        async with _pool.acquire() as c:
            return await c.fetchval(_pg(sql), *args)
    import aiosqlite
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(sql, args)
        row = await cur.fetchone()
        await db.commit()
        return row[0]


def _split(s: str) -> list[str]:
    return [x for x in (s or "").split(",") if x]


def _overlaps(a, b) -> bool:
    return bool(set(a) & set(b))


def _with_sectors(d: dict | None) -> dict | None:
    if d is not None:
        d["sectors"] = _split(d["sectors"])
    return d


async def init():
    global _pool
    if USE_PG:
        import asyncpg
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
        async with _pool.acquire() as c:
            await c.execute(SCHEMA_PG)
    else:
        import aiosqlite
        async with aiosqlite.connect(DB_PATH) as db:
            await db.executescript(SCHEMA_SQLITE)
            await db.commit()


async def close():
    if _pool is not None:
        await _pool.close()


# ---------------- users ----------------
async def upsert_user(user_id: int, full_name: str, username: str | None):
    await _execute(
        """INSERT INTO users (user_id, full_name, username) VALUES (?, ?, ?)
           ON CONFLICT (user_id) DO UPDATE SET full_name=excluded.full_name,
           username=excluded.username""",
        user_id, full_name, username)


async def get_user(user_id: int) -> dict | None:
    return _with_sectors(await _fetchone("SELECT * FROM users WHERE user_id=?", user_id))


async def set_sectors(user_id: int, sectors: list[str]):
    await _execute("UPDATE users SET sectors=? WHERE user_id=?", ",".join(sectors), user_id)


async def toggle_notify(user_id: int) -> bool:
    await _execute("UPDATE users SET notify = 1 - notify WHERE user_id=?", user_id)
    row = await _fetchone("SELECT notify FROM users WHERE user_id=?", user_id)
    return bool(row and row["notify"])


async def subscribers_for(sectors: list[str]) -> list[int]:
    rows = await _fetch("SELECT user_id, sectors FROM users WHERE notify=1")
    return [r["user_id"] for r in rows if _overlaps(_split(r["sectors"]), sectors)]


async def stats() -> dict:
    async def count(sql):
        return (await _fetchone(sql))["n"]
    counts: dict[str, int] = {}
    for r in await _fetch("SELECT sectors FROM users"):
        for k in _split(r["sectors"]):
            counts[k] = counts.get(k, 0) + 1
    return {
        "total": await count("SELECT COUNT(*) AS n FROM users"),
        "active": await count("SELECT COUNT(*) AS n FROM users WHERE notify=1 AND sectors!=''"),
        "updates": await count("SELECT COUNT(*) AS n FROM updates"),
        "deadlines": await count("SELECT COUNT(*) AS n FROM deadlines"),
        "by_sector": counts,
    }


# ---------------- updates ----------------
async def add_update(title, sectors, summary, effective, source_url, details) -> int:
    return await _insert_returning_id(
        """INSERT INTO updates (title, sectors, summary, effective, source_url, details)
           VALUES (?, ?, ?, ?, ?, ?)""",
        title, ",".join(sectors), summary, effective, source_url, details)


async def get_update(update_id: int) -> dict | None:
    return _with_sectors(await _fetchone("SELECT * FROM updates WHERE id=?", update_id))


async def latest_updates(sectors: list[str], limit: int = 5) -> list[dict]:
    out = []
    for d in await _fetch("SELECT * FROM updates ORDER BY id DESC LIMIT 200"):
        _with_sectors(d)
        if _overlaps(d["sectors"], sectors):
            out.append(d)
            if len(out) >= limit:
                break
    return out


# ---------------- deadlines ----------------
async def add_deadline(title, sectors, due_date, description) -> int:
    return await _insert_returning_id(
        "INSERT INTO deadlines (title, sectors, due_date, description) VALUES (?, ?, ?, ?)",
        title, ",".join(sectors), due_date, description)


async def upcoming_deadlines(sectors: list[str] | None = None, limit: int = 10) -> list[dict]:
    rows = await _fetch("SELECT * FROM deadlines WHERE due_date >= ? ORDER BY due_date",
                        date.today().isoformat())
    out = []
    for d in rows:
        _with_sectors(d)
        if sectors is None or _overlaps(d["sectors"], sectors):
            out.append(d)
            if len(out) >= limit:
                break
    return out


async def delete_deadline(deadline_id: int) -> bool:
    return await _execute("DELETE FROM deadlines WHERE id=?", deadline_id) > 0


async def reminder_sent(deadline_id: int, days_before: int) -> bool:
    return await _fetchone(
        "SELECT 1 AS x FROM reminders_sent WHERE deadline_id=? AND days_before=?",
        deadline_id, days_before) is not None


async def mark_reminder(deadline_id: int, days_before: int):
    await _execute(
        "INSERT INTO reminders_sent (deadline_id, days_before) VALUES (?, ?) "
        "ON CONFLICT DO NOTHING", deadline_id, days_before)


# ---------------- feedback ----------------
async def add_feedback(user_id: int, text: str):
    await _execute("INSERT INTO feedback (user_id, text) VALUES (?, ?)", user_id, text)
