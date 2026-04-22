from fastapi import APIRouter, HTTPException, status, Depends, UploadFile, File, Query
from sqlalchemy import select
from typing import Optional

from api.db import SessionDep
from api.db.models import Performer, Song
from api.dependencies.current_admin import current_admin
from api.storage.s3_storage import s3_storage
from api.performer.models import PerformerCreate, PerformerUpdate

router = APIRouter(prefix="/api/performers", tags=["Performers"])


# список всех исполнителей (доступно всем)
@router.get("/", status_code=status.HTTP_200_OK)
async def get_performers(
        session: SessionDep,
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=100),
        search: Optional[str] = None
):
    query = select(Performer)

    if search:
        query = query.where(Performer.nickname.ilike(f"%{search}%"))

    query = query.offset(skip).limit(limit).order_by(Performer.nickname)
    result = await session.execute(query)
    performers = result.scalars().all()

    performers_list = []
    for performer in performers:
        photo_url = await s3_storage.get_file_url(performer.photo) if performer.photo else None
        performers_list.append({
            "id": performer.id,
            "nickname": performer.nickname,
            "style_music": performer.style_music,
            "photo_url": photo_url,
            "created_at": performer.created_at
        })

    return {
        "status": "success",
        "data": performers_list
    }


# получить исполнителя (доступно всем)
@router.get("/{performer_id}", status_code=status.HTTP_200_OK)
async def get_performer(
        performer_id: int,
        session: SessionDep
):
    result = await session.execute(
        select(Performer).where(Performer.id == performer_id)
    )
    performer = result.scalar_one_or_none()

    if not performer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Исполнитель не найден"
        )

    songs_result = await session.execute(
        select(Song).where(Song.performer_id == performer_id).order_by(Song.name)
    )
    songs = songs_result.scalars().all()

    photo_url = await s3_storage.get_file_url(performer.photo) if performer.photo else None

    songs_list = []
    for song in songs:
        cover_url = await s3_storage.get_file_url(song.cover) if song.cover else None
        audio_url = await s3_storage.get_file_url(song.audio_path) if song.audio_path else None
        songs_list.append({
            "id": song.id,
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
        "data": {
            "id": performer.id,
            "nickname": performer.nickname,
            "style_music": performer.style_music,
            "photo_url": photo_url,
            "created_at": performer.created_at,
            "songs": songs_list
        }
    }


# создать исполнителя (только админ)
@router.post("/", status_code=status.HTTP_201_CREATED, dependencies=[Depends(current_admin())])
async def create_performer(
        performer_data: PerformerCreate,
        session: SessionDep
):
    existing = await session.execute(
        select(Performer).where(Performer.nickname == performer_data.nickname)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Исполнитель с таким nickname уже существует"
        )

    new_performer = Performer(
        nickname=performer_data.nickname,
        style_music=performer_data.style_music
    )

    session.add(new_performer)
    await session.commit()
    await session.refresh(new_performer)

    return {
        "status": "success",
        "message": "Исполнитель успешно создан",
        "data": {
            "id": new_performer.id,
            "nickname": new_performer.nickname,
            "style_music": new_performer.style_music,
            "created_at": new_performer.created_at
        }
    }


# обновить исполнителя (только админ)
@router.put("/{performer_id}", status_code=status.HTTP_200_OK, dependencies=[Depends(current_admin())])
async def update_performer(
        performer_id: int,
        performer_data: PerformerUpdate,
        session: SessionDep
):
    result = await session.execute(
        select(Performer).where(Performer.id == performer_id)
    )
    performer = result.scalar_one_or_none()

    if not performer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Исполнитель не найден"
        )

    if performer_data.nickname is not None:
        existing = await session.execute(
            select(Performer).where(
                Performer.nickname == performer_data.nickname,
                Performer.id != performer_id
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Исполнитель с таким nickname уже существует"
            )
        performer.nickname = performer_data.nickname

    if performer_data.style_music is not None:
        performer.style_music = performer_data.style_music

    await session.commit()
    await session.refresh(performer)

    photo_url = await s3_storage.get_file_url(performer.photo) if performer.photo else None

    return {
        "status": "success",
        "message": "Исполнитель успешно обновлен",
        "data": {
            "id": performer.id,
            "nickname": performer.nickname,
            "style_music": performer.style_music,
            "photo_url": photo_url,
            "created_at": performer.created_at
        }
    }


# загрузить фото (только админ)
@router.post("/{performer_id}/photo", status_code=status.HTTP_200_OK, dependencies=[Depends(current_admin())])
async def upload_performer_photo(
        session: SessionDep,
        performer_id: int,
        photo: UploadFile = File(...),
):
    result = await session.execute(
        select(Performer).where(Performer.id == performer_id)
    )
    performer = result.scalar_one_or_none()

    if not performer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Исполнитель не найден"
        )

    allowed_formats = ['jpg', 'jpeg', 'png', 'gif', 'webp']
    file_extension = photo.filename.split('.')[-1].lower() if photo.filename else ''

    if file_extension not in allowed_formats:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Неподдерживаемый формат. Разрешены: {', '.join(allowed_formats)}"
        )

    content = await photo.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Размер файла не должен превышать 5MB"
        )

    old_photo = performer.photo

    try:
        photo_path = await s3_storage.upload_performer_photo(photo, performer_id)
        performer.photo = photo_path
        await session.commit()

        if old_photo:
            await s3_storage.delete_file(old_photo)

        photo_url = await s3_storage.get_file_url(photo_path)

        return {
            "status": "success",
            "message": "Фото исполнителя успешно загружено",
            "photo_url": photo_url
        }
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при загрузке фото: {str(e)}"
        )


# удалить фото (только админ)
@router.delete("/{performer_id}/photo", status_code=status.HTTP_200_OK, dependencies=[Depends(current_admin())])
async def delete_performer_photo(
        performer_id: int,
        session: SessionDep
):
    result = await session.execute(
        select(Performer).where(Performer.id == performer_id)
    )
    performer = result.scalar_one_or_none()

    if not performer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Исполнитель не найден"
        )

    if not performer.photo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Фото не найдено"
        )

    try:
        await s3_storage.delete_file(performer.photo)
        performer.photo = None
        await session.commit()

        return {
            "status": "success",
            "message": "Фото исполнителя успешно удалено"
        }
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при удалении фото: {str(e)}"
        )


# DELETE /performers/{performer_id} - удалить исполнителя (только админ)
@router.delete("/{performer_id}", status_code=status.HTTP_200_OK, dependencies=[Depends(current_admin())])
async def delete_performer(
        performer_id: int,
        session: SessionDep
):
    result = await session.execute(
        select(Performer).where(Performer.id == performer_id)
    )
    performer = result.scalar_one_or_none()

    if not performer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Исполнитель не найден"
        )

    if performer.photo:
        await s3_storage.delete_file(performer.photo)

    songs_result = await session.execute(
        select(Song).where(Song.performer_id == performer_id)
    )
    songs = songs_result.scalars().all()

    for song in songs:
        if song.cover:
            await s3_storage.delete_file(song.cover)
        if song.audio_path:
            await s3_storage.delete_file(song.audio_path)

    await session.delete(performer)
    await session.commit()

    return {
        "status": "success",
        "message": "Исполнитель и все его песни успешно удалены"
    }