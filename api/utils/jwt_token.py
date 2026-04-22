from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete

import jwt

from api.db import SessionDep
from api.db.models import User, RefreshToken
from config import settings


# Объявление констант
SECRET_KEY = settings.JWT_SECRET_KEY
REFRESH_SECRET_KEY = settings.JWT_REFRESH_SECRET_KEY  
ALGORITHM = settings.JWT_ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
REFRESH_TOKEN_EXPIRE_DAYS = getattr(settings, 'JWT_REFRESH_TOKEN_EXPIRE_DAYS', 7)


# Создание ACCESS JWT-токена
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire, "iat": datetime.utcnow(), "type": "access"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


# Создание REFRESH JWT-токена
def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode.update({"exp": expire, "iat": datetime.utcnow(), "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, REFRESH_SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


# Верификация ACCESS JWT-токена
def verify_access_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "access":
            return None
        return payload
    except jwt.ExpiredSignatureError:
        print("Token has expired")
        return None
    except jwt.InvalidTokenError as e:
        print(f"Token verification failed: {e}")
        return None


# Верификация REFRESH JWT-токена
def verify_refresh_token(token: str):
    try:
        payload = jwt.decode(token, REFRESH_SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            return None
        return payload
    except jwt.ExpiredSignatureError:
        print("Refresh token has expired")
        return None
    except jwt.InvalidTokenError as e:
        print(f"Refresh token verification failed: {e}")
        return None



async def save_refresh_token(session: SessionDep, user_id: int, refresh_token: str):
    new_refresh = RefreshToken(
        user_id=user_id,
        token=refresh_token,
        expires_at=datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    )
    session.add(new_refresh)
    await session.commit()
    await session.refresh(new_refresh)
    return new_refresh


# проверка refresh token в БД
async def validate_refresh_token(session: SessionDep, refresh_token: str) -> Optional[int]:
    payload = verify_refresh_token(refresh_token)
    if not payload:
        return None

    user_id = int(payload.get("sub"))

    # Проверяем в БД
    stmt = select(RefreshToken).where(
        RefreshToken.token == refresh_token,
        RefreshToken.revoked == False,
        RefreshToken.expires_at > datetime.utcnow()
    )
    result = await session.execute(stmt)
    db_token = result.scalar_one_or_none()

    if not db_token:
        return None

    return user_id


# отзыв refresh token (при выходе)
async def revoke_refresh_token(session: SessionDep, refresh_token: str):
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.token == refresh_token)
        .values(revoked=True, revoked_at=datetime.utcnow())
    )
    await session.commit()


# отзыв всех refresh token пользователя (при смене пароля)
async def revoke_all_user_tokens(session: SessionDep, user_id: int):
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked == False)
        .values(revoked=True, revoked_at=datetime.utcnow())
    )
    await session.commit()


# удаление просроченных токенов (для периодической очистки)
async def cleanup_expired_tokens(session: SessionDep):
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)

    result = await session.execute(
        delete(RefreshToken).where(
            RefreshToken.expires_at < thirty_days_ago
        )
    )
    await session.commit()
    return result.rowcount


# обновление access token через refresh token
async def refresh_access_token(session: SessionDep, refresh_token: str) -> Optional[str]:

    user_id = await validate_refresh_token(session, refresh_token)
    if not user_id:
        return None

    # Получаем пользователя из БД для email и role
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        return None

    # Создаём новый access token с полными данными
    new_access_token = create_access_token(data={
        "sub": str(user_id),
        "email": user.email,
        "role": user.role.value
    })

    return new_access_token


# получение текущего пользователя из токена
async def get_current_user_from_token(session: SessionDep, token: str):
    payload = verify_access_token(token)
    if not payload:
        return None

    user_id = int(payload.get("sub"))

    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    return user