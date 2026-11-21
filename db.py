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
NEW_ACTS_ON_START: list[dict] = []  # reestrga yangi qo'shilgan aktlar (bot ularni e'lon qiladi)

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
CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS act_vecs (lex_id TEXT PRIMARY KEY, model TEXT, vec TEXT);
CREATE TABLE IF NOT EXISTS drafts (
    id BIGINT PRIMARY KEY, project_id BIGINT, text_id BIGINT, speciality INTEGER, oked TEXT,
    name_uz TEXT, name_ru TEXT, org_uz TEXT, org_ru TEXT, start_date TEXT, end_date TEXT,
    status TEXT, views INTEGER DEFAULT 0, suggestions INTEGER DEFAULT 0, text TEXT,
    first_seen TEXT, notified INTEGER DEFAULT 0);
"""
MIGRATIONS = [  # eski bazalar uchun yangi ustunlar
    ("users", "lang", "TEXT"),
    ("acts", "source", "TEXT DEFAULT 'csv'"),
    ("acts", "text_hash", "TEXT"),
    ("acts", "added_at", "TEXT"),
]
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
    """OKED bo'yicha moslik: bo'lim harflari kesishadimi (47 -> G, eski 'savdo' -> G)."""
    import oked
    if "ALL" in oked.normalize(a) or "ALL" in oked.normalize(b):
        return True
    return oked.match(oked.normalize(b), a)


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
            for table, col, typ in MIGRATIONS:
                await c.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {typ}")
    else:
        import aiosqlite
        async with aiosqlite.connect(DB_PATH) as db:
            await db.executescript(SCHEMA_SQLITE)
            for table, col, typ in MIGRATIONS:
                try:
                    await db.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")
                except Exception:  # noqa: BLE001 — ustun allaqachon bor
                    pass
            await db.commit()
    global NEW_ACTS_ON_START
    NEW_ACTS_ON_START = await seed_acts()


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
    import oked
    u = _with_sectors(await _fetchone("SELECT * FROM users WHERE user_id=?", user_id))
    if u:
        u["sectors"] = oked.normalize(u["sectors"])  # eski 'savdo' -> 'G'
    return u


async def set_sectors(user_id: int, sectors: list[str]):
    await _execute("UPDATE users SET sectors=? WHERE user_id=?", ",".join(sectors), user_id)


async def toggle_notify(user_id: int) -> bool:
    await _execute("UPDATE users SET notify = 1 - notify WHERE user_id=?", user_id)
    row = await _fetchone("SELECT notify FROM users WHERE user_id=?", user_id)
    return bool(row and row["notify"])


async def set_lang(user_id: int, lang: str):
    await _execute("UPDATE users SET lang=? WHERE user_id=?", lang, user_id)


async def all_subscribers() -> list[dict]:
    import oked
    return [{"user_id": r["user_id"], "lang": r["lang"] or "uz",
             "sectors": oked.normalize(_split(r["sectors"]))}
            for r in await _fetch("SELECT user_id, sectors, lang FROM users WHERE notify=1")]


async def subscribers_for(sectors: list[str]) -> list[dict]:
    """[{'user_id': .., 'lang': ..}] — xabarnomasi yoqilgan, sohasi mos foydalanuvchilar."""
    rows = await _fetch("SELECT user_id, sectors, lang FROM users WHERE notify=1")
    return [{"user_id": r["user_id"], "lang": r["lang"] or "uz"} for r in rows
            if _overlaps(_split(r["sectors"]), sectors)]


async def stats() -> dict:
    async def count(sql):
        return (await _fetchone(sql))["n"]
    counts: dict[str, int] = {}
    import oked
    for r in await _fetch("SELECT sectors FROM users"):
        for k in oked.letters(_split(r["sectors"])):
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
async def seed_acts() -> list[dict]:
    """data/acts.csv reestrini bazaga yozadi. Qaytaradi: YANGI qo'shilgan aktlar
    (birinchi ishga tushishda — bo'sh ro'yxat, hammaga xabar yubormaslik uchun)."""
    import legal
    try:
        rows = legal.load_acts_csv()
    except FileNotFoundError:
        return []
    existing = {r["lex_id"]: r["source"] for r in await _fetch("SELECT lex_id, source FROM acts")}
    # birinchi ishga tushish (yoki eski versiyadan yangilanish) — faqat bazaviy holatni yozamiz,
    # foydalanuvchilarga "yangi akt" xabari yuborilmaydi
    first_run = not existing or not await meta_get("acts_baseline")
    today = date.today().isoformat()
    sql = ("INSERT INTO acts (lex_id, title, oked, topic, act_type, requisites, effective, url, "
           "source, added_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'csv', ?) "
           "ON CONFLICT (lex_id) DO UPDATE SET "
           "title=excluded.title, oked=excluded.oked, topic=excluded.topic, "
           "act_type=excluded.act_type, requisites=excluded.requisites, "
           "effective=excluded.effective, url=excluded.url")
    await _executemany(sql, [(r["lex_id"], r["title"], r["oked"], r["topic"], r["act_type"],
                              r["requisites"], r["effective"], r["url"], today) for r in rows])
    # reestrdan chiqarilgan (kuchini yo'qotgan) aktlar o'chiriladi; admin qo'shganlari qoladi
    ids = {r["lex_id"] for r in rows}
    for lex_id, source in existing.items():
        if lex_id not in ids and (source or "csv") == "csv":
            await _execute("DELETE FROM act_chunks WHERE lex_id=?", lex_id)
            await _execute("DELETE FROM acts WHERE lex_id=?", lex_id)
    if first_run:
        await meta_set("acts_baseline", date.today().isoformat())
        return []
    return [dict(r, source="csv") for r in rows if r["lex_id"] not in existing]


async def add_act(lex_id, title, oked, topic, act_type, requisites, effective, url) -> bool:
    """Admin qo'lda qo'shgan akt. True — yangi, False — mavjud edi (yangilandi)."""
    existed = await get_act(lex_id) is not None
    await _execute(
        "INSERT INTO acts (lex_id, title, oked, topic, act_type, requisites, effective, url, "
        "source, added_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'admin', ?) "
        "ON CONFLICT (lex_id) DO UPDATE SET title=excluded.title, oked=excluded.oked, "
        "topic=excluded.topic, act_type=excluded.act_type, requisites=excluded.requisites, "
        "effective=excluded.effective, url=excluded.url",
        lex_id, title, oked, topic, act_type, requisites, effective, url, date.today().isoformat())
    return not existed


async def get_act(lex_id: str) -> dict | None:
    return await _fetchone("SELECT * FROM acts WHERE lex_id=?", lex_id)


async def all_acts() -> list[dict]:
    return await _fetch("SELECT * FROM acts ORDER BY effective DESC")


async def meta_get(k: str) -> str | None:
    r = await _fetchone("SELECT v FROM meta WHERE k=?", k)
    return r["v"] if r else None


async def meta_set(k: str, v: str):
    await _execute("INSERT INTO meta (k, v) VALUES (?, ?) ON CONFLICT (k) DO UPDATE SET v=excluded.v",
                   k, v)


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


async def acts_for_oked(codes: set[str], include_bg: bool = False) -> list[dict]:
    """Foydalanuvchi kodlariga (bo'lim/bo'linma) mos aktlar: sohaga xoslari + 'ALL'.
    'BG' (fon: hududiy dasturlar, mukofotlar, texnik o'zgartishlar) faqat include_bg=True da."""
    import oked
    out = []
    for a in await _fetch("SELECT * FROM acts ORDER BY effective DESC"):
        ac = [x.strip() for x in (a["oked"] or "").split(",") if x.strip()]
        if "BG" in ac:
            if include_bg:
                out.append(a)
        elif oked.match(ac, codes):
            out.append(a)
    return out


async def replace_chunks(lex_id: str, lang: str, chunks: list[dict]) -> tuple[str | None, str]:
    """Akt matnini almashtiradi. Qaytaradi (eski_hash, yangi_hash) — o'zgarishni aniqlash uchun
    (faqat o'zbekcha matn hash'i saqlanadi)."""
    import hashlib
    import legal
    new_hash = hashlib.sha256("\n".join(
        legal.normalize(c["content"]) for c in chunks).encode()).hexdigest()[:16]
    old_hash = None
    if lang == "uz":
        act = await get_act(lex_id)
        old_hash = act.get("text_hash") if act else None
    await _execute("DELETE FROM act_chunks WHERE lex_id=? AND lang=?", lex_id, lang)
    await _executemany(
        "INSERT INTO act_chunks (lex_id, lang, path, heading, content, search) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [(lex_id, lang, c["path"], c["heading"], c["content"],
          legal.normalize(f"{c['heading']} {c['content']}")) for c in chunks])
    if lang == "uz":
        await _execute("UPDATE acts SET text_hash=? WHERE lex_id=?", new_hash, lex_id)
    return old_hash, new_hash


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


