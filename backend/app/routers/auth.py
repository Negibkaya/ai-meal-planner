from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
from app.schemas import UserCreate, UserLogin, UserResponse, Token, ErrorResponse
from app.auth import hash_password, verify_password, create_access_token

router = APIRouter(prefix="/auth", tags=["🔐 Аутентификация"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Регистрация нового пользователя",
    description="""
    Создаёт новую учётную запись пользователя.
    
    - Проверяет уникальность email
    - Хеширует пароль
    - Возвращает данные созданного пользователя
    
    **Ошибки:**
    - `400`: Email уже зарегистрирован
    - `422`: Ошибка валидации данных (некорректный email, пароль < 6 символов)
    """,
    responses={
        201: {
            "description": "Пользователь успешно создан",
            "model": UserResponse
        },
        400: {
            "description": "Email уже зарегистрирован",
            "model": ErrorResponse
        },
        422: {
            "description": "Ошибка валидации входных данных"
        }
    }
)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    """Регистрация нового пользователя.

    Args:
        user_data: Данные для регистрации (email, password, name)
        db: Сессия базы данных

    Returns:
        UserResponse: Данные созданного пользователя

    Raises:
        HTTPException: 400 если email уже зарегистрирован
    """
    # Проверяем существование пользователя с таким email
    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email уже зарегистрирован"
        )

    # Создаём нового пользователя с хешированным паролем
    user = User(
        email=user_data.email,
        password_hash=hash_password(user_data.password),
        name=user_data.name
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post(
    "/login",
    response_model=Token,
    summary="Вход в систему",
    description="""
    Аутентификация пользователя и получение JWT токена.
    
    - Проверяет email и пароль
    - Возвращает access token для доступа к защищённым эндпоинтам
    
    **Использование токена:**
    Передайте токен в заголовке `Authorization: Bearer <token>`
    
    **Ошибки:**
    - `401`: Неверный email или пароль
    - `422`: Ошибка валидации данных
    """,
    responses={
        200: {
            "description": "Успешная аутентификация",
            "model": Token
        },
        401: {
            "description": "Неверные учётные данные",
            "model": ErrorResponse
        },
        422: {
            "description": "Ошибка валидации входных данных"
        }
    }
)
async def login(data: UserLogin, db: AsyncSession = Depends(get_db)):
    """Вход в систему.

    Args:
        data: Учётные данные (email, password)
        db: Сессия базы данных

    Returns:
        Token: JWT токен для аутентификации

    Raises:
        HTTPException: 401 если учётные данные неверны
    """
    # Ищем пользователя по email
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    # Проверяем существование пользователя и пароль
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Создаём JWT токен
    token = create_access_token({"sub": user.id})
    return Token(access_token=token)
