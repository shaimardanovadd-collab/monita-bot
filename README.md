# Monita Bot — biznes uchun qonunchilik monitoringi

Telegram bot (Python, aiogram 3) · o'zbek va rus tillari · Gemma AI · 162 ta amaldagi NPA.

## Foydalanuvchi uchun
- **Boshlash** — birinchi ekran: til tanlash (🇺🇿 / 🇷🇺), so'ng faoliyat turi, so'ng menyu.
  Start tugmasidan oldin bot tavsifi ikki tilda ko'rinadi.
- **Pastdagi doimiy tugmalar**: 🏠 Menyu · 🤖 AI — istalgan joydan menyuga qaytish.
- **Menyu** (ekranlar joyida yangilanadi, chat to'lmaydi; har ekranda ⬅️ Ortga / 🏠 Menyu):
  - 🤖 AI yordamchi — savolga Lex.uz matni asosida javob + manbalar (akt, modda, havola).
    Tugma bosmasdan oddiy matn yozish ham — AI ga savol.
  - 📰 Yangiliklar · 📅 Muddatlar (🔴🟡🟢 qolgan kunlar bo'yicha)
  - 📚 Qonunlar — sohangizga tegishli **barcha amaldagi aktlar** ro'yxati
    (🎯 sohaga xos / 🌍 hamma uchun; 📄 — matni bazada)
  - 👤 Profil · 🔔 Xabarnoma · 🌐 Til · ✉️ Savol/taklif · ℹ️ Bot haqida
- **Avtomatik xabarnomalar** (faqat sohasi mos foydalanuvchilarga, o'z tilida):
  - 📚 **Yangi NPA** — reestrga yoki admin `/akt` orqali yangi akt qo'shilganda
  - ✏️ **O'zgarish** — akt matni Lex.uz da yangilanganda (haftasiga avtomatik tekshiruv)
  - 📰 Yangilik · ⏰ Muddat eslatmasi (7, 3, 1 kun va o'sha kuni)
  - Har bir akt xabarida: «🔗 Lex.uz» va «🤖 AI: bu men uchun nima?» tugmalari.

## Test qilish
1. **Botda**: menyuda `🧪 Demo / test` (yoki `/test`). Har bir turdagi xabarnoma
   **faqat sizga** demo sifatida keladi + AI test + 🩺 Diagnostika.
   `PUBLIC_DEMO=1` qilsangiz — demo tugmasi hammaga (hakaton hakamlari) ko'rinadi.
2. **Web-panel**: `https://<servis>.onrender.com/panel?key=<WEBHOOK_SECRET>`
   (botda Demo → 🌐 Web-panel tugmasi). Tizim holati, AI test (javob + manbalar +
   modelga berilgan kontekst), AI siz qidiruv, sohalar bo'yicha aktlar jadvali,
   demo xabarlarni adminlar Telegramiga yuborish.

## Admin buyruqlari (`/admin` yoki menyuda 🛠)
`/yangilik` · `/akt` (yangi NPA) · `/muddat` · `/muddatlar` · `/muddat_ochir ID` ·
`/yuklash [N]` (Lex.uz matnlari + o'zgarishlar) · `/qonunlar` · `/test` · `/javob ID matn` ·
`/stat` · `/cancel`. Admin matnlari admin tanlagan tilda.

## Render'da bepul joylashtirish
1. **neon.tech** — bepul Postgres, `postgresql://...` satri (Connect → Show password).
2. **aistudio.google.com/apikey** — Gemma uchun kalit.
3. Render → New → **Web Service** → Free. Build: `pip install -r requirements.txt`,
   Start: `python bot.py`.
4. Environment: `BOT_TOKEN`, `ADMIN_IDS` (raqamli ID, @userinfobot), `DATABASE_URL`,
   `GEMINI_API_KEY`, `WEBHOOK_SECRET` (faqat harf/raqam), `TZ=Asia/Tashkent`,
   `PYTHON_VERSION=3.12.8`. Ixtiyoriy: `PUBLIC_DEMO`, `AUTO_CHECK_DAYS`, `AI_DAILY_LIMIT`.
5. Live bo'lgach botga: `/yuklash 3` (sinov) → `/yuklash` (hammasi, ~20 daq).
6. **cron-job.org** — har 10 daqiqada `https://<servis>.onrender.com/tick?key=<WEBHOOK_SECRET>`
   (server uxlamaydi, eslatmalar va haftalik Lex.uz tekshiruvi ishlaydi).

Lex.uz Render'dan ochilmasa (bot xabar beradi) — kompyuterda `START_LOAD_TEXTS.bat`
(`.env` da Render'dagi bilan bir xil `DATABASE_URL`).

## Qonunlar bazasi
- `data/acts.csv` — QonunRadar reestri (20.11.2026), 162 akt. Lex.uz bilan mustaqil
  tekshirilmagan. Yangi qator qo'shib deploy qilsangiz — mos foydalanuvchilarga
  «Yangi NPA» xabari avtomatik ketadi (bir vaqtda 20 tadan ko'p bo'lsa — faqat adminga).
- Sohalar -> OKED: savdo=G; import=G,H; ovqatlanish=I; xizmat=M,N,S,J,K,P,Q,R;
  ishlab chiqarish=C,A,D,E; qurilish=F,L; boshqa=hammasi. "ОБЩИЕ" aktlar hammaga.
- O'zgarishni aniqlash: o'zbekcha matn moddalarining hash'i solishtiriladi.

## Fayllar
| Fayl | Vazifasi |
|---|---|
| `bot.py` | foydalanuvchi ekranlari, menyu, AI chat, ishga tushirish |
| `admin.py` | admin buyruqlari, demo/test, diagnostika |
| `jobs.py` | eslatmalar, Lex.uz yuklash, o'zgarishlarni kuzatish |
| `common.py` | sozlamalar, klaviaturalar, xabarnoma kartochkalari, tarqatish |
| `assistant.py` | AI kontekst (moddalar + reestr), javobni formatlash |
| `ai.py` | Gemma (Google AI Studio yoki Ollama) |
| `web.py` + `panel.html` | /health, /tick, test web-panel |
| `db.py` | Postgres / SQLite |
| `legal.py` | OKED, Lex.uz sahifasini moddalarga ajratish, qidiruv |
| `texts.py` | barcha matnlar (uz/ru) |
| `data/acts.csv` | 162 akt reestri |
| `load_texts.py`, `START_LOAD_TEXTS.bat` | kompyuterdan matn yuklash (zaxira) |
