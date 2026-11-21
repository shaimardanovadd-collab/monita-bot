"""Fon vazifalari: muddat eslatmalari, Lex.uz dan matn yuklash va o'zgarishlarni kuzatish."""
import asyncio
from datetime import date, datetime, timedelta

from aiogram import Bot

import db
import legal
from common import (ADMIN_IDS, AUTO_CHECK_DAYS, LEX_BASE, REMINDER_DAYS, REMINDER_HOUR,
                    broadcast, log, notify_act, notify_admins, render_reminder)

LEX_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")

MAX_AUTO_ANNOUNCE = 20  # bir vaqtda shundan ko'p yangi akt bo'lsa — faqat adminga

_reminder_lock = asyncio.Lock()
load_task: asyncio.Task | None = None


# ---------------- muddat eslatmalari ----------------
async def send_due_reminders(bot: Bot):
    today = date.today()
    for d in await db.upcoming_deadlines(None, limit=500):
        left = (date.fromisoformat(d["due_date"]) - today).days
        if left not in REMINDER_DAYS or await db.reminder_sent(d["id"], left):
            continue
        await db.mark_reminder(d["id"], left)  # avval belgilaymiz — takror yubormaslik uchun
        sent, failed = await broadcast(bot, await db.subscribers_for(d["sectors"]),
                                       lambda lang, d=d: render_reminder(d, lang))
        log.info("Eslatma #%s (%s kun): %s yuborildi, %s xato", d["id"], left, sent, failed)


async def periodic(bot: Bot):
    """Har 30 daqiqada (yoki /tick da): eslatmalar + Lex.uz ni rejali tekshirish."""
    if _reminder_lock.locked():
        return
    async with _reminder_lock:
        try:
            if datetime.now().hour >= REMINDER_HOUR:
                await send_due_reminders(bot)
            await maybe_auto_check(bot)
        except Exception as e:  # noqa: BLE001
            log.exception("Fon vazifa xatosi: %s", e)


async def periodic_loop(bot: Bot):
    while True:
        await periodic(bot)
        await asyncio.sleep(30 * 60)


# ---------------- yangi aktlarni e'lon qilish ----------------
async def announce_new_acts(bot: Bot):
    """Reestrga (acts.csv) yangi akt qo'shilgan bo'lsa — mos foydalanuvchilarga xabar."""
    new = list(db.NEW_ACTS_ON_START)
    db.NEW_ACTS_ON_START.clear()
    if not new:
        return
    if len(new) > MAX_AUTO_ANNOUNCE:
        # ehtiyot: juda ko'p "yangi" akt — ehtimol reestr to'liq almashtirilgan; foydalanuvchilarni
        # ko'p xabar bilan bezovta qilmaymiz, faqat adminga
        await notify_admins(bot, f"📚 Reestrga {len(new)} ta yangi akt qo'shildi. Ko'p bo'lgani uchun "
                                 f"foydalanuvchilarga avtomatik yuborilmadi. Kerak bo'lsa /akt orqali "
                                 f"alohida e'lon qiling. / Добавлено {len(new)} актов — слишком много "
                                 f"для авторассылки, пользователям не отправлено.")
    else:
        for act in new:
            await notify_act(bot, act, "new")
        await notify_admins(bot, f"📚 Reestrga {len(new)} ta yangi akt qo'shildi va e'lon qilindi.")
    start_load(bot, None, new, ["uz", "ru"], notify_changes=False)


# ---------------- Lex.uz dan yuklash + o'zgarishlarni aniqlash ----------------
def start_load(bot: Bot, report_to: int | None, acts: list[dict], langs: list[str],
               notify_changes: bool = True) -> bool:
    global load_task
    if load_task and not load_task.done():
        return False
    load_task = asyncio.create_task(load_job(bot, report_to, acts, langs, notify_changes))
    return True


async def load_job(bot: Bot, report_to: int | None, acts: list[dict], langs: list[str],
                   notify_changes: bool = True):
    import aiohttp

    async def say(text: str):
        targets = [report_to] if report_to else list(ADMIN_IDS)
        for uid in targets:
            try:
                await bot.send_message(uid, text, disable_web_page_preview=True)
            except Exception as e:  # noqa: BLE001
                log.warning("Hisobot yuborilmadi: %s", e)

    total, ok, failed, n_chunks, changed = len(acts) * len(langs), 0, [], 0, []
    i = 0
    timeout = aiohttp.ClientTimeout(total=90)
    async with aiohttp.ClientSession(timeout=timeout, headers={"User-Agent": LEX_UA}) as s:
        for a in acts:
            for lang in langs:
                i += 1
                try:
                    async with s.get(f"{LEX_BASE}/{lang}/docs/-{a['lex_id']}") as r:
                        if r.status != 200:
                            raise RuntimeError(f"HTTP {r.status}")
                        html = await r.text(errors="replace")
                    chunks = await asyncio.to_thread(legal.parse_act, html, lang)
                    if not chunks:
                        raise RuntimeError("matn topilmadi")
                    old, new = await db.replace_chunks(a["lex_id"], lang, chunks)
                    if lang == "uz" and old and old != new:
                        changed.append(a)
                    ok += 1
                    n_chunks += len(chunks)
                except Exception as e:  # noqa: BLE001
                    failed.append(f"{a['lex_id']} {lang}: {e}")
                    log.warning("Yuklanmadi %s %s: %s", a["lex_id"], lang, e)
                if i == min(3, total) and ok == 0:
                    await say("⛔️ Birinchi hujjatlar yuklanmadi — Lex.uz serverdan ochilmayapti "
                              "yoki sahifa tuzilishi boshqacha.\n<code>"
                              + "\n".join(failed[-3:]) + "</code>\n"
                              "Kompyuterdan yuklang: START_LOAD_TEXTS.bat")
                    return
                if report_to and i % 25 == 0:
                    await say(f"⏳ {i}/{total}: ✅ {ok}, ❌ {len(failed)}")
                await asyncio.sleep(3)

    await db.meta_set("last_check", datetime.now().isoformat(timespec="minutes"))
    if notify_changes:
        for a in changed:
            await notify_act(bot, a, "changed")
    text = f"✅ Lex.uz tekshiruvi tugadi: {ok}/{total} hujjat, {n_chunks} ta modda/bo'lak."
    if changed:
        text += f"\n✏️ O'zgargan aktlar: {len(changed)} (foydalanuvchilarga xabar yuborildi)"
    if failed:
        text += "\nXatolar (10 tagacha):\n<code>" + "\n".join(failed[:10]) + "</code>"
    await say(text)


async def maybe_auto_check(bot: Bot):
    """AUTO_CHECK_DAYS da bir marta barcha aktlarni Lex.uz da qayta tekshiradi."""
    if AUTO_CHECK_DAYS <= 0 or (load_task and not load_task.done()):
        return
    last = await db.meta_get("last_check")
    if last and datetime.fromisoformat(last) > datetime.now() - timedelta(days=AUTO_CHECK_DAYS):
        return
    if not last:
        # birinchi marta: matnlar hali yuklanmagan bo'lsa, admin /yuklash ni o'zi boshlaydi
        st = await db.chunk_stats()
        if st["with_text"] == 0:
            return
    log.info("Rejali Lex.uz tekshiruvi boshlandi")
    start_load(bot, None, await db.all_acts(), ["uz"], notify_changes=True)
