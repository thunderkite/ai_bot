import os
import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    filters, 
    ContextTypes, 
    CallbackQueryHandler
)
from google.genai import Client
from google.genai import types

TELEGRAM_TOKEN = "8488492631:AAEBdYI4-gkLcsu-y2c0iFfFeA_Z0mIEfWg"
GEMINI_API_KEY = "AIzaSyD2qNAkTphvy1jC601qBhn1soJQGbDNuE4"

# Список доступных тем
AVAILABLE_TOPICS = ["Python", "Финансы", "Психология", "Астрономия", "История"]

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Хранилище состояния пользователя: {user_id: {'topic': 'Python', 'level': 'новичок', 'day': 1, 'mode': 'lesson'}}
user_data = {}

# --- 2. ИНИЦИАЛИЗАЦИЯ GEMINI ---

gemini_client = None
try:
    # Инициализация клиента Gemini с ключом API
    gemini_client = Client(api_key=GEMINI_API_KEY)
    logger.info("Gemini Client успешно инициализирован.")
except Exception as e:
    logger.error(f"Ошибка инициализации Gemini. Проверьте GEMINI_API_KEY: {e}")

# --- 3. ФУНКЦИИ-ОБРАБОТЧИКИ КОМАНД ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет приветственное сообщение и предлагает выбрать тему с помощью клавиатуры."""
    
    # Создаем клавиатуру с темами (постоянная клавиатура ответов)
    keyboard_buttons = [[KeyboardButton(topic)] for topic in AVAILABLE_TOPICS]
    reply_markup = ReplyKeyboardMarkup(
        keyboard_buttons, 
        one_time_keyboard=False, 
        resize_keyboard=True
    )
    
    welcome_message = (
        "👋 Привет! Я — твой ИИ-наставник для мини-курсов.\n\n"
        "**Выбери интересующую тебя тему** на клавиатуре ниже, чтобы начать курс.\n"
    )
    
    await update.message.reply_text(welcome_message, reply_markup=reply_markup, parse_mode="Markdown")

