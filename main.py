import asyncio
import logging
import os
import sys
from dotenv import load_dotenv

# Загружаем .env файл
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main():
    """Синхронная функция запуска"""
    from telegram.ext import Application
    from src.bot.handlers import setup_handlers
    
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    
    if not TELEGRAM_TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN not found")
        return
    
    print("Starting bot...")
    
    # Создаем application
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Настраиваем обработчики
    setup_handlers(application)
    
    print("Bot started! Press Ctrl+C to stop.")
    
    # Запускаем бота (синхронно)
    try:
        application.run_polling(
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query"]
        )
    except KeyboardInterrupt:
        print("\nBot stopped by user")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()