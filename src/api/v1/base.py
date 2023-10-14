from typing import List
from fastapi import APIRouter, Depends, Header, UploadFile
from fastapi.security import HTTPBasic
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.entities import File
from src.services.services import FilesStorageService

from src.db.db import get_session

api_router = APIRouter()
security = HTTPBasic()

files_storage_service = FilesStorageService()


@api_router.post('/register', dependencies=[Depends(files_storage_service.check_allowed_ip)])
async def register(username: str, password: str, db: AsyncSession = Depends(get_session)):
    return await files_storage_service.register(username, password, db)


@api_router.post('/auth', dependencies=[Depends(files_storage_service.check_allowed_ip)])
async def auth_user(username: str, password: str, db: AsyncSession = Depends(get_session)):
    return await files_storage_service.auth_user(username, password, db)


@api_router.post('/files/upload', response_model=File, dependencies=[Depends(files_storage_service.check_allowed_ip)])
async def upload_file(file: UploadFile, path: str, authorization: str = Header(None), db: AsyncSession = Depends(get_session)):
    return await files_storage_service.upload_file(file, path, authorization, db)


@api_router.get('/files/download', dependencies=[Depends(files_storage_service.check_allowed_ip)])
async def download_file(file: str, authorization: str = Header(None), db: AsyncSession = Depends(get_session)):
    return await files_storage_service.download_file(file, authorization, db)


@api_router.get('/files', response_model=List[File], dependencies=[Depends(files_storage_service.check_allowed_ip)])
async def user_status(authorization: str = Header(None), db: AsyncSession = Depends(get_session)):
    return await files_storage_service.get_files(authorization, db)


@api_router.get('/ping', dependencies=[Depends(files_storage_service.check_allowed_ip)])
async def ping_services(db: AsyncSession = Depends(get_session)):
    return await files_storage_service.ping_services(db)
