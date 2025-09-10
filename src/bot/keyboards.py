"""
Модуль для создания клавиатур и кнопок.
"""

from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def create_main_keyboard():
    """Создает основную клавиатуру с командами"""
    keyboard = [
        [KeyboardButton("📝 Test"), KeyboardButton("📚 Vocabulary")],
        [KeyboardButton("📖 Grammar"), KeyboardButton("💬 Chat")],
        [KeyboardButton("🔥 Motivate"), KeyboardButton("👨‍🏫 Get contact with a teacher")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

def create_test_options_keyboard():
    """Создает клавиатуру для выбора действий с тестом"""
    keyboard = [
        [InlineKeyboardButton("▶️ Продолжить", callback_data="test_continue")],
        [InlineKeyboardButton("🔄 Начать заново", callback_data="test_restart")],
        [InlineKeyboardButton("❌ Отменить", callback_data="test_cancel")]
    ]
    return InlineKeyboardMarkup(keyboard)

def create_answer_keyboard(options):
    """Создает инлайн-клавиатуру с вариантами ответов"""
    keyboard = []
    for i, option in enumerate(options):
        letter = chr(97 + i)  # a, b, c, d
        keyboard.append([InlineKeyboardButton(option, callback_data=f"test_answer_{letter}")])
    return InlineKeyboardMarkup(keyboard)