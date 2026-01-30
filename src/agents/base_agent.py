"""
Базовый класс для всех агентов в системе.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
import logging
from datetime import datetime


class AgentMessage(BaseModel):
    """Модель для сообщений между агентами."""
    role: str = Field(description="Роль отправителя")
    content: str = Field(description="Содержание сообщения")
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BaseAgent(ABC):
    """
    Абстрактный базовый класс для всех агентов.
    Каждый агент должен уметь "мыслить" и "отвечать".
    """
    
    def __init__(
        self,
        name: str,
        role: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs
    ):
        """
        Инициализация агента.
        
        Args:
            name: Уникальное имя агента
            role: Роль в системе (interviewer, observer, etc.)
            model: Модель LLM для использования
            temperature: Креативность модели (0-1)
            max_tokens: Максимальное количество токенов в ответе
        """
        self.name = name
        self.role = role
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        
        # История внутренних мыслей агента
        self.internal_thoughts: List[str] = []
        
        # История сообщений
        self.message_history: List[AgentMessage] = []
        
        # Логгер
        self.logger = logging.getLogger(f"agent.{name}")
        
        # Контекст интервью
        self.interview_context: Dict[str, Any] = {}
        
        self.logger.info(f"Агент {name} ({role}) инициализирован")
    
    def set_interview_context(self, context: Dict[str, Any]) -> None:
        """
        Установка контекста интервью.
        
        Args:
            context: Словарь с контекстом
                    {
                        "position": "Backend Developer",
                        "grade": "Junior", 
                        "experience": "1 год",
                        "technologies": ["Python", "Django", "SQL"]
                    }
        """
        self.interview_context = context
        self.logger.debug(f"Контекст установлен для {self.name}: {context}")
    
    @abstractmethod
    async def think(
        self, 
        user_input: str, 
        context: Dict[str, Any],
        conversation_history: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """
        Внутренний процесс "мышления" агента.
        Анализирует ввод пользователя и решает, как действовать.
        
        Args:
            user_input: Последнее сообщение пользователя
            context: Текущий контекст диалога
            conversation_history: История всего диалога
            
        Returns:
            Dict с мыслями и решениями агента
            {
                "thoughts": "Внутренний монолог агента",
                "action": "next_action_name",
                "parameters": {...},
                "confidence": 0.95
            }
        """
        pass
    
    @abstractmethod
    async def respond(
        self, 
        user_input: str, 
        context: Dict[str, Any],
        conversation_history: List[Dict[str, str]]
    ) -> str:
        """
        Генерация ответа пользователю.
        
        Args:
            user_input: Последнее сообщение пользователя
            context: Текущий контекст диалога
            conversation_history: История всего диалога
            
        Returns:
            Ответ агента пользователю
        """
        pass
    
    def add_internal_thought(self, thought: str) -> None:
        """
        Добавление внутренней мысли в историю.
        
        Args:
            thought: Внутренняя мысль агента
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_thought = f"[{timestamp}] {self.name}: {thought}"
        self.internal_thoughts.append(formatted_thought)
        self.logger.debug(f"Внутренняя мысль {self.name}: {thought}")
    
    def get_internal_thoughts(self) -> str:
        """
        Получение всех внутренних мыслей в виде строки.
        
        Returns:
            Строка с внутренними мыслями
        """
        return "\n".join(self.internal_thoughts)
    
    def send_message(self, to_agent: 'BaseAgent', message: str, metadata: Dict = None) -> None:
        """
        Отправка сообщения другому агенту.
        
        Args:
            to_agent: Агент-получатель
            message: Текст сообщения
            metadata: Дополнительные метаданные
        """
        if metadata is None:
            metadata = {}
        
        agent_message = AgentMessage(
            role=self.role,
            content=message,
            metadata={
                "from": self.name,
                "to": to_agent.name,
                **metadata
            }
        )
        
        self.message_history.append(agent_message)
        to_agent.receive_message(agent_message)
        
        self.logger.debug(f"Сообщение от {self.name} к {to_agent.name}: {message[:50]}...")
    
    def receive_message(self, message: AgentMessage) -> None:
        """
        Получение сообщения от другого агента.
        
        Args:
            message: Сообщение от агента
        """
        self.message_history.append(message)
        self.logger.debug(f"Сообщение для {self.name} от {message.metadata.get('from')}: {message.content[:50]}...")
    
    def clear_memory(self) -> None:
        """Очистка памяти агента (для новой сессии)."""
        self.internal_thoughts = []
        self.message_history = []
        self.interview_context = {}
        self.logger.info(f"Память агента {self.name} очищена")
    
    def get_status(self) -> Dict[str, Any]:
        """
        Получение статуса агента.
        
        Returns:
            Словарь со статусом агента
        """
        return {
            "name": self.name,
            "role": self.role,
            "thoughts_count": len(self.internal_thoughts),
            "messages_count": len(self.message_history),
            "has_context": bool(self.interview_context)
        }
    
    def __str__(self) -> str:
        return f"Agent(name={self.name}, role={self.role})"
    
    def __repr__(self) -> str:
        return self.__str__()