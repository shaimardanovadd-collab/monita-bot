"""
Gemini (Google AI Studio) bilan ishlash. Kalit: GEMINI_API_KEY (aistudio.google.com/apikey).

Model tanlash avtomatik: GEMINI_MODEL berilgan bo'lsa — u birinchi; so'ng Google API dagi
eng yangi barqaror Flash modellari (masalan gemini-3.x-flash), keyin Flash-Lite.
Model topilmasa (404) yoki bepul limiti tugasa (429) — keyingisiga o'tadi.
"""
import os
import re
import time
from collections import defaultdict, deque

import aiohttp

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "").strip()
API_BASE = "https://generativelanguage.googleapis.com/v1beta"
# API ro'yxati ochilmasa ishlatiladigan zaxira nomlar
FALLBACK_MODELS = ["gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-2.5-flash",
                   "gemini-2.5-flash-lite"]
SKIP_WORDS = ("image", "tts", "live", "audio", "embedding", "preview", "exp", "translate",
              "omni", "robotics", "computer", "veo", "nano", "lyria", "native", "learnlm")

MAX_HISTORY = 8              # suhbatda oxirgi 8 ta xabar
MAX_MESSAGE_CHARS = 3000     # bitta savol uzunligi
MAX_OUTPUT_TOKENS = 4096     # (fikrlovchi modellar uchun zaxira bilan)
TIMEOUT_S = 120
COOLDOWN_S = 5
DAILY_LIMIT = int(os.getenv("AI_DAILY_LIMIT", "30"))
# Gemini Lex.uz sahifalarini o'zi o'qiydi (URL context). 0 — o'chiq
READ_URLS = os.getenv("AI_READ_URLS", "1") == "1"
MAX_URLS = int(os.getenv("AI_MAX_URLS", "5"))
_no_url_tool: set[str] = set()   # URL context qo'llamaydigan modellar

active_model: str | None = None
_cooldown_until: dict[str, float] = {}   # limiti tugagan model -> qachongacha chetlab o'tiladi
_models_cache: tuple[float, list[str]] = (0.0, [])

SYSTEM_PROMPT = """Sen "Monita Bot"ning yuridik ma'lumot yordamchisisan. Tadbirkorlarga \
O'zbekiston qonunchiligi bo'yicha FAQAT bot bazasidagi ma'lumotlar asosida javob berasan.

QAT'IY QOIDALAR:
1. Javobni FAQAT pastdagi KONTEKST ga asoslab yoz: [S..] — qonun matnidan parchalar, \
[R..] — amaldagi hujjatlar reestri, [P..] — muhokamadagi loyihalar, [N..] — bot yangiliklari, \
[D..] — muhim muddatlar. \
O'z umumiy bilimingdan qonun normalari, raqamlar, sanalar, stavkalar, jarimalar, \
hujjat nomlari QO'SHMA.
2. Har bir da'vodan keyin manba tegini qo'y, masalan: «... litsenziya talab qilinadi [S2].» \
Faqat kontekstdagi teglarni ishlat, yangi teg o'ylab topma.
3. Modda/band raqamini faqat [S..] parchasida ko'rsatilgan bo'lsa ayt.
4. Agar kontekstda savolga javob bo'lmasa — buni ochiq ayt: «Bazamizdagi hujjatlarda bu savolga \
aniq javob topilmadi» (ruscha: «В нашей базе нет точного ответа на этот вопрос») va reestrdan \
eng mos 1–3 ta hujjatni [R..] teglari bilan tavsiya qil. Taxmin qilma.
5. «O'QISH UCHUN LEX.UZ SAHIFALARI» bo'limidagi havolalarni URL context vositasi bilan \
och va o'qi; ulardan olingan ma'lumotni shu hujjatning [R..] tegi bilan keltir (modda raqamini \
sahifada ko'rgan bo'lsang ayt). Sahifa ochilmasa yoki matni bo'lmasa — hujjat nomini [R..] bilan \
ayt, mazmunini o'ylab topma va Lex.uz da o'qishni tavsiya qil.
6. Foydalanuvchi qaysi tilda yozsa (o'zbek yoki rus), o'sha tilda javob ber.
7. Javob qisqa va amaliy: 3–8 gap yoki qisqa ro'yxat; Telegram uchun oddiy matn, jadvalsiz.
8. Oxirida bir qatorda: bu yuridik maslahat emas, muhim qarorlar uchun mutaxassisga murojaat qiling.
9. Qonunchilik va biznesga aloqasi bo'lmagan savollarga bir gap bilan javob berib, mavzuga qaytar.
10. [P..] — muhokamadagi NPA LOYIHALARI: ular HALI QABUL QILINMAGAN. Ulardan foydalansang, albatta \
«loyiha, hali kuchga kirmagan» deb ayt, muhokama tugash sanasini va portalda taklif berish \
mumkinligini eslat. Loyihani amaldagi norma sifatida taqdim etma."""


