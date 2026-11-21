"""Barcha matnlar (o'zbek / rus) va faoliyat turlari."""

LANGS = ("uz", "ru")
LINE = "━━━━━━━━━━━━━━━━"

import oked


def sector_name(code: str, lang: str = "uz") -> str:
    if code in oked.SECTIONS:
        return oked.section_label(code, lang)
    if code in oked.DIVISIONS:
        return oked.division_label(code, lang, 50)
    return code


def sector_names(codes, lang: str = "uz") -> str:
    return oked.describe(codes, lang)


MONTHS = {
    "uz": ["yanvar", "fevral", "mart", "aprel", "may", "iyun", "iyul", "avgust",
           "sentabr", "oktabr", "noyabr", "dekabr"],
    "ru": ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа",
           "сентября", "октября", "ноября", "декабря"],
}

TEXTS = {
    # ---------- tugmalar ----------
    "btn_menu": {"uz": "🏠 Menyu", "ru": "🏠 Меню"},
    "btn_ai": {"uz": "🤖 AI yordamchi", "ru": "🤖 AI-помощник"},
    "btn_news": {"uz": "📰 Yangiliklar", "ru": "📰 Новости"},
    "btn_deadlines": {"uz": "📅 Muddatlar", "ru": "📅 Сроки"},
    "btn_laws": {"uz": "📚 Qonunlar", "ru": "📚 Законы"},
    "btn_profile": {"uz": "👤 Profil", "ru": "👤 Профиль"},
    "btn_notify_on": {"uz": "🔔 Xabarnoma: yoniq", "ru": "🔔 Уведомления: вкл"},
    "btn_notify_off": {"uz": "🔕 Xabarnoma: o'chiq", "ru": "🔕 Уведомления: выкл"},
    "btn_lang": {"uz": "🌐 Til: O'zbek", "ru": "🌐 Язык: Русский"},
    "btn_about": {"uz": "ℹ️ Bot haqida", "ru": "ℹ️ О боте"},
    "btn_feedback": {"uz": "✉️ Savol yoki taklif", "ru": "✉️ Вопрос или предложение"},
    "btn_admin": {"uz": "🛠 Admin panel", "ru": "🛠 Админ-панель"},
    "btn_back": {"uz": "⬅️ Ortga", "ru": "⬅️ Назад"},
    "btn_back_menu": {"uz": "⬅️ Menyuga", "ru": "⬅️ В меню"},
    "btn_continue": {"uz": "Davom etish ➡️", "ru": "Продолжить ➡️"},
    "btn_edit_sectors": {"uz": "✏️ Sohalarni o'zgartirish", "ru": "✏️ Изменить сферы"},
    "btn_details": {"uz": "📄 Batafsil", "ru": "📄 Подробнее"},
    "btn_source": {"uz": "🔗 Manba (Lex.uz)", "ru": "🔗 Источник (Lex.uz)"},
    "btn_new_chat": {"uz": "🔄 Yangi suhbat", "ru": "🔄 Новый диалог"},
    "btn_prev": {"uz": "◀️", "ru": "◀️"},
    "btn_next": {"uz": "▶️", "ru": "▶️"},

    # ---------- ekranlar ----------
    "choose_lang": {"uz": "🌐 Tilni tanlang / Выберите язык:", "ru": "🌐 Tilni tanlang / Выберите язык:"},
    "welcome": {
        "uz": "👋 <b>Assalomu alaykum, {name}!</b>\n\n"
              "<b>Monita Bot</b> — biznes uchun qonunchilik monitoringi.\n"
              "Sohangizga tegishli yangiliklar, o'zgarishlar va muhim muddatlar "
              "haqida sizni xabardor qilamiz.",
        "ru": "👋 <b>Здравствуйте, {name}!</b>\n\n"
              "<b>Monita Bot</b> — мониторинг законодательства для бизнеса.\n"
              "Сообщаем о новостях, изменениях и важных сроках в вашей сфере.",
    },
    "menu": {
        "uz": "⚖️ <b>Monita Bot</b> · Asosiy menyu\n" + LINE + "\n"
              "💼 <b>Sohalar:</b> {sectors}\n"
              "🔔 <b>Xabarnomalar:</b> {notify}\n" + LINE + "\n"
              "Kerakli bo'limni tanlang 👇",
        "ru": "⚖️ <b>Monita Bot</b> · Главное меню\n" + LINE + "\n"
              "💼 <b>Сферы:</b> {sectors}\n"
              "🔔 <b>Уведомления:</b> {notify}\n" + LINE + "\n"
              "Выберите раздел 👇",
    },
    "on": {"uz": "yoniq ✅", "ru": "включены ✅"},
    "off": {"uz": "o'chiq ⛔️", "ru": "выключены ⛔️"},
    "choose_sectors": {
        "uz": "💼 <b>Faoliyat turingizni tanlang</b>\n\nBir nechta sohani belgilash mumkin. "
              "Shu sohalar bo'yicha yangiliklar va qonunlar tanlanadi.",
        "ru": "💼 <b>Выберите вид деятельности</b>\n\nМожно отметить несколько сфер. "
              "По ним подбираются новости и законы.",
    },
    "need_one_sector": {"uz": "Kamida bitta sohani tanlang", "ru": "Выберите хотя бы одну сферу"},
    "saved": {"uz": "Saqlandi ✅", "ru": "Сохранено ✅"},
    "need_profile": {"uz": "Avval faoliyat turini tanlang.", "ru": "Сначала выберите сферу деятельности."},
    "profile": {
        "uz": "👤 <b>Profil</b>\n" + LINE + "\n"
              "🙋 {name}\n💼 <b>Sohalar:</b>\n{sectors}\n"
              "🔔 <b>Xabarnomalar:</b> {notify}\n🌐 <b>Til:</b> O'zbek",
        "ru": "👤 <b>Профиль</b>\n" + LINE + "\n"
              "🙋 {name}\n💼 <b>Сферы:</b>\n{sectors}\n"
              "🔔 <b>Уведомления:</b> {notify}\n🌐 <b>Язык:</b> Русский",
    },
    "notif_on": {"uz": "🔔 Xabarnomalar yoqildi", "ru": "🔔 Уведомления включены"},
    "notif_off": {"uz": "🔕 Xabarnomalar o'chirildi", "ru": "🔕 Уведомления выключены"},
    "news_header": {"uz": "📰 <b>So'nggi yangiliklar</b>", "ru": "📰 <b>Последние новости</b>"},
    "no_news": {
        "uz": "📰 <b>Yangiliklar</b>\n" + LINE + "\nHozircha sohalaringiz bo'yicha yangiliklar yo'q.",
        "ru": "📰 <b>Новости</b>\n" + LINE + "\nПока нет новостей по вашим сферам.",
    },
    "deadlines_header": {"uz": "📅 <b>Muhim muddatlar</b>", "ru": "📅 <b>Важные сроки</b>"},
    "no_deadlines": {
        "uz": "📅 <b>Muhim muddatlar</b>\n" + LINE + "\nYaqin orada muddatlar yo'q.",
        "ru": "📅 <b>Важные сроки</b>\n" + LINE + "\nБлижайших сроков нет.",
    },
    "days_left": {"uz": "{n} kun qoldi", "ru": "осталось {n} дн."},
    "today": {"uz": "bugun!", "ru": "сегодня!"},
    "laws_header": {
        "uz": "📚 <b>Amaldagi qonun hujjatlari</b>\nSohalaringiz bo'yicha: {count} ta · sahifa {page}/{pages}\n"
              "📄 — matni bazada (AI shu matndan javob beradi)\n" + LINE,
        "ru": "📚 <b>Действующие акты</b>\nПо вашим сферам: {count} · стр. {page}/{pages}\n"
              "📄 — текст в базе (AI отвечает по нему)\n" + LINE,
    },
    "update_card": {
        "uz": "⚖️ <b>Qonunchilikdagi yangi o'zgarish</b>\n" + LINE + "\n<b>{title}</b>\n\n"
              "💼 <b>Soha:</b> {sectors}\n📝 <b>Nima o'zgardi?</b> {summary}\n"
              "📅 <b>Qachondan?</b> {effective}\n🔗 <b>Manba:</b> {source}",
        "ru": "⚖️ <b>Новое изменение в законодательстве</b>\n" + LINE + "\n<b>{title}</b>\n\n"
              "💼 <b>Сфера:</b> {sectors}\n📝 <b>Что изменилось?</b> {summary}\n"
              "📅 <b>С какого числа?</b> {effective}\n🔗 <b>Источник:</b> {source}",
    },
    "reminder": {
        "uz": "⏰ <b>Muhim muddat yaqinlashmoqda!</b>\n" + LINE + "\n<b>{title}</b>\n"
              "📅 Muddat: <b>{due}</b> ({left})\n💼 Soha: {sectors}\n\n{description}",
        "ru": "⏰ <b>Приближается важный срок!</b>\n" + LINE + "\n<b>{title}</b>\n"
              "📅 Срок: <b>{due}</b> ({left})\n💼 Сфера: {sectors}\n\n{description}",
    },
    "not_found": {"uz": "Ma'lumot topilmadi", "ru": "Не найдено"},
    "ask_feedback": {
        "uz": "✉️ <b>Savol yoki taklif</b>\n" + LINE + "\nXabaringizni bitta xabarda yozib yuboring — "
              "jamoamiz javob beradi.",
        "ru": "✉️ <b>Вопрос или предложение</b>\n" + LINE + "\nНапишите сообщение одним текстом — "
              "наша команда ответит.",
    },
    "feedback_thanks": {"uz": "🙏 Rahmat! Xabaringiz qabul qilindi.", "ru": "🙏 Спасибо! Сообщение получено."},
    "admin_reply": {"uz": "✉️ <b>Monita Bot jamoasidan javob:</b>\n\n{text}",
                    "ru": "✉️ <b>Ответ команды Monita Bot:</b>\n\n{text}"},
    "about": {
        "uz": "ℹ️ <b>Monita Bot</b> — biznes uchun qonunchilik monitoringi\n" + LINE + "\n"
              "🔔 <b>Xabarnomalar</b> — tanlangan sohalar bo'yicha avtomatik\n"
              "🤖 <b>AI yordamchi</b> — {acts} ta amaldagi akt asosida javob\n"
              "📚 <b>Qonunlar</b> — sohangizga tegishli hujjatlar ro'yxati\n"
              "📅 <b>Muddatlar</b> — hisobot va litsenziyalar eslatmalari\n"
              "✉️ <b>Aloqa</b> — savol va takliflar uchun\n\n"
              "⚠️ Bot ma'lumot uchun, yuridik maslahat o'rnini bosmaydi. "
              "Rasmiy matnni Lex.uz da tekshiring.",
        "ru": "ℹ️ <b>Monita Bot</b> — мониторинг законодательства для бизнеса\n" + LINE + "\n"
              "🔔 <b>Уведомления</b> — автоматически по выбранным сферам\n"
              "🤖 <b>AI-помощник</b> — ответы на основе {acts} действующих актов\n"
              "📚 <b>Законы</b> — перечень актов для вашей сферы\n"
              "📅 <b>Сроки</b> — напоминания об отчётах и лицензиях\n"
              "✉️ <b>Связь</b> — вопросы и предложения\n\n"
              "⚠️ Бот носит справочный характер и не заменяет юридическую консультацию. "
              "Сверяйте официальный текст на Lex.uz.",
    },
    "lang_set": {"uz": "🌐 Til: O'zbek ✅", "ru": "🌐 Язык: Русский ✅"},
    "cancelled": {"uz": "Bekor qilindi.", "ru": "Отменено."},

    # ---------- AI ----------
    "ai_intro": {
        "uz": "🤖 <b>AI yordamchi</b> · Gemini\n" + LINE + "\n"
              "Biznesingizga oid qonunchilik bo'yicha savol yozing.\n\n"
              "💡 <i>Masalan: «Litsenziya olish tartibi qanday?»</i>\n\n"
              "📚 Javob faqat bot bazasidan: {acts} ta amaldagi akt reestri, shundan {texts} tasining "
              "to'liq matni (Lex.uz), yangiliklar va muddatlar. Har bir fikr manbasi [1], [2] bilan.\n"
              "⏳ Javob 20–40 soniya oladi: bot hujjatlarni topadi va o'qiydi.\n"
              "⚠️ Bu yuridik maslahat emas — rasmiy matnni Lex.uz da tekshiring.",
        "ru": "🤖 <b>AI-помощник</b> · Gemini\n" + LINE + "\n"
              "Задайте вопрос о законодательстве для вашего бизнеса.\n\n"
              "💡 <i>Например: «Как получить лицензию?»</i>\n\n"
              "📚 Ответ только по базе бота: реестр {acts} действующих актов, полные тексты {texts} из них "
              "(Lex.uz), новости и сроки. У каждого утверждения — источник [1], [2].\n"
              "⏳ Ответ занимает 20–40 секунд: бот находит и читает документы.\n"
              "⚠️ Это не юридическая консультация — сверяйте текст на Lex.uz.",
    },
    "ai_new": {"uz": "🔄 Yangi suhbat. Savolingizni yozing.", "ru": "🔄 Новый диалог. Задайте вопрос."},
    "ai_off": {"uz": "AI yordamchi hali sozlanmagan.", "ru": "AI-помощник ещё не настроен."},
    "ai_text_only": {"uz": "Faqat matnli savollarni qabul qilaman.", "ru": "Я принимаю только текстовые вопросы."},
    "ai_sources": {"uz": "📚 Manbalar:", "ru": "📚 Источники:"},
    "ai_read": {"uz": "🔎 <i>Gemini Lex.uz dan o'qidi: {n} ta sahifa</i>",
                "ru": "🔎 <i>Gemini прочитал на Lex.uz: {n} стр.</i>"},
    "ai_related": {"uz": "📚 Bazadagi tegishli hujjatlar:", "ru": "📚 Связанные документы из базы:"},
    "ai_err_cooldown": {"uz": "⏳ Biroz kuting, javob tayyorlanmoqda.", "ru": "⏳ Подождите, готовлю ответ."},
    "ai_err_daily": {"uz": "Bugungi limit tugadi ({n} ta savol). Ertaga urinib ko'ring.",
                     "ru": "Дневной лимит исчерпан ({n} вопросов). Попробуйте завтра."},
    "ai_err_busy": {"uz": "⚠️ AI xizmati band. Bir daqiqadan so'ng urinib ko'ring.",
                    "ru": "⚠️ AI-сервис занят. Попробуйте через минуту."},
    "ai_err_connect": {"uz": "⚠️ AI xizmatiga ulanib bo'lmadi. Keyinroq urinib ko'ring.",
                       "ru": "⚠️ Не удалось подключиться к AI. Попробуйте позже."},
    "ai_err_empty": {"uz": "⚠️ Model javob bermadi. Savolni boshqacha yozib ko'ring.",
                     "ru": "⚠️ Модель не ответила. Переформулируйте вопрос."},
    "ai_err_other": {"uz": "⚠️ Xatolik yuz berdi. Keyinroq urinib ko'ring.",
                     "ru": "⚠️ Произошла ошибка. Попробуйте позже."},
}

