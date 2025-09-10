"""
Обработчики сообщений и команд для Telegram бота подготовки к ЕГЭ.
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters, CallbackQueryHandler

from .keyboards import create_main_keyboard
from src.llm.service import llm_service
from src.test_manager import test_manager
from src.utils.error_handling import handle_async_error
from src.rag.manager import rag_manager
from src.exercise_manager import exercise_manager
from src.utils.validators import require_test_completion

logger = logging.getLogger(__name__)

# Словарь для хранения истории сообщений пользователей
user_chat_history = {}

def clean_markdown_text(text: str) -> str:
    """Очищает текст от проблемных Markdown символов"""
    return text.replace('*', '•').replace('_', '-').replace('`', '"').replace('[', '(').replace(']', ')')

def reset_exercise_session(user_id: int):
    """Сбрасывает активную сессию упражнений для пользователя"""
    if user_id in exercise_manager.active_exercises:
        del exercise_manager.active_exercises[user_id]
    if user_id in exercise_manager.user_answers:
        del exercise_manager.user_answers[user_id]
    if hasattr(exercise_manager, 'user_current_index') and user_id in exercise_manager.user_current_index:
        del exercise_manager.user_current_index[user_id]

def add_to_chat_history(user_id: int, role: str, content: str):
    """Добавляет сообщение в историю чата пользователя"""
    if user_id not in user_chat_history:
        user_chat_history[user_id] = []
    
    user_chat_history[user_id].append({"role": role, "content": content})
    
    # Ограничиваем историю 20 сообщениями
    if len(user_chat_history[user_id]) > 20:
        user_chat_history[user_id] = user_chat_history[user_id][-20:]

def get_chat_history(user_id: int) -> list:
    """Возвращает историю чата пользователя"""
    return user_chat_history.get(user_id, [])

def clear_chat_history(user_id: int):
    """Очищает историю чата пользователя"""
    if user_id in user_chat_history:
        del user_chat_history[user_id]

async def show_exercise(update: Update, context: ContextTypes.DEFAULT_TYPE, exercise, exercise_index: int, total_exercises: int):
    """Показывает упражнение с кнопками ответов"""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    
    # Создаем клавиатуру с вариантами ответов
    keyboard = []
    session_id = exercise_manager.get_short_session_id(update.effective_user.id)
    for i, option in enumerate(exercise.options):
        letter = chr(65 + i)  # A, B, C, D
        keyboard.append([InlineKeyboardButton(
            f"{letter}. {option}", 
            callback_data=f"ex:{session_id}:{exercise_index}:{letter}"
        )])
    
    # Кнопка завершения только на последнем упражнении
    if exercise_index == total_exercises - 1:
        keyboard.append([InlineKeyboardButton("🏁 Завершить упражнения", callback_data="exercise_finish")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Формируем текст упражнения
    exercise_text = f"""📝 Упражнение {exercise_index + 1} из {total_exercises}

{exercise.question}

Выберите правильный ответ:"""
    
    try:
        # Всегда отправляем новое сообщение вместо редактирования
        if hasattr(update, 'message') and update.message:
            await update.message.reply_text(
                exercise_text,
                reply_markup=reply_markup
            )
        elif hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.message.reply_text(
                exercise_text,
                reply_markup=reply_markup
            )
        else:
            # Fallback для любого другого типа update
            chat_id = update.effective_chat.id
            await context.bot.send_message(
                chat_id=chat_id,
                text=exercise_text,
                reply_markup=reply_markup
            )
    except Exception as e:
        logger.error(f"Error in show_exercise: {e}")
        # Fallback - пытаемся отправить сообщение любым способом
        chat_id = update.effective_chat.id
        await context.bot.send_message(
            chat_id=chat_id,
            text=exercise_text,
            reply_markup=reply_markup
        )

async def show_exercise_results(update: Update, context: ContextTypes.DEFAULT_TYPE, results: dict):
    """Показывает результаты выполнения упражнений"""
    result_text = f"""🎉 *Упражнения завершены!*

📊 *Результаты:*
{results['correct_answers']} из {results['total_questions']} правильных ответов
({results['percentage']:.1f}%)

🌟 *Уровень:* {results['level']}

