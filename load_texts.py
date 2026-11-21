"""
162 ta akt matnini Lex.uz dan yuklab, moddalarga ajratib, bot bazasiga yozadi.
O'Z KOMPYUTERINGIZDA ishga tushiring (Lex.uz ochiladigan joyda).

  pip install -r requirements.txt beautifulsoup4 requests
  python load_texts.py --limit 3          # sinov: 3 ta akt
  python load_texts.py                    # hammasi (uz + ru), ~20 daqiqa
  python load_texts.py --offline          # qayta yuklamasdan, saqlangan HTML'dan

.env faylida DATABASE_URL — Render'dagi bilan bir xil Postgres bo'lishi kerak!
Natija: lex_cache/*.html va lex_cache/report.csv
"""
import argparse
import asyncio
import csv
import os
import time

from dotenv import load_dotenv

load_dotenv()

import db  # noqa: E402
import legal  # noqa: E402

CACHE = "lex_cache"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")


def download(lex_id: str, lang: str, delay: float, offline: bool) -> tuple[str | None, str]:
    path = os.path.join(CACHE, f"{lex_id}_{lang}.html")
    if os.path.exists(path) and (offline or os.path.getsize(path) > 5000):
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read(), "cache"
    if offline:
        return None, "no cache"
    import requests
    url = f"https://lex.uz/{lang}/docs/-{lex_id}"
    try:
        r = requests.get(url, headers={"User-Agent": UA, "Accept-Language": lang},
                         timeout=60)
        time.sleep(delay)
        if r.status_code != 200:
            return None, f"HTTP {r.status_code}"
        r.encoding = r.apparent_encoding or "utf-8"
        with open(path, "w", encoding="utf-8") as f:
            f.write(r.text)
        return r.text, "downloaded"
    except Exception as e:  # noqa: BLE001
        time.sleep(delay)
        return None, f"error: {e}"


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="faqat N ta akt (sinov uchun)")
    ap.add_argument("--only", default="", help="vergul bilan lex_id lar")
    ap.add_argument("--lang", default="uz,ru", help="uz, ru yoki uz,ru")
    ap.add_argument("--delay", type=float, default=3.0, help="so'rovlar orasidagi pauza (s)")
    ap.add_argument("--offline", action="store_true", help="faqat lex_cache dan")
    ap.add_argument("--dry-run", action="store_true", help="bazaga yozmasdan, faqat tahlil")
    args = ap.parse_args()

    os.makedirs(CACHE, exist_ok=True)
    acts = legal.load_acts_csv()
    if args.only:
        wanted = set(args.only.split(","))
        acts = [a for a in acts if a["lex_id"] in wanted]
    if args.limit:
        acts = acts[:args.limit]
    langs = [x.strip() for x in args.lang.split(",") if x.strip()]

    if not args.dry_run:
        if not db.USE_PG:
            print("⚠️  DATABASE_URL topilmadi — matnlar LOKAL SQLite (monita.db) ga yoziladi,\n"
                  "    Render'dagi bot ularni ko'rmaydi. .env ga DATABASE_URL qo'shing.\n")
        await db.init()

    report = []
    total = len(acts) * len(langs)
    i = 0
    for a in acts:
        for lang in langs:
            i += 1
            html, status = download(a["lex_id"], lang, args.delay, args.offline)
            row = {"lex_id": a["lex_id"], "lang": lang, "title": a["title"][:80],
                   "status": status, "chunks": 0, "articles": 0, "chars": 0}
            if html:
                chunks = legal.parse_act(html, lang)
                row["chunks"] = len(chunks)
                row["articles"] = sum(1 for c in chunks if "modda" in c["path"]
                                      or "Статья" in c["path"])
                row["chars"] = sum(len(c["content"]) for c in chunks)
                if not chunks:
                    row["status"] += " / matn topilmadi"
                elif not args.dry_run:
                    await db.replace_chunks(a["lex_id"], lang, chunks)
            report.append(row)
            print(f"[{i}/{total}] {a['lex_id']} {lang}: {row['status']}, "
                  f"{row['chunks']} bo'lak, {row['articles']} modda, {row['chars']} belgi")

    with open(os.path.join(CACHE, "report.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(report[0].keys()) if report else ["lex_id"])
        w.writeheader()
        w.writerows(report)

    ok = sum(1 for r in report if r["chunks"])
    print(f"\nTayyor: {ok}/{len(report)} ta hujjat matni olindi. Hisobot: {CACHE}/report.csv")
    if not args.dry_run:
        print("Bazada:", await db.chunk_stats())
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
