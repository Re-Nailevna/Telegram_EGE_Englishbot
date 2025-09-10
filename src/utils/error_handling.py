"""
Минимальная обработка ошибок.
"""

import logging

logger = logging.getLogger(__name__)

def handle_async_error(func):
    """Простой декоратор для обработки ошибок"""
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {e}")
    return wrapper

def setup_error_handling(application):
    """Простая настройка обработки ошибок"""
    async def error_handler(update, context):
        logger.error(f"Error: {context.error}")
    
    application.add_error_handler(error_handler)