"""AI yordamchi: kontekst yig'ish (qonun moddalari + reestr + yangiliklar) va javobni formatlash.
Bot, demo va web-panel bir xil funksiyadan foydalanadi."""
import re
import time
from datetime import date
from html import escape

import ai
import db
import legal
import oked
from texts import t


async def build_context(sectors: list[str], question: str
                        ) -> tuple[str, dict, list[dict], list[str]]:
    """Model uchun kontekst — FAQAT bot bazalaridan, har bir manba tegi bilan:
    [S..] — bazadagi qonun matni parchalari, [R..] — reestrdagi amaldagi hujjatlar,
    [N..] — bot yangiliklari, [D..] — muhim muddatlar.
    Matni bazada yo'q, lekin savolga mos aktlar uchun Lex.uz havolalari qaytariladi —
    Gemini ularni o'zi ochib o'qiydi (URL context).
    Qaytaradi: (kontekst, katalog {teg: manba}, zaxira manbalar, o'qiladigan havolalar)."""
    terms = legal.query_terms(question)
    acts = await db.acts_for_oked(legal.oked_for_sectors(sectors))
    with_text = await db.lex_ids_with_text()
    catalog: dict[str, dict] = {}

    def act_score(a):
        hay = legal.normalize(f"{a['title']} {a['topic']}")
        return sum(1 for term in terms if term in hay)
    ranked = sorted(acts, key=lambda a: (-act_score(a), a["oked"] == "ALL",
                                         -(int((a["effective"] or "0")[:4] or 0))))
    tag_of = {a["lex_id"]: f"R{i}" for i, a in enumerate(ranked, 1)}
    for a in ranked:
        catalog[tag_of[a["lex_id"]]] = {
            "title": a["title"], "path": f"{a['act_type']} {a['requisites']}".strip(),
            "url": a["url"], "lex_id": a["lex_id"], "kind": "register"}

    # 1) bazadagi matndan eng mos moddalar
    chunks = await db.search_chunks(terms, [a["lex_id"] for a in acts], limit=12)
    matched = [a for a in ranked if act_score(a) > 0]
    if not matched and not chunks and ai.is_configured() and ranked:
        # nomi bo'yicha ham, matn bo'yicha ham topilmadi — Gemini reestrdan o'zi tanlaydi
        reg = [f"{tag_of[a['lex_id']]} | {a['title']} | {a['topic'] or ''}" for a in ranked]
        picked = set(await ai.pick_acts(question, reg))
        matched = [a for a in ranked if tag_of[a["lex_id"]] in picked]
    if len(chunks) < 4:
        for a in [x for x in matched if x["lex_id"] in with_text][:2]:
            for c in await db.get_chunks(a["lex_id"], "uz", limit=3):
                chunks.append({**c, "lex_id": a["lex_id"], "title": a["title"], "url": a["url"]})
    # 2) matni bazada yo'q mos aktlar — Gemini Lex.uz sahifasini o'zi o'qiydi
    to_read = [a for a in matched if a["lex_id"] not in with_text][:ai.MAX_URLS]
    read_ids = {a["lex_id"] for a in to_read}

    lines = [f"Foydalanuvchi faoliyati (OKED): {oked.for_ai(sectors)}",
             f"Bugungi sana: {date.today().isoformat()}",
             f"Bazada: {len(acts)} ta tegishli akt, shundan "
             f"{len({a['lex_id'] for a in acts} & with_text)} tasining to'liq matni bor."]
    seen, s_lines = set(), []
    for c in chunks:
        key = (c["lex_id"], c["path"])
        if key in seen:
            continue
        seen.add(key)
        tag = f"S{len(seen)}"
        catalog[tag] = {"title": c["title"], "path": c["path"], "url": c["url"],
                        "lex_id": c["lex_id"], "kind": "text"}
        s_lines.append(f"[{tag}] «{c['title']}», {c['path']}"
                       + (f". {c['heading']}" if c.get("heading") else "")
                       + f"\n{c['content'][:2000]}")
    lines.append("\n=== QONUN MATNIDAN PARCHALAR (bazadan, Lex.uz) ===" if s_lines
                 else "\n=== QONUN MATNIDAN PARCHALAR: bazada savolga mos modda topilmadi ===")
    lines += s_lines
    if to_read:
        lines.append("\n=== O'QISH UCHUN LEX.UZ SAHIFALARI (URL context bilan o'zing och) ===")
        for a in to_read:
            lines.append(f"[{tag_of[a['lex_id']]}] «{a['title']}» → {a['url']}")
    if ranked:
        lines.append(f"\n=== AMALDAGI HUJJATLAR REESTRI ({len(ranked)} ta, savolga moslari birinchi) ===")
        for a in ranked:
            mark = (" | matni bazada" if a["lex_id"] in with_text
                    else " | Lex.uz sahifasi o'qiladi" if a["lex_id"] in read_ids else "")
            lines.append(f"[{tag_of[a['lex_id']]}] {a['act_type']} {a['requisites']} «{a['title']}» | "
                         f"mavzu: {a['topic'] or '—'} | kuchga kirgan: {a['effective'] or '—'}{mark}")

    # 3) muhokamadagi NPA loyihalari (regulation.adliya.uz) — hali qabul qilinmagan
    drafts_all = await db.drafts_for_oked(oked.letters(sectors), active_only=True, limit=40)

    def draft_score(d):
        hay = legal.normalize(f"{d['name_uz']} {d['name_ru']}")
        return sum(1 for term in terms if term in hay)
    drafts_all.sort(key=lambda d: -draft_score(d))
    if drafts_all:
        lines.append("\n=== MUHOKAMADAGI NPA LOYIHALARI (regulation.adliya.uz, HALI QABUL QILINMAGAN) ===")
        for i, d in enumerate(drafts_all, 1):
            tag = f"P{i}"
            import drafts as drafts_mod
            catalog[tag] = {"title": d["name_ru"] if d["name_ru"] else d["name_uz"],
                            "path": f"loyiha, muhokama {d['end_date']} gacha",
                            "url": drafts_mod.page_url(d), "lex_id": f"draft{d['id']}", "kind": "draft"}
            lines.append(f"[{tag}] «{d['name_uz']}» / «{d['name_ru']}» | ishlab chiquvchi: {d['org_uz']} | "
                         f"muhokama: {d['start_date']} — {d['end_date']}")
            if i <= 2 and draft_score(d) > 0:
                text = await draft_text(d)
                if text:
                    lines.append(f"[{tag}] LOYIHA MATNI (parcha):\n{text[:4000]}")

    # 4) bot yangiliklari va muddatlar
    for i, u in enumerate(await db.latest_updates(sectors, limit=5), 1):
        if i == 1:
            lines.append("\n=== BOT YANGILIKLARI ===")
        catalog[f"N{i}"] = {"title": u["title"], "path": "", "url": u.get("source_url") or "",
                            "kind": "news"}
        lines.append(f"[N{i}] {u['title']} | kuchga kirish: {u.get('effective') or '—'} | "
                     f"{u['summary']}" + (f" | {u['details'][:600]}" if u.get("details") else ""))
    for i, d in enumerate(await db.upcoming_deadlines(sectors, limit=5), 1):
        if i == 1:
            lines.append("\n=== MUHIM MUDDATLAR ===")
        catalog[f"D{i}"] = {"title": d["title"], "path": d["due_date"], "url": "", "kind": "deadline"}
        lines.append(f"[D{i}] {d['due_date']}: {d['title']}"
                     + (f" — {d['description']}" if d.get("description") else ""))

    fallback = ([v for k, v in catalog.items() if k.startswith("S")][:3]
                or [catalog[tag_of[a["lex_id"]]] for a in (matched or ranked)[:3]])
    return "\n".join(lines), catalog, fallback, [a["url"] for a in to_read]


