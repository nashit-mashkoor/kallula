from fastapi import APIRouter

from api.commands import router as commands_router
from api.session import router as session_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(session_router)
api_router.include_router(commands_router)
