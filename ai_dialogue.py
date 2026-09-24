"""Переформулировка вопросов анкеты: скелет фиксирован, модель только перефразирует."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Optional

import aiohttp

from config import AI_BASE_URL, AI_API_KEY, AI_DIALOGUE_MODEL, COMPANY_NAME

logger = logging.getLogger(__name__)

# быстрая модель отвечает за ~1 с; не успела — шлём обычный вопрос из конфига
HUMANIZE_TIMEOUT = 8

# Ответ короче этого числа символов считается поверхностным
SHALLOW_ANSWER_LEN = 20

SYSTEM_HUMANIZE = (
    f"Ты — рекрутер IT-компании {COMPANY_NAME}, ведёшь диалог с кандидатом "
    "в Telegram. Тебе дают служебный вопрос анкеты и контекст беседы. "
    "Перепиши вопрос так, как задал бы живой человек в переписке.\n"
    "Правила:\n"
    "- ОБЯЗАТЕЛЬНО сохрани всю конкретику: названия технологий и примеры "
    "из скобок должны остаться в вопросе\n"
    "- Обращайся на «вы»\n"
    "- Один вопрос, максимум 2 предложения, грамотный русский язык\n"
    "- Без приветствий, без комментариев к прошлым ответам, без смайликов\n"
    "- СТРОГО на русском языке. Никакого английского и китайского, "
    "кроме названий технологий\n"
    "- Ответь ТОЛЬКО текстом вопроса, без кавычек и пояснений"
)

SYSTEM_FOLLOWUP = (
    "Ты — рекрутер IT-компании, ведёшь диалог с кандидатом в Telegram. "
    "Кандидат дал короткий поверхностный ответ на вопрос. "
    "Задай ОДИН короткий уточняющий вопрос, чтобы раскрыть детали "
    "(глубина опыта, конкретные инструменты, масштаб задач).\n"
    "СТРОГО на русском языке, обращайся на «вы».\n"
    "Ответь ТОЛЬКО текстом вопроса, без кавычек и пояснений."
)


async def _chat(system: str, user: str, timeout: int = HUMANIZE_TIMEOUT) -> Optional[str]:
    """Один запрос к LLM. Возвращает текст или None при ошибке/таймауте."""
    # qwen2.5 без reasoning-режима: max_tokens безопасен и режет болтливость
    payload = {
        "model": AI_DIALOGUE_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        # низкая температура — меньше ошибок в грамматике
        "temperature": 0.3,
        "max_tokens": 120,
    }
    headers = {"Authorization": f"Bearer {AI_API_KEY}"}
    try:
        client_timeout = aiohttp.ClientTimeout(total=timeout)
        async with aiohttp.ClientSession(timeout=client_timeout) as session:
            async with session.post(
                f"{AI_BASE_URL}/chat/completions",
                json=payload,
                headers=headers,
            ) as resp:
                if resp.status != 200:
                    logger.warning("AI dialogue API статус %s", resp.status)
                    return None
                data = await resp.json()
                text = data["choices"][0]["message"]["content"].strip()
                return _clean(text)
    except (asyncio.TimeoutError, aiohttp.ClientError):
        logger.warning("AI dialogue: таймаут или сетевая ошибка")
        return None
    except Exception:
        logger.exception("AI dialogue: неожиданная ошибка")
        return None


def _is_valid_russian(text: str) -> bool:
    """Русский текст без иероглифов: qwen иногда срывается в китайский."""
    # CJK-иероглифы (китайский/японский/корейский) — сразу брак
    if re.search(r"[一-鿿぀-ヿ가-힯]", text):
        return False
    # латиница допустима: Docker, Kubernetes и т.п.
    cyrillic = len(re.findall(r"[а-яА-ЯёЁ]", text))
    return cyrillic >= 10 and cyrillic >= len(text) * 0.15


def _clean(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    text = text.strip().strip('"').strip("«»").strip()
    # Если модель вернула несколько абзацев — берём первый содержательный
    for part in text.split("\n\n"):
        part = part.strip()
        if part:
            return part
    return text


async def humanize_question(
    question_text: str,
    position_title: str,
    dialogue_history: list[tuple[str, str]],
) -> str:
    """Переформулировать вопрос живым языком с учётом контекста.

    dialogue_history — список пар (вопрос, ответ) текущей анкеты.
    При ошибке возвращает исходный текст вопроса.
    """
    history_text = "\n".join(
        f"Вопрос: {q}\nОтвет кандидата: {a}" for q, a in dialogue_history[-4:]
    ) or "(диалог только начался)"

    user_prompt = (
        f"Вакансия: {position_title}\n\n"
        f"Контекст беседы:\n{history_text}\n\n"
        f"Служебный вопрос анкеты, который нужно переформулировать:\n{question_text}"
    )

    result = await _chat(SYSTEM_HUMANIZE, user_prompt)
    if result and 5 < len(result) < 400 and _is_valid_russian(result):
        return result
    if result:
        logger.warning("AI-вопрос отбракован (не русский/мусор): %.100s", result)
    return question_text


def is_shallow(answer: str) -> bool:
    return len(answer.strip()) < SHALLOW_ANSWER_LEN


async def make_followup(question_text: str, answer: str) -> Optional[str]:
    """Сгенерировать уточняющий вопрос к поверхностному ответу.

    Возвращает None, если генерация не удалась — тогда бот просто
    переходит к следующему вопросу.
    """
    user_prompt = (
        f"Вопрос анкеты: {question_text}\n"
        f"Ответ кандидата: {answer}"
    )
    result = await _chat(SYSTEM_FOLLOWUP, user_prompt)
    if result and 5 < len(result) < 300 and _is_valid_russian(result):
        return result
    if result:
        logger.warning("AI-уточнение отбраковано (не русский/мусор): %.100s", result)
    return None
