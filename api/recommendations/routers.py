from fastapi import APIRouter, HTTPException, status, Depends, Query
from sqlalchemy import select, func, desc
from datetime import datetime, timedelta
import random

from api.db import SessionDep
from api.db.models import User, Song, Performer, ListeningHistory, Like
from api.dependencies.current_user import get_current_user
from api.storage.s3_storage import s3_storage

router = APIRouter(prefix="/api/recommendations", tags=["Recommendations"])


@router.get("/", status_code=status.HTTP_200_OK)
async def get_recommendations(
    session: SessionDep,
    current_user: User = Depends(get_current_user),
    limit: int = Query(20, ge=1, le=50)
):
    """Персональные рекомендации на основе истории и лайков"""

    # Получаем жанры из лайков и истории
    liked_songs_result = await session.execute(
        select(Song.style_music)
        .join(Like, Like.song_id == Song.id)
        .where(Like.user_id == current_user.id)
    )
    liked_styles = [row[0] for row in liked_songs_result.all()]

    history_songs_result = await session.execute(
        select(Song.style_music)
        .join(ListeningHistory, ListeningHistory.song_id == Song.id)
        .where(ListeningHistory.user_id == current_user.id)
        .order_by(ListeningHistory.listened_at.desc())
        .limit(20)
    )
    history_styles = [row[0] for row in history_songs_result.all()]

    # Объединяем предпочтения
    preferred_styles = list(set(liked_styles + history_styles))

    # Получаем ID песен, которые пользователь уже слушал/лайкал
    excluded_songs_result = await session.execute(
        select(ListeningHistory.song_id)
        .where(ListeningHistory.user_id == current_user.id)
    )
    excluded_songs = [row[0] for row in excluded_songs_result.all()]

    liked_songs_ids_result = await session.execute(
        select(Like.song_id)
        .where(Like.user_id == current_user.id)
    )
    excluded_songs += [row[0] for row in liked_songs_ids_result.all()]
    excluded_songs = list(set(excluded_songs))

    recommended_songs = []

    # Если есть предпочтения — рекомендуем по стилям
    if preferred_styles:
        # Берём топ-3 жанра
        top_styles = preferred_styles[:3]

        for style in top_styles:
            query = select(Song).where(Song.style_music == style)
            if excluded_songs:
                query = query.where(Song.id.notin_(excluded_songs))
            query = query.order_by(desc(Song.auditions)).limit(limit // 3)

            result = await session.execute(query)
            songs = result.scalars().all()

            for song in songs:
                cover_url = await s3_storage.get_file_url(song.cover) if song.cover else None
                audio_url = await s3_storage.get_file_url(song.audio_path) if song.audio_path else None

                performer_result = await session.execute(
                    select(Performer).where(Performer.id == song.performer_id)
                )
                performer = performer_result.scalar_one_or_none()

                recommended_songs.append({
                    "id": song.id,
                    "name": song.name,
                    "artist": performer.nickname if performer else "Unknown",
                    "style_music": song.style_music,
                    "cover_url": cover_url,
                    "audio_url": audio_url,
                    "duration": song.duration,
                    "auditions": song.auditions,
                    "reason": f"Похоже на то, что вы слушаете"
                })

    # Если мало рекомендаций — добавляем популярные
    if len(recommended_songs) < limit:
        remaining = limit - len(recommended_songs)
        existing_ids = [s["id"] for s in recommended_songs]

        query = select(Song).order_by(desc(Song.auditions)).limit(remaining + len(existing_ids))
        result = await session.execute(query)
        popular_songs = result.scalars().all()

        for song in popular_songs:
            if song.id in existing_ids or song.id in excluded_songs:
                continue

            cover_url = await s3_storage.get_file_url(song.cover) if song.cover else None
            audio_url = await s3_storage.get_file_url(song.audio_path) if song.audio_path else None

            performer_result = await session.execute(
                select(Performer).where(Performer.id == song.performer_id)
            )
            performer = performer_result.scalar_one_or_none()

            recommended_songs.append({
                "id": song.id,
                "name": song.name,
                "artist": performer.nickname if performer else "Unknown",
                "style_music": song.style_music,
                "cover_url": cover_url,
                "audio_url": audio_url,
                "duration": song.duration,
                "auditions": song.auditions,
                "reason": "Популярное"
            })

            if len(recommended_songs) >= limit:
                break

    # Перемешиваем для разнообразия
    random.shuffle(recommended_songs)

    return {
        "status": "success",
        "data": recommended_songs[:limit]
    }


@router.get("/performers", status_code=status.HTTP_200_OK)
async def get_recommended_performers(
    session: SessionDep,
    current_user: User = Depends(get_current_user),
    limit: int = Query(10, ge=1, le=20)
):
    """Рекомендуемые исполнители"""

    # Получаем исполнителей из истории
    history_performers_result = await session.execute(
        select(Song.performer_id)
        .join(ListeningHistory, ListeningHistory.song_id == Song.id)
        .where(ListeningHistory.user_id == current_user.id)
        .distinct()
    )
    listened_performers = [row[0] for row in history_performers_result.all()]

    # Находим похожих по стилю
    if listened_performers:
        # Получаем стили любимых исполнителей
        styles_result = await session.execute(
            select(Performer.style_music)
            .where(Performer.id.in_(listened_performers))
        )
        preferred_styles = list(set([row[0] for row in styles_result.all()]))

        query = select(Performer).where(
            Performer.style_music.in_(preferred_styles),
            Performer.id.notin_(listened_performers)
        ).limit(limit)

        result = await session.execute(query)
        performers = result.scalars().all()
    else:
        # Если нет истории — возвращаем случайных популярных
        query = select(Performer).order_by(desc(Performer.created_at)).limit(limit)
        result = await session.execute(query)
        performers = result.scalars().all()

    performers_list = []
    for performer in performers:
        photo_url = await s3_storage.get_file_url(performer.photo) if performer.photo else None

        # Считаем песни
        songs_count_result = await session.execute(
            select(func.count()).where(Song.performer_id == performer.id)
        )
        songs_count = songs_count_result.scalar()

        performers_list.append({
            "id": performer.id,
            "nickname": performer.nickname,
            "style_music": performer.style_music,
            "photo_url": photo_url,
            "songs_count": songs_count
        })

    return {"status": "success", "data": performers_list}


@router.get("/playlists", status_code=status.HTTP_200_OK)
async def get_recommended_playlists(
    session: SessionDep,
    current_user: User = Depends(get_current_user),
    limit: int = Query(10, ge=1, le=20)
):
    """Рекомендуемые плейлисты (публичные, не свои)"""

    from api.db.models import Playlist, PlaylistTrack

    query = select(Playlist).where(
        Playlist.is_public == True,
        Playlist.user_id != current_user.id
    ).order_by(desc(Playlist.created_at)).limit(limit)

    result = await session.execute(query)
    playlists = result.scalars().all()

    playlists_list = []
    for playlist in playlists:
        cover_url = await s3_storage.get_file_url(playlist.cover) if playlist.cover else None

        tracks_count_result = await session.execute(
            select(func.count()).where(PlaylistTrack.playlist_id == playlist.id)
        )
        tracks_count = tracks_count_result.scalar()

        playlists_list.append({
            "id": playlist.id,
            "name": playlist.name,
            "description": playlist.description,
            "cover_url": cover_url,
            "tracks_count": tracks_count,
            "created_at": playlist.created_at
        })

    return {"status": "success", "data": playlists_list}
