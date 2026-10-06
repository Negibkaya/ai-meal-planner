# backend/app/schemas.py
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


# =============================================================================
# Auth Schemas
# =============================================================================

class UserCreate(BaseModel):
    """Схема для регистрации нового пользователя.

    Attributes:
        email: Email пользователя (должен быть уникальным)
        password: Пароль (минимум 6 символов)
        name: Имя пользователя (опционально)
    """
    email: EmailStr = Field(
        description="Email пользователя (должен быть уникальным)",
        examples=["user@example.com"]
    )
    password: str = Field(
        min_length=6,
        description="Пароль пользователя (минимум 6 символов)",
        examples=["securepassword123"]
    )
    name: str | None = Field(
        default=None,
        description="Имя пользователя",
        examples=["Иван Петров"]
    )


class UserLogin(BaseModel):
    """Схема для входа пользователя.

    Attributes:
        email: Email пользователя
        password: Пароль пользователя
    """
    email: EmailStr = Field(
        description="Email пользователя",
        examples=["user@example.com"]
    )
    password: str = Field(
        description="Пароль пользователя",
        examples=["securepassword123"]
    )


class UserResponse(BaseModel):
    """Схема ответа с данными пользователя.

    Attributes:
        id: Уникальный идентификатор пользователя
        email: Email пользователя
        name: Имя пользователя
    """
    id: int = Field(
        description="Уникальный идентификатор пользователя", examples=[1])
    email: str = Field(description="Email пользователя",
                       examples=["user@example.com"])
    name: str | None = Field(
        description="Имя пользователя", examples=["Иван Петров"])

    class Config:
        from_attributes = True


class Token(BaseModel):
    """Схема токена аутентификации.

    Attributes:
        access_token: JWT токен для доступа к API
        token_type: Тип токена (bearer)
    """
    access_token: str = Field(
        description="JWT токен для доступа к защищённым эндпоинтам",
        examples=["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."]
    )
    token_type: str = Field(
        default="bearer",
        description="Тип токена",
        examples=["bearer"]
    )


# =============================================================================
# Meal Plan Schemas
# =============================================================================

class MealPlanCreate(BaseModel):
    """Схема для создания плана питания.

    Attributes:
        goal: Цель плана (например, "похудение", "набор массы", "поддержание")
        calories: Целевое количество калорий в день (1000-6000)
        budget: Бюджет на неделю (в рублях)
        preferences: Предпочтения в еде (опционально)
        allergies: Аллергии и непереносимость (опционально)
    """
    goal: str = Field(
        description="Цель плана питания",
        examples=["похудение", "набор массы",
                  "поддержание веса", "здоровое питание"]
    )
    calories: int = Field(
        ge=1000,
        le=6000,
        description="Целевое количество калорий в день",
        examples=[2000, 2500, 1800]
    )
    budget: float = Field(
        ge=0,
        description="Бюджет на неделю (в рублях)",
        examples=[3000, 5000, 7000]
    )
    preferences: str | None = Field(
        default=None,
        description="Предпочтения в еде (вегетарианское, без глютена и т.д.)",
        examples=["вегетарианское", "низкоуглеводное", "много белка"]
    )
    allergies: str | None = Field(
        default=None,
        description="Аллергии и продукты, которые нужно исключить",
        examples=["орехи, молочные продукты", "глютен", "цитрусовые"]
    )


