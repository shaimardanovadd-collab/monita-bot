"""
Gemma bilan ishlash (savol-javob rejimi).

Ikki variant (AI_PROVIDER):
- "google" (standart) — Google AI Studio orqali Gemma, bepul. GEMINI_API_KEY kerak.
- "ollama"            — mahalliy Ollama (local-gemma-chat dagi kabi). OLLAMA_BASE_URL kerak.
"""
import os
import time
from collections import defaultdict, deque

import aiohttp

AI_PROVIDER = os.getenv("AI_PROVIDER", "google").lower()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMMA_MODEL = os.getenv("GEMMA_MODEL", "gemma-3-27b-it")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:12b")

# local-gemma-chat dagi cheklovlar
MAX_HISTORY = 8              # suhbatda oxirgi 8 ta xabar
MAX_MESSAGE_CHARS = 3000     # bitta savol uzunligi
MAX_OUTPUT_TOKENS = 1024
TIMEOUT_S = 120
COOLDOWN_S = 5               # bir foydalanuvchi uchun so'rovlar orasidagi pauza
DAILY_LIMIT = int(os.getenv("AI_DAILY_LIMIT", "30"))

SYSTEM_PROMPT = """Sen "Monita Bot"ning yordamchisisan — O'zbekistondagi tadbirkorlarga \
qonunchilikdagi o'zgarishlar bo'yicha qisqa va aniq tushuntirish berasan.

Qoidalar:
1. Foydalanuvchi qaysi tilda yozsa (o'zbek yoki rus), o'sha tilda javob ber.
2. Avvalo quyidagi KONTEKST ga tayan: qonun matnidan parchalar (Lex.uz), amaldagi \
hujjatlar reestri, bot yangiliklari va muddatlar. Javobda aniq manbani ko'rsat: \
hujjat nomi, modda/band va havola. Kontekstda bo'lmagan modda raqamini aytma.
3. Kontekstda javob bo'lmasa, buni ochiq ayt. Umumiy bilimingdan javob bersang, \
"umumiy ma'lumot, tekshirish kerak" deb belgila.
4. Hech qachon modda raqamlari, hujjat raqamlari, sanalar, stavkalar yoki jarimalarni \
o'ylab topma. Bilmasang — "aniq ma'lumot yo'q, Lex.uz da tekshiring" de.
5. Javob qisqa bo'lsin: 3–8 gap yoki qisqa ro'yxat. Telegram uchun oddiy matn, \
markdown jadvallarsiz.
6. Sen yuridik maslahatchi emassan. Muhim qarorlar uchun yurist yoki buxgalter bilan \
maslahatlashishni tavsiya qil.
7. Qonunchilik va biznesga aloqasi bo'lmagan savollarga qisqa javob berib, \
botning mavzusiga qaytar."""


class AIError(Exception):
    """code: busy | connect | empty | other — bot uni foydalanuvchi tiliga tarjima qiladi."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


# ---------------- suhbat tarixi va limitlar (xotirada) ----------------
_history: dict[int, deque] = defaultdict(lambda: deque(maxlen=MAX_HISTORY))
_last_call: dict[int, float] = {}
_daily: dict[int, tuple[str, int]] = {}


def reset(user_id: int):
    _history.pop(user_id, None)


def check_limits(user_id: int, is_admin: bool = False) -> str | None:
    """Limit oshgan bo'lsa — xato kodi ('cooldown' / 'daily'), aks holda None."""
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
    return AI_PROVIDER == "ollama" or bool(GEMINI_API_KEY)


# ---------------- asosiy funksiya ----------------
async def ask(user_id: int, question: str, context: str, lang: str = "uz") -> str:
    question = question.strip()[:MAX_MESSAGE_CHARS]
    hist = _history[user_id]
    lang_note = ("Foydalanuvchi interfeysi: RUS tili. Savol qaysi tilda bo'lsa, o'sha tilda javob ber "
                 "(odatda rus tilida)." if lang == "ru" else
                 "Foydalanuvchi interfeysi: O'ZBEK tili. Savol qaysi tilda bo'lsa, o'sha tilda javob ber.")
    system = (f"{SYSTEM_PROMPT}\n{lang_note}\n\n"
              f"KONTEKST:\n{context or '(bazada mos ma`lumot yo`q)'}")

    if AI_PROVIDER == "ollama":
        answer = await _ask_ollama(system, list(hist), question)
    else:
        answer = await _ask_google(system, list(hist), question)

    answer = (answer or "").strip()
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
                if r.status >= 400:
                    msg = (data.get("error") or {}).get("message") if isinstance(data, dict) else None
                    raise AIError("other", f"HTTP {r.status} {msg or ''}".strip())
                return data
    except AIError:
        raise
    except (aiohttp.ClientError, TimeoutError) as e:
        raise AIError("connect", str(e)) from e


async def _ask_google(system: str, hist: list, question: str) -> str:
    """Gemma'da alohida system instruction yo'q — uni birinchi user xabariga qo'shamiz."""
    contents = []
    first = True
    for role, text in hist + [("user", question)]:
        if role == "user" and first:
            text = f"{system}\n\n---\nSAVOL: {text}"
            first = False
        contents.append({"role": "user" if role == "user" else "model",
                         "parts": [{"text": text}]})
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{GEMMA_MODEL}:generateContent")
    data = await _post_json(
        url,
        {"contents": contents,
         "generationConfig": {"temperature": 0.3, "maxOutputTokens": MAX_OUTPUT_TOKENS}},
        headers={"x-goog-api-key": GEMINI_API_KEY},
    )
    try:
        parts = data["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts)
    except (KeyError, IndexError, TypeError):
        reason = (data.get("promptFeedback") or {}).get("blockReason") if isinstance(data, dict) else None
        raise AIError("empty", reason or "")


async def _ask_ollama(system: str, hist: list, question: str) -> str:
    messages = [{"role": "system", "content": system}]
    messages += [{"role": r, "content": t} for r, t in hist]
    messages.append({"role": "user", "content": question})
    data = await _post_json(
        f"{OLLAMA_BASE_URL}/api/chat",
        {"model": OLLAMA_MODEL, "messages": messages, "stream": False,
         "options": {"temperature": 0.3, "num_predict": MAX_OUTPUT_TOKENS}},
    )
    return (data.get("message") or {}).get("content", "")
