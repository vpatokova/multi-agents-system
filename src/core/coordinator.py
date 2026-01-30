"""
Координатор для управления взаимодействием агентов.
Обеспечивает соблюдение принципов мультиагентной системы.
"""

import asyncio
from typing import Dict, Any, List, Optional, Tuple
import logging
from datetime import datetime

from .memory_manager import InterviewMemory
from .json_logger import InterviewJSONLogger, set_global_logger
from ..agents.interviewer import InterviewerAgent
from ..agents.observer import ObserverAgent

logger = logging.getLogger(__name__)


class InterviewCoordinator:
    """Координатор для управления взаимодействием агентов."""
    
    def __init__(
        self,
        participant_name: str = "Кандидат",
        enable_logging: bool = True
    ):
        """
        Инициализация координатора.
        
        Args:
            patricipant_name: Имя кандидата
            enable_logging: Включить ли логгирование
        """
        self.participant_name = participant_name
        
        # Инициализация компонентов
        self.memory = InterviewMemory(max_history_length=100)
        
        if enable_logging:
            self.json_logger = InterviewJSONLogger(participant_name=participant_name)
            set_global_logger(self.json_logger)
        else:
            self.json_logger = None
        
        # Создаем агентов
        self.interviewer = InterviewerAgent(
            name="Профессиональный Интервьюер"
        )
        
        self.observer = ObserverAgent(
            name="Эксперт Наблюдатель"
        )
        
        # Состояние интервью
        self.is_interview_active = False
        self.current_topic: Optional[str] = None
        self.current_difficulty: str = "junior"
        self.interview_phase: str = "greeting"  # greeting, technical, challenge, closing
        
        # Статистика
        self.stats = {
            "total_questions": 0,
            "correct_answers": 0,
            "incorrect_answers": 0,
            "hallucinations_detected": 0,
            "offtopic_redirects": 0
        }
        
        logger.info(f"Координатор инициализирован. Имя: {participant_name}")
    
    async def start_interview(self, context: Dict[str, Any]) -> str:
        """
        Начало нового интервью.
        
        Args:
            context: Контекст интервью
            
        Returns:
            Приветственное сообщение
        """
        # Инициализация
        self.memory.initialize_context(context)
        self.interviewer.set_interview_context(context)
        self.observer.set_interview_context(context)
        
        self.is_interview_active = True
        self.interview_phase = "greeting"
        
        # Начинаем интервью
        greeting = await self.interviewer.start_interview(context)
        
        # Логируем начало
        self.memory.add_dialogue_turn(
            speaker="interviewer",
            message=greeting,
            role="interviewer"
        )
        
        if self.json_logger:
            self.json_logger.add_turn(
                agent_visible_message=greeting,
                user_message="",
                internal_thoughts=f"[System]: Начало интервью для позиции {context.get('position')}"
            )
        
        logger.info(f"Интервью начато. Контекст: {context}")
        
        return greeting
    
    async def process_user_response(self, user_response: str) -> str:
        """
        Обработка ответа пользователя.
        
        Args:
            user_response: Ответ пользователя
            
        Returns:
            Ответ системы
        """
        if not self.is_interview_active:
            return "Интервью не активен. Начните новое интервью."
        
        # Добавляем ответ пользователя в память
        self.memory.add_dialogue_turn(
            speaker="candidate",
            message=user_response,
            role="candidate"
        )
        
        # Получаем контекст для анализа
        relevant_context, general_context = self.memory.get_relevant_context(
            self.current_topic or "общие вопросы"
        )
        
        # Получаем последний вопрос из истории диалога
        last_question = ""
        for turn in reversed(self.memory.dialogue_history):
            if turn.get("speaker") == "interviewer":
                last_question = turn.get("message", "")
                break
        
        conversation_history = [
            {"role": "assistant" if turn["speaker"] == "interviewer" else "user",
             "content": turn["message"]}
            for turn in general_context[-10:]
        ]
        
        # Создаем контекст для Observer
        context_for_observer = {
            **self.memory.interview_context,
            "current_topic": self.current_topic or "общие вопросы",
            "current_difficulty": self.current_difficulty,
            "last_question": last_question
        }
        
        # Этап 1: Observer анализирует ответ
        logger.debug("Observer анализирует ответ...")
        
        observer_result = await self.observer.analyze_and_recommend(
            question=last_question,
            answer=user_response,
            context=context_for_observer
        )
        
        # Получаем оценку качества от Observer
        answer_quality = observer_result.get("answer_quality", 5)
        
        # Обновляем статистику
        if observer_result.get("has_hallucinations", False):
            self.stats["hallucinations_detected"] += 1
        
        # Этап 2: Внутренний диалог между агентами (скрытый от пользователя)
        internal_dialogue = await self._conduct_internal_dialogue(
            user_response=user_response,
            observer_result=observer_result,
            conversation_history=conversation_history
        )
        
        # Создаем контекст для Interviewer
        context_for_interviewer = {
            **self.memory.interview_context,
            "observer_recommendation": observer_result.get("recommendation", ""),
            "answer_quality": answer_quality,
            "is_good_answer": answer_quality >= 6,
            "current_topic": self.current_topic,
            "current_difficulty": self.current_difficulty,
            "last_question": last_question
        }
        
        # Этап 3: Interviewer генерирует ответ
        logger.debug("Interviewer генерирует ответ...")
        
        interviewer_response = await self.interviewer.respond(
            user_input=user_response,
            context=context_for_interviewer,
            conversation_history=conversation_history
        )

        # Дополнительная очистка перед возвратом
        interviewer_response = self._clean_final_response(interviewer_response)
        
        # Обновляем состояние
        self._update_interview_state(
            user_response=user_response,
            observer_result=observer_result,
            interviewer_response=interviewer_response,
            answer_quality=answer_quality
        )
        
        # Добавляем ответ интервьюера в память
        self.memory.add_dialogue_turn(
            speaker="interviewer",
            message=interviewer_response,
            role="interviewer",
            metadata={
                "phase": self.interview_phase,
                "topic": self.current_topic,
                "difficulty": self.current_difficulty,
                "answer_quality": answer_quality
            }
        )
        
        # Добавляем пару вопрос-ответ в память
        if last_question:
            self.memory.add_qa_pair(
                question=last_question,
                answer=user_response,
                topic=self.current_topic,
                difficulty=self.current_difficulty,
                evaluation={
                    "quality": answer_quality,
                    "has_hallucinations": observer_result.get("has_hallucinations", False),
                    "recommendation": observer_result.get("recommendation", ""),
                    "is_correct": answer_quality >= 6
                }
            )
        
        # Логируем ход
        if self.json_logger:
            self.json_logger.add_turn(
                agent_visible_message=interviewer_response,
                user_message=user_response,
                internal_thoughts=internal_dialogue
            )
        
        # Проверяем завершение интервью
        if self._should_end_interview(user_response):
            await self.end_interview()
            return interviewer_response + "\n\n[Интервью завершено. Генерирую фидбэк...]"
        
        return interviewer_response



    def _clean_final_response(self, response: str) -> str:
        """Финальная очистка ответа перед показом пользователю."""
        
        # Удаляем все, что в квадратных скобках
        import re
        response = re.sub(r'\[.*?\]', '', response)
        
        # Удаляем все, что в звездочках
        response = re.sub(r'\*.*?\*', '', response)
        
        # Удаляем подчеркивания
        response = re.sub(r'_.*?_', '', response)
        
        # Удаляем разделители типа ---, ===
        lines = response.split('\n')
        clean_lines = []
        
        for line in lines:
            line = line.strip()
            
            # Пропускаем пустые строки и разделители
            if not line or line.startswith('---') or line.startswith('==='):
                continue
            
            # Пропускаем строки с техническими комментариями
            if any(keyword in line.lower() for keyword in [
                'следующий вопрос',
                'предлагаю',
                'рассмотрите',
                'дополнительные аспекты',
                'если кандидат'
            ]):
                continue
            
            clean_lines.append(line)
        
        response = ' '.join(clean_lines)
        
        # Удаляем лишние пробелы
        response = ' '.join(response.split())
        
        # Капитализируем первую букву
        if response:
            response = response[0].upper() + response[1:]
        
        # Убедимся, что это законченное предложение
        if response and not response.endswith(('.', '!', '?')):
            response = response + '.'
        
        return response.strip()
    
    async def _conduct_internal_dialogue(
        self,
        user_response: str,
        observer_result: Dict[str, Any],
        conversation_history: List[Dict[str, str]]
    ) -> str:
        """
        Проведение внутреннего диалога между агентами.
        
        Returns:
            Строка с внутренними мыслями для лога
        """
        internal_messages = []
        
        # Мысли Observer
        analysis = observer_result.get("analysis", "Анализ не проведен")[:500]
        internal_messages.append(f"[Observer]: {analysis}...")
        
        # Observer отправляет рекомендацию Interviewer
        recommendation = observer_result.get("recommendation", "")
        internal_messages.append(f"[Observer → Interviewer]: Рекомендация: {recommendation}")
        
        # Interviewer анализирует рекомендацию
        interviewer_context = {
            "observer_recommendation": recommendation,
            "user_response": user_response,
            "answer_quality": observer_result.get("answer_quality", 5)
        }
        
        # Interviewer думает на основе рекомендации
        try:
            interviewer_thoughts = await self.interviewer.think(
                user_input=f"Рекомендация Observer: {recommendation}",
                context=interviewer_context,
                conversation_history=conversation_history
            )
            
            internal_messages.append(f"[Interviewer]: {interviewer_thoughts['thoughts'][:500]}...")
            
            # Решение о следующем действии
            action = interviewer_thoughts.get("action", "continue")
            internal_messages.append(f"[Interviewer]: Решил выполнить действие: {action}")
            
        except Exception as e:
            internal_messages.append(f"[Interviewer]: Произошла ошибка при анализе рекомендации")
            logger.error(f"Ошибка в _conduct_internal_dialogue: {e}")
        
        return "\n".join(internal_messages)
    
    def _update_interview_state(
        self,
        user_response: str,
        observer_result: Dict[str, Any],
        interviewer_response: str,
        answer_quality: int
    ) -> None:
        """Обновление состояния интервью на основе ответов."""
        
        # Обновляем статистику
        if answer_quality >= 6:
            self.stats["correct_answers"] += 1
        else:
            self.stats["incorrect_answers"] += 1
        
        self.stats["total_questions"] += 1
        
        # Определяем, сменить ли тему
        if self.stats["total_questions"] >= 10:
            self.interview_phase = "closing"
        elif self.stats["total_questions"] >= 5:
            self.interview_phase = "deep_dive"
        
        # Обновляем тему и сложность на основе качества ответа
        if self.current_topic:
            # Обновляем сложность на основе качества ответа
            if answer_quality >= 8:  # Отличный ответ - повышаем сложность
                self._increase_difficulty()
            elif answer_quality <= 4:  # Плохой ответ - понижаем сложность
                self._decrease_difficulty()
            
            # Обновляем статистику темы в памяти
            if answer_quality >= 6:
                # Хороший ответ - увеличиваем счетчик правильных ответов
                if self.current_topic in self.memory.topics_covered:
                    self.memory.topics_covered[self.current_topic]["correct_answers"] = \
                        self.memory.topics_covered[self.current_topic].get("correct_answers", 0) + 1
    
    def _increase_difficulty(self):
        """Повышение сложности вопросов."""
        difficulty_levels = ["junior", "middle", "senior"]
        
        if self.current_difficulty in difficulty_levels:
            current_index = difficulty_levels.index(self.current_difficulty)
            if current_index < len(difficulty_levels) - 1:
                self.current_difficulty = difficulty_levels[current_index + 1]
                logger.debug(f"Сложность повышена до {self.current_difficulty}")
    
    def _decrease_difficulty(self):
        """Понижение сложности вопросов."""
        difficulty_levels = ["junior", "middle", "senior"]
        
        if self.current_difficulty in difficulty_levels:
            current_index = difficulty_levels.index(self.current_difficulty)
            if current_index > 0:
                self.current_difficulty = difficulty_levels[current_index - 1]
                logger.debug(f"Сложность понижена до {self.current_difficulty}")
    
    def _should_end_interview(self, user_response: str) -> bool:
        """Определение, следует ли завершить интервью."""
        end_keywords = [
            "стоп интервью", "завершить", "фидбэк", "конец",
            "stop interview", "finish", "feedback", "завершите"
        ]
        
        user_lower = user_response.lower()
        return any(keyword in user_lower for keyword in end_keywords)
    
    def _clean_response_for_display(self, response: str) -> str:
        """Очистка ответа для отображения пользователю."""
        import re
        
        # Удаляем сообщения об ошибках
        if "Отсутствует переменная" in response or "ошибка" in response.lower():
            # Возвращаем стандартный ответ вместо сообщения об ошибке
            return "Давайте продолжим интервью. Можете рассказать о вашем опыте?"
        
        # Удаляем технические сообщения в квадратных скобках
        response = re.sub(r'\[.*?\]', '', response)
        
        # Удаляем примеры и инструкции
        lines = response.split('\n')
        clean_lines = []
        for line in lines:
            # Пропускаем строки, которые выглядят как инструкции
            if line.strip().startswith('*Пример*') or 'например:' in line.lower():
                continue
            clean_lines.append(line)
        
        response = '\n'.join(clean_lines)
        
        # Обрезаем слишком длинные ответы
        if len(response) > 1000:
            response = response[:997] + "..."
        
        return response.strip()
    
    async def end_interview(self) -> Dict[str, Any]:
        """Завершение интервью и генерация фидбэка."""
        self.is_interview_active = False
        
        # Генерируем фидбэк
        feedback = await self.generate_feedback()
        
        # Добавляем фидбэк в лог
        if self.json_logger:
            self.json_logger.add_final_feedback(feedback)
        
        # Сохраняем память
        self.memory.add_dialogue_turn(
            speaker="system",
            message="Интервью завершено",
            role="system",
            metadata={"feedback": feedback}
        )
        
        logger.info(f"Интервью завершено. Всего вопросов: {self.stats['total_questions']}")
        
        return feedback
    
    # async def generate_feedback(self) -> Dict[str, Any]:
    #     """
    #     Генерация структурированного фидбэка.
    #     Соответствует требованиям из задания.
    #     """
        
    #     # Собираем данные для анализа
    #     qa_pairs = self.memory.qa_pairs
    #     topics_stats = {
    #         topic: self.memory.get_topic_performance(topic)
    #         for topic in self.memory.topics_covered
    #     }
        
    #     # А. Вердикт (Decision)
    #     total_questions = self.stats["total_questions"]
    #     correct_answers = self.stats["correct_answers"]
        
    #     if total_questions == 0:
    #         accuracy = 0
    #     else:
    #         accuracy = correct_answers / total_questions
        
    #     # Определяем уровень
    #     if accuracy >= 0.8:
    #         grade = "Senior"
    #         hiring_recommendation = "Strong Hire"
    #     elif accuracy >= 0.6:
    #         grade = "Middle"
    #         hiring_recommendation = "Hire"
    #     elif accuracy >= 0.4:
    #         grade = "Junior"
    #         hiring_recommendation = "No Hire"
    #     else:
    #         grade = "Trainee"
    #         hiring_recommendation = "No Hire"
        
    #     confidence_score = min(95, int(accuracy * 100))
        
    #     # Б. Анализ Hard Skills (Technical Review)
    #     confirmed_skills = []
    #     knowledge_gaps = []
        
    #     # Анализируем каждую тему
    #     for topic, stats in topics_stats.items():
    #         if not stats.get("asked", False):
    #             continue
            
    #         total = stats.get("total_questions", 0)
    #         correct = stats.get("correct_answers", 0)
            
    #         if total == 0:
    #             continue
            
    #         accuracy_per_topic = correct / total
            
    #         # Confirmed Skills: темы с точностью >= 70%
    #         if accuracy_per_topic >= 0.7:
    #             # Находим пример правильного ответа
    #             example_correct = None
    #             for qa in qa_pairs:
    #                 if qa.get("topic") == topic:
    #                     evaluation = qa.get("evaluation", {})
    #                     if evaluation.get("quality", 0) >= 6:  # Хороший ответ
    #                         example_correct = qa.get("question", "")
    #                         break
                
    #             confirmed_skills.append({
    #                 "topic": topic,
    #                 "accuracy": f"{int(accuracy_per_topic * 100)}%",
    #                 "total_questions": total,
    #                 "correct_answers": correct,
    #                 "example_question": example_correct or f"Вопросы по {topic}"
    #             })
            
    #         # Knowledge Gaps: темы с точностью < 70% или явные ошибки
    #         else:
    #             # Находим вопросы, на которые кандидат ответил плохо
    #             incorrect_questions = []
    #             for qa in qa_pairs:
    #                 if qa.get("topic") == topic:
    #                     evaluation = qa.get("evaluation", {})
    #                     quality = evaluation.get("quality", 5)
                        
    #                     if quality < 6:  # Плохой ответ
    #                         incorrect_questions.append({
    #                             "question": qa.get("question", ""),
    #                             "candidate_answer": qa.get("answer", "")[:150] + "..." if qa.get("answer") else "Нет ответа",
    #                             "quality": quality,
    #                             "recommendation": evaluation.get("recommendation", "")
    #                         })
                
    #             # Берем до 3 самых плохих ответов по теме
    #             for qa_info in incorrect_questions[:3]:
    #                 # Генерируем правильный ответ с помощью LLM
    #                 correct_answer = await self._generate_correct_answer(
    #                     question=qa_info["question"],
    #                     candidate_answer=qa_info["candidate_answer"],
    #                     topic=topic
    #                 )
                    
    #                 knowledge_gaps.append({
    #                     "topic": topic,
    #                     "question": qa_info["question"],
    #                     "candidate_answer": qa_info["candidate_answer"],
    #                     "correct_answer": correct_answer,
    #                     "quality_score": f"{qa_info['quality']}/10",
    #                     "suggested_resources": [
    #                         f"Документация по {topic}",
    #                         f"Практические задания по {topic}",
    #                         f"Курс 'Основы {topic}'"
    #                     ]
    #                 })
        
    #     # Если knowledge_gaps пуст, но есть темы с низкой точностью
    #     if not knowledge_gaps:
    #         for topic, stats in topics_stats.items():
    #             if stats.get("asked", False):
    #                 total = stats.get("total_questions", 0)
    #                 correct = stats.get("correct_answers", 0)
                    
    #                 if total > 0 and correct / total < 0.7:
    #                     # Добавляем общую рекомендацию по теме
    #                     knowledge_gaps.append({
    #                         "topic": topic,
    #                         "question": f"Общие вопросы по {topic}",
    #                         "candidate_answer": f"Правильных ответов: {correct} из {total}",
    #                         "correct_answer": f"Необходимо углубить знания по теме {topic}. Рекомендуется изучить основные концепции и практиковаться.",
    #                         "quality_score": f"{int(correct/total*10) if total>0 else 0}/10",
    #                         "suggested_resources": [
    #                             f"Основы {topic} для начинающих",
    #                             f"Практикум по {topic}",
    #                             f"Разбор типовых задач по {topic}"
    #                         ]
    #                     })
        
    #     # В. Анализ Soft Skills & Communication
    #     soft_skills = {
    #         "clarity": self._assess_clarity(),
    #         "honesty": self._assess_honesty(),
    #         "engagement": self._assess_engagement()
    #     }
        
    #     # Г. Персональный Roadmap (Next Steps)
    #     roadmap = []
        
    #     # Создаем roadmap на основе knowledge_gaps
    #     for gap in knowledge_gaps[:5]:  # Ограничиваем 5 пунктами
    #         topic = gap["topic"]
            
    #         # Определяем приоритет на основе темы
    #         if any(keyword in topic.lower() for keyword in ["python", "основ", "баз"]):
    #             priority = "high"
    #             estimated_time = "2-4 недели"
    #         elif any(keyword in topic.lower() for keyword in ["sql", "баз данных", "database"]):
    #             priority = "high"
    #             estimated_time = "3-5 недель"
    #         elif any(keyword in topic.lower() for keyword in ["алгоритм", "структур", "ооп"]):
    #             priority = "medium"
    #             estimated_time = "4-6 недель"
    #         else:
    #             priority = "medium"
    #             estimated_time = "3-4 недели"
            
    #         roadmap.append({
    #             "priority": priority,
    #             "skill": topic,
    #             "action": f"Углубить знания по теме '{topic}'",
    #             "estimated_time": estimated_time,
    #             "resources": gap.get("suggested_resources", []),
    #             "specific_task": f"Решить 5-10 практических задач по {topic}"
    #         })
        
    #     # Если roadmap пустой, но есть темы для развития
    #     if not roadmap and confirmed_skills:
    #         # Предлагаем развитие по темам, которые уже знает
    #         for skill in confirmed_skills[:3]:
    #             topic = skill["topic"]
    #             roadmap.append({
    #                 "priority": "low",
    #                 "skill": f"Продвинутый {topic}",
    #                 "action": f"Углубиться в продвинутые аспекты {topic}",
    #                 "estimated_time": "4-8 недель",
    #                 "resources": [
    #                     f"Продвинутые техники работы с {topic}",
    #                     f"Оптимизация и best practices по {topic}",
    #                     f"Реальные кейсы использования {topic}"
    #                 ],
    #                 "specific_task": f"Изучить продвинутые возможности {topic} на практике"
    #             })
        
    #     # Формируем финальный фидбэк
    #     feedback = {
    #         "verdict": {
    #             "grade": grade,
    #             "hiring_recommendation": hiring_recommendation,
    #             "confidence_score": f"{confidence_score}%",
    #             "summary": self._generate_summary_text(accuracy, grade)
    #         },
    #         "technical_review": {
    #             "confirmed_skills": confirmed_skills,
    #             "knowledge_gaps": knowledge_gaps,
    #             "topics_covered": list(topics_stats.keys()),
    #             "total_topics_asked": len([t for t in topics_stats if topics_stats[t].get("asked", False)])
    #         },
    #         "soft_skills": soft_skills,
    #         "personal_roadmap": roadmap,
    #         "interview_statistics": {
    #             "total_questions": total_questions,
    #             "correct_answers": correct_answers,
    #             "accuracy": f"{int(accuracy * 100)}%",
    #             "hallucinations_detected": self.stats["hallucinations_detected"],
    #             "offtopic_redirects": self.stats["offtopic_redirects"],
    #             "duration_minutes": self.memory.get_interview_summary().get("duration_minutes", 0)
    #         }
    #     }
        
    #     return feedback

    async def _generate_general_recommendation(self, topic: str) -> str:
        """Генерация общей рекомендации по теме."""
        
        try:
            from ..agents.interviewer import InterviewerAgent
            
            temp_interviewer = InterviewerAgent(name="Эксперт")
            
            system_prompt = f"""Ты - технический эксперт и ментор. Объясни, как лучше всего изучить тему {topic}.
            
            Дай практические рекомендации по изучению этой темы. Включи:
            1. С чего начать изучение
            2. Ключевые концепции, которые нужно понять
            3. Практические задачи для закрепления
            4. Полезные ресурсы (курсы, книги, документация)
            
            Будь конкретным и полезным."""
            
            user_prompt = f"Как лучше всего изучить тему '{topic}' для junior-разработчика?"
            
            recommendation = await temp_interviewer.llm_client.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt
            )
            
            return recommendation.strip()
            
        except Exception as e:
            logger.error(f"Ошибка генерации рекомендации: {e}")
            return f"Рекомендуем начать с основ {topic}: изучить документацию, пройти онлайн-курсы и решать практические задачи."

    async def generate_feedback(self) -> Dict[str, Any]:
        """
        Генерация структурированного фидбэка.
        """
        
        # Собираем данные для анализа
        qa_pairs = self.memory.qa_pairs
        topics_stats = {
            topic: self.memory.get_topic_performance(topic)
            for topic in self.memory.topics_covered
        }
        
        # А. Вердикт
        total_questions = self.stats["total_questions"]
        correct_answers = self.stats["correct_answers"]
        
        if total_questions == 0:
            accuracy = 0
        else:
            accuracy = correct_answers / total_questions
        
        # Определяем уровень
        if accuracy >= 0.8:
            grade = "Senior"
            hiring_recommendation = "Strong Hire"
        elif accuracy >= 0.6:
            grade = "Middle"
            hiring_recommendation = "Hire"
        elif accuracy >= 0.4:
            grade = "Junior"
            hiring_recommendation = "No Hire"
        else:
            grade = "Trainee"
            hiring_recommendation = "No Hire"
        
        confidence_score = min(95, int(accuracy * 100))
        
        # Б. Анализ Hard Skills - ИСПРАВЛЯЕМ
        confirmed_skills = []
        knowledge_gaps = []
        
        # Сначала убедимся, что темы есть
        if not topics_stats:
            # Если статистики нет, создаем на основе qa_pairs
            temp_topics = {}
            for qa in qa_pairs:
                topic = qa.get("topic", "общие вопросы")
                if topic not in temp_topics:
                    temp_topics[topic] = {"asked": 0, "correct": 0, "questions": []}
                temp_topics[topic]["asked"] += 1
                temp_topics[topic]["questions"].append(qa)
                
                eval_data = qa.get("evaluation", {})
                if eval_data.get("is_correct", False) or eval_data.get("quality", 0) >= 6:
                    temp_topics[topic]["correct"] += 1
            
            topics_stats = temp_topics
        
        # Теперь анализируем темы
        for topic, stats in topics_stats.items():
            if not stats.get("asked", 0) and not stats.get("total_questions", 0):
                continue
            
            asked = stats.get("asked", 0) or stats.get("total_questions", 0)
            correct = stats.get("correct", 0) or stats.get("correct_answers", 0)
            
            if asked == 0:
                continue
            
            accuracy_per_topic = correct / asked
            
            # Confirmed Skills: темы с точностью >= 60%
            if accuracy_per_topic >= 0.6:
                # Находим пример правильного ответа
                example_correct = None
                for qa in qa_pairs:
                    if qa.get("topic") == topic:
                        evaluation = qa.get("evaluation", {})
                        if evaluation.get("quality", 0) >= 6:
                            example_correct = qa.get("question", "")
                            break
                
                confirmed_skills.append({
                    "topic": topic,
                    "accuracy": f"{int(accuracy_per_topic * 100)}%",
                    "total_questions": asked,
                    "correct_answers": correct,
                    "example_question": example_correct or f"Вопросы по {topic}"
                })
            
            # Knowledge Gaps: темы с точностью < 60%
            else:
                # Находим вопросы, на которые кандидат ответил плохо
                for qa in qa_pairs:
                    if qa.get("topic") == topic:
                        evaluation = qa.get("evaluation", {})
                        quality = evaluation.get("quality", 5)
                        
                        if quality < 6:  # Плохой ответ
                            # Генерируем правильный ответ
                            correct_answer = await self._generate_correct_answer(
                                question=qa.get("question", ""),
                                candidate_answer=qa.get("answer", ""),
                                topic=topic
                            )
                            
                            knowledge_gaps.append({
                                "topic": topic,
                                "question": qa.get("question", ""),
                                "candidate_answer": qa.get("answer", "")[:100] + "..." if qa.get("answer") else "Нет ответа",
                                "correct_answer": correct_answer,
                                "quality_score": f"{quality}/10",
                                "suggested_resources": [
                                    f"Документация по {topic}",
                                    f"Практические задания по {topic}",
                                    f"Курс 'Основы {topic}'"
                                ]
                            })
                            break  # Берем только один вопрос на тему
        
        # Если все еще нет knowledge_gaps, но есть темы с низкой точностью
        if not knowledge_gaps:
            for topic, stats in topics_stats.items():
                asked = stats.get("asked", 0) or stats.get("total_questions", 0)
                correct = stats.get("correct", 0) or stats.get("correct_answers", 0)
                
                if asked > 0 and correct / asked < 0.6:
                    # Генерируем общую рекомендацию
                    correct_answer = await self._generate_general_recommendation(topic)
                    
                    knowledge_gaps.append({
                        "topic": topic,
                        "question": f"Общие вопросы по {topic}",
                        "candidate_answer": f"Правильных ответов: {correct} из {asked}",
                        "correct_answer": correct_answer,
                        "quality_score": f"{int(correct/asked*10) if asked>0 else 0}/10",
                        "suggested_resources": [
                            f"Основы {topic} для начинающих",
                            f"Практикум по {topic}",
                            f"Разбор типовых задач по {topic}"
                        ]
                    })
        
        # В. Анализ Soft Skills & Communication
        soft_skills = {
            "clarity": self._assess_clarity(),
            "honesty": self._assess_honesty(),
            "engagement": self._assess_engagement()
        }
        
        # Г. Персональный Roadmap (Next Steps) - ОБЯЗАТЕЛЬНО!
        roadmap = []
        
        # Создаем roadmap на основе knowledge_gaps
        for i, gap in enumerate(knowledge_gaps[:5], 1):
            topic = gap["topic"]
            
            # Определяем приоритет
            if "python" in topic.lower() or "основ" in topic.lower() or "баз" in topic.lower():
                priority = "высокий"
            else:
                priority = "средний"
            
            roadmap.append({
                "priority": priority,
                "skill": topic,
                "action": f"Изучить основы {topic}",
                "estimated_time": "2-3 недели",
                "specific_task": f"Решить 5 практических задач по {topic}",
                "resources": [
                    f"Онлайн-курс по {topic}",
                    f"Документация и руководства",
                    f"Практические упражнения"
                ]
            })
        
        # Если roadmap пустой, создаем базовые рекомендации
        if not roadmap:
            basic_topics = ["Python", "алгоритмы", "базы данных", "ООП", "структуры данных"]
            for i, topic in enumerate(basic_topics[:3], 1):
                roadmap.append({
                    "priority": "высокий" if i == 1 else "средний",
                    "skill": topic,
                    "action": f"Освоить основы {topic}",
                    "estimated_time": "3-4 недели",
                    "specific_task": f"Пройти практический курс по {topic}",
                    "resources": [
                        f"Бесплатные курсы на Stepik/Coursera",
                        f"Практические задания на LeetCode/HackerRank",
                        f"Документация и книги по теме"
                    ]
                })
        
        # Формируем финальный фидбэк
        feedback = {
            "verdict": {
                "grade": grade,
                "hiring_recommendation": hiring_recommendation,
                "confidence_score": f"{confidence_score}%",
                "summary": self._generate_summary_text(accuracy, grade)
            },
            "technical_review": {
                "confirmed_skills": confirmed_skills,
                "knowledge_gaps": knowledge_gaps,
                "topics_covered": list(topics_stats.keys()),
                "total_topics_asked": len([t for t in topics_stats if topics_stats[t].get("asked", False) or topics_stats[t].get("total_questions", 0) > 0])
            },
            "soft_skills": soft_skills,
            "personal_roadmap": roadmap
        }
        
        return feedback
    
    # async def generate_feedback(self) -> Dict[str, Any]:
    #     """
    #     Генерация структурированного фидбэка.
    #     Соответствует требованиям из задания.
    #     """
        
    #     # Собираем данные для анализа
    #     qa_pairs = self.memory.qa_pairs
    #     topics_stats = {
    #         topic: self.memory.get_topic_performance(topic)
    #         for topic in self.memory.topics_covered
    #     }
        
    #     # А. Вердикт (Decision)
    #     total_questions = self.stats["total_questions"]
    #     correct_answers = self.stats["correct_answers"]
        
    #     if total_questions == 0:
    #         accuracy = 0
    #     else:
    #         accuracy = correct_answers / total_questions
        
    #     # Определяем уровень
    #     if accuracy >= 0.8:
    #         grade = "Senior"
    #         hiring_recommendation = "Strong Hire"
    #     elif accuracy >= 0.6:
    #         grade = "Middle"
    #         hiring_recommendation = "Hire"
    #     elif accuracy >= 0.4:
    #         grade = "Junior"
    #         hiring_recommendation = "No Hire"
    #     else:
    #         grade = "Trainee"
    #         hiring_recommendation = "No Hire"
        
    #     confidence_score = min(95, int(accuracy * 100))
        
    #     # Б. Анализ Hard Skills (Technical Review)
    #     confirmed_skills = []
    #     knowledge_gaps = []
        
    #     for topic, stats in topics_stats.items():
    #         if stats.get("asked", False):
    #             accuracy_val = stats.get("accuracy", 0)
                
    #             if accuracy_val >= 0.7:
    #                 confirmed_skills.append({
    #                     "topic": topic,
    #                     "accuracy": f"{int(accuracy_val * 100)}%",
    #                     "questions_asked": stats.get("total_questions", 0)
    #                 })
    #             else:
    #                 # Находим вопросы по этой теме
    #                 topic_questions = [
    #                     qa for qa in qa_pairs 
    #                     if qa.get("topic") == topic
    #                 ]
                    
    #                 for qa in topic_questions[:2]:  # Берем до 2 вопросов
    #                     knowledge_gaps.append({
    #                         "topic": topic,
    #                         "question": qa.get("question", ""),
    #                         "candidate_answer": qa.get("answer", "")[:100] + "..." if qa.get("answer") else "Нет ответа",
    #                         "correct_answer": "Требуется изучить тему подробнее",
    #                         "suggested_resources": [
    #                             f"Документация по {topic}",
    #                             f"Курсы по основам {topic}"
    #                         ]
    #                     })
        
    #     # В. Анализ Soft Skills & Communication
    #     soft_skills = {
    #         "clarity": self._assess_clarity(),
    #         "honesty": self._assess_honesty(),
    #         "engagement": self._assess_engagement()
    #     }
        
    #     # Г. Персональный Roadmap (Next Steps)
    #     roadmap = []
    #     for gap in knowledge_gaps[:5]:  # Ограничиваем 5 пунктами
    #         roadmap.append({
    #             "priority": "high" if "python" in gap["topic"].lower() else "medium",
    #             "skill": gap["topic"],
    #             "action": f"Изучить основы {gap['topic']}",
    #             "estimated_time": "2-4 недели",
    #             "resources": gap.get("suggested_resources", [])
    #         })
        
    #     # Формируем финальный фидбэк
    #     feedback = {
    #         "verdict": {
    #             "grade": grade,
    #             "hiring_recommendation": hiring_recommendation,
    #             "confidence_score": f"{confidence_score}%",
    #             "summary": self._generate_summary_text(accuracy, grade)
    #         },
    #         "technical_review": {
    #             "confirmed_skills": confirmed_skills,
    #             "knowledge_gaps": knowledge_gaps,
    #             "topics_coverage": len([t for t in topics_stats if topics_stats[t].get("asked", False)])
    #         },
    #         "soft_skills": soft_skills,
    #         "personal_roadmap": roadmap,
    #         "interview_statistics": {
    #             "total_questions": total_questions,
    #             "correct_answers": correct_answers,
    #             "accuracy": f"{int(accuracy * 100)}%",
    #             "hallucinations_detected": self.stats["hallucinations_detected"],
    #             "offtopic_redirects": self.stats["offtopic_redirects"],
    #             "duration_minutes": self.memory.get_interview_summary().get("duration_minutes", 0)
    #         }
    #     }
        
    #     return feedback

    async def _generate_correct_answer(self, question: str, candidate_answer: str, topic: str) -> str:
        """
        Генерация правильного ответа на вопрос, который кандидат завалил.
        Использует LLM для создания объяснения.
        """
        try:
            # Используем Interviewer для генерации правильного ответа
            from ..agents.interviewer import InterviewerAgent
            
            # Создаем временного агента для генерации ответа
            temp_interviewer = InterviewerAgent(name="Ответчик")
            
            system_prompt = f"""Ты - технический эксперт. Тебе нужно объяснить правильный ответ на вопрос.
            
            Вопрос: {question}
            Неправильный ответ кандидата: {candidate_answer}
            Тема: {topic}
            
            Объясни правильный ответ просто и понятно. Включи:
            1. Короткий правильный ответ
            2. Почему ответ кандидата был неправильным
            3. Пример или аналогию для лучшего понимания
            4. Практическое применение этого знания
            
            Будь вежлив и конструктивен."""
            
            user_prompt = f"Сгенерируй правильный и понятный ответ на вопрос: '{question}'"
            
            correct_answer = await temp_interviewer.llm_client.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt
            )
            
            return correct_answer.strip()
            
        except Exception as e:
            logger.error(f"Ошибка генерации правильного ответа: {e}")
            return f"Правильный ответ по теме {topic}. Для деталей изучите документацию и практические примеры."
    
    def _assess_clarity(self) -> str:
        """Оценка ясности изложения."""
        # Упрощенная оценка
        clarity_scores = []
        for turn in self.memory.dialogue_history[-10:]:
            if turn.get("speaker") == "candidate":
                message = turn.get("message", "")
                # Простые эвристики
                if len(message.split()) > 50:
                    clarity_scores.append(3)  # Детальный ответ
                elif len(message.split()) > 20:
                    clarity_scores.append(2)  # Нормальный ответ
                else:
                    clarity_scores.append(1)  # Короткий ответ
        
        if not clarity_scores:
            return "Средняя"
        
        avg_score = sum(clarity_scores) / len(clarity_scores)
        
        if avg_score >= 2.5:
            return "Высокая"
        elif avg_score >= 1.5:
            return "Средняя"
        else:
            return "Низкая"
    
    def _assess_honesty(self) -> str:
        """Оценка честности."""
        if self.stats["hallucinations_detected"] > 2:
            return "Низкая"
        elif self.stats["hallucinations_detected"] > 0:
            return "Средняя"
        else:
            return "Высокая"
    
    def _assess_engagement(self) -> str:
        """Оценка вовлеченности."""
        # Считаем встречные вопросы
        counter_questions = 0
        for turn in self.memory.dialogue_history:
            if turn.get("speaker") == "candidate" and "?" in turn.get("message", ""):
                counter_questions += 1
        
        if counter_questions >= 3:
            return "Высокая"
        elif counter_questions >= 1:
            return "Средняя"
        else:
            return "Низкая"
    
    def _generate_summary_text(self, accuracy: float, grade: str) -> str:
        """Генерация текстового резюме."""
        
        if accuracy >= 0.8:
            summary = (
                f"Кандидат продемонстрировал отличные технические знания, соответствующие уровню {grade}. "
                f"Ответы были точными, развернутыми и демонстрировали глубокое понимание тем. "
                f"Рекомендуется к найму."
            )
        elif accuracy >= 0.6:
            summary = (
                f"Кандидат показал хорошие базовые знания на уровне {grade}. "
                f"Есть понимание основных концепций, но требуются дополнительные знания в некоторых областях. "
                f"Может рассматриваться на позицию с менторингом."
            )
        elif accuracy >= 0.4:
            summary = (
                f"Кандидат находится на уровне {grade}. "
                f"Требуется дополнительное обучение и практика. "
                f"Рекомендуется пройти стажировку или курсы повышения квалификации."
            )
        else:
            summary = (
                f"Кандидат показал низкий уровень знаний. "
                f"Требуется фундаментальное обучение основам программирования. "
                f"Не рекомендуется к найму на текущий момент."
            )
        
        return summary
    
    def save_session(self, filename: str = None) -> str:
        """Сохранение сессии интервью."""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"logs/interview_session_{timestamp}.json"
        
        # Сохраняем память
        self.memory.save_to_file(filename.replace(".json", "_memory.json"))
        
        # Сохраняем лог
        if self.json_logger:
            log_file = self.json_logger.save_to_file(filename)
            
            # Также сохраняем в формате для сдачи
            submission_file = filename.replace(".json", "_submission.json")
            self.json_logger.export_for_submission(submission_file)

            # Сохраняем файл с именем interview_log.json в текущей директории
            self.json_logger.export_for_submission("interview_log.json")
            
            return log_file
        
        return filename
    
    def get_status(self) -> Dict[str, Any]:
        """Получение статуса системы."""
        return {
            "is_interview_active": self.is_interview_active,
            "interview_phase": self.interview_phase,
            "current_topic": self.current_topic,
            "current_difficulty": self.current_difficulty,
            "stats": self.stats,
            "memory_stats": self.memory.get_interview_summary(),
            "agents": {
                "interviewer": self.interviewer.get_status(),
                "observer": self.observer.get_status()
            }
        }
