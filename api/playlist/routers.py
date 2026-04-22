from fastapi import APIRouter, HTTPException, status, Depends, UploadFile, File, Query
from sqlalchemy import select, func
from typing import Optional

from api.db import SessionDep
from api.db.models import Playlist, PlaylistTrack, Song, User
from api.dependencies.current_user import get_current_user
from api.dependencies.current_admin import current_admin
from api.storage.s3_storage import s3_storage
from api.playlist.models import PlaylistCreate, PlaylistUpdate, AddTrackToPlaylist, UpdateTrackPosition

router = APIRouter(prefix="/api/playlists", tags=["Playlists"])


# GET /playlists - список плейлистов пользователя (доступно авторизованным)
@router.get("/", status_code=status.HTTP_200_OK)
async def get_my_playlists(
        session: SessionDep,
        current_user: User = Depends(get_current_user),
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=100)
):
    query = select(Playlist).where(Playlist.user_id == current_user.id)
    query = query.offset(skip).limit(limit).order_by(Playlist.created_at.desc())
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
            "is_public": playlist.is_public,
            "tracks_count": tracks_count,
            "created_at": playlist.created_at
        })

    return {
        "status": "success",
        "data": playlists_list
    }


# GET /playlists/public - публичные плейлисты всех пользователей (доступно всем)
@router.get("/public", status_code=status.HTTP_200_OK)
async def get_public_playlists(
        session: SessionDep,
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=100),
        search: Optional[str] = None
):
    query = select(Playlist).where(Playlist.is_public == True)

    if search:
        query = query.where(Playlist.name.ilike(f"%{search}%"))

    query = query.offset(skip).limit(limit).order_by(Playlist.created_at.desc())
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
            "user_id": playlist.user_id,
            "name": playlist.name,
            "description": playlist.description,
            "cover_url": cover_url,
            "tracks_count": tracks_count,
            "created_at": playlist.created_at
        })

    return {
        "status": "success",
        "data": playlists_list
    }


# GET /playlists/{playlist_id} - получить плейлист по ID
@router.get("/{playlist_id}", status_code=status.HTTP_200_OK)
async def get_playlist(
        playlist_id: int,
        session: SessionDep,
        current_user: User = Depends(get_current_user)
):
    result = await session.execute(
        select(Playlist).where(Playlist.id == playlist_id)
    )
    playlist = result.scalar_one_or_none()

    if not playlist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Плейлист не найден"
        )

    # Проверяем доступ (владелец или публичный)
    if playlist.user_id != current_user.id and not playlist.is_public:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нет доступа к этому плейлисту"
        )

    cover_url = await s3_storage.get_file_url(playlist.cover) if playlist.cover else None

    # Получаем треки
    tracks_result = await session.execute(
        select(PlaylistTrack)
        .where(PlaylistTrack.playlist_id == playlist_id)
        .order_by(PlaylistTrack.position)
    )
    tracks = tracks_result.scalars().all()

    tracks_list = []
    for track in tracks:
        song_result = await session.execute(
            select(Song).where(Song.id == track.song_id)
        )
        song = song_result.scalar_one_or_none()

        if song:
            cover_url_song = await s3_storage.get_file_url(song.cover) if song.cover else None
            audio_url = await s3_storage.get_file_url(song.audio_path) if song.audio_path else None

            tracks_list.append({
                "id": track.id,
                "song_id": track.song_id,
                "position": track.position,
                "added_at": track.added_at,
                "song": {
                    "id": song.id,
                    "name": song.name,
                    "duration": song.duration,
                    "cover_url": cover_url_song,
                    "audio_url": audio_url
                }
            })

    return {
        "status": "success",
        "data": {
            "id": playlist.id,
            "user_id": playlist.user_id,
            "name": playlist.name,
            "description": playlist.description,
            "cover_url": cover_url,
            "is_public": playlist.is_public,
            "created_at": playlist.created_at,
            "tracks": tracks_list
        }
    }


