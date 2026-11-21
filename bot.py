"""
Monita Bot — biznes uchun qonunchilik monitoringi (Telegram bot).
aiogram 3 + SQLite. Ishga tushirish: python bot.py
"""
import asyncio
import logging
import os
from datetime import date, datetime
from html import escape

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BotCommand, CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv

load_dotenv()  # db import qilinishidan oldin bo'lishi kerak

import db  # noqa: E402
import texts as T  # noqa: E402
from texts import SECTORS, sector_names  # noqa: E402

BOT_TOKEN = os.getenv("BOT_TOKEN")
# Render avtomatik beradi: https://monita-bot.onrender.com — bo'lsa webhook rejimi yoqiladi
BASE_URL = (os.getenv("WEBHOOK_BASE_URL") or os.getenv("RENDER_EXTERNAL_URL") or "").rstrip("/")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "monita-secret-change-me")
PORT = int(os.getenv("PORT", "10000"))
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",")
             if x.lstrip("-").isdigit()}  # raqam bo'lmagan qiymatlar e'tiborsiz qoldiriladi
REMINDER_DAYS = [7, 3, 1, 0]          # muddatdan necha kun oldin eslatish
REMINDER_HOUR = int(os.getenv("REMINDER_HOUR", "9"))  # mahalliy vaqt bo'yicha soat

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("monita")
router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def fmt_date(iso: str | None) -> str:
    """2026-12-01 -> 2026-yil 1-dekabr"""
    months = ["yanvar", "fevral", "mart", "aprel", "may", "iyun", "iyul",
              "avgust", "sentabr", "oktabr", "noyabr", "dekabr"]
    try:
        d = date.fromisoformat(iso)
        return f"{d.year}-yil {d.day}-{months[d.month - 1]}"
    except (TypeError, ValueError):
        return escape(iso or "—")


def parse_date(text: str) -> str | None:
    """Qabul qiladi: 01.12.2026 yoki 2026-12-01 -> ISO."""
    text = text.strip()
    for f in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, f).date().isoformat()
        except ValueError:
            pass
    return None


# ======================= KLAVIATURALAR =======================
def main_menu_kb(notify_on: bool = True):
    kb = InlineKeyboardBuilder()
    kb.button(text="👤 Profilni sozlash", callback_data="profile")
    kb.button(text="🔔 Xabarnomalarni o'chirish" if notify_on else "🔕 Xabarnomalarni yoqish",
              callback_data="notify")
    kb.button(text="📰 So'nggi yangiliklar", callback_data="news")
    kb.button(text="📅 Muhim muddatlar", callback_data="deadlines")
    kb.button(text="❓ Savol yoki taklif", callback_data="feedback")
    kb.button(text="ℹ️ Bot haqida", callback_data="about")
    kb.adjust(1)
    return kb.as_markup()


def sectors_kb(selected: list[str], prefix: str = "sec", done_text: str = "Davom etish ➡️"):
    kb = InlineKeyboardBuilder()
    for key, (emoji, name) in SECTORS.items():
        mark = "✅" if key in selected else "⬜️"
        kb.button(text=f"{mark} {emoji} {name}", callback_data=f"{prefix}:{key}")
    kb.button(text=done_text, callback_data=f"{prefix}:done")
    kb.adjust(1)
    return kb.as_markup()


def update_card_kb(update_id: int):
    kb = InlineKeyboardBuilder()
    kb.button(text="📄 Batafsil ma'lumot", callback_data=f"upd:{update_id}")
    kb.button(text="📅 Muhim muddatlar", callback_data="deadlines")
    kb.adjust(1)
    return kb.as_markup()


def back_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Menyuga qaytish", callback_data="menu")
    return kb.as_markup()


