from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy import select
from datetime import datetime, timedelta

from api.db import SessionDep
from api.db.models import User, Buy, Subscription
from api.dependencies.current_user import get_current_user

router = APIRouter(prefix="/api/subscription", tags=["Subscription"])


@router.get("/", status_code=status.HTTP_200_OK)
async def get_subscription_status(
    session: SessionDep,
    current_user: User = Depends(get_current_user)
):
    """Получить статус подписки пользователя"""

    # Ищем активную покупку премиума
    result = await session.execute(
        select(Buy)
        .where(
            Buy.user_id == current_user.id,
            Buy.status == True,
            Buy.valid_until > datetime.utcnow()
        )
        .order_by(Buy.data.desc())
    )
    active_buy = result.scalar_one_or_none()

    return {
        "status": "success",
        "subscription": current_user.subscription.value,
        "has_active_premium": active_buy is not None,
        "valid_until": active_buy.valid_until.isoformat() if active_buy else None
    }


@router.post("/upgrade", status_code=status.HTTP_200_OK)
async def upgrade_subscription(
    session: SessionDep,
    current_user: User = Depends(get_current_user)
):
    """Обновить подписку до PREMIUM"""

    # Проверяем, не премиум ли уже
    if current_user.subscription == Subscription.PREMIUM:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="У вас уже активна премиум подписка"
        )

    # Создаём запись о покупке
    new_buy = Buy(
        user_id=current_user.id,
        price=200.00,
        valid_until=datetime.utcnow() + timedelta(days=30),
        status=True
    )
    session.add(new_buy)

    # Обновляем подписку пользователя
    current_user.subscription = Subscription.PREMIUM

    await session.commit()
    await session.refresh(new_buy)

    return {
        "status": "success",
        "message": "Подписка успешно обновлена до PREMIUM",
        "subscription": "PREMIUM",
        "valid_until": new_buy.valid_until.isoformat()
    }


@router.post("/cancel", status_code=status.HTTP_200_OK)
async def cancel_subscription(
    session: SessionDep,
    current_user: User = Depends(get_current_user)
):
    """Отменить премиум подписку (вернуть на BASE)"""

    if current_user.subscription == Subscription.BASE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="У вас базовая подписка"
        )

    # Отключаем активные покупки
    await session.execute(
        select(Buy)
        .where(
            Buy.user_id == current_user.id,
            Buy.status == True
        )
        .update({"status": False})
    )

    # Возвращаем базовую подписку
    current_user.subscription = Subscription.BASE
    await session.commit()

    return {
        "status": "success",
        "message": "Подписка отменена",
        "subscription": "BASE"
    }
