import os

import pytest
from httpx import ASGITransport, AsyncClient
from tortoise import Tortoise

from app.config import Settings, get_settings
from app.main import create_application


def get_settings_override():
    return Settings(testing=True)


@pytest.fixture(scope="module")
def test_app():
    app = create_application()
    app.dependency_overrides[get_settings] = get_settings_override
    return app


@pytest.fixture(scope="function")
async def test_app_with_db(test_app):
    """Create a fresh database for each test."""
    test_db_url = os.getenv(
        "DATABASE_TEST_URL", "postgres://postgres:postgres@backend-db:5432/backend_test"
    )

    await Tortoise.init(
        db_url=test_db_url,
        modules={"models": ["app.models.tortoise"]},
    )
    await Tortoise.generate_schemas()

    yield test_app

    # Clean up: drop tables but keep the database
    conn = Tortoise.get_connection("default")
    await conn.execute_query("DROP SCHEMA public CASCADE")
    await conn.execute_query("CREATE SCHEMA public")
    await Tortoise.close_connections()


@pytest.fixture
async def client(test_app_with_db):
    async with AsyncClient(
        transport=ASGITransport(app=test_app_with_db),
        base_url="http://test",
    ) as ac:
        yield ac
