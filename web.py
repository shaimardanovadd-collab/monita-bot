"""HTTP: /health, /tick (cron) va test uchun web-panel /panel?key=WEBHOOK_SECRET."""
import asyncio
import hmac
import os

from aiogram import Bot
from aiohttp import web

import admin
import ai
import assistant
import db
import jobs
import legal
from common import (ADMIN_IDS, WEBHOOK_SECRET, broadcast, render_act_notice, render_reminder,
                    render_update)
import oked

PANEL_HTML = os.path.join(os.path.dirname(os.path.abspath(__file__)), "panel.html")


def _authorized(request: web.Request) -> bool:
    key = request.query.get("key") or request.headers.get("X-Panel-Key", "")
    return hmac.compare_digest(key, WEBHOOK_SECRET)


def setup_routes(app: web.Application, bot: Bot):
    async def health(_):
        return web.Response(text="ok")

    async def tick(request):
        # cron-job.org har 10 daqiqada: server uxlamaydi + eslatmalar + rejali tekshiruv
        if not _authorized(request):
            return web.Response(status=403, text="forbidden")
        asyncio.create_task(jobs.periodic(bot))
        return web.Response(text="ok")

    async def panel(request):
        if not _authorized(request):
            return web.Response(status=403, text="forbidden: /panel?key=WEBHOOK_SECRET")
        with open(PANEL_HTML, encoding="utf-8") as f:
            return web.Response(text=f.read(), content_type="text/html")

    def guard(handler):
        async def wrapped(request):
            if not _authorized(request):
                return web.json_response({"error": "forbidden"}, status=403)
            try:
                return await handler(request)
            except Exception as e:  # noqa: BLE001
                return web.json_response({"error": f"{type(e).__name__}: {e}"}, status=500)
        return wrapped

    async def api_status(_):
        d = await admin.diagnostics(bot)
        d["sectors"] = {k: {"emoji": oked.SECTIONS[k]["emoji"], "uz": oked.SECTIONS[k]["uz"],
                            "ru": oked.SECTIONS[k]["ru"]} for k in oked.BUSINESS}
        return web.json_response(d)

    async def api_ask(request):
        body = await request.json()
        q = (body.get("question") or "").strip()
        if not q:
            return web.json_response({"error": "empty question"}, status=400)
        sectors = oked.normalize(body.get("sectors", [])) or ["G"]
        if body.get("reset", True):
            ai.reset(-1)
        try:
            res = await assistant.run(-1, q, sectors, body.get("lang", "uz"))
        except ai.AIError as e:
            ctx, sources = await assistant.build_context(sectors, q)
            return web.json_response({"error": f"AI: {e}", "context": ctx, "sources": sources})
        return web.json_response(res)

    async def api_search(request):
        body = await request.json()
        q = body.get("question") or ""
        sectors = oked.normalize(body.get("sectors", [])) or ["G"]
        terms = legal.query_terms(q)
        acts = await db.acts_for_oked(legal.oked_for_sectors(sectors))
        chunks = await db.search_chunks(terms, [x["lex_id"] for x in acts], limit=10)
        for c in chunks:
            c.pop("search", None)
            c["score"] = round(float(c.get("score") or 0), 4)
            c["content"] = c["content"][:600]
        return web.json_response({"terms": terms, "acts_in_scope": len(acts), "chunks": chunks})

    async def api_acts(request):
        sectors = oked.normalize(request.query.get("sectors", "").split(","))
        acts = (await db.acts_for_oked(legal.oked_for_sectors(sectors)) if sectors
                else await db.all_acts())
        with_text = await db.lex_ids_with_text()
        return web.json_response([{**{k: x.get(k) for k in (
            "lex_id", "title", "oked", "topic", "act_type", "requisites", "effective", "url",
            "source")}, "has_text": x["lex_id"] in with_text} for x in acts])

    async def api_demo(request):
        """Demo xabarni barcha adminlarga yuboradi (Telegram'da ko'rish uchun)."""
        body = await request.json()
        kind = body.get("kind")
        admins = [{"user_id": a, "lang": await _lang(a)} for a in ADMIN_IDS]
        if not admins:
            return web.json_response({"error": "ADMIN_IDS bo'sh"}, status=400)
        if kind in ("new", "chg"):
            acts = await db.all_acts()
            act = next((x for x in acts if x["oked"] != "ALL"), acts[0] if acts else None)
            if not act:
                return web.json_response({"error": "aktlar yo'q"}, status=400)
            res = await broadcast(bot, admins, lambda lg: render_act_notice(
                act, lg, "new" if kind == "new" else "changed", demo=True))
        elif kind == "news":
            u = {"id": None, "title": "Demo: Import jarayonlariga oid yangi talablar",
                 "sectors": ["G", "H"], "summary": "Bojxona deklaratsiyasi elektron shaklda.",
                 "effective": None, "source_url": "https://lex.uz"}
            res = await broadcast(bot, admins, lambda lg: render_update(u, lg, demo=True))
        elif kind == "rem":
            from datetime import date, timedelta
            d = {"title": "Demo: QQS hisobot", "sectors": ["G"],
                 "due_date": (date.today() + timedelta(days=3)).isoformat(),
                 "description": "my.soliq.uz"}
            res = await broadcast(bot, admins, lambda lg: render_reminder(d, lg, demo=True))
        else:
            return web.json_response({"error": "kind?"}, status=400)
        return web.json_response({"sent": res[0], "failed": res[1]})

    async def _lang(uid):
        u = await db.get_user(uid)
        return (u or {}).get("lang") or "uz"

    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    app.router.add_get("/tick", tick)
    app.router.add_get("/panel", panel)
    app.router.add_get("/panel/api/status", guard(api_status))
    app.router.add_post("/panel/api/ask", guard(api_ask))
    app.router.add_post("/panel/api/search", guard(api_search))
    app.router.add_get("/panel/api/acts", guard(api_acts))
    app.router.add_post("/panel/api/demo", guard(api_demo))
