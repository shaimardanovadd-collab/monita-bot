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
   (`RENDER_EXTERNAL_URL` ni Render o'zi beradi — webhook avtomatik o'rnatiladi.)
4. **Uxlab qolmasligi uchun**: cron-job.org (bepul) da har 10 daqiqaga vazifa yarating:
   `https://<servis-nomi>.onrender.com/tick?key=<WEBHOOK_SECRET>`
   Bu serverni uyg'oq ushlaydi va muddat eslatmalarini o'z vaqtida yuboradi.
   (Bitta servis 24/7 ishlashi oyiga ~744 soat — bepul 750 soat limitiga sig'adi.)

Lokal sinash: `DATABASE_URL` va `RENDER_EXTERNAL_URL` bo'lmasa, bot SQLite + polling rejimida ishlaydi.

## Fayllar
- `bot.py` — barcha handlerlar, admin formalar, eslatmalar
- `db.py` — SQLite jadvallari va so'rovlar
- `texts.py` — barcha matnlar va sohalar ro'yxati (yangi soha qo'shish uchun `SECTORS` ni tahrirlang)
