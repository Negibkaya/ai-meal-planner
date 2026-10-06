from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User, LLMRequest
from app.schemas import LLMLogResponse, ErrorResponse
from app.auth import get_current_user

router = APIRouter(prefix="/llm", tags=["🤖 LLM Логи"])


@router.get(
    "/logs",
    response_model=list[LLMLogResponse],
    summary="Получить историю обращений к LLM",
    description="""
    Возвращает историю последних 50 обращений к LLM для текущего пользователя.
    
    **Данные лога:**
    - `request_json`: Данные запроса к LLM (промпт, параметры)
    - `response_json`: Ответ от LLM
    - `created_at`: Время запроса
    
    Используется для отладки и мониторинга работы LLM.
    
    **Требует авторизации:** Bearer token
    
    **Ошибки:**
    - `401`: Не авторизован
    """,
    responses={
        200: {
            "description": "Список логов обращений к LLM",
            "model": list[LLMLogResponse]
        },
        401: {
            "description": "Не авторизован",
            "model": ErrorResponse
        }
    }
)
async def get_llm_logs(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Получить историю обращений к LLM.

    Args:
        user: Текущий авторизованный пользователь
        db: Сессия базы данных

    Returns:
        list[LLMLogResponse]: Список последних 50 логов (сначала новые)
    """
    result = await db.execute(
        select(LLMRequest)
        .where(LLMRequest.user_id == user.id)
        .order_by(LLMRequest.created_at.desc())
        .limit(50)
    )
    return result.scalars().all()
