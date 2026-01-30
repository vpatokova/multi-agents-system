# src/core/memory_manager.py
"""
Продвинутый менеджер памяти для хранения контекста интервью.
Поддерживает долгосрочную память, извлечение релевантного контекста и семантический поиск.
"""

import json
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from collections import defaultdict
import numpy as np
from pathlib import Path


class InterviewMemory:
    """Продвинутая система памяти для хранения контекста интервью."""
    
    def __init__(self, max_history_length: int = 50):
        """
        Инициализация системы памяти.
        
        Args:
            max_history_length: Максимальное количество хранимых сообщений
        """
        self.max_history_length = max_history_length
        
        # Основная история диалога
        self.dialogue_history: List[Dict[str, Any]] = []
        
        # Контекст интервью (позиция, грейд, опыт)
        self.interview_context: Dict[str, Any] = {}
        
        # Темы и их оценка
        self.topics_covered: Dict[str, Dict[str, Any]] = defaultdict(dict)
        
        # Вопросы и ответы с оценками
        self.qa_pairs: List[Dict[str, Any]] = []
        
        # Временные метки
        self.start_time: Optional[datetime] = None
        self.last_update: Optional[datetime] = None
        
    def initialize_context(self, context: Dict[str, Any]) -> None:
        """Инициализация контекста интервью."""
        self.interview_context = context
        self.start_time = datetime.now()
        self.last_update = self.start_time
        
        # Инициализируем темы на основе технологий
        technologies = context.get("technologies", [])
        for tech in technologies:
            self.topics_covered[tech] = {
                "asked": False,
                "correct_answers": 0,
                "total_questions": 0,
                "difficulty": "junior",
                "last_question": None
            }
    
    def add_dialogue_turn(
        self,
        speaker: str,
        message: str,
        role: str = None,
        metadata: Dict[str, Any] = None
    ) -> None:
        """
        Добавление хода диалога в память.
        
        Args:
            speaker: Кто говорит (agent/user)
            message: Сообщение
            role: Роль говорящего (interviewer/observer/candidate)
            metadata: Дополнительные метаданные
        """
        if metadata is None:
            metadata = {}
        
        turn = {
            "timestamp": datetime.now().isoformat(),
            "speaker": speaker,
            "role": role or speaker,
            "message": message,
            "turn_id": len(self.dialogue_history) + 1,
            "metadata": metadata
        }
        
        self.dialogue_history.append(turn)
        
        # Ограничиваем длину истории
        if len(self.dialogue_history) > self.max_history_length:
            self.dialogue_history = self.dialogue_history[-self.max_history_length:]
        
        self.last_update = datetime.now()

    def add_qa_pair(
        self,
        question: str,
        answer: Optional[str] = None,
        topic: Optional[str] = None,
        difficulty: str = "junior",
        evaluation: Optional[Dict[str, Any]] = None
    ) -> None:
        """Добавление пары вопрос-ответ с оценкой."""
        
        qa_pair = {
            "question": question,
            "answer": answer,
            "topic": topic or self._extract_topic(question),
            "difficulty": difficulty,
            "evaluation": evaluation or {},
            "timestamp": datetime.now().isoformat(),
            "qa_id": len(self.qa_pairs) + 1
        }
        
        self.qa_pairs.append(qa_pair)
        
        # Обновляем статистику по теме
        if topic:
            if topic not in self.topics_covered:
                self.topics_covered[topic] = {
                    "asked": True,
                    "correct_answers": 0,
                    "total_questions": 1,
                    "difficulty": difficulty,
                    "last_question": question[:100]
                }
            else:
                self.topics_covered[topic]["total_questions"] += 1
                self.topics_covered[topic]["asked"] = True
            
            # Увеличиваем счетчик правильных ответов, если ответ хороший
            if evaluation and evaluation.get("is_correct", False):
                self.topics_covered[topic]["correct_answers"] += 1
    
    # def add_qa_pair(
    #     self,
    #     question: str,
    #     answer: Optional[str] = None,
    #     topic: Optional[str] = None,
    #     difficulty: str = "junior",
    #     evaluation: Optional[Dict[str, Any]] = None
    # ) -> None:
    #     """Добавление пары вопрос-ответ с оценкой."""
        
    #     qa_pair = {
    #         "question": question,
    #         "answer": answer,
    #         "topic": topic or self._extract_topic(question),
    #         "difficulty": difficulty,
    #         "evaluation": evaluation or {},
    #         "timestamp": datetime.now().isoformat(),
    #         "qa_id": len(self.qa_pairs) + 1
    #     }
        
    #     self.qa_pairs.append(qa_pair)
        
    #     # Обновляем статистику по теме
    #     if topic:
    #         if topic not in self.topics_covered:
    #             self.topics_covered[topic] = {
    #                 "asked": True,
    #                 "correct_answers": 0,
    #                 "total_questions": 1,
    #                 "difficulty": difficulty,
    #                 "last_question": question[:100]
    #             }
    #         else:
    #             self.topics_covered[topic]["total_questions"] += 1
    #             self.topics_covered[topic]["asked"] = True
                
    #             if evaluation and evaluation.get("is_correct", False):
    #                 self.topics_covered[topic]["correct_answers"] += 1
    
    def update_topic_difficulty(self, topic: str, performance_score: float) -> str:
        """
        Обновление сложности темы на основе производительности.
        
        Args:
            topic: Тема
            performance_score: Оценка производительности (0-1)
            
        Returns:
            Новая сложность
        """
        if topic not in self.topics_covered:
            return "junior"
        
        current_diff = self.topics_covered[topic].get("difficulty", "junior")
        difficulty_levels = ["junior", "middle", "senior"]
        
        try:
            current_index = difficulty_levels.index(current_diff)
        except ValueError:
            current_index = 0
        
        if performance_score > 0.8:  # Хорошие ответы - повышаем сложность
            new_index = min(current_index + 1, len(difficulty_levels) - 1)
        elif performance_score < 0.4:  # Плохие ответы - понижаем сложность
            new_index = max(current_index - 1, 0)
        else:
            new_index = current_index
        
        new_difficulty = difficulty_levels[new_index]
        self.topics_covered[topic]["difficulty"] = new_difficulty
        
        return new_difficulty
    
    def get_recent_context(self, n_turns: int = 10) -> List[Dict[str, Any]]:
        """Получение последних n ходов диалога."""
        return self.dialogue_history[-n_turns:] if self.dialogue_history else []
    
    def get_relevant_context(
        self,
        current_topic: str,
        max_turns: int = 15
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Получение релевантного контекста для текущей темы.
        
        Args:
            current_topic: Текущая тема
            max_turns: Максимальное количество возвращаемых ходов
            
        Returns:
            Кортеж (релевантные ходы, общая история)
        """
        if not self.dialogue_history:
            return [], []
        
        # Ищем ходы, связанные с текущей темой
        relevant_turns = []
        for turn in self.dialogue_history[-max_turns:]:
            message = turn.get("message", "").lower()
            speaker = turn.get("speaker", "")
            
            # Проверяем релевантность по ключевым словам
            topic_keywords = current_topic.lower().split()
            if any(keyword in message for keyword in topic_keywords):
                relevant_turns.append(turn)
            elif speaker == "candidate" and "?" in message:
                # Вопросы кандидата всегда релевантны
                relevant_turns.append(turn)
        
        # Возвращаем последние ходы как общий контекст
        general_context = self.dialogue_history[-max_turns:]
        
        return relevant_turns, general_context
    
    def has_been_asked(self, question: str, similarity_threshold: float = 0.7) -> bool:
        """
        Проверка, был ли задан похожий вопрос ранее.
        
        Args:
            question: Вопрос для проверки
            similarity_threshold: Порог схожести (0-1)
            
        Returns:
            True если похожий вопрос уже задавался
        """
        if not self.qa_pairs:
            return False
        
        question_lower = question.lower()
        
        for qa in self.qa_pairs:
            prev_question = qa.get("question", "").lower()
            
            # Простая проверка на схожесть
            if self._calculate_similarity(question_lower, prev_question) > similarity_threshold:
                return True
        
        return False
    
    def get_topic_performance(self, topic: str) -> Dict[str, Any]:
        """Получение статистики по теме."""
        if topic not in self.topics_covered:
            return {
                "asked": False,
                "correct_answers": 0,
                "total_questions": 0,
                "accuracy": 0.0,
                "difficulty": "junior"
            }
        
        stats = self.topics_covered[topic].copy()
        total = stats.get("total_questions", 0)
        correct = stats.get("correct_answers", 0)
        
        if total > 0:
            stats["accuracy"] = correct / total
        else:
            stats["accuracy"] = 0.0
        
        return stats
    
    def get_interview_summary(self) -> Dict[str, Any]:
        """Получение сводки по всему интервью."""
        
        total_questions = len(self.qa_pairs)
        
        if total_questions == 0:
            return {
                "total_questions": 0,
                "topics_covered": [],
                "average_accuracy": 0.0,
                "duration_minutes": 0
            }
        
        # Вычисляем среднюю точность
        accuracies = []
        for topic, stats in self.topics_covered.items():
            if stats.get("asked", False):
                total = stats.get("total_questions", 0)
                correct = stats.get("correct_answers", 0)
                if total > 0:
                    accuracies.append(correct / total)
        
        avg_accuracy = sum(accuracies) / len(accuracies) if accuracies else 0
        
        # Вычисляем длительность
        duration_minutes = 0
        if self.start_time and self.last_update:
            duration = self.last_update - self.start_time
            duration_minutes = duration.total_seconds() / 60
        
        return {
            "total_questions": total_questions,
            "topics_covered": list(self.topics_covered.keys()),
            "topics_asked": [t for t, s in self.topics_covered.items() if s.get("asked", False)],
            "average_accuracy": round(avg_accuracy, 2),
            "duration_minutes": round(duration_minutes, 1),
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "last_update": self.last_update.isoformat() if self.last_update else None
        }
    
    def _extract_topic(self, text: str) -> str:
        """Извлечение темы из текста."""
        # Простая эвристика для извлечения темы
        common_topics = {
            "python": ["python", "питон"],
            "sql": ["sql", "база данных", "database"],
            "git": ["git", "версионный"],
            "алгоритмы": ["алгоритм", "структур", "сортировк", "поиск"],
            "ооп": ["ооп", "объект", "класс", "наследование"],
            "базы данных": ["база", "sql", "таблиц", "join"],
            "веб": ["веб", "http", "api", "rest", "json"],
            "тестирование": ["тест", "unit", "pytest", "tdd"]
        }
        
        text_lower = text.lower()
        
        for topic, keywords in common_topics.items():
            if any(keyword in text_lower for keyword in keywords):
                return topic
        
        # Если не нашли, возвращаем общую тему
        return "общие вопросы"
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Вычисление схожести двух текстов (упрощенная версия)."""
        if not text1 or not text2:
            return 0.0
        
        # Простая метрика схожести на основе общих слов
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union)
    
    def save_to_file(self, filepath: str) -> None:
        """Сохранение памяти в файл."""
        data = {
            "interview_context": self.interview_context,
            "dialogue_history": self.dialogue_history,
            "topics_covered": dict(self.topics_covered),
            "qa_pairs": self.qa_pairs,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "last_update": self.last_update.isoformat() if self.last_update else None,
            "metadata": {
                "max_history_length": self.max_history_length,
                "total_turns": len(self.dialogue_history),
                "total_qa_pairs": len(self.qa_pairs)
            }
        }
        
        # Создаем директорию если нужно
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def load_from_file(self, filepath: str) -> None:
        """Загрузка памяти из файла."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.interview_context = data.get("interview_context", {})
            self.dialogue_history = data.get("dialogue_history", [])
            
            # Восстанавливаем defaultdict
            topics_data = data.get("topics_covered", {})
            self.topics_covered = defaultdict(dict, topics_data)
            
            self.qa_pairs = data.get("qa_pairs", [])
            
            # Восстанавливаем даты
            if data.get("start_time"):
                self.start_time = datetime.fromisoformat(data["start_time"])
            if data.get("last_update"):
                self.last_update = datetime.fromisoformat(data["last_update"])
                
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Ошибка загрузки памяти: {e}")