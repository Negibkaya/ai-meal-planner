# backend/app/routers/meals.py
import asyncio
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db, async_session
from app.models import User, MealPlan, ShoppingItem, Meal
from app.schemas import (
    MealResponse,
    MealReplaceRequest,
    MealUpdate,
    ShoppingItemResponse,
    ShoppingListStatusResponse,
    ErrorResponse,
    StatusResponse
)
from app.auth import get_current_user
from app.services.llm_service import replace_meal, generate_shopping_list

router = APIRouter(prefix="/meals", tags=["🍽️ Блюда и покупки"])

# Отслеживание активных операций
_replacing_meals: dict[str, bool] = {}  # "plan_id:dish_name" -> bool
_generating_shopping: dict[int, bool] = {}  # plan_id -> bool


async def _get_user_plan(plan_id: int, user: User, db: AsyncSession) -> MealPlan:
    """Получить план пользователя с проверкой доступа.

    Args:
        plan_id: ID плана
        user: Текущий пользователь
        db: Сессия БД

    Returns:
        MealPlan: План питания с загруженными блюдами и покупками

    Raises:
        HTTPException: 404 если план не найден или не принадлежит пользователю
    """
    result = await db.execute(
        select(MealPlan)
        .options(selectinload(MealPlan.meals), selectinload(MealPlan.shopping_items))
        .where(MealPlan.id == plan_id, MealPlan.user_id == user.id)
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="План не найден"
        )
    return plan