def render_update(u: dict) -> str:
    src = (f'<a href="{escape(u["source_url"], quote=True)}">Lex.uz</a>'
           if u.get("source_url") else "—")
    if u.get("source_url") and "lex.uz" not in u["source_url"]:
        src = f'<a href="{escape(u["source_url"], quote=True)}">Havola</a>'
    return T.UPDATE_CARD.format(
        title=escape(u["title"]),
        sectors=escape(sector_names(u["sectors"])),
        summary=escape(u["summary"]),
        effective=fmt_date(u.get("effective")),
        source=src,
    )


# ======================= FOYDALANUVCHI QISMI =======================
class UserStates(StatesGroup):
    choosing_sectors = State()
    feedback = State()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    u = message.from_user
    await db.upsert_user(u.id, u.full_name, u.username)
    user = await db.get_user(u.id)
    await message.answer(T.WELCOME.format(name=escape(u.first_name or "")),
                         reply_markup=main_menu_kb(bool(user["notify"])))
    if not user["sectors"]:
        await state.set_state(UserStates.choosing_sectors)
        await state.update_data(selected=[])
        await message.answer(T.CHOOSE_SECTORS, reply_markup=sectors_kb([]))


@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext):
    await state.clear()
    await db.upsert_user(message.from_user.id, message.from_user.full_name,
                         message.from_user.username)
    user = await db.get_user(message.from_user.id)
    await message.answer(T.MENU, reply_markup=main_menu_kb(bool(user["notify"])))


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(T.CANCELLED, reply_markup=back_kb())


@router.callback_query(F.data == "menu")
async def cb_menu(cq: CallbackQuery, state: FSMContext):
    await state.clear()
    user = await db.get_user(cq.from_user.id)
    await cq.message.answer(T.MENU, reply_markup=main_menu_kb(bool(user and user["notify"])))
    await cq.answer()


# ---- Profil: faoliyat turlarini tanlash ----
@router.callback_query(F.data == "profile")
async def cb_profile(cq: CallbackQuery, state: FSMContext):
    await db.upsert_user(cq.from_user.id, cq.from_user.full_name, cq.from_user.username)
    user = await db.get_user(cq.from_user.id)
    await state.set_state(UserStates.choosing_sectors)
    await state.update_data(selected=user["sectors"])
    await cq.message.answer(T.CHOOSE_SECTORS, reply_markup=sectors_kb(user["sectors"]))
    await cq.answer()


@router.callback_query(UserStates.choosing_sectors, F.data.startswith("sec:"))
async def cb_sector_toggle(cq: CallbackQuery, state: FSMContext):
    key = cq.data.split(":", 1)[1]
    data = await state.get_data()
    selected: list[str] = data.get("selected", [])

    if key == "done":
        if not selected:
            await cq.answer(T.NEED_ONE_SECTOR, show_alert=True)
            return
        await db.set_sectors(cq.from_user.id, selected)
        await state.clear()
        user = await db.get_user(cq.from_user.id)
        await cq.message.edit_text(
            T.PROFILE_SAVED.format(sectors=escape(sector_names(selected))))
        await cq.message.answer(T.MENU, reply_markup=main_menu_kb(bool(user["notify"])))
        await cq.answer("Saqlandi ✅")
        return

    if key in selected:
        selected.remove(key)
    elif key in SECTORS:
        selected.append(key)
    await state.update_data(selected=selected)
    await cq.message.edit_reply_markup(reply_markup=sectors_kb(selected))
    await cq.answer()


# ---- Xabarnomalar ----
@router.callback_query(F.data == "notify")
async def cb_notify(cq: CallbackQuery):
    await db.upsert_user(cq.from_user.id, cq.from_user.full_name, cq.from_user.username)
    on = await db.toggle_notify(cq.from_user.id)
    await cq.message.edit_reply_markup(reply_markup=main_menu_kb(on))
    await cq.message.answer(T.NOTIF_ON if on else T.NOTIF_OFF)
    await cq.answer()