💡 *Детальный разбор:*"""
    
    # Добавляем детальный разбор каждого упражнения
    for i, result in enumerate(results['results'], 1):
        status = "✅" if result['is_correct'] else "❌"
        result_text += f"\n\n{i}. {status} {result['question']}"
        result_text += f"\nВаш ответ: {result['user_answer'] or 'Не отвечен'}"
        result_text += f"\nПравильный ответ: {result['correct_answer']}"
        if not result['is_correct']:
            result_text += f"\n💡 {result['explanation']}"
    
    result_text += "\n\n🎯 Продолжайте практиковаться для улучшения результатов!"
    
    # Очищаем текст от проблемных символов для Markdown
    clean_result = clean_markdown_text(result_text)
    
    try:
        # Всегда отправляем новое сообщение
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.message.reply_text(
                clean_result,
                parse_mode='Markdown',
                reply_markup=create_main_keyboard()
            )
        elif hasattr(update, 'message') and update.message:
            await update.message.reply_text(
                clean_result,
                parse_mode='Markdown',
                reply_markup=create_main_keyboard()
            )
        else:
            # Fallback
            chat_id = update.effective_chat.id
            await context.bot.send_message(
                chat_id=chat_id,
                text=clean_result,
                parse_mode='Markdown',
                reply_markup=create_main_keyboard()
            )
    except Exception as e:
        logger.error(f"Error in show_exercise_results: {e}")
        # Fallback без Markdown
        chat_id = update.effective_chat.id
        await context.bot.send_message(
            chat_id=chat_id,
            text=clean_result,
            reply_markup=create_main_keyboard()
        )

@handle_async_error
@require_test_completion
async def vocabulary_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды Vocabulary - интерактивные упражнения"""
    user_id = update.effective_user.id
    
    # Сбрасываем предыдущую сессию
    reset_exercise_session(user_id)
    await update.message.reply_text("📚 Создаю персонализированные упражнения по лексике...")
    
    try:
        # Начинаем новую сессию упражнений
        exercises = await exercise_manager.start_exercise_session(user_id, "vocabulary")
        logger.info(f"Created {len(exercises)} vocabulary exercises for user {user_id}")
        
        if not exercises:
            await update.message.reply_text(
                "❌ Не удалось создать упражнения. Попробуйте позже.",
                reply_markup=create_main_keyboard()
            )
            return
        
        # Устанавливаем начальный индекс
        exercise_manager.set_current_exercise_index(user_id, 0)
        
        # Показываем первое упражнение
        await show_exercise(update, context, exercises[0], 0, len(exercises))
        
    except Exception as e:
        logger.error(f"Error in vocabulary command: {e}")
        await update.message.reply_text(
            "❌ Ошибка при создании упражнений. Попробуйте позже.",
            reply_markup=create_main_keyboard()
        )

@handle_async_error
@require_test_completion
async def grammar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды Grammar - интерактивные упражнения"""
    user_id = update.effective_user.id
    
    # Проверяем, есть ли уже активная сессию упражнений
    if exercise_manager.is_exercise_session_active(user_id):
        # Сбрасываем старую сессию и создаем новую
        reset_exercise_session(user_id)
        await update.message.reply_text("📖 Создаю новую сессию упражнений по грамматике...")
    else:
        await update.message.reply_text("📖 Создаю персонализированные упражнения по грамматике...")
    
    try:
        # Начинаем новую сессию упражнений
        exercises = await exercise_manager.start_exercise_session(user_id, "grammar")
        logger.info(f"Created {len(exercises)} grammar exercises for user {user_id}")
        
        if not exercises:
            await update.message.reply_text(
                "❌ Не удалось создать упражнения. Попробуйте позже.",
                reply_markup=create_main_keyboard()
            )
            return
        
        # Устанавливаем начальный индекс и показываем первое упражнение
        exercise_manager.set_current_exercise_index(user_id, 0)
        await show_exercise(update, context, exercises[0], 0, len(exercises))
        
    except Exception as e:
        logger.error(f"Error in grammar command: {e}")
        await update.message.reply_text(
            "❌ Ошибка при создании упражнений. Попробуйте позже.",
            reply_markup=create_main_keyboard()
        )

async def send_question(update: Update, question: dict):
    """Отправляет вопрос с кнопками ответов"""
    message_text = f"❓ Вопрос {question['id']}/25\n\n{question['question']}"
    
    keyboard = test_manager.create_question_keyboard(question)
    
    if hasattr(update, 'callback_query'):
        await update.callback_query.edit_message_text(
            message_text,
            reply_markup=keyboard
        )
    else:
        await update.message.reply_text(
            message_text,
            reply_markup=keyboard
        )

async def show_test_results(update: Update, results: dict):
    """Показывает результаты теста"""
    result_text = f"""🎉 *Тест завершен!*

