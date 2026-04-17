from fastapi import Depends, HTTPException
from starlette import status

from api.auth.routers import get_current_user
from api.db.models import Role, User


def current_admin_or_user():
    async def role_checker(
        current_user: User = Depends(get_current_user)
    ) -> User:
        if current_user.role != Role.ADMIN.value or current_user.role != Role.USER.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Доступ запрещен. Требуется роль: {Role.ADMIN.value} или {Role.USER.value}"
            )
        return current_user
    return role_checker