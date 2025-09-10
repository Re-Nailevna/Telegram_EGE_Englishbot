"""
Менеджер упражнений для интерактивных заданий по vocabulary и grammar.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from src.llm.service import llm_service
from src.rag.manager import rag_manager

logger = logging.getLogger(__name__)

class Exercise:
    def __init__(self, exercise_id: str, subject: str, question: str, options: List[str], 
                 correct_answer: str, explanation: str, difficulty: str = "medium"):
        self.exercise_id = exercise_id
        self.subject = subject
        self.question = question
        self.options = options
        self.correct_answer = correct_answer
        self.explanation = explanation
        self.difficulty = difficulty
        self.created_at = datetime.now()

class ExerciseManager:
    def __init__(self):
        self.active_exercises: Dict[int, List[Exercise]] = {}  # user_id -> [exercises]
        self.user_answers: Dict[int, Dict[str, str]] = {}  # user_id -> {exercise_id -> answer}
        self.exercise_results: Dict[int, List[Dict]] = {}  # user_id -> [results]
        self.user_current_index = {}
        self.session_ids: Dict[int, str] = {}
    
    async def start_exercise_session(self, user_id: int, subject: str) -> List[Exercise]:
        """Начинает новую сессию упражнений для пользователя"""
        try:
            # Генерируем новый идентификатор сессии, чтобы отсечь старые кнопки
            import uuid as _uuid
            self.session_ids[user_id] = str(_uuid.uuid4())
            # Генерируем 5 упражнений через LLM
            exercises = await self._generate_exercises(subject, user_id)
            
            # Сохраняем активные упражнения
            self.active_exercises[user_id] = []
            self.user_answers[user_id] = {}
            
            # Если LLM не сгенерировал упражнения, используем fallback
            if not exercises:
                exercises = self._get_fallback_exercises(subject)
            
            self.active_exercises[user_id] = exercises
            
            return exercises
            
        except Exception as e:
            logger.error(f"Error starting exercise session: {e}")
            # Возвращаем fallback упражнения
            exercises = self._get_fallback_exercises(subject)
            self.active_exercises[user_id] = exercises
            self.user_answers[user_id] = {}
            return exercises
    
    async def _generate_exercises(self, subject: str, user_id: int) -> List[Exercise]:
        """Генерирует упражнения через LLM с использованием RAG"""
        try:
            # Формируем персонализированный RAG-контекст
            user_context = rag_manager.create_user_context(user_id)

            # Жесткая спецификация JSON-ответа
            prompt_template = f"""
Создай 5 упражнений по {subject} для подготовки к ЕГЭ.

Контекст пользователя:
{user_context if user_context else "нет данных"}

Верни ТОЛЬКО JSON-массив из 5 объектов без текста вне JSON. Каждый объект:
{{
  "question": "Короткий вопрос или предложение с пропуском (без нумерации и без a)/b)/c)/d) в самом вопросе)",
  "options": ["вариант 1", "вариант 2", "вариант 3", "вариант 4"],
  "correct_answer": "A|B|C|D",
  "explanation": "Краткое объяснение"
}}

