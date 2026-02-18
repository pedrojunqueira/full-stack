import logging

from fastapi import FastAPI

from app.api import ping, summaries
from app.db import init_db

log = logging.getLogger("uvicorn")


def create_application() -> FastAPI:
    application = FastAPI(title="FastAPI TDD Docker")

    # Include routers
    application.include_router(ping.router, tags=["Health"])
    application.include_router(
        summaries.router,
        prefix="/summaries",
        tags=["Summaries"],
    )

    # Initialize database (registers startup/shutdown hooks)
    init_db(application)

    return application


app = create_application()


@app.on_event("startup")
async def startup_event():
    log.info("Starting up...")


@app.on_event("shutdown")
async def shutdown_event():
    log.info("Shutting down...")
