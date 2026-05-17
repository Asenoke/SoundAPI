from fastapi import APIRouter, HTTPException, status, Depends, UploadFile, File, Query, Form
from sqlalchemy import select
from typing import Optional

from api.db import SessionDep
from api.db.models import Song, Performer, Like, User
from api.dependencies.current_admin import current_admin
from api.dependencies.current_user import get_current_user
from api.storage.s3_storage import s3_storage
from api.song.models import SongCreate, SongUpdate

router = APIRouter(prefix="/api/songs", tags=["Songs"])


@router.get("/", status_code=status.HTTP_200_OK)
async def get_songs(
        session: SessionDep,
        current_user: User = Depends(get_current_user),
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
        performer_result = await session.execute(select(Performer).where(Performer.id == song.performer_id))
        performer = performer_result.scalar_one_or_none()
        cover_url = await s3_storage.get_file_url(song.cover) if song.cover else None
        audio_url = await s3_storage.get_file_url(song.audio_path) if song.audio_path else None

        # Проверяем лайк текущего пользователя ← ДОБАВЛЕНО
        liked_result = await session.execute(
            select(Like).where(Like.user_id == current_user.id, Like.song_id == song.id)
        )
        is_liked = liked_result.scalar_one_or_none() is not None

        songs_list.append({
            "id": song.id,
            "performer_id": song.performer_id,
            "performer_nickname": performer.nickname if performer else None,
            "name": song.name,
            "style_music": song.style_music,
            "album": song.album,  # ← ДОБАВЛЕНО
            "genre": song.genre,  # ← ДОБАВЛЕНО
            "cover_url": cover_url,
            "audio_url": audio_url,
            "auditions": song.auditions,
            "duration": song.duration,
            "is_liked": is_liked,  # ← ДОБАВЛЕНО
            "created_at": song.created_at
        })

    return {"status": "success", "data": songs_list}


@router.get("/{song_id}", status_code=status.HTTP_200_OK)
async def get_song(
    song_id: int,
    session: SessionDep,
    current_user: User = Depends(get_current_user)  # ← ДОБАВЛЕНО
):
    result = await session.execute(select(Song).where(Song.id == song_id))
    song = result.scalar_one_or_none()
    if not song:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Песня не найдена")

    song.auditions += 1
    await session.commit()

    performer_result = await session.execute(select(Performer).where(Performer.id == song.performer_id))
    performer = performer_result.scalar_one_or_none()
    cover_url = await s3_storage.get_file_url(song.cover) if song.cover else None
    audio_url = await s3_storage.get_file_url(song.audio_path) if song.audio_path else None

    # Проверяем лайк ← ДОБАВЛЕНО
    liked_result = await session.execute(
        select(Like).where(Like.user_id == current_user.id, Like.song_id == song.id)
    )
    is_liked = liked_result.scalar_one_or_none() is not None

    return {
        "status": "success",
        "data": {
            "id": song.id,
            "performer_id": song.performer_id,
            "performer_nickname": performer.nickname if performer else None,
            "name": song.name,
            "style_music": song.style_music,
            "album": song.album,
            "genre": song.genre,
            "cover_url": cover_url,
            "audio_url": audio_url,
            "auditions": song.auditions,
            "duration": song.duration,
            "is_liked": is_liked,
            "created_at": song.created_at
        }
    }


@router.post("/", status_code=status.HTTP_201_CREATED, dependencies=[Depends(current_admin)])
async def create_song(song_data: SongCreate, session: SessionDep):
    performer_result = await session.execute(select(Performer).where(Performer.id == song_data.performer_id))
    if not performer_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Исполнитель не найден")

    new_song = Song(
        performer_id=song_data.performer_id,
        name=song_data.name,
        style_music=song_data.style_music,
        album=song_data.album,
        genre=song_data.genre,
        duration=song_data.duration,
        audio_path=""
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
            "album": new_song.album,
            "genre": new_song.genre,
            "duration": new_song.duration,
            "created_at": new_song.created_at
        }
    }


