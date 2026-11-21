"""
Monita Bot — biznes uchun qonunchilik monitoringi (Telegram, o'zbek/rus).
Ishga tushirish: python bot.py
"""
import asyncio
from datetime import date
from html import escape

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BotCommand, CallbackQuery, Message

import admin
import ai
import assistant
import db
import jobs
import legal
from common import (ADMIN_IDS, BASE_URL, BOT_TOKEN, PORT, PUBLIC_DEMO, WEBHOOK_SECRET,
                    back_row, days_left_text, fmt_date, get_lang, ikb, is_admin, log,
                    notify_admins, render_act_notice, render_update, reply_kb, set_lang, show)
from texts import (BOT_DESCRIPTION, BOT_SHORT, LINE, SECTORS, all_variants, sector_name,
                   sector_names, t)

router = Router(name="user")
LAWS_PER_PAGE = 6


class UserStates(StatesGroup):
    feedback = State()


# ======================= EKRANLAR =======================
async def ensure_user(u) -> dict:
    await db.upsert_user(u.id, u.full_name, u.username)
    return await db.get_user(u.id)


def menu_kb(lang: str, notify: bool, uid: int):
    rows = [
        [(t("btn_ai", lang), "ai")],
        [(t("btn_news", lang), "news"), (t("btn_deadlines", lang), "dl")],
        [(t("btn_laws", lang), "laws:1"), (t("btn_profile", lang), "prof")],
        [(t("btn_notify_on" if notify else "btn_notify_off", lang), "notify"),
         (t("btn_lang", lang), "lang")],
        [(t("btn_feedback", lang), "fb"), (t("btn_about", lang), "about")],
    ]
    extra = []
    if is_admin(uid) or PUBLIC_DEMO:
        extra.append((t("btn_demo", lang), "demo"))
    if is_admin(uid):
        extra.append((t("btn_admin", lang), "adm"))
    if extra:
        rows.append(extra)
    return ikb(rows)


async def menu_screen(user: dict, lang: str) -> tuple:
    text = t("menu", lang, sectors=escape(sector_names(user["sectors"], lang)),
             notify=t("on" if user["notify"] else "off", lang))
    return text, menu_kb(lang, bool(user["notify"]), user["user_id"])


def lang_kb(prefix: str = "setlang"):
    return ikb([[("🇺🇿 O'zbekcha", f"{prefix}:uz"), ("🇷🇺 Русский", f"{prefix}:ru")]])


