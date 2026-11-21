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
CREATE TABLE IF NOT EXISTS acts (
    lex_id TEXT PRIMARY KEY, title TEXT, oked TEXT, topic TEXT, act_type TEXT,
    requisites TEXT, effective TEXT, url TEXT);
CREATE TABLE IF NOT EXISTS act_chunks (
    id BIGSERIAL PRIMARY KEY, lex_id TEXT NOT NULL, lang TEXT NOT NULL,
    path TEXT, heading TEXT, content TEXT NOT NULL, search TEXT NOT NULL,
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX IF NOT EXISTS act_chunks_lex ON act_chunks (lex_id, lang);
"""
PG_FTS_INDEX = ("CREATE INDEX IF NOT EXISTS act_chunks_fts ON act_chunks "
                "USING GIN (to_tsvector('simple', search))")

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


def _clean_url(url: str) -> str:
    """Neon/Supabase satridagi asyncpg tushunmaydigan parametrlarni olib tashlaydi."""
    from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
    p = urlsplit(url)
    q = [(k, v) for k, v in parse_qsl(p.query) if k not in ("channel_binding", "pgbouncer")]
    return urlunsplit((p.scheme, p.netloc, p.path, urlencode(q), p.fragment))


async def init():
    global _pool
    if USE_PG:
        import asyncpg
        _pool = await asyncpg.create_pool(_clean_url(DATABASE_URL), min_size=1, max_size=5)
        async with _pool.acquire() as c:
            await c.execute(SCHEMA_PG)
            await c.execute(PG_FTS_INDEX)
    else:
        import aiosqlite
        async with aiosqlite.connect(DB_PATH) as db:
            await db.executescript(SCHEMA_SQLITE)
            await db.commit()
    await seed_acts()


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


# ---------------- qonun hujjatlari (162 ta akt reestri va matnlari) ----------------
async def seed_acts():
    """data/acts.csv dagi reestrni bazaga yozadi (har ishga tushganda yangilanadi)."""
    import legal
    try:
        rows = legal.load_acts_csv()
    except FileNotFoundError:
        return
    sql = ("INSERT INTO acts (lex_id, title, oked, topic, act_type, requisites, effective, url) "
           "VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT (lex_id) DO UPDATE SET "
           "title=excluded.title, oked=excluded.oked, topic=excluded.topic, "
           "act_type=excluded.act_type, requisites=excluded.requisites, "
           "effective=excluded.effective, url=excluded.url")
    args = [(r["lex_id"], r["title"], r["oked"], r["topic"], r["act_type"],
             r["requisites"], r["effective"], r["url"]) for r in rows]
    await _executemany(sql, args)
    # reestrdan chiqarilgan (kuchini yo'qotgan) aktlarni o'chiramiz
    ids = {r["lex_id"] for r in rows}
    for r in await _fetch("SELECT lex_id FROM acts"):
        if r["lex_id"] not in ids:
            await _execute("DELETE FROM act_chunks WHERE lex_id=?", r["lex_id"])
            await _execute("DELETE FROM acts WHERE lex_id=?", r["lex_id"])


async def _executemany(sql: str, args: list[tuple]):
    if not args:
        return
    if USE_PG:
        async with _pool.acquire() as c:
            async with c.transaction():
                await c.executemany(_pg(sql), args)
        return
    import aiosqlite
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executemany(sql, args)
        await db.commit()


async def acts_for_oked(letters: set[str]) -> list[dict]:
    out = []
    for a in await _fetch("SELECT * FROM acts ORDER BY effective DESC"):
        if set(x.strip() for x in (a["oked"] or "").split(",")) & letters:
            out.append(a)
    return out


async def replace_chunks(lex_id: str, lang: str, chunks: list[dict]):
    import legal
    await _execute("DELETE FROM act_chunks WHERE lex_id=? AND lang=?", lex_id, lang)
    await _executemany(
        "INSERT INTO act_chunks (lex_id, lang, path, heading, content, search) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [(lex_id, lang, c["path"], c["heading"], c["content"],
          legal.normalize(f"{c['heading']} {c['content']}")) for c in chunks])


async def search_chunks(terms: list[str], lex_ids: list[str], limit: int = 6) -> list[dict]:
    """Savol so'zlari bo'yicha eng mos moddalar (faqat berilgan aktlar ichida)."""
    if not terms or not lex_ids:
        return []
    if USE_PG:
        q = " | ".join(f"{t}:*" for t in terms)
        return await _fetch(
            "SELECT c.lex_id, c.lang, c.path, c.heading, c.content, a.title, a.url, "
            "ts_rank(to_tsvector('simple', c.search), to_tsquery('simple', ?)) AS score "
            "FROM act_chunks c JOIN acts a ON a.lex_id = c.lex_id "
            "WHERE to_tsvector('simple', c.search) @@ to_tsquery('simple', ?) "
            "AND c.lex_id = ANY(?::text[]) ORDER BY score DESC LIMIT ?",
            q, q, list(lex_ids), limit)
    # SQLite: LIKE bilan nomzodlar, so'ng Python'da baholash
    ph = ",".join("?" * len(lex_ids))
    like = " OR ".join("c.search LIKE ?" for _ in terms)
    rows = await _fetch(
        f"SELECT c.lex_id, c.lang, c.path, c.heading, c.content, c.search, a.title, a.url "
        f"FROM act_chunks c JOIN acts a ON a.lex_id = c.lex_id "
        f"WHERE c.lex_id IN ({ph}) AND ({like}) LIMIT 3000",
        *lex_ids, *[f"%{t}%" for t in terms])
    for r in rows:
        r["score"] = sum(1 + min(r["search"].count(t), 5) * 0.2 for t in terms if t in r["search"])
    rows.sort(key=lambda r: -r["score"])
    return rows[:limit]


async def chunk_stats() -> dict:
    acts = (await _fetchone("SELECT COUNT(*) AS n FROM acts"))["n"]
    with_text = (await _fetchone("SELECT COUNT(DISTINCT lex_id) AS n FROM act_chunks"))["n"]
    chunks = (await _fetchone("SELECT COUNT(*) AS n FROM act_chunks"))["n"]
    return {"acts": acts, "with_text": with_text, "chunks": chunks}
