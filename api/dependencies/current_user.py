from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select
from starlette import status

from api.db import SessionDep
from api.db.models import User
from api.dependencies import security
from api.utils.jwt_token import verify_access_token


async def get_current_user(
        session: SessionDep,
        credentials: HTTPAuthorizationCredentials = Depends(security),
) -> User:

    token = credentials.credentials

    # Верифицируем токен
    payload = verify_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недействительный или просроченный токен",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Получаем user_id из payload
    user_id = int(payload.get("sub"))

    # Ищем пользователя в БД
    result = await session.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Пользователь не найден",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user



