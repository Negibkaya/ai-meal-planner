# backend/app/routers/plans.py
import asyncio
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import set_committed_value

from app.database import get_db, async_session
from app.models import User, MealPlan
from app.schemas import (
    MealPlanCreate,
    MealPlanResponse,
    ErrorResponse,
    StatusResponse
)
from app.auth import get_current_user
from app.services.llm_service import generate_meal_plan

router = APIRouter(prefix="/plans", tags=["📋 Планы питания"])

# Словарь для отслеживания активных задач генерации (plan_id -> bool)
_generating_plans: dict[int, bool] = {}


async def _background_generate_plan(plan_id: int, user_id: int):
    """Фоновая генерация плана питания через LLM.

    Args:
        plan_id: ID плана для генерации
        user_id: ID пользователя (для логирования)
    """
    async with async_session() as db:
        try:
            result = await db.execute(
                select(MealPlan).where(MealPlan.id == plan_id)
            )
            plan = result.scalar_one_or_none()

            if not plan:
                return

            # Устанавливаем статус генерации
            plan.status = "generating"
            await db.commit()

            # Генерируем план через LLM
            await generate_meal_plan(plan, db)

            # Устанавливаем статус готовности
            plan.status = "ready"
            await db.commit()

        except Exception as e:
            print(f"Background generation error: {e}")
            try:
                result = await db.execute(
                    select(MealPlan).where(MealPlan.id == plan_id)
                )
                plan = result.scalar_one_or_none()
                if plan:
                    plan.status = "error"
                    await db.commit()
            except:
                pass
        finally:
            _generating_plans.pop(plan_id, None)


