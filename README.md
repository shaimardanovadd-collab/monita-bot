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

## Render'da joylashtirish
- Turi: **Background Worker** (bot polling rejimida ishlaydi, veb-port kerak emas)
- Build: `pip install -r requirements.txt`, Start: `python bot.py`
- Environment: `BOT_TOKEN`, `ADMIN_IDS`, `TZ=Asia/Tashkent`
- ⚠️ Render diski vaqtinchalik — `monita.db` qayta deploy'da o'chadi. Doimiy saqlash uchun
  Persistent Disk ulang va `db.py` dagi `DB_PATH` ni disk yo'liga o'zgartiring
  (masalan `/var/data/monita.db`), yoki PostgreSQL'ga o'ting.

## Fayllar
- `bot.py` — barcha handlerlar, admin formalar, eslatmalar
- `db.py` — SQLite jadvallari va so'rovlar
- `texts.py` — barcha matnlar va sohalar ro'yxati (yangi soha qo'shish uchun `SECTORS` ni tahrirlang)
