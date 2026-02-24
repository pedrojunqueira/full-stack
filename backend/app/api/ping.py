from fastapi import APIRouter

from app.config import get_settings

router = APIRouter()


@router.get("/ping")
async def pong():
    return {"ping": "🏓", 
            "environment": get_settings().environment}
