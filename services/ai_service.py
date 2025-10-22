"""
Сервис для работы с Groq AI API
Обеспечивает взаимодействие с AI-моделями для генерации ответов
"""

import logging
from typing import List, Dict, Optional
from os import getenv

from groq import AsyncGroq
from groq import RateLimitError, APIConnectionError, APIStatusError

logger = logging.getLogger(__name__)


class AIService:
    """
    Сервис для взаимодействия с Groq AI API
    """

    def __init__(self):
        """
        Инициализация сервиса с настройками из переменных окружения
        """
        self.api_key = getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("GROQ_API_KEY не найден в переменных окружения")

        self.model = getenv("AI_MODEL", "llama-3.3-70b-versatile")
        self.temperature = float(getenv("TEMPERATURE", "0.7"))
        self.max_tokens = int(getenv("MAX_TOKENS", "1024"))

        # Инициализация асинхронного клиента Groq
        self.client = AsyncGroq(api_key=self.api_key)

        logger.info(f"✅ AI сервис инициализирован с моделью: {self.model}")

    async def get_ai_response(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None
    ) -> Optional[str]:
        """
        Получить ответ от AI на основе истории сообщений

        Args:
            messages: Список сообщений в формате [{"role": "user/assistant", "content": "текст"}]
            system_prompt: Системный промпт (необязательно)

        Returns:
            Текст ответа от AI или None в случае ошибки
        """
        try:
            # Подготовка сообщений
            formatted_messages = []

            # Добавляем системный промпт, если указан
            if system_prompt:
                formatted_messages.append({
                    "role": "system",
                    "content": system_prompt
                })

            # Добавляем историю сообщений
            formatted_messages.extend(messages)

            logger.info(f"📤 Отправка запроса к AI (сообщений: {len(formatted_messages)})")

            # Создание запроса к Groq API
            chat_completion = await self.client.chat.completions.create(
                messages=formatted_messages,
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                top_p=1,
                stream=False
            )

            # Извлечение ответа
            response_content = chat_completion.choices[0].message.content

            # Логирование статистики использования
            if hasattr(chat_completion, 'usage') and chat_completion.usage:
                logger.info(
                    f"📊 Использовано токенов: {chat_completion.usage.total_tokens} "
                    f"(запрос: {chat_completion.usage.prompt_tokens}, "
                    f"ответ: {chat_completion.usage.completion_tokens})"
                )

            logger.info("✅ Получен ответ от AI")
            return response_content

        except RateLimitError as e:
            logger.error(f"⚠️ Превышен лимит запросов к Groq API: {e}")
            return "⚠️ Извините, превышен лимит запросов. Пожалуйста, попробуйте позже."

        except APIConnectionError as e:
            logger.error(f"❌ Ошибка подключения к Groq API: {e}")
            return "❌ Не удалось подключиться к AI-сервису. Проверьте интернет-соединение."

        except APIStatusError as e:
            logger.error(f"❌ Ошибка API (статус {e.status_code}): {e}")
            return f"❌ Ошибка сервиса AI (код: {e.status_code}). Попробуйте позже."

        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка при обращении к AI: {e}", exc_info=True)
            return "❌ Произошла ошибка при обработке запроса. Попробуйте позже."

    async def get_streaming_response(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None
    ):
        """
        Получить потоковый ответ от AI (для будущего использования)

        Args:
            messages: Список сообщений
            system_prompt: Системный промпт (необязательно)

        Yields:
            Фрагменты ответа по мере их генерации
        """
        try:
            # Подготовка сообщений
            formatted_messages = []

            if system_prompt:
                formatted_messages.append({
                    "role": "system",
                    "content": system_prompt
                })

            formatted_messages.extend(messages)

            logger.info(f"📤 Отправка потокового запроса к AI")

            # Создание потокового запроса
            stream = await self.client.chat.completions.create(
                messages=formatted_messages,
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                top_p=1,
                stream=True
            )

            # Возвращаем генератор
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

            logger.info("✅ Потоковый ответ завершен")

        except Exception as e:
            logger.error(f"❌ Ошибка при потоковом запросе: {e}", exc_info=True)
            yield "❌ Ошибка при получении ответа."

    def get_default_system_prompt(self) -> str:
        """
        Получить системный промпт по умолчанию

        Returns:
            Текст системного промпта
        """
        return """Ты - умный и дружелюбный AI-консультант.
Твоя задача - помогать пользователям с их вопросами и задачами.

Правила:
- Отвечай на русском языке, если вопрос на русском
- Будь вежливым и профессиональным
- Давай четкие и понятные объяснения
- Если не знаешь ответа - честно признай это
- Используй структурированный формат для сложных ответов
- Приводи примеры, когда это уместно

Помни: твоя цель - быть максимально полезным для пользователя."""


# Глобальный экземпляр сервиса
_ai_service_instance: Optional[AIService] = None


def get_ai_service() -> AIService:
    """
    Получить глобальный экземпляр AI сервиса (Singleton)

    Returns:
        Экземпляр AIService
    """
    global _ai_service_instance
    if _ai_service_instance is None:
        _ai_service_instance = AIService()
    return _ai_service_instance
