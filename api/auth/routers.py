from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy import select
from datetime import datetime

from api.auth.models import UserRegister, UserLogin
from api.db import SessionDep
from api.db.models import User, RefreshToken
from api.dependencies.current_user import get_current_user
from api.utils.hash_password import hash_password, verify_password
from api.utils.jwt_token import (
    create_access_token,
    create_refresh_token,
    save_refresh_token,
    refresh_access_token,
    revoke_all_user_tokens
)

router = APIRouter(prefix="/api/auth", tags=["Auth"])


@router.post("/registration", status_code=status.HTTP_201_CREATED)
async def registration(
        user: UserRegister,
        session: SessionDep
):
    # Проверяем уникальность email
    existing_email = await session.execute(
        select(User).where(User.email == user.email)
    )
    if existing_email.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пользователь с таким email уже существует"
        )

    # Проверяем уникальность телефона
    existing_phone = await session.execute(
        select(User).where(User.phone_number == user.phone_number)
    )
    if existing_phone.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пользователь с таким номером телефона уже существует"
        )

    # Создаём пользователя
    new_user = User(
        firstname=user.firstname,
        lastname=user.lastname,
        email=user.email,
        phone_number=user.phone_number,
        password=hash_password(user.password),
        age=user.age,
    )

    session.add(new_user)
    await session.commit()
    await session.refresh(new_user)

    # Генерируем токены
    access_token = create_access_token(
        data={
            "sub": str(new_user.id),
            "email": new_user.email,
            "role": new_user.role.value
        }
    )

    refresh_token = create_refresh_token(
        data={
            "sub": str(new_user.id),
            "email": new_user.email
        }
    )

    # Сохраняем refresh token в БД
    await save_refresh_token(session, new_user.id, refresh_token)

    return {
        "status": "success",
        "message": "Пользователь успешно создан",
        "user": {
            "id": new_user.id,
            "firstname": new_user.firstname,
            "lastname": new_user.lastname,
            "email": new_user.email,
            "role": new_user.role.value,
        },
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }


@router.post("/login", status_code=status.HTTP_200_OK)
async def login(
        user_data: UserLogin,
        session: SessionDep
):
    # Ищем пользователя по email
    result = await session.execute(
        select(User).where(User.email == user_data.email)
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(user_data.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль"
        )

    # Генерируем новые токены
    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "email": user.email,
            "role": user.role.value
        }
    )

    refresh_token = create_refresh_token(
        data={
            "sub": str(user.id),
            "email": user.email
        }
    )

    # Сохраняем refresh token в БД
    await save_refresh_token(session, user.id, refresh_token)


    return {
        "status": "success",
        "message": "Вход выполнен успешно",
        "user": {
            "id": user.id,
            "firstname": user.firstname,
            "lastname": user.lastname,
            "email": user.email,
            "role": user.role.value,
            "avatar_path": user.avatar,
            "avatar_url": "S3"
        },
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }


@router.post("/refresh", status_code=status.HTTP_200_OK)
async def refresh_token(
        session: SessionDep,
        current_user: User = Depends(get_current_user)
):

    # Ищем активный refresh token пользователя в БД
    result = await session.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == current_user.id,
            RefreshToken.revoked == False,
            RefreshToken.expires_at > datetime.utcnow()
        )
    )
    refresh_token_obj = result.scalar_one_or_none()

    if not refresh_token_obj:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token не найден или истек"
        )

    # Получаем строку токена
    refresh_token_str = refresh_token_obj.token

    # Обновляем access token
    new_access_token = await refresh_access_token(session, refresh_token_str)

    if not new_access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Не удалось обновить токен"
        )

    return {
        "status": "success",
        "access_token": new_access_token,
        "token_type": "bearer"
    }


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
        session: SessionDep,
        current_user: User = Depends(get_current_user)

):
    # Отзываем все refresh токены пользователя
    await revoke_all_user_tokens(session, current_user.id)


    return {
        "status": "success",
        "message": "Вы успешно вышли из системы"
    }

