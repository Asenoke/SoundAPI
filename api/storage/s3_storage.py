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
        if ext in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
            return 'jpg' if ext == 'jpeg' else ext
        return 'jpg'

    # Загрузка аватара пользователя
    async def upload_user_avatar(self, file: UploadFile, user_id: int, content: bytes = None) -> str:
        # Определяем расширение
        if file.filename:
            extension = file.filename.split('.')[-1].lower()
            if extension == 'jpeg':
                extension = 'jpg'
        else:
            extension = 'jpg'

        file_path = f"avatars/{user_id}.{extension}"

        # Если content не передан, читаем файл
        if content is None:
            content = await file.read()

        # Проверяем что content не пустой
        if len(content) == 0:
            raise ValueError("Файл пустой")

        # Определяем Content-Type
        content_type = file.content_type or 'image/jpeg'

        async with await self.get_client() as client:
            await client.put_object(
                Bucket=self.bucket_name,
                Key=file_path,
                Body=content,
                ContentType=content_type
            )

        return file_path

    # Загрузка обложки песни
    async def upload_song_cover(self, file: UploadFile, song_name: str, song_id: int) -> str:
        extension = self._get_extension(file.filename)
        # Очищаем имя песни для URL
        clean_name = "".join(c for c in song_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        clean_name = clean_name.replace(' ', '_')[:50]
        file_path = f"covers/{song_id}_{clean_name}.{extension}"

        content = await file.read()
        content_type = file.content_type or 'image/jpeg'

        async with await self.get_client() as client:
            await client.put_object(
                Bucket=self.bucket_name,
                Key=file_path,
                Body=content,
                ContentType=content_type
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

    # Загрузка фото исполнителя
    async def upload_performer_photo(self, file: UploadFile, performer_id: int) -> str:
        extension = self._get_extension(file.filename)
        file_path = f"performers/{performer_id}.{extension}"

        content = await file.read()
        content_type = file.content_type or 'image/jpeg'

        async with await self.get_client() as client:
            await client.put_object(
                Bucket=self.bucket_name,
                Key=file_path,
                Body=content,
                ContentType=content_type
            )

        return file_path

    # Загрузка обложки плейлиста
    async def upload_playlist_cover(self, file: UploadFile, playlist_id: int, playlist_name: str) -> str:
        extension = self._get_extension(file.filename)
        clean_name = "".join(c for c in playlist_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        clean_name = clean_name.replace(' ', '_')[:50]
        file_path = f"playlists/{playlist_id}_{clean_name}.{extension}"

        content = await file.read()
        content_type = file.content_type or 'image/jpeg'

        async with await self.get_client() as client:
            await client.put_object(
                Bucket=self.bucket_name,
                Key=file_path,
                Body=content,
                ContentType=content_type
            )

        return file_path

    # Получение публичного URL файла
    async def get_file_url(self, file_path: str) -> str:
        if not file_path:
            return None
        return f"{self.endpoint_url}/{self.bucket_name}/{file_path}"

    # Проверка существования файла
    async def file_exists(self, file_path: str) -> bool:
        if not file_path:
            return False

        try:
            async with await self.get_client() as client:
                await client.head_object(
                    Bucket=self.bucket_name,
                    Key=file_path
                )
            return True
        except Exception:
            return False

    # Удаление файла из S3
    async def delete_file(self, file_path: str) -> bool:
        if not file_path:
            print("No file path provided")
            return False

        try:
            async with await self.get_client() as client:
                # Проверяем существует ли файл
                try:
                    await client.head_object(
                        Bucket=self.bucket_name,
                        Key=file_path
                    )
                except Exception as e:
                    print(f"File not found in S3: {file_path}, error: {e}")
                    return True  # Файла нет - считаем что удаление успешно

                # Удаляем файл
                await client.delete_object(
                    Bucket=self.bucket_name,
                    Key=file_path
                )
                print(f"Successfully deleted {file_path} from S3")
                return True

        except Exception as e:
            print(f"Error deleting file {file_path} from S3: {e}")
            return False


s3_storage = S3Storage()