📊 *Результаты:*
{results['score']} из {results['total_questions']} правильных ответов
({results['percentage']:.1f}%)

🌟 *Сильные стороны:*
{', '.join(results['strengths']) if results['strengths'] else 'Пока не определены'}

📚 *Над чем стоит поработать:*
{', '.join(results['weaknesses']) if results['weaknesses'] else 'Все разделы требуют внимания'}

💡 *Рекомендации:*
1. Регулярно практикуйте слабые разделы
2. Используйте наши тренировки Vocabulary и Grammar
3. Занимайтесь 15-20 минут ежедневно

Результаты сохранены для персональной программы подготовки!"""

    # Отправляем результаты в основном сообщении
    if hasattr(update, 'callback_query'):
        await update.callback_query.message.reply_text(
            result_text,
            parse_mode='Markdown',
            reply_markup=create_main_keyboard()
        )
    else:
        await update.message.reply_text(
            result_text,
            parse_mode='Markdown',
            reply_markup=create_main_keyboard()
        )

@handle_async_error
async def handle_test_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик действий с тестом"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    action = query.data
    
    if action == "test_continue":
        # Продолжаем тест с текущего вопроса
        current_question = test_manager.get_current_question(user_id)
        if current_question:
            await send_question(update, current_question)
        else:
            # Если вопросы закончились, завершаем тест
            results = test_manager.finish_test(user_id)
            await query.edit_message_text(
                "📊 Подводим итоги...",
                reply_markup=None
            )
            await show_test_results(update, results)
    
    elif action == "test_restart":
        # Начинаем новый тест
        if user_id in test_manager.active_tests:
            del test_manager.active_tests[user_id]
        
        # Начинаем тест заново
        success = test_manager.start_test_for_user(user_id)
        if success:
            current_question = test_manager.get_current_question(user_id)
            if current_question:
                await send_question(update, current_question)
            else:
                await query.edit_message_text(
                    "❌ Ошибка при получении вопросов.",
                    reply_markup=create_main_keyboard()
                )
        else:
            await query.edit_message_text(
                "❌ Ошибка при запуске теста. Попробуйте позже.",
                reply_markup=create_main_keyboard()
            )
    
    elif action == "test_cancel":
        # Отменяем тест
        if user_id in test_manager.active_tests:
            del test_manager.active_tests[user_id]
        await query.edit_message_text(
            "❌ Тест отменен.",
            reply_markup=create_main_keyboard()
        )

@handle_async_error
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start - приветственное сообщение"""
    user = update.effective_user
    welcome_text = f"""🎓 Приветствуем, {user.first_name}!

Я твой персональный ассистент для подготовки к ЕГЭ по английскому языку!

📚 Выбери нужный раздел:
• 📝 Test - Диагностический тест ЕГЭ (25 заданий)
• 📚 Vocabulary - Тренировка лексики (5 упражнений)
• 📖 Grammar - Тренировка грамматики (5 упражнений)
• 💬 Chat - Неформальный чат на английском с AI-другом
• 🔥 Motivate - Мотивационные фразы и поддержка
• 👨‍🏫 Get contact with a teacher - Связь с преподавателем
• 🔄 Сбросить активные упражнения

✨ Подписывайся на наш канал: @ezzy_breezy для полезных материалов!
"""
    
    await update.message.reply_text(welcome_text, reply_markup=create_main_keyboard())