async def get_chunks(lex_id: str, lang: str, limit: int = 6) -> list[dict]:
    rows = await _fetch("SELECT path, heading, content FROM act_chunks WHERE lex_id=? AND lang=? "
                        "ORDER BY id LIMIT ?", lex_id, lang, limit)
    if not rows and lang != "uz":
        rows = await _fetch("SELECT path, heading, content FROM act_chunks WHERE lex_id=? AND lang='uz' "
                            "ORDER BY id LIMIT ?", lex_id, limit)
    return rows


async def lex_ids_with_text() -> set[str]:
    return {r["lex_id"] for r in await _fetch("SELECT DISTINCT lex_id FROM act_chunks")}


async def ping() -> bool:
    return (await _fetchone("SELECT 1 AS x")) is not None


async def chunk_stats() -> dict:
    acts = (await _fetchone("SELECT COUNT(*) AS n FROM acts"))["n"]
    with_text = (await _fetchone("SELECT COUNT(DISTINCT lex_id) AS n FROM act_chunks"))["n"]
    chunks = (await _fetchone("SELECT COUNT(*) AS n FROM act_chunks"))["n"]
    return {"acts": acts, "with_text": with_text, "chunks": chunks}


# ---------------- NPA loyihalari (regulation.adliya.uz) ----------------
DRAFT_FIELDS = ("id", "project_id", "text_id", "speciality", "oked", "name_uz", "name_ru", "org_uz",
                "org_ru", "start_date", "end_date", "status", "views", "suggestions")


