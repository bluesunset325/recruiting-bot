
from __future__ import annotations

import asyncio
import json
import logging
import sys

from aiogram import Bot, Dispatcher, F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from ai_dialogue import humanize_question, is_shallow, make_followup
from ai_scoring import score_candidate
from config import (
    AI_DIALOGUE_ENABLED,
    AI_ENABLED,
    BOT_TOKEN,
    COMPANY_NAME,
    COMPANY_WELCOME,
    LOG_FILE,
    MANAGER_CHAT_ID,
    QUESTION_START_DATE,
    QUESTIONS_COMMON,
    START_DATE_OPTIONS,
    STATUS_OPTIONS,
)
from database import (
    get_candidate_by_telegram_id,
    get_vacancies,
    get_vacancy_by_slug,
    init_db,
    save_candidate,
    update_ai_score,
)
from validators import validate_contact, validate_experience, validate_name

router = Router()
logger = logging.getLogger(__name__)

BTN_APPLY = "📋 Оставить заявку"


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=BTN_APPLY)]],
        resize_keyboard=True,
        input_field_placeholder="Нажмите кнопку ниже или введите /start",
    )


class CandidateForm(StatesGroup):
    choosing_position = State()
    full_name = State()
    email_or_phone = State()
    experience_years = State()
    specialty_q = State()   # динамические вопросы по специальности
    status = State()
    start_date = State()


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()

    existing = get_candidate_by_telegram_id(message.from_user.id)
    extra = ""
    if existing:
        extra = "\n⚠️ Вы уже заполняли анкету. Новая отправка обновит данные.\n"

    await message.answer(
        COMPANY_WELCOME + extra,
        reply_markup=main_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )


async def _show_positions(message: Message, state: FSMContext) -> None:
    vacancies = get_vacancies(active_only=True)
    if not vacancies:
        await message.answer(
            "Сейчас открытых вакансий нет. Загляните позже!",
            reply_markup=main_keyboard(),
        )
        return

    buttons = [
        [InlineKeyboardButton(
            text=f"{v['emoji']}  {v['title']}" + (f" — {v['description']}" if v['description'] else ""),
            callback_data=f"pos_{v['slug']}",
        )]
        for v in vacancies
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(
        "Выберите вакансию:",
        reply_markup=keyboard,
    )
    await state.set_state(CandidateForm.choosing_position)


@router.message(F.text == BTN_APPLY)
async def btn_apply(message: Message, state: FSMContext) -> None:
    await state.clear()
    await _show_positions(message, state)


@router.callback_query(CandidateForm.choosing_position, F.data.startswith("pos_"))
async def position_chosen(callback: CallbackQuery, state: FSMContext) -> None:
    slug = callback.data.removeprefix("pos_")
    vacancy = get_vacancy_by_slug(slug)

    if not vacancy or not vacancy.get("active"):
        await callback.answer("Вакансия не найдена", show_alert=True)
        return

    await state.update_data(
        position=slug,
        position_title=vacancy["title"],
        specialty_questions=vacancy["questions"],
        specialty_index=0,
        specialty_answers={},
        dialogue_history=[],
        awaiting_followup=False,
        pending_followup_q="",
    )

    await callback.message.answer(
        f"✅ Вы выбрали: *{vacancy['emoji']} {vacancy['title']}*\n\n"
        f"Давайте заполним анкету.\n\n"
        f"📝 {QUESTIONS_COMMON[0]['text']}",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardRemove(),
    )
    await state.set_state(CandidateForm.full_name)
    await callback.answer()


@router.message(CandidateForm.full_name)
async def process_full_name(message: Message, state: FSMContext) -> None:
    is_valid, result = validate_name(message.text)
    if not is_valid:
        await message.answer(result)
        return
    await state.update_data(full_name=result)
    await message.answer(f"📝 {QUESTIONS_COMMON[1]['text']}")
    await state.set_state(CandidateForm.email_or_phone)


@router.message(CandidateForm.email_or_phone)
async def process_contact(message: Message, state: FSMContext) -> None:
    is_valid, result = validate_contact(message.text)
    if not is_valid:
        await message.answer(result)
        return
    await state.update_data(email_or_phone=result)
    await message.answer(f"📝 {QUESTIONS_COMMON[2]['text']}")
    await state.set_state(CandidateForm.experience_years)


@router.message(CandidateForm.experience_years)
async def process_experience(message: Message, state: FSMContext) -> None:
    is_valid, years = validate_experience(message.text)
    if not is_valid:
        await message.answer(
            "Не удалось распознать. Укажите опыт, например: "
            "«3 года», «6 месяцев», «1.5» или «нет опыта»:"
        )
        return
    await state.update_data(experience_years=years)
    await _ask_specialty_question(message, state)


async def _ask_specialty_question(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    questions = data.get("specialty_questions", [])
    index = data.get("specialty_index", 0)

    if index < len(questions):
        base_text = questions[index]
        text = base_text
        if AI_DIALOGUE_ENABLED:
            # Показываем «печатает...» пока LLM формулирует вопрос
            await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
            text = await humanize_question(
                base_text,
                data.get("position_title", "сотрудник"),
                data.get("dialogue_history", []),
            )
        await message.answer(f"📝 {text}")
        await state.set_state(CandidateForm.specialty_q)
    else:
        # Все вопросы по специальности пройдены → спрашиваем статус
        buttons = [
            [InlineKeyboardButton(text=opt, callback_data=f"status_{opt}")]
            for opt in STATUS_OPTIONS
        ]
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        await message.answer("📝 Ваш текущий статус?", reply_markup=keyboard)
        await state.set_state(CandidateForm.status)


@router.message(CandidateForm.specialty_q)
async def process_specialty_answer(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    questions = data.get("specialty_questions", [])
    index = data.get("specialty_index", 0)
    answers = data.get("specialty_answers", {})
    history = data.get("dialogue_history", [])
    answer = message.text.strip()

    if index >= len(questions):
        await state.update_data(specialty_index=index + 1)
        await _ask_specialty_question(message, state)
        return

    # Ответы храним по тексту вопроса — так AI-скоринг видит полный контекст
    base_question = questions[index]
    key = base_question

    # Это ответ на уточняющий вопрос — дописываем к основному ответу
    if data.get("awaiting_followup"):
        answers[key] = f"{answers.get(key, '')} (уточнение: {answer})"
        history.append((data.get("pending_followup_q", "уточнение"), answer))
        await state.update_data(
            specialty_answers=answers,
            dialogue_history=history,
            awaiting_followup=False,
            pending_followup_q="",
            specialty_index=index + 1,
        )
        await _ask_specialty_question(message, state)
        return

    answers[key] = answer
    history.append((base_question, answer))

    # Короткий ответ → один уточняющий вопрос (максимум один на вопрос)
    if AI_DIALOGUE_ENABLED and is_shallow(answer):
        await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
        followup = await make_followup(base_question, answer)
        if followup:
            await state.update_data(
                specialty_answers=answers,
                dialogue_history=history,
                awaiting_followup=True,
                pending_followup_q=followup,
            )
            await message.answer(f"📝 {followup}")
            return

    await state.update_data(
        specialty_answers=answers,
        dialogue_history=history,
        specialty_index=index + 1,
    )
    await _ask_specialty_question(message, state)


@router.callback_query(CandidateForm.status, F.data.startswith("status_"))
async def process_status(callback: CallbackQuery, state: FSMContext) -> None:
    status_value = callback.data.removeprefix("status_")
    await state.update_data(status=status_value)

    buttons = [
        [InlineKeyboardButton(text=opt, callback_data=f"date_{i}")]
        for i, opt in enumerate(START_DATE_OPTIONS)
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.answer(
        f"📝 {QUESTION_START_DATE}",
        reply_markup=keyboard,
    )
    await state.set_state(CandidateForm.start_date)
    await callback.answer()


@router.callback_query(CandidateForm.start_date, F.data.startswith("date_"))
async def process_start_date(callback: CallbackQuery, state: FSMContext) -> None:
    idx = int(callback.data.removeprefix("date_"))
    start_date = START_DATE_OPTIONS[idx] if 0 <= idx < len(START_DATE_OPTIONS) else START_DATE_OPTIONS[-1]
    await state.update_data(start_date=start_date)
    data = await state.get_data()

    specialty_answers = data.get("specialty_answers", {})
    programming_languages = ", ".join(specialty_answers.values()) if specialty_answers else ""

    candidate = {
        "telegram_id": callback.from_user.id,
        "telegram_username": callback.from_user.username or "",
        "full_name": data["full_name"],
        "email_or_phone": data["email_or_phone"],
        "experience_years": data["experience_years"],
        "programming_languages": programming_languages,
        "specialty_answers": json.dumps(specialty_answers, ensure_ascii=False),
        "status": data["status"],
        "start_date": start_date,
        "position": data.get("position", ""),
    }

    try:
        candidate_id = save_candidate(candidate)
        if AI_ENABLED:
            # Уведомление менеджеру уйдёт после скоринга — вместе с оценкой
            asyncio.create_task(_run_ai_scoring(callback.bot, candidate_id, candidate))
        else:
            asyncio.create_task(_notify_manager(callback.bot, candidate_id, candidate))
        await callback.message.answer(
            "✅ *Спасибо! Ваша анкета принята.*\n\n"
            f"Номер анкеты: `{candidate_id}`\n"
            f"Команда *{COMPANY_NAME}* свяжется с вами в ближайшее время.\n\n"
            "Чтобы обновить анкету — нажмите кнопку ниже.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_keyboard(),
        )
        logger.info(
            "Анкета сохранена: id=%s, tg_id=%s, name=%s, position=%s",
            candidate_id, callback.from_user.id, data["full_name"], data.get("position"),
        )
    except Exception:
        logger.exception("Ошибка сохранения анкеты")
        await callback.message.answer(
            "❌ Произошла ошибка при сохранении. Попробуйте позже или напишите /start"
        )

    await state.clear()


async def _run_ai_scoring(bot: Bot, candidate_id: int, candidate: dict) -> None:
    score, summary = None, None
    try:
        result = await score_candidate(candidate)
        if result:
            score, summary = result
            update_ai_score(candidate_id, score, summary)
        else:
            logger.warning("AI-скоринг не дал результата для id=%s", candidate_id)
    except Exception:
        logger.exception("Ошибка фонового AI-скоринга id=%s", candidate_id)

    await _notify_manager(bot, candidate_id, candidate, score, summary)


async def _notify_manager(
    bot: Bot,
    candidate_id: int,
    candidate: dict,
    score: int | None = None,
    summary: str | None = None,
) -> None:
    """ошибки отправки не ломают основной поток"""
    if not MANAGER_CHAT_ID:
        return

    vacancy = get_vacancy_by_slug(candidate.get("position", ""))
    position_text = f"{vacancy['emoji']} {vacancy['title']}" if vacancy else candidate.get("position", "?")
    username = candidate.get("telegram_username")
    contact_tg = f"@{username}" if username else f"tg id: {candidate['telegram_id']}"

    text = (
        f"🆕 Новая анкета #{candidate_id}\n\n"
        f"👤 {candidate['full_name']} ({contact_tg})\n"
        f"💼 {position_text}\n"
        f"📊 Опыт: {candidate['experience_years']} лет\n"
        f"📞 {candidate['email_or_phone']}\n"
        f"🕐 Готовность: {candidate['start_date']}\n"
    )
    if score is not None:
        text += f"\n🤖 AI-оценка: {score}/10\n{summary}"

    try:
        await bot.send_message(chat_id=MANAGER_CHAT_ID, text=text)
    except Exception:
        logger.exception("Не удалось уведомить менеджера (chat_id=%s)", MANAGER_CHAT_ID)


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    if await state.get_state() is None:
        await message.answer(
            "Нечего отменять.",
            reply_markup=main_keyboard(),
        )
        return
    await state.clear()
    await message.answer(
        "❌ Заполнение отменено.",
        reply_markup=main_keyboard(),
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "📋 *Команды:*\n\n"
        "/start — начать заполнение анкеты\n"
        "/cancel — отменить заполнение\n"
        "/help — эта справка",
        parse_mode=ParseMode.MARKDOWN,
    )


@router.message(StateFilter(None))
async def fallback(message: Message) -> None:
    await message.answer(
        f"Я — рекрутинговый бот *{COMPANY_NAME}*.\n"
        "Нажмите кнопку ниже, чтобы откликнуться на вакансию.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_keyboard(),
    )


def setup_logging() -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    try:
        handlers.append(logging.FileHandler(str(LOG_FILE), encoding="utf-8"))
    except OSError:
        pass
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
    )


async def main() -> None:
    setup_logging()
    init_db()

    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.error("Укажите токен бота в файле .env (BOT_TOKEN=...)")
        sys.exit(1)

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    logger.info("Бот %s запущен", COMPANY_NAME)
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