@handle_async_error
async def test_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды Test - запуск/продолжение теста"""
    user_id = update.effective_user.id
    
    # Если есть активный тест - предлагаем продолжить или начать заново
    if user_id in test_manager.active_tests:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("▶️ Продолжить тест", callback_data="test_continue")],
            [InlineKeyboardButton("🔄 Начать новый тест", callback_data="test_restart")],
            [InlineKeyboardButton("❌ Отменить тест", callback_data="test_cancel")]
        ])
        
        await update.message.reply_text(
            "📝 У вас есть незавершенный тест. Что хотите сделать?",
            reply_markup=keyboard
        )
        return
    
    # Иначе начинаем новый тест
    await show_test_intro(update)

async def show_test_intro(update: Update):
    """Показывает введение к тесту"""
    test_info = """📝 *Диагностический тест ЕГЭ по английскому*

Тест состоит из 25 вопросов и проверяет 5 ключевых навыков:

🎯 *ГРАММАТИКА* (8 вопросов)
📝 *ЛЕКСИКА* (8 вопросов)  
📖 *ПОНИМАНИЕ ТЕКСТА* (4 вопроса)
✍️ *ПИСЬМО* (2 задания)
📝 *ЭССЕ* (3 задания)

⏰ Время прохождения: 20-25 минут
📊 Результат: персональный план подготовки

*Готовы начать?* Нажмите 'Начать тест'👇"""
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Начать тест", callback_data="start_test")]
    ])
    
    if hasattr(update, 'message'):
        await update.message.reply_text(
            test_info,
            parse_mode='Markdown',
            reply_markup=keyboard
        )
    else:
        await update.callback_query.message.reply_text(
            test_info,
            parse_mode='Markdown',
            reply_markup=keyboard
        )

@handle_async_error
async def handle_test_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик начала теста"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # Начинаем тест
    success = test_manager.start_test_for_user(user_id)
    if not success:
        await query.edit_message_text(
            "❌ Ошибка при запуске теста. Попробуйте позже.",
            reply_markup=create_main_keyboard()
        )
        return
    
    # Отправляем первый вопрос
    current_question = test_manager.get_current_question(user_id)
    if current_question:
        await send_question(update, current_question)
    else:
        await query.edit_message_text(
            "❌ Ошибка при получении вопросов.",
            reply_markup=create_main_keyboard()
        )

@handle_async_error
async def handle_test_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ответов на вопросы теста"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    answer = query.data.replace("test_answer_", "")
    
    # Обрабатываем ответ
    test_manager.process_answer(user_id, answer)
    
    # Проверяем завершен ли тест
    if test_manager.is_test_completed(user_id):
        results = test_manager.finish_test(user_id)
        # Удаляем клавиатуру и показываем результаты
        await query.edit_message_text(
            "📊 Подводим итоги...",
            reply_markup=None
        )
        await show_test_results(update, results)
    else:
        # Отправляем следующий вопрос
        next_question = test_manager.get_current_question(user_id)
        if next_question:
            await send_question(update, next_question)

@handle_async_error
async def chat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды Chat - активация промпта chat"""
    user_id = update.effective_user.id
    context.user_data['mode'] = 'chat'
    
    # Очищаем историю чата при активации режима
    clear_chat_history(user_id)
    
    await update.message.reply_text(
        "💬 Chat with an AI Friend is ready!\n\n"
        "Now you can practice your English in a friendly and relaxed way! 🎭\n"
        "You write to me in English, and I will answer like a good friend.\n\n"
        "Some ideas for our chat:\n"
        "• How was your day?\n"
        "• Plans for the weekend\n"
        "• Your favorite movies or books\n"
        "• Your hobbies and interests\n\n"
        "Don't be shy – let's practice your English together! 🚀",
        reply_markup=create_main_keyboard()
    )

