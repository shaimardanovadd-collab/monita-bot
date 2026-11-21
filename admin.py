"""Admin buyruqlari va demo/test rejimi. Admin matnlari admin tanlagan tilda (uz/ru)."""
from datetime import date, datetime, timedelta
from html import escape

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

import ai
import assistant
import db
import jobs
import legal
from common import (ADMIN_IDS, BASE_URL, PUBLIC_DEMO, broadcast, get_lang, ikb, is_admin,
                    notify_act, panel_url, parse_date, render_act_notice, render_reminder,
                    render_update, show)
import oked
from texts import sector_names, t

router = Router(name="admin")


def a(lang: str, uz: str, ru: str) -> str:
    return ru if lang == "ru" else uz


# ======================= DIAGNOSTIKA (bot va web-panel uchun) =======================
async def diagnostics(bot: Bot) -> dict:
    d = {"time": datetime.now().isoformat(timespec="seconds"),
         "db": "Postgres" if db.USE_PG else "SQLite (vaqtinchalik!)"}
    try:
        d["db_ok"] = await db.ping()
        d["stats"] = await db.stats()
        d["acts"] = await db.chunk_stats()
        d["last_check"] = await db.meta_get("last_check")
        d["drafts"] = await db.draft_stats()
    except Exception as e:  # noqa: BLE001
        d["db_ok"], d["db_error"] = False, str(e)
    d["ai"] = {"configured": ai.is_configured(), "provider": "Gemini", "model": ai.model_name()}
    try:
        info = await bot.get_webhook_info()
        d["webhook"] = {"url_set": bool(info.url), "pending": info.pending_update_count,
                        "last_error": info.last_error_message}
    except Exception as e:  # noqa: BLE001
        d["webhook"] = {"error": str(e)}
    d["mode"] = "webhook" if BASE_URL else "polling"
    d["admins"] = len(ADMIN_IDS)
    d["public_demo"] = PUBLIC_DEMO
    d["loading"] = bool(jobs.load_task and not jobs.load_task.done())
    return d


def diag_text(d: dict, lang: str) -> str:
    ok = lambda b: "✅" if b else "❌"  # noqa: E731
    st, ac, wh = d.get("stats", {}), d.get("acts", {}), d.get("webhook", {})
    lines = [
        "🩺 <b>" + a(lang, "Diagnostika", "Диагностика") + "</b>",
        f"{ok(d.get('db_ok'))} {a(lang, 'Baza', 'База')}: {d['db']}",
        f"👥 {a(lang, 'Foydalanuvchilar', 'Пользователи')}: {st.get('total', '?')} "
        f"({a(lang, 'faol', 'активных')}: {st.get('active', '?')})",
        f"📚 {a(lang, 'Aktlar', 'Акты')}: {ac.get('acts', '?')} · "
        f"{a(lang, 'matni bor', 'с текстом')}: {ac.get('with_text', '?')} · "
        f"{a(lang, 'bo‘laklar', 'фрагментов')}: {ac.get('chunks', '?')}",
        f"🔎 {a(lang, 'Oxirgi Lex.uz tekshiruvi', 'Последняя проверка Lex.uz')}: "
        f"{d.get('last_check') or '—'}" + (" ⏳" if d.get("loading") else ""),
        f"📝 {a(lang, 'Muhokamadagi loyihalar', 'Проекты на обсуждении')}: "
        f"{d.get('drafts', {}).get('in_discussion', '?')} · "
        f"{a(lang, 'sinxron', 'синхр.')}: {d.get('drafts', {}).get('last_sync') or '—'}",
        f"{ok(d['ai']['configured'])} AI: {d['ai']['provider']} · {d['ai']['model']}",
        f"{ok(wh.get('url_set') or d['mode'] == 'polling')} {a(lang, 'Rejim', 'Режим')}: {d['mode']}"
        + (f" · pending {wh.get('pending')}" if wh.get("pending") else "")
        + (f"\n⚠️ {escape(str(wh['last_error']))}" if wh.get("last_error") else ""),
        f"🧪 PUBLIC_DEMO: {'on' if d['public_demo'] else 'off'} · "
        f"{a(lang, 'adminlar', 'админов')}: {d['admins']}",
    ]
    if d.get("db_error"):
        lines.append(f"⚠️ <code>{escape(d['db_error'][:300])}</code>")
    return "\n".join(lines)


