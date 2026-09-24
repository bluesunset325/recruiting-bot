
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _load_dotenv(path: Path) -> None:
    """читаем .env без python-dotenv"""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(BASE_DIR / ".env")

# Путь к БД можно переопределить (в Docker БД лежит на volume)
DB_PATH = Path(os.getenv("DB_PATH", str(BASE_DIR / "candidates.db")))

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

HR_PANEL_HOST = os.getenv("HR_PANEL_HOST", "0.0.0.0")
HR_PANEL_PORT = int(os.getenv("HR_PANEL_PORT", "5050"))
HR_PANEL_SECRET_KEY = os.getenv("HR_PANEL_SECRET_KEY", "change-me-in-production")
HR_PANEL_PASSWORD = os.getenv("HR_PANEL_PASSWORD", "admin")

MANAGER_CHAT_ID = int(os.getenv("MANAGER_CHAT_ID", "0"))

# AI-скоринг
# любой OpenAI-совместимый API: Ollama, OpenRouter и т.п.
AI_ENABLED = os.getenv("AI_ENABLED", "1") == "1"
# формулировка вопросов — отдельная быстрая модель без reasoning (~1 с),
# скоринг — на основной
AI_DIALOGUE_ENABLED = os.getenv("AI_DIALOGUE_ENABLED", "0") == "1"
AI_DIALOGUE_MODEL = os.getenv("AI_DIALOGUE_MODEL", "qwen2.5:3b-instruct")
AI_BASE_URL = os.getenv("AI_BASE_URL", "http://localhost:11434/v1")
AI_MODEL = os.getenv("AI_MODEL", "qwen3-vl:8b")
AI_API_KEY = os.getenv("AI_API_KEY", "ollama")  # для Ollama значение не важно
AI_TIMEOUT = int(os.getenv("AI_TIMEOUT", "120"))

LOG_FILE = BASE_DIR / "bot.log"

# название компании для приветствия и промптов — под клиента меняется тут
COMPANY_NAME = os.getenv("COMPANY_NAME", "Mindl")

# описание компании в приветствии, задаётся через .env
COMPANY_ABOUT = os.getenv(
    "COMPANY_ABOUT",
    f"{COMPANY_NAME} — компания, которая помогает бизнесу находить лучших сотрудников.",
)

COMPANY_WELCOME = (
    "╔══════════════════════╗\n"
    f"║    {'  '.join(COMPANY_NAME.upper()):^18}║\n"
    "╚══════════════════════╝\n\n"
    f"Привет! Я — рекрутинговый бот компании *{COMPANY_NAME}*.\n\n"
    f"{COMPANY_ABOUT}\n\n"
    "Выберите вакансию, которая вас интересует:"
)

# Общие вопросы (для всех вакансий)
QUESTIONS_COMMON = [
    {"key": "full_name",       "text": "Как вас зовут? (ФИО)"},
    {"key": "email_or_phone",  "text": "Ваш email или телефон для связи?"},
    {"key": "experience_years","text": "Какой у вас опыт работы в этой сфере? (например: 3 года, 6 месяцев, нет опыта)"},
]

# стартовые вакансии, если таблица пустая; дальше ими рулит HR в панели
DEFAULT_VACANCIES = [
    {
        "slug": "cleaner",
        "title": "Клинер",
        "emoji": "🧹",
        "description": "Уборка квартир, офисов, после ремонта",
        "questions": [
            "Есть ли у вас опыт уборки (квартиры, офисы, после ремонта)? Расскажите.",
            "Есть ли у вас действующая медицинская книжка?",
            "Какой график вам удобен? (2/2, 5/2, подработка по выходным)",
            "В каких районах города вам удобно работать?",
        ],
        "scoring_criteria": "опыт уборки, наличие медкнижки, гибкость по графику и районам",
    },
    {
        "slug": "loader",
        "title": "Грузчик / Разнорабочий",
        "emoji": "📦",
        "description": "Погрузка, разгрузка, работа на складе",
        "questions": [
            "Есть ли опыт работы грузчиком или на складе? Где и сколько?",
            "Готовы ли к физическим нагрузкам и ночным сменам?",
            "Какой график рассматриваете? (полный день, подработка, вахта)",
        ],
        "scoring_criteria": "физическая готовность, опыт складской работы, гибкость по сменам",
    },
    {
        "slug": "cashier",
        "title": "Продавец-кассир",
        "emoji": "🛒",
        "description": "Работа в магазине, касса, выкладка товара",
        "questions": [
            "Есть ли опыт работы в торговле или на кассе? Расскажите.",
            "Работали ли с кассовым ПО? (1С, Эвотор, Атол...)",
            "Есть ли у вас действующая медицинская книжка?",
            "Какой график вам подходит? (2/2, 5/2, только вечера)",
        ],
        "scoring_criteria": "опыт в торговле, навыки работы с кассой, медкнижка, надёжность",
    },
]

STATUS_OPTIONS = ["Работаю", "Ищу работу", "Ищу подработку"]

QUESTION_START_DATE = "Укажите предполагаемую дату начала работы:"

START_DATE_OPTIONS = [
    "Готов приступить немедленно",
    "В течение 1–2 рабочих дней",
    "В течение одной рабочей недели",
    "Через две недели",
    "Через месяц",
    "Готов обсудить сроки с менеджером",
]