@handle_async_error
async def motivate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды Motivate - генерация мотивации по промпту"""
    await update.message.reply_text("🔥 Генерирую мотивацию...")
    
    try:
        # Генерируем мотивацию через LLM с промптом motivate
        motivation = await llm_service.generate_content("motivate")
        
        # Отправляем мотивацию
        await update.message.reply_text(
            motivation,
            reply_markup=create_main_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Error generating motivation: {e}")
        # Fallback - стандартные мотивационные фразы
        await update.message.reply_text(
            "✨ Ты делаешь отличные успехи! Каждое занятие приближает тебя к цели! 💪\n"
            "Не сдавайся - у тебя все получится! 🚀",
            reply_markup=create_main_keyboard()
        )

@handle_async_error
async def teacher_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды Teacher - связь с преподавателем"""
    teacher_info = """👨‍🏫 Связь с преподавателем

🎓 Онлайн-курсы подготовки к ЕГЭ:
• Индивидуальные занятия
• Разбор всех разделов экзамена  
• Персональный план подготовки
• Регулярные пробные тесты

📞 Контакты:
• Email: re.nailevna@mail.ru
• Телеграм: @MellinaRina

📢 Подписывайся на наш канал:
EAZY BREEZY | Английский язык ЕГЭ 2026
https://t.me/ezzy_breezy

💡 Первая консультация - бесплатно!"""
    
    await update.message.reply_text(
        teacher_info,
        reply_markup=create_main_keyboard()
    )

@handle_async_error
async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на кнопки главного меню"""
    text = update.message.text
    
    if text == "📝 Test":
        await test_command(update, context)
    elif text == "📚 Vocabulary":
        await vocabulary_command(update, context)
    elif text == "📖 Grammar":
        await grammar_command(update, context)
    elif text == "💬 Chat":
        await chat_command(update, context)
    elif text == "🔥 Motivate":
        await motivate_command(update, context)
    elif text == "👨‍🏫 Get contact with a teacher":
        await teacher_command(update, context)
    elif text == "🔄 Сбросить активные упражнения":
        await reset_exercises_command(update, context)

@handle_async_error
async def reset_exercises_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды сброса активных упражнений"""
    user_id = update.effective_user.id
    
    if exercise_manager.is_exercise_session_active(user_id):
        reset_exercise_session(user_id)
        await update.message.reply_text(
            "🔄 Активная сессия упражнений сброшена!\n"
            "Теперь вы можете начать новую сессию.",
            reply_markup=create_main_keyboard()
        )
    else:
        await update.message.reply_text(
            "ℹ️ У вас нет активной сессии упражнений.",
            reply_markup=create_main_keyboard()
        )