@router.post(
    "/{plan_id}/replace",
    response_model=list[MealResponse],
    summary="Заменить блюдо в плане",
    description="""
    Использует LLM для подбора альтернативных блюд на замену указанному.
    
    **Процесс:**
    1. Анализирует текущий план (цель, калории, аллергии)
    2. Учитывает причину замены
    3. Генерирует 2-3 альтернативы через LLM
    
    **Защита от повторных запросов:**
    Если замена для этого блюда уже выполняется, возвращается ошибка 409.
    
    **Требует авторизации:** Bearer token
    
    **Ошибки:**
    - `401`: Не авторизован
    - `404`: План не найден
    - `409`: Замена уже выполняется
    """,
    responses={
        200: {
            "description": "Список альтернативных блюд",
            "model": list[MealResponse]
        },
        401: {
            "description": "Не авторизован",
            "model": ErrorResponse
        },
        404: {
            "description": "План не найден",
            "model": ErrorResponse
        },
        409: {
            "description": "Замена уже выполняется",
            "model": ErrorResponse
        }
    }
)
async def replace_dish(
    plan_id: int,
    data: MealReplaceRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Заменить блюдо в плане через LLM.

    Args:
        plan_id: ID плана питания
        data: Название блюда и причина замены
        user: Текущий авторизованный пользователь
        db: Сессия базы данных

    Returns:
        list[MealResponse]: Список альтернативных блюд

    Raises:
        HTTPException: 404 если план не найден, 409 если замена уже идёт
    """
    # Ключ для отслеживания
    replace_key = f"{plan_id}:{data.dish_name}"

    # Проверка на повторный запрос
    if replace_key in _replacing_meals:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Замена этого блюда уже выполняется"
        )

    try:
        _replacing_meals[replace_key] = True
        plan = await _get_user_plan(plan_id, user, db)
        alternatives = await replace_meal(plan, data.dish_name, data.reason, db)
        return alternatives
    finally:
        _replacing_meals.pop(replace_key, None)


@router.get(
    "/{plan_id}/shopping-list",
    response_model=ShoppingListStatusResponse,
    summary="Получить список покупок",
    description="""
    Возвращает список покупок для плана с текущим статусом.
    
    **Статусы:**
    - `ready`: Список готов, возвращаются items
    - `generating`: Идёт генерация через LLM
    - `pending`: Список не создан, нужно вызвать POST /generate
    
    **При статусе ready также возвращается:**
    - `total_price`: Общая стоимость продуктов
    
    **Требует авторизации:** Bearer token
    
    **Ошибки:**
    - `401`: Не авторизован
    - `404`: План не найден
    """,
    responses={
        200: {
            "description": "Статус и список покупок",
            "model": ShoppingListStatusResponse
        },
        401: {
            "description": "Не авторизован",
            "model": ErrorResponse
        },
        404: {
            "description": "План не найден",
            "model": ErrorResponse
        }
    }
)
async def get_shopping_list(
    plan_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Получить список покупок для плана.

    Args:
        plan_id: ID плана питания
        user: Текущий авторизованный пользователь
        db: Сессия базы данных

    Returns:
        ShoppingListStatusResponse: Статус и список покупок
    """
    plan = await _get_user_plan(plan_id, user, db)

    # Если список уже есть - возвращаем
    if plan.shopping_items:
        total = sum(item.estimated_price or 0 for item in plan.shopping_items)
        return ShoppingListStatusResponse(
            status="ready",
            items=plan.shopping_items,
            total_price=total
        )

    # Если генерация уже идёт
    if plan_id in _generating_shopping:
        return ShoppingListStatusResponse(status="generating", items=[], total_price=None)

    # Возвращаем pending
    return ShoppingListStatusResponse(status="pending", items=[], total_price=None)


@router.post(
    "/{plan_id}/shopping-list/generate",
    response_model=ShoppingListStatusResponse,
    summary="Сгенерировать список покупок",
    description="""
    Запускает генерацию списка покупок через LLM на основе блюд плана.
    
    **Процесс:**
    1. Анализирует все блюда в плане
    2. Группирует ингредиенты по категориям
    3. Оценивает стоимость каждого продукта
    4. Сохраняет список в БД
    
    **Защита от повторных запросов:**
    Если генерация уже идёт, возвращается ошибка 409.
    
    **Требует авторизации:** Bearer token
    
    **Ошибки:**
    - `401`: Не авторизован
    - `404`: План не найден
    - `409`: Генерация уже выполняется
    """,
    responses={
        200: {
            "description": "Список сгенерирован",
            "model": ShoppingListStatusResponse
        },
        401: {
            "description": "Не авторизован",
            "model": ErrorResponse
        },
        404: {
            "description": "План не найден",
            "model": ErrorResponse
        },
        409: {
            "description": "Генерация уже выполняется",
            "model": ErrorResponse
        }
    }
)
async def generate_shopping_list_endpoint(
    plan_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Запустить генерацию списка покупок.

    Args:
        plan_id: ID плана питания
        user: Текущий авторизованный пользователь
        db: Сессия базы данных

    Returns:
        ShoppingListStatusResponse: Сгенерированный список с ценами

    Raises:
        HTTPException: 409 если генерация уже идёт
    """
    # Проверка на повторный запрос
    if plan_id in _generating_shopping:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Генерация списка покупок уже выполняется"
        )

    plan = await _get_user_plan(plan_id, user, db)

    # Если уже есть - возвращаем
    if plan.shopping_items:
        total = sum(item.estimated_price or 0 for item in plan.shopping_items)
        return ShoppingListStatusResponse(
            status="ready",
            items=plan.shopping_items,
            total_price=total
        )

    try:
        _generating_shopping[plan_id] = True
        items = await generate_shopping_list(plan, db)
        total = sum(item.estimated_price or 0 for item in items)
        return ShoppingListStatusResponse(
            status="ready",
            items=items,
            total_price=total
        )
    finally:
        _generating_shopping.pop(plan_id, None)


@router.patch(
    "/{meal_id}",
    response_model=MealResponse,
    summary="Обновить блюдо",
    description="""
    Обновляет данные конкретного блюда (например, после выбора альтернативы).
    
    **Обновляемые поля:**
    - `dish_name`: Название блюда
    - `calories`: Калорийность
    - `protein`: Белки
    - `fat`: Жиры
    - `carbs`: Углеводы
    - `recipe`: Рецепт
    
    **Требует авторизации:** Bearer token
    
    **Ошибки:**
    - `401`: Не авторизован
    - `404`: Блюдо не найдено или не принадлежит пользователю
    - `422`: Ошибка валидации данных
    """,
    responses={
        200: {
            "description": "Блюдо обновлено",
            "model": MealResponse
        },
        401: {
            "description": "Не авторизован",
            "model": ErrorResponse
        },
        404: {
            "description": "Блюдо не найдено",
            "model": ErrorResponse
        },
        422: {
            "description": "Ошибка валидации данных"
        }
    }
)
async def update_meal(
    meal_id: int,
    data: MealUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Обновить данные блюда.

    Args:
        meal_id: ID блюда для обновления
        data: Новые данные блюда
        user: Текущий авторизованный пользователь
        db: Сессия базы данных

    Returns:
        MealResponse: Обновлённые данные блюда

    Raises:
        HTTPException: 404 если блюдо не найдено
    """
    # Ищем блюдо и проверяем права доступа через meal_plan -> user_id
    result = await db.execute(
        select(Meal)
        .join(MealPlan)
        .where(Meal.id == meal_id, MealPlan.user_id == user.id)
    )
    meal = result.scalar_one_or_none()

    if not meal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Блюдо не найдено"
        )

    # Обновляем поля
    meal.dish_name = data.dish_name
    if data.calories is not None:
        meal.calories = data.calories
    if data.recipe is not None:
        meal.recipe = data.recipe
    if data.protein is not None:
        meal.protein = data.protein
    if data.fat is not None:
        meal.fat = data.fat
    if data.carbs is not None:
        meal.carbs = data.carbs

    await db.commit()
    await db.refresh(meal)
    return meal


@router.delete(
    "/{plan_id}/shopping-list",
    summary="Очистить список покупок",
    description="""
    Удаляет весь список покупок для плана.
    
    Полезно для перегенерации списка (например, после изменения блюд).
    
    **Требует авторизации:** Bearer token
    
    **Ошибки:**
    - `401`: Не авторизован
    - `404`: План не найден
    """,
    responses={
        200: {
            "description": "Список очищен",
            "model": StatusResponse
        },
        401: {
            "description": "Не авторизован",
            "model": ErrorResponse
        },
        404: {
            "description": "План не найден",
            "model": ErrorResponse
        }
    }
)
async def clear_shopping_list(
    plan_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Очистить список покупок.

    Args:
        plan_id: ID плана питания
        user: Текущий авторизованный пользователь
        db: Сессия базы данных

    Returns:
        StatusResponse: Подтверждение очистки
    """
    plan = await _get_user_plan(plan_id, user, db)

    for item in plan.shopping_items:
        await db.delete(item)

    await db.commit()
    return StatusResponse(status="cleared")
