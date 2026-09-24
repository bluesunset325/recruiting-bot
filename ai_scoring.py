
from __future__ import annotations

import json
import logging
import re
from typing import Optional, Tuple

import aiohttp

from config import AI_BASE_URL, AI_API_KEY, AI_MODEL, AI_TIMEOUT

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "Ты — строгий HR-ассистент. Оцени соответствие кандидата "
    "указанной вакансии.\n"
    "Шкала оценки (придерживайся строго):\n"
    "1-2 — нет релевантного опыта вообще (учебные проекты не считаются опытом)\n"
    "3-4 — опыт по касательной, ключевых навыков вакансии нет\n"
    "5-6 — часть требований закрыта, но есть серьёзные пробелы\n"
    "7-8 — уверенное соответствие, небольшие пробелы\n"
    "9-10 — полное соответствие + глубина, брать в приоритет\n"
    "Ответь СТРОГО в JSON без пояснений:\n"
    '{"score": <целое число 1-10>, "summary": "<2-3 предложения на русском: '
    'сильные стороны, риски, рекомендация>"}'
)


def _build_prompt(candidate: dict) -> str:
    from database import get_vacancy_by_slug

    vacancy = get_vacancy_by_slug(candidate.get("position", ""))
    if vacancy:
        position_text = f"{vacancy['title']}"
        if vacancy.get("description"):
            position_text += f" ({vacancy['description']})"
        criteria = vacancy.get("scoring_criteria", "")
    else:
        position_text = candidate.get("position", "не указана")
        criteria = ""

    answers = candidate.get("specialty_answers") or "{}"
    if isinstance(answers, str):
        try:
            answers = json.loads(answers)
        except json.JSONDecodeError:
            answers = {"ответы": answers}

    answers_text = "\n".join(f"- {k}: {v}" for k, v in answers.items())

    prompt = f"Вакансия: {position_text}\n"
    if criteria:
        prompt += f"Ключевые критерии отбора: {criteria}\n"
    prompt += (
        f"\nАнкета кандидата:\n"
        f"- Опыт: {candidate.get('experience_years', '?')} лет\n"
        f"{answers_text}\n"
        f"- Текущий статус: {candidate.get('status', '?')}\n"
        f"- Готовность к выходу: {candidate.get('start_date', '?')}"
    )
    return prompt


def _parse_response(text: str) -> Optional[Tuple[int, str]]:
    """score и summary из ответа, даже если модель обернула JSON в текст"""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
        score = int(data["score"])
        summary = str(data["summary"]).strip()
        if not 1 <= score <= 10 or not summary:
            return None
        return score, summary
    except (json.JSONDecodeError, KeyError, ValueError, TypeError):
        return None


async def score_candidate(candidate: dict) -> Optional[Tuple[int, str]]:
    """(score, summary) или None при ошибке"""
    payload = {
        "model": AI_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_prompt(candidate)},
        ],
        "temperature": 0.3,
    }
    headers = {"Authorization": f"Bearer {AI_API_KEY}"}

    try:
        timeout = aiohttp.ClientTimeout(total=AI_TIMEOUT)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                f"{AI_BASE_URL}/chat/completions",
                json=payload,
                headers=headers,
            ) as resp:
                if resp.status != 200:
                    logger.error("AI API вернул статус %s", resp.status)
                    return None
                data = await resp.json()
                content = data["choices"][0]["message"]["content"]
    except Exception:
        logger.exception("Ошибка запроса к AI API (%s)", AI_BASE_URL)
        return None

    result = _parse_response(content)
    if result is None:
        logger.error("Не удалось разобрать ответ модели: %.200s", content)
    return result
