import pytest
from asyncpg import InvalidCatalogNameError
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.util import greenlet_spawn
from sqlalchemy_utils import database_exists, create_database


from src.models.base import Base
from src.db.db import get_session
from src.core.config import app_settings
from src.main import app

TEST_DATABASE_DSN = f'{app_settings.database_dsn}_test'
tables_created = False

async def override_get_session() -> AsyncSession:
    global tables_created
    engine = create_async_engine(TEST_DATABASE_DSN, echo=True, future=True)

    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    if not tables_created:
        try:
            await greenlet_spawn(database_exists, engine.url)
        except InvalidCatalogNameError:
            await greenlet_spawn(create_database, engine.url)

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        tables_created = True

    async with async_session() as session:
        yield session


app.dependency_overrides[get_session] = override_get_session
credentials = ('testuser', 'testpass')

access_token = ''
test_file_id = ''


@pytest.fixture(scope='session')
def client():
    return TestClient(app)


def test_ping_services(client):
    response = client.get('/api/v1/ping')
    assert response.status_code == 200
    assert len(response.json()) == 3


def test_register_user(client):
    response = client.post('/api/v1/register', params={'username': credentials[0], 'password': credentials[1]})
    assert response.status_code == 200
    assert response.json() == {'detail': 'User registered successfully'}


def test_auth_user(client):
    global access_token
    response = client.post('/api/v1/auth', params={'username': credentials[0], 'password': credentials[1]})
    assert response.status_code == 200

    data = response.json()
    access_token = data['access_token']
    assert 'access_token' in data
    assert 'token_type' in data
    assert data['token_type'] == 'bearer'


def test_upload_file_without_filename(client):
    global test_file_id
    file_data = ('sample1.txt', 'Sample file content 1', 'text/plain')
    files = {'file': file_data}

    response = client.post(
        url='/api/v1/files/upload',
        headers={'Authorization': f'Bearer {access_token}'},
        params={'path': '/upload-folder/'},
        files=files,
    )

    assert response.status_code == 200

    data = response.json()
    test_file_id = data['id']
    assert 'id' in data
    assert 'name' in data
    assert 'created_at' in data
    assert 'path' in data
    assert 'size' in data


def test_upload_file_with_filename(client):
    file_data = ('sample2.txt', 'Sample file content 2', 'text/plain')
    files = {'file': file_data}

    response = client.post(
        url='/api/v1/files/upload',
        headers={'Authorization': f'Bearer {access_token}'},
        params={'path': '/upload-folder/sample_name.txt'},
        files=files,
    )

    assert response.status_code == 200

    data = response.json()
    assert 'id' in data
    assert 'name' in data
    assert 'created_at' in data
    assert 'path' in data
    assert 'size' in data


def test_list_uploaded(client):
    response = client.get(
        url='/api/v1/files',
        headers={'Authorization': f'Bearer {access_token}'},
    )

    assert response.status_code == 200
    assert len(response.json()) == 2


def test_download_file_id(client):
    response = client.get(
        url=f"/api/v1/files/download",
        params={"file": test_file_id},
        headers={"Authorization": f"Bearer {access_token}"}
    )

    assert response.status_code == 200
    assert response.headers.get("content-type") == "text/plain; charset=utf-8"
    assert response.content == b"Sample file content 1"


def test_download_file_name(client):
    response = client.get(
        url=f"/api/v1/files/download",
        params={"file": "/upload-folder/sample_name.txt"},
        headers={"Authorization": f"Bearer {access_token}"}
    )

    assert response.status_code == 200
    assert response.headers.get("content-type") == "text/plain; charset=utf-8"
    assert response.content == b"Sample file content 2"
