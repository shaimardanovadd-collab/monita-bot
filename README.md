# Monita Bot — biznes uchun qonunchilik monitoringi

Telegram bot (Python, aiogram 3, SQLite).

## Imkoniyatlar
**Foydalanuvchi uchun**
- `/start` — salomlashish va asosiy menyu
- 👤 Profilni sozlash — bir nechta faoliyat turini tanlash (✅ belgisi bilan)
- 🔔 Xabarnomalarni yoqish/o'chirish
- 📰 So'nggi yangiliklar — tanlangan sohalar bo'yicha oxirgi 5 ta o'zgarish
- 📅 Muhim muddatlar — kelgusi hisobot/litsenziya muddatlari
- ❓ Savol yoki taklif — xabar adminlarga yuboriladi
- ℹ️ Bot haqida
- 🤖 Savol bering (AI) — Gemma modeli bot bazasidagi yangilik va muddatlarga tayanib javob beradi (o'zbek/rus)

Har bir yangilik kartochkasi: **Soha / Nima o'zgardi? / Qachondan? / Manba** va
"Batafsil ma'lumot", "Muhim muddatlar" tugmalari.

**Admin uchun** (`ADMIN_IDS` dagi foydalanuvchilar, `/admin` — yordam)
- `/yangilik` — 6 qadamli forma → ko'rib chiqish → mos sohadagi obunachilarga yuborish
- `/muddat` — muddat qo'shish; 7, 3, 1 kun qolganda va o'sha kuni avtomatik eslatma
- `/muddatlar`, `/muddat_ochir ID`
- `/javob USER_ID matn` — murojaatga javob
- `/stat` — statistika

## O'rnatish (lokal)
```bash
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # BOT_TOKEN va ADMIN_IDS ni to'ldiring
python bot.py
```

## Render'da BEPUL joylashtirish ($0)
Render'da Background Worker bepul emas, shuning uchun bot **Web Service (Free)** + webhook
rejimida ishlaydi. Ma'lumotlar bepul Postgres'da saqlanadi.

1. **Bepul Postgres oling** — Neon (neon.tech) yoki Supabase. Ulanish satrini
   (`postgresql://...`) nusxalang. Render'ning bepul Postgres'i 30 kundan keyin o'chadi — ishlatmang.
2. Render → **New → Web Service** → repozitoriy → Instance type: **Free**
   - Build: `pip install -r requirements.txt`
   - Start: `python bot.py`
3. Environment Variables:
   - `BOT_TOKEN` — @BotFather tokeni
   - `ADMIN_IDS` — sizning Telegram ID
   - `DATABASE_URL` — 1-qadamdagi Postgres satri
   - `WEBHOOK_SECRET` — istalgan uzun tasodifiy so'z (faqat harf/raqam)
   - `TZ` = `Asia/Tashkent`
   - `GEMINI_API_KEY` — aistudio.google.com/apikey dan bepul kalit (AI yordamchi uchun)
   (`RENDER_EXTERNAL_URL` ni Render o'zi beradi — webhook avtomatik o'rnatiladi.)
4. **Uxlab qolmasligi uchun**: cron-job.org (bepul) da har 10 daqiqaga vazifa yarating:
   `https://<servis-nomi>.onrender.com/tick?key=<WEBHOOK_SECRET>`
   Bu serverni uyg'oq ushlaydi va muddat eslatmalarini o'z vaqtida yuboradi.
   (Bitta servis 24/7 ishlashi oyiga ~744 soat — bepul 750 soat limitiga sig'adi.)

Lokal sinash: `DATABASE_URL` va `RENDER_EXTERNAL_URL` bo'lmasa, bot SQLite + polling rejimida ishlaydi.

## Qonunlar bazasi (162 ta amaldagi akt)
- `data/acts.csv` — reestr (QonunRadar Excel, 20.11.2026 holati): nomi, OKED bo'limlari,
  mavzu, turi, rekvizitlari, kuchga kirgan sanasi, Lex.uz havolasi. Bot ishga tushganda
  avtomatik bazaga yoziladi. Reestr Lex.uz bilan mustaqil tekshirilmagan.
- Matnlarni yuklash — **1-usul (oson)**: botga admin sifatida `/yuklash 3` (sinov), so'ng
  `/yuklash` (hammasi, ~20 daqiqa). Server o'zi Lex.uz dan yuklab, bulutdagi bazaga yozadi.
- **2-usul** (agar Render'dan Lex.uz ochilmasa — bot shuni yozadi): o'z kompyuteringizda:
  1. Papkada `.env` yarating, unga Render'dagi bilan **bir xil** `DATABASE_URL` yozing.
  2. Sinov: `START_LOAD_TEXTS.bat --limit 3` (yoki `python load_texts.py --limit 3`).
  3. Hammasi: `START_LOAD_TEXTS.bat` — 162 akt x 2 til, 3 soniya pauza bilan ~20 daqiqa.
  4. `lex_cache/report.csv` da har bir hujjat bo'yicha nechta modda olinganini tekshiring.
     Botda admin uchun: `/qonunlar`.
- Qayta ishga tushirish xavfsiz: har bir akt matni almashtiriladi, takrorlanmaydi.
- Sohalar -> OKED: savdo=G; import=G,H; ovqatlanish=I; xizmat=M,N,S,J,K,P,Q,R;
  ishlab chiqarish=C,A,D,E; qurilish=F,L; boshqa=hammasi. "ОБЩИЕ" aktlar hammaga.
- AI savol berilganda: foydalanuvchi sohasidagi aktlar ichidan eng mos 6 ta modda topiladi
  va Gemma'ga manba (akt, modda, havola) bilan beriladi.

## Fayllar
- `bot.py` — barcha handlerlar, admin formalar, eslatmalar
- `db.py` — SQLite jadvallari va so'rovlar
- `ai.py` — Gemma (Google AI Studio yoki Ollama)
- `legal.py` — reestr, OKED, Lex.uz sahifasini moddalarga ajratish
- `load_texts.py` — matnlarni yuklovchi skript
- `data/acts.csv` — 162 akt reestri
- `texts.py` — barcha matnlar va sohalar ro'yxati (yangi soha qo'shish uchun `SECTORS` ni tahrirlang)

## AI yordamchi (Gemma)
- Standart: Google AI Studio orqali `gemma-3-27b-it` (bepul). Faqat `GEMINI_API_KEY` kerak.
- Mahalliy Ollama bilan ishlatish: `AI_PROVIDER=ollama`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL`.
- Cheklovlar (local-gemma-chat dagi kabi): suhbatda 8 ta oxirgi xabar, savol 3000 belgigacha,
  so'rovlar orasida 5 soniya, kuniga `AI_DAILY_LIMIT` ta savol.
- Model bot bazasidagi yangiliklar va muddatlarni kontekst sifatida oladi — shuning uchun
  `/yangilik` orqali qancha ko'p ma'lumot kiritsangiz, javoblar shuncha aniq bo'ladi.
- Bepul Google API'da so'rovlar Google tomonidan modelni o'qitish uchun ishlatilishi mumkin —
  foydalanuvchilarga shaxsiy ma'lumot yozmaslikni tavsiya qiling.
