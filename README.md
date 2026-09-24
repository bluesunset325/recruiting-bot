# Recruiting Bot — Mindl

Telegram-бот для сбора анкет кандидатов + веб-панель для HR.

## Возможности

- **Telegram-бот** — 3 вакансии (DevOps / Frontend / Backend) с вопросами под специальность
- **HR-панель** (Flask) — таблица кандидатов, real-time фильтры, поиск по навыкам, экспорт в Excel
- **Приглашение / отказ** — отправка уведомлений кандидату прямо из панели, статусы с цветовой подсветкой
- **Бэкап** — резервное копирование базы данных одной кнопкой
- **SQLite** — локальная БД, без внешних серверов

## Быстрый старт (Docker)

```bash
cp .env.example .env      # вписать BOT_TOKEN и пароль панели
docker compose up -d      # запускает бота и панель, авторестарт при падении
```

HR-панель: http://localhost:5050

Остановка: `docker compose down` (данные сохраняются на volume).

## Демо-данные

Чтобы показать панель клиенту с наполненной базой:

```bash
python3 seed_demo.py
```

Добавит 8 реалистичных кандидатов с разными статусами (приглашён, отказано, принят).

## Требования (запуск без Docker)

- Python 3.9+
- Telegram Bot Token (получить у [@BotFather](https://t.me/BotFather))

## Установка

### 1. Клонировать / скопировать проект

```bash
cd recruiting_bot
```

### 2. Создать виртуальное окружение

```bash
python3 -m venv venv
```

Активация:

- **macOS / Linux:**
  ```bash
  source venv/bin/activate
  ```
- **Windows:**
  ```bash
  venv\Scripts\activate
  ```

### 3. Установить зависимости

```bash
pip install -r requirements.txt
```

### 4. Настроить токен и пароль

```bash
cp .env.example .env
```

Откройте `.env` и впишите токен от @BotFather и пароль панели:

```
BOT_TOKEN=ваш_токен
HR_PANEL_PASSWORD=ваш_пароль
```

## Запуск

### Telegram-бот

```bash
python3 bot.py
```

### HR-панель

В отдельном терминале:

```bash
python3 hr_panel.py
```

Откройте в браузере: [http://localhost:5000](http://localhost:5000)

Пароль по умолчанию: `admin`

## Структура проекта

```
recruiting_bot/
├── bot.py              # Telegram-бот (aiogram 3)
├── hr_panel.py         # HR веб-панель (Flask)
├── database.py         # Операции с SQLite
├── config.py           # Конфигурация
├── requirements.txt    # Зависимости
├── templates/          # HTML-шаблоны
│   ├── base.html
│   ├── login.html
│   ├── candidates.html
│   └── invite.html
├── static/
│   └── css/
│       └── style.css
├── candidates.db       # БД (создаётся автоматически)
└── README.md
```

## Использование

1. Запустите бот и HR-панель (см. выше)
2. Откройте бота в Telegram → нажмите `/start`
3. Выберите вакансию → заполните анкету
4. Откройте HR-панель → увидите кандидата в таблице
5. Используйте фильтры, экспорт в Excel, приглашения

## Команды бота

| Команда   | Описание                      |
|-----------|-------------------------------|
| `/start`  | Начать заполнение анкеты      |
| `/cancel` | Отменить заполнение           |
| `/help`   | Показать справку              |