@handle_async_error
async def handle_exercise_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ответов на упражнения"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    # Ожидаемый формат: ex:{session_id6}:{index}:{letter}
    parts = query.data.split(':')
    if len(parts) != 4 or parts[0] != 'ex':
        logger.error(f"Invalid callback data: {query.data}")
        await query.message.reply_text(
            "❌ Ошибка формата данных.",
            reply_markup=create_main_keyboard()
        )
        return

    session_id = parts[1]
    idx_str = parts[2]
    answer = parts[3]
    try:
        selected_index = int(idx_str)
    except ValueError:
        logger.error(f"Invalid index in callback: {idx_str}")
        await query.message.reply_text(
            "❌ Ошибка индекса упражнения.",
            reply_markup=create_main_keyboard()
        )
        return

    # Проверяем, что сессия актуальна
    current_session = exercise_manager.get_short_session_id(user_id)
    if not current_session or session_id != current_session:
        logger.warning(f"Stale or invalid session in callback: {session_id} != {current_session}")
        await query.message.reply_text(
            "ℹ️ Эта сессия упражнений уже завершена или устарела. Начните новую.",
            reply_markup=create_main_keyboard()
        )
        return
    
    logger.info(f"User {user_id} answered exercise index {selected_index} with answer {answer}")
    
    # Проверяем есть ли активные упражнения у пользователя
    if user_id not in exercise_manager.active_exercises:
        logger.error(f"No active exercises for user {user_id}")
        await query.message.reply_text(
            "❌ Нет активной сессии упражнений.",
            reply_markup=create_main_keyboard()
        )
        return
    
    exercises = exercise_manager.active_exercises[user_id]
    # Доверяем индексу из коллбэка, чтобы исключить рассинхрон
    current_index = selected_index
    
    # Проверяем, что индекс в пределах диапазона
    if current_index >= len(exercises):
        logger.error(f"Current index {current_index} out of range for {len(exercises)} exercises")
        await query.message.reply_text(
            "❌ Ошибка: индекс упражнения вне диапазона.",
            reply_markup=create_main_keyboard()
        )
        return
    
    current_exercise = exercises[current_index]
    
    # Проверяем, что ID совпадает
    #if str(current_exercise.exercise_id) != str(exercise_id):
    #    logger.error(f"Exercise ID mismatch: current {current_exercise.exercise_id} vs callback {exercise_id}")
    #    await query.message.reply_text(
    #        "❌ Несоответствие ID упражнения.",
    #        reply_markup=create_main_keyboard()
    #    )
    #    return
    
    # Сохраняем ответ пользователя
    # Формируем упражнение ID коротко: subject_user_index
    short_exercise_id = f"{current_exercise.subject}_{user_id}_{current_index}"
    # Защита от повторных нажатий на ту же кнопку
    if user_id in exercise_manager.user_answers and short_exercise_id in exercise_manager.user_answers[user_id]:
        logger.info(f"Duplicate answer ignored for {short_exercise_id}")
        await query.answer()
        return
    try:
        exercise_manager.submit_answer(user_id, short_exercise_id, answer)
        logger.info(f"Answer submitted successfully for exercise {short_exercise_id}")
    except Exception as e:
        logger.error(f"Error submitting answer: {e}")
        await query.message.reply_text(
            "❌ Ошибка при сохранении ответа.",
            reply_markup=create_main_keyboard()
        )
        return
    
    # Отмечаем ответ как правильный/неправильный
    is_correct = (answer.upper() == current_exercise.correct_answer.upper())
    status_icon = "✅" if is_correct else "❌"
    
    #try:
    #    await query.edit_message_text(
    #        f"{status_icon} Ответ принят: {answer.upper()}\n\nПереходим к следующему вопросу...",
    #        reply_markup=None
    #    )
    #except Exception as e:
    #    logger.error(f"Error editing message: {e}")
    #    await query.message.reply_text(
    #        f"{status_icon} Ответ принят: {answer.upper()}\n\nПереходим к следующему вопросу..."
    #    )
    
    # Пытаемся снять клавиатуру с предыдущего сообщения, чтобы избежать повторных нажатий
    try:
        await query.edit_message_text(
            f"Ответ принят: {answer.upper()}",
            reply_markup=None
        )
    except Exception as e:
        logger.debug(f"Could not edit message to acknowledge answer: {e}")

    # Устанавливаем следующий индекс детерминированно
    next_index = current_index + 1
    exercise_manager.set_current_exercise_index(user_id, next_index)
    
    # Проверяем, есть ли следующее упражнение
    if next_index < len(exercises):
        # Показываем следующее упражнение отдельным сообщением
        next_exercise = exercises[next_index]
        logger.info(f"Showing next exercise {next_index}: {next_exercise.exercise_id}")
        await show_exercise(update, context, next_exercise, next_index, len(exercises))
    else:
        # Это последнее упражнение, завершаем сессию
        logger.info("Last exercise completed, finishing session")
        try:
            results = exercise_manager.finish_exercise_session(user_id)
            # Сбрасываем индекс при завершении
            exercise_manager.reset_current_index(user_id)
            await show_exercise_results(update, context, results)
        except Exception as e:
            logger.error(f"Error finishing exercise session: {e}")
            await query.message.reply_text(
                "❌ Ошибка при завершении упражнений.",
                reply_markup=create_main_keyboard()
            )

@handle_async_error
async def handle_exercise_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик завершения упражнений"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    try:
        # Завершаем сессию упражнений
        results = exercise_manager.finish_exercise_session(user_id)
        
        if "error" in results:
            await query.message.reply_text(
                "❌ Ошибка при завершении упражнений.",
                reply_markup=create_main_keyboard()
            )
            return
        
        # Показываем результаты
        await show_exercise_results(update, context, results)
        
    except Exception as e:
        logger.error(f"Error in handle_exercise_finish: {e}")
        await query.message.reply_text(
            "❌ Ошибка при завершении упражнений. Попробуйте еще раз.",
            reply_markup=create_main_keyboard()
        )

