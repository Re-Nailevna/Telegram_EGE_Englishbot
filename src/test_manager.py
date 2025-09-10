"""
Менеджер тестирования с фиксированным тестом.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)

class TestManager:
    def __init__(self):
        self.active_tests: Dict[int, dict] = {}  # user_id -> test_data
        self.test_results: Dict[int, list] = {}  # user_id -> results
        self.fixed_test = self.load_fixed_test()
    
    def _infer_topic(self, section: str, question: str, explanation: str, options: list) -> str:
        """Пытается определить тему задания (грамматика/лексика) по тексту/объяснению."""
        text = f"{question} {explanation} {' '.join(options)}".lower()
        if section == "grammar":
            if any(k in text for k in ["past perfect", "by the time", "had "]):
                return "Tenses: Past Perfect"
            if any(k in text for k in ["future continuous", "will be", "this time next"]):
                return "Tenses: Future Continuous"
            if any(k in text for k in ["present perfect", "yet", "have ", "has "]):
                return "Tenses: Present Perfect"
            if any(k in text for k in ["conditional", "if i", "would "]):
                return "Conditionals (II)"
            if any(k in text for k in ["mustn't", "mustn'", "mustn", "must not", "must ", "should ", "have to", "modal"]):
                return "Modals"
            if any(k in text for k in ["reported speech", "asked me where", "indirect speech"]):
                return "Reported Speech"
            if any(k in text for k in ["article", " the ", " a ", " an "]):
                return "Articles"
            if any(k in text for k in ["passive", "was read", "is made", "were "]):
                return "Passive Voice"
            if any(k in text for k in ["preposition", "in ", "on ", "at ", "for "]):
                return "Prepositions"
            return "Grammar: Other"
        if section == "vocabulary":
            if any(k in text for k in ["phrasal", "look up", "look after", "look into", "look for"]):
                return "Vocabulary: Phrasal Verbs"
            if any(k in text for k in ["collocation", "make a decision", "take", "do "]):
                return "Vocabulary: Collocations"
            if any(k in text for k in ["word formation", "-tion", "-ment", "prefix", "suffix"]):
                return "Vocabulary: Word Formation"
            if any(k in text for k in ["synonym", "antonym", "closest in meaning"]):
                return "Vocabulary: Synonyms/Antonyms"
            if any(k in text for k in ["idiom", "open-minded", "piece of cake"]):
                return "Vocabulary: Idioms"
            return "Vocabulary: Other"
        return section.capitalize()
    
    def load_fixed_test(self) -> dict:
        """Загружает фиксированный тест из файла"""
        try:
            test_file = Path("data/fixed_test.json")
            if test_file.exists():
                with open(test_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                return self.create_default_test()
        except Exception as e:
            logger.error(f"Error loading fixed test: {e}")
            return self.create_default_test()
    
    def create_default_test(self) -> dict:
        """Создает тест по умолчанию если файл не найден"""
        return {
            "test_name": "Пробный вариант ЕГЭ по английскому языку",
            "total_questions": 25,
            "questions": [
                {
                    "id": 1,
                    "section": "grammar",
                    "question": "By the time we arrived at the theatre, the performance ______.",
                    "options": [
                        "a) had already started",
                        "b) already started", 
                        "c) has already started",
                        "d) was already starting"
                    ],
                    "correct_answer": "a"
                }
                # ... остальные вопросы ...
            ]
        }
    
    def start_test_for_user(self, user_id: int) -> bool:
        """Начинает новый тест для пользователя"""
        try:
            self.active_tests[user_id] = {
                'questions': self.fixed_test['questions'].copy(),
                'current_question': 0,
                'score': 0,
                'answers': []
            }
            return True
        except Exception as e:
            logger.error(f"Error starting test: {e}")
            return False
    
    def get_current_question(self, user_id: int) -> Optional[dict]:
        """Возвращает текущий вопрос пользователя"""
        if user_id not in self.active_tests:
            return None
        
        test = self.active_tests[user_id]
        current_idx = test['current_question']
        
        if current_idx < len(test['questions']):
            return test['questions'][current_idx]
        return None
    
    def create_question_keyboard(self, question: dict) -> InlineKeyboardMarkup:
        """Создает клавиатуру с вариантами ответов"""
        keyboard = []
        
        for option in question['options']:
            # Извлекаем букву варианта (первый символ)
            option_letter = option[0].lower()
            if option_letter in ['a', 'b', 'c', 'd']:
                keyboard.append([
                    InlineKeyboardButton(option, callback_data=f"test_answer_{option_letter}")
                ])
        
        return InlineKeyboardMarkup(keyboard)
    
    def process_answer(self, user_id: int, answer: str):
        """Обрабатывает ответ пользователя"""
        if user_id not in self.active_tests:
            return
        
        test = self.active_tests[user_id]
        current_idx = test['current_question']
        
        if current_idx >= len(test['questions']):
            return
        
        current_question = test['questions'][current_idx]
        section = current_question.get('section', '')
        explanation = current_question.get('explanation', '')
        options = current_question.get('options', [])
        topic = self._infer_topic(section, current_question.get('question', ''), explanation, options)
        
        # Сохраняем ответ
        test['answers'].append({
            'question_id': current_question['id'],
            'user_answer': answer,
            'correct_answer': current_question['correct_answer'],
            'is_correct': (answer == current_question['correct_answer']),
            'section': section,
            'topic': topic
        })
        
        # Увеличиваем счетчик
        if answer == current_question['correct_answer']:
            test['score'] += 1
        
        # Переходим к следующему вопросу
        test['current_question'] += 1
    
    def is_test_completed(self, user_id: int) -> bool:
        """Проверяет завершен ли тест"""
        if user_id not in self.active_tests:
            return False
        
        test = self.active_tests[user_id]
        return test['current_question'] >= len(test['questions'])
    
    def finish_test(self, user_id: int) -> dict:
        """Завершает тест и возвращает результаты"""
        if user_id not in self.active_tests:
            return None
        
        test = self.active_tests[user_id]
        
        # Анализ результатов
        total_questions = len(test['questions'])
        results = {
            'total_questions': total_questions,
            'score': test['score'],
            'percentage': (test['score'] / total_questions) * 100 if total_questions > 0 else 0,
            'answers': test['answers']
        }
        
        # Анализ по разделам
        section_stats = {}
        topic_stats = {}
        for answer in test['answers']:
            section = answer['section']
            if section not in section_stats:
                section_stats[section] = {'total': 0, 'correct': 0}
            section_stats[section]['total'] += 1
            if answer['is_correct']:
                section_stats[section]['correct'] += 1
            topic = answer.get('topic', 'Unknown')
            if topic not in topic_stats:
                topic_stats[topic] = {'total': 0, 'correct': 0}
            topic_stats[topic]['total'] += 1
            if answer['is_correct']:
                topic_stats[topic]['correct'] += 1
        
        # Определяем сильные и слабые стороны по темам
        strengths = []
        weaknesses = []
        for topic, stats in topic_stats.items():
            if stats['total'] > 0:
                accuracy = stats['correct'] / stats['total']
                if accuracy >= 0.7:
                    strengths.append(topic)
                elif accuracy <= 0.6:
                    weaknesses.append(topic)
        
        results['section_stats'] = section_stats
        results['topic_stats'] = topic_stats
        results['strengths'] = strengths
        results['weaknesses'] = weaknesses
        
        # Сохраняем результаты
        if user_id not in self.test_results:
            self.test_results[user_id] = []
        self.test_results[user_id].append(results)
        
        # Обновляем флаг прохождения теста в базе и статистику
        try:
            from src.database.manager import database_manager
            from src.database.models import TestResult, TestAnswer
            
            # Создаем объект TestResult для сохранения в базе
            test_result = TestResult(
                test_id=f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                total_questions=total_questions,
                correct_answers=test['score'],
                score=test['score'],
                percentage=results['percentage'],
                time_spent=0.0,  # Можно добавить отслеживание времени
                completed_at=datetime.now(),
                answers=[
                    TestAnswer(
                        question_id=answer['question_id'],
                        user_answer=answer['user_answer'],
                        correct_answer=answer['correct_answer'],
                        is_correct=answer['is_correct'],
                        time_spent=0.0,
                        section=answer['section']
                    ) for answer in test['answers']
                ],
                strengths=results['strengths'],
                weaknesses=results['weaknesses'],
                section_stats=results['section_stats']
            )
            
            # Получаем пользователя и добавляем результат
            user = database_manager.get_user(user_id)
            user.add_test_result(test_result)
            database_manager.save_user(user)
            
        except Exception as e:
            logger.error(f"Error updating user database: {e}")
            # Fallback: просто отмечаем что тест пройден
            try:
                database_manager.mark_test_completed(user_id)
            except Exception as e2:
                logger.error(f"Error marking test as completed: {e2}")
        
        # Сохраняем в файл
        self.save_results_to_file(user_id)
        
        # Удаляем активный тест
        if user_id in self.active_tests:
            del self.active_tests[user_id]
        
        return results
    
    def save_results_to_file(self, user_id: int):
        """Сохраняет результаты в файл"""
        try:
            results_dir = Path("data/tests")
            results_dir.mkdir(exist_ok=True)
            
            results = self.test_results.get(user_id, [])
            if results:
                with open(results_dir / f"user_{user_id}.json", 'w', encoding='utf-8') as f:
                    json.dump(results, f, ensure_ascii=False, indent=2)
                    
        except Exception as e:
            logger.error(f"Error saving results: {e}")
    
    def has_user_completed_test(self, user_id: int) -> bool:
        """Проверяет проходил ли пользователь тест"""
        try:
            from src.database.manager import database_manager
            return database_manager.has_completed_test(user_id)
        except Exception as e:
            logger.error(f"Error checking test completion: {e}")
            return False

# Глобальный экземпляр менеджера тестов
test_manager = TestManager()