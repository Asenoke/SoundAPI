from fastapi import APIRouter, HTTPException, status, Depends, UploadFile, File, Query
from sqlalchemy import select

from api.db import SessionDep
from api.db.models import User
from api.dependencies.current_user import get_current_user
from api.dependencies.current_admin import current_admin
from api.auth.models import UserEdit
from api.utils.hash_password import hash_password, verify_password
from api.utils.jwt_token import revoke_all_user_tokens
from api.storage.s3_storage import s3_storage

router = APIRouter(prefix="/api/users", tags=["Users"])


@router.get("/", status_code=status.HTTP_200_OK, dependencies=[Depends(current_admin)])  # ← ДОБАВЛЕНО
async def get_all_users(
    session: SessionDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100)
):
    """Получить список всех пользователей (только для админов)"""
    result = await session.execute(select(User).offset(skip).limit(limit))
    users = result.scalars().all()

    users_list = []
    for user in users:
        avatar_url = await s3_storage.get_file_url(user.avatar) if user.avatar else None
        users_list.append({
            "id": user.id,
            "firstname": user.firstname,
            "lastname": user.lastname,
            "email": user.email,
            "phone_number": user.phone_number,
            "age": user.age,
            "role": user.role.value,
            "subscription": user.subscription.value,
            "avatar_url": avatar_url,
            "created_at": user.created_at
        })

    return {"status": "success", "data": users_list}


@router.get("/profile", status_code=status.HTTP_200_OK)
async def get_profile(current_user: User = Depends(get_current_user)):
    avatar_url = await s3_storage.get_file_url(current_user.avatar) if current_user.avatar else None

    return {
        "status": "success",
        "user": {
            "id": current_user.id,
            "firstname": current_user.firstname,
            "lastname": current_user.lastname,
            "email": current_user.email,
            "phone_number": current_user.phone_number,
            "age": current_user.age,
            "role": current_user.role.value,
            "subscription": current_user.subscription.value,
            "avatar_url": avatar_url
        }
    }