Требования:
- options ровно из 4 строк;
- correct_answer — одна буква из A,B,C,D;
- не добавляй номера 1.,2. и не встраивай метки a),b),c),d) в текст вопроса;
- никаких комментариев вне JSON.
"""

            # Используем нейтральный тип промпта, без конфликтующих системных инструкций
            # Добавляем небольшой nonce, чтобы снизить детерминизм и повторяемость
            import uuid as _uuid
            nonce = str(_uuid.uuid4())[:8]

            from datetime import datetime as _dt
            ts = _dt.utcnow().isoformat()

            response = await llm_service.generate_content(
                prompt_type="tutor",
                user_message=prompt_template,
                additional_context=f"Ответ строго в формате JSON массива из 5 объектов без комментариев или пояснений. nonce={nonce} ts={ts}",
                temperature=0.9,
            )
            
            # Проверяем, что ответ не пустой
            if not response or response.strip() == "":
                logger.warning("Empty response from LLM, using fallback exercises")
                return self._get_fallback_exercises(subject)
            
            # Пытаемся найти JSON в ответе
            try:
                # Парсим JSON ответ
                exercises_data = json.loads(response)
            except json.JSONDecodeError:
                # Если не удалось распарсить JSON, ищем JSON в тексте
                import re
                # Убираем кодовые блоки ```json ... ``` при наличии
                fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", response)
                if fenced:
                    response = fenced.group(1)
                json_match = re.search(r'\[.*\]', response, re.DOTALL)
                if json_match:
                    try:
                        exercises_data = json.loads(json_match.group())
                    except json.JSONDecodeError:
                        logger.error(f"Could not parse JSON from response: {response[:200]}")
                        return self._get_fallback_exercises(subject)
                else:
                    logger.error(f"No JSON found in response: {response[:200]}")
                    return self._get_fallback_exercises(subject)
            
            # Проверяем, что это список, либо словарь с ключом 'exercises'
            if isinstance(exercises_data, dict) and 'exercises' in exercises_data and isinstance(exercises_data['exercises'], list):
                exercises_list = exercises_data['exercises']
            elif isinstance(exercises_data, list):
                exercises_list = exercises_data
            else:
                logger.error(f"Response JSON has unexpected shape: {type(exercises_data)}; keys={list(exercises_data.keys()) if isinstance(exercises_data, dict) else 'n/a'}")
                return self._get_fallback_exercises(subject)
            
            exercises = []
            
            for i, data in enumerate(exercises_list):
                try:
                    # Проверяем наличие всех необходимых полей
                    required_fields = ["question", "options", "correct_answer", "explanation"]
                    for field in required_fields:
                        if field not in data:
                            logger.error(f"Missing field '{field}' in exercise {i}")
                            continue
                    # Нормализуем варианты и ответ
                    options = data["options"] if isinstance(data.get("options"), list) else []
                    if len(options) != 4:
                        logger.error(f"Invalid options length in exercise {i}: {len(options)}")
                        continue

                    correct_answer_raw = str(data.get("correct_answer", "")).strip().upper()
                    # Приводим к одной букве A-D
                    import re as _re
                    normalized_correct = _re.sub(r"[^A-D]", "", correct_answer_raw)[:1]
                    if normalized_correct not in ["A", "B", "C", "D"]:
                        logger.error(f"Invalid correct_answer in exercise {i}: {data.get('correct_answer')}")
                        continue

                    exercise = Exercise(
                        exercise_id=f"{subject}_{user_id}_{i}",
                        subject=subject,
                        question=data["question"],
                        options=options,
                        correct_answer=normalized_correct,
                        explanation=data["explanation"]
                    )
                    exercises.append(exercise)
                except Exception as e:
                    logger.error(f"Error creating exercise {i}: {e}")
                    continue
            
            # Если удалось создать хотя бы одно упражнение, возвращаем их
            if exercises:
                return exercises
            else:
                logger.error("No valid exercises created from LLM response; using fallback")
                return self._get_fallback_exercises(subject)
            
        except Exception as e:
            logger.error(f"Error generating exercises: {e}")
            return self._get_fallback_exercises(subject)
    
    def _get_fallback_exercises(self, subject: str) -> List[Exercise]:
        """Возвращает резервные упражнения"""
        if subject == "vocabulary":
            return [
                Exercise(
                    exercise_id=f"{subject}_fallback_1",
                    subject=subject,
                    question="Choose the correct phrasal verb:\nI need to ___ my notes before the exam.",
                    options=["look up", "look after", "look into", "look for"],
                    correct_answer="A",
                    explanation="'Look up' means to search for information, which fits the context of studying notes."
                ),
                Exercise(
                    exercise_id=f"{subject}_fallback_2",
                    subject=subject,
                    question="Complete the collocation:\nMake a ___ about your future plans.",
                    options=["decision", "solution", "problem", "opinion"],
                    correct_answer="A",
                    explanation="'Make a decision' is the correct collocation in English."
                ),
                Exercise(
                    exercise_id=f"{subject}_fallback_3",
                    subject=subject,
                    question="Choose the correct word:\nThe weather was so ___ that we had to cancel the picnic.",
                    options=["terrible", "terribly", "terribleness", "terrify"],
                    correct_answer="A",
                    explanation="'Terrible' is an adjective that describes the weather."
                ),
                Exercise(
                    exercise_id=f"{subject}_fallback_4",
                    subject=subject,
                    question="Select the right synonym:\nThe movie was very ___ and kept us interested.",
                    options=["boring", "entertaining", "difficult", "expensive"],
                    correct_answer="B",
                    explanation="'Entertaining' means interesting and enjoyable, which fits the context."
                ),
                Exercise(
                    exercise_id=f"{subject}_fallback_5",
                    subject=subject,
                    question="Choose the correct word form:\nShe has a great ___ for languages.",
                    options=["ability", "able", "ably", "enable"],
                    correct_answer="A",
                    explanation="'Ability' is a noun that means the power or skill to do something."
                )
            ]
        
        elif subject == "grammar":
            return [
                Exercise(
                    exercise_id=f"{subject}_fallback_1",
                    subject=subject,
                    question="Choose the correct tense:\nBy this time next year, I ___ university.",
                    options=["will finish", "will have finished", "finish", "am finishing"],
                    correct_answer="B",
                    explanation="'Will have finished' is the future perfect tense, used for actions completed by a specific time in the future."
                ),
                Exercise(
                    exercise_id=f"{subject}_fallback_2",
                    subject=subject,
                    question="Select the right conditional:\nIf I ___ more time, I would travel the world.",
                    options=["have", "had", "would have", "have had"],
                    correct_answer="B",
                    explanation="This is a second conditional sentence, so we use 'had' (past simple) in the if-clause."
                ),
                Exercise(
                    exercise_id=f"{subject}_fallback_3",
                    subject=subject,
                    question="Choose the correct article:\n___ sun rises in the east.",
                    options=["A", "An", "The", "No article"],
                    correct_answer="C",
                    explanation="'The' is used with unique objects like the sun, moon, earth, etc."
                ),
                Exercise(
                    exercise_id=f"{subject}_fallback_4",
                    subject=subject,
                    question="Select the correct passive form:\nThe book ___ by many students last year.",
                    options=["was read", "was reading", "read", "has read"],
                    correct_answer="A",
                    explanation="'Was read' is the past simple passive form, indicating the book was the object of the action."
                ),
                Exercise(
                    exercise_id=f"{subject}_fallback_5",
                    subject=subject,
                    question="Choose the right modal verb:\nYou ___ study harder if you want to pass the exam.",
                    options=["can", "must", "should", "would"],
                    correct_answer="C",
                    explanation="'Should' is used to give advice or make recommendations."
                )
            ]
        
        return []
    
    def get_current_exercise(self, user_id: int, exercise_index: int = 0) -> Optional[Exercise]:
        """Получает текущее упражнение для пользователя"""
        if user_id in self.active_exercises and self.active_exercises[user_id]:
            if 0 <= exercise_index < len(self.active_exercises[user_id]):
                return self.active_exercises[user_id][exercise_index]
        return None
    
    def submit_answer(self, user_id: int, exercise_id: str, answer: str) -> bool:
        """Сохраняет ответ пользователя"""
        if user_id not in self.user_answers:
            self.user_answers[user_id] = {}
         
        self.user_answers[user_id][exercise_id] = answer
        return True
    
    def finish_exercise_session(self, user_id: int) -> Dict:
        """Завершает сессию упражнений и возвращает результаты"""
        if user_id not in self.active_exercises:
            return {"error": "No active exercise session"}
        
        exercises = self.active_exercises[user_id]
        user_answers = self.user_answers.get(user_id, {})
        
        results = []
        correct_count = 0
        total_count = len(exercises)
        
        for exercise in exercises:
            user_answer = user_answers.get(exercise.exercise_id, "")
            is_correct = user_answer.upper() == exercise.correct_answer.upper()
            
            if is_correct:
                correct_count += 1
            
            result = {
                "exercise_id": exercise.exercise_id,
                "question": exercise.question,
                "user_answer": user_answer,
                "correct_answer": exercise.correct_answer,
                "is_correct": is_correct,
                "explanation": exercise.explanation,
                "options": exercise.options
            }
            results.append(result)
        
        # Вычисляем процент правильных ответов
        percentage = (correct_count / total_count * 100) if total_count > 0 else 0
        
        # Определяем уровень успеха
        if percentage >= 80:
            level = "Отлично! 🎉"
        elif percentage >= 60:
            level = "Хорошо! 👍"
        elif percentage >= 40:
            level = "Удовлетворительно 📚"
        else:
            level = "Требует улучшения 💪"
        
        # Сохраняем результаты
        self.exercise_results[user_id] = results
        
        # Очищаем активную сессию
        if user_id in self.active_exercises:
            del self.active_exercises[user_id]
        if user_id in self.user_answers:
            del self.user_answers[user_id]
        if user_id in self.session_ids:
            del self.session_ids[user_id]
        
        return {
            "total_questions": total_count,
            "correct_answers": correct_count,
            "percentage": percentage,
            "level": level,
            "results": results
        }
    
    def is_exercise_session_active(self, user_id: int) -> bool:
        """Проверяет, активна ли сессия упражнений"""
        return user_id in self.active_exercises and len(self.active_exercises[user_id]) > 0
    
    def get_exercise_progress(self, user_id: int) -> Tuple[int, int]:
        """Возвращает прогресс выполнения упражнений (текущее, всего)"""
        if user_id not in self.active_exercises:
            return (0, 0)
        
        total = len(self.active_exercises[user_id])
        answered = len(self.user_answers.get(user_id, {}))
        return (answered, total)
    
    def get_current_exercise_index(self, user_id: int) -> int:
        """Возвращает текущий индекс упражнения для пользователя"""
        return self.user_current_index.get(user_id, 0)

    def set_current_exercise_index(self, user_id: int, index: int):
        """Устанавливает текущий индекс упражнения для пользователя"""
        self.user_current_index[user_id] = index

    def increment_current_index(self, user_id: int):
        """Увеличивает текущий индекс на 1"""
        current = self.user_current_index.get(user_id, 0)
        self.user_current_index[user_id] = current + 1

    def reset_current_index(self, user_id: int):
        """Сбрасывает текущий индекс"""
        if user_id in self.user_current_index:
            del self.user_current_index[user_id]

    def get_session_id(self, user_id: int) -> Optional[str]:
        """Возвращает текущий идентификатор сессии упражнений пользователя"""
        return self.session_ids.get(user_id)

    def get_short_session_id(self, user_id: int) -> Optional[str]:
        sid = self.session_ids.get(user_id)
        if not sid:
            # Создаем, если отсутствует (для надежности при сбоях)
            import uuid as _uuid
            sid = str(_uuid.uuid4())
            self.session_ids[user_id] = sid
        return sid[:6]

# Глобальный экземпляр
exercise_manager = ExerciseManager()