class MealPlanResponse(BaseModel):
    """Схема ответа с данными плана питания.

    Attributes:
        id: Уникальный идентификатор плана
        goal: Цель плана
        calories: Целевое количество калорий
        budget: Бюджет на неделю
        preferences: Предпочтения в еде
        allergies: Аллергии
        total_days: Количество дней в плане
        status: Статус генерации (pending, generating, ready, error)
        created_at: Дата создания
        meals: Список блюд в плане
    """
    id: int = Field(description="Уникальный идентификатор плана", examples=[1])
    goal: str = Field(description="Цель плана питания", examples=["похудение"])
    calories: int = Field(description="Калорийность в день", examples=[2000])
    budget: float = Field(description="Бюджет на неделю", examples=[5000])
    preferences: str | None = Field(
        description="Предпочтения в еде", examples=["вегетарианское"])
    allergies: str | None = Field(description="Аллергии", examples=["орехи"])
    total_days: int = Field(
        description="Количество дней в плане", examples=[7])
    status: str = Field(
        description="Статус генерации плана",
        examples=["pending", "generating", "ready", "error"]
    )
    created_at: datetime = Field(description="Дата создания плана")
    meals: list["MealResponse"] = Field(
        default=[],
        description="Список блюд в плане"
    )

    class Config:
        from_attributes = True


# =============================================================================
# Meal Schemas
# =============================================================================

class MealResponse(BaseModel):
    """Схема ответа с данными блюда.

    Attributes:
        id: Уникальный идентификатор блюда
        day_of_week: День недели
        meal_type: Тип приёма пищи (завтрак, обед, ужин, перекус)
        dish_name: Название блюда
        recipe: Рецепт приготовления
        calories: Калорийность порции
        protein: Белки (граммы)
        fat: Жиры (граммы)
        carbs: Углеводы (граммы)
    """
    id: int | None = Field(
        default=None,
        description="Уникальный идентификатор блюда",
        examples=[1]
    )
    day_of_week: str = Field(
        description="День недели",
        examples=["Понедельник", "Вторник", "Среда"]
    )
    meal_type: str = Field(
        description="Тип приёма пищи",
        examples=["завтрак", "обед", "ужин", "перекус"]
    )
    dish_name: str = Field(
        description="Название блюда",
        examples=["Овсянка с фруктами", "Куриный суп", "Гречка с овощами"]
    )
    recipe: str | None = Field(
        default=None,
        description="Рецепт приготовления",
        examples=["1. Залейте овсянку молоком..."]
    )
    calories: int | None = Field(
        default=None,
        description="Калорийность порции (ккал)",
        examples=[350, 450, 600]
    )
    protein: int | None = Field(
        default=None,
        description="Содержание белков (г)",
        examples=[15, 25, 30]
    )
    fat: int | None = Field(
        default=None,
        description="Содержание жиров (г)",
        examples=[10, 15, 20]
    )
    carbs: int | None = Field(
        default=None,
        description="Содержание углеводов (г)",
        examples=[40, 55, 70]
    )

    class Config:
        from_attributes = True


class MealUpdate(BaseModel):
    """Схема для обновления блюда.

    Attributes:
        dish_name: Новое название блюда
        calories: Калорийность
        protein: Белки
        fat: Жиры
        carbs: Углеводы
        recipe: Рецепт
    """
    dish_name: str = Field(
        description="Название блюда",
        examples=["Овсянка с ягодами"]
    )
    calories: int | None = Field(
        default=None,
        description="Калорийность (ккал)",
        examples=[350]
    )
    protein: int | None = Field(
        default=None,
        description="Белки (г)",
        examples=[15]
    )
    fat: int | None = Field(
        default=None,
        description="Жиры (г)",
        examples=[10]
    )
    carbs: int | None = Field(
        default=None,
        description="Углеводы (г)",
        examples=[45]
    )
    recipe: str | None = Field(
        default=None,
        description="Рецепт приготовления",
        examples=["1. Смешайте все ингредиенты..."]
    )


class MealReplaceRequest(BaseModel):
    """Схема для запроса замены блюда через LLM.

    Attributes:
        dish_name: Название блюда для замены
        reason: Причина замены (опционально)
    """
    dish_name: str = Field(
        description="Название блюда, которое нужно заменить",
        examples=["Овсянка с фруктами"]
    )
    reason: str | None = Field(
        default=None,
        description="Причина замены (поможет LLM подобрать альтернативу)",
        examples=["не люблю овсянку", "слишком много калорий",
                  "хочу что-то более сытное"]
    )


