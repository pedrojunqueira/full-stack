import os
from unittest.mock import MagicMock

import asyncpg
import pytest
from httpx import ASGITransport, AsyncClient
from tortoise import Tortoise

from app.auth import get_azure_user
from app.config import Settings, get_settings
from app.main import create_application


def get_settings_override():
    return Settings(testing=True)


def get_mock_azure_user():
    """
    Create a mock Azure user for testing.

    This simulates a validated Azure AD token with user claims.
    """
    mock_user = MagicMock()
    mock_user.claims = {
        "preferred_username": "test@example.com",
        "oid": "test-oid-12345-67890",
        "name": "Test User",
        "roles": [],
    }
    return mock_user


@pytest.fixture(scope="module")
def test_app():
    """Create test application with mocked dependencies."""
    app = create_application()

    # Override settings for testing
    app.dependency_overrides[get_settings] = get_settings_override

    # Mock Azure authentication - return a fake validated user
    app.dependency_overrides[get_azure_user] = lambda: get_mock_azure_user()

    return app


@pytest.fixture(scope="function")
async def test_app_with_db(test_app):
    """Create a fresh database for each test."""
    test_db_url = os.getenv(
        "DATABASE_TEST_URL",
        "postgres://postgres:postgres@backend-db:5432/backend_test"
    )

    # Ensure the test database exists (creates it if missing)
    sys_conn = await asyncpg.connect(
        "postgres://postgres:postgres@backend-db:5432/postgres"
    )
    db_exists = await sys_conn.fetchval(
        "SELECT 1 FROM pg_database WHERE datname = 'backend_test'"
    )
    if not db_exists:
        await sys_conn.execute("CREATE DATABASE backend_test")
    await sys_conn.close()

    await Tortoise.init(
        db_url=test_db_url,
        modules={"models": ["app.models.tortoise"]},
    )
    await Tortoise.generate_schemas()

    yield test_app

    # Drop all tables but keep the database — _drop_databases() would delete
    # the entire DB, causing subsequent tests to fail on connection
    conn = Tortoise.get_connection("default")
    await conn.execute_script("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    await Tortoise.close_connections()


@pytest.fixture
async def client(test_app_with_db):
    """Create async HTTP client for testing."""
    async with AsyncClient(
        transport=ASGITransport(app=test_app_with_db),
        base_url="http://test",
    ) as ac:
        yield ac