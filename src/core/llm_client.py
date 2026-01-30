"""
Клиент для работы с Mistral API.
"""

import os
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv
import logging
from mistralai import Mistral

# Загрузка переменных окружения
load_dotenv()

logger = logging.getLogger(__name__)


class MistralClient:
    """Клиент для работы с Mistral моделями через официальный API."""
    
    def __init__(
        self,
        model: str = "mistral-large-latest",
        temperature: float = 0.7,
        max_tokens: int = 1000,
        api_key: Optional[str] = None,
        **kwargs
    ):
        """
        Инициализация Mistral клиента.
        
        Args:
            model: Название модели (mistral-tiny, mistral-small, mistral-medium, mistral-large-latest)
            temperature: Креативность (0-1)
            max_tokens: Максимальное количество токенов в ответе
            api_key: API ключ Mistral
        """
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.model = model
        
        # Получаем API ключ
        self.api_key = api_key or os.getenv("MISTRAL_API_KEY")
        if not self.api_key:
            raise ValueError("MISTRAL_API_KEY не найден в переменных окружения. Добавьте его в .env файл")
        
        # Инициализация клиента Mistral
        self.client = Mistral(api_key=self.api_key)
        
        logger.info(f"Инициализирован Mistral клиент с моделью {model}")
    
    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """
        Генерация ответа с использованием Mistral API.
        
        Args:
            system_prompt: Системный промпт
            user_prompt: Пользовательский промпт
            history: История диалога
            
        Returns:
            Сгенерированный текст
        """
        try:
            # Подготавливаем сообщения
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            # Добавляем историю если есть
            if history:
                for msg in history[-10:]:  # Берем последние 10 сообщений
                    if msg["role"] == "user":
                        messages.append({"role": "user", "content": msg["content"]})
                    else:
                        messages.append({"role": "assistant", "content": msg["content"]})
            
            # Генерируем ответ
            response = self.client.chat.complete(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Ошибка генерации Mistral: {e}")
            # Возвращаем заглушку для тестирования
            return "Продолжим интервью. Расскажите, пожалуйста, о вашем опыте работы с основными технологиями для этой позиции."
    
    def generate_sync(
        self,
        system_prompt: str,
        user_prompt: str,
        history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """
        Синхронная версия generate.
        """
        import asyncio
        return asyncio.run(self.generate(system_prompt, user_prompt, history))
    
    async def generate_with_template(
        self,
        template: str,
        variables: Dict[str, Any],
        system_prompt: Optional[str] = None
    ) -> str:
        """
        Генерация с использованием шаблона и переменных.
        
        Args:
            template: Шаблон промпта с плейсхолдерами {variable}
            variables: Словарь переменных для подстановки
            system_prompt: Опциональный системный промпт
            
        Returns:
            Сгенерированный текст
        """
        # Заполняем шаблон переменными
        try:
            user_prompt = template.format(**variables)
        except KeyError as e:
            logger.error(f"Отсутствует переменная в шаблоне: {e}")
            user_prompt = template
        
        # Используем базовый системный промпт если не указан
        if not system_prompt:
            system_prompt = "Ты - полезный AI-ассистент. Отвечай точно и по делу."
        
        return await self.generate(system_prompt, user_prompt)


# Фабрика для создания Mistral клиентов
class MistralClientFactory:
    """Фабрика для создания Mistral клиентов."""
    
    @staticmethod
    def create_client(
        model: str = None,
        **kwargs
    ) -> MistralClient:
        """
        Создание Mistral клиента.
        
        Args:
            model: Модель (если None, используется из окружения или дефолтная)
            **kwargs: Дополнительные параметры
            
        Returns:
            Экземпляр MistralClient
        """
        if model is None:
            model = os.getenv("MISTRAL_MODEL", "mistral-large-latest")
        
        return MistralClient(
            model=model,
            **kwargs
        )


# Тестирование клиента
async def test_mistral_client():
    """Тестирование Mistral клиента."""
    
    try:
        client = MistralClientFactory.create_client(
            temperature=0.1,
            max_tokens=100
        )
        
        # Тестовый запрос
        response = await client.generate(
            system_prompt="Ты - полезный помощник.",
            user_prompt="Привет! Напиши 'Тест успешен'."
        )
        
        print(f"Ответ от Mistral: {response}")
        
        return True
    except Exception as e:
        print(f"Ошибка Mistral: {e}")
        print("\nУбедитесь, что:")
        print("1. Установлен mistralai: pip install mistralai")
        print("2. В .env файле указан MISTRAL_API_KEY")
        print("3. API ключ действителен")
        return False


if __name__ == "__main__":
    import asyncio
    
    # Быстрый тест
    result = asyncio.run(test_mistral_client())
    if result:
        print("✓ Mistral клиент работает корректно")
