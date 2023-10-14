import os
from logging import config as logging_config
from pydantic import BaseSettings, PostgresDsn

from src.core.logger import LOGGING

logging_config.dictConfig(LOGGING)


BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ENV_FILE_PATH = os.path.join(BASE_DIR, '.env')

class AppSettings(BaseSettings):
    storage_path = '/tmp/'
    app_title: str = "Files Storage App"
    database_dsn: PostgresDsn
    database_logging: bool = True
    project_name: str = 'Files Storage'
    project_host: str = '127.0.0.1'
    project_port: int = 8080
    redis_host: str = 'redis'
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str = ''
    access_token_expire_minutes: int = 15
    secret_token: str = ''
    algorithm: str = 'HS256'
    black_list: list = [
        # "127.0.0.1/24"
        "56.24.15.106",
    ]

    class Config:
        env_file = ENV_FILE_PATH


app_settings = AppSettings()
