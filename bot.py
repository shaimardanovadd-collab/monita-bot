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
                    back_row, days_left_text, draft_left, draft_name, fmt_date, get_lang, ikb,
                    is_admin, log, notify_admins, render_act_notice, render_draft_card,
                    render_update, reply_kb, set_lang, show)
import oked
from texts import BOT_DESCRIPTION_ALL, BOT_SHORT_ALL, LINE, all_variants, sector_names, t

router = Router(name="user")
LAWS_PER_PAGE = 6
DIV_PER_PAGE = 8


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
        [(t("btn_drafts", lang), "drafts:1")],
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


def lang_row(lang: str) -> list[tuple[str, str]]:
    return [("🇺🇿 O'zbekcha" + (" ✅" if lang == "uz" else ""), "setlang:uz"),
            ("🇷🇺 Русский" + (" ✅" if lang == "ru" else ""), "setlang:ru")]


def sections_kb(codes: list[str], lang: str, with_lang: bool = False):
    """OKED bo'limlari (biznes uchun 18 ta), 2 ustunda."""
    chosen = oked.letters(codes)
    rows = [lang_row(lang)] if with_lang else []
    row = []
    for key in oked.BUSINESS:
        mark = "✅" if key in chosen else "▫️"
        row.append((f"{mark} {oked.section_label(key, lang)}", f"sx:{key}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([(t("btn_next_step", lang), "sx:next")])
    return ikb(rows)


def divisions_kb(codes: list[str], lang: str, page: int):
    divs = [d for s in sorted(oked.letters(codes)) if s in oked.SECTIONS
            for d in oked.SECTIONS[s]["divisions"]]
    pages = max(1, -(-len(divs) // DIV_PER_PAGE))
    page = min(max(1, page), pages)
    chosen = set(oked.divisions_of(codes))
    rows = [[(("✅ " if d in chosen else "▫️ ") + oked.division_label(d, lang, 38), f"dv:{d}:{page}")]
            for d in divs[(page - 1) * DIV_PER_PAGE: page * DIV_PER_PAGE]]
    nav = []
    if page > 1:
        nav.append((t("btn_prev", lang), f"dvp:{page - 1}"))
    if pages > 1:
        nav.append((f"{page}/{pages}", f"dvp:{page}"))
    if page < pages:
        nav.append((t("btn_next", lang), f"dvp:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([(t("btn_save", lang) if chosen else t("btn_skip", lang), "dv:done"),
                 (t("btn_back", lang), "sec")])
    return ikb(rows), page, pages


async def open_menu(target, user_id: int, new: bool = False):
    user = await db.get_user(user_id)
    lang = await get_lang(user_id)
    if not user or not user["sectors"]:
        await show(target, t("choose_sections", lang), sections_kb([], lang), new=new)
        return
    text, kb = await menu_screen(user, lang)
    await show(target, text, kb, new=new)


# ======================= START: TIL TANLASH =======================
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user = await ensure_user(message.from_user)
    name = escape(message.from_user.first_name or "")
    if user.get("lang") and user["sectors"]:
        lang = await get_lang(user["user_id"])
        await message.answer(t("start_again", lang, name=name), reply_markup=reply_kb(lang))
        await open_menu(message, user["user_id"], new=True)
        return
    # yangi foydalanuvchi: avval o'zbekcha, til almashtirish tugmasi pastda
    lang = user.get("lang") or "uz"
    if not user.get("lang"):
        await set_lang(user["user_id"], "uz")
    await message.answer(t("welcome_new", lang, name=name), reply_markup=reply_kb(lang))
    await message.answer(t("choose_sections", lang), reply_markup=sections_kb(user["sectors"], lang, True))


@router.message(Command("lang"))
@router.callback_query(F.data == "lang")
async def cb_lang(event: Message | CallbackQuery):
    await ensure_user(event.from_user)
    lang = await get_lang(event.from_user.id)
    await show(event, t("choose_lang"), ikb([lang_row(lang), back_row(lang)]))
    if isinstance(event, CallbackQuery):
        await event.answer()


@router.callback_query(F.data.startswith("setlang:"))
async def cb_set_lang(cq: CallbackQuery):
    lang = cq.data.split(":")[1]
    user = await ensure_user(cq.from_user)
    old = await get_lang(cq.from_user.id)
    await set_lang(cq.from_user.id, lang)
    await cq.answer(t("lang_set", lang))
    if not user["sectors"]:
        # ro'yxatdan o'tish davomida: shu ekranni yangi tilda qayta chizamiz
        await show(cq, t("choose_sections", lang), sections_kb([], lang, True))
        if old != lang:
            await cq.message.answer(t("lang_set", lang), reply_markup=reply_kb(lang))
        return
    if old != lang:
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
    text = t("profile", lang, name=escape(cq.from_user.full_name),
             sectors=escape(oked.describe_long(user["sectors"], lang)),
             notify=t("on" if user["notify"] else "off", lang))
    await show(cq, text, ikb([[(t("btn_edit_sectors", lang), "sec")],
                              [(t("btn_edit_divisions", lang), "dvp:1")],
                              [(t("btn_lang", lang), "lang")], back_row(lang)]))
    await cq.answer()


@router.callback_query(F.data == "sec")
async def cb_sectors(cq: CallbackQuery):
    user = await ensure_user(cq.from_user)
    lang = await get_lang(cq.from_user.id)
    await show(cq, t("choose_sections", lang), sections_kb(user["sectors"], lang))
    await cq.answer()


@router.callback_query(F.data.startswith("sx:"))
async def cb_section_toggle(cq: CallbackQuery):
    """Holatsiz: har bosish darhol bazaga yoziladi."""
    key = cq.data.split(":", 1)[1]
    user = await ensure_user(cq.from_user)
    lang = await get_lang(cq.from_user.id)
    codes = list(user["sectors"])
    if key == "next":
        if not oked.letters(codes):
            await cq.answer(t("need_one_sector", lang), show_alert=True)
            return
        await cq.answer()
        await show_divisions(cq, codes, lang, 1)
        return
    if key in oked.letters(codes):
        # bo'limni olib tashlash — uning bo'linmalari ham
        codes = [c for c in codes if c != key and not (c in oked.DIVISIONS
                                                      and oked.DIVISIONS[c]["s"] == key)]
    elif key in oked.SECTIONS:
        codes.append(key)
    await db.set_sectors(cq.from_user.id, codes)
    first_time = "setlang:uz" in str(cq.message.reply_markup)
    await cq.message.edit_reply_markup(reply_markup=sections_kb(codes, lang, first_time))
    await cq.answer()


async def show_divisions(cq: CallbackQuery, codes: list[str], lang: str, page: int):
    kb, page, pages = divisions_kb(codes, lang, page)
    chosen = escape(oked.describe(codes, lang))
    await show(cq, t("choose_divisions", lang, page=page, pages=pages) + f"\n\n💼 {chosen}", kb)


@router.callback_query(F.data.startswith("dvp:"))
async def cb_div_page(cq: CallbackQuery):
    user = await ensure_user(cq.from_user)
    lang = await get_lang(cq.from_user.id)
    if not oked.letters(user["sectors"]):
        await show(cq, t("choose_sections", lang), sections_kb([], lang))
    else:
        await show_divisions(cq, user["sectors"], lang, int(cq.data.split(":")[1]))
    await cq.answer()


@router.callback_query(F.data.startswith("dv:"))
async def cb_div_toggle(cq: CallbackQuery):
    parts = cq.data.split(":")
    user = await ensure_user(cq.from_user)
    lang = await get_lang(cq.from_user.id)
    if parts[1] == "done":
        await cq.answer(t("saved", lang))
        await open_menu(cq, cq.from_user.id)
        return
    code, page = parts[1], int(parts[2])
    codes = list(user["sectors"])
    if code in codes:
        codes.remove(code)
    elif code in oked.DIVISIONS:
        codes.append(code)
    await db.set_sectors(cq.from_user.id, codes)
    await show_divisions(cq, codes, lang, page)
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
        await show(cq, t("choose_sections", lang), sections_kb([], lang))
        return None
    return user


@router.callback_query(F.data == "news")
async def cb_news(cq: CallbackQuery):
    user = await need_sectors(cq)
    if not user:
        return
    lang = await get_lang(cq.from_user.id)
    lines = [t("news_screen", lang)]
    buttons = []
    items = await db.latest_updates(user["sectors"], limit=4)
    if items:
        lines.append(t("news_admin", lang))
        for i, u in enumerate(items, 1):
            lines.append(f"<b>{i}.</b> {escape(u['title'])} · 📅 {fmt_date(u.get('effective'), lang)}")
            buttons.append((f"📣 {i}", f"upd:{u['id']}"))
        lines.append("")
    acts = await assistant.latest_acts_for(user["sectors"])
    secs = ", ".join(sorted(x for x in oked.letters(user["sectors"]) if x != "ALL"))
    lines.append(t("news_acts", lang, sec=secs))
    for i, a in enumerate(acts, 1):
        title = a["title"] if len(a["title"]) <= 110 else a["title"][:107] + "…"
        scope = "🌍" if a["oked"] == "ALL" else "🎯"
        lines.append(f"{scope} <b>{i}.</b> {escape(title)}\n     📅 {fmt_date(a['effective'], lang)} · "
                     f"{escape(a['act_type'] or '')}")
        buttons.append((f"📄 {i}", f"act:{a['lex_id']}"))
    lines.append("\n" + t("news_hint", lang))
    rows = [buttons[i:i + 4] for i in range(0, len(buttons), 4)]
    rows += [[(t("btn_laws", lang), "laws:1")], back_row(lang)]
    await show(cq, "\n".join(lines), ikb(rows))
    await cq.answer()


@router.callback_query(F.data.startswith("act:"))
async def cb_act(cq: CallbackQuery):
    lang = await get_lang(cq.from_user.id)
    act = await db.get_act(cq.data.split(":")[1])
    if not act:
        await cq.answer(t("not_found", lang), show_alert=True)
        return
    has_text = act["lex_id"] in await db.lex_ids_with_text()
    from common import act_sectors_text
    text = t("act_card", lang, act_type=escape(act["act_type"] or ""),
             requisites=escape(act["requisites"] or ""), title=escape(act["title"]),
             effective=fmt_date(act["effective"], lang),
             sectors=escape(act_sectors_text(act, lang)), topic=escape(act.get("topic") or "—"),
             text_status=t("text_loaded" if has_text else "text_missing", lang))
    await show(cq, text, ikb([[(t("btn_lex", lang), act["url"])],
                              [(t("btn_ai_summary", lang), f"sum:{act['lex_id']}")],
                              [(t("btn_ask_ai_act", lang), f"aiact:{act['lex_id']}")],
                              back_row(lang, "news")]))
    await cq.answer()


@router.callback_query(F.data.startswith("sum:"))
async def cb_act_summary(cq: CallbackQuery, bot: Bot):
    """AI qisqa mazmuni — hujjat matni asosida «yangilik»."""
    uid = cq.from_user.id
    lang = await get_lang(uid)
    act = await db.get_act(cq.data.split(":")[1])
    if not act:
        await cq.answer(t("not_found", lang), show_alert=True)
        return
    if not ai.is_configured():
        await cq.answer(t("ai_off", lang), show_alert=True)
        return
    limit = ai.check_limits(uid, is_admin(uid))
    if limit:
        await cq.answer(t("ai_err_cooldown", lang) if limit == "cooldown"
                        else t("ai_err_daily", lang, n=ai.DAILY_LIMIT), show_alert=True)
        return
    await cq.answer("🤖 …")
    await bot.send_chat_action(cq.message.chat.id, "typing")
    user = await db.get_user(uid) or {}
    try:
        res = await assistant.act_summary(act, user.get("sectors") or [], lang)
    except Exception as e:  # noqa: BLE001
        log.warning("Qisqa mazmun xatosi: %s", e)
        await bot.send_message(cq.message.chat.id, assistant.error_text(e, lang))
        return
    body = (f"{t('ai_summary_title', lang)}\n<b>{escape(act['title'][:200])}</b>\n{LINE}\n"
            + assistant.md_to_html(res["answer"])
            + ("" if res["has_text"] else f"\n\n<i>{t('summary_no_text', lang)}</i>"))
    kb = ikb([[(t("btn_lex", lang), act["url"])],
              [(t("btn_ask_ai_act", lang), f"aiact:{act['lex_id']}"), (t("btn_menu", lang), "m")]])
    for i, part in enumerate(parts := assistant.split_message(body)):
        await bot.send_message(cq.message.chat.id, part, disable_web_page_preview=True,
                               reply_markup=kb if i == len(parts) - 1 else None)


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


# ---- NPA loyihalari (regulation.adliya.uz) ----
DRAFTS_PER_PAGE = 5


@router.callback_query(F.data.startswith("drafts:"))
async def cb_drafts(cq: CallbackQuery):
    user = await need_sectors(cq)
    if not user:
        return
    lang = await get_lang(cq.from_user.id)
    items = await db.drafts_for_oked(oked.letters(user["sectors"]), active_only=True, limit=200)
    if not items:
        st = await db.draft_stats()
        text = t("no_drafts", lang) if st["last_sync"] else t("drafts_not_synced", lang)
        await show(cq, text, ikb([back_row(lang)]))
        await cq.answer()
        return
    pages = max(1, -(-len(items) // DRAFTS_PER_PAGE))
    page = min(max(1, int(cq.data.split(":")[1])), pages)
    chunk = items[(page - 1) * DRAFTS_PER_PAGE: page * DRAFTS_PER_PAGE]
    lines = [t("drafts_screen", lang, count=len(items), page=page, pages=pages)]
    buttons = []
    for i, d in enumerate(chunk, (page - 1) * DRAFTS_PER_PAGE + 1):
        name = draft_name(d, lang)
        name = name if len(name) <= 130 else name[:127] + "…"
        org = ((d["org_ru"] if lang == "ru" else d["org_uz"]) or "")[:60]
        lines.append(f"<b>{i}.</b> {escape(name)}\n     🏛 {escape(org)} · {draft_left(d, lang)}")
        buttons.append((f"📝 {i}", f"draft:{d['id']}"))
    nav = []
    if page > 1:
        nav.append((t("btn_prev", lang), f"drafts:{page - 1}"))
    if pages > 1:
        nav.append((f"{page}/{pages}", f"drafts:{page}"))
    if page < pages:
        nav.append((t("btn_next", lang), f"drafts:{page + 1}"))
    await show(cq, "\n\n".join(lines), ikb([buttons, nav, back_row(lang)]))
    await cq.answer()


@router.callback_query(F.data.startswith("draft:"))
async def cb_draft(cq: CallbackQuery):
    lang = await get_lang(cq.from_user.id)
    d = await db.get_draft(int(cq.data.split(":")[1]))
    if not d:
        await cq.answer(t("not_found", lang), show_alert=True)
        return
    text, kb = render_draft_card(d, lang)
    await show(cq, text, kb)
    await cq.answer()


@router.callback_query(F.data.startswith("dsum:"))
async def cb_draft_summary(cq: CallbackQuery, bot: Bot):
    uid = cq.from_user.id
    lang = await get_lang(uid)
    d = await db.get_draft(int(cq.data.split(":")[1]))
    if not d:
        await cq.answer(t("not_found", lang), show_alert=True)
        return
    if not ai.is_configured():
        await cq.answer(t("ai_off", lang), show_alert=True)
        return
    limit = ai.check_limits(uid, is_admin(uid))
    if limit:
        await cq.answer(t("ai_err_cooldown", lang) if limit == "cooldown"
                        else t("ai_err_daily", lang, n=ai.DAILY_LIMIT), show_alert=True)
        return
    await cq.answer("🤖 …")
    await bot.send_chat_action(cq.message.chat.id, "typing")
    user = await db.get_user(uid) or {}
    try:
        res = await assistant.draft_summary(d, user.get("sectors") or [], lang)
    except Exception as e:  # noqa: BLE001
        log.warning("Loyiha tahlili xatosi: %s", e)
        await bot.send_message(cq.message.chat.id, assistant.error_text(e, lang))
        return
    import drafts as drafts_mod
    body = (f"{t('draft_ai_title', lang)}\n<b>{escape(draft_name(d, lang)[:220])}</b>\n"
            f"{draft_left(d, lang)}\n{LINE}\n" + assistant.md_to_html(res["answer"])
            + ("" if res["has_text"] else f"\n\n<i>{t('draft_no_text', lang)}</i>"))
    kb = ikb([[(t("btn_portal", lang), drafts_mod.page_url(d))],
              [(t("btn_all_drafts", lang), "drafts:1"), (t("btn_menu", lang), "m")]])
    parts = assistant.split_message(body)
    for i, part in enumerate(parts):
        await bot.send_message(cq.message.chat.id, part, disable_web_page_preview=True,
                               reply_markup=kb if i == len(parts) - 1 else None)


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
        st = await db.chunk_stats()
        text = t("ai_intro", lang, acts=st["acts"], texts=st["with_text"])
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
    body = (head + assistant.md_to_html(res["answer"])
            + assistant.sources_html(res["sources"], lang, cited=res["cited"])
            + assistant.read_note(res, lang))
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
    if not user["sectors"]:
        lang = await get_lang(user["user_id"])
        await message.answer(t("choose_sections", lang), reply_markup=sections_kb([], lang, True))
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
        lg = "ru" if lang_code == "ru" else "uz"
        try:
            await bot.set_my_commands([BotCommand(command=c, description=d) for c, d in cmds[lg]],
                                      language_code=lang_code)
            # tavsif hamma uchun bir xil: avval o'zbekcha, so'ng ruscha
            await bot.set_my_description(BOT_DESCRIPTION_ALL, language_code=lang_code)
            await bot.set_my_short_description(BOT_SHORT_ALL, language_code=lang_code)
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
    asyncio.create_task(jobs.initial_load(bot))
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
