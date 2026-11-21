"""OKED (IFUT, 2-tahrir) — iqtisodiy faoliyat turlari: bo'limlar (A–U) va bo'linmalar (01–99).
Manba: Oʻzbekiston Respublikasi IFUT / ОКЭД ред. 2 (data/oked.json, uz lotin + ru).

Foydalanuvchi profili kodlar ro'yxati sifatida saqlanadi: bo'lim harfi ("G") va/yoki
bo'linma raqami ("47"). Qonun aktlari reestrda bo'lim darajasida belgilangan, shuning uchun
moslik bo'lim harfi bo'yicha aniqlanadi; bo'linma AI javobini aniqlashtiradi."""
import json
import os

_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "oked.json")
with open(_PATH, encoding="utf-8") as _f:
    _DATA = json.load(_f)

SECTIONS: dict = _DATA["sections"]      # {"G": {"emoji", "uz", "ru", "divisions": [...]}}
DIVISIONS: dict = _DATA["divisions"]    # {"47": {"s": "G", "uz", "ru"}}

# Biznes uchun tanlanadigan bo'limlar (davlat boshqaruvi, uy xo'jaliklari, xalqaro tashkilotlarsiz)
BUSINESS = [k for k in SECTIONS if k not in ("O", "T", "U")]

# Eski versiyadagi 7 ta soha -> OKED bo'limlari (eski foydalanuvchilar va yangiliklar uchun)
LEGACY = {
    "savdo": ["G"], "import": ["G", "H"], "ovqat": ["I"],
    "xizmat": ["M", "N", "S", "J", "K", "P", "Q", "R"], "ishlab": ["C", "A", "D", "E"],
    "qurilish": ["F", "L"], "boshqa": BUSINESS,
}


def normalize(codes) -> list[str]:
    """Eski kalitlarni OKED ga o'tkazadi, noto'g'ri kodlarni olib tashlaydi."""
    out: list[str] = []
    for c in codes or []:
        c = str(c).strip()
        for x in LEGACY.get(c, [c]):
            if (x in SECTIONS or x in DIVISIONS or x == "ALL") and x not in out:
                out.append(x)
    return out


def letters(codes) -> set[str]:
    """Kodlar -> bo'lim harflari (47 -> G)."""
    res = set()
    for c in normalize(codes):
        if c in DIVISIONS:
            res.add(DIVISIONS[c]["s"])
        elif c in SECTIONS or c == "ALL":
            res.add(c)
    return res


def sections_of(codes) -> list[str]:
    return [c for c in normalize(codes) if c in SECTIONS]


def divisions_of(codes) -> list[str]:
    return [c for c in normalize(codes) if c in DIVISIONS]


def section_label(letter: str, lang: str = "uz") -> str:
    s = SECTIONS[letter]
    return f"{s['emoji']} {s.get(lang) or s['uz']}"


def division_label(code: str, lang: str = "uz", width: int = 0) -> str:
    name = DIVISIONS[code].get(lang) or DIVISIONS[code]["uz"]
    if width and len(name) > width:
        name = name[:width - 1].rstrip(" ,") + "…"
    return f"{code} · {name}"


def describe(codes, lang: str = "uz") -> str:
    """Qisqa: «🏪 Ulgurji va chakana savdo (47), 💻 Axborot va aloqa (IT)»."""
    codes = normalize(codes)
    if "ALL" in codes:
        return "🌍 " + ("barcha faoliyat turlari" if lang == "uz" else "все виды деятельности")
    parts = []
    for sec in sorted(letters(codes)):
        if sec not in SECTIONS:
            continue
        divs = [d for d in divisions_of(codes) if DIVISIONS[d]["s"] == sec]
        parts.append(section_label(sec, lang) + (f" ({', '.join(divs)})" if divs else ""))
    return ", ".join(parts) or "—"


def describe_long(codes, lang: str = "uz") -> str:
    """Profil uchun: har bo'lim alohida qatorda, ostida tanlangan bo'linmalar."""
    codes = normalize(codes)
    lines = []
    for sec in sorted(letters(codes)):
        if sec not in SECTIONS:
            continue
        lines.append(f"   {section_label(sec, lang)}")
        for d in divisions_of(codes):
            if DIVISIONS[d]["s"] == sec:
                lines.append(f"      └ {division_label(d, lang, 60)}")
    return "\n".join(lines) or "   —"


def match(act_codes, user_codes) -> bool:
    """Akt kodlari foydalanuvchi faoliyatiga mosmi (2 xonali bo'linma darajasida aniq).
    Akt 'ALL' — barcha biznes uchun; 'BG' — fon (lentaga chiqmaydi).
    Akt bo'limga (C) belgilangan bo'lsa — bo'limdagi barcha bo'linmalarga tegishli;
    foydalanuvchi butun bo'limni (P) tanlagan bo'lsa — bo'lim ichidagi har qanday aktga mos."""
    a_set = {str(x).strip() for x in (act_codes or []) if str(x).strip()}
    if "ALL" in a_set:
        return True
    users = [u for u in normalize(user_codes) if u != "ALL"]
    for a in a_set:
        for u in users:
            if a == u:
                return True
            if a in SECTIONS and u in DIVISIONS and DIVISIONS[u]["s"] == a:
                return True
            if u in SECTIONS and a in DIVISIONS and DIVISIONS[a]["s"] == u:
                return True
    return False


def for_ai(codes) -> str:
    """Model uchun to'liq tavsif (ikki tilda — aniqroq javob uchun)."""
    codes = normalize(codes)
    out = []
    for sec in sorted(letters(codes)):
        if sec in SECTIONS:
            s = SECTIONS[sec]
            out.append(f"{sec} — {s['uz']} / {s['ru']}")
    for d in divisions_of(codes):
        out.append(f"{d} — {DIVISIONS[d]['uz']} / {DIVISIONS[d]['ru']}")
    return "; ".join(out) or "ko'rsatilmagan"