class AIError(Exception):
    """code: busy | connect | empty | notfound | other — bot uni foydalanuvchi tiliga tarjima qiladi."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


# ---------------- suhbat tarixi va limitlar ----------------
_history: dict[int, deque] = defaultdict(lambda: deque(maxlen=MAX_HISTORY))
_last_call: dict[int, float] = {}
_daily: dict[int, tuple[str, int]] = {}


def reset(user_id: int):
    _history.pop(user_id, None)


def check_limits(user_id: int, is_admin: bool = False) -> str | None:
    """Limit oshgan bo'lsa — 'cooldown' / 'daily', aks holda None."""
    now = time.time()
    if now - _last_call.get(user_id, 0) < COOLDOWN_S:
        return "cooldown"
    if not is_admin:
        today = time.strftime("%Y-%m-%d")
        day, n = _daily.get(user_id, (today, 0))
        if day != today:
            n = 0
        if n >= DAILY_LIMIT:
            return "daily"
        _daily[user_id] = (today, n + 1)
    _last_call[user_id] = now
    return None


def is_configured() -> bool:
    return bool(GEMINI_API_KEY)


def model_name() -> str:
    return active_model or GEMINI_MODEL or "auto"


# ---------------- modelni tanlash ----------------
def _version(name: str) -> float:
    m = re.search(r"gemini-(\d+(?:\.\d+)?)", name)
    return float(m.group(1)) if m else 0.0


async def list_models() -> list[str]:
    """API dagi matn uchun barqaror Gemini Flash modellari: yangisi birinchi, Lite oxirida.
    Natija 6 soat keshlanadi."""
    global _models_cache
    if time.time() - _models_cache[0] < 6 * 3600 and _models_cache[1]:
        return _models_cache[1]
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as s:
            async with s.get(f"{API_BASE}/models?pageSize=1000",
                             headers={"x-goog-api-key": GEMINI_API_KEY}) as r:
                data = await r.json(content_type=None)
    except (aiohttp.ClientError, TimeoutError):
        return []
    names = []
    for m in (data or {}).get("models", []):
        n = m.get("name", "").split("/", 1)[-1]
        if (n.startswith("gemini-") and "flash" in n
                and "generateContent" in m.get("supportedGenerationMethods", [])
                and not any(w in n for w in SKIP_WORDS)
                and not re.search(r"-\d{3}$|-\d{2}-\d{4}$", n)):   # sanali nusxalar emas
            names.append(n)
    names.sort(key=lambda n: ("lite" in n, -_version(n), len(n)))
    _models_cache = (time.time(), names)
    return names


async def _candidates() -> list[str]:
    out: list[str] = []
    for m in ([active_model, GEMINI_MODEL] + await list_models() + FALLBACK_MODELS):
        if m and m not in out and _cooldown_until.get(m, 0) < time.time():
            out.append(m)
    return out


# ---------------- asosiy funksiya ----------------
async def ask(user_id: int, question: str, context: str, lang: str = "uz",
              urls: list[str] | None = None, meta: dict | None = None) -> str:
    """urls — Gemini o'zi ochib o'qiydigan Lex.uz sahifalari (URL context).
    meta ga {'model', 'read': [{'url', 'status'}]} yoziladi."""
    question = question.strip()[:MAX_MESSAGE_CHARS]
    hist = _history[user_id]
    lang_note = ("Foydalanuvchi interfeysi: RUS tili. Savol qaysi tilda bo'lsa, o'sha tilda javob ber "
                 "(odatda rus tilida)." if lang == "ru" else
                 "Foydalanuvchi interfeysi: O'ZBEK tili. Savol qaysi tilda bo'lsa, o'sha tilda javob ber.")
    system = (f"{SYSTEM_PROMPT}\n{lang_note}\n\n"
              f"KONTEKST:\n{context or '(bazada mos ma`lumot yo`q)'}")
    urls = (urls or [])[:MAX_URLS] if READ_URLS else []
    answer = (await _generate(system, list(hist), question, urls, meta)).strip()
    if not answer:
        raise AIError("empty")
    hist.append(("user", question))
    hist.append(("assistant", answer))
    return answer