TEXTS.update({
    "btn_demo": {"uz": "🧪 Demo / test", "ru": "🧪 Демо / тест"},
    "btn_ask_ai_act": {"uz": "🤖 AI: bu men uchun nima?", "ru": "🤖 AI: что это значит для меня?"},
    "btn_lex": {"uz": "🔗 Lex.uz da ochish", "ru": "🔗 Открыть на Lex.uz"},
    "act_new": {
        "uz": "📚 <b>Yangi qonun hujjati</b>\n" + LINE + "\n<b>{act_type}</b> · {requisites}\n"
              "«{title}»\n\n📅 <b>Kuchga kirgan:</b> {effective}\n💼 <b>Sohangizga tegishli:</b> {sectors}",
        "ru": "📚 <b>Новый нормативный акт</b>\n" + LINE + "\n<b>{act_type}</b> · {requisites}\n"
              "«{title}»\n\n📅 <b>Вступил в силу:</b> {effective}\n💼 <b>Касается вашей сферы:</b> {sectors}",
    },
    "act_changed": {
        "uz": "✏️ <b>Hujjatga o'zgartirish kiritildi</b>\n" + LINE + "\n<b>{act_type}</b> · {requisites}\n"
              "«{title}»\n\nLex.uz dagi matn yangilandi. Amaldagi tahririni tekshiring.\n"
              "💼 <b>Sohangizga tegishli:</b> {sectors}",
        "ru": "✏️ <b>В акт внесены изменения</b>\n" + LINE + "\n<b>{act_type}</b> · {requisites}\n"
              "«{title}»\n\nТекст на Lex.uz обновился. Проверьте действующую редакцию.\n"
              "💼 <b>Касается вашей сферы:</b> {sectors}",
    },
    "all_sectors": {"uz": "barcha faoliyat turlari", "ru": "все виды деятельности"},
    "ai_act_question": {
        "uz": "«{title}» ({act_type}, {requisites}) hujjati mening biznesim uchun nimani anglatadi? "
              "Asosiy talablar va nima qilishim kerakligini qisqa ayting.",
        "ru": "Что означает акт «{title}» ({act_type}, {requisites}) для моего бизнеса? "
              "Кратко: основные требования и что мне нужно сделать.",
    },
    "demo": {
        "uz": "🧪 <b>Demo rejim</b>\n" + LINE + "\nBot qanday ishlashini sinab ko'ring: tugmani bosing — "
              "xabarnoma <b>faqat sizga</b> keladi, xuddi haqiqiydek.\n\n"
              "📚 Yangi NPA — sohangizga yangi hujjat qo'shilganda\n"
              "✏️ O'zgarish — hujjat matni Lex.uz da yangilanganda\n"
              "📰 Yangilik — sohangizdagi eng so'nggi hujjat + AI qisqa mazmuni\n"
              "⏰ Eslatma — muhim muddat yaqinlashganda\n"
              "📝 Loyiha — sohangizda yangi NPA loyihasi muhokamaga qo'yilganda\n"
              "🤖 AI — namunaviy savolga javob va manbalar",
        "ru": "🧪 <b>Демо-режим</b>\n" + LINE + "\nПроверьте, как работает бот: нажмите кнопку — "
              "уведомление придёт <b>только вам</b>, как настоящее.\n\n"
              "📚 Новый НПА — когда в вашей сфере появляется новый акт\n"
              "✏️ Изменение — когда текст акта на Lex.uz обновился\n"
              "📰 Новость — последний акт вашей отрасли + краткое изложение AI\n"
              "⏰ Напоминание — когда приближается важный срок\n"
              "📝 Проект — когда в вашей сфере на обсуждение вынесен новый проект НПА\n"
              "🤖 AI — ответ на пример вопроса с источниками",
    },
    "demo_new": {"uz": "📚 Yangi NPA", "ru": "📚 Новый НПА"},
    "demo_change": {"uz": "✏️ O'zgarish", "ru": "✏️ Изменение"},
    "demo_news": {"uz": "📰 Yangilik", "ru": "📰 Новость"},
    "demo_rem": {"uz": "⏰ Eslatma", "ru": "⏰ Напоминание"},
    "demo_ai": {"uz": "🤖 AI test", "ru": "🤖 Тест AI"},
    "demo_diag": {"uz": "🩺 Diagnostika", "ru": "🩺 Диагностика"},
    "demo_panel": {"uz": "🌐 Web-panel", "ru": "🌐 Веб-панель"},
    "demo_sent": {"uz": "Demo xabar yuborildi 👇", "ru": "Демо-уведомление отправлено 👇"},
    "demo_tag": {"uz": "🧪 <i>Demo xabar</i>\n", "ru": "🧪 <i>Демо-уведомление</i>\n"},
    "demo_ai_q": {"uz": "Litsenziya olish va tekshiruvlar tartibi qanday?",
                  "ru": "Какой порядок получения лицензий и проведения проверок?"},
    "start_again": {"uz": "👋 Qaytganingizdan xursandmiz, {name}!", "ru": "👋 Рады видеть вас снова, {name}!"},
})