# ---- So'nggi yangiliklar ----
@router.callback_query(F.data == "news")
async def cb_news(cq: CallbackQuery):
    user = await db.get_user(cq.from_user.id)
    if not user or not user["sectors"]:
        await cq.answer(T.NEED_PROFILE, show_alert=True)
        return
    items = await db.latest_updates(user["sectors"], limit=5)
    if not items:
        await cq.message.answer(T.NO_NEWS, reply_markup=back_kb())
    else:
        await cq.message.answer(T.NEWS_HEADER.format(count=len(items)))
        for u in items:
            await cq.message.answer(render_update(u), reply_markup=update_card_kb(u["id"]),
                                    disable_web_page_preview=True)
    await cq.answer()


@router.callback_query(F.data.startswith("upd:"))
async def cb_update_detail(cq: CallbackQuery):
    u = await db.get_update(int(cq.data.split(":")[1]))
    if not u:
        await cq.answer("Ma'lumot topilmadi", show_alert=True)
        return
    text = f"📄 <b>{escape(u['title'])}</b>\n\n{escape(u.get('details') or u['summary'])}"
    if u.get("source_url"):
        text += f'\n\n🔗 <a href="{escape(u["source_url"], quote=True)}">Rasmiy matn</a>'
    await cq.message.answer(text, reply_markup=back_kb(), disable_web_page_preview=True)
    await cq.answer()


# ---- Muhim muddatlar ----
@router.callback_query(F.data == "deadlines")
async def cb_deadlines(cq: CallbackQuery):
    user = await db.get_user(cq.from_user.id)
    if not user or not user["sectors"]:
        await cq.answer(T.NEED_PROFILE, show_alert=True)
        return
    items = await db.upcoming_deadlines(user["sectors"])
    if not items:
        await cq.message.answer(T.NO_DEADLINES, reply_markup=back_kb())
    else:
        lines = [T.DEADLINES_HEADER, ""]
        for d in items:
            left = (date.fromisoformat(d["due_date"]) - date.today()).days
            lines.append(f"• <b>{fmt_date(d['due_date'])}</b> ({left} kun qoldi)\n"
                         f"  {escape(d['title'])}")
        await cq.message.answer("\n".join(lines), reply_markup=back_kb())
    await cq.answer()


# ---- Savol yoki taklif ----
@router.callback_query(F.data == "feedback")
async def cb_feedback(cq: CallbackQuery, state: FSMContext):
    await state.set_state(UserStates.feedback)
    await cq.message.answer(T.ASK_FEEDBACK)
    await cq.answer()


@router.message(UserStates.feedback, F.text)
async def got_feedback(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    await db.add_feedback(message.from_user.id, message.text)
    u = message.from_user
    who = f"@{u.username}" if u.username else escape(u.full_name)
    for admin in ADMIN_IDS:
        try:
            await bot.send_message(
                admin,
                f"✉️ <b>Yangi murojaat</b>\nKimdan: {who} (ID: <code>{u.id}</code>)\n\n"
                f"{escape(message.text)}\n\nJavob berish: <code>/javob {u.id} matn</code>")
        except Exception as e:  # noqa: BLE001
            log.warning("Adminga yuborilmadi %s: %s", admin, e)
    await message.answer(T.FEEDBACK_THANKS, reply_markup=back_kb())


# ---- Bot haqida ----
@router.callback_query(F.data == "about")
async def cb_about(cq: CallbackQuery):
    await cq.message.answer(T.ABOUT, reply_markup=back_kb())
    await cq.answer()


# ======================= ADMIN QISMI =======================
class AddUpdate(StatesGroup):
    title = State()
    sectors = State()
    summary = State()
    effective = State()
    source = State()
    details = State()
    confirm = State()


class AddDeadline(StatesGroup):
    title = State()
    sectors = State()
    due = State()
    description = State()


ADMIN_HELP = (
    "<b>Admin buyruqlari</b>\n"
    "/yangilik — yangi o'zgarish qo'shish va obunachilarga yuborish\n"
    "/muddat — muhim muddat qo'shish (avtomatik eslatmalar bilan)\n"
    "/muddatlar — barcha kelgusi muddatlar ro'yxati\n"
    "/muddat_ochir ID — muddatni o'chirish\n"
    "/javob USER_ID matn — foydalanuvchiga javob\n"
    "/stat — statistika\n"
    "/cancel — joriy amalni bekor qilish"
)


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if is_admin(message.from_user.id):
        await message.answer(ADMIN_HELP)


# ---- /yangilik ----
@router.message(Command("yangilik"))
async def upd_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(AddUpdate.title)
    await message.answer("1/6. O'zgarish <b>sarlavhasini</b> yozing:\n"
                         "(masalan: Import jarayonlariga oid yangi talablar)")


@router.message(AddUpdate.title, F.text)
async def upd_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text.strip(), selected=[])
    await state.set_state(AddUpdate.sectors)
    await message.answer("2/6. Qaysi <b>sohalarga</b> tegishli?",
                         reply_markup=sectors_kb([], prefix="asec", done_text="Tayyor ➡️"))


