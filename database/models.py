"""
Database models for the Telegram AI Bot
"""

import aiosqlite
import logging
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class Database:
    """
    Класс для работы с базой данных SQLite
    """

    def __init__(self, db_path: str = "bot_database.db"):
        """
        Инициализация базы данных

        Args:
            db_path: Путь к файлу базы данных
        """
        self.db_path = db_path
        self.connection: Optional[aiosqlite.Connection] = None

    async def connect(self):
        """Подключение к базе данных"""
        self.connection = await aiosqlite.connect(self.db_path)
        self.connection.row_factory = aiosqlite.Row
        logger.info(f"✅ Подключение к базе данных: {self.db_path}")

    async def disconnect(self):
        """Отключение от базы данных"""
        if self.connection:
            await self.connection.close()
            logger.info("🔌 Отключение от базы данных")

    async def init_db(self):
        """Инициализация схемы базы данных"""
        await self.connect()

        # Таблица пользователей
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                first_interaction TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_interaction TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_messages INTEGER DEFAULT 0
            )
        """)

        # Таблица истории диалогов
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS conversation_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
                content TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                tokens_used INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        # Индекс для быстрого поиска по user_id и timestamp
        await self.connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_conversation_user_timestamp
            ON conversation_history(user_id, timestamp DESC)
        """)

        # Таблица настроек пользователя
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY,
                max_context_messages INTEGER DEFAULT 10,
                temperature REAL DEFAULT 0.7,
                system_prompt TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        await self.connection.commit()
        logger.info("✅ Схема базы данных инициализирована")

    async def get_connection(self) -> aiosqlite.Connection:
        """
        Получить подключение к базе данных

        Returns:
            Подключение к БД
        """
        if not self.connection:
            await self.connect()
        return self.connection


# Глобальный экземпляр базы данных
_database_instance: Optional[Database] = None


def get_database() -> Database:
    """
    Получить глобальный экземпляр базы данных (Singleton)

    Returns:
        Экземпляр Database
    """
    global _database_instance
    if _database_instance is None:
        _database_instance = Database()
    return _database_instance