async def get_lesson(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Генерирует ежедневный урок с помощью Gemini."""
    
    # Определяем, откуда пришел вызов: от команды /lesson или от кнопки Callback
    if update.callback_query:
        user_id = update.callback_query.from_user.id
        await update.callback_query.answer()
    else:
        user_id = update.effective_user.id
        
    if user_id not in user_data or 'topic' not in user_data[user_id]:
        await update.effective_message.reply_text("Сначала выбери тему на клавиатуре или используй /start.")
        return
        
    # Сбрасываем режим, если пользователь переходит к уроку
    user_data[user_id]['mode'] = 'lesson'
    
    topic = user_data[user_id]['topic']
    day = user_data[user_id]['day']
    level = user_data[user_id]['level']

    # Системный промпт для Gemini
    system_prompt = (
        "Ты — профессиональный наставник, который ведет короткий, ежедневный, "
        "адаптивный курс в формате 'Мини-курс от ИИ'. "
        "Каждый урок должен быть содержательным, но очень кратким (не более 500 символов). "
        "В конце урока обязательно задай 1-2 вопроса по материалу и приведи 1 краткий пример. "
        "Используй Markdown для форматирования: жирный шрифт, списки, эмодзи."
    )
    
    # Запрос к Gemini
    prompt = (
        f"Создай 'Урок Дня {day}' по теме **'{topic}'** для уровня **'{level}'**. "
        "Включи вопросы для самопроверки и один короткий практический пример. "
        "Оформи ответ как урок для отправки в Telegram."
    )
    
    try:
        if not gemini_client:
             await update.effective_message.reply_text("Ошибка: Gemini Client не инициализирован.")
             return

        response = gemini_client.models.generate_content(
            model='gemini-2.5-flash', 
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
            )
        )
        
        lesson_text = response.text
        
        # 2. Создаем Инлайн-клавиатуру для урока
        keyboard = [
            [
                InlineKeyboardButton(f"Продолжить (День {day+1}) ➡️", callback_data="next_lesson"),
                InlineKeyboardButton("Задать вопрос по уроку ❓", callback_data="ask_question")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Отправляем ответ пользователю с клавиатурой
        await update.effective_message.reply_text(
            f"**💡 {topic} | День {day}**\n\n"
            f"{lesson_text}",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
        
        # НЕ увеличиваем день здесь - это будет сделано при нажатии кнопки "Продолжить"
        
    except Exception as e:
        logger.error(f"Ошибка Gemini API: {e}")
        await update.effective_message.reply_text("Произошла ошибка при генерации урока. Попробуй позже.")

# --- 4. ОБРАБОТЧИКИ КЛАВИАТУР И ТЕКСТА ---

async def handle_topic_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает выбор темы с клавиатуры."""
    user_id = update.effective_user.id
    text = update.message.text
    
    if text in AVAILABLE_TOPICS:
        topic = text
        # Сохраняем данные пользователя: Тема, Уровень, День (сброс)
        user_data[user_id] = {'topic': topic, 'level': 'новичок', 'day': 1, 'mode': 'lesson'}
        
        await update.message.reply_text(
            f"Отлично! Твоя тема: **{topic}**. Твой курс начинается с **Дня 1**.\n\n"
            f"Нажми /lesson, чтобы получить первый урок.",
            parse_mode="Markdown"
        )
    elif user_id in user_data and user_data[user_id].get('mode') == 'Q&A':
        # Если пользователь в режиме вопросов (Q&A)
        await handle_qa_message(update, context)
    else:
        # Если это не тема и не режим Q&A, можно игнорировать или отвечать заглушкой
        await update.message.reply_text("Пожалуйста, выберите тему на клавиатуре или используйте /start. Чтобы начать урок, используйте /lesson.")

async def handle_qa_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отвечает на вопрос пользователя в режиме Q&A, используя Gemini."""
    user_id = update.effective_user.id
    question = update.message.text
    topic = user_data[user_id]['topic']

    prompt = (
        f"Ты — дружелюбный наставник по курсу '{topic}'. Ответь на следующий вопрос пользователя "
        f"кратко и по существу, используя информацию по этой теме: {question}"
    )

    try:
        if not gemini_client:
             await update.message.reply_text("Ошибка: Gemini Client не инициализирован.")
             return

        response = gemini_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        await update.message.reply_text(f"**Ответ ИИ:**\n\n{response.text}", parse_mode="Markdown")
        await update.message.reply_text("Чтобы вернуться к урокам, введите /lesson.")
        
    except Exception as e:
        logger.error(f"Ошибка Q&A с Gemini: {e}")
        await update.message.reply_text("Произошла ошибка при ответе на вопрос.")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает нажатия на инлайн-кнопки."""
    query = update.callback_query
    await query.answer() # Убираем часы загрузки
    
    data = query.data
    user_id = query.from_user.id

    if user_id not in user_data:
        # Редактируем сообщение, чтобы избежать повторных нажатий
        await query.edit_message_text("Пожалуйста, начни с /start.")
        return

    if data == "next_lesson":
        # Увеличиваем день перед переходом к следующему уроку
        user_data[user_id]['day'] += 1
        # Убираем старую клавиатуру и переходим к следующему уроку
        await query.edit_message_text(f"Загружаю урок **День {user_data[user_id]['day']}**...", parse_mode="Markdown")
        await get_lesson(update, context) # Вызываем get_lesson, передавая update
    
    elif data == "ask_question":
        # Переводим пользователя в режим вопросов (Q&A)
        user_data[user_id]['mode'] = 'Q&A'
        # Отправляем новое сообщение вместо редактирования старого, чтобы урок остался видимым
        await query.message.reply_text(
            "**❓ Режим вопросов (Q&A) активирован!**\n\n"
            "Напиши свой вопрос по уроку или теме. Я отвечу с помощью ИИ.\n"
            "Чтобы вернуться к урокам, введи /lesson.",
            parse_mode="Markdown"
        )

# --- 5. ФУНКЦИЯ MAIN ---

def main() -> None:
    """Запуск бота."""
    
    # Создание Application и передача токена
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Добавление обработчиков
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("lesson", get_lesson))
    
    # Добавляем обработчик для инлайн-кнопок
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Обработчик текстовых сообщений (для выбора темы и Q&A)
    # Важно: он должен стоять после всех CommandHandler'ов
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_topic_selection))
    
    # Запуск бота
    logger.info("Бот запущен и опрашивает Telegram...")
    application.run_polling(poll_interval=3)

if __name__ == "__main__":
    main()