async def _post_json(url: str, payload: dict, headers: dict | None = None) -> dict:
    timeout = aiohttp.ClientTimeout(total=TIMEOUT_S)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as s:
            async with s.post(url, json=payload, headers=headers or {}) as r:
                data = await r.json(content_type=None)
                if r.status in (429, 503):
                    raise AIError("busy", f"HTTP {r.status}")
                if r.status == 404:
                    raise AIError("notfound", f"HTTP 404 {url.split('/models/')[-1]}")
                if r.status >= 400:
                    msg = (data.get("error") or {}).get("message") if isinstance(data, dict) else None
                    raise AIError("other", f"HTTP {r.status} {msg or ''}".strip())
                return data
    except AIError:
        raise
    except (aiohttp.ClientError, TimeoutError) as e:
        raise AIError("connect", str(e)) from e


def _url_meta(data: dict) -> list[dict]:
    cand = ((data or {}).get("candidates") or [{}])[0] or {}
    m = cand.get("urlContextMetadata") or cand.get("url_context_metadata") or {}
    items = m.get("urlMetadata") or m.get("url_metadata") or []
    return [{"url": i.get("retrievedUrl") or i.get("retrieved_url"),
             "status": (i.get("urlRetrievalStatus") or i.get("url_retrieval_status") or "")
             .replace("URL_RETRIEVAL_STATUS_", "")} for i in items]


def _extract_text(data: dict) -> str:
    """Javob matni; «fikrlash» (thought) qismlari olib tashlanadi."""
    try:
        parts = data["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError, TypeError):
        reason = None
        if isinstance(data, dict):
            reason = ((data.get("promptFeedback") or {}).get("blockReason")
                      or ((data.get("candidates") or [{}])[0] or {}).get("finishReason"))
        raise AIError("empty", reason or "")
    text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
    return re.sub(r"(?s)<(think|thought)>.*?</\1>", "", text).strip()


async def _generate(system: str, hist: list, question: str, urls: list[str] | None = None,
                    meta: dict | None = None) -> str:
    global active_model
    contents = [{"role": "user" if role == "user" else "model", "parts": [{"text": text}]}
                for role, text in hist]
    q = question
    if urls:
        q += ("\n\n[Ushbu Lex.uz sahifalarini o'qib, javobda foydalan / "
              "Прочитай эти страницы Lex.uz:]\n" + "\n".join(urls))
    contents.append({"role": "user", "parts": [{"text": q}]})
    last_err: AIError | None = None
    for model in await _candidates():
        payload = {"systemInstruction": {"parts": [{"text": system}]},
                   "contents": contents,
                   "generationConfig": {"temperature": 0.3, "maxOutputTokens": MAX_OUTPUT_TOKENS}}
        use_tool = bool(urls) and model not in _no_url_tool
        if use_tool:
            payload["tools"] = [{"url_context": {}}]
        try:
            data = await _post_json(f"{API_BASE}/models/{model}:generateContent", payload,
                                    headers={"x-goog-api-key": GEMINI_API_KEY})
        except AIError as e:
            last_err = e
            if e.code == "other" and use_tool and "HTTP 400" in e.detail:
                # model URL context ni qo'llamaydi — vositasiz qayta urinamiz
                _no_url_tool.add(model)
                payload.pop("tools", None)
                try:
                    data = await _post_json(f"{API_BASE}/models/{model}:generateContent", payload,
                                            headers={"x-goog-api-key": GEMINI_API_KEY})
                except AIError as e2:
                    last_err = e2
                    continue
            elif e.code == "notfound":
                continue
            elif e.code == "busy":
                _cooldown_until[model] = time.time() + 600
                if active_model == model:
                    active_model = None
                continue
            else:
                raise
        active_model = model
        if meta is not None:
            meta["model"] = model
            meta["read"] = _url_meta(data)
        return _extract_text(data)
    raise last_err or AIError("other", "Gemini modeli topilmadi")


async def pick_acts(question: str, register: list[str], k: int = 3) -> list[str]:
    """Nomi bo'yicha mos akt topilmasa — Gemini reestrdan eng mos aktlarni tanlaydi.
    register: ["R1 | nomi | mavzu", ...]. Qaytaradi: ["R4", "R12"]."""
    prompt = ("Savolga javob berish uchun quyidagi reestrdan eng mos (ko'pi bilan "
              f"{k} ta) hujjatni tanla. Faqat teglarni vergul bilan yoz (masalan: R4, R12). "
              "Mos hujjat bo'lmasa: NONE.\n\nSAVOL: " + question + "\n\nREESTR:\n" + "\n".join(register))
    for model in await _candidates():
        try:
            data = await _post_json(
                f"{API_BASE}/models/{model}:generateContent",
                {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
                 "generationConfig": {"temperature": 0, "maxOutputTokens": 1024}},
                headers={"x-goog-api-key": GEMINI_API_KEY})
        except AIError as e:
            if e.code in ("notfound", "busy"):
                continue
            return []
        return re.findall(r"R\d+", _extract_text(data))[:k]
    return []
