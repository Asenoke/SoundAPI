from aiobotocore.session import get_session
from fastapi import UploadFile
from botocore.config import Config

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
            config=Config(connect_timeout=30, read_timeout=30)
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

    # Определение Content-Type по расширению
    def _get_content_type(self, filename: str, default: str = 'application/octet-stream') -> str:
        if not filename:
            return default
        ext = filename.split('.')[-1].lower()
        content_types = {
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png',
            'gif': 'image/gif',
            'webp': 'image/webp',
            'mp3': 'audio/mpeg',
            'wav': 'audio/wav',
            'ogg': 'audio/ogg',
            'm4a': 'audio/mp4',
            'flac': 'audio/flac',
        }
        return content_types.get(ext, default)

    # Загрузка аватара пользователя
    async def upload_user_avatar(self, file: UploadFile, user_id: int, content: bytes = None) -> str:
        if file.filename:
            extension = file.filename.split('.')[-1].lower()
            if extension == 'jpeg':
                extension = 'jpg'
        else:
            extension = 'jpg'

        file_path = f"avatars/{user_id}.{extension}"

        # Используем переданный content или читаем из файла
        if content is None:
            content = await file.read()

        if len(content) == 0:
            raise ValueError("Файл пустой")

        content_type = self._get_content_type(file.filename, 'image/jpeg')

        async with await self.get_client() as client:
            await client.put_object(
                Bucket=self.bucket_name,
                Key=file_path,
                Body=content,
                ContentType=content_type
            )

        return file_path

    # Загрузка обложки песни
    async def upload_song_cover(self, file: UploadFile, song_name: str, song_id: int, content: bytes = None) -> str:
        extension = self._get_extension(file.filename)
        clean_name = "".join(c for c in song_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        clean_name = clean_name.replace(' ', '_')[:50]
        file_path = f"covers/{song_id}_{clean_name}.{extension}"

        # Используем переданный content или читаем из файла
        if content is None:
            content = await file.read()

        if len(content) == 0:
            raise ValueError("Файл пустой")

        content_type = self._get_content_type(file.filename, 'image/jpeg')

        async with await self.get_client() as client:
            await client.put_object(
                Bucket=self.bucket_name,
                Key=file_path,
                Body=content,
                ContentType=content_type
            )

        return file_path

    # Загрузка аудио файла песни
    async def upload_song_audio(self, file: UploadFile, song_name: str, song_id: int, content: bytes = None) -> str:
        extension = file.filename.split('.')[-1].lower() if file.filename else 'mp3'
        clean_name = "".join(c for c in song_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        clean_name = clean_name.replace(' ', '_')[:50]
        file_path = f"music/{song_id}_{clean_name}.{extension}"

        # Используем переданный content или читаем из файла
        if content is None:
            content = await file.read()

        if len(content) == 0:
            raise ValueError("Файл пустой")

        content_type = self._get_content_type(file.filename, 'audio/mpeg')

        async with await self.get_client() as client:
            await client.put_object(
                Bucket=self.bucket_name,
                Key=file_path,
                Body=content,
                ContentType=content_type
            )

        return file_path

    # Загрузка фото исполнителя
    async def upload_performer_photo(self, file: UploadFile, performer_id: int, content: bytes = None) -> str:
        extension = self._get_extension(file.filename)
        file_path = f"performers/{performer_id}.{extension}"

        # Используем переданный content или читаем из файла
        if content is None:
            content = await file.read()

        if len(content) == 0:
            raise ValueError("Файл пустой")

        content_type = self._get_content_type(file.filename, 'image/jpeg')

        async with await self.get_client() as client:
            await client.put_object(
                Bucket=self.bucket_name,
                Key=file_path,
                Body=content,
                ContentType=content_type
            )

        return file_path

    # Загрузка обложки плейлиста
    async def upload_playlist_cover(self, file: UploadFile, playlist_id: int, playlist_name: str, content: bytes = None) -> str:
        extension = self._get_extension(file.filename)
        clean_name = "".join(c for c in playlist_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        clean_name = clean_name.replace(' ', '_')[:50]
        file_path = f"playlists/{playlist_id}_{clean_name}.{extension}"

        # Используем переданный content или читаем из файла
        if content is None:
            content = await file.read()

        if len(content) == 0:
            raise ValueError("Файл пустой")

        content_type = self._get_content_type(file.filename, 'image/jpeg')

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

    # Получение presigned URL для временного доступа (для приватных бакетов)
    async def get_presigned_url(self, file_path: str, expiration: int = 3600) -> str:
        """Генерирует presigned URL для доступа к файлу"""
        if not file_path:
            return None
        try:
            async with await self.get_client() as client:
                url = await client.generate_presigned_url(
                    'get_object',
                    Params={
                        'Bucket': self.bucket_name,
                        'Key': file_path
                    },
                    ExpiresIn=expiration
                )
                return url
        except Exception as e:
            print(f"Ошибка генерации presigned URL для {file_path}: {e}")
            # Fallback на обычный URL
            return await self.get_file_url(file_path)

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
