"""Umumiy sozlamalar, klaviaturalar, kartochkalar va xabar tarqatish."""
import asyncio
import logging
import os
from datetime import date, datetime
from html import escape

from aiogram import Bot
from aiogram.exceptions import (TelegramBadRequest, TelegramForbiddenError,
                                TelegramRetryAfter)
from aiogram.types import (CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup,
                           KeyboardButton, Message, ReplyKeyboardMarkup)
from dotenv import load_dotenv

load_dotenv()

import db  # noqa: E402
import oked  # noqa: E402
from texts import MONTHS, sector_names, t  # noqa: E402

# ---------------- sozlamalar ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",")
             if x.lstrip("-").isdigit()}
BASE_URL = (os.getenv("WEBHOOK_BASE_URL") or os.getenv("RENDER_EXTERNAL_URL") or "").rstrip("/")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "monita-secret-change-me")
PORT = int(os.getenv("PORT", "10000"))
REMINDER_DAYS = [7, 3, 1, 0]
REMINDER_HOUR = int(os.getenv("REMINDER_HOUR", "9"))
# 1 — demo tugmasi hamma foydalanuvchilarga ko'rinadi (hakaton/hakamlar uchun)
PUBLIC_DEMO = os.getenv("PUBLIC_DEMO", "0") == "1"
# Lex.uz ni avtomatik qayta tekshirish (kun). 0 — o'chiq
AUTO_CHECK_DAYS = int(os.getenv("AUTO_CHECK_DAYS", "7"))
LEX_BASE = os.getenv("LEX_BASE", "https://lex.uz")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("monita")


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def panel_url() -> str | None:
    return f"{BASE_URL}/panel?key={WEBHOOK_SECRET}" if BASE_URL else None


# ---------------- til ----------------
_lang_cache: dict[int, str] = {}


async def get_lang(user_id: int) -> str:
    if user_id not in _lang_cache:
        u = await db.get_user(user_id)
        _lang_cache[user_id] = (u or {}).get("lang") or "uz"
    return _lang_cache[user_id]


async def set_lang(user_id: int, lang: str):
    await db.set_lang(user_id, lang)
    _lang_cache[user_id] = lang


# ---------------- sana ----------------
def fmt_date(iso: str | None, lang: str = "uz") -> str:
    try:
        d = date.fromisoformat(str(iso)[:10])
    except (TypeError, ValueError):
        return escape(str(iso)) if iso else "—"
    m = MONTHS.get(lang, MONTHS["uz"])[d.month - 1]
    return f"{d.day} {m} {d.year}" if lang == "ru" else f"{d.year}-yil {d.day}-{m}"


def parse_date(text: str) -> str | None:
    for f in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text.strip(), f).date().isoformat()
        except ValueError:
            pass
    return None


def days_left_text(due_iso: str, lang: str) -> str:
    n = (date.fromisoformat(due_iso) - date.today()).days
    return t("today", lang) if n == 0 else t("days_left", lang, n=n)


# ---------------- klaviaturalar ----------------
def ikb(rows: list[list[tuple[str, str]]]) -> InlineKeyboardMarkup:
    """[[('matn', 'callback' yoki 'https://...')]] -> inline klaviatura."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=txt, url=val) if val.startswith(("http://", "https://"))
         else InlineKeyboardButton(text=txt, callback_data=val) for txt, val in row]
        for row in rows if row])


def reply_kb(lang: str) -> ReplyKeyboardMarkup:
    """Pastdagi doimiy tugmalar — har doim menyuga qaytish mumkin."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t("btn_menu", lang)), KeyboardButton(text=t("btn_ai", lang))]],
        resize_keyboard=True, is_persistent=True)


def back_row(lang: str, back: str | None = None) -> list[tuple[str, str]]:
    row = [(t("btn_back", lang), back)] if back else []
    return row + [(t("btn_menu", lang), "m")]


async def show(target: Message | CallbackQuery, text: str, kb=None, new: bool = False):
    """Ekranni ko'rsatish: callback bo'lsa — xabarni joyida tahrirlaydi (chat to'lmaydi)."""
    if isinstance(target, CallbackQuery) and not new:
        try:
            await target.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
            return
        except TelegramBadRequest as e:
            if "not modified" in str(e):
                return
        target = target.message
    elif isinstance(target, CallbackQuery):
        target = target.message
    await target.answer(text, reply_markup=kb, disable_web_page_preview=True)