@router.put("/profile", status_code=status.HTTP_200_OK)
async def update_profile(
        session: SessionDep,
        user_data: UserEdit,
        current_user: User = Depends(get_current_user),
):
    if user_data.firstname is not None:
        current_user.firstname = user_data.firstname

    if user_data.lastname is not None:
        current_user.lastname = user_data.lastname

    if user_data.age is not None:
        current_user.age = user_data.age

    if user_data.email is not None:
        existing = await session.execute(
            select(User).where(User.email == user_data.email, User.id != current_user.id)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email уже используется")
        current_user.email = user_data.email

    if user_data.phone_number is not None:
        existing = await session.execute(
            select(User).where(User.phone_number == user_data.phone_number, User.id != current_user.id)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Номер телефона уже используется")
        current_user.phone_number = user_data.phone_number

    if user_data.password is not None:
        current_user.password = hash_password(user_data.password)
        await revoke_all_user_tokens(session, current_user.id)

    await session.commit()
    await session.refresh(current_user)

    avatar_url = await s3_storage.get_file_url(current_user.avatar) if current_user.avatar else None

    return {
        "status": "success",
        "message": "Профиль успешно обновлен",
        "user": {
            "id": current_user.id,
            "firstname": current_user.firstname,
            "lastname": current_user.lastname,
            "email": current_user.email,
            "phone_number": current_user.phone_number,
            "age": current_user.age,
            "role": current_user.role.value,
            "subscription": current_user.subscription.value,
            "avatar_url": avatar_url
        }
    }


@router.put("/{user_id}", status_code=status.HTTP_200_OK, dependencies=[Depends(current_admin)])  # ← ДОБАВЛЕНО
async def update_user_by_id(
    user_id: int,
    session: SessionDep,
    user_data: UserEdit,
):
    """Обновить пользователя по ID (только для админов)"""
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")

    if user_data.firstname is not None:
        user.firstname = user_data.firstname

    if user_data.lastname is not None:
        user.lastname = user_data.lastname

    if user_data.age is not None:
        user.age = user_data.age

    if user_data.email is not None:
        existing = await session.execute(
            select(User).where(User.email == user_data.email, User.id != user_id)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email уже используется")
        user.email = user_data.email

    if user_data.phone_number is not None:
        existing = await session.execute(
            select(User).where(User.phone_number == user_data.phone_number, User.id != user_id)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Номер телефона уже используется")
        user.phone_number = user_data.phone_number

    if user_data.password is not None:
        user.password = hash_password(user_data.password)
        await revoke_all_user_tokens(session, user_id)

    await session.commit()
    await session.refresh(user)

    avatar_url = await s3_storage.get_file_url(user.avatar) if user.avatar else None

    return {
        "status": "success",
        "message": "Пользователь успешно обновлен",
        "user": {
            "id": user.id,
            "firstname": user.firstname,
            "lastname": user.lastname,
            "email": user.email,
            "phone_number": user.phone_number,
            "age": user.age,
            "role": user.role.value,
            "subscription": user.subscription.value,
            "avatar_url": avatar_url
        }
    }


@router.post("/change-password", status_code=status.HTTP_200_OK)
async def change_password(
        session: SessionDep,
        old_password: str,
        new_password: str,
        current_user: User = Depends(get_current_user)
):
    if not verify_password(old_password, current_user.password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Неверный старый пароль")

    if len(new_password) < 8:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Новый пароль должен содержать минимум 8 символов")

    # Проверка сложности пароля
    special_chars = ["/", "!", "@", "#", "$", "%", "^", "&", "*", "+", "-", "?"]
    if not any(char in new_password for char in special_chars):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Пароль должен содержать хотя бы один специальный символ")
    if not any(c.isupper() for c in new_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Пароль должен содержать хотя бы одну заглавную букву")
    if not any(c.islower() for c in new_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Пароль должен содержать хотя бы одну строчную букву")
    if not any(c.isdigit() for c in new_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Пароль должен содержать хотя бы одну цифру")

    current_user.password = hash_password(new_password)
    await revoke_all_user_tokens(session, current_user.id)
    await session.commit()

    return {"status": "success", "message": "Пароль успешно изменен. Пожалуйста, войдите заново."}


@router.post("/avatar", status_code=status.HTTP_200_OK)
async def upload_avatar(
        session: SessionDep,
        avatar: UploadFile = File(...),
        current_user: User = Depends(get_current_user),
):
    # Проверяем что файл вообще пришел
    if not avatar:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Файл не передан")

    # Проверяем имя файла
    if not avatar.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Имя файла отсутствует")

    # Проверяем формат
    allowed_formats = ['jpg', 'jpeg', 'png', 'gif', 'webp']
    file_extension = avatar.filename.split('.')[-1].lower() if avatar.filename else ''

    if file_extension not in allowed_formats:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Неподдерживаемый формат. Разрешены: {', '.join(allowed_formats)}")

    # Проверяем размер (5MB)
    content = await avatar.read()
    if len(content) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Файл пустой")

    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Размер файла не должен превышать 5MB")

    # Сохраняем старый аватар
    old_avatar = current_user.avatar

    try:
        # Загружаем новый аватар — передаём content чтобы избежать повторного чтения ← ИСПРАВЛЕНО
        avatar_path = await s3_storage.upload_user_avatar(avatar, current_user.id, content=content)
        current_user.avatar = avatar_path
        await session.commit()

        # Удаляем старый аватар
        if old_avatar:
            await s3_storage.delete_file(old_avatar)

        avatar_url = await s3_storage.get_file_url(avatar_path)

        return {
            "status": "success",
            "message": "Аватар успешно загружен",
            "avatar_url": avatar_url,
            "avatar_path": avatar_path
        }
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Ошибка при загрузке аватара: {str(e)}")


@router.get("/avatar", status_code=status.HTTP_200_OK)
async def get_avatar(current_user: User = Depends(get_current_user)):
    if not current_user.avatar:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Аватар не найден"
        )

    avatar_url = await s3_storage.get_file_url(current_user.avatar)

    return {
        "status": "success",
        "avatar_url": avatar_url
    }
