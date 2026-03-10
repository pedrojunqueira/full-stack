import logging
import os
from functools import lru_cache

from pydantic_settings import BaseSettings

log = logging.getLogger("uvicorn")


class Settings(BaseSettings):
    environment: str = os.getenv("ENVIRONMENT", "dev")
    testing: bool = os.getenv("TESTING", "0") == "1"
    database_url: str = os.getenv(
        "DATABASE_URL", "postgres://postgres:postgres@backend-db:5432/backend_dev"
    )
    database_test_url: str = os.getenv(
        "DATABASE_TEST_URL", "postgres://postgres:postgres@backend-db:5432/backend_test"
    )

    # Azure AD Configuration
    tenant_id: str = os.getenv("TENANT_ID", "")
    app_client_id: str = os.getenv("APP_CLIENT_ID", "")
    openapi_client_id: str = os.getenv("OPENAPI_CLIENT_ID", "")
    scope_description: str = os.getenv("SCOPE_DESCRIPTION", "user_impersonation")

    # CORS - Add your frontend URLs here
    backend_cors_origins: list[str] = ["http://localhost:3000", "http://localhost:8004"]

    @property
    def is_auth_enabled(self) -> bool:
        """Check if authentication is properly configured."""
        return bool(self.tenant_id and self.app_client_id)


@lru_cache
def get_settings() -> Settings:
    log.info("Loading config settings from the environment...")
    return Settings()