TEXTS.update({
    "welcome_new": {
        "uz": "👋 <b>Assalomu alaykum, {name}!</b>\n\n"
              "<b>Monita Bot</b> — biznes uchun qonunchilik monitoringi.\n"
              "Faoliyatingizga (OKED) tegishli amaldagi qonunlar, yangi va o'zgargan hujjatlar, "
              "muhim muddatlar haqida xabar beramiz. Savollaringizga AI yordamchi javob beradi.\n\n"
              "⏳ <i>Bot hozir test rejimida ishlaydi: uzoq tanaffusdan keyin birinchi javob 1 daqiqagacha, "
              "AI javobi esa 20–40 soniya olishi mumkin.</i>\n\n"
              "🌐 <i>Til: O'zbek. Rus tiliga pastdagi tugma orqali o'tishingiz mumkin.</i>\n"
              "🇷🇺 <i>Язык можно сменить на русский кнопкой ниже.</i>",
        "ru": "👋 <b>Здравствуйте, {name}!</b>\n\n"
              "<b>Monita Bot</b> — мониторинг законодательства для бизнеса.\n"
              "Сообщаем о действующих законах для вашей деятельности (ОКЭД), новых и изменённых "
              "актах, важных сроках. На вопросы отвечает AI-помощник.\n\n"
              "⏳ <i>Бот работает в тестовом режиме: после долгого перерыва первый ответ может занять "
              "до минуты, а ответ AI — 20–40 секунд.</i>\n\n"
              "🌐 <i>Язык: русский. Сменить язык можно кнопкой ниже.</i>",
    },
    "choose_sections": {
        "uz": "💼 <b>Faoliyat turingiz (OKED bo'limi)</b>\n" + LINE + "\n"
              "Bir yoki bir nechta bo'limni belgilang. Keyingi qadamda aniqroq yo'nalishni "
              "(OKED bo'linmasi, masalan 47 — chakana savdo) tanlashingiz mumkin.",
        "ru": "💼 <b>Ваш вид деятельности (секция ОКЭД)</b>\n" + LINE + "\n"
              "Отметьте одну или несколько секций. На следующем шаге можно уточнить направление "
              "(раздел ОКЭД, например 47 — розничная торговля).",
    },
    "choose_divisions": {
        "uz": "🎯 <b>Aniqroq yo'nalish (ixtiyoriy)</b>\n" + LINE + "\n"
              "OKED bo'linmalarini belgilang — AI javoblari va yangiliklar faoliyatingizga "
              "aniqroq moslashadi. Tanlamasangiz, butun bo'lim hisobga olinadi.\n"
              "<i>Sahifa {page}/{pages}</i>",
        "ru": "🎯 <b>Уточните направление (необязательно)</b>\n" + LINE + "\n"
              "Отметьте разделы ОКЭД — ответы AI и новости точнее подстроятся под вашу "
              "деятельность. Если не выбрать, учитывается вся секция.\n"
              "<i>Страница {page}/{pages}</i>",
    },
    "btn_next_step": {"uz": "Keyingi ➡️", "ru": "Далее ➡️"},
    "btn_save": {"uz": "✅ Saqlash", "ru": "✅ Сохранить"},
    "btn_skip": {"uz": "⏭ O'tkazib yuborish", "ru": "⏭ Пропустить"},
    "btn_edit_divisions": {"uz": "🎯 Yo'nalishlarni aniqlash", "ru": "🎯 Уточнить направления"},
    "btn_ai_summary": {"uz": "🤖 Qisqacha mazmuni (AI)", "ru": "🤖 Кратко о главном (AI)"},
    "news_screen": {
        "uz": "📰 <b>Sohangiz yangiliklari</b>\n" + LINE,
        "ru": "📰 <b>Новости вашей отрасли</b>\n" + LINE,
    },
    "news_admin": {"uz": "📣 <b>E'lonlar</b>", "ru": "📣 <b>Объявления</b>"},
    "news_acts": {"uz": "📚 <b>So'nggi hujjatlar (OKED: {sec})</b>", "ru": "📚 <b>Последние акты (ОКЭД: {sec})</b>"},
    "news_hint": {
        "uz": "<i>Yangiliklar — rasmiy hujjatlar reestri va Lex.uz monitoringidan. "
              "«🤖 Qisqacha» — AI hujjat matnidan qisqa mazmun tayyorlaydi.</i>",
        "ru": "<i>Новости берутся из реестра официальных актов и мониторинга Lex.uz. "
              "«🤖 Кратко» — AI готовит выжимку по тексту акта.</i>",
    },
    "act_card": {
        "uz": "📄 <b>{act_type}</b> · {requisites}\n" + LINE + "\n«{title}»\n\n"
              "📅 <b>Kuchga kirgan:</b> {effective}\n💼 <b>Kimga tegishli:</b> {sectors}\n"
              "🏷 <b>Mavzu:</b> {topic}\n{text_status}",
        "ru": "📄 <b>{act_type}</b> · {requisites}\n" + LINE + "\n«{title}»\n\n"
              "📅 <b>Вступил в силу:</b> {effective}\n💼 <b>Кого касается:</b> {sectors}\n"
              "🏷 <b>Тема:</b> {topic}\n{text_status}",
    },
    "text_loaded": {"uz": "📄 Matni bazada — AI shu matndan javob beradi.",
                    "ru": "📄 Текст в базе — AI отвечает по нему."},
    "text_missing": {"uz": "▫️ Matni hali yuklanmagan.", "ru": "▫️ Текст ещё не загружен."},
    "ai_summary_title": {"uz": "🤖 <b>Qisqacha mazmuni</b>", "ru": "🤖 <b>Кратко о главном</b>"},
    "summary_no_text": {
        "uz": "(Hujjat matni bazada yo'q — qisqa mazmun faqat nomi va rekvizitlari asosida.)",
        "ru": "(Текста акта нет в базе — выжимка только по названию и реквизитам.)",
    },
})

