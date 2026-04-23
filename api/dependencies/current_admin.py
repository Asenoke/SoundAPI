from fastapi import Depends, HTTPException
from starlette import status

from api.dependencies.current_user import get_current_user  # Исправлен импорт
from api.db.models import Role, User


async def current_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != Role.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Доступ запрещен. Требуется роль: {Role.ADMIN.value}"
        )
    return current_user