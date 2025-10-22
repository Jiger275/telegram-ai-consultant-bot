"""
Обработчики для AI-диалога: /ask, /clear и обработка обычных сообщений
"""

import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram import html

from services.ai_service import get_ai_service

logger = logging.getLogger(__name__)

# Создаем роутер для AI-диалога
router = Router(name="ai_chat")

# Временное хранилище истории диалогов (в памяти)
# Формат: {user_id: [{"role": "user/assistant", "content": "текст"}, ...]}
conversation_history = {}

# Максимальное количество сообщений в контексте
MAX_CONTEXT_MESSAGES = 5


@router.message(Command("ask"))
async def command_ask_handler(message: Message) -> None:
    """
    Обработчик команды /ask [вопрос]
    Отправляет вопрос AI и возвращает ответ
    """
    # Извлекаем текст вопроса после команды
    question = message.text.replace("/ask", "").strip()

    if not question:
        await message.answer(
            "❓ <b>Использование команды /ask</b>\n\n"
            "Формат: <code>/ask [ваш вопрос]</code>\n\n"
            "<b>Примеры:</b>\n"
            "• <code>/ask Что такое Python?</code>\n"
            "• <code>/ask Объясни квантовую физику</code>\n\n"
            "Или просто напишите сообщение без команды!"
        )
        return

    await process_ai_message(message, question)


@router.message(Command("clear"))
async def command_clear_handler(message: Message) -> None:
    """
    Обработчик команды /clear
    Очищает историю диалога пользователя
    """
    user_id = message.from_user.id

    if user_id in conversation_history:
        messages_count = len(conversation_history[user_id])
        conversation_history[user_id] = []
        logger.info(f"🗑 Очищена история диалога для пользователя {user_id} ({messages_count} сообщений)")
    else:
        messages_count = 0

    await message.answer(
        f"🗑 <b>История диалога очищена</b>\n\n"
        f"Удалено сообщений: {messages_count}\n\n"
        f"Теперь вы можете начать новый разговор с чистого листа! 🚀"
    )


@router.message(F.text)
async def message_handler(message: Message) -> None:
    """
    Обработчик всех текстовых сообщений
    Отправляет сообщение в AI и возвращает ответ
    """
    user_message = message.text.strip()

    if not user_message:
        await message.answer("⚠️ Пожалуйста, отправьте текстовое сообщение.")
        return

    await process_ai_message(message, user_message)


async def process_ai_message(message: Message, user_text: str) -> None:
    """
    Обработка сообщения пользователя и получение ответа от AI

    Args:
        message: Объект сообщения Telegram
        user_text: Текст сообщения пользователя
    """
    user_id = message.from_user.id
    user_name = message.from_user.full_name

    # Отправляем уведомление о том, что бот "печатает"
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")

    logger.info(f"💬 Пользователь {user_name} (ID: {user_id}): {user_text[:50]}...")

    try:
        # Инициализация истории для пользователя, если её нет
        if user_id not in conversation_history:
            conversation_history[user_id] = []

        # Добавляем сообщение пользователя в историю
        conversation_history[user_id].append({
            "role": "user",
            "content": user_text
        })

        # Ограничиваем историю последними N сообщениями
        if len(conversation_history[user_id]) > MAX_CONTEXT_MESSAGES * 2:
            # Удаляем старые сообщения (оставляем последние MAX_CONTEXT_MESSAGES пар)
            conversation_history[user_id] = conversation_history[user_id][-(MAX_CONTEXT_MESSAGES * 2):]
            logger.info(f"✂️ Обрезана история диалога для пользователя {user_id}")

        # Получаем AI сервис
        ai_service = get_ai_service()

        # Получаем системный промпт
        system_prompt = ai_service.get_default_system_prompt()

        # Отправляем запрос к AI
        ai_response = await ai_service.get_ai_response(
            messages=conversation_history[user_id],
            system_prompt=system_prompt
        )

        if ai_response:
            # Добавляем ответ AI в историю
            conversation_history[user_id].append({
                "role": "assistant",
                "content": ai_response
            })

            # Отправляем ответ пользователю
            await message.answer(ai_response)

            logger.info(f"✅ Отправлен ответ пользователю {user_id}")
        else:
            # Если ответ None, значит была ошибка (уже залогирована в ai_service)
            await message.answer(
                "❌ <b>Не удалось получить ответ от AI</b>\n\n"
                "Попробуйте:\n"
                "• Повторить запрос через несколько секунд\n"
                "• Использовать команду /clear для сброса контекста\n"
                "• Проверить работу сервиса позже"
            )

    except Exception as e:
        logger.error(f"❌ Ошибка при обработке сообщения от пользователя {user_id}: {e}", exc_info=True)
        await message.answer(
            "❌ <b>Произошла ошибка</b>\n\n"
            "К сожалению, не удалось обработать ваше сообщение.\n"
            "Пожалуйста, попробуйте позже или используйте /clear для сброса."
        )


def get_conversation_stats(user_id: int) -> dict:
    """
    Получить статистику диалога пользователя

    Args:
        user_id: ID пользователя

    Returns:
        Словарь со статистикой
    """
    if user_id not in conversation_history:
        return {
            "messages_count": 0,
            "user_messages": 0,
            "ai_messages": 0
        }

    history = conversation_history[user_id]
    user_messages = sum(1 for msg in history if msg["role"] == "user")
    ai_messages = sum(1 for msg in history if msg["role"] == "assistant")

    return {
        "messages_count": len(history),
        "user_messages": user_messages,
        "ai_messages": ai_messages
    }