TEXTS.update({
    "ai_wait": {"uz": "⏳ Qonunlardan qidiryapman… odatda 20–40 soniya.",
                "ru": "⏳ Ищу в законах… обычно 20–40 секунд."},
    "ai_wait_doc": {"uz": "⏳ Hujjatni o'qiyapman… odatda 20–40 soniya.",
                    "ru": "⏳ Читаю документ… обычно 20–40 секунд."},
    "btn_drafts": {"uz": "📝 Loyihalar (muhokamada)", "ru": "📝 Проекты НПА (обсуждение)"},
    "btn_portal": {"uz": "🔗 Portalda ochish / taklif berish", "ru": "🔗 Открыть на портале / предложить"},
    "btn_draft_ai": {"uz": "🤖 Nima o'zgaradi? (AI)", "ru": "🤖 Что изменится? (AI)"},
    "btn_all_drafts": {"uz": "📝 Barcha loyihalar", "ru": "📝 Все проекты"},
    "drafts_screen": {
        "uz": "📝 <b>Muhokamadagi NPA loyihalari</b>\nSohangiz bo'yicha: {count} ta · sahifa {page}/{pages}\n"
              "<i>Manba: regulation.adliya.uz — hali qabul qilinmagan hujjatlar. Taklifingizni "
              "muhokama tugaguncha portalda qoldirishingiz mumkin.</i>\n" + LINE,
        "ru": "📝 <b>Проекты НПА на обсуждении</b>\nПо вашей сфере: {count} · стр. {page}/{pages}\n"
              "<i>Источник: regulation.adliya.uz — документы ещё не приняты. Пока идёт обсуждение, "
              "можно оставить предложение на портале.</i>\n" + LINE,
    },
    "no_drafts": {
        "uz": "📝 <b>NPA loyihalari</b>\n" + LINE + "\nHozir sohangiz bo'yicha muhokamada loyiha yo'q. "
              "Yangi loyiha paydo bo'lishi bilan xabar beramiz.",
        "ru": "📝 <b>Проекты НПА</b>\n" + LINE + "\nСейчас по вашей сфере нет проектов на обсуждении. "
              "Сообщим, как только появится новый.",
    },
    "draft_card": {
        "uz": "📝 <b>NPA loyihasi — jamoatchilik muhokamasida</b>\n" + LINE + "\n«{name}»\n\n"
              "🏛 <b>Ishlab chiquvchi:</b> {org}\n🗂 <b>Soha:</b> {spec}\n"
              "📅 <b>Muhokama:</b> {start} — {end} ({left})\n👁 {views} · 💬 {sugg} ta taklif\n\n"
              "⚠️ <i>Bu hali qabul qilinmagan loyiha. Biznesingizga ta'sir qilsa — portalda taklif qoldiring.</i>",
        "ru": "📝 <b>Проект НПА — на общественном обсуждении</b>\n" + LINE + "\n«{name}»\n\n"
              "🏛 <b>Разработчик:</b> {org}\n🗂 <b>Сфера:</b> {spec}\n"
              "📅 <b>Обсуждение:</b> {start} — {end} ({left})\n👁 {views} · 💬 предложений: {sugg}\n\n"
              "⚠️ <i>Документ ещё не принят. Если он касается вашего бизнеса — оставьте предложение на портале.</i>",
    },
    "draft_left": {"uz": "⏳ {n} kun qoldi", "ru": "⏳ осталось {n} дн."},
    "draft_last_day": {"uz": "⏳ bugun oxirgi kun!", "ru": "⏳ сегодня последний день!"},
    "draft_closed": {"uz": "muhokama yakunlangan", "ru": "обсуждение завершено"},
    "drafts_digest": {
        "uz": "📝 <b>Sohangizda yangi NPA loyihalari muhokamaga qo'yildi</b>\n" + LINE + "\n"
              "Hozir quyidagi hujjatlar ko'rib chiqilmoqda — hali qabul qilinmagan, taklif berish mumkin:\n",
        "ru": "📝 <b>В вашей сфере на обсуждение вынесены новые проекты НПА</b>\n" + LINE + "\n"
              "Сейчас рассматриваются следующие документы — они ещё не приняты, можно предложить правки:\n",
    },
    "draft_ai_title": {"uz": "🤖 <b>Loyiha: nima o'zgaradi?</b>", "ru": "🤖 <b>Проект: что изменится?</b>"},
    "draft_no_text": {
        "uz": "(Loyiha matni portaldan olinmadi — tahlil faqat nomi asosida. To'liq matn portalda.)",
        "ru": "(Текст проекта не удалось получить с портала — разбор только по названию. Полный текст — на портале.)",
    },
    "demo_draft": {"uz": "📝 Yangi loyiha", "ru": "📝 Новый проект НПА"},
    "drafts_not_synced": {
        "uz": "Loyihalar hali yuklanmagan (portal bilan sinxronlash kutilmoqda).",
        "ru": "Проекты ещё не загружены (ожидается синхронизация с порталом).",
    },
})

