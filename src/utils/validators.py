"""
Упрощенные валидаторы без циклических импортов.
"""

import logging
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

def require_test_completion(func):
    """Декоратор для проверки прохождения теста"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        # Простая проверка без сложных импортов
        from src.bot.keyboards import create_main_keyboard
        
        user_id = update.effective_user.id
        
        try:
            # Пытаемся проверить активный тест
            from src.test_manager import test_manager
            if user_id in test_manager.active_tests:
                message_text = """⏸️ Сначала завершите текущий тест!
                
Вернитесь к тесту через меню '📝 Test'"""
                await update.message.reply_text(message_text, reply_markup=create_main_keyboard())
                return None
        except:
            pass
        
        try:
            # Пытаемся проверить завершенность теста
            from src.database.manager import database_manager
            if not database_manager.has_completed_test(user_id):
                # Дополнительная проверка: есть ли результаты тестов в файле
                import json
                from pathlib import Path
                test_file = Path(f"data/tests/user_{user_id}.json")
                
                if test_file.exists():
                    try:
                        with open(test_file, 'r', encoding='utf-8') as f:
                            test_results = json.load(f)
                        if test_results and len(test_results) > 0:
                            # У пользователя есть результаты тестов, но флаг не установлен
                            # Устанавливаем флаг автоматически
                            logger.info(f"Auto-fixing test completion flag for user {user_id}")
                            database_manager.mark_test_completed(user_id)
                        else:
                            message_text = """📝 Сначала пройдите диагностический тест!
                            
Нажмите '📝 Test' чтобы начать!"""
                            await update.message.reply_text(message_text, reply_markup=create_main_keyboard())
                            return None
                    except Exception as file_error:
                        logger.error(f"Error reading test file for user {user_id}: {file_error}")
                        message_text = """📝 Сначала пройдите диагностический тест!
                        
Нажмите '📝 Test' чтобы начать!"""
                        await update.message.reply_text(message_text, reply_markup=create_main_keyboard())
                        return None
                else:
                    message_text = """📝 Сначала пройдите диагностический тест!
                    
Нажмите '📝 Test' чтобы начать!"""
                    await update.message.reply_text(message_text, reply_markup=create_main_keyboard())
                    return None
        except Exception as e:
            # Логируем ошибку для отладки
            logger.error(f"Error checking test completion for user {user_id}: {e}")
            # Если не удалось проверить, пропускаем проверку
            pass
        
        return await func(update, context, *args, **kwargs)
    return wrapper