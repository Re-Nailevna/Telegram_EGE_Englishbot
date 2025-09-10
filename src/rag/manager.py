"""
Упрощенный менеджер RAG для персонализации на основе данных пользователя.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Optional
from src.llm.service import llm_service

logger = logging.getLogger(__name__)

class SimpleRAGManager:
    def __init__(self):
        self.user_profiles: Dict[int, dict] = {}
    
    def load_user_profile(self, user_id: int) -> Optional[dict]:
        """Загружает профиль пользователя для RAG"""
        try:
            # Сначала пробуем загрузить из основного файла пользователя
            user_path = Path(f"data/users/{user_id}.json")
            if user_path.exists():
                with open(user_path, 'r', encoding='utf-8') as f:
                    user_data = json.load(f)
                
                # Создаем профиль на основе данных пользователя
                profile = {
                    'user_id': user_data.get('user_id'),
                    'test_results': user_data.get('test_results', []),
                    'stats': user_data.get('stats', {}),
                    'weaknesses': [],
                    'error_patterns': {}
                }
                
                # Загружаем результаты тестов из отдельного файла
                test_path = Path(f"data/tests/user_{user_id}.json")
                if test_path.exists():
                    with open(test_path, 'r', encoding='utf-8') as f:
                        test_results = json.load(f)
                    profile['test_results'] = test_results
                    
                    # Анализируем слабые стороны по темам из последнего теста
                    if test_results:
                        latest_test = test_results[-1]
                        profile['weaknesses'] = latest_test.get('weaknesses', [])
                        # Добавляем статистику по темам, если есть
                        profile['topic_stats'] = latest_test.get('topic_stats', {})
                        
                        # Анализируем ошибки по темам и разделам
                        error_patterns = {}
                        for answer in latest_test.get('answers', []):
                            if not answer.get('is_correct'):
                                topic = answer.get('topic') or answer.get('section', 'unknown')
                                if topic not in error_patterns:
                                    error_patterns[topic] = []
                                error_patterns[topic].append(answer.get('correct_answer', ''))
                        profile['error_patterns'] = error_patterns
                
                return profile
                
        except Exception as e:
            logger.error(f"Error loading user profile {user_id}: {e}")
        return None
    
    def create_user_context(self, user_id: int) -> str:
        """Создает контекст пользователя для персонализации"""
        profile = self.load_user_profile(user_id)
        if not profile:
            return "Нет данных о пользователе"
        
        context_parts = []
        
        # Добавляем информацию о последнем тесте
        if profile.get('test_results'):
            latest_test = profile['test_results'][-1]
            context_parts.append(
                f"Результат последнего теста: {latest_test['score']}/{latest_test['total_questions']} "
                f"({latest_test['percentage']:.1f}%)"
            )
        
        # Добавляем слабые стороны (темы)
        if profile.get('weaknesses'):
            context_parts.append(f"Слабые темы: {', '.join(profile['weaknesses'])}")
        
        # Добавляем частые ошибки по темам
        if profile.get('error_patterns'):
            for topic, errors in profile['error_patterns'].items():
                if errors:
                    context_parts.append(f"Ошибки по теме {topic}: {', '.join(errors)}")
        
        return "\n".join(context_parts)
    
    async def generate_personalized_exercise(self, subject: str, user_id: int) -> str:
        """Генерирует персонализированное задание"""
        user_context = self.create_user_context(user_id)
        
        # Формируем промпт с контекстом пользователя
        prompt = f"""
        Создай {subject} задание для подготовки к ЕГЭ по английскому.
        
        Контекст пользователя:
        {user_context}
        
        Создай 5 заданий, которые помогут улучшить слабые стороны.
        Формат: четкие задания с вариантами ответов или упражнениями.
        """
        
        try:
            # Используем основной LLM сервис с персонализированным промптом
            return await llm_service.generate_content(
                prompt_type="tutor",
                user_message=prompt,
                additional_context=f"Генерируй задания по {subject}"
            )
        except Exception as e:
            logger.error(f"Error generating personalized exercise: {e}")
            return self.get_fallback_exercise(subject)
    
    def get_fallback_exercise(self, subject: str) -> str:
        """Резервные задания при ошибке"""
        if subject == "vocabulary":
            return """📚 Задания по лексике:
            
1. Choose the correct phrasal verb:
   I need to ___ my notes before the exam.
   a) look up    b) look after    c) look into    d) look for

2. Complete the collocation:
   Make a ___ about your future plans.
   a) decision   b) solution   c) problem   d) opinion"""
        
        elif subject == "grammar":
            return """📖 Задания по грамматике:
            
1. Choose the correct tense:
   By this time next year, I ___ university.
   a) will finish    b) will have finished    c) finish    d) am finishing

2. Select the right conditional:
   If I ___ more time, I would travel the world.
   a) have    b) had    c) would have    d) have had"""
        
        return "Задания временно недоступны."
    

    

# Глобальный экземпляр
rag_manager = SimpleRAGManager()