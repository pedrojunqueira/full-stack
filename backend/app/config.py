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


@lru_cache
def get_settings() -> Settings:
    log.info("Loading config settings from the environment...")
    return Settings()