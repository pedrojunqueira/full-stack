import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import ping, summaries
from app.azure import azure_scheme
from app.config import get_settings
from app.db import init_db

log = logging.getLogger("uvicorn")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.

    Startup: Load Azure AD config
    Shutdown: Clean up resources
    """
    log.info("Starting up...")

    # Load Azure AD OpenID configuration (public keys for JWT validation)
    if azure_scheme:
        log.info("Loading Azure AD OpenID configuration...")
        await azure_scheme.openid_config.load_config()

    yield

    log.info("Shutting down...")


def create_application() -> FastAPI:
    # Configure OAuth2 for Swagger UI
    swagger_ui_init_oauth = None
    if settings.openapi_client_id:
        swagger_ui_init_oauth = {
            "usePkceWithAuthorizationCodeGrant": True,
            "clientId": settings.openapi_client_id,
            "scopes": f"api://{settings.app_client_id}/{settings.scope_description}",
        }

    application = FastAPI(
        title="FastAPI TDD Docker",
        description="A FastAPI application with Azure AD authentication",
        version="1.0.0",
        lifespan=lifespan,
        # OAuth2 redirect endpoint for Swagger
        swagger_ui_oauth2_redirect_url="/oauth2-redirect",
        swagger_ui_init_oauth=swagger_ui_init_oauth,
    )

    # CORS middleware
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.backend_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    application.include_router(ping.router, tags=["Health"])
    application.include_router(
        summaries.router,
        prefix="/summaries",
        tags=["Summaries"],
    )

    # Register Tortoise ORM — must be called here, not inside lifespan,
    # so its startup hooks are registered before the app starts
    init_db(application)

    return application


app = create_application()