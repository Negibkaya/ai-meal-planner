from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.routers import auth, plans, meals, llm
from app.schemas import StatusResponse, ErrorResponse

# =============================================================================
# FastAPI Application
# =============================================================================

app = FastAPI(
    title="🍽️ AI Meal Planner API",
    version="1.0.0",
    description="""
    # API для управления планами питания с использованием LLM
    
    ## Возможности
    
    - **🔐 Аутентификация**: Регистрация и вход с JWT токенами
    - **📋 Планы питания**: Создание и управление планами через LLM
    - **🍽️ Блюда**: Просмотр и замена блюд с помощью ИИ
    - **🛒 Списки покупок**: Автоматическая генерация списка продуктов
    - **🤖 LLM интеграция**: Логирование запросов к языковой модели
    
    ## Статусы генерации
    
    Планы и списки покупок могут иметь следующие статусы:
    - `pending`: Ожидает начала генерации
    - `generating`: Идёт генерация через LLM
    - `ready`: Генерация завершена успешно
    - `error`: Произошла ошибка
    
    ## Аутентификация
    
    Все эндпоинты (кроме `/health` и `/auth/*`) требуют Bearer токен:
    ```
    Authorization: Bearer <your_jwt_token>
    ```
    """,
    summary="API для AI-генерации планов питания",
    contact={
        "name": "AI Meal Planner Team",
        "email": "support@aimealplanner.com"
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT"
    },
    openapi_tags=[
        {"name": "🔐 Аутентификация", "description": "Регистрация и вход пользователей"},
        {"name": "📋 Планы питания", "description": "Управление планами питания"},
        {"name": "🍽️ Блюда и покупки",
            "description": "Работа с блюдами и списками покупок"},
        {"name": "🤖 LLM Логи", "description": "История обращений к LLM"},
    ],
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# =============================================================================
# Middleware
# =============================================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================================================================
# Routers
# =============================================================================

app.include_router(auth.router)
app.include_router(plans.router)
app.include_router(meals.router)
app.include_router(llm.router)


# =============================================================================
# Health Check Endpoint
# =============================================================================

@app.get(
    "/health",
    response_model=StatusResponse,
    summary="Проверка работоспособности",
    description="""
    Проверяет, что API работает и доступен.
    
    **Не требует авторизации.**
    
    Используется для health checks в Docker/Kubernetes.
    """,
    tags=["🏥 Система"],
    responses={
        200: {
            "description": "API работает нормально",
            "model": StatusResponse
        }
    }
)
async def health():
    """Проверка работоспособности API.

    Returns:
        StatusResponse: Статус "ok"
    """
    return StatusResponse(status="ok")


# =============================================================================
# Exception Handlers
# =============================================================================

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Глобальный обработчик необработанных исключений."""
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "Произошла внутренняя ошибка сервера"
        }
    )