BOT_DESCRIPTION_ALL = (
    "⚖️ Monita Bot — biznes uchun qonunchilik monitoringi.\n"
    "• Faoliyatingizga (OKED) tegishli amaldagi NPA\n"
    "• Yangi va o'zgargan hujjatlar haqida xabarnoma\n"
    "• AI yordamchi: Lex.uz matni asosida javob\n\n"
    "⏳ Bot uzoq ishlatilmagan bo'lsa, birinchi javob 1 daqiqagacha kechikishi mumkin.\n\n"
    "🇷🇺 Мониторинг законодательства для бизнеса: НПА по ОКЭД, уведомления, AI-помощник. "
    "Первый ответ после перерыва — до 1 минуты. Русский язык — после запуска.\n\n"
    "Boshlash uchun pastdagi tugmani bosing 👇"
)
BOT_SHORT_ALL = "Biznes uchun qonunchilik monitoringi · Мониторинг законодательства для бизнеса"

BOT_DESCRIPTION = {
    "uz": "⚖️ Monita Bot — biznes uchun qonunchilik monitoringi.\n\n"
          "• Sohangizga tegishli amaldagi qonun hujjatlari ro'yxati\n"
          "• Yangi va o'zgargan hujjatlar haqida avtomatik xabarnoma\n"
          "• AI yordamchi: savolingizga Lex.uz matni asosida javob\n"
          "• Hisobot va litsenziya muddatlari eslatmalari\n\n"
          "Boshlash uchun pastdagi tugmani bosing 👇",
    "ru": "⚖️ Monita Bot — мониторинг законодательства для бизнеса.\n\n"
          "• Перечень действующих актов для вашей сферы\n"
          "• Автоуведомления о новых и изменённых актах\n"
          "• AI-помощник: ответы на основе текстов Lex.uz\n"
          "• Напоминания о сроках отчётов и лицензий\n\n"
          "Нажмите кнопку ниже, чтобы начать 👇",
}
BOT_SHORT = {
    "uz": "Biznes uchun qonunchilik monitoringi: yangi NPA, o'zgarishlar, muddatlar va AI yordamchi.",
    "ru": "Мониторинг законодательства для бизнеса: новые НПА, изменения, сроки и AI-помощник.",
}


def t(key: str, lang: str = "uz", **kw) -> str:
    entry = TEXTS[key]
    s = entry.get(lang) or entry["uz"]
    return s.format(**kw) if kw else s


def all_variants(key: str) -> set[str]:
    return set(TEXTS[key].values())
