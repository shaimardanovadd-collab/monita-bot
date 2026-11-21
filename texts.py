"""Barcha matnlar va faoliyat turlari (sohalar)."""

# Faoliyat turlari: kalit -> (emoji, nom)
SECTORS = {
    "savdo": ("🏪", "Savdo (ulgurji / chakana)"),
    "import": ("📦", "Import / eksport"),
    "ovqat": ("🍽", "Umumiy ovqatlanish (kafe, restoran)"),
    "xizmat": ("⚙️", "Xizmat ko'rsatish"),
    "ishlab": ("🏭", "Ishlab chiqarish"),
    "qurilish": ("🏗", "Qurilish"),
    "boshqa": ("•••", "Boshqa"),
}


def sector_names(keys: list[str]) -> str:
    names = [SECTORS[k][1] for k in keys if k in SECTORS]
    return ", ".join(names) if names else "—"


WELCOME = (
    "<b>Assalomu alaykum, {name}!</b> 👋\n"
    "Monita Botga xush kelibsiz!\n\n"
    "Biznesingizga tegishli qonunchilikdagi yangiliklar, o'zgarishlar "
    "va muhim muddatlar haqida sizni doimiy xabardor qilamiz."
)

MENU = "Asosiy menyu. Kerakli bo'limni tanlang 👇"

CHOOSE_SECTORS = (
    "<b>Faoliyat turini tanlang</b>\n"
    "Siz bir nechta sohani tanlashingiz mumkin."
)

PROFILE_SAVED = (
    "✅ <b>Profil saqlandi!</b>\n\n"
    "Tanlangan sohalar: {sectors}\n\n"
    "Endi shu sohalar bo'yicha qonunchilikdagi o'zgarishlar sizga avtomatik yuboriladi."
)

NEED_ONE_SECTOR = "Kamida bitta sohani tanlang"

NOTIF_ON = "🔔 Xabarnomalar <b>yoqildi</b>. Yangi o'zgarishlar sizga avtomatik yuboriladi."
NOTIF_OFF = "🔕 Xabarnomalar <b>o'chirildi</b>. Qayta yoqish uchun tugmani yana bosing."
NEED_PROFILE = "Avval profilni sozlang — faoliyat turlaringizni tanlang."

NO_NEWS = "Hozircha tanlangan sohalaringiz bo'yicha yangiliklar yo'q."
NEWS_HEADER = "📰 <b>So'nggi yangiliklar</b> ({count} ta)"

ASK_FEEDBACK = (
    "✍️ Savol, taklif yoki fikr-mulohazangizni bitta xabarda yozib yuboring.\n"
    "Bekor qilish uchun /cancel"
)
FEEDBACK_THANKS = "Rahmat! Xabaringiz qabul qilindi. Tez orada javob beramiz. 🙏"

ABOUT = (
    "<b>Monita Bot</b> — biznes uchun qonunchilik monitoringi.\n\n"
    "🔔 <b>Doimiy xabarnomalar</b> — siz tanlagan sohalar bo'yicha avtomatik yuboriladi\n"
    "🗂 <b>Moslashtirilgan monitoring</b> — bir nechta faoliyat turini tanlash mumkin\n"
    "⚡ <b>Muhim muddatlar</b> — hisobotlar, litsenziyalar va boshqa majburiyatlar eslatmalari\n"
    "✉️ <b>Qulay aloqa</b> — savol, taklif va fikr-mulohazalaringiz uchun\n\n"
    "⚠️ Bot ma'lumot uchun mo'ljallangan va yuridik maslahat o'rnini bosmaydi. "
    "Rasmiy matnni har doim manbada (Lex.uz) tekshiring."
)

NO_DEADLINES = "Yaqin orada tanlangan sohalaringiz bo'yicha muhim muddatlar yo'q."
DEADLINES_HEADER = "📅 <b>Muhim muddatlar</b>"

UPDATE_CARD = (
    "⚖️ <b>Qonunchilikdagi yangi o'zgarish</b>\n"
    "<b>{title}</b>\n\n"
    "💼 <b>Soha:</b> {sectors}\n"
    "📝 <b>Nima o'zgardi?</b> {summary}\n"
    "📅 <b>Qachondan?</b> {effective}\n"
    "🔗 <b>Manba:</b> {source}"
)

REMINDER = (
    "⏰ <b>Eslatma: muhim muddat yaqinlashmoqda!</b>\n\n"
    "<b>{title}</b>\n"
    "📅 Muddat: <b>{due}</b> ({left})\n"
    "💼 Soha: {sectors}\n\n"
    "{description}"
)

CANCELLED = "Bekor qilindi."
