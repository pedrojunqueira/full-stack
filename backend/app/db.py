import logging
import os

from tortoise import Tortoise
from tortoise.contrib.fastapi import register_tortoise

from app.config import get_settings

log = logging.getLogger("uvicorn")

TORTOISE_ORM = {
    "connections": {
        "default": os.getenv(
            "DATABASE_URL", "postgres://postgres:postgres@backend-db:5432/backend_dev"
        )
    },
    "apps": {
        "models": {
            "models": ["app.models.tortoise", "aerich.models"],
            "default_connection": "default",
        },
    },
}


def init_db(app, generate_schemas: bool = False):
    settings = get_settings()
    db_url = settings.database_test_url if settings.testing else settings.database_url

    register_tortoise(
        app,
        db_url=db_url,
        modules={"models": ["app.models.tortoise"]},
        generate_schemas=generate_schemas,
        add_exception_handlers=True,
    )


async def close_db():
    await Tortoise.close_connections()