def sectors_kb(selected: list[str], lang: str):
    rows, row = [], []
    for key in SECTORS:
        mark = "✅" if key in selected else "▫️"
        row.append((f"{mark} {sector_name(key, lang)}", f"sec:{key}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([(t("btn_continue", lang), "sec:done")])
    return ikb(rows)


async def open_menu(target, user_id: int, new: bool = False):
    user = await db.get_user(user_id)
    lang = await get_lang(user_id)
    if not user or not user["sectors"]:
        await show(target, t("choose_sectors", lang), sectors_kb([], lang), new=new)
        return
    text, kb = await menu_screen(user, lang)
    await show(target, text, kb, new=new)


# ======================= START: TIL TANLASH =======================
@router.message(CommandStart())
@router.message(Command("lang"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user = await ensure_user(message.from_user)
    is_start = (message.text or "").startswith("/start")
    if user.get("lang") and is_start:
        lang = await get_lang(user["user_id"])
        await message.answer(t("start_again", lang, name=escape(message.from_user.first_name or "")),
                             reply_markup=reply_kb(lang))
        await open_menu(message, user["user_id"], new=True)
        return
    # yangi foydalanuvchi yoki /lang — avval til
    await message.answer("⚖️ <b>Monita Bot</b>\n" + LINE + "\n" + t("choose_lang"),
                         reply_markup=lang_kb())


@router.callback_query(F.data == "lang")
async def cb_lang(cq: CallbackQuery):
    await show(cq, t("choose_lang"), lang_kb())
    await cq.answer()


@router.callback_query(F.data.startswith("setlang:"))
async def cb_set_lang(cq: CallbackQuery):
    lang = cq.data.split(":")[1]
    user = await ensure_user(cq.from_user)
    first_time = not user.get("lang")
    await set_lang(cq.from_user.id, lang)
    await cq.answer(t("lang_set", lang))
    if first_time:
        await cq.message.edit_text(t("welcome", lang, name=escape(cq.from_user.first_name or "")))
        await cq.message.answer(t("lang_set", lang), reply_markup=reply_kb(lang))
        await open_menu(cq.message, cq.from_user.id, new=True)
    else:
        # pastki tugmalar tilini ham yangilaymiz
        await cq.message.answer(t("lang_set", lang), reply_markup=reply_kb(lang))
        await open_menu(cq, cq.from_user.id)


# ======================= MENYU =======================
@router.message(Command("menu", "cancel"))
@router.message(F.text.in_(all_variants("btn_menu")))
async def msg_menu(message: Message, state: FSMContext):
    await state.clear()
    await ensure_user(message.from_user)
    await open_menu(message, message.from_user.id, new=True)


@router.callback_query(F.data == "m")
async def cb_menu(cq: CallbackQuery, state: FSMContext):
    await state.clear()
    await ensure_user(cq.from_user)
    await open_menu(cq, cq.from_user.id)
    await cq.answer()


# ---- Profil va sohalar ----
@router.callback_query(F.data == "prof")
async def cb_profile(cq: CallbackQuery):
    user = await ensure_user(cq.from_user)
    lang = await get_lang(cq.from_user.id)
    sectors = "\n".join(f"   {sector_name(k, lang)}" for k in user["sectors"]) or "   —"
    text = t("profile", lang, name=escape(cq.from_user.full_name), sectors=sectors,
             notify=t("on" if user["notify"] else "off", lang))
    await show(cq, text, ikb([[(t("btn_edit_sectors", lang), "sec")],
                              [(t("btn_lang", lang), "lang")], back_row(lang)]))
    await cq.answer()


@router.callback_query(F.data == "sec")
async def cb_sectors(cq: CallbackQuery):
    user = await ensure_user(cq.from_user)
    lang = await get_lang(cq.from_user.id)
    await show(cq, t("choose_sectors", lang), sectors_kb(user["sectors"], lang))
    await cq.answer()


@router.callback_query(F.data.startswith("sec:"))
async def cb_sector_toggle(cq: CallbackQuery):
    """Holatsiz: har bosishda bazaga yoziladi (server qayta ishga tushsa ham ishlaydi)."""
    key = cq.data.split(":", 1)[1]
    user = await ensure_user(cq.from_user)
    lang = await get_lang(cq.from_user.id)
    selected = list(user["sectors"])
    if key == "done":
        if not selected:
            await cq.answer(t("need_one_sector", lang), show_alert=True)
            return
        await cq.answer(t("saved", lang))
        await open_menu(cq, cq.from_user.id)
        return
    if key in selected:
        selected.remove(key)
    elif key in SECTORS:
        selected.append(key)
    await db.set_sectors(cq.from_user.id, selected)
    await cq.message.edit_reply_markup(reply_markup=sectors_kb(selected, lang))
    await cq.answer()


@router.callback_query(F.data == "notify")
async def cb_notify(cq: CallbackQuery):
    await ensure_user(cq.from_user)
    lang = await get_lang(cq.from_user.id)
    on = await db.toggle_notify(cq.from_user.id)
    await cq.answer(t("notif_on" if on else "notif_off", lang))
    await open_menu(cq, cq.from_user.id)


# ---- Yangiliklar ----
async def need_sectors(cq: CallbackQuery) -> dict | None:
    user = await ensure_user(cq.from_user)
    if not user["sectors"]:
        lang = await get_lang(cq.from_user.id)
        await cq.answer(t("need_profile", lang), show_alert=True)
        await show(cq, t("choose_sectors", lang), sectors_kb([], lang))
        return None
    return user


@router.callback_query(F.data == "news")
async def cb_news(cq: CallbackQuery):
    user = await need_sectors(cq)
    if not user:
        return
    lang = await get_lang(cq.from_user.id)
    items = await db.latest_updates(user["sectors"], limit=8)
    if not items:
        await show(cq, t("no_news", lang), ikb([back_row(lang)]))
        await cq.answer()
        return
    lines = [t("news_header", lang), LINE]
    buttons = []
    for i, u in enumerate(items, 1):
        lines.append(f"<b>{i}.</b> {escape(u['title'])}\n"
                     f"     📅 {fmt_date(u.get('effective'), lang)}")
        buttons.append((f"📄 {i}", f"upd:{u['id']}"))
    rows = [buttons[i:i + 4] for i in range(0, len(buttons), 4)] + [back_row(lang)]
    await show(cq, "\n".join(lines), ikb(rows))
    await cq.answer()


@router.callback_query(F.data.startswith("upd:"))
async def cb_update_detail(cq: CallbackQuery):
    lang = await get_lang(cq.from_user.id)
    u = await db.get_update(int(cq.data.split(":")[1]))
    if not u:
        await cq.answer(t("not_found", lang), show_alert=True)
        return
    card, _ = render_update(u, lang)
    if u.get("details"):
        card += f"\n{LINE}\n{escape(u['details'])}"
    rows = [[(t("btn_source", lang), u["source_url"])]] if u.get("source_url") else []
    rows.append(back_row(lang, "news"))
    await show(cq, card, ikb(rows))
    await cq.answer()


# ---- Muddatlar ----
@router.callback_query(F.data == "dl")
async def cb_deadlines(cq: CallbackQuery):
    user = await need_sectors(cq)
    if not user:
        return
    lang = await get_lang(cq.from_user.id)
    items = await db.upcoming_deadlines(user["sectors"])
    if not items:
        await show(cq, t("no_deadlines", lang), ikb([back_row(lang)]))
    else:
        lines = [t("deadlines_header", lang), LINE]
        for d in items:
            left = (date.fromisoformat(d["due_date"]) - date.today()).days
            icon = "🔴" if left <= 3 else "🟡" if left <= 7 else "🟢"
            lines.append(f"{icon} <b>{fmt_date(d['due_date'], lang)}</b> · "
                         f"{days_left_text(d['due_date'], lang)}\n     {escape(d['title'])}")
        await show(cq, "\n".join(lines), ikb([back_row(lang)]))
    await cq.answer()


# ---- Qonunlar (sohaga tegishli aktlar ro'yxati) ----
@router.callback_query(F.data.startswith("laws:"))
async def cb_laws(cq: CallbackQuery):
    user = await need_sectors(cq)
    if not user:
        return
    lang = await get_lang(cq.from_user.id)
    acts = await db.acts_for_oked(legal.oked_for_sectors(user["sectors"]))
    with_text = await db.lex_ids_with_text()
    # avval sohaga xos aktlar, keyin umumiylar
    acts.sort(key=lambda x: (x["oked"] == "ALL", -(int((x["effective"] or "0")[:4] or 0))))
    pages = max(1, -(-len(acts) // LAWS_PER_PAGE))
    page = min(max(1, int(cq.data.split(":")[1])), pages)
    chunk = acts[(page - 1) * LAWS_PER_PAGE: page * LAWS_PER_PAGE]
    lines = [t("laws_header", lang, count=len(acts), page=page, pages=pages)]
    for x in chunk:
        icon = "📄" if x["lex_id"] in with_text else "▫️"
        scope = "🌍" if x["oked"] == "ALL" else "🎯"
        title = x["title"] if len(x["title"]) <= 120 else x["title"][:117] + "…"
        lines.append(f"{icon}{scope} <b>{escape(x['act_type'] or '')}</b> · "
                     f"{escape(x['requisites'] or '')}\n"
                     f'<a href="{escape(x["url"], quote=True)}">{escape(title)}</a>')
    nav = []
    if page > 1:
        nav.append((t("btn_prev", lang), f"laws:{page - 1}"))
    nav.append((f"{page}/{pages}", f"laws:{page}"))
    if page < pages:
        nav.append((t("btn_next", lang), f"laws:{page + 1}"))
    legend = ("🎯 — sohangizga xos · 🌍 — barcha uchun" if lang == "uz"
              else "🎯 — для вашей сферы · 🌍 — для всех")
    await show(cq, "\n\n".join(lines) + f"\n\n<i>{legend}</i>",
               ikb([nav, [(t("btn_ai", lang), "ai")], back_row(lang)]))
    await cq.answer()


# ---- Bot haqida ----
@router.callback_query(F.data == "about")
async def cb_about(cq: CallbackQuery):
    lang = await get_lang(cq.from_user.id)
    st = await db.chunk_stats()
    await show(cq, t("about", lang, acts=st["acts"]), ikb([back_row(lang)]))
    await cq.answer()


# ---- Savol yoki taklif ----
@router.callback_query(F.data == "fb")
async def cb_feedback(cq: CallbackQuery, state: FSMContext):
    lang = await get_lang(cq.from_user.id)
    await state.set_state(UserStates.feedback)
    await show(cq, t("ask_feedback", lang), ikb([back_row(lang)]))
    await cq.answer()


@router.message(UserStates.feedback, F.text, ~F.text.startswith("/"))
async def got_feedback(message: Message, state: FSMContext, bot: Bot):
    if message.text in all_variants("btn_ai"):
        await state.clear()
        await ai_intro(message)
        return
    await state.clear()
    lang = await get_lang(message.from_user.id)
    await db.add_feedback(message.from_user.id, message.text)
    u = message.from_user
    who = f"@{u.username}" if u.username else escape(u.full_name)
    await notify_admins(bot, f"✉️ <b>Murojaat / Обращение</b>\n{who} (ID <code>{u.id}</code>)\n\n"
                             f"{escape(message.text)}\n\n<code>/javob {u.id} </code>")
    await message.answer(t("feedback_thanks", lang), reply_markup=ikb([back_row(lang)]))


# ======================= AI YORDAMCHI =======================
@router.callback_query(F.data == "ai")
@router.message(F.text.in_(all_variants("btn_ai")))
async def ai_intro(event: Message | CallbackQuery, state: FSMContext | None = None):
    if state:
        await state.clear()
    uid = event.from_user.id
    await ensure_user(event.from_user)
    lang = await get_lang(uid)
    if not ai.is_configured():
        text = t("ai_off", lang)
    else:
        text = t("ai_intro", lang, acts=(await db.chunk_stats())["acts"])
    await show(event, text, ikb([[(t("btn_new_chat", lang), "ai:new")], back_row(lang)]))
    if isinstance(event, CallbackQuery):
        await event.answer()


@router.callback_query(F.data == "ai:new")
async def ai_new(cq: CallbackQuery):
    lang = await get_lang(cq.from_user.id)
    ai.reset(cq.from_user.id)
    await cq.answer(t("ai_new", lang))
    await cq.message.answer(t("ai_new", lang))


@router.callback_query(F.data.startswith("aiact:"))
async def ai_about_act(cq: CallbackQuery, bot: Bot):
    """Xabarnomadagi «AI: bu men uchun nima?» tugmasi."""
    lang = await get_lang(cq.from_user.id)
    act = await db.get_act(cq.data.split(":")[1])
    if not act:
        await cq.answer(t("not_found", lang), show_alert=True)
        return
    await cq.answer("🤖 …")
    q = t("ai_act_question", lang, title=act["title"], act_type=act["act_type"] or "",
          requisites=act["requisites"] or "")
    ai.reset(cq.from_user.id)
    await answer_question(bot, cq.message.chat.id, cq.from_user.id, q, show_question=True)


async def answer_question(bot: Bot, chat_id: int, uid: int, question: str,
                          show_question: bool = False):
    lang = await get_lang(uid)
    if not ai.is_configured():
        await bot.send_message(chat_id, t("ai_off", lang))
        return
    limit = ai.check_limits(uid, is_admin(uid))
    if limit:
        await bot.send_message(chat_id, t("ai_err_cooldown", lang) if limit == "cooldown"
                               else t("ai_err_daily", lang, n=ai.DAILY_LIMIT))
        return
    user = await db.get_user(uid) or {}
    await bot.send_chat_action(chat_id, "typing")
    try:
        res = await assistant.run(uid, question, user.get("sectors") or [], lang)
    except ai.AIError as e:
        log.warning("AI xatosi: %s", e)
        await bot.send_message(chat_id, assistant.error_text(e, lang))
        return
    except Exception as e:  # noqa: BLE001
        log.exception("AI kutilmagan xato: %s", e)
        await bot.send_message(chat_id, t("ai_err_other", lang))
        return
    head = f"❓ <i>{escape(question)}</i>\n\n" if show_question else ""
    body = head + assistant.md_to_html(res["answer"]) + assistant.sources_html(res["sources"], lang)
    kb = ikb([[(t("btn_new_chat", lang), "ai:new"), (t("btn_menu", lang), "m")]])
    parts = assistant.split_message(body)
    for i, part in enumerate(parts):
        try:
            await bot.send_message(chat_id, part, reply_markup=kb if i == len(parts) - 1 else None,
                                   disable_web_page_preview=True)
        except Exception:  # noqa: BLE001 — HTML buzilgan bo'lsa oddiy matn
            await bot.send_message(chat_id, part, parse_mode=None,
                                   reply_markup=kb if i == len(parts) - 1 else None)


@router.message(StateFilter(None), F.text, ~F.text.startswith("/"))
async def free_text(message: Message, bot: Bot):
    """Har qanday oddiy matn — AI yordamchiga savol (tugma bosish shart emas)."""
    user = await ensure_user(message.from_user)
    if not user.get("lang"):
        await message.answer(t("choose_lang"), reply_markup=lang_kb())
        return
    await answer_question(bot, message.chat.id, message.from_user.id, message.text)


@router.message(StateFilter(None), ~F.text)
async def other_messages(message: Message):
    lang = await get_lang(message.from_user.id)
    await message.answer(t("ai_text_only", lang), reply_markup=ikb([back_row(lang)]))


# ======================= ISHGA TUSHIRISH =======================
async def setup_bot_profile(bot: Bot):
    """Start tugmasidan oldin ko'rinadigan tavsif va buyruqlar — ikki tilda."""
    cmds = {
        "uz": [("menu", "🏠 Asosiy menyu"), ("lang", "🌐 Tilni o'zgartirish"),
               ("start", "▶️ Qayta boshlash")],
        "ru": [("menu", "🏠 Главное меню"), ("lang", "🌐 Сменить язык"),
               ("start", "▶️ Перезапуск")],
    }
    for lang_code in (None, "uz", "ru"):
        lg = lang_code or "uz"
        try:
            await bot.set_my_commands([BotCommand(command=c, description=d) for c, d in cmds[lg]],
                                      language_code=lang_code)
            await bot.set_my_description(BOT_DESCRIPTION[lg], language_code=lang_code)
            await bot.set_my_short_description(BOT_SHORT[lg], language_code=lang_code)
        except Exception as e:  # noqa: BLE001
            log.warning("Bot profili (%s) o'rnatilmadi: %s", lang_code, e)


def make_bot_and_dp() -> tuple[Bot, Dispatcher]:
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN topilmadi. .env yoki Render Environment'ni to'ldiring.")
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    # foydalanuvchi routeri birinchi: «🏠 Menyu» va /cancel har doim ishlaydi (admin formasida ham).
    # Erkin matn -> AI faqat hech qanday forma ochiq bo'lmaganda (StateFilter(None)).
    dp.include_router(router)
    dp.include_router(admin.router)
    return bot, dp


async def on_startup_common(bot: Bot):
    await db.init()
    await setup_bot_profile(bot)
    asyncio.create_task(jobs.periodic_loop(bot))
    asyncio.create_task(jobs.announce_new_acts(bot))
    log.info("Monita Bot ishga tushdi. Rejim: %s | Adminlar: %s | PUBLIC_DEMO=%s",
             "webhook" if BASE_URL else "polling", ADMIN_IDS or "yo'q", PUBLIC_DEMO)


def run_webhook():
    from aiohttp import web
    from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

    import web as panel

    bot, dp = make_bot_and_dp()
    path = f"/tg/{WEBHOOK_SECRET}"

    async def register_webhook():
        url = f"{BASE_URL}{path}"
        for attempt in range(1, 61):
            try:
                info = await bot.get_webhook_info()
                if info.url != url:
                    await bot.set_webhook(url, secret_token=WEBHOOK_SECRET)
                log.info("Webhook o'rnatildi: %s/tg/***", BASE_URL)
                return
            except Exception as e:  # noqa: BLE001
                log.warning("Webhook o'rnatilmadi (urinish %s): %s", attempt, e)
                await asyncio.sleep(30)

    async def on_startup(bot: Bot):
        await on_startup_common(bot)
        asyncio.create_task(register_webhook())

    async def on_shutdown(bot: Bot):
        await db.close()

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    app = web.Application()
    panel.setup_routes(app, bot)
    SimpleRequestHandler(dispatcher=dp, bot=bot, secret_token=WEBHOOK_SECRET).register(app, path)
    setup_application(app, dp, bot=bot)
    web.run_app(app, host="0.0.0.0", port=PORT)


async def run_polling():
    """Kompyuterda sinash: polling + web-panel http://localhost:PORT/panel?key=..."""
    from aiohttp import web

    import web as panel

    bot, dp = make_bot_and_dp()
    await on_startup_common(bot)
    app = web.Application()
    panel.setup_routes(app, bot)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", PORT).start()
    log.info("Web-panel: http://127.0.0.1:%s/panel?key=%s", PORT, WEBHOOK_SECRET)
    await bot.delete_webhook(drop_pending_updates=True)
    try:
        await dp.start_polling(bot)
    finally:
        await db.close()
        await runner.cleanup()


if __name__ == "__main__":
    if BASE_URL:
        run_webhook()
    else:
        asyncio.run(run_polling())

_ = render_act_notice  # (admin va jobs ishlatadi)
