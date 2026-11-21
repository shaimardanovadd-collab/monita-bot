"""Barcha matnlar (o'zbek / rus) va faoliyat turlari."""

LANGS = ("uz", "ru")
LINE = "━━━━━━━━━━━━━━━━"

# Faoliyat turlari: kalit -> (emoji, {til: nom})
SECTORS = {
    "savdo": ("🏪", {"uz": "Savdo (ulgurji / chakana)", "ru": "Торговля (опт / розница)"}),
    "import": ("📦", {"uz": "Import / eksport", "ru": "Импорт / экспорт"}),
    "ovqat": ("🍽", {"uz": "Umumiy ovqatlanish", "ru": "Общепит (кафе, рестораны)"}),
    "xizmat": ("⚙️", {"uz": "Xizmat ko'rsatish", "ru": "Услуги"}),
    "ishlab": ("🏭", {"uz": "Ishlab chiqarish", "ru": "Производство"}),
    "qurilish": ("🏗", {"uz": "Qurilish", "ru": "Строительство"}),
    "boshqa": ("🧩", {"uz": "Boshqa", "ru": "Другое"}),
}


def sector_name(key: str, lang: str = "uz") -> str:
    emoji, names = SECTORS[key]
    return f"{emoji} {names.get(lang, names['uz'])}"


def sector_names(keys: list[str], lang: str = "uz") -> str:
    names = [SECTORS[k][1].get(lang, SECTORS[k][1]["uz"]) for k in keys if k in SECTORS]
    return ", ".join(names) if names else "—"


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
        "uz": "🤖 <b>AI yordamchi</b> · Gemma\n" + LINE + "\n"
              "Biznesingizga oid qonunchilik bo'yicha savol yozing.\n\n"
              "💡 <i>Masalan: «Litsenziya olish tartibi qanday?»</i>\n\n"
              "📚 Javob {acts} ta amaldagi akt va bot yangiliklariga asoslanadi.\n"
              "⚠️ Bu yuridik maslahat emas — rasmiy matnni Lex.uz da tekshiring.",
        "ru": "🤖 <b>AI-помощник</b> · Gemma\n" + LINE + "\n"
              "Задайте вопрос о законодательстве для вашего бизнеса.\n\n"
              "💡 <i>Например: «Как получить лицензию?»</i>\n\n"
              "📚 Ответ основан на {acts} действующих актах и новостях бота.\n"
              "⚠️ Это не юридическая консультация — сверяйте текст на Lex.uz.",
    },
    "ai_new": {"uz": "🔄 Yangi suhbat. Savolingizni yozing.", "ru": "🔄 Новый диалог. Задайте вопрос."},
    "ai_off": {"uz": "AI yordamchi hali sozlanmagan.", "ru": "AI-помощник ещё не настроен."},
    "ai_text_only": {"uz": "Faqat matnli savollarni qabul qilaman.", "ru": "Я принимаю только текстовые вопросы."},
    "ai_sources": {"uz": "📚 Manbalar:", "ru": "📚 Источники:"},
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
              "📰 Yangilik — admin yangilik e'lon qilganda\n"
              "⏰ Eslatma — muhim muddat yaqinlashganda\n"
              "🤖 AI — namunaviy savolga javob va manbalar",
        "ru": "🧪 <b>Демо-режим</b>\n" + LINE + "\nПроверьте, как работает бот: нажмите кнопку — "
              "уведомление придёт <b>только вам</b>, как настоящее.\n\n"
              "📚 Новый НПА — когда в вашей сфере появляется новый акт\n"
              "✏️ Изменение — когда текст акта на Lex.uz обновился\n"
              "📰 Новость — когда админ публикует новость\n"
              "⏰ Напоминание — когда приближается важный срок\n"
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
