from fastapi import APIRouter

from config import Settings

router = APIRouter()


@router.get("/ping")
async def pong():
    return {"ping": "pong!", "environment": Settings.environment}