# ======================= DEMO / TEST =======================
def can_demo(uid: int) -> bool:
    return is_admin(uid) or PUBLIC_DEMO


def demo_kb(lang: str, uid: int):
    rows = [[(t("demo_new", lang), "dm:new"), (t("demo_change", lang), "dm:chg")],
            [(t("demo_news", lang), "dm:news"), (t("demo_rem", lang), "dm:rem")],
            [(t("demo_draft", lang), "dm:draft"), (t("demo_ai", lang), "dm:ai")]]
    if is_admin(uid):
        rows.append([(t("demo_diag", lang), "dm:diag")])
        if panel_url():
            rows.append([(t("demo_panel", lang), panel_url())])
    rows.append([(t("btn_menu", lang), "m")])
    return ikb(rows)


async def demo_act(uid: int) -> dict:
    """Foydalanuvchi sohasiga mos haqiqiy akt (demo uchun)."""
    user = await db.get_user(uid)
    acts = await db.acts_for_oked(legal.oked_for_sectors((user or {}).get("sectors") or []))
    specific = [x for x in acts if x["oked"] != "ALL"]
    return (specific or acts or [{"lex_id": "31846", "title": "Demo", "oked": "ALL",
                                  "act_type": "Закон", "requisites": "—", "effective": None,
                                  "url": "https://lex.uz/uz/docs/-31846"}])[0]


@router.callback_query(F.data == "demo")
@router.message(Command("test", "demo"))
async def demo_screen(event: Message | CallbackQuery, state: FSMContext):
    uid = event.from_user.id
    if not can_demo(uid):
        return
    await state.clear()
    lang = await get_lang(uid)
    await show(event, t("demo", lang), demo_kb(lang, uid))
    if isinstance(event, CallbackQuery):
        await event.answer()