# ---------------- kartochkalar ----------------
def act_sectors_text(act: dict, lang: str) -> str:
    letters = [x.strip() for x in (act.get("oked") or "").split(",") if x.strip()]
    return sector_names(letters, lang)


def render_act_notice(act: dict, lang: str, kind: str = "new", demo: bool = False) -> tuple:
    text = (t("demo_tag", lang) if demo else "") + t(
        "act_new" if kind == "new" else "act_changed", lang,
        act_type=escape(act.get("act_type") or ""), requisites=escape(act.get("requisites") or ""),
        title=escape(act.get("title") or ""), effective=fmt_date(act.get("effective"), lang),
        sectors=escape(act_sectors_text(act, lang)))
    kb = ikb([[(t("btn_lex", lang), act["url"])],
              [(t("btn_ask_ai_act", lang), f"aiact:{act['lex_id']}")],
              [(t("btn_menu", lang), "m")]])
    return text, kb


def render_update(u: dict, lang: str, demo: bool = False) -> tuple:
    src = "—"
    if u.get("source_url"):
        label = "Lex.uz" if "lex.uz" in u["source_url"] else "link"
        src = f'<a href="{escape(u["source_url"], quote=True)}">{label}</a>'
    text = (t("demo_tag", lang) if demo else "") + t(
        "update_card", lang, title=escape(u["title"]),
        sectors=escape(sector_names(u["sectors"], lang)), summary=escape(u["summary"]),
        effective=fmt_date(u.get("effective"), lang), source=src)
    rows = []
    if u.get("id"):
        rows.append([(t("btn_details", lang), f"upd:{u['id']}"), (t("btn_deadlines", lang), "dl")])
    rows.append([(t("btn_menu", lang), "m")])
    return text, ikb(rows)


def render_reminder(d: dict, lang: str, demo: bool = False) -> tuple:
    text = (t("demo_tag", lang) if demo else "") + t(
        "reminder", lang, title=escape(d["title"]), due=fmt_date(d["due_date"], lang),
        left=days_left_text(d["due_date"], lang), sectors=escape(sector_names(d["sectors"], lang)),
        description=escape(d.get("description") or ""))
    return text, ikb([[(t("btn_deadlines", lang), "dl"), (t("btn_menu", lang), "m")]])


# ---------------- tarqatish ----------------
async def broadcast(bot: Bot, recipients: list[dict], render) -> tuple[int, int]:
    """recipients: [{'user_id', 'lang'}]; render(lang) -> (text, kb). Har bir kishiga o'z tilida."""
    sent = failed = 0
    cache: dict[str, tuple] = {}
    for r in recipients:
        lang = r.get("lang") or "uz"
        if lang not in cache:
            cache[lang] = render(lang)
        text, kb = cache[lang]
        for attempt in range(2):
            try:
                await bot.send_message(r["user_id"], text, reply_markup=kb,
                                       disable_web_page_preview=True)
                sent += 1
                break
            except TelegramRetryAfter as e:
                await asyncio.sleep(e.retry_after)
            except TelegramForbiddenError:
                failed += 1  # botni bloklagan
                break
            except Exception as e:  # noqa: BLE001
                log.warning("Yuborilmadi %s: %s", r["user_id"], e)
                failed += 1
                break
        await asyncio.sleep(0.05)  # Telegram limiti ~30 xabar/soniya
    return sent, failed


async def subscribers_for_act(act: dict) -> list[dict]:
    """Akt OKED bo'limlariga mos sohani tanlagan obunachilar."""
    letters = {x.strip() for x in (act.get("oked") or "").split(",") if x.strip()}
    out = []
    for s in await db.all_subscribers():
        if not s["sectors"]:
            continue
        if "ALL" in letters or oked.letters(s["sectors"]) & letters:
            out.append(s)
    return out


async def notify_act(bot: Bot, act: dict, kind: str = "new") -> tuple[int, int]:
    subs = await subscribers_for_act(act)
    res = await broadcast(bot, subs, lambda lang: render_act_notice(act, lang, kind))
    log.info("Akt %s (%s): %s yuborildi, %s xato", act["lex_id"], kind, *res)
    return res


async def notify_admins(bot: Bot, text: str):
    for a in ADMIN_IDS:
        try:
            await bot.send_message(a, text, disable_web_page_preview=True)
        except Exception as e:  # noqa: BLE001
            log.warning("Adminga yuborilmadi %s: %s", a, e)
