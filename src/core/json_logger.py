# src/core/json_logger.py
"""
Специализированный логгер для сохранения интервью в JSON формате.
Соответствует требованиям задания.
"""

import json
from typing import Dict, Any, List
from datetime import datetime
from pathlib import Path
import uuid


# class InterviewJSONLogger:
#     """Логгер для сохранения интервью в JSON формате."""
    
#     def __init__(self, team_name: str = "InterviewCoachTeam"):
#         """
#         Инициализация логгера.
        
#         Args:
#             team_name: Название команды
#         """
#         self.team_name = team_name
#         self.interview_id = str(uuid.uuid4())[:8]
        
#         # Структура лога
#         self.log_data: Dict[str, Any] = {
#             "team_name": team_name,
#             "interview_id": self.interview_id,
#             "start_time": datetime.now().isoformat(),
#             "turns": [],
#             "metadata": {
#                 "version": "1.0",
#                 "format": "multi-agent-interview",
#                 "created_at": datetime.now().isoformat()
#             }
#         }
        
#         self.current_turn = 0
    
#     def add_turn(
#         self,
#         agent_visible_message: str,
#         user_message: str,
#         internal_thoughts: str,
#         metadata: Dict[str, Any] = None
#     ) -> int:
#         """
#         Добавление хода в лог.
        
#         Args:
#             agent_visible_message: Сообщение агента (видимое пользователю)
#             user_message: Сообщение пользователя
#             internal_thoughts: Внутренние мысли агентов
#             metadata: Дополнительные метаданные
            
#         Returns:
#             ID хода
#         """
#         self.current_turn += 1
        
#         turn_data = {
#             "turn_id": self.current_turn,
#             "timestamp": datetime.now().isoformat(),
#             "agent_visible_message": agent_visible_message,
#             "user_message": user_message,
#             "internal_thoughts": internal_thoughts,
#             "metadata": metadata or {}
#         }
        
#         self.log_data["turns"].append(turn_data)
        
#         return self.current_turn
    
#     def add_final_feedback(self, feedback: Dict[str, Any]) -> None:
#         """Добавление финального фидбэка в лог."""
#         self.log_data["final_feedback"] = feedback
#         self.log_data["end_time"] = datetime.now().isoformat()
        
#         # Добавляем статистику
#         self.log_data["statistics"] = {
#             "total_turns": len(self.log_data["turns"]),
#             "duration_seconds": self._calculate_duration(),
#             "agent_messages": sum(1 for t in self.log_data["turns"] if t["agent_visible_message"]),
#             "user_messages": sum(1 for t in self.log_data["turns"] if t["user_message"])
#         }
    
#     def save_to_file(self, filepath: str) -> str:
#         """
#         Сохранение лога в файл.
        
#         Args:
#             filepath: Путь к файлу
            
#         Returns:
#             Путь к сохраненному файлу
#         """
#         # Создаем директорию если нужно
#         Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        
#         # Форматируем JSON
#         formatted_json = json.dumps(self.log_data, ensure_ascii=False, indent=2)
        
#         with open(filepath, 'w', encoding='utf-8') as f:
#             f.write(formatted_json)
        
#         return filepath
    
#     def get_log_summary(self) -> Dict[str, Any]:
#         """Получение сводки лога."""
#         return {
#             "interview_id": self.interview_id,
#             "team_name": self.team_name,
#             "total_turns": len(self.log_data.get("turns", [])),
#             "start_time": self.log_data.get("start_time"),
#             "end_time": self.log_data.get("end_time"),
#             "has_feedback": "final_feedback" in self.log_data
#         }
    
#     def _calculate_duration(self) -> float:
#         """Вычисление длительности интервью в секундах."""
#         try:
#             start = datetime.fromisoformat(self.log_data["start_time"])
#             end = datetime.fromisoformat(self.log_data.get("end_time", datetime.now().isoformat()))
#             return (end - start).total_seconds()
#         except:
#             return 0.0
    
#     def export_for_submission(self, filepath: str) -> str:
#         """
#         Экспорт лога в формате для сдачи задания.
        