@router.callback_query(F.data.startswith("dm:"))
async def demo_action(cq: CallbackQuery, bot: Bot):
    uid = cq.from_user.id
    if not can_demo(uid):
        await cq.answer()
        return
    lang = await get_lang(uid)
    kind = cq.data.split(":")[1]
    user = await db.get_user(uid) or {}
    sectors = user.get("sectors") or ["G"]
    me = [{"user_id": uid, "lang": lang}]

    if kind in ("new", "chg"):
        act = await demo_act(uid)
        text, kb = render_act_notice(act, lang, "new" if kind == "new" else "changed", demo=True)
        await bot.send_message(uid, text, reply_markup=kb, disable_web_page_preview=True)
    elif kind == "news":
        # haqiqiy ma'lumot: sohangizdagi eng so'nggi akt + Gemini qisqa mazmuni (hujjat matnidan)
        acts = await assistant.latest_acts_for(sectors, limit=1)
        if not acts:
            await cq.answer(t("not_found", lang), show_alert=True)
            return
        act = acts[0]
        await cq.answer("🤖 …")
        await bot.send_chat_action(uid, "typing")
        head = (t("demo_tag", lang) + t("news_screen", lang) + "\n"
                + f"📄 <b>{escape(act['act_type'] or '')}</b> · {escape(act['requisites'] or '')}\n"
                + f"«{escape(act['title'])}»\n📅 {escape(act['effective'] or '—')}\n\n")
        try:
            res = await assistant.act_summary(act, sectors, lang)
            body = head + assistant.md_to_html(res["answer"]) + (
                "" if res["has_text"] else f"\n\n<i>{t('summary_no_text', lang)}</i>")
        except Exception as e:  # noqa: BLE001
            body = head + assistant.error_text(e, lang) + f"\n<code>{escape(str(e))[:200]}</code>"
        kb = ikb([[(t("btn_lex", lang), act["url"])],
                  [(t("btn_ask_ai_act", lang), f"aiact:{act['lex_id']}"), (t("btn_menu", lang), "m")]])
        for i, part in enumerate(parts := assistant.split_message(body)):
            await bot.send_message(uid, part, disable_web_page_preview=True,
                                   reply_markup=kb if i == len(parts) - 1 else None)
        return
    elif kind == "draft":
        items = await db.drafts_for_oked(oked.normalize(sectors), active_only=True, limit=3)
        if not items:
            await cq.answer(t("drafts_not_synced", lang), show_alert=True)
            return
        from common import render_drafts_digest
        await broadcast(bot, me, lambda lg: render_drafts_digest(items, lg, demo=True))
    elif kind == "rem":
        d = {"title": a(lang, "QQS bo'yicha choraklik hisobot", "Квартальный отчёт по НДС"),
             "due_date": (date.today() + timedelta(days=3)).isoformat(), "sectors": sectors,
             "description": a(lang, "Hisobotni my.soliq.uz orqali topshiring.",
                              "Сдайте отчёт через my.soliq.uz.")}
        await broadcast(bot, me, lambda lg: render_reminder(d, lg, demo=True))
    elif kind == "ai":
        await cq.answer(t("ai_err_cooldown", lang))
        await bot.send_chat_action(uid, "typing")
        q = t("demo_ai_q", lang)
        try:
            ai.reset(uid)
            res = await assistant.run(uid, q, sectors, lang)
            body = (f"🧪 <b>{escape(q)}</b>\n\n" + assistant.md_to_html(res["answer"])
                    + assistant.sources_html(res["sources"], lang, cited=res["cited"])
                    + assistant.read_note(res, lang)
                    + f"\n\n⏱ {res['ms']} ms · "
                    + a(lang, f"topilgan moddalar: {len(res['sources'])}",
                        f"найдено статей: {len(res['sources'])}"))
        except Exception as e:  # noqa: BLE001
            body = assistant.error_text(e, lang) + f"\n<code>{escape(str(e))[:300]}</code>"
        for part in assistant.split_message(body):
            await bot.send_message(uid, part, disable_web_page_preview=True)
        return
    elif kind == "diag" and is_admin(uid):
        await bot.send_message(uid, diag_text(await diagnostics(bot), lang))
    await cq.answer(t("demo_sent", lang))


# ======================= ADMIN PANEL =======================
def admin_help(lang: str) -> str:
    return a(lang,
             "🛠 <b>Admin panel</b>\n"
             "/yangilik — yangilik e'lon qilish (mos sohalarga)\n"
             "/akt — yangi NPA qo'shish va e'lon qilish\n"
             "/muddat — muhim muddat (avto-eslatmalar)\n"
             "/muddatlar, /muddat_ochir ID\n"
             "/yuklash [N] — Lex.uz matnlari + o'zgarishlarni tekshirish\n"
             "/qonunlar — matnlar bazasi holati\n"
             "/loyihalar — regulation.adliya.uz dan loyihalarni hozir yangilash\n"
             "/test — demo va diagnostika\n"
             "/javob ID matn — foydalanuvchiga javob\n"
             "/stat — statistika · /cancel — bekor qilish",
             "🛠 <b>Админ-панель</b>\n"
             "/yangilik — опубликовать новость (по сферам)\n"
             "/akt — добавить новый НПА и разослать\n"
             "/muddat — важный срок (автонапоминания)\n"
             "/muddatlar, /muddat_ochir ID\n"
             "/yuklash [N] — тексты с Lex.uz + проверка изменений\n"
             "/qonunlar — состояние базы текстов\n"
             "/loyihalar — обновить проекты с regulation.adliya.uz сейчас\n"
             "/test — демо и диагностика\n"
             "/javob ID текст — ответить пользователю\n"
             "/stat — статистика · /cancel — отмена")