@router.put("/{song_id}", status_code=status.HTTP_200_OK, dependencies=[Depends(current_admin)])
async def update_song(song_id: int, song_data: SongUpdate, session: SessionDep):
    result = await session.execute(select(Song).where(Song.id == song_id))
    song = result.scalar_one_or_none()
    if not song:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Песня не найдена")

    if song_data.performer_id is not None:
        performer_result = await session.execute(select(Performer).where(Performer.id == song_data.performer_id))
        if not performer_result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Исполнитель не найден")
        song.performer_id = song_data.performer_id
    if song_data.name is not None:
        song.name = song_data.name
    if song_data.style_music is not None:
        song.style_music = song_data.style_music
    if song_data.album is not None:  # ← ДОБАВЛЕНО
        song.album = song_data.album
    if song_data.genre is not None:  # ← ДОБАВЛЕНО
        song.genre = song_data.genre
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
            "album": song.album,  # ← ДОБАВЛЕНО
            "genre": song.genre,  # ← ДОБАВЛЕНО
            "duration": song.duration,
            "created_at": song.created_at
        }
    }


@router.post("/with-files", status_code=status.HTTP_201_CREATED, dependencies=[Depends(current_admin)])
async def create_song_with_files(
    session: SessionDep,
    song_data: str = Form(..., description="JSON строка с данными песни"),
    cover: UploadFile = File(None),
    audio: UploadFile = File(None)
):
    """Создание песни с обложкой и аудио за один запрос"""
    import json

    # Парсим JSON данные
    try:
        data = json.loads(song_data)
    except json.JSONDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Некорректный JSON в song_data")

    # Валидируем обязательные поля
    performer_id = data.get("performer_id")
    name = data.get("name", "").strip()
    style_music = data.get("style_music", "").strip()

    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Название песни обязательно")
    if not style_music:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Стиль музыки обязателен")
    if not performer_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Исполнитель обязателен")

    # Проверяем исполнителя
    performer_result = await session.execute(select(Performer).where(Performer.id == performer_id))
    if not performer_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Исполнитель не найден")

    # Создаём песню
    new_song = Song(
        performer_id=performer_id,
        name=name,
        style_music=style_music,
        album=data.get("album"),
        genre=data.get("genre"),
        duration=data.get("duration"),
        audio_path=""
    )
    session.add(new_song)
    await session.commit()
    await session.refresh(new_song)

    cover_url = None
    audio_url = None
    cover_content = None
    audio_content = None

    # Читаем файлы ЗАРАНЕЕ, до вызова s3_storage
    if cover and cover.filename:
        cover_content = await cover.read()
    if audio and audio.filename:
        audio_content = await audio.read()

    # Загружаем обложку если есть
    if cover_content:
        allowed_formats = ['jpg', 'jpeg', 'png', 'webp']
        file_extension = cover.filename.split('.')[-1].lower() if cover.filename else ''
        if file_extension not in allowed_formats:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Неподдерживаемый формат обложки. Разрешены: {', '.join(allowed_formats)}"
            )

        if len(cover_content) > 5 * 1024 * 1024:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Размер обложки не должен превышать 5MB")

        try:
            cover_path = await s3_storage.upload_song_cover(cover, new_song.name, new_song.id, content=cover_content)
            new_song.cover = cover_path
            cover_url = await s3_storage.get_file_url(cover_path)
        except Exception as e:
            await session.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Ошибка загрузки обложки: {str(e)}")

    # Загружаем аудио если есть
    if audio_content:
        allowed_formats = ['mp3', 'wav', 'ogg', 'm4a']
        file_extension = audio.filename.split('.')[-1].lower() if audio.filename else ''
        if file_extension not in allowed_formats:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Неподдерживаемый формат аудио. Разрешены: {', '.join(allowed_formats)}"
            )

        if len(audio_content) > 20 * 1024 * 1024:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Размер аудио не должен превышать 20MB")

        try:
            audio_path = await s3_storage.upload_song_audio(audio, new_song.name, new_song.id, content=audio_content)
            new_song.audio_path = audio_path
            audio_url = await s3_storage.get_file_url(audio_path)
        except Exception as e:
            await session.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Ошибка загрузки аудио: {str(e)}")

    await session.commit()
    await session.refresh(new_song)

    # Получаем исполнителя для ответа
    performer_result = await session.execute(select(Performer).where(Performer.id == new_song.performer_id))
    performer = performer_result.scalar_one_or_none()

    return {
        "status": "success",
        "message": "Песня успешно создана",
        "data": {
            "id": new_song.id,
            "performer_id": new_song.performer_id,
            "performer_nickname": performer.nickname if performer else None,
            "name": new_song.name,
            "style_music": new_song.style_music,
            "album": new_song.album,
            "genre": new_song.genre,
            "cover_url": cover_url,
            "audio_url": audio_url,
            "duration": new_song.duration,
            "auditions": new_song.auditions,
            "created_at": new_song.created_at
        }
    }