# POST /playlists - создать плейлист (доступно авторизованным)
@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_playlist(
        playlist_data: PlaylistCreate,
        session: SessionDep,
        current_user: User = Depends(get_current_user)
):
    new_playlist = Playlist(
        user_id=current_user.id,
        name=playlist_data.name,
        description=playlist_data.description,
        is_public=playlist_data.is_public
    )

    session.add(new_playlist)
    await session.commit()
    await session.refresh(new_playlist)

    return {
        "status": "success",
        "message": "Плейлист успешно создан",
        "data": {
            "id": new_playlist.id,
            "name": new_playlist.name,
            "description": new_playlist.description,
            "is_public": new_playlist.is_public,
            "created_at": new_playlist.created_at
        }
    }


# PUT /playlists/{playlist_id} - обновить плейлист
@router.put("/{playlist_id}", status_code=status.HTTP_200_OK)
async def update_playlist(
        playlist_id: int,
        playlist_data: PlaylistUpdate,
        session: SessionDep,
        current_user: User = Depends(get_current_user)
):
    result = await session.execute(
        select(Playlist).where(Playlist.id == playlist_id)
    )
    playlist = result.scalar_one_or_none()

    if not playlist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Плейлист не найден"
        )

    if playlist.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нет прав для редактирования этого плейлиста"
        )

    if playlist_data.name is not None:
        playlist.name = playlist_data.name

    if playlist_data.description is not None:
        playlist.description = playlist_data.description

    if playlist_data.is_public is not None:
        playlist.is_public = playlist_data.is_public

    await session.commit()
    await session.refresh(playlist)

    return {
        "status": "success",
        "message": "Плейлист успешно обновлен",
        "data": {
            "id": playlist.id,
            "name": playlist.name,
            "description": playlist.description,
            "is_public": playlist.is_public
        }
    }


# POST /playlists/{playlist_id}/cover - загрузить обложку плейлиста
@router.post("/{playlist_id}/cover", status_code=status.HTTP_200_OK)
async def upload_playlist_cover(
        session: SessionDep,
        playlist_id: int,
        cover: UploadFile = File(...),
        current_user: User = Depends(get_current_user)
):
    result = await session.execute(
        select(Playlist).where(Playlist.id == playlist_id)
    )
    playlist = result.scalar_one_or_none()

    if not playlist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Плейлист не найден"
        )

    if playlist.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нет прав для редактирования этого плейлиста"
        )

    allowed_formats = ['jpg', 'jpeg', 'png', 'webp']
    file_extension = cover.filename.split('.')[-1].lower() if cover.filename else ''

    if file_extension not in allowed_formats:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Неподдерживаемый формат. Разрешены: {', '.join(allowed_formats)}"
        )

    content = await cover.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Размер файла не должен превышать 5MB"
        )

    old_cover = playlist.cover

    try:
        cover_path = await s3_storage.upload_playlist_cover(cover, playlist_id, playlist.name)
        playlist.cover = cover_path
        await session.commit()

        if old_cover:
            await s3_storage.delete_file(old_cover)

        cover_url = await s3_storage.get_file_url(cover_path)

        return {
            "status": "success",
            "message": "Обложка плейлиста успешно загружена",
            "cover_url": cover_url
        }
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при загрузке обложки: {str(e)}"
        )


