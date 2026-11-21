"""
NPA loyihalari — regulation.adliya.uz (Normativ-huquqiy hujjatlar loyihalari muhokamasi portali).

Portalning ochiq API si (avtorizatsiyasiz):
  ro'yxat:  /api/api/aux-jk/v1/open/project?statuses=IN_DISCUSSION&page=0&size=50&...
  matn:     /api/api/aux-jk/v1/published/api/project/v1/item/field?projectItemId={projectTextId}
  sahifa:   /project/{projectId}/{id}
Har bir loyihada "projectPassportSpecialityId" — portal sohasi (34 ta); u OKED bo'limlariga
quyidagi jadval orqali bog'lanadi.
"""
import html
import os
import re

import aiohttp

REG_BASE = os.getenv("REG_BASE", "https://regulation.adliya.uz").rstrip("/")
LIST_PATH = "/api/api/aux-jk/v1/open/project"
FIELD_PATH = "/api/api/aux-jk/v1/published/api/project/v1/item/field"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")

# Portal sohalari (id -> uz, ru) — /api/api/project/v1/speciality dan
SPECIALITIES = {
    1: ("Konstitutsiyaviy tuzum", "Конституционный строй"),
    2: ("Atrof tabiiy muhit va tabiiy resurslar", "Окружающая среда и природные ресурсы"),
    3: ("Axborot va axborotlashtirish", "Информация и информатизация"),
    4: ("Bank faoliyati", "Банковская деятельность"),
    5: ("Davlat boshqaruv asoslari", "Основы государственного управления"),
    6: ("Fuqarolik qonunchiligi", "Гражданское законодательство"),
    7: ("Ijtimoiy ta'minot va sug'urta", "Социальное обеспечение и страхование"),
    8: ("Mehnat va bandlik", "Труд и занятость"),
    9: ("Mudofaa", "Оборона"),
    10: ("Odil sudlov", "Правосудие"),
    11: ("Prokuratura, advokatura, notariat", "Прокуратура, адвокатура, нотариат"),
    12: ("Oila qonunchiligi", "Семейное законодательство"),
    13: ("Sog'liqni saqlash, sport, turizm", "Здравоохранение, спорт, туризм"),
    14: ("Soliq qonunchiligi", "Налоговое законодательство"),
    15: ("Ta'lim, fan, madaniyat", "Образование, наука, культура"),
    16: ("Tadbirkorlik va xo'jalik faoliyati", "Предпринимательство и хозяйственная деятельность"),
    17: ("Tashqi iqtisodiy faoliyat, bojxona", "ВЭД, таможенное дело"),
    18: ("Uy-joy, kommunal xo'jalik", "Жилищное и коммунальное хозяйство"),
    19: ("Xalqaro munosabatlar", "Международные отношения"),
    20: ("Xavfsizlik va huquq-tartibot", "Безопасность и правопорядок"),
    21: ("Yer masalalari", "Земельные вопросы"),
    22: ("Strategik islohotlar", "Стратегические реформы"),
    23: ("Fermer, dehqon va tomorqa xo'jaliklari", "Фермерские и дехканские хозяйства"),
    24: ("Soliq maslahati", "Налоговое консультирование"),
    25: ("Advokatlik faoliyati", "Адвокатская деятельность"),
    26: ("Mahalliy davlat hokimiyati", "Местная власть"),
    27: ("Ta'lim sifati", "Качество образования"),
    28: ("Geologiya va mineral resurslar", "Геология и минеральные ресурсы"),
    29: ("Raqobatni rivojlantirish", "Развитие конкуренции"),
    30: ("Tadbirkorlik subyektlarining huquqlari", "Права субъектов предпринимательства"),
    31: ("Ijtimoiy himoya", "Социальная защита"),
    32: ("Davlat xizmatini rivojlantirish", "Развитие госслужбы"),
    33: ("Investitsiyalar va tashqi savdo", "Инвестиции и внешняя торговля"),
    34: ("Iqtisodiy va moliyaviy masalalar", "Экономические и финансовые вопросы"),
}

# Portal sohasi -> OKED bo'limlari. "ALL" — har qanday biznesga tegishli (soliq, mehnat,
# tadbirkorlik, raqobat...). Bo'sh — biznesga bevosita aloqasi yo'q (mudofaa, sud...).
SPECIALITY_OKED = {
    1: [], 2: ["A", "B", "C", "D", "E"], 3: ["J"], 4: ["K"], 5: [], 6: ["ALL"], 7: ["ALL"],
    8: ["ALL"], 9: [], 10: [], 11: ["M"], 12: [], 13: ["Q", "R", "I", "N"], 14: ["ALL"],
    15: ["P", "M", "R"], 16: ["ALL"], 17: ["G", "H", "C"], 18: ["L", "F", "D", "E"], 19: [],
    20: [], 21: ["A", "F", "L"], 22: ["ALL"], 23: ["A"], 24: ["M"], 25: ["M"], 26: [],
    27: ["85"], 28: ["B"], 29: ["ALL"], 30: ["ALL"], 31: ["Q"], 32: [], 33: ["G", "H", "C", "K", "F"],
    34: ["ALL"],
}


