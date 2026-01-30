# src/agents/observer.py
"""
Агент Observer - анализирует ответы кандидата и дает рекомендации Interviewer.
"""

import asyncio
from typing import Dict, Any, List, Optional
import logging
from ..core.llm_client import MistralClientFactory
from .base_agent import BaseAgent
from config.prompts import (
    BASE_SYSTEM_PROMPT,
    OBSERVER_SYSTEM_PROMPT,
    EVALUATION_PROMPT
)

logger = logging.getLogger(__name__)


class ObserverAgent(BaseAgent):
    """Агент-наблюдатель для анализа ответов кандидата."""
    
    def __init__(
        self,
        name: str = "Наблюдатель",
        llm_model: str = None,
        **kwargs
    ):
        """
        Инициализация агента-наблюдателя.
        
        Args:
            name: Имя агента
            llm_provider: Провайдер LLM
            llm_model: Модель LLM
        """
        super().__init__(name=name, role="observer", **kwargs)
        
        # Инициализация LLM клиента
        self.llm_client = MistralClientFactory.create_client(
            model=llm_model,
            temperature=0.3,  # Более консервативный для анализа
            max_tokens=800
        )
        
        # История оценок
        self.evaluation_history: List[Dict[str, Any]] = []
        
        logger.info(f"Агент Observer '{name}' инициализирован")
    
    async def think(
        self, 
        user_input: str, 
        context: Dict[str, Any],
        conversation_history: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """
        Observer анализирует ответ кандидата и генерирует рекомендации.
        """
        
        self.add_internal_thought(f"Анализирую ответ кандидата: '{user_input[:150]}...'")
        
        # Получаем последний вопрос из истории диалога
        last_question = self._extract_last_question(conversation_history)
        
        # Анализируем ответ
        analysis = await self._analyze_answer(
            question=last_question,
            answer=user_input,
            context=context
        )
        
        # Генерируем рекомендацию для Interviewer
        recommendation = await self._generate_recommendation(analysis, context)
        
        # Сохраняем оценку в историю
        evaluation_record = {
            "question": last_question,
            "answer": user_input,
            "analysis": analysis,
            "recommendation": recommendation,
            "timestamp": asyncio.get_event_loop().time()
        }
        self.evaluation_history.append(evaluation_record)
        
        thoughts = f"""
        ЗАВЕРШЕН АНАЛИЗ ОТВЕТА КАНДИДАТА:
        
        ВОПРОС: {last_question[:100]}...
        ОТВЕТ: {user_input[:100]}...
        
        КРАТКИЙ АНАЛИЗ:
        {analysis[:200]}...
        
        РЕКОМЕНДАЦИЯ ДЛЯ INTERVIEWER:
        {recommendation}
        """
        
        self.add_internal_thought(thoughts.strip())
        
        return {
            "thoughts": thoughts,
            "action": "provide_recommendation",
            "parameters": {
                "analysis": analysis,
                "recommendation": recommendation,
                "question": last_question
            },
            "confidence": 0.9
        }
    
    async def respond(
        self, 
        user_input: str, 
        context: Dict[str, Any],
        conversation_history: List[Dict[str, str]]
    ) -> str:
        """
        Observer не отвечает напрямую пользователю.
        Вместо этого он отправляет рекомендации Interviewer.
        """
        
        # Observer не генерирует ответы для пользователя
        return "[Observer]: Это внутреннее сообщение для Interviewer. Пользователь его не видит."
    
    async def analyze_and_recommend(
        self,
        question: str,
        answer: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Анализ ответа и генерация рекомендации.
        Добавляем проверку на содержательность.
        """
        
        self.add_internal_thought(f"Запускаю анализ ответа на вопрос: '{question[:100]}...'")
        
        # Проверяем, является ли ответ содержательным
        is_meaningful = self._is_answer_meaningful(answer, question)
        
        # Если ответ не содержательный, сразу возвращаем рекомендацию об упрощении
        if not is_meaningful:
            return {
                "analysis": "Ответ не содержит полезной информации или является неполным.",
                "recommendation": "упростить вопрос или попросить дать более развернутый ответ",
                "has_hallucinations": False,
                "confidence_score": 0.3,
                "answer_quality": 2
            }
        
        # Если ответ содержательный, проводим полный анализ
        analysis = await self._analyze_answer(question, answer, context)
        
        # Извлекаем оценку качества из анализа
        answer_quality = self._extract_quality_score(analysis)
        
        # Генерируем рекомендацию на основе анализа
        recommendation = await self._generate_recommendation(analysis, context)
        
        return {
            "analysis": analysis,
            "recommendation": recommendation,
            "has_hallucinations": self._detect_hallucinations_in_analysis(analysis),
            "confidence_score": self._extract_confidence_score(analysis),
            "answer_quality": answer_quality
        }

    def _is_answer_meaningful(self, answer: str, question: str) -> bool:
        """Проверка, является ли ответ содержательным."""
        
        # Минимальная длина содержательного ответа
        if len(answer.strip()) < 15:
            return False
        
        # Проверка на бессмысленные или уклончивые ответы
        meaningless_patterns = [
            "не знаю", "хз", "не помню", "забыл", "тыкаю", "как бы",
            "типа", "ну", "эээ", "ага", "угу", "да нет",
            "скорее всего", "возможно", "может быть", "наверное"
        ]
        
        answer_lower = answer.lower()
        for pattern in meaningless_patterns:
            if pattern in answer_lower:
                return False
        
        # Проверка, что ответ хотя бы пытается ответить на вопрос
        # (простая эвристика: ответ должен содержать хотя бы одно из ключевых слов вопроса)
        question_keywords = set(question.lower().split())
        answer_words = set(answer_lower.split())
        common_words = question_keywords.intersection(answer_words)
        
        if len(common_words) == 0:
            # Ответ не содержит ни одного слова из вопроса - возможно, оффтоп
            return False
        
        return True

    def _extract_quality_score(self, analysis: str) -> int:
        """Извлечение оценки качества из анализа."""
        import re
        
        # Ищем паттерн "ТОЧНОСТЬ: X/10"
        pattern = r"ТОЧНОСТЬ:\s*(\d+)/10"
        match = re.search(pattern, analysis, re.IGNORECASE)
        
        if match:
            return int(match.group(1))
        
        # Альтернативный поиск по ключевым словам
        if "отличн" in analysis.lower() or "10/10" in analysis.lower():
            return 9
        elif "хорошо" in analysis.lower() or "8/10" in analysis.lower():
            return 8
        elif "удовлетворительно" in analysis.lower() or "6/10" in analysis.lower():
            return 6
        elif "плохо" in analysis.lower() or "3/10" in analysis.lower():
            return 3
        else:
            return 5  # Средняя оценка по умолчанию
    
    # async def analyze_and_recommend(
    #     self,
    #     question: str,
    #     answer: str,
    #     context: Dict[str, Any]
    # ) -> Dict[str, Any]:
    #     """
    #     Основной метод: анализ ответа и генерация рекомендации.
        
    #     Args:
    #         question: Вопрос, который задал Interviewer
    #         answer: Ответ кандидата
    #         context: Контекст интервью
            
    #     Returns:
    #         Словарь с анализом и рекомендацией
    #     """
        
    #     self.add_internal_thought(f"Запускаю анализ ответа на вопрос: '{question[:100]}...'")
        
    #     # Анализируем ответ
    #     analysis = await self._analyze_answer(question, answer, context)
        
    #     # Генерируем рекомендацию
    #     recommendation = await self._generate_recommendation(analysis, context)
        
    #     # Сохраняем в историю
    #     self.evaluation_history.append({
    #         "question": question,
    #         "answer": answer,
    #         "analysis": analysis,
    #         "recommendation": recommendation
    #     })
        
    #     return {
    #         "analysis": analysis,
    #         "recommendation": recommendation,
    #         "has_hallucinations": self._detect_hallucinations_in_analysis(analysis),
    #         "confidence_score": self._extract_confidence_score(analysis)
    #     }
    
    # async def _analyze_answer(
    #     self,
    #     question: str,
    #     answer: str,
    #     context: Dict[str, Any]
    # ) -> str:
    #     """Детальный анализ ответа кандидата."""
        
    #     # Формируем системный промпт для Observer
    #     system_prompt = OBSERVER_SYSTEM_PROMPT.format(
    #         position=context.get("position", "разработчик"),
    #         current_topic=context.get("current_topic", "общие вопросы"),
    #         current_difficulty=context.get("current_difficulty", "junior"),
    #         candidate_level=context.get("grade", "Junior"),
    #         last_question=question[:200],
    #         candidate_answer=answer[:500]
    #     )
        
    #     # Формируем промпт для анализа
    #     user_prompt = EVALUATION_PROMPT.format(
    #         question=question,
    #         answer=answer
    #     )
        
    #     # Генерируем анализ
    #     analysis = await self.llm_client.generate(system_prompt, user_prompt)
        
    #     return analysis
    
    async def _analyze_answer(
        self,
        question: str,
        answer: str,
        context: Dict[str, Any]
    ) -> str:
        """Детальный анализ ответа кандидата."""
        
        # Формируем системный промпт для Observer с использованием шаблона
        system_prompt = OBSERVER_SYSTEM_PROMPT.format(
            base_system_prompt=BASE_SYSTEM_PROMPT,
            position=context.get("position", "разработчик"),
            current_topic=context.get("current_topic", "общие вопросы"),
            current_difficulty=context.get("current_difficulty", "junior"),
            candidate_level=context.get("grade", "Junior"),
            last_question=question[:200],
            candidate_answer=answer[:500]
        )
        
        # Формируем промпт для анализа
        user_prompt = EVALUATION_PROMPT.format(
            question=question,
            answer=answer
        )
        
        # Генерируем анализ
        analysis = await self.llm_client.generate(system_prompt, user_prompt)
        
        return analysis
    
    async def _generate_recommendation(
        self,
        analysis: str,
        context: Dict[str, Any]
    ) -> str:
        """Генерация рекомендации для Interviewer на основе анализа."""
        
        # Анализируем текст анализа для извлечения ключевых моментов
        recommendation_rules = [
            ("ТОЧНОСТЬ: [0-5]/10", "упростить вопрос или дать подсказку"),
            ("ТОЧНОСТЬ: [6-7]/10", "продолжить текущую тему"),
            ("ТОЧНОСТЬ: [8-10]/10", "усложнить вопрос или сменить тему"),
            ("ГАЛЛЮЦИНАЦИИ: Да", "вежливо указать на ошибку и задать уточняющий вопрос"),
            ("ПРОБЕЛЫ:", "задать вопрос по выявленным пробелам"),
            ("УВЕРЕННОСТЬ: [0-5]/10", "задать более простой вопрос для восстановления уверенности"),
            ("УВЕРЕННОСТЬ: [6-10]/10", "продолжить с текущей сложностью")
        ]
        
        # Определяем рекомендацию на основе анализа
        recommendation = "продолжить интервью с текущей темой и сложностью"
        
        analysis_lower = analysis.lower()
        
        if "галлюцинации: да" in analysis_lower or "выдум" in analysis_lower:
            recommendation = "вежливо указать на неточность и задать уточняющий вопрос по той же теме"
        elif "не знаю" in analysis_lower or "не ответил" in analysis_lower:
            recommendation = "упростить вопрос или перейти к более базовой теме"
        elif "отличн" in analysis_lower or "превосходн" in analysis_lower:
            recommendation = "усложнить следующий вопрос или перейти к более продвинутой теме"
        elif "уверенность: низк" in analysis_lower:
            recommendation = "задать более простой вопрос для восстановления уверенности кандидата"
        
        # Добавляем контекстные детали
        position = context.get("position", "")
        if "backend" in position.lower():
            recommendation += " с акцентом на практические задачи бэкенда"
        elif "frontend" in position.lower():
            recommendation += " с фокусом на интерфейсные технологии"
        
        return recommendation
    
    def _extract_last_question(self, conversation_history: List[Dict[str, str]]) -> str:
        """Извлечение последнего вопроса из истории диалога."""
        
        # Ищем последнее сообщение от ассистента (Interviewer)
        for message in reversed(conversation_history):
            if message.get("role") in ["assistant", "interviewer"]:
                return message.get("content", "Вопрос не найден")
        
        return "Расскажите о вашем опыте"
    
    def _detect_hallucinations_in_analysis(self, analysis: str) -> bool:
        """Определение, выявил ли анализ галлюцинации."""
        
        hallucination_keywords = [
            "галлюцинации: да",
            "ложные утверждения",
            "выдумал",
            "ошибочно утверждает",
            "не соответствует фактам"
        ]
        
        analysis_lower = analysis.lower()
        for keyword in hallucination_keywords:
            if keyword in analysis_lower:
                return True
        
        return False
    
    def _extract_confidence_score(self, analysis: str) -> float:
        """Извлечение оценки уверенности из анализа."""
        
        import re
        
        # Ищем паттерн "УВЕРЕННОСТЬ: X/10"
        pattern = r"УВЕРЕННОСТЬ:\s*(\d+)/10"
        match = re.search(pattern, analysis, re.IGNORECASE)
        
        if match:
            score = int(match.group(1))
            return score / 10.0  # Конвертируем в 0-1
        
        # Альтернативный поиск
        if "высокая уверенность" in analysis.lower():
            return 0.8
        elif "средняя уверенность" in analysis.lower():
            return 0.5
        elif "низкая уверенность" in analysis.lower():
            return 0.2
        
        return 0.5  # По умолчанию
    
    def get_evaluation_summary(self) -> Dict[str, Any]:
        """Получение сводки всех оценок."""
        
        if not self.evaluation_history:
            return {"total_evaluations": 0, "average_confidence": 0}
        
        # Вычисляем среднюю уверенность
        confidence_scores = []
        hallucination_count = 0
        
        for eval_record in self.evaluation_history:
            analysis = eval_record.get("analysis", "")
            confidence = self._extract_confidence_score(analysis)
            confidence_scores.append(confidence)
            
            if self._detect_hallucinations_in_analysis(analysis):
                hallucination_count += 1
        
        avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0
        
        return {
            "total_evaluations": len(self.evaluation_history),
            "average_confidence": round(avg_confidence, 2),
            "hallucination_count": hallucination_count,
            "recommendations": [e.get("recommendation", "") for e in self.evaluation_history[-5:]]  # Последние 5 рекомендаций
        }
    async def _update_interview_state(
        self,
        user_response: str,
        observer_analysis: Dict[str, Any],
        interviewer_response: str
    ) -> None:
        """Обновление состояния интервью на основе анализа Observer."""
        
        # Получаем детальный анализ от Observer
        analysis = observer_analysis["parameters"].get("analysis", "")
        recommendation = observer_analysis["parameters"].get("recommendation", "")
        
        # Анализируем, был ли ответ хорошим
        is_good_answer = self._is_good_answer_based_on_analysis(analysis, user_response)
        
        # Обновляем статистику
        if is_good_answer:
            self.stats["correct_answers"] += 1
        else:
            self.stats["incorrect_answers"] += 1
        
        self.stats["total_questions"] += 1
        
        # Обновляем тему и сложность ТОЛЬКО если ответ был хорошим
        if self.current_topic and is_good_answer:
            topic_stats = self.memory.get_topic_performance(self.current_topic)
            accuracy = topic_stats.get("accuracy", 0.5)
            
            # Только если ответ хороший, повышаем сложность
            new_difficulty = self.memory.update_topic_difficulty(
                self.current_topic,
                accuracy
            )
            self.current_difficulty = new_difficulty
        elif not is_good_answer:
            # Если ответ плохой, упрощаем
            self._decrease_difficulty()
        
        # Логируем решение
        self.add_internal_thought(
            f"Ответ оценивается как {'хороший' if is_good_answer else 'плохой'}. "
            f"Рекомендация Observer: {recommendation}"
        )

    def _is_good_answer_based_on_analysis(self, analysis: str, user_response: str) -> bool:
        """Определение качества ответа на основе анализа Observer."""
        
        analysis_lower = analysis.lower()
        user_lower = user_response.lower()
        
        # Признаки плохого ответа
        bad_signs = [
            "не знаю",
            "не уверен", 
            "не помню",
            "забыл",
            "галлюцинации: да",
            "ошибка",
            "неправильно",
            "неверно",
            "частично верный",
            "неполный",
            "не раскрыл",
            "пробелы"
        ]
        
        # Признаки хорошего ответа
        good_signs = [
            "точно",
            "правильно", 
            "верно",
            "полный",
            "полностью",
            "хорошо",
            "отлично",
            "превосходно",
            "исчерпывающе"
        ]
        
        # Если анализ содержит признаки плохого ответа
        for sign in bad_signs:
            if sign in analysis_lower:
                return False
        
        # Если анализ содержит признаки хорошего ответа
        for sign in good_signs:
            if sign in analysis_lower:
                return True
        
        # Если анализ неоднозначный, проверяем сам ответ
        return self._is_response_meaningful(user_response)

    def _is_response_meaningful(self, response: str) -> bool:
        """Проверка, является ли ответ осмысленным."""
        
        if len(response.strip()) < 15:
            return False
        
        # Проверка на бессмысленные ответы
        meaningless_responses = [
            "тыкаю туда сюда",
            "не знаю что сказать",
            "давайте дальше",
            "хз",
            "эээ",
            "ну",
            "как бы",
            "типа того"
        ]
        
        response_lower = response.lower()
        for meaningless in meaningless_responses:
            if meaningless in response_lower:
                return False
        
        # Проверка, содержит ли ответ хотя бы одно законченное предложение
        if "." not in response and "!" not in response and "?" not in response:
            # Возможно, это неполный ответ
            if len(response.split()) < 5:
                return False
        
        return True

    def _decrease_difficulty(self):
        """Упрощение сложности вопросов."""
        difficulty_levels = ["senior", "middle", "junior"]
        
        if self.current_difficulty in difficulty_levels:
            current_index = difficulty_levels.index(self.current_difficulty)
            if current_index > 0:
                self.current_difficulty = difficulty_levels[current_index - 1]
        
        self.add_internal_thought(f"Сложность понижена до {self.current_difficulty}")