async def upsert_drafts(items: list[dict]) -> list[dict]:
    """Portal ro'yxatini saqlaydi. Qaytaradi: YANGI paydo bo'lgan loyihalar
    (birinchi sinxronlashda bo'sh — eski loyihalar haqida xabar yubormaslik uchun).
    Ro'yxatda yo'q bo'lib qolgan loyihalar 'CLOSED' deb belgilanadi."""
    existing = {r["id"] for r in await _fetch("SELECT id FROM drafts")}
    baseline = await meta_get("drafts_baseline")
    today = date.today().isoformat()
    cols = ", ".join(DRAFT_FIELDS)
    sql = (f"INSERT INTO drafts ({cols}, first_seen) VALUES ({', '.join('?' * (len(DRAFT_FIELDS) + 1))}) "
           "ON CONFLICT (id) DO UPDATE SET " + ", ".join(
               f"{c}=excluded.{c}" for c in DRAFT_FIELDS if c != "id"))
    await _executemany(sql, [tuple(it[c] for c in DRAFT_FIELDS) + (today,) for it in items])
    seen = {it["id"] for it in items}
    for old_id in existing - seen:
        await _execute("UPDATE drafts SET status='CLOSED' WHERE id=? AND status='IN_DISCUSSION'", old_id)
    if not baseline:
        await meta_set("drafts_baseline", today)
        await _execute("UPDATE drafts SET notified=1")
        return []
    return [it for it in items if it["id"] not in existing]


async def drafts_for_oked(codes, active_only: bool = True, limit: int = 100) -> list[dict]:
    """Foydalanuvchi OKED kodlariga (bo'lim/bo'linma) tegishli loyihalar (muhokama tugashi
    yaqinlari birinchi). codes ichida 'ALL' bo'lsa — barchasi."""
    import oked
    codes = set(codes or [])
    sql = "SELECT * FROM drafts" + (" WHERE status='IN_DISCUSSION'" if active_only else "")
    out = []
    for r in await _fetch(sql + " ORDER BY end_date, id DESC"):
        ok = {x for x in (r["oked"] or "").split(",") if x}
        if ok and ("ALL" in codes or oked.match(ok, codes)):
            out.append(r)
    return out[:limit]


async def get_draft(draft_id: int) -> dict | None:
    return await _fetchone("SELECT * FROM drafts WHERE id=?", draft_id)


async def set_draft_text(draft_id: int, text: str):
    await _execute("UPDATE drafts SET text=? WHERE id=?", text, draft_id)


async def pending_drafts() -> list[dict]:
    return await _fetch("SELECT * FROM drafts WHERE status='IN_DISCUSSION' AND notified=0")


async def mark_drafts_notified(ids: list[int]):
    for i in ids:
        await _execute("UPDATE drafts SET notified=1 WHERE id=?", i)


async def draft_stats() -> dict:
    r = await _fetchone("SELECT COUNT(*) AS n FROM drafts WHERE status='IN_DISCUSSION'")
    return {"in_discussion": r["n"], "last_sync": await meta_get("drafts_last_sync")}


# ---------------- aktlar embeddinglari (ma'no bo'yicha qidiruv) ----------------
async def get_act_vecs(model: str) -> dict[str, list[float]]:
    import json
    return {r["lex_id"]: json.loads(r["vec"])
            for r in await _fetch("SELECT lex_id, vec FROM act_vecs WHERE model=?", model)}


async def save_act_vecs(model: str, vecs: dict[str, list[float]]):
    import json
    await _executemany(
        "INSERT INTO act_vecs (lex_id, model, vec) VALUES (?, ?, ?) "
        "ON CONFLICT (lex_id) DO UPDATE SET model=excluded.model, vec=excluded.vec",
        [(k, model, json.dumps([round(x, 5) for x in v])) for k, v in vecs.items()])
