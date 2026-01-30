# src/agents/interviewer.py
"""
Агент Interviewer - ведет диалог с кандидатом.
"""

import asyncio
from typing import Dict, Any, List, Optional
import logging
from ..core.llm_client import MistralClientFactory
from .base_agent import BaseAgent
from config.prompts import (
    QUESTION_PROMPTS,
    INTERVIEWER_SYSTEM_PROMPT,
    NEXT_QUESTION_PROMPT,
    OFFTOPIC_HANDLER_PROMPT,
    COUNTER_QUESTION_PROMPT
)

logger = logging.getLogger(__name__)


class InterviewerAgent(BaseAgent):
    """Агент-интервьюер для проведения технического интервью."""
    
    def __init__(
        self,
        name: str = "Интервьюер",
        llm_model: str = None,
        **kwargs
    ):
        """
        Инициализация агента-интервьюера.
        
        Args:
            name: Имя агента
            llm_model: Модель LLM
        """
        super().__init__(name=name, role="interviewer", **kwargs)
        
        # Инициализация LLM клиента
        self.llm_client = MistralClientFactory.create_client(
            model=llm_model,
            temperature=0.7,
            max_tokens=500
        )
        
        # Состояние интервью
        self.current_topic: Optional[str] = None
        self.current_difficulty: str = "junior"  # junior, middle, senior
        self.question_count: int = 0
        self.topics_covered: List[str] = []
        
        # Память о вопросах и ответах
        self.qa_history: List[Dict[str, Any]] = []
        
        logger.info(f"Агент Interviewer '{name}' инициализирован")

    async def think(
        self, 
        user_input: str, 
        context: Dict[str, Any],
        conversation_history: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """
        Интервьюер анализирует ответ кандидата.
        Теперь использует рекомендацию Observer для принятия решения.
        """
        
        self.add_internal_thought(f"Анализирую ответ кандидата: '{user_input[:100]}...'")
        
        # Получаем рекомендацию от Observer
        observer_recommendation = context.get("observer_recommendation", "")
        is_bad_answer = context.get("is_bad_answer", False)
        
        # Определяем, является ли ответ оффтопиком
        is_offtopic = await self._detect_offtopic(user_input, context)
        
        # Определяем, является ли ответ встречным вопросом
        is_counter_question = await self._detect_counter_question(user_input)
        
        # Определяем качество ответа
        if "answer_quality" in context:
            answer_quality = context["answer_quality"]
        else:
            answer_quality = await self._evaluate_answer_quality(user_input, context)
        
        # Корректируем оценку на основе рекомендации Observer
        if "упростить" in observer_recommendation.lower() or is_bad_answer:
            answer_quality = max(1, answer_quality - 3)
        
        if "усложнить" in observer_recommendation.lower():
            answer_quality = min(10, answer_quality + 2)
        
        # Генерируем мысли для лога
        thoughts = f"""
        Ответ кандидата получен.
        Длина ответа: {len(user_input)} символов
        Оффтопик: {'Да' if is_offtopic else 'Нет'}
        Встречный вопрос: {'Да' if is_counter_question else 'Нет'}
        Качество ответа: {answer_quality}/10
        Рекомендация Observer: {observer_recommendation}
        Текущая тема: {self.current_topic or 'Не определена'}
        Текущая сложность: {self.current_difficulty}
        """
        
        self.add_internal_thought(thoughts.strip())
        
        # Определяем следующее действие на основе качества и рекомендации
        if is_offtopic:
            action = "handle_offtopic"
        elif is_counter_question:
            action = "handle_counter_question"
        elif answer_quality < 3 or "упростить" in observer_recommendation.lower():
            action = "simplify_question"
        elif answer_quality > 7 and "усложнить" in observer_recommendation.lower():
            action = "escalate_difficulty"
        else:
            action = "continue_topic"
        
        return {
            "thoughts": thoughts,
            "action": action,
            "parameters": {
                "is_offtopic": is_offtopic,
                "is_counter_question": is_counter_question,
                "answer_quality": answer_quality,
                "observer_recommendation": observer_recommendation,
                "current_topic": self.current_topic,
                "current_difficulty": self.current_difficulty
            },
            "confidence": min(0.9, answer_quality / 10)  # Уверенность зависит от качества
        }
    
    # async def think(
    #     self, 
    #     user_input: str, 
    #     context: Dict[str, Any],
    #     conversation_history: List[Dict[str, str]]
    # ) -> Dict[str, Any]:
    #     """
    #     Интервьюер анализирует ответ кандидата и решает, что делать дальше.
    #     В реальной системе эта функция будет использовать рекомендации Observer.
    #     """
        
    #     self.add_internal_thought(f"Анализирую ответ кандидата: '{user_input[:100]}...'")
        
    #     # Определяем, является ли ответ оффтопиком
    #     is_offtopic = await self._detect_offtopic(user_input, context)
        
    #     # Определяем, является ли ответ встречным вопросом
    #     is_counter_question = await self._detect_counter_question(user_input)
        
    #     # Анализируем качество ответа (в упрощенной версии)
    #     answer_quality = await self._evaluate_answer_quality(user_input, context)
        
    #     # Генерируем мысли для лога
    #     thoughts = f"""
    #     Ответ кандидата получен.
    #     Длина ответа: {len(user_input)} символов
    #     Оффтопик: {'Да' if is_offtopic else 'Нет'}
    #     Встречный вопрос: {'Да' if is_counter_question else 'Нет'}
    #     Предварительная оценка качества: {answer_quality}/10
    #     Текущая тема: {self.current_topic or 'Не определена'}
    #     Текущая сложность: {self.current_difficulty}
    #     """
        
    #     self.add_internal_thought(thoughts.strip())
        
    #     # Определяем следующее действие
    #     if is_offtopic:
    #         action = "handle_offtopic"
    #     elif is_counter_question:
    #         action = "handle_counter_question"
    #     elif answer_quality < 4:
    #         action = "simplify_question"
    #     elif answer_quality > 8:
    #         action = "escalate_difficulty"
    #     else:
    #         action = "continue_topic"
        
    #     return {
    #         "thoughts": thoughts,
    #         "action": action,
    #         "parameters": {
    #             "is_offtopic": is_offtopic,
    #             "is_counter_question": is_counter_question,
    #             "answer_quality": answer_quality,
    #             "current_topic": self.current_topic,
    #             "current_difficulty": self.current_difficulty
    #         },
    #         "confidence": 0.8
    #     }

    async def respond(
        self, 
        user_input: str, 
        context: Dict[str, Any],
        conversation_history: List[Dict[str, str]]
    ) -> str:
        """
        Генерация ответа интервьюера.
        """
        
        # Получаем результат анализа
        answer_quality = context.get("answer_quality", 5)
        observer_recommendation = context.get("observer_recommendation", "")
        is_good_answer = context.get("is_good_answer", answer_quality >= 6)
        
        # Определяем действие на основе оценки качества
        if answer_quality < 4 or "упростить" in observer_recommendation.lower():
            action = "simplify_question"
        elif answer_quality > 7 and "усложнить" in observer_recommendation.lower():
            action = "escalate_difficulty"
        else:
            action = "continue_topic"
        
        # Сохраняем вопрос-ответ в историю
        if self.qa_history:
            last_question = self.qa_history[-1]["question"]
            self.qa_history[-1]["answer"] = user_input
            self.qa_history[-1]["quality"] = answer_quality
        
        # Генерируем следующий вопрос в зависимости от действия
        if action == "simplify_question":
            response = await self._generate_simpler_question(context)
        elif action == "escalate_difficulty":
            response = await self._generate_harder_question(context)
        else:
            response = await self._generate_next_question(context)
        
        # Очищаем ответ от возможных вступлений
        response = self._clean_response_text(response)
        
        # Сохраняем новый вопрос в историю
        self.qa_history.append({
            "question": response,
            "answer": None,
            "topic": self.current_topic,
            "difficulty": self.current_difficulty,
            "quality": None,
            "question_number": self.question_count + 1
        })
        
        self.question_count += 1
        
        return response

    def _clean_response_text(self, response: str) -> str:
        """Очистка текста ответа от технических вступлений."""
        
        # Удаляем вступления о качестве предыдущих ответов
        patterns_to_remove = [
            r'Отлично[,\s]+учитывая.*?предлагаю следующий вопрос:',
            r'На основе.*?рекомендации.*?следующий вопрос:',
            r'Учитывая.*?качество.*?ответа.*?вопрос:',
            r'Следующий вопрос:',
            r'Давайте перейдем к следующему вопросу:',
            r'Теперь.*?вопрос:',
            r'^.*?[,\s]+предлагаю.*?:'
        ]
        
        import re
        for pattern in patterns_to_remove:
            response = re.sub(pattern, '', response, flags=re.IGNORECASE)
        
        # Удаляем лишние пробелы и переносы
        response = ' '.join(response.split())
        
        # Капитализируем первую букву
        if response:
            response = response[0].upper() + response[1:]
        
        # Убедимся, что это вопрос
        if not response.endswith('?'):
            response = response.rstrip('.') + '?'
        
        return response.strip()
    
    # async def respond(
    #     self, 
    #     user_input: str, 
    #     context: Dict[str, Any],
    #     conversation_history: List[Dict[str, str]]
    # ) -> str:
    #     """
    #     Генерация ответа интервьюера.
    #     В реальной системе будет использовать результат think() и рекомендации Observer.
    #     """
        
    #     # Получаем результат анализа
    #     analysis = await self.think(user_input, context, conversation_history)
    #     action = analysis["action"]
        
    #     # Сохраняем вопрос-ответ в историю
    #     if self.qa_history:
    #         last_question = self.qa_history[-1]["question"]
    #         self.qa_history[-1]["answer"] = user_input
    #         self.qa_history[-1]["analysis"] = analysis
        
    #     # Генерируем следующий вопрос в зависимости от действия
    #     if action == "handle_offtopic":
    #         response = await self._handle_offtopic_response(user_input, context)
    #     elif action == "handle_counter_question":
    #         response = await self._handle_counter_question(user_input, context)
    #     elif action == "simplify_question":
    #         response = await self._generate_simpler_question(context)
    #     elif action == "escalate_difficulty":
    #         response = await self._generate_harder_question(context)
    #     else:
    #         response = await self._generate_next_question(context)
        
    #     # Сохраняем новый вопрос в историю
    #     self.qa_history.append({
    #         "question": response,
    #         "answer": None,
    #         "topic": self.current_topic,
    #         "difficulty": self.current_difficulty,
    #         "question_number": self.question_count + 1
    #     })
        
    #     self.question_count += 1
        
    #     return response
    
    async def start_interview(self, context: Dict[str, Any]) -> str:
        """Начало интервью - приветствие и первый вопрос."""
        
        position = context.get("position", "разработчик")
        
        # Приветствие
        greeting = f"""Привет! Меня зовут {self.name}. Я буду проводить техническое интервью на позицию {position}.

Давайте начнем. Расскажите, пожалуйста, о вашем опыте работы с {context.get('technologies', ['технологиями'])[0]}."""
        
        # Сохраняем приветствие как первый "вопрос"
        self.qa_history.append({
            "question": greeting,
            "answer": None,
            "topic": "опыт и введение",
            "difficulty": "junior",
            "question_number": 1
        })
        
        self.question_count = 1
        self.current_topic = "опыт и введение"
        
        self.add_internal_thought(f"Начинаю интервью для позиции {position}")
        
        return greeting
    
    async def _generate_next_question(self, context: Dict[str, Any]) -> str:
        """Генерация следующего вопроса."""
        
        # Определяем тему для следующего вопроса
        if not self.current_topic or self.question_count > 3:
            technologies = context.get("technologies", ["Python", "базы данных", "алгоритмы"])
            tech_index = (self.question_count // 3) % len(technologies)
            self.current_topic = technologies[tech_index]
        
        # Формируем системный промпт
        system_prompt = INTERVIEWER_SYSTEM_PROMPT.format(
            position=context.get("position", "разработчик"),
            grade=context.get("grade", "Junior"),
            experience=context.get("experience", "не указан"),
            technologies=", ".join(context.get("technologies", [])),
            current_task="сгенерировать естественный технический вопрос"
        )
        
        # Определяем сложность вопроса
        difficulty = self.current_difficulty
        if "observer_recommendation" in context:
            recommendation = context["observer_recommendation"].lower()
            if "упростить" in recommendation:
                difficulty = "junior"
            elif "усложнить" in recommendation:
                difficulty = "senior"
        
        # Формируем промпт для генерации вопроса
        user_prompt = QUESTION_PROMPTS.get(difficulty, QUESTION_PROMPTS["junior"]).format(
            topic=self.current_topic
        )
        
        # Генерируем вопрос
        question = await self.llm_client.generate(system_prompt, user_prompt)
        
        # Очищаем вопрос от технических артефактов
        question = self._clean_question(question)
        
        self.add_internal_thought(f"Сгенерирован вопрос по теме '{self.current_topic}', сложность: {difficulty}")
        
        return question

    def _clean_question(self, question: str) -> str:
        """Очистка вопроса от технических артефактов."""
        
        # Удаляем все в квадратных скобках
        import re
        question = re.sub(r'\[.*?\]', '', question)
        
        # Удаляем все в звездочках
        question = re.sub(r'\*.*?\*', '', question)
        
        # Удаляем подчеркивания
        question = re.sub(r'_.*?_', '', question)
        
        # Удаляем маркеры типа ---, ===
        question = re.sub(r'^[-=]+$', '', question, flags=re.MULTILINE)
        
        # Удаляем текст "Дополнительные аспекты" и подобное
        lines = question.split('\n')
        clean_lines = []
        skip_next = False
        
        for line in lines:
            line = line.strip()
            
            # Пропускаем пустые строки и разделители
            if not line or line.startswith('---') or line.startswith('==='):
                continue
            
            # Пропускаем строки, которые выглядят как инструкции
            if any(keyword in line.lower() for keyword in [
                'дополнительные аспекты', 
                'если кандидат не затронет',
                'рассмотрите следующие аспекты',
                'пример хорошего вопроса',
                'формат вопроса',
                'сгенерируй вопрос'
            ]):
                continue
            
            # Удаляем нумерацию в начале строки (1., 2., и т.д.)
            line = re.sub(r'^\d+\.\s*', '', line)
            line = re.sub(r'^[-*]\s*', '', line)
            
            clean_lines.append(line)
        
        # Объединяем строки
        question = ' '.join(clean_lines)
        
        # Удаляем лишние пробелы
        question = ' '.join(question.split())
        
        # Добавляем вопросительный знак, если его нет
        if not question.endswith('?') and len(question) > 10:
            question = question.rstrip('.') + '?'
        
        # Капитализируем первую букву
        if question:
            question = question[0].upper() + question[1:]
        
        return question.strip()
    
    # async def _generate_next_question(self, context: Dict[str, Any]) -> str:
    #     """Генерация следующего вопроса с учетом оценки предыдущего ответа."""
        
    #     # Получаем информацию о предыдущем ответе
    #     previous_quality = context.get("answer_quality", 5)
    #     observer_recommendation = context.get("observer_recommendation", "")
        
    #     # Определяем, нужно ли менять тему
    #     if previous_quality < 4 or "сменить тему" in observer_recommendation.lower():
    #         # Меняем тему на более простую
    #         simple_topics = ["базовые концепции", "фундаментальные знания", "основы"]
    #         self.current_topic = simple_topics[self.question_count % len(simple_topics)]
    #         self.current_difficulty = "junior"
    #     elif previous_quality > 7 and "углубиться" in observer_recommendation.lower():
    #         # Углубляемся в текущую тему
    #         self.current_difficulty = self._increase_difficulty(self.current_difficulty)
    #     else:
    #         # Продолжаем текущую тему с текущей сложностью
    #         pass
        
    #     # Формируем системный промпт
    #     system_prompt = INTERVIEWER_SYSTEM_PROMPT.format(
    #         position=context.get("position", "разработчик"),
    #         grade=context.get("grade", "Junior"),
    #         experience=context.get("experience", "не указан"),
    #         technologies=", ".join(context.get("technologies", [])),
    #         current_task=self._get_current_task_based_on_quality(previous_quality)
    #     )
        
    #     # Формируем промпт для генерации вопроса
    #     user_prompt = NEXT_QUESTION_PROMPT.format(
    #         topic=self.current_topic,
    #         previous_difficulty=self.current_difficulty,
    #         evaluation_summary=f"Качество предыдущего ответа: {previous_quality}/10",
    #         observer_recommendation=observer_recommendation,
    #         position=context.get("position", "разработчик")
    #     )
        
    #     # Генерируем вопрос
    #     question = await self.llm_client.generate(system_prompt, user_prompt)
        
    #     self.add_internal_thought(
    #         f"Сгенерирован новый вопрос. Тема: '{self.current_topic}', "
    #         f"Сложность: {self.current_difficulty}, "
    #         f"Качество предыдущего ответа: {previous_quality}/10"
    #     )
        
    #     return question

    def _get_current_task_based_on_quality(self, quality: int) -> str:
        """Определение задачи на основе качества ответа."""
        if quality < 4:
            return "упростить вопрос или вернуться к основам"
        elif quality < 7:
            return "продолжить исследование текущей темы с той же сложностью"
        else:
            return "углубиться в тему или перейти к более сложным вопросам"

    def _increase_difficulty(self, current: str) -> str:
        """Повышение сложности."""
        levels = ["junior", "middle", "senior"]
        if current in levels:
            index = levels.index(current)
            if index < len(levels) - 1:
                return levels[index + 1]
        return current
    
    # async def _generate_next_question(self, context: Dict[str, Any]) -> str:
    #     """Генерация следующего вопроса."""
        
    #     # Определяем тему для следующего вопроса
    #     if not self.current_topic or self.question_count > 3:
    #         # Меняем тему после 3 вопросов
    #         technologies = context.get("technologies", ["Python", "базы данных", "алгоритмы"])
    #         tech_index = (self.question_count // 3) % len(technologies)
    #         self.current_topic = technologies[tech_index]
        
    #     # Формируем системный промпт с использованием шаблона
    #     system_prompt = INTERVIEWER_SYSTEM_PROMPT.format(
    #         base_system_prompt=BASE_SYSTEM_PROMPT,
    #         position=context.get("position", "разработчик"),
    #         grade=context.get("grade", "Junior"),
    #         experience=context.get("experience", "не указан"),
    #         technologies=", ".join(context.get("technologies", [])),
    #         current_task="сгенерировать следующий технический вопрос"
    #     )
        
    #     # Формируем промпт для генерации вопроса
    #     user_prompt = NEXT_QUESTION_PROMPT.format(
    #         topic=self.current_topic,
    #         previous_difficulty=self.current_difficulty,
    #         evaluation_summary="ответ принят, продолжаем тему",
    #         observer_recommendation="продолжить исследование текущей темы",
    #         position=context.get("position", "разработчик")
    #     )
        
    #     # Генерируем вопрос
    #     question = await self.llm_client.generate(system_prompt, user_prompt)
        
    #     self.add_internal_thought(f"Сгенерирован новый вопрос по теме '{self.current_topic}'")
        
    #     return question
    # async def _generate_next_question(self, context: Dict[str, Any]) -> str:
    #     """Генерация следующего вопроса."""
        
    #     # Определяем тему для следующего вопроса
    #     if not self.current_topic or self.question_count > 3:
    #         # Меняем тему после 3 вопросов
    #         technologies = context.get("technologies", ["Python", "базы данных", "алгоритмы"])
    #         tech_index = (self.question_count // 3) % len(technologies)
    #         self.current_topic = technologies[tech_index]
        
    #     # Формируем системный промпт
    #     system_prompt = INTERVIEWER_SYSTEM_PROMPT.format(
    #         position=context.get("position", "разработчик"),
    #         grade=context.get("grade", "Junior"),
    #         experience=context.get("experience", "не указан"),
    #         technologies=", ".join(context.get("technologies", [])),
    #         current_task="сгенерировать следующий технический вопрос"
    #     )
        
    #     # Формируем промпт для генерации вопроса
    #     user_prompt = NEXT_QUESTION_PROMPT.format(
    #         topic=self.current_topic,
    #         previous_difficulty=self.current_difficulty,
    #         evaluation_summary="ответ принят, продолжаем тему",
    #         observer_recommendation="продолжить исследование текущей темы",
    #         position=context.get("position", "разработчик")
    #     )
        
    #     # Генерируем вопрос
    #     question = await self.llm_client.generate(system_prompt, user_prompt)
        
    #     self.add_internal_thought(f"Сгенерирован новый вопрос по теме '{self.current_topic}'")
        
    #     return question

    async def _generate_simpler_question(self, context: Dict[str, Any]) -> str:
        """Генерация более простого вопроса."""
        
        # Понижаем сложность
        difficulty_levels = ["senior", "middle", "junior"]
        if self.current_difficulty in difficulty_levels:
            current_index = difficulty_levels.index(self.current_difficulty)
            if current_index > 0:
                self.current_difficulty = difficulty_levels[current_index - 1]
        
        self.add_internal_thought(f"Упрощаю вопрос. Новая сложность: {self.current_difficulty}")
        
        # Берем простую тему
        simple_topics = ["основы программирования", "базовые концепции", "фундаментальные знания"]
        if self.question_count < len(simple_topics):
            self.current_topic = simple_topics[self.question_count]
        else:
            self.current_topic = "основы программирования"
        
        return await self._generate_next_question(context)

    async def _generate_harder_question(self, context: Dict[str, Any]) -> str:
        """Генерация более сложного вопроса."""
        
        # Повышаем сложность
        difficulty_levels = ["junior", "middle", "senior"]
        if self.current_difficulty in difficulty_levels:
            current_index = difficulty_levels.index(self.current_difficulty)
            if current_index < len(difficulty_levels) - 1:
                self.current_difficulty = difficulty_levels[current_index + 1]
        
        self.add_internal_thought(f"Усложняю вопрос. Новая сложность: {self.current_difficulty}")
        
        # Берем сложную тему
        complex_topics = ["архитектура систем", "оптимизация производительности", "масштабирование"]
        if self.question_count < len(complex_topics):
            self.current_topic = complex_topics[self.question_count]
        else:
            self.current_topic = "архитектура систем"
        
        return await self._generate_next_question(context)
    
    # async def _generate_simpler_question(self, context: Dict[str, Any]) -> str:
    #     """Генерация более простого вопроса."""
        
    #     self.current_difficulty = max("junior", self.current_difficulty)  # Не упрощаем дальше junior
        
    #     self.add_internal_thought(f"Упрощаю вопрос. Новая сложность: {self.current_difficulty}")
        
    #     # Меняем тему на более простую
    #     simple_topics = ["базовые концепции", "синтаксис", "фундаментальные знания"]
    #     self.current_topic = simple_topics[self.question_count % len(simple_topics)]
        
    #     return await self._generate_next_question(context)
    
    # async def _generate_harder_question(self, context: Dict[str, Any]) -> str:
    #     """Генерация более сложного вопроса."""
        
    #     # Повышаем сложность
    #     difficulty_levels = ["junior", "middle", "senior"]
    #     current_index = difficulty_levels.index(self.current_difficulty) if self.current_difficulty in difficulty_levels else 0
    #     if current_index < len(difficulty_levels) - 1:
    #         self.current_difficulty = difficulty_levels[current_index + 1]
        
    #     self.add_internal_thought(f"Усложняю вопрос. Новая сложность: {self.current_difficulty}")
        
    #     # Меняем тему на более сложную
    #     complex_topics = ["архитектура", "оптимизация", "масштабирование", "производительность"]
    #     self.current_topic = complex_topics[self.question_count % len(complex_topics)]
        
    #     return await self._generate_next_question(context)
    
    async def _handle_offtopic_response(self, user_input: str, context: Dict[str, Any]) -> str:
        """Обработка оффтопик-ответа."""
        
        self.add_internal_thought("Обнаружен оффтопик. Возвращаю к теме интервью.")
        
        # Получаем последний вопрос
        last_question = self.qa_history[-1]["question"] if self.qa_history else "Предыдущий вопрос"
        
        # Определяем тему оффтопика (простая эвристика)
        offtopic_topic = self._extract_offtopic_topic(user_input)
        
        try:
            # Формируем промпт для обработки оффтопика
            response = await self.llm_client.generate_with_template(
                template=OFFTOPIC_HANDLER_PROMPT,
                variables={
                    "original_question": last_question[:300],  # Ограничиваем длину
                    "offtopic_response": user_input[:200]  # Ограничиваем длину
                },
                system_prompt="Ты - профессиональный интервьюер. Вежливо верни кандидата к теме интервью. Не используй квадратные скобки в ответе."
            )
            
            # Очищаем ответ от остатков шаблона
            response = self._clean_response(response)
            
            return response
            
        except Exception as e:
            # В случае ошибки, используем стандартный ответ
            logger.error(f"Ошибка обработки оффтопика: {e}")
            return "Спасибо за вопрос. Давайте вернемся к теме интервью. Можете рассказать о вашем опыте работы с Python?"
    
    def _extract_offtopic_topic(self, response: str) -> str:
        """Извлечение темы оффтопика из ответа."""
        
        # Простые ключевые слова
        topics = {
            "зарплата": ["зарплат", "оплат", "доход", "заработн"],
            "отпуск": ["отпуск", "отпуска", "каникул"],
            "офис": ["офис", "удаленк", "удалёнк", "рабочее место"],
            "команда": ["команд", "коллектив", "сотрудник"],
            "график": ["график", "расписан", "режим работы"],
            "обучение": ["обучен", "курс", "тренинг", "образован"]
        }
        
        response_lower = response.lower()
        for topic, keywords in topics.items():
            for keyword in keywords:
                if keyword in response_lower:
                    return topic
        
        return "этот вопрос"

    def _clean_response(self, response: str) -> str:
        """Очистка ответа от артефактов шаблона."""
        
        # Удаляем текст в квадратных скобках
        import re
        response = re.sub(r'\[.*?\]', '', response)
        
        # Удаляем текст в звездочках
        response = re.sub(r'\*.*?\*', '', response)
        
        # Удаляем примеры в кавычках, которые могут остаться из промпта
        response = response.replace('"Спасибо за вопрос о...', 'Спасибо за вопрос.')
        
        # Удаляем лишние пробелы и переносы
        response = ' '.join(response.split())
        
        # Обрезаем, если ответ слишком длинный
        if len(response) > 500:
            response = response[:497] + "..."
        
        return response.strip()

    # async def _handle_offtopic_response(self, user_input: str, context: Dict[str, Any]) -> str:
    #     """Обработка оффтопик-ответа."""
        
    #     self.add_internal_thought("Обнаружен оффтопик. Возвращаю к теме интервью.")
        
    #     # Получаем последний вопрос
    #     last_question = self.qa_history[-1]["question"] if self.qa_history else "Предыдущий вопрос"
        
    #     # Формируем промпт для обработки оффтопика
    #     response = await self.llm_client.generate_with_template(
    #         template=OFFTOPIC_HANDLER_PROMPT,
    #         variables={
    #             "original_question": last_question,
    #             "offtopic_response": user_input
    #         },
    #         system_prompt="Ты - профессиональный интервьюер. Вежливо верни кандидата к теме интервью."
    #     )
        
    #     return response
    
    async def _handle_counter_question(self, user_input: str, context: Dict[str, Any]) -> str:
        """Обработка встречного вопроса от кандидата."""
        
        self.add_internal_thought("Кандидат задал встречный вопрос. Отвечаю кратко и возвращаю к интервью.")
        
        # Формируем промпт для ответа на встречный вопрос
        response = await self.llm_client.generate_with_template(
            template=COUNTER_QUESTION_PROMPT,
            variables={
                "candidate_question": user_input,
                "context": f"Интервью на позицию {context.get('position')}"
            },
            system_prompt="Ты - интервьюер. Кратко ответь на вопрос кандидата и вернись к интервью."
        )
        
        return response
    
    async def _detect_offtopic(self, user_input: str, context: Dict[str, Any]) -> bool:
        """Определение, является ли ответ оффтопиком."""
        
        # Простая эвристика для определения оффтопика
        offtopic_keywords = ["погода", "отпуск", "зарплата", "офис", "удаленка", "команда", "начальник"]
        
        user_input_lower = user_input.lower()
        for keyword in offtopic_keywords:
            if keyword in user_input_lower:
                return True
        
        # Проверяем, не слишком ли короткий ответ для оффтопика
        if len(user_input) < 20:
            # Слишком короткий ответ - вероятно, не оффтопик
            return False
        
        return False
    
    async def _detect_counter_question(self, user_input: str) -> bool:
        """Определение, содержит ли ответ встречный вопрос."""
        
        question_keywords = ["?", "почему", "как", "что", "когда", "где", "зачем"]
        user_input_lower = user_input.lower()
        
        # Проверяем наличие знака вопроса
        if "?" in user_input:
            return True
        
        # Проверяем вопросительные слова
        for keyword in question_keywords:
            if keyword in user_input_lower and len(user_input) > 10:
                return True
        
        return False
    
    async def _evaluate_answer_quality(self, user_input: str, context: Dict[str, Any]) -> int:
        """Улучшенная оценка качества ответа (1-10)."""
        
        # Базовая оценка
        score = 5
        
        # 1. Проверка на минимальную длину (должен быть осмысленный ответ)
        if len(user_input.strip()) < 10:
            return 2  # Слишком короткий ответ
        
        # 2. Проверка на бессмысленные ответы
        meaningless_patterns = [
            "тыкаю", "не знаю", "хз", "как бы", "типа", "ну", "эээ",
            "ага", "угу", "да нет", "наверное", "может быть",
            "я не уверен", "скорее всего", "вроде как"
        ]
        
        user_input_lower = user_input.lower()
        for pattern in meaningless_patterns:
            if pattern in user_input_lower:
                score -= 3  # Штраф за неопределенность
        
        # 3. Проверка на уклончивые ответы
        if any(phrase in user_input_lower for phrase in ["не помню", "забыл", "не помню точно"]):
            score -= 2
        
        # 4. Проверка на конкретику - хорошие ответы содержат конкретные термины
        # (это упрощенная проверка, в реальности нужно использовать LLM)
        tech_keywords = ["потому что", "например", "во-первых", "таким образом", "следовательно"]
        has_structure = any(keyword in user_input_lower for keyword in tech_keywords)
        if has_structure:
            score += 2
        
        # 5. Проверка на использование технических терминов (если контекст позволяет)
        if "current_topic" in context:
            # Простая проверка: ответ должен содержать слова, связанные с темой
            topic = context["current_topic"].lower()
            if topic in user_input_lower:
                score += 1
        
        # Ограничиваем диапазон 1-10
        return max(1, min(10, score))
    
    # async def _evaluate_answer_quality(self, user_input: str, context: Dict[str, Any]) -> int:
    #     """Упрощенная оценка качества ответа (1-10)."""
        
    #     # Простые эвристики
    #     score = 5  # Базовая оценка
        
    #     # Длина ответа
    #     if len(user_input) < 20:
    #         score -= 2  # Слишком короткий
    #     elif len(user_input) > 200:
    #         score += 1  # Развернутый ответ
        
    #     # Уверенные формулировки
    #     confident_keywords = ["точно", "определенно", "конечно", "разумеется", "безусловно"]
    #     uncertain_keywords = ["может быть", "кажется", "наверное", "возможно", "не уверен"]
        
    #     user_input_lower = user_input.lower()
    #     for keyword in confident_keywords:
    #         if keyword in user_input_lower:
    #             score += 1
        
    #     for keyword in uncertain_keywords:
    #         if keyword in user_input_lower:
    #             score -= 1
        
    #     # Ограничиваем диапазон 1-10
    #     return max(1, min(10, score))
    
    def get_interview_summary(self) -> Dict[str, Any]:
        """Получение сводки по интервью."""
        
        return {
            "total_questions": self.question_count,
            "topics_covered": list(set([qa.get("topic", "") for qa in self.qa_history if qa.get("topic")])),
            "difficulty_progression": self.current_difficulty,
            "qa_history": self.qa_history
        }