#         Args:
#             filepath: Путь для сохранения
            
#         Returns:
#             Путь к файлу
#         """
#         # Форматируем специально для задания
#         submission_data = {
#             "team_name": self.team_name,
#             "turns": [
#                 {
#                     "turn_id": turn["turn_id"],
#                     "agent_visible_message": turn["agent_visible_message"],
#                     "user_message": turn["user_message"],
#                     "internal_thoughts": turn["internal_thoughts"]
#                 }
#                 for turn in self.log_data.get("turns", [])
#             ],
#             "final_feedback": self.log_data.get("final_feedback", {})
#         }
        
#         # Сохраняем
#         Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        
#         with open(filepath, 'w', encoding='utf-8') as f:
#             json.dump(submission_data, f, ensure_ascii=False, indent=2)
        
#         return filepath


class InterviewJSONLogger:
    """Логгер для сохранения интервью в JSON формате, соответствующем заданию."""
    
    def __init__(self, participant_name: str = "Кандидат"):
        """
        Инициализация логгера.
        
        Args:
            participant_name: Имя участника (кандидата)
        """
        self.participant_name = participant_name
        self.interview_id = str(uuid.uuid4())[:8]
        
        # Структура лога согласно заданию
        self.log_data: Dict[str, Any] = {
            "participant_name": participant_name,
            "turns": [],
            "final_feedback": None
        }
        
        self.current_turn = 0
    
    def add_turn(
        self,
        agent_visible_message: str,
        user_message: str,
        internal_thoughts: str
    ) -> int:
        """
        Добавление хода в лог.
        
        Args:
            agent_visible_message: Сообщение агента (видимое пользователю)
            user_message: Сообщение пользователя
            internal_thoughts: Внутренние мысли агентов
            
        Returns:
            ID хода
        """
        self.current_turn += 1
        
        turn_data = {
            "turn_id": self.current_turn,
            "agent_visible_message": agent_visible_message,
            "user_message": user_message,
            "internal_thoughts": internal_thoughts
        }
        
        self.log_data["turns"].append(turn_data)
        
        return self.current_turn
    
    def add_final_feedback(self, feedback: Dict[str, Any]) -> None:
        """Добавление финального фидбэка в лог."""
        self.log_data["final_feedback"] = feedback
    
    def save_to_file(self, filepath: str) -> str:
        """
        Сохранение лога в файл в формате задания.
        
        Args:
            filepath: Путь к файлу
            
        Returns:
            Путь к сохраненному файлу
        """
        # Создаем директорию если нужно
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        
        # Форматируем JSON согласно требованиям задания
        formatted_json = json.dumps(self.log_data, ensure_ascii=False, indent=2)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(formatted_json)
        
        return filepath
    
    def export_for_submission(self, filepath: str) -> str:
        """
        Экспорт лога в формате для сдачи задания.
        Создает файл с именем interview_log.json
        
        Args:
            filepath: Путь для сохранения
            
        Returns:
            Путь к файлу
        """
        # Если filepath не содержит имени файла, добавляем interview_log.json
        if not filepath.endswith('.json'):
            if filepath.endswith('/'):
                filepath = filepath + "interview_log.json"
            else:
                filepath = filepath + "/interview_log.json"
        
        return self.save_to_file(filepath)
    
    def get_log_summary(self) -> Dict[str, Any]:
        """Получение сводки лога."""
        return {
            "participant_name": self.participant_name,
            "total_turns": len(self.log_data.get("turns", [])),
            "has_feedback": self.log_data.get("final_feedback") is not None
        }
    
# Глобальный логгер
_global_logger = None

def get_global_logger() -> InterviewJSONLogger:
    """Получение глобального логгера."""
    global _global_logger
    if _global_logger is None:
        _global_logger = InterviewJSONLogger()
    return _global_logger

def set_global_logger(logger: InterviewJSONLogger) -> None:
    """Установка глобального логгера."""
    global _global_logger
    _global_logger = logger
