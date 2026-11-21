"""
Qonun hujjatlari bilan ishlash: reestr (data/acts.csv), sohalar -> OKED,
Lex.uz sahifasini moddalarga ajratish va qidiruv uchun matnni normallashtirish.
"""
import csv
import os
import re

ACTS_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "acts.csv")

import oked  # noqa: E402

SECTOR_OKED = oked.LEGACY  # eski nom (moslik uchun)


def oked_for_sectors(codes: list[str]) -> set[str]:
    """Foydalanuvchi kodlari (bo'lim/bo'linma/eski kalit) -> akt filtri uchun aniq kodlar + ALL."""
    return set(oked.normalize(codes)) | {"ALL"}


def load_acts_csv(path: str = ACTS_CSV) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ---------------- qidiruv uchun normallashtirish ----------------
_APOS = re.compile(r"[ʻʼ‘’`'´ʹ]")
STOP = set("""
va bilan uchun ham yoki lekin agar qanday qaysi nima nimа kim qachon qayerda nega
bu shu u ular biz siz men mening bizning sizning bor yo'q yoq kerak mumkin emas
haqida bo'yicha boyicha bo'lsa bolsa bo'ladi boladi qilish qilinadi edi ekan
и в во на с со по к ко о об от до за из у для что как какой какие каким когда где
это этот эта эти тот та те же ли бы не нет да или но а если то мне нам вам меня
можно нужно надо есть был была были будет буду при про под над через
""".split())


def normalize(text: str) -> str:
    return _APOS.sub("", (text or "").lower())


def query_terms(question: str, max_terms: int = 12) -> list[str]:
    """Savoldan qidiruv so'zlari: 3+ harf, stop-so'zlarsiz, 6 harfgacha qisqartirilgan
    (o'zbek/rus qo'shimchalari uchun: 'litsenziyalar' -> 'litsen')."""
    seen, out = set(), []
    for w in re.findall(r"\w+", normalize(question)):
        if len(w) < 3 or w in STOP or w.isdigit():
            continue
        t = w[:6]
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out[:max_terms]


# ---------------- Lex.uz sahifasini ajratish ----------------
_UZ_ART = re.compile(r"^\s*(\d+)\s*(?:[\^]?\s*(\d+))?\s*-\s*modda\.?\s*(.*)$", re.I)
_RU_ART = re.compile(r"^\s*Статья\s+(\d+)\s*(?:[\^]?\s*(\d+))?\s*\.?\s*(.*)$")
_CHAPTER = re.compile(r"^\s*(?:[IVXLC]+\.|\d+-bob|Глава\s+\d+)\s", re.I)
_NOISE = ("LexUZ sharhi", "Комментарий LexUZ", "ONLINE TRANSLATE", "Oldingi tahrir",
          "Keyingi tahrir", "Предыдущая редакция", "Следующая редакция")

MAX_CHUNK = 1500


def html_to_lines(html: str) -> list[str]:
    from bs4 import BeautifulSoup  # faqat load_texts.py uchun kerak
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "form"]):
        tag.decompose()
    root = (soup.find(id="divCont") or soup.find(class_="docBody")
            or soup.find("article") or soup.body or soup)
    for sup in root.find_all("sup"):          # 39<sup>1</sup>-modda -> 39^1-modda
        sup.replace_with(f"^{sup.get_text(strip=True)}")
    for br in root.find_all("br"):
        br.replace_with("\n")
    for tag in root.find_all(["p", "div", "li", "tr", "td", "h1", "h2", "h3", "h4",
                              "h5", "h6", "table", "section", "article", "blockquote"]):
        tag.insert_before("\n")
        tag.insert_after("\n")
    lines = []
    for ln in root.get_text("").split("\n"):
        ln = re.sub(r"\s+", " ", ln).strip()
        if ln and not any(n in ln for n in _NOISE):
            lines.append(ln)
    return lines


def _split_long(path: str, heading: str, body: str) -> list[dict]:
    out, part = [], 1
    while body:
        if len(body) <= MAX_CHUNK:
            piece, body = body, ""
        else:
            cut = body.rfind("\n", 0, MAX_CHUNK)
            cut = cut if cut > MAX_CHUNK // 2 else MAX_CHUNK
            piece, body = body[:cut], body[cut:].lstrip()
        p = path if part == 1 else f"{path} (davomi {part})"
        out.append({"path": p, "heading": heading, "content": piece.strip()})
        part += 1
    return out


def parse_act(html: str, lang: str = "uz") -> list[dict]:
    """HTML -> [{'path': '5-modda', 'heading': '...', 'content': '...'}].
    Moddali hujjat (qonun, kodeks) — moddalar bo'yicha; aks holda (qaror, farmon) —
    ~1500 belgilik bo'laklar."""
    lines = html_to_lines(html)
    rx = _RU_ART if lang == "ru" else _UZ_ART
    word = "Статья" if lang == "ru" else "modda"

    # 1) moddalar
    segments: dict[str, dict] = {}
    cur = None
    for ln in lines:
        m = rx.match(ln)
        if m and len(ln) < 300:
            num = m.group(1) + (f"^{m.group(2)}" if m.group(2) else "")
            cur = {"num": num, "title": m.group(3).strip(" ."), "body": []}
            prev = segments.get(num)
            # mundarijadagi (bo'sh) nusxa o'rniga — matnli nusxa saqlanadi
            if prev is None or len(" ".join(prev["body"])) < 40:
                segments[num] = cur
            continue
        if cur is not None and not _CHAPTER.match(ln):
            if not cur["title"] and not cur["body"] and len(ln) < 200:
                cur["title"] = ln
            else:
                cur["body"].append(ln)
    articles = [s for s in segments.values() if len(" ".join(s["body"])) >= 40]
    if len(articles) >= 3:
        chunks = []
        for s in articles:
            path = (f"Статья {s['num']}" if lang == "ru" else f"{s['num']}-{word}")
            chunks += _split_long(path, s["title"], "\n".join(s["body"])[:8000])
        return chunks

    # 2) moddasiz hujjat: asosiy matn — birinchi uzun xatboshidan boshlab
    start = next((i for i, ln in enumerate(lines) if len(ln) > 150), None)
    if start is None:
        return []
    start = max(0, start - 3)
    last = max(i for i, ln in enumerate(lines) if len(ln) > 150)
    body_lines = lines[start:last + 6]
    label = "qism" if lang != "ru" else "часть"

    def make(buf: list[str], n: int) -> dict:
        pt = next((m for m in (re.match(r"^(\d+)\.\s", x) for x in buf) if m), None)
        if pt:
            path = f"п. {pt.group(1)}" if lang == "ru" else f"{pt.group(1)}-band"
        else:
            path = f"{n}-{label}"
        return {"path": path, "heading": "", "content": "\n".join(buf)}

    chunks, buf = [], []
    for ln in body_lines:
        if buf and sum(len(x) for x in buf) + len(ln) > MAX_CHUNK:
            chunks.append(make(buf, len(chunks) + 1))
            buf = []
        buf.append(ln)
    if buf:
        chunks.append(make(buf, len(chunks) + 1))
    return chunks
