from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy import select, delete

from api.db import SessionDep
from api.db.models import User, Song, Like
from api.dependencies.current_user import get_current_user

router = APIRouter(prefix="/api/likes", tags=["Likes"])


@router.get("/", status_code=status.HTTP_200_OK)
async def get_liked_songs(
    session: SessionDep,
    current_user: User = Depends(get_current_user),
    skip: int = 0,
    limit: int = 100
):
    """Получить список лайкнутых песен пользователя"""
    from api.storage.s3_storage import s3_storage

    result = await session.execute(
        select(Like)
        .where(Like.user_id == current_user.id)
        .offset(skip)
        .limit(limit)
        .order_by(Like.created_at.desc())
    )
    likes = result.scalars().all()

    songs_list = []
    for like in likes:
        song_result = await session.execute(select(Song).where(Song.id == like.song_id))
        song = song_result.scalar_one_or_none()
        if song:
            cover_url = await s3_storage.get_file_url(song.cover) if song.cover else None
            audio_url = await s3_storage.get_file_url(song.audio_path) if song.audio_path else None

            # Получаем исполнителя
            from api.db.models import Performer
            performer_result = await session.execute(
                select(Performer).where(Performer.id == song.performer_id)
            )
            performer = performer_result.scalar_one_or_none()

            songs_list.append({
                "id": song.id,
                "name": song.name,
                "style_music": song.style_music,
                "cover_url": cover_url,
                "audio_url": audio_url,
                "auditions": song.auditions,
                "duration": song.duration,
                "performer_nickname": performer.nickname if performer else None,
                "liked_at": like.created_at
            })

    return {"status": "success", "data": songs_list}


@router.post("/{song_id}", status_code=status.HTTP_201_CREATED)
async def like_song(
    song_id: int,
    session: SessionDep,
    current_user: User = Depends(get_current_user)
):
    """Добавить песню в лайки"""
    # Проверяем существование песни
    song_result = await session.execute(select(Song).where(Song.id == song_id))
    song = song_result.scalar_one_or_none()
    if not song:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Песня не найдена")

    # Проверяем, не лайкнута ли уже
    existing = await session.execute(
        select(Like).where(Like.user_id == current_user.id, Like.song_id == song_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Песня уже в избранном")

    new_like = Like(user_id=current_user.id, song_id=song_id)
    session.add(new_like)
    await session.commit()
    await session.refresh(new_like)

    return {"status": "success", "message": "Песня добавлена в избранное"}


@router.delete("/{song_id}", status_code=status.HTTP_200_OK)
async def unlike_song(
    song_id: int,
    session: SessionDep,
    current_user: User = Depends(get_current_user)
):
    """Удалить песню из лайков"""
    result = await session.execute(
        select(Like).where(Like.user_id == current_user.id, Like.song_id == song_id)
    )
    like = result.scalar_one_or_none()
    if not like:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Песня не найдена в избранном")

    await session.delete(like)
    await session.commit()

    return {"status": "success", "message": "Песня удалена из избранного"}


@router.get("/check/{song_id}", status_code=status.HTTP_200_OK)
async def check_like(
    song_id: int,
    session: SessionDep,
    current_user: User = Depends(get_current_user)
):
    """Проверить, лайкнута ли песня"""
    result = await session.execute(
        select(Like).where(Like.user_id == current_user.id, Like.song_id == song_id)
    )
    is_liked = result.scalar_one_or_none() is not None

    return {"status": "success", "is_liked": is_liked}
