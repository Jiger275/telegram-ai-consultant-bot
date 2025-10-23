"""
Обработчики для AI-диалога: /ask, /clear, /stats и обработка обычных сообщений
"""

import logging
import html as html_lib
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram import html
from datetime import datetime

from services.ai_service import get_ai_service
from services.conversation_service import get_conversation_service

logger = logging.getLogger(__name__)

# Создаем роутер для AI-диалога
router = Router(name="ai_chat")


def escape_html_in_code(text: str) -> str:
    """
    Экранирует HTML-символы в коде, сохраняя безопасные HTML-теги

    Args:
        text: Исходный текст

    Returns:
        Текст с экранированными опасными символами
    """
    # Список безопасных тегов, которые мы хотим сохранить
    safe_tags = ['b', 'i', 'u', 's', 'code', 'pre', 'a', 'strong', 'em']

    # Простое экранирование: заменяем < и > на HTML entities
    # но сохраняем безопасные теги
    result = text

    # Более безопасный подход - отключить парсинг HTML для ответов с кодом
    # Проверяем, содержит ли текст код (наличие специфичных для кода символов)
    if '```' in text or any(pattern in text for pattern in ['#include', 'def ', 'class ', 'function', 'import ', '<?', '<?php']):
        # Экранируем все HTML
        result = html_lib.escape(text)

    return result


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
    conv_service = get_conversation_service()

    messages_count = await conv_service.clear_conversation_history(user_id)

    await message.answer(
        f"🗑 <b>История диалога очищена</b>\n\n"
        f"Удалено сообщений: {messages_count}\n\n"
        f"Теперь вы можете начать новый разговор с чистого листа! 🚀"
    )


@router.message(Command("stats"))
async def command_stats_handler(message: Message) -> None:
    """
    Обработчик команды /stats
    Показывает статистику диалога пользователя
    """
    user_id = message.from_user.id
    conv_service = get_conversation_service()

    # Получаем статистику
    stats = await conv_service.get_conversation_stats(user_id)

    # Форматируем дату первого и последнего сообщения
    first_msg = stats['first_message']
    last_msg = stats['last_message']

    if first_msg:
        first_msg_str = datetime.fromisoformat(first_msg).strftime("%d.%m.%Y %H:%M")
    else:
        first_msg_str = "Нет данных"

    if last_msg:
        last_msg_str = datetime.fromisoformat(last_msg).strftime("%d.%m.%Y %H:%M")
    else:
        last_msg_str = "Нет данных"

    # Получаем настройки контекста
    max_context = await conv_service.get_user_max_context(user_id)

    # Формируем сообщение со статистикой
    stats_message = (
        f"📊 <b>Статистика вашего диалога</b>\n\n"
        f"💬 <b>Сообщения:</b>\n"
        f"  • Всего: {stats['total_messages']}\n"
        f"  • Ваших: {stats['user_messages']}\n"
        f"  • От AI: {stats['assistant_messages']}\n\n"
        f"🔢 <b>Токены:</b> {stats['total_tokens']}\n\n"
        f"📅 <b>Временная шкала:</b>\n"
        f"  • Первое сообщение: {first_msg_str}\n"
        f"  • Последнее сообщение: {last_msg_str}\n\n"
        f"⚙️ <b>Настройки:</b>\n"
        f"  • Размер контекста: {max_context} сообщений\n\n"
        f"💡 <i>Используйте /clear для очистки истории</i>"
    )

    await message.answer(stats_message)


@router.message(Command("context"))
async def command_context_handler(message: Message) -> None:
    """
    Обработчик команды /context [число]
    Управление размером контекстного окна
    """
    user_id = message.from_user.id
    conv_service = get_conversation_service()

    # Извлекаем аргумент команды
    args = message.text.replace("/context", "").strip()

    if not args:
        # Показываем текущие настройки
        current_context = await conv_service.get_user_max_context(user_id)
        await message.answer(
            f"⚙️ <b>Управление контекстом диалога</b>\n\n"
            f"📊 Текущий размер контекста: <b>{current_context}</b> сообщений\n\n"
            f"💡 <b>Что это значит?</b>\n"
            f"Бот запоминает последние {current_context} сообщений вашего диалога, "
            f"чтобы поддерживать контекст разговора.\n\n"
            f"<b>Изменить размер:</b>\n"
            f"<code>/context [число]</code>\n\n"
            f"<b>Примеры:</b>\n"
            f"• <code>/context 10</code> - запоминать 10 сообщений\n"
            f"• <code>/context 20</code> - запоминать 20 сообщений\n"
            f"• <code>/context 5</code> - запоминать 5 сообщений\n\n"
            f"⚠️ Рекомендуемый диапазон: <b>5-30</b> сообщений\n"
            f"• Меньше = быстрее, но меньше контекста\n"
            f"• Больше = больше контекста, но больше токенов"
        )
        return

    try:
        # Парсим число
        new_context = int(args)

        # Валидация
        if new_context < 2:
            await message.answer(
                "⚠️ Размер контекста не может быть меньше 2 сообщений!"
            )
            return

        if new_context > 50:
            await message.answer(
                "⚠️ Размер контекста не может быть больше 50 сообщений!\n"
                "Это может привести к превышению лимита токенов."
            )
            return

        # Сохраняем новую настройку
        await conv_service.set_user_max_context(user_id, new_context)

        await message.answer(
            f"✅ <b>Размер контекста обновлен</b>\n\n"
            f"Теперь бот будет запоминать последние <b>{new_context}</b> сообщений\n\n"
            f"💡 Изменения вступят в силу при следующем сообщении"
        )

        logger.info(f"⚙️ Пользователь {user_id} изменил размер контекста на {new_context}")

    except ValueError:
        await message.answer(
            "❌ Неверный формат команды!\n\n"
            "Используйте: <code>/context [число]</code>\n"
            "Например: <code>/context 15</code>"
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
    username = message.from_user.username

    # Отправляем уведомление о том, что бот "печатает"
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")

    logger.info(f"💬 Пользователь {user_name} (ID: {user_id}): {user_text[:50]}...")

    try:
        # Получаем сервисы
        ai_service = get_ai_service()
        conv_service = get_conversation_service()

        # Убеждаемся, что пользователь существует в базе данных
        await conv_service.ensure_user_exists(user_id, username, user_name)

        # Добавляем сообщение пользователя в историю
        await conv_service.add_message(user_id, "user", user_text)

        # Получаем историю диалога
        conversation_history = await conv_service.get_conversation_history(user_id)

        # Получаем системный промпт
        system_prompt = ai_service.get_default_system_prompt()

        # Отправляем запрос к AI
        ai_response = await ai_service.get_ai_response(
            messages=conversation_history,
            system_prompt=system_prompt
        )

        if ai_response:
            # Добавляем ответ AI в историю
            await conv_service.add_message(user_id, "assistant", ai_response)

            # Проверяем, содержит ли ответ код или потенциально опасные HTML символы
            contains_code = any(marker in ai_response for marker in [
                '```', '#include', 'def ', 'class ', 'import ', '<?', 'function',
                '<iostream>', '<algorithm>', '<vector>', '<string>', '<=', '>=', '<>'
            ])

            # Отправляем ответ пользователю
            if contains_code:
                # Отключаем парсинг HTML для сообщений с кодом
                await message.answer(ai_response, parse_mode=None)
            else:
                # Обычная отправка с HTML-парсингом
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


