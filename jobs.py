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

DRAFTS_SYNC_HOURS = float(__import__("os").getenv("DRAFTS_SYNC_HOURS", "3"))
DIGEST_HOURS = (9, 21)   # loyihalar haqidagi xabarlar faqat kunduzi (mahalliy vaqt)
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


_last_periodic = 0.0
PERIODIC_MIN_GAP = 25 * 60   # bazaga ko'pi bilan 25–30 daqiqada bir marta murojaat


async def periodic(bot: Bot):
    """Eslatmalar, Lex.uz tekshiruvi, loyihalar. /tick (cron) har 10 daqiqada chaqirsa ham,
    bazaga ko'pi bilan har 25 daqiqada murojaat qilinadi — Neon Free bazasi uxlab
    turishi va oylik 100 CU-soat limitidan oshmasligi uchun."""
    global _last_periodic
    import time as _time
    if _reminder_lock.locked() or _time.time() - _last_periodic < PERIODIC_MIN_GAP:
        return
    _last_periodic = _time.time()
    async with _reminder_lock:
        try:
            if datetime.now().hour >= REMINDER_HOUR:
                await send_due_reminders(bot)
            await maybe_auto_check(bot)
            await maybe_sync_drafts(bot)
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


async def initial_load(bot: Bot):
    """Matnlar bazasi bo'sh bo'lsa — ishga tushganda avtomatik yuklash (kuniga ko'pi bilan 1 urinish)."""
    st = await db.chunk_stats()
    if st["acts"] == 0 or st["with_text"] >= st["acts"] * 0.5 or (load_task and not load_task.done()):
        return
    today = date.today().isoformat()
    if await db.meta_get("initial_load_try") == today:
        return
    await db.meta_set("initial_load_try", today)
    acts = await db.all_acts()
    done = await db.lex_ids_with_text()
    todo = [a for a in acts if a["lex_id"] not in done]
    await notify_admins(bot, f"📥 Bazada matnlar kam ({st['with_text']}/{st['acts']}). Lex.uz dan "
                             f"{len(todo)} ta akt avtomatik yuklanmoqda (~{max(1, len(todo) * 8 // 60)} daq). "
                             f"/ Автозагрузка текстов с Lex.uz: {len(todo)} актов.")
    start_load(bot, None, todo, ["uz", "ru"], notify_changes=False)


# ---------------- bitta akt matnini darhol yuklash (savol paytida) ----------------
_lex_down_until = 0.0   # Lex.uz serverdan ochilmasa — 30 daqiqa qayta urinmaymiz


async def fetch_act_now(act: dict, langs: list[str], timeout: float = 25) -> bool:
    """Foydalanuvchi aynan shu akt haqida so'raganda matnni Lex.uz dan hozir oladi va saqlaydi.
    True — kamida bitta til yuklandi."""
    global _lex_down_until
    import time as _time
    import aiohttp
    if _time.time() < _lex_down_until:
        return False
    ok = False
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout),
                                         headers={"User-Agent": LEX_UA}) as s:
            for lang in langs:
                async with s.get(f"{LEX_BASE}/{lang}/docs/-{act['lex_id']}") as r:
                    if r.status != 200:
                        raise RuntimeError(f"HTTP {r.status}")
                    html = await r.text(errors="replace")
                chunks = await asyncio.to_thread(legal.parse_act, html, lang)
                if chunks:
                    await db.replace_chunks(act["lex_id"], lang, chunks)
                    ok = True
    except Exception as e:  # noqa: BLE001
        log.warning("Lex.uz dan %s darhol olinmadi: %s", act.get("lex_id"), e)
        if not ok:
            _lex_down_until = _time.time() + 1800
    return ok


async def fetch_acts_now(acts: list[dict], lang: str, limit: int = 3, timeout: float = 25) -> int:
    """Bir nechta aktni parallel yuklash (umumiy vaqt chegarasi bilan)."""
    langs = ["uz"] if lang == "uz" else ["uz", lang]
    todo = acts[:limit]
    if not todo:
        return 0
    try:
        res = await asyncio.wait_for(asyncio.gather(*(fetch_act_now(a, langs, timeout) for a in todo)),
                                     timeout + 5)
    except asyncio.TimeoutError:
        return 0
    return sum(1 for x in res if x)


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


# ---------------- NPA loyihalari (regulation.adliya.uz) ----------------
async def sync_drafts(bot: Bot | None = None) -> dict:
    """Portaldan muhokamadagi loyihalarni oladi, saqlaydi, yangilari haqida xabar beradi."""
    import drafts
    items = await drafts.fetch_in_discussion()
    new = await db.upsert_drafts(items)
    await db.meta_set("drafts_last_sync", datetime.now().isoformat(timespec="minutes"))
    log.info("Loyihalar sinxronlandi: %s ta muhokamada, %s ta yangi", len(items), len(new))
    sent = 0
    if bot:
        sent = await send_draft_digests(bot)
    return {"total": len(items), "new": len(new), "sent": sent}


async def send_draft_digests(bot: Bot) -> int:
    """Hali xabar qilinmagan loyihalar — har bir foydalanuvchiga bitta jamlangan xabar
    (faqat uning OKED bo'limiga tegishlilari). Kechasi yuborilmaydi."""
    from common import render_drafts_digest, subscribers_for_draft_letters
    import oked
    if not (DIGEST_HOURS[0] <= datetime.now().hour < DIGEST_HOURS[1]):
        return 0
    pending = [d for d in await db.pending_drafts() if d.get("oked")]
    if not pending:
        return 0
    letters_all = set()
    for d in pending:
        letters_all |= set(d["oked"].split(","))
    sent = 0
    for sub in await subscribers_for_draft_letters(letters_all):
        items = [d for d in pending if oked.match(d["oked"].split(","), sub["sectors"])]
        if not items:
            continue
        items.sort(key=lambda d: d.get("end_date") or "")
        s, _ = await broadcast(bot, [sub], lambda lg, items=items: render_drafts_digest(items, lg))
        sent += s
    await db.mark_drafts_notified([d["id"] for d in pending])
    return sent


async def maybe_sync_drafts(bot: Bot):
    if DRAFTS_SYNC_HOURS <= 0:
        return
    last = await db.meta_get("drafts_last_sync")
    if last and datetime.fromisoformat(last) > datetime.now() - timedelta(hours=DRAFTS_SYNC_HOURS):
        await send_draft_digests(bot)   # kechasi kelgan loyihalar — ertalab
        return
    try:
        await sync_drafts(bot)
    except Exception as e:  # noqa: BLE001
        log.warning("Loyihalarni olishda xato: %s", e)
        await db.meta_set("drafts_last_sync", datetime.now().isoformat(timespec="minutes"))
        if not await db.meta_get("drafts_error_reported"):
            await db.meta_set("drafts_error_reported", "1")
            await notify_admins(bot, f"⚠️ regulation.adliya.uz dan loyihalar olinmadi: {e}")
