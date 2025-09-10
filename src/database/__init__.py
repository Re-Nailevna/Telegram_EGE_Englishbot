"""
Пакет для работы с данными пользователей.
"""

from .manager import database_manager, DatabaseManager
from .models import User, TestResult  # УБИРАЕМ ErrorAnalysis

__all__ = ['database_manager', 'DatabaseManager', 'User', 'TestResult']