from aiobotocore.session import get_session
from fastapi import UploadFile

from config import settings


class S3Storage:
    def __init__(self):
        self.bucket_name = settings.AWS_S3_BUCKET_NAME
        self.endpoint_url = settings.AWS_S3_ENDPOINT_URL
        self.access_key = settings.AWS_ACCESS_KEY_ID
        self.secret_key = settings.AWS_SECRET_ACCESS_KEY
        self.region = settings.AWS_REGION

    # Получение клиента S3
    async def get_client(self):
        session = get_session()
        client = session.create_client(
            's3',
            region_name=self.region,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            endpoint_url=self.endpoint_url,
        )
        return client

    # Получение расширения файла
    def _get_extension(self, filename: str) -> str:

        if not filename:
            return 'jpg'
        ext = filename.split('.')[-1].lower()
        if ext in ['jpg', 'jpeg', 'png']:
            return 'jpg' if ext == 'jpeg' else ext
        return 'jpg'

    # Загрузка аватара пользователя (имя = user_id.jpg или user_id.png)
    async def upload_user_avatar(self, file: UploadFile, user_id: int) -> str:
        extension = self._get_extension(file.filename)
        file_path = f"avatars/{user_id}.{extension}"

        content = await file.read()

        async with await self.get_client() as client:
            await client.put_object(
                Bucket=self.bucket_name,
                Key=file_path,
                Body=content,
                ContentType=file.content_type
            )

        return file_path

    # Загрузка обложки песни (имя = song_id.jpg или song_id.png)
    async def upload_song_cover(self, file: UploadFile, song_name: str, song_id: int) -> str:
        extension = self._get_extension(file.filename)
        # Очищаем имя песни для URL (только для читаемости)
        clean_name = "".join(c for c in song_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        clean_name = clean_name.replace(' ', '_')[:50]  # Ограничиваем длину
        file_path = f"covers/{song_id}_{clean_name}.{extension}"

        content = await file.read()

        async with await self.get_client() as client:
            await client.put_object(
                Bucket=self.bucket_name,
                Key=file_path,
                Body=content,
                ContentType=file.content_type
            )

        return file_path

    # Загрузка аудио файла песни
    async def upload_song_audio(self, file: UploadFile, song_name: str, song_id: int) -> str:
        extension = file.filename.split('.')[-1] if file.filename else 'mp3'
        clean_name = "".join(c for c in song_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        clean_name = clean_name.replace(' ', '_')[:50]
        file_path = f"music/{song_id}_{clean_name}.{extension}"

        content = await file.read()

        async with await self.get_client() as client:
            await client.put_object(
                Bucket=self.bucket_name,
                Key=file_path,
                Body=content,
                ContentType='audio/mpeg'
            )

        return file_path

    # загрузка фото
    async def upload_performer_photo(self, file: UploadFile, performer_id: int) -> str:
        extension = self._get_extension(file.filename)
        file_path = f"performers/{performer_id}.{extension}"

        content = await file.read()

        async with await self.get_client() as client:
            await client.put_object(
                Bucket=self.bucket_name,
                Key=file_path,
                Body=content,
                ContentType=file.content_type
            )

        return file_path

    # Загрузка обложки плейлиста
    async def upload_playlist_cover(self, file: UploadFile, playlist_id: int, playlist_name: str) -> str:
        extension = self._get_extension(file.filename)
        clean_name = "".join(c for c in playlist_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        clean_name = clean_name.replace(' ', '_')[:50]
        file_path = f"playlists/{playlist_id}_{clean_name}.{extension}"

        content = await file.read()

        async with await self.get_client() as client:
            await client.put_object(
                Bucket=self.bucket_name,
                Key=file_path,
                Body=content,
                ContentType=file.content_type
            )

        return file_path

    # Получение публичного URL файла
    async def get_file_url(self, file_path: str) -> str:
        return f"{self.endpoint_url}/{self.bucket_name}/{file_path}"

    # Удаление файла из S3
    async def delete_file(self, file_path: str) -> bool:
        try:
            async with await self.get_client() as client:
                await client.delete_object(
                    Bucket=self.bucket_name,
                    Key=file_path
                )
            return True
        except Exception as e:
            print(f"Error deleting file: {e}")
            return False


s3_storage = S3Storage()