@handle_async_error
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик обычных текстовых сообщений"""
    user_message = update.message.text
    user_id = update.effective_user.id
    
    # Если это команда из кнопок главного меню
    if user_message in ["📝 Test", "📚 Vocabulary", "📖 Grammar", "💬 Chat", "🔥 Motivate", "👨‍🏫 Get contact with a teacher", "🔄 Сбросить активные упражнения"]:
        await handle_buttons(update, context)
        return
    
    # Определяем режим работы
    mode = context.user_data.get('mode', 'tutor')
    
    if mode == 'chat':
        # Режим чата с AI-другом на английском - используем промпт chat
        try:
            # Добавляем сообщение пользователя в историю
            add_to_chat_history(user_id, "user", user_message)
            
            await update.message.reply_text("💬 Обрабатываю сообщение...")
            
            # Получаем историю чата
            chat_history = get_chat_history(user_id)
            
            # Формируем контекст с историей
            context_with_history = f"История чата:\n"
            for msg in chat_history[:-1]:  # Исключаем текущее сообщение
                context_with_history += f"{msg['role']}: {msg['content']}\n"
            context_with_history += f"\nТекущее сообщение пользователя: {user_message}"
            
            response = await llm_service.generate_content("chat", context_with_history)
            
            # Добавляем ответ бота в историю
            add_to_chat_history(user_id, "assistant", response)
            
            await update.message.reply_text(response, reply_markup=create_main_keyboard())
        except Exception as e:
            logger.error(f"Error in chat mode: {e}")
            await update.message.reply_text(
                "😊 Nice to chat with you! How was your day?",
                reply_markup=create_main_keyboard()
            )
    else:
        # Режим ИИ-помощника (по умолчанию) - используем промпт tutor
        try:
            # Добавляем сообщение пользователя в историю
            add_to_chat_history(user_id, "user", user_message)
            
            await update.message.reply_text("🤔 Думаю над ответом...")
            
            # Получаем историю чата
            chat_history = get_chat_history(user_id)
            
            # Формируем контекст с историей
            context_with_history = f"История чата:\n"
            for msg in chat_history[:-1]:  # Исключаем текущее сообщение
                context_with_history += f"{msg['role']}: {msg['content']}\n"
            context_with_history += f"\nТекущее сообщение пользователя: {user_message}"
            
            response = await llm_service.generate_content("tutor", context_with_history)
            
            # Добавляем ответ бота в историю
            add_to_chat_history(user_id, "assistant", response)
            
            await update.message.reply_text(response, reply_markup=create_main_keyboard())
        except Exception as e:
            logger.error(f"Error in tutor mode: {e}")
            await update.message.reply_text(
                "📚 Я помогу тебе с подготовкой к ЕГЭ по английскому!\n"
                "Задавай вопросы по грамматике, лексике или структуре экзамена.\n\n"
                "Или выбери одну из команд в меню 👆",
                reply_markup=create_main_keyboard()
            )

def setup_handlers(application):
    """Настройка всех обработчиков для приложения"""
    
    # Команда /start
    application.add_handler(CommandHandler("start", start))
    
    # Обработчики кнопок главного меню
    application.add_handler(MessageHandler(
        filters.Text([
            "📝 Test", "📚 Vocabulary", "📖 Grammar", 
            "💬 Chat", "🔥 Motivate", "👨‍🏫 Get contact with a teacher",
            "🔄 Сбросить активные упражнения"
        ]), 
        handle_buttons
    ))
    
    # СНАЧАЛА обработчики упражнений (более специфичные)
    application.add_handler(CallbackQueryHandler(handle_exercise_answer, pattern="^ex:"))
    application.add_handler(CallbackQueryHandler(handle_exercise_finish, pattern="^exercise_finish$"))
    
    # ПОТОМ обработчики теста
    application.add_handler(CallbackQueryHandler(handle_test_start, pattern="^start_test$"))
    application.add_handler(CallbackQueryHandler(handle_test_actions, pattern="^test_(continue|restart|cancel)$"))
    application.add_handler(CallbackQueryHandler(handle_test_answer, pattern="^test_answer_"))
    
    # Обработчик обычных текстовых сообщений
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, 
        handle_message
    ))
    
    logger.info("✅ All handlers registered successfully")