@router.callback_query(F.data == "adm")
@router.message(Command("admin"))
async def admin_panel(event: Message | CallbackQuery, state: FSMContext):
    if not is_admin(event.from_user.id):
        return
    await state.clear()
    lang = await get_lang(event.from_user.id)
    kb = ikb([[(t("btn_demo", lang), "demo"), (t("demo_diag", lang), "dm:diag")],
              [(t("btn_menu", lang), "m")]])
    await show(event, admin_help(lang), kb)
    if isinstance(event, CallbackQuery):
        await event.answer()


def sectors_pick_kb(selected: list[str], lang: str, with_all: bool = False):
    rows, row = [], []
    for key in oked.BUSINESS:
        mark = "✅" if key in selected else "▫️"
        row.append((f"{mark} {oked.section_label(key, lang)}", f"asec:{key}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    if with_all:
        mark = "✅" if "ALL" in selected else "▫️"
        rows.append([(f"{mark} 🌍 " + t("all_sectors", lang), "asec:ALL")])
    rows.append([(a(lang, "Tayyor ➡️", "Готово ➡️"), "asec:done")])
    return ikb(rows)


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


class AddAct(StatesGroup):
    url = State()
    title = State()
    sectors = State()
    kind = State()
    effective = State()
    confirm = State()


@router.callback_query(AddUpdate.sectors, F.data.startswith("asec:"))
@router.callback_query(AddDeadline.sectors, F.data.startswith("asec:"))
@router.callback_query(AddAct.sectors, F.data.startswith("asec:"))
async def admin_sector_toggle(cq: CallbackQuery, state: FSMContext):
    lang = await get_lang(cq.from_user.id)
    key = cq.data.split(":", 1)[1]
    data = await state.get_data()
    selected: list[str] = data.get("selected", [])
    current = await state.get_state()
    if key == "done":
        if not selected:
            await cq.answer(t("need_one_sector", lang), show_alert=True)
            return
        names = t("all_sectors", lang) if "ALL" in selected else sector_names(selected, lang)
        await cq.message.edit_text(f"💼 {escape(names)}")
        if current == AddUpdate.sectors.state:
            await state.set_state(AddUpdate.summary)
            await cq.message.answer(a(lang, "3/6. <b>Nima o'zgardi?</b> 1–2 gap:",
                                      "3/6. <b>Что изменилось?</b> 1–2 предложения:"))
        elif current == AddDeadline.sectors.state:
            await state.set_state(AddDeadline.due)
            await cq.message.answer(a(lang, "3/4. <b>Muddat sanasi</b> (01.12.2026):",
                                      "3/4. <b>Дата срока</b> (01.12.2026):"))
        else:
            await state.set_state(AddAct.kind)
            await cq.message.answer(a(
                lang, "4/5. <b>Turi va rekvizitlari</b> bitta qatorda, masalan:\n"
                      "<code>Постановление Президента; PQ-400, 20.11.2026-y.</code>",
                "4/5. <b>Вид и реквизиты</b> одной строкой, например:\n"
                "<code>Постановление Президента; PQ-400, 20.11.2026-y.</code>"))
        await cq.answer()
        return
    if key == "ALL":
        selected = [] if "ALL" in selected else ["ALL"]
    else:
        selected = [x for x in selected if x != "ALL"]
        if key in selected:
            selected.remove(key)
        elif key in oked.SECTIONS:
            selected.append(key)
    await state.update_data(selected=selected)
    await cq.message.edit_reply_markup(
        reply_markup=sectors_pick_kb(selected, lang, with_all=current == AddAct.sectors.state))
    await cq.answer()


# ---- /akt: yangi NPA ----
@router.message(Command("akt"))
async def act_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    lang = await get_lang(message.from_user.id)
    await state.set_state(AddAct.url)
    await message.answer(a(lang, "📚 <b>Yangi NPA</b>\n1/5. Lex.uz havolasini yuboring "
                                 "(masalan https://lex.uz/uz/docs/-8537009):",
                           "📚 <b>Новый НПА</b>\n1/5. Пришлите ссылку Lex.uz "
                           "(например https://lex.uz/uz/docs/-8537009):"))


@router.message(AddAct.url, F.text)
async def act_url(message: Message, state: FSMContext):
    import re
    lang = await get_lang(message.from_user.id)
    m = re.search(r"lex\.uz/(?:\w+/)?docs/-?(\d+)", message.text)
    if not m:
        await message.answer(a(lang, "Lex.uz havolasi topilmadi. Qayta yuboring.",
                               "Не вижу ссылку Lex.uz. Пришлите ещё раз."))
        return
    lex_id = m.group(1)
    exists = await db.get_act(lex_id)
    await state.update_data(lex_id=lex_id, url=f"https://lex.uz/uz/docs/-{lex_id}")
    await state.set_state(AddAct.title)
    note = a(lang, "⚠️ Bu akt bazada bor — ma'lumotlari yangilanadi.\n",
             "⚠️ Этот акт уже есть в базе — данные обновятся.\n") if exists else ""
    await message.answer(note + a(lang, "2/5. Hujjat <b>nomi</b>:", "2/5. <b>Название</b> акта:"))


@router.message(AddAct.title, F.text)
async def act_title(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    await state.update_data(title=message.text.strip(), selected=[])
    await state.set_state(AddAct.sectors)
    await message.answer(a(lang, "3/5. Qaysi <b>sohalarga</b> tegishli?",
                           "3/5. Каких <b>сфер</b> касается?"),
                         reply_markup=sectors_pick_kb([], lang, with_all=True))


@router.message(AddAct.kind, F.text)
async def act_kind(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    parts = [p.strip() for p in message.text.split(";", 1)]
    await state.update_data(act_type=parts[0], requisites=parts[1] if len(parts) > 1 else "")
    await state.set_state(AddAct.effective)
    await message.answer(a(lang, "5/5. <b>Kuchga kirgan sana</b> (01.12.2026) yoki <code>-</code>",
                           "5/5. <b>Дата вступления в силу</b> (01.12.2026) или <code>-</code>"))


@router.message(AddAct.effective, F.text)
async def act_effective(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    txt = message.text.strip()
    eff = None if txt == "-" else parse_date(txt)
    if txt != "-" and not eff:
        await message.answer(a(lang, "Sana formati: 01.12.2026", "Формат даты: 01.12.2026"))
        return
    await state.update_data(effective=eff)
    data = await state.get_data()
    sel = data["selected"]
    oked_codes = "ALL" if "ALL" in sel else ",".join(sorted(oked.normalize(sel)))
    await state.update_data(oked=oked_codes)
    act = {**data, "oked": oked_codes}
    subs = await _subs_count(act)
    text, _ = render_act_notice(act, lang, "new")
    await state.set_state(AddAct.confirm)
    await message.answer(
        a(lang, "<b>Ko'rib chiqing</b> (OKED: {o}):\n\n", "<b>Проверьте</b> (ОКЭД: {o}):\n\n")
        .format(o=oked_codes) + text,
        reply_markup=ikb([[(a(lang, f"✅ Saqlash va yuborish ({subs})",
                              f"✅ Сохранить и разослать ({subs})"), "actpub:yes")],
                          [(a(lang, "💾 Faqat saqlash", "💾 Только сохранить"), "actpub:save")],
                          [(a(lang, "❌ Bekor qilish", "❌ Отмена"), "actpub:no")]]),
        disable_web_page_preview=True)


async def _subs_count(act: dict) -> int:
    from common import subscribers_for_act
    return len(await subscribers_for_act(act))


@router.callback_query(AddAct.confirm, F.data.startswith("actpub:"))
async def act_publish(cq: CallbackQuery, state: FSMContext, bot: Bot):
    lang = await get_lang(cq.from_user.id)
    choice = cq.data.split(":")[1]
    data = await state.get_data()
    await state.clear()
    await cq.message.edit_reply_markup(reply_markup=None)
    if choice == "no":
        await cq.message.answer(t("cancelled", lang))
        await cq.answer()
        return
    await db.add_act(data["lex_id"], data["title"], data["oked"], "", data["act_type"],
                     data["requisites"], data.get("effective"), data["url"])
    act = await db.get_act(data["lex_id"])
    msg = a(lang, "💾 Saqlandi.", "💾 Сохранено.")
    if choice == "yes":
        sent, failed = await notify_act(bot, act, "new")
        msg += a(lang, f" 📤 Yuborildi: {sent}, xato: {failed}.",
                 f" 📤 Отправлено: {sent}, ошибок: {failed}.")
    started = jobs.start_load(bot, cq.from_user.id, [act], ["uz", "ru"], notify_changes=False)
    if started:
        msg += a(lang, "\n📥 Matni Lex.uz dan yuklanmoqda…", "\n📥 Загружаю текст с Lex.uz…")
    await cq.message.answer(msg)
    await cq.answer()


# ---- /yangilik ----
@router.message(Command("yangilik"))
async def upd_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    lang = await get_lang(message.from_user.id)
    await state.set_state(AddUpdate.title)
    await message.answer(a(lang, "📰 1/6. Yangilik <b>sarlavhasi</b>:",
                           "📰 1/6. <b>Заголовок</b> новости:"))


@router.message(AddUpdate.title, F.text)
async def upd_title(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    await state.update_data(title=message.text.strip(), selected=[])
    await state.set_state(AddUpdate.sectors)
    await message.answer(a(lang, "2/6. Qaysi <b>sohalarga</b>?", "2/6. Для каких <b>сфер</b>?"),
                         reply_markup=sectors_pick_kb([], lang))


@router.message(AddUpdate.summary, F.text)
async def upd_summary(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    await state.update_data(summary=message.text.strip())
    await state.set_state(AddUpdate.effective)
    await message.answer(a(lang, "4/6. <b>Qachondan</b>? (01.12.2026) yoki <code>-</code>",
                           "4/6. <b>С какого числа</b>? (01.12.2026) или <code>-</code>"))


@router.message(AddUpdate.effective, F.text)
async def upd_effective(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    txt = message.text.strip()
    eff = None if txt == "-" else parse_date(txt)
    if txt != "-" and not eff:
        await message.answer(a(lang, "Sana formati: 01.12.2026", "Формат даты: 01.12.2026"))
        return
    await state.update_data(effective=eff)
    await state.set_state(AddUpdate.source)
    await message.answer(a(lang, "5/6. <b>Manba havolasi</b> yoki <code>-</code>",
                           "5/6. <b>Ссылка на источник</b> или <code>-</code>"))


@router.message(AddUpdate.source, F.text)
async def upd_source(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    txt = message.text.strip()
    if txt != "-" and not txt.startswith(("http://", "https://")):
        await message.answer(a(lang, "Havola http(s):// bilan boshlanishi kerak.",
                               "Ссылка должна начинаться с http(s)://"))
        return
    await state.update_data(source_url=None if txt == "-" else txt)
    await state.set_state(AddUpdate.details)
    await message.answer(a(lang, "6/6. <b>Batafsil</b> matn yoki <code>-</code>",
                           "6/6. <b>Подробный</b> текст или <code>-</code>"))


@router.message(AddUpdate.details, F.text)
async def upd_details(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    txt = message.text.strip()
    await state.update_data(details=None if txt == "-" else txt)
    data = await state.get_data()
    preview, _ = render_update({**data, "id": None, "sectors": data["selected"]}, lang)
    subs = await db.subscribers_for(data["selected"])
    await state.set_state(AddUpdate.confirm)
    await message.answer(
        a(lang, "<b>Ko'rib chiqing:</b>\n\n", "<b>Проверьте:</b>\n\n") + preview,
        reply_markup=ikb([[(a(lang, f"✅ Yuborish ({len(subs)})", f"✅ Отправить ({len(subs)})"),
                            "pub:yes")],
                          [(a(lang, "❌ Bekor qilish", "❌ Отмена"), "pub:no")]]),
        disable_web_page_preview=True)


@router.callback_query(AddUpdate.confirm, F.data.startswith("pub:"))
async def upd_publish(cq: CallbackQuery, state: FSMContext, bot: Bot):
    lang = await get_lang(cq.from_user.id)
    data = await state.get_data()
    await state.clear()
    await cq.message.edit_reply_markup(reply_markup=None)
    if cq.data == "pub:no":
        await cq.message.answer(t("cancelled", lang))
        await cq.answer()
        return
    update_id = await db.add_update(data["title"], data["selected"], data["summary"],
                                    data.get("effective"), data.get("source_url"),
                                    data.get("details"))
    u = await db.get_update(update_id)
    await cq.answer("…")
    sent, failed = await broadcast(bot, await db.subscribers_for(u["sectors"]),
                                   lambda lg: render_update(u, lg))
    await cq.message.answer(a(lang, f"📤 Yuborildi: {sent}, xato: {failed} (ID {update_id})",
                              f"📤 Отправлено: {sent}, ошибок: {failed} (ID {update_id})"))


# ---- /muddat ----
@router.message(Command("muddat"))
async def dl_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    lang = await get_lang(message.from_user.id)
    await state.set_state(AddDeadline.title)
    await message.answer(a(lang, "📅 1/4. Muddat <b>nomi</b>:", "📅 1/4. <b>Название</b> срока:"))


@router.message(AddDeadline.title, F.text)
async def dl_title(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    await state.update_data(title=message.text.strip(), selected=[])
    await state.set_state(AddDeadline.sectors)
    await message.answer(a(lang, "2/4. Qaysi <b>sohalarga</b>?", "2/4. Для каких <b>сфер</b>?"),
                         reply_markup=sectors_pick_kb([], lang))


@router.message(AddDeadline.due, F.text)
async def dl_due(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    due = parse_date(message.text)
    if not due or due < date.today().isoformat():
        await message.answer(a(lang, "Kelgusi sanani kiriting (01.12.2026).",
                               "Введите будущую дату (01.12.2026)."))
        return
    await state.update_data(due=due)
    await state.set_state(AddDeadline.description)
    await message.answer(a(lang, "4/4. Qisqa <b>izoh</b> yoki <code>-</code>",
                           "4/4. Краткое <b>описание</b> или <code>-</code>"))


@router.message(AddDeadline.description, F.text)
async def dl_desc(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    data = await state.get_data()
    await state.clear()
    desc = None if message.text.strip() == "-" else message.text.strip()
    dl_id = await db.add_deadline(data["title"], data["selected"], data["due"], desc)
    await message.answer(a(lang, f"✅ Muddat qo'shildi (ID {dl_id}). Eslatmalar: 7, 3, 1 kun va o'sha kuni.",
                           f"✅ Срок добавлен (ID {dl_id}). Напоминания: за 7, 3, 1 день и в день срока."))


@router.message(Command("muddatlar"))
async def dl_list(message: Message):
    if not is_admin(message.from_user.id):
        return
    items = await db.upcoming_deadlines(None, limit=50)
    await message.answer("\n".join(f"<code>{d['id']}</code> · {d['due_date']} · {escape(d['title'])}"
                                   for d in items) or "—")


@router.message(Command("muddat_ochir"))
async def dl_delete(message: Message, command: CommandObject):
    if not is_admin(message.from_user.id):
        return
    arg = (command.args or "").strip()
    ok = arg.isdigit() and await db.delete_deadline(int(arg))
    await message.answer("✅" if ok else "ID?")


# ---- /yuklash, /qonunlar ----
@router.message(Command("yuklash"))
async def admin_load(message: Message, command: CommandObject, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    lang = await get_lang(message.from_user.id)
    acts = await db.all_acts()
    arg = (command.args or "").strip()
    if arg.isdigit():
        acts = acts[:int(arg)]
    if not jobs.start_load(bot, message.from_user.id, acts, ["uz", "ru"]):
        await message.answer(a(lang, "Yuklash allaqachon ketmoqda.", "Загрузка уже идёт."))
        return
    mins = max(1, len(acts) * 2 * 4 // 60)
    await message.answer(a(lang, f"📥 {len(acts)} ta akt (uz+ru) yuklanmoqda, ~{mins} daq. "
                                 "O'zgargan aktlar bo'yicha foydalanuvchilarga xabar boradi.",
                           f"📥 Загружаю {len(acts)} актов (uz+ru), ~{mins} мин. "
                           "Об изменённых актах пользователи получат уведомление."))


@router.message(Command("qonunlar"))
async def admin_acts(message: Message):
    if not is_admin(message.from_user.id):
        return
    lang = await get_lang(message.from_user.id)
    st = await db.chunk_stats()
    await message.answer(a(lang, "📚 Aktlar: {a} · matni bor: {w} · bo'laklar: {c}\nOxirgi tekshiruv: {l}",
                           "📚 Актов: {a} · с текстом: {w} · фрагментов: {c}\nПоследняя проверка: {l}")
                         .format(a=st["acts"], w=st["with_text"], c=st["chunks"],
                                 l=await db.meta_get("last_check") or "—"))


@router.message(Command("loyihalar"))
async def admin_sync_drafts(message: Message, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    lang = await get_lang(message.from_user.id)
    try:
        r = await jobs.sync_drafts(bot)
    except Exception as e:  # noqa: BLE001
        await message.answer(f"❌ regulation.adliya.uz: <code>{escape(str(e))[:300]}</code>")
        return
    await message.answer(a(lang, f"📝 Muhokamada: {r['total']} · yangi: {r['new']} · xabar yuborildi: {r['sent']}",
                           f"📝 На обсуждении: {r['total']} · новых: {r['new']} · уведомлений: {r['sent']}"))


# ---- /javob, /stat ----
@router.message(Command("javob"))
async def admin_reply(message: Message, command: CommandObject, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    parts = (command.args or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[0].isdigit():
        await message.answer("/javob USER_ID ...")
        return
    try:
        ulang = await get_lang(int(parts[0]))
        await bot.send_message(int(parts[0]), t("admin_reply", ulang, text=escape(parts[1])))
        await message.answer("✅")
    except Exception as e:  # noqa: BLE001
        await message.answer(f"❌ {escape(str(e))}")


@router.message(Command("stat"))
async def admin_stats(message: Message):
    if not is_admin(message.from_user.id):
        return
    lang = await get_lang(message.from_user.id)
    s = await db.stats()
    by = "\n".join(f"  {oked.section_label(k, lang)}: {v}" for k, v in
                   sorted(s["by_sector"].items(), key=lambda x: -x[1]) if k in oked.SECTIONS) or "  —"
    await message.answer(f"📊 <b>{a(lang, 'Statistika', 'Статистика')}</b>\n"
                         f"👥 {s['total']} · {a(lang, 'faol', 'активных')}: {s['active']}\n"
                         f"📰 {s['updates']} · 📅 {s['deadlines']}\n\n{by}")

