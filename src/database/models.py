"""
Модели данных для хранения информации о пользователях.
"""

from typing import List, Dict, Optional, Literal
from datetime import datetime
from pydantic import BaseModel, Field
import json

class TestAnswer(BaseModel):
    """Модель ответа на вопрос теста"""
    question_id: int
    user_answer: str
    correct_answer: str
    is_correct: bool
    time_spent: float = 0.0
    section: str

class TestResult(BaseModel):
    """Модель результата теста"""
    test_id: str = ""
    total_questions: int = 0
    correct_answers: int = 0
    score: int = 0
    percentage: float = 0.0
    time_spent: float = 0.0
    completed_at: datetime = Field(default_factory=datetime.now)
    answers: List[TestAnswer] = []
    strengths: List[str] = []
    weaknesses: List[str] = []
    section_stats: Dict = {}

class UserStats(BaseModel):
    """Модель статистики пользователя"""
    total_tests_taken: int = 0
    average_score: float = 0.0
    total_time_spent: float = 0.0
    last_activity: datetime = Field(default_factory=datetime.now)

class User(BaseModel):
    """Основная модель пользователя"""
    user_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    has_completed_test: bool = False  # Флаг прохождения теста
    last_test_date: Optional[datetime] = None
    
    # Прогресс и активность
    test_results: List[TestResult] = []
    stats: UserStats = Field(default_factory=UserStats)
    chat_history: List[Dict] = []
    
    def add_test_result(self, result: TestResult):
        """Добавляет результат теста"""
        self.test_results.append(result)
        self.has_completed_test = True
        self.last_test_date = datetime.now()
        
        # Обновляем статистику
        self.stats.total_tests_taken += 1
        self.stats.total_time_spent += result.time_spent
        self.stats.last_activity = datetime.now()
        
        # Пересчитываем средний score
        if self.test_results:
            total_score = sum(r.score for r in self.test_results)
            self.stats.average_score = total_score / len(self.test_results)

    def to_dict(self):
        """Конвертирует в словарь для сериализации"""
        data = self.model_dump()
        # Ручная сериализация datetime объектов
        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()
            elif isinstance(value, dict):
                for k, v in value.items():
                    if isinstance(v, datetime):
                        value[k] = v.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: dict):
        """Создает из словаря"""
        return cls(**data)