@router.get(
    "",
    response_model=list[MealPlanResponse],
    summary="Получить все планы пользователя",
    description="""
    Возвращает список всех планов питания текущего пользователя,
    отсортированных по дате создания (новые первыми).
    
    Каждый план включает список блюд (meals).
    
    **Требует авторизации:** Bearer token
    """,
    responses={
        200: {
            "description": "Список планов питания",
            "model": list[MealPlanResponse]
        },
        401: {
            "description": "Не авторизован",
            "model": ErrorResponse
        }
    }
)
async def get_plans(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Получить все планы питания текущего пользователя.

    Args:
        user: Текущий авторизованный пользователь
        db: Сессия базы данных

    Returns:
        list[MealPlanResponse]: Список планов с блюдами
    """
    result = await db.execute(
        select(MealPlan)
        .options(selectinload(MealPlan.meals))
        .where(MealPlan.user_id == user.id)
        .order_by(MealPlan.created_at.desc())
    )
    return result.scalars().all()


@router.post(
    "",
    response_model=MealPlanResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Создать новый план питания",
    description="""
    Создаёт новый план питания и запускает его генерацию в фоновом режиме.
    
    **Процесс:**
    1. Создаётся план со статусом "pending"
    2. Запускается фоновая задача генерации через LLM
    3. Статус меняется на "generating" → "ready" или "error"
    
    **Параметры плана:**
    - `goal`: Цель (похудение, набор массы, поддержание)
    - `calories`: Калорийность в день (1000-6000)
    - `budget`: Бюджет на неделю
    - `preferences`: Предпочтения в еде
    - `allergies`: Аллергии и исключения
    
    **Требует авторизации:** Bearer token
    
    **Ошибки:**
    - `401`: Не авторизован
    - `422`: Ошибка валидации данных
    """,
    responses={
        201: {
            "description": "План создан, генерация запущена",
            "model": MealPlanResponse
        },
        401: {
            "description": "Не авторизован",
            "model": ErrorResponse
        },
        422: {
            "description": "Ошибка валидации данных"
        }
    }
)
async def create_plan(
    data: MealPlanCreate,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Создать новый план питания.

    Args:
        data: Параметры плана (цель, калории, бюджет и т.д.)
        background_tasks: Менеджер фоновых задач
        user: Текущий авторизованный пользователь
        db: Сессия базы данных

    Returns:
        MealPlanResponse: Созданный план со статусом "pending"
    """
    plan = MealPlan(
        user_id=user.id,
        goal=data.goal,
        calories=data.calories,
        budget=data.budget,
        preferences=data.preferences,
        allergies=data.allergies,
        status="pending"
    )
    db.add(plan)
    await db.commit()
    await db.refresh(plan)

    # Устанавливаем пустой список блюд без запроса к БД
    set_committed_value(plan, "meals", [])

    # Запускаем генерацию в фоне
    _generating_plans[plan.id] = True
    asyncio.create_task(_background_generate_plan(plan.id, user.id))

    return plan


@router.get(
    "/{plan_id}",
    response_model=MealPlanResponse,
    summary="Получить детали плана",
    description="""
    Возвращает детальную информацию о конкретном плане питания
    вместе со списком всех блюд.
    
    **Требует авторизации:** Bearer token
    
    **Ошибки:**
    - `401`: Не авторизован
    - `404`: План не найден или не принадлежит пользователю
    """,
    responses={
        200: {
            "description": "Детали плана с блюдами",
            "model": MealPlanResponse
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
async def get_plan(
    plan_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Получить детали конкретного плана.

    Args:
        plan_id: ID плана питания
        user: Текущий авторизованный пользователь
        db: Сессия базы данных

    Returns:
        MealPlanResponse: Детали плана с блюдами

    Raises:
        HTTPException: 404 если план не найден
    """
    result = await db.execute(
        select(MealPlan)
        .options(selectinload(MealPlan.meals))
        .where(MealPlan.id == plan_id, MealPlan.user_id == user.id)
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="План не найден"
        )
    return plan


@router.get(
    "/{plan_id}/status",
    summary="Проверить статус генерации плана",
    description="""
    Возвращает текущий статус генерации плана питания.
    
    **Статусы:**
    - `pending`: Ожидает начала генерации
    - `generating`: Идёт генерация через LLM
    - `ready`: Генерация завершена успешно
    - `error`: Произошла ошибка при генерации
    
    **Также возвращает:**
    - `is_generating`: true если генерация активна прямо сейчас
    
    **Требует авторизации:** Bearer token
    
    **Ошибки:**
    - `401`: Не авторизован
    - `404`: План не найден
    """,
    responses={
        200: {
            "description": "Статус генерации",
            "content": {
                "application/json": {
                    "example": {
                        "status": "generating",
                        "is_generating": True
                    }
                }
            }
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
async def get_plan_status(
    plan_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Проверить статус генерации плана.

    Args:
        plan_id: ID плана питания
        user: Текущий авторизованный пользователь
        db: Сессия базы данных

    Returns:
        dict: Статус плана и флаг активной генерации

    Raises:
        HTTPException: 404 если план не найден
    """
    result = await db.execute(
        select(MealPlan).where(
            MealPlan.id == plan_id,
            MealPlan.user_id == user.id
        )
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="План не найден"
        )

    return {
        "status": plan.status,
        "is_generating": plan.id in _generating_plans
    }


@router.post(
    "/{plan_id}/regenerate",
    response_model=MealPlanResponse,
    summary="Перегенерировать план",
    description="""
    Удаляет все текущие блюда из плана и запускает повторную генерацию.
    
    **Процесс:**
    1. Удаляет все существующие блюда
    2. Устанавливает статус "pending"
    3. Запускает фоновую генерацию
    
    **Защита от повторных запросов:**
    Если генерация уже идёт, возвращается ошибка 409.
    
    **Требует авторизации:** Bearer token
    
    **Ошибки:**
    - `401`: Не авторизован
    - `404`: План не найден
    - `409`: Генерация уже в процессе
    """,
    responses={
        200: {
            "description": "Перегенерация запущена",
            "model": MealPlanResponse
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
            "description": "Генерация уже в процессе",
            "model": ErrorResponse
        }
    }
)
async def regenerate_plan(
    plan_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Перегенерировать план питания.

    Args:
        plan_id: ID плана для перегенерации
        user: Текущий авторизованный пользователь
        db: Сессия базы данных

    Returns:
        MealPlanResponse: План со статусом "pending"

    Raises:
        HTTPException: 404 если план не найден, 409 если генерация уже идёт
    """
    # Проверка на активную генерацию
    if plan_id in _generating_plans:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Генерация плана уже выполняется"
        )

    result = await db.execute(
        select(MealPlan)
        .options(selectinload(MealPlan.meals))
        .where(MealPlan.id == plan_id, MealPlan.user_id == user.id)
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="План не найден"
        )

    # Удаляем все блюда
    for meal in plan.meals:
        await db.delete(meal)

    plan.status = "pending"
    await db.commit()

    # Запускаем генерацию в фоне
    _generating_plans[plan.id] = True
    asyncio.create_task(_background_generate_plan(plan.id, user.id))

    await db.refresh(plan)
    set_committed_value(plan, "meals", [])

    return plan


@router.delete(
    "/{plan_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить план",
    description="""
    Полностью удаляет план питания со всеми блюдами и списком покупок.
    
    **Требует авторизации:** Bearer token
    
    **Ошибки:**
    - `401`: Не авторизован
    - `404`: План не найден
    """,
    responses={
        204: {
            "description": "План успешно удалён"
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
async def delete_plan(
    plan_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Удалить план питания.

    Args:
        plan_id: ID плана для удаления
        user: Текущий авторизованный пользователь
        db: Сессия базы данных

    Raises:
        HTTPException: 404 если план не найден
    """
    result = await db.execute(
        select(MealPlan).where(
            MealPlan.id == plan_id,
            MealPlan.user_id == user.id
        )
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="План не найден"
        )

    # Удаляем из отслеживания генераций
    _generating_plans.pop(plan_id, None)

    await db.delete(plan)
    await db.commit()
