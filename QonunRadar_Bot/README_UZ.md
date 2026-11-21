# QonunRadar — Telegram botning sinov versiyasi

## Ishlaydigan imkoniyatlar
- Telegram menyusi, /start, /menu, /help, /status va /search buyruqlari.
- Biznes sohasini tanlash va saqlash.
- Bazadagi 225 ta NHH rekviziti va Lex.uz havolasi bo‘yicha qidiruv.

## Hali ulanmagan
- Lex.uz va Regulation.gov.uz saytlari bilan avtomatik sinxronlash.
- Hujjatlarning to‘liq matni va rasmiy tahrirlar tarixi.
- Tekshirilgan o‘zgarishlar haqida avtomatik xabarnomalar.
- Muddatlar taqvimi va huquqiy qo‘llanishni aniq tekshirish.

## Ishga tushirish
1. Telegramdagi @BotFather orqali /newbot buyrug‘i bilan bot yarating.
2. Python 3.11 yoki yangiroq versiyasini o‘rnating.
3. Arxivni oching va loyiha papkasiga o‘ting.
4. `python -m venv .venv` buyrug‘ini bajaring.
5. Windows: `.venv\\Scripts\\activate`; Linux/macOS: `source .venv/bin/activate`.
6. `pip install -r requirements.txt` buyrug‘ini bajaring.
7. `.env.example` faylidan `.env` nusxa yarating va BOT_TOKEN qiymatini kiriting.
8. `python bot.py` buyrug‘i bilan ishga tushiring.
9. Telegramda botni ochib Start tugmasini bosing.

Bot ishlashi uchun dastur doimiy ishlashi kerak. 24/7 uchun serverga joylashtirish zarur.
