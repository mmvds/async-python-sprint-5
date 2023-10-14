import asyncio
from datetime import datetime, timedelta
from logging import config as logging_config, getLogger
import uuid
import ipaddress
import socket
import os
import time
import redis

from jose import JWTError, jwt
from passlib.context import CryptContext

from fastapi import HTTPException, Request, Header, Depends, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import DBAPIError

from src.models.entities import User, File, FileItem
from src.core.config import app_settings
from src.core.logger import LOGGING
from src.db.db import get_session, db_init
from src.services.redis import redis_cached_async, redis_client

logger = getLogger(__name__)

logging_config.dictConfig(LOGGING)


class FilesStorageService:
    def __init__(self):
        asyncio.run(db_init())

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    @staticmethod
    async def get_user_id_from_db(username: str, db: AsyncSession):
        user = await db.execute(User.__table__.select().where(User.username == username))
        user = user.fetchone()
        if user:
            return user.id
        return None

    @staticmethod
    def create_access_token(data: dict, expires_delta: timedelta = None):
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=15)
        to_encode['exp'] = expire
        return jwt.encode(
            to_encode, app_settings.secret_token, algorithm=app_settings.algorithm
        )

    async def update_user_tokens(self, user: User, access_token: str, token_expiration_time: datetime,
                                 db: AsyncSession):

        stmt = User.__table__.update().where(User.id == user.id).values(
            access_token=access_token,
            token_expiration_time=token_expiration_time
        )
        await db.execute(stmt)
        await db.commit()

    async def auth_user(self, username: str, password: str, db: AsyncSession):
        user = await db.execute(User.__table__.select().where(User.username == username))
        user = user.fetchone()
        if user is None or not self.pwd_context.verify(password, user['hashed_password']):
            raise HTTPException(status_code=401, detail='Unauthorized')

        access_token_expires = timedelta(minutes=app_settings.access_token_expire_minutes)
        access_token = self.create_access_token(data={'sub': user.username}, expires_delta=access_token_expires)
        token_expiration_time = datetime.utcnow() + access_token_expires

        stmt = User.__table__.update().where(User.id == user.id).values(
            access_token=access_token,
            token_expiration_time=token_expiration_time
        )
        await db.execute(stmt)
        await db.commit()

        return {'access_token': access_token, 'token_type': 'bearer'}

    async def get_authorization_token(self, authorization: str = Header(None), db: AsyncSession = Depends(get_session)):

        if not authorization or not authorization.startswith('Bearer '):
            raise HTTPException(status_code=401, detail='Invalid authorization header')

        token = authorization.replace('Bearer ', '')

        try:
            payload = jwt.decode(token, app_settings.secret_token, algorithms=[app_settings.algorithm])
        except JWTError:
            raise HTTPException(status_code=401, detail='Invalid token')

        if not await self.is_valid_token(payload['sub'], db):
            raise HTTPException(status_code=401, detail='Token has expired')

        return payload

    async def is_valid_token(self, username: str, db: AsyncSession):
        user = await db.execute(User.__table__.select().where(User.username == username))
        user = user.fetchone()
        if user is None or not user.access_token:
            return False

        if user.token_expiration_time and user.token_expiration_time < datetime.utcnow():
            return False

        return True

    async def check_allowed_ip(self, request: Request):
        try:
            real_ip = socket.gethostbyname(request.client.host)
        except socket.gaierror:
            real_ip = '127.0.0.1'
        logger.debug(f'{real_ip=}')
        ip_address = ipaddress.ip_address(real_ip)
        is_banned = any(ip_address in ipaddress.ip_network(network) for network in app_settings.black_list)
        if is_banned:
            raise HTTPException(status_code=403, detail='Forbidden IP')

    async def register(self, username: str, password: str, db: AsyncSession):
        hashed_password = self.pwd_context.hash(password)
        user = User(username=username, hashed_password=hashed_password)
        db.add(user)
        await db.commit()
        return {'detail': 'User registered successfully'}

    async def upload_file(self,
                          file: UploadFile,
                          path: str,
                          authorization: str = Header(None),
                          db: AsyncSession = Depends(get_session)
                          ):
        payload = await self.get_authorization_token(authorization, db)
        user_id = await self.get_user_id_from_db(payload['sub'], db)

        file_id = str(uuid.uuid4())

        if path.endswith('/'):
            path += file.filename
        full_path = f'{app_settings.storage_path}/{user_id}/{path}'.replace('//', '/')
        os.makedirs('/'.join(full_path.split('/')[:-1]), exist_ok=True)
        with open(full_path, 'wb') as f:
            f.write(file.file.read())

        file_record = FileItem(
            id=file_id,
            name=file.filename,
            created_at=datetime.utcnow(),
            path=path,
            size=file.file.tell(),
            is_downloadable=True,
            user_id=user_id
        )

        db.add(file_record)
        await db.commit()

        return File(
            id=file_id,
            name=file.filename,
            created_at=file_record.created_at,
            path=path,
            size=file.file.tell(),
            is_downloadable=True
        )

    @redis_cached_async(arg_slice=slice(1, 3))
    async def download_file(self, file: str, authorization: str, db: AsyncSession):
        payload = await self.get_authorization_token(authorization, db)
        user_id = await self.get_user_id_from_db(payload['sub'], db)

        if '-' in file and len(file) == 36:
            file_record = await db.execute(FileItem.__table__.select().where(FileItem.id == file))
        else:
            file_record = await db.execute(FileItem.__table__.select().where(FileItem.path == file))

        file_record = file_record.fetchone()
        if not file_record:
            raise HTTPException(status_code=404, detail='File not found')

        if file_record.user_id != user_id:
            raise HTTPException(status_code=403, detail='Access denied')

        file_path = f'{app_settings.storage_path}/{user_id}/{file_record.path}'.replace('//', '/')
        return FileResponse(file_path)

    async def get_files(self, authorization: str = Header(None), db: AsyncSession = Depends(get_session)):
        payload = await self.get_authorization_token(authorization, db)
        user_id = await self.get_user_id_from_db(payload["sub"], db)

        files = await db.execute(FileItem.__table__.select().where(FileItem.user_id == user_id))
        if file_records := files.fetchall():
            return [
                File(
                    id=str(file_record.id),
                    name=file_record.name,
                    created_at=file_record.created_at,
                    path=file_record.path,
                    size=file_record.size,
                    is_downloadable=file_record.is_downloadable
                )
                for file_record in file_records
            ]
        else:
            raise HTTPException(status_code=404, detail='No files found for this user')

    async def ping_services(self, db: AsyncSession):
        db_ping_time = await self.ping_database(db)
        cache_ping_time = self.ping_cache()
        storage_ping_time = self.ping_storage()

        return {
            "db": db_ping_time,
            "cache": cache_ping_time,
            "storage": storage_ping_time,
        }

    async def ping_database(self, db: AsyncSession):
        try:
            start_time = time.time()
            await db.execute('SELECT 1')
            end_time = time.time()
            return end_time - start_time
        except DBAPIError:
            return None

    def ping_storage(self):
        try:
            start_time = time.time()
            with open(f'{app_settings.storage_path}/testfile.txt', 'w') as f:
                f.write('test')
            end_time = time.time()
            return end_time - start_time
        except (PermissionError, IOError):
            return None

    def ping_cache(self):
        try:
            start_time = time.time()
            redis_client.ping()
            end_time = time.time()
            return end_time - start_time
        except (redis.ConnectionError, redis.ResponseError):
            return None