# =============================================================================
# Shopping List Schemas
# =============================================================================

class ShoppingItemResponse(BaseModel):
    """Схема ответа с элементом списка покупок.

    Attributes:
        id: Уникальный идентификатор
        item_name: Название продукта
        category: Категория продукта
        quantity: Количество
        estimated_price: Примерная стоимость
        checked: Отмечен ли пункт
    """
    id: int | None = Field(
        default=None,
        description="Уникальный идентификатор",
        examples=[1]
    )
    item_name: str | None = Field(
        default=None,
        description="Название продукта",
        examples=["Куриное филе", "Гречневая крупа", "Яблоки"]
    )
    category: str | None = Field(
        default=None,
        description="Категория продукта",
        examples=["Мясо", "Крупы", "Фрукты", "Овощи", "Молочные продукты"]
    )
    quantity: str | None = Field(
        default=None,
        description="Количество/вес",
        examples=["500 г", "1 кг", "3 шт"]
    )
    estimated_price: float | None = Field(
        default=None,
        description="Примерная стоимость (руб)",
        examples=[250.50, 120.00, 89.99]
    )
    checked: bool = Field(
        default=False,
        description="Отмечен ли пункт в списке",
        examples=[False, True]
    )

    class Config:
        from_attributes = True


class ShoppingListStatusResponse(BaseModel):
    """Схема ответа со статусом списка покупок.

    Attributes:
        status: Статус генерации (pending, generating, ready, error)
        items: Список продуктов
        total_price: Общая стоимость
    """
    status: str = Field(
        description="Статус генерации списка",
        examples=["pending", "generating", "ready", "error"]
    )
    items: list[ShoppingItemResponse] = Field(
        default=[],
        description="Список продуктов для покупки"
    )
    total_price: float | None = Field(
        default=None,
        description="Общая стоимость всех продуктов (руб)",
        examples=[3500.50, 5200.00]
    )


# =============================================================================
# LLM Schemas
# =============================================================================

class LLMLogResponse(BaseModel):
    """Схема ответа с логом обращения к LLM.

    Attributes:
        id: Уникальный идентификатор запроса
        request_json: Данные запроса к LLM
        response_json: Ответ от LLM
        created_at: Дата запроса
    """
    id: int = Field(
        description="Уникальный идентификатор запроса", examples=[1])
    request_json: dict | None = Field(
        default=None,
        description="Данные запроса к LLM"
    )
    response_json: dict | None = Field(
        default=None,
        description="Ответ от LLM"
    )
    created_at: datetime = Field(description="Дата и время запроса")

    class Config:
        from_attributes = True


# =============================================================================
# Error Schemas
# =============================================================================

class ErrorResponse(BaseModel):
    """Схема ответа с ошибкой.

    Attributes:
        error: Тип ошибки
        message: Подробное сообщение об ошибке
    """
    error: str = Field(
        description="Тип ошибки",
        examples=["Bad Request", "Unauthorized", "Not Found", "Conflict"]
    )
    message: str = Field(
        description="Подробное сообщение об ошибке",
        examples=["Email already registered",
                  "Plan not found", "Invalid credentials"]
    )


class ValidationErrorResponse(BaseModel):
    """Схема ответа с ошибкой валидации.

    Attributes:
        error: Тип ошибки
        message: Общее сообщение об ошибке
        details: Детали по каждому полю с ошибкой
    """
    error: str = Field(description="Тип ошибки", examples=["Validation Error"])
    message: str = Field(description="Общее сообщение", examples=[
                         "Ошибка валидации входных данных"])
    details: dict = Field(
        description="Детали ошибок по полям",
        examples=[{"calories": "Значение должно быть между 1000 и 6000"}]
    )


class StatusResponse(BaseModel):
    """Схема простого ответа со статусом операции.

    Attributes:
        status: Статус операции
    """
    status: str = Field(
        description="Статус операции",
        examples=["ok", "cleared", "success", "pending"]
    )
