"""
Менеджер для работы с JSON базой данных пользователей.
"""

import json
from pathlib import Path
from typing import Optional
from datetime import datetime
from .models import User

class DatabaseManager:
    """Менеджер для работы с JSON базой данных пользователей."""
    
    def __init__(self):
        self.data_dir = Path("data/users")
        self.data_dir.mkdir(parents=True, exist_ok=True)
    
    def get_user(self, user_id: int) -> User:
        """Получает пользователя по ID, создает нового если не существует."""
        user_file = self.data_dir / f"{user_id}.json"
        
        if user_file.exists():
            try:
                with open(user_file, 'r', encoding='utf-8') as f:
                    user_data = json.load(f)
                return User.from_dict(user_data)
            except (json.JSONDecodeError, FileNotFoundError) as e:
                print(f"Error loading user {user_id}: {e}")
                return User(user_id=user_id)
        
        return User(user_id=user_id)
    
    def save_user(self, user: User):
        """Сохраняет пользователя в JSON файл."""
        try:
            user_file = self.data_dir / f"{user.user_id}.json"
            with open(user_file, 'w', encoding='utf-8') as f:
                json.dump(user.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving user {user.user_id}: {e}")
    
    def user_exists(self, user_id: int) -> bool:
        """Проверяет существует ли пользователь."""
        user_file = self.data_dir / f"{user_id}.json"
        return user_file.exists()
    
    def mark_test_completed(self, user_id: int):
        """Отмечает что пользователь прошел тест"""
        try:
            user = self.get_user(user_id)
            user.has_completed_test = True
            user.last_test_date = datetime.now()
            self.save_user(user)
            return True
        except Exception as e:
            print(f"Error marking test as completed: {e}")
            return False
    
    def has_completed_test(self, user_id: int) -> bool:
        """Проверяет проходил ли пользователь тест"""
        try:
            user = self.get_user(user_id)
            return user.has_completed_test
        except Exception as e:
            print(f"Error checking test completion: {e}")
            return False

# Глобальный экземпляр менеджера
database_manager = DatabaseManager()