_TAG_RX = re.compile(r"\[((?:[SRNDP]\d+)(?:\s*[,;]\s*[SRNDP]\d+)*)\]")


def apply_citations(answer: str, catalog: dict) -> tuple[str, list[dict]]:
    """[S3], [R5, S1] -> [1], [2][3]; faqat haqiqatda keltirilgan manbalar ro'yxati qaytadi.
    Katalogda yo'q teglar (model o'ylab topgan) olib tashlanadi."""
    order: dict[str, int] = {}

    def repl(m):
        out = []
        for tag in re.split(r"\s*[,;]\s*", m.group(1)):
            if tag not in catalog:
                continue
            key = (catalog[tag].get("lex_id"), catalog[tag].get("path"), catalog[tag]["title"])
            if key not in order:
                order[key] = len(order) + 1
            out.append(f"[{order[key]}]")
        return "".join(dict.fromkeys(out))
    text = _TAG_RX.sub(repl, answer)
    text = re.sub(r"[ \t]+([.,;:])", r"\1", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    by_key = {}
    for v in catalog.values():
        by_key.setdefault((v.get("lex_id"), v.get("path"), v["title"]), v)
    sources = [dict(by_key[k], n=n) for k, n in sorted(order.items(), key=lambda x: x[1])]
    return text, sources


async def run(user_id: int, question: str, sectors: list[str], lang: str) -> dict:
    """{'answer', 'sources', 'cited', 'context', 'ms'} yoki AIError ko'taradi."""
    sectors = sectors or list(oked.BUSINESS)
    t0 = time.time()
    context, catalog, fallback, urls = await build_context(sectors, question)
    meta: dict = {}
    raw = await ai.ask(user_id, question, context, lang, urls=urls, meta=meta)
    answer, cited = apply_citations(raw, catalog)
    return {"answer": answer, "sources": cited or fallback, "cited": bool(cited),
            "context": context, "urls": urls, "read": meta.get("read", []),
            "model": meta.get("model"), "ms": int((time.time() - t0) * 1000)}


SUMMARY_PROMPT = {
    "uz": "Quyidagi rasmiy hujjat bo'yicha tadbirkor uchun QISQA yangilik yoz (4–6 gap, o'zbek tilida): "
          "1) hujjat nima haqida; 2) kimga tegishli; 3) tadbirkor nima qilishi kerak. "
          "Faqat berilgan matnga tayan, yo'q narsani o'ylab topma. Manba teglari shart emas. "
          "Oxirida «Manba: Lex.uz» deb yoz.",
    "ru": "По официальному акту ниже напиши КОРОТКУЮ новость для предпринимателя (4–6 предложений, "
          "на русском): 1) о чём акт; 2) кого касается; 3) что нужно сделать бизнесу. "
          "Опирайся только на данный текст, ничего не выдумывай. Теги источников не нужны. "
          "В конце: «Источник: Lex.uz».",
}


async def act_summary(act: dict, user_codes: list[str], lang: str) -> dict:
    """Akt bo'yicha AI qisqa mazmuni (yangilik). Matn bo'lmasa — faqat nomi asosida."""
    chunks = await db.get_chunks(act["lex_id"], lang, limit=60)
    text = "\n\n".join(f"[{c['path']}] {c.get('heading') or ''}\n{c['content']}"
                        for c in chunks)[:30000]   # Gemini hujjatni to'liqroq o'qiydi
    context = (f"HUJJAT: {act.get('act_type')} {act.get('requisites')} «{act['title']}», "
               f"kuchga kirgan: {act.get('effective') or '—'}, havola: {act['url']}\n"
               f"O'quvchi faoliyati (OKED): {oked.for_ai(user_codes)}\n\n"
               f"MATN:\n{text or '(matn bazada yoq)'}")
    uid = -100000 - (abs(hash(act["lex_id"])) % 100000)   # alohida suhbat (tarixsiz)
    ai.reset(uid)
    t0 = time.time()
    meta: dict = {}
    # matn bazada bo'lmasa — Gemini Lex.uz sahifasini o'zi o'qiydi
    answer = await ai.ask(uid, SUMMARY_PROMPT[lang], context, lang,
                          urls=None if chunks else [act["url"]], meta=meta)
    ai.reset(uid)
    read_ok = any(r.get("status") == "SUCCESS" for r in meta.get("read", []))
    return {"answer": answer, "has_text": bool(chunks) or read_ok, "read": meta.get("read", []),
            "ms": int((time.time() - t0) * 1000)}


async def latest_acts_for(codes: list[str], limit: int = 6) -> list[dict]:
    """Foydalanuvchi OKED bo'limiga xos so'nggi aktlar (avval aniq bo'lim, keyin umumiylar)."""
    acts = await db.acts_for_oked(legal.oked_for_sectors(codes))
    specific = sorted([a for a in acts if a["oked"] != "ALL"],
                      key=lambda x: x["effective"] or "", reverse=True)
    general = sorted([a for a in acts if a["oked"] == "ALL"],
                     key=lambda x: x["effective"] or "", reverse=True)
    return (specific + general)[:limit]


async def draft_text(d: dict) -> str:
    """Loyiha matni: bazadan yoki portal API dan (keshlanadi)."""
    if d.get("text"):
        return d["text"]
    if not d.get("text_id"):
        return ""
    import drafts as drafts_mod
    try:
        text = await drafts_mod.fetch_text(d["text_id"])
    except Exception:  # noqa: BLE001
        return ""
    if text:
        await db.set_draft_text(d["id"], text)
        d["text"] = text
    return text


DRAFT_PROMPT = {
    "uz": "Quyidagi NPA LOYIHASI (hali qabul qilinmagan, jamoatchilik muhokamasida) bo'yicha tadbirkor "
          "uchun qisqa tahlil yoz (o'zbek tilida, 5–8 gap yoki ro'yxat): 1) nimani o'zgartirish taklif "
          "qilinmoqda; 2) kimga ta'sir qiladi (o'quvchi faoliyatini hisobga ol); 3) biznes nima qilishi "
          "kerak — muhokama tugash sanasigacha portalda taklif qoldirish mumkinligini ayt. Faqat berilgan "
          "matnga tayan, o'ylab topma, teglar shart emas. Bu loyiha ekanini, qabul qilinmaganini ta'kidla.",
    "ru": "По ПРОЕКТУ НПА ниже (ещё не принят, на общественном обсуждении) напиши короткий разбор для "
          "предпринимателя (на русском, 5–8 предложений или список): 1) что предлагается изменить; "
          "2) кого коснётся (учти деятельность читателя); 3) что делать бизнесу — скажи, что до даты "
          "окончания обсуждения можно оставить предложение на портале. Опирайся только на текст, ничего "
          "не выдумывай, теги не нужны. Подчеркни, что это проект и он ещё не принят.",
}


async def draft_summary(d: dict, user_codes: list[str], lang: str) -> dict:
    import drafts as drafts_mod
    text = await draft_text(d)
    context = (f"LOYIHA: «{d['name_uz']}» / «{d['name_ru']}»\nIshlab chiquvchi: {d['org_uz']}\n"
               f"Soha: {drafts_mod.speciality_name(d.get('speciality'))}\n"
               f"Muhokama: {d['start_date']} — {d['end_date']}\nHavola: {drafts_mod.page_url(d)}\n"
               f"O'quvchi faoliyati (OKED): {oked.for_ai(user_codes)}\n\n"
               f"LOYIHA MATNI:\n{text[:30000] if text else '(matn olinmadi)'}")
    uid = -300000 - int(d["id"]) % 100000
    ai.reset(uid)
    t0 = time.time()
    answer = await ai.ask(uid, DRAFT_PROMPT[lang], context, lang)
    ai.reset(uid)
    return {"answer": answer, "has_text": bool(text), "ms": int((time.time() - t0) * 1000)}


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


def sources_html(sources: list[dict], lang: str, limit: int = 8, cited: bool = True) -> str:
    if not sources:
        return ""
    head = t("ai_sources" if cited else "ai_related", lang)
    items = []
    for i, s in enumerate(sources[:limit], 1):
        num = f"[{s.get('n', i)}] " if cited else "• "
        title = escape(s["title"][:90])
        link = f'<a href="{escape(s["url"], quote=True)}">{title}</a>' if s.get("url") else title
        items.append(f"{num}{link}" + (f", {escape(s['path'])}" if s.get("path") else ""))
    return "\n\n" + head + "\n" + "\n".join(items)


def read_note(res: dict, lang: str) -> str:
    n = sum(1 for r in res.get("read") or [] if r.get("status") == "SUCCESS")
    return ("\n" + t("ai_read", lang, n=n)) if n else ""


def split_message(text: str, limit: int = 3800) -> list[str]:
    parts = []
    while len(text) > limit:
        cut = text.rfind("\n", 0, limit)
        cut = cut if cut > limit // 2 else limit
        parts.append(text[:cut])
        text = text[cut:].lstrip("\n")
    parts.append(text)
    return parts
