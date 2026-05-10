from fastapi import APIRouter, HTTPException, status, Depends, Query
from sqlalchemy import select, or_, func
from typing import Optional

from api.db import SessionDep
from api.db.models import Song, Performer, Playlist, User
from api.dependencies.current_user import get_current_user
from api.storage.s3_storage import s3_storage

router = APIRouter(prefix="/api/search", tags=["Search"])


@router.get("/", status_code=status.HTTP_200_OK)
async def search(
    session: SessionDep,
    q: str = Query(..., min_length=1, max_length=100, description="Поисковый запрос"),
    current_user: User = Depends(get_current_user),
    limit: int = Query(20, ge=1, le=100)
):
    """Универсальный поиск по песням, исполнителям и плейлистам"""

    search_query = f"%{q}%"

    # Поиск песен
    songs_result = await session.execute(
        select(Song)
        .where(Song.name.ilike(search_query))
        .limit(limit)
        .order_by(Song.name)
    )
    songs = songs_result.scalars().all()

    songs_list = []
    for song in songs:
        performer_result = await session.execute(
            select(Performer).where(Performer.id == song.performer_id)
        )
        performer = performer_result.scalar_one_or_none()
        cover_url = await s3_storage.get_file_url(song.cover) if song.cover else None
        audio_url = await s3_storage.get_file_url(song.audio_path) if song.audio_path else None

        songs_list.append({
            "id": song.id,
            "type": "song",
            "name": song.name,
            "artist": performer.nickname if performer else "Unknown",
            "cover_url": cover_url,
            "audio_url": audio_url,
            "duration": song.duration
        })

    # Поиск исполнителей
    performers_result = await session.execute(
        select(Performer)
        .where(Performer.nickname.ilike(search_query))
        .limit(limit)
        .order_by(Performer.nickname)
    )
    performers = performers_result.scalars().all()

    performers_list = []
    for performer in performers:
        photo_url = await s3_storage.get_file_url(performer.photo) if performer.photo else None

        # Считаем количество песен
        songs_count_result = await session.execute(
            select(func.count()).where(Song.performer_id == performer.id)
        )
        songs_count = songs_count_result.scalar()

        performers_list.append({
            "id": performer.id,
            "type": "performer",
            "name": performer.nickname,
            "style_music": performer.style_music,
            "photo_url": photo_url,
            "songs_count": songs_count
        })

    # Поиск плейлистов (только публичные + свои)
    playlists_query = select(Playlist).where(
        Playlist.name.ilike(search_query),
        or_(
            Playlist.is_public == True,
            Playlist.user_id == current_user.id
        )
    ).limit(limit).order_by(Playlist.name)

    playlists_result = await session.execute(playlists_query)
    playlists = playlists_result.scalars().all()

    playlists_list = []
    for playlist in playlists:
        cover_url = await s3_storage.get_file_url(playlist.cover) if playlist.cover else None

        # Считаем количество треков
        from api.db.models import PlaylistTrack
        tracks_count_result = await session.execute(
            select(func.count()).where(PlaylistTrack.playlist_id == playlist.id)
        )
        tracks_count = tracks_count_result.scalar()

        playlists_list.append({
            "id": playlist.id,
            "type": "playlist",
            "name": playlist.name,
            "description": playlist.description,
            "cover_url": cover_url,
            "tracks_count": tracks_count,
            "is_public": playlist.is_public
        })

    return {
        "status": "success",
        "query": q,
        "results": {
            "songs": songs_list,
            "performers": performers_list,
            "playlists": playlists_list
        },
        "total": len(songs_list) + len(performers_list) + len(playlists_list)
    }


@router.get("/suggestions", status_code=status.HTTP_200_OK)
async def get_search_suggestions(
    session: SessionDep,
    q: str = Query(..., min_length=1, max_length=50),
    limit: int = Query(5, ge=1, le=10)
):
    """Подсказки для поиска (автодополнение)"""

    search_query = f"%{q}%"

    # Подсказки из песен
    songs_result = await session.execute(
        select(Song.name)
        .where(Song.name.ilike(search_query))
        .limit(limit)
        .distinct()
    )
    song_suggestions = [row[0] for row in songs_result.all()]

    # Подсказки из исполнителей
    performers_result = await session.execute(
        select(Performer.nickname)
        .where(Performer.nickname.ilike(search_query))
        .limit(limit)
        .distinct()
    )
    performer_suggestions = [row[0] for row in performers_result.all()]

    return {
        "status": "success",
        "query": q,
        "suggestions": {
            "songs": song_suggestions,
            "performers": performer_suggestions
        }
    }
