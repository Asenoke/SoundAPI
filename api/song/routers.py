from fastapi import APIRouter, HTTPException, status, Depends, UploadFile, File, Query
from sqlalchemy import select, update
from typing import Optional

from api.db import SessionDep
from api.db.models import Song, Performer
from api.dependencies.current_admin import current_admin
from api.storage.s3_storage import s3_storage
from api.song.models import SongCreate, SongUpdate

router = APIRouter(prefix="/api/songs", tags=["Songs"])


# список песен (доступно всем)
@router.get("/", status_code=status.HTTP_200_OK)
async def get_songs(
        session: SessionDep,
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=100),
        search: Optional[str] = None,
        performer_id: Optional[int] = None
):
    query = select(Song)

    if search:
        query = query.where(Song.name.ilike(f"%{search}%"))

    if performer_id:
        query = query.where(Song.performer_id == performer_id)

    query = query.offset(skip).limit(limit).order_by(Song.name)
    result = await session.execute(query)
    songs = result.scalars().all()

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
            "performer_id": song.performer_id,
            "performer_nickname": performer.nickname if performer else None,
            "name": song.name,
            "style_music": song.style_music,
            "cover_url": cover_url,
            "audio_url": audio_url,
            "auditions": song.auditions,
            "duration": song.duration,
            "created_at": song.created_at
        })

    return {
        "status": "success",
        "data": songs_list
    }


# получить песню (доступно всем)
@router.get("/{song_id}", status_code=status.HTTP_200_OK)
async def get_song(
        song_id: int,
        session: SessionDep
):
    result = await session.execute(
        select(Song).where(Song.id == song_id)
    )
    song = result.scalar_one_or_none()

    if not song:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Песня не найдена"
        )

    await session.execute(
        update(Song)
        .where(Song.id == song_id)
        .values(auditions=Song.auditions + 1)
    )
    await session.commit()

    performer_result = await session.execute(
        select(Performer).where(Performer.id == song.performer_id)
    )
    performer = performer_result.scalar_one_or_none()

    cover_url = await s3_storage.get_file_url(song.cover) if song.cover else None
    audio_url = await s3_storage.get_file_url(song.audio_path) if song.audio_path else None

    return {
        "status": "success",
        "data": {
            "id": song.id,
            "performer_id": song.performer_id,
            "performer_nickname": performer.nickname if performer else None,
            "name": song.name,
            "style_music": song.style_music,
            "cover_url": cover_url,
            "audio_url": audio_url,
            "auditions": song.auditions + 1,
            "duration": song.duration,
            "created_at": song.created_at
        }
    }


# создать песню (только админ)
@router.post("/", status_code=status.HTTP_201_CREATED, dependencies=[Depends(current_admin())])
async def create_song(
        song_data: SongCreate,
        session: SessionDep
):
    # Проверяем существование исполнителя
    performer_result = await session.execute(
        select(Performer).where(Performer.id == song_data.performer_id)
    )
    if not performer_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Исполнитель не найден"
        )

    new_song = Song(
        performer_id=song_data.performer_id,
        name=song_data.name,
        style_music=song_data.style_music,
        duration=song_data.duration
    )

    session.add(new_song)
    await session.commit()
    await session.refresh(new_song)

    return {
        "status": "success",
        "message": "Песня успешно создана",
        "data": {
            "id": new_song.id,
            "performer_id": new_song.performer_id,
            "name": new_song.name,
            "style_music": new_song.style_music,
            "duration": new_song.duration,
            "created_at": new_song.created_at
        }
    }


# обновить песню (только админ)
@router.put("/{song_id}", status_code=status.HTTP_200_OK, dependencies=[Depends(current_admin())])
async def update_song(
        song_id: int,
        song_data: SongUpdate,
        session: SessionDep
):
    result = await session.execute(
        select(Song).where(Song.id == song_id)
    )
    song = result.scalar_one_or_none()

    if not song:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Песня не найдена"
        )

    if song_data.performer_id is not None:
        performer_result = await session.execute(
            select(Performer).where(Performer.id == song_data.performer_id)
        )
        if not performer_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Исполнитель не найден"
            )
        song.performer_id = song_data.performer_id

    if song_data.name is not None:
        song.name = song_data.name

    if song_data.style_music is not None:
        song.style_music = song_data.style_music

    if song_data.duration is not None:
        song.duration = song_data.duration

    await session.commit()
    await session.refresh(song)

    return {
        "status": "success",
        "message": "Песня успешно обновлена",
        "data": {
            "id": song.id,
            "performer_id": song.performer_id,
            "name": song.name,
            "style_music": song.style_music,
            "duration": song.duration,
            "created_at": song.created_at
        }
    }


# загрузить обложку песни (только админ)
@router.post("/{song_id}/cover", status_code=status.HTTP_200_OK, dependencies=[Depends(current_admin())])
async def upload_song_cover(
        session: SessionDep,
        song_id: int,
        cover: UploadFile = File(...)
):
    result = await session.execute(
        select(Song).where(Song.id == song_id)
    )
    song = result.scalar_one_or_none()

    if not song:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Песня не найдена"
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

    old_cover = song.cover

    try:
        cover_path = await s3_storage.upload_song_cover(cover, song.name, song_id)
        song.cover = cover_path
        await session.commit()

        if old_cover:
            await s3_storage.delete_file(old_cover)

        cover_url = await s3_storage.get_file_url(cover_path)

        return {
            "status": "success",
            "message": "Обложка песни успешно загружена",
            "cover_url": cover_url
        }
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при загрузке обложки: {str(e)}"
        )


#  загрузить аудио файл (только админ)
@router.post("/{song_id}/audio", status_code=status.HTTP_200_OK, dependencies=[Depends(current_admin())])
async def upload_song_audio(
        session: SessionDep,
        song_id: int,
        audio: UploadFile = File(...)
):
    result = await session.execute(
        select(Song).where(Song.id == song_id)
    )
    song = result.scalar_one_or_none()

    if not song:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Песня не найдена"
        )

    allowed_formats = ['mp3', 'wav', 'ogg', 'm4a']
    file_extension = audio.filename.split('.')[-1].lower() if audio.filename else ''

    if file_extension not in allowed_formats:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Неподдерживаемый формат. Разрешены: {', '.join(allowed_formats)}"
        )

    content = await audio.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Размер файла не должен превышать 20MB"
        )

    old_audio = song.audio_path

    try:
        audio_path = await s3_storage.upload_song_audio(audio, song.name, song_id)
        song.audio_path = audio_path
        await session.commit()

        if old_audio:
            await s3_storage.delete_file(old_audio)

        audio_url = await s3_storage.get_file_url(audio_path)

        return {
            "status": "success",
            "message": "Аудио файл успешно загружен",
            "audio_url": audio_url
        }
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при загрузке аудио: {str(e)}"
        )


# удалить песню (только админ)
@router.delete("/{song_id}", status_code=status.HTTP_200_OK, dependencies=[Depends(current_admin())])
async def delete_song(
        song_id: int,
        session: SessionDep
):
    result = await session.execute(
        select(Song).where(Song.id == song_id)
    )
    song = result.scalar_one_or_none()

    if not song:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Песня не найдена"
        )

    if song.cover:
        await s3_storage.delete_file(song.cover)
    if song.audio_path:
        await s3_storage.delete_file(song.audio_path)

    await session.delete(song)
    await session.commit()

    return {
        "status": "success",
        "message": "Песня успешно удалена"
    }