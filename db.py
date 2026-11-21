"""SQLite bazasi bilan ishlash (aiosqlite)."""
import aiosqlite
from datetime import date

DB_PATH = "monita.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id     INTEGER PRIMARY KEY,
    full_name   TEXT,
    username    TEXT,
    sectors     TEXT DEFAULT '',
    notify      INTEGER DEFAULT 1,
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS updates (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    sectors     TEXT NOT NULL,
    summary     TEXT NOT NULL,
    effective   TEXT,
    source_url  TEXT,
    details     TEXT,
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS deadlines (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    sectors     TEXT NOT NULL,
    due_date    TEXT NOT NULL,          -- YYYY-MM-DD
    description TEXT,
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS reminders_sent (
    deadline_id INTEGER,
    days_before INTEGER,
    PRIMARY KEY (deadline_id, days_before)
);
CREATE TABLE IF NOT EXISTS feedback (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER,
    text        TEXT,
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


def _split(s: str) -> list[str]:
    return [x for x in (s or "").split(",") if x]


def _overlaps(a: list[str], b: list[str]) -> bool:
    return bool(set(a) & set(b))


async def init():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)
        await db.commit()


# ---------- users ----------
async def upsert_user(user_id: int, full_name: str, username: str | None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO users (user_id, full_name, username) VALUES (?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET full_name=excluded.full_name,
               username=excluded.username""",
            (user_id, full_name, username),
        )
        await db.commit()


async def get_user(user_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
        row = await cur.fetchone()
    if not row:
        return None
    d = dict(row)
    d["sectors"] = _split(d["sectors"])
    return d


async def set_sectors(user_id: int, sectors: list[str]):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET sectors=? WHERE user_id=?",
                         (",".join(sectors), user_id))
        await db.commit()


async def toggle_notify(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET notify = 1 - notify WHERE user_id=?", (user_id,))
        await db.commit()
        cur = await db.execute("SELECT notify FROM users WHERE user_id=?", (user_id,))
        (val,) = await cur.fetchone()
    return bool(val)


async def subscribers_for(sectors: list[str]) -> list[int]:
    """Xabarnomasi yoqilgan va kamida bitta soha mos keladigan foydalanuvchilar."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT user_id, sectors FROM users WHERE notify=1")
        rows = await cur.fetchall()
    return [uid for uid, s in rows if _overlaps(_split(s), sectors)]


async def stats() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        q = lambda sql: db.execute(sql)
        total = (await (await q("SELECT COUNT(*) FROM users")).fetchone())[0]
        active = (await (await q(
            "SELECT COUNT(*) FROM users WHERE notify=1 AND sectors!=''")).fetchone())[0]
        ups = (await (await q("SELECT COUNT(*) FROM updates")).fetchone())[0]
        dls = (await (await q("SELECT COUNT(*) FROM deadlines")).fetchone())[0]
        cur = await q("SELECT sectors FROM users")
        counts: dict[str, int] = {}
        for (s,) in await cur.fetchall():
            for k in _split(s):
                counts[k] = counts.get(k, 0) + 1
    return {"total": total, "active": active, "updates": ups,
            "deadlines": dls, "by_sector": counts}


# ---------- updates ----------
async def add_update(title, sectors, summary, effective, source_url, details) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """INSERT INTO updates (title, sectors, summary, effective, source_url, details)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (title, ",".join(sectors), summary, effective, source_url, details),
        )
        await db.commit()
        return cur.lastrowid


async def get_update(update_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM updates WHERE id=?", (update_id,))
        row = await cur.fetchone()
    if not row:
        return None
    d = dict(row)
    d["sectors"] = _split(d["sectors"])
    return d


async def latest_updates(sectors: list[str], limit: int = 5) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM updates ORDER BY id DESC LIMIT 200")
        rows = await cur.fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["sectors"] = _split(d["sectors"])
        if _overlaps(d["sectors"], sectors):
            out.append(d)
        if len(out) >= limit:
            break
    return out


# ---------- deadlines ----------
async def add_deadline(title, sectors, due_date, description) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO deadlines (title, sectors, due_date, description) VALUES (?, ?, ?, ?)",
            (title, ",".join(sectors), due_date, description),
        )
        await db.commit()
        return cur.lastrowid


async def upcoming_deadlines(sectors: list[str] | None = None, limit: int = 10) -> list[dict]:
    today = date.today().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM deadlines WHERE due_date >= ? ORDER BY due_date", (today,))
        rows = await cur.fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["sectors"] = _split(d["sectors"])
        if sectors is None or _overlaps(d["sectors"], sectors):
            out.append(d)
        if len(out) >= limit:
            break
    return out


async def delete_deadline(deadline_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("DELETE FROM deadlines WHERE id=?", (deadline_id,))
        await db.commit()
        return cur.rowcount > 0


async def reminder_sent(deadline_id: int, days_before: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT 1 FROM reminders_sent WHERE deadline_id=? AND days_before=?",
            (deadline_id, days_before))
        return await cur.fetchone() is not None


async def mark_reminder(deadline_id: int, days_before: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO reminders_sent VALUES (?, ?)",
                         (deadline_id, days_before))
        await db.commit()


# ---------- feedback ----------
async def add_feedback(user_id: int, text: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO feedback (user_id, text) VALUES (?, ?)", (user_id, text))
        await db.commit()
