import asyncio
import logging
import os
import sqlite3
from pathlib import Path
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv

load_dotenv()
BASE = Path(__file__).resolve().parent
DB = Path(os.getenv('DATABASE_PATH', str(BASE / 'qonunradar.sqlite3')))
TOKEN = os.getenv('BOT_TOKEN')
logging.basicConfig(level=logging.INFO)
dp = Dispatcher()
SECTORS = {'A':'Qishloq xo‘jaligi','C':'Ishlab chiqarish','F':'Qurilish','G':'Savdo','H':'Transport','I':'Ovqatlanish va mehmonxonalar','J':'Axborot va aloqa','K':'Moliya','M':'Professional xizmatlar','P':'Ta’lim','Q':'Sog‘liqni saqlash','OTHER':'Barcha sohalar'}

def connect():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    with connect() as con:
        con.execute('CREATE TABLE IF NOT EXISTS bot_users (user_id INTEGER PRIMARY KEY, sector TEXT, region TEXT, legal_form TEXT, tax_regime TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)')
        con.execute('CREATE TABLE IF NOT EXISTS bot_settings (user_id INTEGER PRIMARY KEY, notifications_enabled INTEGER DEFAULT 0)')

def menu():
    kb = InlineKeyboardBuilder()
    for label, data in [('🏢 Mening biznesim','profile'),('📚 Hujjatlar','docs'),('🔎 Qidiruv','search'),('🔔 O‘zgarishlar','updates'),('📋 Loyihalar','drafts'),('🗓 Muddatlar','calendar'),('⚙️ Sozlamalar','settings')]:
        kb.button(text=label, callback_data=data)
    kb.adjust(2,2,2,1)
    return kb.as_markup()

def sectors_keyboard():
    kb = InlineKeyboardBuilder()
    for code, name in SECTORS.items(): kb.button(text=name, callback_data=f'sector:{code}')
    kb.adjust(2)
    return kb.as_markup()

def get_sector(user_id):
    with connect() as con:
        row = con.execute('SELECT sector FROM bot_users WHERE user_id=?',(user_id,)).fetchone()
        return row['sector'] if row else None

def list_docs(sector=None, term=None, limit=8):
    sql='SELECT lex_id,title_uz,source_url,act_reference,oked_sections FROM documents WHERE 1=1'
    params=[]
    if sector and sector!='OTHER':
        sql+=' AND (oked_sections LIKE ? OR oked_sections LIKE ?)'
        params.extend([f'%{sector}%', '%ALL%'])
    if term:
        sql+=' AND (title_uz LIKE ? OR act_reference LIKE ? OR topic LIKE ?)'
        params.extend([f'%{term}%']*3)
    sql+=' ORDER BY lex_id DESC LIMIT ?';params.append(limit)
    with connect() as con:return con.execute(sql,params).fetchall()

def doc_text(rows):
    if not rows:return 'Hozircha mos hujjat topilmadi. Boshqa so‘z bilan qidirib ko‘ring.'
    out=[]
    for i,r in enumerate(rows,1):
        url=r['source_url'] or f'https://lex.uz/uz/docs/-{r["lex_id"]}'
        out.append(f'{i}. {r["title_uz"][:190]}\n{r["act_reference"] or ""}\n{url}')
    return '\n\n'.join(out)[:3900]

@dp.message(CommandStart())
async def start(m:Message):
    await m.answer('Assalomu alaykum! QonunRadar test versiyasiga xush kelibsiz.\n\n📌 Hozir bazada 225 ta hujjat rekviziti va Lex.uz havolasi bor. Hujjatlarning to‘liq matni va avtomatik yangilanishi hali tasdiqlanmagan.\n\nBiznes sohangizni tanlang:',reply_markup=sectors_keyboard())

@dp.message(Command('menu'))
async def show_menu(m:Message): await m.answer('QonunRadar — asosiy menyu',reply_markup=menu())

@dp.message(Command('help'))
async def help_cmd(m:Message): await m.answer('/start — boshlash\n/menu — menyu\n/search so‘z — hujjat qidirish\n/status — ma’lumotlar holati')

@dp.message(Command('status'))
async def status(m:Message):
    with connect() as con:
        docs=con.execute('SELECT COUNT(*) FROM documents').fetchone()[0]
        snaps=con.execute('SELECT COUNT(*) FROM snapshots').fetchone()[0]
        vers=con.execute('SELECT COUNT(*) FROM document_versions').fetchone()[0]
    await m.answer(f'📊 Baza holati\nHujjat rekvizitlari: {docs}\nYuklangan matnlar: {snaps}\nSaqlangan tahrirlar: {vers}\n\n⚠️ Avtomatik sinxronizatsiya hali ulanmagan.')

@dp.message(Command('search'))
async def search_command(m:Message):
    term=(m.text or '').partition(' ')[2].strip()
    if not term:return await m.answer('Masalan: /search soliq')
    await m.answer('🔎 Qidiruv natijalari:\n\n'+doc_text(list_docs(term=term)))

@dp.callback_query(F.data.startswith('sector:'))
async def choose_sector(c:CallbackQuery):
    sector=c.data.split(':',1)[1]
    with connect() as con:
        con.execute('INSERT INTO bot_users(user_id,sector) VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET sector=excluded.sector',(c.from_user.id,sector))
    await c.message.answer(f'✅ Sohangiz: {SECTORS.get(sector,sector)}\n\nMenyudan foydalanishingiz mumkin.',reply_markup=menu())
    await c.answer()

@dp.callback_query(F.data.in_({'profile','docs','search','updates','drafts','calendar','settings'}))
async def handle_menu(c:CallbackQuery):
    action=c.data;sector=get_sector(c.from_user.id)
    if action=='profile':await c.message.answer(f'🏢 Tanlangan soha: {SECTORS.get(sector,"Hali tanlanmagan")}\n\nSohani o‘zgartirish:',reply_markup=sectors_keyboard())
    elif action=='docs':await c.message.answer('📚 Sizning sohangiz bo‘yicha hujjatlar (Excel reyestridagi dastlabki tasnif):\n\n'+doc_text(list_docs(sector=sector)))
    elif action=='search':await c.message.answer('🔎 Qidirish uchun yozing: /search soliq')
    elif action=='updates':await c.message.answer('🔔 Hozircha tasdiqlangan o‘zgarishlar lentasi yo‘q. Lex.uz sinxronizatsiyasi va huquqiy tekshiruv ulanganidan so‘ng ishga tushadi.')
    elif action=='drafts':await c.message.answer('📋 Regulation.gov.uz loyihalari integratsiyasi hali ulanmagan. Loyihalar qabul qilingan qonun sifatida ko‘rsatilmaydi.')
    elif action=='calendar':await c.message.answer('🗓 Hozircha tasdiqlangan muddatlar kalendari mavjud emas. Excel sanalari huquqiy tekshiruvdan o‘tmaguncha eslatmalar yuborilmaydi.')
    elif action=='settings':await c.message.answer('⚙️ Test rejimi: avtomatik bildirishnomalar o‘chirilgan. Sohani o‘zgartirish uchun «Mening biznesim» bo‘limiga kiring.')
    await c.answer()

async def main():
    if not TOKEN:raise RuntimeError('BOT_TOKEN .env faylida ko‘rsatilmagan')
    if not DB.exists():raise RuntimeError(f'Database not found: {DB}')
    init_db()
    bot=Bot(TOKEN)
    await dp.start_polling(bot)

if __name__=='__main__':asyncio.run(main())
