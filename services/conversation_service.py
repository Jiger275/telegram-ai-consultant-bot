"""
Сервис для управления историей диалогов и контекстом
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime

from database.models import get_database

logger = logging.getLogger(__name__)


class ConversationService:
    """
    Сервис для управления историей диалогов пользователей
    """

    def __init__(self):
        """Инициализация сервиса"""
        self.db = get_database()

    async def ensure_user_exists(
        self,
        user_id: int,
        username: Optional[str] = None,
        full_name: Optional[str] = None
    ) -> None:
        """
        Убедиться, что пользователь существует в базе данных

        Args:
            user_id: ID пользователя Telegram
            username: Username пользователя (может быть None)
            full_name: Полное имя пользователя
        """
        conn = await self.db.get_connection()

        # Проверяем, существует ли пользователь
        async with conn.execute(
            "SELECT user_id FROM users WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            user = await cursor.fetchone()

        if not user:
            # Создаем нового пользователя
            await conn.execute(
                """
                INSERT INTO users (user_id, username, full_name)
                VALUES (?, ?, ?)
                """,
                (user_id, username, full_name)
            )
            await conn.commit()
            logger.info(f"✨ Создан новый пользователь: {user_id} ({full_name})")
        else:
            # Обновляем last_interaction
            await conn.execute(
                """
                UPDATE users
                SET last_interaction = CURRENT_TIMESTAMP,
                    username = COALESCE(?, username),
                    full_name = COALESCE(?, full_name)
                WHERE user_id = ?
                """,
                (username, full_name, user_id)
            )
            await conn.commit()

    async def add_message(
        self,
        user_id: int,
        role: str,
        content: str,
        tokens_used: int = 0
    ) -> None:
        """
        Добавить сообщение в историю диалога

        Args:
            user_id: ID пользователя
            role: Роль отправителя ('user', 'assistant', 'system')
            content: Содержимое сообщения
            tokens_used: Количество использованных токенов
        """
        conn = await self.db.get_connection()

        await conn.execute(
            """
            INSERT INTO conversation_history (user_id, role, content, tokens_used)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, role, content, tokens_used)
        )

        # Обновляем счетчик сообщений пользователя
        if role == "user":
            await conn.execute(
                """
                UPDATE users
                SET total_messages = total_messages + 1,
                    last_interaction = CURRENT_TIMESTAMP
                WHERE user_id = ?
                """,
                (user_id,)
            )

        await conn.commit()
        logger.debug(f"💬 Добавлено сообщение ({role}) для пользователя {user_id}")

    async def get_conversation_history(
        self,
        user_id: int,
        limit: Optional[int] = None
    ) -> List[Dict[str, str]]:
        """
        Получить историю диалога пользователя

        Args:
            user_id: ID пользователя
            limit: Максимальное количество сообщений (последние N)

        Returns:
            Список сообщений в формате [{"role": "...", "content": "..."}]
        """
        conn = await self.db.get_connection()

        # Получаем настройки пользователя для определения лимита
        if limit is None:
            limit = await self.get_user_max_context(user_id)

        # Получаем последние N сообщений
        query = """
            SELECT role, content
            FROM conversation_history
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """

        async with conn.execute(query, (user_id, limit)) as cursor:
            rows = await cursor.fetchall()

        # Переворачиваем список, чтобы сообщения были в хронологическом порядке
        messages = [
            {"role": row["role"], "content": row["content"]}
            for row in reversed(rows)
        ]

        logger.debug(f"📜 Загружено {len(messages)} сообщений для пользователя {user_id}")
        return messages

    async def clear_conversation_history(self, user_id: int) -> int:
        """
        Очистить историю диалога пользователя

        Args:
            user_id: ID пользователя

        Returns:
            Количество удаленных сообщений
        """
        conn = await self.db.get_connection()

        # Подсчитываем количество сообщений перед удалением
        async with conn.execute(
            "SELECT COUNT(*) as count FROM conversation_history WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            result = await cursor.fetchone()
            count = result["count"] if result else 0

        # Удаляем все сообщения
        await conn.execute(
            "DELETE FROM conversation_history WHERE user_id = ?",
            (user_id,)
        )
        await conn.commit()

        logger.info(f"🗑 Очищена история диалога для пользователя {user_id} ({count} сообщений)")
        return count

    async def get_conversation_stats(self, user_id: int) -> Dict:
        """
        Получить статистику диалога пользователя

        Args:
            user_id: ID пользователя

        Returns:
            Словарь со статистикой
        """
        conn = await self.db.get_connection()

        # Получаем общую статистику
        query = """
            SELECT
                COUNT(*) as total_messages,
                SUM(CASE WHEN role = 'user' THEN 1 ELSE 0 END) as user_messages,
                SUM(CASE WHEN role = 'assistant' THEN 1 ELSE 0 END) as assistant_messages,
                SUM(tokens_used) as total_tokens,
                MIN(timestamp) as first_message,
                MAX(timestamp) as last_message
            FROM conversation_history
            WHERE user_id = ?
        """

        async with conn.execute(query, (user_id,)) as cursor:
            row = await cursor.fetchone()

        # Получаем информацию о пользователе
        async with conn.execute(
            "SELECT * FROM users WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            user = await cursor.fetchone()

        stats = {
            "total_messages": row["total_messages"] if row else 0,
            "user_messages": row["user_messages"] if row else 0,
            "assistant_messages": row["assistant_messages"] if row else 0,
            "total_tokens": row["total_tokens"] if row else 0,
            "first_message": row["first_message"] if row else None,
            "last_message": row["last_message"] if row else None,
            "user_info": dict(user) if user else None
        }

        return stats

    async def get_user_max_context(self, user_id: int) -> int:
        """
        Получить максимальное количество сообщений в контексте для пользователя

        Args:
            user_id: ID пользователя

        Returns:
            Максимальное количество сообщений
        """
        conn = await self.db.get_connection()

        async with conn.execute(
            "SELECT max_context_messages FROM user_settings WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            result = await cursor.fetchone()

        # По умолчанию 10 сообщений (5 пар вопрос-ответ)
        return result["max_context_messages"] if result else 10

    async def set_user_max_context(self, user_id: int, max_context: int) -> None:
        """
        Установить максимальное количество сообщений в контексте

        Args:
            user_id: ID пользователя
            max_context: Новое максимальное количество сообщений
        """
        conn = await self.db.get_connection()

        await conn.execute(
            """
            INSERT INTO user_settings (user_id, max_context_messages, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                max_context_messages = excluded.max_context_messages,
                updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, max_context)
        )
        await conn.commit()

        logger.info(f"⚙️ Установлен max_context={max_context} для пользователя {user_id}")

    async def get_user_settings(self, user_id: int) -> Optional[Dict]:
        """
        Получить настройки пользователя

        Args:
            user_id: ID пользователя

        Returns:
            Словарь с настройками или None
        """
        conn = await self.db.get_connection()

        async with conn.execute(
            "SELECT * FROM user_settings WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            result = await cursor.fetchone()

        return dict(result) if result else None

    async def trim_old_messages(self, user_id: int, keep_last: int = 50) -> int:
        """
        Удалить старые сообщения, оставив только последние N

        Args:
            user_id: ID пользователя
            keep_last: Количество последних сообщений для сохранения

        Returns:
            Количество удаленных сообщений
        """
        conn = await self.db.get_connection()

        # Получаем ID последних N сообщений
        query = """
            DELETE FROM conversation_history
            WHERE user_id = ? AND id NOT IN (
                SELECT id FROM conversation_history
                WHERE user_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            )
        """

        cursor = await conn.execute(query, (user_id, user_id, keep_last))
        deleted_count = cursor.rowcount
        await conn.commit()

        if deleted_count > 0:
            logger.info(f"✂️ Удалено {deleted_count} старых сообщений для пользователя {user_id}")

        return deleted_count


# Глобальный экземпляр сервиса
_conversation_service_instance: Optional[ConversationService] = None


def get_conversation_service() -> ConversationService:
    """
    Получить глобальный экземпляр сервиса диалогов (Singleton)

    Returns:
        Экземпляр ConversationService
    """
    global _conversation_service_instance
    if _conversation_service_instance is None:
        _conversation_service_instance = ConversationService()
    return _conversation_service_instance