@router.post("/{song_id}/cover", status_code=status.HTTP_200_OK, dependencies=[Depends(current_admin)])
async def upload_song_cover(session: SessionDep, song_id: int, cover: UploadFile = File(...)):
    result = await session.execute(select(Song).where(Song.id == song_id))
    song = result.scalar_one_or_none()
    if not song:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Песня не найдена")

    allowed_formats = ['jpg', 'jpeg', 'png', 'webp']
    file_extension = cover.filename.split('.')[-1].lower() if cover.filename else ''
    if file_extension not in allowed_formats:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Неподдерживаемый формат. Разрешены: {', '.join(allowed_formats)}"
        )

    # Читаем контент ЗДЕСЬ и передаём в s3_storage
    cover_content = await cover.read()
    if len(cover_content) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Файл пустой")
    if len(cover_content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Размер файла не должен превышать 5MB")

    try:
        cover_path = await s3_storage.upload_song_cover(cover, song.name, song_id, content=cover_content)
        song.cover = cover_path
        await session.commit()
        cover_url = await s3_storage.get_file_url(cover_path)
        return {
            "status": "success",
            "message": "Обложка песни успешно загружена",
            "cover_url": cover_url
        }
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Ошибка при загрузке обложки: {str(e)}")


@router.post("/{song_id}/audio", status_code=status.HTTP_200_OK, dependencies=[Depends(current_admin)])
async def upload_song_audio(session: SessionDep, song_id: int, audio: UploadFile = File(...)):
    result = await session.execute(select(Song).where(Song.id == song_id))
    song = result.scalar_one_or_none()
    if not song:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Песня не найдена")

    allowed_formats = ['mp3', 'wav', 'ogg', 'm4a']
    file_extension = audio.filename.split('.')[-1].lower() if audio.filename else ''
    if file_extension not in allowed_formats:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Неподдерживаемый формат. Разрешены: {', '.join(allowed_formats)}"
        )

    # Читаем контент ЗДЕСЬ и передаём в s3_storage
    audio_content = await audio.read()
    if len(audio_content) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Файл пустой")
    if len(audio_content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Размер файла не должен превышать 20MB")

    try:
        audio_path = await s3_storage.upload_song_audio(audio, song.name, song_id, content=audio_content)
        song.audio_path = audio_path
        await session.commit()
        audio_url = await s3_storage.get_file_url(audio_path)
        return {
            "status": "success",
            "message": "Аудио файл успешно загружен",
            "audio_url": audio_url
        }
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Ошибка при загрузке аудио: {str(e)}")


@router.delete("/{song_id}", status_code=status.HTTP_200_OK, dependencies=[Depends(current_admin)])
async def delete_song(song_id: int, session: SessionDep):
    result = await session.execute(select(Song).where(Song.id == song_id))
    song = result.scalar_one_or_none()
    if not song:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Песня не найдена")

    await session.delete(song)
    await session.commit()
    return {"status": "success", "message": "Песня успешно удалена"}