@router.callback_query(AddUpdate.sectors, F.data.startswith("asec:"))
@router.callback_query(AddDeadline.sectors, F.data.startswith("asec:"))
async def admin_sector_toggle(cq: CallbackQuery, state: FSMContext):
    key = cq.data.split(":", 1)[1]
    data = await state.get_data()
    selected: list[str] = data.get("selected", [])
    if key == "done":
        if not selected:
            await cq.answer(T.NEED_ONE_SECTOR, show_alert=True)
            return
        await cq.message.edit_text(f"Sohalar: {escape(sector_names(selected))}")
        current = await state.get_state()
        if current == AddUpdate.sectors.state:
            await state.set_state(AddUpdate.summary)
            await cq.message.answer("3/6. <b>Nima o'zgardi?</b> Qisqa (1–2 gap) yozing:")
        else:
            await state.set_state(AddDeadline.due)
            await cq.message.answer("3/4. <b>Muddat sanasi</b> (masalan 01.12.2026):")
        await cq.answer()
        return
    if key in selected:
        selected.remove(key)
    elif key in SECTORS:
        selected.append(key)
    await state.update_data(selected=selected)
    await cq.message.edit_reply_markup(
        reply_markup=sectors_kb(selected, prefix="asec", done_text="Tayyor ➡️"))
    await cq.answer()


@router.message(AddUpdate.summary, F.text)
async def upd_summary(message: Message, state: FSMContext):
    await state.update_data(summary=message.text.strip())
    await state.set_state(AddUpdate.effective)
    await message.answer("4/6. <b>Qachondan</b> kuchga kiradi? (01.12.2026) "
                         "yoki noma'lum bo'lsa <code>-</code>")


@router.message(AddUpdate.effective, F.text)
async def upd_effective(message: Message, state: FSMContext):
    txt = message.text.strip()
    if txt == "-":
        eff = None
    else:
        eff = parse_date(txt)
        if not eff:
            await message.answer("Sana formati noto'g'ri. Masalan: 01.12.2026")
            return
    await state.update_data(effective=eff)
    await state.set_state(AddUpdate.source)
    await message.answer("5/6. <b>Manba havolasi</b> (masalan https://lex.uz/docs/...) "
                         "yoki <code>-</code>")


@router.message(AddUpdate.source, F.text)
async def upd_source(message: Message, state: FSMContext):
    txt = message.text.strip()
    if txt != "-" and not txt.startswith(("http://", "https://")):
        await message.answer("Havola http:// yoki https:// bilan boshlanishi kerak.")
        return
    await state.update_data(source_url=None if txt == "-" else txt)
    await state.set_state(AddUpdate.details)
    await message.answer("6/6. <b>Batafsil ma'lumot</b> (\"Batafsil ma'lumot\" tugmasida "
                         "ko'rinadi) yoki <code>-</code>")


