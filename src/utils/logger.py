"""
Настройка системы логгирования для проекта.
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
from loguru import logger


class JSONLogger:
    """Логгер для сохранения интервью в JSON формате."""
    
    def __init__(self, json_file: str):
        self.json_file = json_file
        self.interview_data: Dict[str, Any] = {
            "team_name": "InterviewCoachTeam",
            "turns": [],
            "start_time": datetime.now().isoformat()
        }
        
    def add_turn(
        self,
        turn_id: int,
        agent_visible_message: str,
        user_message: str,
        internal_thoughts: str
    ) -> None:
        """Добавление хода интервью."""
        
        turn_data = {
            "turn_id": turn_id,
            "agent_visible_message": agent_visible_message,
            "user_message": user_message,
            "internal_thoughts": internal_thoughts,
            "timestamp": datetime.now().isoformat()
        }
        
        self.interview_data["turns"].append(turn_data)
        
        # Автосохранение после каждого хода
        self.save()
        
    def add_final_feedback(self, feedback: Dict[str, Any]) -> None:
        """Добавление финального фидбэка."""
        self.interview_data["final_feedback"] = feedback
        self.interview_data["end_time"] = datetime.now().isoformat()
        self.save()
        
    def save(self) -> None:
        """Сохранение лога в файл."""
        try:
            with open(self.json_file, 'w', encoding='utf-8') as f:
                json.dump(self.interview_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Ошибка сохранения JSON лога: {e}")
    
    def _calculate_duration(self) -> float:
        """Вычисление длительности интервью в секундах."""
        try:
            start = datetime.fromisoformat(self.interview_data["start_time"])
            end = datetime.fromisoformat(self.interview_data.get("end_time", datetime.now().isoformat()))
            return (end - start).total_seconds()
        except:
            return 0.0


# Глобальный экземпляр JSON логгера
json_logger: JSONLogger = None


def setup_logging(
    log_level: str = "INFO",
    log_file: str = "logs/interview_system.log",
    json_log_file: str = "logs/interview_log.json"
) -> None:
    """
    Настройка системы логгирования.
    
    Args:
        log_level: Уровень логгирования (DEBUG, INFO, WARNING, ERROR)
        log_file: Файл для текстовых логов
        json_log_file: Файл для JSON логов (структурированных)
    """
    
    # Создаем директории для логов если их нет
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)
    Path(json_log_file).parent.mkdir(parents=True, exist_ok=True)
    
    # Конфигурация loguru
    logger.remove()  # Удаляем дефолтный handler
    
    # Console handler
    logger.add(
        sys.stdout,
        level=log_level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        colorize=True
    )
    
    # File handler
    logger.add(
        log_file,
        level=log_level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function} - {message}",
        rotation="10 MB",  # Ротация логов
        retention="30 days"  # Хранение 30 дней
    )
    
    # Создаем глобальный JSON логгер
    global json_logger
    json_logger = JSONLogger(json_log_file)
    
    logger.info(f"Логгирование настроено. Уровень: {log_level}")


def get_json_logger() -> JSONLogger:
    """Получение JSON логгера."""
    if json_logger is None:
        raise RuntimeError("JSON логгер не инициализирован. Сначала вызовите setup_logging()")
    return json_logger


# Альтернатива: использование стандартного logging
def setup_basic_logging():
    """Базовая настройка стандартного logging."""
    
    import logging
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('logs/app.log', encoding='utf-8')
        ]
    )
    
    return logging.getLogger(__name__)
