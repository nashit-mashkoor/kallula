from fastapi import APIRouter

from api.commands import router as commands_router
from api.projects import router as projects_router
from api.runs import router as runs_router
from api.session import router as session_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(session_router)
api_router.include_router(commands_router)
api_router.include_router(projects_router)
api_router.include_router(runs_router)
