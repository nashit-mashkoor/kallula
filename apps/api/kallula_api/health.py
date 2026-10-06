from fastapi import APIRouter
from starlette.requests import Request

from kallula_api.db import DatabaseUnavailableError, check_database
from kallula_api.problems import problem_response

router = APIRouter(tags=["health"])


@router.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
async def ready(request: Request):
    try:
        await check_database(request.app.state.engine)
    except DatabaseUnavailableError:
        return problem_response(
            request,
            503,
            title="Service Unavailable",
            detail="The control-state database is not reachable.",
        )
    return {"status": "ready"}
