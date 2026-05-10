from fastapi import APIRouter, HTTPException, status, Depends, Query
from sqlalchemy import select, func
from datetime import datetime, timedelta

from api.db import SessionDep
from api.db.models import User, Song, ListeningHistory, Performer
from api.dependencies.current_user import get_current_user
from api.storage.s3_storage import s3_storage

router = APIRouter(prefix="/api/history", tags=["History"])


@router.get("/", status_code=status.HTTP_200_OK)
async def get_listening_history(
    session: SessionDep,
    current_user: User = Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    days: int = Query(None, ge=1, le=365, description="Фильтр по количеству дней")
):
    """Получить историю прослушиваний пользователя"""

    query = select(ListeningHistory).where(ListeningHistory.user_id == current_user.id)

    if days:
        from_date = datetime.utcnow() - timedelta(days=days)
        query = query.where(ListeningHistory.listened_at >= from_date)

    query = query.order_by(ListeningHistory.listened_at.desc())
    query = query.offset(skip).limit(limit)

    result = await session.execute(query)
    history = result.scalars().all()

    history_list = []
    for record in history:
        song_result = await session.execute(select(Song).where(Song.id == record.song_id))
        song = song_result.scalar_one_or_none()
        if song:
            cover_url = await s3_storage.get_file_url(song.cover) if song.cover else None
            audio_url = await s3_storage.get_file_url(song.audio_path) if song.audio_path else None

            performer_result = await session.execute(
                select(Performer).where(Performer.id == song.performer_id)
            )
            performer = performer_result.scalar_one_or_none()

            history_list.append({
                "id": record.id,
                "song_id": song.id,
                "name": song.name,
                "artist": performer.nickname if performer else "Unknown",
                "cover_url": cover_url,
                "audio_url": audio_url,
                "duration": song.duration,
                "listened_at": record.listened_at
            })

    return {"status": "success", "data": history_list}


@router.post("/{song_id}", status_code=status.HTTP_201_CREATED)
async def add_to_history(
    song_id: int,
    session: SessionDep,
    current_user: User = Depends(get_current_user)
):
    """Добавить песню в историю прослушиваний"""

    song_result = await session.execute(select(Song).where(Song.id == song_id))
    song = song_result.scalar_one_or_none()
    if not song:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Песня не найдена")

    # Проверяем, не слушали ли уже эту песню в последние 5 минут (чтобы не спамить)
    five_min_ago = datetime.utcnow() - timedelta(minutes=5)
    recent = await session.execute(
        select(ListeningHistory)
        .where(
            ListeningHistory.user_id == current_user.id,
            ListeningHistory.song_id == song_id,
            ListeningHistory.listened_at >= five_min_ago
        )
    )

    if recent.scalar_one_or_none():
        # Обновляем время последнего прослушивания
        recent_record = recent.scalar_one_or_none()
        if recent_record:
            recent_record.listened_at = datetime.utcnow()
            await session.commit()
        return {"status": "success", "message": "Время прослушивания обновлено"}

    new_record = ListeningHistory(
        user_id=current_user.id,
        song_id=song_id,
        listened_at=datetime.utcnow()
    )
    session.add(new_record)
    await session.commit()
    await session.refresh(new_record)

    return {"status": "success", "message": "Добавлено в историю"}


@router.delete("/{history_id}", status_code=status.HTTP_200_OK)
async def remove_from_history(
    history_id: int,
    session: SessionDep,
    current_user: User = Depends(get_current_user)
):
    """Удалить запись из истории"""

    result = await session.execute(
        select(ListeningHistory)
        .where(ListeningHistory.id == history_id, ListeningHistory.user_id == current_user.id)
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Запись не найдена")

    await session.delete(record)
    await session.commit()

    return {"status": "success", "message": "Запись удалена из истории"}


@router.delete("/", status_code=status.HTTP_200_OK)
async def clear_history(
    session: SessionDep,
    current_user: User = Depends(get_current_user)
):
    """Очистить всю историю прослушиваний"""

    await session.execute(
        select(ListeningHistory)
        .where(ListeningHistory.user_id == current_user.id)
        .delete()
    )
    await session.commit()

    return {"status": "success", "message": "История очищена"}


@router.get("/stats", status_code=status.HTTP_200_OK)
async def get_listening_stats(
    session: SessionDep,
    current_user: User = Depends(get_current_user),
    days: int = Query(30, ge=1, le=365)
):
    """Статистика прослушиваний"""

    from_date = datetime.utcnow() - timedelta(days=days)

    # Общее количество прослушиваний
    total_result = await session.execute(
        select(func.count())
        .where(
            ListeningHistory.user_id == current_user.id,
            ListeningHistory.listened_at >= from_date
        )
    )
    total_listens = total_result.scalar()

    # Самые прослушиваемые песни
    top_songs_result = await session.execute(
        select(ListeningHistory.song_id, func.count().label("count"))
        .where(
            ListeningHistory.user_id == current_user.id,
            ListeningHistory.listened_at >= from_date
        )
        .group_by(ListeningHistory.song_id)
        .order_by(func.count().desc())
        .limit(5)
    )
    top_songs = []
    for row in top_songs_result.all():
        song_result = await session.execute(select(Song).where(Song.id == row[0]))
        song = song_result.scalar_one_or_none()
        if song:
            cover_url = await s3_storage.get_file_url(song.cover) if song.cover else None
            top_songs.append({
                "song_id": song.id,
                "name": song.name,
                "cover_url": cover_url,
                "listens": row[1]
            })

    return {
        "status": "success",
        "period_days": days,
        "total_listens": total_listens,
        "top_songs": top_songs
    }
