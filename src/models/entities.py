import uuid
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
from pydantic import BaseModel

from .base import Base


class FileItem(Base):
    __tablename__ = 'files'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(256))
    created_at = Column(DateTime, default=datetime.utcnow)
    path = Column(String(1024))
    size = Column(Integer)
    is_downloadable = Column(Boolean, default=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)


class File(BaseModel):
    id: str
    name: str
    created_at: datetime
    path: str
    size: int
    is_downloadable: bool


class User(Base):
    __tablename__ = 'users'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(32), unique=True, index=True)
    hashed_password = Column(String(256))
    access_token = Column(String(256), nullable=True)
    token_expiration_time = Column(DateTime, nullable=True)
