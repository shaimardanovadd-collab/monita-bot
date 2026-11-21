"""AI yordamchi: kontekst yig'ish (qonun moddalari + reestr + yangiliklar) va javobni formatlash.
Bot, demo va web-panel bir xil funksiyadan foydalanadi."""
import re
import time
from datetime import date
from html import escape

import ai
import db
import legal
from texts import SECTORS, sector_names, t


async def build_context(sectors: list[str], question: str) -> tuple[str, list[dict]]:
    """Qaytaradi: (model uchun kontekst, manbalar ro'yxati [{title, path, url}])."""
    lines = [f"Foydalanuvchi sohalari: {sector_names(sectors)}",
             f"Bugungi sana: {date.today().isoformat()}"]
    terms = legal.query_terms(question)
    acts = await db.acts_for_oked(legal.oked_for_sectors(sectors))

    chunks = await db.search_chunks(terms, [a["lex_id"] for a in acts], limit=6)
    sources, seen = [], set()
    if chunks:
        lines.append("\nQONUN MATNIDAN PARCHALAR (Lex.uz):")
        for c in chunks:
            lines.append(f"[{c['title']}, {c['path']}"
                         + (f". {c['heading']}" if c.get("heading") else "")
                         + f" | {c['url']}]\n{c['content'][:1200]}")
            key = (c["lex_id"], c["path"])
            if key not in seen:
                seen.add(key)
                sources.append({"title": c["title"], "path": c["path"], "url": c["url"],
                                "lex_id": c["lex_id"]})

    def act_score(a):
        hay = legal.normalize(f"{a['title']} {a['topic']}")
        return sum(1 for term in terms if term in hay)
    ranked = sorted(acts, key=act_score, reverse=True)
    top = [a for a in ranked if act_score(a) > 0][:10] or ranked[:5]
    if top:
        lines.append("\nTEGISHLI AMALDAGI HUJJATLAR (reestrdan):")
        for a in top:
            lines.append(f"- {a['act_type']} {a['requisites']} «{a['title']}» "
                         f"(kuchga kirgan: {a['effective'] or '—'}) {a['url']}")

    updates = await db.latest_updates(sectors, limit=5)
    if updates:
        lines.append("\nBOT YANGILIKLARI:")
        for u in updates:
            lines.append(f"- {u['title']} | Kuchga kirish: {u.get('effective') or '—'} | "
                         f"{u['summary']}" + (f" | {u['source_url']}" if u.get("source_url") else ""))
    deadlines = await db.upcoming_deadlines(sectors, limit=5)
    if deadlines:
        lines.append("\nMUHIM MUDDATLAR:")
        for d in deadlines:
            lines.append(f"- {d['due_date']}: {d['title']}"
                         + (f" — {d['description']}" if d.get("description") else ""))
    return "\n".join(lines), sources


async def run(user_id: int, question: str, sectors: list[str], lang: str) -> dict:
    """{'answer', 'sources', 'context', 'ms'} yoki AIError ko'taradi."""
    sectors = sectors or list(SECTORS.keys())
    t0 = time.time()
    context, sources = await build_context(sectors, question)
    answer = await ai.ask(user_id, question, context, lang)
    return {"answer": answer, "sources": sources, "context": context,
            "ms": int((time.time() - t0) * 1000)}


def error_text(e: Exception, lang: str) -> str:
    code = getattr(e, "code", "other")
    return t({"busy": "ai_err_busy", "connect": "ai_err_connect",
              "empty": "ai_err_empty"}.get(code, "ai_err_other"), lang)


def md_to_html(text: str) -> str:
    """Modelning markdown belgilarini Telegram HTML ga o'tkazadi."""
    s = escape(text)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"(?m)^\s*[\*\-]\s+", "• ", s)
    s = re.sub(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)", r"<i>\1</i>", s)
    s = re.sub(r"(?m)^#{1,6}\s*(.+)$", r"<b>\1</b>", s)
    return s


def sources_html(sources: list[dict], lang: str, limit: int = 4) -> str:
    if not sources:
        return ""
    items = [f'• <a href="{escape(s["url"], quote=True)}">{escape(s["title"][:70])}</a>, '
             f'{escape(s["path"])}' for s in sources[:limit]]
    return "\n\n" + t("ai_sources", lang) + "\n" + "\n".join(items)


def split_message(text: str, limit: int = 3800) -> list[str]:
    parts = []
    while len(text) > limit:
        cut = text.rfind("\n", 0, limit)
        cut = cut if cut > limit // 2 else limit
        parts.append(text[:cut])
        text = text[cut:].lstrip("\n")
    parts.append(text)
    return parts
