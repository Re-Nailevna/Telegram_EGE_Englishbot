"""
Конфигурация приложения с поддержкой .env файла.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Загружаем переменные из .env файла
load_dotenv()

class Config:
    # Telegram Bot Token
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    
    # Yandex Cloud API
    YA_API_KEY = os.getenv("YA_API_KEY")
    YA_FOLDER_ID = os.getenv("YA_FOLDER_ID")
    YA_MODEL = f"gpt://{YA_FOLDER_ID}/yandexgpt-lite" if YA_FOLDER_ID else None
    YA_BASE_URL = "https://llm.api.cloud.yandex.net/v1"
    
    # Пути
    BASE_DIR = Path(__file__).parent.parent
    DATA_DIR = BASE_DIR / "data"
    PROMPTS_DIR = BASE_DIR / "src" / "llm" / "prompts"
    
    # Настройки
    MAX_HISTORY_LENGTH = 10
    REQUEST_TIMEOUT = 30
    MAX_MESSAGE_LENGTH = 4000
    
    @classmethod
    def validate(cls):
        """Проверяет наличие всех необходимых переменных окружения"""
        missing_vars = []
        
        if not cls.TELEGRAM_TOKEN:
            missing_vars.append("TELEGRAM_BOT_TOKEN")
        
        if not cls.YA_API_KEY:
            missing_vars.append("YA_API_KEY")
        
        if not cls.YA_FOLDER_ID:
            missing_vars.append("YA_FOLDER_ID")
        
        if missing_vars:
            raise ValueError(
                f"Отсутствуют обязательные переменные окружения: {', '.join(missing_vars)}\n"
                "Убедитесь, что файл .env существует и содержит все необходимые переменные."
            )
        
        # Дополнительная проверка формата токена
        if cls.TELEGRAM_TOKEN and not cls.TELEGRAM_TOKEN.startswith(''):
            print("⚠️  Предупреждение: TELEGRAM_BOT_TOKEN может быть в неправильном формате")

# Валидируем конфигурацию при импорте
Config.validate()