@router.message(AddUpdate.details, F.text)
async def upd_details(message: Message, state: FSMContext):
    txt = message.text.strip()
    await state.update_data(details=None if txt == "-" else txt)
    data = await state.get_data()
    preview = render_update({**data, "sectors": data["selected"]})
    subs = await db.subscribers_for(data["selected"])
    kb = InlineKeyboardBuilder()
    kb.button(text=f"✅ Yuborish ({len(subs)} ta obunachi)", callback_data="pub:yes")
    kb.button(text="❌ Bekor qilish", callback_data="pub:no")
    kb.adjust(1)
    await state.set_state(AddUpdate.confirm)
    await message.answer("<b>Ko'rib chiqing:</b>\n\n" + preview,
                         reply_markup=kb.as_markup(), disable_web_page_preview=True)


@router.callback_query(AddUpdate.confirm, F.data.startswith("pub:"))
async def upd_publish(cq: CallbackQuery, state: FSMContext, bot: Bot):
    if cq.data == "pub:no":
        await state.clear()
        await cq.message.edit_reply_markup(reply_markup=None)
        await cq.message.answer(T.CANCELLED)
        await cq.answer()
        return
    data = await state.get_data()
    await state.clear()
    await cq.message.edit_reply_markup(reply_markup=None)
    update_id = await db.add_update(data["title"], data["selected"], data["summary"],
                                    data.get("effective"), data.get("source_url"),
                                    data.get("details"))
    u = await db.get_update(update_id)
    await cq.answer("Yuborilmoqda...")
    sent, failed = await broadcast(bot, await db.subscribers_for(u["sectors"]),
                                   render_update(u), update_card_kb(update_id))
    await cq.message.answer(f"📤 Yuborildi: {sent} ta, xato: {failed} ta. (ID: {update_id})")


async def broadcast(bot: Bot, user_ids: list[int], text: str, kb=None) -> tuple[int, int]:
    sent = failed = 0
    for uid in user_ids:
        try:
            await bot.send_message(uid, text, reply_markup=kb, disable_web_page_preview=True)
            sent += 1
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
            try:
                await bot.send_message(uid, text, reply_markup=kb,
                                       disable_web_page_preview=True)
                sent += 1
            except Exception:  # noqa: BLE001
                failed += 1
        except TelegramForbiddenError:
            failed += 1  # foydalanuvchi botni bloklagan
        except Exception as e:  # noqa: BLE001
            log.warning("Yuborilmadi %s: %s", uid, e)
            failed += 1
        await asyncio.sleep(0.05)  # Telegram limiti: ~30 xabar/soniya
    return sent, failed


# ---- /muddat ----
@router.message(Command("muddat"))
async def dl_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(AddDeadline.title)
    await message.answer("1/4. Muddat <b>nomi</b>:\n"
                         "(masalan: QQS bo'yicha choraklik hisobot topshirish)")


@router.message(AddDeadline.title, F.text)
async def dl_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text.strip(), selected=[])
    await state.set_state(AddDeadline.sectors)
    await message.answer("2/4. Qaysi <b>sohalarga</b> tegishli?",
                         reply_markup=sectors_kb([], prefix="asec", done_text="Tayyor ➡️"))


@router.message(AddDeadline.due, F.text)
async def dl_due(message: Message, state: FSMContext):
    due = parse_date(message.text)
    if not due:
        await message.answer("Sana formati noto'g'ri. Masalan: 01.12.2026")
        return
    if due < date.today().isoformat():
        await message.answer("Bu sana o'tib ketgan. Kelgusi sanani kiriting.")
        return
    await state.update_data(due=due)
    await state.set_state(AddDeadline.description)
    await message.answer("4/4. Qisqa <b>izoh</b> (nima qilish kerak) yoki <code>-</code>")