# POST /playlists/{playlist_id}/tracks - добавить трек в плейлист
@router.post("/{playlist_id}/tracks", status_code=status.HTTP_201_CREATED)
async def add_track_to_playlist(
        playlist_id: int,
        track_data: AddTrackToPlaylist,
        session: SessionDep,
        current_user: User = Depends(get_current_user)
):
    result = await session.execute(
        select(Playlist).where(Playlist.id == playlist_id)
    )
    playlist = result.scalar_one_or_none()

    if not playlist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Плейлист не найден"
        )

    if playlist.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нет прав для редактирования этого плейлиста"
        )

    # Проверяем существование песни
    song_result = await session.execute(
        select(Song).where(Song.id == track_data.song_id)
    )
    if not song_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Песня не найдена"
        )

    # Проверяем, не добавлена ли уже песня
    existing = await session.execute(
        select(PlaylistTrack).where(
            PlaylistTrack.playlist_id == playlist_id,
            PlaylistTrack.song_id == track_data.song_id
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Песня уже добавлена в плейлист"
        )

    # Получаем максимальную позицию
    max_pos_result = await session.execute(
        select(func.max(PlaylistTrack.position))
        .where(PlaylistTrack.playlist_id == playlist_id)
    )
    max_position = max_pos_result.scalar() or -1

    new_track = PlaylistTrack(
        playlist_id=playlist_id,
        song_id=track_data.song_id,
        position=max_position + 1
    )

    session.add(new_track)
    await session.commit()
    await session.refresh(new_track)

    return {
        "status": "success",
        "message": "Трек успешно добавлен в плейлист",
        "data": {
            "id": new_track.id,
            "song_id": new_track.song_id,
            "position": new_track.position,
            "added_at": new_track.added_at
        }
    }


# PUT /playlists/{playlist_id}/tracks/{track_id}/position - изменить позицию трека
@router.put("/{playlist_id}/tracks/{track_id}/position", status_code=status.HTTP_200_OK)
async def update_track_position(
        playlist_id: int,
        track_id: int,
        position_data: UpdateTrackPosition,
        session: SessionDep,
        current_user: User = Depends(get_current_user)
):
    result = await session.execute(
        select(Playlist).where(Playlist.id == playlist_id)
    )
    playlist = result.scalar_one_or_none()

    if not playlist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Плейлист не найден"
        )

    if playlist.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нет прав для редактирования этого плейлиста"
        )

    track_result = await session.execute(
        select(PlaylistTrack).where(
            PlaylistTrack.id == track_id,
            PlaylistTrack.playlist_id == playlist_id
        )
    )
    track = track_result.scalar_one_or_none()

    if not track:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Трек не найден в плейлисте"
        )

    track.position = position_data.position
    await session.commit()

    return {
        "status": "success",
        "message": "Позиция трека обновлена",
        "data": {
            "id": track.id,
            "position": track.position
        }
    }


# DELETE /playlists/{playlist_id}/tracks/{track_id} - удалить трек из плейлиста
@router.delete("/{playlist_id}/tracks/{track_id}", status_code=status.HTTP_200_OK)
async def remove_track_from_playlist(
        playlist_id: int,
        track_id: int,
        session: SessionDep,
        current_user: User = Depends(get_current_user)
):
    result = await session.execute(
        select(Playlist).where(Playlist.id == playlist_id)
    )
    playlist = result.scalar_one_or_none()

    if not playlist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Плейлист не найден"
        )

    if playlist.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нет прав для редактирования этого плейлиста"
        )

    track_result = await session.execute(
        select(PlaylistTrack).where(
            PlaylistTrack.id == track_id,
            PlaylistTrack.playlist_id == playlist_id
        )
    )
    track = track_result.scalar_one_or_none()

    if not track:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Трек не найден в плейлисте"
        )

    await session.delete(track)
    await session.commit()

    return {
        "status": "success",
        "message": "Трек успешно удален из плейлиста"
    }


# DELETE /playlists/{playlist_id} - удалить плейлист
@router.delete("/{playlist_id}", status_code=status.HTTP_200_OK)
async def delete_playlist(
        playlist_id: int,
        session: SessionDep,
        current_user: User = Depends(get_current_user)
):
    result = await session.execute(
        select(Playlist).where(Playlist.id == playlist_id)
    )
    playlist = result.scalar_one_or_none()

    if not playlist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Плейлист не найден"
        )

    if playlist.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нет прав для удаления этого плейлиста"
        )

    if playlist.cover:
        await s3_storage.delete_file(playlist.cover)

    await session.delete(playlist)
    await session.commit()

    return {
        "status": "success",
        "message": "Плейлист успешно удален"
    }