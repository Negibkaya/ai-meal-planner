# AI Meal Planner

Веб-приложение для автоматического создания персонализированных планов питания с помощью языковых моделей (LLM). Пользователь указывает цель (похудение, набор массы, здоровое питание), бюджет, калорийность, предпочтения, аллергии и диетические ограничения — система генерирует подробный план на неделю, считает БЖУ и стоимость, подбирает рецепты и формирует список покупок.

## Основные возможности

- **Генерация планов питания** — создание недельного плана по целям, калориям, бюджету и предпочтениям через LLM (OpenAI / OpenRouter, есть мок-режим без ключа).
- **Асинхронная генерация** — план готовится в фоне (`pending` → `generating` → `ready` / `error`), фронтенд опрашивает статус.
- **Замена блюд** — для любого блюда можно запросить альтернативы от LLM и сохранить понравившуюся.
- **Список покупок** — автогенерация из плана, с категориями и примерными ценами.
- **Аутентификация** — регистрация и вход по JWT.

## Стек

**Backend** (`backend/`): FastAPI, PostgreSQL + SQLAlchemy (async), Alembic, JWT (`python-jose` + `passlib`), `httpx` + `openai` для LLM, `pydantic-settings`. Пакеты — `uv`/`pip`, `requirements.txt`.

**Frontend** (`frontend/`): React 19 + TypeScript, Vite 6, маршрутизация на хешах, компоненты `auth / layout / dashboard / plans` (`AuthForm`, `Sidebar`, `Header`, `Dashboard`, `CreatePlanForm`, `PlanList`, `PlanDetail`).

**Прочее**: `api/` — черновики/пробы API, `database/` — SQL-наброски схемы, `docs/` — спеки (`api-spec.md`, `database.md`, `ui-components.md`, `use-case.md`, `ux-scenarios.md`), `design/` — макеты, `utils/` — вспомогательные скрипты.

## Структура

```
backend/app/
  main.py            # FastAPI app, CORS, подключение роутеров
  config.py          # pydantic-settings (.env)
  database.py        # async engine/session
  models.py / schemas.py
  routers/auth.py    # регистрация, логин (JWT)
  routers/plans.py   # CRUD планов, статус генерации
  routers/meals.py   # замена/обновление блюд, список покупок
  routers/llm.py     # проверка LLM
  services/llm_service.py
frontend/
  App.tsx            # hash-роутер, layout
  components/        # auth, layout, dashboard, plans
  services/          # api-клиент
  constants.ts / types.ts
```

## API (кратко)

- `POST /auth/register` — регистрация
- `POST /auth/login` — вход, выдача JWT
- `GET /plans` — все планы пользователя
- `POST /plans` — создать план (запуск фоновой генерации)
- `GET /plans/{plan_id}` — конкретный план
- `GET /plans/{plan_id}/status` — статус генерации
- `POST /meals/{plan_id}/replace` — альтернативы для блюда
- `PATCH /meals/{meal_id}` — сохранить замену
- `POST /meals/{plan_id}/shopping-list/generate` — список покупок

Полная интерактивная документация: `http://127.0.0.1:8000/docs` при запущенном бэкенде.

## Запуск

Требования: Python 3.12+, Node.js 18+, запущенный PostgreSQL.

### 1. Backend

```bash
cd backend

# окружение (uv или venv)
uv venv
uv pip install -r requirements.txt
# либо: python -m venv .venv && .venv\Scripts\activate && pip install -r requirements.txt

# конфиг — создать backend/.env:
# DATABASE_URL="postgresql+asyncpg://user:password@localhost:5432/db_name"
# SECRET_KEY="your_strong_secret_key"
# ALGORITHM="HS256"
# OPENAI_API_KEY="..."  # опционально (OpenRouter/OpenAI), без него — мок-данные
# OPENAI_BASE_URL="https://openrouter.ai/api/v1"  # опционально

alembic upgrade head
uv run uvicorn app.main:app --reload
```

Сервер: `http://127.0.0.1:8000`.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Приложение: адрес из вывода Vite (обычно `http://localhost:5173`).

## Заметки

- `backend/.env` с секретами не коммитится (см. `.gitignore`).
- Без `OPENAI_API_KEY` приложение работает на мок-данных — удобно для локальной разработки без трат на LLM.
- CORS по умолчанию открыт для локального фронтенда; перед деплоем ограничить origins в `backend/app/main.py`.