@router.message(AddDeadline.description, F.text)
async def dl_desc(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    desc = None if message.text.strip() == "-" else message.text.strip()
    dl_id = await db.add_deadline(data["title"], data["selected"], data["due"], desc)
    await message.answer(
        f"✅ Muddat qo'shildi (ID: {dl_id}).\n<b>{escape(data['title'])}</b> — "
        f"{fmt_date(data['due'])}\nObunachilarga {', '.join(map(str, REMINDER_DAYS))} "
        f"kun qolganda avtomatik eslatma boradi.")


@router.message(Command("muddatlar"))
async def dl_list(message: Message):
    if not is_admin(message.from_user.id):
        return
    items = await db.upcoming_deadlines(None, limit=50)
    if not items:
        await message.answer("Kelgusi muddatlar yo'q.")
        return
    lines = [f"<code>{d['id']}</code> · {fmt_date(d['due_date'])} · {escape(d['title'])}"
             for d in items]
    await message.answer("\n".join(lines))


@router.message(Command("muddat_ochir"))
async def dl_delete(message: Message, command: CommandObject):
    if not is_admin(message.from_user.id):
        return
    if not command.args or not command.args.strip().isdigit():
        await message.answer("Foydalanish: /muddat_ochir ID")
        return
    ok = await db.delete_deadline(int(command.args.strip()))
    await message.answer("O'chirildi ✅" if ok else "Bunday ID topilmadi.")


# ---- /javob, /stat ----
@router.message(Command("javob"))
async def admin_reply(message: Message, command: CommandObject, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    parts = (command.args or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[0].isdigit():
        await message.answer("Foydalanish: /javob USER_ID matn")
        return
    try:
        await bot.send_message(int(parts[0]),
                               f"✉️ <b>Monita Bot jamoasidan javob:</b>\n\n{escape(parts[1])}")
        await message.answer("Yuborildi ✅")
    except Exception as e:  # noqa: BLE001
        await message.answer(f"Yuborilmadi: {escape(str(e))}")


@router.message(Command("stat"))
async def admin_stats(message: Message):
    if not is_admin(message.from_user.id):
        return
    s = await db.stats()
    by = "\n".join(f"  {SECTORS[k][0]} {SECTORS[k][1]}: {v}"
                   for k, v in sorted(s["by_sector"].items(), key=lambda x: -x[1])
                   if k in SECTORS) or "  —"
    await message.answer(
        f"📊 <b>Statistika</b>\nFoydalanuvchilar: {s['total']}\n"
        f"Faol obunachilar: {s['active']}\nYangiliklar: {s['updates']}\n"
        f"Muddatlar: {s['deadlines']}\n\nSohalar bo'yicha:\n{by}")


# ======================= ESLATMALAR =======================
_reminder_lock = asyncio.Lock()


async def check_reminders(bot: Bot):
    """REMINDER_HOUR dan keyin bo'lsa, bugungi eslatmalarni yuboradi (takrorlanmaydi)."""
    if datetime.now().hour < REMINDER_HOUR or _reminder_lock.locked():
        return
    async with _reminder_lock:
        try:
            await send_due_reminders(bot)
        except Exception as e:  # noqa: BLE001
            log.exception("Eslatma xatosi: %s", e)


async def reminder_loop(bot: Bot):
    """Server uyg'oq turgan paytda har 30 daqiqada tekshiradi."""
    while True:
        await check_reminders(bot)
        await asyncio.sleep(30 * 60)


async def send_due_reminders(bot: Bot):
    today = date.today()
    for d in await db.upcoming_deadlines(None, limit=500):
        left = (date.fromisoformat(d["due_date"]) - today).days
        if left not in REMINDER_DAYS or await db.reminder_sent(d["id"], left):
            continue
        left_txt = "bugun!" if left == 0 else f"{left} kun qoldi"
        text = T.REMINDER.format(
            title=escape(d["title"]), due=fmt_date(d["due_date"]), left=left_txt,
            sectors=escape(sector_names(d["sectors"])),
            description=escape(d.get("description") or ""))
        await db.mark_reminder(d["id"], left)  # avval belgilaymiz — takror yubormaslik uchun
        sent, failed = await broadcast(bot, await db.subscribers_for(d["sectors"]), text)
        log.info("Eslatma #%s (%s kun): %s yuborildi, %s xato", d["id"], left, sent, failed)


# ======================= ISHGA TUSHIRISH =======================
COMMANDS = [
    BotCommand(command="start", description="Botni ishga tushirish"),
    BotCommand(command="menu", description="Asosiy menyu"),
    BotCommand(command="cancel", description="Bekor qilish"),
]


def make_bot_and_dp() -> tuple[Bot, Dispatcher]:
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN topilmadi. .env yoki Render Environment'ni to'ldiring.")
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)
    return bot, dp


def run_webhook():
    """Render Free Web Service uchun: Telegram xabarlarni HTTP orqali yuboradi."""
    from aiohttp import web
    from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

    bot, dp = make_bot_and_dp()
    path = f"/tg/{WEBHOOK_SECRET}"

    async def register_webhook(bot: Bot):
        """Yangi Render manzili DNS'da darhol ko'rinmasligi mumkin — qayta urinamiz."""
        url = f"{BASE_URL}{path}"
        for attempt in range(1, 61):  # ~30 daqiqagacha
            try:
                info = await bot.get_webhook_info()
                if info.url != url:
                    await bot.set_webhook(url, secret_token=WEBHOOK_SECRET)
                log.info("Webhook o'rnatildi: %s/tg/***", BASE_URL)
                return
            except Exception as e:  # noqa: BLE001
                log.warning("Webhook o'rnatilmadi (urinish %s): %s", attempt, e)
                await asyncio.sleep(30)
        log.error("Webhook o'rnatib bo'lmadi. BASE_URL ni tekshiring: %s", BASE_URL)

    async def on_startup(bot: Bot):
        await db.init()
        try:
            await bot.set_my_commands(COMMANDS)
        except Exception as e:  # noqa: BLE001
            log.warning("Buyruqlar ro'yxati o'rnatilmadi: %s", e)
        asyncio.create_task(register_webhook(bot))
        asyncio.create_task(reminder_loop(bot))
        log.info("Server ishga tushdi. BASE_URL=%s | Adminlar: %s", BASE_URL, ADMIN_IDS or "yo'q")

    async def on_shutdown(bot: Bot):
        await db.close()

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    async def health(_):
        return web.Response(text="ok")

    async def tick(request: web.Request):
        # cron-job.org shu manzilni har 10 daqiqada ochadi: server uxlamaydi + eslatmalar
        if request.query.get("key") != WEBHOOK_SECRET:
            return web.Response(status=403, text="forbidden")
        asyncio.create_task(check_reminders(bot))
        return web.Response(text="ok")

    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    app.router.add_get("/tick", tick)
    SimpleRequestHandler(dispatcher=dp, bot=bot, secret_token=WEBHOOK_SECRET).register(app, path)
    setup_application(app, dp, bot=bot)
    web.run_app(app, host="0.0.0.0", port=PORT)


async def run_polling():
    """Kompyuterda sinash uchun (BASE_URL yo'q bo'lsa)."""
    bot, dp = make_bot_and_dp()
    await db.init()
    await bot.set_my_commands(COMMANDS)
    asyncio.create_task(reminder_loop(bot))
    log.info("Polling rejimi. Adminlar: %s", ADMIN_IDS or "yo'q")
    await bot.delete_webhook(drop_pending_updates=True)
    try:
        await dp.start_polling(bot)
    finally:
        await db.close()


if __name__ == "__main__":
    if BASE_URL:
        run_webhook()
    else:
        asyncio.run(run_polling())