# Keng rubrikalar (masalan "Ta'lim, fan, madaniyat") nomidagi kalit so'zlar bo'yicha
# aniq OKED bo'linmalariga ajratiladi: maktab haqidagi loyiha teatrga, muzey haqidagisi
# o'quv markaziga yuborilmaydi. Hech narsa topilmasa — rubrika bo'yicha umumiy bog'lanish.
REFINE_SPECIALITIES = {2, 13, 15, 18, 21, 27, 33}
KEYWORDS = [  # (bo'linmalar, kalit so'z o'zaklari — lotin/kirill, kichik harf, apostrofsiz)
    (["94"], ["diniy", "umra", "masjid", "религ", "умра", "хадж", "мечет"]),
    (["85"], ["talim", "maktab", "oquv", "oqituv", "oquvchi", "talaba", "universitet",
              "litsey", "kollej", "texnikum", "bogcha", "abituriyent", "образова", "школ", "учеб",
              "учащ", "студент", "вуз", "университет", "лицей", "колледж", "детск сад", "абитуриент"]),
    (["72"], ["ilmiy", "ilm-fan", "fanlar akademiya", "innovatsi", "научн", "наук", "инновац"]),
    (["90", "91"], ["madaniyat", "muzey", "teatr", "kutubxona", "sanat", "meros", "культур",
                    "музе", "театр", "библиотек", "искусств", "наследи"]),
    (["93"], ["sport", "jismoniy tarbiya", "olimpiya", "спорт", "физическ"]),
    (["55", "79"], ["turizm", "turistik", "mehmonxona", "туризм", "туристск", "гостиниц"]),
    (["86", "21"], ["tibbiy", "tibbiyot", "sogliq", "shifoxona", "farmatsevt", "dori", "медицин",
                    "здравоохр", "больниц", "фармацевт", "лекарств"]),
]


def refine_oked(sid: int | None, text: str) -> list[str]:
    base = oked_of(sid)
    if sid not in REFINE_SPECIALITIES:
        return base
    hay = re.sub(r"[ʻʼ‘’`'´]", "", (text or "").lower()) + " "
    for divs, words in KEYWORDS:
        if any(w in hay for w in words):
            return divs  # birinchi mos guruh (diniy ta'lim -> 94, ta'limga emas)
    return base


def speciality_name(sid: int | None, lang: str = "uz") -> str:
    uz, ru = SPECIALITIES.get(sid or 0, ("—", "—"))
    return ru if lang == "ru" else uz


def oked_of(sid: int | None) -> list[str]:
    return SPECIALITY_OKED.get(sid or 0, [])


def page_url(d: dict) -> str:
    return f"{REG_BASE}/project/{d['project_id']}/{d['id']}"


def _norm(p: dict) -> dict:
    """API elementi -> bot bazasi qatori."""
    sid = p.get("projectPassportSpecialityId")
    name_uz = (p.get("projectNameUz") or "").strip()
    name_ru = (p.get("projectNameRu") or "").strip()
    return {
        "id": int(p["id"]), "project_id": int(p["projectId"]),
        "text_id": int(p["projectTextId"]) if p.get("projectTextId") else None,
        "speciality": sid,
        "oked": ",".join(refine_oked(sid, f"{name_uz} {name_ru}")),
        "name_uz": re.sub(r"\s+", " ", name_uz), "name_ru": re.sub(r"\s+", " ", name_ru or name_uz),
        "org_uz": (p.get("projectOrganizationNameUz") or "").strip(),
        "org_ru": (p.get("projectOrganizationNameRu") or p.get("projectOrganizationNameUz") or "").strip(),
        "start_date": (p.get("startDate") or "")[:10], "end_date": (p.get("endDate") or "")[:10],
        "status": p.get("status") or "", "views": p.get("views") or 0,
        "suggestions": p.get("totalSuggestionsCount") or 0,
    }


async def fetch_in_discussion(max_pages: int = 10) -> list[dict]:
    """Muhokamadagi barcha loyihalar (barcha sohalar)."""
    out: list[dict] = []
    timeout = aiohttp.ClientTimeout(total=60)
    async with aiohttp.ClientSession(timeout=timeout, headers={"User-Agent": UA}) as s:
        for page in range(max_pages):
            params = {"statuses": "IN_DISCUSSION", "search": "", "orderBy": "createdDate",
                      "page": page, "size": 50, "sortOrder": "desc"}
            async with s.get(REG_BASE + LIST_PATH, params=params) as r:
                if r.status != 200:
                    raise RuntimeError(f"regulation.adliya.uz HTTP {r.status}")
                data = (await r.json(content_type=None)).get("data") or {}
            out += [_norm(p) for p in data.get("content") or [] if p.get("id") and p.get("projectId")]
            if data.get("last", True):
                break
    return out


def _flatten(fields) -> list[dict]:
    res = []
    for f in fields or []:
        res.append(f)
        res += _flatten(f.get("children"))
    return res


def html_to_text(s: str) -> str:
    s = re.sub(r"<\s*(br|/p|/li|/tr|/h\d)\s*/?>", "\n", s or "", flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s).replace("\xa0", " ")
    return "\n".join(re.sub(r"[ \t]+", " ", ln).strip() for ln in s.split("\n") if ln.strip())


async def fetch_text(text_id: int) -> str:
    """Loyiha matni (barcha bandlar, HTML siz)."""
    timeout = aiohttp.ClientTimeout(total=60)
    async with aiohttp.ClientSession(timeout=timeout, headers={"User-Agent": UA}) as s:
        async with s.get(REG_BASE + FIELD_PATH, params={"projectItemId": text_id}) as r:
            if r.status != 200:
                raise RuntimeError(f"HTTP {r.status}")
            data = await r.json(content_type=None)
    inner = (data.get("data") or {})
    fields = inner.get("data") if isinstance(inner, dict) else inner
    parts = [html_to_text(f.get("content") or f.get("contentUz") or f.get("contentRu") or "")
             for f in _flatten(fields)]
    return "\n".join(p for p in parts if p)
